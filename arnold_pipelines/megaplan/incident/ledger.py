"""Incident ledger append wrapper for the canonical M1 event stream."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
import os
import sys
import uuid
from typing import Any, Callable

from arnold.runtime.event_journal import NdjsonEventJournal

from arnold_pipelines.megaplan.incident.schema import (
    lifecycle_idempotency_key,
    validate_incident_event,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256(json.dumps(parts, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _valid_nbf(validator: Callable[[dict[str, Any]], dict[str, Any]], payload: dict[str, Any]) -> bool:
    try:
        validator(payload)
    except (TypeError, ValueError):
        return False
    return True


def reservation_key(projection_key: str, semantic_dispatch_fingerprint: str) -> str:
    if not isinstance(projection_key, str) or not projection_key or not isinstance(semantic_dispatch_fingerprint, str) or not semantic_dispatch_fingerprint:
        raise ValueError("reservation key requires projection key and semantic fingerprint")
    return _stable_id("reservation", projection_key, semantic_dispatch_fingerprint)


def derive_receipt_id(**kwargs: Any) -> str:
    from arnold_pipelines.megaplan.incident.schema import receipt_id
    return receipt_id(**kwargs)

_INCIDENT_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_EVENTS_FILE = "events.jsonl"


# ---------------------------------------------------------------------------
# P2 — typed runtime transition events
# ---------------------------------------------------------------------------
# One typed deviation/fallback event path. Every runtime manifest selection,
# declared deviation, and fallback consideration/decision is appended to the
# incident ledger BEFORE the caller performs any dispatch side effect. The
# append is synchronous and never swallowed: a policy rejection (ValueError)
# or a journal write failure (OSError) propagates to the caller, which MUST
# treat it as "do not dispatch". Emitting is a pure append-only ledger write
# — it never dispatches repair and never triggers a scan.

EVENT_MANIFEST_SELECTED = "runtime.manifest_selected"
EVENT_DEVIATION_DECLARED = "runtime.deviation_declared"
EVENT_FALLBACK_CONSIDERED = "runtime.fallback_considered"
EVENT_FALLBACK_TAKEN = "runtime.fallback_taken"
EVENT_FALLBACK_REJECTED = "runtime.fallback_rejected"

RUNTIME_TRANSITION_EVENT_TYPES: tuple[str, ...] = (
    EVENT_MANIFEST_SELECTED,
    EVENT_DEVIATION_DECLARED,
    EVENT_FALLBACK_CONSIDERED,
    EVENT_FALLBACK_TAKEN,
    EVENT_FALLBACK_REJECTED,
)

# Failure-class policy: a fallback may be TAKEN only for retryable
# availability/infrastructure failures. Auth/config, semantic, schema, test,
# evidence, and post-mutation execute failures are permanent deviations —
# they must be recorded as REJECTED, never masked behind a fallback.
RETRYABLE_FAILURE_CLASSES: frozenset[str] = frozenset(
    {"availability", "infrastructure"}
)
NON_RETRYABLE_FAILURE_CLASSES: frozenset[str] = frozenset(
    {"auth", "config", "semantic", "schema", "test", "evidence", "execute"}
)
KNOWN_FAILURE_CLASSES: frozenset[str] = (
    RETRYABLE_FAILURE_CLASSES | NON_RETRYABLE_FAILURE_CLASSES
)

_EVENT_ID_PREFIXES: dict[str, str] = {
    EVENT_MANIFEST_SELECTED: "runtime-manifest-selected",
    EVENT_DEVIATION_DECLARED: "runtime-deviation-declared",
    EVENT_FALLBACK_CONSIDERED: "runtime-fallback-considered",
    EVENT_FALLBACK_TAKEN: "runtime-fallback-taken",
    EVENT_FALLBACK_REJECTED: "runtime-fallback-rejected",
}

_DEFAULT_OUTCOMES: dict[str, str] = {
    EVENT_MANIFEST_SELECTED: "selected",
    EVENT_DEVIATION_DECLARED: "declared",
    EVENT_FALLBACK_CONSIDERED: "considered",
    EVENT_FALLBACK_TAKEN: "taken",
    EVENT_FALLBACK_REJECTED: "rejected",
}

_DEFAULT_SUMMARIES: dict[str, str] = {
    EVENT_MANIFEST_SELECTED: "runtime manifest selected",
    EVENT_DEVIATION_DECLARED: "runtime deviation declared",
    EVENT_FALLBACK_CONSIDERED: "runtime fallback considered",
    EVENT_FALLBACK_TAKEN: "runtime fallback taken",
    EVENT_FALLBACK_REJECTED: "runtime fallback rejected",
}


def is_retryable_failure_class(failure_class: str | None) -> bool:
    """True iff *failure_class* is a retryable availability/infrastructure class."""
    return failure_class in RETRYABLE_FAILURE_CLASSES


def _normalize_chain_digest(digest: str) -> str:
    """Normalize a ``chain_spec_sha256`` contract digest, or ``\"\"`` when empty."""
    digest = str(digest).strip()
    if not digest:
        return ""
    if digest.startswith("sha256:"):
        hex_part = digest[len("sha256:") :]
        if len(hex_part) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in hex_part
        ):
            raise ValueError(
                "chain_spec_sha256 must be 'sha256:' followed by 64 hex chars "
                f"(got {digest!r})"
            )
        return "sha256:" + hex_part.lower()
    return digest


# ---------------------------------------------------------------------------
# M3 — lifecycle idempotency across the journal boundary (T4)
# ---------------------------------------------------------------------------
# The strict Maintenance journal compares the canonical lifecycle idempotency
# key recorded at the append boundary (:func:`lifecycle_idempotency_key`):
# operational lifecycle rows (repair request, source change, installation,
# retrigger, progress, checkpoint, terminal, recurrence, escalation) compare
# their strict action key — so DISTINCT actions for ONE occurrence coexist —
# while legacy M2 rows (detection / efficiency_analysis / audit_report) fall
# back to ``occurrence_id`` and keep the exact historical behavior.  Exact
# retries deduplicate (same key + same canonical digest), divergent reuse
# raises :class:`MaintenanceEventConflict` without advancing the journal, and
# the atomic lookup → decide → append critical section is unchanged.


def strict_maintenance_model(payload: dict[str, Any]) -> Any:
    """Strict-decode *payload* as ``MaintenanceEvent`` or ``OperationalEvent``.

    Legacy M2 rows decode as :class:`MaintenanceEvent`; M3 operational
    lifecycle rows decode as :class:`OperationalEvent`.  A malformed payload
    raises ``MaintenanceCodecError`` — a model/digest is never derived from
    guessed values.
    """
    from arnold_pipelines.megaplan.maintenance.events import (
        MaintenanceEvent,
        OperationalEvent,
    )
    from arnold_pipelines.megaplan.maintenance.identity import (
        MaintenanceCodecError,
        strict_loads,
    )

    try:
        return strict_loads(MaintenanceEvent, payload)
    except MaintenanceCodecError:
        return strict_loads(OperationalEvent, payload)


def strict_maintenance_digest(payload: dict[str, Any]) -> str:
    """Return the canonical content digest of a strict Maintenance payload."""
    from arnold_pipelines.megaplan.maintenance.identity import canonical_digest

    return canonical_digest(strict_maintenance_model(payload))


def record_matches_lifecycle_key(stored: dict[str, Any], idempotency_key: str) -> bool:
    """Return whether a stored record's payload carries *idempotency_key*.

    The comparison uses the canonical lifecycle idempotency key recorded at
    the journal boundary (:func:`lifecycle_idempotency_key`): operational
    rows compare their strict action key, legacy rows fall back to
    ``occurrence_id``.  Records that cannot carry a lifecycle key (legacy
    non-Maintenance incident events) never match.
    """
    try:
        return lifecycle_idempotency_key(stored) == idempotency_key
    except ValueError:
        return False


class _IncidentEventJournal(NdjsonEventJournal):
    """Reuse runtime journal locking/seq semantics with the M1 filename."""

    def __init__(self, artifact_root: Path) -> None:
        super().__init__(artifact_root)
        self._ndjson_path = self._root / _EVENTS_FILE

    # ── Maintenance routing: atomic lookup/append keyed by occurrence ──────

    def _read_records(self) -> list[dict[str, Any]]:
        """Parse every committed record from ``events.jsonl`` (append order)."""
        if not self._ndjson_path.exists():
            return []
        records: list[dict[str, Any]] = []
        with open(self._ndjson_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _emit_locked(
        self,
        seq_fd: int,
        *,
        kind: str,
        payload: dict[str, Any],
        idempotency_key: str,
        init_ts: datetime | None,
    ) -> dict[str, Any]:
        """Append one record while the caller holds the seq-sidecar flock."""
        try:
            raw = os.read(seq_fd, 128)
            current = (
                int(raw.strip()) if raw.strip() else self._recover_durable_sequence()
            )
        except (ValueError, FileNotFoundError):
            current = self._recover_durable_sequence()
        new_seq = current + 1
        os.lseek(seq_fd, 0, os.SEEK_SET)
        os.write(seq_fd, str(new_seq).encode("ascii"))
        os.ftruncate(seq_fd, os.lseek(seq_fd, 0, os.SEEK_CUR))
        os.fsync(seq_fd)

        ts_utc = datetime.now(timezone.utc)
        event: dict[str, Any] = {
            "seq": new_seq,
            "schema_version": 1,
            "ts_utc": ts_utc.isoformat(),
            "ts_rel_init_s": (
                (ts_utc - init_ts).total_seconds() if init_ts is not None else None
            ),
            "kind": kind,
            "payload": payload,
            "idempotency_key": idempotency_key,
        }
        line = json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with open(self._ndjson_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return event

    def lookup_maintenance(self, idempotency_key: str) -> dict[str, Any] | None:
        """Return the committed record for *idempotency_key*, or ``None``.

        *idempotency_key* is the canonical lifecycle idempotency key recorded
        at the journal boundary (SD2 + M3 Step 2): the strict action key for
        operational lifecycle rows, with a legacy fallback to ``occurrence_id``
        for M2 detection / efficiency_analysis / audit_report rows.  Only
        records whose payload carries the exact lifecycle key are considered;
        other records (legacy non-Maintenance incident events) are skipped.
        """
        for record in self._read_records():
            stored = record.get("payload") or {}
            if record_matches_lifecycle_key(stored, idempotency_key):
                return record
        return None

    def append_maintenance(
        self,
        *,
        kind: str,
        payload: dict[str, Any],
        idempotency_key: str,
        digest: str,
    ) -> dict[str, Any]:
        """Atomically append one strict Maintenance payload with dedupe.

        Runs the full lookup → decide → append critical section under the
        journal's ``fcntl.flock`` on the seq sidecar, so concurrent writers
        cannot interleave between the duplicate check and the append.

        *idempotency_key* is the canonical lifecycle idempotency key of
        *payload* (strict action key for operational rows, ``occurrence_id``
        fallback for legacy M2 rows):

        * an exact duplicate (same lifecycle key AND same canonical digest)
          returns the PRIOR committed record — nothing is appended;
        * a divergent duplicate (same lifecycle key, different canonical
          digest) raises :class:`MaintenanceEventConflict` — nothing is
          appended;
        * otherwise the record is appended once and returned.

        Distinct lifecycle actions for one occurrence carry distinct action
        keys, so they append as separate records while exact retries of the
        same action deduplicate.
        """
        # Canonical validation up front: the payload must strict-decode (as a
        # MaintenanceEvent or an OperationalEvent) and its digest must be
        # reproducible from the canonical codec.
        strict_maintenance_digest(payload)

        init_ts = self._load_init_ts()
        seq_fd = os.open(str(self._seq_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(seq_fd, fcntl.LOCK_EX)
            for record in self._read_records():
                stored = record.get("payload") or {}
                if not record_matches_lifecycle_key(stored, idempotency_key):
                    continue
                stored_digest = strict_maintenance_digest(stored)
                if stored_digest == digest:
                    return record
                raise MaintenanceEventConflict(
                    f"maintenance idempotency conflict for lifecycle key "
                    f"{idempotency_key!r}: stored digest {stored_digest} "
                    f"!= incoming digest {digest}; nothing appended"
                )
            appended = self._emit_locked(
                seq_fd,
                kind=kind,
                payload=payload,
                idempotency_key=idempotency_key,
                init_ts=init_ts,
            )
            fcntl.flock(seq_fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(seq_fd)
            except OSError:
                pass
        if init_ts is None:
            self._write_init_ts(datetime.now(timezone.utc))
        return appended


class MaintenanceEventConflict(ValueError):
    """Raised when a Maintenance event reuses an occurrence idempotency
    identity with a different canonical digest.

    The conflicting event is NOT appended; the ledger is left unchanged.
    """


class IncidentLedger:
    """Append-only incident ledger rooted at ``<root>/.megaplan/incident-ledger``."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path.cwd() if root is None else Path(root)
        if self._root.exists() and not self._root.is_dir():
            raise ValueError("ledger root must be a directory")
        self._ledger_dir = self._root / _INCIDENT_LEDGER_DIR
        self._journal = _IncidentEventJournal(self._ledger_dir)

    @property
    def ledger_dir(self) -> Path:
        return self._ledger_dir

    @property
    def events_path(self) -> Path:
        return self._ledger_dir / _EVENTS_FILE

    # ── NBF single transaction authority ────────────────────────────────
    def read_nbf_events(self) -> list[dict[str, Any]]:
        """Return complete NBF records in append order.

        A physically torn JSON line is an uncommitted write and is ignored;
        valid JSON carrying an invalid NBF payload is corruption and fails
        closed.  Silently dropping the latter would turn forged history into
        an apparently healthy projection.
        """
        from arnold_pipelines.megaplan.incident.schema import validate_nbf_event
        valid = []
        for record in self._journal._read_records():
            payload = record.get("payload")
            if not (isinstance(payload, dict) and str(record.get("kind", "")).startswith("incident.nbf")):
                continue
            validate_nbf_event(payload, _allow_persisted_changed_precondition=True)
            valid.append(record)
        return valid

    def _nbf_event_id(self, payload: dict[str, Any]) -> str:
        event_id = payload.get("event_id") or payload.get("disposition_id") or payload.get("observation_id") or payload.get("reconciliation_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("NBF event requires a canonical event identity")
        return event_id

    def _append_nbf_locked(self, seq_fd: int, payload: dict[str, Any], records: list[dict[str, Any]], *, event_type: str | None = None, _changed_precondition: Any = None) -> dict[str, Any]:
        """Validate and append with the caller's flock held.

        All compare/read/consume decisions must use ``records`` captured after
        acquiring the sequence-sidecar lock.  This is deliberately a small
        extension of the existing journal door, not a second transaction API.
        """
        """Validate and append one typed record under the existing journal lock.

        Event IDs are idempotent.  This is intentionally the only write door
        used by the NBF primitives; legacy ``append_event`` remains untouched.
        """
        from arnold_pipelines.megaplan.incident.schema import validate_nbf_event
        payload = validate_nbf_event(payload, _changed_precondition=_changed_precondition)
        event_id = self._nbf_event_id(payload)
        for record in records:
            stored_payload = record.get("payload") or {}
            if (payload.get("event_type") == "supervision_confirmation_consumed"
                    and stored_payload.get("event_type") == "supervision_confirmation_consumed"
                    and stored_payload.get("confirmation_id") == payload.get("confirmation_id")):
                if stored_payload == payload:
                    return record
                raise ValueError("confirmation was already consumed by another scan")
            stored_id = stored_payload.get("event_id") or stored_payload.get("disposition_id") or stored_payload.get("observation_id") or stored_payload.get("reconciliation_id")
            if stored_id == event_id:
                if stored_payload == payload:
                    return record
                raise ValueError(f"conflicting NBF event_id: {event_id}")
        return self._journal._emit_locked(seq_fd, kind=f"incident.nbf.{event_type or payload['event_type']}", payload=payload, idempotency_key=event_id, init_ts=self._journal._load_init_ts())

    def _append_nbf(self, payload: dict[str, Any], *, event_type: str | None = None, _changed_precondition: Any = None) -> dict[str, Any]:
        """Validate and append one typed record through the single journal door."""
        # Validate before touching the filesystem, then validate again in the
        # locked helper so callers cannot bypass the append authority.
        from arnold_pipelines.megaplan.incident.schema import validate_nbf_event
        validate_nbf_event(payload, _changed_precondition=_changed_precondition)
        seq_fd = os.open(str(self._journal._seq_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(seq_fd, fcntl.LOCK_EX)
            return self._append_nbf_locked(seq_fd, payload, self._journal._read_records(), event_type=event_type, _changed_precondition=_changed_precondition)
        finally:
            try:
                fcntl.flock(seq_fd, fcntl.LOCK_UN)
            finally:
                os.close(seq_fd)

    def _locked(self):
        """Context manager for NBF operations needing a projected compare."""
        from contextlib import contextmanager
        @contextmanager
        def cm():
            fd = os.open(str(self._journal._seq_path), os.O_RDWR | os.O_CREAT, 0o644)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield fd, self._journal._read_records()
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
        return cm()

    def _project_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Deterministically rebuild all NBF state from the one journal."""
        from arnold_pipelines.megaplan.incident.schema import validate_nbf_event
        checked: list[dict[str, Any]] = []
        seen_ids: dict[str, dict[str, Any]] = {}
        for record in records:
            payload = record.get("payload")
            if not (isinstance(payload, dict) and str(record.get("kind", "")).startswith("incident.nbf")):
                checked.append(record)
                continue
            validate_nbf_event(payload, _allow_persisted_changed_precondition=True)
            identity = self._nbf_event_id(payload)
            prior = seen_ids.get(identity)
            if prior is not None and prior != payload:
                raise ValueError(f"conflicting committed NBF event: {identity}")
            if prior is None:
                seen_ids[identity] = payload
                checked.append(record)
        records = checked
        reservations: dict[str, dict[str, Any]] = {}
        terminals: dict[str, dict[str, Any]] = {}
        dispositions: dict[str, dict[str, Any]] = {}
        changes: dict[str, dict[str, Any]] = {}
        confirmations: dict[str, dict[str, Any]] = {}
        provider_streams: dict[str, dict[str, Any]] = {}
        latest_stream_key: str | None = None
        active_provider_key: str | None = None
        active_base: tuple[Any, ...] | None = None
        for record in records:
            if not (isinstance(record.get("payload"), dict) and str(record.get("kind", "")).startswith("incident.nbf")):
                continue
            p = record["payload"]
            typ = p.get("event_type")
            if typ == "admission_reserved":
                key = p["reservation_key"]
                reservations[key] = {
                    **p,
                    "event_id": p["event_id"],
                    "closed": False,
                    "reconciliation": None,
                    "accepted_launch": False,
                }
                consumed = p.get("changed_precondition_event_id")
                if consumed in changes:
                    changes[consumed]["consumed"] = True
            elif typ == "provider_route_child_reserved":
                key = p["reservation_key"]
                reservations[key] = {
                    **p,
                    "event_id": p["event_id"],
                    "logical_dispatch_id": p["child_logical_dispatch_id"],
                    "dispatch_family_id": p["child_dispatch_family_id"],
                    "physical_door_id": p["child_physical_door_id"],
                    "semantic_dispatch_fingerprint": p["child_semantic_dispatch_fingerprint"],
                    "selected_spec": p["to_spec"],
                    "admission_receipt_id": derive_receipt_id(
                        reservation_event_id=p["event_id"],
                        plan_id=p["plan_id"],
                        phase=p["phase"],
                        dispatch_family_id=p["child_dispatch_family_id"],
                        logical_dispatch_id=p["child_logical_dispatch_id"],
                        physical_door_id=p["child_physical_door_id"],
                        semantic_dispatch_fingerprint=p["child_semantic_dispatch_fingerprint"],
                        derivation_version=p["receipt_derivation_version"],
                    ),
                    "closed": False,
                    "reconciliation": None,
                    "accepted_launch": False,
                }
                consumed = p.get("consumed_changed_precondition_event_id") or p.get("authorizing_event_id")
                if consumed in changes:
                    changes[consumed]["consumed"] = True
            elif typ == "worker_disposition":
                dispositions[p["disposition_id"]] = p
            elif typ == "worker_terminal_outcome":
                terminals[p["terminal_outcome_id"]] = p
                key = p.get("reservation_key") or reservation_key(p.get("projection_key", ""), p.get("semantic_dispatch_fingerprint", ""))
                k = p.get("provider_failure_key")
                reservation = reservations.get(key, {})
                base = (p.get("plan_id"), p.get("phase"), p.get("primary_spec") or reservation.get("primary_spec") or p.get("selected_spec"), p.get("configured_fallback_chain_identity", "") or reservation.get("configured_fallback_chain_identity", ""))
                outcome_kind = p.get("outcome_kind")
                stream = None
                if k:
                    stream_key = _stable_id("provider-stream", *base, k)
                    stream = provider_streams.setdefault(stream_key, {"provider_failure_key": k, "plan_id": base[0], "phase": base[1], "primary_spec": base[2], "selected_spec": p.get("selected_spec"), "configured_fallback_chain_identity": base[3], "observation_streak": 0, "broken": False})
                    latest_stream_key = stream_key
                    active_base = base
                if outcome_kind == "provider_exhausted" and stream is not None:
                    stream["observation_streak"] = 1 if stream["broken"] else stream["observation_streak"] + 1
                    stream["broken"] = False
                    active_provider_key = k
                elif outcome_kind == "success" and stream is not None:
                    stream["observation_streak"] = 0
                    stream["broken"] = False
                    active_provider_key = None
                elif outcome_kind in {"ordinary_terminal_failure", "worker_disposition"} and stream is not None:
                    stream["observation_streak"] = 0
                    stream["broken"] = True
                # Terminal projection precedes reservation closure.  Keeping
                # this assignment after replaying the terminal's provider
                # transition makes the ordering explicit and deterministic.
                if key in reservations:
                    reservations[key]["closed"] = True
            elif typ == "changed_precondition":
                changes[p["event_id"]] = {**p, "consumed": False}
                before, after = p.get("provider_failure_key_before"), p.get("provider_failure_key_after")
                if before and after and before != after:
                    matching = [s for s in provider_streams.values() if s.get("provider_failure_key") == before]
                    for old in matching:
                        new_key = _stable_id("provider-stream", old.get("plan_id"), old.get("phase"), old.get("primary_spec"), old.get("configured_fallback_chain_identity", ""), after)
                        provider_streams[new_key] = {**old, "provider_failure_key": after, "observation_streak": 0, "broken": False}
                        latest_stream_key = new_key
                        active_provider_key = after
            elif typ == "changed_precondition_consumed":
                if p.get("changed_precondition_event_id") in changes:
                    changes[p["changed_precondition_event_id"]]["consumed"] = True
            elif typ == "reservation_reconciled":
                for key, value in reservations.items():
                    if value.get("event_id") == p.get("reservation_event_id") or value.get("reservation_event_id") == p.get("reservation_event_id"):
                        value["reconciliation"] = p["resolution"]
                        value["closed"] = p["resolution"] != "permanent_hold_ambiguous"
            elif typ in {"supervision_confirmation_observed", "supervision_confirmation_replaced"}:
                if typ == "supervision_confirmation_replaced" and p.get("prior_confirmation_event_id"):
                    for prior in confirmations.values():
                        if prior.get("event_id") == p["prior_confirmation_event_id"]:
                            prior["replaced"] = True
                            prior["expired"] = True
                confirmations[p["confirmation_id"]] = {**p, "consumed": False, "expired": False, "replaced": False}
            elif typ in {"supervision_confirmation_consumed", "supervision_confirmation_expired"}:
                if p.get("confirmation_id") in confirmations:
                    if typ == "supervision_confirmation_consumed":
                        confirmations[p["confirmation_id"]]["consumed"] = True
                    else:
                        confirmations[p["confirmation_id"]]["expired"] = True
            elif typ == "controlled_adapter_state":
                for reservation in reservations.values():
                    if (reservation.get("event_id") == p.get("reservation_event_id")
                            and reservation.get("admission_receipt_id") == p.get("admission_receipt_id")):
                        if p.get("launch_state_identity") == "accepted":
                            reservation["accepted_launch"] = True
                            reservation["accepted_launch_marker"] = dict(p)
        latest = provider_streams.get(latest_stream_key, {"provider_failure_key": None, "observation_streak": 0})
        return {"projection_version": len(records), "reservations": reservations, "terminals": terminals, "dispositions": dispositions, "changed_preconditions": changes, "confirmations": confirmations, "active_provider_failure_key": active_provider_key, "observation_streak": latest.get("observation_streak", 0), "provider_streaks": provider_streams}

    def projection(self) -> dict[str, Any]:
        return self._project_records(self.read_nbf_events())

    def reserve(self, *, plan_id: str, phase: str, projection_key: str, semantic_dispatch_fingerprint: str, logical_dispatch_id: str, dispatch_family_id: str, physical_door_id: str = "default-door", expected_projection_version: int | None = None, changed_precondition_event_id: str | None = None, selected_spec: str = "unspecified", primary_spec: str | None = None, configured_fallback_chain_identity: str = "", execution_context_identity: str = "", actor: str = "megaplan") -> dict[str, Any]:
        key = reservation_key(projection_key, semantic_dispatch_fingerprint)
        with self._locked() as (fd, records):
            projection = self._project_records(records)
            if expected_projection_version is not None and expected_projection_version != projection["projection_version"]:
                raise ValueError("reservation projection version mismatch")
            current = projection["reservations"].get(key)
            if current and not current.get("closed"):
                raise ValueError("active reservation already exists for projection key and fingerprint")
            if current and current.get("reconciliation") != "released_no_launch" and not changed_precondition_event_id:
                raise ValueError("terminal fingerprint requires a changed precondition")
            if changed_precondition_event_id:
                change = projection["changed_preconditions"].get(changed_precondition_event_id)
                if not change or change.get("consumed"):
                    raise ValueError("changed precondition is missing or already consumed")
                if change.get("plan_id") != plan_id or change.get("phase") != phase:
                    raise ValueError("changed precondition context mismatch")
                if change.get("logical_dispatch_id") not in (None, logical_dispatch_id):
                    raise ValueError("changed precondition logical identity mismatch")
                if change.get("provider_failure_key_before") and change.get("provider_failure_key_after") and change.get("provider_failure_key_before") == change.get("provider_failure_key_after") and change.get("reason") != "provider_recovery_verified":
                    raise ValueError("unchanged provider key cannot authorize this reservation")
            event_id = _stable_id("admission_reserved", key, logical_dispatch_id, str(projection["projection_version"]))
            payload = {"schema_version": 1, "event_type": "admission_reserved", "event_id": event_id, "plan_id": plan_id, "phase": phase, "projection_key": projection_key, "reservation_key": key, "semantic_dispatch_fingerprint": semantic_dispatch_fingerprint, "logical_dispatch_id": logical_dispatch_id, "dispatch_family_id": dispatch_family_id, "physical_door_id": physical_door_id, "selected_spec": selected_spec, "expected_projection_version": projection["projection_version"], "changed_precondition_event_id": changed_precondition_event_id, "recorded_at": _now(), "actor": actor, "admission_receipt_id": derive_receipt_id(
                    reservation_event_id=event_id,
                    plan_id=plan_id,
                    phase=phase,
                    dispatch_family_id=dispatch_family_id,
                    logical_dispatch_id=logical_dispatch_id,
                    physical_door_id=physical_door_id,
                    semantic_dispatch_fingerprint=semantic_dispatch_fingerprint,
                )}
            payload["primary_spec"] = primary_spec or selected_spec
            payload["configured_fallback_chain_identity"] = configured_fallback_chain_identity
            if execution_context_identity:
                payload["execution_context_identity"] = execution_context_identity
            # The receipt is returned only after _emit_locked has fsynced the
            # reservation.  The payload still carries the deterministic value
            # so replay can validate the exact committed context.
            return self._append_nbf_locked(fd, payload, records)

    def append_controlled_adapter_state(self, *, reservation_event_id: str, admission_receipt_id: str, physical_door_id: str, launch_state_identity: str, phase: str | None = None, selected_spec: str | None = None, primary_spec: str | None = None, logical_dispatch_id: str | None = None, worker_identity: Any = None, started_at: str | None = None, finished_at: str | None = None, actor: str = "controlled-adapter") -> dict[str, Any]:
        """Persist the adapter's launch proof through the canonical NBF door."""
        payload = {
            "schema_version": 1,
            "event_type": "controlled_adapter_state",
            "event_id": _stable_id("controlled-adapter", reservation_event_id, admission_receipt_id, launch_state_identity, str(phase), str(selected_spec), str(logical_dispatch_id)),
            "reservation_event_id": reservation_event_id,
            "admission_receipt_id": admission_receipt_id,
            "physical_door_id": physical_door_id,
            "launch_state_identity": launch_state_identity,
            "recorded_at": _now(),
            "actor": actor,
        }
        if launch_state_identity == "accepted":
            payload.update({"phase": phase, "selected_spec": selected_spec, "primary_spec": primary_spec, "logical_dispatch_id": logical_dispatch_id, "worker_identity": worker_identity, "started_at": started_at, "finished_at": finished_at})
        with self._locked() as (fd, records):
            reservation = next((r.get("payload", {}) for r in records if r.get("payload", {}).get("event_type") in {"admission_reserved", "provider_route_child_reserved"} and r.get("payload", {}).get("event_id") == reservation_event_id), None)
            if reservation is None or reservation.get("admission_receipt_id", admission_receipt_id) != admission_receipt_id:
                raise ValueError("controlled adapter state is not bound to reservation receipt")
            if launch_state_identity == "accepted":
                prior = [r.get("payload", {}) for r in records if r.get("payload", {}).get("event_type") == "controlled_adapter_state" and r.get("payload", {}).get("reservation_event_id") == reservation_event_id and r.get("payload", {}).get("launch_state_identity") == "accepted"]
                if prior and prior[0] != payload:
                    raise ValueError("accepted launch marker already exists")
            return self._append_nbf_locked(fd, payload, records)

    def append_terminal_outcome(self, *, outcome: Any, reservation_event_id: str, projection_key: str, physical_door_id: str = "default-door", actor: str = "megaplan", execution_context_identity: str = "", primary_spec: str | None = None, configured_fallback_chain_identity: str | None = None) -> dict[str, Any]:
        from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
        if isinstance(outcome, dict):
            outcome = DispatchOutcome.from_dict(outcome)
        if not isinstance(outcome, DispatchOutcome):
            raise ValueError("terminal outcome must be a DispatchOutcome")
        if outcome.kind == "no_launch" or outcome.kind == "unresolved_launch":
            raise ValueError("scheduling outcomes have no worker terminal event")
        with self._locked() as (fd, records):
            p = self._project_records(records)
            reservation = next((r for r in p["reservations"].values() if r.get("event_id") == reservation_event_id), None)
            if reservation is None:
                raise ValueError("terminal outcome references unknown reservation")
            # Reservation context is authoritative; never let a caller route a
            # terminal to a different phase/fingerprint/logical dispatch.
            expected_receipt = reservation.get("admission_receipt_id") or self.derive_receipt(next(r for r in records if r.get("payload", {}).get("event_id") == reservation_event_id))
            bound_transport = bool(expected_receipt and outcome.admission_receipt_id == expected_receipt)
            context_fields = (("plan_id", outcome.plan_id), ("phase", outcome.phase), ("projection_key", projection_key), ("semantic_dispatch_fingerprint", outcome.semantic_dispatch_fingerprint), ("logical_dispatch_id", outcome.logical_dispatch_id), ("dispatch_family_id", outcome.dispatch_family_id), ("selected_spec", outcome.selected_spec))
            for name, value in context_fields:
                expected = reservation.get(name)
                if expected != value:
                    raise ValueError(f"terminal outcome reservation context mismatch: {name}")
            if not expected_receipt or not bound_transport:
                raise ValueError("terminal outcome receipt is not bound to reservation")
            if reservation.get("physical_door_id", "") != physical_door_id:
                raise ValueError("terminal outcome reservation context mismatch: physical_door_id")
            if outcome.worker_identity is None or not outcome.started_at or not outcome.finished_at:
                raise ValueError("terminal outcome requires persisted accepted-launch context")
            stored_execution = reservation.get("execution_context_identity", "")
            if stored_execution != execution_context_identity:
                raise ValueError("terminal outcome reservation context mismatch: execution_context_identity")
            expected_primary = reservation.get("primary_spec", "")
            if primary_spec is not None and primary_spec != expected_primary:
                raise ValueError("terminal outcome reservation context mismatch: primary_spec")
            expected_chain = reservation.get("configured_fallback_chain_identity", "")
            if configured_fallback_chain_identity is not None and configured_fallback_chain_identity != expected_chain:
                raise ValueError("terminal outcome reservation context mismatch: configured_fallback_chain_identity")
            accepted_markers = [r.get("payload", {}) for r in records
                                if r.get("payload", {}).get("event_type") == "controlled_adapter_state"
                                and r.get("payload", {}).get("reservation_event_id") == reservation_event_id
                                and r.get("payload", {}).get("admission_receipt_id") == expected_receipt
                                and r.get("payload", {}).get("launch_state_identity") == "accepted"]
            if len(accepted_markers) != 1:
                raise ValueError("terminal outcome requires exactly one persisted accepted launch marker")
            marker = accepted_markers[0]
            for name, value in (("phase", outcome.phase), ("selected_spec", outcome.selected_spec), ("logical_dispatch_id", outcome.logical_dispatch_id), ("worker_identity", outcome.worker_identity), ("started_at", outcome.started_at), ("finished_at", outcome.finished_at), ("physical_door_id", physical_door_id)):
                if marker.get(name) != value:
                    raise ValueError(f"terminal outcome accepted-launch marker mismatch: {name}")
            if marker.get("primary_spec") != expected_primary:
                raise ValueError("terminal outcome accepted-launch marker mismatch: primary_spec")
            if outcome.kind == "worker_disposition":
                disp = p["dispositions"].get(outcome.disposition_id)
                if not disp:
                    raise ValueError("worker disposition must already be committed")
                for n in ("admission_receipt_id", "semantic_dispatch_fingerprint", "phase", "selected_spec", "logical_dispatch_id", "worker_identity"):
                    if disp.get(n) != getattr(outcome, n):
                        raise ValueError(f"worker disposition context mismatch: {n}")
            terminal_id = outcome.terminal_outcome_event_id or _stable_id("worker_terminal_outcome", reservation_event_id, outcome.kind)
            for existing in p["terminals"].values():
                if existing.get("reservation_event_id") == reservation_event_id:
                    if existing.get("outcome_kind") == outcome.kind:
                        comparable = {
                            "terminal_outcome_id": terminal_id,
                            "outcome_kind": outcome.kind,
                            "disposition_id": outcome.disposition_id,
                            "admission_receipt_id": outcome.admission_receipt_id,
                            "semantic_dispatch_fingerprint": outcome.semantic_dispatch_fingerprint,
                            "logical_dispatch_id": outcome.logical_dispatch_id,
                            "worker_identity": outcome.worker_identity,
                        }
                        if all(existing.get(name) == value for name, value in comparable.items()):
                            return next(r for r in records if r.get("payload", {}).get("terminal_outcome_id") == existing["terminal_outcome_id"])
                        raise ValueError("conflicting terminal linkage for reservation")
                    raise ValueError("reservation already has a conflicting terminal outcome")
            if reservation.get("closed"):
                raise ValueError("reservation is already closed")
            provider = outcome.provider_evidence if isinstance(outcome.provider_evidence, dict) else {}
            payload = {"schema_version": 1, "event_type": "worker_terminal_outcome", "event_id": terminal_id, "terminal_outcome_id": terminal_id, "outcome_kind": outcome.kind, "plan_id": outcome.plan_id, "phase": outcome.phase, "projection_key": projection_key, "reservation_key": reservation.get("reservation_key"), "dispatch_family_id": outcome.dispatch_family_id, "logical_dispatch_id": outcome.logical_dispatch_id, "admission_receipt_id": outcome.admission_receipt_id, "reservation_event_id": reservation_event_id, "semantic_dispatch_fingerprint": outcome.semantic_dispatch_fingerprint, "selected_spec": outcome.selected_spec, "physical_door_id": physical_door_id, "launch_state": outcome.launch_state, "worker_identity": outcome.worker_identity, "started_at": outcome.started_at, "finished_at": outcome.finished_at, "success_payload": outcome.success_payload, "terminal_failure": outcome.terminal_failure, "provider_evidence": provider, "provider_failure_key": outcome.provider_failure_key or provider.get("provider_failure_key"), "disposition_id": outcome.disposition_id, "execution_context_identity": execution_context_identity, "recorded_at": _now(), "actor": actor}
            payload["primary_spec"] = expected_primary
            payload["configured_fallback_chain_identity"] = expected_chain
            return self._append_nbf_locked(fd, payload, records)

    def append_disposition(self, disposition: Any) -> dict[str, Any]:
        payload = disposition.to_dict() if hasattr(disposition, "to_dict") else dict(disposition)
        with self._locked() as (fd, records):
            if payload.get("event_type") == "worker_disposition" and payload.get("confirmation_event_id"):
                projected = self._project_records(records)
                confirmation = projected["confirmations"].get(payload["confirmation_event_id"])
                if not confirmation or not confirmation.get("consumed"):
                    raise ValueError("required confirmation is missing or not consumed")
            return self._append_nbf_locked(fd, payload, records)

    def append_changed_precondition(self, event: Any) -> dict[str, Any]:
        from arnold_pipelines.megaplan.incident.schema import ChangedPrecondition, _digest, _validate_producer_binding
        obj = event if isinstance(event, ChangedPrecondition) else ChangedPrecondition.from_dict(event)
        _validate_producer_binding(obj)
        with self._locked() as (fd, records):
            # Evidence identity is bound to a committed ledger event.  A
            # caller cannot mint a valid-looking change from an arbitrary
            # digest and then consume it as an authorization.
            cited = next((r.get("payload", {}) for r in records if r.get("payload", {}).get("event_id") == obj.evidence_event_id), None)
            if cited is None:
                raise ValueError("changed precondition evidence event is not persisted")
            if _digest(cited) != obj.evidence_digest:
                raise ValueError("changed precondition evidence digest mismatch")
            if obj.evidence_snapshot != cited:
                raise ValueError("changed precondition evidence is not the cited authoritative event")
            if obj.evidence_event_id != cited.get("event_id"):
                raise ValueError("changed precondition evidence identity is not canonical")
            if obj.reason == "provider_recovery_verified":
                if cited.get("event_type") != "provider_probe_result" or cited.get("passed") is not True:
                    raise ValueError("provider recovery requires a passed canonical probe")
                key = cited.get("provider_failure_key")
                if obj.provider_failure_key_before != key or obj.provider_failure_key_after != key:
                    raise ValueError("provider recovery key is not bound to the probe")
            return self._append_nbf_locked(fd, obj.to_dict(), records, _changed_precondition=obj)

    def reserve_provider_route_child(self, *, plan_id: str, phase: str, projection_key: str, expected_projection_version: int, transition_kind: str, from_spec: str, to_spec: str, parent_logical_dispatch_id: str, parent_terminal_event_id: str, authorizing_event_id: str, configured_fallback_chain_identity: str, precondition_identity: str, child_dispatch_family_id: str, child_logical_dispatch_id: str, child_physical_door_id: str, child_semantic_dispatch_fingerprint: str, child_route_liveness_identity: str, consumed_changed_precondition_event_id: str | None = None, receipt_derivation_version: str = "1", actor: str = "megaplan") -> dict[str, Any]:
        with self._locked() as (fd, records):
            p = self._project_records(records)
            if expected_projection_version != p["projection_version"]:
                raise ValueError("route child projection version mismatch")
            parent = next((t for t in p["terminals"].values() if t.get("terminal_outcome_id") == parent_terminal_event_id), None)
            if not parent or parent.get("outcome_kind") not in {"provider_exhausted"}:
                raise ValueError("provider child requires a canonical provider terminal parent")
            if parent.get("plan_id") != plan_id or parent.get("phase") != phase or parent.get("projection_key") != projection_key or parent.get("logical_dispatch_id") != parent_logical_dispatch_id:
                raise ValueError("provider child parent context mismatch")
            if parent.get("selected_spec") != from_spec:
                raise ValueError("provider child source route mismatch")
            authorizing = next((r.get("payload", {}) for r in records if (r.get("payload", {}).get("event_id") == authorizing_event_id or r.get("payload", {}).get("disposition_id") == authorizing_event_id)), None)
            if not authorizing or authorizing.get("event_type") not in {"provider_recovery_verified", "changed_precondition"}:
                raise ValueError("provider child requires a persisted authorizing recovery event")
            if authorizing.get("event_type") == "changed_precondition" and authorizing.get("reason") != "provider_recovery_verified":
                raise ValueError("provider child authorizer is not provider recovery")
            if authorizing.get("event_type") != "changed_precondition":
                raise ValueError("provider child authorizer must be a producer-derived recovery")
            if authorizing.get("provider_failure_key_before") != authorizing.get("provider_failure_key_after"):
                raise ValueError("provider child recovery changed the provider key")
            provider_key = authorizing.get("provider_failure_key_before")
            if not provider_key or provider_key != parent.get("provider_failure_key"):
                raise ValueError("provider child recovery key does not match parent")
            probe = next((r.get("payload", {}) for r in records
                          if r.get("payload", {}).get("event_type") == "provider_probe_result"
                          and r.get("payload", {}).get("event_id") == authorizing.get("evidence_event_id")), None)
            lease = next((r.get("payload", {}) for r in records
                          if r.get("payload", {}).get("event_type") == "provider_probe_started"
                          and r.get("payload", {}).get("probe_lease_id") == (probe or {}).get("probe_lease_id")), None)
            expected_route = f"{from_spec}->{to_spec}"
            if not probe or probe.get("passed") is not True or probe.get("provider_failure_key") != provider_key:
                raise ValueError("provider child requires a passed canonical probe result")
            if not lease or lease.get("provider_failure_key") != provider_key or lease.get("parent_reservation_event_id") != parent.get("reservation_event_id") or lease.get("phase") != phase:
                raise ValueError("provider probe lease is not bound to parent context")
            if lease.get("route_identity") not in (None, expected_route):
                raise ValueError("provider probe route context mismatch")
            if authorizing.get("evidence_snapshot") is not None:
                # The changed-precondition append path already proves this is
                # the exact committed probe payload; retain the explicit
                # comparison here as the child authorization door.
                if authorizing.get("evidence_snapshot") != probe:
                    raise ValueError("provider recovery evidence is not the cited probe")
            if any(r.get("payload", {}).get("event_type") == "provider_route_child_reserved" and r.get("payload", {}).get("authorizing_event_id") == authorizing_event_id for r in records):
                raise ValueError("provider recovery authorization already consumed")
            child_key = reservation_key(projection_key, child_semantic_dispatch_fingerprint)
            if child_key in p["reservations"] and not p["reservations"][child_key].get("closed"):
                raise ValueError("duplicate provider child reservation")
            consumed_id = consumed_changed_precondition_event_id or (authorizing_event_id if authorizing.get("event_type") == "changed_precondition" else None)
            if consumed_id:
                change = p["changed_preconditions"].get(consumed_id)
                if not change or change.get("consumed"):
                    raise ValueError("child changed precondition is missing or already consumed")
            event_id = _stable_id("provider_route_child_reserved", plan_id, phase, child_logical_dispatch_id, child_semantic_dispatch_fingerprint)
            payload = {"schema_version": 1, "event_type": "provider_route_child_reserved", "event_id": event_id, "plan_id": plan_id, "phase": phase, "projection_key": projection_key, "reservation_key": child_key, "expected_projection_version": expected_projection_version, "transition_kind": transition_kind, "from_spec": from_spec, "to_spec": to_spec, "parent_logical_dispatch_id": parent_logical_dispatch_id, "parent_terminal_event_id": parent_terminal_event_id, "authorizing_event_id": authorizing_event_id, "configured_fallback_chain_identity": configured_fallback_chain_identity, "precondition_identity": precondition_identity, "child_dispatch_family_id": child_dispatch_family_id, "child_logical_dispatch_id": child_logical_dispatch_id, "child_physical_door_id": child_physical_door_id, "child_semantic_dispatch_fingerprint": child_semantic_dispatch_fingerprint, "child_route_liveness_identity": child_route_liveness_identity, "consumed_changed_precondition_event_id": consumed_id, "receipt_derivation_version": receipt_derivation_version, "recorded_at": _now(), "actor": actor}
            return self._append_nbf_locked(fd, payload, records)

    def derive_receipt(self, event: dict[str, Any]) -> str:
        p = event.get("payload", event)
        return derive_receipt_id(reservation_event_id=p.get("event_id") or p.get("reservation_event_id"), plan_id=p["plan_id"], phase=p["phase"], dispatch_family_id=p.get("dispatch_family_id") or p.get("child_dispatch_family_id"), logical_dispatch_id=p.get("logical_dispatch_id") or p.get("child_logical_dispatch_id"), physical_door_id=p.get("physical_door_id") or p.get("child_physical_door_id"), semantic_dispatch_fingerprint=p.get("semantic_dispatch_fingerprint") or p.get("child_semantic_dispatch_fingerprint"), derivation_version=p.get("receipt_derivation_version", "1"))

    def reconcile_reservation(self, reconciliation: Any) -> dict[str, Any]:
        payload = reconciliation.to_dict() if hasattr(reconciliation, "to_dict") else dict(reconciliation)
        with self._locked() as (fd, records):
            p = self._project_records(records)
            target = next((r for r in p["reservations"].values() if r.get("event_id") == payload.get("reservation_event_id") or r.get("reservation_event_id") == payload.get("reservation_event_id")), None)
            if not target:
                raise ValueError("unknown reservation for reconciliation")
            prior = next((e["payload"] for e in records if e.get("payload", {}).get("event_type") == "reservation_reconciled" and e["payload"].get("reservation_event_id") == payload.get("reservation_event_id")), None)
            if prior is not None:
                if prior == payload:
                    return next(e for e in records if e.get("payload") == prior)
                raise ValueError("conflicting reconciliation for reservation")
            for name in ("plan_id", "phase", "projection_key", "logical_dispatch_id", "semantic_dispatch_fingerprint"):
                if payload.get(name) != target.get(name):
                    raise ValueError(f"reconciliation context mismatch: {name}")
            expected_receipt = target.get("admission_receipt_id") or self.derive_receipt(next(r for r in records if r.get("payload", {}).get("event_id") == target["event_id"]))
            if payload.get("admission_receipt_id") != expected_receipt:
                raise ValueError("reconciliation receipt is not bound to reservation")
            if target.get("closed") and payload.get("resolution") != "terminal_outcome_recovered":
                raise ValueError("closed reservation cannot be reconciled")
            evidence = []
            for evidence_id in payload.get("evidence_event_ids", ()):
                found = next((r.get("payload", {}) for r in records if r.get("payload", {}).get("event_id") == evidence_id or r.get("payload", {}).get("disposition_id") == evidence_id), None)
                if found is None:
                    raise ValueError("reconciliation evidence is not persisted")
                evidence.append(found)
            resolution = payload.get("resolution")
            if resolution == "released_no_launch":
                if payload.get("evidence_kind") != "controlled_adapter" or payload.get("launch_state_identity") != "not_started":
                    raise ValueError("blind no-launch release rejected")
                if not any(item.get("event_type") == "controlled_adapter_state" and item.get("reservation_event_id") == target["event_id"] and item.get("admission_receipt_id") == expected_receipt and item.get("launch_state_identity") == "not_started" and item.get("physical_door_id") == target.get("physical_door_id", "") for item in evidence):
                    raise ValueError("no-launch release lacks positive bound adapter evidence")
                if any(item.get("launch_state_identity") in {"entered", "accepted"} or item.get("event_type") in {"worker_terminal_outcome", "worker_disposition"} for item in evidence):
                    raise ValueError("contradictory launch evidence rejects no-launch release")
            elif resolution == "terminal_outcome_recovered":
                if payload.get("launch_state_identity") != "accepted":
                    raise ValueError("terminal recovery requires accepted launch evidence")
                terminal = next((item for item in evidence if item.get("event_type") == "worker_terminal_outcome" and item.get("terminal_outcome_id") == payload.get("terminal_outcome_event_id") and item.get("reservation_event_id") == target["event_id"] and item.get("admission_receipt_id") == expected_receipt), None)
                if terminal is None:
                    raise ValueError("terminal recovery lacks persisted canonical terminal")
                if terminal.get("outcome_kind") == "worker_disposition" and terminal.get("disposition_id") not in p["dispositions"]:
                    raise ValueError("recovered disposition is not persisted")
            elif resolution == "permanent_hold_ambiguous":
                if payload.get("launch_state_identity") != "ambiguous":
                    raise ValueError("ambiguous reconciliation requires ambiguous launch state")
            else:
                raise ValueError("unsupported reconciliation resolution")
            return self._append_nbf_locked(fd, payload, records)

    def observe_confirmation(self, payload: dict[str, Any]) -> dict[str, Any]:
        typ = payload.get("event_type")
        if typ == "supervision_confirmation_observed":
            with self._locked() as (fd, records):
                # A changed process identity is a durable replacement, not a
                # second timestamp-only observation.  Keep the new proof's
                # complete identity in the replacement event for restart
                # replay and auditability.
                projected = self._project_records(records)
                existing = projected["confirmations"].get(payload.get("confirmation_id"))
                if existing and not existing.get("expired") and not existing.get("consumed"):
                    # The first scan is durable state.  Re-observing the same
                    # identity must not replace its original timestamp/expiry.
                    return next(r for r in records if r.get("payload", {}).get("event_id") == existing.get("event_id"))
                old = next((r.get("payload", {}) for r in reversed(records)
                            if r.get("payload", {}).get("event_type") in {"supervision_confirmation_observed", "supervision_confirmation_replaced"}
                            and r.get("payload", {}).get("site_id") == payload.get("site_id")
                            and r.get("payload", {}).get("subject_class") == payload.get("subject_class")
                            and r.get("payload", {}).get("confirmation_id") != payload.get("confirmation_id")
                            and not projected["confirmations"].get(r.get("payload", {}).get("confirmation_id"), {}).get("consumed")
                            and not projected["confirmations"].get(r.get("payload", {}).get("confirmation_id"), {}).get("expired")), None)
                if old:
                    replacement = dict(payload)
                    replacement.update({"event_type": "supervision_confirmation_replaced", "event_id": _stable_id("confirmation-replaced", old.get("event_id"), payload.get("confirmation_id")), "prior_confirmation_event_id": old.get("event_id"), "replacement_reason": "identity_changed", "second_observed_at": payload.get("first_observed_at"), "second_evidence_digest": payload.get("evidence_digest"), "disposition_id": None})
                    return self._append_nbf_locked(fd, replacement, records)
                return self._append_nbf_locked(fd, payload, records)
        if typ == "supervision_confirmation_consumed":
            with self._locked() as (fd, records):
                p = self._project_records(records)
                prior = p["confirmations"].get(payload.get("confirmation_id"))
                if not prior or prior.get("consumed") or prior.get("expired"):
                    raise ValueError("confirmation missing or already consumed")
                identity_pairs = (
                    ("victim_pid", payload.get("victim_pid")),
                    ("victim_process_start_identity", payload.get("victim_process_start_identity")),
                    ("relevant_progress_identity", payload.get("relevant_progress_identity")),
                    ("supervisor_incarnation_identity", payload.get("supervisor_incarnation_identity")),
                    ("cause_kind", payload.get("cause_kind")),
                )
                if any(value is None or value != prior.get(name) for name, value in identity_pairs):
                    raise ValueError("confirmation identity mismatch")
                if payload.get("second_evidence_digest") != prior.get("evidence_digest"):
                    raise ValueError("confirmation evidence identity mismatch")
                try:
                    first = datetime.fromisoformat(str(prior["first_observed_at"]).replace("Z", "+00:00"))
                    second = datetime.fromisoformat(str(payload["second_observed_at"]).replace("Z", "+00:00"))
                    if second.timestamp() - first.timestamp() < float(prior["scan_interval_s"]):
                        raise ValueError("confirmation second scan is too early")
                    if second.timestamp() > float(prior["expires_at"]):
                        raise ValueError("confirmation expired")
                except (KeyError, TypeError, ValueError) as exc:
                    if isinstance(exc, ValueError) and str(exc) in {"confirmation second scan is too early", "confirmation expired"}:
                        raise
                    raise ValueError("invalid confirmation timestamps") from exc
                return self._append_nbf_locked(fd, payload, records)
        return self._append_nbf(payload)

    def consume_confirmation(self, *, confirmation_id: str, second_observed_at: str, second_evidence_digest: str, victim_pid: int, victim_process_start_identity: str, relevant_progress_identity: str, supervisor_incarnation_identity: str, cause_kind: str, scan_interval_s: float | None = None, expires_at: float | None = None, confirmation_policy_identity: str | None = None, schema_version: int | None = None, disposition_id: str | None = None, actor: str = "supervisor") -> dict[str, Any]:
        """Consume a matching two-scan proof inside the ledger lock."""
        with self._locked() as (fd, records):
            prior = self._project_records(records)["confirmations"].get(confirmation_id)
            if not prior or prior.get("consumed") or prior.get("expired") or prior.get("replaced"):
                raise ValueError("confirmation missing or already consumed")
            identity_pairs = (("victim_pid", victim_pid), ("victim_process_start_identity", victim_process_start_identity), ("relevant_progress_identity", relevant_progress_identity), ("supervisor_incarnation_identity", supervisor_incarnation_identity), ("cause_kind", cause_kind), ("scan_interval_s", scan_interval_s), ("expires_at", expires_at), ("confirmation_policy_identity", confirmation_policy_identity), ("schema_version", schema_version))
            for name, value in identity_pairs:
                if value is None or value != prior.get(name):
                    raise ValueError(f"confirmation identity mismatch: {name}")
            if second_evidence_digest != prior.get("evidence_digest"):
                raise ValueError("confirmation evidence identity mismatch")
            try:
                first = datetime.fromisoformat(str(prior["first_observed_at"]).replace("Z", "+00:00"))
                second = datetime.fromisoformat(str(second_observed_at).replace("Z", "+00:00"))
                if second.timestamp() - first.timestamp() < float(prior["scan_interval_s"]):
                    raise ValueError("confirmation second scan is too early")
                if second.timestamp() > float(prior["expires_at"]):
                    expiry = {"schema_version": 1, "event_type": "supervision_confirmation_expired", "event_id": _stable_id("confirmation-expired", confirmation_id), "confirmation_id": confirmation_id, "prior_confirmation_event_id": prior.get("event_id"), "site_id": prior.get("site_id"), "replacement_reason": "expired", "second_observed_at": second_observed_at, "second_evidence_digest": second_evidence_digest, "victim_pid": victim_pid, "victim_process_start_identity": victim_process_start_identity, "relevant_progress_identity": relevant_progress_identity, "supervisor_incarnation_identity": supervisor_incarnation_identity, "cause_kind": cause_kind, "disposition_id": None, "recorded_at": _now(), "actor": actor}
                    self._append_nbf_locked(fd, expiry, records)
                    raise ValueError("confirmation expired")
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, ValueError) and str(exc) in {"confirmation second scan is too early", "confirmation expired"}:
                    raise
                raise ValueError("invalid confirmation timestamps") from exc
            payload = {"schema_version": 1, "event_type": "supervision_confirmation_consumed", "event_id": _stable_id("consumed", confirmation_id, second_observed_at, second_evidence_digest), "confirmation_id": confirmation_id, "prior_confirmation_event_id": prior.get("event_id"), "site_id": prior.get("site_id"), "replacement_reason": None, "second_observed_at": second_observed_at, "second_evidence_digest": second_evidence_digest, "victim_pid": victim_pid, "victim_process_start_identity": victim_process_start_identity, "relevant_progress_identity": relevant_progress_identity, "supervisor_incarnation_identity": supervisor_incarnation_identity, "cause_kind": cause_kind, "scan_interval_s": scan_interval_s, "expires_at": expires_at, "confirmation_policy_identity": confirmation_policy_identity, "disposition_id": disposition_id, "recorded_at": _now(), "actor": actor}
            return self._append_nbf_locked(fd, payload, records)

    def expire_confirmation(self, confirmation_id: str, *, observed_at: str | None = None, actor: str = "supervisor") -> dict[str, Any]:
        """Persist expiry of an unconsumed confirmation under the journal lock."""
        with self._locked() as (fd, records):
            prior = self._project_records(records)["confirmations"].get(confirmation_id)
            if not prior:
                raise ValueError("confirmation missing")
            if prior.get("consumed") or prior.get("expired") or prior.get("replaced"):
                raise ValueError("confirmation cannot be expired after consumption or replacement")
            payload = {"schema_version": 1, "event_type": "supervision_confirmation_expired", "event_id": _stable_id("confirmation-expired", confirmation_id), "confirmation_id": confirmation_id, "prior_confirmation_event_id": prior.get("event_id"), "site_id": prior.get("site_id"), "replacement_reason": "expired", "second_observed_at": observed_at or _now(), "second_evidence_digest": prior.get("evidence_digest"), "victim_pid": prior.get("victim_pid"), "victim_process_start_identity": prior.get("victim_process_start_identity"), "relevant_progress_identity": prior.get("relevant_progress_identity"), "supervisor_incarnation_identity": prior.get("supervisor_incarnation_identity"), "cause_kind": prior.get("cause_kind"), "disposition_id": None, "recorded_at": _now(), "actor": actor}
            return self._append_nbf_locked(fd, payload, records)

    def append_provider_observation(self, *, observation_id: str, provider_failure_key: str, selected_spec: str, phase: str, provider_failure_class: str, provider_epoch_identity: str, actor: str = "megaplan") -> dict[str, Any]:
        return self._append_nbf({"schema_version": 1, "event_type": "provider_observation", "event_id": observation_id, "observation_id": observation_id, "provider_failure_key": provider_failure_key, "selected_spec": selected_spec, "phase": phase, "provider_failure_class": provider_failure_class, "provider_epoch_identity": provider_epoch_identity, "recorded_at": _now(), "actor": actor})

    def append_probe_result(self, *, probe_lease_id: str, provider_failure_key: str, passed: bool, evidence_digest: str, parent_reservation_event_id: str | None = None, phase: str | None = None, route_identity: str | None = None, actor: str = "megaplan") -> dict[str, Any]:
        event_id = _stable_id("provider_probe_result", probe_lease_id, provider_failure_key, str(passed), evidence_digest)
        payload = {"schema_version": 1, "event_type": "provider_probe_result", "event_id": event_id, "probe_lease_id": probe_lease_id, "provider_failure_key": provider_failure_key, "passed": bool(passed), "evidence_digest": evidence_digest, "recorded_at": _now(), "actor": actor}
        if parent_reservation_event_id is not None:
            payload.update({"parent_reservation_event_id": parent_reservation_event_id, "phase": phase, "route_identity": route_identity})
        with self._locked() as (fd, records):
            lease = next((r.get("payload", {}) for r in records if r.get("payload", {}).get("event_type") == "provider_probe_started" and r.get("payload", {}).get("probe_lease_id") == probe_lease_id), None)
            if lease is None:
                raise ValueError("provider probe result requires a persisted lease")
            if float(lease.get("expires_at", 0)) <= datetime.now(timezone.utc).timestamp():
                raise ValueError("provider probe lease is expired")
            if lease.get("provider_failure_key") != provider_failure_key:
                raise ValueError("provider probe lease key mismatch")
            for name, value in (("parent_reservation_event_id", parent_reservation_event_id), ("phase", phase), ("route_identity", route_identity)):
                if lease.get(name) != value:
                    raise ValueError(f"provider probe lease context mismatch: {name}")
            if any(r.get("payload", {}).get("event_type") == "provider_probe_result" and r.get("payload", {}).get("probe_lease_id") == probe_lease_id for r in records):
                raise ValueError("provider probe lease has already been consumed")
            return self._append_nbf_locked(fd, payload, records)

    def consume_changed_precondition(self, event: Any, *, actor: str = "megaplan") -> dict[str, Any]:
        from arnold_pipelines.megaplan.incident.schema import ChangedPrecondition, _validate_producer_binding
        obj = event if isinstance(event, ChangedPrecondition) else ChangedPrecondition.from_dict(event)
        _validate_producer_binding(obj)
        with self._locked() as (fd, records):
            projected = self._project_records(records)
            persisted = projected["changed_preconditions"].get(obj.event_id)
            if persisted is None or any(persisted.get(k) != obj.to_dict().get(k) for k in obj.to_dict()):
                raise ValueError("changed precondition is not the persisted authoritative event")
            if persisted.get("consumed"):
                raise ValueError("changed precondition already consumed")
            return self._append_nbf_locked(fd, {"schema_version": 1, "event_type": "changed_precondition_consumed", "event_id": _stable_id("consume", obj.event_id), "changed_precondition_event_id": obj.event_id, "recorded_at": _now(), "actor": actor}, records)

    def create_probe_lease(self, *, provider_failure_key: str, expires_at: float, parent_reservation_event_id: str | None = None, phase: str | None = None, route_identity: str | None = None, actor: str = "megaplan") -> dict[str, Any]:
        with self._locked() as (fd, records):
            if any(r.get("payload", {}).get("event_type") == "provider_probe_started" and r.get("payload", {}).get("provider_failure_key") == provider_failure_key for r in records):
                raise ValueError("provider probe lease already exists")
            projection = self._project_records(records)
            lease_id = _stable_id("probe", provider_failure_key, str(projection["projection_version"]))
            payload = {"schema_version": 1, "event_type": "provider_probe_started", "event_id": lease_id, "probe_lease_id": lease_id, "provider_failure_key": provider_failure_key, "expires_at": expires_at, "recorded_at": _now(), "actor": actor}
            if any(value is not None for value in (parent_reservation_event_id, phase, route_identity)):
                payload.update({"parent_reservation_event_id": parent_reservation_event_id, "phase": phase, "route_identity": route_identity})
            return self._append_nbf_locked(fd, payload, records)

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Redact, validate, and append one incident event to the canonical ledger."""
        payload = validate_incident_event(event)
        kind = payload.get("type") or payload.get("event_kind") or "event"
        return self._journal.emit(
            f"incident.{kind}",
            payload=payload,
        )

    def append_maintenance_event(
        self,
        event: dict[str, Any] | Any,
    ) -> dict[str, Any]:
        """Strict-route one Maintenance event with atomic idempotency.

        *event* may be a :class:`MaintenanceEvent` or
        :class:`OperationalEvent` model, or its canonical dict form.  It is
        strict-decoded through the shared Maintenance codec (unknown/missing
        fields and identity mismatches fail before any write), then appended
        atomically keyed by the canonical lifecycle idempotency key plus
        digest:

        * the recorded key is the strict action key for operational lifecycle
          rows (so distinct request/source-change/installation/retrigger/
          progress/checkpoint/terminal/recurrence/escalation records coexist
          for ONE occurrence) with the legacy ``occurrence_id`` fallback for
          M2 detection / efficiency_analysis / audit_report rows;
        * an exact duplicate returns the PRIOR committed record (same seq);
        * a divergent duplicate raises :class:`MaintenanceEventConflict`
          without appending;
        * otherwise exactly one record is appended.

        Never touches runtime ``.megaplan/incident-ledger`` data: the caller
        supplies the root.
        """
        from arnold_pipelines.megaplan.maintenance.events import (
            MaintenanceEvent,
            OperationalEvent,
        )
        from arnold_pipelines.megaplan.maintenance.identity import (
            MaintenanceCodecError,
            canonical_digest,
            canonical_dumps,
            strict_loads,
        )

        if isinstance(event, (MaintenanceEvent, OperationalEvent)):
            model = event
        else:
            try:
                model = strict_loads(MaintenanceEvent, event)
            except MaintenanceCodecError:
                try:
                    model = strict_loads(OperationalEvent, event)
                except MaintenanceCodecError as exc:
                    raise ValueError(
                        f"maintenance event strict decode failed: {exc}"
                    ) from exc
        payload = json.loads(canonical_dumps(model))
        digest = canonical_digest(model)
        kind_name = getattr(model, "event_kind", None) or getattr(
            model, "action_kind", None
        )
        return self._journal.append_maintenance(
            kind=f"incident.{kind_name.value}",
            payload=payload,
            idempotency_key=lifecycle_idempotency_key(payload),
            digest=digest,
        )

    def lookup_maintenance_event(self, idempotency_key: str) -> dict[str, Any] | None:
        """Return the committed record for *idempotency_key*, or ``None``.

        *idempotency_key* is the canonical lifecycle idempotency key: the
        strict action key for operational lifecycle rows, or ``occurrence_id``
        for legacy M2 rows.
        """
        return self._journal.lookup_maintenance(idempotency_key)

    def append_authorized_lifecycle_event(
        self,
        *,
        occurrence_id: str,
        transition: str,
        owner: str,
        grant_id: str,
        custody_epoch: int,
        run_authority_check: Callable[[str, str], bool],
        custody_check: Callable[[str, int, str], bool],
        session_id: str = "",
    ) -> dict[str, Any]:
        """Append an acknowledged/resolved event after live authority rereads.

        The notification store intentionally has no lifecycle writer. This
        method is the canonical incident-owned writer: the current Run
        Authority and Custody sources validate the owner/grant/epoch before
        an append-only event is committed. A card or caller-supplied JSON
        authority blob cannot satisfy either check.
        """
        if transition not in {"acknowledged", "resolved"}:
            raise ValueError("incident lifecycle transition must be acknowledged or resolved")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty canonical identity")
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise ValueError("grant_id must be a non-empty current grant identity")
        if not isinstance(custody_epoch, int) or isinstance(custody_epoch, bool) or custody_epoch < 1:
            raise ValueError("custody_epoch must be a positive current epoch")
        if not callable(run_authority_check) or not run_authority_check(grant_id, owner):
            raise ValueError("Run Authority grant/owner is not current")
        if not callable(custody_check) or not custody_check(owner, custody_epoch, occurrence_id):
            raise ValueError("Custody owner/epoch is not current")
        occurrence_id = str(occurrence_id).strip()
        if not occurrence_id:
            raise ValueError("occurrence_id must be a non-empty canonical identity")
        event_key = hashlib.sha256(
            json.dumps(
                [occurrence_id, transition, owner, grant_id, custody_epoch],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        return self.append_event(
            {
                "schema_version": 1,
                "event_id": f"incident-lifecycle-{event_key}",
                "ts": now,
                "type": transition,
                "actor": owner,
                "scope": f"incident:{occurrence_id}",
                "outcome": "accepted",
                "summary": f"Incident {transition} through canonical Run Authority and Custody",
                "evidence": [
                    f"run-authority:{grant_id}",
                    f"custody:{owner}:{custody_epoch}",
                ],
                "parent_event_ids": [],
                "next_expected_event": None,
                "deadline_ts": None,
                "trigger_event_id": None,
                "incident_id": occurrence_id,
                "session_id": session_id or None,
                "run_authority_grant_id": grant_id,
                "custody_epoch": custody_epoch,
            }
        )


class RuntimeTransitionWriter:
    """Append-only writer for the five typed runtime transition events.

    Every emit is a pure ledger append routed through :class:`IncidentLedger`
    (validate -> redact -> flocked monotonic append). Emitting NEVER performs
    a dispatch side effect and never triggers a scan — mirror the
    side-effect-free watchdog bridge event pattern.

    Failures propagate and MUST block dispatch:

    * ``ValueError`` — policy rejection (non-retryable ``fallback_taken``,
      unknown failure class, missing required field, malformed digest).
    * ``OSError`` — journal write failure.

    A caller MUST treat either exception as "the transition was not durably
    recorded, so do not perform the dispatch side effect".
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        ledger: IncidentLedger | None = None,
    ) -> None:
        self._ledger = ledger if ledger is not None else IncidentLedger(root)

    # ── public emit methods ────────────────────────────────────────────

    def emit_manifest_selected(
        self,
        *,
        scope: str,
        candidate_to: str | dict[str, Any],
        candidate_from: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        chain_spec_sha256: str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.manifest_selected`` before a runtime selection."""
        return self._emit(
            EVENT_MANIFEST_SELECTED,
            scope=scope,
            failure_class=None,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_deviation_declared(
        self,
        *,
        scope: str,
        failure_class: str,
        error: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.deviation_declared`` for a declared deviation."""
        return self._emit(
            EVENT_DEVIATION_DECLARED,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_fallback_considered(
        self,
        *,
        scope: str,
        failure_class: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.fallback_considered`` before a fallback decision."""
        return self._emit(
            EVENT_FALLBACK_CONSIDERED,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_fallback_taken(
        self,
        *,
        scope: str,
        failure_class: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.fallback_taken`` — only for retryable classes.

        Raises
        ------
        ValueError
            When *failure_class* is not in :data:`RETRYABLE_FAILURE_CLASSES`.
            Non-retryable deviations MUST be recorded with
            :meth:`emit_fallback_rejected` instead.
        """
        return self._emit(
            EVENT_FALLBACK_TAKEN,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    def emit_fallback_rejected(
        self,
        *,
        scope: str,
        failure_class: str,
        chain_spec_sha256: str,
        candidate_from: str | dict[str, Any] | None = None,
        candidate_to: str | dict[str, Any] | None = None,
        error: str = "",
        attempt: int | str = "",
        evidence: list[Any] | None = None,
        actor: str = "runtime",
        session_id: str = "",
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Record ``runtime.fallback_rejected`` for a declined fallback."""
        return self._emit(
            EVENT_FALLBACK_REJECTED,
            scope=scope,
            failure_class=failure_class,
            chain_spec_sha256=chain_spec_sha256,
            attempt=attempt,
            error=error,
            evidence=evidence if evidence is not None else [],
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            actor=actor,
            session_id=session_id,
            summary=summary,
        )

    # ── shared emit + failure-class gate ───────────────────────────────

    def _emit(
        self,
        event_type: str,
        *,
        scope: str,
        failure_class: str | None,
        chain_spec_sha256: str,
        attempt: int | str,
        error: str,
        evidence: list[Any],
        candidate_from: str | dict[str, Any] | None,
        candidate_to: str | dict[str, Any] | None,
        actor: str,
        session_id: str,
        summary: str | None,
    ) -> dict[str, Any]:
        if event_type not in _EVENT_ID_PREFIXES:
            raise ValueError(f"unknown runtime transition event type: {event_type!r}")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be a non-empty canonical identity")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor must be a non-empty canonical identity")
        if not isinstance(session_id, str):
            raise ValueError("session_id must be a string")
        if not isinstance(error, str):
            raise ValueError("error must be a normalized string")
        if not isinstance(attempt, (int, str)) or isinstance(attempt, bool):
            raise ValueError("attempt must be an int or a string")
        if not isinstance(evidence, list):
            raise ValueError("evidence must be a list")
        for label, value in (
            ("candidate_from", candidate_from),
            ("candidate_to", candidate_to),
        ):
            if value is not None and not isinstance(value, (str, dict)):
                raise ValueError(f"{label} must be a string, a dict, or None")
            if isinstance(value, dict):
                try:
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"{label} must be JSON serializable"
                    ) from exc
        chain_spec_sha256 = _normalize_chain_digest(chain_spec_sha256)

        # ── failure-class policy ───────────────────────────────────────
        if failure_class is not None:
            if not isinstance(failure_class, str) or not failure_class.strip():
                raise ValueError("failure_class must be a non-empty string")
            failure_class = failure_class.strip()
            if failure_class not in KNOWN_FAILURE_CLASSES:
                raise ValueError(
                    f"failure_class must be one of {sorted(KNOWN_FAILURE_CLASSES)} "
                    f"(got {failure_class!r})"
                )
        if event_type in {
            EVENT_DEVIATION_DECLARED,
            EVENT_FALLBACK_CONSIDERED,
            EVENT_FALLBACK_TAKEN,
            EVENT_FALLBACK_REJECTED,
        }:
            if not failure_class:
                raise ValueError(f"{event_type} requires a failure_class")
            if not chain_spec_sha256:
                raise ValueError(f"{event_type} requires chain_spec_sha256")
        if event_type == EVENT_FALLBACK_TAKEN and not is_retryable_failure_class(
            failure_class
        ):
            raise ValueError(
                f"runtime.fallback_taken requires a retryable failure class "
                f"(one of {sorted(RETRYABLE_FAILURE_CLASSES)}); non-retryable "
                f"deviations must be recorded with emit_fallback_rejected "
                f"(got {failure_class!r})"
            )

        # ── event assembly ─────────────────────────────────────────────
        base_summary = _DEFAULT_SUMMARIES[event_type]
        if failure_class:
            base_summary = f"{base_summary} (failure_class={failure_class})"
        now = datetime.now(timezone.utc).isoformat()
        event: dict[str, Any] = {
            "schema_version": 1,
            "event_id": f"{_EVENT_ID_PREFIXES[event_type]}-{uuid.uuid4().hex[:12]}",
            "ts": now,
            "type": event_type,
            "actor": actor,
            "scope": scope,
            "outcome": _DEFAULT_OUTCOMES[event_type],
            "summary": summary if summary is not None else base_summary,
            "evidence": evidence,
            "parent_event_ids": [],
            "next_expected_event": None,
            "deadline_ts": None,
            "trigger_event_id": None,
            "candidate_from": candidate_from,
            "candidate_to": candidate_to,
            "error": error,
            "attempt": attempt,
            "chain_spec_sha256": chain_spec_sha256,
            "failure_class": failure_class,
            "session_id": session_id or None,
        }
        return self._ledger.append_event(event)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for bash wrappers: append one typed runtime transition.

    A non-zero exit (or a raised exception) means the transition was NOT
    durably recorded — callers MUST treat it as "do not dispatch". On
    success the full journal envelope (with ``seq`` and ``kind``) is printed
    as one JSON line to stdout.

    Exit codes: 0 = appended; 1 = policy rejection / ledger write failure
    (nothing written); 2 = usage error (argparse).
    """
    short_names = {
        event_type.removeprefix("runtime."): event_type
        for event_type in RUNTIME_TRANSITION_EVENT_TYPES
    }
    choices = list(short_names) + list(RUNTIME_TRANSITION_EVENT_TYPES)

    parser = argparse.ArgumentParser(
        prog="megaplan runtime-transition",
        description=(
            "Append one typed runtime transition event to the incident ledger "
            "BEFORE any dispatch side effect. Non-zero exit = do not dispatch."
        ),
    )
    parser.add_argument(
        "event",
        choices=choices,
        help=(
            "manifest_selected | deviation_declared | fallback_considered | "
            "fallback_taken | fallback_rejected (dotted form also accepted)"
        ),
    )
    parser.add_argument(
        "--root",
        default=None,
        help="workspace root for the incident ledger (default: cwd)",
    )
    parser.add_argument(
        "--scope",
        required=True,
        help="session-scoped identity, e.g. chain:<session-id>",
    )
    parser.add_argument("--actor", default="runtime", help="attribution identity")
    parser.add_argument(
        "--session-id", default="", help="optional session id for the payload"
    )
    parser.add_argument(
        "--candidate-from",
        default=None,
        help="previous candidate: plain string or JSON value",
    )
    parser.add_argument(
        "--candidate-to",
        default=None,
        help="selected/fallback candidate: plain string or JSON value",
    )
    parser.add_argument("--error", default="", help="normalized error string")
    parser.add_argument(
        "--attempt", default="", help="attempt number or attempt id"
    )
    parser.add_argument(
        "--chain-spec-sha256",
        default="",
        help="contract digest 'sha256:<64 hex>' (required for deviation/fallback events)",
    )
    parser.add_argument(
        "--failure-class",
        default=None,
        help="one of availability, infrastructure, auth, config, semantic, schema, test, evidence, execute",
    )
    parser.add_argument(
        "--evidence",
        default="[]",
        help="JSON array of evidence references (default: '[]')",
    )
    parser.add_argument("--summary", default=None, help="override the summary text")

    args = parser.parse_args(argv)
    event_type = short_names.get(args.event, args.event)

    try:
        evidence = json.loads(args.evidence)
        if not isinstance(evidence, list):
            raise ValueError("--evidence must decode to a JSON array")
    except json.JSONDecodeError as exc:
        print(f"invalid --evidence JSON: {exc}", file=sys.stderr)
        return 1

    def _candidate(value: str | None) -> str | dict[str, Any] | None:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    writer = RuntimeTransitionWriter(Path(args.root) if args.root else None)
    try:
        if event_type == EVENT_MANIFEST_SELECTED:
            appended = writer.emit_manifest_selected(
                scope=args.scope,
                candidate_to=_candidate(args.candidate_to),
                candidate_from=_candidate(args.candidate_from),
                error=args.error,
                attempt=args.attempt,
                chain_spec_sha256=args.chain_spec_sha256,
                evidence=evidence,
                actor=args.actor,
                session_id=args.session_id,
                summary=args.summary,
            )
        else:
            emit = {
                EVENT_DEVIATION_DECLARED: writer.emit_deviation_declared,
                EVENT_FALLBACK_CONSIDERED: writer.emit_fallback_considered,
                EVENT_FALLBACK_TAKEN: writer.emit_fallback_taken,
                EVENT_FALLBACK_REJECTED: writer.emit_fallback_rejected,
            }[event_type]
            appended = emit(
                scope=args.scope,
                failure_class=args.failure_class,
                chain_spec_sha256=args.chain_spec_sha256,
                candidate_from=_candidate(args.candidate_from),
                candidate_to=_candidate(args.candidate_to),
                error=args.error,
                attempt=args.attempt,
                evidence=evidence,
                actor=args.actor,
                session_id=args.session_id,
                summary=args.summary,
            )
    except (ValueError, OSError) as exc:
        print(f"runtime transition not recorded ({event_type}): {exc}", file=sys.stderr)
        return 1

    print(json.dumps(appended, sort_keys=True, separators=(",", ":")))
    return 0


__all__ = [
    "IncidentLedger",
    "MaintenanceEventConflict",
    "RuntimeTransitionWriter",
    "EVENT_MANIFEST_SELECTED",
    "EVENT_DEVIATION_DECLARED",
    "EVENT_FALLBACK_CONSIDERED",
    "EVENT_FALLBACK_TAKEN",
    "EVENT_FALLBACK_REJECTED",
    "RUNTIME_TRANSITION_EVENT_TYPES",
    "RETRYABLE_FAILURE_CLASSES",
    "NON_RETRYABLE_FAILURE_CLASSES",
    "KNOWN_FAILURE_CLASSES",
    "is_retryable_failure_class",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
