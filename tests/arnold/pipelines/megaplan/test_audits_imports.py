"""Canonical audit module import checks."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("canonical_module", "symbol"),
    [
        ("arnold.pipelines.megaplan.audits.audit_engine", "record_tiebreaker_audit"),
        ("arnold.pipelines.megaplan.audits.critique_evaluator", "validate_evaluator_verdict"),
        ("arnold.pipelines.megaplan.audits.hermes_vendoring", "audit_vendored_agent_tree"),
        ("arnold.pipelines.megaplan.audits.iteration", "compute_iteration_pressure"),
        ("arnold.pipelines.megaplan.audits.quality_gates", "run_quality_checks"),
        ("arnold.pipelines.megaplan.audits.robustness", "validate_critique_checks"),
        ("arnold.pipelines.megaplan.audits.capabilities", "get_worker_capabilities"),
        ("arnold.pipelines.megaplan.audits.verifiability", "audit_criteria"),
    ],
)
def test_canonical_audit_modules_export_symbols(
    canonical_module: str,
    symbol: str,
) -> None:
    canonical = importlib.import_module(canonical_module)
    assert hasattr(canonical, symbol)


def test_canonical_quality_gates_exports_private_helpers() -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.audits.quality_gates")
    assert callable(canonical._check_file_growth)
    assert callable(canonical._check_duplicate_functions)
    assert callable(canonical._check_dead_imports)
    assert callable(canonical._check_test_coverage)


def test_canonical_audit_engine_exports_private_totals_helpers() -> None:
    canonical = importlib.import_module("arnold.pipelines.megaplan.audits.audit_engine")
    assert callable(canonical._compute_totals)
    assert callable(canonical._empty_totals)
    assert callable(canonical._next_index)
