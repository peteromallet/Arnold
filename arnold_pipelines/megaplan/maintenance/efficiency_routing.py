"""M5 inert recommendation routing (Plan Step 19 / T19).

This module routes deduplicated, INERT recommendation decisions from
deterministic root-cause candidates (Step 18 / T18) plus the stable
open-ticket identity (Step 9 / T9).  It is the pure routing half of Phase 3:

* it NEVER invokes ticket materialization, initiative prioritization,
  repair, retry/relaunch, or routing/profile/budget/plan/chain mutation —
  the router exposes no mutation-capable dependency and returns only typed
  inert recommendations (``auto_materialization`` stays locked ``False``);
* it matches open tickets through the injected read-only snapshot query
  (``OpenTicketSnapshotRead``) and chooses exactly one of the four closed
  recommendation kinds: ``new_ticket_proposal``,
  ``existing_ticket_recommendation``, ``initiative_recommendation``, or
  ``report_only``;
* it enforces the versioned coverage / confidence / recurrence / precision
  policy (provisional shadow-mode gates: evidence coverage >= 0.80, cluster
  confidence >= 0.80, recurrence 2-in-7-day OR 3-in-30-day) and the
  100-sample / 10-plan guard before any p99- or regression-driven priority
  recommendation;
* it deduplicates on the LOCKED cross-window proposal key (SD3): the stable
  occurrence ID is derived from the key (Step 4), and a prior-proposal-key
  ledger lookup (injected, to be invoked under the current resident fence)
  turns a re-emission into an ``already_present`` decision — the same
  proposal can never re-append at the occurrence-only
  ``lifecycle_idempotency_key`` boundary;
* it records matching open-ticket identity, active repair custody,
  evidence refs, rationale, alternatives, estimated impact, and the human
  acceptance state (``pending_human_acceptance``) on every decision.

Inputs are pure Step 2/3/4 contracts plus the Step 9 ticket snapshot; this
module never constructs or mutates an owner store and never imports a
mutation-capable module (proven by the negative tests in
``test_maintenance_efficiency_routing.py``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from typing import Literal

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
    BaselineSnapshot,
    DailyEfficiencyProposal,
    ProposalKind,
    RootCauseAlternative,
    RootCauseCandidate,
    ShadowMeasure,
    ShadowMeasureKind,
    derive_proposal_key,
    derive_proposal_occurrence_id,
)
from arnold_pipelines.megaplan.maintenance.efficiency_sources import (
    NO_MATCH_TICKET_IDENTITY,
    OpenTicketSnapshotRead,
    SourceReadDisposition,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    EventWindow,
    OwnerRef,
    UtcTime,
)


def _coerce_environment(environment: EnvironmentId | str | None) -> EnvironmentId | None:
    """Normalize an environment coordinate to its strict identity (or None)."""
    if environment is None:
        return None
    if isinstance(environment, EnvironmentId):
        return environment
    return EnvironmentId(environment)


# ---------------------------------------------------------------------------
# Fail-closed routing callback admission (G1-F-002)
# ---------------------------------------------------------------------------
# Opaque lambdas / functions / writer objects are refused.  The router
# accepts only the explicit read-only capability wrappers below, then
# retains a sealed single-operation surface — never the original callback.


class RoutingAdmissionError(TypeError):
    """Construction-time refusal of an opaque or mutation-capable routing seam."""


_ROUTING_MUTATION_VERBS: frozenset[str] = frozenset(
    {
        "append",
        "reserve",
        "update",
        "write",
        "delete",
        "remove",
        "create",
        "acquire",
        "renew",
        "transfer",
        "release",
        "expire",
        "fence",
        "migrate",
        "insert",
        "reclaim",
        "record_event",
    }
)


def _routing_writer_named(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    if lowered in _ROUTING_MUTATION_VERBS:
        return True
    return any(
        part in _ROUTING_MUTATION_VERBS for part in lowered.split("_") if part
    )


def _routing_public_callables(provider: object) -> tuple[str, ...]:
    names: list[str] = []
    for name in dir(provider):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(provider, name)
        except Exception:
            continue
        if callable(attr):
            names.append(name)
    return tuple(names)


def _reject_routing_writers(
    provider: object, *, allowed: frozenset[str], what: str
) -> None:
    writers = [
        name
        for name in _routing_public_callables(provider)
        if name not in allowed and _routing_writer_named(name)
    ]
    if writers:
        raise RoutingAdmissionError(
            f"{what} exposes mutation-capable method(s) {sorted(writers)!r}; "
            "routing admits only the declared read-only capability"
        )


def _wrap_routing_operation(operation: Callable[..., bool], name: str) -> Callable[..., bool]:
    def _bound(*args: object, **kwargs: object) -> bool:
        return bool(operation(*args, **kwargs))

    _bound.__name__ = name
    _bound.__qualname__ = name
    return _bound


class PriorKeyLookup:
    """Explicit read-only prior-proposal-key lookup (``str -> bool``)."""

    __slots__ = ("_lookup",)

    def __init__(self, lookup: Callable[[str], bool]) -> None:
        if not callable(lookup):
            raise RoutingAdmissionError(
                "prior-key lookup payload must be a callable str -> bool"
            )
        _reject_routing_writers(
            lookup, allowed=frozenset(), what="prior-key lookup payload"
        )
        object.__setattr__(
            self, "_lookup", _wrap_routing_operation(lookup, "lookup")
        )

    def lookup(self, key: str) -> bool:
        return bool(object.__getattribute__(self, "_lookup")(key))


class InitiativeEligibility:
    """Explicit read-only initiative-eligibility predicate (candidate -> bool)."""

    __slots__ = ("_eligible",)

    def __init__(self, predicate: Callable[[RootCauseCandidate], bool]) -> None:
        if not callable(predicate):
            raise RoutingAdmissionError(
                "initiative-eligibility payload must be a callable "
                "RootCauseCandidate -> bool"
            )
        _reject_routing_writers(
            predicate,
            allowed=frozenset(),
            what="initiative-eligibility payload",
        )
        object.__setattr__(
            self, "_eligible", _wrap_routing_operation(predicate, "eligible")
        )

    def eligible(self, candidate: RootCauseCandidate) -> bool:
        return bool(object.__getattribute__(self, "_eligible")(candidate))


def _seal_routing_operation(
    capability: object,
    *,
    expected_type: type,
    operation: str,
    what: str,
) -> Callable[..., bool]:
    if not isinstance(capability, expected_type):
        raise RoutingAdmissionError(
            f"{what} must be an explicit {expected_type.__name__} "
            "read-only capability; unwrapped callables are refused"
        )
    _reject_routing_writers(
        capability, allowed=frozenset({operation}), what=what
    )
    method = getattr(capability, operation, None)
    if not callable(method):
        raise RoutingAdmissionError(
            f"{what} is missing required read operation {operation!r}"
        )
    return _wrap_routing_operation(method, operation)


def _admit_prior_key_lookup(capability: object) -> Callable[[str], bool]:
    return _seal_routing_operation(
        capability,
        expected_type=PriorKeyLookup,
        operation="lookup",
        what="prior_key_lookup",
    )


def _admit_initiative_eligibility(
    capability: object | None,
) -> Callable[[RootCauseCandidate], bool]:
    if capability is None:

        def _closed(_candidate: RootCauseCandidate) -> bool:
            return False

        return _closed
    return _seal_routing_operation(
        capability,
        expected_type=InitiativeEligibility,
        operation="eligible",
        what="initiative_eligible",
    )


class RecommendationKind(str, Enum):
    """Closed vocabulary of inert M5 recommendation decisions (Step 19).

    ``new_ticket_proposal`` — a proven no-match open ticket, so a fresh
    ticket proposal is recommended (still inert: ``auto_materialization`` is
    locked ``False``); ``existing_ticket_recommendation`` — a stable matching
    open ticket already exists and receives the recommendation;
    ``initiative_recommendation`` — a cross-cutting initiative recommendation
    (product-gated, never ticket-scoped); ``report_only`` — the candidate
    stays a report finding and can never become a proposal.
    """

    NEW_TICKET_PROPOSAL = "new_ticket_proposal"
    EXISTING_TICKET_RECOMMENDATION = "existing_ticket_recommendation"
    INITIATIVE_RECOMMENDATION = "initiative_recommendation"
    REPORT_ONLY = "report_only"


class RecommendationState(str, Enum):
    """Closed dedupe state of one routed recommendation.

    ``new`` — the locked proposal key is not yet committed, so the inert
    proposal may be appended; ``already_present`` — the locked proposal key
    is already committed under the current fence (prior-key lookup), so the
    cross-window re-emission is deduplicated and nothing is appended.
    """

    NEW = "new"
    ALREADY_PRESENT = "already_present"


class RoutingPolicy(BaseModel):
    """Versioned recommendation policy (provisional shadow-mode gates).

    The locked Step 19 policy enforces evidence coverage, cluster confidence,
    and recurrence before ANY proposal, and the 100-sample / 10-plan guard
    (plus a measured shadow precision) before a recommendation may affect
    ticket priority.  The provisional shadow-mode values are the plan's
    defaults: evidence coverage >= 0.80, cluster confidence >= 0.80,
    recurrence 2-in-7-day OR 3-in-30-day.  Changing approved values updates
    this versioned packet — never hard-coded analyzer branches.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    policy_version: StrictStr
    #: Minimum evidence coverage ratio (numerator/denominator) for a proposal.
    min_evidence_coverage: float = Field(default=0.80, ge=0, le=1)
    #: Minimum cluster confidence (value, or conservative lower bound) for a proposal.
    min_cluster_confidence: float = Field(default=0.80, ge=0, le=1)
    #: Recurrence gate: at least this many occurrences in 7 days ...
    recurrence_min_7d: int = Field(default=2, ge=0)
    #: ... OR at least this many occurrences in 30 days.
    recurrence_min_30d: int = Field(default=3, ge=0)
    #: Guard before a p99/regression-driven PRIORITY recommendation: minimum
    #: completed cohort samples from the baseline snapshots.
    priority_min_samples: int = Field(default=100, ge=1)
    #: Guard before a priority recommendation: minimum distinct plans.
    priority_min_plans: int = Field(default=10, ge=1)
    #: Measured shadow precision required before a recommendation may affect
    #: priority.  Provisional default 1.0 keeps priority effects report-only
    #: until measured precision is perfect (decision-gated policy value).
    priority_min_precision: float = Field(default=1.0, ge=0, le=1)

    @field_validator("policy_version")
    @classmethod
    def _validate_policy_version(cls, value: str) -> str:
        if not value:
            raise ValueError("routing policy_version must be a non-empty string")
        return value


#: Provisional shadow-mode routing policy (locked Step 19 defaults).
DEFAULT_ROUTING_POLICY: RoutingPolicy = RoutingPolicy(policy_version="policy-v1")


class RoutingDecision(BaseModel):
    """One typed INERT recommendation decision (Step 19 output).

    Carries the candidate identity, the closed recommendation kind, the
    dedupe state, the policy version, the gate rationale, the matching
    open-ticket identity (the stable no-match identity for a proven
    no-match), active-custody context, the priority guard, the optional
    locked proposal payload (``None`` for ``report_only`` and
    ``already_present``), alternatives, estimated impact, and the human
    acceptance state (inert until ticket authority accepts).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    candidate_id: StrictStr
    root_cause_fingerprint: StrictStr
    affected_contract: StrictStr
    classifier_version: StrictStr
    recommendation_kind: RecommendationKind
    policy_version: StrictStr
    state: RecommendationState = RecommendationState.NEW
    reason: StrictStr
    #: Locked cross-window proposal key when a proposal was derived (SD3).
    proposal_key: StrictStr | None = None
    #: Matching open-ticket identity, or the stable no-match identity for a
    #: proven no-match; ``None`` for initiative/report-only decisions.
    open_ticket_identity: StrictStr | None = None
    active_custody_present: bool = False
    #: True only when the 100-sample / 10-plan / measured-precision guard
    #: passes; priority effects stay report-only otherwise.
    priority_eligible: bool = False
    priority_guard_reason: StrictStr | None = None
    #: The INERT proposal payload (``None`` for report_only / already_present).
    proposal: DailyEfficiencyProposal | None = None
    alternatives: tuple[RootCauseAlternative, ...] = ()
    estimated_impact: AcceptedOutcomeEconomics | None = None
    #: Proposals are inert until ticket authority accepts them.
    acceptance_state: Literal["pending_human_acceptance"] = "pending_human_acceptance"

    @field_validator(
        "candidate_id",
        "root_cause_fingerprint",
        "affected_contract",
        "classifier_version",
        "policy_version",
        "reason",
    )
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "routing decision identities/versions/reasons must be non-empty strings"
            )
        return value

    @field_validator("open_ticket_identity")
    @classmethod
    def _validate_ticket_identity(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("open_ticket_identity must be a non-empty string when present")
        return value

    @field_validator("proposal_key")
    @classmethod
    def _validate_proposal_key(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("proposal_key must be a non-empty string when present")
        return value

    @model_validator(mode="after")
    def _check_decision_consistency(self) -> RoutingDecision:
        if self.recommendation_kind is RecommendationKind.REPORT_ONLY:
            if self.proposal is not None:
                raise ValueError(
                    "a report_only decision can never carry a proposal payload"
                )
            if self.state is not RecommendationState.NEW:
                raise ValueError("a report_only decision must be in state new")
            if self.proposal_key is not None:
                raise ValueError("a report_only decision can never carry a proposal key")
        if self.state is RecommendationState.ALREADY_PRESENT:
            if self.proposal is not None:
                raise ValueError(
                    "an already_present decision is deduplicated and carries no "
                    "proposal payload (cross-window re-emission never re-appends)"
                )
            if self.proposal_key is None:
                raise ValueError(
                    "an already_present decision must carry the locked proposal key"
                )
        if self.state is RecommendationState.NEW and self.proposal is not None:
            if self.proposal.proposal_key != self.proposal_key:
                raise ValueError(
                    "decision proposal_key must equal the proposal payload's "
                    "locked cross-window key"
                )
        return self


class RoutingResult(BaseModel):
    """Deterministic, sorted collection of inert routing decisions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: Literal["daily_efficiency.v1"] = DAILY_EFFICIENCY_CONTRACT_ID
    decisions: tuple[RoutingDecision, ...] = ()

    @field_validator("decisions")
    @classmethod
    def _sort_decisions(
        cls, value: Sequence[RoutingDecision]
    ) -> tuple[RoutingDecision, ...]:
        return tuple(
            sorted(
                value,
                key=lambda d: (
                    d.candidate_id,
                    d.recommendation_kind.value,
                    d.state.value,
                ),
            )
        )


# ---------------------------------------------------------------------------
# Pure policy gates
# ---------------------------------------------------------------------------


def recommendation_eligible(
    candidate: RootCauseCandidate,
    policy: RoutingPolicy,
) -> tuple[bool, str]:
    """Enforce the versioned coverage / confidence / recurrence gates.

    Returns ``(True, reason)`` when the candidate may become a proposal and
    ``(False, reason)`` otherwise.  Coverage is never fabricated: a missing
    numerator, missing denominator, or zero denominator fails the gate
    closed.  Confidence uses the point estimate when present, otherwise the
    conservative lower bound; an unavailable confidence fails the gate.
    The recurrence gate is the locked 2-in-7-day OR 3-in-30-day signal.
    """
    coverage = candidate.coverage.coverage
    if coverage is None:
        return (
            False,
            "evidence coverage has no exact denominator; coverage is never "
            "fabricated from a missing numerator/denominator",
        )
    if coverage < policy.min_evidence_coverage:
        return (
            False,
            f"evidence coverage {coverage:.4f} below policy minimum "
            f"{policy.min_evidence_coverage}",
        )
    confidence = candidate.confidence.value
    if confidence is None:
        confidence = candidate.confidence.lower_bound
    if confidence is None:
        return False, "cluster confidence is unavailable; no proposal"
    if confidence < policy.min_cluster_confidence:
        return (
            False,
            f"cluster confidence {confidence:.4f} below policy minimum "
            f"{policy.min_cluster_confidence}",
        )
    if not (
        candidate.recurrence_count_7d >= policy.recurrence_min_7d
        or candidate.recurrence_count_30d >= policy.recurrence_min_30d
    ):
        return (
            False,
            f"recurrence signal not satisfied ({candidate.recurrence_count_7d} "
            f"in 7d, {candidate.recurrence_count_30d} in 30d); the locked "
            f"signal requires {policy.recurrence_min_7d}-in-7d or "
            f"{policy.recurrence_min_30d}-in-30d",
        )
    return True, "candidate passes coverage, confidence, and recurrence gates"


def priority_guard_eligible(
    baselines: Sequence[BaselineSnapshot],
    shadow_measures: Sequence[ShadowMeasure],
    policy: RoutingPolicy,
) -> tuple[bool, str | None]:
    """Enforce the 100-sample / 10-plan / measured-precision priority guard.

    A recommendation may affect ticket priority only when the cohort
    baselines prove at least ``priority_min_samples`` completed samples from
    at least ``priority_min_plans`` distinct plans AND a measured shadow
    precision at least ``priority_min_precision`` exists.  Any missing
    evidence (no baselines, no measured precision) keeps priority effects
    report-only — the guard never guesses.
    """
    sample_count = max((baseline.sample_count for baseline in baselines), default=0)
    plan_count = max((baseline.plan_count for baseline in baselines), default=0)
    precision_values = [
        measure.value
        for measure in shadow_measures
        if measure.measure is ShadowMeasureKind.PRECISION and measure.value is not None
    ]
    measured_precision = min(precision_values) if precision_values else None
    if sample_count < policy.priority_min_samples:
        return (
            False,
            f"priority guard: {sample_count} completed samples below "
            f"{policy.priority_min_samples}",
        )
    if plan_count < policy.priority_min_plans:
        return (
            False,
            f"priority guard: {plan_count} distinct plans below "
            f"{policy.priority_min_plans}",
        )
    if measured_precision is None:
        return False, "priority guard: no measured shadow precision available"
    if measured_precision < policy.priority_min_precision:
        return (
            False,
            f"priority guard: measured shadow precision {measured_precision:.4f} "
            f"below {policy.priority_min_precision}",
        )
    return True, None


# ---------------------------------------------------------------------------
# Proposal construction
# ---------------------------------------------------------------------------


def _candidate_ref(candidate: RootCauseCandidate) -> OwnerRef:
    """Locator-only reference to the emitting root-cause candidate."""
    return OwnerRef(
        owner="maintenance",
        record_type="root_cause_candidate",
        identity=candidate.candidate_id,
        schema_version="1",
        locator=f"candidate://{candidate.candidate_id}",
    )


def build_proposal(
    candidate: RootCauseCandidate,
    *,
    proposal_kind: ProposalKind,
    open_ticket_identity: str | None,
    environment: EnvironmentId | str | None,
    window: EventWindow,
    generated_at: UtcTime,
    cluster_ref: OwnerRef,
) -> DailyEfficiencyProposal:
    """Build the locked INERT proposal payload for one eligible candidate.

    The proposal identity is the locked cross-window derivation (SD3) over
    (proposal kind, root-cause fingerprint, affected contract, classifier
    version, open-ticket identity); the window carries no identity weight, so
    the same proposal keeps ONE identity across windows.  ``auto_materialization``
    is locked ``False`` by the contract.  ``cluster_ref``
    is a locator-only reference to the emitting daily cluster (never embedded).
    """
    return DailyEfficiencyProposal(
        proposal_id=derive_proposal_occurrence_id(
            proposal_kind=proposal_kind,
            root_cause_fingerprint=candidate.root_cause_fingerprint,
            affected_contract=candidate.affected_contract,
            classifier_version=candidate.classifier_version,
            open_ticket_identity=open_ticket_identity,
        ),
        proposal_kind=proposal_kind,
        root_cause_fingerprint=candidate.root_cause_fingerprint,
        affected_contract=candidate.affected_contract,
        classifier_version=candidate.classifier_version,
        open_ticket_identity=open_ticket_identity,
        environment=_coerce_environment(environment),
        window=window,
        cluster_ref=cluster_ref,
        candidate_refs=(_candidate_ref(candidate),),
        evidence_refs=candidate.evidence_refs,
        active_custody_refs=candidate.active_custody_refs,
        active_custody_present=bool(candidate.active_custody_refs),
        auto_materialization=False,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Main routing entry point
# ---------------------------------------------------------------------------


def route_recommendations(
    *,
    candidates: Sequence[RootCauseCandidate],
    ticket_read: OpenTicketSnapshotRead,
    policy: RoutingPolicy,
    environment: EnvironmentId | str | None,
    window: EventWindow,
    generated_at: UtcTime,
    cluster_refs: Mapping[str, OwnerRef],
    prior_key_lookup: PriorKeyLookup,
    baselines: Sequence[BaselineSnapshot] = (),
    shadow_measures: Sequence[ShadowMeasure] = (),
    initiative_eligible: InitiativeEligibility | None = None,
) -> RoutingResult:
    """Route deduplicated inert recommendations (Plan Step 19).

    For every candidate the router:

    1. enforces the versioned coverage / confidence / recurrence gates —
       a failing candidate is ``report_only`` and can never become a proposal;
    2. matches the open ticket through the injected read-only snapshot:
       a NON-coherent read (torn / mid-read mutation) is ``report_only``, a
       stable match becomes ``existing_ticket_recommendation``, and a proven
       no-match becomes ``new_ticket_proposal`` (or
       ``initiative_recommendation`` when the injected product gate says so);
    3. derives the locked cross-window proposal key (SD3) and performs the
       injected prior-proposal-key ledger lookup (to be invoked under the
       current resident fence): a committed key turns the decision into
       ``already_present`` — the same proposal never re-appends;
    4. records matching open-ticket identity, active custody, evidence refs,
       rationale, alternatives, estimated impact, the priority guard, and the
       pending human acceptance state.

    The router admits ONLY the explicit read-only capability wrappers
    (:class:`PriorKeyLookup`, optional :class:`InitiativeEligibility`)
    before any candidate is processed.  Opaque callables and
    mutation-capable seams are refused; every returned recommendation is
    typed and inert.
    """
    prior_lookup = _admit_prior_key_lookup(prior_key_lookup)
    initiative_gate = _admit_initiative_eligibility(initiative_eligible)
    env = _coerce_environment(environment)
    priority_eligible, priority_reason = priority_guard_eligible(
        baselines, shadow_measures, policy
    )

    decisions: list[RoutingDecision] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        eligible, gate_reason = recommendation_eligible(candidate, policy)
        if not eligible:
            decisions.append(
                RoutingDecision(
                    candidate_id=candidate.candidate_id,
                    root_cause_fingerprint=candidate.root_cause_fingerprint,
                    affected_contract=candidate.affected_contract,
                    classifier_version=candidate.classifier_version,
                    recommendation_kind=RecommendationKind.REPORT_ONLY,
                    policy_version=policy.policy_version,
                    reason=gate_reason,
                    open_ticket_identity=None,
                    active_custody_present=bool(candidate.active_custody_refs),
                    priority_eligible=priority_eligible,
                    priority_guard_reason=priority_reason,
                    alternatives=candidate.alternatives,
                    estimated_impact=candidate.avoidable_impact,
                )
            )
            continue

        if ticket_read.disposition is not SourceReadDisposition.COHERENT:
            decisions.append(
                RoutingDecision(
                    candidate_id=candidate.candidate_id,
                    root_cause_fingerprint=candidate.root_cause_fingerprint,
                    affected_contract=candidate.affected_contract,
                    classifier_version=candidate.classifier_version,
                    recommendation_kind=RecommendationKind.REPORT_ONLY,
                    policy_version=policy.policy_version,
                    reason=(
                        "open-ticket read is not coherent; a torn or unknown "
                        "read can never authorize a ticket proposal"
                    ),
                    open_ticket_identity=None,
                    active_custody_present=bool(candidate.active_custody_refs),
                    priority_eligible=priority_eligible,
                    priority_guard_reason=priority_reason,
                    alternatives=candidate.alternatives,
                    estimated_impact=candidate.avoidable_impact,
                )
            )
            continue

        if ticket_read.matched:
            kind = RecommendationKind.EXISTING_TICKET_RECOMMENDATION
            proposal_kind = ProposalKind.TICKET
            proposal_ticket_identity = ticket_read.ticket_identity
            decision_ticket_identity = ticket_read.ticket_identity
        elif initiative_gate(candidate):
            kind = RecommendationKind.INITIATIVE_RECOMMENDATION
            proposal_kind = ProposalKind.INITIATIVE
            proposal_ticket_identity = None
            decision_ticket_identity = None
        else:
            kind = RecommendationKind.NEW_TICKET_PROPOSAL
            proposal_kind = ProposalKind.TICKET
            proposal_ticket_identity = None
            decision_ticket_identity = NO_MATCH_TICKET_IDENTITY

        cluster_ref = cluster_refs.get(candidate.candidate_id)
        if cluster_ref is None:
            raise ValueError(
                "a proposal-emitting recommendation requires a locator-only "
                f"cluster reference for candidate {candidate.candidate_id!r}; "
                "proposals are cluster-bound"
            )

        proposal = build_proposal(
            candidate,
            proposal_kind=proposal_kind,
            open_ticket_identity=proposal_ticket_identity,
            environment=env,
            window=window,
            generated_at=generated_at,
            cluster_ref=cluster_ref,
        )
        proposal_key = proposal.proposal_key

        if prior_lookup(proposal_key):
            decisions.append(
                RoutingDecision(
                    candidate_id=candidate.candidate_id,
                    root_cause_fingerprint=candidate.root_cause_fingerprint,
                    affected_contract=candidate.affected_contract,
                    classifier_version=candidate.classifier_version,
                    recommendation_kind=kind,
                    policy_version=policy.policy_version,
                    state=RecommendationState.ALREADY_PRESENT,
                    reason=(
                        "proposal key already committed under the current "
                        "fence; cross-window re-emission is deduplicated"
                    ),
                    proposal_key=proposal_key,
                    open_ticket_identity=decision_ticket_identity,
                    active_custody_present=bool(candidate.active_custody_refs),
                    priority_eligible=priority_eligible,
                    priority_guard_reason=priority_reason,
                    alternatives=candidate.alternatives,
                    estimated_impact=candidate.avoidable_impact,
                )
            )
            continue

        decisions.append(
            RoutingDecision(
                candidate_id=candidate.candidate_id,
                root_cause_fingerprint=candidate.root_cause_fingerprint,
                affected_contract=candidate.affected_contract,
                classifier_version=candidate.classifier_version,
                recommendation_kind=kind,
                policy_version=policy.policy_version,
                state=RecommendationState.NEW,
                reason="candidate passes all gates; inert recommendation emitted",
                proposal_key=proposal_key,
                open_ticket_identity=decision_ticket_identity,
                active_custody_present=bool(candidate.active_custody_refs),
                priority_eligible=priority_eligible,
                priority_guard_reason=priority_reason,
                proposal=proposal,
                alternatives=candidate.alternatives,
                estimated_impact=candidate.avoidable_impact,
            )
        )

    return RoutingResult(decisions=decisions)


__all__ = [
    "DEFAULT_ROUTING_POLICY",
    "InitiativeEligibility",
    "PriorKeyLookup",
    "RecommendationKind",
    "RecommendationState",
    "RoutingAdmissionError",
    "RoutingDecision",
    "RoutingPolicy",
    "RoutingResult",
    "build_proposal",
    "priority_guard_eligible",
    "recommendation_eligible",
    "route_recommendations",
]