"""Single-source policy for automatic review and chain advancement.

This module is deliberately pure.  Normal chain execution, cloud recovery,
watchdog reconciliation, schedulers, status consumers, and compatibility
supervisors must agree on whether a cursor may move without a person.  The
decision never performs the action; the owning path still runs its existing
validation, publication, and completion guards.

Successor gate
--------------
When a chain declares ``successors`` in its spec the completion of the final
milestone does not automatically open the gate for the successor to initialise.
In fail-closed (atomic/enforce) mode the completed chain must carry a validated
acceptance receipt for the final milestone before the successor may proceed.

The gate is generic — it reads the ``require_accepted_transaction`` flag from
each ``SuccessorSpec`` and only blocks when at least one successor requires it
AND the chain is in fail-closed mode.  The first consumer relationship is
M5 → M5A → M6, declared as YAML configuration rather than hardcoded policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .spec import ChainSpec, SuccessorSpec, effective_chain_policy, load_runtime_policy, load_spec


HUMAN_ONLY_STATES = frozenset(
    {
        "awaiting_human",
        "awaiting_human_verify",
        "paused",
        "tiebreaker_pending",
        "tiebreaker_ready",
    }
)


@dataclass(frozen=True)
class AdvancementPolicy:
    merge_policy: str
    clean_milestone_pr: str
    auto_approve: bool
    source: str

    @property
    def automatic_pr_progression(self) -> bool:
        return (
            self.merge_policy == "auto"
            and self.clean_milestone_pr == "auto"
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["automatic_pr_progression"] = self.automatic_pr_progression
        return payload


@dataclass(frozen=True)
class AdvancementDecision:
    action: str
    automatic: bool
    reason: str
    gate: str | None
    policy: AdvancementPolicy

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["policy"] = self.policy.to_dict()
        return payload


def policy_for_spec(
    spec: ChainSpec,
    *,
    runtime_overrides: Mapping[str, Any] | None = None,
) -> AdvancementPolicy:
    effective = effective_chain_policy(spec, dict(runtime_overrides or {}))
    review = effective.get("review_policy") or {}
    return AdvancementPolicy(
        merge_policy=spec.merge_policy,
        clean_milestone_pr=str(review.get("clean_milestone_pr") or "auto"),
        auto_approve=spec.auto_approve,
        source=str(effective.get("source") or "chain_yaml"),
    )


def policy_for_spec_path(spec_path: Path | str) -> AdvancementPolicy:
    path = Path(spec_path)
    spec = load_spec(path)
    return policy_for_spec(spec, runtime_overrides=load_runtime_policy(path))


def check_successor_gate(
    policy: AdvancementPolicy,
    *,
    successors: Sequence[SuccessorSpec] | None = None,
    completion_contract_mode: str = "shadow",
    completed_count: int = 0,
    has_final_acceptance_receipt: bool = False,
    final_milestone_label: str | None = None,
) -> AdvancementDecision | None:
    """Check whether a completed chain's declared successors may be initialised.

    Returns ``None`` when the gate is not applicable (no successors, or the
    chain is not in fail-closed mode).  Returns an ``AdvancementDecision``
    when the gate applies — either ``successor_ready`` (gate open) or
    ``successor_gate_closed`` (blocked until acceptance evidence is present).

    The gate is generic: it reads ``require_accepted_transaction`` from each
    successor declaration.  Hardcoding initiative names (M5, M5A, M6) is NOT
    done here — those relationships are declared in the YAML spec metadata.
    """
    if not successors:
        return None

    # Determine whether ANY declared successor requires an accepted transaction.
    any_require_acceptance = any(
        s.require_accepted_transaction for s in successors
    )
    if not any_require_acceptance:
        return None  # No acceptance requirement — gate is open.

    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        is_fail_closed_mode,
    )

    if not is_fail_closed_mode(completion_contract_mode):
        # Shadow / warn / off — legacy behaviour, gate is always open.
        return None

    # ── fail-closed mode with successors requiring acceptance ──────────
    if completed_count == 0:
        return _decision(
            policy,
            "successor_gate_closed",
            False,
            "chain is complete but successor gate requires acceptance evidence; "
            "no completed milestones found",
            gate="successor_acceptance",
        )

    if not has_final_acceptance_receipt:
        label_hint = f" ({final_milestone_label!r})" if final_milestone_label else ""
        return _decision(
            policy,
            "successor_gate_closed",
            False,
            f"chain is complete but successor gate requires a validated acceptance "
            f"receipt for the final milestone{label_hint}; gate is closed",
            gate="successor_acceptance",
        )

    # Valid evidence present — gate is open.
    return _decision(
        policy,
        "successor_ready",
        True,
        "chain is complete and successor gate is satisfied with acceptance evidence",
    )


def assess_advancement(
    policy: AdvancementPolicy,
    *,
    current_state: str | None,
    chain_last_state: str | None = None,
    chain_complete: bool = False,
    pr_state: str | None = None,
    active_step: bool = False,
    explicit_human_gate: str | None = None,
    failure_kind: str | None = None,
    # ── successor gate parameters (backward-compatible) ──────────────
    successors: Sequence[SuccessorSpec] | None = None,
    completion_contract_mode: str = "shadow",
    completed_count: int = 0,
    has_final_acceptance_receipt: bool = False,
    final_milestone_label: str | None = None,
) -> AdvancementDecision:
    """Classify the next safe owner action without executing it.

    Explicit human gates always win.  A merged PR is different: it is durable
    evidence that the PR gate has already been satisfied, so bookkeeping and
    the next milestone may continue automatically even under manual policy.
    """

    state = str(current_state or "").strip().lower()
    chain_state = str(chain_last_state or "").strip().lower()
    pr = str(pr_state or "").strip().lower()
    failure = str(failure_kind or "").strip().lower()

    if chain_complete:
        # ── successor gate ──────────────────────────────────────────
        successor_decision = check_successor_gate(
            policy,
            successors=successors,
            completion_contract_mode=completion_contract_mode,
            completed_count=completed_count,
            has_final_acceptance_receipt=has_final_acceptance_receipt,
            final_milestone_label=final_milestone_label,
        )
        if successor_decision is not None:
            return successor_decision
        return _decision(policy, "none", False, "chain is complete")
    if explicit_human_gate:
        return _decision(
            policy,
            "await_human",
            False,
            f"explicit human gate remains: {explicit_human_gate}",
            gate=explicit_human_gate,
        )
    if active_step:
        return _decision(
            policy,
            "preserve_live",
            False,
            "active plan step is still running; duplicate execution is forbidden",
        )
    if state in HUMAN_ONLY_STATES:
        return _decision(
            policy,
            "await_human",
            False,
            f"plan state {state} is human-only",
            gate=state,
        )
    if state == "manual_review":
        return _decision(
            policy,
            "await_human",
            False,
            "manual review cursor requires an explicit repair or human resolution",
            gate="manual_review",
        )

    if chain_state == "awaiting_pr_merge":
        if pr == "merged":
            return _decision(
                policy,
                "reconcile_terminal",
                True,
                "merged PR satisfies the review gate; reconcile and continue",
            )
        if policy.automatic_pr_progression:
            return _decision(
                policy,
                "reconcile_pr",
                True,
                "auto merge and clean-milestone review policies permit PR reconciliation",
            )
        gate = (
            "merge_policy"
            if policy.merge_policy != "auto"
            else "review_policy.clean_milestone_pr"
        )
        return _decision(
            policy,
            "await_human",
            False,
            f"{gate} requires human review/merge",
            gate=gate,
        )

    if state in {"done", "complete", "completed", "reviewed"}:
        return _decision(
            policy,
            "reconcile_terminal",
            True,
            "terminal reviewed plan is eligible for guarded chain reconciliation",
        )
    if state == "executed":
        return _decision(
            policy,
            "run_review",
            True,
            "execution completed; automatic review is the next workflow phase",
        )
    if chain_state == "between_milestones":
        if policy.automatic_pr_progression or pr == "merged" or not pr:
            return _decision(
                policy,
                "continue_chain",
                True,
                "prior milestone gate is satisfied; initialize the next milestone",
            )
        return _decision(
            policy,
            "await_human",
            False,
            "manual PR review policy blocks between-milestone continuation",
            gate="review_policy.clean_milestone_pr",
        )
    if (
        state in {"failed", "blocked", "authority_divergence"}
        or chain_state in {"failed", "blocked", "authority_divergence"}
        or failure
    ):
        return _decision(
            policy,
            "repair",
            False,
            f"failure requires guarded repair ({failure or state or 'unknown'})",
        )
    if state in {
        "initialized",
        "prepped",
        "planned",
        "critiqued",
        "gated",
        "finalized",
    }:
        return _decision(
            policy,
            "continue_plan",
            True,
            f"normal workflow continuation from {state}",
        )
    return _decision(
        policy,
        "observe",
        False,
        f"no automatic advancement rule for state {state or chain_state or 'unknown'}",
    )


def _decision(
    policy: AdvancementPolicy,
    action: str,
    automatic: bool,
    reason: str,
    *,
    gate: str | None = None,
) -> AdvancementDecision:
    return AdvancementDecision(
        action=action,
        automatic=automatic,
        reason=reason,
        gate=gate,
        policy=policy,
    )
