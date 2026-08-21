"""M5 deterministic root-cause clustering (Plan Step 18 / T18).

This module implements the deterministic, store-free clustering of normalized
evidence signatures into root-cause candidates.  It is the pure clustering
half of Phase 3: it never constructs or mutates an owner store and never
invokes an opaque or nondeterministic model call.

Locked Step 18 rules implemented here:

* **Cluster by affected contract and evidence features.**  Evidence groups by
  ``(affected_contract, classifier_version, evidence feature set)`` — NEVER by
  schedule/repair occurrence identity.  Occurrence identities
  (``evidence_id``) appear only as exact reference/covariate refs; the
  root-cause fingerprint is a canonical hash over the affected contract, the
  sorted evidence feature set, and the classifier version.
* **Input-order independence.**  Feature sets are sorted and de-duplicated at
  the contract boundary, reference groups are sorted, and outputs (candidates
  and context) are sorted by stable identities — shuffling the input evidence
  never changes fingerprints, counts, coverage, confidence, or ordering.
* **Classifier-version separation.**  The classifier version is part of the
  group key and of the fingerprint: evidence produced by different classifier
  versions NEVER merges, even for the same contract and feature set.
* **Contract-distinct non-merging.**  Superficially similar evidence
  (identical features) on different affected contracts never merges: the
  contract is part of the fingerprint.
* **Recurrence gating (2-in-7 or 3-in-30).**  A group becomes a
  :class:`RootCauseCandidate` only when the recurrence signal is satisfied:
  at least 2 occurrences within any 7-day window OR at least 3 occurrences
  within any 30-day window.  Groups below the signal (and singletons) stay
  typed :class:`ClusterContextEntry` rows — they remain report findings but
  can never become proposals.
* **Late occurrences are deterministic corrections.**  The fingerprint and
  candidate ID are occurrence-set independent: adding a late occurrence to
  the same contract/features/classifier re-derives the SAME candidate
  identity with advanced recurrence counts, so late evidence corrects counts
  without ever rewriting the root-cause identity.
* **Alternatives, coverage, confidence, custody refs, bounded impact.**
  Every candidate carries deterministic alternative explanations (the other
  distinct signatures observed on the same affected contract), an
  evidence-coverage denominator (cluster evidence over the contract's total
  observed evidence, with featureless evidence typed unknown), conservative
  confidence bounds (supported share with an unknown ceiling when censored
  evidence is present), reference-only active custody, and denominator-gated
  avoidable-impact economics over the EXACT accepted-outcome count.

Inputs are pure :class:`ClusterEvidence` facts (the Step 11 normalized
evidence shape); this module never constructs or mutates an owner store.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

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
    AcceptedOutcomeEconomics,
    DenominatorCoverage,
    QuantileBounds,
    RootCauseAlternative,
    RootCauseCandidate,
)
from arnold_pipelines.megaplan.maintenance.identity import OwnerRef, UtcTime, canonical_json


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


def _sorted_features(features: Sequence[str]) -> tuple[str, ...]:
    """Canonical sorted de-duplicated evidence feature set."""
    return tuple(sorted(set(features)))


# ---------------------------------------------------------------------------
# Cluster evidence input (Step 11 normalized shape)
# ---------------------------------------------------------------------------


class ClusterEvidence(BaseModel):
    """One normalized clustering evidence fact (Step 18 input).

    ``evidence_id`` is the operational occurrence identity — it is NEVER part
    of a root-cause fingerprint or candidate ID.  ``evidence_features`` is the
    normalized non-content feature set of the evidence (finding family /
    kind / stage / failure or repair signature / mismatch legs / ...); it is
    sorted and de-duplicated at the contract boundary so hashing is
    input-order independent.  ``occurred_at`` timestamps bound the recurrence
    windows; occurrences without timestamps contribute to the group total
    only (recurrence counts stay exact counts of timestamped occurrences —
    missing timestamps are never inferred).  ``accepted_outcome_id`` pins the
    exact accepted outcome the evidence is attributed to (the avoidable-impact
    denominator basis); when present, ``accepted_resolution_refs`` must carry
    the exact resolution anchors (T3 contract).  Active custody appears only
    as reference/covariate refs — never claimed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    evidence_id: StrictStr
    affected_contract: StrictStr
    classifier_version: StrictStr
    evidence_features: tuple[StrictStr, ...] = ()
    occurred_at: UtcTime | None = None
    accepted_outcome_id: StrictStr | None = None
    #: Exact time measure of the evidence (never coerced; may be absent).
    time_seconds: float | None = Field(default=None, ge=0)
    censored: bool = False
    #: Exact source evidence refs for this evidence (mandatory).
    refs: tuple[OwnerRef, ...] = ()
    accepted_resolution_refs: tuple[OwnerRef, ...] = ()
    active_custody_refs: tuple[OwnerRef, ...] = ()
    gate_backoff_refs: tuple[OwnerRef, ...] = ()
    censoring_refs: tuple[OwnerRef, ...] = ()

    @field_validator("evidence_id", "affected_contract", "classifier_version")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "cluster evidence id/contract/classifier must be non-empty strings"
            )
        return value

    @field_validator("accepted_outcome_id")
    @classmethod
    def _validate_outcome(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("accepted_outcome_id must be a non-empty string when present")
        return value

    @field_validator("evidence_features")
    @classmethod
    def _sort_features(cls, value: Sequence[str]) -> tuple[str, ...]:
        for feature in value:
            if not feature:
                raise ValueError("evidence features must be non-empty strings")
        return _sorted_features(value)

    @field_validator(
        "refs",
        "accepted_resolution_refs",
        "active_custody_refs",
        "gate_backoff_refs",
        "censoring_refs",
    )
    @classmethod
    def _sort_reference_groups(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @model_validator(mode="after")
    def _check_evidence(self) -> ClusterEvidence:
        if not self.refs:
            raise ValueError(
                "cluster evidence requires at least one exact source ref"
            )
        if self.accepted_outcome_id is not None and not self.accepted_resolution_refs:
            raise ValueError(
                "evidence attributed to an exact accepted outcome requires exact "
                "accepted_resolution_refs"
            )
        return self


class ClusterContextEntry(BaseModel):
    """One non-candidate clustering row retained as report context (SC19).

    Evidence that does not form a candidate — a single occurrence, or a group
    whose recurrence signal is not satisfied — stays context: it remains a
    report finding but can NEVER become a proposal.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = DAILY_EFFICIENCY_CONTRACT_ID
    evidence_id: StrictStr
    affected_contract: StrictStr
    classifier_version: StrictStr
    evidence_features: tuple[StrictStr, ...] = ()
    occurred_at: UtcTime | None = None
    context_reason: StrictStr
    refs: tuple[OwnerRef, ...] = ()

    @field_validator("evidence_id", "affected_contract", "classifier_version", "context_reason")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "cluster context identity/contract/classifier/reason must be "
                "non-empty strings"
            )
        return value

    @field_validator("evidence_features")
    @classmethod
    def _sort_features(cls, value: Sequence[str]) -> tuple[str, ...]:
        return _sorted_features(value)

    @field_validator("refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)


class ClusterAnalysisResult(BaseModel):
    """Output of the root-cause clusterer (candidates + retained context)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: tuple[RootCauseCandidate, ...] = ()
    context: tuple[ClusterContextEntry, ...] = ()


# ---------------------------------------------------------------------------
# Deterministic signature / identity derivations
# ---------------------------------------------------------------------------


def derive_evidence_feature_key(
    evidence_features: Sequence[str],
    *,
    classifier_version: str,
) -> str:
    """Canonical feature-key for grouping (sorted feature set + classifier).

    The key is input-order independent (features are sorted and de-duplicated)
    and carries the classifier version so different classifier versions NEVER
    merge into one group.
    """
    if not classifier_version:
        raise ValueError("evidence feature keys require a classifier version")
    return canonical_json(
        {
            "evidence_features": _sorted_features(evidence_features),
            "classifier_version": classifier_version,
        }
    )


def derive_root_cause_fingerprint(
    *,
    affected_contract: str,
    evidence_features: Sequence[str],
    classifier_version: str,
) -> str:
    """Canonical root-cause fingerprint over (contract, features, classifier).

    sha256 of the canonical JSON over the affected contract, the sorted
    de-duplicated evidence feature set, and the classifier version.  The
    fingerprint is the locked problem signature: the reused envelope
    :class:`RootCauseCluster` signature binds to it (Step 1 seam), cluster
    occurrence IDs derive from it, and proposal keys embed it.  Occurrence
    identities and timestamps are deliberately NOT part of the material, so a
    late occurrence re-derives the SAME fingerprint.
    """
    if not affected_contract or not classifier_version:
        raise ValueError(
            "root-cause fingerprints require an affected contract and a "
            "classifier version"
        )
    material = canonical_json(
        {
            "affected_contract": affected_contract,
            "evidence_features": _sorted_features(evidence_features),
            "classifier_version": classifier_version,
        }
    )
    return _sha256_hex(material)


def derive_candidate_id(root_cause_fingerprint: str) -> str:
    """Deterministic candidate identity from the root-cause fingerprint."""
    if not root_cause_fingerprint:
        raise ValueError("candidate IDs require a root-cause fingerprint")
    return f"efficiency_root_cause|{root_cause_fingerprint}"


# ---------------------------------------------------------------------------
# Recurrence signal (locked: 2-in-7 OR 3-in-30)
# ---------------------------------------------------------------------------


def recurrence_signal_satisfied(
    *,
    recurrence_count_7d: int,
    recurrence_count_30d: int,
) -> bool:
    """Locked recurrence gate: 2 occurrences in 7 days OR 3 in 30 days.

    The counts are the maximum occurrence counts inside any 7-day / 30-day
    window over the group's timestamped occurrences (window end anchored at
    each occurrence, inclusive of the anchor), so a recurrence is detected
    wherever it actually occurs — not only in the window ending at the latest
    occurrence.
    """
    if recurrence_count_7d < 0 or recurrence_count_30d < 0:
        raise ValueError("recurrence counts cannot be negative")
    return recurrence_count_7d >= 2 or recurrence_count_30d >= 3


def _recurrence_max_counts(
    timestamps: Sequence[datetime],
) -> tuple[int, int]:
    """Maximum 7-day and 30-day occurrence counts over any anchor window.

    For each timestamped occurrence used as the anchor, count occurrences
    within 7 / 30 days before (inclusive of) the anchor; return the maxima.
    Empty input yields ``(0, 0)`` — missing timestamps are never inferred.
    The 30-day window contains the 7-day window, so ``max_30d >= max_7d``
    always holds (the RootCauseCandidate contract requires this).
    """
    if not timestamps:
        return 0, 0
    max_7d = 0
    max_30d = 0
    for anchor in timestamps:
        anchor_ts = anchor.timestamp()
        # Window is [anchor - days, anchor]: strictly BEFORE the anchor,
        # inclusive of the anchor, never including future occurrences.
        count_7d = sum(
            1
            for stamp in timestamps
            if anchor_ts - 7 * 86400.0 <= stamp.timestamp() <= anchor_ts
        )
        count_30d = sum(
            1
            for stamp in timestamps
            if anchor_ts - 30 * 86400.0 <= stamp.timestamp() <= anchor_ts
        )
        max_7d = max(max_7d, count_7d)
        max_30d = max(max_30d, count_30d)
    return max_7d, max_30d


# ---------------------------------------------------------------------------
# Candidate assembly helpers
# ---------------------------------------------------------------------------


def _exact_accepted_outcome_economics(
    group: Sequence[ClusterEvidence],
) -> AcceptedOutcomeEconomics | None:
    """Impact economics over the EXACT accepted-outcome denominator.

    The denominator is the number of distinct exact accepted outcomes the
    grouped evidence is attributed to; per-accepted time is the total exact
    time over that denominator.  Returns ``None`` when no evidence carries an
    exact accepted-outcome attribution — a missing denominator is never
    inferred and no raw-total claim is emitted without it.
    """
    attributed = [item for item in group if item.accepted_outcome_id is not None]
    if not attributed:
        return None
    denominator = len({item.accepted_outcome_id for item in attributed})
    known = [item.time_seconds for item in attributed if item.time_seconds is not None]
    time_per_accepted = (
        round(sum(known) / denominator, 6) if known else None
    )
    return AcceptedOutcomeEconomics(
        accepted_outcome_count=denominator,
        time_seconds_per_accepted=time_per_accepted,
    )


def _candidate_confidence(group: Sequence[ClusterEvidence]) -> QuantileBounds:
    """Conservative confidence bounds for one candidate group.

    ``value``/``lower_bound`` are the exact share of cluster evidence with an
    exact accepted-outcome attribution (supported evidence); the upper bound
    stays ``None`` (unknown ceiling) whenever censored evidence is present —
    a finite confidence ceiling is only claimed when every contributing
    measure is exact.
    """
    supported = sum(1 for item in group if item.accepted_outcome_id is not None)
    value = round(supported / len(group), 6) if group else None
    has_censored = any(item.censored for item in group)
    return QuantileBounds(
        value=value,
        lower_bound=value,
        upper_bound=None if has_censored else value,
    )


def _cluster_coverage(
    group: Sequence[ClusterEvidence],
    *,
    contract_total: int,
    contract_unknown: int,
) -> DenominatorCoverage:
    """Evidence-coverage denominator for one candidate.

    ``numerator`` is the cluster evidence count, ``denominator`` is the
    affected contract's total observed evidence (across every signature
    group), ``unknown_count`` is the contract evidence that could not be
    clustered (featureless), and ``censored_count`` is the cluster's censored
    evidence.  Coverage is never fabricated: the denominator is always an
    exact count of the supplied evidence.
    """
    return DenominatorCoverage(
        metric="evidence_coverage",
        numerator=len(group),
        denominator=contract_total,
        unknown_count=contract_unknown,
        censored_count=sum(1 for item in group if item.censored),
    )


def _build_alternatives(
    *,
    affected_contract: str,
    classifier_version: str,
    own_feature_key: str,
    other_groups: Sequence[tuple[str, Sequence[ClusterEvidence]]],
) -> tuple[RootCauseAlternative, ...]:
    """Deterministic alternative explanations from the contract's OTHER groups.

    Each other distinct signature observed on the same affected contract is an
    alternative explanation for the contract-level symptoms; its confidence is
    that group's conservative confidence bounds and its evidence refs are the
    group's occurrence refs.  Self-alternatives are never emitted, and each
    alternative keeps its own classifier version in its fingerprint (classifier
    separation is preserved everywhere).
    """
    alternatives: list[RootCauseAlternative] = []
    own_key = (affected_contract, classifier_version, own_feature_key)
    for other_key, other_group in other_groups:
        if other_key == own_key:
            continue
        other_classifier = other_group[0].classifier_version
        other_fingerprint = derive_root_cause_fingerprint(
            affected_contract=affected_contract,
            evidence_features=other_group[0].evidence_features,
            classifier_version=other_classifier,
        )
        alternatives.append(
            RootCauseAlternative(
                alternative_id=f"root_cause_alt|{other_fingerprint}",
                summary=(
                    "alternative explanation from a distinct signature observed "
                    f"on contract {affected_contract!r}"
                ),
                confidence=_candidate_confidence(other_group),
                evidence_refs=_union_refs([item.refs for item in other_group]),
            )
        )
    return tuple(sorted(alternatives, key=lambda alt: alt.alternative_id))


def _build_candidate(
    group: Sequence[ClusterEvidence],
    *,
    affected_contract: str,
    classifier_version: str,
    feature_key: str,
    contract_total: int,
    contract_unknown: int,
    other_groups: Sequence[tuple[str, Sequence[ClusterEvidence]]],
) -> RootCauseCandidate:
    """Build one strict root-cause candidate from a recurrence-eligible group."""
    features = group[0].evidence_features
    fingerprint = derive_root_cause_fingerprint(
        affected_contract=affected_contract,
        evidence_features=features,
        classifier_version=classifier_version,
    )
    timestamps = [
        item.occurred_at.root for item in group if item.occurred_at is not None
    ]
    recurrence_count_7d, recurrence_count_30d = _recurrence_max_counts(timestamps)
    return RootCauseCandidate(
        candidate_id=derive_candidate_id(fingerprint),
        root_cause_fingerprint=fingerprint,
        affected_contract=affected_contract,
        classifier_version=classifier_version,
        alternatives=_build_alternatives(
            affected_contract=affected_contract,
            classifier_version=classifier_version,
            own_feature_key=feature_key,
            other_groups=other_groups,
        ),
        coverage=_cluster_coverage(
            group,
            contract_total=contract_total,
            contract_unknown=contract_unknown,
        ),
        confidence=_candidate_confidence(group),
        recurrence_count_7d=recurrence_count_7d,
        recurrence_count_30d=recurrence_count_30d,
        occurrence_refs=_union_refs([item.refs for item in group]),
        active_custody_refs=_union_refs(
            [item.active_custody_refs for item in group]
        ),
        evidence_refs=_union_refs(
            [item.accepted_resolution_refs for item in group]
        ),
        avoidable_impact=_exact_accepted_outcome_economics(group),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def cluster_root_causes(
    evidence: Sequence[ClusterEvidence],
) -> ClusterAnalysisResult:
    """Cluster normalized evidence deterministically into root-cause candidates.

    Groups evidence by ``(affected_contract, classifier_version, evidence
    feature set)`` — never by occurrence identity and never with an opaque
    model call.  A group becomes a :class:`RootCauseCandidate` only when the
    locked recurrence signal holds (2-in-7 OR 3-in-30 over timestamped
    occurrences); singletons and below-signal groups stay typed
    :class:`ClusterContextEntry` context rows (report findings, never
    proposals).  All outputs are sorted by stable identities, so the result is
    input-order independent.
    """
    groups: dict[tuple[str, str, str], list[ClusterEvidence]] = {}
    for item in evidence:
        feature_key = derive_evidence_feature_key(
            item.evidence_features, classifier_version=item.classifier_version
        )
        groups.setdefault(
            (item.affected_contract, item.classifier_version, feature_key), []
        ).append(item)

    contract_totals: dict[str, int] = {}
    contract_unknown: dict[str, int] = {}
    for item in evidence:
        contract_totals[item.affected_contract] = (
            contract_totals.get(item.affected_contract, 0) + 1
        )
        if not item.evidence_features:
            contract_unknown[item.affected_contract] = (
                contract_unknown.get(item.affected_contract, 0) + 1
            )

    candidates: list[RootCauseCandidate] = []
    context: list[ClusterContextEntry] = []

    for (affected_contract, classifier_version, feature_key), group in groups.items():
        if len(group) < 2:
            context.extend(
                ClusterContextEntry(
                    evidence_id=item.evidence_id,
                    affected_contract=affected_contract,
                    classifier_version=classifier_version,
                    evidence_features=item.evidence_features,
                    occurred_at=item.occurred_at,
                    context_reason="below recurrence threshold (single occurrence)",
                    refs=item.refs,
                )
                for item in group
            )
            continue
        timestamps = [
            item.occurred_at.root for item in group if item.occurred_at is not None
        ]
        recurrence_count_7d, recurrence_count_30d = _recurrence_max_counts(timestamps)
        if not recurrence_signal_satisfied(
            recurrence_count_7d=recurrence_count_7d,
            recurrence_count_30d=recurrence_count_30d,
        ):
            context.extend(
                ClusterContextEntry(
                    evidence_id=item.evidence_id,
                    affected_contract=affected_contract,
                    classifier_version=classifier_version,
                    evidence_features=item.evidence_features,
                    occurred_at=item.occurred_at,
                    context_reason=(
                        "recurrence signal not satisfied (no 2-in-7-day or "
                        "3-in-30-day window)"
                    ),
                    refs=item.refs,
                )
                for item in group
            )
            continue
        candidates.append(
            _build_candidate(
                group,
                affected_contract=affected_contract,
                classifier_version=classifier_version,
                feature_key=feature_key,
                contract_total=contract_totals.get(affected_contract, 0),
                contract_unknown=contract_unknown.get(affected_contract, 0),
                other_groups=[
                    (key, other)
                    for key, other in groups.items()
                    if key[0] == affected_contract
                ],
            )
        )

    return ClusterAnalysisResult(
        candidates=tuple(sorted(candidates, key=lambda item: item.candidate_id)),
        context=tuple(
            sorted(
                context,
                key=lambda entry: (
                    entry.evidence_id,
                    entry.affected_contract,
                    entry.classifier_version,
                    entry.evidence_features,
                ),
            )
        ),
    )


__all__ = [
    "ClusterAnalysisResult",
    "ClusterContextEntry",
    "ClusterEvidence",
    "cluster_root_causes",
    "derive_candidate_id",
    "derive_evidence_feature_key",
    "derive_root_cause_fingerprint",
    "recurrence_signal_satisfied",
]