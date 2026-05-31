from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from unittest.mock import patch

import megaplan
import megaplan.control_interface as control_interface
from megaplan._core.state import write_plan_state
from megaplan._pipeline.flags import control_interface_routing_on
from megaplan._pipeline.types import StateDelta
from megaplan.control_interface import (
    ArtifactRequest,
    ControlProjection,
    ControlInterfaceTarget,
    ControlTarget,
    ControlTargetRef,
    ControlTransition,
    ControlTransitionRequest,
    ControlTransitionResult,
    RunOutcome,
    RunStateView,
    apply_transition,
    read_valid_targets,
    synthesize_artifacts,
)
from megaplan.types import STATE_INITIALIZED


class _Binding:
    def valid_targets(self, run_state: RunStateView) -> tuple[ControlTargetRef, ...]:
        return (ControlTargetRef(id=f"{run_state.run_id}:next"),)

    def recover_targets(self, run_state: RunStateView) -> tuple[ControlTargetRef, ...]:
        return (ControlTargetRef(id=f"{run_state.run_id}:recover"),)

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransition,
    ) -> ControlTransitionResult:
        return ControlTransitionResult(
            accepted=True,
            mutated=True,
            reason=f"{run_state.run_id}:{transition.op}",
        )

    def synthesize_artifacts(
        self,
        run_state: RunStateView,
        transition: ControlTransition,
    ) -> dict[str, str]:
        return {"run": run_state.run_id, "op": transition.op}


class _DeltaBinding(_Binding):
    def __init__(self, *deltas: StateDelta) -> None:
        self._deltas = deltas

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransition,
    ) -> ControlTransitionResult:
        return ControlTransitionResult(
            accepted=True,
            reason="delta-bound",
            state_deltas=self._deltas,
            events=({"kind": "BINDING_EVENT", "run_id": run_state.run_id},),
        )


def _state(**overrides):
    state = {
        "name": "p",
        "idea": "i",
        "current_state": STATE_INITIALIZED,
        "iteration": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "config": {"project_dir": "/tmp/project"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    state.update(overrides)
    return state


def _read(plan_dir: Path) -> dict:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def test_control_interface_import_surface_from_module_and_package() -> None:
    assert control_interface.RunOutcome is RunOutcome
    assert control_interface.ControlTarget is ControlTarget
    assert control_interface.ControlInterfaceTarget is ControlTarget
    assert control_interface.ControlProjection is ControlProjection
    assert control_interface.ControlTransitionRequest is ControlTransitionRequest
    assert control_interface.ArtifactRequest is ArtifactRequest
    assert megaplan.RunOutcome is RunOutcome
    assert not hasattr(megaplan, "ControlTarget")
    assert megaplan.ControlInterfaceTarget is ControlTarget
    assert megaplan.ControlProjection is ControlProjection
    assert megaplan.ControlTransitionRequest is ControlTransitionRequest
    assert megaplan.ArtifactRequest is ArtifactRequest
    assert megaplan.RunStateView is RunStateView
    assert megaplan.ControlTransition is ControlTransition
    assert megaplan.apply_transition is apply_transition
    assert megaplan.read_valid_targets is read_valid_targets
    assert megaplan.synthesize_artifacts is synthesize_artifacts


def test_run_outcome_vocabulary_is_exact_and_domain_neutral() -> None:
    assert {outcome.value for outcome in RunOutcome} == {
        "succeeded",
        "failed",
        "escalated",
        "blocked",
        "awaiting_human",
    }


def test_control_interface_delegates_projections_and_artifacts() -> None:
    state = RunStateView(run_id="run-1", outcome=RunOutcome.BLOCKED)
    transition = ControlTransition(op="recover", target_id="previous")
    binding = _Binding()

    projection = read_valid_targets(state, binding)
    recovery_projection = read_valid_targets(state, binding, recovery=True)

    assert projection == (ControlTargetRef(id="run-1:next"),)
    assert isinstance(projection, ControlProjection)
    assert projection.valid_targets == (ControlTargetRef(id="run-1:next"),)
    assert projection.recover_targets == ()
    assert projection.diagnostics == ()
    assert recovery_projection == (ControlTargetRef(id="run-1:recover"),)
    assert recovery_projection.valid_targets == ()
    assert recovery_projection.recover_targets == (ControlTargetRef(id="run-1:recover"),)
    assert synthesize_artifacts(state, transition, binding) == {"run": "run-1", "op": "recover"}


def test_control_transition_request_and_artifact_request_are_public_contracts() -> None:
    request = ControlTransitionRequest(
        action="force-advance",
        target_id="gate",
        params={"recommendation": "PROCEED"},
        actor="operator",
        source="cli",
        reason="accepted risk",
        note="ship it",
        metadata={"actor": "test"},
        expected_versions={"meta": 3},
        idempotency_key="idem",
    )
    artifact_request = ArtifactRequest(
        artifact_type="gate",
        transition=request,
        params={"path": "gate.json"},
    )

    assert request.op == "force-advance"
    assert request.payload == {
        "actor": "operator",
        "source": "cli",
        "reason": "accepted risk",
        "note": "ship it",
        "recommendation": "PROCEED",
    }
    assert artifact_request.transition is request
    assert ControlTarget(kind="operator", id="recover").kind == "operator"


def test_read_valid_targets_supports_default_planning_dispatch() -> None:
    projection = read_valid_targets(_state())

    assert [target.id for target in projection] == ["plan"]


def test_read_valid_targets_supports_named_planning_binding() -> None:
    projection = read_valid_targets(_state(), binding="planning")

    assert [target.id for target in projection] == ["plan"]


def test_apply_transition_is_non_mutating_stub_without_binding() -> None:
    state = RunStateView(run_id="run-1")
    transition = ControlTransition(op="force-advance")

    result = apply_transition(state, transition)

    assert result == ControlTransitionResult(
        accepted=False,
        mutated=False,
        reason="control_interface_transition_stub",
    )


def test_apply_transition_delegates_when_binding_is_supplied() -> None:
    state = RunStateView(run_id="run-1")
    transition = ControlTransition(op="force-advance")

    result = apply_transition(state, transition, _Binding())

    assert result.accepted is True
    assert result.mutated is True
    assert result.reason == "run-1:force-advance"


def test_apply_transition_applies_binding_deltas_with_patch_many_cas(tmp_path: Path) -> None:
    write_plan_state(tmp_path, mode="replace", state=_state(meta={"operator": {}}))
    state = RunStateView(run_id="run-1", outcome=RunOutcome.BLOCKED, cursor="execute:1")
    transition = ControlTransition(
        op="override",
        target_id="force-proceed",
        idempotency_key="idem-1",
    )
    binding = _DeltaBinding(
        StateDelta(
            op="deep_merge",
            key="meta",
            value={"operator": {"decision": "force-proceed"}},
            version=0,
        )
    )

    result = apply_transition(state, transition, binding, plan_dir=tmp_path)

    assert result.accepted is True
    assert result.mutated is True
    assert _read(tmp_path)["meta"]["operator"] == {"decision": "force-proceed"}
    assert _read(tmp_path)["_state_meta"]["versions"]["meta"] == 1
    assert [event["kind"] for event in result.events] == [
        "BINDING_EVENT",
        "OVERRIDE_APPLIED",
        "STATE_TRANSITION",
    ]
    override_event = result.events[1]
    assert override_event == {
        "kind": "OVERRIDE_APPLIED",
        "run_id": "run-1",
        "op": "override",
        "target_id": "force-proceed",
        "idempotency_key": "idem-1",
        "mutated": True,
        "state_version": {"meta": 1},
        "outcome": "blocked",
        "cursor": "execute:1",
    }


def test_apply_transition_returns_conflict_for_stale_expected_versions(tmp_path: Path) -> None:
    write_plan_state(
        tmp_path,
        mode="replace",
        state=_state(
            meta={"operator": {}},
            _state_meta={"versions": {"meta": 2}},
        ),
    )
    state = RunStateView(run_id="run-1")
    transition = ControlTransition(op="override", target_id="force-proceed")
    binding = _DeltaBinding(
        StateDelta(
            op="deep_merge",
            key="meta",
            value={"operator": {"decision": "force-proceed"}},
            version=1,
        )
    )

    result = apply_transition(state, transition, binding, plan_dir=tmp_path)

    assert result.accepted is False
    assert result.mutated is False
    assert result.reason == "control_transition_conflict"
    assert result.artifacts["conflict"] == {"key": "meta", "expected": 1, "actual": 2}
    assert _read(tmp_path)["meta"] == {"operator": {}}
    assert result.events[-1] == {
        "kind": "STATE_TRANSITION",
        "run_id": "run-1",
        "op": "override",
        "target_id": "force-proceed",
        "idempotency_key": None,
        "mutated": False,
        "conflict": {"key": "meta", "expected": 1, "actual": 2},
    }


def test_apply_transition_enforces_request_expected_versions(tmp_path: Path) -> None:
    write_plan_state(
        tmp_path,
        mode="replace",
        state=_state(
            meta={"operator": {}},
            _state_meta={"versions": {"meta": 2}},
        ),
    )
    state = RunStateView(run_id="run-1")
    request = ControlTransitionRequest(
        action="override",
        target_id="force-proceed",
        expected_versions={"meta": 999},
    )
    binding = _DeltaBinding(
        StateDelta(
            op="deep_merge",
            key="meta",
            value={"operator": {"decision": "force-proceed"}},
            version=2,
        )
    )

    result = apply_transition(state, request, binding, plan_dir=tmp_path)

    assert result.accepted is False
    assert result.mutated is False
    assert result.reason == "control_transition_conflict"
    assert result.artifacts["conflict"] == {"key": "meta", "expected": 999, "actual": 2}
    assert _read(tmp_path)["meta"] == {"operator": {}}


def test_control_transition_request_action_routes_planning_override(tmp_path: Path) -> None:
    write_plan_state(tmp_path, mode="replace", state=_state(meta={"notes": [], "overrides": []}))
    request = ControlTransitionRequest(
        action="add-note",
        note="public request note",
        source="api",
        expected_versions={"meta": 0},
    )

    result = apply_transition(_read(tmp_path), request, binding="planning", plan_dir=tmp_path)

    assert result.accepted is True
    assert result.mutated is True
    state = _read(tmp_path)
    assert state["meta"]["notes"][-1]["note"] == "public request note"
    assert state["meta"]["notes"][-1]["source"] == "api"


def test_control_interface_routing_flag_is_default_off_and_exact_opt_in() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert control_interface_routing_on() is False
    with patch.dict(os.environ, {"MEGAPLAN_UNIFIED_DISPATCH": "1"}, clear=True):
        assert control_interface_routing_on() is False
    with patch.dict(os.environ, {"MEGAPLAN_CONTROL_INTERFACE_ROUTING": "0"}, clear=True):
        assert control_interface_routing_on() is False
    with patch.dict(os.environ, {"MEGAPLAN_CONTROL_INTERFACE_ROUTING": "1"}, clear=True):
        assert control_interface_routing_on() is True


def test_control_interface_has_no_planning_imports_or_literals() -> None:
    source = inspect.getsource(control_interface)
    forbidden = (
        "megaplan.planning",
        "megaplan.handlers",
        "megaplan._core.workflow",
        "_OVERRIDE_ACTIONS",
        "build_gate_artifact",
        "gate.json",
    )

    assert all(token not in source for token in forbidden)
