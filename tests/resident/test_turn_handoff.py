from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident import profile as profile_module
from arnold_pipelines.megaplan.resident.agent_loop import (
    AgentRequest,
    FakeAgentRunner,
    FakeAgentStep,
    OpenAICompatibleAgentRunner,
)
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import InboundEvent, OutboundMessage, ResidentRuntime
from arnold_pipelines.megaplan.resident.subagent import SubagentResult
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistration, ToolRegistry
from arnold_pipelines.megaplan.resident.tool_schemas import ToolInput, ToolResult
from arnold_pipelines.megaplan.store import FileStore


class _LaunchInput(ToolInput):
    task: str
    continue_turn: bool = False


class _EmptyInput(ToolInput):
    pass


def _discord_request() -> AgentRequest:
    return AgentRequest(
        conversation_id="conversation-1",
        messages=({"role": "user", "content": "delegate it"},),
        system_prompt="test",
        launch_origin={
            "transport": "discord",
            "applicability": "applicable",
            "reply_to_message_id": "1525000000000000001",
        },
    )


def _tools(*, launch_ok: bool = True) -> tuple[ToolRegistry, list[str]]:
    registry = ToolRegistry()
    polled: list[str] = []

    def launch(payload: _LaunchInput) -> ToolResult:
        if not launch_ok:
            return ToolResult(ok=False, message="launch failed", data={"error": "boom"})
        return ToolResult(
            ok=True,
            message="subagent launched",
            data={
                "run_id": f"subagent-{payload.task}",
                "status": "running",
                "manifest_path": f"/runs/subagent-{payload.task}/manifest.json",
            },
        )

    def poll(_payload: _EmptyInput) -> ToolResult:
        polled.append("poll")
        return ToolResult(ok=True, message="still running")

    registry.register(
        ToolRegistration(
            "launch_subagent",
            "launch",
            "write",
            _LaunchInput,
            ToolResult,
            launch,
        )
    )
    registry.register(
        ToolRegistration("poll", "poll", "read", _EmptyInput, ToolResult, poll)
    )
    return registry, polled


def test_successful_durable_launch_finishes_before_poll_or_duplicate_result() -> None:
    tools, polled = _tools()
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("launch_subagent", {"task": "alpha"}),
            FakeAgentStep.call("poll"),
            FakeAgentStep.final("The delegated work is complete."),
        ]
    )

    response = asyncio.run(runner.run(_discord_request(), tools))

    assert response.final_text == (
        "Launched resident-managed run `subagent-alpha`. "
        "Terminal results will reply automatically to this message."
    )
    assert response.metadata["turn_handoff"] == "durable_subagents"
    assert response.metadata["launched_run_ids"] == ["subagent-alpha"]
    assert [call.tool_name for call in response.tool_calls] == ["launch_subagent"]
    assert polled == []


@pytest.mark.parametrize(
    ("launch_ok", "arguments", "final_text"),
    [
        (False, {"task": "alpha"}, "The launch failed; no work was started."),
        (
            True,
            {"task": "alpha", "continue_turn": True},
            "I need the required human input before the same-turn follow-up.",
        ),
    ],
)
def test_launch_failure_or_explicit_same_turn_work_keeps_turn_open(
    launch_ok: bool,
    arguments: dict[str, object],
    final_text: str,
) -> None:
    tools, _polled = _tools(launch_ok=launch_ok)
    runner = FakeAgentRunner(
        [FakeAgentStep.call("launch_subagent", arguments), FakeAgentStep.final(final_text)]
    )

    response = asyncio.run(runner.run(_discord_request(), tools))

    assert response.final_text == final_text
    assert "turn_handoff" not in response.metadata
    assert len(response.tool_calls) == 1


def test_sequential_launches_acknowledge_all_runs_after_explicit_final_handoff() -> None:
    tools, polled = _tools()
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call(
                "launch_subagent", {"task": "alpha", "continue_turn": True}
            ),
            FakeAgentStep.call("launch_subagent", {"task": "beta"}),
            FakeAgentStep.call("poll"),
        ]
    )

    response = asyncio.run(runner.run(_discord_request(), tools))

    assert response.final_text == (
        "Launched resident-managed runs `subagent-alpha`, `subagent-beta`. "
        "Terminal results will reply automatically to this message."
    )
    assert response.metadata["launched_run_ids"] == ["subagent-alpha", "subagent-beta"]
    assert polled == []


def test_live_tool_loop_does_not_request_another_model_step_after_parallel_launches() -> None:
    tools, _polled = _tools()

    class Completions:
        def __init__(self) -> None:
            self.calls = 0

        async def create(self, **_kwargs):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("resident requested a second model step after handoff")
            tool_calls = [
                SimpleNamespace(
                    id=f"call-{task}",
                    function=SimpleNamespace(
                        name="launch_subagent",
                        arguments=json.dumps({"task": task}),
                    ),
                )
                for task in ("alpha", "beta")
            ]
            message = SimpleNamespace(content=None, tool_calls=tool_calls)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    completions = Completions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    runner = OpenAICompatibleAgentRunner(
        ResidentConfig(), client_override=client, model_override="gpt-5.6-terra"
    )

    response = asyncio.run(runner.run(_discord_request(), tools))

    assert completions.calls == 1
    assert response.metadata["launched_run_ids"] == ["subagent-alpha", "subagent-beta"]
    assert response.final_text.startswith("Launched resident-managed runs")


def test_runtime_ack_and_terminal_custody_keep_exact_inbound_reply_owner(
    tmp_path, monkeypatch
) -> None:
    source_discord_message_id = "1525000000000000001"
    captured_launches: list[dict[str, object]] = []

    async def fake_launch(_config, **kwargs) -> SubagentResult:
        captured_launches.append(kwargs)
        return SubagentResult(
            ok=True,
            final_text="",
            stderr="",
            returncode=0,
            run_id="subagent-exact-owner",
            status="running",
            manifest_path="/runs/subagent-exact-owner/manifest.json",
        )

    class CapturingOutbound:
        def __init__(self) -> None:
            self.sent: list[OutboundMessage] = []

        async def mark_processing(self, **_kwargs) -> None:
            return None

        async def send(self, message: OutboundMessage) -> None:
            self.sent.append(message)

    monkeypatch.setattr(profile_module, "launch_subagent_task", fake_launch)
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("user-1",),
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    authorizer = ResidentAuthorizer(config)
    outbound = CapturingOutbound()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
        runner=FakeAgentRunner(
            [
                FakeAgentStep.call("launch_subagent", {"task": "do it"}),
                FakeAgentStep.final("duplicate terminal result"),
            ]
        ),
        outbound=outbound,
    )

    async def run_case() -> None:
        await runtime.receive(
            InboundEvent(
                idempotency_key=f"discord:message:{source_discord_message_id}",
                conversation_key="discord:guild:12:channel:34",
                subject=AuthorizationSubject(
                    user_id="user-1", guild_id="12", channel_id="34"
                ),
                content="please do it",
                raw={"discord_message_id": source_discord_message_id},
            )
        )
        await runtime.coalescer.flush_all()

    asyncio.run(run_case())

    assert len(captured_launches) == 1
    origin = captured_launches[0]["launch_origin"]
    assert isinstance(origin, dict)
    assert origin["reply_to_message_id"] == source_discord_message_id
    assert origin["discord_message_id"] == source_discord_message_id
    assert origin["source_record_id"].startswith("msg_")
    assert len(outbound.sent) == 1
    acknowledgement = outbound.sent[0]
    assert acknowledgement.metadata["discord_reply_to_message_id"] == source_discord_message_id
    assert acknowledgement.metadata["discord_processing_continues"] is True
    assert acknowledgement.content == (
        "Launched resident-managed run `subagent-exact-owner`. "
        "Terminal results will reply automatically to this message."
    )
