from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from arnold_pipelines.megaplan.resident import subagent as subagent_module
from arnold_pipelines.megaplan.resident.runtime import (
    _managed_completion_verification_prompt,
)
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
DELIVERED_SUMMARY = VERIFIED_SUMMARY


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
        }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _mark_dependency_failed(
    tmp_path: Path,
    manifest_path: Path,
    *,
    predecessor_status: str = "failed",
) -> Path:
    predecessor_run_id = "subagent-dependency"
    predecessor_dir = manifest_path.parent.parent / predecessor_run_id
    predecessor_dir.mkdir()
    predecessor_result = predecessor_dir / "result.md"
    predecessor_result.write_text("partial predecessor finding", encoding="utf-8")
    predecessor_manifest = predecessor_dir / "manifest.json"
    predecessor_manifest.write_text(
        json.dumps(
            {
                "schema_version": "arnold-resident-agent-run-v1",
                "run_kind": "resident_delegated_agent",
                "custodian": "arnold.megaplan.resident",
                "run_id": predecessor_run_id,
                "status": predecessor_status,
                "result_path": str(predecessor_result),
            }
        ),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text())
    manifest.update(
        {
            "status": "failed",
            "terminal_outcome": "failed",
            "error": "queued successor dependency failed closed",
            "error_class": "ResidentSubagentDependencyFailure",
            "queue": {
                "schema_version": "arnold-resident-subagent-queue-v1",
                "state": "dependency_failed",
                "attention": (
                    "predecessor_abandoned"
                    if predecessor_status == "abandoned"
                    else "predecessor_terminal_failure"
                ),
                "failed_predecessor_run_id": predecessor_run_id,
                "predecessor_status": predecessor_status,
                "predecessor_states": [
                    {
                        "run_id": predecessor_run_id,
                        "status": predecessor_status,
                        "result_state": "not_applicable",
                    }
                ],
            },
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return predecessor_manifest


class _AcceptedOutbound:
    def __init__(self, message_id: str = "1526249999999999999") -> None:
        self.message_id = message_id
        self.sent = []

    async def send(self, message) -> None:
        self.sent.append(message)
        message.metadata["discord_message_ids"] = [self.message_id]


def test_scheduled_standalone_completion_delivers_plain_dm_without_reply_metadata(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / ".megaplan/plans/resident-subagents/subagent-standalone"
    run_dir.mkdir(parents=True)
    result_path = run_dir / "result.md"
    result_path.write_text("worker claim", encoding="utf-8")
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "arnold-resident-agent-run-v1",
        "run_kind": "resident_delegated_agent",
        "custodian": "arnold.megaplan.resident",
        "run_id": "subagent-standalone",
        "status": "completed",
        "created_at": "2026-07-20T08:00:00+00:00",
        "project_dir": str(tmp_path),
        "result_path": str(result_path),
        "launch_provenance": {
            "schema_version": "arnold-resident-delegation-provenance-v1",
            "applicability": "not_applicable",
            "transport": "non_discord",
            "source_kind": "schedule",
        },
        "discord_delivery_target": {
            "transport": "discord",
            "conversation_key": "discord:dm:42",
            "mode": "standalone",
        },
        "completion_delivery": {
            "transport": "discord",
            "delivery_mode": "standalone",
            "status": "pending",
            "attempt_count": 0,
            "destination": {"conversation_key": "discord:dm:42"},
            "payload": {
                "content": VERIFIED_SUMMARY,
                "result_kind": "resident_verified_summary",
                "verification_outcome": "success",
            },
        },
        "resident_completion_turn": {
            "status": "completed",
            "verification_outcome": "success",
        },
    }), encoding="utf-8")
    outbound = _AcceptedOutbound()

    result = asyncio.run(sweep_managed_agent_deliveries(
        outbound=outbound, project_root=tmp_path, workspace_root=None
    ))

    assert result.delivered == 1
    assert outbound.sent[0].conversation_key == "discord:dm:42"
    assert "discord_reply_to_message_id" not in outbound.sent[0].metadata
    assert "discord_processing_message_ids" not in outbound.sent[0].metadata
    persisted = json.loads(manifest_path.read_text())
    assert persisted["completion_delivery"]["delivery_evidence"]["delivery_mode"] == "plain"
    assert "reply_target" not in persisted["completion_delivery"]


def test_dependency_failed_owner_delivers_truthful_partial_fallback_exactly_once(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, status="failed", with_verified_payload=False
    )
    _mark_dependency_failed(tmp_path, manifest_path, predecessor_status="failed")
    outbound = _AcceptedOutbound()

    first = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
        )
    )
    second = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
        )
    )

    delivery = json.loads(manifest_path.read_text())["completion_delivery"]
    assert first.delivered == 1
    assert second.delivered == 0
    assert len(outbound.sent) == 1
    assert "did not run because required predecessor subagent-dependency" in (
        outbound.sent[0].content
    )
    assert "non-empty partial result artifact" in outbound.sent[0].content
    assert "Downstream synthesis was not performed" in outbound.sent[0].content
    assert delivery["result_kind"] == "terminal_dependency_failure"
    assert delivery["status"] == "delivered"


def test_abandoned_predecessor_owner_uses_verifier_and_preserves_failure_truth(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, status="failed", with_verified_payload=False
    )
    _mark_dependency_failed(tmp_path, manifest_path, predecessor_status="abandoned")
    calls = 0

    async def verify(_path, manifest):
        nonlocal calls
        calls += 1
        assert manifest["queue"]["failed_predecessor_run_id"] == (
            "subagent-dependency"
        )
        return ManagedCompletionTurnResult(
            final_text=(
                "The predecessor produced partial findings, but it was abandoned; the "
                "synthesis owner never ran. The verification outcome is partial."
            ),
            verification_outcome="partial",
            turn_id="turn_dependency_completion",
            outbound_message_id="msg_dependency_completion",
        )

    outbound = _AcceptedOutbound()
    first = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
            completion_turn_handler=verify,
        )
    )
    second = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
            completion_turn_handler=verify,
        )
    )

    assert first.delivered == 1
    assert second.delivered == 0
    assert calls == 1
    assert len(outbound.sent) == 1
    assert "abandoned" in outbound.sent[0].content
    assert "never ran" in outbound.sent[0].content


def test_dependency_failed_verifier_prompt_requires_partial_and_blocker_truth(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, status="failed", with_verified_payload=False
    )
    _mark_dependency_failed(tmp_path, manifest_path, predecessor_status="abandoned")
    manifest = json.loads(manifest_path.read_text())

    prompt = _managed_completion_verification_prompt(
        manifest_path=manifest_path,
        manifest=manifest,
        source_message="original request",
    )

    assert "Terminal dependency evidence" in prompt
    assert '"failed_predecessor_run_id": "subagent-dependency"' in prompt
    assert '"predecessor_status": "abandoned"' in prompt
    assert "label it as partial/unverified" in prompt
    assert "never claim downstream synthesis ran" in prompt


def test_shared_unknown_terminal_status_is_deliverable(tmp_path: Path) -> None:
    manifest_path = _write_terminal_manifest(
        tmp_path, status="unknown", with_verified_payload=False
    )
    outbound = _AcceptedOutbound()

    result = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=tmp_path,
            workspace_root=None,
        )
    )

    assert result.delivered == 1
    assert len(outbound.sent) == 1
    assert "status: unknown" in outbound.sent[0].content
    assert json.loads(manifest_path.read_text())["completion_delivery"]["status"] == (
        "delivered"
    )


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


def test_multiline_authoritative_request_does_not_rewrite_verified_delivery(tmp_path: Path) -> None:
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
    assert outbound.sent[0].content == VERIFIED_SUMMARY
    payload = json.loads(manifest_path.read_text())["completion_delivery"]["payload"]
    assert payload["content"] == outbound.sent[0].content
    assert payload["result_kind"] == "resident_verified_summary"
    assert len(payload["content_sha256"]) == 64


def test_missing_authoritative_request_does_not_rewrite_verified_delivery(tmp_path: Path) -> None:
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
    assert outbound.sent[0].content == VERIFIED_SUMMARY


def test_ambiguous_authoritative_records_do_not_rewrite_frozen_delivery(
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
    assert outbound.sent[0].content == "delegated claim"


def test_frozen_payload_without_summary_contract_delivers_without_rewriting(
    tmp_path: Path,
) -> None:
    manifest_path = _write_terminal_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    payload = manifest["completion_delivery"]["payload"]
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
    assert result.delivered == 1
    assert outbound.sent[0].content == VERIFIED_SUMMARY
    assert delivery["status"] == "delivered"
    assert delivery["payload"]["content"] == VERIFIED_SUMMARY
