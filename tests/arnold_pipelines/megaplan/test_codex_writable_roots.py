from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.runtime.execution_environment import ExecutionEnvironment
from arnold_pipelines.megaplan.runtime.engine_isolation import (
    engine_write_barrier,
    validate_logical_local_dev,
)
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import _impl


def _env(*, project: Path, target: Path, work: Path, engine: Path) -> ExecutionEnvironment:
    return ExecutionEnvironment(
        project_root=project.resolve(),
        target_root=target.resolve(),
        work_dir=work.resolve(),
        engine_root=engine.resolve(),
        target_head=None,
        target_base=None,
        target_base_ref=None,
        target_fallback_reason=None,
    )


def test_codex_writable_roots_refuse_same_engine_target_without_opt_in(tmp_path: Path) -> None:
    root = tmp_path / "megaplan"
    root.mkdir()
    env = _env(project=root, target=root, work=root, engine=root)

    with pytest.raises(CliError) as exc_info:
        _impl._codex_writable_roots(root, {"config": {}}, env)

    assert exc_info.value.code == "codex_writable_root_overlaps_engine"
    assert exc_info.value.extra["overlap"] == "equal"


def test_codex_writable_roots_allow_self_hosted_engine_target_with_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "megaplan"
    root.mkdir()
    env = _env(project=root, target=root, work=root, engine=root)
    monkeypatch.setenv("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", "self_hosted_editable")

    assert _impl._codex_writable_roots(root, {"config": {}}, env) == [str(root.resolve())]


def test_codex_writable_roots_refuse_target_that_contains_engine(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    engine = target / "engine"
    engine.mkdir(parents=True)
    env = _env(project=target, target=target, work=target, engine=engine)

    with pytest.raises(CliError) as exc_info:
        _impl._codex_writable_roots(target, {"config": {}}, env)

    assert exc_info.value.code == "codex_writable_root_overlaps_engine"
    assert exc_info.value.extra["overlap"] == "left_contains_right"


def test_codex_writable_roots_refuse_configured_engine_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    engine = tmp_path / "engine"
    target.mkdir()
    engine.mkdir()
    env = _env(project=target, target=target, work=target, engine=engine)
    state = {"config": {"extra_writable_roots": [str(engine)]}}

    with pytest.raises(CliError) as exc_info:
        _impl._codex_writable_roots(target, state, env)

    assert exc_info.value.code == "codex_writable_root_overlaps_engine"
    assert exc_info.value.extra["writable_root_source"] == "configured"


def test_engine_barrier_accepts_explicit_self_hosted_editable(tmp_path: Path) -> None:
    root = tmp_path / "megaplan"
    root.mkdir()
    env = _env(project=root, target=root, work=root, engine=root)

    proof = engine_write_barrier(
        env,
        "execute",
        env_vars={"MEGAPLAN_ENGINE_ISOLATION_PROVIDER": "self_hosted_editable"},
    )

    assert proof.provider == "self_hosted_editable"
    assert proof.logical_dev_accepted is True
    assert proof.engine_target_overlap == "equal"


def test_logical_local_dev_remains_disjoint_only(tmp_path: Path) -> None:
    root = tmp_path / "megaplan"
    root.mkdir()
    env = _env(project=root, target=root, work=root, engine=root)

    proof = validate_logical_local_dev(env)

    assert proof.logical_dev_accepted is False
    assert proof.engine_target_overlap == "equal"
