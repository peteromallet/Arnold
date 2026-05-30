"""Tests for ``InProcessDriver``.

Covers:
1. ``sys.exit(1)`` propagates ``SystemExit`` (crash-isolation gap).
2. ``raise`` surfaces as ``StepResult.failed``.
3. Success path returns the callable's ``StepResult`` verbatim.
4. ``step_func`` is ``None`` returns a failed ``StepResult``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from megaplan._pipeline.types import StepContext, StepResult
from megaplan.drivers.in_process import InProcessDriver


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_ctx(tmp_path: Path) -> StepContext:
    return StepContext(plan_dir=tmp_path, state={}, profile=None, mode="auto")


def _success_step(ctx: StepContext) -> StepResult:
    return StepResult(
        next="halt",
        state_patch={"ok": True, "received_plan_dir": str(ctx.plan_dir)},
    )


def _exit_step(ctx: StepContext) -> StepResult:
    sys.exit(1)
    return StepResult(next="halt")  # unreachable


def _raise_step(ctx: StepContext) -> StepResult:
    raise ValueError("boom")


# ---------------------------------------------------------------------------
# 1. sys.exit(1) propagates SystemExit
# ---------------------------------------------------------------------------


def test_sys_exit_propagates_system_exit(tmp_path: Path) -> None:
    """``sys.exit(1)`` inside the step propagates ``SystemExit`` to the caller.

    This is the documented crash-isolation gap: unlike a subprocess driver,
    the in-process driver cannot contain a ``sys.exit()``.
    """
    driver = InProcessDriver(step_func=_exit_step)
    ctx = _make_ctx(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        driver.run_step(ctx)

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 2. raise surfaces as StepResult.failed
# ---------------------------------------------------------------------------


def test_raise_surfaces_as_step_result_failed(tmp_path: Path) -> None:
    """A regular exception is caught and returned as a failed ``StepResult``."""
    driver = InProcessDriver(step_func=_raise_step)
    ctx = _make_ctx(tmp_path)

    result = driver.run_step(ctx)

    assert isinstance(result, StepResult)
    assert result.next == "halt"
    assert result.state_patch["failed"] is True
    assert "ValueError" in result.state_patch["error"]
    assert "boom" in result.state_patch["error"]
    assert result.state_patch["error_type"] == "ValueError"


# ---------------------------------------------------------------------------
# 3. Success path
# ---------------------------------------------------------------------------


def test_success_returns_step_result_verbatim(tmp_path: Path) -> None:
    """On success the callable's ``StepResult`` is returned unchanged."""
    driver = InProcessDriver(step_func=_success_step)
    ctx = _make_ctx(tmp_path)

    result = driver.run_step(ctx)

    assert isinstance(result, StepResult)
    assert result.next == "halt"
    assert result.state_patch["ok"] is True
    assert result.state_patch["received_plan_dir"] == str(tmp_path)


# ---------------------------------------------------------------------------
# 4. step_func is None
# ---------------------------------------------------------------------------


def test_step_func_none_returns_failed(tmp_path: Path) -> None:
    """When ``step_func`` is ``None``, the driver returns a failed ``StepResult``."""
    driver = InProcessDriver(step_func=None)
    ctx = _make_ctx(tmp_path)

    result = driver.run_step(ctx)

    assert isinstance(result, StepResult)
    assert result.next == "halt"
    assert result.state_patch["failed"] is True
    assert result.state_patch["error"] == "step_func is None"


# ---------------------------------------------------------------------------
# 5. Default attributes satisfy the Step protocol
# ---------------------------------------------------------------------------


def test_default_attributes() -> None:
    """``InProcessDriver`` defaults satisfy the ``Step`` Protocol surface."""
    driver = InProcessDriver()
    assert driver.name == "in_process"
    assert driver.kind == "produce"
    assert driver.prompt_key is None
    assert driver.slot is None
    assert driver.produces == ()
    assert driver.consumes == ()
    assert driver.step_func is None
    assert callable(driver.run_step)
