"""Autonomy ladder for supervisor-managed runs.

The ladder is intentionally neutral at the supervisor boundary: it decides
when to retry, when to bump run configuration for the next attempt, and when
to request a control transition through the shared control interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from megaplan._core import atomic_write_json
from megaplan.control_interface import (
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlBinding,
    ControlTarget,
    ControlTransitionRequest,
    RunStateView,
    apply_transition,
    read_valid_targets,
)
from megaplan.run_outcome import RunOutcome
from megaplan.supervisor.model import RunNode, SupervisorState
from megaplan.supervisor.state import save_supervisor_state, supervisor_state_root


PROFILE_BUMP_ORDER = ("premium", "apex")
ROBUSTNESS_BUMP_ORDER = ("thorough", "extreme")
DEPTH_BUMP_ORDER = ("high", "max")
DEFAULT_RETRY_LIMIT = 2
APEX_EXTREME_RETRY_LIMIT = 1


class LadderAction(StrEnum):
    """Supervisor ladder actions returned to callers."""

    ADVANCE = "advance"
    RETRY = "retry"
    TRANSITION = "transition"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class SupervisorLadderPolicy:
    """Configuration for bounded retry, bump, and neutral target ordering."""

    retry_limit: int = DEFAULT_RETRY_LIMIT
    apex_extreme_retry_limit: int = APEX_EXTREME_RETRY_LIMIT
    profile_order: tuple[str, ...] = PROFILE_BUMP_ORDER
    robustness_order: tuple[str, ...] = ROBUSTNESS_BUMP_ORDER
    depth_order: tuple[str, ...] = DEPTH_BUMP_ORDER
    max_recovery_transitions_per_target: int = 1
    max_escalation_transitions_per_target: int = 1
    recovery_target_order: tuple[str, ...] = (
        CONTROL_TARGET_RECOVER_FROM_STUCK,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_ABORT,
    )
    escalation_target_order: tuple[str, ...] = (
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_ABORT,
    )


@dataclass(frozen=True)
class LadderDecision:
    """Decision produced by the supervisor ladder."""

    action: LadderAction
    node_id: str
    outcome: RunOutcome
    target_id: str | None = None
    retry_count: int | None = None
    bumped: Mapping[str, str] = field(default_factory=dict)
    transition_accepted: bool | None = None
    transition_mutated: bool | None = None
    transition_reason: str | None = None
    ticket_path: str | None = None
    reason: str | None = None


def apply_ladder(
    *,
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    run_state: RunStateView,
    outcome: RunOutcome,
    plan_dir: Path,
    binding: ControlBinding | str = "megaplan",
    policy: SupervisorLadderPolicy = SupervisorLadderPolicy(),
) -> LadderDecision:
    """Apply one autonomy-ladder step and persist supervisor state.

    The default binding is the canonical ``megaplan`` plugin identity; callers
    pass a concrete ``ControlBinding`` for non-megaplan run types.

    The ladder walks this order:

    * successful outcomes advance the node;
    * blocked outcomes get one bounded neutral recovery transition first;
    * failures retry up to a bounded cap;
    * exhausted retries bump profile, robustness, then depth, one rung per
      failed attempt;
    * exhausted bumps fall through to bounded neutral escalation targets;
    * terminal exhaustion emits a ticket artifact.
    """

    if outcome == RunOutcome.SUCCEEDED:
        if node.node_id not in state.completed_node_ids:
            state.completed_node_ids.append(node.node_id)
        decision = LadderDecision(
            action=LadderAction.ADVANCE,
            node_id=node.node_id,
            outcome=outcome,
            reason="outcome_succeeded",
        )
        _record_ladder_transition(state, decision)
        save_supervisor_state(root, state_id, state)
        return decision

    if outcome == RunOutcome.BLOCKED:
        recovery = _apply_neutral_transition(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            run_state=run_state,
            outcome=outcome,
            plan_dir=plan_dir,
            binding=binding,
            policy=policy,
            recovery=True,
        )
        if recovery is not None:
            return recovery

    retry = _maybe_retry(root, state_id, state, node, outcome, policy)
    if retry is not None:
        return retry

    bump = _maybe_bump(root, state_id, state, node, outcome, policy)
    if bump is not None:
        return bump

    transition = _apply_neutral_transition(
        root=root,
        state_id=state_id,
        state=state,
        node=node,
        run_state=run_state,
        outcome=outcome,
        plan_dir=plan_dir,
        binding=binding,
        policy=policy,
        recovery=False,
    )
    if transition is not None:
        return transition

    return emit_terminal_ticket(
        root=root,
        state_id=state_id,
        state=state,
        node=node,
        outcome=outcome,
        reason="autonomy_ladder_exhausted",
    )


def select_neutral_target(
    run_state: RunStateView,
    binding: ControlBinding | str,
    *,
    recovery: bool,
    policy: SupervisorLadderPolicy = SupervisorLadderPolicy(),
) -> ControlTarget | None:
    """Select the first available neutral target in policy order."""

    projection = read_valid_targets(run_state, binding, recovery=recovery)
    targets_by_id = {target.id: target for target in projection}
    ordered_ids = policy.recovery_target_order if recovery else policy.escalation_target_order
    for target_id in ordered_ids:
        target = targets_by_id.get(target_id)
        if target is not None:
            return target
    return None


def emit_terminal_ticket(
    *,
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    outcome: RunOutcome,
    reason: str,
) -> LadderDecision:
    """Persist a terminal ladder-exhaustion ticket and record it in state."""

    ticket_dir = supervisor_state_root(root) / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = ticket_dir / f"{_safe_fragment(state_id)}-{_safe_fragment(node.node_id)}-terminal.json"
    ticket = {
        "kind": "supervisor_ladder_terminal",
        "state_id": state_id,
        "node_id": node.node_id,
        "outcome": outcome.value,
        "reason": reason,
        "retry_count": _retry_counts(state).get(node.node_id, 0),
        "profile_bump": _string_bucket(state, "profile_bumps").get(node.node_id),
        "robustness_bump": _string_bucket(state, "robustness_bumps").get(node.node_id),
        "depth_bump": _string_bucket(state, "depth_bumps").get(node.node_id),
        "needs": "human attention: supervisor autonomy ladder is exhausted",
    }
    atomic_write_json(ticket_path, ticket)
    tickets = _list_bucket(state, "terminal_tickets")
    tickets.append({"node_id": node.node_id, "path": str(ticket_path), "reason": reason})
    decision = LadderDecision(
        action=LadderAction.TERMINAL,
        node_id=node.node_id,
        outcome=outcome,
        ticket_path=str(ticket_path),
        reason=reason,
    )
    _record_ladder_transition(state, decision)
    save_supervisor_state(root, state_id, state)
    return decision


def bump_one_tier(current: str | None, order: Sequence[str]) -> tuple[str | None, bool]:
    """Return the next rung in ``order`` without guessing unknown custom values."""

    if not order:
        return current, False
    if current is None:
        return order[0], True
    try:
        index = tuple(order).index(current)
    except ValueError:
        return current, False
    if index >= len(order) - 1:
        return current, False
    return order[index + 1], True


def _apply_neutral_transition(
    *,
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    run_state: RunStateView,
    outcome: RunOutcome,
    plan_dir: Path,
    binding: ControlBinding | str,
    policy: SupervisorLadderPolicy,
    recovery: bool,
) -> LadderDecision | None:
    projection = read_valid_targets(run_state, binding, recovery=recovery)
    targets_by_id = {target.id: target for target in projection}
    ordered_ids = policy.recovery_target_order if recovery else policy.escalation_target_order
    target_counts = _transition_counts(state)
    max_count = (
        policy.max_recovery_transitions_per_target
        if recovery
        else policy.max_escalation_transitions_per_target
    )
    target: ControlTarget | None = None
    count_key: str | None = None
    for target_id in ordered_ids:
        candidate = targets_by_id.get(target_id)
        if candidate is None:
            continue
        candidate_count_key = (
            f"{node.node_id}:{'recovery' if recovery else 'escalation'}:{candidate.id}"
        )
        if target_counts.get(candidate_count_key, 0) >= max_count:
            continue
        target = candidate
        count_key = candidate_count_key
        break
    if target is None or count_key is None:
        return None

    result = apply_transition(
        run_state,
        ControlTransitionRequest(
            action="override",
            target_id=target.id,
            reason=f"supervisor ladder {'recovery' if recovery else 'escalation'}",
            source="supervisor_ladder",
        ),
        binding,
        plan_dir=plan_dir,
    )
    target_counts[count_key] = target_counts.get(count_key, 0) + 1
    decision = LadderDecision(
        action=(
            LadderAction.TERMINAL
            if target.id == CONTROL_TARGET_ABORT
            else LadderAction.TRANSITION
        ),
        node_id=node.node_id,
        outcome=outcome,
        target_id=target.id,
        transition_accepted=result.accepted,
        transition_mutated=result.mutated,
        transition_reason=result.reason,
        reason="neutral_recovery_target" if recovery else "neutral_escalation_target",
    )
    _record_ladder_transition(state, decision)
    if decision.action == LadderAction.TERMINAL:
        ticket = emit_terminal_ticket(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            outcome=outcome,
            reason="abort_target_selected",
        )
        return LadderDecision(
            action=LadderAction.TERMINAL,
            node_id=node.node_id,
            outcome=outcome,
            target_id=target.id,
            transition_accepted=result.accepted,
            transition_mutated=result.mutated,
            transition_reason=result.reason,
            ticket_path=ticket.ticket_path,
            reason="abort_target_selected",
        )
    save_supervisor_state(root, state_id, state)
    return decision


def _maybe_retry(
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    outcome: RunOutcome,
    policy: SupervisorLadderPolicy,
) -> LadderDecision | None:
    counts = _retry_counts(state)
    spent = counts.get(node.node_id, 0)
    limit = _retry_limit(node, policy)
    if spent >= limit:
        return None
    counts[node.node_id] = spent + 1
    decision = LadderDecision(
        action=LadderAction.RETRY,
        node_id=node.node_id,
        outcome=outcome,
        retry_count=spent + 1,
        reason="bounded_retry",
    )
    _record_ladder_transition(state, decision)
    save_supervisor_state(root, state_id, state)
    return decision


def _maybe_bump(
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    outcome: RunOutcome,
    policy: SupervisorLadderPolicy,
) -> LadderDecision | None:
    for bucket_name, node_key, order in (
        ("profile_bumps", "profile", policy.profile_order),
        ("robustness_bumps", "robustness", policy.robustness_order),
        ("depth_bumps", "depth", policy.depth_order),
    ):
        bucket = _string_bucket(state, bucket_name)
        current = bucket.get(node.node_id)
        if current is None:
            raw_current = node.metadata.get(node_key)
            current = raw_current if isinstance(raw_current, str) and raw_current else None
        next_value, bumped = bump_one_tier(current, order)
        if not bumped or next_value is None:
            continue
        bucket[node.node_id] = next_value
        _retry_counts(state)[node.node_id] = 0
        decision = LadderDecision(
            action=LadderAction.RETRY,
            node_id=node.node_id,
            outcome=outcome,
            bumped={node_key: next_value},
            reason=f"bump_{node_key}",
        )
        _record_ladder_transition(state, decision)
        save_supervisor_state(root, state_id, state)
        return decision
    return None


def _retry_limit(node: RunNode, policy: SupervisorLadderPolicy) -> int:
    profile = node.metadata.get("profile")
    robustness = node.metadata.get("robustness")
    if profile == "apex" or robustness == "extreme":
        return policy.apex_extreme_retry_limit
    return policy.retry_limit


def _record_ladder_transition(state: SupervisorState, decision: LadderDecision) -> None:
    transitions = _list_bucket(state, "ladder_transitions")
    entry: dict[str, Any] = {
        "action": decision.action.value,
        "node_id": decision.node_id,
        "outcome": decision.outcome.value,
        "reason": decision.reason,
    }
    if decision.target_id is not None:
        entry["target_id"] = decision.target_id
    if decision.retry_count is not None:
        entry["retry_count"] = decision.retry_count
    if decision.bumped:
        entry["bumped"] = dict(decision.bumped)
    if decision.transition_accepted is not None:
        entry["transition_accepted"] = decision.transition_accepted
        entry["transition_mutated"] = decision.transition_mutated
        entry["transition_reason"] = decision.transition_reason
    if decision.ticket_path is not None:
        entry["ticket_path"] = decision.ticket_path
    transitions.append(entry)


def _retry_counts(state: SupervisorState) -> dict[str, int]:
    raw = state.metadata.setdefault("retry_counts", {})
    if not isinstance(raw, dict):
        raw = {}
        state.metadata["retry_counts"] = raw
    normalized: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(key, str):
            try:
                normalized[key] = int(value)
            except (TypeError, ValueError):
                continue
    if normalized != raw:
        raw.clear()
        raw.update(normalized)
    return raw  # type: ignore[return-value]


def _transition_counts(state: SupervisorState) -> dict[str, int]:
    raw = state.metadata.setdefault("transition_counts", {})
    if not isinstance(raw, dict):
        raw = {}
        state.metadata["transition_counts"] = raw
    return raw  # type: ignore[return-value]


def _string_bucket(state: SupervisorState, key: str) -> dict[str, str]:
    raw = state.metadata.setdefault(key, {})
    if not isinstance(raw, dict):
        raw = {}
        state.metadata[key] = raw
    return raw  # type: ignore[return-value]


def _list_bucket(state: SupervisorState, key: str) -> list[dict[str, Any]]:
    raw = state.metadata.setdefault(key, [])
    if not isinstance(raw, list):
        raw = []
        state.metadata[key] = raw
    return raw  # type: ignore[return-value]


def _safe_fragment(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-") or "run"


__all__ = [
    "APEX_EXTREME_RETRY_LIMIT",
    "DEFAULT_RETRY_LIMIT",
    "DEPTH_BUMP_ORDER",
    "LadderAction",
    "LadderDecision",
    "PROFILE_BUMP_ORDER",
    "ROBUSTNESS_BUMP_ORDER",
    "SupervisorLadderPolicy",
    "apply_ladder",
    "bump_one_tier",
    "emit_terminal_ticket",
    "select_neutral_target",
]
