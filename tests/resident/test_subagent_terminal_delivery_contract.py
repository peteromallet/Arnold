from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from arnold_pipelines.megaplan.resident import subagent as subagent_module
from arnold_pipelines.megaplan.resident.subagent import (
    ManagedCompletionTurnResult,
    list_managed_resident_agents,
    sweep_managed_agent_deliveries,
)


SOURCE_RECORD_ID = "msg_deliverycontract1"
CONVERSATION_ID = "rconv_deliverycontract1"
SOURCE_DISCORD_ID = "1526239110321274921"
CONVERSATION_KEY = "discord:dm:42"
VERIFIED_SUMMARY = "Durable completion evidence was verified. The verification outcome is success."
REQUEST_SUMMARY = "Current request: original request"
DELIVERED_SUMMARY = f"{REQUEST_SUMMARY}\n\n{VERIFIED_SUMMARY}"


def _write_terminal_manifest(
    tmp_path: Path,
    *,
    status: str = "completed",
    with_verified_payload: bool = True,
    source_content: object = "original request",
) -> Path:
    resident_root = tmp_path / ".megaplan/resident"
    messages = resident_root / "messages"
    conversations = resident_root / "resident_conversations"
    turns = resident_root / "turns"
    messages.mkdir(parents=True)
    conversations.mkdir(parents=True)
    turns.mkdir(parents=True)
    (messages / f"{SOURCE_RECORD_ID}.json").write_text(
        json.dumps(
            {
                "id": SOURCE_RECORD_ID,
                "conversation_id": CONVERSATION_ID,
                "direction": "inbound",
                "discord_message_id": SOURCE_DISCORD_ID,
                "content": source_content,
            }
        )
    )
    (conversations / f"{CONVERSATION_ID}.json").write_text(
        json.dumps(
            {
                "id": CONVERSATION_ID,
                "transport": "discord",
                "conversation_key": CONVERSATION_KEY,
                "channel_id": "42",
                "dm_user_id": "42",
            }
        )
    )
    # This is deliberately terminal before the delegated worker is terminal.
    # The delivery sweep must not load or resume it.
    (turns / "turn_launchended.json").write_text(
        json.dumps(
            {
                "id": "turn_launchended",
                "status": "completed",
                "triggered_by_message_ids": [SOURCE_RECORD_ID],
                "message_sent": True,
            }
        )
    )

    run_dir = tmp_path / ".megaplan/plans/resident-subagents/subagent-contract"
    run_dir.mkdir(parents=True)
    result_path = run_dir / "result.md"
    result_path.write_text("delegated claim")
    provenance = {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "correlation_id": "discord-corr-delivery-contract",
        "custody_id": "discord-custody-delivery-contract",
        "resident_conversation_id": CONVERSATION_ID,
        "source_record_id": SOURCE_RECORD_ID,
        "conversation_key": CONVERSATION_KEY,
        "discord_message_id": SOURCE_DISCORD_ID,
        "reply_to_message_id": SOURCE_DISCORD_ID,
        "guild_id": None,
        "channel_id": "42",
        "thread_id": None,
        "dm_user_id": "42",
        "resident_turn_id": "turn_launchended",
        "source_kind": "discord_inbound_message",
    }
    delivery = {
        "transport": "discord",
        "status": "pending",
        "attempt_count": 0,
        "custody_id": provenance["custody_id"],
        "outbox_id": "discord-outbox-delivery-contract",
        "idempotency_key": "resident-subagent-completion:subagent-contract",
        "reply_target": {
            "conversation_key": CONVERSATION_KEY,
            "message_id": SOURCE_DISCORD_ID,
            "source_record_id": SOURCE_RECORD_ID,
        },
    }
    manifest = {
        "schema_version": "arnold-resident-agent-run-v1",
        "run_kind": "resident_delegated_agent",
        "custodian": "arnold.megaplan.resident",
        "run_id": "subagent-contract",
        "status": status,
        "created_at": "2026-07-13T14:50:32+00:00",
        "project_dir": str(tmp_path),
        "result_path": str(result_path),
        "request_id": SOURCE_RECORD_ID,
        "source_record_id": SOURCE_RECORD_ID,
        "resident_conversation_id": CONVERSATION_ID,
        "correlation_id": provenance["correlation_id"],
        "custody_id": provenance["custody_id"],
        "launch_provenance": provenance,
        "discord_origin": {
            "transport": "discord",
            "conversation_id": CONVERSATION_ID,
            "conversation_key": CONVERSATION_KEY,
            "message_id": SOURCE_DISCORD_ID,
            "reply_to_message_id": SOURCE_DISCORD_ID,
            "guild_id": None,
            "channel_id": "42",
            "thread_id": None,
            "dm_user_id": "42",
            "reply_target_source_record_id": SOURCE_RECORD_ID,
            "correlation_id": provenance["correlation_id"],
            "custody_id": provenance["custody_id"],
        },
        "completion_delivery": delivery,
    }
    if with_verified_payload:
        manifest["resident_completion_turn"] = {
            "status": "completed",
            "verification_outcome": "success",
            "resident_turn_id": "turn_completion",
        }
        delivery["payload"] = {
            "content": DELIVERED_SUMMARY,
            "content_sha256": "fixture-sha",
            "result_kind": "resident_verified_summary",
            "verification_outcome": "success",
            "request_summary_line": REQUEST_SUMMARY,
            "request_summary_authority": "immutable_inbound_source_record",
        }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


class _AcceptedOutbound:
    def __init__(self, message_id: str = "1526249999999999999") -> None:
        self.message_id = message_id
        self.sent = []

    async def send(self, message) -> None:
        self.sent.append(message)
        message.metadata["discord_message_ids"] = [self.message_id]


def test_launch_turn_can_end_before_verified_terminal_reply(tmp_path: Path) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, status="running", with_verified_payload=False
    )
    manifest = json.loads(manifest_path.read_text())
    assert manifest["launch_provenance"]["resident_turn_id"] == "turn_launchended"
    assert json.loads(
        (tmp_path / ".megaplan/resident/turns/turn_launchended.json").read_text()
    )["status"] == "completed"

    # Simulate the detached worker completing after the launch turn ended.
    manifest["status"] = "completed"
    manifest_path.write_text(json.dumps(manifest))
    handler_calls = 0

    async def verify(_path, _manifest):
        nonlocal handler_calls
        handler_calls += 1
        return ManagedCompletionTurnResult(
            final_text=VERIFIED_SUMMARY,
            verification_outcome="success",
            turn_id="turn_completion",
            outbound_message_id="msg_completion",
        )

    outbound = _AcceptedOutbound()
    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
            completion_turn_handler=verify,
        )
    )

    assert result.delivered == 1
    assert handler_calls == 1
    assert outbound.sent[0].content == DELIVERED_SUMMARY
    assert outbound.sent[0].metadata["discord_reply_to_message_id"] == SOURCE_DISCORD_ID


def test_persisted_outbox_recovers_with_same_payload_and_nonce(tmp_path: Path) -> None:
    manifest_path = _write_terminal_manifest(tmp_path)
    first_now = datetime(2026, 7, 13, 15, 0, tzinfo=timezone.utc)

    class _LostResponseOutbound:
        def __init__(self) -> None:
            self.nonce = None

        async def send(self, message) -> None:
            self.nonce = message.metadata["discord_nonce"]
            raise TimeoutError("provider response unavailable")

    first_outbound = _LostResponseOutbound()
    first = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=first_outbound,
            project_root=tmp_path,
            workspace_root=None,
            now=first_now,
        )
    )
    retry_state = json.loads(manifest_path.read_text())
    Path(retry_state["result_path"]).write_text("later mutable artifact")

    restarted_outbound = _AcceptedOutbound()
    second = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=restarted_outbound,
            project_root=tmp_path,
            workspace_root=None,
            now=first_now + timedelta(seconds=31),
        )
    )

    assert first.retry_pending == 1
    assert second.delivered == 1
    assert restarted_outbound.sent[0].content == DELIVERED_SUMMARY
    assert restarted_outbound.sent[0].metadata["discord_nonce"] == first_outbound.nonce


def test_exact_source_record_and_discord_message_correlation_is_preserved(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(tmp_path)
    outbound = _AcceptedOutbound()
    asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound, project_root=tmp_path, workspace_root=None
        )
    )

    persisted = json.loads(manifest_path.read_text())
    source = json.loads(
        (tmp_path / f".megaplan/resident/messages/{SOURCE_RECORD_ID}.json").read_text()
    )
    assert source["discord_message_id"] == SOURCE_DISCORD_ID
    assert persisted["launch_provenance"]["source_record_id"] == SOURCE_RECORD_ID
    assert persisted["discord_origin"]["reply_to_message_id"] == SOURCE_DISCORD_ID
    assert persisted["completion_delivery"]["reply_target"] == {
        "conversation_key": CONVERSATION_KEY,
        "message_id": SOURCE_DISCORD_ID,
        "source_record_id": SOURCE_RECORD_ID,
    }
    assert outbound.sent[0].metadata["discord_reply_to_message_id"] == SOURCE_DISCORD_ID


def test_only_one_terminal_reply_is_sent_across_repeated_sweeps(tmp_path: Path) -> None:
    _write_terminal_manifest(tmp_path)
    outbound = _AcceptedOutbound()

    first = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound, project_root=tmp_path, workspace_root=None
        )
    )
    second = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound, project_root=tmp_path, workspace_root=None
        )
    )

    assert first.delivered == 1
    assert second.delivered == 0
    assert len(outbound.sent) == 1


def test_missing_provider_acceptance_evidence_is_retry_pending_and_visible(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(tmp_path)

    class _NoProviderIdentityOutbound:
        async def send(self, _message) -> None:
            return None

    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=_NoProviderIdentityOutbound(),
            project_root=tmp_path,
            workspace_root=None,
            now=datetime(2026, 7, 13, 15, 0, tzinfo=timezone.utc),
        )
    )
    delivery = json.loads(manifest_path.read_text())["completion_delivery"]
    visibility = list_managed_resident_agents(
        project_root=tmp_path, workspace_root=None
    )

    assert result.delivered == 0
    assert result.retry_pending == 1
    assert delivery["status"] == "retry_pending"
    assert delivery["last_error_category"] == "provider_acceptance_unknown"
    assert "discord_message_ids" not in delivery
    assert visibility["terminal_delivery_status_counts"] == {"retry_pending": 1}
    assert visibility["delivery_attention_count"] == 1


def test_verification_and_delivery_timestamps_use_actual_transition_times(
    tmp_path: Path, monkeypatch
) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, with_verified_payload=False
    )
    transition_times = iter(
        datetime(2026, 7, 13, 15, minute, tzinfo=timezone.utc)
        for minute in range(4)
    )
    monkeypatch.setattr(
        subagent_module,
        "_delivery_transition_now",
        lambda _fixed: next(transition_times),
    )

    async def verify(_path, _manifest):
        return ManagedCompletionTurnResult(
            final_text=VERIFIED_SUMMARY,
            verification_outcome="success",
            turn_id="turn_completion",
            outbound_message_id="msg_completion",
        )

    asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=_AcceptedOutbound(),
            project_root=tmp_path,
            workspace_root=None,
            completion_turn_handler=verify,
        )
    )
    manifest = json.loads(manifest_path.read_text())

    assert manifest["resident_completion_turn"]["claimed_at"].startswith(
        "2026-07-13T15:00:00"
    )
    assert manifest["resident_completion_turn"]["completed_at"].startswith(
        "2026-07-13T15:01:00"
    )
    assert manifest["completion_delivery"]["last_attempt_at"].startswith(
        "2026-07-13T15:02:00"
    )
    assert manifest["completion_delivery"]["delivered_at"].startswith(
        "2026-07-13T15:03:00"
    )


def test_multiline_authoritative_request_is_first_delivery_line(tmp_path: Path) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path,
        with_verified_payload=False,
        source_content="implement this\nwith tests\tand docs",
    )

    async def verify(_path, _manifest):
        return ManagedCompletionTurnResult(
            final_text=VERIFIED_SUMMARY,
            verification_outcome="success",
        )

    outbound = _AcceptedOutbound()
    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
            completion_turn_handler=verify,
        )
    )

    assert result.delivered == 1
    assert outbound.sent[0].content.splitlines()[0] == (
        "Current request: implement this with tests and docs"
    )
    payload = json.loads(manifest_path.read_text())["completion_delivery"]["payload"]
    assert payload["content"] == outbound.sent[0].content
    assert payload["request_summary_authority"] == "immutable_inbound_source_fallback"


def test_missing_authoritative_request_uses_safe_delivery_fallback(tmp_path: Path) -> None:
    _write_terminal_manifest(
        tmp_path,
        with_verified_payload=False,
        source_content=None,
    )

    async def verify(_path, _manifest):
        return ManagedCompletionTurnResult(
            final_text=VERIFIED_SUMMARY,
            verification_outcome="success",
        )

    outbound = _AcceptedOutbound()
    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
            completion_turn_handler=verify,
        )
    )

    assert result.delivered == 1
    assert outbound.sent[0].content.splitlines()[0] == (
        "Current request: unavailable from the authoritative inbound request"
    )


def test_ambiguous_authoritative_records_use_safe_delivery_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    _write_terminal_manifest(tmp_path, with_verified_payload=False)
    other_store = tmp_path / "other-resident-store"
    other_messages = other_store / "messages"
    other_messages.mkdir(parents=True)
    (other_messages / f"{SOURCE_RECORD_ID}.json").write_text(
        json.dumps(
            {
                "id": SOURCE_RECORD_ID,
                "conversation_id": CONVERSATION_ID,
                "direction": "inbound",
                "discord_message_id": SOURCE_DISCORD_ID,
                "content": "conflicting exact-record content",
            }
        )
    )
    monkeypatch.setenv("MEGAPLAN_RESIDENT_STORE_ROOT", str(other_store))
    outbound = _AcceptedOutbound()

    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
        )
    )

    assert result.delivered == 1
    assert outbound.sent[0].content.splitlines()[0] == (
        "Current request: unavailable from the authoritative inbound request"
    )


def test_frozen_precontract_payload_fails_closed_without_breaking_idempotency(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    payload = manifest["completion_delivery"]["payload"]
    payload.pop("request_summary_line")
    payload.pop("request_summary_authority")
    payload["content"] = VERIFIED_SUMMARY
    manifest_path.write_text(json.dumps(manifest))
    outbound = _AcceptedOutbound()

    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
        )
    )

    delivery = json.loads(manifest_path.read_text())["completion_delivery"]
    assert result.failed == 1
    assert not outbound.sent
    assert delivery["status"] == "failed"
    assert delivery["last_error_category"] == "invalid_completion_payload"
    assert delivery["payload"]["content"] == VERIFIED_SUMMARY
