from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from agentbox.reset_notifications import (
    RESET_FALLBACK_CONVERSATION_ENV,
    list_reset_notifications,
    mark_reset_failed,
    mark_reset_succeeded,
    prepare_reset_notification,
    reconcile_prepared_reset_notifications,
    sweep_reset_notifications,
    ResetNotificationError,
)
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


def _discord_provenance() -> dict[str, object]:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "resident_conversation_id": "rconv-source",
        "source_record_id": "msg-source",
        "conversation_key": "discord:dm:301463647895683072",
        "discord_message_id": "1525445255711952977",
        "reply_to_message_id": "1525445255711952977",
        "dm_user_id": "301463647895683072",
        "source_kind": "discord_inbound_message",
    }


class _Outbound:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.sent = []

    async def send(self, message) -> None:
        self.sent.append(message)
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("provider connection dropped token=not-persisted")
        message.metadata["discord_message_ids"] = [f"reply-{len(self.sent)}"]


class _IdempotentOutbound:
    def __init__(self) -> None:
        self.attempts = []
        self.visible_by_nonce = {}
        self.drop_first_response = True

    async def send(self, message) -> None:
        self.attempts.append(message)
        nonce = message.metadata["discord_nonce"]
        message_id = self.visible_by_nonce.setdefault(
            nonce, f"reply-{len(self.visible_by_nonce) + 1}"
        )
        message.metadata["discord_message_ids"] = [message_id]
        if self.drop_first_response:
            self.drop_first_response = False
            raise ConnectionError("response lost after provider acceptance")


class _BlockingOutbound:
    def __init__(self) -> None:
        self.sent = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def send(self, message) -> None:
        self.sent.append(message)
        self.entered.set()
        await self.release.wait()
        message.metadata["discord_message_ids"] = ["reply-concurrent"]


def test_restart_delivers_exactly_one_terminal_reply_across_repeated_sweeps(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    mark_reset_succeeded(
        reservation,
        restart_evidence={"service": "agentbox-discord-resident", "backend": "tmux"},
        now=now,
    )
    outbound = _Outbound()

    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )
    second = asyncio.run(
        sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=now + timedelta(minutes=1),
        )
    )

    assert first.delivered == 1
    assert second.delivered == 0
    assert len(outbound.sent) == 1
    message = outbound.sent[0]
    assert message.conversation_key == "discord:dm:301463647895683072"
    assert message.metadata["discord_reply_to_message_id"] == "1525445255711952977"
    assert message.metadata["resident_reset_notification"] is True
    assert message.metadata["resident_reset_notification_phase"] == "terminal"
    assert message.metadata["resident_reset_notification_outcome"] == "succeeded"
    assert message.content == "Discord resident restart complete."
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"delivered": 1}
    assert state["records"][0]["acknowledgement"] == {}
    assert state["records"][0]["delivery"]["discord_message_ids"] == ["reply-1"]


def test_manual_reset_uses_truthful_non_reply_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    monkeypatch.setenv(RESET_FALLBACK_CONVERSATION_ENV, "discord:dm:301463647895683072")
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    mark_reset_succeeded(reservation, restart_evidence={"backend": "systemd"}, now=now)
    outbound = _Outbound()

    result = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )

    assert result.delivered == 1
    assert len(outbound.sent) == 1
    assert outbound.sent[0].conversation_key == "discord:dm:301463647895683072"
    assert "discord_reply_to_message_id" not in outbound.sent[0].metadata
    assert outbound.sent[0].metadata["resident_reset_notification_phase"] == "terminal"
    assert "fallback notification" in outbound.sent[0].content
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["provenance_mode"] == "manual_or_non_discord"
    assert state["acknowledgement"] == {}
    assert state["delivery"]["status"] == "delivered"


def test_reset_delivery_retry_is_provider_idempotent_with_stable_nonce(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    first_now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=first_now)
    mark_reset_succeeded(reservation, restart_evidence={"backend": "tmux"}, now=first_now)
    outbound = _IdempotentOutbound()

    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=first_now)
    )
    retry_record = list_reset_notifications(notification_root=tmp_path)["records"][0]
    retry = retry_record["delivery"]
    second = asyncio.run(
        sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=first_now + timedelta(seconds=31),
        )
    )
    delivered = list_reset_notifications(notification_root=tmp_path)["records"][0]["delivery"]

    assert first.retry_pending == 1
    assert retry["status"] == "retry_pending"
    assert retry["attempt_count"] == 1
    assert "not-persisted" not in retry["last_error"]
    assert second.delivered == 1
    assert delivered["status"] == "delivered"
    assert delivered["attempt_count"] == 2
    assert len(outbound.attempts) == 2
    assert len(outbound.visible_by_nonce) == 1
    assert (
        outbound.attempts[0].metadata["discord_nonce"]
        == outbound.attempts[1].metadata["discord_nonce"]
    )


def test_concurrent_and_repeated_sweeps_issue_one_terminal_send(
    tmp_path, monkeypatch
) -> None:
    async def run_case() -> None:
        monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
        now = datetime(2026, 7, 11, tzinfo=UTC)
        reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
        mark_reset_succeeded(
            reservation, restart_evidence={"backend": "tmux"}, now=now
        )
        outbound = _BlockingOutbound()

        first_task = asyncio.create_task(
            sweep_reset_notifications(
                outbound=outbound, notification_root=tmp_path, now=now
            )
        )
        await outbound.entered.wait()
        concurrent = await sweep_reset_notifications(
            outbound=outbound, notification_root=tmp_path, now=now
        )
        assert concurrent.delivered == 0
        assert len(outbound.sent) == 1

        outbound.release.set()
        first = await first_task
        repeated = await sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=now + timedelta(minutes=1),
        )

        assert first.delivered == 1
        assert repeated.delivered == 0
        assert len(outbound.sent) == 1

    asyncio.run(run_case())


def test_legacy_pending_acceptance_is_suppressed_not_delivered(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    legacy = json.loads(reservation.path.read_text())
    legacy["acknowledgement"] = {
        "transport": "discord",
        "status": "pending",
        "attempt_count": 0,
        "idempotency_key": f"legacy-accepted:{reservation.notification_id}",
        "discord_nonce": "legacy-accepted-nonce",
        "content": "Discord resident restart accepted.",
        "reply_target": dict(legacy["delivery"]["reply_target"]),
    }
    reservation.path.write_text(json.dumps(legacy))
    mark_reset_succeeded(
        reservation, restart_evidence={"backend": "tmux"}, now=now
    )
    outbound = _Outbound()

    result = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )

    assert result.delivered == 1
    assert len(outbound.sent) == 1
    assert outbound.sent[0].metadata["resident_reset_notification_phase"] == "terminal"
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["acknowledgement"]["status"] == "suppressed"
    assert state["delivery"]["status"] == "delivered"


def test_failed_restart_delivers_exactly_one_truthful_terminal_outcome(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    mark_reset_failed(
        reservation,
        restart_evidence={"backend": "tmux", "error": "replacement unhealthy"},
        now=now,
    )
    outbound = _Outbound()

    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )
    second = asyncio.run(
        sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=now + timedelta(minutes=1),
        )
    )

    assert first.delivered == 1
    assert second.delivered == 0
    assert len(outbound.sent) == 1
    message = outbound.sent[0]
    assert message.metadata["resident_reset_notification_phase"] == "terminal"
    assert message.metadata["resident_reset_notification_outcome"] == "failed"
    assert message.content == (
        "Discord resident restart failed. The replacement process was not verified."
    )


def test_legacy_non_deliverable_failure_is_suppressed_without_delivery(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    mark_reset_failed(
        reservation,
        restart_evidence={"backend": "systemd", "error": "identity unchanged"},
        now=now,
    )
    legacy = json.loads(reservation.path.read_text())
    legacy.pop("notification_contract")
    legacy["delivery"]["status"] = "restart_failed"
    reservation.path.write_text(json.dumps(legacy))
    outbound = _Outbound()

    result = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )

    assert result.delivered == 0
    assert len(outbound.sent) == 0
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["delivery"]["status"] == "suppressed"
    assert any(
        item["evidence"] == "legacy_backlog_suppressed_on_single_terminal_upgrade"
        for item in state["delivery"]["state_history"]
    )


def test_repeated_failure_finalization_does_not_rearm_delivered_outcome(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=now)
    evidence = {"backend": "systemd", "error": "replacement unhealthy"}
    mark_reset_failed(reservation, restart_evidence=evidence, now=now)
    outbound = _Outbound()
    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=now)
    )

    mark_reset_failed(
        reservation,
        restart_evidence=evidence,
        now=now + timedelta(seconds=1),
    )
    repeated = asyncio.run(
        sweep_reset_notifications(
            outbound=outbound,
            notification_root=tmp_path,
            now=now + timedelta(minutes=1),
        )
    )

    assert first.delivered == 1
    assert repeated.delivered == 0
    assert len(outbound.sent) == 1
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["delivery"]["status"] == "delivered"


def test_prepared_record_reconciles_from_changed_identity_idempotently(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    reservation = prepare_reset_notification(
        notification_root=tmp_path,
        restart_request={
            "service": "agentbox-discord-resident",
            "backend": "tmux",
            "old_identity": {"backend": "tmux", "pane_pid": 101},
        },
    )

    first = reconcile_prepared_reset_notifications(
        notification_root=tmp_path,
        current_identity={"backend": "tmux", "pane_pid": 202},
    )
    second = reconcile_prepared_reset_notifications(
        notification_root=tmp_path,
        current_identity={"backend": "tmux", "pane_pid": 202},
    )

    assert first == {"scanned": 1, "succeeded": 1, "failed": 0, "in_progress": 0}
    assert second == {"scanned": 0, "succeeded": 0, "failed": 0, "in_progress": 0}
    record = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert record["restart"]["status"] == "succeeded"
    assert record["restart"]["evidence"]["finalized_by"] == (
        "replacement_startup_reconciliation"
    )
    assert record["delivery"]["status"] == "pending"
    assert reservation.notification_id == record["notification_id"]


def test_prepared_record_with_unchanged_identity_fails_safe_and_releases_fence(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    prepare_reset_notification(
        notification_root=tmp_path,
        restart_request={
            "backend": "systemd",
            "old_identity": {"backend": "systemd", "main_pid": 303},
        },
    )

    result = reconcile_prepared_reset_notifications(
        notification_root=tmp_path,
        current_identity={"backend": "systemd", "main_pid": 303},
    )
    replacement = prepare_reset_notification(
        notification_root=tmp_path,
        restart_request={
            "backend": "systemd",
            "old_identity": {"backend": "systemd", "main_pid": 303},
        },
    )

    assert result == {"scanned": 1, "succeeded": 0, "failed": 1, "in_progress": 0}
    records = list_reset_notifications(notification_root=tmp_path)["records"]
    failed = next(row for row in records if row["notification_id"] != replacement.notification_id)
    assert failed["restart"]["status"] == "failed"
    assert failed["delivery"]["status"] == "pending"


def test_legacy_prepared_record_reconciles_failure_without_arming_backlog(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    reservation = prepare_reset_notification(
        notification_root=tmp_path,
        restart_request={
            "backend": "systemd",
            "old_identity": {"backend": "systemd", "main_pid": 303},
        },
    )
    legacy = json.loads(reservation.path.read_text())
    legacy.pop("notification_contract")
    reservation.path.write_text(json.dumps(legacy))

    result = reconcile_prepared_reset_notifications(
        notification_root=tmp_path,
        current_identity={"backend": "systemd", "main_pid": 303},
    )
    outbound = _Outbound()
    sweep = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path)
    )

    assert result == {"scanned": 1, "succeeded": 0, "failed": 1, "in_progress": 0}
    assert sweep.delivered == 0
    assert outbound.sent == []
    record = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert record["restart"]["status"] == "failed"
    assert record["delivery"]["status"] == "suppressed"


def test_duplicate_restart_from_same_discord_source_reuses_durable_receipt(
    tmp_path, monkeypatch
) -> None:
    provenance = _discord_provenance()
    provenance["resident_turn_id"] = "turn-restarting"
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(provenance))
    first = prepare_reset_notification(
        notification_root=tmp_path,
        restart_request={
            "backend": "systemd",
            "old_identity": {"backend": "systemd", "main_pid": 1001},
        },
    )
    mark_reset_succeeded(
        first,
        restart_evidence={"backend": "systemd", "health": {"main_pid": 1002}},
    )

    duplicate = prepare_reset_notification(
        notification_root=tmp_path,
        restart_request={
            "backend": "systemd",
            "old_identity": {"backend": "systemd", "main_pid": 1001},
        },
    )

    record = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert duplicate.notification_id == first.notification_id
    assert duplicate.reused is True
    assert len(list(tmp_path.glob("reset-*.json"))) == 1
    assert record["notification_id"] == first.notification_id
    assert record["initiator"]["resident_turn_id"] == "turn-restarting"
    assert record["initiator"]["reply_to_message_id"] == "1525445255711952977"
    assert record["restart"]["request"]["old_identity"]["main_pid"] == 1001


def test_different_discord_source_cannot_queue_behind_active_restart(
    tmp_path, monkeypatch
) -> None:
    provenance = _discord_provenance()
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(provenance))
    prepare_reset_notification(notification_root=tmp_path)
    provenance["source_record_id"] = "msg-other"
    provenance["discord_message_id"] = "1525445255711952978"
    provenance["reply_to_message_id"] = "1525445255711952978"
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(provenance))

    with pytest.raises(ResetNotificationError, match="already active"):
        prepare_reset_notification(notification_root=tmp_path)
