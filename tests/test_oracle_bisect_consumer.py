"""M4 T12 — Consumer test: m4_oracle_bisect makes a branching decision."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "m4_oracle_bisect.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("m4_oracle_bisect", _TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["m4_oracle_bisect"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_bisect_classifies_good_for_true(capsys):
    mod = _load_tool()
    verdict, result = mod.bisect_step(["true"])
    assert verdict == "good"
    assert result.exit == 0
    out = capsys.readouterr().out
    assert "good" in out  # branch decision was emitted


def test_bisect_classifies_bad_for_false(capsys):
    mod = _load_tool()
    verdict, result = mod.bisect_step(["false"])
    assert verdict == "bad"
    assert result.exit != 0
    out = capsys.readouterr().out
    assert "bad" in out  # branch decision was emitted


def test_branching_decision_is_driven_by_exit_code(capsys):
    """The crucial property: the verdict must flip based on oracle.run exit."""
    mod = _load_tool()
    good_verdict, _ = mod.bisect_step(["true"])
    bad_verdict, _ = mod.bisect_step(["false"])
    assert good_verdict != bad_verdict  # >= 1 branching decision exercised
