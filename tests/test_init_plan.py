from __future__ import annotations

import json
import subprocess
import sys
import time
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import megaplan
import megaplan._core
import megaplan.cli
import megaplan.execute.core
import megaplan.handlers
import megaplan.workers
from megaplan._core import WORKFLOW, _ROBUSTNESS_OVERRIDES, clear_active_step, save_state, set_active_step, workflow_next
from megaplan.orchestration.evaluation import PLAN_STRUCTURE_REQUIRED_STEP_ISSUE, validate_plan_structure
from megaplan.types import STATE_PREPPED, CliError
from megaplan.workers import WorkerResult, _build_mock_payload
from tests.conftest import (
    PlanFixture,
    _make_plan_fixture_with_robustness,
    latest_plan_name,
    load_state,
    make_args_factory,
    read_json,
)


def test_init_sets_last_gate_and_next_step_plan(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == megaplan.STATE_INITIALIZED
    assert state["last_gate"] == {}


def test_init_includes_next_step_runtime(plan_fixture: PlanFixture) -> None:
    response = megaplan.handle_init(
        plan_fixture.root,
        plan_fixture.make_args(name="runtime-test"),
    )

    assert response["next_step"] == "plan"
    assert response["next_step_runtime"]["expected_duration_seconds"]["min"] == 60
    assert response["next_step_runtime"]["recommended_next_check_seconds"] == 120
    assert "Expected duration:" in response["next_step_runtime"]["duration_hint"]


def test_init_prep_direction_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--prep-direction lands in state['config']['prep_direction']."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(name="prep-direction-init", prep_direction="  focus on cache invalidation  "),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert state["config"]["prep_direction"] == "focus on cache invalidation"


def test_init_prep_direction_rejects_blank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    with pytest.raises(CliError) as info:
        megaplan.handle_init(
            root,
            make_args(name="prep-direction-blank", prep_direction="   "),
        )
    assert info.value.code == "invalid_args"
    assert "prep-direction" in str(info.value)


def test_init_without_prep_direction_omits_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(root, make_args(name="prep-direction-none"))
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert "prep_direction" not in state["config"]


def test_init_strict_notes_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--strict-notes should land in state['config']['strict_notes']."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(root, make_args(name="strict-on", strict_notes=True))
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert state["config"]["strict_notes"] is True


def test_init_metaplan_defaults_strict_notes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--mode metaplan (alias for doc) without --strict-notes should auto-enable it."""
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(
            name="meta-default",
            mode="metaplan",
            output="design.md",
        ),
    )
    plan_dir = megaplan.plans_root(root) / response["plan"]
    state = load_state(plan_dir)
    assert state["config"]["mode"] == "doc"
    assert state["config"]["strict_notes"] is True


def test_init_response_points_to_next_step_by_robustness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    make_args = make_args_factory(project_dir)
    standard = megaplan.handle_init(root, make_args(name="standard-plan", robustness="standard"))
    light = megaplan.handle_init(root, make_args(name="light-plan", robustness="light"))
    robust = megaplan.handle_init(root, make_args(name="robust-plan", robustness="robust"))
    assert standard["next_step"] == "plan"
    assert light["next_step"] == "plan"
    assert robust["next_step"] == "prep"


_LEGACY_STATE_MACHINE_CASES = [
    ({"current_state": megaplan.STATE_INITIALIZED, "last_gate": {}}, ["plan"]),
    ({"current_state": STATE_PREPPED, "last_gate": {}}, ["plan"]),
    ({"current_state": megaplan.STATE_PLANNED, "last_gate": {}}, ["critique", "plan", "step"]),
    ({"current_state": megaplan.STATE_CRITIQUED, "last_gate": {}}, ["gate", "step"]),
    ({"current_state": megaplan.STATE_CRITIQUED, "last_gate": {"recommendation": "ITERATE"}}, ["revise", "step"]),
    (
        {"current_state": megaplan.STATE_CRITIQUED, "last_gate": {"recommendation": "ESCALATE"}},
        ["override add-note", "override force-proceed", "override abort", "step"],
    ),
    (
        {"current_state": megaplan.STATE_CRITIQUED, "last_gate": {"recommendation": "PROCEED", "passed": False}},
        ["gate", "step"],
    ),
    (
        {
            "current_state": megaplan.STATE_CRITIQUED,
            "last_gate": {
                "recommendation": "PROCEED",
                "passed": False,
                "preflight_results": {
                    "project_dir_exists": True,
                    "project_dir_writable": True,
                    "success_criteria_present": True,
                    "claude_available": False,
                    "codex_available": False,
                },
            },
        },
        ["override force-proceed", "gate", "step"],
    ),
    ({"current_state": megaplan.STATE_GATED, "last_gate": {}}, ["finalize", "override replan", "step"]),
    ({"current_state": megaplan.STATE_FINALIZED, "last_gate": {}}, ["execute", "override replan", "step"]),
]


def test_infer_next_steps_matches_new_state_machine() -> None:
    for state, expected in _LEGACY_STATE_MACHINE_CASES:
        assert megaplan.infer_next_steps(state) == expected


def test_workflow_next_matches_legacy_partial_state_cases() -> None:
    for state, expected in _LEGACY_STATE_MACHINE_CASES:
        assert workflow_next(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            {"current_state": megaplan.STATE_INITIALIZED, "last_gate": {}, "config": {"robustness": "light"}},
            ["plan"],
        ),
        (
            {"current_state": megaplan.STATE_CRITIQUED, "last_gate": {}, "config": {"robustness": "light"}},
            ["revise", "step"],
        ),
        (
            {
                "current_state": megaplan.STATE_CRITIQUED,
                "last_gate": {"recommendation": "ESCALATE"},
                "config": {"robustness": "light"},
            },
            ["revise", "step"],
        ),
        (
            {"current_state": megaplan.STATE_EXECUTED, "last_gate": {}, "config": {"robustness": "light"}},
            [],
        ),
    ],
)
def test_workflow_next_light_robustness_overrides(state: dict[str, object], expected: list[str]) -> None:
    assert workflow_next(state) == expected


def test_workflow_definition_is_complete_for_standard_flow() -> None:
    expected_states = {
        megaplan.STATE_INITIALIZED,
        megaplan.STATE_PLANNED,
        megaplan.STATE_CRITIQUED,
        megaplan.STATE_GATED,
        megaplan.STATE_FINALIZED,
        megaplan.STATE_EXECUTED,
    }

    assert expected_states.issubset(WORKFLOW)
    for state_name, transitions in WORKFLOW.items():
        assert transitions or state_name in megaplan.TERMINAL_STATES
    for robustness, overrides in _ROBUSTNESS_OVERRIDES.items():
        assert robustness in megaplan._core.ROBUSTNESS_LEVELS
        assert set(overrides).issubset(WORKFLOW)


def test_workflow_walk_matches_documented_standard_flow() -> None:
    walk = [
        ({"current_state": megaplan.STATE_INITIALIZED, "last_gate": {}}, "plan"),
        ({"current_state": megaplan.STATE_PLANNED, "last_gate": {}}, "critique"),
        ({"current_state": megaplan.STATE_CRITIQUED, "last_gate": {}}, "gate"),
        (
            {"current_state": megaplan.STATE_CRITIQUED, "last_gate": {"recommendation": "ITERATE"}},
            "revise",
        ),
        ({"current_state": megaplan.STATE_PLANNED, "last_gate": {}}, "critique"),
        (
            {
                "current_state": megaplan.STATE_CRITIQUED,
                "last_gate": {"recommendation": "PROCEED", "passed": True},
            },
            "gate",
        ),
        ({"current_state": megaplan.STATE_GATED, "last_gate": {}}, "finalize"),
        ({"current_state": megaplan.STATE_FINALIZED, "last_gate": {}}, "execute"),
        ({"current_state": megaplan.STATE_EXECUTED, "last_gate": {}}, "review"),
    ]

    actual_steps: list[str] = []
    for state, expected_step in walk:
        assert expected_step in workflow_next(state)
        actual_steps.append(expected_step)

    assert actual_steps == [
        "plan",
        "critique",
        "gate",
        "revise",
        "critique",
        "gate",
        "finalize",
        "execute",
        "review",
    ]


def test_workflow_walk_matches_documented_robust_flow() -> None:
    robust_config = {"config": {"robustness": "robust"}}
    walk = [
        ({"current_state": megaplan.STATE_INITIALIZED, "last_gate": {}, **robust_config}, "prep"),
        ({"current_state": STATE_PREPPED, "last_gate": {}, **robust_config}, "plan"),
        ({"current_state": megaplan.STATE_PLANNED, "last_gate": {}, **robust_config}, "critique"),
        ({"current_state": megaplan.STATE_CRITIQUED, "last_gate": {}, **robust_config}, "gate"),
        (
            {"current_state": megaplan.STATE_CRITIQUED, "last_gate": {"recommendation": "ITERATE"}, **robust_config},
            "revise",
        ),
        ({"current_state": megaplan.STATE_PLANNED, "last_gate": {}, **robust_config}, "critique"),
        (
            {
                "current_state": megaplan.STATE_CRITIQUED,
                "last_gate": {"recommendation": "PROCEED", "passed": True},
                **robust_config,
            },
            "gate",
        ),
        ({"current_state": megaplan.STATE_GATED, "last_gate": {}, **robust_config}, "finalize"),
        ({"current_state": megaplan.STATE_FINALIZED, "last_gate": {}, **robust_config}, "execute"),
        ({"current_state": megaplan.STATE_EXECUTED, "last_gate": {}, **robust_config}, "review"),
    ]

    actual_steps: list[str] = []
    for state, expected_step in walk:
        assert expected_step in workflow_next(state)
        actual_steps.append(expected_step)

    assert actual_steps == [
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "critique",
        "gate",
        "finalize",
        "execute",
        "review",
    ]


def test_workflow_walk_matches_documented_light_flow() -> None:
    light_config = {"config": {"robustness": "light"}}
    walk = [
        ({"current_state": megaplan.STATE_INITIALIZED, "last_gate": {}, **light_config}, "plan"),
        ({"current_state": megaplan.STATE_PLANNED, "last_gate": {}, **light_config}, "critique"),
        ({"current_state": megaplan.STATE_CRITIQUED, "last_gate": {}, **light_config}, "revise"),
        ({"current_state": megaplan.STATE_GATED, "last_gate": {}, **light_config}, "finalize"),
        ({"current_state": megaplan.STATE_FINALIZED, "last_gate": {}, **light_config}, "execute"),
    ]

    actual_steps: list[str] = []
    for state, expected_step in walk:
        assert expected_step in workflow_next(state)
        actual_steps.append(expected_step)

    assert workflow_next({"current_state": megaplan.STATE_EXECUTED, "last_gate": {}, **light_config}) == []
    assert actual_steps == ["plan", "critique", "revise", "finalize", "execute"]


def test_non_tiny_robustness_levels_route_planned_to_critique() -> None:
    """All robustness levels except tiny go directly from planned to critique.
    Tiny skips critique entirely and routes planned -> finalize."""
    for level in ("light", "standard", "robust", "superrobust"):
        state = {"current_state": megaplan.STATE_PLANNED, "last_gate": {}, "config": {"robustness": level}}
        next_steps = workflow_next(state)
        assert "critique" in next_steps, f"{level} should offer critique"
        assert "research" not in next_steps, f"{level} should not offer research"


def test_tiny_robustness_routes_planned_to_finalize() -> None:
    """At tiny robustness, planned -> finalize directly (critique is bypassed)."""
    state = {"current_state": megaplan.STATE_PLANNED, "last_gate": {}, "config": {"robustness": "tiny"}}
    next_steps = workflow_next(state)
    assert "finalize" in next_steps, "tiny should offer finalize from planned"
    assert "critique" not in next_steps, "tiny should not offer critique"


def test_handle_plan_sets_and_clears_active_step(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run_step_with_worker(step: str, state: dict, plan_dir: Path, args: Namespace, **kwargs: object):
        del state, args, kwargs
        persisted = read_json(plan_dir / "state.json")
        observed.update(persisted["active_step"])
        return (
            WorkerResult(
                payload=_build_mock_payload(step, load_state(plan_dir), plan_dir),
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="session-1",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.handlers.worker_module, "run_step_with_worker", fake_run_step_with_worker)

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert observed["phase"] == "plan"
    assert "started_at" in observed
    assert "active_step" not in state


def test_handle_plan_failure_clears_active_step(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run_step_with_worker(step: str, state: dict, plan_dir: Path, args: Namespace, **kwargs: object):
        del step, state, args, kwargs
        persisted = read_json(plan_dir / "state.json")
        observed.update(persisted["active_step"])
        raise megaplan.CliError("worker_error", "boom", extra={"raw_output": "boom"})

    monkeypatch.setattr(megaplan.handlers.worker_module, "run_step_with_worker", fake_run_step_with_worker)

    with pytest.raises(megaplan.CliError, match="boom"):
        megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert observed["phase"] == "plan"
    assert "active_step" not in state


def test_clear_active_step_ignores_mismatched_run_id() -> None:
    state = {"sessions": {}}
    first_run_id = set_active_step(state, step="plan", agent="codex", mode="persistent")
    second_run_id = set_active_step(state, step="critique", agent="claude", mode="persistent")

    clear_active_step(state, run_id=first_run_id)

    assert state["active_step"]["phase"] == "critique"
    assert state["active_step"]["run_id"] == second_run_id


def test_handle_status_reports_observability_fields(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["meta"]["notes"] = [{"timestamp": "2026-04-09T00:00:00Z", "note": "Newest note."}]
    state["active_step"] = {
        "phase": "critique",
        "agent": "claude",
        "mode": "persistent",
        "started_at": "2026-04-09T00:00:00Z",
        "session_id": "critique-session",
    }
    state["sessions"] = {
        "claude_critic": {
            "id": "critique-session",
            "mode": "persistent",
            "created_at": "2026-04-09T00:00:00Z",
            "last_used_at": "2026-04-09T00:05:00Z",
            "refreshed": False,
        }
    }
    state["history"].append(
        {
            "step": "plan",
            "timestamp": "2026-04-09T00:01:00Z",
            "duration_ms": 1,
            "cost_usd": 0.0,
            "result": "success",
            "output_file": "plan_v1.md",
        }
    )
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["notes_count"] == 1
    assert response["notes"][0]["note"] == "Newest note."
    assert response["last_step"]["step"] == "plan"
    assert response["active_step"]["phase"] == "critique"
    assert response["active_step"]["session_id"] == "critique-session"
    assert "stale" in response["active_step"]
    assert response["active_step"]["artifact_mode"] == "completion_only"
    assert response["active_step"]["recommended_action"] == "rerun_same_step"
    assert response["active_step"]["recommended_next_check_seconds"] == 120
    assert response["active_step"]["expected_duration_seconds"]["max"] == 900
    assert response["active_step"]["timeout_budget_seconds"] == 900
    assert response["active_step"]["escalation_threshold_seconds"] == 900
    assert response["active_step"]["orphaned"] is True
    assert "critique stale" in response["active_step"]["phase_progress_summary"]
    assert "rerun the same step" in response["active_step"]["recovery_hint"].lower()
    assert response["next_step_runtime"]["expected_duration_seconds"]["min"] == 60
    assert response["session_summaries"][0]["key"] == "claude_critic"
    assert response["lock_file_present"] is False
    assert response["lock_held"] is False


def _drive_to_finalized(plan_fixture: PlanFixture) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))


def test_handle_status_uses_execute_runtime_guidance(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["active_step"] = {
        "phase": "execute",
        "agent": "codex",
        "mode": "persistent",
        "started_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
    }
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["active_step"]["artifact_mode"] == "completion_only"
    assert response["active_step"]["recommended_next_check_seconds"] == 300
    assert response["active_step"]["timeout_budget_seconds"] == 7200
    assert response["active_step"]["expected_duration_seconds"]["max"] == 7200
    assert "execute running" in response["active_step"]["phase_progress_summary"]
    assert "progress_pct" not in response["active_step"]


def test_handle_status_includes_progress_when_finalize_exists(plan_fixture: PlanFixture) -> None:
    _drive_to_finalized(plan_fixture)
    state = load_state(plan_fixture.plan_dir)
    state["active_step"] = {
        "phase": "execute",
        "agent": "codex",
        "mode": "persistent",
        "started_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
    }
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["progress"]["tasks_total"] >= 1
    assert response["progress"]["tasks_pending"] == response["progress"]["tasks_total"]
    assert "Execution progress:" in response["summary"]


def test_handle_status_distinguishes_lock_file_from_held_lock(plan_fixture: PlanFixture) -> None:
    lock_path = plan_fixture.plan_dir / ".plan.lock"
    lock_path.write_text("", encoding="utf-8")

    response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["lock_file_present"] is True
    assert response["lock_held"] is False
    assert ".plan.lock" not in response["artifacts"]
    assert "may remain on disk" in response["summary"]


def test_handle_watch_combines_status_and_progress(plan_fixture: PlanFixture) -> None:
    _drive_to_finalized(plan_fixture)

    status_response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.cli.handle_watch(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["step"] == "watch"
    expected = dict(status_response)
    expected["step"] = "watch"
    assert response == expected


def test_phase_progress_summary_completion_only(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["active_step"] = {
        "phase": "critique",
        "agent": "codex",
        "mode": "persistent",
        "started_at": (datetime.now(timezone.utc) - timedelta(minutes=3, seconds=12)).isoformat().replace("+00:00", "Z"),
    }
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert "critique running" in response["active_step"]["phase_progress_summary"]
    assert 0 <= response["active_step"]["progress_pct"] <= 95


def test_phase_progress_summary_stale(plan_fixture: PlanFixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["active_step"] = {
        "phase": "plan",
        "agent": "claude",
        "mode": "persistent",
        "started_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.cli.handle_status(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert "plan stale" in response["active_step"]["phase_progress_summary"]


def test_plan_rerun_keeps_iteration_and_uses_same_iteration_subversion(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="add-note", note="answer to questions"),
    )
    response = megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert response["iteration"] == 1
    assert state["iteration"] == 1
    assert (plan_fixture.plan_dir / "plan_v1.md").exists()
    assert (plan_fixture.plan_dir / "plan_v1a.md").exists()


def test_override_add_note_includes_next_step_runtime(plan_fixture: PlanFixture) -> None:
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="Keep going.",
        ),
    )

    assert response["next_step"] == "plan"
    assert response["next_step_runtime"]["recommended_next_check_seconds"] == 120


def test_handle_plan_includes_next_step_runtime(plan_fixture: PlanFixture) -> None:
    response = megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["next_step"] == "critique"
    assert response["next_step_runtime"]["recommended_next_check_seconds"] == 120
    assert "Expected duration:" in response["next_step_runtime"]["duration_hint"]


def test_build_monitor_hint_references_status(plan_fixture: PlanFixture) -> None:
    hint = megaplan.execute.core.build_monitor_hint(plan_fixture.plan_dir)

    assert "status" in hint
    assert "watch" not in hint


def test_format_duration_hint_uses_human_readable_ranges() -> None:
    critique_hint = megaplan._core.format_duration_hint(
        "critique",
        configured_timeout_seconds=7200,
    )
    execute_hint = megaplan._core.format_duration_hint(
        "execute",
        configured_timeout_seconds=7200,
    )

    assert critique_hint == "Expected duration: 1m-15m."
    assert execute_hint == "Expected minimum duration: 5m (depends on task count)."


def test_emit_phase_notice_logs_on_megaplan_logger(caplog: pytest.LogCaptureFixture) -> None:
    import logging
    caplog.set_level(logging.INFO, logger="megaplan")
    megaplan.handlers._emit_phase_notice("plan")

    assert "[megaplan]" in caplog.text
    assert "plan" in caplog.text
    assert "Expected duration:" in caplog.text
    assert any(record.name == "megaplan" for record in caplog.records)


def test_emit_phase_notice_ignores_non_phase_commands(caplog: pytest.LogCaptureFixture) -> None:
    import logging
    caplog.set_level(logging.INFO, logger="megaplan")
    megaplan.handlers._emit_phase_notice("status")

    assert caplog.text == ""


def test_workflow_mock_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from megaplan.handlers import handle_prep

    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="robust")
    make_args = plan_fixture.make_args
    recorded_steps: list[str] = []
    original_run_step = megaplan.workers.run_step_with_worker

    def _record(step: str, *args: object, **kwargs: object) -> tuple[WorkerResult, str, str, bool]:
        recorded_steps.append(step)
        return original_run_step(step, *args, **kwargs)

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _record)
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="add-note", note="keep changes scoped"),
    )
    prep = handle_prep(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    plan = megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    critique1 = megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    gate1 = megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    revise = megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    critique2 = megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    gate2 = megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize = megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalized_tracking = read_json(plan_fixture.plan_dir / "finalize.json")
    final_md_after_finalize = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")
    execute = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    finalized_after_execute = read_json(plan_fixture.plan_dir / "finalize.json")
    final_md_after_execute = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")
    review = megaplan.handle_review(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalized_after_review = read_json(plan_fixture.plan_dir / "finalize.json")
    review_after_review = read_json(plan_fixture.plan_dir / "review.json")
    final_md_after_review = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")
    plan_meta = read_json(plan_fixture.plan_dir / "plan_v1.meta.json")
    revise_meta = read_json(plan_fixture.plan_dir / "plan_v2.meta.json")
    state = load_state(plan_fixture.plan_dir)

    assert prep["state"] == STATE_PREPPED
    assert prep["next_step"] == "plan"
    assert plan["state"] == megaplan.STATE_PLANNED
    assert plan["next_step"] == "critique"
    assert critique1["state"] == megaplan.STATE_CRITIQUED
    assert gate1["recommendation"] == "ITERATE"
    assert revise["state"] == megaplan.STATE_PLANNED
    assert revise["next_step"] == "critique"
    assert critique2["iteration"] == 2
    assert gate2["state"] == megaplan.STATE_GATED
    assert gate2["recommendation"] == "PROCEED"
    assert finalize["state"] == megaplan.STATE_FINALIZED
    assert plan_meta["structure_warnings"] == []
    assert revise_meta["structure_warnings"] == []
    assert (plan_fixture.plan_dir / "final.md").exists()
    assert (plan_fixture.plan_dir / "finalize.json").exists()
    assert (plan_fixture.plan_dir / "prep.json").exists()
    assert finalized_tracking["tasks"][0]["status"] == "pending"
    assert "# Execution Checklist" in final_md_after_finalize
    assert execute["state"] == megaplan.STATE_EXECUTED
    assert all(task["status"] == "done" for task in finalized_after_execute["tasks"])
    assert all(task["executor_notes"] for task in finalized_after_execute["tasks"])
    assert "Executor notes:" in final_md_after_execute
    assert review["state"] == megaplan.STATE_DONE
    assert all(task["reviewer_verdict"] == "" for task in finalized_after_review["tasks"])
    assert all(verdict["reviewer_verdict"] for verdict in review_after_review["task_verdicts"])
    assert all(verdict["verdict"] for verdict in review_after_review["sense_check_verdicts"])
    assert "Reviewer verdict:" in final_md_after_review
    assert "Verdict:" in final_md_after_review
    execute_entry = next(entry for entry in state["history"] if entry["step"] == "execute")
    review_entry = next(entry for entry in state["history"] if entry["step"] == "review")
    assert execute_entry["finalize_hash"].startswith("sha256:")
    assert review_entry["finalize_hash"].startswith("sha256:")
    assert recorded_steps == [
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "critique",
        "gate",
        "finalize",
        "execute",
        "review",
    ]
    assert (plan_fixture.project_dir / "IMPLEMENTED_BY_MEGAPLAN.txt").exists()


def test_workflow_light_robustness_single_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="light")
    make_args = plan_fixture.make_args
    recorded_steps: list[str] = []
    original_run_step = megaplan.workers.run_step_with_worker

    def _record(step: str, *args: object, **kwargs: object) -> tuple[WorkerResult, str, str, bool]:
        recorded_steps.append(step)
        return original_run_step(step, *args, **kwargs)

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _record)

    plan = megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    assert plan["next_step"] == "critique"

    critique = megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    assert critique["next_step"] == "revise"

    revise = megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    assert revise["next_step"] == "finalize"
    assert revise["state"] == megaplan.STATE_GATED

    finalize = megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    execute = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    stored_review = read_json(plan_fixture.plan_dir / "review.json")

    assert finalize["state"] == megaplan.STATE_FINALIZED
    assert execute["state"] == megaplan.STATE_DONE
    assert execute["next_step"] is None
    assert "review.json" in execute["artifacts"]
    assert stored_review["review_verdict"] == "approved"
    assert recorded_steps == ["plan", "critique", "revise", "finalize", "execute"]
    assert [entry["step"] for entry in state["history"]] == [
        "init",
        "plan",
        "critique",
        "revise",
        "finalize",
        "execute",
    ]


def test_handle_plan_stores_nonblocking_structure_warnings(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = WorkerResult(
        payload={
            "plan": """# Implementation Plan: Warning Case

## Step 1: Touch one file (`megaplan/evaluation.py`)
1. **Implement** the change (`megaplan/evaluation.py:1`).

## Validation Order
1. Run a focused test.
""",
            "questions": [],
            "success_criteria": [{"criterion": "warn but continue", "priority": "must"}],
            "assumptions": [],
        },
        raw_output="warning case",
        duration_ms=1,
        cost_usd=0.0,
        session_id="plan-warning",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    meta = read_json(plan_fixture.plan_dir / "plan_v1.md".replace(".md", ".meta.json"))

    assert response["success"] is True
    assert meta["structure_warnings"] == ["Plan should include a `## Overview` section."]


def test_handle_prep_direction_arg_overrides_state(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`megaplan prep --direction` writes state.config.prep_direction before worker runs."""
    captured: dict[str, str | None] = {}
    worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "stub",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "stub",
        },
        raw_output="prep output",
        duration_ms=1,
        cost_usd=0.0,
        session_id="prep-direction",
    )

    def fake_run(step, state, plan_dir, args, **kwargs):
        del step, plan_dir, args, kwargs
        captured["prep_direction"] = state["config"].get("prep_direction")
        return (worker, "claude", "persistent", False)

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run)

    megaplan.handlers.handle_prep(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            prep_direction="trace the shutdown path in workers/shannon.py",
        ),
    )
    persisted = load_state(plan_fixture.plan_dir)
    assert captured["prep_direction"] == "trace the shutdown path in workers/shannon.py"
    assert persisted["config"]["prep_direction"] == "trace the shutdown path in workers/shannon.py"


def test_handle_prep_direction_blank_rejected(
    plan_fixture: PlanFixture,
) -> None:
    with pytest.raises(CliError) as info:
        megaplan.handlers.handle_prep(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, prep_direction="   "),
        )
    assert info.value.code == "invalid_args"


def test_handle_prep_harvests_primary_criterion_for_joke_mode(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "joke"
    state["config"]["output_path"] = "scenes/test.md"
    save_state(plan_fixture.plan_dir, state)

    worker = WorkerResult(
        payload={
            "skip": False,
            "task_summary": "Write a cafe return scene.",
            "primary_criterion": "weirdest coherent",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "Escalate through prop logic.",
        },
        raw_output="prep output",
        duration_ms=1,
        cost_usd=0.0,
        session_id="prep-primary-criterion",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handlers.handle_prep(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )
    updated = load_state(plan_fixture.plan_dir)

    assert response["state"] == STATE_PREPPED
    assert updated["config"]["primary_criterion"] == "weirdest coherent"


def test_handle_plan_rejects_joke_mode_without_primary_criterion(
    plan_fixture: PlanFixture,
) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "joke"
    state["config"]["output_path"] = "scenes/test.md"
    state["config"].pop("primary_criterion", None)
    save_state(plan_fixture.plan_dir, state)

    with pytest.raises(CliError) as info:
        megaplan.handle_plan(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name),
        )

    assert info.value.code == "invalid_state"
    assert "primary_criterion" in str(info.value)


def test_handle_plan_rejects_zero_step_structure_error(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = WorkerResult(
        payload={
            "plan": """# Implementation Plan: Invalid

## Overview
No numbered step sections here.

## Validation Order
1. Run a focused test.
""",
            "questions": [],
            "success_criteria": [{"criterion": "should fail", "priority": "must"}],
            "assumptions": [],
        },
        raw_output="invalid plan output",
        duration_ms=1,
        cost_usd=0.0,
        session_id="plan-invalid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match="structural validation"):
        megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    error_entry = state["history"][-1]
    assert error_entry["result"] == "error"
    assert PLAN_STRUCTURE_REQUIRED_STEP_ISSUE in error_entry["message"]


def test_step_add(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    response = megaplan.handle_step(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            step_action="add",
            after="S2",
            description="Add parser edge-case coverage",
        ),
    )
    state = load_state(plan_fixture.plan_dir)
    plan_name = latest_plan_name(plan_fixture.plan_dir)
    plan_text = (plan_fixture.plan_dir / plan_name).read_text(encoding="utf-8")
    latest_meta = read_json(plan_fixture.plan_dir / plan_name.replace(".md", ".meta.json"))
    previous_meta = read_json(plan_fixture.plan_dir / "plan_v1.meta.json")

    assert response["state"] == megaplan.STATE_PLANNED
    assert state["iteration"] == 1
    assert plan_name == "plan_v1a.md"
    assert state["last_gate"] == {}
    assert "## Step 3: Add parser edge-case coverage" in plan_text
    assert "## Step 4: Verify the behavior" in plan_text
    assert latest_meta["questions"] == previous_meta["questions"]
    assert latest_meta["success_criteria"] == previous_meta["success_criteria"]
    assert latest_meta["assumptions"] == previous_meta["assumptions"]
    assert latest_meta["step_edit"]["action"] == "add"


def test_step_add_scaffold_passes_validation(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_step(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            step_action="add",
            after="S1",
            description="Document the handler change",
        ),
    )

    plan_name = latest_plan_name(plan_fixture.plan_dir)
    plan_text = (plan_fixture.plan_dir / plan_name).read_text(encoding="utf-8")

    assert validate_plan_structure(plan_text) == []
    assert "1. **TODO** Fill in implementation details (`path/to/file`)." in plan_text


def test_step_remove(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    response = megaplan.handle_step(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, step_action="remove", step_id="S2"),
    )
    state = load_state(plan_fixture.plan_dir)
    plan_name = latest_plan_name(plan_fixture.plan_dir)
    plan_text = (plan_fixture.plan_dir / plan_name).read_text(encoding="utf-8")

    assert response["state"] == megaplan.STATE_PLANNED
    assert plan_name == "plan_v1a.md"
    assert state["iteration"] == 1
    assert "## Step 2: Verify the behavior" in plan_text
    assert "Implement the smallest viable change" not in plan_text


def test_step_move(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    response = megaplan.handle_step(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, step_action="move", step_id="S3", after="S1"),
    )
    plan_name = latest_plan_name(plan_fixture.plan_dir)
    plan_text = (plan_fixture.plan_dir / plan_name).read_text(encoding="utf-8")
    step_two_index = plan_text.index("## Step 2: Verify the behavior")
    step_three_index = plan_text.index("## Step 3: Implement the smallest viable change")

    assert response["state"] == megaplan.STATE_PLANNED
    assert plan_name == "plan_v1a.md"
    assert step_two_index < step_three_index


def test_step_remove_last_step_rejected(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = WorkerResult(
        payload={
            "plan": """# Implementation Plan: Single Step

## Overview
Keep the plan small.

## Step 1: Only step (`megaplan/handlers.py`)
1. **Implement** the change (`megaplan/handlers.py:1`).

## Validation Order
1. Run a focused test.
""",
            "questions": ["q"],
            "success_criteria": [{"criterion": "c", "priority": "must"}],
            "assumptions": ["a"],
        },
        raw_output="single-step plan",
        duration_ms=1,
        cost_usd=0.0,
        session_id="plan-single-step",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    with pytest.raises(megaplan.CliError, match="last remaining step"):
        megaplan.handle_step(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, step_action="remove", step_id="S1"),
        )


@pytest.mark.parametrize("state_name", [megaplan.STATE_DONE, megaplan.STATE_ABORTED])
def test_step_invalid_state(plan_fixture: PlanFixture, state_name: str) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = state_name
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(megaplan.CliError, match="Cannot run 'step'"):
        megaplan.handle_step(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                step_action="add",
                after="S1",
                description="Should fail",
            ),
        )


def test_step_preserves_meta(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    meta_path = plan_fixture.plan_dir / "plan_v1.meta.json"
    meta = read_json(meta_path)
    meta["questions"] = ["What should happen next?"]
    meta["success_criteria"] = [{"criterion": "Ship the step editor.", "priority": "must"}]
    meta["assumptions"] = ["The existing plan file is valid."]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    megaplan.handle_step(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, step_action="move", step_id="S3", after="S1"),
    )

    plan_name = latest_plan_name(plan_fixture.plan_dir)
    new_meta = read_json(plan_fixture.plan_dir / plan_name.replace(".md", ".meta.json"))

    assert new_meta["questions"] == ["What should happen next?"]
    assert new_meta["success_criteria"] == [{"criterion": "Ship the step editor.", "priority": "must"}]
    assert new_meta["assumptions"] == ["The existing plan file is valid."]


def test_step_edit_rejects_concurrent_plan_lock(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    ready_path = plan_fixture.root / "step-lock.ready"
    script = """
import fcntl
import sys
import time
from pathlib import Path

plan_dir = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
lock_path = plan_dir / ".plan.lock"
lock_path.parent.mkdir(parents=True, exist_ok=True)
handle = lock_path.open("a+", encoding="utf-8")
fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
ready_path.write_text("ready", encoding="utf-8")
time.sleep(30)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(plan_fixture.plan_dir), str(ready_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not ready_path.exists():
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                pytest.fail(f"lock helper exited early: stdout={stdout!r} stderr={stderr!r}")
            if time.monotonic() >= deadline:
                pytest.fail("lock helper did not acquire the plan lock in time")
            time.sleep(0.05)

        with pytest.raises(megaplan.CliError) as exc_info:
            megaplan.handle_step(
                plan_fixture.root,
                plan_fixture.make_args(
                    plan=plan_fixture.plan_name,
                    step_action="add",
                    after="S1",
                    description="Blocked by lock",
                ),
            )

        assert exc_info.value.code == "plan_locked"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_progress_all_pending(plan_fixture: PlanFixture) -> None:
    _drive_to_finalized(plan_fixture)
    response = megaplan.handle_progress(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )
    assert response["success"] is True
    assert response["tasks_pending"] == response["tasks_total"]
    assert response["tasks_done"] == 0
    assert response["batches_completed"] == 0
    assert response["batches_total"] >= 1


def test_progress_after_partial_execution(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _drive_to_finalized(plan_fixture)
    # Set up 2-batch plan: T1 (no deps), T2 (depends on T1)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "First",
            "depends_on": [],
            "status": "done",
            "executor_notes": "Done.",
            "files_changed": ["a.py"],
            "commands_run": ["pytest"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Second",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    response = megaplan.handle_progress(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )
    assert response["batches_completed"] == 1
    assert response["batches_total"] == 2
    assert response["tasks_done"] == 1
    assert response["tasks_pending"] == 1


def test_progress_after_full_execution(plan_fixture: PlanFixture) -> None:
    _drive_to_finalized(plan_fixture)
    megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    response = megaplan.handle_progress(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )
    assert response["tasks_done"] + response["tasks_skipped"] == response["tasks_total"]
    assert response["batches_completed"] == response["batches_total"]
    assert response["tasks_pending"] == 0
