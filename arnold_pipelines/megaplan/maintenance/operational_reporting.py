"""Exact UTC half-open operational reports with append-only corrections (M4 T3).

Plan Step 3: build deterministic, exact-window operational reports from the
last closed Maintenance watermark and persist them through the existing
Maintenance seams — :class:`MaintenanceLedger` (strict append, dead-letter,
at-most-once replay) and :class:`ProjectionEngine` (digest-linked late
corrections, absent-only replay, divergent-identity rejection, crash-safe
idempotency).  This module is reference/report-only (SD1/SD3): it never
constructs an owner authority record, never enqueues a repair, never claims
custody, and never authorizes action.  Provisional numeric values (allowed
lateness, window size) seed shadow reports but cannot authorize repair.

Locked decisions (frozen, do not re-litigate):

* **Exact half-open UTC windows.**  A report window is
  ``[window.start, window.end)`` in UTC event time; ``window.start`` is the
  last closed Maintenance watermark (inclusive) and ``window.end`` is
  exclusive.  ``window.start`` must equal the stored watermark exactly.
* **Immutable sorted inputs.**  Input IDs and owner references are stored
  deterministically sorted (and deduplicated); the same inputs reproduce the
  same canonical content hash, and a different input set changes the hash.
* **Explicit missing metrics.**  A missing numerator or denominator is
  preserved as explicit ``None``; ``coverage`` returns ``None`` (never ``0``)
  when the numerator or denominator is missing or the denominator is zero —
  absence is never promoted to a green signal.  Unknown and censored counts
  are retained, never dropped.
* **Canonical cadence.**  ``next_three_hour`` is the canonical operational
  cadence (SD1); ``six_hour`` is a read-only legacy alias.  The legacy product
  label ``six_hour_operational`` is preserved as ``report_type`` for VP
  compatibility while ``cadence`` records the canonical value.
* **Digest-linked late corrections.**  A late report event never rewrites a
  prior projection result; the engine appends a :class:`CorrectionRecord`
  that links the new sequence to the corrected sequence and preserves the
  corrected result's ``output_digest``.
* **Absent-only replay / divergent-identity rejection / crash-safe
  idempotency.**  Replay appends only absent outputs; an exact duplicate is
  ``already_present`` (nothing new), and a divergent reuse of the same
  occurrence identity is rejected (recorded as ``conflict``, never written).
  Re-opening the ledger after a crash replays dead letters at most once.

All models are frozen, forbid unknown fields, and round-trip through the
single canonical codec (``canonical_dumps`` / ``strict_loads``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.events import (
    ClassifierInfo,
    EfficiencyAnalysis,
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
    RootCauseCluster,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    EventWindow,
    Extensions,
    Lateness,
    OwnerRef,
    UtcTime,
    Watermark,
    canonical_digest,
    canonical_dumps,
    canonical_json,
    classify_lateness,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import (
    MaintenanceEventConflict,
    MaintenanceLedger,
)
from arnold_pipelines.megaplan.maintenance.operational_policy import (
    CohortIdentity,
)
from arnold_pipelines.megaplan.maintenance.projections import (
    ProjectionEngine,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical operational cadence (SD1, locked): ``next_three_hour`` is the
#: single canonical auditor cadence; ``six_hour`` is a legacy VP label only.
CANONICAL_CADENCE: str = "next_three_hour"

#: Read-only legacy alias accepted on input and normalized to the canonical
#: cadence; it can never mint a second cadence.
LEGACY_CADENCE_ALIAS: str = "six_hour"

#: Legacy product label preserved on every report for VP compatibility.
LEGACY_REPORT_TYPE: str = "six_hour_operational"

#: Provisional fixed-rate UTC window size (report-only until approved, SD3).
REPORT_WINDOW_SECONDS: int = 3 * 3600

#: Default provisional allowed lateness (report-only until approved, SD3).
DEFAULT_ALLOWED_LATENESS_SECONDS: int = 300

#: Canonical event-id prefix for persisted operational reports.
REPORT_EVENT_ID_PREFIX: str = "operational-report"


# ---------------------------------------------------------------------------
# Closed report contracts
# ---------------------------------------------------------------------------


class MetricFacts(BaseModel):
    """Closed metric facts for one exact-window operational report.

    A missing numerator or denominator stays explicit ``None`` — it is never
    coerced to ``0`` and never becomes a green signal.  ``unknown_count`` and
    ``censored_count`` are retained so suppressed/unknown observations keep
    their censored metrics (locked suppressor rule).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Accepted/covered observations (the metric numerator).  ``None`` is an
    #: explicit missing numerator — never promoted to zero.
    numerator: int | None = Field(default=None, ge=0)
    #: Total eligible observations (the metric denominator).  ``None`` is an
    #: explicit missing denominator — never promoted to zero.
    denominator: int | None = Field(default=None, ge=0)
    #: Observations whose outcome was explicitly UNKNOWN.
    unknown_count: int = Field(default=0, ge=0)
    #: Observations censored by a suppressor or gate (retained, never dropped).
    censored_count: int = Field(default=0, ge=0)

    @property
    def missing_denominator(self) -> bool:
        """True when the denominator is missing (``None``), never inferred."""
        return self.denominator is None

    @property
    def coverage(self) -> float | None:
        """Derived coverage (numerator / denominator), or ``None`` when unknown.

        ``None`` covers every unknown case: a missing numerator, a missing
        denominator, or a zero denominator (never a division by zero).
        """
        if self.numerator is None or self.denominator is None:
            return None
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @model_validator(mode="after")
    def _check_bounds(self) -> MetricFacts:
        if (
            self.numerator is not None
            and self.denominator is not None
            and self.numerator > self.denominator
        ):
            raise ValueError(
                f"metric numerator {self.numerator} exceeds "
                f"denominator {self.denominator}"
            )
        return self


class OperationalReport(BaseModel):
    """Closed exact-window operational report row (reference-only).

    Carries the exact half-open UTC window, the last closed watermark,
    allowed lateness, immutable sorted input IDs and owner references,
    policy/classifier versions, cohort and metric facts, and the canonical
    content hash.  ``report_type`` preserves the legacy
    ``six_hour_operational`` label while ``cadence`` records the canonical
    ``next_three_hour`` cadence (SD1).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    report_id: StrictStr
    report_type: StrictStr = LEGACY_REPORT_TYPE
    cadence: StrictStr = CANONICAL_CADENCE
    #: Exact half-open UTC event-time window ``[start, end)``.
    window: EventWindow
    #: The last closed Maintenance watermark; must equal ``window.start``.
    watermark: Watermark
    #: Provisional allowed lateness in seconds (report-only, SD3).
    allowed_lateness_seconds: int = Field(
        default=DEFAULT_ALLOWED_LATENESS_SECONDS, ge=0
    )
    #: Immutable sorted input IDs (deterministic order, deduplicated).
    input_ids: tuple[StrictStr, ...] = ()
    #: Immutable sorted owner references (deterministic order, deduplicated).
    owner_refs: tuple[OwnerRef, ...] = ()
    policy_version: StrictStr
    classifier_version: StrictStr
    cohort: CohortIdentity | None = None
    metrics: MetricFacts
    #: Canonical sha256 content hash (validated at strict decode).
    content_hash: StrictStr

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("report_id", "policy_version", "classifier_version")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("report/policy/classifier identities must be non-empty")
        return value

    @field_validator("content_hash")
    @classmethod
    def _validate_hash(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(
                "content_hash must be a 64-character lowercase sha256 hex digest"
            )
        return value

    @field_validator("input_ids")
    @classmethod
    def _validate_input_ids(cls, value: Sequence[str]) -> tuple[str, ...]:
        ordered = tuple(value)
        if ordered != tuple(sorted(ordered)):
            raise ValueError(
                "operational report input_ids must be sorted (immutable "
                "deterministic order)"
            )
        if len(set(ordered)) != len(ordered):
            raise ValueError(
                "operational report input_ids must be deduplicated (immutable "
                "deterministic order)"
            )
        for item in ordered:
            if not item:
                raise ValueError("operational report input_ids must be non-empty")
        return ordered

    @field_validator("owner_refs")
    @classmethod
    def _validate_owner_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        ordered = _sort_owner_refs(value)
        if tuple(value) != ordered:
            raise ValueError(
                "operational report owner_refs must be sorted and deduplicated "
                "(immutable deterministic order)"
            )
        return ordered

    @model_validator(mode="after")
    def _enforce_report_invariants(self) -> OperationalReport:
        # 1. Exact boundary: the report window opens at the last closed
        #    watermark (inclusive); only the end is exclusive.
        if self.window.start.root != self.watermark.root:
            raise ValueError(
                "operational report window.start must equal the stored "
                "watermark (the last closed Maintenance watermark); "
                f"window.start={self.window.start.root.isoformat()} != "
                f"watermark={self.watermark.root.isoformat()}"
            )
        # 2. The canonical content hash must match the content exactly; a
        #    tampered hash is rejected at strict decode (fail closed).
        expected = _content_digest(self)
        if self.content_hash != expected:
            raise ValueError(
                "operational report content_hash does not match the canonical "
                f"content digest (expected {expected}, got {self.content_hash})"
            )
        return self


# ---------------------------------------------------------------------------
# Canonical content hash
# ---------------------------------------------------------------------------

#: Fields excluded from the content digest: the hash itself and the envelope
#: schema version (the digest is over the report's materialized content).
_CONTENT_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {"schema_version", "content_hash"}
)


def _content_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Strip hash/bookkeeping fields from a JSON-safe report payload."""
    return {
        key: value
        for key, value in dict(data).items()
        if key not in _CONTENT_EXCLUDED_FIELDS
    }


def report_content_dict(report: OperationalReport) -> dict[str, Any]:
    """Materialize the report content (excluding hash/bookkeeping fields)."""
    return _content_payload(report.model_dump(mode="json", exclude_none=False))


def content_digest(report: OperationalReport) -> str:
    """Return the canonical sha256 content digest of *report*.

    Identical inputs reproduce the identical digest; any change to the
    window, watermark, lateness, inputs, versions, cohort, or metrics changes
    it.  The digest excludes only the hash field itself and the schema
    version.
    """
    return hashlib.sha256(
        canonical_json(report_content_dict(report)).encode("utf-8")
    ).hexdigest()


def _content_digest(report: OperationalReport) -> str:
    return content_digest(report)


def _sort_owner_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic sorted, deduplicated (owner, locator, digest, cursor) order."""
    seen: set[tuple[Any, ...]] = set()
    ordered: list[OwnerRef] = []
    for ref in refs:
        key = (ref.owner, ref.locator, ref.digest, ref.cursor)
        if key not in seen:
            seen.add(key)
            ordered.append(ref)
    return tuple(
        sorted(
            ordered,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _sort_input_ids(ids: Sequence[str]) -> tuple[str, ...]:
    """Deterministic sorted, deduplicated input-ID order."""
    return tuple(sorted({str(item) for item in ids if str(item)}))


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_operational_report(
    *,
    report_id: str,
    watermark: Watermark | datetime | str,
    input_ids: Sequence[str] = (),
    owner_refs: Sequence[OwnerRef] = (),
    policy_version: str,
    classifier_version: str,
    cohort: CohortIdentity | None = None,
    metrics: MetricFacts | None = None,
    allowed_lateness_seconds: int = DEFAULT_ALLOWED_LATENESS_SECONDS,
    window_end: Watermark | datetime | str | None = None,
    report_type: str = LEGACY_REPORT_TYPE,
    cadence: str = CANONICAL_CADENCE,
) -> OperationalReport:
    """Build an exact-window operational report from the last closed watermark.

    The window is ``[watermark, window_end)`` with ``window_end`` defaulting
    to the provisional fixed-rate three-hour horizon
    (:data:`REPORT_WINDOW_SECONDS`) — exact half-open UTC event time.  Input
    IDs and owner references are sorted and deduplicated before being stored
    (immutable deterministic order), and the canonical content hash is
    computed over the materialized content.

    ``cadence`` accepts the canonical ``next_three_hour`` or the read-only
    legacy alias ``six_hour`` (normalized); any other value is rejected so a
    caller can never mint a second cadence.
    """
    mark = _coerce_watermark(watermark, what="watermark")
    end = (
        _coerce_watermark(window_end, what="window_end")
        if window_end is not None
        else UtcTime(mark.root + timedelta(seconds=REPORT_WINDOW_SECONDS))
    )
    window = EventWindow(start=UtcTime(mark.root), end=UtcTime(end.root))
    normalized_cadence = _normalize_cadence(cadence)
    # Construct with a placeholder hash (model_construct skips validation so
    # the content digest can be computed from the exact canonical serialization
    # pydantic produces), then strict-decode to enforce every invariant —
    # including the recomputed hash — at build time.
    provisional = OperationalReport.model_construct(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        report_id=report_id,
        report_type=report_type,
        cadence=normalized_cadence,
        window=window,
        watermark=Watermark(mark.root),
        allowed_lateness_seconds=allowed_lateness_seconds,
        input_ids=_sort_input_ids(input_ids),
        owner_refs=_sort_owner_refs(owner_refs),
        policy_version=policy_version,
        classifier_version=classifier_version,
        cohort=cohort,
        metrics=metrics if metrics is not None else MetricFacts(),
        content_hash="0" * 64,
    )
    digest = content_digest(provisional)
    return strict_loads(
        OperationalReport,
        provisional.model_copy(update={"content_hash": digest}).model_dump(
            mode="json", exclude_none=False
        ),
    )


def _coerce_watermark(value: Watermark | datetime | str, *, what: str) -> UtcTime:
    if isinstance(value, Watermark):
        return UtcTime(value.root)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(f"{what} must carry an explicit UTC offset")
        return UtcTime(value.astimezone(timezone.utc))
    if isinstance(value, str):
        return UtcTime(value)
    raise ValueError(f"{what} must be a Watermark, aware datetime, or ISO-8601 string")


def _normalize_cadence(cadence: str) -> str:
    if cadence == LEGACY_CADENCE_ALIAS:
        return CANONICAL_CADENCE
    if cadence != CANONICAL_CADENCE:
        raise ValueError(
            f"unknown operational cadence {cadence!r}; the only canonical "
            f"cadence is {CANONICAL_CADENCE!r} (legacy alias "
            f"{LEGACY_CADENCE_ALIAS!r} is normalized to it)"
        )
    return CANONICAL_CADENCE


# ---------------------------------------------------------------------------
# Report → strict event (reference-only)
# ---------------------------------------------------------------------------


def operational_report_to_event(
    report: OperationalReport,
    *,
    observed_at: UtcTime | datetime | None = None,
    environment: str | None = None,
    run: str | None = None,
    chain: str | None = None,
    plan: str | None = None,
    stage: str | None = None,
    model: str | None = None,
    profile: str | None = None,
    attempt: str | None = None,
    event_id: str | None = None,
) -> MaintenanceEvent:
    """Map one report to a strict ``efficiency_analysis`` MaintenanceEvent.

    The event carries the exact window and stored watermark on the envelope,
    the coverage/denominator facts in the typed payload (missing values stay
    explicit ``None``), and the full immutable report facts — sorted input
    IDs, owner references, versions, cohort, allowed lateness, metric facts,
    report type, and canonical cadence — in the envelope ``extensions`` map
    (the only place unknown keys are allowed).

    ``observed_at`` defaults to the exact window close (``window.end``), so
    the SAME report always reproduces the SAME event bytes — deterministic
    replay and crash-safe idempotency without caller-supplied clocks.  The
    default observation instant is strictly after the stored watermark
    (``window.start``), so the report is on-time.  A caller may override it,
    e.g. to emit late evidence (which appends a digest-linked correction
    instead of rewriting the prior projection).

    ``occurrence_id`` is the report id (the sole idempotency scope), so the
    same report appends at most once and a divergent reuse of the id is
    rejected by the ledger/engine.  This builder performs no I/O, no
    dispatch, and no mutation; it is reference-only.
    """
    observed = _coerce_observed_at(observed_at, default=report.window.end)
    event_time = UtcTime(observed)
    payload = EfficiencyAnalysis(
        product=CANONICAL_CADENCE,
        coverage_denominator=report.metrics.denominator,
        covered_count=report.metrics.numerator,
        censored_duration_seconds=None,
        bucket_counts={},
    )
    extensions = Extensions(
        root={
            "report_id": report.report_id,
            "report_type": report.report_type,
            "cadence": report.cadence,
            "allowed_lateness_seconds": report.allowed_lateness_seconds,
            "input_ids": list(report.input_ids),
            "owner_refs": [
                ref.model_dump(mode="json", exclude_none=False)
                for ref in report.owner_refs
            ],
            "policy_version": report.policy_version,
            "classifier_version": report.classifier_version,
            "cohort": (
                report.cohort.model_dump(mode="json", exclude_none=False)
                if report.cohort is not None
                else None
            ),
            "metrics": report.metrics.model_dump(mode="json", exclude_none=False),
            "content_hash": report.content_hash,
        }
    )
    return MaintenanceEvent.build(
        event_id=event_id or f"{REPORT_EVENT_ID_PREFIX}:{report.report_id}",
        occurrence_id=report.report_id,
        observed_at=observed,
        event_time=event_time,
        window=report.window,
        watermark=report.watermark,
        classifier=ClassifierInfo(classifier_version=report.classifier_version),
        cluster=RootCauseCluster(signature=report.report_type),
        budget=OccurrenceBudget(max_attempts=1),
        payload=payload,
        environment=environment,
        run=run,
        chain=chain,
        plan=plan,
        stage=stage,
        model=model,
        profile=profile,
        attempt=attempt,
        resolution_proof=report.owner_refs,
        extensions=extensions,
    )


def _coerce_observed_at(
    observed_at: UtcTime | datetime | None,
    *,
    default: UtcTime | datetime,
) -> datetime:
    if observed_at is None:
        observed = default
    else:
        observed = observed_at
    if isinstance(observed, UtcTime):
        return observed.root
    if isinstance(observed, datetime):
        if observed.tzinfo is None:
            raise ValueError("observed_at must carry an explicit UTC offset")
        return observed.astimezone(timezone.utc)
    raise ValueError("observed_at must be a UtcTime or aware datetime")


# ---------------------------------------------------------------------------
# Persistence through the existing Maintenance seams
# ---------------------------------------------------------------------------


def last_closed_watermark(
    ledger: MaintenanceLedger,
    *,
    now: datetime | None = None,
) -> Watermark | None:
    """Return the last closed Maintenance watermark from *ledger*, or ``None``.

    The watermark is the maximum validated event watermark over the strict
    Maintenance events already committed to the ledger (deterministic scan of
    the existing append-only stream).  An empty ledger yields ``None`` —
    never a guessed epoch.
    """
    mark: datetime | None = None
    for record in _read_ledger_records(ledger):
        model = _strict_decode_ledger_record(record)
        if model is None:
            continue
        if isinstance(model, MaintenanceEvent):
            if mark is None or model.watermark.root > mark:
                mark = model.watermark.root
    return Watermark(mark) if mark is not None else None


def read_committed_report_events(
    ledger: MaintenanceLedger,
) -> tuple[dict[str, Any], ...]:
    """Return the canonical dicts of committed ``efficiency_analysis`` events.

    Read-only scan of the existing ledger stream; used to rebuild projections
    deterministically (absent-only replay) without inventing any new state.
    """
    events: list[dict[str, Any]] = []
    for record in _read_ledger_records(ledger):
        model = _strict_decode_ledger_record(record)
        if model is None:
            continue
        if (
            isinstance(model, MaintenanceEvent)
            and model.event_kind is EventKind.EFFICIENCY_ANALYSIS
        ):
            events.append(json.loads(canonical_dumps(model)))
    return tuple(events)


def _read_ledger_records(ledger: MaintenanceLedger) -> list[dict[str, Any]]:
    path = ledger.events_path
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _strict_decode_ledger_record(
    record: Mapping[str, Any],
) -> MaintenanceEvent | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    try:
        return strict_loads(MaintenanceEvent, payload)
    except Exception:
        return None


def append_operational_report(
    ledger: MaintenanceLedger,
    report: OperationalReport,
    *,
    engine: ProjectionEngine | None = None,
    observed_at: UtcTime | datetime | None = None,
    environment: str | None = None,
    run: str | None = None,
    chain: str | None = None,
    plan: str | None = None,
    stage: str | None = None,
    model: str | None = None,
    profile: str | None = None,
    attempt: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    """Persist one report through the strict ledger, then the projection engine.

    Uses :class:`MaintenanceLedger` (strict append with dead-letter and
    at-most-once replay) and :class:`ProjectionEngine` (digest-linked late
    corrections, absent-only replay, divergent-identity rejection, crash-safe
    idempotency).  An exact duplicate returns the prior committed event
    (``append_status == "already_present"``); a divergent reuse of the
    occurrence identity raises :class:`MaintenanceEventConflict` /
    :class:`ProjectionConflictError` without writing anything.
    """
    event = operational_report_to_event(
        report,
        observed_at=observed_at,
        environment=environment,
        run=run,
        chain=chain,
        plan=plan,
        stage=stage,
        model=model,
        profile=profile,
        attempt=attempt,
        event_id=event_id,
    )
    digest = canonical_digest(event)
    try:
        committed = ledger.append(event)
    except MaintenanceEventConflict:
        # Divergent identity: rejection, nothing written.
        return {
            "report_id": report.report_id,
            "event": json.loads(canonical_dumps(event)),
            "event_digest": digest,
            "append_status": "conflict",
            "projection": None,
        }
    disposition = "appended"
    projection = None
    if engine is not None:
        try:
            result = engine.apply(event)
            projection = {
                "disposition": result.disposition.value,
                "efficiency_sequence": result.efficiency.sequence,
                "efficiency_output_digest": result.efficiency.output_digest,
                "efficiency_watermark": result.efficiency.watermark,
                "efficiency_window_start": result.efficiency.window_start,
                "efficiency_window_end": result.efficiency.window_end,
                "corrections": [
                    correction.model_dump(mode="json", exclude_none=False)
                    for correction in result.efficiency.corrections
                ],
            }
            if result.disposition.value == "deduped":
                disposition = "already_present"
        except Exception:
            # Projection conflict (divergent identity) never rewrites history.
            raise
    return {
        "report_id": report.report_id,
        "event": json.loads(canonical_dumps(event)),
        "event_digest": digest,
        "append_status": disposition,
        "committed": committed,
        "projection": projection,
    }


def replay_absent_reports(
    ledger: MaintenanceLedger,
    reports: Sequence[OperationalReport],
    *,
    engine: ProjectionEngine | None = None,
    observed_at: UtcTime | datetime | None = None,
    environment: str | None = None,
    run: str | None = None,
    chain: str | None = None,
    plan: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """Append only *absent* reports; exact duplicates and conflicts are recorded.

    Mirrors the ledger's dead-letter replay dispositions: each report maps to
    ``appended`` (first commit), ``already_present`` (identical event already
    committed — nothing new), or ``conflict`` (a divergent event already
    committed for the same occurrence identity — rejected, history untouched).
    Replaying the same report set twice therefore appends each report at most
    once (crash-safe idempotency) and never rewrites history.
    """
    outcomes: list[dict[str, Any]] = []
    appended_count = 0
    already_present_count = 0
    conflict_count = 0
    for report in reports:
        event = operational_report_to_event(
            report,
            observed_at=observed_at,
            environment=environment,
            run=run,
            chain=chain,
            plan=plan,
            stage=stage,
        )
        digest = canonical_digest(event)
        existing = _existing_event_for_occurrence(ledger, report.report_id)
        if existing is not None:
            if existing == digest:
                outcomes.append(
                    {
                        "report_id": report.report_id,
                        "event_digest": digest,
                        "outcome": "already_present",
                    }
                )
                already_present_count += 1
                continue
            outcomes.append(
                {
                    "report_id": report.report_id,
                    "event_digest": digest,
                    "outcome": "conflict",
                }
            )
            conflict_count += 1
            continue
        ledger.append(event)
        if engine is not None:
            engine.apply(event)
        outcomes.append(
            {
                "report_id": report.report_id,
                "event_digest": digest,
                "outcome": "appended",
            }
        )
        appended_count += 1
    return {
        "outcomes": outcomes,
        "appended_count": appended_count,
        "already_present_count": already_present_count,
        "conflict_count": conflict_count,
    }


def _existing_event_for_occurrence(
    ledger: MaintenanceLedger, occurrence_id: str
) -> str | None:
    """Return the canonical digest of the committed event for *occurrence_id*.

    ``None`` when no event for the occurrence is committed yet.  A divergent
    committed event for the same occurrence is detected by its (different)
    digest — the caller rejects it without writing.
    """
    for record in _read_ledger_records(ledger):
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("occurrence_id") != occurrence_id:
            continue
        try:
            model = strict_loads(MaintenanceEvent, payload)
        except Exception:
            continue
        return canonical_digest(model)
    return None


def replay_committed_reports(
    ledger: MaintenanceLedger,
    engine: ProjectionEngine | None = None,
) -> ProjectionEngine:
    """Deterministically rebuild the projection state from committed reports.

    Absent-only replay: identical committed events deduplicate, and the
    rebuild reproduces the same sequences and digests for the same event
    order (crash-safe idempotency).  Returns the engine so callers can read
    the efficiency projection.
    """
    target = engine if engine is not None else ProjectionEngine()
    for event_dict in read_committed_report_events(ledger):
        target.apply(event_dict)
    return target


__all__ = [
    "CANONICAL_CADENCE",
    "DEFAULT_ALLOWED_LATENESS_SECONDS",
    "LEGACY_CADENCE_ALIAS",
    "LEGACY_REPORT_TYPE",
    "MetricFacts",
    "OperationalReport",
    "REPORT_EVENT_ID_PREFIX",
    "REPORT_WINDOW_SECONDS",
    "append_operational_report",
    "build_operational_report",
    "content_digest",
    "last_closed_watermark",
    "operational_report_to_event",
    "read_committed_report_events",
    "replay_absent_reports",
    "replay_committed_reports",
    "report_content_dict",
]
