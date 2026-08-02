"""Durable admission and projection for quiet human-review notifications.

The watchdog is an observer.  Its only notification capability is to admit a
stable occurrence and an outbox intent into the canonical workflow ledger.
Provider delivery is deliberately outside this module: a delivery worker may
consume the outbox, but an observer must never call a provider or invent a
fallback route after persistence fails.

The workflow ledger/outbox is the authority.  The incident card written here
is a bounded operator projection and can be rebuilt from the durable event and
outbox rows.  In particular, ``incident-card.json`` is never used to decide
whether an effect is new.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.ledger_outbox import SqliteLedgerOutbox


SCHEMA = "arnold-incident-notification-v1"
_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS incident_occurrences (
        occurrence_id TEXT PRIMARY KEY,
        diagnostic_attempt_id TEXT NOT NULL,
        notification_intent_id TEXT NOT NULL UNIQUE,
        state_version INTEGER NOT NULL,
        fingerprint TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        authority_state_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_provider_attempts (
        provider_attempt_id TEXT PRIMARY KEY,
        notification_intent_id TEXT NOT NULL,
        attempt_number INTEGER NOT NULL,
        status TEXT NOT NULL,
        request_digest TEXT NOT NULL,
        receipt_json TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(notification_intent_id, attempt_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS incident_authority_transitions (
        transition_id TEXT PRIMARY KEY,
        occurrence_id TEXT NOT NULL,
        action TEXT NOT NULL,
        authority_id TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        UNIQUE(occurrence_id, action)
    )
    """,
)
_INITIALIZATION_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _required(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _stable_recipient(payload: Mapping[str, Any], marker: Mapping[str, Any]) -> str:
    for candidate in (
        payload.get("recipient"),
        payload.get("dm_user_id"),
        payload.get("discord_user_id"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return f"discord:user:{candidate.strip()}"
    provenance = marker.get("resident_delegation")
    if isinstance(provenance, Mapping):
        source = provenance.get("source_record_id")
        if isinstance(source, str) and source.strip():
            return f"discord:source:{source.strip()}"
    # This is an identity, not a route or an authorization.  It lets the
    # durable record represent a provenance-pending incident without ever
    # manufacturing a provider target.
    return "discord:provenance-pending:" + _digest(marker)[:32]


@dataclass(frozen=True)
class NotificationAdmission:
    occurrence_id: str
    diagnostic_attempt_id: str
    notification_intent_id: str
    outbox_id: str
    state_version: int
    notification_kind: str
    recipient: str
    payload_digest: str
    duplicate: bool
    storage_health: str
    card_path: str


class IncidentNotificationStore:
    """Small facade over the canonical SQLite WBC/ledger outbox."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.db_path = self.root / ".incident-notifications.sqlite3"
        self._store = SqliteAttemptLedgerStore(self.db_path)
        with _INITIALIZATION_LOCK:
            for attempt in range(20):
                try:
                    self._outbox = SqliteLedgerOutbox(self._store)
                    conn = self._store.conn
                    for ddl in _TABLES:
                        conn.execute(ddl)
                    break
                except sqlite3.OperationalError as exc:
                    self._store.close()
                    if "locked" not in str(exc).lower() or attempt == 19:
                        raise
                    time.sleep(min(0.01 * (2**attempt), 0.5))

    @property
    def conn(self) -> sqlite3.Connection:
        return self._store.conn

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> "IncidentNotificationStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def admit(
        self,
        *,
        occurrence_id: str,
        session: str,
        state: str,
        owner: str,
        payload: Mapping[str, Any],
        marker: Mapping[str, Any],
    ) -> NotificationAdmission:
        occurrence_id = _required(occurrence_id, "occurrence_id")
        session = _required(session, "session")
        state = _required(state, "state")
        owner = _required(owner, "owner")
        kind = str(payload.get("notification_kind") or "repair_exhaustion_diagnostic").strip()
        kind = _required(kind, "notification_kind")
        recipient = _stable_recipient(payload, marker)
        # Watchdog payloads carry observation timestamps and other volatile
        # diagnostics.  They must not change the logical notification effect
        # identity on replay.
        stable_payload = {
            str(key): value
            for key, value in payload.items()
            if str(key) not in {"timestamp_utc", "observed_at", "generated_at"}
        }
        payload_digest = _digest(stable_payload)
        state_version = 1
        intent_id = "notify-" + hashlib.sha256(
            "\x1f".join((occurrence_id, str(state_version), recipient, kind, payload_digest)).encode("utf-8")
        ).hexdigest()[:32]
        diagnostic_attempt_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"arnold:human-review-diagnostic:{occurrence_id}")
        )
        attempt_id = diagnostic_attempt_id
        fingerprint = _digest(
            {
                "occurrence_id": occurrence_id,
                "session": session,
                "state": state,
                "kind": kind,
                "recipient": recipient,
                "payload_digest": payload_digest,
            }
        )
        event_key = f"incident-opened:{occurrence_id}:v{state_version}"
        event_payload = {
            "schema": SCHEMA,
            "transition": "opened",
            "incident_occurrence_id": occurrence_id,
            "diagnostic_attempt_id": diagnostic_attempt_id,
            "notification_intent_id": intent_id,
            "state": state,
            "state_version": state_version,
            "owner": owner,
            "recipient": recipient,
            "notification_kind": kind,
            "payload_digest": payload_digest,
        }
        identity = AttemptIdentity(
            workflow_id="arnold.incident-recovery",
            run_id=session,
            graph_revision="incident-notification-v1",
            boundary_id=occurrence_id,
            invocation_id=event_key,
            attempt_id=attempt_id,
        )
        event = LedgerEvent(
            idempotency_key=event_key,
            event_type=AttemptEventType.STARTED,
            identity=identity,
            provenance=AttemptProvenance(actor_id=owner, tool_id="watchdog-observer"),
            adapter=RuntimeAdapter(AdapterKind.MEGAPLAN_CLOUD_REPAIR, "incident-notification-v1"),
            versions=VersionSet(code_version="incident-notification-v1"),
            grant_ref=GrantRef("run-authority:incident-notification-admission"),
            sequence=1,
            causal_predecessor_sequence=0,
            append_position=0,
            occurred_at=_now(),
            observed_at=_now(),
            persistence_status=PersistenceStatus.DURABLE,
            payload=event_payload,
        )
        outbox_payload = {
            "outbox_id": intent_id,
            "destination": "notification:discord",
            "payload": {
                "schema": "arnold.notification.intent.v1",
                "notification_intent_id": intent_id,
                "incident_occurrence_id": occurrence_id,
                "diagnostic_attempt_id": diagnostic_attempt_id,
                "state_version": state_version,
                "recipient": recipient,
                "notification_kind": kind,
                "payload_digest": payload_digest,
                "payload": stable_payload,
            },
        }
        result = self._outbox.append_event_with_outbox(attempt_id, event, [outbox_payload])
        now = _now()
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO incident_occurrences
                    (occurrence_id, diagnostic_attempt_id, notification_intent_id,
                     state_version, fingerprint, created_at, authority_state_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(occurrence_id) DO NOTHING
                """,
                (
                    occurrence_id,
                    diagnostic_attempt_id,
                    intent_id,
                    state_version,
                    fingerprint,
                    now,
                    _canonical({"acknowledged": False, "resolved": False}),
                ),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        card_path = self.card_path(occurrence_id)
        return NotificationAdmission(
            occurrence_id=occurrence_id,
            diagnostic_attempt_id=diagnostic_attempt_id,
            notification_intent_id=intent_id,
            outbox_id=result.outbox_records[0].outbox_id if result.outbox_records else intent_id,
            state_version=state_version,
            notification_kind=kind,
            recipient=recipient,
            payload_digest=payload_digest,
            duplicate=result.is_duplicate,
            storage_health="durable",
            card_path=str(card_path),
        )

    def record_diagnostic_terminal(
        self,
        admission: NotificationAdmission,
        *,
        status: str,
        error: str,
    ) -> None:
        """Persist one terminal diagnostic result after admission.

        The terminal event uses its own stable idempotency key.  Replaying a
        provenance failure therefore returns the existing terminal evidence
        and cannot create a second result.
        """
        status = _required(status, "status")
        error = _required(error, "error")
        event = LedgerEvent(
            idempotency_key=f"diagnostic-terminal:{admission.diagnostic_attempt_id}:{status}",
            event_type=AttemptEventType.FAILED,
            identity=AttemptIdentity(
                workflow_id="arnold.incident-recovery",
                run_id=admission.occurrence_id,
                graph_revision="incident-notification-v1",
                boundary_id=admission.occurrence_id,
                invocation_id=f"diagnostic-terminal:{admission.diagnostic_attempt_id}",
                attempt_id=admission.diagnostic_attempt_id,
            ),
            provenance=AttemptProvenance(actor_id="diagnostic-launcher", tool_id="human-review-diagnostic"),
            adapter=RuntimeAdapter(AdapterKind.MEGAPLAN_CLOUD_REPAIR, "incident-notification-v1"),
            versions=VersionSet(code_version="incident-notification-v1"),
            grant_ref=GrantRef("run-authority:incident-diagnostic-result"),
            sequence=2,
            causal_predecessor_sequence=1,
            append_position=0,
            occurred_at=_now(),
            observed_at=_now(),
            persistence_status=PersistenceStatus.DURABLE,
            outcome=AttemptOutcome.FAILED,
            payload={
                "schema": SCHEMA,
                "diagnostic_attempt_id": admission.diagnostic_attempt_id,
                "incident_occurrence_id": admission.occurrence_id,
                "status": status,
                "error": error[:1500],
            },
        )
        self._outbox.append_event_with_outbox(admission.diagnostic_attempt_id, event, [])

    def card_path(self, occurrence_id: str) -> Path:
        return self.root / "human-review-diagnostics" / _required(occurrence_id, "occurrence_id") / "incident-card.json"

    def write_card(self, occurrence_id: str, card: Mapping[str, Any]) -> Path:
        path = self.card_path(occurrence_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(dict(card), sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return path

    def record_provider_attempt(
        self,
        *,
        intent_id: str,
        attempt_number: int,
        request_digest: str,
    ) -> str:
        intent_id = _required(intent_id, "notification_intent_id")
        request_digest = _required(request_digest, "request_digest")
        if not isinstance(attempt_number, int) or attempt_number < 1:
            raise ValueError("attempt_number must be positive")
        attempt_id = f"provider-{intent_id}-{attempt_number}"
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """
                INSERT INTO notification_provider_attempts
                    (provider_attempt_id, notification_intent_id, attempt_number,
                     status, request_digest, created_at)
                VALUES (?, ?, ?, 'PENDING', ?, ?)
                ON CONFLICT(notification_intent_id, attempt_number) DO NOTHING
                """,
                (attempt_id, intent_id, attempt_number, request_digest, _now()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return attempt_id

    def record_provider_receipt(
        self,
        *,
        intent_id: str,
        attempt_number: int,
        status: str,
        receipt: Mapping[str, Any] | None,
    ) -> str:
        status = str(status).upper()
        if status not in {"SUCCEEDED", "FAILED", "INDETERMINATE"}:
            raise ValueError("provider status must be SUCCEEDED, FAILED, or INDETERMINATE")
        intent_id = _required(intent_id, "notification_intent_id")
        receipt_json = _canonical(dict(receipt or {}))
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT status FROM notification_provider_attempts WHERE notification_intent_id = ? AND attempt_number = ?",
                (intent_id, attempt_number),
            ).fetchone()
            if row is None:
                raise ValueError("provider receipt has no durable provider attempt")
            # INDETERMINATE is sticky: a timeout/unknown result may never be
            # downgraded to FAILED or blindly redispatched.
            if row[0] == "INDETERMINATE":
                status = "INDETERMINATE"
            conn.execute(
                "UPDATE notification_provider_attempts SET status = ?, receipt_json = ? WHERE notification_intent_id = ? AND attempt_number = ?",
                (status, receipt_json, intent_id, attempt_number),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        occurrence_row = conn.execute(
            "SELECT occurrence_id FROM incident_occurrences WHERE notification_intent_id = ?",
            (intent_id,),
        ).fetchone()
        if occurrence_row:
            occurrence_id = str(occurrence_row[0])
            card_path = self.card_path(occurrence_id)
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
                if isinstance(card, dict):
                    card["ambiguity"] = status if status == "INDETERMINATE" else "NONE"
                    card["next_action"] = (
                        "reconcile provider receipt; do not blindly redispatch this intent"
                        if status == "INDETERMINATE"
                        else "notification delivery receipt recorded"
                    )
                    self.write_card(occurrence_id, card)
            except (OSError, ValueError, TypeError):
                # The ledger receipt is authoritative; a projection rebuild
                # can repair an unavailable or malformed incident card.
                pass
        return status

    def dispatch_eligible(self, intent_id: str) -> bool:
        row = self.conn.execute(
            "SELECT status FROM notification_provider_attempts WHERE notification_intent_id = ? ORDER BY attempt_number DESC LIMIT 1",
            (_required(intent_id, "notification_intent_id"),),
        ).fetchone()
        # PENDING means a delivery worker may still be between provider call
        # and receipt persistence. Treat it as ambiguous until a receipt is
        # recorded; redispatching could duplicate the provider effect.
        return row is None or row[0] == "FAILED"

    def authority_transition(
        self,
        *,
        occurrence_id: str,
        action: str,
        authority_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        if action not in {"acknowledge", "resolve"}:
            raise ValueError("unsupported incident authority transition")
        occurrence_id = _required(occurrence_id, "occurrence_id")
        authority_id = _required(authority_id, "authority_id")
        actor_id = _required(actor_id, "actor_id")
        transition_id = f"incident-authority-{uuid.uuid4().hex}"
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT 1 FROM incident_occurrences WHERE occurrence_id = ?", (occurrence_id,)
            ).fetchone()
            if row is None:
                raise ValueError("unknown incident occurrence")
            current_row = conn.execute(
                "SELECT authority_state_json FROM incident_occurrences WHERE occurrence_id = ?",
                (occurrence_id,),
            ).fetchone()
            authority_state = json.loads(current_row[0]) if current_row and current_row[0] else {}
            if not isinstance(authority_state, dict):
                raise ValueError("incident authority state is not a JSON object")
            authority_key = "acknowledged" if action == "acknowledge" else "resolved"
            authority_state[authority_key] = True
            authority_state["authority_state"] = "resolved" if action == "resolve" else "acknowledged"
            conn.execute(
                "INSERT INTO incident_authority_transitions VALUES (?, ?, ?, ?, ?, ?)",
                (transition_id, occurrence_id, action, authority_id, actor_id, _now()),
            )
            conn.execute(
                "UPDATE incident_occurrences SET authority_state_json = ? WHERE occurrence_id = ?",
                (_canonical(authority_state), occurrence_id),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        card_path = self.card_path(occurrence_id)
        if card_path.exists():
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
                if isinstance(card, dict):
                    state = dict(card.get("acknowledgement_resolution_authority") or {})
                    state["acknowledged"] = bool(state.get("acknowledged")) or action == "acknowledge"
                    state["resolved"] = bool(state.get("resolved")) or action == "resolve"
                    state["authority_state"] = "resolved" if state["resolved"] else "acknowledged"
                    card["acknowledgement_resolution_authority"] = state
                    self.write_card(occurrence_id, card)
            except (OSError, ValueError, TypeError):
                # The authority table remains authoritative; a projection
                # rebuild can repair a missing or malformed card.
                pass
        return {
            "transition_id": transition_id,
            "occurrence_id": occurrence_id,
            "action": action,
            "authority_id": authority_id,
            "actor_id": actor_id,
        }


def initial_incident_card(
    admission: NotificationAdmission,
    *,
    state: str,
    owner: str,
    runtime_generation: str,
) -> dict[str, Any]:
    return {
        "schema": "arnold.incident-card.v1",
        "incident_occurrence_id": admission.occurrence_id,
        "diagnostic_attempt_id": admission.diagnostic_attempt_id,
        "notification_intent_id": admission.notification_intent_id,
        "state": state,
        "owner": owner,
        "last_accepted_transition": {
            "name": "opened",
            "state_version": admission.state_version,
            "notification_intent_id": admission.notification_intent_id,
        },
        "diagnostic_fixer_result": {"status": "pending"},
        "ambiguity": "NONE",
        "storage_health": admission.storage_health,
        "runtime_generation": runtime_generation or "unknown",
        "next_action": "durable diagnostic worker may consume the notification intent",
        "acknowledgement_resolution_authority": {
            "acknowledged": False,
            "resolved": False,
            "authority_state": "awaiting_authority",
        },
        "recipient": admission.recipient,
        "notification_kind": admission.notification_kind,
        "payload_digest": admission.payload_digest,
    }


__all__ = [
    "IncidentNotificationStore",
    "NotificationAdmission",
    "initial_incident_card",
]
