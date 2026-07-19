"""Supervisor-backed chain runner.

This runner is the M5d serial orchestration core for chain YAML specs. It
keeps chain parsing/progress in ``megaplan.chain.spec`` and stores neutral
cross-run state under the supervisor state root. Driver outcomes, guarded
blocked recovery, and PR-merge waits are handled here while cloud remains the
long-lived host above this tier.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    read_json,
    resolve_plan_dir,
)
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.advancement import policy_for_spec
from arnold.control.interface import ControlBinding, RunStateView
from arnold.runtime.outcome import RunOutcome
from arnold_pipelines.megaplan.cloud.incident_bridge import (
    append_chain_lifecycle,
    append_dispatch_expired,
)
from arnold_pipelines.megaplan.supervisor.driver import (
    DefaultRunDriver,
    PackRunner,
    RunDriver,
    RunRequest,
)
from arnold_pipelines.megaplan.supervisor.ladder import (
    LadderAction,
    LadderDecision,
    SupervisorLadderPolicy,
    apply_ladder,
)
from arnold_pipelines.megaplan.supervisor.model import (
    DependencyAssertion,
    RunNode,
    RunRecord,
    SupervisorState,
    SupervisorVariantKind,
)
from arnold_pipelines.megaplan.supervisor.outcomes import NormalizedOutcome, normalize_driver_outcome
from arnold_pipelines.megaplan.supervisor.pr_merge import maybe_resolve_pr_merge_wait
from arnold_pipelines.megaplan.supervisor.state import (
    load_supervisor_state,
    save_supervisor_state,
    validate_supervisor_state,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.resolutions import effective_user_action_resolutions
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.user_actions import action_resolution_status
from arnold_pipelines.megaplan.runtime.execution_environment import (
    merge_isolation_evidence,
    resolve_execution_environment,
)
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
    is_fail_closed_mode,
    normalize_contract_mode,
)

SUPERVISOR_DRIVER_ESCALATE_ACTION = "fail"


class ChainMilestonePackRunner:
    """Default adapter from one chain milestone to an initialized plan name."""

    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        metadata = node.metadata
        idea = _metadata_str(metadata, "idea")
        if idea is None:
            raise CliError(
                "invalid_supervisor_chain",
                f"supervisor chain node {node.node_id!r} is missing an idea path",
            )

        # Imported lazily to avoid making megaplan.chain import the supervisor
        # runner before the flag-on CLI route asks for it.
        from arnold_pipelines.megaplan.chain import _init_plan

        return _init_plan(
            root,
            idea,
            robustness=_metadata_str(metadata, "robustness"),
            auto_approve=bool(metadata.get("auto_approve", True)),
            profile=_metadata_str(metadata, "profile"),
            vendor=_metadata_str(metadata, "vendor"),
            depth=_metadata_str(metadata, "depth"),
            critic=_metadata_str(metadata, "critic"),
            deepseek_provider=_metadata_str(metadata, "deepseek_provider"),
            with_prep=bool(metadata.get("with_prep", False)),
            with_feedback=bool(metadata.get("with_feedback", False)),
            prep_clarify=bool(metadata.get("prep_clarify", True)),
            prep_direction=_metadata_str(metadata, "prep_direction"),
            phase_model=[
                item
                for item in metadata.get("phase_model", [])
                if isinstance(item, str)
            ],
            writer=sys.stdout.write,
        )


def run_chain(
    spec_path: Path,
    root: Path,
    *,
    writer=sys.stdout.write,
    driver: RunDriver | None = None,
    pack_runner: PackRunner | None = None,
    binding: ControlBinding | str = "megaplan",
    ladder_policy: SupervisorLadderPolicy = SupervisorLadderPolicy(),
    one: bool = False,
    require_anchor_override: bool | None = None,
    missing_anchor_ack_override: str | None = None,
) -> dict[str, Any]:
    """Execute a chain spec serially in listed order through the supervisor.

    The default binding is the canonical ``megaplan`` plugin identity; chain
    callers inject a concrete binding only for non-megaplan run types.

    Returns the CLI-facing dict shape used by the old chain path, with
    ``status``, ``milestone_results``, and ``events`` available at top level.
    """

    spec_path = Path(spec_path).expanduser().resolve()
    root = Path(root).resolve()
    spec = chain_spec.load_spec(spec_path)
    anchor_requirement = chain_spec.validate_anchor_requirement(
        spec,
        spec_path,
        require_anchor_override=require_anchor_override,
        missing_anchor_ack_override=missing_anchor_ack_override,
    )
    if anchor_requirement.warning:
        writer(f"[supervisor-chain] WARNING: {anchor_requirement.warning}\n")
    chain_spec.validate_paths(spec, root, spec_path=spec_path)
    chain_state = chain_spec.load_chain_state(spec_path)
    env = resolve_execution_environment(
        root=root,
        state={"config": {"project_dir": str(root), "base_branch": spec.base_branch}},
    )
    chain_state.metadata = merge_isolation_evidence(
        chain_state.metadata,
        env,
        phase="supervisor_chain_start",
    )
    chain_spec.save_chain_state(spec_path, chain_state)
    state_id = str(spec_path)
    supervisor_state = _load_or_create_supervisor_state(
        root=root,
        state_id=state_id,
        spec=spec,
    )
    supervisor_state.metadata = merge_isolation_evidence(
        supervisor_state.metadata,
        env,
        phase="supervisor_chain_start",
    )
    driver = driver or DefaultRunDriver()
    pack_runner = pack_runner or ChainMilestonePackRunner()
    events: list[dict[str, Any]] = []
    milestone_results: list[dict[str, Any]] = list(chain_state.completed)

    def event(kind: str, **fields: Any) -> None:
        payload = {"kind": kind, **fields}
        events.append(payload)
        writer(f"[supervisor-chain] {kind}: {json.dumps(fields, sort_keys=True)}\n")

    def _bridge_lifecycle(outcome: str, summary: str, **kwargs: Any) -> None:
        """Best-effort append a chain_lifecycle event to the incident ledger."""
        try:
            append_chain_lifecycle(
                outcome=outcome,
                summary=summary,
                root=root,
                **kwargs,
            )
        except Exception:
            pass

    def _bridge_dispatch_expired(summary: str, **kwargs: Any) -> None:
        """Best-effort append a dispatch_expired event to the incident ledger."""
        try:
            append_dispatch_expired(
                summary=summary,
                root=root,
                **kwargs,
            )
        except Exception:
            pass

    from arnold_pipelines.megaplan.chain.operator_pause import is_paused

    if is_paused(chain_state):
        return _result(
            "paused",
            chain_state,
            supervisor_state,
            milestone_results,
            events,
            spec=spec,
            reason="durable operator pause is active; explicit chain resume required",
        )

    start_index = max(chain_state.current_milestone_index, 0)
    if chain_state.current_milestone_index < 0:
        chain_state.current_milestone_index = 0
        chain_spec.save_chain_state(spec_path, chain_state)

    for index in range(start_index, len(spec.milestones)):
        milestone = spec.milestones[index]
        node = supervisor_state.run_nodes[index]
        _assert_dependencies_completed(node, supervisor_state)
        # ── acceptance gate for dependency completion ─────────────────
        dep_blocker = _check_dependency_acceptance_gate(
            chain_state, spec, node, supervisor_state, writer=writer
        )
        if dep_blocker is not None:
            events.append(dep_blocker)
            chain_spec.save_chain_state(spec_path, chain_state)
            return _result(
                "blocked",
                chain_state,
                supervisor_state,
                milestone_results,
                events,
                spec=spec,
                reason=(
                    f"dependency acceptance gate closed for milestone "
                    f"{milestone.label!r}"
                ),
            )
        supervisor_state.current_node_id = node.node_id
        chain_state.current_milestone_index = index
        chain_spec.save_chain_state(spec_path, chain_state)
        save_supervisor_state(root, state_id, supervisor_state)
        event("milestone_start", label=milestone.label, index=index)
        _bridge_lifecycle(
            "milestone_start",
            f"chain milestone {index}: {milestone.label} started",
            evidence=[{"label": milestone.label, "index": index}],
        )

        while True:
            chain_state = chain_spec.load_chain_state(spec_path)
            if is_paused(chain_state):
                return _result(
                    "paused",
                    chain_state,
                    supervisor_state,
                    milestone_results,
                    events,
                    spec=spec,
                    reason="durable operator pause is active; explicit chain resume required",
                )
            plan_name = chain_state.current_plan_name
            if not plan_name:
                plan_name = pack_runner.prepare_plan(root=root, node=node)
                from arnold_pipelines.megaplan.chain import _attach_chain_anchors_to_plan

                _attach_chain_anchors_to_plan(root, spec_path, plan_name, spec, milestone)
                chain_state.current_plan_name = plan_name
                chain_spec.save_chain_state(spec_path, chain_state)
                event("plan_prepared", label=milestone.label, plan=plan_name)
                _bridge_lifecycle(
                    "plan_prepared",
                    f"plan {plan_name} prepared for milestone {milestone.label}",
                    evidence=[{"label": milestone.label, "plan": plan_name}],
                )
            else:
                raw_state = _plan_raw_state(
                    root,
                    plan_name,
                    NormalizedOutcome(
                        outcome=RunOutcome.BLOCKED,
                        original_status=str(chain_state.last_state or ""),
                        final_state=str(chain_state.last_state or ""),
                        plan=plan_name,
                        iterations=0,
                        reason="resume_probe",
                        last_phase=None,
                    ),
                )
                if _blocked_plan_replay_would_be_redundant(chain_state, raw_state=raw_state):
                    chain_spec.save_chain_state(spec_path, chain_state)
                    return _result(
                        "stopped",
                        chain_state,
                        supervisor_state,
                        milestone_results,
                        events,
                        spec=spec,
                        reason=f"milestone {milestone.label} remains blocked",
                    )

            raw_outcome = driver.drive(_run_request(root, spec, plan_name, writer))
            normalized = normalize_driver_outcome(
                raw_outcome.status,
                plan=raw_outcome.plan,
                final_state=raw_outcome.final_state,
                iterations=raw_outcome.iterations,
                reason=raw_outcome.reason,
                last_phase=raw_outcome.last_phase,
                total_cost_usd=raw_outcome.total_cost_usd,
                cost_cap_usd=raw_outcome.cost_cap_usd,
                context_retries_used=raw_outcome.context_retries_used,
                max_context_retries=raw_outcome.max_context_retries,
                external_retries_used=raw_outcome.external_retries_used,
                max_external_retries=raw_outcome.max_external_retries,
                blocked_retries_used=raw_outcome.blocked_retries_used,
                max_blocked_retries=raw_outcome.max_blocked_retries,
                blocking_reasons=list(raw_outcome.blocking_reasons),
                tier_escalations_used=raw_outcome.tier_escalations_used,
                escalation_tier_pin=raw_outcome.escalation_tier_pin,
            )
            raw_state = _plan_raw_state(root, plan_name, normalized)
            attempt = _attempt_count(supervisor_state, node.node_id) + 1
            supervisor_state.run_records.append(
                _run_record(
                    node=node,
                    attempt=attempt,
                    normalized=normalized,
                    raw_state=raw_state,
                )
            )
            chain_state.last_state = raw_outcome.status
            chain_spec.save_chain_state(spec_path, chain_state)
            save_supervisor_state(root, state_id, supervisor_state)
            event(
                "driver_outcome",
                label=milestone.label,
                plan=plan_name,
                status=raw_outcome.status,
                outcome=normalized.outcome.value,
                attempt=attempt,
            )
            _bridge_lifecycle(
                "driver_outcome",
                f"plan {plan_name} outcome={normalized.outcome.value} status={raw_outcome.status} attempt={attempt}",
                evidence=[
                    {
                        "label": milestone.label,
                        "plan": plan_name,
                        "outcome": normalized.outcome.value,
                        "status": raw_outcome.status,
                        "attempt": attempt,
                    }
                ],
            )

            if (
                normalized.outcome == RunOutcome.BLOCKED
                and _recover_blocked_execute_if_tasks_done(root, plan_name, writer=writer)
            ):
                event(
                    "blocked_execute_recovered",
                    label=milestone.label,
                    plan=plan_name,
                )
                _bridge_lifecycle(
                    "blocked_execute_recovered",
                    f"blocked execute recovered for {plan_name} ({milestone.label})",
                    evidence=[{"label": milestone.label, "plan": plan_name}],
                )
                continue

            run_state = _run_state_view(
                plan_name=plan_name,
                normalized=normalized,
                raw_state=raw_state,
            )
            pr_resolution = maybe_resolve_pr_merge_wait(
                root=root,
                state_id=state_id,
                state=supervisor_state,
                node=node,
                run_state=run_state,
                plan_dir=_plan_dir(root, plan_name),
                binding=binding,
                policy=ladder_policy,
                automatic_pr_progression=policy_for_spec(
                    spec,
                    runtime_overrides=chain_spec.load_runtime_policy(spec_path),
                ).automatic_pr_progression,
                writer=writer,
            )
            if pr_resolution.handled:
                _annotate_latest_run_record(
                    supervisor_state,
                    node_id=node.node_id,
                    pr_number=pr_resolution.pr_number,
                    pr_state=pr_resolution.pr_state,
                )
                save_supervisor_state(root, state_id, supervisor_state)
                event(
                    "pr_merge_resolution",
                    label=milestone.label,
                    plan=plan_name,
                    advanced=pr_resolution.advanced,
                    pr_number=pr_resolution.pr_number,
                    pr_state=pr_resolution.pr_state,
                    reason=pr_resolution.reason,
                )
                _bridge_lifecycle(
                    "pr_merge_resolution",
                    f"PR merge resolution for {plan_name}: advanced={pr_resolution.advanced} pr=#{pr_resolution.pr_number}",
                    evidence=[
                        {
                            "label": milestone.label,
                            "plan": plan_name,
                            "advanced": pr_resolution.advanced,
                            "pr_number": pr_resolution.pr_number,
                            "pr_state": pr_resolution.pr_state,
                        }
                    ],
                )
                if pr_resolution.advanced:
                    # ── acceptance gate before supervisor advance ──────
                    blocker = _check_supervisor_advance_acceptance_gate(
                        chain_state, spec, milestone, writer=writer
                    )
                    if blocker is not None:
                        events.append(blocker)
                        chain_spec.save_chain_state(spec_path, chain_state)
                        return _result(
                            "blocked",
                            chain_state,
                            supervisor_state,
                            milestone_results,
                            events,
                            spec=spec,
                            reason=(
                                f"supervisor advance blocked for milestone "
                                f"{milestone.label!r}: acceptance gate closed"
                            ),
                        )
                    if node.node_id not in supervisor_state.completed_node_ids:
                        supervisor_state.completed_node_ids.append(node.node_id)
                    save_supervisor_state(root, state_id, supervisor_state)
                    decision = pr_resolution.decision or LadderDecision(
                        action=LadderAction.ADVANCE,
                        node_id=node.node_id,
                        outcome=RunOutcome.AWAITING_HUMAN,
                        reason=pr_resolution.reason or "pr_merge_resolution",
                    )
                    authority_shadow = _derive_milestone_authority_shadow(
                        root,
                        plan_name,
                        normalized=normalized,
                        decision=decision,
                    )
                    result = _milestone_result(
                        label=milestone.label,
                        plan=plan_name,
                        normalized=normalized,
                        decision=decision,
                        pr_number=pr_resolution.pr_number,
                        pr_state=pr_resolution.pr_state,
                        authority_shadow=authority_shadow,
                    )
                    if not _completed_contains(chain_state, milestone.label):
                        chain_state.completed.append(result)
                    milestone_results = list(chain_state.completed)
                    chain_state.current_milestone_index = index + 1
                    chain_state.current_plan_name = None
                    chain_state.last_state = "done"
                    chain_spec.save_chain_state(spec_path, chain_state)
                    _bridge_lifecycle(
                        "milestone_complete",
                        f"milestone {milestone.label} completed via PR merge resolution (plan={plan_name})",
                        evidence=[
                            {
                                "label": milestone.label,
                                "plan": plan_name,
                                "pr_number": pr_resolution.pr_number,
                            }
                        ],
                    )
                    if one:
                        return _result(
                            "paused",
                            chain_state,
                            supervisor_state,
                            milestone_results,
                            events,
                            spec=spec,
                            reason=f"completed one milestone: {milestone.label}",
                        )
                    break
                if pr_resolution.decision is not None:
                    event(
                        "ladder_decision",
                        label=milestone.label,
                        action=pr_resolution.decision.action.value,
                        target_id=pr_resolution.decision.target_id,
                        reason=pr_resolution.decision.reason,
                    )
                    _bridge_lifecycle(
                        "ladder_decision",
                        f"ladder decision for {milestone.label}: {pr_resolution.decision.action.value} → {pr_resolution.decision.target_id}",
                        evidence=[
                            {
                                "label": milestone.label,
                                "action": pr_resolution.decision.action.value,
                                "target_id": pr_resolution.decision.target_id,
                            }
                        ],
                    )
                    if pr_resolution.decision.action in {
                        LadderAction.RETRY,
                        LadderAction.TRANSITION,
                    }:
                        chain_state.current_plan_name = None
                        chain_spec.save_chain_state(spec_path, chain_state)
                        continue
                    _bridge_dispatch_expired(
                        f"milestone {milestone.label} stopped by ladder: {pr_resolution.decision.reason or pr_resolution.decision.action.value}",
                        evidence=[
                            {
                                "label": milestone.label,
                                "plan": plan_name,
                                "action": pr_resolution.decision.action.value,
                                "reason": pr_resolution.decision.reason,
                            }
                        ],
                    )
                    return _result(
                        "stopped",
                        chain_state,
                        supervisor_state,
                        milestone_results,
                        events,
                        spec=spec,
                        reason=pr_resolution.decision.reason
                        or f"milestone {milestone.label} stopped",
                    )
            decision = apply_ladder(
                root=root,
                state_id=state_id,
                state=supervisor_state,
                node=node,
                run_state=run_state,
                outcome=normalized.outcome,
                plan_dir=_plan_dir(root, plan_name),
                binding=binding,
                policy=ladder_policy,
            )
            event(
                "ladder_decision",
                label=milestone.label,
                action=decision.action.value,
                target_id=decision.target_id,
                reason=decision.reason,
            )
            _bridge_lifecycle(
                "ladder_decision",
                f"ladder decision for {milestone.label}: {decision.action.value} → {decision.target_id}",
                evidence=[
                    {
                        "label": milestone.label,
                        "action": decision.action.value,
                        "target_id": decision.target_id,
                        "reason": decision.reason,
                    }
                ],
            )

            if decision.action == LadderAction.ADVANCE:
                # ── acceptance gate before supervisor advance ──────────
                blocker = _check_supervisor_advance_acceptance_gate(
                    chain_state, spec, milestone, writer=writer
                )
                if blocker is not None:
                    events.append(blocker)
                    chain_spec.save_chain_state(spec_path, chain_state)
                    return _result(
                        "blocked",
                        chain_state,
                        supervisor_state,
                        milestone_results,
                        events,
                        spec=spec,
                        reason=(
                            f"supervisor advance blocked for milestone "
                            f"{milestone.label!r}: acceptance gate closed"
                        ),
                    )
                authority_shadow = _derive_milestone_authority_shadow(
                    root,
                    plan_name,
                    normalized=normalized,
                    decision=decision,
                )
                result = _milestone_result(
                    label=milestone.label,
                    plan=plan_name,
                    normalized=normalized,
                    decision=decision,
                    authority_shadow=authority_shadow,
                )
                if not _completed_contains(chain_state, milestone.label):
                    chain_state.completed.append(result)
                milestone_results = list(chain_state.completed)
                chain_state.current_milestone_index = index + 1
                chain_state.current_plan_name = None
                chain_state.last_state = raw_outcome.status
                chain_spec.save_chain_state(spec_path, chain_state)
                _bridge_lifecycle(
                    "milestone_complete",
                    f"milestone {milestone.label} completed (plan={plan_name}, outcome={normalized.outcome.value})",
                    evidence=[
                        {
                            "label": milestone.label,
                            "plan": plan_name,
                            "outcome": normalized.outcome.value,
                        }
                    ],
                )
                if one:
                    return _result(
                        "paused",
                        chain_state,
                        supervisor_state,
                        milestone_results,
                        events,
                        spec=spec,
                        reason=f"completed one milestone: {milestone.label}",
                    )
                break

            if decision.action in {LadderAction.RETRY, LadderAction.TRANSITION}:
                chain_state.current_plan_name = None
                chain_spec.save_chain_state(spec_path, chain_state)
                continue

            _bridge_dispatch_expired(
                f"milestone {milestone.label} stopped: {decision.reason or decision.action.value}",
                evidence=[
                    {
                        "label": milestone.label,
                        "plan": plan_name,
                        "action": decision.action.value,
                        "reason": decision.reason,
                    }
                ],
            )
            return _result(
                "stopped",
                chain_state,
                supervisor_state,
                milestone_results,
                events,
                spec=spec,
                reason=decision.reason or f"milestone {milestone.label} stopped",
            )

    supervisor_state.current_node_id = None
    save_supervisor_state(root, state_id, supervisor_state)
    _bridge_lifecycle(
        "chain_done",
        f"chain completed: {len(spec.milestones)} milestones, {len(milestone_results)} results",
        evidence=[{"total_milestones": len(spec.milestones), "completed": len(milestone_results)}],
    )
    return _result("done", chain_state, supervisor_state, milestone_results, events, spec=spec)


def _check_dependency_acceptance_gate(
    chain_state: chain_spec.ChainState,
    spec: chain_spec.ChainSpec,
    node: RunNode,
    supervisor_state: SupervisorState,
    *,
    writer,
) -> dict[str, Any] | None:
    """Check that all completed dependency milestones carry acceptance receipts.

    In fail-closed (atomic/enforce) mode a milestone that depends on another
    completed milestone must verify that the predecessor has a validated
    acceptance receipt before the successor is allowed to start.
    """
    mode = normalize_contract_mode(chain_state.completion_contract_mode)
    if not is_fail_closed_mode(mode):
        return None

    successors = getattr(spec, "successors", None) or []
    if not successors:
        return None

    any_require = any(
        getattr(s, "require_accepted_transaction", True) for s in successors
    )
    if not any_require:
        return None

    completed_ids = set(supervisor_state.completed_node_ids)
    for assertion in supervisor_state.dependency_assertions:
        if assertion.node_id != node.node_id:
            continue
        for dep_id in assertion.depends_on:
            if dep_id not in completed_ids:
                continue  # handled by _assert_dependencies_completed
            if not chain_state.has_acceptance_receipt(dep_id):
                blocker_event: dict[str, Any] = {
                    "kind": "supervisor_dependency_acceptance_gate_closed",
                    "predicate_kind": PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
                    "evidence_kind": "dependency_acceptance",
                    "summary": (
                        f"dependency {dep_id!r} is marked completed but has no "
                        f"validated acceptance receipt; successor milestone "
                        f"{node.node_id!r} is blocked"
                    ),
                    "details": {
                        "node_id": node.node_id,
                        "dependency_id": dep_id,
                        "completion_contract_mode": mode,
                    },
                }
                writer(
                    f"[supervisor-chain] dependency acceptance gate closed: "
                    f"dependency {dep_id!r} has no acceptance receipt; "
                    f"milestone {node.node_id!r} blocked\n"
                )
                return blocker_event
    return None


def _check_supervisor_advance_acceptance_gate(
    chain_state: chain_spec.ChainState,
    spec: chain_spec.ChainSpec,
    milestone: chain_spec.MilestoneSpec,
    *,
    writer,
) -> dict[str, Any] | None:
    """Check the acceptance gate before the supervisor advances a milestone.

    In fail-closed (atomic/enforce) mode a completed milestone that declares
    successors requiring acceptance MUST carry a validated acceptance receipt
    before the supervisor is allowed to advance the chain cursor.

    Returns a typed blocker-event dict when the gate is closed, or ``None``
    when the gate is open / not applicable / not in fail-closed mode.
    """
    mode = normalize_contract_mode(chain_state.completion_contract_mode)
    if not is_fail_closed_mode(mode):
        return None  # shadow / warn / off — gate is always open

    successors = getattr(spec, "successors", None) or []
    if not successors:
        return None  # no declared successors — no gate to check

    any_require = any(
        getattr(s, "require_accepted_transaction", True) for s in successors
    )
    if not any_require:
        return None  # no successor requires acceptance

    has_receipt = chain_state.has_acceptance_receipt(milestone.label)
    if has_receipt:
        return None  # gate is open

    # ── Gate is closed — emit typed blocker event ────────────────────
    blocker_event: dict[str, Any] = {
        "kind": "supervisor_advance_acceptance_gate_closed",
        "predicate_kind": PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
        "evidence_kind": "supervisor_advance",
        "summary": (
            f"supervisor advance blocked for milestone {milestone.label!r}: "
            f"no validated acceptance receipt; declared successors require "
            f"acceptance evidence before advancement"
        ),
        "details": {
            "milestone_label": milestone.label,
            "completion_contract_mode": mode,
            "successor_count": len(successors),
        },
    }
    writer(
        f"[supervisor-chain] acceptance gate closed for milestone "
        f"{milestone.label!r}: no acceptance receipt; advancement blocked\n"
    )
    return blocker_event


def _load_or_create_supervisor_state(
    *,
    root: Path,
    state_id: str,
    spec: chain_spec.ChainSpec,
) -> SupervisorState:
    existing = load_supervisor_state(root, state_id)
    if existing is not None:
        validate_supervisor_state(existing)
        return existing
    nodes = [_node_from_milestone(milestone, index, spec) for index, milestone in enumerate(spec.milestones)]
    state = SupervisorState(
        variant=SupervisorVariantKind.CHAIN,
        run_nodes=nodes,
        dependency_assertions=[
            DependencyAssertion(
                node_id=node.node_id,
                depends_on=tuple(
                    item
                    for item in node.metadata.get("depends_on", [])
                    if isinstance(item, str)
                ),
            )
            for node in nodes
        ],
        metadata={"chain_spec": state_id},
    )
    save_supervisor_state(root, state_id, state)
    return state


def _node_from_milestone(
    milestone: chain_spec.MilestoneSpec,
    index: int,
    spec: chain_spec.ChainSpec,
) -> RunNode:
    metadata = {
        "index": index,
        "label": milestone.label,
        "idea": milestone.idea,
        "branch": milestone.branch,
        "profile": milestone.profile,
        "robustness": milestone.robustness or spec.robustness,
        "vendor": milestone.vendor,
        "depth": milestone.depth,
        "critic": milestone.critic,
        "deepseek_provider": milestone.deepseek_provider,
        "with_prep": milestone.with_prep,
        "with_feedback": milestone.with_feedback,
        "prep_clarify": milestone.prep_clarify,
        "prep_direction": milestone.prep_direction,
        "phase_model": list(milestone.phase_model),
        "bakeoff": milestone.bakeoff,
        "notes": milestone.notes,
        "depends_on": list(milestone.depends_on),
        "auto_approve": spec.auto_approve,
    }
    return RunNode(
        node_id=milestone.label,
        spec_ref=milestone.label,
        description=milestone.notes,
        metadata=metadata,
    )


def _assert_dependencies_completed(node: RunNode, state: SupervisorState) -> None:
    completed = set(state.completed_node_ids)
    for assertion in state.dependency_assertions:
        if assertion.node_id != node.node_id:
            continue
        missing = [dep for dep in assertion.depends_on if dep not in completed]
        if missing:
            raise CliError(
                "invalid_supervisor_state",
                f"chain node {node.node_id!r} has unmet dependencies: {missing}",
            )


def _run_request(
    root: Path,
    spec: chain_spec.ChainSpec,
    plan_name: str,
    writer: Any,
) -> RunRequest:
    return RunRequest(
        root=root,
        plan=plan_name,
        stall_threshold=spec.stall_threshold,
        max_iterations=spec.max_iterations,
        poll_sleep=spec.poll_sleep,
        phase_timeout=spec.phase_timeout,
        status_timeout=spec.status_timeout,
        # The supervisor owns cross-run escalation through the neutral ladder.
        # Do not ask the canonical megaplan auto-driver to perform its old
        # legacy-planning force-proceed action in the flag-on path.
        escalate_action=SUPERVISOR_DRIVER_ESCALATE_ACTION,
        writer=writer,
    )


def _run_record(
    *,
    node: RunNode,
    attempt: int,
    normalized: NormalizedOutcome,
    raw_state: Mapping[str, Any],
) -> RunRecord:
    resume_cursor = raw_state.get("resume_cursor")
    if not isinstance(resume_cursor, dict):
        resume_cursor = None
    return RunRecord(
        node_id=node.node_id,
        attempt=attempt,
        outcome=normalized.outcome,
        original_status=normalized.original_status,
        plan_id=normalized.plan,
        final_state=normalized.final_state,
        current_state=_optional_state_str(raw_state.get("current_state")),
        resume_cursor=dict(resume_cursor) if resume_cursor is not None else None,
        reason=normalized.reason,
        last_phase=normalized.last_phase,
        blocking_reasons=tuple(normalized.blocking_reasons),
        total_cost_usd=normalized.total_cost_usd,
        tier_escalations_used=normalized.tier_escalations_used,
        escalation_tier_pin=normalized.escalation_tier_pin,
        pr_number=_optional_state_int(raw_state.get("pr_number")),
        pr_state=_optional_state_str(raw_state.get("pr_state")),
        metadata={
            "diagnostic_reason": normalized.diagnostic_reason,
            "escalated_diagnostic": normalized.escalated_diagnostic,
            "iterations": normalized.iterations,
            "cost_cap_usd": normalized.cost_cap_usd,
            "context_retries_used": normalized.context_retries_used,
            "max_context_retries": normalized.max_context_retries,
            "external_retries_used": normalized.external_retries_used,
            "max_external_retries": normalized.max_external_retries,
            "blocked_retries_used": normalized.blocked_retries_used,
            "max_blocked_retries": normalized.max_blocked_retries,
        },
    )


def _run_state_view(
    *,
    plan_name: str,
    normalized: NormalizedOutcome,
    raw_state: Mapping[str, Any],
) -> RunStateView:
    resume_cursor = raw_state.get("resume_cursor")
    cursor_kind = None
    if isinstance(resume_cursor, dict):
        for key in ("kind", "wait_kind", "state"):
            value = resume_cursor.get(key)
            if isinstance(value, str) and value:
                cursor_kind = value
                break
    return RunStateView(
        run_id=plan_name,
        outcome=normalized.outcome,
        cursor=raw_state.get("current_state")
        if isinstance(raw_state.get("current_state"), str)
        else normalized.final_state,
        metadata={
            "projection_surface": "supervisor",
            "original_status": normalized.original_status,
            "cursor_kind": cursor_kind,
        },
        raw_state=raw_state,
    )


def _plan_raw_state(
    root: Path,
    plan_name: str,
    normalized: NormalizedOutcome,
) -> dict[str, Any]:
    try:
        state_path = _plan_dir(root, plan_name) / "state.json"
        raw = read_json(state_path)
        if isinstance(raw, dict):
            raw.setdefault("name", plan_name)
            raw.setdefault("current_state", normalized.final_state)
            raw.setdefault("config", {})
            if not isinstance(raw.get("config"), dict):
                raw["config"] = {}
            return raw
    except (CliError, OSError, json.JSONDecodeError):
        pass
    return {
        "name": plan_name,
        "current_state": normalized.final_state or normalized.original_status,
        "config": {},
    }


def _annotate_latest_run_record(
    state: SupervisorState,
    *,
    node_id: str,
    pr_number: int | None,
    pr_state: str | None,
) -> None:
    if not state.run_records:
        return
    latest = state.run_records[-1]
    if latest.node_id != node_id:
        return
    state.run_records[-1] = RunRecord(
        node_id=latest.node_id,
        attempt=latest.attempt,
        outcome=latest.outcome,
        original_status=latest.original_status,
        plan_id=latest.plan_id,
        final_state=latest.final_state,
        current_state=latest.current_state,
        reason=latest.reason,
        last_phase=latest.last_phase,
        resume_cursor=dict(latest.resume_cursor) if latest.resume_cursor is not None else None,
        blocking_reasons=latest.blocking_reasons,
        total_cost_usd=latest.total_cost_usd,
        tier_escalations_used=latest.tier_escalations_used,
        escalation_tier_pin=latest.escalation_tier_pin,
        pr_number=pr_number,
        pr_state=pr_state,
        metadata=dict(latest.metadata),
    )


def _plan_dir(root: Path, plan_name: str) -> Path:
    try:
        return resolve_plan_dir(root, plan_name)
    except CliError:
        return root / ".megaplan" / "plans" / plan_name


def _plan_has_live_active_step(raw_state: Mapping[str, Any]) -> bool:
    active_step = raw_state.get("active_step")
    if not isinstance(active_step, Mapping):
        return False
    return bool(
        active_step.get("phase")
        or active_step.get("worker_pid")
        or active_step.get("pid")
        or active_step.get("session_id")
    )


def _blocked_plan_replay_would_be_redundant(
    chain_state: chain_spec.ChainState,
    *,
    raw_state: Mapping[str, Any],
) -> bool:
    current_state = raw_state.get("current_state")
    if not isinstance(current_state, str):
        return False
    return (
        chain_state.last_state == "blocked"
        and current_state == "blocked"
        and not _plan_has_live_active_step(raw_state)
    )


def _execution_batch_sort_key(path: Path) -> tuple[int, str]:
    match = re.fullmatch(r"execution_batch_(\d+)\.json", path.name)
    if match:
        return (int(match.group(1)), path.name)
    return (-1, path.name)


def _latest_execute_result(plan_dir: Path) -> str | None:
    try:
        state = read_json(plan_dir / "state.json")
    except (CliError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None
    history = state.get("history")
    if not isinstance(history, list):
        return None
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("step") == "execute":
            result = entry.get("result")
            return result if isinstance(result, str) else None
    return None


def _latest_execution_batch_all_tasks_done(plan_dir: Path) -> tuple[bool, str]:
    try:
        state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        state_payload = {}
    config = state_payload.get("config") if isinstance(state_payload, dict) else {}
    raw_project_dir = config.get("project_dir") if isinstance(config, dict) else None
    project_dir = Path(raw_project_dir) if isinstance(raw_project_dir, str) and raw_project_dir else None
    batches = sorted(
        list_batch_artifacts(plan_dir),
        key=_execution_batch_sort_key,
    )
    if not batches:
        return False, "no execution_batch_*.json artifact found"
    latest = batches[-1]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, f"{latest.name} could not be read: {error}"
    if not isinstance(payload, dict):
        return False, f"{latest.name} payload is not an object"

    task_records: list[dict[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw_records = payload.get(key)
        if isinstance(raw_records, list):
            task_records.extend(item for item in raw_records if isinstance(item, dict))
    if not task_records:
        return False, f"{latest.name} has no task records"

    decisions: dict[str, Any] = {}
    completed = effective_execute_completed_task_ids(
        task_records,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state_payload,
        decisions=decisions,
    )
    pending: list[str] = []
    for task in task_records:
        task_id = str(task.get("task_id") or task.get("id") or "?")
        if task_id in completed:
            continue
        decision = decisions.get(task_id)
        authority_status = getattr(getattr(decision, "status", None), "value", None)
        if authority_status is None:
            authority_status = "unknown"
        raw_status = task.get("status")
        pending.append(f"{task_id}={raw_status!r}:authority={authority_status}")
    if pending:
        return False, f"{latest.name} has uncorroborated tasks: {', '.join(pending)}"
    finalize_path = plan_dir / "finalize.json"
    if finalize_path.exists():
        try:
            finalize_payload = json.loads(finalize_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return False, f"finalize.json could not be read: {error}"
        finalize_tasks = (
            finalize_payload.get("tasks")
            if isinstance(finalize_payload, dict)
            else None
        )
        if isinstance(finalize_tasks, list) and finalize_tasks:
            finalize_records = [
                task for task in finalize_tasks if isinstance(task, dict)
            ]
            filtered_finalize_records: list[dict[str, Any]] = []
            batch_task_ids = {
                str(task.get("task_id") or task.get("id") or "")
                for task in task_records
                if isinstance(task, dict)
            }
            for task in finalize_records:
                task_id = str(task.get("task_id") or task.get("id") or "")
                if task_id and task_id in batch_task_ids:
                    filtered_finalize_records.append(task)
                    continue
                if task.get("status") != "pending":
                    filtered_finalize_records.append(task)
                    continue
                if any(
                    task.get(field)
                    for field in (
                        "files_changed",
                        "commands_run",
                        "evidence_files",
                        "sections_written",
                        "evidence",
                        "head_sha",
                    )
                ):
                    filtered_finalize_records.append(task)
            finalize_records = filtered_finalize_records
            finalize_decisions: dict[str, Any] = {}
            finalize_completed = effective_execute_completed_task_ids(
                finalize_records,
                plan_dir=plan_dir,
                project_dir=project_dir,
                state=state_payload,
                decisions=finalize_decisions,
            )
            pending = []
            for task in finalize_records:
                task_id = str(task.get("task_id") or task.get("id") or "?")
                if task_id in finalize_completed:
                    continue
                decision = finalize_decisions.get(task_id)
                authority_status = getattr(getattr(decision, "status", None), "value", None)
                if authority_status is None:
                    authority_status = "unknown"
                raw_status = task.get("status")
                pending.append(f"{task_id}={raw_status!r}:authority={authority_status}")
            if pending:
                return False, f"finalize.json has uncorroborated tasks: {', '.join(pending)}"
    return True, latest.name


def _mark_blocked_execute_as_executed(plan_dir: Path) -> None:
    def _patch_blocked_execute(current: dict[str, Any]) -> bool:
        current.pop("active_step", None)
        current.pop("latest_failure", None)
        current.pop("resume_cursor", None)
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": "executed"},
        mutation=_patch_blocked_execute,
    )


def _has_unresolved_execute_user_actions(plan_dir: Path) -> tuple[bool, str | None]:
    finalize_payload = read_json(plan_dir / "finalize.json", default={})
    if not isinstance(finalize_payload, dict):
        return False, None
    user_actions = finalize_payload.get("user_actions")
    if not isinstance(user_actions, list) or not user_actions:
        return False, None
    state_payload = read_json(plan_dir / "state.json", default={})
    if not isinstance(state_payload, dict):
        state_payload = {}
    resolutions = effective_user_action_resolutions(plan_dir, state_payload)
    for action in user_actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not action_id:
            continue
        status = action_resolution_status(action, resolutions)
        if status.get("resolution") in {"satisfied", "accepted_blocked", "waived"}:
            continue
        return True, action_id
    return False, None


def _recover_blocked_execute_if_tasks_done(
    root: Path,
    plan_name: str,
    *,
    writer: Any,
) -> bool:
    plan_dir = _plan_dir(root, plan_name)
    if _latest_execute_result(plan_dir) != "blocked":
        return False
    has_unresolved_user_actions, action_id = _has_unresolved_execute_user_actions(plan_dir)
    if has_unresolved_user_actions:
        reason = (
            f"unresolved user action {action_id}"
            if action_id
            else "unresolved execute user action"
        )
        writer(
            f"[supervisor-chain] execute result=blocked for {plan_name}; "
            f"treating as real block: {reason}\n"
        )
        return False

    all_done, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    if not all_done:
        writer(
            f"[supervisor-chain] execute result=blocked for {plan_name}; "
            f"treating as real block: {reason}\n"
        )
        return False

    _mark_blocked_execute_as_executed(plan_dir)
    writer(
        f"[supervisor-chain] execute result=blocked for {plan_name}, "
        f"but {reason} has all tasks done; continuing from executed state\n"
    )
    return True


def _attempt_count(state: SupervisorState, node_id: str) -> int:
    return sum(1 for record in state.run_records if record.node_id == node_id)


def _completed_contains(state: chain_spec.ChainState, label: str) -> bool:
    return any(entry.get("label") == label for entry in state.completed)


def _milestone_result(
    *,
    label: str,
    plan: str,
    normalized: NormalizedOutcome,
    decision: LadderDecision,
    pr_number: int | None = None,
    pr_state: str | None = None,
    authority_shadow: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "label": label,
        "plan": plan,
        "status": normalized.original_status,
        "outcome": normalized.outcome.value,
        "ladder_action": decision.action.value,
        "target_id": decision.target_id,
    }
    if pr_number is not None:
        result["pr_number"] = pr_number
    if pr_state is not None:
        result["pr_state"] = pr_state
    if authority_shadow is not None:
        result["authority_shadow"] = authority_shadow
    return result


def _result(
    status: str,
    chain_state: chain_spec.ChainState,
    supervisor_state: SupervisorState,
    milestone_results: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    spec: chain_spec.ChainSpec,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "milestone_results": milestone_results,
        "chain_state": chain_state.to_dict(),
        "supervisor_state": supervisor_state.to_dict(),
        "events": events,
        "base_branch": spec.base_branch,
    }


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _optional_state_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _optional_state_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _derive_milestone_authority_shadow(
    root: Path,
    plan_name: str,
    *,
    normalized: NormalizedOutcome,
    decision: LadderDecision,
) -> dict[str, Any]:
    """Derive authority-view-backed shadow for a supervisor milestone completion.

    Cross-checks the ladder's ADVANCE decision against the accepted-attempt /
    view-backed projection via ``_latest_execution_batch_all_tasks_done``.
    Legacy chain state is retained as an observation; the authority shadow is
    purely diagnostic and never blocks milestone advancement.

    Returns a dict suitable for inclusion in ``_milestone_result`` and
    ``chain_state.completed`` entries.
    """
    shadow: dict[str, Any] = {
        "kind": "supervisor_milestone_authority_shadow",
        "plan": plan_name,
        "ladder_action": decision.action.value,
        "legacy_outcome": normalized.outcome.value,
    }
    try:
        plan_dir = _plan_dir(root, plan_name)
        authoritative, reason = _latest_execution_batch_all_tasks_done(plan_dir)
        shadow["authority_verdict"] = authoritative
        shadow["authority_reason"] = reason
        if decision.action == LadderAction.ADVANCE and not authoritative:
            shadow["authority_drift"] = {
                "kind": "ladder_advance_authority_disagrees",
                "legacy_ladder_action": decision.action.value,
                "legacy_outcome": normalized.outcome.value,
                "authority_verdict": authoritative,
                "authority_reason": reason,
                "plan": plan_name,
            }
    except Exception:
        shadow["authority_verdict"] = None
        shadow["authority_reason"] = "authority_shadow_derivation_failed"
    return shadow


__all__ = [
    "ChainMilestonePackRunner",
    "run_chain",
]
