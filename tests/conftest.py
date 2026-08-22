from __future__ import annotations

import argparse
import dataclasses
import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable

import pytest

from arnold_pipelines.megaplan._core.io import plans_root
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    Deviation,
    ExternalError,
    PhaseResult,
    atomic_write_phase_result,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolate_nested_pytest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermeticity boundary for tests that spawn nested pytest processes.

    Shard/hermetic runners export ``PYTEST_ADDOPTS`` (for example
    ``--basetemp=<shared shard temp>``) into the outer test process. Nested
    pytest runs spawned by these tests inherit that option, clear the shared
    basetemp on startup, and delete the outer test's tmp tree mid-flight. Strip
    the outer pytest CLI environment at the boundary so nested validation runs
    manage their own temporary state.
    """
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)


@pytest.fixture
def isolate_user_megaplan_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hermeticity boundary for tests that load megaplan profiles.

    ``load_profiles`` consults the operator's real ``$XDG_CONFIG_HOME``/
    ``~/.config/megaplan/profiles.toml``. Point the lookup at the test's own
    tmp tree so profile resolution depends only on repo and fixture state.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))


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


def _make_plan_fixture_with_robustness(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    robustness: str,
) -> PlanFixture:
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    project_dir = root / "project"
    project_dir.mkdir()
    make_args = make_args_factory(project_dir)
    response = handle_init(
        root,
        make_args(
            idea="fixture plan",
            name="fixture-plan",
            robustness=robustness,
        ),
    )
    plan_name = response["plan"]
    return PlanFixture(
        root=root,
        project_dir=project_dir,
        plan_name=plan_name,
        plan_dir=plans_root(root) / plan_name,
        make_args=make_args,
    )


@pytest.fixture
def plan_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PlanFixture:
    """Create a temporary megaplan plan and expose its directories/args helper."""

    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    root = tmp_path / "root"
    root.mkdir()
    return _make_plan_fixture_with_robustness(
        root,
        monkeypatch,
        robustness="standard",
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


@pytest.fixture
def db_store_factory(request: pytest.FixtureRequest):
    """Create a real DB store when the explicit DB test profile is selected."""

    backend = request.config.getoption("--backend", default=None)
    if backend != "db":
        pytest.skip("--backend db not passed")
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip("SUPABASE_DB_URL not set")

    from arnold_pipelines.megaplan.store import DBStore, deterministic_idempotency_key

    actor_id = f"ci-actor-{uuid.uuid4().hex[:12]}"
    bootstrap = DBStore(actor_id=None, dsn=dsn)
    try:
        bootstrap.create_automation_actor(
            actor_id=actor_id,
            name="CI Contract Actor",
            granted_epic_ids="*",
            actor_kind="cli",
            idempotency_key=deterministic_idempotency_key(
                "db-store-fixture", actor_id, "create_actor"
            ),
        )
    finally:
        bootstrap.close()
    return lambda: DBStore(actor_id=actor_id, dsn=dsn)


@pytest.fixture
def editorial_store(request: pytest.FixtureRequest, tmp_path: Path):
    """Provide the selected real editorial store without DB-to-file fallback."""

    backend = request.config.getoption("--backend", default=None)
    if backend == "db":
        return request.getfixturevalue("db_store_factory")()

    from arnold_pipelines.megaplan.store import FileStore

    return FileStore(tmp_path / "store")


@pytest.fixture
def editorial_backend_name(request: pytest.FixtureRequest) -> str:
    """Expose the actual backend selected by ``editorial_store``."""

    backend = request.config.getoption("--backend", default=None)
    return "db" if backend == "db" else "file"


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
