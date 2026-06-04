from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import patch

from megaplan._core.state import write_plan_state
from megaplan._core.workflow import workflow_next
from megaplan.control_interface import (
    CONTROL_TARGET_ABORT,
    CONTROL_TARGET_FORCE_ADVANCE,
    CONTROL_TARGET_RECOVER_FROM_STUCK,
    CONTROL_TARGET_REROUTE,
    ControlTargetRef,
    ControlTransitionRequest,
    RunStateView,
    apply_transition,
    read_valid_targets,
)
from megaplan.planning import PlanningControlBinding, planning_control_binding
from megaplan.planning.control_binding import (
    planning_run_state_view,
    planning_supervisor_run_state_view,
)
from megaplan.planning.state import (
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_CRITIQUED,
    STATE_EXECUTED,
    STATE_FAILED,
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


def _read(plan_dir: Path) -> dict:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


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


def test_supervisor_projection_uses_neutral_ids_for_escalation_and_recovery() -> None:
    binding = planning_control_binding()

    critiqued_targets = read_valid_targets(
        planning_supervisor_run_state_view(_state(current_state=STATE_CRITIQUED)),
        binding,
    )
    blocked_targets = read_valid_targets(
        planning_supervisor_run_state_view(
            _state(
                current_state=STATE_BLOCKED,
                resume_cursor={"phase": "execute", "retry_strategy": "fresh_session"},
            )
        ),
        binding,
        recovery=True,
    )
    failed_targets = read_valid_targets(
        planning_supervisor_run_state_view(
            _state(
                current_state=STATE_FAILED,
                latest_failure={"metadata": {"phase_result": {"phase": "execute"}}},
            )
        ),
        binding,
        recovery=True,
    )

    assert [target.id for target in critiqued_targets] == [
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_ABORT,
    ]
    assert [target.id for target in blocked_targets] == [CONTROL_TARGET_RECOVER_FROM_STUCK]
    assert [target.id for target in failed_targets] == [CONTROL_TARGET_REROUTE]


def test_legacy_and_supervisor_projections_keep_distinct_action_ids() -> None:
    binding = planning_control_binding()

    legacy_critiqued_targets = read_valid_targets(
        planning_run_state_view(_state(current_state=STATE_CRITIQUED)),
        binding,
    )
    supervisor_critiqued_targets = read_valid_targets(
        planning_supervisor_run_state_view(_state(current_state=STATE_CRITIQUED)),
        binding,
    )
    legacy_failed_targets = read_valid_targets(
        planning_run_state_view(
            _state(
                current_state=STATE_FAILED,
                latest_failure={"metadata": {"phase_result": {"phase": "execute"}}},
            )
        ),
        binding,
        recovery=True,
    )
    supervisor_failed_targets = read_valid_targets(
        planning_supervisor_run_state_view(
            _state(
                current_state=STATE_FAILED,
                latest_failure={"metadata": {"phase_result": {"phase": "execute"}}},
            )
        ),
        binding,
        recovery=True,
    )

    assert [target.id for target in legacy_critiqued_targets] == workflow_next(
        _state(current_state=STATE_CRITIQUED)
    )
    assert [target.id for target in supervisor_critiqued_targets] == [
        CONTROL_TARGET_FORCE_ADVANCE,
        CONTROL_TARGET_REROUTE,
        CONTROL_TARGET_ABORT,
    ]
    assert [target.id for target in legacy_failed_targets] == ["execute"]
    assert [target.id for target in supervisor_failed_targets] == [CONTROL_TARGET_REROUTE]


def test_supervisor_projection_leaves_awaiting_human_without_neutral_recovery_target() -> None:
    targets = read_valid_targets(
        planning_supervisor_run_state_view(
            _state(
                current_state=STATE_AWAITING_HUMAN,
                clarification={"source": "prep"},
            )
        ),
        planning_control_binding(),
        recovery=True,
    )

    assert tuple(targets) == ()
    assert targets.recover_targets == ()


def test_planning_binding_module_does_not_route_through_legacy_planning_bindings() -> None:
    import megaplan.planning.control_binding as planning_control_binding_module

    source = inspect.getsource(planning_control_binding_module)

    assert "_pipeline.planning_bindings" not in source


def test_neutral_force_advance_maps_to_force_proceed_with_plan_dir(tmp_path: Path) -> None:
    write_plan_state(
        tmp_path,
        mode="replace",
        state=_state(
            current_state=STATE_EXECUTED,
            metadata={"plan_dir": "wrong-plan-dir"},
            meta={"notes": [], "overrides": []},
        ),
    )

    result = apply_transition(
        _read(tmp_path),
        ControlTransitionRequest(
            action=CONTROL_TARGET_FORCE_ADVANCE,
            reason="ship it",
            expected_versions={"current_state": 0, "meta": 0},
        ),
        binding="planning",
        plan_dir=tmp_path,
    )

    assert result.accepted is True
    assert result.reason == "force-proceed"
    state = _read(tmp_path)
    assert state["current_state"] == "done"
    assert state["meta"]["overrides"][-1]["action"] == "force-proceed"
    assert state["meta"]["overrides"][-1]["reason"] == "ship it"


def test_legacy_force_proceed_still_uses_passed_plan_dir(tmp_path: Path) -> None:
    write_plan_state(
        tmp_path,
        mode="replace",
        state=_state(
            current_state=STATE_EXECUTED,
            metadata={"plan_dir": "wrong-plan-dir"},
            meta={"notes": [], "overrides": []},
        ),
    )

    result = apply_transition(
        _read(tmp_path),
        ControlTransitionRequest(
            action="force-proceed",
            reason="legacy ship it",
            expected_versions={"current_state": 0, "meta": 0},
        ),
        binding="planning",
        plan_dir=tmp_path,
    )

    assert result.accepted is True
    assert result.reason == "force-proceed"
    state = _read(tmp_path)
    assert state["current_state"] == "done"
    assert state["meta"]["overrides"][-1]["action"] == "force-proceed"
    assert state["meta"]["overrides"][-1]["reason"] == "legacy ship it"


def test_neutral_re_route_maps_to_replan(tmp_path: Path) -> None:
    write_plan_state(
        tmp_path,
        mode="replace",
        state=_state(
            current_state=STATE_FINALIZED,
            plan_versions=[{"file": "plan_v1.md"}],
            meta={"notes": [], "overrides": []},
        ),
    )
    (tmp_path / "plan_v1.md").write_text("# plan\n", encoding="utf-8")

    result = apply_transition(
        _read(tmp_path),
        ControlTransitionRequest(
            action=CONTROL_TARGET_REROUTE,
            reason="loop back",
            note="needs new plan",
            expected_versions={"current_state": 0, "last_gate": 0, "meta": 0},
        ),
        binding="planning",
        plan_dir=tmp_path,
    )

    assert result.accepted is True
    assert result.reason == "replan"
    state = _read(tmp_path)
    assert state["current_state"] == STATE_PLANNED
    assert state["meta"]["overrides"][-1]["action"] == "replan"


def test_neutral_recover_from_stuck_maps_to_recover_blocked(tmp_path: Path) -> None:
    write_plan_state(
        tmp_path,
        mode="replace",
        state=_state(
            current_state=STATE_BLOCKED,
            resume_cursor={"phase": "execute", "retry_strategy": "fresh_session"},
            meta={"notes": [], "overrides": []},
        ),
    )
    with (
        patch(
            "megaplan.planning.control_binding.read_phase_result",
            return_value=type(
                "_PhaseResult",
                (),
                {"blocked_tasks": (), "deviations": (), "exit_kind": "blocked_by_prereq"},
            )(),
        ),
        patch(
            "megaplan.planning.control_binding.evaluate_blocker_recovery",
            return_value=type(
                "_Eval",
                (),
                {
                    "can_continue": True,
                    "requires_rerun": False,
                    "blockers": (
                        type("_Blocker", (), {"blocker_id": "prereq:ua1:T1"})(),
                    ),
                },
            )(),
        ),
        patch(
            "megaplan.planning.control_binding.command_blocker_details",
            return_value=(
                {
                    "blocker_id": "prereq:ua1:T1",
                    "is_non_terminal": True,
                },
            ),
        ),
    ):
        result = apply_transition(
            _read(tmp_path),
            ControlTransitionRequest(
                action=CONTROL_TARGET_RECOVER_FROM_STUCK,
                reason="user resolved blocker",
                expected_versions={"current_state": 0, "meta": 0},
            ),
            binding="planning",
            plan_dir=tmp_path,
        )

    assert result.accepted is True
    assert result.reason == "recover-blocked"
    state = _read(tmp_path)
    assert state["current_state"] == STATE_FINALIZED
    assert state["meta"]["overrides"][-1]["action"] == "recover-blocked"
