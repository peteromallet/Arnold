from __future__ import annotations

import json
import os
import uuid
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

import arnold.pipelines.megaplan as megaplan
import arnold.pipelines.megaplan.cli as megaplan_cli
import arnold.pipelines.megaplan._core as megaplan_core
import arnold.pipelines.megaplan._core.io as io_module
from arnold.pipelines.megaplan.orchestration.phase_result import (
    BlockedTask,
    Deviation,
    ExternalError,
    PhaseResult,
    atomic_write_phase_result,
)
from arnold.pipelines.megaplan.workers import WorkerResult

# Backward-compat aliases for test code that accesses megaplan.cli / megaplan._core
megaplan.cli = megaplan_cli  # type: ignore[attr-defined]
megaplan._core = megaplan_core  # type: ignore[attr-defined]

REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepend_pythonpath(path: Path) -> None:
    existing = os.environ.get("PYTHONPATH")
    parts = [str(path)]
    if existing:
        parts.extend(part for part in existing.split(os.pathsep) if part and part != str(path))
    os.environ["PYTHONPATH"] = os.pathsep.join(parts)


_prepend_pythonpath(REPO_ROOT)


@pytest.fixture(autouse=True)
def isolate_worker_unit_tests_from_global_mock_env(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker subprocess unit tests own their mocks even under broad mock runs.

    The integration suite is often invoked with ``MEGAPLAN_MOCK_WORKERS=1`` so
    high-level phases use synthetic workers. Low-level worker tests patch the
    command runners directly and must still exercise that code path; otherwise
    the global env var bypasses the behavior they are asserting.
    """
    rel = request.node.path.relative_to(Path(__file__).resolve().parents[1]).as_posix()
    if (
        rel.startswith("tests/test_workers_")
        or rel.startswith("tests/workers/")
        or rel == "tests/test_prep.py"
        or rel in {
            "tests/test_sandbox.py",
            "tests/test_shannon_wall_clock_timeout.py",
        }
    ):
        monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)


@pytest.fixture(autouse=True)
def isolate_pipeline_contextvars() -> None:
    """Prevent tree-scoped runtime ContextVars from leaking across tests."""
    from arnold.pipelines.megaplan._pipeline.envelope import _envelope_ctx, _fanout_active_ctx
    from arnold.pipelines.megaplan.runtime.governor import _governor_ctx

    env_token = _envelope_ctx.set(None)
    fanout_token = _fanout_active_ctx.set(False)
    governor_token = _governor_ctx.set(None)
    try:
        yield
    finally:
        _governor_ctx.reset(governor_token)
        _fanout_active_ctx.reset(fanout_token)
        _envelope_ctx.reset(env_token)


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
    return json.loads(path.read_text(encoding="utf-8"))


def run_main_json(
    argv: list[str],
    *,
    cwd: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, dict]:
    monkeypatch.chdir(cwd)
    exit_code = megaplan.main(argv)
    return exit_code, json.loads(capsys.readouterr().out)


def _write_lines(path: Path, count: int, *, prefix: str = "line") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{prefix}_{index}" for index in range(count)) + "\n", encoding="utf-8")


def make_args_factory(project_dir: Path) -> Callable[..., Namespace]:
    def make_args(**overrides: object) -> Namespace:
        data = {
            "plan": None,
            "idea": "test idea",
            "name": "test-plan",
            "project_dir": str(project_dir),
            "auto_approve": None,
            "robustness": None,
            "agent": None,
            "ephemeral": False,
            "fresh": False,
            "persist": False,
            "confirm_destructive": True,
            "user_approved": False,
            "confirm_self_review": False,
            "batch": None,
            "override_action": None,
            "note": None,
            "reason": "",
            "robustness": None,
            "strict_notes": None,
            "prep_clarify": True,
            "source": "user",
        }
        data.update(overrides)
        return Namespace(**data)

    return make_args


@dataclass
class PlanFixture:
    root: Path
    project_dir: Path
    plan_name: str
    plan_dir: Path
    make_args: Callable[..., Namespace]


def _make_plan_fixture_with_robustness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    robustness: str,
) -> PlanFixture:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(root, make_args(robustness=robustness))
    plan_name = response["plan"]
    return PlanFixture(
        root=root,
        project_dir=project_dir,
        plan_name=plan_name,
        plan_dir=megaplan.plans_root(root) / plan_name,
        make_args=make_args,
    )


@pytest.fixture
def bootstrap_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Lightweight env bootstrap: monkeypatches ``shutil.which``, config dir, and
    creates ``root`` / ``project_dir`` (with ``.git``).  Returns ``(root, project_dir)``
    **without** initializing a plan — callers that need a plan must still call
    ``megaplan.handle_init`` themselves.
    """
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)
    return root, project_dir


@pytest.fixture
def db_store_factory(request: pytest.FixtureRequest):
    """Factory fixture for DBStore; skips if --backend db not passed or SUPABASE_DB_URL not set."""
    backend = request.config.getoption("--backend", default=None)
    if backend != "db":
        pytest.skip("--backend db not passed")
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip("SUPABASE_DB_URL not set")
    from arnold.pipelines.megaplan.store import DBStore, deterministic_idempotency_key
    actor_id = f"ci-actor-{uuid.uuid4().hex[:12]}"
    bootstrap = DBStore(actor_id=None, dsn=dsn)
    try:
        bootstrap.create_automation_actor(
            actor_id=actor_id,
            name="CI Contract Actor",
            granted_epic_ids="*",
            actor_kind="cli",
            idempotency_key=deterministic_idempotency_key("db-store-fixture", actor_id, "create_actor"),
        )
    finally:
        bootstrap.close()
    return lambda: DBStore(actor_id=actor_id, dsn=dsn)


@pytest.fixture
def editorial_store(request: pytest.FixtureRequest, tmp_path: Path):
    """Store fixture for editorial tests.

    `--backend db` must exercise real DBStore persistence or skip through
    db_store_factory; it must not silently fall back to FileStore.
    """
    backend = request.config.getoption("--backend", default=None)
    if backend == "db":
        db_store_factory = request.getfixturevalue("db_store_factory")
        return db_store_factory()
    from arnold.pipelines.megaplan.store import FileStore

    return FileStore(tmp_path / "store")


@pytest.fixture
def editorial_backend_name(request: pytest.FixtureRequest) -> str:
    backend = request.config.getoption("--backend", default=None)
    return "db" if backend == "db" else "file"


@pytest.fixture
def plan_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PlanFixture:
    return _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="standard")


def load_state(plan_dir: Path) -> dict:
    return read_json(plan_dir / "state.json")


def latest_plan_name(plan_dir: Path) -> str:
    return load_state(plan_dir)["plan_versions"][-1]["file"]


def debt_registry_path(root: Path) -> Path:
    return root / ".megaplan" / "debt.json"


def first_open_significant_flag(plan_dir: Path) -> dict:
    registry = read_json(plan_dir / "faults.json")
    return next(
        flag
        for flag in registry["flags"]
        if flag["status"] in {"open", "disputed"} and flag.get("severity") == "significant"
    )


def open_blocking_flags(plan_dir: Path) -> list[dict]:
    registry = read_json(plan_dir / "faults.json")
    return [
        flag
        for flag in registry["flags"]
        if flag["status"] in {"open", "disputed"}
        and flag.get("severity") in {"significant", "likely-significant"}
    ]


def ensure_blocking_flags(plan_dir: Path, count: int) -> list[dict]:
    registry = read_json(plan_dir / "faults.json")
    flags = [
        flag
        for flag in registry["flags"]
        if flag["status"] in {"open", "disputed"}
        and flag.get("severity") in {"significant", "likely-significant"}
    ]
    if not flags:
        raise AssertionError("expected at least one blocking flag in the fixture")
    template = flags[0]
    next_index = 1
    while len(flags) < count:
        clone = dict(template)
        clone["id"] = f"{template['id']}-extra-{next_index}"
        clone["concern"] = f"{template['concern']} (extra {next_index})"
        registry["flags"].append(clone)
        flags.append(clone)
        next_index += 1
    for extra in flags[count:]:
        extra["severity"] = "minor"
    (plan_dir / "faults.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return open_blocking_flags(plan_dir)


def make_gate_worker_result(
    *,
    recommendation: str,
    rationale: str,
    signals_assessment: str,
    flag_resolutions: list[dict] | None = None,
    accepted_tradeoffs: list[dict] | None = None,
    session_id: str,
) -> WorkerResult:
    return WorkerResult(
        payload={
            "recommendation": recommendation,
            "rationale": rationale,
            "signals_assessment": signals_assessment,
            "warnings": [],
            "settled_decisions": [],
            "flag_resolutions": flag_resolutions or [],
            "accepted_tradeoffs": accepted_tradeoffs or [],
        },
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id=session_id,
    )


def make_worker_sequence(
    results: list[tuple[WorkerResult, str, str, bool]],
    call_counter: dict[str, int],
) -> Callable[..., tuple[WorkerResult, str, str, bool]]:
    iterator = iter(results)

    def _run_step_with_worker(*args, **kwargs):
        call_counter["count"] += 1
        return next(iterator)

    return _run_step_with_worker


# ---------------------------------------------------------------------------
# PhaseResult test fixtures (T13)
# ---------------------------------------------------------------------------


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
    """Write a synthetic ``phase_result.json`` to *plan_dir*.

    Returns the written ``PhaseResult`` so callers can inspect what was stored.
    """
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
    """Return a callable matching ``_run_planning_phase(cmd, ...) → (int, str, str)``.

    The callable also writes a synthetic ``phase_result.json`` alongside so
    that ``_run_phase`` can pick it up.  Returns ``(code, stdout, stderr)``
    on every call.
    """

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
