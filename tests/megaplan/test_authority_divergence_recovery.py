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
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED
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
