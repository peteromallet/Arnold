"""Unit tests for arnold.pipeline.steps.agent.AgentStep."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.steps.agent import AgentStep, WorkerFn
from arnold.pipeline.types import StepContext, StepResult


# ---------------------------------------------------------------------------
# Minimal StepContext factory
# ---------------------------------------------------------------------------

def _ctx(tmp_path: Path, inputs: dict[str, Any] | None = None) -> StepContext:
    return StepContext(
        artifact_root=tmp_path,
        state=None,
        inputs=inputs or {},
        mode="test",
    )


# ---------------------------------------------------------------------------
# WorkerFn type annotation
# ---------------------------------------------------------------------------

def test_worker_fn_type_is_callable_returning_any() -> None:
    """WorkerFn = Callable[..., Any] — not Callable[..., str]."""
    import typing
    args = typing.get_args(WorkerFn)
    # get_args on Callable[..., Any] returns (..., Any)
    # The return type (last element) must be Any, not str.
    assert args[-1] is Any, f"WorkerFn return type should be Any, got {args[-1]}"


# ---------------------------------------------------------------------------
# str() coercion tests
# ---------------------------------------------------------------------------

class _IntWorker:
    """Returns an int — confirms str() coercion writes a file."""
    def __call__(self, **kw: Any) -> int:
        return 42


class _DictWorker:
    """Returns a dict — confirms str() coercion writes a file."""
    def __call__(self, **kw: Any) -> dict:
        return {"answer": 42}


class _NoneWorker:
    """Returns None — confirms str() coercion writes 'None'."""
    def __call__(self, **kw: Any) -> None:
        return None


@pytest.mark.parametrize(
    "worker, expected_text",
    [
        (_IntWorker(), "42"),
        (_DictWorker(), "{'answer': 42}"),
        (_NoneWorker(), "None"),
    ],
)
def test_non_string_result_coerced_to_str(
    tmp_path: Path,
    worker: Any,
    expected_text: str,
) -> None:
    """write_text wraps result_text in str() so non-str returns land on disk."""
    step = AgentStep(name="check", _worker=worker)
    ctx = _ctx(tmp_path)
    result = step.run(ctx)

    assert isinstance(result, StepResult)
    output_path = Path(result.outputs["check"])
    assert output_path.exists(), f"output file not created: {output_path}"
    assert output_path.read_text(encoding="utf-8") == expected_text


def test_string_result_unchanged(tmp_path: Path) -> None:
    """str results pass through write_text without double-coercion."""
    def worker(**kw: Any) -> str:
        return "hello"

    step = AgentStep(name="str_check", _worker=worker)
    ctx = _ctx(tmp_path)
    result = step.run(ctx)

    output_path = Path(result.outputs["str_check"])
    assert output_path.read_text(encoding="utf-8") == "hello"
