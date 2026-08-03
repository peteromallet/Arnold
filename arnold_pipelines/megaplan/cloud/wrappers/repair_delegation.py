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
from typing import Any, Callable, ClassVar, Mapping

from arnold_pipelines.megaplan.cloud.simple_fixer import (
    SimpleFixerAction,
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

    @property
    def occurrence(self) -> SimpleFixerOccurrence:
        """The exact occurrence identity this delegation targets."""
        return SimpleFixerOccurrence(target=self.target)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_type": self.contract_type,
            "schema_version": self.schema_version,
            "caller_kind": self.caller_kind,
            "caller_id": self.caller_id,
            "target": dict(self.target.to_dict()),
        }


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
    elif isinstance(target, Mapping):
        from arnold_pipelines.megaplan.custody.contracts import (
            build_custody_target_key,
        )

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

    # Truth firewall: only a material mutation attempt is delegated.  A no-op
    # or exhausted budget is evidence that no repair authority was consumed;
    # callers must not turn either state into a launch/dispatched claim.
    if sf_outcome == "attempted":
        return RepairDelegationResult(
            outcome="delegated",
            delegation=delegation,
            occurrence_fingerprint=fingerprint,
            simple_fixer_outcome=sf_outcome,
            evidence={
                "simple_fixer_outcome": sf_outcome,
                "receipt": receipt.to_dict() if receipt else None,
            },
        )

    return RepairDelegationResult(
        outcome="delegation_failed",
        delegation=delegation,
        occurrence_fingerprint=fingerprint,
        simple_fixer_outcome=sf_outcome,
        evidence={
            "reason": f"simple_fixer did not authorize an effect: {sf_outcome}",
            "simple_fixer_outcome": sf_outcome,
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
    "RepairDelegation",
    "RepairDelegationOutcome",
    "RepairDelegationResult",
    "build_repair_delegation",
    "delegate_to_simple_fixer",
    "emit_zero_authority_rejection",
]
