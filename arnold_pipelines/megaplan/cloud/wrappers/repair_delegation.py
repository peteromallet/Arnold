"""Typed repair delegation shim (Step 38).

Provides a minimal typed delegation contract and wrapper-oriented adapter
so that wrappers, controller APIs, terminal audit, live watchdog, enqueue
producers, operator triggers, and materializers all funnel through a single
delegation surface.  Every path either:

* delegates to ``simple_fixer`` (CanonicalRunner with occurrence identity), or
* emits typed zero-authority rejection without child fanout.

The shim never derives authority from labels, liveness, WBC receipts, or
rebuildable projections, and never spawns a child agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar, Mapping

from arnold_pipelines.megaplan.cloud.simple_fixer import (
    SimpleFixerAction,
    SimpleFixerClaimResult,
    SimpleFixerOccurrence,
    SimpleFixerSession,
    build_canonical_runner,
    claim_singleton_occurrence,
    guard_no_child_agent,
    release_singleton_occurrence_claim,
)
from arnold_pipelines.megaplan.custody.contracts import (
    Contract,
    ContractError,
    CustodyTargetKey,
    F01_REPAIR_OCCURRENCE_FIELDS,
)

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

REPAIR_DELEGATION_SCHEMA_VERSION: int = 1

# Closed delegation-outcome vocabulary.  Every delegation attempt returns
# one of these typed outcomes so callers branch on a finite set.
RepairDelegationOutcome = (
    "delegated",               # successfully delegated to simple_fixer
    "zero_authority_rejected", # cannot build exact-occurrence identity
    "no_child_agent_rejected", # caller requested child fan-out
    "delegation_failed",       # simple_fixer rejected the mutation
    "invalid_caller",          # caller context is invalid/insufficient
)

REPAIR_DELEGATION_OUTCOMES: tuple[str, ...] = RepairDelegationOutcome

# Closed caller-kind vocabulary.  Every delegation MUST declare one of
# these kinds so audits can trace which caller family produced a result.
CallerKind = (
    "wrapper",
    "controller",
    "terminal_audit",
    "live_watchdog",
    "enqueue_producer",
    "operator_trigger",
    "materializer",
)

CALLER_KINDS: tuple[str, ...] = CallerKind


# ═══════════════════════════════════════════════════════════════════════════
# Delegation contract
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RepairDelegation(Contract):
    """Typed repair-delegation contract.

    A delegation binds a caller context to an exact occurrence identity
    and funnels the request through the canonical ``simple_fixer`` path.
    The contract never spawns a child agent and never derives authority
    from labels, liveness, WBC receipts, or rebuildable projections.
    """

    contract_type: ClassVar[str] = "repair_delegation"
    schema_version: ClassVar[int] = REPAIR_DELEGATION_SCHEMA_VERSION

    caller_kind: str
    caller_id: str
    target: CustodyTargetKey
    repair_identity: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.caller_kind not in CALLER_KINDS:
            raise ContractError(
                f"unknown caller kind {self.caller_kind!r}; "
                f"must be one of {CALLER_KINDS}"
            )
        if not self.caller_id or not self.caller_id.strip():
            raise ContractError("caller_id must be non-empty")
        if not isinstance(self.target, CustodyTargetKey):
            raise ContractError("target must be a CustodyTargetKey")
        # Reject authority derived from a label, liveness signal, WBC
        # receipt, or rebuildable projection: every F01 field must be a
        # non-empty string — a partial tuple cannot become a delegation.
        for name in F01_REPAIR_OCCURRENCE_FIELDS:
            value = getattr(self.target, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractError(
                    "delegation requires the exact F01 tuple; "
                    f"field {name!r} is empty — authority may not be "
                    "derived from a label, liveness signal, WBC receipt, "
                    "or rebuildable projection"
                )
        if self.repair_identity is not None:
            from arnold_pipelines.megaplan.cloud.repair_requests import (
                normalize_repair_identity,
            )

            normalized = normalize_repair_identity(self.repair_identity)
            if normalized is None:
                raise ContractError("delegation repair identity is not current")
            occurrence = normalized.get("occurrence")
            if not isinstance(occurrence, Mapping) or occurrence.get("target") != self.target.to_dict():
                raise ContractError("delegation target disagrees with repair identity")
            object.__setattr__(self, "repair_identity", normalized)

    @property
    def occurrence(self) -> SimpleFixerOccurrence:
        """The exact occurrence identity this delegation targets."""
        return SimpleFixerOccurrence(
            target=self.target,
            repair_identity=self.repair_identity,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "caller_kind": self.caller_kind,
            "caller_id": self.caller_id,
            "target": dict(self.target.to_dict()),
        }
        if self.repair_identity is not None:
            result["repair_identity"] = dict(self.repair_identity)
        return result


# ═══════════════════════════════════════════════════════════════════════════
# Delegation result
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RepairDelegationResult:
    """Typed result of a repair-delegation attempt."""

    outcome: str
    delegation: RepairDelegation | None = None
    occurrence_fingerprint: str = ""
    simple_fixer_outcome: str = ""
    evidence: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.outcome not in REPAIR_DELEGATION_OUTCOMES:
            raise ContractError(
                f"unknown delegation outcome {self.outcome!r}"
            )

    @property
    def delegated(self) -> bool:
        return self.outcome == "delegated"

    @property
    def rejected(self) -> bool:
        return self.outcome != "delegated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "delegated": self.delegated,
            "occurrence_fingerprint": self.occurrence_fingerprint,
            "simple_fixer_outcome": self.simple_fixer_outcome,
            "evidence": self.evidence or {},
        }


# ═══════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════


def build_repair_delegation(
    caller_kind: str,
    caller_id: str,
    target: CustodyTargetKey | Mapping[str, Any] | None,
) -> RepairDelegation | None:
    """Build a :class:`RepairDelegation` or ``None`` for invalid input.

    Returns ``None`` (does not raise) when the target cannot satisfy the
    exact F01 tuple requirements, so a forbidden authority source (label,
    liveness signal, WBC receipt, rebuildable projection) simply fails to
    produce a delegation rather than raising.
    """
    if not caller_kind or caller_kind not in CALLER_KINDS:
        return None
    if not caller_id or not caller_id.strip():
        return None
    if isinstance(target, CustodyTargetKey):
        key = target
        repair_identity = None
    elif isinstance(target, Mapping):
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            normalize_repair_identity,
        )
        from arnold_pipelines.megaplan.custody.contracts import (
            build_custody_target_key,
            normalize_custody_target_key,
        )

        repair_identity = normalize_repair_identity(target)
        if repair_identity is not None:
            occurrence = repair_identity.get("occurrence")
            key = normalize_custody_target_key(
                occurrence.get("target") if isinstance(occurrence, Mapping) else None
            )
        else:
            key = build_custody_target_key(
                **{name: target.get(name, "") for name in F01_REPAIR_OCCURRENCE_FIELDS}
            )
    else:
        return None
    if key is None:
        return None
    try:
        return RepairDelegation(
            caller_kind=caller_kind,
            caller_id=caller_id,
            target=key,
            repair_identity=repair_identity,
        )
    except ContractError:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Delegation adapter — the single funnel for all caller families
# ═══════════════════════════════════════════════════════════════════════════


def delegate_to_simple_fixer(
    delegation: RepairDelegation,
    *,
    queue_dir: str,
    mutate: Callable[[SimpleFixerOccurrence], str],
    actor: str = "",
    request_id: str = "",
    session_id: str = "",
    kind: str = "immediate_trigger",
    verifier_slot: str = "",
) -> RepairDelegationResult:
    """Delegate a repair action to the canonical ``simple_fixer``.

    This is the **single** delegation path used by wrappers, controllers,
    terminal audit, live watchdog, enqueue producers, operator triggers,
    and materializers.  It:

    1. validates the delegation contract,
    2. builds the exact occurrence identity,
    3. guards against child-agent fan-out,
    4. claims the singleton occurrence through the plural repair-queue API,
    5. runs the mutation through the canonical runner,
    6. releases the claim, and
    7. returns a typed :class:`RepairDelegationResult`.

    The shim never spawns a child agent and never derives authority from
    labels, liveness, WBC receipts, or rebuildable projections.
    """
    if not isinstance(delegation, RepairDelegation):
        return RepairDelegationResult(
            outcome="invalid_caller",
            evidence={"reason": "delegation must be a RepairDelegation instance"},
        )
    if delegation.repair_identity is None:
        return RepairDelegationResult(
            outcome="zero_authority_rejected",
            delegation=delegation,
            evidence={
                "reason": (
                    "delegation requires the current normalized repair identity; "
                    "legacy F01-only delegation is diagnostic only"
                )
            },
        )

    # Gate: no child agent at the delegation layer.
    child_check = guard_no_child_agent()
    if child_check is not None:
        return RepairDelegationResult(
            outcome="no_child_agent_rejected",
            delegation=delegation,
            evidence={"reason": "child-agent fan-out rejected at delegation layer"},
        )

    # Build occurrence identity from the delegation's exact F01 tuple.
    # This is the boundary where forbidden authority sources are rejected:
    # if the delegation target does not satisfy the exact F01 tuple,
    # we emit ``zero_authority_rejected``.
    try:
        occurrence = delegation.occurrence
    except ContractError as exc:
        return RepairDelegationResult(
            outcome="zero_authority_rejected",
            delegation=delegation,
            evidence={"reason": str(exc)},
        )

    fingerprint = occurrence.occurrence_fingerprint

    # Build the canonical runner (one implementation for both immediate
    # trigger and reconciliation paths).
    runner = build_canonical_runner()

    # Claim the singleton occurrence.
    claim = claim_singleton_occurrence(
        queue_dir,
        occurrence,
        actor=actor or delegation.caller_id,
        request_id=request_id or f"delegation-{delegation.caller_id}",
        session=session_id or delegation.caller_id,
    )

    if not claim.claimed:
        return RepairDelegationResult(
            outcome="delegation_failed",
            delegation=delegation,
            occurrence_fingerprint=fingerprint,
            simple_fixer_outcome=claim.outcome,
            evidence={
                "reason": f"claim outcome: {claim.outcome}",
                "claim_evidence": claim.evidence,
            },
        )

    # Build the session and action, then run through the canonical runner.
    session = SimpleFixerSession(occurrence=occurrence, claim=claim)
    action = SimpleFixerAction(mutate=mutate)

    try:
        sf_outcome, receipt = runner.run(
            occurrence,
            action,
            kind=kind,
            session=session,
            verifier_slot=verifier_slot,
        )
    finally:
        release_singleton_occurrence_claim(queue_dir, occurrence)

    # Truth firewall: only a material mutation attempt is delegated. A no-op
    # or exhausted budget is evidence that no repair authority was consumed;
    # callers must not turn either state into a dispatch claim.
    if sf_outcome in ("attempted", "adopted"):
        ledger_record = getattr(session, "last_reservation", None)
        return RepairDelegationResult(
            outcome="delegated",
            delegation=delegation,
            occurrence_fingerprint=fingerprint,
            simple_fixer_outcome=sf_outcome,
            evidence={
                "simple_fixer_outcome": sf_outcome,
                "receipt": receipt.to_dict() if receipt else None,
                "effect_ledger": (
                    {
                        "repair_identity_key": ledger_record.repair_identity_key,
                        "state": ledger_record.state,
                        "reservation_id": ledger_record.reservation_id,
                        "total_attempts": ledger_record.total_attempts,
                        "unchanged_attempts": ledger_record.unchanged_attempts,
                        "effect_outcome": ledger_record.effect_outcome,
                    }
                    if ledger_record is not None
                    else None
                ),
            },
        )

    ledger_record = getattr(session, "last_reservation", None)
    return RepairDelegationResult(
        outcome="delegation_failed",
        delegation=delegation,
        occurrence_fingerprint=fingerprint,
        simple_fixer_outcome=sf_outcome,
        evidence={
            "reason": f"simple_fixer did not authorize an effect: {sf_outcome}",
            "simple_fixer_outcome": sf_outcome,
            "effect_ledger": (
                {
                    "repair_identity_key": ledger_record.repair_identity_key,
                    "state": ledger_record.state,
                    "reservation_id": ledger_record.reservation_id,
                    "total_attempts": ledger_record.total_attempts,
                    "unchanged_attempts": ledger_record.unchanged_attempts,
                    "effect_outcome": ledger_record.effect_outcome,
                }
                if ledger_record is not None
                else None
            ),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# Owner-adoption exact-occurrence consumer (T-0640 D2 / G14 round 3)
# ═══════════════════════════════════════════════════════════════════════════
#
# An owner-boundary-adoption identity carries NO F01 tuple — its occurrence
# identity is the deterministic adoption digest and its authority is the
# OPERATOR's live occurrence-join claim (T-0101e' scope).  The generic F01
# path above MUST keep rejecting it (zero_authority_rejected, fail closed),
# so the exact-occurrence consumer is a SIBLING entry point: it runs the
# SAME canonical simple_fixer runner and the SAME queue-root ``mkdir`` claim
# primitive under the LIVE join claim, keyed by the join claim/lease id —
# never by a fabricated F01 fingerprint.
#
# The consumer never derives authority from a label, a liveness signal, a
# WBC receipt, or a rebuildable projection.  The live join claim (in-flight
# WBC ``kind=occurrence_join`` STARTED + an unexpired plan-scoped custody
# lease covering the occurrence, plus the accepted owner-adoption
# request/decision) IS the custody, and every check fails closed.


@dataclass(frozen=True)
class OwnerAdoptedOccurrence:
    """Exact owner-adoption occurrence identity (digest-based, not F01).

    Wraps the normalized owner-boundary-adoption envelope.  The occurrence
    fingerprint is the deterministic adoption digest
    (:func:`~arnold_pipelines.megaplan.cloud.repair_requests.owner_adoption_identity_key`),
    never an F01 fingerprint, and the claim key is derived from the live
    join claim (lease/claim id).  Construction refuses a non-normalized
    envelope or an empty claim key, so the digest identity can never be
    confused with an exact F01 occurrence.
    """

    contract_type: ClassVar[str] = "owner_adopted_blocked_occurrence"
    schema_version: ClassVar[int] = 1

    repair_identity: Mapping[str, Any]
    claim_key: str = ""

    def __post_init__(self) -> None:
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            normalize_owner_adoption_identity,
            owner_adoption_identity_key,
        )

        normalized = normalize_owner_adoption_identity(self.repair_identity)
        if normalized is None:
            raise ContractError(
                "owner-adopted occurrence requires the normalized "
                "owner_boundary_adoption identity envelope"
            )
        if not owner_adoption_identity_key(normalized):
            raise ContractError("owner-adopted occurrence identity key is empty")
        claim_key = str(self.claim_key or "").strip()
        if not claim_key:
            raise ContractError(
                "owner-adopted occurrence requires a lease-derived claim key"
            )
        object.__setattr__(self, "repair_identity", normalized)
        object.__setattr__(self, "claim_key", claim_key)

    @property
    def authoritative(self) -> bool:
        """The owner-adoption envelope is the authority-bearing identity."""
        return True

    @property
    def occurrence_fingerprint(self) -> str:
        """Deterministic digest-based occurrence identity (not an F01 tuple)."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            owner_adoption_identity_key,
        )

        return owner_adoption_identity_key(self.repair_identity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "identity_kind": "owner_boundary_adoption",
            "occurrence_fingerprint": self.occurrence_fingerprint,
            "claim_key": self.claim_key,
        }


@dataclass
class OwnerAdoptedFixerSession:
    """Runner-compatible fixer session for ONE owner-adopted occurrence.

    The canonical runner gates on ``has_claim`` and ``attempt_mutation``.
    Unlike the F01 :class:`SimpleFixerSession` — whose durable effect
    ledger is keyed by normalized F01 repair identities and therefore
    cannot key the adoption envelope — this session enforces the SAME
    no-child-agent and claim-held boundaries and runs the mutation through
    the SAME canonical runner.  The mutation budget for this path is the
    live, expiring occurrence-join claim plus the lease-derived singleton
    claim, not the F01 effect ledger.
    """

    occurrence: OwnerAdoptedOccurrence
    claim: SimpleFixerClaimResult | None = None
    last_reservation: Any = None
    post_mutation_fingerprint: str = ""

    @property
    def has_claim(self) -> bool:
        return self.claim is not None and self.claim.claimed

    def attempt_mutation(
        self,
        action: SimpleFixerAction,
        *,
        requests_child_agent: bool = False,
        child_agent_count: int = 0,
        after_fingerprint: str | None = None,
    ) -> str:
        """Apply a gated owner-adoption mutation and return its outcome.

        ``after_fingerprint`` lets the caller supply the post-mutation
        occurrence-state fingerprint directly; when ``None`` the action's
        callable is invoked and its return value is used.
        """

        verdict = guard_no_child_agent(
            requests_child_agent=requests_child_agent,
            child_agent_count=child_agent_count,
        )
        if verdict is not None:
            return verdict
        if not self.occurrence.authoritative:
            return "rejected_identity"
        if not self.has_claim:
            return "rejected_no_claim"
        try:
            if after_fingerprint is None:
                after_fingerprint = action.mutate(self.occurrence)
        except Exception:
            # The callable may have performed its external effect before the
            # exception became visible; never convert ambiguity into an
            # ordinary retryable failure.
            return "indeterminate"
        if not isinstance(after_fingerprint, str) or not after_fingerprint.strip():
            return "indeterminate"
        self.post_mutation_fingerprint = after_fingerprint
        return "attempted"


def _latest_decision_for_request(
    queue_dir: str | Path,
    request_id: str,
) -> dict[str, Any] | None:
    """Return the latest decision for *request_id* (None on absence/tie).

    Mirrors occurrence_join: decisions carry second-resolution ``created_at``
    with no monotonic sequence, so a same-second tie is ambiguous and must
    never authorize a stale acceptance (fail closed).
    """
    from arnold_pipelines.megaplan.cloud import repair_requests

    candidates = [
        dict(record)
        for record in repair_requests.iter_repair_decisions(queue_dir)
        if str(record.get("request_id") or "").strip() == str(request_id or "").strip()
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda record: (
            str(record.get("created_at") or ""),
            str(record.get("decision_id") or ""),
        )
    )
    latest_created_at = str(candidates[-1].get("created_at") or "").strip()
    tied = [
        candidate
        for candidate in candidates
        if str(candidate.get("created_at") or "").strip() == latest_created_at
    ]
    if len(tied) > 1:
        return None
    return tied[0]


def verify_owner_adoption_join_claim(
    *,
    workspace: str | Path,
    plan_name: str,
    occurrence_id: str,
    queue_dir: str | Path | None = None,
    request_id: str = "",
    expected_identity_key: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Verify the LIVE occurrence-join claim covering an adopted occurrence.

    Fail closed (``(False, verdict)``) unless ALL of the following hold:

    1. when *queue_dir* and *request_id* are given: the owner-adoption
       request exists with a valid owner-adopted request contract whose
       ``repair_identity_key`` matches *expected_identity_key*, and its
       LATEST decision is ``accepted`` (a same-second tie is ambiguous and
       fails closed);
    2. the plan-scoped WBC ledger holds an IN-FLIGHT ``STARTED`` claim
       attempt with ``kind=occurrence_join`` covering *occurrence_id*;
    3. the plan-scoped custody lease store holds an UNEXPIRED lease whose
       history records *occurrence_id* (returned as ``lease_id``), with the
       join ``claim_id`` read from the covering WBC/lease payload.

    The returned verdict carries ``ok`` plus every discovered id; on failure
    it carries the first failing ``reason``.  Authority is NEVER derived
    from labels, liveness, WBC receipts, or rebuildable projections — the
    live join claim IS the authorized custody for an adopted occurrence.
    """
    verdict: dict[str, Any] = {"ok": False}
    occurrence_id = str(occurrence_id or "").strip()
    if not occurrence_id:
        verdict["reason"] = "occurrence_id required"
        return False, verdict

    if queue_dir is not None and str(request_id or "").strip():
        from arnold_pipelines.megaplan.cloud import repair_requests

        request = None
        for record in repair_requests.iter_repair_requests(queue_dir):
            if str(record.get("request_id") or "").strip() != str(request_id or "").strip():
                continue
            if not repair_requests.has_owner_adopted_repair_request_contract(record):
                continue
            request = record
            break
        if request is None:
            verdict["reason"] = "owner-adoption request not found in queue root"
            return False, verdict
        recorded_key = str(request.get("repair_identity_key") or "").strip()
        if expected_identity_key and recorded_key != str(expected_identity_key or "").strip():
            verdict["reason"] = "repair identity key mismatch"
            return False, verdict
        latest = _latest_decision_for_request(queue_dir, request_id)
        if latest is None:
            verdict["reason"] = "no latest decision for owner-adoption request"
            return False, verdict
        if str(latest.get("decision") or "").strip() != "accepted":
            verdict["reason"] = "latest owner-adoption decision is not accepted"
            return False, verdict
        verdict["request_id"] = str(request_id or "").strip()
        verdict["decision_id"] = str(latest.get("decision_id") or "").strip()

    plan = str(plan_name or "").strip()
    if not plan:
        verdict["reason"] = "plan name required"
        return False, verdict
    plan_dir = Path(workspace) / ".megaplan" / "plans" / plan

    # 2 — in-flight WBC STARTED kind=occurrence_join covering the occurrence.
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.execution_attempt_ledger import AttemptEventType
    from arnold_pipelines.megaplan.custody.phase_wbc import PHASE_WBC_LEDGER_FILENAME

    wbc_live = False
    wbc_claim_id = ""
    wbc_path = plan_dir / PHASE_WBC_LEDGER_FILENAME
    if wbc_path.is_file():
        try:
            store = SqliteAttemptLedgerStore(wbc_path)
            for attempt_id in store.list_in_flight_attempts():
                events = store.read_events(attempt_id)
                started = next(
                    (
                        event
                        for event in events
                        if event.event_type == AttemptEventType.STARTED
                    ),
                    None,
                )
                if started is None:
                    continue
                payload = (
                    started.payload if isinstance(started.payload, Mapping) else {}
                )
                if str(payload.get("kind") or "").strip() != "occurrence_join":
                    continue
                if str(payload.get("occurrence_id") or "").strip() != occurrence_id:
                    continue
                wbc_live = True
                wbc_claim_id = str(payload.get("claim_id") or "").strip()
                verdict["wbc_attempt_id"] = attempt_id
                break
        except Exception:
            wbc_live = False
    if not wbc_live:
        verdict["reason"] = "no in-flight WBC occurrence_join claim for occurrence"
        return False, verdict

    # 3 — unexpired custody lease recording the occurrence.
    from arnold_pipelines.megaplan.custody.lease_store import open_lease_store

    lease_live = False
    lease_dir = plan_dir / "custody" / "leases"
    if lease_dir.is_dir():
        try:
            store = open_lease_store(lease_dir)
            for history in sorted(lease_dir.glob("*.history.jsonl")):
                lease_id = history.name.removesuffix(".history.jsonl")
                lease = store.current_lease(lease_id)
                if lease is None or lease.is_expired:
                    continue
                covered = False
                for event in store.load_history(lease_id):
                    payload = (
                        event.payload if isinstance(event.payload, Mapping) else {}
                    )
                    if str(payload.get("occurrence_id") or "").strip() == occurrence_id:
                        covered = True
                        break
                if covered:
                    lease_live = True
                    verdict["lease_id"] = lease_id
                    if not wbc_claim_id:
                        for event in store.load_history(lease_id):
                            payload = (
                                event.payload if isinstance(event.payload, Mapping) else {}
                            )
                            wbc_claim_id = str(payload.get("claim_id") or "").strip()
                            if wbc_claim_id:
                                break
                    break
        except Exception:
            lease_live = False
    if not lease_live:
        verdict["reason"] = "no unexpired custody lease for occurrence"
        return False, verdict

    verdict["ok"] = True
    verdict["occurrence_id"] = occurrence_id
    verdict["claim_id"] = wbc_claim_id
    return True, verdict


def delegate_owner_adopted_occurrence(
    identity: Mapping[str, Any],
    *,
    queue_dir: str | Path,
    workspace: str | Path,
    plan_name: str,
    mutate: Callable[[OwnerAdoptedOccurrence], str],
    actor: str = "",
    request_id: str = "",
    session_id: str = "",
    decision_id: str = "",
    blocker_id: str = "",
    kind: str = "owner_adoption_dispatch",
    verifier_slot: str = "",
) -> RepairDelegationResult:
    """Delegate an OWNER-ADOPTED occurrence to the canonical simple_fixer runner.

    This is the exact-occurrence consumer for the owner-boundary-adoption
    identity (T-0101e' scope).  The owner-adoption envelope carries NO F01
    tuple, so it can never run through :func:`delegate_to_simple_fixer`
    (which requires the exact F01 tuple and would emit
    ``zero_authority_rejected``).  Instead:

    1. the identity is normalized to the digest-based owner-adoption key
       (``subject_occurrence_digest`` / ``repair_identity_key``) — never a
       fabricated F01 fingerprint;
    2. the live join claim is re-verified read-only and fails closed — an
       in-flight WBC ``kind=occurrence_join`` STARTED attempt plus an
       unexpired plan-scoped custody lease covering the occurrence, plus
       the accepted owner-adoption request/decision;
    3. the occurrence is claimed through the SAME queue-root ``mkdir`` lock
       primitive as the F01 path, but keyed by the JOIN claim (lease/claim
       id) — never the F01 singleton fingerprint key;
    4. the mutation runs through the SAME canonical runner
       (:class:`~arnold_pipelines.megaplan.cloud.simple_fixer.CanonicalRunner`),
       the only implementation allowed to execute a simple_fixer mutation;
    5. the claim is released and a typed :class:`RepairDelegationResult` is
       returned.

    The consumer never derives authority from a label, a liveness signal, a
    WBC receipt, or a rebuildable projection: the live join claim IS the
    custody, and every failure mode returns a typed rejection.
    """
    from arnold_pipelines.megaplan.cloud import repair_requests

    normalized = repair_requests.normalize_owner_adoption_identity(identity)
    if normalized is None:
        return RepairDelegationResult(
            outcome="zero_authority_rejected",
            evidence={
                "reason": (
                    "owner-adoption consumer requires the normalized "
                    "owner_boundary_adoption identity envelope"
                ),
                "request_id": request_id,
                "decision_id": decision_id,
                "blocker_id": blocker_id,
            },
        )
    fingerprint = repair_requests.owner_adoption_identity_key(normalized)
    if not fingerprint:
        return RepairDelegationResult(
            outcome="zero_authority_rejected",
            evidence={"reason": "owner-adoption identity key is empty"},
        )

    # Re-verify the LIVE join claim + accepted request/decision (fail closed).
    ok, verdict = verify_owner_adoption_join_claim(
        workspace=workspace,
        plan_name=plan_name,
        occurrence_id=fingerprint,
        queue_dir=queue_dir,
        request_id=request_id,
        expected_identity_key=fingerprint,
    )
    if not ok:
        return RepairDelegationResult(
            outcome="zero_authority_rejected",
            occurrence_fingerprint=fingerprint,
            evidence={
                "reason": (
                    f"live occurrence-join claim not verified: "
                    f"{verdict.get('reason')}"
                ),
                "claim_verdict": verdict,
                "request_id": request_id,
                "decision_id": decision_id,
                "blocker_id": blocker_id,
            },
        )

    # Gate: no child agent at the delegation layer.
    child_check = guard_no_child_agent()
    if child_check is not None:
        return RepairDelegationResult(
            outcome="no_child_agent_rejected",
            evidence={"reason": "child-agent fan-out rejected at delegation layer"},
        )

    lease_id = str(verdict.get("lease_id") or "").strip()
    claim_id = str(verdict.get("claim_id") or "").strip()
    claim_key = f"owner-adoption:{lease_id or claim_id}"
    try:
        occurrence = OwnerAdoptedOccurrence(
            repair_identity=normalized,
            claim_key=claim_key,
        )
    except ContractError as exc:
        return RepairDelegationResult(
            outcome="zero_authority_rejected",
            evidence={"reason": str(exc)},
        )

    # Claim through the SAME queue-root mkdir lock primitive, keyed by the
    # JOIN claim id — never the F01 singleton fingerprint key.
    from arnold_pipelines.megaplan.cloud.repair_lock import (
        acquire_repair_lock,
        release_repair_lock,
    )
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        singleton_occurrence_claim_lock_dir,
    )

    lock_dir = singleton_occurrence_claim_lock_dir(queue_dir, claim_key)
    claim_result = acquire_repair_lock(
        lock_dir,
        session=session_id or actor or "owner-adoption-consumer",
        target_id=claim_key,
        repair_identity=normalized,
        extra={
            "kind": "owner_adoption_consumer_claim",
            "occurrence_fingerprint": fingerprint,
            "lease_id": lease_id,
            "claim_id": claim_id,
            "request_id": request_id,
            "decision_id": decision_id,
        },
    )
    if not claim_result.acquired:
        return RepairDelegationResult(
            outcome="delegation_failed",
            occurrence_fingerprint=fingerprint,
            evidence={
                "reason": f"owner-adoption claim outcome: {claim_result.status}",
                "claim_evidence": claim_result.stale_evidence,
                "claim_key": claim_key,
            },
        )
    claim = SimpleFixerClaimResult(
        outcome="claimed",
        occurrence_fingerprint=fingerprint,
        lock_dir=str(lock_dir),
        owner=claim_result.owner,
        evidence={
            "kind": "owner_adoption_consumer_claim",
            "claim_key": claim_key,
            "lease_id": lease_id,
            "claim_id": claim_id,
        },
    )

    # Run the SAME canonical runner with the real repair mutation.
    runner = build_canonical_runner()
    session = OwnerAdoptedFixerSession(occurrence=occurrence, claim=claim)
    action = SimpleFixerAction(
        mutate=mutate, label="owner_adoption_phase_contract_repair"
    )
    try:
        sf_outcome, receipt = runner.run(
            occurrence,
            action,
            kind=kind,
            session=session,
            verifier_slot=verifier_slot,
        )
    finally:
        release_repair_lock(lock_dir, owner=claim_result.owner)

    common_evidence: dict[str, Any] = {
        "consumer_entered": True,
        "simple_fixer_outcome": sf_outcome,
        "claim_key": claim_key,
        "lease_id": lease_id,
        "claim_id": claim_id,
        "post_mutation_fingerprint": session.post_mutation_fingerprint,
        "receipt": receipt.to_dict() if receipt else None,
    }
    if sf_outcome in ("attempted", "adopted"):
        return RepairDelegationResult(
            outcome="delegated",
            delegation=None,
            occurrence_fingerprint=fingerprint,
            simple_fixer_outcome=sf_outcome,
            evidence=common_evidence,
        )
    return RepairDelegationResult(
        outcome="delegation_failed",
        occurrence_fingerprint=fingerprint,
        simple_fixer_outcome=sf_outcome,
        evidence={
            **common_evidence,
            "reason": f"owner-adoption mutation not authorized: {sf_outcome}",
        },
    )


def emit_zero_authority_rejection(
    caller_kind: str,
    caller_id: str,
    *,
    reason: str = "",
) -> RepairDelegationResult:
    """Emit a typed zero-authority rejection without child fanout.

    This is the path callers use when they **cannot** build a valid
    delegation (e.g., they only have a label, a liveness signal, a WBC
    receipt, or a rebuildable projection).  It returns a typed rejection
    without attempting any mutation and without spawning any child process.
    """
    return RepairDelegationResult(
        outcome="zero_authority_rejected",
        evidence={
            "reason": reason or "insufficient authority to construct exact occurrence",
            "caller_kind": caller_kind,
            "caller_id": caller_id,
        },
    )


__all__ = [
    "CALLER_KINDS",
    "CallerKind",
    "REPAIR_DELEGATION_OUTCOMES",
    "REPAIR_DELEGATION_SCHEMA_VERSION",
    "OwnerAdoptedFixerSession",
    "OwnerAdoptedOccurrence",
    "RepairDelegation",
    "RepairDelegationOutcome",
    "RepairDelegationResult",
    "build_repair_delegation",
    "delegate_owner_adopted_occurrence",
    "delegate_to_simple_fixer",
    "emit_zero_authority_rejection",
    "verify_owner_adoption_join_claim",
]
