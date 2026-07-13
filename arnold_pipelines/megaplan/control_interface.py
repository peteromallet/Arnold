"""Domain-neutral control interface for run outcomes and control operations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import logging
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold.workflow.boundary_evidence import BoundaryOutcome, BoundaryReceipt
from arnold.control.interface import (
    ArtifactRequest,
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlBinding,
    ControlInterfaceTarget,
    ControlProjection,
    ControlTarget,
    ControlTargetRef,
    ControlTransition,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunStateView,
)
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.orchestration.override_authority import (
    OverrideAuthorityError,
    build_override_authority_record,
    current_freshness_token,
    override_authority_contract_for_transition,
)
from arnold_pipelines.megaplan.receipts.writer import write_boundary_receipt
from arnold_pipelines.megaplan.state_delta import StateDelta, StateDeltaConflict, apply_delta
from arnold_pipelines.megaplan.workflows.override_matrix import OVERRIDE_ACTION_MATRIX
from arnold.runtime.outcome import RunOutcome


_MISSING_BINDING = object()
_OVERRIDE_AUTHORITY_TRANSITIONS = frozenset(
    {"adopt-execution", "recover-blocked", "resume-clarify"}
)
log = logging.getLogger(__name__)


def _build_declared_override_policy_targets() -> Mapping[str, Mapping[str, str]]:
    targets: dict[str, Mapping[str, str]] = {}
    for entry in OVERRIDE_ACTION_MATRIX:
        if entry.dispatch_surface != "workflow.native_policy":
            continue
        target_ref = entry.declared_target_ref or entry.target_ref
        if target_ref is None or entry.route_signal is None or entry.policy_route_ref is None:
            raise ValueError(
                f"Override action {entry.action!r} is missing a native policy target declaration"
            )
        targets[entry.action] = {
            "route_signal": entry.route_signal,
            "target_ref": target_ref,
            "policy_route_ref": entry.policy_route_ref,
        }
    return targets


DECLARED_OVERRIDE_POLICY_TARGETS: Mapping[str, Mapping[str, str]] = (
    _build_declared_override_policy_targets()
)


def build_override_transition_request(
    action: str,
    *,
    target_id: str | None = None,
    params: Mapping[str, Any] | None = None,
    actor: str | None = None,
    source: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    expected_versions: Mapping[str, int] | None = None,
    idempotency_key: str | None = None,
) -> ControlTransitionRequest:
    """Build a caller-facing override request without granting route authority."""

    request_metadata = dict(metadata or {})
    request_metadata.setdefault("request_surface", "control.adapter")
    request_metadata.setdefault("requested_action", action)
    return ControlTransitionRequest(
        action=action,
        target_id=target_id or action,
        params=dict(params or {}),
        actor=actor,
        source=source,
        reason=reason,
        note=note,
        metadata=request_metadata,
        expected_versions=dict(expected_versions or {}),
        idempotency_key=idempotency_key,
    )


@dataclass(frozen=True)
class ControlTransitionConflict:
    """Observed stale-version conflict while applying a control transition."""

    key: str
    expected: int
    actual: int


def declared_override_policy_target(
    action: str,
    *,
    direction: str,
    source: str | None = None,
    target_state: str | None = None,
    operator_action: str | None = None,
) -> ControlTargetRef:
    declared = DECLARED_OVERRIDE_POLICY_TARGETS[action]
    metadata: dict[str, object] = {
        "kind": "workflow_step",
        "direction": direction,
        "actionable": True,
        "target_ref": declared["target_ref"],
        "route_signal": declared["route_signal"],
        "policy_route_ref": declared["policy_route_ref"],
        "dispatch_surface": "workflow.native_policy",
    }
    if source is not None:
        metadata["source"] = source
    if target_state is not None:
        metadata["target_state"] = target_state
    if operator_action is not None:
        metadata["operator_action"] = operator_action
    return ControlTargetRef(id=action, label=action, metadata=metadata)


def emit_override_authority_receipt(
    plan_dir: Path,
    state: Mapping[str, Any],
    action: str,
    *,
    actor: str = "operator",
    role: str = "human.override",
    details: Mapping[str, Any] | None = None,
    source_view_hash: str | None = None,
    source_view_revision: str | None = None,
) -> None:
    if action not in _OVERRIDE_AUTHORITY_TRANSITIONS:
        return
    try:
        contract = override_authority_contract_for_transition(action)
        freshness_token = current_freshness_token(state, transition=action)

        # --- assemble receipt details with optional source-view binding ----------
        receipt_details: dict[str, Any] = {
            "dispatch_surface": "workflow.native_policy",
            "declared_target_ref": DECLARED_OVERRIDE_POLICY_TARGETS[action]["target_ref"],
            "policy_route_ref": DECLARED_OVERRIDE_POLICY_TARGETS[action]["policy_route_ref"],
        }
        if source_view_hash is not None:
            receipt_details["source_view_hash"] = source_view_hash
        if source_view_revision is not None:
            receipt_details["source_view_revision"] = source_view_revision

        record_details: dict[str, Any] = {
            "route_signal": DECLARED_OVERRIDE_POLICY_TARGETS[action]["route_signal"],
            "declared_target_ref": DECLARED_OVERRIDE_POLICY_TARGETS[action]["target_ref"],
            "policy_route_ref": DECLARED_OVERRIDE_POLICY_TARGETS[action]["policy_route_ref"],
            **(dict(details) if details else {}),
        }
        if source_view_hash is not None:
            record_details["source_view_hash"] = source_view_hash

        record = build_override_authority_record(
            action,
            plan_dir=plan_dir,
            actor=actor,
            role=role,
            freshness_token=freshness_token,
            expected_freshness_token=freshness_token,
            details=record_details,
        )
        config = state.get("config")
        project_dir = (
            config.get("project_dir")
            if isinstance(config, Mapping)
            and isinstance(config.get("project_dir"), str)
            and config.get("project_dir")
            else None
        )
        receipt = BoundaryReceipt(
            boundary_id=contract.boundary_id,
            workflow_id=contract.workflow_id,
            row_id=contract.row_id,
            invocation_id=freshness_token,
            artifact_refs=record.evidence_refs,
            state_observation={
                "current_state": state.get("current_state"),
                "override_action": action,
                "route_signal": DECLARED_OVERRIDE_POLICY_TARGETS[action]["route_signal"],
            },
            outcome=BoundaryOutcome.COMPLETE,
            authority_records=(record,),
            details=receipt_details,
        )
        write_boundary_receipt(
            plan_dir,
            receipt,
            project_dir=project_dir,
        )
    except OverrideAuthorityError:
        log.warning(
            "override authority record build failed for %s",
            action,
            exc_info=True,
        )
    except Exception:
        log.warning(
            "override authority receipt emission failed for %s",
            action,
            exc_info=True,
        )


def _event_payload(
    kind: str,
    *,
    run_state: RunStateView,
    transition: ControlTransition | ControlTransitionRequest,
    mutated: bool,
    target_state: Mapping[str, Any] | None = None,
    conflict: ControlTransitionConflict | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "run_id": run_state.run_id,
        "op": transition.op,
        "target_id": transition.target_id,
        "idempotency_key": transition.idempotency_key,
        "mutated": mutated,
    }
    if target_state is not None:
        payload["state_version"] = target_state.get("_state_meta", {}).get("versions", {})
        payload["outcome"] = run_state.outcome.value if run_state.outcome is not None else None
        payload["cursor"] = run_state.cursor
    if conflict is not None:
        payload["conflict"] = {
            "key": conflict.key,
            "expected": conflict.expected,
            "actual": conflict.actual,
        }
    return payload


def _extract_state_deltas(result: ControlTransitionResult) -> tuple[StateDelta, ...]:
    if result.state_deltas:
        return tuple(result.state_deltas)
    raw = result.artifacts.get("state_deltas")
    if raw is None:
        raw = result.artifacts.get("deltas")
    if raw is None:
        return ()
    if isinstance(raw, StateDelta):
        return (raw,)
    return tuple(delta for delta in raw if isinstance(delta, StateDelta))


def _with_plan_dir(
    transition: ControlTransition | ControlTransitionRequest,
    plan_dir: str | Path | None,
) -> ControlTransition | ControlTransitionRequest:
    if plan_dir is None:
        return transition
    plan_dir_str = str(plan_dir)
    if isinstance(transition, ControlTransitionRequest):
        payload = transition.payload
        if payload.get("plan_dir") == plan_dir_str:
            return transition
        params = dict(transition.params)
        params.setdefault("plan_dir", plan_dir_str)
        return ControlTransitionRequest(
            action=transition.action,
            target_id=transition.target_id,
            params=params,
            actor=transition.actor,
            source=transition.source,
            reason=transition.reason,
            note=transition.note,
            metadata=dict(transition.metadata),
            expected_versions=dict(transition.expected_versions),
            idempotency_key=transition.idempotency_key,
        )
    if transition.payload.get("plan_dir") == plan_dir_str:
        return transition
    return ControlTransition(
        op=transition.op,
        target_id=transition.target_id,
        payload={**dict(transition.payload), "plan_dir": plan_dir_str},
        idempotency_key=transition.idempotency_key,
    )


def _projection_from_targets(
    targets: Sequence[ControlTarget],
    *,
    recovery: bool,
) -> ControlProjection:
    actionable: list[ControlTarget] = []
    diagnostics: list[Mapping[str, Any]] = []
    for target in targets:
        if target.metadata.get("kind") == "diagnostic":
            diagnostics.append(dict(target.metadata))
        else:
            actionable.append(target)
    if recovery:
        return ControlProjection(
            recover_targets=tuple(actionable),
            diagnostics=tuple(diagnostics),
            recovery=True,
        )
    return ControlProjection(
        valid_targets=tuple(actionable),
        diagnostics=tuple(diagnostics),
        recovery=False,
    )


def _resolve_binding_and_state(
    run_state: RunStateView | Mapping[str, Any],
    binding: ControlBinding | str,
) -> tuple[RunStateView, ControlBinding]:
    # The canonical megaplan binding and the legacy planning alias both
    # resolve to the same planning control surface.
    # New bindings (e.g. bakeoff) use direct ControlBinding instance
    # injection — no string dispatch is added.  The caller imports
    # and constructs the binding (e.g. bakeoff_control_binding()) and
    # passes it directly.
    if isinstance(binding, str):
        if binding not in {"megaplan", "planning"}:
            raise ValueError(f"unknown control binding: {binding!r}")
        planning = import_module("arnold_pipelines.megaplan." + "planning")

        resolved_state = (
            run_state
            if isinstance(run_state, RunStateView)
            else planning.planning_run_state_view(run_state)
        )
        return resolved_state, planning.planning_control_binding()
    if not isinstance(run_state, RunStateView):
        planning = import_module("arnold_pipelines.megaplan." + "planning")

        run_state = planning.planning_run_state_view(run_state)
    return run_state, binding


def read_valid_targets(
    run_state: RunStateView | Mapping[str, Any],
    binding: ControlBinding | str | object = _MISSING_BINDING,
    *,
    recovery: bool = False,
    plugin_id: str | None = None,
) -> ControlProjection:
    """Read binding-projected targets for ``run_state``."""

    if binding is _MISSING_BINDING and plugin_id is not None:
        binding = plugin_id
    if binding is _MISSING_BINDING:
        raise ValueError("read_valid_targets requires an explicit binding or plugin identity")
    if isinstance(binding, str) and binding in {"megaplan", "planning"}:
        from arnold.execution.operations import OperationKind, OperationRequest
        from arnold_pipelines.megaplan.registry import (
            control_status_result_from_operation_result,
            dispatch_operation_for,
        )
        planning = import_module("arnold_pipelines.megaplan." + "planning")

        result = dispatch_operation_for(
            binding,
            OperationRequest(
                kind=OperationKind.STATUS_PROJECTION,
                payload={
                    "state": dict(run_state.raw_state)
                    if isinstance(run_state, RunStateView)
                    else dict(run_state),
                    "state_view": run_state if isinstance(run_state, RunStateView) else None,
                    "mode": "recover_targets" if recovery else "valid_targets",
                },
            ),
        )
        if result.ok:
            payload = control_status_result_from_operation_result(
                result,
                require_recover_targets=recovery,
                require_valid_targets=not recovery,
            )
            targets = payload["recover_targets"] if recovery else payload["valid_targets"]
            return _projection_from_targets(tuple(targets), recovery=recovery)

        direct_state = (
            run_state if isinstance(run_state, RunStateView) else planning.planning_run_state_view(dict(run_state))
        )
        direct_binding = planning.planning_control_binding()
        targets = (
            direct_binding.recover_targets(direct_state)
            if recovery
            else direct_binding.valid_targets(direct_state)
        )
        return _projection_from_targets(tuple(targets), recovery=recovery)

    run_state, binding = _resolve_binding_and_state(run_state, binding)
    targets = binding.recover_targets(run_state) if recovery else binding.valid_targets(run_state)
    return _projection_from_targets(tuple(targets), recovery=recovery)


def synthesize_artifacts(
    run_state: RunStateView | Mapping[str, Any],
    transition: ControlTransition | ControlTransitionRequest,
    binding: ControlBinding | str,
) -> Mapping[str, Any]:
    """Delegate artifact synthesis to the binding."""

    run_state, binding = _resolve_binding_and_state(run_state, binding)
    return binding.synthesize_artifacts(run_state, transition)


def apply_transition(
    run_state: RunStateView | Mapping[str, Any],
    transition: ControlTransition | ControlTransitionRequest,
    binding: ControlBinding | str | None = None,
    *,
    plan_dir: str | Path | None = None,
) -> ControlTransitionResult:
    """Apply a transition through a binding and optional CAS-backed state write."""

    if binding is None:
        return ControlTransitionResult(
            accepted=False,
            mutated=False,
            reason="control_interface_transition_stub",
        )
    run_state, binding = _resolve_binding_and_state(run_state, binding)
    transition = _with_plan_dir(transition, plan_dir)
    if plan_dir is None:
        return binding.apply_transition(run_state, transition)

    binding_result = binding.apply_transition(run_state, transition)
    if not binding_result.accepted:
        return binding_result

    deltas = _extract_state_deltas(binding_result)
    if not deltas:
        events = tuple(binding_result.events) + (
            _event_payload(
                "STATE_TRANSITION",
                run_state=run_state,
                transition=transition,
                mutated=False,
            ),
        )
        return ControlTransitionResult(
            accepted=True,
            mutated=False,
            reason=binding_result.reason,
            artifacts=binding_result.artifacts,
            state_deltas=binding_result.state_deltas,
            events=events,
        )

    applied_state: dict[str, Any] | None = None

    def _apply_control_deltas(current: dict[str, Any]) -> bool:
        nonlocal applied_state
        expected_versions = getattr(transition, "expected_versions", {}) or {}
        versions = current.get("_state_meta", {}).get("versions", {})
        if not isinstance(versions, Mapping):
            versions = {}
        for key, expected in expected_versions.items():
            actual = versions.get(key, 0)
            actual = actual if isinstance(actual, int) else 0
            if actual != expected:
                raise StateDeltaConflict(key, expected, actual)
        next_state = dict(current)
        for delta in deltas:
            next_state, _ = apply_delta(next_state, delta)
        remove_keys = binding_result.artifacts.get("remove_state_keys", ())
        if isinstance(remove_keys, Sequence) and not isinstance(remove_keys, (str, bytes)):
            for key in remove_keys:
                if isinstance(key, str):
                    next_state.pop(key, None)
        current.clear()
        current.update(next_state)
        applied_state = next_state
        return True

    try:
        persisted = write_plan_state(
            Path(plan_dir),
            mode="patch-many",
            patch={},
            mutation=_apply_control_deltas,
        )
    except StateDeltaConflict as exc:
        conflict = ControlTransitionConflict(
            key=exc.key,
            expected=exc.expected,
            actual=exc.actual,
        )
        return ControlTransitionResult(
            accepted=False,
            mutated=False,
            reason="control_transition_conflict",
            artifacts={
                **dict(binding_result.artifacts),
                "conflict": {
                    "key": conflict.key,
                    "expected": conflict.expected,
                    "actual": conflict.actual,
                },
            },
            state_deltas=binding_result.state_deltas,
            events=tuple(binding_result.events)
            + (
                _event_payload(
                    "STATE_TRANSITION",
                    run_state=run_state,
                    transition=transition,
                    mutated=False,
                    conflict=conflict,
                ),
            ),
        )

    next_state = applied_state if applied_state is not None else persisted
    if (
        transition.op == "override"
        and isinstance(transition.target_id, str)
        and transition.target_id
    ):
        # --- optionally bind the receipt to a source HumanGateView hash ----------
        source_view_hash: str | None = None
        source_view_revision: str | None = None
        try:
            from arnold_pipelines.megaplan.authority.views import derive_human_gate_view

            meta = next_state.get("meta") if isinstance(next_state, Mapping) else None
            plan_revision = (
                meta.get("current_invocation_id")
                if isinstance(meta, Mapping)
                else None
            )
            override_signal: dict[str, Any] = {
                "gate_type": "override",
                "gate_reason": transition.target_id,
                "source": f"control://override/{transition.target_id}",
            }
            if plan_revision and isinstance(plan_revision, str):
                override_signal["plan_ref"] = plan_revision
            if hasattr(transition, "actor") and transition.actor:
                override_signal["actor"] = transition.actor
            if hasattr(transition, "reason") and transition.reason:
                override_signal["reason"] = transition.reason
            view = derive_human_gate_view([override_signal], current_plan_revision=plan_revision)
            source_view_hash = view.view_hash
            if view.source_paths:
                source_view_revision = view.source_paths[0]
        except Exception:
            pass  # source-view binding is best-effort; never block the receipt

        emit_override_authority_receipt(
            Path(plan_dir),
            next_state,
            transition.target_id,
            source_view_hash=source_view_hash,
            source_view_revision=source_view_revision,
        )
    events = tuple(binding_result.events) + (
        _event_payload(
            "OVERRIDE_APPLIED",
            run_state=run_state,
            transition=transition,
            mutated=True,
            target_state=next_state,
        ),
        _event_payload(
            "STATE_TRANSITION",
            run_state=run_state,
            transition=transition,
            mutated=True,
            target_state=next_state,
        ),
    )
    return ControlTransitionResult(
        accepted=True,
        mutated=True,
        reason=binding_result.reason,
        artifacts=binding_result.artifacts,
        state_deltas=binding_result.state_deltas,
        events=events,
    )


__all__ = [
    "ControlBinding",
    "CONTROL_TARGET_ABORT",
    "CONTROL_TARGET_FORCE_ADVANCE",
    "CONTROL_TARGET_RECOVER_FROM_STUCK",
    "CONTROL_TARGET_REROUTE",
    "ArtifactRequest",
    "build_override_transition_request",
    "DECLARED_OVERRIDE_POLICY_TARGETS",
    "ControlProjection",
    "ControlInterfaceTarget",
    "ControlTarget",
    "ControlTargetRef",
    "ControlTransition",
    "ControlTransitionConflict",
    "ControlTransitionRequest",
    "ControlTransitionResult",
    "RunOutcome",
    "RunStateView",
    "apply_transition",
    "declared_override_policy_target",
    "emit_override_authority_receipt",
    "read_valid_targets",
    "synthesize_artifacts",
]
