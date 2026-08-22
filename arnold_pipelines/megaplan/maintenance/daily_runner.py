"""T6.2 closure-proven daily runner over fenced efficiency events.

One entry point — :func:`run_daily_efficiency` — owns the WHOLE daily
efficiency cycle against ONE ``(MaintenanceLedger, ProjectionEngine)`` pair
and PROVES terminal closure deterministically:

1. **Replay-first (resolves the T6.1 residual).**  The runner scans the
   incident journal once (read-only), replays every committed Maintenance
   event into a FRESH :class:`ProjectionEngine` with the journal sequences
   as source cursors, and only then derives closure and emits.  The replayed
   engine's ``committed_daily`` registry therefore already contains every
   cross-process commit, so a keyed correction whose supersedes target was
   committed by a DIFFERENT writer process passes the T6.1 pre-append
   pre-flight instead of false-rejecting (the T6.1 engine-scoped pre-flight
   fails closed exactly because a bare engine cannot see foreign commits —
   the runner closes that gap by owning the replay).
2. **Closure authority (SD2, adapted from the M5 coordinator).**
   :func:`derive_daily_closure` proves a contiguous, non-overlapping,
   single-environment chain of committed ``EFFICIENCY_ANALYSIS`` operational
   report windows from ``previous_boundary`` to ``candidate_boundary``.  The
   daily window IS the proven span — never nominal clock time and never
   ``last_closed_watermark``.  An empty chain, a coverage gap/overlap, a
   cross-environment break, or an incoherent (torn) committed read is a
   typed NON-APPENDING result: no analysis, no synthesis, no emission.
3. **Exactly-once fenced emission.**  The single synthesizer binds the
   canonical bundle and the runner emits the day's
   report -> cluster -> proposal -> correction events through the T6.1
   :func:`emit_daily_events` seam — the ONE canonical writer — under the
   caller's live :class:`OccurrenceFence` (T2.1 custody claim coordinates).
   The fence is re-verified at every emission boundary and a lost fence is
   mapped to a typed NON-APPENDING result; the journal stays authoritative
   and the next run converges deterministically (committed events classify
   ``already_present`` and unprojected ones self-heal on replay).  The SD3
   prior-proposal-key lookup is DERIVED from the replayed journal (real,
   journal-authoritative) — no ``fence_check=None`` and no
   always-``never_seen`` fallback exists on this API (G0-006 / MF-004).
4. **Closure proof (typed, not prose).**  After emission the runner re-reads
   the journal fresh, proves that every committed emission record's
   sequence exists, that each daily stream cursor equals the latest
   committed journal sequence of its kind, and that a fresh replay of the
   full journal reproduces BYTE-IDENTICAL projection state — then returns
   the validated :class:`DailyClosureReceipt`.  An unverified receipt
   cannot be constructed; a failed proof raises
   :class:`DailyReplayMismatchError` (fail closed).

The runner performs NO raw I/O beyond read-only journal scans, adds NO
second writer (its only data-product mutations are the delegated
``emit_daily_events`` appends and the in-memory projection advance), and
mints no schedule, ticket, repair, or policy authority: it is a consumer of
the T2.1 claim coordinates and never constructs, extends, or reclaims
custody.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.incident.ledger import strict_maintenance_model
from arnold_pipelines.megaplan.maintenance.efficiency_contracts import (
    DAILY_EFFICIENCY_CONTRACT_ID,
    BaselineSnapshot,
    DailyEfficiencyCorrection,
    DailyEfficiencyKind,
    DailyEfficiencyProposal,
    DenominatorCoverage,
    DurationObservation,
    EfficiencyFinding,
    RootCauseCandidate,
    ShadowMeasure,
)
from arnold_pipelines.megaplan.maintenance.efficiency_reporting import (
    DailyEmissionOutcome,
    DailyEmissionResult,
    DailyReportBundle,
    OccurrenceFence,
    OccurrenceFenceLostError,
    OperationalClosureReceipt,
    build_daily_cluster,
    build_daily_report,
    emit_daily_events,
)
from arnold_pipelines.megaplan.maintenance.events import (
    ClassifierInfo,
    DailyEfficiencyProposalPayload,
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    OwnerRef,
    UtcTime,
    Watermark,
    canonical_digest,
    canonical_dumps,
)
from arnold_pipelines.megaplan.maintenance.ledger import MaintenanceLedger
from arnold_pipelines.megaplan.maintenance.projections import (
    DAILY_EVENT_KINDS,
    ProjectionEngine,
    replay,
)

#: Default classifier version for the envelope (the locked analysis default).
DEFAULT_CLASSIFIER_VERSION = "cls-v1"

#: Default report policy version (the provisional Step 19 shadow packet).
DEFAULT_POLICY_VERSION = "policy-v1"

#: Default deterministic event-id prefix (T6.1 emission seam contract).
DEFAULT_EVENT_ID_PREFIX = "daily-efficiency"

_FENCE_BOUNDARY_RE = re.compile(r"at the (.+?) boundary")


def _coerce_utc(value: UtcTime | datetime) -> UtcTime:
    """Normalize a timestamp to its strict UtcTime identity."""
    return value if isinstance(value, UtcTime) else UtcTime(value)


def _coerce_environment(
    environment: EnvironmentId | str | None,
) -> EnvironmentId | None:
    """Normalize an environment coordinate to its strict identity (or None)."""
    if environment is None or isinstance(environment, EnvironmentId):
        return environment
    return EnvironmentId(environment)


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


# ---------------------------------------------------------------------------
# Closure authority: the typed daily closure probe (SD2, adapted from M5)
# ---------------------------------------------------------------------------


class DailyClosureOutcome(str, Enum):
    """Closed outcome of one daily closure probe.

    ``closed`` is the ONLY outcome that may synthesize and emit a daily
    report.  Every other outcome is a typed NON-APPENDING result: an empty
    committed chain (``empty_chain``), a coverage gap or overlap
    (``coverage_gap``), a cross-environment break
    (``cross_environment_break``), or an incoherent committed read
    (``incoherent_read``) never produces a green report and never advances
    the boundary.
    """

    CLOSED = "closed"
    EMPTY_CHAIN = "empty_chain"
    COVERAGE_GAP = "coverage_gap"
    CROSS_ENVIRONMENT_BREAK = "cross_environment_break"
    INCOHERENT_READ = "incoherent_read"


class DailyClosureResult(BaseModel):
    """One typed closure probe result.

    ``receipt`` is present exactly when ``outcome`` is ``closed``; the daily
    window is the receipt's boundary-derived window
    ``[previous_boundary, closed_boundary)``.  A non-closed outcome carries
    the typed reason and NO receipt — there is nothing to close.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    outcome: DailyClosureOutcome
    reason: StrictStr | None = None
    receipt: OperationalClosureReceipt | None = None

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("closure reason must be a non-empty string when present")
        return value

    @model_validator(mode="after")
    def _check_shape(self) -> DailyClosureResult:
        if self.outcome is DailyClosureOutcome.CLOSED:
            if self.receipt is None:
                raise ValueError("a closed closure probe requires the closure receipt")
            if self.reason is not None:
                raise ValueError("a closed closure probe cannot carry a failure reason")
        else:
            if self.receipt is not None:
                raise ValueError("a non-closed closure probe cannot carry a receipt")
            if self.reason is None:
                raise ValueError("a non-closed closure probe requires a typed reason")
        return self

    @property
    def closed(self) -> bool:
        """True exactly when closure is proven (the only emitting outcome)."""
        return self.outcome is DailyClosureOutcome.CLOSED


def derive_report_refs(events: Sequence[MaintenanceEvent]) -> tuple[OwnerRef, ...]:
    """Locator-only immutable refs to the committed operational reports.

    Each ref binds the event's canonical digest so the daily report's input
    fingerprint covers its closure proof (the Step 20 binding rule).
    """
    return _sort_refs(
        tuple(
            OwnerRef(
                owner="maintenance",
                record_type="efficiency_analysis",
                locator=f"ledger://efficiency_analysis/{event.occurrence_id}",
                digest=canonical_digest(event),
            )
            for event in events
        )
    )


def derive_daily_closure(
    *,
    events: Sequence[Any],
    previous_boundary: UtcTime | datetime,
    candidate_boundary: UtcTime | datetime,
    environment: EnvironmentId | str | None,
    report_refs: Sequence[OwnerRef] | None = None,
) -> DailyClosureResult:
    """Prove the authoritative daily closure receipt from committed events.

    Sorts the committed operational report windows (``EFFICIENCY_ANALYSIS``
    events' window coordinates) and proves a contiguous, non-overlapping,
    single-environment chain from ``previous_boundary`` to
    ``candidate_boundary``.  The daily window is boundary-derived from that
    proof — never from a cron time and never from ``last_closed_watermark``
    (SD2).  A coverage gap or overlap, a cross-environment break, an
    incoherent committed read, or an empty chain yields a typed
    NON-APPENDING outcome with no receipt.

    ``events`` may be canonical ledger record dicts or already
    strict-decoded :class:`MaintenanceEvent` objects; every record must
    strict-decode or the probe is ``incoherent_read`` (closure proof is
    never guessed from torn bytes).
    """
    env = _coerce_environment(environment)
    previous = _coerce_utc(previous_boundary)
    candidate = _coerce_utc(candidate_boundary)
    if previous.root >= candidate.root:
        return DailyClosureResult(
            outcome=DailyClosureOutcome.COVERAGE_GAP,
            reason=(
                "closure requires previous_boundary < candidate_boundary "
                f"({previous.root.isoformat()} >= {candidate.root.isoformat()})"
            ),
        )

    decoded: list[MaintenanceEvent] = []
    for index, record in enumerate(events):
        if isinstance(record, MaintenanceEvent):
            decoded.append(record)
            continue
        try:
            model = strict_maintenance_model(record)
        except Exception as exc:  # noqa: BLE001 - every decode failure is torn
            if not isinstance(record, dict):
                return DailyClosureResult(
                    outcome=DailyClosureOutcome.INCOHERENT_READ,
                    reason=(
                        f"committed operational record {index} is not a "
                        f"decodable MaintenanceEvent: {type(exc).__name__}"
                    ),
                )
            return DailyClosureResult(
                outcome=DailyClosureOutcome.INCOHERENT_READ,
                reason=(
                    f"committed operational record {index} is not a strict "
                    f"MaintenanceEvent: {exc}"
                ),
            )
        if not isinstance(model, MaintenanceEvent):
            return DailyClosureResult(
                outcome=DailyClosureOutcome.INCOHERENT_READ,
                reason=(
                    f"committed operational record {index} is an operational "
                    "lifecycle event, not a MaintenanceEvent report row"
                ),
            )
        decoded.append(model)

    # Scope the coverage evidence to THIS candidate span: only operational
    # report windows that overlap ``[previous, candidate)`` are this day's
    # coverage chain.  Earlier/later days' reports are different days'
    # evidence — they neither close nor gap this span.
    analysis_events = [
        event
        for event in decoded
        if event.event_kind is EventKind.EFFICIENCY_ANALYSIS
        and event.window.end.root > previous.root
        and event.window.start.root < candidate.root
    ]
    if not analysis_events:
        return DailyClosureResult(
            outcome=DailyClosureOutcome.EMPTY_CHAIN,
            reason=(
                "no committed EFFICIENCY_ANALYSIS operational report window; "
                "coverage is never assumed and an empty chain closes nothing"
            ),
        )

    # Single-environment closure proof: every committed operational report
    # must carry the exact requested environment.  A missing (None) or
    # divergent environment cannot prove single-environment coverage.
    for event in analysis_events:
        if event.environment != env:
            return DailyClosureResult(
                outcome=DailyClosureOutcome.CROSS_ENVIRONMENT_BREAK,
                reason=(
                    f"committed operational report {event.occurrence_id!r} "
                    f"carries environment {event.environment!r}; closure "
                    f"proof requires the single environment {env!r}"
                ),
            )

    windows = sorted(
        (event.window for event in analysis_events),
        key=lambda window: (window.start.root, window.end.root),
    )
    if windows[0].start.root != previous.root:
        return DailyClosureResult(
            outcome=DailyClosureOutcome.COVERAGE_GAP,
            reason=(
                "committed operational coverage must begin exactly at the "
                "previous daily boundary; the first window starts at "
                f"{windows[0].start.root.isoformat()} != "
                f"{previous.root.isoformat()} (last_closed_watermark is "
                "never closure proof)"
            ),
        )
    if windows[-1].end.root != candidate.root:
        return DailyClosureResult(
            outcome=DailyClosureOutcome.COVERAGE_GAP,
            reason=(
                "committed operational coverage must end exactly at the "
                "candidate boundary; the last window ends at "
                f"{windows[-1].end.root.isoformat()} != "
                f"{candidate.root.isoformat()}"
            ),
        )
    for left, right in zip(windows, windows[1:]):
        if left.end.root != right.start.root:
            return DailyClosureResult(
                outcome=DailyClosureOutcome.COVERAGE_GAP,
                reason=(
                    "committed operational coverage must be contiguous and "
                    "non-overlapping; the chain breaks between "
                    f"{left.end.root.isoformat()} and "
                    f"{right.start.root.isoformat()}"
                ),
            )

    refs = (
        _sort_refs(report_refs)
        if report_refs is not None
        else derive_report_refs(analysis_events)
    )
    try:
        receipt = OperationalClosureReceipt(
            environment=env,
            previous_boundary=previous,
            closed_boundary=candidate,
            covered_windows=tuple(windows),
            report_refs=refs,
        )
    except Exception as exc:  # noqa: BLE001 - defensive: the chain is proven above
        return DailyClosureResult(
            outcome=DailyClosureOutcome.COVERAGE_GAP,
            reason=f"committed operational coverage cannot be closed: {exc}",
        )
    return DailyClosureResult(
        outcome=DailyClosureOutcome.CLOSED,
        receipt=receipt,
    )


# ---------------------------------------------------------------------------
# Replay-first journal ownership (the T6.1 residual fix)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JournalReplay:
    """One read-only journal scan replayed into a fresh engine.

    ``rows`` are ``(seq, strict model)`` pairs for every committed
    Maintenance row in append order; ``torn`` is the typed failure reason
    when a maintenance-shaped record failed strict decode (the run fails
    closed BEFORE any emission — a torn journal never supports a closure
    proof).  Legacy non-Maintenance incident rows carry no idempotency key
    and are skipped: they are not Maintenance domain events.
    """

    rows: tuple[tuple[int, Any], ...]
    torn: str | None = None

    @property
    def seqs(self) -> tuple[int, ...]:
        return tuple(seq for seq, _ in self.rows)

    @property
    def head_seq(self) -> int:
        return self.seqs[-1] if self.rows else 0

    def maintenance_events(self) -> tuple[Any, ...]:
        return tuple(model for _, model in self.rows)

    def operational_reports(self) -> tuple[MaintenanceEvent, ...]:
        return tuple(
            model
            for model in self.maintenance_events()
            if isinstance(model, MaintenanceEvent)
            and model.event_kind is EventKind.EFFICIENCY_ANALYSIS
        )

    def committed_proposal_keys(self) -> frozenset[str]:
        """Every committed cross-window proposal key (SD3 lookup basis)."""
        return frozenset(
            model.payload.proposal.proposal_key
            for model in self.maintenance_events()
            if isinstance(model, MaintenanceEvent)
            and isinstance(model.payload, DailyEfficiencyProposalPayload)
        )


def _scan_journal(ledger: MaintenanceLedger) -> JournalReplay:
    """Read-only single scan of the committed journal (never fabricates).

    A line that does not parse as JSON is skipped (consistent with every
    journal reader); a record that CLAIMS Maintenance identity (carries an
    idempotency key and a payload dict) but fails strict decode makes the
    whole scan torn — the caller must fail closed.
    """
    rows: list[tuple[int, Any]] = []
    path = ledger.events_path
    if not path.exists():
        return JournalReplay(rows=tuple())
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not (
            isinstance(record, dict)
            and record.get("idempotency_key")
            and isinstance(record.get("payload"), dict)
        ):
            continue  # legacy non-Maintenance incident row
        try:
            model = strict_maintenance_model(record["payload"])
        except Exception as exc:  # noqa: BLE001 - torn maintenance row
            return JournalReplay(
                rows=tuple(),
                torn=(
                    f"journal seq {record.get('seq')!r} claims Maintenance "
                    "identity but its payload does not strict-decode: "
                    f"{exc}"
                ),
            )
        rows.append((int(record["seq"]), model))
    return JournalReplay(rows=tuple(rows))


def _replayed_engine(scan: JournalReplay) -> ProjectionEngine:
    """Replay every committed Maintenance row into a FRESH engine.

    The journal sequences are the source cursors, so the replayed engine's
    stream cursors and ``committed_daily`` registry bind exactly to the
    journal — including every commit made by a DIFFERENT writer process.
    """
    return replay(
        [model for _, model in scan.rows],
        cursors=[seq for seq, _ in scan.rows],
    )


# ---------------------------------------------------------------------------
# Analysis stage (injected, pure) and the SINGLE synthesizer
# ---------------------------------------------------------------------------


class DailyAnalysisOutput(BaseModel):
    """Immutable analysis-stage output bound into one daily report.

    The caller fans out its pure problem-family analyzers over the proven
    closure receipt; the runner never fabricates analytical content.  With
    the default report-only stage the bundle carries the report alone (plus
    any caller-supplied keyed corrections) — a cluster, proposal, or
    correction event is emitted exactly when the day's inputs carry one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    observations: tuple[DurationObservation, ...] = ()
    baselines: tuple[BaselineSnapshot, ...] = ()
    findings: tuple[EfficiencyFinding, ...] = ()
    denominators: tuple[DenominatorCoverage, ...] = ()
    shadow_measures: tuple[ShadowMeasure, ...] = ()
    candidates: tuple[RootCauseCandidate, ...] = ()
    proposals: tuple[DailyEfficiencyProposal, ...] = ()
    extra_input_refs: tuple[OwnerRef, ...] = ()


#: Pure analysis fan-out over the proven closure receipt (injected).
DailyAnalysisStage = Callable[[OperationalClosureReceipt], DailyAnalysisOutput]


def _report_only_analysis(receipt: OperationalClosureReceipt) -> DailyAnalysisOutput:
    """Default analysis stage: report-only, no fabricated analytical content."""
    del receipt
    return DailyAnalysisOutput()


def synthesize_daily_report(
    closure: OperationalClosureReceipt,
    analysis: DailyAnalysisOutput,
    *,
    generated_at: UtcTime | datetime,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> DailyReportBundle:
    """The SINGLE synthesizer: merge clusters and bind the canonical bundle.

    Only this function merges the analysis-stage candidates into per-window
    :class:`DailyEfficiencyCluster` payloads and binds the canonical report
    bundle over the closure receipt.  The bundle's window IS the closure
    receipt's boundary-derived window — a report can never drift from its
    closure proof (SD2).
    """
    generated = _coerce_utc(generated_at)
    clusters = tuple(
        build_daily_cluster(
            candidate,
            environment=closure.environment,
            window=closure.window,
            generated_at=generated,
        )
        for candidate in sorted(analysis.candidates, key=lambda item: item.candidate_id)
    )
    return build_daily_report(
        closure,
        generated_at=generated,
        classifier_version=classifier_version,
        policy_version=policy_version,
        observations=analysis.observations,
        baselines=analysis.baselines,
        findings=analysis.findings,
        denominators=analysis.denominators,
        shadow_measures=analysis.shadow_measures,
        clusters=clusters,
        proposals=analysis.proposals,
        extra_input_refs=analysis.extra_input_refs,
    )


# ---------------------------------------------------------------------------
# Typed run outcome and the terminal closure receipt
# ---------------------------------------------------------------------------


class DailyRunStatus(str, Enum):
    """Closed status of one daily runner invocation.

    ``closed_appended`` — closure was proven, emission ran under a live
    fence, and at least one daily event was newly committed; ``receipt``
    carries the terminal closure proof.  ``closed_joined`` — closure was
    proven and every payload was already committed (an exact rerun joins
    with no new writes); ``receipt`` proves the same terminal state.
    ``non_closing`` — the closure probe (or the journal scan) returned a
    typed non-closing outcome; NOTHING was emitted.  ``fence_lost`` — the
    occurrence fence was lost at an emission boundary; the journal stays
    authoritative and the next run converges deterministically.
    """

    CLOSED_APPENDED = "closed_appended"
    CLOSED_JOINED = "closed_joined"
    NON_CLOSING = "non_closing"
    FENCE_LOST = "fence_lost"


class CommittedDailyRecord(BaseModel):
    """One committed daily payload coordinate inside a closure receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    kind: DailyEfficiencyKind
    occurrence_id: StrictStr
    event_id: StrictStr
    outcome: DailyEmissionOutcome
    #: Committed journal sequence (None only for a proposal short-circuited
    #: by its cross-window prior key — its identity is committed under an
    #: earlier window, never re-appended here).
    seq: int | None = None
    digest: StrictStr
    proposal_key: StrictStr | None = None

    @field_validator("occurrence_id", "event_id", "digest")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("committed record identities/digests must be non-empty")
        return value


class DailyClosureReceipt(BaseModel):
    """Terminal closure proof of one daily runner invocation (typed).

    Constructed ONLY by :func:`run_daily_efficiency` after the proof passed:
    every committed emission sequence exists in the journal, each daily
    stream cursor equals the latest committed journal sequence of its kind,
    and a fresh replay of the full journal reproduced BYTE-IDENTICAL
    projection state (``replay_identical`` is validated ``True`` — an
    unverified receipt cannot be constructed).  The report kind is mandatory
    (a day is never closed without its report); cluster, proposal, and
    correction records appear exactly when the day carried them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    environment: EnvironmentId | None = None
    window: EventWindow
    #: Occurrence fence number under which the day ran (T2.1 audit coordinate).
    fence: int
    committed: tuple[CommittedDailyRecord, ...] = ()
    #: Highest journal sequence observed at proof time (journal-authoritative).
    journal_head_seq: int
    report_cursor: int
    cluster_cursor: int
    proposal_cursor: int
    correction_cursor: int
    custody_output_digest: str | None = None
    verification_output_digest: str | None = None
    efficiency_output_digest: str | None = None
    replay_identical: bool

    @field_validator("fence")
    @classmethod
    def _validate_fence(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"closure receipt fence must be >= 1, got {value}")
        return value

    @field_validator("journal_head_seq", "report_cursor")
    @classmethod
    def _validate_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"receipt coordinates must be >= 0, got {value}")
        return value

    @model_validator(mode="after")
    def _check_proven(self) -> DailyClosureReceipt:
        if not self.replay_identical:
            raise ValueError(
                "a closure receipt can only be issued for a byte-identical "
                "fresh replay; an unverified receipt cannot be constructed"
            )
        report_records = [
            record
            for record in self.committed
            if record.kind is DailyEfficiencyKind.DAILY_EFFICIENCY_REPORT
        ]
        if not report_records:
            raise ValueError(
                "a closure receipt requires the day's report record; a day "
                "is never closed without its report"
            )
        if report_records[0].seq is None:
            raise ValueError(
                "the committed report record must carry its journal sequence"
            )
        for record in self.committed:
            if record.outcome is DailyEmissionOutcome.APPENDED and record.seq is None:
                raise ValueError(
                    f"appended {record.kind.value} record "
                    f"{record.occurrence_id!r} must carry its journal sequence"
                )
        return self


class DailyEfficiencyRunResult(BaseModel):
    """One typed daily runner outcome (never prose-only).

    ``receipt`` is present exactly when the status is a closed one; a
    non-closing or fence-lost run carries the typed ``reason`` (and, for a
    fence loss, the named ``fence_boundary``) and NO receipt.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    status: DailyRunStatus
    closure: DailyClosureResult
    receipt: DailyClosureReceipt | None = None
    reason: StrictStr | None = None
    fence_boundary: StrictStr | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> DailyEfficiencyRunResult:
        if self.status in (DailyRunStatus.CLOSED_APPENDED, DailyRunStatus.CLOSED_JOINED):
            if self.receipt is None:
                raise ValueError("a closed daily run requires its closure receipt")
            if self.reason is not None:
                raise ValueError("a closed daily run cannot carry a failure reason")
        else:
            if self.receipt is not None:
                raise ValueError(
                    "a non-closed daily run is NON-APPENDING and cannot carry "
                    "a closure receipt"
                )
            if not self.reason:
                raise ValueError("a non-closed daily run requires a typed reason")
            if self.status is DailyRunStatus.FENCE_LOST and not self.fence_boundary:
                raise ValueError(
                    "a fence-lost daily run names the boundary that lost the fence"
                )
            if self.status is DailyRunStatus.NON_CLOSING and self.fence_boundary:
                raise ValueError(
                    "a non-closing daily run carries no fence boundary"
                )
        return self

    @property
    def closed(self) -> bool:
        """True exactly when the run proved terminal closure."""
        return self.status in (
            DailyRunStatus.CLOSED_APPENDED,
            DailyRunStatus.CLOSED_JOINED,
        )

    @property
    def appended(self) -> bool:
        """True exactly when the run newly committed at least one event."""
        return self.status is DailyRunStatus.CLOSED_APPENDED


class DailyReplayMismatchError(RuntimeError):
    """The post-emission closure proof failed; nothing further is written.

    The journal stays authoritative: the already-committed events classify
    ``already_present`` on the next run and the projection self-heals on
    replay.  This error indicates the run engine and the journal diverged —
    a bug-level inconsistency, never a green receipt.
    """


# ---------------------------------------------------------------------------
# Closure proof: fresh replay must reproduce byte-identical state
# ---------------------------------------------------------------------------


def _projection_bytes(engine: ProjectionEngine) -> tuple[str, str, str]:
    """Canonical bytes of the three projection states (byte-identity basis)."""
    return (
        canonical_dumps(engine.custody),
        canonical_dumps(engine.verification),
        canonical_dumps(engine.efficiency),
    )


def _stream_cursor_map(engine: ProjectionEngine) -> dict[EventKind, int]:
    """The four daily stream cursors of the efficiency projection."""
    efficiency = engine.efficiency
    return {
        EventKind.DAILY_EFFICIENCY_REPORT: efficiency.report_cursor,
        EventKind.DAILY_EFFICIENCY_CLUSTER: efficiency.cluster_cursor,
        EventKind.DAILY_EFFICIENCY_PROPOSAL: efficiency.proposal_cursor,
        EventKind.DAILY_EFFICIENCY_CORRECTION: efficiency.correction_cursor,
    }


def _prove_closure(
    *,
    ledger: MaintenanceLedger,
    engine: ProjectionEngine,
    emission: DailyEmissionResult,
    closure: DailyClosureResult,
    fence: OccurrenceFence,
) -> DailyClosureReceipt:
    """Prove terminal closure deterministically; return the typed receipt.

    Re-reads the journal FRESH (never trusts in-memory state) and requires:

    * every committed emission record's sequence exists in the journal;
    * each daily stream cursor equals the latest committed journal sequence
      of its kind (cursors ARE journal sequences — auditable back to the
      append-only file);
    * a fresh engine replaying the full journal reproduces BYTE-IDENTICAL
      projection state (canonical bytes of all three projections).
    """
    scan = _scan_journal(ledger)
    if scan.torn is not None:
        raise DailyReplayMismatchError(
            f"closure proof aborted: the journal scan is torn: {scan.torn}"
        )
    committed_seqs = set(scan.seqs)
    for record in emission.records:
        if record.seq is not None and record.seq not in committed_seqs:
            raise DailyReplayMismatchError(
                f"closure proof aborted: committed {record.kind.value} record "
                f"{record.occurrence_id!r} names journal seq {record.seq} "
                "which the fresh journal read does not contain"
            )

    latest_by_kind: dict[EventKind, int] = {}
    for seq, model in scan.rows:
        if (
            isinstance(model, MaintenanceEvent)
            and model.event_kind in DAILY_EVENT_KINDS
        ):
            latest_by_kind[model.event_kind] = seq  # append order: last wins

    fresh = _replayed_engine(scan)
    for kind, cursor in _stream_cursor_map(engine).items():
        expected = latest_by_kind.get(kind, 0)
        if cursor != expected:
            raise DailyReplayMismatchError(
                f"closure proof aborted: {kind.value} stream cursor "
                f"{cursor} != latest committed journal seq {expected}"
            )
    if _projection_bytes(fresh) != _projection_bytes(engine):
        raise DailyReplayMismatchError(
            "closure proof aborted: a fresh replay of the journal did not "
            "reproduce byte-identical projection state"
        )

    committed = tuple(
        CommittedDailyRecord(
            kind=record.kind,
            occurrence_id=record.occurrence_id,
            event_id=record.event_id,
            outcome=record.outcome,
            seq=record.seq,
            digest=record.digest,
            proposal_key=record.proposal_key,
        )
        for record in emission.records
    )
    proven_receipt = closure.receipt
    if proven_receipt is None:  # pragma: no cover - caller-proven invariant
        raise DailyReplayMismatchError(
            "closure proof aborted: the closed probe lost its receipt"
        )
    return DailyClosureReceipt(
        environment=proven_receipt.environment,
        window=proven_receipt.window,
        fence=fence.fence,
        committed=committed,
        journal_head_seq=scan.head_seq,
        report_cursor=engine.efficiency.report_cursor,
        cluster_cursor=engine.efficiency.cluster_cursor,
        proposal_cursor=engine.efficiency.proposal_cursor,
        correction_cursor=engine.efficiency.correction_cursor,
        custody_output_digest=engine.custody.output_digest,
        verification_output_digest=engine.verification.output_digest,
        efficiency_output_digest=engine.efficiency.output_digest,
        replay_identical=True,
    )


# ---------------------------------------------------------------------------
# The daily runner entry point
# ---------------------------------------------------------------------------


def run_daily_efficiency(
    *,
    ledger: MaintenanceLedger,
    previous_boundary: UtcTime | datetime,
    candidate_boundary: UtcTime | datetime,
    environment: EnvironmentId | str | None,
    generated_at: UtcTime | datetime,
    occurrence_fence: OccurrenceFence,
    fence_check: Callable[[OccurrenceFence], bool],
    analysis: DailyAnalysisStage | None = None,
    corrections: Sequence[DailyEfficiencyCorrection] = (),
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
    policy_version: str = DEFAULT_POLICY_VERSION,
    classifier: ClassifierInfo | None = None,
    budget: OccurrenceBudget | None = None,
    watermark: Watermark | datetime | None = None,
    observed_at: UtcTime | datetime | None = None,
    event_time: UtcTime | datetime | None = None,
) -> DailyEfficiencyRunResult:
    """Run the WHOLE daily efficiency cycle and prove terminal closure.

    Deterministic order, all against ONE owned ``(ledger, engine)`` pair:

    1. **Replay-first.**  Scan the journal once (read-only) and replay every
       committed Maintenance event into a fresh engine with the journal
       sequences as cursors.  A torn maintenance-shaped record is a typed
       NON-APPENDING ``incoherent_read`` — nothing is emitted from a torn
       journal.
    2. **Closure probe.**  :func:`derive_daily_closure` proves the daily
       window from committed operational report evidence; a non-closing
       probe returns the typed NON-APPENDING result (empty chain, coverage
       gap, cross-environment break) — the boundary never advances on
       unproven coverage (SD2).
    3. **Single synthesis.**  The injected analysis stage (default:
       report-only) fans out over the proven receipt; the single synthesizer
       binds the canonical bundle.
    4. **Fenced exactly-once emission.**  The bundle plus any caller-derived
       keyed corrections emit through :func:`emit_daily_events` — the ONE
       canonical writer — under the caller's live T2.1 fence.  The SD3
       prior-proposal-key lookup is DERIVED from the replayed journal
       (journal-authoritative; the forbidden ``None``/always-never-seen
       fallbacks do not exist here).  Exact reruns join as
       ``already_present``; divergent input raises the canonical conflict
       and writes nothing.  A fence lost at any boundary maps to the typed
       NON-APPENDING ``fence_lost`` result naming the boundary.
    5. **Closure proof.**  A fresh journal read must contain every committed
       sequence, stream cursors must equal the latest committed sequence of
       their kind, and a fresh replay must reproduce byte-identical state —
       then the validated :class:`DailyClosureReceipt` is returned
       (``closed_appended`` when something new committed, ``closed_joined``
       on an exact rerun).

    Envelope inputs (``generated_at``, classifier/policy versions, budget)
    are part of the digest-bound event bytes: a rerun is an exact join only
    when they are identical; ANY divergence is divergent input and fails
    closed.  ``watermark`` defaults to the proven ``closed_boundary`` and
    ``observed_at``/``event_time`` to ``generated_at`` (deterministic).
    """
    # 1. Replay-first: own the journal before any decision.
    scan = _scan_journal(ledger)
    if scan.torn is not None:
        return DailyEfficiencyRunResult(
            status=DailyRunStatus.NON_CLOSING,
            closure=DailyClosureResult(
                outcome=DailyClosureOutcome.INCOHERENT_READ,
                reason=scan.torn,
            ),
            reason=scan.torn,
        )
    engine = _replayed_engine(scan)

    # 2. Closure probe over the replayed operational evidence.
    closure = derive_daily_closure(
        events=scan.operational_reports(),
        previous_boundary=previous_boundary,
        candidate_boundary=candidate_boundary,
        environment=environment,
    )
    if not closure.closed or closure.receipt is None:
        return DailyEfficiencyRunResult(
            status=DailyRunStatus.NON_CLOSING,
            closure=closure,
            reason=closure.reason,
        )

    # 3. Single synthesizer over the injected analysis stage.
    stage = analysis if analysis is not None else _report_only_analysis
    bundle = synthesize_daily_report(
        closure.receipt,
        stage(closure.receipt),
        generated_at=generated_at,
        classifier_version=classifier_version,
        policy_version=policy_version,
    )

    # 4. Fenced exactly-once emission through the ONE canonical writer.
    try:
        emission = emit_daily_events(
            bundle,
            ledger=ledger,
            engine=engine,
            observed_at=_coerce_utc(observed_at or generated_at),
            event_time=_coerce_utc(event_time or generated_at),
            watermark=Watermark(
                _coerce_utc(watermark or closure.receipt.closed_boundary).root
            ),
            classifier=classifier
            or ClassifierInfo(classifier_version=classifier_version, confidence=1.0),
            budget=budget or OccurrenceBudget(max_attempts=1),
            prior_key_lookup=scan.committed_proposal_keys().__contains__,
            corrections=corrections,
            occurrence_fence=occurrence_fence,
            fence_check=fence_check,
        )
    except OccurrenceFenceLostError as exc:
        match = _FENCE_BOUNDARY_RE.search(str(exc))
        return DailyEfficiencyRunResult(
            status=DailyRunStatus.FENCE_LOST,
            closure=closure,
            reason=str(exc),
            fence_boundary=match.group(1) if match else "unknown",
        )
    # MaintenanceEventConflict (divergent input) and DailyCorrectionTargetError
    # (keyed pre-flight) propagate unchanged: fail closed, nothing written.

    # 5. Closure proof and typed receipt.
    receipt = _prove_closure(
        ledger=ledger,
        engine=engine,
        emission=emission,
        closure=closure,
        fence=occurrence_fence,
    )
    appended = any(
        record.outcome is DailyEmissionOutcome.APPENDED for record in emission.records
    )
    return DailyEfficiencyRunResult(
        status=DailyRunStatus.CLOSED_APPENDED
        if appended
        else DailyRunStatus.CLOSED_JOINED,
        closure=closure,
        receipt=receipt,
    )


__all__ = [
    "DAILY_EFFICIENCY_CONTRACT_ID",
    "CommittedDailyRecord",
    "DailyAnalysisOutput",
    "DailyAnalysisStage",
    "DailyClosureOutcome",
    "DailyClosureReceipt",
    "DailyClosureResult",
    "DailyEfficiencyRunResult",
    "DailyReplayMismatchError",
    "DailyRunStatus",
    "JournalReplay",
    "DEFAULT_CLASSIFIER_VERSION",
    "DEFAULT_POLICY_VERSION",
    "derive_daily_closure",
    "derive_report_refs",
    "run_daily_efficiency",
]
