from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from agentbox.reset_notifications import (
    RESET_FALLBACK_CONVERSATION_ENV,
    list_reset_notifications,
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


def test_reset_confirmation_preserves_discord_provenance_and_is_not_duplicated(
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

    assert first.delivered == 2
    assert second.delivered == 0
    assert len(outbound.sent) == 2
    accepted, message = outbound.sent
    assert accepted.content.startswith("Discord resident restart accepted")
    assert accepted.metadata["resident_reset_notification_phase"] == "accepted"
    assert message.conversation_key == "discord:dm:301463647895683072"
    assert message.metadata["discord_reply_to_message_id"] == "1525445255711952977"
    assert message.metadata["resident_reset_notification"] is True
    assert message.content == "Discord resident reset complete."
    state = list_reset_notifications(notification_root=tmp_path)
    assert state["delivery_status_counts"] == {"delivered": 1}
    assert state["records"][0]["acknowledgement"]["discord_message_ids"] == ["reply-1"]
    assert state["records"][0]["delivery"]["discord_message_ids"] == ["reply-2"]


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

    assert result.delivered == 2
    assert outbound.sent[1].conversation_key == "discord:dm:301463647895683072"
    assert "discord_reply_to_message_id" not in outbound.sent[1].metadata
    assert "fallback notification" in outbound.sent[1].content
    state = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert state["provenance_mode"] == "manual_or_non_discord"
    assert state["delivery"]["status"] == "delivered"


def test_reset_delivery_retry_persists_state_and_reuses_nonce(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(_discord_provenance()))
    first_now = datetime(2026, 7, 11, tzinfo=UTC)
    reservation = prepare_reset_notification(notification_root=tmp_path, now=first_now)
    mark_reset_succeeded(reservation, restart_evidence={"backend": "tmux"}, now=first_now)
    outbound = _Outbound(fail_once=True)

    first = asyncio.run(
        sweep_reset_notifications(outbound=outbound, notification_root=tmp_path, now=first_now)
    )
    retry_record = list_reset_notifications(notification_root=tmp_path)["records"][0]
    retry = retry_record["acknowledgement"]
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
    assert retry_record["delivery"]["status"] == "pending"
    assert second.delivered == 2
    assert delivered["status"] == "delivered"
    assert delivered["attempt_count"] == 1
    assert outbound.sent[0].metadata["discord_nonce"] == outbound.sent[1].metadata["discord_nonce"]
    assert outbound.sent[2].metadata["discord_nonce"] != outbound.sent[1].metadata["discord_nonce"]


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
    assert failed["delivery"]["status"] == "restart_failed"


def test_duplicate_restart_is_fenced_and_initiator_is_diagnostic(
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

    with pytest.raises(ResetNotificationError, match="already active"):
        prepare_reset_notification(
            notification_root=tmp_path,
            restart_request={
                "backend": "systemd",
                "old_identity": {"backend": "systemd", "main_pid": 1001},
            },
        )

    record = list_reset_notifications(notification_root=tmp_path)["records"][0]
    assert record["notification_id"] == first.notification_id
    assert record["initiator"]["resident_turn_id"] == "turn-restarting"
    assert record["initiator"]["reply_to_message_id"] == "1525445255711952977"
    assert record["restart"]["request"]["old_identity"]["main_pid"] == 1001
