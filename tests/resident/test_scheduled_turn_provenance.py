from __future__ import annotations

import asyncio

from arnold_pipelines.megaplan.resident.agent_loop import AgentResponse
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import (
    InboundEvent,
    OutboundMessage,
    PersistedInboundEvent,
    ResidentRuntime,
)
from arnold_pipelines.megaplan.store import FileStore


class _Runner:
    request = None

    async def run(self, request, tools):
        self.request = request
        return AgentResponse(final_text="audited")


class _Outbound:
    async def send(self, message: OutboundMessage) -> None:
        return None


def _runtime(tmp_path):
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("owner",), burst_idle_delay_s=0, burst_max_delay_s=1
    )
    authorizer = ResidentAuthorizer(config)
    runner = _Runner()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
        runner=runner,
        outbound=_Outbound(),
        project_root=tmp_path,
    )
    return runtime, runner, store


def test_scheduled_turn_uses_exact_inbound_content_without_a_summary_field(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, _ = _runtime(tmp_path)
        await runtime.receive(
            InboundEvent(
                idempotency_key="scheduled:1",
                conversation_key="discord:dm:owner",
                subject=AuthorizationSubject(user_id="owner"),
                content="synthetic audit prompt",
                raw={"source_kind": "scheduled_turn"},
            )
        )
        await runtime.coalescer.flush_all()

        current = runner.request.hot_context["current_request"]
        assert "summary_line" not in current
        assert current["authority"] == "persisted inbound records triggering this turn"
        assert len(current["source_record_ids"]) == 1
        assert '"content": "synthetic audit prompt"' in runner.request.system_prompt
        assert runner.request.launch_origin["applicability"] == "not_applicable"
        assert runner.request.launch_origin["source_kind"] == "scheduled_turn"
        assert runner.request.report_only is False

    asyncio.run(run_case())


def test_scheduled_audit_propagates_report_only_custody(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, _ = _runtime(tmp_path)
        await runtime.receive(
            InboundEvent(
                idempotency_key="scheduled:report-only",
                conversation_key="discord:dm:owner",
                subject=AuthorizationSubject(user_id="owner"),
                content="bounded todo audit",
                raw={"source_kind": "scheduled_turn", "report_only": True},
            )
        )
        await runtime.coalescer.flush_all()

        assert runner.request.report_only is True
        assert runner.request.launch_origin["report_only"] is True

    asyncio.run(run_case())


def test_scheduled_turn_needs_no_parallel_request_summary(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, store = _runtime(tmp_path)
        await runtime.receive(
            InboundEvent(
                idempotency_key="scheduled:missing",
                conversation_key="discord:dm:owner",
                subject=AuthorizationSubject(user_id="owner"),
                content="synthetic audit prompt",
                raw={"source_kind": "scheduled_turn"},
            )
        )
        await runtime.coalescer.flush_all()
        assert runner.request is not None
        assert store.get_resident_conversation_by_key(
            transport="discord", conversation_key="discord:dm:owner"
        ) is not None

    asyncio.run(run_case())


def test_mixed_scheduler_and_discord_burst_cannot_borrow_discord_provenance(tmp_path) -> None:
    runtime, _, _ = _runtime(tmp_path)
    subject = AuthorizationSubject(user_id="owner")
    scheduled = InboundEvent(
        idempotency_key="scheduled:mixed",
        conversation_key="discord:dm:owner",
        subject=subject,
        content="scheduled",
        raw={
            "source_kind": "scheduled_turn",
        },
    )
    discord = InboundEvent(
        idempotency_key="discord:mixed",
        conversation_key="discord:dm:owner",
        subject=subject,
        content="user request",
        raw={"discord_message_id": "1526500000000000000"},
    )
    conversation = type("Conversation", (), {"conversation_key": "discord:dm:owner"})()
    message = type("Message", (), {"id": "msg_mixed"})()
    items = (
        PersistedInboundEvent(scheduled, conversation, message),
        PersistedInboundEvent(discord, conversation, message),
    )

    origin = runtime._managed_subagent_launch_origin(
        items, turn_id="turn_mixed", timezone_name="UTC"
    )

    assert origin["applicability"] == "ambiguous"
    assert origin["source_kind"] == "mixed_scheduler_discord_burst"
