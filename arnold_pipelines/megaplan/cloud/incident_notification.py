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
        created_at TEXT NOT NULL
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
    """Canonical notification admission and projection facade.

    This class deliberately owns admission only. Delivery attempts, provider
    receipts, Run Authority transitions, and custody belong to the resident
    ``EffectProtocol`` path. The old local provider and authority tables are
    retired by ``_migrate_legacy_schema``.
    """

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
                    self._migrate_legacy_schema(conn)
                    break
                except sqlite3.OperationalError as exc:
                    self._store.close()
                    if "locked" not in str(exc).lower() or attempt == 19:
                        raise
                    time.sleep(min(0.01 * (2**attempt), 0.5))

    @staticmethod
    def _migrate_legacy_schema(conn: sqlite3.Connection) -> None:
        """Retire the pre-consolidation local authority/provider schema."""
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(incident_occurrences)").fetchall()
        }
        if "authority_state_json" in columns:
            conn.execute("ALTER TABLE incident_occurrences RENAME TO incident_occurrences_legacy")
            conn.execute(_TABLES[0])
            conn.execute(
                """
                INSERT OR IGNORE INTO incident_occurrences
                    (occurrence_id, diagnostic_attempt_id, notification_intent_id,
                     state_version, fingerprint, created_at)
                SELECT occurrence_id, diagnostic_attempt_id, notification_intent_id,
                       state_version, fingerprint, created_at
                FROM incident_occurrences_legacy
                """
            )
            conn.execute("DROP TABLE incident_occurrences_legacy")
        # These records cannot be upgraded into a canonical reservation or
        # incident event, so historical values are not authorization inputs.
        conn.execute("DROP TABLE IF EXISTS notification_provider_attempts")
        conn.execute("DROP TABLE IF EXISTS incident_authority_transitions")

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
        payload: Mapping[str, Any],
        marker: Mapping[str, Any],
    ) -> NotificationAdmission:
        occurrence_id = _required(occurrence_id, "occurrence_id")
        session = _required(session, "session")
        state = _required(state, "state")
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
            provenance=AttemptProvenance(
                actor_id="arnold.cloud.notification-admission",
                tool_id="watchdog-observer",
            ),
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
            # Migration evidence only: the resident completion effect is the
            # sole dispatchable notification path.
            "destination": "notification:discord.retired",
            "payload": {
                "schema": "arnold.notification.intent.v1",
                "dispatchable": False,
                "retirement": {
                    "status": "retired",
                    "replacement": "resident-subagent-completion:<run_id>",
                    "reason": "no in-tree consumer exists for this cloud destination",
                },
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
        # The event/outbox commit is canonical. The occurrence table is a
        # rebuildable projection; repopulate it from the committed event so a
        # crash between these operations cannot strand dedupe state.
        self._project_occurrence(result.event, fingerprint=fingerprint)
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

    def _project_occurrence(self, event: LedgerEvent, *, fingerprint: str) -> None:
        """Rebuild one occurrence row from a committed canonical event."""
        payload = event.payload if isinstance(event.payload, Mapping) else {}
        occurrence_id = _required(str(payload.get("incident_occurrence_id") or ""), "occurrence_id")
        diagnostic_attempt_id = _required(str(payload.get("diagnostic_attempt_id") or event.identity.attempt_id), "diagnostic_attempt_id")
        intent_id = _required(str(payload.get("notification_intent_id") or ""), "notification_intent_id")
        self.conn.execute(
            """
            INSERT INTO incident_occurrences
                (occurrence_id, diagnostic_attempt_id, notification_intent_id,
                 state_version, fingerprint, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(occurrence_id) DO UPDATE SET
                diagnostic_attempt_id=excluded.diagnostic_attempt_id,
                notification_intent_id=excluded.notification_intent_id,
                state_version=excluded.state_version,
                fingerprint=excluded.fingerprint
            """,
            (
                occurrence_id,
                diagnostic_attempt_id,
                intent_id,
                int(payload.get("state_version") or 1),
                fingerprint,
                str(event.occurred_at),
            ),
        )

    def canonical_intent(self, intent_id: str) -> dict[str, Any]:
        """Return a canonical retired intent; never a provider projection."""
        intent_id = _required(intent_id, "notification_intent_id")
        row = self.conn.execute(
            "SELECT destination, payload_json FROM outbox_records WHERE json_extract(payload_json, '$.notification_intent_id') = ?",
            (intent_id,),
        ).fetchone()
        if row is None:
            raise ValueError("notification intent is not a canonical outbox intent")
        payload = json.loads(str(row[1]))
        if not isinstance(payload, dict) or payload.get("dispatchable") is not False:
            raise ValueError("notification intent is not retired migration evidence")
        return {"destination": str(row[0]), "payload": payload}


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
        "next_action": "resident completion effect owns user-facing notification delivery",
        "acknowledgement_resolution_projection": {
            "source": "canonical-incident-ledger",
            "status": "not_recorded",
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
