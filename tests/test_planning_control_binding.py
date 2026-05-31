from __future__ import annotations

import inspect

from megaplan._core.workflow import workflow_next
from megaplan.control_interface import ControlTargetRef, RunStateView, read_valid_targets
from megaplan.planning import PlanningControlBinding, planning_control_binding
from megaplan.types import (
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_INITIALIZED,
    STATE_PLANNED,
    STATE_REVIEWED,
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


def test_planning_package_path_is_importable() -> None:
    binding = planning_control_binding()

    assert isinstance(binding, PlanningControlBinding)


def test_sdk_dispatch_uses_planning_control_binding_path_for_valid_targets() -> None:
    state = _state()
    run_state = RunStateView(run_id="run-1", raw_state=state)

    targets = read_valid_targets(run_state, planning_control_binding())

    assert targets == tuple(
        ControlTargetRef(
            id=step,
            label=step,
            metadata={
                "kind": "workflow_step",
                "step": step,
                "direction": "forward",
                "actionable": True,
            },
        )
        for step in workflow_next(state)
    )


def test_forward_projection_tracks_robustness_prep_and_feedback_variants() -> None:
    binding = planning_control_binding()
    variants = (
        _state(config={"project_dir": "/tmp/project", "robustness": "light"}),
        _state(config={"project_dir": "/tmp/project", "with_prep": True}),
        _state(
            current_state=STATE_REVIEWED,
            config={"project_dir": "/tmp/project", "with_feedback": True},
        ),
    )

    for state in variants:
        targets = read_valid_targets(
            RunStateView(run_id="run-1", raw_state=state),
            binding,
        )

        assert [target.id for target in targets] == workflow_next(state)
        assert all(target.metadata["kind"] == "workflow_step" for target in targets)


def test_blocked_recovery_uses_resume_cursor_phase_predecessor() -> None:
    state = _state(
        current_state=STATE_BLOCKED,
        resume_cursor={"phase": "execute", "retry_strategy": "fresh_session"},
    )

    targets = read_valid_targets(
        RunStateView(run_id="run-1", raw_state=state),
        planning_control_binding(),
        recovery=True,
    )

    assert targets == (
        ControlTargetRef(
            id="recover-blocked",
            label="recover-blocked",
            metadata={
                "kind": "workflow_step",
                "step": "recover-blocked",
                "direction": "recovery",
                "actionable": True,
                "target_state": STATE_FINALIZED,
                "source": "resume_cursor.phase",
                "operator_action": "recover-blocked",
            },
        ),
    )


def test_recovery_phase_falls_back_to_active_step_name_then_phase_result_metadata() -> None:
    binding = planning_control_binding()
    by_active_name = _state(
        current_state=STATE_BLOCKED,
        active_step={"name": "review", "phase": "execute"},
    )
    by_phase_result_metadata = _state(
        current_state=STATE_BLOCKED,
        latest_failure={"metadata": {"phase_result": {"phase": "critique"}}},
    )

    active_targets = read_valid_targets(
        RunStateView(run_id="run-active", raw_state=by_active_name),
        binding,
        recovery=True,
    )
    metadata_targets = read_valid_targets(
        RunStateView(run_id="run-meta", raw_state=by_phase_result_metadata),
        binding,
        recovery=True,
    )

    assert active_targets[0].metadata["target_state"] == STATE_EXECUTED
    assert active_targets[0].metadata["source"] == "active_step.name"
    assert metadata_targets[0].metadata["target_state"] == STATE_PLANNED
    assert metadata_targets[0].metadata["source"] == "latest_failure.metadata.phase_result.phase"


def test_awaiting_human_projects_to_operator_action_variants() -> None:
    binding = planning_control_binding()
    prep_state = _state(
        current_state=STATE_AWAITING_HUMAN,
        clarification={"source": "prep"},
    )
    verify_state = _state(current_state=STATE_AWAITING_HUMAN)

    prep_targets = read_valid_targets(
        RunStateView(run_id="run-prep", raw_state=prep_state),
        binding,
        recovery=True,
    )
    verify_targets = read_valid_targets(
        RunStateView(run_id="run-verify", raw_state=verify_state),
        binding,
        recovery=True,
    )

    assert prep_targets[0].id == "resume-clarify"
    assert prep_targets[0].metadata["operator_action"] == "resume-clarify"
    assert verify_targets[0].id == "verify-human"
    assert verify_targets[0].metadata["operator_action"] == "verify-human"


def test_unknown_or_malformed_projection_states_return_diagnostics() -> None:
    binding = planning_control_binding()

    malformed = read_valid_targets(
        RunStateView(run_id="run-bad", raw_state={"current_state": STATE_BLOCKED}),
        binding,
        recovery=True,
    )
    unknown = read_valid_targets(
        RunStateView(
            run_id="run-unknown",
            raw_state=_state(
                current_state=STATE_BLOCKED,
                resume_cursor={"phase": "bogus"},
            ),
        ),
        binding,
        recovery=True,
    )

    assert tuple(malformed) == ()
    assert malformed.recover_targets == ()
    assert malformed.diagnostics[0]["kind"] == "diagnostic"
    assert malformed.diagnostics[0]["code"] == "malformed_plan_state"
    assert malformed.diagnostics[0]["actionable"] is False
    assert tuple(unknown) == ()
    assert unknown.recover_targets == ()
    assert unknown.diagnostics[0]["kind"] == "diagnostic"
    assert unknown.diagnostics[0]["code"] == "unknown_recovery_phase"
    assert unknown.diagnostics[0]["phase"] == "bogus"


def test_planning_binding_module_does_not_route_through_legacy_planning_bindings() -> None:
    import megaplan.planning.control_binding as planning_control_binding_module

    source = inspect.getsource(planning_control_binding_module)

    assert "_pipeline.planning_bindings" not in source
