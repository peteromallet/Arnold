"""Durable Discord transaction state for the canonical resident restart.

Exactly one user-visible message is eligible for each restart transaction: the
terminal success or failure outcome.  It remains ineligible until an external
supervisor or replacement startup has determined that outcome, then uses
retryable, provider-idempotent outbox state tied to the initiating Discord
message or the configured fallback conversation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import uuid4

RESET_NOTIFICATION_SCHEMA = "agentbox-resident-reset-notification-v1"
RESET_NOTIFICATION_ENV = "AGENTBOX_RESET_NOTIFICATION_ROOT"
RESET_FALLBACK_CONVERSATION_ENV = "AGENTBOX_DISCORD_RESET_FALLBACK_CONVERSATION"
DEFAULT_NOTIFICATION_ROOT = Path("/workspace/.megaplan/resident/reset_notifications")
_RETRY_BASE_SECONDS = 30
_RETRY_MAX_SECONDS = 60 * 60
_MAX_ATTEMPTS = 8
_CLAIM_LEASE_SECONDS = 60
_TERMINAL_DELIVERY_STATES = frozenset({"delivered", "failed", "suppressed"})
_ACTIVE_RESTART_STATES = frozenset({"prepared", "supervisor_started", "restarting"})


class ResetNotificationError(RuntimeError):
    """The notification lifecycle cannot be made durable enough to restart."""


@dataclass(frozen=True)
class ResetNotificationReservation:
    """Opaque identity of a reset outbox record prepared before a restart."""

    notification_id: str
    path: Path
    provenance_mode: str


@dataclass(frozen=True)
class ResetNotificationSweepResult:
    scanned: int = 0
    delivered: int = 0
    retry_pending: int = 0
    failed: int = 0
    waiting_for_target: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class RestartInterruptedTurnClaim:
    notification_id: str
    turn_id: str
    source_record_ids: tuple[str, ...]


def reset_notification_root(
    workspace_root: str | Path | None = None,
) -> Path:
    """Return the common host/container outbox root.

    A host operator may explicitly override the root, while the normal AgentBox
    workspace maps both the CLI and the container resident to ``/workspace``.
    """

    configured = os.environ.get(RESET_NOTIFICATION_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    if workspace_root is not None:
        return Path(workspace_root).expanduser().resolve() / ".megaplan" / "resident" / "reset_notifications"
    return DEFAULT_NOTIFICATION_ROOT


def prepare_reset_notification(
    *,
    notification_root: str | Path | None = None,
    restart_request: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> ResetNotificationReservation:
    """Persist an ineligible reset outbox record before touching the resident.

    The record deliberately starts as ``prepared``.  A later failed restart is
    therefore visible but can never produce a false success confirmation.
    """

    now = now or datetime.now(UTC)
    root = Path(notification_root) if notification_root is not None else reset_notification_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ResetNotificationError("cannot create durable resident reset outbox") from exc

    provenance, provenance_mode, provenance_error = _current_provenance()
    notification_id = f"reset-{uuid4().hex}"
    path = root / f"{notification_id}.json"
    initiator = _initiator_projection(provenance)
    record: dict[str, Any] = {
        "schema_version": RESET_NOTIFICATION_SCHEMA,
        "notification_id": notification_id,
        "created_at": _timestamp(now),
        "updated_at": _timestamp(now),
        "provenance_mode": provenance_mode,
        "provenance": provenance,
        "initiator": initiator,
        "restart": {
            "status": "prepared",
            "requested_at": _timestamp(now),
            "request": _restart_request_projection(restart_request),
            "state_history": [
                {
                    "status": "prepared",
                    "at": _timestamp(now),
                    "evidence": "restart_transaction_committed_before_supervisor_launch",
                }
            ],
        },
        "delivery": {
            "transport": "discord",
            "status": "prepared",
            "attempt_count": 0,
            "idempotency_key": f"agentbox-resident-reset:{notification_id}",
            "discord_nonce": _nonce(notification_id, phase="terminal"),
            "state_history": [
                {
                    "status": "prepared",
                    "at": _timestamp(now),
                    "evidence": "outbox_committed_before_guarded_restart",
                }
            ],
        },
    }
    source_record_id = str((initiator or {}).get("source_record_id") or "")
    turn_id = str((initiator or {}).get("resident_turn_id") or "")
    record["interrupted_turn_replay"] = {
        "status": "pending" if turn_id and source_record_id else "not_applicable",
        "turn_id": turn_id or None,
        "source_record_ids": [source_record_id] if source_record_id else [],
        "attempt_count": 0,
    }
    if provenance_error:
        # The bad envelope is intentionally not copied into durable state.
        record["provenance_error"] = provenance_error
    if provenance is not None:
        target = {
            "conversation_key": provenance["conversation_key"],
            "message_id": provenance["reply_to_message_id"],
            "source_record_id": provenance["source_record_id"],
            "kind": "reply",
        }
        record["delivery"]["reply_target"] = dict(target)
    else:
        fallback = os.environ.get(RESET_FALLBACK_CONVERSATION_ENV) or None
        record["delivery"]["fallback_target"] = fallback
    try:
        with _root_lock(root):
            active = _active_restart_record(root)
            if active is not None:
                raise ResetNotificationError(
                    f"restart transaction already active: {active.get('notification_id')}"
                )
            _atomic_json(path, record)
    except OSError as exc:
        raise ResetNotificationError("cannot persist resident reset outbox record") from exc
    return ResetNotificationReservation(notification_id, path, provenance_mode)


def mark_reset_supervisor_started(
    reservation: ResetNotificationReservation,
    *,
    supervisor_pid: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record external supervisor custody before the caller can be replaced."""

    now = now or datetime.now(UTC)
    with _locked_record(reservation.path) as record:
        _assert_record(record, reservation)
        restart = dict(record.get("restart") or {})
        if restart.get("status") == "prepared":
            _append_restart_state(
                restart,
                status="supervisor_started",
                now=now,
                evidence="detached_restart_supervisor_started",
            )
            restart.update(
                {
                    "status": "supervisor_started",
                    "supervisor_pid": int(supervisor_pid),
                    "supervisor_started_at": _timestamp(now),
                }
            )
            record["restart"] = restart
            record["updated_at"] = _timestamp(now)
            _atomic_json(reservation.path, record)
        return _public_record(record)


def mark_reset_restarting(
    reservation: ResetNotificationReservation,
    *,
    supervisor_pid: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    with _locked_record(reservation.path) as record:
        _assert_record(record, reservation)
        restart = dict(record.get("restart") or {})
        if restart.get("status") in {"prepared", "supervisor_started"}:
            _append_restart_state(
                restart,
                status="restarting",
                now=now,
                evidence="canonical_restart_boundary_invoked_by_external_supervisor",
            )
            restart["status"] = "restarting"
            if supervisor_pid is not None:
                restart["supervisor_pid"] = int(supervisor_pid)
            record["restart"] = restart
            record["updated_at"] = _timestamp(now)
            _atomic_json(reservation.path, record)
        return _public_record(record)


def mark_reset_succeeded(
    reservation: ResetNotificationReservation,
    *,
    restart_evidence: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Make a previously prepared record deliverable after a successful reset."""

    now = now or datetime.now(UTC)
    with _locked_record(reservation.path) as record:
        _assert_record(record, reservation)
        delivery = dict(record.get("delivery") or {})
        if delivery.get("status") == "prepared":
            history = list(delivery.get("state_history") or [])
            history.append(
                {
                    "status": "pending",
                    "at": _timestamp(now),
                    "evidence": "guarded_restart_reported_success",
                }
            )
            delivery.update(
                {
                    "status": "pending",
                    "updated_at": _timestamp(now),
                    "state_history": history[-20:],
                }
            )
        restart = dict(record.get("restart") or {})
        if restart.get("status") == "succeeded":
            return _public_record(record)
        _append_restart_state(
            restart,
            status="succeeded",
            now=now,
            evidence="replacement_process_identity_verified",
        )
        restart.update(
            {
                "status": "succeeded",
                "completed_at": _timestamp(now),
                "evidence": _restart_evidence(restart_evidence),
            }
        )
        record["restart"] = restart
        record["delivery"] = delivery
        record["updated_at"] = _timestamp(now)
        _atomic_json(reservation.path, record)
        return _public_record(record)


def mark_reset_failed(
    reservation: ResetNotificationReservation,
    *,
    restart_evidence: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Make the truthful terminal failure outcome deliverable."""

    now = now or datetime.now(UTC)
    with _locked_record(reservation.path) as record:
        _assert_record(record, reservation)
        restart = dict(record.get("restart") or {})
        if restart.get("status") in {"succeeded", "failed"}:
            return _public_record(record)
        delivery = dict(record.get("delivery") or {})
        history = list(delivery.get("state_history") or [])
        history.append(
            {
                "status": "pending",
                "at": _timestamp(now),
                "evidence": "guarded_restart_reported_failure",
            }
        )
        delivery.update(
            {
                "status": "pending",
                "updated_at": _timestamp(now),
                "state_history": history[-20:],
            }
        )
        _append_restart_state(
            restart,
            status="failed",
            now=now,
            evidence="guarded_restart_failed_or_identity_unchanged",
        )
        restart.update(
            {
                "status": "failed",
                "completed_at": _timestamp(now),
                "evidence": _restart_evidence(restart_evidence),
            }
        )
        record["restart"] = restart
        record["delivery"] = delivery
        record["updated_at"] = _timestamp(now)
        _atomic_json(reservation.path, record)
        return _public_record(record)


async def sweep_reset_notifications(
    *,
    outbound: Any,
    store: Any | None = None,
    notification_root: str | Path | None = None,
    now: datetime | None = None,
) -> ResetNotificationSweepResult:
    """Deliver each due terminal restart outcome exactly once per outbox item."""

    now = now or datetime.now(UTC)
    root = Path(notification_root) if notification_root is not None else reset_notification_root()
    paths = sorted(root.glob("reset-*.json")) if root.is_dir() else []
    delivered = retry_pending = failed = waiting_for_target = skipped = 0
    fallback = _fallback_conversation(store)
    for path in paths:
        _suppress_legacy_acknowledgement(path, now=now)
        claim = _claim_delivery(
            path,
            now=now,
            fallback_conversation=fallback,
            phase="delivery",
        )
        if claim is None:
            state = _delivery_status(path, phase="delivery")
            if state == "awaiting_fallback_target":
                waiting_for_target += 1
            elif state == "failed":
                failed += 1
            else:
                skipped += 1
            continue
        record, target = claim
        outcome = await _deliver_claimed_notification(
            outbound=outbound,
            path=path,
            record=record,
            target=target,
            now=now,
        )
        delivered += int(outcome == "delivered")
        retry_pending += int(outcome == "retry_pending")
        failed += int(outcome == "failed")
    return ResetNotificationSweepResult(
        scanned=len(paths),
        delivered=delivered,
        retry_pending=retry_pending,
        failed=failed,
        waiting_for_target=waiting_for_target,
        skipped=skipped,
    )


async def _deliver_claimed_notification(
    *,
    outbound: Any,
    path: Path,
    record: Mapping[str, Any],
    target: Mapping[str, str],
    now: datetime,
) -> str:
    from arnold_pipelines.megaplan.resident.runtime import OutboundMessage

    delivery = dict(record["delivery"])
    metadata: dict[str, Any] = {
        "resident_reset_notification": True,
        "resident_reset_notification_phase": "terminal",
        "resident_reset_notification_outcome": str(record["restart"]["status"]),
        "resident_reset_notification_id": record["notification_id"],
        "discord_nonce": delivery["discord_nonce"],
    }
    if target.get("kind") == "reply":
        metadata["discord_reply_to_message_id"] = target["message_id"]
    content = _terminal_content(record, target)
    try:
        await outbound.send(
            OutboundMessage(
                conversation_key=target["conversation_key"],
                content=content,
                idempotency_key=delivery["idempotency_key"],
                metadata=metadata,
            )
        )
    except Exception as exc:
        return _record_delivery_failure(path, phase="delivery", now=now, exc=exc)
    message_ids = [str(item) for item in metadata.get("discord_message_ids", []) if str(item)]
    _record_delivery_success(path, phase="delivery", now=now, message_ids=message_ids)
    return "delivered"


def list_reset_notifications(
    *,
    notification_root: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return bounded, non-secret reset outbox state for operators and tests."""

    root = Path(notification_root) if notification_root is not None else reset_notification_root()
    records: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("reset-*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if isinstance(payload, dict):
                records.append(_public_record(payload))
    records.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("notification_id") or "")), reverse=True)
    counts: dict[str, int] = {}
    for row in records:
        status = str(row.get("delivery", {}).get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "notification_root": str(root),
        "count": len(records),
        "delivery_status_counts": counts,
        "records": records[:max(0, limit)],
    }


def load_reset_reservation(
    notification_id: str,
    *,
    notification_root: str | Path | None = None,
) -> ResetNotificationReservation:
    """Rehydrate a prepared transaction for the detached supervisor."""

    if not notification_id.startswith("reset-") or not notification_id[6:].isalnum():
        raise ResetNotificationError("invalid reset transaction id")
    root = Path(notification_root) if notification_root is not None else reset_notification_root()
    path = root / f"{notification_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ResetNotificationError("reset transaction record is unavailable") from exc
    if not isinstance(payload, Mapping) or payload.get("notification_id") != notification_id:
        raise ResetNotificationError("reset transaction identity mismatch")
    return ResetNotificationReservation(
        notification_id=notification_id,
        path=path,
        provenance_mode=str(payload.get("provenance_mode") or "unknown"),
    )


def reset_transaction_request(
    reservation: ResetNotificationReservation,
) -> dict[str, Any]:
    with _locked_record(reservation.path) as record:
        _assert_record(record, reservation)
        restart = record.get("restart")
        request = restart.get("request") if isinstance(restart, Mapping) else None
        return dict(request) if isinstance(request, Mapping) else {}


def reconcile_prepared_reset_notifications(
    *,
    current_identity: Mapping[str, Any] | None,
    notification_root: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Finalize restart records stranded across process replacement.

    A changed canonical identity is sufficient success evidence.  An unchanged
    identity is failed only when its recorded external supervisor is no longer
    alive; a live supervisor retains custody and the startup sweep is a no-op.
    """

    now = now or datetime.now(UTC)
    root = Path(notification_root) if notification_root is not None else reset_notification_root()
    result = {"scanned": 0, "succeeded": 0, "failed": 0, "in_progress": 0}
    for path in sorted(root.glob("reset-*.json")) if root.is_dir() else []:
        try:
            with _locked_record(path) as record:
                restart = dict(record.get("restart") or {})
                if restart.get("status") not in _ACTIVE_RESTART_STATES:
                    continue
                result["scanned"] += 1
                request = restart.get("request")
                old_identity = (
                    request.get("old_identity") if isinstance(request, Mapping) else None
                )
                identity_changed = _identity_changed(old_identity, current_identity)
                if identity_changed:
                    _set_reconciled_success(
                        path,
                        record,
                        restart,
                        current_identity=current_identity,
                        now=now,
                    )
                    result["succeeded"] += 1
                    continue
                supervisor_pid = _optional_positive_int(restart.get("supervisor_pid"))
                if supervisor_pid is not None and _pid_is_live(supervisor_pid):
                    result["in_progress"] += 1
                    continue
                _set_reconciled_failure(path, record, restart, now=now)
                result["failed"] += 1
        except (OSError, ValueError, TypeError):
            continue
    return result


def claim_restart_interrupted_turns(
    *,
    process_identity: Mapping[str, Any],
    notification_root: str | Path | None = None,
    now: datetime | None = None,
) -> list[RestartInterruptedTurnClaim]:
    """Claim restart-owned inbound turns once per replacement identity."""

    now = now or datetime.now(UTC)
    root = Path(notification_root) if notification_root is not None else reset_notification_root()
    claimant = _identity_token(process_identity)
    claims: list[RestartInterruptedTurnClaim] = []
    for path in sorted(root.glob("reset-*.json")) if root.is_dir() else []:
        try:
            with _locked_record(path) as record:
                restart = record.get("restart")
                replay = dict(record.get("interrupted_turn_replay") or {})
                if not isinstance(restart, Mapping) or restart.get("status") != "succeeded":
                    continue
                status = str(replay.get("status") or "not_applicable")
                if status in {"complete", "skipped", "not_applicable"}:
                    continue
                if status == "claimed" and replay.get("claimed_by") == claimant:
                    continue
                turn_id = str(replay.get("turn_id") or "")
                source_ids = tuple(
                    str(value)
                    for value in replay.get("source_record_ids", [])
                    if str(value)
                )
                if not turn_id or not source_ids:
                    replay["status"] = "not_applicable"
                    record["interrupted_turn_replay"] = replay
                    _atomic_json(path, record)
                    continue
                replay.update(
                    {
                        "status": "claimed",
                        "claimed_by": claimant,
                        "claimed_at": _timestamp(now),
                        "attempt_count": int(replay.get("attempt_count") or 0) + 1,
                    }
                )
                record["interrupted_turn_replay"] = replay
                record["updated_at"] = _timestamp(now)
                _atomic_json(path, record)
                claims.append(
                    RestartInterruptedTurnClaim(
                        notification_id=str(record["notification_id"]),
                        turn_id=turn_id,
                        source_record_ids=source_ids,
                    )
                )
        except (OSError, ValueError, TypeError):
            continue
    return claims


def finish_restart_interrupted_turn(
    notification_id: str,
    *,
    status: str,
    replacement_turn_id: str | None = None,
    error_class: str | None = None,
    notification_root: str | Path | None = None,
    now: datetime | None = None,
) -> None:
    if status not in {"complete", "pending", "skipped"}:
        raise ValueError("invalid restart replay completion status")
    now = now or datetime.now(UTC)
    reservation = load_reset_reservation(
        notification_id, notification_root=notification_root
    )
    with _locked_record(reservation.path) as record:
        replay = dict(record.get("interrupted_turn_replay") or {})
        replay.update({"status": status, "updated_at": _timestamp(now)})
        if replacement_turn_id:
            replay["replacement_turn_id"] = replacement_turn_id
        if error_class:
            replay["last_error_class"] = str(error_class)
        replay.pop("claimed_by", None)
        record["interrupted_turn_replay"] = replay
        record["updated_at"] = _timestamp(now)
        _atomic_json(reservation.path, record)


def _current_provenance() -> tuple[dict[str, Any] | None, str, str | None]:
    # Import only when a reset is actually requested.  Importing a resident
    # submodule initializes its public package, whose profile imports the
    # AgentBox service constants; eager imports would therefore be circular.
    from arnold_pipelines.megaplan.resident.provenance import (
        DelegationProvenanceError,
        safe_provenance_projection,
    )

    try:
        provenance = safe_provenance_projection()
    except DelegationProvenanceError:
        return None, "invalid_or_ambiguous", "delegation provenance was invalid or ambiguous"
    if provenance is None:
        return None, "manual_or_non_discord", None
    if provenance.get("applicability") == "applicable" and provenance.get("transport") == "discord":
        return provenance, "discord_reply", None
    return None, "manual_or_non_discord", None


def _claim_delivery(
    path: Path,
    *,
    now: datetime,
    fallback_conversation: str | None,
    phase: str,
) -> tuple[dict[str, Any], dict[str, str]] | None:
    try:
        with _locked_record(path) as record:
            if record.get("schema_version") != RESET_NOTIFICATION_SCHEMA:
                return None
            restart = record.get("restart")
            delivery = dict(record.get(phase) or {})
            if not delivery:
                return None
            if phase == "delivery":
                if (
                    not isinstance(restart, Mapping)
                    or restart.get("status") not in {"succeeded", "failed"}
                ):
                    return None
            status = str(delivery.get("status") or "prepared")
            if status == "restart_failed":
                # v1 records used this as a non-deliverable terminal marker.
                # The single-notification contract reports that failure instead.
                status = "pending"
                delivery["status"] = status
                _append_state(
                    delivery,
                    status=status,
                    now=now,
                    evidence="legacy_terminal_failure_made_deliverable",
                )
            if status in _TERMINAL_DELIVERY_STATES:
                return None
            due_at = _parse_timestamp(delivery.get("next_attempt_at"))
            if status == "retry_pending" and due_at is not None and due_at > now:
                return None
            if status == "sending":
                lease_expires_at = _parse_timestamp(delivery.get("claim_expires_at"))
                claimer_pid = _optional_positive_int(delivery.get("claimer_pid"))
                if (
                    lease_expires_at is not None
                    and lease_expires_at > now
                    and claimer_pid is not None
                    and _pid_is_live(claimer_pid)
                ):
                    return None
                _append_state(
                    delivery,
                    status="unknown",
                    now=now,
                    evidence="resident_restarted_during_provider_attempt",
                    attempt_id=delivery.get("attempt_id"),
                )
            target = _target_from_delivery(delivery)
            if target is None:
                candidate = str(delivery.get("fallback_target") or fallback_conversation or "").strip()
                if not candidate:
                    delivery.update(
                        {"status": "awaiting_fallback_target", "updated_at": _timestamp(now)}
                    )
                    _append_state(
                        delivery,
                        status="awaiting_fallback_target",
                        now=now,
                        evidence="no_safe_discord_fallback_conversation_available",
                    )
                    record[phase] = delivery
                    record["updated_at"] = _timestamp(now)
                    _atomic_json(path, record)
                    return None
                target = {"kind": "fallback", "conversation_key": candidate}
                delivery["fallback_target"] = candidate
            attempt = int(delivery.get("attempt_count") or 0) + 1
            if attempt > _MAX_ATTEMPTS:
                delivery.update(
                    {
                        "status": "failed",
                        "updated_at": _timestamp(now),
                        "last_error": "Discord delivery failed: retry budget exhausted",
                        "last_error_class": "DeliveryRetryExhausted",
                        "last_error_category": "retry_exhausted",
                    }
                )
                _append_state(delivery, status="failed", now=now, evidence="retry_budget_exhausted")
                record[phase] = delivery
                record["updated_at"] = _timestamp(now)
                _atomic_json(path, record)
                return None
            delivery.update(
                {
                    "status": "sending",
                    "claim_state": "sending",
                    "attempt_count": attempt,
                    "attempt_id": f"{record['notification_id']}:{attempt}",
                    "claimer_pid": os.getpid(),
                    "claim_expires_at": _timestamp(
                        now + timedelta(seconds=_CLAIM_LEASE_SECONDS)
                    ),
                    "last_attempt_at": _timestamp(now),
                    "updated_at": _timestamp(now),
                }
            )
            delivery.pop("next_attempt_at", None)
            _append_state(
                delivery,
                status="sending",
                now=now,
                evidence="provider_attempt_claimed",
                attempt_id=delivery["attempt_id"],
            )
            record[phase] = delivery
            record["updated_at"] = _timestamp(now)
            _atomic_json(path, record)
            return record, target
    except (OSError, ValueError, TypeError):
        return None


def _record_delivery_success(
    path: Path,
    *,
    phase: str,
    now: datetime,
    message_ids: list[str],
) -> None:
    with _locked_record(path) as record:
        delivery = dict(record.get(phase) or {})
        _append_state(
            delivery,
            status="delivered",
            now=now,
            evidence="provider_message_ids_persisted",
            attempt_id=delivery.get("attempt_id"),
        )
        delivery.update(
            {
                "status": "delivered",
                "delivered_at": _timestamp(now),
                "discord_message_ids": message_ids,
                "updated_at": _timestamp(now),
            }
        )
        delivery.pop("claim_state", None)
        delivery.pop("claimer_pid", None)
        delivery.pop("claim_expires_at", None)
        delivery.pop("next_attempt_at", None)
        record[phase] = delivery
        record["updated_at"] = _timestamp(now)
        _atomic_json(path, record)


def _record_delivery_failure(
    path: Path,
    *,
    phase: str,
    now: datetime,
    exc: Exception,
) -> str:
    with _locked_record(path) as record:
        delivery = dict(record.get(phase) or {})
        attempt = max(1, int(delivery.get("attempt_count") or 1))
        evidence = _delivery_error_evidence(exc)
        permanent = evidence["last_error_category"] in {
            "invalid_reply_target",
            "unauthorized",
            "forbidden",
            "not_found",
            "client_error",
        }
        status = "failed" if permanent or attempt >= _MAX_ATTEMPTS else "retry_pending"
        errors = list(delivery.get("error_history") or [])
        errors.append(
            {
                "attempt_id": delivery.get("attempt_id"),
                "attempted_at": delivery.get("last_attempt_at") or _timestamp(now),
                **evidence,
            }
        )
        delivery.update(
            {
                "status": status,
                "updated_at": _timestamp(now),
                "error_history": errors[-10:],
                **evidence,
            }
        )
        _append_state(
            delivery,
            status=status,
            now=now,
            evidence=("permanent_provider_rejection" if permanent else "retryable_provider_failure"),
            attempt_id=delivery.get("attempt_id"),
        )
        delivery.pop("claim_state", None)
        delivery.pop("claimer_pid", None)
        delivery.pop("claim_expires_at", None)
        if status == "retry_pending":
            delay = min(_RETRY_MAX_SECONDS, _RETRY_BASE_SECONDS * (2 ** min(attempt - 1, 7)))
            delivery["next_attempt_at"] = _timestamp(now + timedelta(seconds=delay))
        else:
            delivery.pop("next_attempt_at", None)
        record[phase] = delivery
        record["updated_at"] = _timestamp(now)
        _atomic_json(path, record)
        return status


def _target_from_delivery(delivery: Mapping[str, Any]) -> dict[str, str] | None:
    target = delivery.get("reply_target")
    if not isinstance(target, Mapping):
        return None
    conversation_key = str(target.get("conversation_key") or "").strip()
    message_id = str(target.get("message_id") or "").strip()
    if not conversation_key.startswith("discord:") or not message_id.isdigit() or int(message_id) <= 0:
        return None
    return {"kind": "reply", "conversation_key": conversation_key, "message_id": message_id}


def _fallback_conversation(store: Any | None) -> str | None:
    configured = os.environ.get(RESET_FALLBACK_CONVERSATION_ENV)
    if configured and configured.strip():
        return configured.strip()
    if store is None:
        return None
    try:
        conversations = store.list_resident_conversations(transport="discord", limit=100)
    except Exception:
        return None
    candidates = [
        row
        for row in conversations
        if isinstance(getattr(row, "conversation_key", None), str)
        and row.conversation_key.startswith("discord:")
    ]
    if not candidates:
        return None
    latest = max(
        candidates,
        key=lambda row: (
            _timestamp(getattr(row, "last_active_at", None)) if getattr(row, "last_active_at", None) else "",
            _timestamp(getattr(row, "updated_at", None)) if getattr(row, "updated_at", None) else "",
            str(getattr(row, "id", "")),
        ),
    )
    return str(latest.conversation_key)


def _terminal_content(
    record: Mapping[str, Any], target: Mapping[str, str]
) -> str:
    restart = record.get("restart")
    succeeded = isinstance(restart, Mapping) and restart.get("status") == "succeeded"
    content = (
        "Discord resident restart complete."
        if succeeded
        else "Discord resident restart failed. The replacement process was not verified."
    )
    if target.get("kind") == "reply":
        return content
    return (
        f"{content} This is a fallback notification for a manual/non-Discord "
        "restart, not a reply to an initiating message."
    )


def _suppress_legacy_acknowledgement(path: Path, *, now: datetime) -> None:
    """Make a pre-correction acceptance item permanently ineligible."""

    try:
        with _locked_record(path) as record:
            acknowledgement = dict(record.get("acknowledgement") or {})
            if not acknowledgement:
                return
            status = str(acknowledgement.get("status") or "pending")
            if status in {"delivered", "failed", "suppressed"}:
                return
            acknowledgement.update(
                {
                    "status": "suppressed",
                    "updated_at": _timestamp(now),
                    "suppressed_by_contract": "single_terminal_restart_notification",
                }
            )
            acknowledgement.pop("claim_state", None)
            acknowledgement.pop("next_attempt_at", None)
            _append_state(
                acknowledgement,
                status="suppressed",
                now=now,
                evidence="acceptance_delivery_removed_by_single_terminal_contract",
            )
            record["acknowledgement"] = acknowledgement
            record["updated_at"] = _timestamp(now)
            _atomic_json(path, record)
    except (OSError, ValueError, TypeError):
        return


def _delivery_status(path: Path, *, phase: str = "delivery") -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        delivery = payload.get(phase) if isinstance(payload, Mapping) else None
        return str(delivery.get("status")) if isinstance(delivery, Mapping) else None
    except (OSError, ValueError, TypeError):
        return None


@contextmanager
def _locked_record(path: Path) -> Iterator[dict[str, Any]]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("reset notification record is not an object")
            yield payload
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _root_lock(root: Path) -> Iterator[None]:
    lock_path = root / ".restart-transaction.lock"
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _active_restart_record(root: Path) -> dict[str, Any] | None:
    for path in sorted(root.glob("reset-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        restart = payload.get("restart") if isinstance(payload, Mapping) else None
        if isinstance(restart, Mapping) and restart.get("status") in _ACTIVE_RESTART_STATES:
            return dict(payload)
    return None


def _assert_record(record: Mapping[str, Any], reservation: ResetNotificationReservation) -> None:
    if (
        record.get("schema_version") != RESET_NOTIFICATION_SCHEMA
        or record.get("notification_id") != reservation.notification_id
    ):
        raise ResetNotificationError("reset notification outbox record changed unexpectedly")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _restart_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep restart proof useful without persisting arbitrary command output."""

    evidence: dict[str, Any] = {}
    for key in ("service", "unit", "backend", "error", "finalized_by"):
        item = value.get(key)
        if item is not None:
            evidence[key] = str(item)
    for key in ("safety", "health"):
        item = value.get(key)
        if isinstance(item, Mapping):
            evidence[key] = dict(item)
    return evidence


def _restart_request_projection(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected: dict[str, Any] = {}
    for key in ("service", "unit", "backend"):
        if value.get(key) is not None:
            projected[key] = str(value[key])
    old_identity = value.get("old_identity")
    if isinstance(old_identity, Mapping):
        projected["old_identity"] = {
            key: item
            for key, item in old_identity.items()
            if key in {"backend", "main_pid", "pane_id", "pane_pid", "resident_pid"}
            and isinstance(item, (str, int, bool))
        }
    return projected


def _initiator_projection(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    allowed = {
        "transport",
        "applicability",
        "resident_conversation_id",
        "resident_turn_id",
        "source_record_id",
        "conversation_key",
        "discord_message_id",
        "reply_to_message_id",
        "guild_id",
        "channel_id",
        "thread_id",
        "dm_user_id",
        "source_kind",
    }
    return {key: value[key] for key in allowed if value.get(key) is not None}


def _identity_key(value: Mapping[str, Any] | None) -> tuple[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    backend = str(value.get("backend") or "")
    if backend == "systemd":
        pid = _optional_positive_int(value.get("main_pid"))
        return (backend, str(pid)) if pid is not None else None
    if backend == "tmux":
        pid = _optional_positive_int(value.get("pane_pid"))
        return (backend, str(pid)) if pid is not None else None
    return None


def _identity_changed(
    old_identity: object,
    current_identity: Mapping[str, Any] | None,
) -> bool:
    old_key = _identity_key(old_identity if isinstance(old_identity, Mapping) else None)
    current_key = _identity_key(current_identity)
    return old_key is not None and current_key is not None and old_key != current_key


def _identity_token(value: Mapping[str, Any]) -> str:
    key = _identity_key(value)
    if key is None:
        encoded = json.dumps(dict(value), sort_keys=True, default=str)
        return "identity:" + hashlib.sha256(encoded.encode()).hexdigest()[:20]
    return f"{key[0]}:{key[1]}"


def _optional_positive_int(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _pid_is_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def _append_restart_state(
    restart: dict[str, Any],
    *,
    status: str,
    now: datetime,
    evidence: str,
) -> None:
    history = list(restart.get("state_history") or [])
    history.append({"status": status, "at": _timestamp(now), "evidence": evidence})
    restart["state_history"] = history[-20:]


def _set_reconciled_success(
    path: Path,
    record: dict[str, Any],
    restart: dict[str, Any],
    *,
    current_identity: Mapping[str, Any] | None,
    now: datetime,
) -> None:
    delivery = dict(record.get("delivery") or {})
    if delivery.get("status") == "prepared":
        delivery["status"] = "pending"
        _append_state(
            delivery,
            status="pending",
            now=now,
            evidence="replacement_startup_reconciled_stranded_restart",
        )
    _append_restart_state(
        restart,
        status="succeeded",
        now=now,
        evidence="replacement_startup_observed_changed_process_identity",
    )
    restart.update(
        {
            "status": "succeeded",
            "completed_at": _timestamp(now),
            "evidence": {
                "finalized_by": "replacement_startup_reconciliation",
                "health": {"current_identity": dict(current_identity or {})},
            },
        }
    )
    record["restart"] = restart
    record["delivery"] = delivery
    record["updated_at"] = _timestamp(now)
    _atomic_json(path, record)


def _set_reconciled_failure(
    path: Path,
    record: dict[str, Any],
    restart: dict[str, Any],
    *,
    now: datetime,
) -> None:
    delivery = dict(record.get("delivery") or {})
    delivery["status"] = "pending"
    _append_state(
        delivery,
        status="pending",
        now=now,
        evidence="startup_found_no_supervisor_and_unchanged_identity_failure_deliverable",
    )
    _append_restart_state(
        restart,
        status="failed",
        now=now,
        evidence="startup_reconciled_stranded_prepared_record_without_identity_change",
    )
    restart.update(
        {
            "status": "failed",
            "completed_at": _timestamp(now),
            "evidence": {"finalized_by": "replacement_startup_reconciliation"},
        }
    )
    record["restart"] = restart
    record["delivery"] = delivery
    record["updated_at"] = _timestamp(now)
    _atomic_json(path, record)


def _delivery_error_evidence(exc: Exception) -> dict[str, Any]:
    status = _optional_http_status(exc)
    detail = str(exc).lower()
    if "reply target" in detail or "snowflake" in detail:
        category = "invalid_reply_target"
    elif status == 429:
        category = "rate_limited"
    elif status == 401:
        category = "unauthorized"
    elif status == 403:
        category = "forbidden"
    elif status == 404:
        category = "not_found"
    elif status is not None and status >= 500:
        category = "server_error"
    elif status is not None and status >= 400:
        category = "client_error"
    elif isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        category = "timeout"
    elif isinstance(exc, (ConnectionError, OSError)):
        category = "network_error"
    else:
        category = "runtime_error"
    return {
        "last_error": f"Discord delivery failed: {category}",
        "last_error_class": exc.__class__.__name__,
        "last_error_category": category,
        "last_http_status": status,
    }


def _optional_http_status(exc: Exception) -> int | None:
    for value in (
        getattr(exc, "status", None),
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        try:
            status = int(value)
        except (TypeError, ValueError):
            continue
        if 100 <= status <= 599:
            return status
    return None


def _append_state(
    delivery: dict[str, Any],
    *,
    status: str,
    now: datetime,
    evidence: str,
    attempt_id: object | None = None,
) -> None:
    history = list(delivery.get("state_history") or [])
    item: dict[str, Any] = {"status": status, "at": _timestamp(now), "evidence": evidence}
    if attempt_id:
        item["attempt_id"] = str(attempt_id)
    history.append(item)
    delivery["state_history"] = history[-20:]


def _nonce(notification_id: str, *, phase: str) -> str:
    return hashlib.sha256(
        f"agentbox-resident-reset:{phase}:{notification_id}".encode("utf-8")
    ).hexdigest()[:20]


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Expose lifecycle evidence but never command output or credentials."""

    return {
        "notification_id": record.get("notification_id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "provenance_mode": record.get("provenance_mode"),
        "initiator": dict(record.get("initiator") or {}),
        "restart": dict(record.get("restart") or {}),
        # Kept as an empty/legacy-only projection for callers reading v1 state.
        "acknowledgement": dict(record.get("acknowledgement") or {}),
        "delivery": dict(record.get("delivery") or {}),
        "interrupted_turn_replay": dict(record.get("interrupted_turn_replay") or {}),
    }


__all__ = [
    "DEFAULT_NOTIFICATION_ROOT",
    "RESET_FALLBACK_CONVERSATION_ENV",
    "RESET_NOTIFICATION_ENV",
    "RESET_NOTIFICATION_SCHEMA",
    "ResetNotificationError",
    "ResetNotificationReservation",
    "ResetNotificationSweepResult",
    "RestartInterruptedTurnClaim",
    "claim_restart_interrupted_turns",
    "finish_restart_interrupted_turn",
    "list_reset_notifications",
    "load_reset_reservation",
    "mark_reset_failed",
    "mark_reset_restarting",
    "mark_reset_succeeded",
    "mark_reset_supervisor_started",
    "prepare_reset_notification",
    "reconcile_prepared_reset_notifications",
    "reset_notification_root",
    "reset_transaction_request",
    "sweep_reset_notifications",
]
