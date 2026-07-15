from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import pytest

from arnold_pipelines.megaplan._core.worker_fanout import (
    WorkerUnit,
    WorkerUnitResult,
    _scatter_worker_unit_from_packed,
    scatter_worker_unit,
    scatter_worker_units,
)
from arnold_pipelines.megaplan._core.hermes_fanout import GenericScatterResult
from arnold_pipelines.megaplan.fallback_chains import (
    ExecuteFallbackMutationUnsafe,
    ExecuteFallbackUnsafe,
)
from arnold_pipelines.megaplan.types import AgentMode, CliError
from arnold_pipelines.megaplan.workers import WorkerResult


def _resolved_mode() -> AgentMode:
    return AgentMode(
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.5",
        effort="high",
        resolved_model="gpt-5.5",
    )


def test_worker_unit_clone_keeps_fallback_metadata_independent() -> None:
    configured_specs = ["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"]
    attempted_specs = [configured_specs[0]]
    failed_attempt_reasons = ["availability"]
    unit = WorkerUnit(
        step="critique",
        resolved=_resolved_mode(),
        prompt="prompt",
        output_path=Path("out.json"),
        configured_specs=configured_specs,
        attempted_specs=attempted_specs,
        failed_attempt_reasons=failed_attempt_reasons,
    )

    clone = dataclasses.replace(
        unit,
        attempt_index=1,
        attempted_specs=[*unit.attempted_specs, configured_specs[1]],
        failed_attempt_reasons=[*unit.failed_attempt_reasons, "infrastructure"],
        fallback_trigger="availability",
    )

    configured_specs.append("hermes:deepseek:deepseek-v4-pro")
    attempted_specs.append("mutated")
    failed_attempt_reasons.append("mutated")

    assert unit.configured_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert unit.attempt_index == 0
    assert unit.attempted_specs == ("codex:gpt-5.5:high",)
    assert unit.failed_attempt_reasons == ("availability",)
    assert unit.fallback_trigger is None

    assert clone.configured_specs == unit.configured_specs
    assert clone.attempt_index == 1
    assert clone.attempted_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert clone.failed_attempt_reasons == ("availability", "infrastructure")
    assert clone.fallback_trigger == "availability"


def test_process_pack_unpack_preserves_worker_unit_fallback_metadata(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_scatter_worker_unit(index: int, unit: WorkerUnit, **kwargs):
        captured["index"] = index
        captured["unit"] = unit
        captured["kwargs"] = kwargs
        return (index, unit, 0.0, 0, 0, 0)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.worker_fanout.scatter_worker_unit",
        fake_scatter_worker_unit,
    )

    packed = {
        "step": "critique",
        "resolved": _resolved_mode(),
        "prompt": "prompt",
        "output_path": "out.json",
        "read_only": True,
        "validation_step": "critique",
        "schema": {"type": "object"},
        "model": "gpt-5.5",
        "tier": "enforced",
        "extra": {"check_id": "SC9"},
        "configured_specs": ["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"],
        "attempt_index": 1,
        "attempted_specs": ["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"],
        "failed_attempt_reasons": ["availability", "infrastructure"],
        "fallback_trigger": "availability",
        "state": {"name": "plan", "config": {"project_dir": "."}},
        "plan_dir": ".",
        "root": ".",
        "args": argparse.Namespace(phase_model=[]),
    }

    result = _scatter_worker_unit_from_packed(3, packed)

    assert result[0] == 3
    unit = captured["unit"]
    assert isinstance(unit, WorkerUnit)
    assert unit.configured_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert unit.attempt_index == 1
    assert unit.attempted_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert unit.failed_attempt_reasons == ("availability", "infrastructure")
    assert unit.fallback_trigger == "availability"
    assert captured["kwargs"] == {
        "state": packed["state"],
        "plan_dir": Path("."),
        "root": Path("."),
        "args": packed["args"],
        "isolation": "process",
    }


def test_scatter_worker_units_packs_fallback_metadata_per_worker(monkeypatch) -> None:
    units = [
        WorkerUnit(
            step="critique",
            resolved=_resolved_mode(),
            prompt="prompt-a",
            output_path=Path("a.json"),
            configured_specs=["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"],
            attempt_index=0,
            attempted_specs=["codex:gpt-5.5:high"],
        ),
        WorkerUnit(
            step="critique",
            resolved=_resolved_mode(),
            prompt="prompt-b",
            output_path=Path("b.json"),
            configured_specs=["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"],
            attempt_index=1,
            attempted_specs=["codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"],
            failed_attempt_reasons=["availability", "infrastructure"],
            fallback_trigger="availability",
        ),
    ]

    def fake_scatter_gather_processes(**kwargs):
        packed_units = kwargs["units"]
        assert packed_units[0]["configured_specs"] == [
            "codex:gpt-5.5:high",
            "claude:claude-sonnet-4-6:high",
        ]
        assert packed_units[0]["attempt_index"] == 0
        assert packed_units[0]["attempted_specs"] == ["codex:gpt-5.5:high"]
        assert packed_units[0]["failed_attempt_reasons"] == []
        assert packed_units[0]["fallback_trigger"] is None

        assert packed_units[1]["configured_specs"] == [
            "codex:gpt-5.5:high",
            "claude:claude-sonnet-4-6:high",
        ]
        assert packed_units[1]["attempt_index"] == 1
        assert packed_units[1]["attempted_specs"] == [
            "codex:gpt-5.5:high",
            "claude:claude-sonnet-4-6:high",
        ]
        assert packed_units[1]["failed_attempt_reasons"] == [
            "availability",
            "infrastructure",
        ]
        assert packed_units[1]["fallback_trigger"] == "availability"

        metadata = kwargs["metadata_fn"](1, packed_units[1])
        assert metadata["configured_specs"] == [
            "codex:gpt-5.5:high",
            "claude:claude-sonnet-4-6:high",
        ]
        assert metadata["attempt_index"] == 1
        assert metadata["attempted_specs"] == [
            "codex:gpt-5.5:high",
            "claude:claude-sonnet-4-6:high",
        ]
        assert metadata["failed_attempt_reasons"] == [
            "availability",
            "infrastructure",
        ]
        assert metadata["fallback_trigger"] == "availability"

        return GenericScatterResult(
            ordered_results=[{"id": "a"}, {"id": "b"}],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.worker_fanout.scatter_gather_processes",
        fake_scatter_gather_processes,
    )

    result = scatter_worker_units(
        units=units,
        state={"name": "plan", "config": {"project_dir": "."}},
        plan_dir=Path("."),
        root=Path("."),
        args=argparse.Namespace(phase_model=[]),
    )

    assert result.ordered_results == [{"id": "a"}, {"id": "b"}]


def test_agent_mode_iter_remains_four_values() -> None:
    agent, mode, refreshed, model = _resolved_mode()

    assert (agent, mode, refreshed, model) == (
        "codex",
        "persistent",
        False,
        "gpt-5.5",
    )


def _worker_result(payload: dict[str, object] | None = None) -> WorkerResult:
    return WorkerResult(
        payload=payload or {"ok": True},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.01,
    )


def _chain_unit(
    *,
    step: str = "critique",
    configured_specs: list[str] | None = None,
) -> WorkerUnit:
    specs = configured_specs or [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    return WorkerUnit(
        step=step,
        resolved=_resolved_mode(),
        prompt="prompt",
        output_path=Path("out.json"),
        configured_specs=specs,
        attempted_specs=[specs[0]],
    )


def test_scatter_worker_unit_advances_explicit_chain_for_retryable_cross_provider_failure(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_step_with_worker(*args, **kwargs):
        calls.append(kwargs)
        assert kwargs["worker_options"]["_suppress_ambient_agent_fallback"] is True
        resolved = kwargs["resolved"]
        if len(calls) == 1:
            assert resolved.agent == "codex"
            raise CliError("worker_timeout", "timed out")
        assert resolved.agent == "claude"
        return _worker_result({"attempt": "fallback"}), resolved.agent, resolved.mode, True

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        fake_run_step_with_worker,
    )

    result = scatter_worker_unit(
        0,
        _chain_unit(),
        state={"name": "plan", "config": {"project_dir": "."}},
        plan_dir=Path("."),
        root=Path("."),
        args=argparse.Namespace(phase_model=[]),
    )

    unit_result = result[1]
    assert isinstance(unit_result, WorkerUnitResult)
    assert unit_result.payload == {"attempt": "fallback"}
    assert unit_result.attempt_index == 1
    assert unit_result.attempted_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert unit_result.failed_attempt_reasons == ("worker_timeout",)
    assert unit_result.fallback_trigger == "worker_timeout"


@pytest.mark.parametrize(
    "error",
    [
        CliError("malformed_output", "malformed output"),
        CliError("schema", "schema validation failed"),
        CliError("test", "test failed"),
        CliError("evidence", "evidence check failed"),
        CliError("blocked", "worker blocked"),
        CliError("gate", "gate rejected the plan"),
        CliError("review", "review rejected the change"),
        CliError("semantic", "semantic postcheck failed"),
    ],
)
def test_scatter_worker_unit_does_not_advance_for_forbidden_failure_classes(
    monkeypatch,
    error: CliError,
) -> None:
    calls = 0

    def fake_run_step_with_worker(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise error

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        fake_run_step_with_worker,
    )

    with pytest.raises(CliError) as raised:
        scatter_worker_unit(
            0,
            _chain_unit(),
            state={"name": "plan", "config": {"project_dir": "."}},
            plan_dir=Path("."),
            root=Path("."),
            args=argparse.Namespace(phase_model=[]),
        )

    assert raised.value is error
    assert calls == 1


@pytest.mark.parametrize(
    "error",
    [
        CliError("worker_timeout", "timed out"),
        CliError("rate_limit", "rate limit"),
        CliError("unsupported_model", "unsupported model"),
    ],
)
def test_scatter_worker_unit_advances_same_family_for_read_only_operational_failure(
    monkeypatch,
    error: CliError,
) -> None:
    calls = 0

    def fake_run_step_with_worker(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error
        return (
            _worker_result({"attempt": "same-family"}),
            kwargs["resolved"].agent,
            "persistent",
            True,
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        fake_run_step_with_worker,
    )

    result = scatter_worker_unit(
        0,
        _chain_unit(
            configured_specs=[
                "codex:gpt-5.6-sol:high",
                "codex:gpt-5.6-terra:high",
            ]
        ),
        state={"name": "plan", "config": {"project_dir": "."}},
        plan_dir=Path("."),
        root=Path("."),
        args=argparse.Namespace(phase_model=[]),
    )

    assert calls == 2
    assert result[1].payload == {"attempt": "same-family"}
    assert result[1].attempt_index == 1


def test_scatter_worker_unit_keeps_writing_same_family_failure_fail_closed(monkeypatch) -> None:
    calls = 0

    def fake_run_step_with_worker(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise CliError("worker_timeout", "timed out")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        fake_run_step_with_worker,
    )

    with pytest.raises(CliError):
        scatter_worker_unit(
            0,
            dataclasses.replace(
                _chain_unit(
                    configured_specs=[
                        "codex:gpt-5.6-sol:high",
                        "codex:gpt-5.6-terra:high",
                    ]
                ),
                read_only=False,
            ),
            state={"name": "plan", "config": {"project_dir": "."}},
            plan_dir=Path("."),
            root=Path("."),
            args=argparse.Namespace(phase_model=[]),
        )

    assert calls == 1


@pytest.mark.parametrize("step", ["execute", "loop_execute"])
def test_scatter_worker_unit_requires_execute_mutation_attestation(
    monkeypatch,
    step: str,
) -> None:
    calls = 0

    def fake_run_step_with_worker(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise CliError("worker_timeout", "timed out")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        fake_run_step_with_worker,
    )

    with pytest.raises(ExecuteFallbackMutationUnsafe) as raised:
        scatter_worker_unit(
            0,
            _chain_unit(step=step),
            state={"name": "plan", "config": {"project_dir": "."}},
            plan_dir=Path("."),
            root=Path("."),
            args=argparse.Namespace(phase_model=[]),
        )

    assert calls == 1
    assert raised.value.configured_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert raised.value.attempted_index == 0
    assert "attestation" in (raised.value.guard_error or "")


@pytest.mark.parametrize("step", ["execute", "loop_execute"])
def test_scatter_worker_unit_rejects_preselected_execute_fallback_attempt(
    monkeypatch,
    step: str,
) -> None:
    calls = 0

    def fake_run_step_with_worker(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _worker_result(), "claude", "persistent", True

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        fake_run_step_with_worker,
    )

    with pytest.raises(ExecuteFallbackUnsafe) as raised:
        scatter_worker_unit(
            0,
            dataclasses.replace(
                _chain_unit(step=step),
                attempt_index=1,
                attempted_specs=(
                    "codex:gpt-5.5:high",
                    "claude:claude-sonnet-4-6:high",
                ),
            ),
            state={"name": "plan", "config": {"project_dir": "."}},
            plan_dir=Path("."),
            root=Path("."),
            args=argparse.Namespace(phase_model=[]),
        )

    assert calls == 0
    assert raised.value.phase == step
    assert raised.value.configured_specs == (
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    )
    assert raised.value.attempted_index == 1
