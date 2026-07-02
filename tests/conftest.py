from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any, Callable

import pytest

import arnold_pipelines.megaplan as megaplan
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    Deviation,
    ExternalError,
    PhaseResult,
    atomic_write_phase_result,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclasses.dataclass
class PlanFixture:
    """Lightweight handle for a freshly initialized megaplan plan."""

    root: Path
    project_dir: Path
    plan_name: str
    plan_dir: Path
    make_args: Callable[..., argparse.Namespace]


def make_args_factory(project_dir: Path) -> Callable[..., argparse.Namespace]:
    """Return a helper that builds argparse Namespaces for megaplan handlers."""

    base = build_parser().parse_args(["init"])

    def _make_args(**kwargs: Any) -> argparse.Namespace:
        args = argparse.Namespace(**vars(base))
        args.project_dir = str(project_dir)
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    return _make_args


def load_state(plan_dir: Path) -> dict[str, Any]:
    """Read a plan's state.json."""

    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


@pytest.fixture
def plan_fixture(tmp_path: Path) -> PlanFixture:
    """Create a temporary megaplan plan and expose its directories/args helper."""

    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(idea="fixture plan", name="fixture-plan", robustness="standard"),
    )
    plan_name = response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name
    return PlanFixture(
        root=root,
        project_dir=project_dir,
        plan_name=plan_name,
        plan_dir=plan_dir,
        make_args=make_args,
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--backend",
        action="store",
        default=None,
        help="Optional storage backend selector used by Sprint 1 backend tests.",
    )
    parser.addoption(
        "--write-fixture",
        action="store_true",
        default=False,
        help="Regenerate characterization test fixtures on disk.",
    )
    parser.addoption(
        "--record-goldens",
        action="store_true",
        default=False,
        help="Record native golden trace fixtures to disk (multi-file directory format).",
    )


def read_json(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def make_fake_phase_result(
    plan_dir: Path,
    *,
    phase: str = "execute",
    exit_kind: str = "success",
    invocation_id: str = "fake-invocation-id",
    blocked_tasks: tuple[BlockedTask, ...] = (),
    deviations: tuple[Deviation, ...] = (),
    artifacts_written: tuple[str, ...] = (),
    cli_provenance: dict[str, object] | None = None,
    external_error: ExternalError | None = None,
) -> PhaseResult:
    """Write a synthetic ``phase_result.json`` to *plan_dir*."""
    result = PhaseResult(
        phase=phase,
        invocation_id=invocation_id,
        exit_kind=exit_kind,
        blocked_tasks=blocked_tasks,
        deviations=deviations,
        artifacts_written=artifacts_written,
        cli_provenance=cli_provenance or {},
        external_error=external_error,
    )
    atomic_write_phase_result(plan_dir, result)
    return result


def fake_run_with_phase_result(
    plan_dir: Path,
    *,
    exit_kind: str = "success",
    code: int = 0,
    stdout: str = "",
    stderr: str = "",
    **kwargs: object,
):
    """Return a fake phase runner that also writes ``phase_result.json``."""

    def _runner(
        cmd: list[str],
        *,
        cwd=None,
        timeout=None,
        idle_timeout=None,
        progress_env=None,
        liveness_plan_dir=None,
    ) -> tuple[int, str, str]:
        make_fake_phase_result(plan_dir, exit_kind=exit_kind, **kwargs)
        return code, stdout, stderr

    return _runner
