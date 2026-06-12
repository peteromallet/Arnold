"""Unit tests for megaplan._core.worker_fanout.

Covers ordering, token/cost aggregation, error propagation, picklability
where applicable, caller-controlled parse/reduce hooks, deterministic output
paths, and that ``WorkerUnit(read_only=True)`` is dispatched as read-only.
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan._core.worker_fanout import (
    WorkerUnit,
    WorkerUnitResult,
    _scatter_worker_unit_from_packed,
    _worker_unit_to_agent_request,
    scatter_worker_unit,
    scatter_worker_units,
)
from megaplan.agent_runtime import AgentRequest, AgentResult
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


def _worker_unit_result(
    unit: WorkerUnit,
    *,
    payload: dict | None = None,
    cost_usd: float = 0.01,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int = 150,
) -> WorkerUnitResult:
    return WorkerUnitResult.from_worker_result(
        _worker_result(
            payload=payload,
            cost_usd=cost_usd,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        ),
        unit,
    )


def _scatter_args() -> argparse.Namespace:
    return argparse.Namespace()


# ===================================================================
# WorkerResult compatibility tests
# ===================================================================


class TestWorkerResultCompatibility:
    """Compatibility projection between WorkerResult and AgentResult."""

    def test_to_agent_result_preserves_all_fields(self) -> None:
        worker = WorkerResult(
            payload={"ok": True},
            raw_output='{"ok": true}',
            duration_ms=123,
            cost_usd=0.42,
            session_id="sess-123",
            trace_output="trace",
            rendered_prompt="rendered",
            model_actual="gpt-5.5",
            prompt_tokens=21,
            completion_tokens=34,
            total_tokens=55,
            shannon_plan={"kind": "resume", "session_id": "shannon-1"},
            rate_limit={"window": "1h", "remaining": 42},
        )

        result = worker.to_agent_result()

        assert isinstance(result, AgentResult)
        assert result.payload == worker.payload
        assert result.raw_output == worker.raw_output
        assert result.duration_ms == worker.duration_ms
        assert result.cost_usd == worker.cost_usd
        assert result.session_id == worker.session_id
        assert result.trace_output == worker.trace_output
        assert result.rendered_prompt == worker.rendered_prompt
        assert result.model_actual == worker.model_actual
        assert result.prompt_tokens == worker.prompt_tokens
        assert result.completion_tokens == worker.completion_tokens
        assert result.total_tokens == worker.total_tokens
        assert result.shannon_plan == worker.shannon_plan
        assert result.rate_limit == worker.rate_limit

    def test_from_agent_result_preserves_all_fields(self) -> None:
        result = AgentResult(
            payload={"ok": True},
            raw_output='{"ok": true}',
            duration_ms=321,
            cost_usd=0.24,
            session_id="sess-456",
            trace_output="trace-2",
            rendered_prompt="rendered-2",
            model_actual="claude-opus-4-7",
            prompt_tokens=13,
            completion_tokens=8,
            total_tokens=21,
            shannon_plan={"kind": "resume", "session_id": "shannon-2"},
            rate_limit={"window": "1h", "remaining": 7},
        )

        worker = WorkerResult.from_agent_result(result)

        assert isinstance(worker, WorkerResult)
        assert worker.payload == result.payload
        assert worker.raw_output == result.raw_output
        assert worker.duration_ms == result.duration_ms
        assert worker.cost_usd == result.cost_usd
        assert worker.session_id == result.session_id
        assert worker.trace_output == result.trace_output
        assert worker.rendered_prompt == result.rendered_prompt
        assert worker.model_actual == result.model_actual
        assert worker.prompt_tokens == result.prompt_tokens
        assert worker.completion_tokens == result.completion_tokens
        assert worker.total_tokens == result.total_tokens
        assert worker.shannon_plan == result.shannon_plan
        assert worker.rate_limit == result.rate_limit

    def test_rate_limit_defaults_to_none_across_result_types(self) -> None:
        worker = WorkerResult(
            payload={"ok": True},
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
        )
        agent_result = worker.to_agent_result()
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=Path("out.json"),
        )
        unit_result = WorkerUnitResult.from_worker_result(worker, unit)

        assert worker.rate_limit is None
        assert agent_result.rate_limit is None
        assert unit_result.rate_limit is None

    def test_worker_unit_result_preserves_rate_limit_metadata(self) -> None:
        worker = WorkerResult(
            payload={"ok": True},
            raw_output="{}",
            duration_ms=1,
            cost_usd=0.0,
            rate_limit={"window": "1h", "remaining": 3},
        )
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=Path("out.json"),
        )

        unit_result = WorkerUnitResult.from_worker_result(worker, unit)

        assert unit_result.rate_limit == worker.rate_limit


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
# WorkerUnit -> AgentRequest adapter tests
# ===================================================================


class TestWorkerUnitToAgentRequest:
    """Local compatibility adapter for the runtime request contract."""

    def test_preserves_every_required_field_without_process_fanout(
        self, tmp_path: Path
    ) -> None:
        state = _state(tmp_path)
        args = argparse.Namespace(worker_timeout=99, flag=True)
        parse_result = lambda index, payload, worker_unit: (index, payload, worker_unit.step)
        on_unit_error = lambda index, exc: ({"error": f"{index}:{exc}"}, 0.0, 0, 0, 0)
        unit = WorkerUnit(
            step="critique",
            resolved=AgentMode(
                agent="codex",
                mode="read",
                refreshed=True,
                model="gpt-5.3-codex",
                effort="high",
                resolved_model="gpt-5.3-codex-actual",
            ),
            prompt="check contract",
            output_path=tmp_path / "critique_0.json",
            read_only=False,
            extra={"check_id": "CHK-001", "area": "correctness"},
        )

        request = _worker_unit_to_agent_request(
            unit,
            state=state,
            plan_dir=tmp_path / "plan",
            root=tmp_path,
            args=args,
            index=4,
            parse_result=parse_result,
            on_unit_error=on_unit_error,
            max_concurrent=2,
            timeout_seconds=45.5,
            isolation="process",
        )

        assert isinstance(request, AgentRequest)
        assert request.agent == "codex"
        assert request.mode == "read"
        assert request.model == "gpt-5.3-codex"
        assert request.resolved_model == "gpt-5.3-codex-actual"
        assert request.effort == "high"
        assert request.spec == ("codex", "gpt-5.3-codex")
        assert request.spec.effort == "high"
        assert request.read_only is False
        assert request.prompt == "check contract"
        assert request.timeout_seconds == 45.5
        assert request.provenance is not None
        assert request.provenance.agent == "codex"
        assert request.provenance.mode == "read"
        assert request.provenance.model == "gpt-5.3-codex"
        assert request.provenance.resolved_model == "gpt-5.3-codex-actual"
        assert request.provenance.effort == "high"
        assert request.provenance.metadata == {
            "worker_step": "critique",
            "output_path": str(unit.output_path),
            "read_only": False,
        }
        assert request.metadata["worker_unit"] == {
            "index": 4,
            "step": "critique",
            "output_path": str(unit.output_path),
            "read_only": False,
            "extra": {"check_id": "CHK-001", "area": "correctness"},
        }
        assert request.metadata["paths"] == {
            "plan_dir": str(tmp_path / "plan"),
            "root": str(tmp_path),
        }
        assert request.metadata["state"] is state
        assert request.metadata["args"] is args
        assert request.metadata["fanout"]["parse_result"] is parse_result
        assert request.metadata["fanout"]["on_unit_error"] is on_unit_error
        assert request.metadata["fanout"]["max_concurrent"] == 2
        assert request.metadata["fanout"]["timeout_seconds"] == 45.5
        assert request.metadata["fanout"]["isolation"] == "process"
        assert request.attestation == {
            "adapter": "megaplan._core.worker_fanout._worker_unit_to_agent_request",
            "legacy_worker_entrypoint": "scatter_worker_unit",
        }

    def test_preserves_parse_hooks_and_error_hooks(self, tmp_path: Path) -> None:
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(),
            prompt="check",
            output_path=tmp_path / "out.json",
        )

        def _parse(index: int, payload: dict, worker_unit: WorkerUnit) -> str:
            return f"{index}:{worker_unit.step}:{payload['ok']}"

        def _on_error(index: int, exc: Exception):
            return ({"error": f"{index}:{exc}"}, 0.0, 0, 0, 0)

        request = _worker_unit_to_agent_request(
            unit,
            state=_state(tmp_path),
            plan_dir=tmp_path,
            root=tmp_path,
            args=_scatter_args(),
            parse_result=_parse,
            on_unit_error=_on_error,
            timeout_seconds=12.0,
        )

        assert request.metadata["fanout"]["parse_result"] is _parse
        assert request.metadata["fanout"]["on_unit_error"] is _on_error
        assert request.metadata["fanout"]["timeout_seconds"] == 12.0


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
        assert isinstance(payload, WorkerUnitResult)
        assert payload.payload == {"status": "ok"}
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

    def test_forwards_json_like_worker_options(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        worker_options = {
            "template_path": str(tmp_path / "template.json"),
            "session_db_path": str(tmp_path / "review.db"),
            "max_tokens": 40000,
            "resolved_model": "qwen/qwen3-32b",
            "reasoning_config": {"enabled": False},
        }
        unit = WorkerUnit(
            step="review",
            resolved=_agent_mode(agent="hermes", mode="persistent", model="minimax:MiniMax-M2"),
            prompt="review this",
            output_path=tmp_path / "review.json",
            extra={"worker_options": worker_options, "check_id": "CHK-001"},
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(_worker_result(), "hermes", "persistent", False),
        ) as mock_run:
            scatter_worker_unit(
                1,
                unit,
                state=state,
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert mock_run.call_args.kwargs["worker_options"] == worker_options

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

        idx, payload, cost, pt, ct, tt = result
        assert idx == 7
        assert isinstance(payload, WorkerUnitResult)
        assert payload.payload == {"verdict": "pass"}
        assert cost == 0.42
        assert pt == 2048
        assert ct == 512
        assert tt == 2560

    def test_projects_through_agent_result_and_returns_raw_payload_dict(
        self, tmp_path: Path
    ) -> None:
        """The adapter path preserves provenance inside the tuple payload."""
        state = _state(tmp_path)
        payload = {"nested": {"status": "ok"}}
        worker = _worker_result(
            payload=payload,
            cost_usd=0.33,
            prompt_tokens=11,
            completion_tokens=22,
            total_tokens=33,
        )
        unit = WorkerUnit(
            step="critique",
            resolved=_agent_mode(agent="codex", mode="read", model="gpt-5.3-codex"),
            prompt="check via adapter",
            output_path=tmp_path / "adapter_out.json",
            read_only=False,
        )

        with patch(
            "megaplan.workers.run_step_with_worker",
            return_value=(worker, "codex", "read", False),
        ) as mock_run:
            result = scatter_worker_unit(
                2,
                unit,
                state=state,
                plan_dir=tmp_path / "plan",
                root=tmp_path,
                args=_scatter_args(),
                isolation="process",
            )

        idx, unit_result, cost, pt, ct, tt = result
        assert idx == 2
        assert isinstance(unit_result, WorkerUnitResult)
        assert unit_result.payload is payload
        assert unit_result.cost_usd == cost == 0.33
        assert unit_result.prompt_tokens == pt == 11
        assert unit_result.completion_tokens == ct == 22
        assert unit_result.total_tokens == tt == 33
        assert unit_result.step == "critique"
        assert unit_result.output_path == str(tmp_path / "adapter_out.json")
        assert unit_result.read_only is False
        assert unit_result.agent == "codex"
        assert unit_result.mode == "read"
        assert unit_result.model == "gpt-5.3-codex"
        mock_run.assert_called_once()
        assert mock_run.call_args[0][1] is state
        assert mock_run.call_args[1]["prompt_override"] == "check via adapter"
        assert mock_run.call_args[1]["read_only"] is False
        assert mock_run.call_args[1]["output_path"] == tmp_path / "adapter_out.json"


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
            ordered_results=[
                _worker_unit_result(units[0], payload={"value": "result-0"}),
                _worker_unit_result(units[1], payload={"value": "result-1"}),
                _worker_unit_result(units[2], payload={"value": "result-2"}),
            ],
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

        assert result.ordered_results == [
            {"value": "result-0"},
            {"value": "result-1"},
            {"value": "result-2"},
        ]

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
            ordered_results=[
                _worker_unit_result(units[0], payload={"value": "a"}),
                _worker_unit_result(units[1], payload={"value": "b"}),
            ],
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
            ordered_results=[
                _worker_unit_result(units[0], payload={"v": 1}),
                _worker_unit_result(units[1], payload={"v": 2}),
            ],
            total_cost=0.02,
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            side_results=[],
        )

        def _parse(index: int, result: WorkerUnitResult, unit: WorkerUnit) -> str:
            return f"unit-{unit.extra['index']}-v{result.payload['v']}"

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
            ordered_results=[
                _worker_unit_result(units[0], payload={"value": "r0"}),
                _worker_unit_result(units[1], payload={"value": "r1"}),
                _worker_unit_result(units[2], payload={"value": "r2"}),
            ],
            total_cost=0.03,
            total_prompt_tokens=300,
            total_completion_tokens=150,
            total_tokens=450,
            side_results=[],
        )

        seen: list[tuple[int, WorkerUnitResult, WorkerUnit]] = []

        def _parse(index: int, result: WorkerUnitResult, unit: WorkerUnit) -> dict:
            seen.append((index, result, unit))
            return result.payload

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
        for i, (idx, result, wu) in enumerate(seen):
            assert idx == i
            assert isinstance(result, WorkerUnitResult)
            assert result.payload == {"value": f"r{i}"}
            assert wu is units[i]

    def test_side_units_share_flattened_process_batch_and_split_ordered_results(
        self, tmp_path: Path
    ) -> None:
        """Main and side units are one process batch, then split by original role."""
        units = [self._unit(i, tmp_path) for i in range(2)]
        side_units = [
            self._unit(10, tmp_path, extra={"side": 0}),
            self._unit(11, tmp_path, extra={"side": 1}),
        ]

        raw = GenericScatterResult(
            ordered_results=[
                _worker_unit_result(units[0], payload={"main": 0}),
                _worker_unit_result(units[1], payload={"main": 1}),
                _worker_unit_result(side_units[0], payload={"side": 0}),
                _worker_unit_result(side_units[1], payload={"side": 1}),
            ],
            total_cost=0.40,
            total_prompt_tokens=400,
            total_completion_tokens=200,
            total_tokens=600,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            result = scatter_worker_units(
                units=units,
                side_units=side_units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert result.ordered_results == [{"main": 0}, {"main": 1}]
        assert result.side_results == [{"side": 0}, {"side": 1}]
        packed = mock_sgp.call_args[1]["units"]
        assert [(u["role"], u["original_index"]) for u in packed] == [
            ("main", 0),
            ("main", 1),
            ("side", 0),
            ("side", 1),
        ]

    def test_side_parse_hook_receives_side_units_in_side_order(
        self, tmp_path: Path
    ) -> None:
        units = [self._unit(0, tmp_path)]
        side_units = [self._unit(20, tmp_path), self._unit(21, tmp_path)]

        raw = GenericScatterResult(
            ordered_results=[
                _worker_unit_result(units[0], payload={"main": "ok"}),
                _worker_unit_result(side_units[0], payload={"v": "a"}),
                _worker_unit_result(side_units[1], payload={"v": "b"}),
            ],
            total_cost=0.03,
            total_prompt_tokens=30,
            total_completion_tokens=15,
            total_tokens=45,
            side_results=[],
        )
        seen: list[tuple[int, WorkerUnitResult, WorkerUnit]] = []

        def _parse_side(index: int, result: WorkerUnitResult, unit: WorkerUnit) -> str:
            seen.append((index, result, unit))
            return f"side-{index}-{result.payload['v']}"

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ):
            result = scatter_worker_units(
                units=units,
                side_units=side_units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
                parse_side_result=_parse_side,
            )

        assert result.ordered_results == [{"main": "ok"}]
        assert result.side_results == ["side-0-a", "side-1-b"]
        assert [idx for idx, _result, _unit in seen] == [0, 1]
        assert [unit for _idx, _result, unit in seen] == side_units

    def test_zero_main_plus_side_units_supported(self, tmp_path: Path) -> None:
        side_units = [self._unit(30, tmp_path), self._unit(31, tmp_path)]
        raw = GenericScatterResult(
            ordered_results=[
                _worker_unit_result(side_units[0], payload={"side": "a"}),
                _worker_unit_result(side_units[1], payload={"side": "b"}),
            ],
            total_cost=0.02,
            total_prompt_tokens=20,
            total_completion_tokens=10,
            total_tokens=30,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ) as mock_sgp:
            result = scatter_worker_units(
                units=[],
                side_units=side_units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert result.ordered_results == []
        assert result.side_results == [{"side": "a"}, {"side": "b"}]
        packed = mock_sgp.call_args[1]["units"]
        assert [(u["role"], u["original_index"]) for u in packed] == [
            ("side", 0),
            ("side", 1),
        ]

    def test_side_failure_propagates(self, tmp_path: Path) -> None:
        side_units = [self._unit(40, tmp_path)]

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            side_effect=RuntimeError("side worker failed"),
        ):
            with pytest.raises(RuntimeError, match="side worker failed"):
                scatter_worker_units(
                    units=[],
                    side_units=side_units,
                    state=_state(tmp_path),
                    plan_dir=tmp_path,
                    root=tmp_path,
                    args=_scatter_args(),
                )

    def test_aggregate_accounting_includes_main_and_side_units(
        self, tmp_path: Path
    ) -> None:
        units = [self._unit(0, tmp_path)]
        side_units = [self._unit(50, tmp_path)]
        raw = GenericScatterResult(
            ordered_results=[
                _worker_unit_result(units[0], payload={"main": 0}),
                _worker_unit_result(side_units[0], payload={"side": 0}),
            ],
            total_cost=0.12,
            total_prompt_tokens=120,
            total_completion_tokens=34,
            total_tokens=154,
            side_results=[],
        )

        with patch(
            "megaplan._core.worker_fanout.scatter_gather_processes",
            return_value=raw,
        ):
            result = scatter_worker_units(
                units=units,
                side_units=side_units,
                state=_state(tmp_path),
                plan_dir=tmp_path,
                root=tmp_path,
                args=_scatter_args(),
            )

        assert result.total_cost == 0.12
        assert result.total_prompt_tokens == 120
        assert result.total_completion_tokens == 34
        assert result.total_tokens == 154

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
