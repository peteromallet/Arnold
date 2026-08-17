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
        self._ledger_dir = self._root / _INCIDENT_LEDGER_DIR
        self._journal = _IncidentEventJournal(self._ledger_dir)

    @property
    def ledger_dir(self) -> Path:
        return self._ledger_dir

    @property
    def events_path(self) -> Path:
        return self._ledger_dir / _EVENTS_FILE

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
