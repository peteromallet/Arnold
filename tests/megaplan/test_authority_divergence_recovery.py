from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path
from typing import Callable

import pytest

from arnold_pipelines.megaplan._core.io import plans_root
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.cli.parser import build_parser
from arnold_pipelines.megaplan.cli.status_view import handle_status
from arnold_pipelines.megaplan.handlers import override as override_handler
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.orchestration.phase_result import (
    Deviation,
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
)
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED
from arnold_pipelines.megaplan.quality_resolutions import build_quality_resolution_event
from arnold_pipelines.megaplan.types import CliError
from tests.conftest import load_state


@dataclasses.dataclass
class LocalPlanFixture:
    root: Path
    project_dir: Path
    plan_name: str
    plan_dir: Path
    make_args: Callable[..., argparse.Namespace]


@pytest.fixture
def local_plan_fixture(tmp_path: Path) -> LocalPlanFixture:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    base = build_parser().parse_args(["init"])

    def make_args(**kwargs: object) -> argparse.Namespace:
        args = argparse.Namespace(**vars(base))
        args.project_dir = str(project_dir)
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    response = handle_init(
        root,
        make_args(idea="fixture plan", name="fixture-plan", robustness="standard"),
    )
    plan_name = response["plan"]
    plan_dir = plans_root(root) / plan_name
    return LocalPlanFixture(root, project_dir, plan_name, plan_dir, make_args)


def _set_authority_divergence_blocked_state(fixture: LocalPlanFixture) -> None:
    state = load_state(fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "rerun_phase"}
    state["latest_failure"] = {
        "kind": "authority_divergence",
        "message": "execute terminal success lacks corroborated task completion",
        "phase": "execute",
        "state": STATE_BLOCKED,
    }
    write_plan_state(fixture.plan_dir, mode="replace", state=state)


def test_status_projects_execute_for_authority_divergence_block(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    _set_authority_divergence_blocked_state(local_plan_fixture)

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "execute"
    assert response["valid_next"] == ["execute"]


def test_recover_blocked_rejects_authority_divergence(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    _set_authority_divergence_blocked_state(local_plan_fixture)

    with pytest.raises(CliError) as exc_info:
        override_handler.handle_override(
            local_plan_fixture.root,
            local_plan_fixture.make_args(
                plan=local_plan_fixture.plan_name,
                override_action="recover-blocked",
                reason="retry automation",
            ),
        )

    assert exc_info.value.code == "rerun_phase_required"
    assert "fresh phase rerun" in exc_info.value.message
    assert exc_info.value.extra["rerun_command"] == (
        f"megaplan execute --plan {local_plan_fixture.plan_name} "
        "--confirm-destructive --user-approved"
    )


def test_status_projects_execute_for_stale_recover_blocked_iteration_cap(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "recover-blocked",
        "retry_strategy": "manual_review",
    }
    state["latest_failure"] = {
        "kind": "iteration_cap",
        "message": "exceeded max_iterations=200",
        "phase": "recover-blocked",
        "state": STATE_BLOCKED,
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
        ),
    )

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "execute"
    assert response["valid_next"] == ["execute"]


def test_status_projects_execute_for_stale_recover_blocked_failure(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "fresh_session",
    }
    state["latest_failure"] = {
        "kind": "blocked_recovery_not_resolved",
        "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
        "phase": "recover-blocked",
        "state": STATE_BLOCKED,
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
        ),
    )

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "execute"
    assert response["valid_next"] == ["execute"]


def test_recover_blocked_allows_fixed_quality_rerun(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state.setdefault("meta", {})["quality_gate_resolutions"] = [
        build_quality_resolution_event(
            blocker_id="quality:global:pending-tasks",
            resolution="fixed",
            phase="execute",
        )
    ]
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    (local_plan_fixture.plan_dir / "finalize.json").write_text(
        '{"tasks":[]}\n',
        encoding="utf-8",
    )
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
            deviations=(
                Deviation(
                    kind="quality_gate",
                    message=(
                        "Advisory audit finding: Tasks left pending after execute "
                        "(executor never started them): T12, T13, T14"
                    ),
                    blocker_id="quality:global:pending-tasks",
                ),
            ),
        ),
    )

    response = override_handler.handle_override(
        local_plan_fixture.root,
        local_plan_fixture.make_args(
            plan=local_plan_fixture.plan_name,
            override_action="recover-blocked",
            reason="rerun execute after resolving quality blockers as fixed",
        ),
    )

    updated = load_state(local_plan_fixture.plan_dir)
    assert response["success"] is True
    assert response["state"] == "finalized"
    assert response["next_step"] == "execute"
    assert updated["current_state"] == "finalized"
