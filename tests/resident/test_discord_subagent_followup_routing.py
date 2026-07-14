from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

from arnold_pipelines.megaplan.resident import subagent
from arnold_pipelines.megaplan.resident.agent_loop import FakeAgentRunner
from arnold_pipelines.megaplan.resident.auth import AuthorizationSubject, ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.reply_chain import build_reply_provenance
from arnold_pipelines.megaplan.resident.runtime import (
    InboundEvent,
    PersistedInboundEvent,
    ResidentRuntime,
)
from arnold_pipelines.megaplan.store import FileStore, ResidentConversationInput


CONVERSATION_ID = "rconv_followuprouting"
CONVERSATION_KEY = "discord:dm:42"
PARENT_DISCORD_ID = "1001"
RUN_ID = "subagent-20260713-203257-59552356"
SESSION_ID = "019f5d2e-d5da-75f3-a617-4712a1c57cc4"


def _provenance(
    *,
    source_record_id: str,
    discord_message_id: str = PARENT_DISCORD_ID,
    conversation_id: str = CONVERSATION_ID,
) -> dict:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "resident_conversation_id": conversation_id,
        "source_record_id": source_record_id,
        "conversation_key": CONVERSATION_KEY,
        "discord_message_id": discord_message_id,
        "reply_to_message_id": discord_message_id,
        "channel_id": "42",
        "dm_user_id": "42",
        "source_kind": "discord_inbound_message",
    }


def _write_manifest(
    root: Path,
    *,
    source_record_id: str,
    started_at: datetime,
    run_id: str = RUN_ID,
    lineage_root_run_id: str | None = None,
    provenance: dict | None = None,
    conversation_id: str = CONVERSATION_ID,
) -> Path:
    run_dir = root / ".megaplan/plans/resident-subagents" / run_id
    run_dir.mkdir(parents=True)
    log_path = run_dir / "run.log"
    log_path.write_text(f"session id: {SESSION_ID}\n")
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "arnold-managed-agent-run-v2",
                "run_kind": "resident_delegated_agent",
                "custodian": "arnold.megaplan.managed_agent",
                "run_id": run_id,
                "status": "completed",
                "project_dir": str(root),
                "log_path": str(log_path),
                "started_at": started_at.isoformat(),
                "created_at": (started_at - timedelta(seconds=1)).isoformat(),
                "launch_provenance": provenance
                or _provenance(
                    source_record_id=source_record_id,
                    conversation_id=conversation_id,
                ),
                **(
                    {"lineage_root_run_id": lineage_root_run_id}
                    if lineage_root_run_id
                    else {}
                ),
            }
        )
    )
    return manifest_path


def test_exact_fifteen_minute_boundary_is_inclusive_and_expiry_is_not(tmp_path: Path) -> None:
    anchor = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
    _write_manifest(tmp_path, source_record_id="msg_parent", started_at=anchor)

    accepted = subagent.find_discord_followup_target(
        source_record_id="msg_parent",
        discord_message_id=PARENT_DISCORD_ID,
        resident_conversation_id=CONVERSATION_ID,
        conversation_key=CONVERSATION_KEY,
        reply_received_at=anchor + timedelta(minutes=15),
        project_root=tmp_path,
        workspace_root=None,
    )
    expired = subagent.find_discord_followup_target(
        source_record_id="msg_parent",
        discord_message_id=PARENT_DISCORD_ID,
        resident_conversation_id=CONVERSATION_ID,
        conversation_key=CONVERSATION_KEY,
        reply_received_at=anchor + timedelta(minutes=15, microseconds=1),
        project_root=tmp_path,
        workspace_root=None,
    )

    assert accepted is not None
    assert accepted.run_id == RUN_ID
    assert accepted.launch_anchor_field == "started_at"
    assert expired is None


def test_provenance_mismatch_and_multiple_launch_lineages_fail_closed(tmp_path: Path) -> None:
    anchor = datetime(2026, 7, 13, 20, 0, tzinfo=UTC)
    _write_manifest(tmp_path, source_record_id="msg_parent", started_at=anchor)
    mismatch = subagent.find_discord_followup_target(
        source_record_id="msg_other",
        discord_message_id=PARENT_DISCORD_ID,
        resident_conversation_id=CONVERSATION_ID,
        conversation_key=CONVERSATION_KEY,
        reply_received_at=anchor + timedelta(minutes=1),
        project_root=tmp_path,
        workspace_root=None,
    )
    _write_manifest(
        tmp_path,
        source_record_id="msg_parent",
        started_at=anchor + timedelta(seconds=1),
        run_id="subagent-20260713-203258-aaaaaaaa",
    )
    ambiguous = subagent.find_discord_followup_target(
        source_record_id="msg_parent",
        discord_message_id=PARENT_DISCORD_ID,
        resident_conversation_id=CONVERSATION_ID,
        conversation_key=CONVERSATION_KEY,
        reply_received_at=anchor + timedelta(minutes=1),
        project_root=tmp_path,
        workspace_root=None,
    )

    assert mismatch is None
    assert ambiguous is None


def _persisted_reply(tmp_path: Path, *, parent_author: str = "42") -> tuple[ResidentRuntime, PersistedInboundEvent]:
    store = FileStore(tmp_path / "store")
    conversation = store.upsert_resident_conversation(
        ResidentConversationInput(
            conversation_key=CONVERSATION_KEY,
            channel_id="42",
            dm_user_id="42",
        )
    )
    parent_provenance = build_reply_provenance(
        source_message_id=PARENT_DISCORD_ID,
        source_author_id=parent_author,
        conversation_key=CONVERSATION_KEY,
        scope={"dm_user_id": "42"},
        raw_chain=None,
        reference_message_id=None,
        reference_author_id=None,
        reference_content=None,
    )
    parent = store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="original request",
        discord_message_id=PARENT_DISCORD_ID,
        discord_reply_provenance=parent_provenance,
        idempotency_key="parent",
    )
    current_provenance = build_reply_provenance(
        source_message_id="1002",
        source_author_id="42",
        conversation_key=CONVERSATION_KEY,
        scope={"dm_user_id": "42"},
        raw_chain={
            "ancestors": [
                {
                    "message_id": PARENT_DISCORD_ID,
                    "author_id": parent_author,
                    "content": "original request",
                    "status": "available",
                }
            ],
            "chain_complete": True,
            "termination_reason": "root",
        },
        reference_message_id=PARENT_DISCORD_ID,
        reference_author_id=parent_author,
        reference_content="original request",
        stored_parent=parent,
    )
    current = store.create_message(
        epic_id=None,
        conversation_id=conversation.id,
        direction="inbound",
        content="new direction",
        discord_message_id="1002",
        discord_reply_provenance=current_provenance,
        idempotency_key="current",
    )
    event = InboundEvent(
        idempotency_key="discord:message:1002",
        conversation_key=CONVERSATION_KEY,
        subject=AuthorizationSubject(user_id="42", channel_id="42"),
        content="new direction",
        raw={
            "discord_message_id": "1002",
            "discord_reference_message_id": PARENT_DISCORD_ID,
            "dm_user_id": "42",
        },
    )
    config = ResidentConfig(allowed_user_ids=("42",), burst_idle_delay_s=0)
    authorizer = ResidentAuthorizer(config)

    class Outbound:
        def __init__(self) -> None:
            self.processing: list[list[str]] = []

        async def send(self, _message) -> None:
            return None

        async def mark_processing(self, **kwargs) -> None:
            self.processing.append(kwargs["message_ids"])

    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(store=store, authorizer=authorizer, config=config),
        runner=FakeAgentRunner([]),
        outbound=Outbound(),
        project_root=tmp_path,
    )
    return runtime, PersistedInboundEvent(event, conversation, current)


def test_reply_to_own_message_routes_with_immutable_new_message_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    runtime, persisted = _persisted_reply(tmp_path)
    parent = runtime.store.find_conversation_message_by_discord_id(
        persisted.conversation.id, PARENT_DISCORD_ID
    )
    assert parent is not None
    _write_manifest(
        tmp_path,
        source_record_id=parent.id,
        started_at=persisted.message.sent_at - timedelta(minutes=1),
        conversation_id=persisted.conversation.id,
    )
    monkeypatch.chdir(tmp_path)
    captured: dict = {}

    def fake_followup(**kwargs):
        captured.update(kwargs)
        return subagent.SubagentFollowupResult(
            ok=True,
            followup_id="followup-test",
            target_run_id=RUN_ID,
            parent_run_id=RUN_ID,
            lineage_root_run_id=RUN_ID,
            continuation_run_id="subagent-20260713-203300-bbbbbbbb",
            status="continuation_started",
            evidence_path="evidence.json",
            message_path="message.md",
            continuation_manifest_path="manifest.json",
        )

    monkeypatch.setattr(subagent, "follow_up_managed_subagent", fake_followup)

    routed = asyncio.run(runtime._route_discord_managed_followup(persisted))

    assert routed is True
    assert captured["run_id"] == RUN_ID
    assert captured["message"] == "new direction"
    assert captured["caller_provenance"]["source_record_id"] == persisted.message.id
    assert captured["caller_provenance"]["discord_message_id"] == "1002"
    assert runtime.outbound.processing == [["1002"]]


def test_receive_intercepts_eligible_discord_reply_before_fresh_resident_turn(
    tmp_path: Path, monkeypatch
) -> None:
    runtime, persisted = _persisted_reply(tmp_path)
    parent = runtime.store.find_conversation_message_by_discord_id(
        persisted.conversation.id, PARENT_DISCORD_ID
    )
    assert parent is not None
    _write_manifest(
        tmp_path,
        source_record_id=parent.id,
        started_at=persisted.message.sent_at - timedelta(minutes=1),
        conversation_id=persisted.conversation.id,
    )
    captured: list[dict] = []

    def fake_followup(**kwargs):
        captured.append(kwargs)
        return subagent.SubagentFollowupResult(
            ok=True,
            followup_id="followup-inbound",
            target_run_id=RUN_ID,
            parent_run_id=RUN_ID,
            lineage_root_run_id=RUN_ID,
            continuation_run_id="subagent-20260713-203301-cccccccc",
            status="continuation_started",
            evidence_path="evidence.json",
            message_path="message.md",
            continuation_manifest_path="manifest.json",
        )

    monkeypatch.setattr(subagent, "follow_up_managed_subagent", fake_followup)
    event = InboundEvent(
        idempotency_key="discord:message:1003",
        conversation_key=CONVERSATION_KEY,
        subject=AuthorizationSubject(user_id="42", channel_id="42"),
        content="route this before starting a new resident turn",
        raw={
            "discord_message_id": "1003",
            "discord_reference_message_id": PARENT_DISCORD_ID,
            "discord_reference_author_id": "42",
            "discord_reference_content": "original request",
            "discord_reply_chain": {
                "ancestors": [
                    {
                        "message_id": PARENT_DISCORD_ID,
                        "author_id": "42",
                        "content": "original request",
                        "status": "available",
                    }
                ],
                "chain_complete": True,
                "termination_reason": "root",
            },
            "dm_user_id": "42",
        },
    )

    asyncio.run(runtime.receive(event))

    assert len(captured) == 1
    assert captured[0]["message"] == event.content
    assert captured[0]["caller_provenance"]["discord_message_id"] == "1003"
    assert runtime.store.list_recent_turns(n=10) == []


def test_non_own_reply_and_missing_session_use_safe_normal_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    runtime, not_own = _persisted_reply(tmp_path / "not-own", parent_author="99")
    assert asyncio.run(runtime._route_discord_managed_followup(not_own)) is False

    runtime, persisted = _persisted_reply(tmp_path / "missing-session")
    parent = runtime.store.find_conversation_message_by_discord_id(
        persisted.conversation.id, PARENT_DISCORD_ID
    )
    assert parent is not None
    _write_manifest(
        tmp_path / "missing-session",
        source_record_id=parent.id,
        started_at=persisted.message.sent_at - timedelta(minutes=1),
        conversation_id=persisted.conversation.id,
    )
    monkeypatch.chdir(tmp_path / "missing-session")
    monkeypatch.setattr(
        subagent,
        "follow_up_managed_subagent",
        lambda **_kwargs: (_ for _ in ()).throw(
            subagent.SubagentFollowupError("terminal target has no persistent session")
        ),
    )

    assert asyncio.run(runtime._route_discord_managed_followup(persisted)) is False
