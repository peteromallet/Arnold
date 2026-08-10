"""Durable, occurrence-scoped mutation ledger for the canonical simple fixer.

The singleton claim is admission control; it is deliberately *not* the
mutation budget.  Claims can be released, reclaimed, or lost with a process.
This ledger survives those events and is the sole authority for deciding
whether a repair effect may run.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.repair_requests import (
    normalize_repair_identity,
    repair_identity_key,
    validate_queue_root,
)


SCHEMA_VERSION = 1
LEDGER_NAME = ".simple-fixer-effects.sqlite3"

STATE_RESERVED = "RESERVED"
STATE_COMPLETED = "COMPLETED"
STATE_UNCHANGED = "UNCHANGED"
STATE_EXHAUSTED = "EXHAUSTED"
STATE_INDETERMINATE = "INDETERMINATE"
TERMINAL_STATES = frozenset(
    {STATE_COMPLETED, STATE_EXHAUSTED, STATE_INDETERMINATE}
)

DECISION_RESERVED = "reserved"
DECISION_ADOPTED = "adopted"
DECISION_IN_FLIGHT = "in_flight"
DECISION_EXHAUSTED = "exhausted"
DECISION_INDETERMINATE = "indeterminate"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def claim_owner_token(owner: Mapping[str, Any] | None) -> str:
    """Content-address the exact claim owner without making it effect identity."""

    if not isinstance(owner, Mapping) or not owner:
        return ""
    return "sha256:" + hashlib.sha256(_canonical(dict(owner)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MutationReservation:
    decision: str
    repair_identity_key: str
    state: str
    reservation_id: str = ""
    total_attempts: int = 0
    unchanged_attempts: int = 0
    effect_outcome: str = ""
    after_fingerprint: str = ""

    @property
    def reserved(self) -> bool:
        return self.decision == DECISION_RESERVED


class RepairEffectLedger:
    """SQLite CAS ledger shared by every process/container for one workspace.

    Rows are keyed solely by :func:`repair_identity_key`.  Actor, process,
    request, model, and provider fields are evidence only and cannot create a
    fresh budget.  ``BEGIN IMMEDIATE`` serializes reservation and outcome
    transitions across independent connections and containers sharing the
    workspace volume.
    """

    def __init__(self, queue_dir: str | Path) -> None:
        self.queue_dir = validate_queue_root(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.queue_dir / LEDGER_NAME
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS repair_effects (
                    repair_identity_key TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    normalized_identity_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('RESERVED', 'COMPLETED', 'UNCHANGED', 'EXHAUSTED', 'INDETERMINATE')
                    ),
                    reservation_id TEXT NOT NULL,
                    reservation_owner_token TEXT NOT NULL,
                    total_attempts INTEGER NOT NULL CHECK (total_attempts >= 1),
                    unchanged_attempts INTEGER NOT NULL CHECK (unchanged_attempts >= 0),
                    effect_outcome TEXT NOT NULL,
                    after_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Predecessor/experimental rows are evidence only.  An unknown
            # schema must never be silently upgraded into mutation authority.
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(repair_effects)").fetchall()
            }
            required = {
                "repair_identity_key",
                "schema_version",
                "normalized_identity_json",
                "state",
                "reservation_id",
                "reservation_owner_token",
                "total_attempts",
                "unchanged_attempts",
                "effect_outcome",
                "after_fingerprint",
                "created_at",
                "updated_at",
            }
            if columns != required:
                raise RuntimeError("simple fixer effect ledger schema is not current")
            connection.execute("COMMIT")

    @staticmethod
    def _identity(identity: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
        normalized = normalize_repair_identity(identity)
        key = repair_identity_key(normalized)
        if normalized is None or not key:
            raise ValueError(
                "repair effect reservation requires current normalized repair identity"
            )
        return normalized, key

    @staticmethod
    def _record(row: sqlite3.Row, *, decision: str) -> MutationReservation:
        return MutationReservation(
            decision=decision,
            repair_identity_key=str(row["repair_identity_key"]),
            state=str(row["state"]),
            reservation_id=str(row["reservation_id"]),
            total_attempts=int(row["total_attempts"]),
            unchanged_attempts=int(row["unchanged_attempts"]),
            effect_outcome=str(row["effect_outcome"]),
            after_fingerprint=str(row["after_fingerprint"]),
        )

    def inspect(self, identity: Mapping[str, Any] | None) -> MutationReservation | None:
        _normalized, key = self._identity(identity)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
            ).fetchone()
        return self._record(row, decision="observed") if row is not None else None

    def reserve(
        self,
        identity: Mapping[str, Any] | None,
        *,
        owner_token: str,
        max_unchanged_attempts: int,
    ) -> MutationReservation:
        """Reserve before mutation, or adopt/refuse the durable prior result.

        A RESERVED row owned by a *different* claim is an orphaned/ambiguous
        effect.  The new claimant durably closes it as INDETERMINATE and may
        not redrive.  The same claimant merely observes IN_FLIGHT; it also may
        not invoke the mutation twice.
        """

        normalized, key = self._identity(identity)
        if not owner_token:
            raise ValueError("reservation requires an exact claim owner token")
        if max_unchanged_attempts <= 0:
            raise ValueError("max_unchanged_attempts must be positive")
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
            ).fetchone()
            if row is None:
                reservation_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO repair_effects (
                        repair_identity_key, schema_version, normalized_identity_json,
                        state, reservation_id, reservation_owner_token,
                        total_attempts, unchanged_attempts, effect_outcome,
                        after_fingerprint, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, 0, '', '', ?, ?)
                    """,
                    (
                        key,
                        SCHEMA_VERSION,
                        _canonical(normalized),
                        STATE_RESERVED,
                        reservation_id,
                        owner_token,
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
                ).fetchone()
                connection.execute("COMMIT")
                assert row is not None
                return self._record(row, decision=DECISION_RESERVED)

            if int(row["schema_version"]) != SCHEMA_VERSION:
                connection.execute("ROLLBACK")
                raise RuntimeError("simple fixer effect row schema is not current")
            if str(row["normalized_identity_json"]) != _canonical(normalized):
                connection.execute("ROLLBACK")
                raise RuntimeError("repair identity key collision or forged identity")

            state = str(row["state"])
            if state == STATE_COMPLETED:
                connection.execute("COMMIT")
                return self._record(row, decision=DECISION_ADOPTED)
            if state == STATE_EXHAUSTED:
                connection.execute("COMMIT")
                return self._record(row, decision=DECISION_EXHAUSTED)
            if state == STATE_INDETERMINATE:
                connection.execute("COMMIT")
                return self._record(row, decision=DECISION_INDETERMINATE)
            if state == STATE_RESERVED:
                if str(row["reservation_owner_token"]) == owner_token:
                    connection.execute("COMMIT")
                    return self._record(row, decision=DECISION_IN_FLIGHT)
                cursor = connection.execute(
                    """
                    UPDATE repair_effects
                    SET state = ?, effect_outcome = ?, updated_at = ?
                    WHERE repair_identity_key = ? AND reservation_id = ? AND state = ?
                    """,
                    (
                        STATE_INDETERMINATE,
                        "reservation_owner_changed_before_durable_outcome",
                        now,
                        key,
                        str(row["reservation_id"]),
                        STATE_RESERVED,
                    ),
                )
                if cursor.rowcount != 1:
                    connection.execute("ROLLBACK")
                    raise RuntimeError("orphan repair effect reservation CAS rejected")
                current = connection.execute(
                    "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
                ).fetchone()
                connection.execute("COMMIT")
                assert current is not None
                return self._record(current, decision=DECISION_INDETERMINATE)
            if state != STATE_UNCHANGED:
                connection.execute("ROLLBACK")
                raise RuntimeError(f"unknown simple fixer effect state: {state!r}")
            if int(row["unchanged_attempts"]) >= max_unchanged_attempts:
                connection.execute(
                    "UPDATE repair_effects SET state = ?, updated_at = ? WHERE repair_identity_key = ?",
                    (STATE_EXHAUSTED, now, key),
                )
                current = connection.execute(
                    "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
                ).fetchone()
                connection.execute("COMMIT")
                assert current is not None
                return self._record(current, decision=DECISION_EXHAUSTED)

            reservation_id = str(uuid.uuid4())
            cursor = connection.execute(
                """
                UPDATE repair_effects
                SET state = ?, reservation_id = ?, reservation_owner_token = ?,
                    total_attempts = total_attempts + 1, effect_outcome = '',
                    after_fingerprint = '', updated_at = ?
                WHERE repair_identity_key = ? AND state = ?
                """,
                (STATE_RESERVED, reservation_id, owner_token, now, key, STATE_UNCHANGED),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RuntimeError("repair effect retry reservation CAS rejected")
            current = connection.execute(
                "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
            ).fetchone()
            connection.execute("COMMIT")
            assert current is not None
            return self._record(current, decision=DECISION_RESERVED)

    def record_outcome(
        self,
        identity: Mapping[str, Any] | None,
        *,
        reservation_id: str,
        owner_token: str,
        before_fingerprint: str,
        after_fingerprint: str = "",
        error: str = "",
        max_unchanged_attempts: int,
    ) -> MutationReservation:
        """CAS one reserved effect to a durable terminal/intermediate outcome."""

        _normalized, key = self._identity(identity)
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                raise RuntimeError("repair effect reservation is missing")
            if (
                str(row["state"]) != STATE_RESERVED
                or str(row["reservation_id"]) != reservation_id
                or str(row["reservation_owner_token"]) != owner_token
            ):
                connection.execute("ROLLBACK")
                raise RuntimeError("repair effect reservation CAS rejected")

            if error:
                state = STATE_INDETERMINATE
                outcome = "mutation_raised_after_reservation:" + error[:512]
                unchanged_attempts = int(row["unchanged_attempts"])
            elif before_fingerprint == after_fingerprint:
                unchanged_attempts = int(row["unchanged_attempts"]) + 1
                state = (
                    STATE_EXHAUSTED
                    if unchanged_attempts >= max_unchanged_attempts
                    else STATE_UNCHANGED
                )
                outcome = "unchanged"
            else:
                state = STATE_COMPLETED
                outcome = "completed"
                unchanged_attempts = 0
            cursor = connection.execute(
                """
                UPDATE repair_effects
                SET state = ?, unchanged_attempts = ?, effect_outcome = ?,
                    after_fingerprint = ?, updated_at = ?
                WHERE repair_identity_key = ? AND reservation_id = ? AND state = ?
                """,
                (
                    state,
                    unchanged_attempts,
                    outcome,
                    after_fingerprint,
                    now,
                    key,
                    reservation_id,
                    STATE_RESERVED,
                ),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RuntimeError("repair effect outcome CAS rejected")
            current = connection.execute(
                "SELECT * FROM repair_effects WHERE repair_identity_key = ?", (key,)
            ).fetchone()
            connection.execute("COMMIT")
            assert current is not None
            decision = {
                STATE_COMPLETED: DECISION_ADOPTED,
                STATE_UNCHANGED: "unchanged",
                STATE_EXHAUSTED: DECISION_EXHAUSTED,
                STATE_INDETERMINATE: DECISION_INDETERMINATE,
            }[state]
            return self._record(current, decision=decision)


__all__ = [
    "DECISION_ADOPTED",
    "DECISION_EXHAUSTED",
    "DECISION_INDETERMINATE",
    "DECISION_IN_FLIGHT",
    "DECISION_RESERVED",
    "LEDGER_NAME",
    "MutationReservation",
    "RepairEffectLedger",
    "STATE_COMPLETED",
    "STATE_EXHAUSTED",
    "STATE_INDETERMINATE",
    "STATE_RESERVED",
    "STATE_UNCHANGED",
    "claim_owner_token",
]
