"""Pre-dispatch memory headroom gate inside ``handlers/shared._run_worker``
(occurrence 1ac805e5eef9).

Proves:

* the gate runs BEFORE ``set_active_step`` (no worker is constructed or
  ``active_step`` written for an unsafe launch);
* a gate-selected later spec reaches worker construction with the rebound
  identity;
* ``configured_specs`` / ``attempt_index`` / ``attempted_specs`` identify the
  actually-selected spec (the codex-required ``fallback_observability_fields``
  attempt_index fix);
* a scalar unsafe chain records a typed ``insufficient_memory_headroom`` and
  constructs no worker.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.fallback_chains import (
    FallbackSpecChain,
    encode_phase_model_value,
)
from arnold_pipelines.megaplan.handlers import shared as shared_handlers
from arnold_pipelines.megaplan.runtime import memory_headroom
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import _impl as worker_impl

OX_ALPHA = "omp:openrouter/stealth/ox-alpha"
FLASH = "omp:deepseek/deepseek-v4-flash"


def _state(tmp_path: Path) -> dict:
    return {
        "config": {"project_dir": str(tmp_path)},
        "meta": {"current_invocation_id": "inv-gate"},
        "name": "plan-gate",
        "iteration": 1,
    }


def _worker() -> worker_impl.WorkerResult:
    return worker_impl.WorkerResult(
        payload={"success": True},
        raw_output="ok",
        duration_ms=12,
        cost_usd=0.0,
        session_id="session-gate",
        worker_channel="omp_rpc",
    )


def _chain_args(phase: str = "revise") -> argparse.Namespace:
    chain = FallbackSpecChain.from_value([OX_ALPHA, FLASH])
    return argparse.Namespace(
        phase_model=[encode_phase_model_value(phase, chain)],
        robustness="standard",
    )


def _patch_worker_surroundings(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    @contextmanager
    def _guard(_plan_dir: Path):
        yield

    monkeypatch.setattr(shared_handlers, "apply_profile_expansion", lambda *a, **k: None)
    monkeypatch.setattr(shared_handlers, "save_state_merge_meta", lambda *a, **k: None)
    monkeypatch.setattr(shared_handlers, "phase_result_guard", _guard)
    monkeypatch.setattr(shared_handlers, "record_step_failure", lambda *a, **k: None)

    def _fake_set_active_step(current_state: dict, *args: Any, **kwargs: Any) -> str:
        captured["set_active_step_kwargs"] = kwargs
        current_state["active_step"] = {"run_id": "run-gate"}
        return "run-gate"

    def _fake_run_step(*args: Any, **kwargs: Any) -> tuple:
        captured["run_step_kwargs"] = kwargs
        return _worker(), "omp", "persistent", False

    monkeypatch.setattr(shared_handlers, "set_active_step", _fake_set_active_step)
    monkeypatch.setattr(
        shared_handlers.worker_module, "run_step_with_worker", _fake_run_step
    )


def test_gate_selects_fallback_spec_before_active_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}
    _patch_worker_surroundings(monkeypatch, captured)
    # Low headroom: ox-alpha (high-memory, needs 1.5 GiB) is skipped; Flash
    # (normal, needs 256 MiB) is selected.
    snapshot = {
        "memory_current": int(7.5 * 1024**3),
        "memory_max": 8 * 1024**3,
        "memory_swap_max": 0,
        "memory_events": {"oom_kill": 0},
        "host_swap_total": 0,
    }
    monkeypatch.setattr(memory_headroom, "read_cgroup_memory_snapshot", lambda: snapshot)
    monkeypatch.setattr(memory_headroom, "record_dispatch_memory_marker", lambda *a, **k: None)

    worker, agent, mode, refreshed = shared_handlers._run_worker(
        "revise",
        _state(tmp_path),
        tmp_path,
        _chain_args(),
        root=tmp_path,
        resolved=("omp", "persistent", False, "openrouter/stealth/ox-alpha"),
        wbc_dispatch=object(),
    )

    assert (worker.session_id, agent, mode, refreshed) == ("session-gate", "omp", "persistent", False)
    step_kwargs = captured["set_active_step_kwargs"]
    # The gate rebound the identity to the selected Flash spec BEFORE
    # set_active_step was consulted.
    assert step_kwargs["model"] == "deepseek/deepseek-v4-flash"
    assert step_kwargs["configured_specs"] == [OX_ALPHA, FLASH]
    assert step_kwargs["attempt_index"] == 1
    assert step_kwargs["attempted_specs"] == [OX_ALPHA, FLASH]
    run_kwargs = captured["run_step_kwargs"]
    assert run_kwargs["resolved"].model == "deepseek/deepseek-v4-flash"


def test_no_safe_spec_blocks_typed_and_constructs_no_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}
    _patch_worker_surroundings(monkeypatch, captured)
    # No fallback: scalar unsafe chain under low headroom.
    monkeypatch.setattr(
        memory_headroom,
        "read_cgroup_memory_snapshot",
        lambda: {
            "memory_current": int(7.5 * 1024**3),
            "memory_max": 8 * 1024**3,
            "memory_swap_max": 0,
            "memory_events": {"oom_kill": 0},
            "host_swap_total": 0,
        },
    )

    with pytest.raises(CliError) as excinfo:
        shared_handlers._run_worker(
            "revise",
            _state(tmp_path),
            tmp_path,
            argparse.Namespace(phase_model=None),
            root=tmp_path,
            resolved=("omp", "persistent", False, "openrouter/stealth/ox-alpha"),
            wbc_dispatch=object(),
        )

    assert excinfo.value.code == "insufficient_memory_headroom"
    assert "set_active_step" not in captured
    assert "run_step_kwargs" not in captured


def test_unknown_cgroup_blocks_high_memory_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}
    _patch_worker_surroundings(monkeypatch, captured)
    # Unreadable cgroup -> ok=None -> never launch a known-dangerous worker.
    monkeypatch.setattr(memory_headroom, "read_cgroup_memory_snapshot", lambda: None)

    with pytest.raises(CliError) as excinfo:
        shared_handlers._run_worker(
            "revise",
            _state(tmp_path),
            tmp_path,
            argparse.Namespace(phase_model=None),
            root=tmp_path,
            resolved=("omp", "persistent", False, "openrouter/stealth/ox-alpha"),
            wbc_dispatch=object(),
        )

    assert excinfo.value.code == "insufficient_memory_headroom"
    assert "set_active_step" not in captured
    assert "run_step_kwargs" not in captured


def test_attempt_index_identifies_selected_spec_in_active_step_fields() -> None:
    # Direct regression for the codex-required fallback_observability_fields
    # attempt_index fix: a gate-selected later spec is recorded at its real
    # index, not as attempt 0.
    chain = FallbackSpecChain.from_value([OX_ALPHA, FLASH])
    args = argparse.Namespace(
        phase_model=[encode_phase_model_value("revise", chain)],
    )
    fields = shared_handlers._active_step_fallback_fields(
        "revise",
        args,
        agent="omp",
        model="deepseek/deepseek-v4-flash",
        effort=None,
    )
    assert fields["configured_specs"] == [OX_ALPHA, FLASH]
    assert fields["attempt_index"] == 1
    assert fields["attempted_specs"] == [OX_ALPHA, FLASH]


def test_scalar_spec_records_attempt_zero() -> None:
    args = argparse.Namespace(phase_model=None)
    fields = shared_handlers._active_step_fallback_fields(
        "revise",
        args,
        agent="omp",
        model="deepseek/deepseek-v4-flash",
        effort=None,
    )
    assert fields["configured_specs"] == ["omp:deepseek/deepseek-v4-flash"]
    assert fields["attempt_index"] == 0


def test_gate_records_dispatch_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    _patch_worker_surroundings(monkeypatch, captured)
    markers: list[tuple] = []
    snapshot = {
        "memory_current": int(7.5 * 1024**3),
        "memory_max": 8 * 1024**3,
        "memory_swap_max": 0,
        "memory_events": {"oom_kill": 0},
        "host_swap_total": 0,
    }
    monkeypatch.setattr(memory_headroom, "read_cgroup_memory_snapshot", lambda: snapshot)

    def _record(plan_dir, phase, spec):
        markers.append((phase, spec))

    monkeypatch.setattr(memory_headroom, "record_dispatch_memory_marker", _record)

    shared_handlers._run_worker(
        "revise",
        _state(tmp_path),
        tmp_path,
        _chain_args(),
        root=tmp_path,
        resolved=("omp", "persistent", False, "openrouter/stealth/ox-alpha"),
        wbc_dispatch=object(),
    )
    assert ("revise", FLASH) in markers
