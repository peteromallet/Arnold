"""Tests for engine/target write-isolation providers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.runtime.engine_isolation import (
    EngineIsolationProof,
    engine_write_barrier,
    select_provider,
    validate_logical_local_dev,
)
from arnold.pipelines.megaplan.runtime.execution_environment import ExecutionEnvironment
from arnold.pipelines.megaplan.types import CliError


def _env(engine_root: Path, target_root: Path, work_dir: Path | None = None) -> ExecutionEnvironment:
    return ExecutionEnvironment(
        project_root=target_root,
        target_root=target_root,
        work_dir=work_dir or target_root,
        engine_root=engine_root,
        target_head=None,
        target_base=None,
        target_base_ref=None,
        target_fallback_reason=None,
    )


def test_select_provider_logical_local_dev() -> None:
    assert select_provider({"MEGAPLAN_ENGINE_ISOLATION_PROVIDER": "logical_local_dev"}) == "logical_local_dev"
    assert select_provider({}) != "logical_local_dev"


def test_validate_logical_local_dev_accepts_disjoint(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()

    proof = validate_logical_local_dev(_env(engine, target))

    assert proof.provider == "logical_local_dev"
    assert proof.logical_dev_accepted is True
    assert proof.target_write_allowed is True
    assert proof.engine_target_overlap == "disjoint"
    assert proof.worker_cwd_is_target is True
    assert proof.diagnostic is None


def test_validate_logical_local_dev_rejects_overlap(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = engine / "target"
    engine.mkdir()
    target.mkdir()

    proof = validate_logical_local_dev(_env(engine, target))

    assert proof.logical_dev_accepted is False
    assert proof.engine_target_overlap == "left_contains_right"
    assert proof.diagnostic == "logical_local_dev_contract_failed"


def test_validate_logical_local_dev_rejects_bad_work_dir(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    bad_work = tmp_path / "bad_work"
    engine.mkdir()
    target.mkdir()
    bad_work.mkdir()

    proof = validate_logical_local_dev(_env(engine, target, work_dir=bad_work))

    assert proof.logical_dev_accepted is False
    assert proof.worker_cwd_is_target is False
    assert proof.diagnostic == "logical_local_dev_contract_failed"


def test_engine_write_barrier_accepts_logical_local_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()

    monkeypatch.setenv("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", "logical_local_dev")

    proof = engine_write_barrier(_env(engine, target), phase="execute")

    assert proof.provider == "logical_local_dev"
    assert proof.logical_dev_accepted is True


def test_engine_write_barrier_rejects_logical_local_dev_overlap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = tmp_path / "engine"
    target = engine / "target"
    engine.mkdir()
    target.mkdir()

    monkeypatch.setenv("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", "logical_local_dev")

    with pytest.raises(CliError) as exc_info:
        engine_write_barrier(_env(engine, target), phase="execute")

    assert exc_info.value.code == "engine_write_isolation_unverified"


def test_engine_write_barrier_default_still_fails_without_provider(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "target"
    engine.mkdir()
    target.mkdir()

    # Ensure no env var selects the logical provider.
    env_vars = {k: v for k, v in os.environ.items() if not k.startswith("MEGAPLAN_")}

    with pytest.raises(CliError) as exc_info:
        engine_write_barrier(_env(engine, target), phase="execute", env_vars=env_vars)

    assert exc_info.value.code == "engine_write_isolation_unverified"
