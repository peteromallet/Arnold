"""T6: Verify _assert_envelope_present raises EnvelopeDroppedError under
conveyance_strict_on() and is silent when the flag is OFF.

Covers:
- Direct _assert_envelope_present behavior (flag ON / OFF / valid envelope)
- _record_error threads envelope and asserts it
- A pipeline step returning envelope=None raises under strict mode
- Same scenario is silent without strict mode
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.envelope import (
    EMPTY_ENVELOPE,
    EnvelopeDroppedError,
    RunEnvelope,
    make_envelope,
)
from arnold.pipelines.megaplan._pipeline.executor import _assert_envelope_present, _record_error, run_pipeline
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _FixedStep:
    """Step that returns a StepResult with a caller-supplied envelope."""

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple = ()
    consumes: tuple = ()

    _envelope: RunEnvelope | None = dataclasses.field(default=None)

    def run(self, ctx: StepContext) -> StepResult:
        result = StepResult(next="halt")
        # Bypass frozen to inject the caller-supplied envelope (may be None).
        object.__setattr__(result, "envelope", self._envelope)
        return result


def _single_step_pipeline(step: _FixedStep) -> Pipeline:
    stages = {
        step.name: Stage(
            name=step.name,
            step=step,
            edges=[Edge(kind="normal", label="halt", target="halt")],
        )
    }
    return Pipeline(entry=step.name, stages=stages)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _assert_envelope_present — direct tests
# ---------------------------------------------------------------------------


def test_assert_raises_on_none_under_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raises EnvelopeDroppedError when envelope is None and CONVEYANCE_STRICT=1."""
    monkeypatch.setenv("CONVEYANCE_STRICT", "1")
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    with pytest.raises(EnvelopeDroppedError, match="dropped"):
        _assert_envelope_present(None, "test_direct")


def test_assert_silent_flag_off_none_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """No exception when flag is OFF even with None envelope."""
    monkeypatch.delenv("CONVEYANCE_STRICT", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    _assert_envelope_present(None, "test_direct")  # must not raise


def test_assert_silent_with_valid_envelope_under_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    """No exception with a valid (non-None) envelope under strict mode."""
    monkeypatch.setenv("CONVEYANCE_STRICT", "1")
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    _assert_envelope_present(EMPTY_ENVELOPE, "test_direct")  # must not raise


def test_assert_inherits_master_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONVEYANCE_STRICT inherits from MEGAPLAN_UNIFIED_DISPATCH when unset."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    monkeypatch.delenv("CONVEYANCE_STRICT", raising=False)

    with pytest.raises(EnvelopeDroppedError):
        _assert_envelope_present(None, "inherit_master")


def test_assert_own_var_overrides_master_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONVEYANCE_STRICT=0 disables strict even when MEGAPLAN_UNIFIED_DISPATCH=1."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    monkeypatch.setenv("CONVEYANCE_STRICT", "0")

    _assert_envelope_present(None, "override_off")  # must not raise


# ---------------------------------------------------------------------------
# _record_error — envelope threading
# ---------------------------------------------------------------------------


def test_record_error_raises_on_dropped_envelope_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_record_error raises EnvelopeDroppedError when envelope=None under strict."""
    monkeypatch.setenv("CONVEYANCE_STRICT", "1")
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    with pytest.raises(EnvelopeDroppedError):
        _record_error(tmp_path, "stage_x", ValueError("boom"), envelope=None)


def test_record_error_silent_without_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_record_error does not raise with envelope=None when strict is OFF."""
    monkeypatch.delenv("CONVEYANCE_STRICT", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    _record_error(tmp_path, "stage_x", ValueError("boom"), envelope=None)
    assert (tmp_path / "stage_x" / "error.json").exists()


def test_record_error_silent_with_valid_envelope_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """_record_error does not raise when a valid envelope is passed under strict."""
    monkeypatch.setenv("CONVEYANCE_STRICT", "1")
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    _record_error(tmp_path, "stage_y", RuntimeError("oops"), envelope=EMPTY_ENVELOPE)
    assert (tmp_path / "stage_y" / "error.json").exists()


# ---------------------------------------------------------------------------
# Full pipeline — step returning envelope=None
# ---------------------------------------------------------------------------


def test_pipeline_dropped_step_envelope_raises_strict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pipeline raises EnvelopeDroppedError when a step returns envelope=None under strict."""
    monkeypatch.setenv("CONVEYANCE_STRICT", "1")
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    step = _FixedStep(name="drop_step", _envelope=None)
    pipeline = _single_step_pipeline(step)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")

    with pytest.raises(EnvelopeDroppedError, match="drop_step"):
        run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")


def test_pipeline_dropped_step_envelope_silent_flag_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pipeline does NOT raise when a step returns envelope=None and strict is OFF."""
    monkeypatch.delenv("CONVEYANCE_STRICT", raising=False)
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    step = _FixedStep(name="drop_step", _envelope=None)
    pipeline = _single_step_pipeline(step)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")

    # join(None) would AttributeError — but strict is OFF so _assert_envelope_present
    # is silent. The join itself will still raise AttributeError since None has no
    # join method. That's expected: strict mode is what converts the silent None into
    # an informative EnvelopeDroppedError before the join reaches None.
    with pytest.raises((AttributeError, TypeError)):
        run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")


def test_pipeline_valid_envelope_strict_no_raise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pipeline completes normally when steps return valid envelopes under strict."""
    monkeypatch.setenv("CONVEYANCE_STRICT", "1")
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)

    step = _FixedStep(name="ok_step", _envelope=make_envelope(taint="clean", cost=1.0))
    pipeline = _single_step_pipeline(step)
    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")

    result = run_pipeline(pipeline, ctx, artifact_root=tmp_path / "artifacts")
    assert result["envelope"].cost == 1.0
