from __future__ import annotations

import inspect
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import megaplan
import megaplan.control_interface as control_interface
from megaplan._core.state import write_plan_state
from megaplan._pipeline.flags import control_interface_routing_on
from megaplan._pipeline.types import StateDelta
from megaplan.control_interface import (
    ArtifactRequest,
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlProjection,
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


class _PlanDirBinding(_Binding):
    def __init__(self) -> None:
        self.last_transition: ControlTransition | ControlTransitionRequest | None = None

    def apply_transition(
        self,
        run_state: RunStateView,
        transition: ControlTransition,
    ) -> ControlTransitionResult:
        self.last_transition = transition
        return ControlTransitionResult(accepted=True, reason="saw-plan-dir")


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
    assert control_interface.CONTROL_TARGET_FORCE_ADVANCE == CONTROL_TARGET_FORCE_ADVANCE
    assert control_interface.CONTROL_TARGET_REROUTE == CONTROL_TARGET_REROUTE
    assert (
        control_interface.CONTROL_TARGET_RECOVER_FROM_STUCK
        == CONTROL_TARGET_RECOVER_FROM_STUCK
    )
    assert control_interface.CONTROL_TARGET_ABORT == CONTROL_TARGET_ABORT
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
        action=CONTROL_TARGET_FORCE_ADVANCE,
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

    assert request.op == CONTROL_TARGET_FORCE_ADVANCE
    assert request.payload == {
        "actor": "operator",
        "source": "cli",
        "reason": "accepted risk",
        "note": "ship it",
        "recommendation": "PROCEED",
    }
    assert artifact_request.transition is request
    assert ControlTarget(kind="operator", id="recover").kind == "operator"


def test_neutral_control_target_constants_are_stable_and_project_through_targets() -> None:
    assert CONTROL_TARGET_FORCE_ADVANCE == "force-advance"
    assert CONTROL_TARGET_REROUTE == "re-route"
    assert CONTROL_TARGET_RECOVER_FROM_STUCK == "recover-from-stuck"
    assert CONTROL_TARGET_ABORT == "abort"
    assert control_interface.__all__ == [
        "ControlBinding",
        "CONTROL_TARGET_ABORT",
        "CONTROL_TARGET_FORCE_ADVANCE",
        "CONTROL_TARGET_RECOVER_FROM_STUCK",
        "CONTROL_TARGET_REROUTE",
        "ArtifactRequest",
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
        "read_valid_targets",
        "synthesize_artifacts",
    ]

    projection = ControlProjection(
        valid_targets=(
            ControlTargetRef(id=CONTROL_TARGET_FORCE_ADVANCE),
            ControlTargetRef(id=CONTROL_TARGET_REROUTE),
        ),
        recover_targets=(
            ControlTargetRef(id=CONTROL_TARGET_RECOVER_FROM_STUCK),
            ControlTargetRef(id=CONTROL_TARGET_ABORT),
        ),
    )

    assert [target.id for target in projection.valid_targets] == [
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
    ]
    assert [target.id for target in projection.recover_targets] == [
        CONTROL_TARGET_RECOVER_FROM_STUCK,
        CONTROL_TARGET_ABORT,
    ]


def test_read_valid_targets_requires_explicit_binding_or_plugin_identity() -> None:
    with pytest.raises(ValueError, match="explicit binding"):
        read_valid_targets(_state())


def test_read_valid_targets_supports_named_planning_binding() -> None:
    projection = read_valid_targets(_state(), binding="planning")

    assert [target.id for target in projection] == ["plan"]


def test_read_valid_targets_supports_canonical_megaplan_operation_dispatch() -> None:
    projection = read_valid_targets(_state(), binding="megaplan")

    assert [target.id for target in projection] == ["plan"]


def test_apply_transition_is_non_mutating_stub_without_binding() -> None:
    state = RunStateView(run_id="run-1")
    transition = ControlTransition(op=CONTROL_TARGET_FORCE_ADVANCE)

    result = apply_transition(state, transition)

    assert result == ControlTransitionResult(
        accepted=False,
        mutated=False,
        reason="control_interface_transition_stub",
    )


def test_apply_transition_delegates_when_binding_is_supplied() -> None:
    state = RunStateView(run_id="run-1")
    transition = ControlTransition(op=CONTROL_TARGET_FORCE_ADVANCE)

    result = apply_transition(state, transition, _Binding())

    assert result.accepted is True
    assert result.mutated is True
    assert result.reason == f"run-1:{CONTROL_TARGET_FORCE_ADVANCE}"


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


def test_apply_transition_injects_plan_dir_into_binding_request(tmp_path: Path) -> None:
    binding = _PlanDirBinding()
    request = ControlTransitionRequest(action=CONTROL_TARGET_FORCE_ADVANCE)

    result = apply_transition(_state(), request, binding, plan_dir=tmp_path)

    assert result.accepted is True
    assert binding.last_transition is not None
    assert binding.last_transition.payload["plan_dir"] == str(tmp_path)


def test_control_interface_routing_flag_is_default_off_and_exact_opt_in() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert control_interface_routing_on() is False
    with patch.dict(os.environ, {"MEGAPLAN_UNIFIED_DISPATCH": "1"}, clear=True):
        assert control_interface_routing_on() is False
    with patch.dict(os.environ, {"MEGAPLAN_CONTROL_INTERFACE_ROUTING": "0"}, clear=True):
        assert control_interface_routing_on() is False
    with patch.dict(os.environ, {"MEGAPLAN_CONTROL_INTERFACE_ROUTING": "1"}, clear=True):
        assert control_interface_routing_on() is True


# ---------------------------------------------------------------------------
# T8: stable neutral IDs, export surface, ControlTargetRef / ControlProjection
# ---------------------------------------------------------------------------


def test_control_target_ref_is_identical_to_control_target() -> None:
    """ControlTargetRef must be the same type as ControlTarget (alias)."""
    assert ControlTargetRef is ControlTarget
    # Constructing through either name produces the same shape.
    a = ControlTargetRef(id="t1")
    b = ControlTarget(id="t1")
    assert a == b
    assert a.id == b.id == "t1"
    assert a.kind == b.kind == "workflow_step"


def test_control_projection_sequence_protocol() -> None:
    """ControlProjection supports iteration, len, and indexing."""
    targets = (
        ControlTargetRef(id=CONTROL_TARGET_FORCE_ADVANCE),
        ControlTargetRef(id=CONTROL_TARGET_REROUTE),
    )
    proj = ControlProjection(valid_targets=targets)

    # __len__
    assert len(proj) == 2
    # __iter__
    assert [t.id for t in proj] == [CONTROL_TARGET_FORCE_ADVANCE, CONTROL_TARGET_REROUTE]
    # __getitem__
    assert proj[0].id == CONTROL_TARGET_FORCE_ADVANCE
    assert proj[1].id == CONTROL_TARGET_REROUTE

    # Empty projection
    empty = ControlProjection()
    assert len(empty) == 0
    assert list(empty) == []


def test_control_projection_recovery_flag_switches_targets() -> None:
    """When recovery=True, targets returns recover_targets instead of valid_targets."""
    proj = ControlProjection(
        valid_targets=(ControlTargetRef(id="forward"),),
        recover_targets=(ControlTargetRef(id="backward"),),
        recovery=True,
    )
    assert proj.recovery is True
    assert [t.id for t in proj] == ["backward"]
    assert proj == (ControlTargetRef(id="backward"),)

    # Non-recovery projection returns valid_targets.
    proj2 = ControlProjection(
        valid_targets=(ControlTargetRef(id="forward"),),
        recover_targets=(ControlTargetRef(id="backward"),),
        recovery=False,
    )
    assert [t.id for t in proj2] == ["forward"]


def test_control_projection_eq_with_tuple_and_non_tuple() -> None:
    """ControlProjection __eq__ delegates to targets for tuples, identity otherwise."""
    proj = ControlProjection(
        valid_targets=(ControlTargetRef(id="a"), ControlTargetRef(id="b")),
    )
    # Tuple comparison: __eq__ compares targets sequence to the tuple
    assert proj == (ControlTargetRef(id="a"), ControlTargetRef(id="b"))
    assert proj != (ControlTargetRef(id="a"),)

    # Same-targets projection is still a different object (identity-based fallback).
    proj2 = ControlProjection(
        valid_targets=(ControlTargetRef(id="a"), ControlTargetRef(id="b")),
    )
    assert proj is not proj2
    # Non-tuple, non-projection comparison uses identity (object.__eq__)
    assert proj != "not-a-projection"

    # Equality with itself holds
    assert proj == proj


def test_neutral_ids_round_trip_through_targetref_and_projection() -> None:
    """Every neutral ID constant round-trips through ControlTargetRef → ControlProjection."""
    neutral_ids = (
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_RECOVER_FROM_STUCK,
        CONTROL_TARGET_ABORT,
    )

    # Build targets from every neutral ID
    refs = tuple(ControlTargetRef(id=nid) for nid in neutral_ids)
    proj = ControlProjection(valid_targets=refs, recover_targets=refs)

    # All IDs survive the round-trip
    assert [t.id for t in proj.valid_targets] == list(neutral_ids)
    assert [t.id for t in proj.recover_targets] == list(neutral_ids)

    # Recovery mode switches to recover_targets
    recovery_proj = ControlProjection(
        valid_targets=refs, recover_targets=refs, recovery=True
    )
    assert [t.id for t in recovery_proj] == list(neutral_ids)

    # Each ref is a proper ControlTarget with the neutral ID as its id
    for ref, nid in zip(refs, neutral_ids):
        assert isinstance(ref, ControlTarget)
        assert ref.id == nid
        assert ref.kind == "workflow_step"


def test_neutral_id_constants_are_importable_and_hashable() -> None:
    """Neutral ID constants must be importable strings usable as dict keys and set members."""
    ids = {
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_RECOVER_FROM_STUCK,
        CONTROL_TARGET_ABORT,
    }
    assert len(ids) == 4

    # Usable as mapping keys
    routing = {
        CONTROL_TARGET_FORCE_ADVANCE: "advance_handler",
        CONTROL_TARGET_REROUTE: "reroute_handler",
        CONTROL_TARGET_RECOVER_FROM_STUCK: "recover_handler",
        CONTROL_TARGET_ABORT: "abort_handler",
    }
    assert routing[CONTROL_TARGET_FORCE_ADVANCE] == "advance_handler"
    assert routing["force-advance"] == "advance_handler"

    # Immutable string identity
    assert isinstance(CONTROL_TARGET_FORCE_ADVANCE, str)
    assert CONTROL_TARGET_FORCE_ADVANCE is control_interface.CONTROL_TARGET_FORCE_ADVANCE


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
