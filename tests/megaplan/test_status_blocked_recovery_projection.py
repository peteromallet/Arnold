from __future__ import annotations

import argparse
import json
from pathlib import Path

from arnold_pipelines.megaplan._core.io import plans_root
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.cli.status_view import handle_status
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.orchestration.phase_result import (
    Deviation,
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
)
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED
from tests.conftest import load_state


def test_status_hides_recover_blocked_until_blockers_are_resolved(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    base = build_parser().parse_args(["init"])
    args = argparse.Namespace(**vars(base))
    args.project_dir = str(project_dir)

    init_args = argparse.Namespace(**vars(args))
    init_args.idea = "fixture plan"
    init_args.name = "fixture-plan"

    response = handle_init(root, init_args)
    plan_dir = plans_root(root) / response["plan"]

    state = load_state(plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {"phase": "review", "retry_strategy": "manual_review"}
    state["latest_failure"] = {
        "kind": "quality_gate_blocked",
        "message": "review found unresolved blockers",
        "phase": "review",
        "state": STATE_BLOCKED,
    }
    write_plan_state(plan_dir, mode="replace", state=state)

    (plan_dir / "finalize.json").write_text(json.dumps({"tasks": []}) + "\n", encoding="utf-8")
    atomic_write_phase_result(
        plan_dir,
        PhaseResult(
            phase="review",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
            deviations=(
                Deviation(
                    kind="quality_gate",
                    message="Backend replay routes are still missing.",
                ),
            ),
        ),
    )

    status = handle_status(
        root,
        argparse.Namespace(plan=response["plan"], pending_human=False),
    )

    assert status["state"] == STATE_BLOCKED
    assert status["next_step"] is None
    assert status["valid_next"] == []
    assert status["blocker_recovery"]["has_terminal_blockers"] is True
    assert "override recover-blocked" in " ".join(status["suggested_recovery_commands"])


def test_status_keeps_execute_available_for_finalized_plan_with_quality_blockers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    base = build_parser().parse_args(["init"])
    args = argparse.Namespace(**vars(base))
    args.project_dir = str(project_dir)

    init_args = argparse.Namespace(**vars(args))
    init_args.idea = "fixture plan"
    init_args.name = "fixture-plan"

    response = handle_init(root, init_args)
    plan_dir = plans_root(root) / response["plan"]

    state = load_state(plan_dir)
    state["current_state"] = "finalized"
    write_plan_state(plan_dir, mode="replace", state=state)

    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "status": "pending"}]}) + "\n",
        encoding="utf-8",
    )

    status = handle_status(
        root,
        argparse.Namespace(plan=response["plan"], pending_human=False),
    )

    assert status["state"] == "finalized"
    assert status["next_step"] == "execute"
    assert "execute" in status["valid_next"]
    assert status["valid_next"][0] == "execute"
    assert status["blocker_recovery"]["has_terminal_blockers"] is True
