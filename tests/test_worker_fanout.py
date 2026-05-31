"""Unit tests for megaplan._core.worker_fanout.

Covers ordering, token/cost aggregation, error propagation, picklability
where applicable, caller-controlled parse/reduce hooks, deterministic output
paths, and that ``WorkerUnit(read_only=True)`` is dispatched as read-only.
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from megaplan._core.worker_fanout import (
    WorkerUnit,
    _scatter_worker_unit_from_packed,
    scatter_worker_unit,
    scatter_worker_units,
)
from megaplan._core.hermes_fanout import GenericScatterResult
from megaplan.types import AgentMode
from megaplan.workers import WorkerResult

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------


def _agent_mode(
    agent: str = "hermes",
    mode: str = "creative",
    refreshed: bool = False,
    model: str | None = None,
) -> AgentMode:
    return AgentMode(agent=agent, mode=mode, refreshed=refreshed, model=model)


def _state(tmp_path: Path) -> dict:
    """Minimal PlanState shape for worker_fanout tests."""
    return {
        "name": "fanout-test",
        "idea": "test worker fan-out",
        "current_state": "initialized",
        "iteration": 0,
        "created_at": "2026-05-30T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "robustness": "standard"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"total_cost_usd": 0.0, "notes": []},
    }


def _worker_result(
    *,
    payload: dict | None = None,
    cost_usd: float = 0.01,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int = 150,
) -> WorkerResult:
    return WorkerResult(
        payload=payload or {"status": "ok"},
        raw_output="{}",
        duration_ms=200,
        cost_usd=cost_usd,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _scatter_args() -> argparse.Namespace:
    return argparse.Namespace()


# ===================================================================
# WorkerUnit dataclass tests
# ===================================================================


class TestWorkerUnit:
    """Construction, defaults, picklability."""

    def test_defaults(self) -> None:
        u = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check this",
            output_path=Path("/tmp/out.json"),
        )
        assert u.read_only is True
        assert u.extra == {}

    def test_explicit_read_only_false(self) -> None:
        u = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check this",
            output_path=Path("/tmp/out.json"),
            read_only=False,
        )
        assert u.read_only is False

    def test_extra_carries_arbitrary_metadata(self) -> None:
        u = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check this",
            output_path=Path("/tmp/out.json"),
            extra={"check_id": "CHK-001", "area": "correctness"},
        )
        assert u.extra["check_id"] == "CHK-001"
        assert u.extra["area"] == "correctness"

    def test_picklable(self) -> None:
        u = WorkerUnit(
            step="critique",
            resolved=_agent_mode(agent="claude", mode="prose", model="claude-opus-4-7"),
            prompt="check this",
            output_path=Path("/tmp/out.json"),
            read_only=True,
            extra={"check_id": "CHK-001"},
        )
        encoded = pickle.dumps(u)
        restored = pickle.loads(encoded)
        assert restored.step == u.step
        assert restored.resolved == u.resolved
        assert restored.prompt == u.prompt
        assert restored.output_path == u.output_path
        assert restored.read_only == u.read_only
        assert restored.extra == u.extra

    def test_picklable_minimal(self) -> None:
        """WorkerUnit with only required fields is picklable."""
        u = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=Path("/tmp/o.json"),
        )
        encoded = pickle.dumps(u)
        restored = pickle.loads(encoded)
        assert restored.step == "critique"
        assert restored.read_only is True

    def test_is_dataclass(self) -> None:
        """WorkerUnit is a dataclass (required for picklability and unpacking)."""
        from dataclasses import is_dataclass

        assert is_dataclass(WorkerUnit)


# ===================================================================
# scatter_worker_unit tests
# ===================================================================


class TestScatterWorkerUnit:
    """Single-unit dispatch, read_only forwarding, error propagation."""

    def test_returns_6_tuple(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ) as mock_run:
            result = scatter_worker_unit(
                0,
                unit,
                state=state,
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert len(result) == 6
        idx, payload, cost, pt, ct, tt = result
        assert idx == 0
        assert payload == {"status": "ok"}
        assert cost == 0.01
        assert pt == 100
        assert ct == 50
        assert tt == 150

    def test_dispatches_with_correct_params(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(agent="claude", mode="prose", model="claude-opus-4-7"),
            prompt="check correctness",
            output_path=tmp_path / "critique_0.json",
            read_only=True,
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "claude", "prose", False),
        ) as mock_run:
            scatter_worker_unit(
                3,
                unit,
                state=state,
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        mock_run.assert_called_once()
        _call_args = mock_run.call_args
        assert _call_args[0][0] == "critique"  # step
        assert _call_args[0][1] is state  # state
        assert _call_args[0][2] == tmp_path  # plan_dir
        assert _call_args[1]["root"] == tmp_path
        assert _call_args[1]["resolved"] == unit.resolved
        assert _call_args[1]["prompt_override"] == "check correctness"
        assert _call_args[1]["read_only"] is True

    def test_read_only_true_forwarded(self, tmp_path: Path) -> None:
        """WorkerUnit(read_only=True) must be dispatched as read_only=True."""
        state = _state(tmp_path)
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
            read_only=True,
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ) as mock_run:
            scatter_worker_unit(
                0,
                unit,
                state=state,
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert mock_run.call_args[1]["read_only"] is True

    def test_read_only_false_forwarded(self, tmp_path: Path) -> None:
        """WorkerUnit(read_only=False) must be dispatched as read_only=False."""
        state = _state(tmp_path)
        unit = WorkerUnit(
            step="execute",
            resolved=_agent_mode(),
            prompt="do it",
            output_path=tmp_path / "out.json",
            read_only=False,
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ) as mock_run:
            scatter_worker_unit(
                0,
                unit,
                state=state,
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert mock_run.call_args[1]["read_only"] is False

    def test_invalid_isolation_raises(self, tmp_path: Path) -> None:
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )
        with pytest.raises(ValueError, match="unsupported isolation"):
            scatter_worker_unit(
                0,
                unit,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                isolation="green_thread",
            )

    def test_thread_isolation_accepted(self, tmp_path: Path) -> None:
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )
        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ):
            scatter_worker_unit(
                0,
                unit,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                isolation="thread",
            )

    def test_process_isolation_accepted(self, tmp_path: Path) -> None:
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )
        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ):
            scatter_worker_unit(
                0,
                unit,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                isolation="process",
            )

    def test_worker_exception_propagates(self, tmp_path: Path) -> None:
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )
        with patch(
            "megaplan.workers.run_step_with_worker",
            side_effect=RuntimeError("worker exploded"),
        ):
            with pytest.raises(RuntimeError, match="worker exploded"):
                scatter_worker_unit(
                    0,
                    unit,
                    state=_state(tmp_path),
                    plan_dir=tmp_path,
                    root=tmp_path,
                    args=_scatter_args(),
                )

    def test_cost_and_token_aggregation_from_worker_result(self, tmp_path: Path) -> None:
        """Verify the full 6-tuple maps correctly from WorkerResult fields."""
        state = _state(tmp_path)
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )
        wr = _worker_result(
            payload={"verdict": "pass"},
            cost_usd=0.42,
            prompt_tokens=2048,
            completion_tokens=512,
            total_tokens=2560,
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(wr, "hermes", "creative", False),
        ):
            result = scatter_worker_unit(
                7,
                unit,
                state=state,
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert result == (7, {"verdict": "pass"}, 0.42, 2048, 512, 2560)


# ===================================================================
# scatter_worker_units tests
# ===================================================================


class TestScatterWorkerUnits:
    """Multi-unit fan-out: ordering, aggregation, hooks, errors, paths."""

    def _unit(
        self,
        index: int,
        tmp_path: Path,
        *,
        read_only: bool = True,
        extra: dict | None = None,
    ) -> WorkerUnit:
        return WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt=f"check unit {index}",
            output_path=tmp_path / f"critique_{index}.json",
            read_only=read_only,
            extra=extra or {"index": index},
        )

    def test_empty_units_returns_zero_result(self, tmp_path: Path) -> None:
        result = scatter_worker_units(
            units=[],
            state=_state(tmp_path),
            plan_dir=tmp_path,
            root=tmp_path,
            args=_scatter_args(),
        )
        assert result.ordered_results == []
        assert result.total_cost == 0.0
        assert result.total_prompt_tokens == 0
        assert result.total_completion_tokens == 0
        assert result.total_tokens == 0
        assert result.side_results == []

    def test_ordering_results_in_input_order(self, tmp_path: Path) -> None:
        """Results must be returned in input order, not completion order."""
        units = [self._unit(i, tmp_path) for i in range(3)]

        # Simulate scatter_gather_processes returning results in order
        raw = GenericScatterResult(
            ordered_results=["result-0", "result-1", "result-2"],
            total_cost=0.03,
            total_prompt_tokens=300,
            total_completion_tokens=150,
            total_tokens=450,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            result = scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert result.ordered_results == ["result-0", "result-1", "result-2"]

        # Verify packed units are correctly formed
        mock_sgp.assert_called_once()
        packed = mock_sgp.call_args[1]["units"]
        assert len(packed) == 3
        assert packed[0]["step"] == "critique"
        assert packed[0]["prompt"] == "check unit 0"
        assert packed[0]["read_only"] is True
        assert packed[0]["extra"] == {"index": 0}
        assert str(units[0].output_path) == packed[0]["output_path"]

    def test_token_cost_aggregation(self, tmp_path: Path) -> None:
        """Total cost and token counts are aggregated from scatter_gather_processes."""
        units = [self._unit(i, tmp_path) for i in range(2)]

        raw = GenericScatterResult(
            ordered_results=["a", "b"],
            total_cost=0.07,
            total_prompt_tokens=500,
            total_completion_tokens=200,
            total_tokens=700,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ):
            result = scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert result.total_cost == 0.07
        assert result.total_prompt_tokens == 500
        assert result.total_completion_tokens == 200
        assert result.total_tokens == 700

    def test_parse_result_hook_called_per_unit(self, tmp_path: Path) -> None:
        """Caller-supplied parse_result transforms each raw payload."""
        units = [self._unit(i, tmp_path) for i in range(2)]

        raw = GenericScatterResult(
            ordered_results=[{"v": 1}, {"v": 2}],
            total_cost=0.02,
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            side_results=[],
        )

        def _parse(index: int, payload: dict, unit: WorkerUnit) -> str:
            return f"unit-{unit.extra['index']}-v{payload['v']}"

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ):
            result = scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                parse_result=_parse,
            )

        assert result.ordered_results == ["unit-0-v1", "unit-1-v2"]
        # cost/token aggregation still flows through
        assert result.total_cost == 0.02

    def test_parse_result_hook_receives_correct_unit(self, tmp_path: Path) -> None:
        """parse_result receives the WorkerUnit matching each index."""
        units = [self._unit(i, tmp_path) for i in range(3)]

        raw = GenericScatterResult(
            ordered_results=["r0", "r1", "r2"],
            total_cost=0.03,
            total_prompt_tokens=300,
            total_completion_tokens=150,
            total_tokens=450,
            side_results=[],
        )

        seen: list[tuple[int, WorkerUnit]] = []

        def _parse(index: int, payload: str, unit: WorkerUnit) -> str:
            seen.append((index, unit))
            return payload

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ):
            scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                parse_result=_parse,
            )

        assert len(seen) == 3
        for i, (idx, wu) in enumerate(seen):
            assert idx == i
            assert wu is units[i]

    def test_on_unit_error_propagates_to_scatter_gather(self, tmp_path: Path) -> None:
        """on_unit_error is passed through to scatter_gather_processes."""
        units = [self._unit(0, tmp_path)]

        def _on_error(index: int, exc: Exception):
            return ({"error": str(exc)}, 0.0, 0, 0, 0)

        raw = GenericScatterResult(
            ordered_results=[{"error": "test"}],
            total_cost=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                on_unit_error=_on_error,
            )

        assert mock_sgp.call_args[1]["on_unit_error"] is _on_error

    def test_on_unit_error_not_set_omitted_from_call(self, tmp_path: Path) -> None:
        """When on_unit_error is None, the kwarg is not passed (default behavior)."""
        units = [self._unit(0, tmp_path)]

        raw = GenericScatterResult(
            ordered_results=["ok"],
            total_cost=0.01,
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert mock_sgp.call_args[1].get("on_unit_error") is None

    def test_deterministic_output_paths_per_unit(self, tmp_path: Path) -> None:
        """Each unit gets its own output_path, packed into the dict correctly."""
        out_a = tmp_path / "critique_a.json"
        out_b = tmp_path / "critique_b.json"

        units = [
            WorkerUnit(
                step="critique",
                resolved=_agent_mode(),
                prompt="check A",
                output_path=out_a,
            ),
            WorkerUnit(
                step="critique",
                resolved=_agent_mode(),
                prompt="check B",
                output_path=out_b,
            ),
        ]

        raw = GenericScatterResult(
            ordered_results=["ra", "rb"],
            total_cost=0.02,
            total_prompt_tokens=200,
            total_completion_tokens=100,
            total_tokens=300,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        packed = mock_sgp.call_args[1]["units"]
        assert packed[0]["output_path"] == str(out_a)
        assert packed[1]["output_path"] == str(out_b)

    def test_read_only_unit_packed_correctly(self, tmp_path: Path) -> None:
        """WorkerUnit(read_only=True) is packed with read_only=True for dispatch."""
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="read-only check",
            output_path=tmp_path / "out.json",
            read_only=True,
        )

        raw = GenericScatterResult(
            ordered_results=["ok"],
            total_cost=0.01,
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            scatter_worker_units(
                units=[unit],
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        packed = mock_sgp.call_args[1]["units"]
        assert packed[0]["read_only"] is True

    def test_max_concurrent_forwarded(self, tmp_path: Path) -> None:
        """max_concurrent is passed through to scatter_gather_processes."""
        units = [self._unit(0, tmp_path)]

        raw = GenericScatterResult(
            ordered_results=["ok"],
            total_cost=0.01,
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                max_concurrent=4,
            )

        assert mock_sgp.call_args[1]["max_concurrent"] == 4

    def test_timeout_seconds_forwarded(self, tmp_path: Path) -> None:
        """timeout_seconds is passed through to scatter_gather_processes."""
        units = [self._unit(0, tmp_path)]

        raw = GenericScatterResult(
            ordered_results=["ok"],
            total_cost=0.01,
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            scatter_worker_units(
                units=units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                timeout_seconds=120.0,
            )

        assert mock_sgp.call_args[1]["timeout_seconds"] == 120.0


# ===================================================================
# _scatter_worker_unit_from_packed tests
# ===================================================================


class TestScatterWorkerUnitFromPacked:
    """Process-safe entry point: unpacking and picklability."""

    def _packed_unit(self, tmp_path: Path, **overrides) -> dict:
        base = {
            "step": "critique",
            "resolved": _agent_mode(),
            "prompt": "check",
            "output_path": str(tmp_path / "out.json"),
            "read_only": True,
            "extra": {},
            "state": _state(tmp_path),
            "plan_dir": str(tmp_path),
            "root": str(tmp_path),
            "args": _scatter_args(),
        }
        base.update(overrides)
        return base

    def test_picklable(self, tmp_path: Path) -> None:
        """_scatter_worker_unit_from_packed must be picklable for process dispatch."""
        packed = self._packed_unit(tmp_path)

        encoded = pickle.dumps((_scatter_worker_unit_from_packed, 0, packed))
        decoded_fn, decoded_idx, decoded_unit = pickle.loads(encoded)

        assert decoded_fn is _scatter_worker_unit_from_packed
        assert decoded_idx == 0
        assert decoded_unit["step"] == "critique"

    def test_unpacks_worker_unit_correctly(self, tmp_path: Path) -> None:
        """The packed dict is correctly unpacked into a WorkerUnit."""
        packed = self._packed_unit(
            tmp_path,
            step="execute",
            prompt="do it",
            read_only=False,
            extra={"task_id": "T1"},
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ) as mock_run:
            _scatter_worker_unit_from_packed(5, packed)

        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == "execute"
        assert mock_run.call_args[1]["prompt_override"] == "do it"
        assert mock_run.call_args[1]["read_only"] is False

    def test_read_only_defaults_to_true_when_missing(self, tmp_path: Path) -> None:
        """When read_only is absent from packed dict, default to True."""
        packed = self._packed_unit(tmp_path)
        del packed["read_only"]

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ) as mock_run:
            _scatter_worker_unit_from_packed(0, packed)

        assert mock_run.call_args[1]["read_only"] is True

    def test_extra_defaults_to_empty_when_missing(self, tmp_path: Path) -> None:
        """When extra is absent from packed dict, default to {}."""
        packed = self._packed_unit(tmp_path)
        del packed["extra"]

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "creative", False),
        ):
            # Should not raise — extra defaults to {}
            _scatter_worker_unit_from_packed(0, packed)
