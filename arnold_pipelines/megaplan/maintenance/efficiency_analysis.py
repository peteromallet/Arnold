"""M5 pure dwell, loop, handoff, and repair-pattern analyzers (Steps 13-15).

This module implements the deterministic, store-free analyzers for the
finding families defined in Step 3 (T3):

* :func:`analyze_gate_dwell` / :func:`analyze_finalize_publication_dwell` /
  :func:`analyze_review_dwell` / :func:`analyze_dwell` — the dwell family
  (Step 13 / T13): gate, finalize-publication, and review dwell legs with
  the shared exclusion model (SC14) that keeps legitimate depth,
  exploration, configured backoff, human gates, and productive proof/review
  OUT of avoidable-impact findings while retaining their context;
* :func:`analyze_equivalent_failures` — equivalent stage failures with the
  same normalized problem signature become ``revision_loop`` findings;
* :func:`analyze_retry_loops` — repeated calls of the same operation
  (normalized operation key) become ``retry_loop`` findings;
* :func:`analyze_duplicate_calls` — exact duplicate calls (normalized
  duplicate key) become ``duplicate_call`` findings;
* :func:`analyze_no_progress` — calls with an exact no-progress delta become
  ``no_progress`` findings;
* :func:`analyze_loops` — the combined deterministic loop entry point;
* :func:`analyze_idle_handoffs` — idle handoff legs become
  ``idle_handoff`` findings that reference active custody WITHOUT claiming
  or altering it (Step 15 / T15, SC16);
* :func:`analyze_repair_patterns` — recurring repair patterns (same
  affected contract + normalized repair signature) become typed
  ``repair_pattern`` findings reporting recurrence windows and
  custody-reference-only active custody (Step 15 / T15, SC16);
* :func:`aggregate_exclusion_accounting` — the typed exclusion accounting
  API (SC16) that aggregates excluded context and proven avoidable seconds
  across the dwell/loop/handoff/repair-pattern families into conservative
  avoidable-impact bounds with explicit lower/upper/unknown states.

Design rules (locked Step 6 / Step 13-14 policy):

* **Problem signatures are separate from occurrence IDs.**  Finding IDs are
  derived from the normalized *problem signature* (stage + failure /
  operation / duplicate signature + classifier version), never from
  ``call_id`` occurrence identities.  The same problem across different
  occurrences derives the SAME finding identity; occurrences are attached
  only as exact source references.
* **Impacts are counted only against exact accepted outcomes.**  Economics
  carry ``accepted_outcome_count`` equal to the number of distinct exact
  accepted outcomes the grouped calls are attributed to, and per-accepted
  time is only computed over that exact denominator (SC15).  Every T3
  finding anchors to an exact accepted resolution, so a loop group whose
  calls carry no accepted-resolution refs yields NO finding (conservative:
  unattributed patterns stay context and never produce an inferred-impact
  finding).
* **Dwell avoidable classification is conservative (T12).**  A dwell leg is
  flagged only when the T12 conservative predicate proves it above the p95
  upper bound AND (2x median upper bound OR the declared SLO); a
  right-censored leg is flagged only when its known lower bound already
  proves the predicate — never coerced to completion or zero.
* **Every finding anchors to an exact accepted resolution and exact source
  references** (T3 :class:`FindingReferences` contract): the reference
  bundle is the sorted union of the grouped calls' accepted-resolution and
  source refs, with exact-when-present gate/backoff, censoring, and active
  custody refs.
* **Censoring is preserved.**  Calls marked ``censored`` contribute their
  ``censoring_refs`` to the finding and are never coerced to completion.
* **Determinism.**  All grouping, reference unions, and output ordering are
  input-order independent; results are sorted by finding ID.

Inputs are pure :class:`NormalizedCall` / :class:`NormalizedDwellObservation`
facts (the Step 11 normalization contract); this module never constructs or
mutates an owner store.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance.efficiency_baselines import (
    conservative_dwell_predicate,
)
from arnold_pipelines.megaplan.maintenance.efficiency_contracts import (
    DAILY_EFFICIENCY_CONTRACT_ID,
    AcceptedOutcomeEconomics,
    DwellFinding,
    DwellFindingKind,
    FindingReferences,
    IdleHandoffFinding,
    LoopFinding,
    LoopFindingKind,
    QuantileBounds,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    canonical_json,
)

#: Default classifier version used for finding-ID derivation when the caller
#: does not pin one (classifier-version separation is part of the signature).
DEFAULT_CLASSIFIER_VERSION: str = "cls-v1"


def _sha256_hex(material: str) -> str:
    """Canonical sha256 hex digest of *material*."""
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


def _union_refs(groups: Sequence[Sequence[OwnerRef]]) -> tuple[OwnerRef, ...]:
    """Sorted union of reference groups (input-order independent)."""
    return _sort_refs({ref for group in groups for ref in group})


class CallOutcome(str, Enum):
    """Closed outcome of one normalized call (never coerced)."""

    FAILED = "failed"
    ACCEPTED = "accepted"


class NormalizedCall(BaseModel):
    """One normalized call/attempt fact (Step 11 shape, consumed by Step 14).

    ``call_id`` is the operational occurrence identity — it is NEVER part of
    a problem signature or finding ID.  ``failure_signature`` /
    ``operation_key`` / ``duplicate_key`` are normalized non-content problem
    signatures (empty when the call has none).  ``accepted_outcome_id`` pins
    the exact accepted outcome the call is attributed to (the impact
    denominator basis); when present, ``accepted_resolution_refs`` must
    carry the exact resolution anchors (T3 contract).  A completed call may
    have an exact measure or an unknown measure.  A censored call carries
    only an explicit lower bound and is never coerced to completion.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    call_id: StrictStr
    stage: StrictStr
    outcome: CallOutcome
    failure_signature: StrictStr | None = None
    operation_key: StrictStr | None = None
    duplicate_key: StrictStr | None = None
    accepted_outcome_id: StrictStr | None = None
    started_at: UtcTime | None = None
    ended_at: UtcTime | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    no_progress_delta_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    #: Exact source evidence refs for this call (mandatory: normalized facts
    #: always carry immutable source references).
    refs: tuple[OwnerRef, ...] = ()
    #: Exact accepted-resolution anchors (mandatory when attributed).
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    censoring_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()

    @field_validator("call_id", "stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("call_id and stage must be non-empty strings")
        return value

    @field_validator(
        "failure_signature", "operation_key", "duplicate_key", "accepted_outcome_id"
    )
    @classmethod
    def _validate_signatures(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("normalized signatures must be non-empty strings when present")
        return value

    @field_validator("refs", "accepted_resolution_refs", "gate_backoff_refs",
                     "censoring_refs", "active_custody_refs")
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_attribution(self) -> NormalizedCall:
        if not self.refs:
            raise ValueError(
                "normalized calls require at least one exact source ref"
            )
        if self.censored:
            if (
                self.elapsed_seconds is not None
                or self.no_progress_delta_seconds is not None
            ):
                raise ValueError(
                    "censored calls cannot carry an exact elapsed or "
                    "no_progress_delta_seconds measure"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored calls require an explicit lower_bound_seconds"
                )
        elif self.lower_bound_seconds is not None:
            raise ValueError(
                "completed calls cannot carry a lower_bound_seconds"
            )
        if self.accepted_outcome_id is not None and not self.accepted_resolution_refs:
            raise ValueError(
                "calls attributed to an exact accepted outcome require exact "
                "accepted_resolution_refs"
            )
        return self


def derive_loop_problem_id(
    kind: LoopFindingKind,
    *,
    stage: str,
    problem_signature: str,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> str:
    """Deterministic finding ID from the normalized PROBLEM signature.

    ``efficiency_loop|{kind}|{sha256(stage|signature|classifier_version)}``
    over the canonical problem signature — never over occurrence/call IDs.
    The same problem across different occurrences derives the same finding
    identity, and classifier-version separation is part of the material.
    """
    if not stage or not problem_signature:
        raise ValueError("loop problem IDs require a stage and a problem signature")
    material = canonical_json(
        {
            "family": "loop",
            "kind": kind.value,
            "stage": stage,
            "problem_signature": problem_signature,
            "classifier_version": classifier_version,
        }
    )
    return f"efficiency_loop|{kind.value}|{_sha256_hex(material)}"


def _loop_span_seconds(calls: Sequence[NormalizedCall]) -> float | None:
    """Span (max end - min start) of the grouped calls when fully timestamped."""
    started = [call.started_at.root for call in calls if call.started_at is not None]
    ended = [call.ended_at.root for call in calls if call.ended_at is not None]
    if not started or not ended:
        return None
    return max(ended).timestamp() - min(started).timestamp()


def _call_time_seconds(call: NormalizedCall) -> float | None:
    """Exact completed time measure of one call.

    Censored calls retain their explicit lower bound for context, but that
    bound is never used as a completed numeric duration.
    """
    if call.censored:
        return None
    if call.elapsed_seconds is not None:
        return call.elapsed_seconds
    return call.no_progress_delta_seconds


def _exact_accepted_outcome_economics(
    calls: Sequence[NormalizedCall],
) -> AcceptedOutcomeEconomics | None:
    """Impact economics over the EXACT accepted-outcome denominator (SC15).

    The denominator is the number of distinct exact accepted outcomes the
    grouped calls are attributed to; per-accepted time is total exact time
    over that denominator.  Returns ``None`` when no call carries an exact
    accepted-outcome attribution — a missing denominator is never inferred
    and no raw-total claim is emitted without it.
    """
    attributed = [call for call in calls if call.accepted_outcome_id is not None]
    if not attributed:
        return None
    denominator = len({call.accepted_outcome_id for call in attributed})
    times = [_call_time_seconds(call) for call in attributed]
    time_per_accepted = (
        round(sum(value for value in times if value is not None) / denominator, 6)
        if all(value is not None for value in times)
        else None
    )
    return AcceptedOutcomeEconomics(
        accepted_outcome_count=denominator,
        time_seconds_per_accepted=time_per_accepted,
    )


def _build_loop_finding(
    kind: LoopFindingKind,
    *,
    stage: str,
    problem_signature: str,
    calls: Sequence[NormalizedCall],
    classifier_version: str,
    no_progress_delta_seconds: float | None = None,
) -> LoopFinding | None:
    """Build one typed loop finding from its grouped calls, or ``None``.

    The finding ID comes from the problem signature (never occurrence IDs);
    the reference bundle is the sorted union of the calls' exact
    accepted-resolution, source, gate/backoff, censoring, and active-custody
    refs; economics are the exact accepted-outcome denominator impact.

    The T3 contract anchors EVERY finding to an exact accepted resolution,
    so a group whose calls carry no accepted-resolution refs yields ``None``
    (conservative: unattributed loop patterns stay context and never produce
    an inferred-impact finding).
    """
    accepted_resolution_refs = _union_refs(
        [call.accepted_resolution_refs for call in calls]
    )
    if not accepted_resolution_refs:
        return None
    loop_span = _loop_span_seconds(calls)
    return LoopFinding(
        finding_id=derive_loop_problem_id(
            kind, stage=stage, problem_signature=problem_signature,
            classifier_version=classifier_version,
        ),
        references=FindingReferences(
            accepted_resolution_refs=accepted_resolution_refs,
            active_custody_refs=_union_refs(
                [call.active_custody_refs for call in calls]
            ),
            source_refs=_union_refs([call.refs for call in calls]),
            gate_backoff_refs=_union_refs([call.gate_backoff_refs for call in calls]),
            censoring_refs=_union_refs([call.censoring_refs for call in calls]),
        ),
        economics=_exact_accepted_outcome_economics(calls),
        kind=kind,
        repeated_stage=stage,
        attempt_count=len(calls),
        loop_span_seconds=loop_span,
        no_progress_delta_seconds=no_progress_delta_seconds,
    )


def _group_by(
    calls: Sequence[NormalizedCall],
    key_of: Callable[[NormalizedCall], str | None],
) -> dict[tuple[str, str], list[NormalizedCall]]:
    """Group calls by ``(stage, normalized signature)`` in input order."""
    groups: dict[tuple[str, str], list[NormalizedCall]] = {}
    for call in calls:
        signature = key_of(call)
        if signature is None:
            continue
        groups.setdefault((call.stage, signature), []).append(call)
    return groups


def analyze_equivalent_failures(
    calls: Sequence[NormalizedCall],
    *,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> tuple[LoopFinding, ...]:
    """Equivalent-failure analyzer: repeated identical failed signatures.

    Failed calls carrying the same normalized ``failure_signature`` at the
    same stage, with at least 2 attempts, become one ``revision_loop``
    finding whose ID is derived from the signature — never from call IDs.
    """
    failed = [call for call in calls if call.outcome is CallOutcome.FAILED]
    findings: list[LoopFinding] = []
    for (stage, signature), group in _group_by(failed, lambda call: call.failure_signature).items():
        if len(group) < 2:
            continue
        finding = _build_loop_finding(
            LoopFindingKind.REVISION_LOOP,
            stage=stage,
            problem_signature=signature,
            calls=group,
            classifier_version=classifier_version,
        )
        if finding is not None:
            findings.append(finding)
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))


def analyze_retry_loops(
    calls: Sequence[NormalizedCall],
    *,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> tuple[LoopFinding, ...]:
    """Retry-loop analyzer: repeated calls of the same normalized operation.

    Calls sharing the same ``operation_key`` at the same stage, with at
    least 2 attempts, become one ``retry_loop`` finding keyed by the
    operation signature.
    """
    findings: list[LoopFinding] = []
    for (stage, signature), group in _group_by(calls, lambda call: call.operation_key).items():
        if len(group) < 2:
            continue
        finding = _build_loop_finding(
            LoopFindingKind.RETRY_LOOP,
            stage=stage,
            problem_signature=signature,
            calls=group,
            classifier_version=classifier_version,
        )
        if finding is not None:
            findings.append(finding)
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))


def analyze_duplicate_calls(
    calls: Sequence[NormalizedCall],
    *,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> tuple[LoopFinding, ...]:
    """Duplicate-call analyzer: exact duplicates of the same normalized call.

    Calls sharing the same ``duplicate_key`` at the same stage, with at
    least 2 attempts, become one ``duplicate_call`` finding keyed by the
    duplicate signature.  Impact economics are counted ONLY against exact
    accepted outcomes (SC15): the denominator is the number of distinct
    accepted outcomes the duplicated calls are attributed to, and a group
    whose calls carry no exact accepted-resolution anchor yields no finding
    at all (a missing denominator is never inferred).
    """
    findings: list[LoopFinding] = []
    for (stage, signature), group in _group_by(calls, lambda call: call.duplicate_key).items():
        if len(group) < 2:
            continue
        finding = _build_loop_finding(
            LoopFindingKind.DUPLICATE_CALL,
            stage=stage,
            problem_signature=signature,
            calls=group,
            classifier_version=classifier_version,
        )
        if finding is not None:
            findings.append(finding)
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))


def _no_progress_signature(call: NormalizedCall) -> str | None:
    """Problem signature for no-progress grouping, or the call ID fallback.

    Prefers the normalized problem signatures (failure/operation/duplicate)
    so recurring no-progress calls share one finding; a call with no
    signature at all is its own group keyed by its occurrence ID (there is
    no problem signature to separate).
    """
    for signature in (call.failure_signature, call.operation_key, call.duplicate_key):
        if signature is not None:
            return signature
    return call.call_id


def analyze_no_progress(
    calls: Sequence[NormalizedCall],
    *,
    min_delta_seconds: float = 0.0,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> tuple[LoopFinding, ...]:
    """No-progress analyzer: exact no-progress deltas per problem signature.

    Calls carrying an exact ``no_progress_delta_seconds`` strictly above
    *min_delta_seconds* are grouped by ``(stage, problem signature)``; the
    finding's ``no_progress_delta_seconds`` is the explicit total of the
    group (never coerced from missing deltas).  Impact economics are counted
    only against exact accepted outcomes (SC15); a group without any exact
    accepted-resolution anchor yields no finding at all.
    """
    candidates = [
        call
        for call in calls
        if call.no_progress_delta_seconds is not None
        and call.no_progress_delta_seconds > min_delta_seconds
    ]
    findings: list[LoopFinding] = []
    for (stage, signature), group in _group_by(candidates, _no_progress_signature).items():
        total_delta = sum(
            float(call.no_progress_delta_seconds)
            for call in group
            if call.no_progress_delta_seconds is not None
        )
        finding = _build_loop_finding(
            LoopFindingKind.NO_PROGRESS,
            stage=stage,
            problem_signature=signature,
            calls=group,
            classifier_version=classifier_version,
            no_progress_delta_seconds=total_delta,
        )
        if finding is not None:
            findings.append(finding)
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))


def analyze_loops(
    calls: Sequence[NormalizedCall],
    *,
    min_no_progress_delta_seconds: float = 0.0,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> tuple[LoopFinding, ...]:
    """Combined deterministic loop-family analyzer (Step 14 entry point).

    Runs the equivalent-failure, retry-loop, duplicate-call, and no-progress
    analyzers over the same normalized calls and returns the findings sorted
    by finding ID.  Problem signatures stay separate from occurrence IDs,
    and every impact is counted against exact accepted-outcome denominators
    only.
    """
    findings = (
        analyze_equivalent_failures(calls, classifier_version=classifier_version)
        + analyze_retry_loops(calls, classifier_version=classifier_version)
        + analyze_duplicate_calls(calls, classifier_version=classifier_version)
        + analyze_no_progress(
            calls,
            min_delta_seconds=min_no_progress_delta_seconds,
            classifier_version=classifier_version,
        )
    )
    return tuple(sorted(findings, key=lambda finding: finding.finding_id))


# ---------------------------------------------------------------------------
# Step 13 / T13: dwell-family analyzers — gate, finalize-publication, review
# ---------------------------------------------------------------------------
# Pure per-family dwell analyzers over normalized dwell legs.  Every finding
# attaches the exact accepted resolution, active-custody, source,
# gate/backoff, and censoring references (T3 :class:`FindingReferences`).
# The shared exclusion model (SC14) keeps legitimate high-depth work,
# deliberate exploration, configured backoff, known human gates, and
# productive proof/review OUT of the avoidable-impact findings while the
# elapsed/cost context is still reported as a :class:`DwellContextEntry`.
# Avoidable classification calls the T12 conservative bound predicate
# (:func:`conservative_dwell_predicate`) so a dwell is flagged only when the
# conservative p95 upper bound and the 2x-median/SLO disjunction are proven;
# a right-censored leg is flagged only when its known lower bound already
# proves the predicate (never coerced to completion or zero).


class DwellExclusionReason(str, Enum):
    """Closed typed reasons a dwell leg is excluded from avoidable impact.

    Legitimate high-depth work, deliberate exploration, configured backoff,
    known human gates, and productive proof/review are NEVER counted as
    avoidable dwell; their elapsed context is retained instead.
    """

    LEGITIMATE_DEPTH = "legitimate_depth"
    EXPLORATION = "exploration"
    CONFIGURED_BACKOFF = "configured_backoff"
    HUMAN_GATE = "human_gate"
    PRODUCTIVE = "productive"


class NormalizedDwellObservation(BaseModel):
    """One normalized gate/finalize-publication/review dwell leg (Step 13).

    A **completed** leg carries its exact ``elapsed_seconds``; a
    **censored** leg carries no completion duration and an explicit
    ``lower_bound_seconds`` (never coerced to completion or zero).  The
    exclusion flags are the machine-checkable basis of the shared exclusion
    model: any flag set requires the matching typed ``excluded_reason``, and
    an excluded leg is reported as context only (SC14).  Every leg carries
    exact source refs and, when attributed, exact accepted-resolution refs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    kind: DwellFindingKind
    stage: StrictStr
    started_at: UtcTime | None = None
    ended_at: UtcTime | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    slo_seconds: float | None = Field(default=None, ge=0)
    #: Typed exclusion reason (SC14); ``None`` when the leg is avoidable
    #: eligible.  Present exactly when at least one exclusion flag is set.
    excluded_reason: DwellExclusionReason | None = None
    deep_work: bool = False
    exploration: bool = False
    configured_backoff: bool = False
    human_gate: bool = False
    productive: bool = False
    accepted_outcome_id: StrictStr | None = None
    #: Exact source evidence refs for this leg (mandatory).
    refs: tuple[OwnerRef, ...] = ()
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    censoring_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id", "stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("observation_id and stage must be non-empty strings")
        return value

    @field_validator("accepted_outcome_id")
    @classmethod
    def _validate_outcome(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("accepted_outcome_id must be a non-empty string when present")
        return value

    @field_validator("refs", "accepted_resolution_refs", "gate_backoff_refs",
                     "censoring_refs", "active_custody_refs")
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_leg(self) -> NormalizedDwellObservation:
        if not self.refs:
            raise ValueError(
                "normalized dwell legs require at least one exact source ref"
            )
        if self.censored:
            if self.elapsed_seconds is not None:
                raise ValueError(
                    "censored dwell legs cannot carry a completion elapsed_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored dwell legs require an explicit lower_bound_seconds"
                )
        else:
            if self.elapsed_seconds is None:
                raise ValueError(
                    "completed dwell legs require an exact elapsed_seconds"
                )
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed dwell legs cannot carry a lower_bound_seconds"
                )
        if self.accepted_outcome_id is not None and not self.accepted_resolution_refs:
            raise ValueError(
                "legs attributed to an exact accepted outcome require exact "
                "accepted_resolution_refs"
            )
        flags = (
            self.deep_work,
            self.exploration,
            self.configured_backoff,
            self.human_gate,
            self.productive,
        )
        if any(flags) != (self.excluded_reason is not None):
            raise ValueError(
                "excluded_reason must be present exactly when an exclusion "
                "flag (deep_work/exploration/configured_backoff/human_gate/"
                "productive) is set"
            )
        return self

    @property
    def lower_bound(self) -> float | None:
        """Exact elapsed (completed) or explicit lower bound (censored)."""
        if self.censored:
            return self.lower_bound_seconds
        return self.elapsed_seconds


class DwellContextEntry(BaseModel):
    """One dwell leg's retained context WITHOUT any avoidable-impact claim.

    Excluded legs (legitimate depth / exploration / backoff / human gate /
    productive proof) and unattributed legs are reported here so elapsed
    context is never lost (SC14), while the typed finding stream stays
    strictly avoidable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    kind: DwellFindingKind
    stage: StrictStr
    elapsed_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    excluded_reason: DwellExclusionReason | None = None
    context_reason: StrictStr | None = None
    refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id", "stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("observation_id and stage must be non-empty strings")
        return value

    @field_validator("refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_context(self) -> DwellContextEntry:
        if self.censored:
            if self.elapsed_seconds is not None:
                raise ValueError(
                    "censored context entries cannot carry a completion elapsed_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored context entries require an explicit lower_bound_seconds"
                )
        else:
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed context entries cannot carry a lower_bound_seconds"
                )
        if self.excluded_reason is None and self.context_reason is None:
            raise ValueError(
                "context entries require a typed excluded_reason or a "
                "context_reason"
            )
        return self


class DwellAnalysisResult(BaseModel):
    """Output of one dwell-family analyzer (findings + retained context)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[DwellFinding, ...] = ()
    context: tuple[DwellContextEntry, ...] = ()


def derive_dwell_finding_id(
    kind: DwellFindingKind,
    *,
    stage: str,
    observation_identity: str,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> str:
    """Deterministic dwell finding ID from the normalized leg identity.

    ``efficiency_dwell|{kind}|{sha256(stage|observation_identity|classifier_version)}``
    over the normalized observation identity and classifier version — never
    over raw owner occurrence coordinates.
    """
    if not stage or not observation_identity:
        raise ValueError("dwell finding IDs require a stage and observation identity")
    material = canonical_json(
        {
            "family": "dwell",
            "kind": kind.value,
            "stage": stage,
            "observation_identity": observation_identity,
            "classifier_version": classifier_version,
        }
    )
    return f"efficiency_dwell|{kind.value}|{_sha256_hex(material)}"


def _dwell_economics(
    observation: NormalizedDwellObservation,
    value_seconds: float,
) -> AcceptedOutcomeEconomics | None:
    """Exact accepted-outcome economics for a PROVEN dwell leg.

    Returns ``None`` when the leg carries no exact accepted-outcome
    attribution (a missing denominator is never inferred); otherwise the
    per-accepted time is the proven value over the single exact accepted
    outcome the leg is attributed to.
    """
    if observation.accepted_outcome_id is None:
        return None
    return AcceptedOutcomeEconomics(
        accepted_outcome_count=1,
        time_seconds_per_accepted=round(value_seconds, 6),
    )


def _classify_dwell_observation(
    observation: NormalizedDwellObservation,
    *,
    p95: QuantileBounds | None,
    median: QuantileBounds | None,
    slo_seconds: float | None,
    classifier_version: str,
) -> DwellFinding | DwellContextEntry:
    """Shared exclusion + conservative classification of one dwell leg.

    * excluded legs (SC14) become :class:`DwellContextEntry` (context only);
    * legs without an exact accepted-resolution anchor become context
      (every T3 finding requires an exact accepted resolution);
    * avoidable-eligible legs call the T12 conservative predicate: the
      finding's flags are the predicate outcome and economics are attached
      only when the dwell predicate is proven.
    """
    if observation.excluded_reason is not None:
        return DwellContextEntry(
            observation_id=observation.observation_id,
            kind=observation.kind,
            stage=observation.stage,
            elapsed_seconds=observation.elapsed_seconds,
            censored=observation.censored,
            lower_bound_seconds=observation.lower_bound_seconds,
            excluded_reason=observation.excluded_reason,
            context_reason=(
                f"excluded from avoidable-impact totals: "
                f"{observation.excluded_reason.value}"
            ),
            refs=observation.refs,
        )
    if not observation.accepted_resolution_refs:
        return DwellContextEntry(
            observation_id=observation.observation_id,
            kind=observation.kind,
            stage=observation.stage,
            elapsed_seconds=observation.elapsed_seconds,
            censored=observation.censored,
            lower_bound_seconds=observation.lower_bound_seconds,
            context_reason="no exact accepted-resolution anchor",
            refs=observation.refs,
        )

    value_seconds = observation.lower_bound
    effective_slo = (
        observation.slo_seconds
        if observation.slo_seconds is not None
        else slo_seconds
    )
    if p95 is not None and median is not None and value_seconds is not None:
        predicate = conservative_dwell_predicate(
            value_seconds,
            censored=observation.censored,
            p95=p95,
            median=median,
            slo_seconds=effective_slo,
        )
        above_p95 = predicate.above_p95
        above_2x_median = predicate.above_2x_median
        above_slo = predicate.above_slo
        dwell = predicate.dwell
    else:
        above_p95 = False
        above_2x_median = False
        above_slo = False
        dwell = False

    economics = _dwell_economics(observation, value_seconds) if dwell else None
    return DwellFinding(
        finding_id=derive_dwell_finding_id(
            observation.kind,
            stage=observation.stage,
            observation_identity=observation.observation_id,
            classifier_version=classifier_version,
        ),
        references=FindingReferences(
            accepted_resolution_refs=observation.accepted_resolution_refs,
            active_custody_refs=observation.active_custody_refs,
            source_refs=observation.refs,
            gate_backoff_refs=observation.gate_backoff_refs,
            censoring_refs=observation.censoring_refs,
        ),
        economics=economics,
        kind=observation.kind,
        duration_seconds=observation.elapsed_seconds,
        censored=observation.censored,
        lower_bound_seconds=observation.lower_bound_seconds,
        slo_seconds=effective_slo,
        above_p95=above_p95,
        above_2x_median=above_2x_median,
        above_slo=above_slo,
    )


def _analyze_dwell_family(
    kind: DwellFindingKind,
    observations: Sequence[NormalizedDwellObservation],
    *,
    p95: QuantileBounds | None,
    median: QuantileBounds | None,
    slo_seconds: float | None,
    classifier_version: str,
) -> DwellAnalysisResult:
    family = [observation for observation in observations if observation.kind is kind]
    findings: list[DwellFinding] = []
    context: list[DwellContextEntry] = []
    for observation in family:
        result = _classify_dwell_observation(
            observation,
            p95=p95,
            median=median,
            slo_seconds=slo_seconds,
            classifier_version=classifier_version,
        )
        if isinstance(result, DwellFinding):
            findings.append(result)
        else:
            context.append(result)
    return DwellAnalysisResult(
        findings=tuple(sorted(findings, key=lambda finding: finding.finding_id)),
        context=tuple(
            sorted(
                context,
                key=lambda entry: (entry.observation_id, entry.kind.value),
            )
        ),
    )


def analyze_gate_dwell(
    observations: Sequence[NormalizedDwellObservation],
    *,
    p95: QuantileBounds | None = None,
    median: QuantileBounds | None = None,
    slo_seconds: float | None = None,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> DwellAnalysisResult:
    """Gate-dwell analyzer: avoidable time spent waiting at known gates.

    Applies the shared exclusion model (SC14): human-gated, backoff,
    exploration, depth, and productive legs stay context; avoidable legs are
    classified with the T12 conservative predicate.
    """
    return _analyze_dwell_family(
        DwellFindingKind.GATE,
        observations,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
        classifier_version=classifier_version,
    )


def analyze_finalize_publication_dwell(
    observations: Sequence[NormalizedDwellObservation],
    *,
    p95: QuantileBounds | None = None,
    median: QuantileBounds | None = None,
    slo_seconds: float | None = None,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> DwellAnalysisResult:
    """Finalize-publication dwell analyzer (the 79/84/176-minute gap family).

    Covers finalize-output publication gaps as completed or right-censored
    handoff dwell observations — never suggesting a WBC restart and never
    coercing a censored gap to completion or zero.
    """
    return _analyze_dwell_family(
        DwellFindingKind.FINALIZE_PUBLICATION,
        observations,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
        classifier_version=classifier_version,
    )


def analyze_review_dwell(
    observations: Sequence[NormalizedDwellObservation],
    *,
    p95: QuantileBounds | None = None,
    median: QuantileBounds | None = None,
    slo_seconds: float | None = None,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> DwellAnalysisResult:
    """Review-dwell analyzer: avoidable review wait, productive review excluded.

    Productive proof/review legs are reported as context only (SC14) while
    the avoidable review wait keeps its exact references and economics.
    """
    return _analyze_dwell_family(
        DwellFindingKind.REVIEW,
        observations,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
        classifier_version=classifier_version,
    )


def analyze_dwell(
    observations: Sequence[NormalizedDwellObservation],
    *,
    p95: QuantileBounds | None = None,
    median: QuantileBounds | None = None,
    slo_seconds: float | None = None,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> DwellAnalysisResult:
    """Combined deterministic dwell-family analyzer (Step 13 entry point).

    Runs the gate, finalize-publication, and review analyzers over the same
    normalized legs and returns findings sorted by finding ID plus the
    retained context entries sorted by observation ID.  Excluded legs never
    appear in the finding stream (SC14).
    """
    gate = analyze_gate_dwell(
        observations,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
        classifier_version=classifier_version,
    )
    finalize = analyze_finalize_publication_dwell(
        observations,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
        classifier_version=classifier_version,
    )
    review = analyze_review_dwell(
        observations,
        p95=p95,
        median=median,
        slo_seconds=slo_seconds,
        classifier_version=classifier_version,
    )
    return DwellAnalysisResult(
        findings=tuple(
            sorted(
                (*gate.findings, *finalize.findings, *review.findings),
                key=lambda finding: finding.finding_id,
            )
        ),
        context=tuple(
            sorted(
                (*gate.context, *finalize.context, *review.context),
                key=lambda entry: (entry.observation_id, entry.kind.value),
            )
        ),
    )


# ---------------------------------------------------------------------------
# Step 15 / T15: idle-handoff and repair-pattern analyzers + exclusion
# accounting (SC16)
# ---------------------------------------------------------------------------
# Pure per-family analyzers over normalized handoff/repair-pattern facts.
#
# * Idle handoffs: a normalized handoff leg (from_stage -> to_stage with no
#   progress) becomes an :class:`~arnold_pipelines.megaplan.maintenance.
#   efficiency_contracts.IdleHandoffFinding` when it is completed,
#   attributed to an exact accepted resolution, and not excluded.  Excluded
#   (legitimate depth / exploration / backoff / human gate / productive),
#   unattributed, and censored legs stay context entries — a censored
#   handoff is never coerced to completion or zero.
# * Recurring repair patterns: occurrences sharing the same affected
#   contract and normalized repair signature, with at least 2 occurrences,
#   become one ``repair_pattern`` finding reporting recurrence windows and
#   recurrence counts.  Findings carry active custody ONLY as
#   reference/covariate refs and NEVER carry economics — repair patterns
#   report recurrence without any avoidable-impact or custody claim (SC16).
# * Exclusion accounting (SC16): :func:`aggregate_exclusion_accounting`
#   aggregates the typed exclusions and the proven avoidable seconds across
#   the dwell/loop/handoff/repair-pattern families into conservative
#   avoidable-impact bounds with explicit lower/upper/unknown states:
#   censored or missing measures make the upper bound ``None`` (unknown),
#   excluded context is retained with its typed reason and never counted as
#   avoidable.


class NormalizedHandoffObservation(BaseModel):
    """One normalized idle handoff leg (Step 15 input, SC16).

    A **completed** handoff carries its exact ``idle_seconds``; a
    **censored** handoff carries no exact idle duration and an explicit
    ``lower_bound_seconds`` (never coerced to completion or zero).  The
    exclusion flags mirror the shared Step 13 exclusion model (SC14): any
    flag set requires the matching typed ``excluded_reason`` and an excluded
    handoff is reported as context only.  Every handoff carries exact source
    refs and, when attributed, exact accepted-resolution refs; active
    custody appears only as reference/covariate refs — never claimed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    from_stage: StrictStr
    to_stage: StrictStr
    handed_off_at: UtcTime | None = None
    idle_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    #: Typed exclusion reason (shared SC14 model); present exactly when an
    #: exclusion flag is set.
    excluded_reason: DwellExclusionReason | None = None
    deep_work: bool = False
    exploration: bool = False
    configured_backoff: bool = False
    human_gate: bool = False
    productive: bool = False
    accepted_outcome_id: StrictStr | None = None
    #: Exact source evidence refs for this handoff (mandatory).
    refs: tuple[OwnerRef, ...] = ()
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    censoring_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id", "from_stage", "to_stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("handoff identity/stages must be non-empty strings")
        return value

    @field_validator("accepted_outcome_id")
    @classmethod
    def _validate_outcome(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("accepted_outcome_id must be a non-empty string when present")
        return value

    @field_validator("refs", "accepted_resolution_refs", "gate_backoff_refs",
                     "censoring_refs", "active_custody_refs")
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_handoff(self) -> NormalizedHandoffObservation:
        if self.from_stage == self.to_stage:
            raise ValueError(
                "idle handoff stages must differ "
                f"({self.from_stage!r} == {self.to_stage!r})"
            )
        if not self.refs:
            raise ValueError(
                "normalized handoffs require at least one exact source ref"
            )
        if self.censored:
            if self.idle_seconds is not None:
                raise ValueError(
                    "censored handoffs cannot carry an exact idle_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored handoffs require an explicit lower_bound_seconds"
                )
        else:
            if self.idle_seconds is None:
                raise ValueError(
                    "completed handoffs require an exact idle_seconds"
                )
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed handoffs cannot carry a lower_bound_seconds"
                )
        if self.accepted_outcome_id is not None and not self.accepted_resolution_refs:
            raise ValueError(
                "handoffs attributed to an exact accepted outcome require exact "
                "accepted_resolution_refs"
            )
        flags = (
            self.deep_work,
            self.exploration,
            self.configured_backoff,
            self.human_gate,
            self.productive,
        )
        if any(flags) != (self.excluded_reason is not None):
            raise ValueError(
                "excluded_reason must be present exactly when an exclusion "
                "flag (deep_work/exploration/configured_backoff/human_gate/"
                "productive) is set"
            )
        return self

    @property
    def lower_bound(self) -> float | None:
        """Exact idle (completed) or explicit lower bound (censored)."""
        if self.censored:
            return self.lower_bound_seconds
        return self.idle_seconds


class HandoffContextEntry(BaseModel):
    """One handoff leg's retained context WITHOUT any avoidable-impact claim.

    Excluded handoffs (legitimate depth / exploration / backoff / human
    gate / productive), unattributed handoffs, and censored handoffs are
    reported here so context is never lost (SC16) while the typed finding
    stream stays strictly avoidable and claim-free.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    from_stage: StrictStr
    to_stage: StrictStr
    idle_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    lower_bound_seconds: float | None = Field(default=None, ge=0)
    excluded_reason: DwellExclusionReason | None = None
    context_reason: StrictStr | None = None
    refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id", "from_stage", "to_stage")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError("handoff context identity/stages must be non-empty strings")
        return value

    @field_validator("refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_context(self) -> HandoffContextEntry:
        if self.from_stage == self.to_stage:
            raise ValueError(
                "idle handoff context stages must differ "
                f"({self.from_stage!r} == {self.to_stage!r})"
            )
        if self.censored:
            if self.idle_seconds is not None:
                raise ValueError(
                    "censored handoff context cannot carry an exact idle_seconds"
                )
            if self.lower_bound_seconds is None:
                raise ValueError(
                    "censored handoff context requires an explicit "
                    "lower_bound_seconds"
                )
        else:
            if self.lower_bound_seconds is not None:
                raise ValueError(
                    "completed handoff context cannot carry a lower_bound_seconds"
                )
        if self.excluded_reason is None and self.context_reason is None:
            raise ValueError(
                "handoff context entries require a typed excluded_reason or a "
                "context_reason"
            )
        return self


class HandoffAnalysisResult(BaseModel):
    """Output of the idle-handoff analyzer (findings + retained context)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[IdleHandoffFinding, ...] = ()
    context: tuple[HandoffContextEntry, ...] = ()


def derive_handoff_finding_id(
    *,
    from_stage: str,
    to_stage: str,
    observation_identity: str,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> str:
    """Deterministic idle-handoff finding ID from the normalized leg identity.

    ``efficiency_handoff|{sha256(from_stage|to_stage|observation_identity|
    classifier_version)}`` — never over raw owner occurrence coordinates.
    """
    if not from_stage or not to_stage or not observation_identity:
        raise ValueError("handoff finding IDs require both stages and an observation identity")
    material = canonical_json(
        {
            "family": "idle_handoff",
            "from_stage": from_stage,
            "to_stage": to_stage,
            "observation_identity": observation_identity,
            "classifier_version": classifier_version,
        }
    )
    return f"efficiency_handoff|{_sha256_hex(material)}"


def analyze_idle_handoffs(
    observations: Sequence[NormalizedHandoffObservation],
    *,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> HandoffAnalysisResult:
    """Idle-handoff analyzer: pure, reference-only, claim-free (Step 15).

    * excluded handoffs (SC14 shared exclusion model) stay context;
    * handoffs without an exact accepted-resolution anchor stay context;
    * censored handoffs stay context with their explicit lower bound —
      never coerced to completion or zero;
    * completed, attributed, non-excluded handoffs become
      :class:`IdleHandoffFinding` payloads whose references carry the exact
      accepted-resolution, active-custody (reference-only), source,
      gate/backoff, and censoring refs.
    """
    findings: list[IdleHandoffFinding] = []
    context: list[HandoffContextEntry] = []
    for observation in observations:
        if observation.excluded_reason is not None:
            context.append(
                HandoffContextEntry(
                    observation_id=observation.observation_id,
                    from_stage=observation.from_stage,
                    to_stage=observation.to_stage,
                    idle_seconds=observation.idle_seconds,
                    censored=observation.censored,
                    lower_bound_seconds=observation.lower_bound_seconds,
                    excluded_reason=observation.excluded_reason,
                    context_reason=(
                        f"excluded from avoidable-impact totals: "
                        f"{observation.excluded_reason.value}"
                    ),
                    refs=observation.refs,
                )
            )
            continue
        if not observation.accepted_resolution_refs:
            context.append(
                HandoffContextEntry(
                    observation_id=observation.observation_id,
                    from_stage=observation.from_stage,
                    to_stage=observation.to_stage,
                    idle_seconds=observation.idle_seconds,
                    censored=observation.censored,
                    lower_bound_seconds=observation.lower_bound_seconds,
                    context_reason="no exact accepted-resolution anchor",
                    refs=observation.refs,
                )
            )
            continue
        if observation.censored:
            context.append(
                HandoffContextEntry(
                    observation_id=observation.observation_id,
                    from_stage=observation.from_stage,
                    to_stage=observation.to_stage,
                    censored=True,
                    lower_bound_seconds=observation.lower_bound_seconds,
                    context_reason=(
                        "censored handoff has no exact idle duration; "
                        "never coerced to completion or zero"
                    ),
                    refs=observation.refs,
                )
            )
            continue
        findings.append(
            IdleHandoffFinding(
                finding_id=derive_handoff_finding_id(
                    from_stage=observation.from_stage,
                    to_stage=observation.to_stage,
                    observation_identity=observation.observation_id,
                    classifier_version=classifier_version,
                ),
                references=FindingReferences(
                    accepted_resolution_refs=observation.accepted_resolution_refs,
                    active_custody_refs=observation.active_custody_refs,
                    source_refs=observation.refs,
                    gate_backoff_refs=observation.gate_backoff_refs,
                    censoring_refs=observation.censoring_refs,
                ),
                economics=AcceptedOutcomeEconomics(
                    accepted_outcome_count=1,
                    time_seconds_per_accepted=round(float(observation.idle_seconds), 6),
                ),
                from_stage=observation.from_stage,
                to_stage=observation.to_stage,
                idle_seconds=float(observation.idle_seconds),
                handed_off_at=observation.handed_off_at,
            )
        )
    return HandoffAnalysisResult(
        findings=tuple(sorted(findings, key=lambda finding: finding.finding_id)),
        context=tuple(
            sorted(
                context,
                key=lambda entry: (
                    entry.observation_id,
                    entry.from_stage,
                    entry.to_stage,
                ),
            )
        ),
    )


class NormalizedRepairPatternObservation(BaseModel):
    """One normalized recurring-repair occurrence (Step 15 input, SC16).

    ``repair_signature`` is the normalized non-content problem signature of
    the repair activity (never an occurrence ID); occurrences sharing the
    same ``(affected_contract, repair_signature)`` group into one repair
    pattern.  ``occurred_at`` timestamps bound the recurrence window;
    occurrences without timestamps contribute to the total count only (the
    7d/30d recurrence counts stay exact counts of timestamped occurrences —
    missing timestamps are never inferred).  Active custody appears only as
    reference/covariate refs — never claimed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    affected_contract: StrictStr
    repair_signature: StrictStr
    occurred_at: UtcTime | None = None
    accepted_outcome_id: StrictStr | None = None
    #: Exact source evidence refs for this occurrence (mandatory).
    refs: tuple[OwnerRef, ...] = ()
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    censoring_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id", "affected_contract", "repair_signature")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "repair-pattern observation identity/contract/signature must "
                "be non-empty strings"
            )
        return value

    @field_validator("accepted_outcome_id")
    @classmethod
    def _validate_outcome(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("accepted_outcome_id must be a non-empty string when present")
        return value

    @field_validator("refs", "accepted_resolution_refs", "gate_backoff_refs",
                     "censoring_refs", "active_custody_refs")
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_occurrence(self) -> NormalizedRepairPatternObservation:
        if not self.refs:
            raise ValueError(
                "normalized repair-pattern occurrences require at least one "
                "exact source ref"
            )
        if self.accepted_outcome_id is not None and not self.accepted_resolution_refs:
            raise ValueError(
                "occurrences attributed to an exact accepted outcome require "
                "exact accepted_resolution_refs"
            )
        return self


class RepairPatternFinding(BaseModel):
    """One recurring repair-pattern finding (Step 15, SC16).

    Reports the recurrence window and recurrence counts of a normalized
    repair pattern across exact occurrences.  It NEVER carries economics
    (``economics`` is always ``None`` — recurrence is reported without any
    avoidable-impact claim) and active custody appears ONLY as
    reference/covariate refs inside ``references`` — never claimed or
    altered.  The finding ID derives from the normalized repair signature
    (affected contract + repair signature + classifier version) — never
    from occurrence IDs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    family: Literal["repair_pattern"] = "repair_pattern"
    finding_id: StrictStr
    affected_contract: StrictStr
    repair_signature: StrictStr
    classifier_version: StrictStr
    recurrence_count: int = Field(ge=2)
    recurrence_count_7d: int = Field(ge=0)
    recurrence_count_30d: int = Field(ge=0)
    first_occurred_at: UtcTime | None = None
    last_occurred_at: UtcTime | None = None
    recurrence_window_seconds: float | None = Field(default=None, ge=0)
    references: FindingReferences
    #: Always ``None`` — repair patterns report recurrence WITHOUT claims.
    economics: AcceptedOutcomeEconomics | None = None

    @field_validator("finding_id", "affected_contract", "repair_signature",
                     "classifier_version")
    @classmethod
    def _validate_identities(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "repair-pattern finding identities must be non-empty strings"
            )
        return value

    @model_validator(mode="after")
    def _check_pattern(self) -> RepairPatternFinding:
        if self.recurrence_count_30d < self.recurrence_count_7d:
            raise ValueError(
                "recurrence_count_30d cannot be below recurrence_count_7d "
                f"({self.recurrence_count_30d} < {self.recurrence_count_7d})"
            )
        if self.economics is not None:
            raise ValueError(
                "repair-pattern findings never carry economics: recurrence "
                "is reported without any avoidable-impact claim"
            )
        return self


class RepairPatternContextEntry(BaseModel):
    """One non-recurring repair occurrence retained as context (SC16).

    Occurrences that do not yet form a recurrence (fewer than 2 with the
    same normalized signature) or that carry no exact accepted-resolution
    anchor stay context — never a finding and never an impact claim.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    observation_id: StrictStr
    affected_contract: StrictStr
    repair_signature: StrictStr
    occurred_at: UtcTime | None = None
    context_reason: StrictStr | None = None
    refs: tuple[OwnerRef, ...] = ()

    @field_validator("observation_id", "affected_contract", "repair_signature")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "repair-pattern context identity/contract/signature must be "
                "non-empty strings"
            )
        return value

    @field_validator("refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_context(self) -> RepairPatternContextEntry:
        if not self.context_reason:
            raise ValueError(
                "repair-pattern context entries require a context_reason"
            )
        return self


class RepairPatternAnalysisResult(BaseModel):
    """Output of the repair-pattern analyzer (findings + retained context)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: tuple[RepairPatternFinding, ...] = ()
    context: tuple[RepairPatternContextEntry, ...] = ()


def derive_repair_pattern_finding_id(
    *,
    affected_contract: str,
    repair_signature: str,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> str:
    """Deterministic repair-pattern finding ID from the normalized signature.

    ``efficiency_repair_pattern|{sha256(affected_contract|repair_signature|
    classifier_version)}`` — never over occurrence IDs, so the same repair
    pattern across different occurrences derives the same finding identity.
    """
    if not affected_contract or not repair_signature:
        raise ValueError(
            "repair-pattern finding IDs require an affected contract and a "
            "repair signature"
        )
    material = canonical_json(
        {
            "family": "repair_pattern",
            "affected_contract": affected_contract,
            "repair_signature": repair_signature,
            "classifier_version": classifier_version,
        }
    )
    return f"efficiency_repair_pattern|{_sha256_hex(material)}"


def _recurrence_count_within(
    timestamps: Sequence[datetime],
    *,
    reference: datetime,
    days: int,
) -> int:
    """Count timestamps within *days* before (inclusive of) *reference*."""
    cutoff = reference.timestamp() - days * 86400.0
    return sum(1 for stamp in timestamps if stamp.timestamp() >= cutoff)


def analyze_repair_patterns(
    observations: Sequence[NormalizedRepairPatternObservation],
    *,
    classifier_version: str = DEFAULT_CLASSIFIER_VERSION,
) -> RepairPatternAnalysisResult:
    """Repair-pattern analyzer: recurrence windows, reference-only custody.

    Occurrences sharing the same ``(affected_contract, repair_signature)``
    become one ``repair_pattern`` finding when at least 2 occurrences share
    the normalized signature.  The finding reports the recurrence window
    (first/last timestamped occurrence and the span between them) and the
    7d/30d recurrence counts over timestamped occurrences relative to the
    latest occurrence — occurrences without timestamps contribute to the
    total count only (missing timestamps are never inferred).  Active
    custody is carried ONLY as reference/covariate refs and the finding
    NEVER carries economics (SC16: recurrence reported without claims).

    A group whose occurrences carry no exact accepted-resolution anchor
    yields NO finding (conservative: every T3 finding anchors to an exact
    accepted resolution); non-recurring singleton occurrences stay context.
    """
    groups: dict[tuple[str, str], list[NormalizedRepairPatternObservation]] = {}
    for observation in observations:
        groups.setdefault(
            (observation.affected_contract, observation.repair_signature), []
        ).append(observation)

    findings: list[RepairPatternFinding] = []
    context: list[RepairPatternContextEntry] = []
    for (affected_contract, repair_signature), group in groups.items():
        if len(group) < 2:
            context.extend(
                RepairPatternContextEntry(
                    observation_id=observation.observation_id,
                    affected_contract=affected_contract,
                    repair_signature=repair_signature,
                    occurred_at=observation.occurred_at,
                    context_reason="below recurrence threshold (single occurrence)",
                    refs=observation.refs,
                )
                for observation in group
            )
            continue
        accepted_resolution_refs = _union_refs(
            [observation.accepted_resolution_refs for observation in group]
        )
        if not accepted_resolution_refs:
            context.extend(
                RepairPatternContextEntry(
                    observation_id=observation.observation_id,
                    affected_contract=affected_contract,
                    repair_signature=repair_signature,
                    occurred_at=observation.occurred_at,
                    context_reason="no exact accepted-resolution anchor",
                    refs=observation.refs,
                )
                for observation in group
            )
            continue
        timestamps = [
            observation.occurred_at.root
            for observation in group
            if observation.occurred_at is not None
        ]
        last_occurred_at = max(timestamps) if timestamps else None
        first_occurred_at = min(timestamps) if timestamps else None
        recurrence_window_seconds = (
            round(last_occurred_at.timestamp() - first_occurred_at.timestamp(), 6)
            if last_occurred_at is not None and first_occurred_at is not None
            else None
        )
        recurrence_count_7d = (
            _recurrence_count_within(timestamps, reference=last_occurred_at, days=7)
            if last_occurred_at is not None
            else 0
        )
        recurrence_count_30d = (
            _recurrence_count_within(timestamps, reference=last_occurred_at, days=30)
            if last_occurred_at is not None
            else 0
        )
        findings.append(
            RepairPatternFinding(
                finding_id=derive_repair_pattern_finding_id(
                    affected_contract=affected_contract,
                    repair_signature=repair_signature,
                    classifier_version=classifier_version,
                ),
                affected_contract=affected_contract,
                repair_signature=repair_signature,
                classifier_version=classifier_version,
                recurrence_count=len(group),
                recurrence_count_7d=recurrence_count_7d,
                recurrence_count_30d=recurrence_count_30d,
                first_occurred_at=first_occurred_at,
                last_occurred_at=last_occurred_at,
                recurrence_window_seconds=recurrence_window_seconds,
                references=FindingReferences(
                    accepted_resolution_refs=accepted_resolution_refs,
                    active_custody_refs=_union_refs(
                        [observation.active_custody_refs for observation in group]
                    ),
                    source_refs=_union_refs([observation.refs for observation in group]),
                    gate_backoff_refs=_union_refs(
                        [observation.gate_backoff_refs for observation in group]
                    ),
                    censoring_refs=_union_refs(
                        [observation.censoring_refs for observation in group]
                    ),
                ),
                economics=None,
            )
        )
    return RepairPatternAnalysisResult(
        findings=tuple(sorted(findings, key=lambda finding: finding.finding_id)),
        context=tuple(
            sorted(
                context,
                key=lambda entry: (
                    entry.observation_id,
                    entry.affected_contract,
                    entry.repair_signature,
                ),
            )
        ),
    )


class ExclusionAccountEntry(BaseModel):
    """One typed exclusion accounting row (SC16).

    Counts the excluded legs of one family under one typed reason and the
    exact retained context seconds of those legs — excluded context is
    NEVER counted as avoidable impact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    family: Literal["dwell", "loop", "idle_handoff", "repair_pattern"]
    reason: DwellExclusionReason
    count: int = Field(ge=0)
    retained_context_seconds: float = Field(ge=0)


class AvoidableImpactBounds(BaseModel):
    """Conservative aggregate avoidable-impact bounds (SC16).

    ``lower_bound_seconds`` is the sum of the exact proven avoidable
    seconds plus the explicit censored lower bounds (known floors, never
    coerced); ``upper_bound_seconds`` is ``None`` (unknown) whenever any
    avoidable-eligible measure is censored or missing — a finite upper
    bound is only claimed when every contributing measure is exact.
    ``unknown_count`` counts censored/missing avoidable-eligible legs;
    ``excluded_count`` / ``excluded_seconds`` retain the typed exclusion
    accounting that is never part of the bounds.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    lower_bound_seconds: float = Field(ge=0)
    upper_bound_seconds: float | None = Field(default=None, ge=0)
    unknown_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    excluded_seconds: float = Field(ge=0)
    entries: tuple[ExclusionAccountEntry, ...] = ()


def _exact_finding_seconds(economics: AcceptedOutcomeEconomics) -> float | None:
    """Total exact attributed seconds of one economics payload (or ``None``)."""
    if economics.time_seconds_per_accepted is None or economics.accepted_outcome_count is None:
        return None
    return economics.time_seconds_per_accepted * economics.accepted_outcome_count


def aggregate_exclusion_accounting(
    *,
    dwell: DwellAnalysisResult | None = None,
    loops: Sequence[LoopFinding] = (),
    handoffs: HandoffAnalysisResult | None = None,
    repair_patterns: Sequence[RepairPatternFinding] = (),
) -> AvoidableImpactBounds:
    """Typed exclusion accounting across families -> avoidable-impact bounds.

    * **Proven exact seconds** (dwell/loop/handoff findings with exact
      economics) add to ``lower_bound_seconds``;
    * **Censored known floors** (censored dwell findings whose economics
      carry the proven lower-bound value) add to ``lower_bound_seconds`` as
      known floors and mark the measure unknown — the aggregate
      ``upper_bound_seconds`` becomes ``None`` whenever any contributing
      measure is censored or missing (conservative: a finite upper bound is
      only claimed when every measure is exact);
    * **Excluded context** (typed exclusion reasons from the dwell and
      handoff families) is retained per family/reason with its exact
      context seconds and NEVER enters the bounds;
    * **Repair-pattern findings never carry economics** (SC16), so they
      contribute no avoidable-impact claim to the bounds.

    Deterministic: entries are sorted by (family, reason); all aggregation
    is input-order independent.
    """
    lower_bound = 0.0
    unknown_count = 0
    censored_or_missing = False
    excluded_count = 0
    excluded_seconds = 0.0
    entries: dict[tuple[str, DwellExclusionReason], tuple[int, float]] = {}

    def _record_exclusion(family: str, reason: DwellExclusionReason, seconds: float) -> None:
        nonlocal excluded_count, excluded_seconds
        excluded_count += 1
        excluded_seconds = round(excluded_seconds + seconds, 6)
        count, total = entries.get((family, reason), (0, 0.0))
        entries[(family, reason)] = (count + 1, round(total + seconds, 6))

    if dwell is not None:
        for finding in dwell.findings:
            if finding.economics is None:
                continue
            if finding.censored:
                value = finding.economics.time_seconds_per_accepted
                if value is None:
                    censored_or_missing = True
                    unknown_count += 1
                    continue
                lower_bound = round(lower_bound + value, 6)
                censored_or_missing = True
                unknown_count += 1
            else:
                value = _exact_finding_seconds(finding.economics)
                if value is None:
                    censored_or_missing = True
                    unknown_count += 1
                    continue
                lower_bound = round(lower_bound + value, 6)
        for entry in dwell.context:
            if entry.excluded_reason is None:
                continue
            seconds = float(
                entry.elapsed_seconds
                if entry.elapsed_seconds is not None
                else (entry.lower_bound_seconds or 0.0)
            )
            _record_exclusion("dwell", entry.excluded_reason, seconds)

    for finding in loops:
        if finding.economics is None:
            continue
        value = _exact_finding_seconds(finding.economics)
        if value is None:
            censored_or_missing = True
            unknown_count += 1
            continue
        lower_bound = round(lower_bound + value, 6)

    if handoffs is not None:
        for finding in handoffs.findings:
            if finding.economics is None:
                continue
            value = _exact_finding_seconds(finding.economics)
            if value is None:
                censored_or_missing = True
                unknown_count += 1
                continue
            lower_bound = round(lower_bound + value, 6)
        for entry in handoffs.context:
            if entry.excluded_reason is None:
                continue
            seconds = float(
                entry.idle_seconds
                if entry.idle_seconds is not None
                else (entry.lower_bound_seconds or 0.0)
            )
            _record_exclusion("idle_handoff", entry.excluded_reason, seconds)

    # Repair-pattern findings never carry economics (SC16): they report
    # recurrence and custody references only, so they contribute no
    # avoidable-impact claim to the bounds.
    for _finding in repair_patterns:
        if _finding.economics is not None:  # pragma: no cover - model forbids it
            censored_or_missing = True
            unknown_count += 1

    return AvoidableImpactBounds(
        lower_bound_seconds=round(lower_bound, 6),
        upper_bound_seconds=None if censored_or_missing else round(lower_bound, 6),
        unknown_count=unknown_count,
        excluded_count=excluded_count,
        excluded_seconds=round(excluded_seconds, 6),
        entries=tuple(
            sorted(
                (
                    ExclusionAccountEntry(
                        family=family,
                        reason=reason,
                        count=count,
                        retained_context_seconds=round(total, 6),
                    )
                    for (family, reason), (count, total) in entries.items()
                ),
                key=lambda entry: (entry.family, entry.reason.value),
            )
        ),
    )


__all__ = [
    "AvoidableImpactBounds",
    "CallOutcome",
    "DEFAULT_CLASSIFIER_VERSION",
    "DwellAnalysisResult",
    "DwellContextEntry",
    "DwellExclusionReason",
    "ExclusionAccountEntry",
    "HandoffAnalysisResult",
    "HandoffContextEntry",
    "NormalizedCall",
    "NormalizedDwellObservation",
    "NormalizedHandoffObservation",
    "NormalizedRepairPatternObservation",
    "RepairPatternAnalysisResult",
    "RepairPatternContextEntry",
    "RepairPatternFinding",
    "aggregate_exclusion_accounting",
    "analyze_duplicate_calls",
    "analyze_dwell",
    "analyze_equivalent_failures",
    "analyze_finalize_publication_dwell",
    "analyze_gate_dwell",
    "analyze_idle_handoffs",
    "analyze_loops",
    "analyze_no_progress",
    "analyze_repair_patterns",
    "analyze_retry_loops",
    "analyze_review_dwell",
    "derive_dwell_finding_id",
    "derive_handoff_finding_id",
    "derive_loop_problem_id",
    "derive_repair_pattern_finding_id",
]