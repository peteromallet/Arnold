"""Tests for megaplan/chain/ci_hook.py (T33 / Step 28).

Verifies:
- GATE_ORDER contains all 8 mandated gates in the correct order.
- run_chain_ci collects all outcomes (no short-circuit on red).
- commit_label() returns HINGE_GATE_GREEN_STAMP iff all gates pass.
- A single red gate produces empty commit_label.
- Raising gate is captured as a failure outcome (not propagated).
- assert_program_md() ensures PROGRAM.md exists with the M3 Entry section.
- PROGRAM.md stub-survival: re-creates from template when missing.
- assert_program_md() is idempotent (no duplicate M3 Entry sections).
- All 8 real gates are importable and callable (import-level smoke).
- ChainCIResult.failures returns only red outcomes.
- Green result: all gates ok -> passed=True -> commit_label non-empty.
"""

from __future__ import annotations

import importlib
import textwrap
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

from megaplan.chain.ci_hook import (
    GATE_ORDER,
    HINGE_GATE_GREEN_STAMP,
    ChainCIResult,
    GateOutcome,
    assert_program_md,
    run_chain_ci,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GATE_NAMES_EXPECTED = [
    "parity",
    "fold_baseline",
    "fold_flag_on",
    "crash_isolation",
    "version_skew",
    "cloud_smoke",
    "acceptance_toy",
    "dual_green",
    "supervisor_purity",
]


def _make_green(name: str = "g") -> GateOutcome:
    return GateOutcome(name=name, ok=True, detail="ok")


def _make_red(name: str = "r") -> GateOutcome:
    return GateOutcome(name=name, ok=False, detail="failed")


def _all_green_gates():
    return [(name, lambda n=name: _make_green(n)) for name in _GATE_NAMES_EXPECTED]


# ---------------------------------------------------------------------------
# GATE_ORDER structure
# ---------------------------------------------------------------------------


def test_gate_order_has_9_gates():
    assert len(GATE_ORDER) == 9


def test_gate_order_names_match():
    names = [name for name, _ in GATE_ORDER]
    assert names == _GATE_NAMES_EXPECTED


def test_gate_order_all_callable():
    for name, fn in GATE_ORDER:
        assert callable(fn), f"gate {name!r} is not callable"


# ---------------------------------------------------------------------------
# run_chain_ci — control flow
# ---------------------------------------------------------------------------


def test_run_chain_ci_all_green_passes():
    result = run_chain_ci(gates=_all_green_gates())
    assert result.passed is True
    assert len(result.gate_outcomes) == 9
    assert all(g.ok for g in result.gate_outcomes)


def test_run_chain_ci_no_short_circuit_on_red():
    """All gates run even when gate 1 is red."""
    first_red = [("parity", lambda: _make_red("parity"))]
    rest_green = [(name, lambda n=name: _make_green(n)) for name in _GATE_NAMES_EXPECTED[1:]]
    result = run_chain_ci(gates=first_red + rest_green)
    assert result.passed is False
    assert len(result.gate_outcomes) == 9  # all 9 collected


def test_run_chain_ci_collects_all_failures():
    gates = [(name, lambda n=name: _make_red(n)) for name in _GATE_NAMES_EXPECTED]
    result = run_chain_ci(gates=gates)
    assert not result.passed
    assert len(result.failures) == 9


def test_run_chain_ci_partial_red():
    gates = [(name, lambda n=name: _make_red(n) if n in ("parity", "dual_green") else _make_green(n))
             for name in _GATE_NAMES_EXPECTED]
    result = run_chain_ci(gates=gates)
    assert not result.passed
    assert {f.name for f in result.failures} == {"parity", "dual_green"}


def test_run_chain_ci_raising_gate_captured_not_propagated():
    def _raiser():
        raise RuntimeError("oracle blew up")

    gates = [("parity", _raiser)] + [
        (name, lambda n=name: _make_green(n)) for name in _GATE_NAMES_EXPECTED[1:]
    ]
    result = run_chain_ci(gates=gates)
    assert not result.passed
    assert result.gate_outcomes[0].name == "parity"
    assert not result.gate_outcomes[0].ok
    assert "oracle blew up" in result.gate_outcomes[0].detail


# ---------------------------------------------------------------------------
# commit_label
# ---------------------------------------------------------------------------


def test_commit_label_green_returns_stamp():
    result = ChainCIResult(passed=True, gate_outcomes=[_make_green()])
    assert result.commit_label() == HINGE_GATE_GREEN_STAMP
    assert "[HINGE GATE: GREEN]" in result.commit_label()


def test_commit_label_red_returns_empty_string():
    result = ChainCIResult(passed=False, gate_outcomes=[_make_red()])
    assert result.commit_label() == ""


def test_commit_label_all_green_stamp_non_empty():
    result = run_chain_ci(gates=_all_green_gates())
    label = result.commit_label()
    assert label == HINGE_GATE_GREEN_STAMP
    assert label  # non-empty


def test_commit_label_any_red_stamp_empty():
    gates = _all_green_gates()
    gates[3] = ("crash_isolation", lambda: _make_red("crash_isolation"))
    result = run_chain_ci(gates=gates)
    assert result.commit_label() == ""


# ---------------------------------------------------------------------------
# assert_program_md — stub-survival
# ---------------------------------------------------------------------------


def test_assert_program_md_returns_existing_file(tmp_path):
    stub = tmp_path / "PROGRAM.md"
    stub.write_text("# PROGRAM\n\n## M3\n\nstub\n\n## M3 Entry\n\n- seam: dormant\n", encoding="utf-8")
    with patch("megaplan.chain.ci_hook._PROGRAM_MD", stub):
        path = assert_program_md()
    assert path == stub


def test_assert_program_md_recreates_when_missing(tmp_path):
    stub = tmp_path / "briefs" / "validation" / "sequencing" / "PROGRAM.md"
    with patch("megaplan.chain.ci_hook._PROGRAM_MD", stub):
        path = assert_program_md()
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# PROGRAM" in content
    assert "## M3 Entry" in content


def test_assert_program_md_appends_m3_entry_when_missing(tmp_path):
    stub = tmp_path / "PROGRAM.md"
    stub.write_text("# PROGRAM\n\n## M3\n\nstub.\n", encoding="utf-8")
    with patch("megaplan.chain.ci_hook._PROGRAM_MD", stub):
        assert_program_md()
    content = stub.read_text(encoding="utf-8")
    assert "## M3 Entry" in content
    assert "dormant" in content


def test_assert_program_md_idempotent(tmp_path):
    stub = tmp_path / "PROGRAM.md"
    stub.write_text("# PROGRAM\n\n## M3\n\nstub.\n", encoding="utf-8")
    with patch("megaplan.chain.ci_hook._PROGRAM_MD", stub):
        assert_program_md()
        assert_program_md()
    content = stub.read_text(encoding="utf-8")
    assert content.count("## M3 Entry") == 1


def test_assert_program_md_real_file_has_m3_entry():
    """The real PROGRAM.md in the repo already has the M3 Entry section."""
    path = assert_program_md()
    content = path.read_text(encoding="utf-8")
    assert "## M3 Entry" in content
    assert "dormant" in content.lower()
    assert "M6" in content


# ---------------------------------------------------------------------------
# ChainCIResult.failures
# ---------------------------------------------------------------------------


def test_failures_property_filters_red():
    outcomes = [_make_green("a"), _make_red("b"), _make_green("c"), _make_red("d")]
    result = ChainCIResult(passed=False, gate_outcomes=outcomes)
    assert [f.name for f in result.failures] == ["b", "d"]


def test_failures_property_empty_when_all_green():
    outcomes = [_make_green(n) for n in _GATE_NAMES_EXPECTED]
    result = ChainCIResult(passed=True, gate_outcomes=outcomes)
    assert result.failures == []


# ---------------------------------------------------------------------------
# Import smoke — all gate callables are importable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gate_name", [
    "gate_parity",
    "gate_fold_baseline",
    "gate_fold_flag_on",
    "gate_crash_isolation",
    "gate_version_skew",
    "gate_cloud_smoke",
    "gate_acceptance_toy",
    "gate_dual_green",
    "gate_supervisor_purity",
])
def test_gate_callable_importable(gate_name):
    mod = importlib.import_module("megaplan.chain.ci_hook")
    fn = getattr(mod, gate_name, None)
    assert callable(fn), f"{gate_name} not importable or not callable"
