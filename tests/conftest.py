from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    Deviation,
    ExternalError,
    PhaseResult,
    atomic_write_phase_result,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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
