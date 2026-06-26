from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.auto import DriverOutcome, run_auto
from arnold_pipelines.megaplan.runtime.engine_isolation import (
    default_provider_for_local_auto,
    engine_write_barrier,
)
from arnold_pipelines.megaplan.runtime.execution_environment import ExecutionEnvironment
from arnold_pipelines.megaplan.types import CliError


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


def _auto_args(plan: str) -> Namespace:
    return Namespace(
        plan=plan,
        stall_threshold=1,
        max_iterations=1,
        max_review_rework_cycles=1,
        max_cost_usd=None,
        max_context_retries=0,
        max_external_retries=0,
        max_blocked_retries=0,
        max_add_note_attempts=1,
        escalate_after_fails=1,
        on_escalate="force-proceed",
        poll_sleep=0,
        phase_timeout=1,
        phase_idle_timeout=0,
        status_timeout=1,
        outcome_file=None,
    )


def _write_plan(root: Path, plan: str, *, target: Path) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    state = {
        "name": plan,
        "current_state": "planned",
        "config": {"project_dir": str(target)},
        "history": [],
        "meta": {},
    }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return plan_dir


def test_auto_default_preserves_explicit_provider(tmp_path: Path) -> None:
    target = tmp_path / "target"
    engine = tmp_path / "engine"
    target.mkdir()
    engine.mkdir()
    env = _env(project=target, target=target, work=target, engine=engine)

    assert (
        default_provider_for_local_auto(
            env,
            env_vars={"MEGAPLAN_ENGINE_ISOLATION_PROVIDER": "local_immutable_probe"},
        )
        is None
    )
    assert (
        default_provider_for_local_auto(
            env,
            env_vars={"MEGPLAN_ENGINE_ISOLATION_PROVIDER": "logical_local_dev"},
        )
        is None
    )


def test_auto_default_preserves_trusted_container(tmp_path: Path) -> None:
    target = tmp_path / "target"
    engine = tmp_path / "engine"
    target.mkdir()
    engine.mkdir()
    env = _env(project=target, target=target, work=target, engine=engine)

    assert (
        default_provider_for_local_auto(
            env,
            env_vars={"MEGAPLAN_TRUSTED_CONTAINER": "1"},
        )
        is None
    )


def test_disjoint_local_auto_defaults_and_passes_barrier(tmp_path: Path) -> None:
    target = tmp_path / "target"
    engine = tmp_path / "engine"
    target.mkdir()
    engine.mkdir()
    env = _env(project=target, target=target, work=target, engine=engine)

    default = default_provider_for_local_auto(env, env_vars={})

    assert default is not None
    assert default.provider == "logical_local_dev"
    proof = engine_write_barrier(
        env,
        "execute",
        env_vars={"MEGAPLAN_ENGINE_ISOLATION_PROVIDER": default.provider},
    )
    assert proof.provider == "logical_local_dev"
    assert proof.logical_dev_accepted is True


@pytest.mark.parametrize("overlap", ["equal", "target_contains_engine"])
def test_auto_default_rejects_overlapping_engine_target(
    tmp_path: Path,
    overlap: str,
) -> None:
    if overlap == "equal":
        target = tmp_path / "target"
        engine = target
        target.mkdir()
    else:
        target = tmp_path / "target"
        engine = target / "engine"
        engine.mkdir(parents=True)
    env = _env(project=target, target=target, work=target, engine=engine)

    assert default_provider_for_local_auto(env, env_vars={}) is None
    with pytest.raises(CliError) as exc_info:
        engine_write_barrier(env, "execute", env_vars={})
    assert exc_info.value.code == "engine_write_isolation_unverified"


def test_run_auto_sets_provider_for_drive_and_records_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    target = root
    engine = tmp_path / "engine"
    target.mkdir()
    engine.mkdir()
    plan_dir = _write_plan(root, "run", target=target)
    seen_provider: list[str | None] = []

    monkeypatch.delenv("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", raising=False)
    monkeypatch.delenv("MEGPLAN_ENGINE_ISOLATION_PROVIDER", raising=False)
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.delenv("MEGPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.execution_environment.megaplan_engine_root",
        lambda: engine.resolve(),
    )

    def fake_drive(*_args, **_kwargs):
        seen_provider.append(os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER"))
        return DriverOutcome(status="done", plan="run", final_state="done", iterations=1)

    monkeypatch.setattr("arnold_pipelines.megaplan.auto.drive", fake_drive)

    assert run_auto(root, _auto_args("run")) == 0

    assert seen_provider == ["logical_local_dev"]
    assert os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER") is None
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    evidence = state["meta"]["engine_isolation_auto_default"]
    assert evidence["provider"] == "logical_local_dev"
    assert evidence["proof"]["engine_target_overlap"] == "disjoint"
