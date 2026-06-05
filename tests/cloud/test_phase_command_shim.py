"""Tests for the _phase_command substrate shim (M3 Step 12).

The shim adds a *substrate* kwarg to ``auto._phase_command`` so callers
in the unified-dispatch path can explicitly declare their execution model.
The parameter is forward-looking: both ``"subprocess_isolated"`` and
``"in_process"`` currently return identical CLI args (the legacy contract).
"""

from __future__ import annotations

import inspect

import pytest

from arnold.pipelines.megaplan.auto import _phase_command
from arnold.pipelines.megaplan.cloud.cli import cloud_substrate


# ---------------------------------------------------------------------------
# Backward-compatible signature
# ---------------------------------------------------------------------------

def test_phase_command_accepts_no_substrate_kwarg() -> None:
    """Calling without *substrate* uses the default and returns correct args."""
    result = _phase_command("review")
    assert result == ["review"]


def test_phase_command_default_is_subprocess_isolated() -> None:
    """The default substrate value is ``"subprocess_isolated"``."""
    sig = inspect.signature(_phase_command)
    assert sig.parameters["substrate"].default == "subprocess_isolated"


def test_phase_command_substrate_annotation_is_string() -> None:
    """The *substrate* parameter is annotated (string under PEP 563)."""
    sig = inspect.signature(_phase_command)
    param = sig.parameters["substrate"]
    assert param.annotation is not inspect.Parameter.empty


# ---------------------------------------------------------------------------
# Both substrates return identical args (shim contract)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("next_step,expected", [
    ("review", ["review"]),
    ("step", ["step"]),
    ("plan", ["plan"]),
    ("execute", ["execute", "--confirm-destructive", "--user-approved", "--retry-blocked-tasks"]),
    ("feedback", ["feedback", "workflow"]),
    ("override add-note", ["override", "add-note"]),
    ("override force-proceed", ["override", "force-proceed"]),
    ("override abort", ["override", "abort"]),
])
def test_both_substrates_return_same_args(next_step: str, expected: list[str]) -> None:
    """``subprocess_isolated`` and ``in_process`` produce identical CLI args."""
    assert _phase_command(next_step, substrate="subprocess_isolated") == expected
    assert _phase_command(next_step, substrate="in_process") == expected


def test_default_matches_explicit_subprocess_isolated() -> None:
    """Default (no substrate) == explicit ``subprocess_isolated``."""
    for step in ("review", "execute", "feedback", "override add-note"):
        assert _phase_command(step) == _phase_command(step, substrate="subprocess_isolated")


# ---------------------------------------------------------------------------
# cloud_substrate constant
# ---------------------------------------------------------------------------

def test_cloud_substrate_exists() -> None:
    """``cloud_substrate`` is importable from ``megaplan.cloud.cli``."""
    assert cloud_substrate == "subprocess_isolated"


def test_cloud_substrate_is_string() -> None:
    """``cloud_substrate`` is a plain string literal."""
    assert isinstance(cloud_substrate, str)


# ---------------------------------------------------------------------------
# In-process shim does not break any caller
# ---------------------------------------------------------------------------

def test_in_process_substrate_does_not_alter_execute_flags() -> None:
    """Execute under ``in_process`` still returns the auto-mode flags."""
    result = _phase_command("execute", substrate="in_process")
    assert "--confirm-destructive" in result
    assert "--user-approved" in result
    assert "--retry-blocked-tasks" in result


def test_in_process_substrate_does_not_alter_feedback() -> None:
    """Feedback under ``in_process`` still returns the workflow operation."""
    assert _phase_command("feedback", substrate="in_process") == ["feedback", "workflow"]
