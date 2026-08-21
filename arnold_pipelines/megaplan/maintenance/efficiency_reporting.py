"""T6.1 canonical daily report builder and fenced ledger emission.

Adapted from the M5 ``maintenance/efficiency_reporting.py`` pack (Plan Steps
20-22) onto the runtime consolidation contract (Batch 6 / T6.1): reports,
clusters, proposals, and corrections persist ONLY as idempotent observation
events through ONE canonical writer.

The single canonical writer chain (named by G0 / T0.2) is:

    ``MaintenanceLedger.append`` (public facade)
      -> ``IncidentLedger.append_maintenance_event``
        -> ``_IncidentEventJournal.append_maintenance`` (atomic
           lookup -> digest compare -> append under the journal ``flock``)

This module adds NO second writer: the only data-product mutations it
performs are ``ledger.append`` (the canonical writer above) and the
in-memory ``ProjectionEngine.apply`` projection advance.  Every append is

* **occurrence-fenced** — the caller supplies the current
  :class:`OccurrenceFence` (locator-only reference to the T2.1 custody
  claim) and a live ``fence_check`` callable; the fence is re-verified at
  every boundary (entry, proposal prior-key lookup, pre-append
  classification, append, projection apply) and a lost fence fails closed
  BEFORE the next write.  ``fence_check=None`` and an always-``never_seen``
  ``prior_key_lookup`` are the forbidden unfenced fallbacks and are
  rejected at the signature boundary (no defaults, explicit ``None``
  rejected).
* **evidence-digest-bound** — the journal's CAS appends only when the
  canonical digest of the incoming event matches the digest recorded for
  the same lifecycle idempotency key; exact replay returns the PRIOR
  committed record (``already_present``) and a divergent digest raises
  :class:`MaintenanceEventConflict` (history is never rewritten).

The fence coordinates deliberately stay OUT of the digest-bound event
bytes: the committed event must remain a pure function of the immutable
report inputs so exact replay stays idempotent across lease reclaims; the
fence gates the WRITE, never the CONTENT.  The fence number under which
each emission decision ran is recorded on the typed
:class:`DailyEmissionRecord` for audit.

Pure construction half (unchanged from M5): the deterministic, store-free
construction of the canonical daily efficiency report and its bound
payloads — exact half-open window boundary-derived from the operational
closure receipt (SD2), closure refs bound into the report input
fingerprint, canonical sorted bytes (SC21), unavailable values preserved
as explicit ``null`` (never fabricated), and locked occurrence-id
derivations.  This module never constructs or mutates an owner store.

Locked Step 20 rules implemented here:

* **Exact half-open window from the closure receipt (SD2).**  The daily
  window is boundary-derived: :class:`OperationalClosureReceipt` proves a
  contiguous, non-overlapping, single-environment chain of committed M4
  operational report windows (``EFFICIENCY_ANALYSIS`` events) from the
  previous daily boundary to the closed boundary, and the daily report's
  window is exactly ``[previous_boundary, closed_boundary)``.  The builder
  takes NO separate window: the report window IS the closure receipt window,
  so a report can never drift from its closure proof.
* **Closure binding.**  The closure receipt's ``report_refs`` (locator-only
  references to the committed operational reports) are part of the report's
  sorted immutable ``input_refs``, and the bundle contract rejects any report
  whose bound input refs omit them.
* **Sorted immutable refs and canonical bytes.**  Input refs, observations,
  baselines, findings, denominators, shadow measures, clusters, and proposals
  are canonical-sorted by the contracts; the builder derives the locked
  ``report_id`` and canonical ``input_fingerprint``, and ``report_bytes`` /
  ``report_hash`` reproduce byte-for-byte from identical immutable inputs
  (SC21).
* **Unavailable values stay null.**  Missing numerators, denominators,
  censoring counts, and unavailable shadow measures serialize as explicit
  JSON ``null`` — never fabricated (SC21).
* **Bound payloads.**  The bundle binds the report, the closure receipt, the
  per-window :class:`DailyEfficiencyCluster` payloads, and the
  :class:`DailyEfficiencyProposal` payloads; every bound payload must agree
  with the report's exact window and environment.

Inputs are pure contracts (Step 2/3/4 payloads plus the closure receipt);
this module never constructs or mutates an owner store.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.efficiency_contracts import (
    DAILY_EFFICIENCY_CONTRACT_ID,
    BaselineSnapshot,
    DailyEfficiencyCluster,
    DailyEfficiencyCorrection,
    DailyEfficiencyKind,
    DailyEfficiencyProposal,
    DailyEfficiencyReport,
    DenominatorCoverage,
    DurationObservation,
    EfficiencyFinding,
    RootCauseCandidate,
    ShadowMeasure,
    ShadowMeasureKind,
    UnavailableReason,
    derive_cluster_occurrence_id,
    derive_correction_occurrence_id,
    derive_input_fingerprint,
    derive_report_occurrence_id,
)
from arnold_pipelines.megaplan.maintenance.events import (
    ClassifierInfo,
    DailyEfficiencyClusterPayload,
    DailyEfficiencyCorrectionPayload,
    DailyEfficiencyProposalPayload,
    DailyEfficiencyReportPayload,
    MaintenanceEvent,
    OccurrenceBudget,
    RootCauseCluster,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    OwnerRef,
    UtcTime,
    Watermark,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.incident.ledger import strict_maintenance_model
from arnold_pipelines.megaplan.maintenance.ledger import (
    MaintenanceEventConflict,
    MaintenanceLedger,
)
from arnold_pipelines.megaplan.maintenance.projections import (
    ProjectionEngine,
    daily_commit_key,
)


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _coerce_environment(environment: EnvironmentId | str | None) -> EnvironmentId | None:
    """Normalize an environment coordinate to its strict identity (or None)."""
    if environment is None:
        return None
    if isinstance(environment, EnvironmentId):
        return environment
    return EnvironmentId(environment)


# ---------------------------------------------------------------------------
# T6.1 occurrence fence (locator-only reference to the T2.1 custody claim)
# ---------------------------------------------------------------------------


class OccurrenceFence(BaseModel):
    """The current occurrence fence coordinates an emission runs under.

    Locator-only REFERENCE to the live T2.1 custody claim
    (``ScheduleService.claim`` / ``claim_superfixer_occurrence`` projection:
    monotonic ``fence`` + one-shot ``claim_token``).  The emitter never
    constructs, mutates, or re-derives custody: the caller passes the
    coordinates it claimed and the ``fence_check`` callable re-reads the
    custody source at every emission boundary.  A stale/lost fence fails
    closed before the next write — it can never mint, extend, or reclaim
    custody here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: StrictStr
    #: Monotonic custody fence of the current claim (T2.1: >= 1).
    fence: int
    #: One-shot claim token of the current claim.
    claim_token: StrictStr

    @field_validator("occurrence_id", "claim_token")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("occurrence fence identity fields must be non-empty")
        return value

    @field_validator("fence")
    @classmethod
    def _validate_fence(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"occurrence fence must be >= 1, got {value}")
        return value


class OccurrenceFenceLostError(RuntimeError):
    """A required occurrence fence was lost at an emission boundary.

    Raised BEFORE the next write at the named boundary: nothing was
    appended, projected, or otherwise mutated by the failed emission step.
    Consistent with the T2.1 custody seam's ``RuntimeError("stale
    occurrence fence")`` vocabulary.
    """


class DailyCorrectionTargetError(ValueError):
    """A keyed daily correction cannot apply to its declared supersedes target.

    Raised by the pre-append target pre-flight (and identically by the
    efficiency reducer) when the declared target is uncommitted or its
    committed digest diverges from the declared digest.  Nothing is
    appended and the projection is untouched.
    """


def _require_live_fence(
    fence_check: Callable[[OccurrenceFence], bool],
    fence: OccurrenceFence,
    *,
    boundary: str,
) -> None:
    """Re-verify the occurrence fence at one emission boundary; fail closed.

    A ``False`` return raises :class:`OccurrenceFenceLostError` naming the
    boundary BEFORE any further read/append/projection step.  An exception
    raised by *fence_check* propagates unchanged (fail closed the same way).
    """
    if not fence_check(fence):
        raise OccurrenceFenceLostError(
            f"occurrence fence lost at the {boundary} boundary "
            f"(occurrence {fence.occurrence_id!r}, fence {fence.fence}); "
            "nothing was written"
        )


# ---------------------------------------------------------------------------
# Operational closure receipt (M4 committed coverage chain)
# ---------------------------------------------------------------------------


class OperationalClosureReceipt(BaseModel):
    """Authoritative closure receipt: contiguous committed operational coverage.

    Proves that committed M4 operational report windows (``EFFICIENCY_ANALYSIS``
    events) cover the exact half-open span ``[previous_boundary,
    closed_boundary)`` contiguously and without overlap in one environment.
    The daily window is boundary-derived from this receipt — never from a cron
    time and never from ``last_closed_watermark`` (SD2).  ``report_refs`` are
    locator-only immutable references to the committed operational reports;
    they are bound into the daily report's ``input_refs`` so the report's
    input fingerprint covers its closure proof.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    environment: EnvironmentId | None = None
    previous_boundary: UtcTime
    closed_boundary: UtcTime
    #: Committed operational report windows, sorted, contiguous, and exactly
    #: covering ``[previous_boundary, closed_boundary)``.
    covered_windows: tuple[EventWindow, ...] = ()
    #: Locator-only refs to the committed EFFICIENCY_ANALYSIS reports.
    report_refs: tuple[OwnerRef, ...] = ()

    @field_validator("covered_windows")
    @classmethod
    def _sort_windows(cls, value: Sequence[EventWindow]) -> tuple[EventWindow, ...]:
        return tuple(
            sorted(value, key=lambda window: (window.start.root, window.end.root))
        )

    @field_validator("report_refs")
    @classmethod
    def _sort_report_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_contiguous_coverage(self) -> OperationalClosureReceipt:
        if self.previous_boundary.root >= self.closed_boundary.root:
            raise ValueError(
                "closure receipt requires previous_boundary < closed_boundary "
                f"({self.previous_boundary.root} >= {self.closed_boundary.root})"
            )
        windows = self.covered_windows
        if not windows:
            raise ValueError(
                "closure receipt requires at least one committed operational "
                "report window (coverage is never assumed)"
            )
        if windows[0].start.root != self.previous_boundary.root:
            raise ValueError(
                "closure receipt coverage must begin exactly at "
                "previous_boundary; a coverage gap or unaligned start is not "
                "closure proof"
            )
        if windows[-1].end.root != self.closed_boundary.root:
            raise ValueError(
                "closure receipt coverage must end exactly at closed_boundary; "
                "an unaligned end is not closure proof"
            )
        for left, right in zip(windows, windows[1:]):
            if left.end.root != right.start.root:
                raise ValueError(
                    "closure receipt coverage must be contiguous and "
                    "non-overlapping; a gap or overlap between operational "
                    "report windows is not closure proof"
                )
        return self

    @property
    def window(self) -> EventWindow:
        """The boundary-derived daily window ``[previous_boundary, closed_boundary)``."""
        return EventWindow(
            start=self.previous_boundary,
            end=self.closed_boundary,
        )


# ---------------------------------------------------------------------------
# Canonical daily report bundle
# ---------------------------------------------------------------------------


class DailyReportBundle(BaseModel):
    """One canonical daily report bound to its closure proof and payloads.

    The bundle is the complete Step 20 artifact: the strict
    :class:`DailyEfficiencyReport` payload, the :class:`OperationalClosureReceipt`
    it is bound to, and the per-window cluster / proposal payloads emitted
    alongside it.  Every bound payload must agree with the report's exact
    half-open window and environment, and the report's ``input_refs`` must
    include the closure receipt's ``report_refs`` (the report's input
    fingerprint covers its closure proof).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    report: DailyEfficiencyReport
    closure_receipt: OperationalClosureReceipt
    clusters: tuple[DailyEfficiencyCluster, ...] = ()
    proposals: tuple[DailyEfficiencyProposal, ...] = ()

    @field_validator("clusters")
    @classmethod
    def _sort_clusters(
        cls, value: Sequence[DailyEfficiencyCluster]
    ) -> tuple[DailyEfficiencyCluster, ...]:
        return tuple(sorted(value, key=lambda item: item.cluster_id))

    @field_validator("proposals")
    @classmethod
    def _sort_proposals(
        cls, value: Sequence[DailyEfficiencyProposal]
    ) -> tuple[DailyEfficiencyProposal, ...]:
        return tuple(sorted(value, key=lambda item: item.proposal_id))

    @model_validator(mode="after")
    def _check_binding(self) -> DailyReportBundle:
        receipt_window = self.closure_receipt.window
        if self.report.window != receipt_window:
            raise ValueError(
                "report window diverges from the closure receipt window; the "
                "daily window is boundary-derived from the closure receipt "
                f"({self.report.window!r} != {receipt_window!r})"
            )
        if self.report.environment != self.closure_receipt.environment:
            raise ValueError(
                "report environment diverges from the closure receipt "
                "environment; closure proof is single-environment"
            )
        # The report's bound input refs must include the closure proof refs.
        report_refs = set(self.report.input_refs)
        missing = [
            ref for ref in self.closure_receipt.report_refs if ref not in report_refs
        ]
        if missing:
            raise ValueError(
                "report input_refs must include every closure receipt "
                "report_ref; the input fingerprint must cover the closure "
                f"proof (missing {len(missing)} refs)"
            )
        for cluster in self.clusters:
            if cluster.window != self.report.window:
                raise ValueError(
                    "bound cluster window diverges from the report window "
                    f"({cluster.cluster_id!r})"
                )
            if cluster.environment != self.report.environment:
                raise ValueError(
                    "bound cluster environment diverges from the report "
                    f"environment ({cluster.cluster_id!r})"
                )
        for proposal in self.proposals:
            if proposal.window != self.report.window:
                raise ValueError(
                    "bound proposal window diverges from the report window "
                    f"({proposal.proposal_id!r})"
                )
            if proposal.environment != self.report.environment:
                raise ValueError(
                    "bound proposal environment diverges from the report "
                    f"environment ({proposal.proposal_id!r})"
                )
        return self

    @property
    def report_bytes(self) -> str:
        """Canonical serialized bytes of the report payload (reproducible)."""
        return canonical_dumps(self.report)

    @property
    def report_hash(self) -> str:
        """Replayable canonical digest of the report payload."""
        return self.report.report_hash

    def reproduce_report(self) -> bool:
        """True when the report bytes strict-decode back to the same payload.

        ``strict_loads(DailyEfficiencyReport, report_bytes) == report`` AND the
        decoded payload re-serializes to the identical bytes — the canonical
        byte reproduction contract (SC21).
        """
        decoded = strict_loads(DailyEfficiencyReport, self.report_bytes)
        return decoded == self.report and canonical_dumps(decoded) == self.report_bytes


# ---------------------------------------------------------------------------
# Canonical builders
# ---------------------------------------------------------------------------


def build_daily_cluster(
    candidate: RootCauseCandidate,
    *,
    environment: EnvironmentId | str | None,
    window: EventWindow,
    generated_at: UtcTime,
) -> DailyEfficiencyCluster:
    """Build the strict daily cluster payload for one root-cause candidate.

    The cluster identity is the locked derivation over (environment, window,
    root-cause fingerprint); the embedded candidate's fingerprint must equal
    the cluster fingerprint (the Step 1 envelope signature binding stays
    exact), which the contract itself enforces.
    """
    env = _coerce_environment(environment)
    cluster_id = derive_cluster_occurrence_id(
        environment=env,
        window=window,
        root_cause_fingerprint=candidate.root_cause_fingerprint,
    )
    return DailyEfficiencyCluster(
        cluster_id=cluster_id,
        environment=env,
        window=window,
        root_cause_fingerprint=candidate.root_cause_fingerprint,
        candidate=candidate,
        occurrence_refs=candidate.occurrence_refs,
        evidence_refs=candidate.evidence_refs,
        generated_at=generated_at,
    )


def build_daily_report(
    closure_receipt: OperationalClosureReceipt,
    *,
    generated_at: UtcTime,
    classifier_version: str,
    policy_version: str,
    observations: Sequence[DurationObservation] = (),
    baselines: Sequence[BaselineSnapshot] = (),
    findings: Sequence[EfficiencyFinding] = (),
    denominators: Sequence[DenominatorCoverage] = (),
    shadow_measures: Sequence[ShadowMeasure] = (),
    clusters: Sequence[DailyEfficiencyCluster] = (),
    proposals: Sequence[DailyEfficiencyProposal] = (),
    extra_input_refs: Sequence[OwnerRef] = (),
) -> DailyReportBundle:
    """Build the canonical daily report bound to its closure receipt.

    The daily window IS the closure receipt's boundary-derived window
    (SD2) — no separate window is accepted, so a report can never drift from
    its closure proof.  The report's immutable ``input_refs`` are the sorted
    union of the closure receipt's ``report_refs`` and ``extra_input_refs``,
    and the locked ``report_id`` / canonical ``input_fingerprint`` are derived
    from them.  Unavailable shadow denominators and other missing values are
    preserved as explicit ``None`` by the strict contracts (SC21).
    """
    environment = closure_receipt.environment
    window = closure_receipt.window
    input_refs = _sort_refs(
        [*closure_receipt.report_refs, *extra_input_refs]
    )
    report = DailyEfficiencyReport(
        report_id=derive_report_occurrence_id(environment=environment, window=window),
        environment=environment,
        window=window,
        generated_at=generated_at,
        classifier_version=classifier_version,
        policy_version=policy_version,
        observations=tuple(observations),
        baselines=tuple(baselines),
        findings=tuple(findings),
        denominators=tuple(denominators),
        shadow_measures=tuple(shadow_measures),
        input_refs=input_refs,
        input_fingerprint=derive_input_fingerprint(input_refs),
    )
    return DailyReportBundle(
        report=report,
        closure_receipt=closure_receipt,
        clusters=tuple(clusters),
        proposals=tuple(proposals),
    )


# ---------------------------------------------------------------------------
# Step 21: fenced ledger emission, replay, and projection integration
# ---------------------------------------------------------------------------
# The emitter wraps each bound daily payload in the common MaintenanceEvent
# envelope (occurrence identity = the payload's locked daily occurrence ID,
# envelope cluster signature = the payload root-cause fingerprint when one
# exists — the Step 1 seam binding) and appends through the ONE canonical
# writer (``MaintenanceLedger.append`` -> ``IncidentLedger
# .append_maintenance_event`` -> ``_IncidentEventJournal.append_maintenance``),
# then advances the ProjectionEngine with the committed ledger sequence as its
# source cursor.  Idempotency is append-only: an exact duplicate returns the
# PRIOR committed record (already_present), a cross-window proposal
# re-emission is deduplicated by the REQUIRED injected prior-proposal-key
# lookup (SD3), and divergent identity reuse propagates the ledger conflict
# without rewriting history.  Every append is fenced: the caller-supplied
# ``fence_check`` re-reads the T2.1 custody source at each boundary and a
# lost fence fails closed before the next write.  Primary I/O failures
# dead-letter through the ledger and replay at most once.

DailyPayload = (
    DailyEfficiencyReport
    | DailyEfficiencyCluster
    | DailyEfficiencyProposal
    | DailyEfficiencyCorrection
)


def daily_payload_kind(payload: DailyPayload) -> DailyEfficiencyKind:
    """Closed kind of one bound daily payload (report/cluster/proposal/correction)."""
    if isinstance(payload, DailyEfficiencyReport):
        return DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT
    if isinstance(payload, DailyEfficiencyCluster):
        return DailyEfficiencyKind.DAILY_EFFICIENCY_CLUSTER
    if isinstance(payload, DailyEfficiencyProposal):
        return DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL
    if isinstance(payload, DailyEfficiencyCorrection):
        return DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION
    raise TypeError(f"unsupported daily payload type {type(payload).__name__}")


def payload_occurrence_id(payload: DailyPayload) -> str:
    """The locked daily occurrence identity carried by the payload."""
    if isinstance(payload, DailyEfficiencyReport):
        return payload.report_id
    if isinstance(payload, DailyEfficiencyCluster):
        return payload.cluster_id
    if isinstance(payload, DailyEfficiencyProposal):
        return payload.proposal_id
    if isinstance(payload, DailyEfficiencyCorrection):
        return payload.correction_id
    raise TypeError(f"unsupported daily payload type {type(payload).__name__}")


def _envelope_cluster(payload: DailyPayload) -> RootCauseCluster:
    """Reused envelope cluster whose signature binds the payload fingerprint.

    Cluster and proposal payloads carry a root-cause fingerprint — the
    envelope ``cluster.signature`` MUST equal it (Step 1 seam binding).
    Report and correction payloads carry no fingerprint; their signature is
    the deterministic locked occurrence identity, so replay stays stable.
    """
    fingerprint = getattr(payload, "root_cause_fingerprint", None)
    signature = fingerprint if fingerprint else payload_occurrence_id(payload)
    return RootCauseCluster(signature=signature)


def _wrap_payload(payload: DailyPayload) -> object:
    """Bind a daily payload into its closed M5 event payload wrapper."""
    if isinstance(payload, DailyEfficiencyReport):
        return DailyEfficiencyReportPayload(report=payload)
    if isinstance(payload, DailyEfficiencyCluster):
        return DailyEfficiencyClusterPayload(cluster=payload)
    if isinstance(payload, DailyEfficiencyProposal):
        return DailyEfficiencyProposalPayload(proposal=payload)
    if isinstance(payload, DailyEfficiencyCorrection):
        return DailyEfficiencyCorrectionPayload(correction=payload)
    raise TypeError(f"unsupported daily payload type {type(payload).__name__}")


def build_daily_event(
    payload: DailyPayload,
    *,
    event_id: str,
    observed_at: UtcTime | datetime,
    event_time: UtcTime | datetime,
    watermark: Watermark | datetime,
    classifier: ClassifierInfo,
    budget: OccurrenceBudget,
    environment: EnvironmentId | str | None = None,
    fence_refs: Sequence[OwnerRef] = (),
) -> MaintenanceEvent:
    """Wrap one locked daily payload in the common MaintenanceEvent envelope.

    The occurrence identity is the payload's locked daily occurrence ID (the
    sole idempotency scope), the envelope window is the payload's exact
    half-open window, the envelope ``cluster.signature`` binds the payload
    root-cause fingerprint (Step 1 seam), and ``lateness`` is derived from
    the watermark by the envelope contract.  ``fence_refs`` are locator-only
    references to the current resident fence (never owned here).
    """
    payload_environment = payload.environment  # type: ignore[attr-defined]
    return MaintenanceEvent.build(
        event_id=event_id,
        occurrence_id=payload_occurrence_id(payload),
        observed_at=observed_at,
        event_time=event_time,
        window=payload.window,  # type: ignore[attr-defined]
        watermark=watermark,
        classifier=classifier,
        cluster=_envelope_cluster(payload),
        budget=budget,
        payload=_wrap_payload(payload),  # type: ignore[arg-type]
        environment=(
            environment if environment is not None else payload_environment
        ),
        fence_refs=fence_refs,
    )


class DailyEmissionOutcome(str, Enum):
    """Closed outcome of one daily event emission.

    ``appended`` — the event was newly appended and advanced the projection;
    ``already_present`` — the exact duplicate (or cross-window proposal key)
    was already committed, so nothing new was appended and history was not
    rewritten.
    """

    APPENDED = "appended"
    ALREADY_PRESENT = "already_present"


class DailyEmissionRecord(BaseModel):
    """One typed emission record (Step 21 output)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    kind: DailyEfficiencyKind
    occurrence_id: StrictStr
    event_id: StrictStr
    outcome: DailyEmissionOutcome
    seq: int | None = None
    digest: StrictStr
    #: Locked cross-window proposal key for proposal records (SD3).
    proposal_key: StrictStr | None = None
    #: Occurrence fence number under which this emission decision ran (T6.1
    #: audit coordinate; locator-only — never part of the event digest).
    fence: int

    @field_validator("event_id", "occurrence_id", "digest")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("emission record identities/digests must be non-empty")
        return value

    @field_validator("fence")
    @classmethod
    def _validate_fence(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"emission record fence must be >= 1, got {value}")
        return value


class DailyEmissionResult(BaseModel):
    """Deterministic collection of daily emission records, in emission order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    records: tuple[DailyEmissionRecord, ...] = ()


def _committed_daily_record(
    ledger: MaintenanceLedger, event: MaintenanceEvent
) -> dict[str, Any] | None:
    """Return the committed journal record for *event*, or ``None``.

    The daily event's canonical lifecycle idempotency key is its occurrence
    identity (the sole idempotency scope), so the lookup uses
    ``event.idempotency_key`` through the facade's composed incident journal
    — the same seam the ledger's own at-most-once replay uses.  This is a
    best-effort pre-append classification aid: the journal's atomic
    lookup->append CAS remains authoritative for concurrent writers.
    """
    return ledger._incident.lookup_maintenance_event(event.idempotency_key)


def _classify_existing(
    ledger: MaintenanceLedger,
    event: MaintenanceEvent,
    existing: dict[str, Any],
    *,
    event_digest: str,
    kind: DailyEfficiencyKind,
    proposal_key: str | None,
    fence: int,
) -> DailyEmissionRecord:
    """Classify a committed record as already-present or divergent reuse.

    An existing record whose canonical digest matches the incoming event is
    an exact duplicate (already_present).  A digest mismatch is DIVERGENT
    identity reuse: history is never rewritten, and the ledger conflict is
    raised exactly as the journal would raise it on append (nothing written).
    """
    stored = existing.get("payload") or {}
    try:
        stored_digest = canonical_digest(strict_maintenance_model(stored))
    except Exception as exc:  # pragma: no cover - defensive
        raise MaintenanceEventConflict(
            "daily emission found an un-decodable committed record for "
            f"lifecycle key {event.idempotency_key!r}; nothing appended"
        ) from exc
    if stored_digest != event_digest:
        raise MaintenanceEventConflict(
            "daily emission reuses lifecycle key "
            f"{event.idempotency_key!r} with a divergent digest; history "
            "is never rewritten and nothing was appended"
        )
    return DailyEmissionRecord(
        kind=kind,
        occurrence_id=event.occurrence_id,
        event_id=event.event_id,
        outcome=DailyEmissionOutcome.ALREADY_PRESENT,
        seq=int(existing["seq"]),
        digest=event_digest,
        proposal_key=proposal_key,
        fence=fence,
    )


def _preflight_daily_correction(
    engine: ProjectionEngine, event: MaintenanceEvent
) -> None:
    """Fail closed BEFORE the append when a keyed correction cannot apply.

    Mirrors the efficiency reducer's keyed-supersedes validation against the
    engine's committed-daily registry (the same ``daily_commit_key``
    derivation — one definition, never a second representation): an
    uncommitted target or a divergent declared digest raises
    :class:`DailyCorrectionTargetError` before ``ledger.append`` so a
    projection-rejected correction event can never enter the journal.
    Conservative by design: a target committed by a DIFFERENT writer
    process (invisible to this engine) fails closed here too — replay the
    engine from the journal first (T6.2 runner owns one ledger + engine).
    """
    payload = event.payload.correction
    target_key = daily_commit_key(
        payload.supersedes_kind.value, payload.supersedes_window
    )
    committed = engine.efficiency.committed_daily.get(target_key)
    if committed is None:
        raise DailyCorrectionTargetError(
            "daily correction supersedes an uncommitted target "
            f"{target_key!r}; nothing appended"
        )
    committed_digest = committed[1]
    if committed_digest != payload.supersedes_digest:
        raise DailyCorrectionTargetError(
            "daily correction supersedes digest does not match the committed "
            f"target {target_key!r}: declared {payload.supersedes_digest!r} "
            f"!= committed {committed_digest!r}; nothing appended"
        )


def _require_emission_injections(
    *,
    prior_key_lookup: Callable[[str], bool] | None,
    fence_check: Callable[[OccurrenceFence], bool] | None,
) -> None:
    """Reject the forbidden unfenced fallbacks at the signature boundary.

    ``prior_key_lookup=None`` (an implicit always-``never_seen`` lookup that
    would re-append cross-window proposals) and ``fence_check=None`` (an
    unfenced append path) are the exact optional fallbacks G0-006 forbids
    porting; production emission requires both callables.
    """
    if prior_key_lookup is None:
        raise ValueError(
            "daily emission requires a real prior-proposal-key lookup; "
            "prior_key_lookup=None is the forbidden always-never_seen "
            "fallback (SD3)"
        )
    if not callable(prior_key_lookup):
        raise ValueError("prior_key_lookup must be callable")
    if fence_check is None:
        raise ValueError(
            "daily emission requires a live occurrence-fence check; "
            "fence_check=None is the forbidden unfenced fallback (G0-006)"
        )
    if not callable(fence_check):
        raise ValueError("fence_check must be callable")


def emit_daily_events(
    bundle: DailyReportBundle,
    *,
    ledger: MaintenanceLedger,
    engine: ProjectionEngine,
    observed_at: UtcTime | datetime,
    event_time: UtcTime | datetime,
    watermark: Watermark | datetime,
    classifier: ClassifierInfo,
    budget: OccurrenceBudget,
    prior_key_lookup: Callable[[str], bool],
    occurrence_fence: OccurrenceFence,
    fence_check: Callable[[OccurrenceFence], bool],
    corrections: Sequence[DailyEfficiencyCorrection] = (),
    event_id_prefix: str = "daily-efficiency",
) -> DailyEmissionResult:
    """Append report, cluster, proposal, and correction events idempotently.

    Emission order is deterministic: report, then clusters, then proposals,
    then corrections (so a keyed correction always sees its superseded target
    already committed).  For every payload:

    * the event is built with a DETERMINISTIC event id
      ``{event_id_prefix}|{occurrence_id}`` — replaying the same payload
      derives the same event;
    * the occurrence fence is re-verified through ``fence_check`` at EVERY
      boundary — emission entry, proposal prior-key lookup, pre-append
      classification, append, and projection apply — and a lost fence raises
      :class:`OccurrenceFenceLostError` BEFORE the next write (fence loss at
      or before the append boundary leaves the journal untouched);
    * a proposal whose locked cross-window key is already committed under the
      current fence (``prior_key_lookup``) is recorded ``already_present``
      and NEVER reaches the ledger — the same proposal never re-appends at
      the occurrence-only lifecycle_idempotency_key boundary (SD3);
    * an event whose occurrence identity is already committed is recorded
      ``already_present`` (exact duplicate) or raises the ledger conflict
      (divergent identity reuse — history is never rewritten); the exact
      duplicate ALSO advances the projection deterministically (the engine
      dedupes an already-applied event, so a prior crash between append and
      projection self-heals on replay);
    * a keyed correction whose declared supersedes target is uncommitted or
      digest-divergent fails closed via the pre-append target pre-flight —
      a projection-rejected correction can never enter the journal;
    * a newly appended event advances the projection engine with the ledger
      sequence as its source cursor; a primary I/O failure propagates after
      dead-lettering (replayable at most once).

    The fence coordinates gate the WRITE, never the CONTENT: they stay out
    of the digest-bound event bytes so exact replay stays idempotent across
    lease reclaims; each record carries the fence number for audit.
    """
    _require_emission_injections(
        prior_key_lookup=prior_key_lookup, fence_check=fence_check
    )
    if not isinstance(occurrence_fence, OccurrenceFence):
        raise ValueError(
            "daily emission requires the current OccurrenceFence coordinates "
            "of the T2.1 custody claim"
        )
    _require_live_fence(fence_check, occurrence_fence, boundary="emission-entry")

    records: list[DailyEmissionRecord] = []
    order: Sequence[DailyPayload] = (
        [bundle.report]
        + list(bundle.clusters)
        + list(bundle.proposals)
        + list(corrections)
    )
    for payload in order:
        kind = daily_payload_kind(payload)
        occurrence_id = payload_occurrence_id(payload)
        event_id = f"{event_id_prefix}|{occurrence_id}"
        digest = canonical_digest(payload)

        proposal_key: str | None = None
        if kind is DailyEfficiencyKind.DAILY_EFFICIENCY_PROPOSAL:
            proposal_key = payload.proposal_key  # type: ignore[attr-defined]
            _require_live_fence(
                fence_check, occurrence_fence, boundary="proposal-prior-key-lookup"
            )
            if prior_key_lookup(proposal_key):
                records.append(
                    DailyEmissionRecord(
                        kind=kind,
                        occurrence_id=occurrence_id,
                        event_id=event_id,
                        outcome=DailyEmissionOutcome.ALREADY_PRESENT,
                        digest=digest,
                        proposal_key=proposal_key,
                        fence=occurrence_fence.fence,
                    )
                )
                continue

        event = build_daily_event(
            payload,
            event_id=event_id,
            observed_at=observed_at,
            event_time=event_time,
            watermark=watermark,
            classifier=classifier,
            budget=budget,
            environment=bundle.report.environment,
        )
        event_digest = canonical_digest(event)
        _require_live_fence(
            fence_check, occurrence_fence, boundary="pre-append-classification"
        )
        existing = _committed_daily_record(ledger, event)
        if existing is not None:
            record = _classify_existing(
                ledger,
                event,
                existing,
                event_digest=event_digest,
                kind=kind,
                proposal_key=proposal_key,
                fence=occurrence_fence.fence,
            )
            # Deterministic projection catch-up: the engine dedupes an
            # already-applied event (DEDUPED, no state change) and applies a
            # committed-but-unprojected one (a prior crash between append and
            # apply self-heals here).  The cursor is the COMMITTED seq.
            _require_live_fence(
                fence_check, occurrence_fence, boundary="projection-catch-up"
            )
            engine.apply(event, cursor=int(existing["seq"]))
            records.append(record)
            continue

        if kind is DailyEfficiencyKind.DAILY_EFFICIENCY_CORRECTION:
            _preflight_daily_correction(engine, event)
        _require_live_fence(fence_check, occurrence_fence, boundary="append")
        appended = ledger.append(event)
        seq = int(appended["seq"])
        _require_live_fence(
            fence_check, occurrence_fence, boundary="projection-apply"
        )
        engine.apply(event, cursor=seq)
        records.append(
            DailyEmissionRecord(
                kind=kind,
                occurrence_id=occurrence_id,
                event_id=event_id,
                outcome=DailyEmissionOutcome.APPENDED,
                seq=seq,
                digest=digest,
                proposal_key=proposal_key,
                fence=occurrence_fence.fence,
            )
        )
    return DailyEmissionResult(records=tuple(records))


# ---------------------------------------------------------------------------
# Step 22: discoverable late-correction generation and shadow aggregation
# ---------------------------------------------------------------------------
# The runner revisits every already-reported window and compares the CURRENT
# per-window owner snapshot fingerprint (canonical hash of the current owner
# snapshot cursors/digests) with the fingerprint BOUND into the committed
# report.  An advanced input set deterministically generates exactly one
# keyed DAILY_EFFICIENCY_CORRECTION whose identity is locked to the
# superseded (kind, window, digest) target (Step 4) — a late-evidence digest
# advance derives a NEW correction identity instead of rewriting the prior
# report.  Re-deriving the same advancement yields the SAME correction
# (replay idempotent at the identity level), and emitting it through
# emit_daily_events is already_present on replay.  Shadow-evaluation
# measures are then aggregated from committed reports and corrections with
# unavailable denominators preserved as explicit null (never fabricated).


class InputAdvancement(BaseModel):
    """One deterministic per-window input-advancement comparison (Step 22).

    ``advanced`` is true exactly when the current owner snapshot fingerprint
    diverges from the fingerprint bound into the committed report; a false
    result carries NO correction (a correction is never fabricated for an
    unchanged input set).  On advancement the keyed correction is derived
    deterministically: the same ``(report, current_refs, supersedes_digest)``
    always derives the same :class:`DailyEfficiencyCorrection`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    window: EventWindow
    bound_fingerprint: StrictStr
    current_fingerprint: StrictStr
    advanced: bool
    correction: DailyEfficiencyCorrection | None = None

    @field_validator("bound_fingerprint", "current_fingerprint")
    @classmethod
    def _validate_fingerprints(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(
                "input fingerprints must be 64-character lowercase sha256 hex digests"
            )
        return value

    @model_validator(mode="after")
    def _check_correction_consistency(self) -> InputAdvancement:
        if not self.advanced and self.correction is not None:
            raise ValueError(
                "an un-advanced input set never carries a correction; a "
                "correction is only fabricated on advancement"
            )
        if self.advanced and self.correction is None:
            raise ValueError(
                "an advanced input set must carry exactly one keyed correction"
            )
        return self


def current_input_fingerprint(current_refs: Sequence[OwnerRef]) -> str:
    """Canonical fingerprint of the CURRENT per-window owner snapshot refs.

    The refs carry the owner snapshot cursors/digests (locator-only), so the
    fingerprint is the canonical hash of the exact current input set — the
    Step 22 correction-discovery basis.
    """
    return derive_input_fingerprint(current_refs)


def build_input_advance_correction(
    *,
    report: DailyEfficiencyReport,
    current_refs: Sequence[OwnerRef],
    generated_at: UtcTime,
    supersedes_digest: str | None = None,
    reason: str | None = None,
) -> InputAdvancement:
    """Compare the current owner snapshot refs with the report-bound refs.

    When the current fingerprint equals the report's bound fingerprint the
    input set did NOT advance and no correction is produced.  When it
    advanced, exactly one :class:`DailyEfficiencyCorrection` is derived,
    keyed to the superseded digest (default: the committed report's canonical
    ``report_hash``; a caller may pass the latest committed correction digest
    for the same window so a further digest advance derives a NEW identity).
    The new input fingerprint is carried in the correction ``reason`` so the
    correction records exactly which input set superseded the committed one.
    The derivation is deterministic: replaying the same inputs derives the
    same correction identity (replay idempotent).
    """
    bound = report.input_fingerprint
    current = current_input_fingerprint(current_refs)
    if current == bound:
        return InputAdvancement(
            window=report.window,
            bound_fingerprint=bound,
            current_fingerprint=current,
            advanced=False,
            correction=None,
        )
    superseded = supersedes_digest or report.report_hash
    fingerprint_reason = (
        reason
        if reason is not None
        else f"input_advanced|{current}"
    )
    correction = DailyEfficiencyCorrection(
        correction_id=derive_correction_occurrence_id(
            supersedes_kind=DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
            supersedes_window=report.window,
            supersedes_digest=superseded,
        ),
        supersedes_kind=DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT,
        supersedes_window=report.window,
        supersedes_digest=superseded,
        environment=report.environment,
        window=report.window,
        reason=fingerprint_reason,
        generated_at=generated_at,
    )
    return InputAdvancement(
        window=report.window,
        bound_fingerprint=bound,
        current_fingerprint=current,
        advanced=True,
        correction=correction,
    )


class ShadowAggregate(BaseModel):
    """One aggregated shadow-evaluation measure (Step 22.3).

    Numerators and denominators are summed only when EVERY contributing
    measure carries them; a single unavailable denominator keeps the
    aggregate denominator (and value) explicitly ``None`` with a typed
    ``unavailable_reason`` — an unavailable denominator is never fabricated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    measure: ShadowMeasureKind
    numerator: int | None = None
    denominator: int | None = None
    value: float | None = None
    unavailable_reason: UnavailableReason | None = None
    contributing_measure_count: int = Field(ge=0)
    unavailable_measure_count: int = Field(ge=0)


class ShadowAggregation(BaseModel):
    """Deterministic aggregation of shadow measures across committed reports.

    Measures are collected from committed reports EXCLUDING the reports a
    keyed correction supersedes (their measures were corrected and cannot
    support the aggregate), then grouped by measure kind in canonical order.
    ``correction_count`` records how many keyed corrections were consulted;
    ``report_count`` / ``superseded_report_count`` record the committed
    report provenance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    aggregates: tuple[ShadowAggregate, ...] = ()
    report_count: int = Field(ge=0)
    superseded_report_count: int = Field(ge=0)
    correction_count: int = Field(ge=0)


def aggregate_shadow_measures(
    reports: Sequence[DailyEfficiencyReport],
    corrections: Sequence[DailyEfficiencyCorrection] = (),
) -> ShadowAggregation:
    """Aggregate shadow-evaluation measures from committed reports/corrections.

    A keyed correction supersedes exactly one committed report digest; the
    superseded report's shadow measures are EXCLUDED (they were corrected and
    cannot contribute).  Within each measure kind the numerator/denominator
    are summed only when every contributing measure carries them; otherwise
    the aggregate denominator and value stay explicit ``None`` with a typed
    unavailable reason (never fabricated).  Deterministic canonical order by
    measure kind.
    """
    superseded_digests = {correction.supersedes_digest for correction in corrections}
    superseded_ids = {
        report.report_id
        for report in reports
        if report.report_hash in superseded_digests
    }
    contributing: list[ShadowMeasure] = []
    for report in reports:
        if report.report_id in superseded_ids:
            continue
        contributing.extend(report.shadow_measures)
    by_kind: dict[ShadowMeasureKind, list[ShadowMeasure]] = {}
    for measure in contributing:
        by_kind.setdefault(measure.measure, []).append(measure)
    aggregates: list[ShadowAggregate] = []
    for kind in sorted(by_kind, key=lambda item: item.value):
        measures = by_kind[kind]
        all_available = all(
            measure.numerator is not None and measure.denominator is not None
            for measure in measures
        )
        unavailable = [
            measure
            for measure in measures
            if measure.numerator is None or measure.denominator is None
        ]
        if all_available:
            numerator = sum(int(measure.numerator) for measure in measures)  # type: ignore[arg-type]
            denominator = sum(int(measure.denominator) for measure in measures)  # type: ignore[arg-type]
            if denominator <= 0:
                aggregates.append(
                    ShadowAggregate(
                        measure=kind,
                        numerator=numerator,
                        denominator=0,
                        value=None,
                        unavailable_reason=UnavailableReason.ZERO_DENOMINATOR,
                        contributing_measure_count=len(measures),
                        unavailable_measure_count=0,
                    )
                )
            else:
                aggregates.append(
                    ShadowAggregate(
                        measure=kind,
                        numerator=numerator,
                        denominator=denominator,
                        value=numerator / denominator,
                        contributing_measure_count=len(measures),
                        unavailable_measure_count=0,
                    )
                )
        else:
            first_unavailable = next(
                (
                    measure.unavailable_reason
                    for measure in unavailable
                    if measure.unavailable_reason is not None
                ),
                None,
            )
            reason = first_unavailable or UnavailableReason.MISSING_DENOMINATOR
            aggregates.append(
                ShadowAggregate(
                    measure=kind,
                    numerator=None,
                    denominator=None,
                    value=None,
                    unavailable_reason=reason,
                    contributing_measure_count=len(measures),
                    unavailable_measure_count=len(unavailable),
                )
            )
    return ShadowAggregation(
        aggregates=tuple(aggregates),
        report_count=len(reports),
        superseded_report_count=len(superseded_ids),
        correction_count=len(corrections),
    )


__all__ = [
    "DailyCorrectionTargetError",
    "DailyEmissionOutcome",
    "DailyEmissionRecord",
    "DailyEmissionResult",
    "DailyReportBundle",
    "InputAdvancement",
    "OccurrenceFence",
    "OccurrenceFenceLostError",
    "OperationalClosureReceipt",
    "ShadowAggregate",
    "ShadowAggregation",
    "aggregate_shadow_measures",
    "build_daily_cluster",
    "build_daily_event",
    "build_daily_report",
    "build_input_advance_correction",
    "current_input_fingerprint",
    "daily_payload_kind",
    "emit_daily_events",
    "payload_occurrence_id",
]
