"""Compatibility checks for canonical audit modules and legacy facades."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("legacy_module", "canonical_module", "symbol"),
    [
        ("megaplan.audits.audit_engine", "arnold.pipelines.megaplan.audits.audit_engine", "record_tiebreaker_audit"),
        ("megaplan.audits.critique_evaluator", "arnold.pipelines.megaplan.audits.critique_evaluator", "validate_evaluator_verdict"),
        ("megaplan.audits.hermes_vendoring", "arnold.pipelines.megaplan.audits.hermes_vendoring", "audit_vendored_agent_tree"),
        ("megaplan.audits.iteration", "arnold.pipelines.megaplan.audits.iteration", "compute_iteration_pressure"),
        ("megaplan.audits.quality_gates", "arnold.pipelines.megaplan.audits.quality_gates", "run_quality_checks"),
        ("megaplan.audits.robustness", "arnold.pipelines.megaplan.audits.robustness", "validate_critique_checks"),
        ("megaplan.audits.capabilities", "arnold.pipelines.megaplan.audits.capabilities", "get_worker_capabilities"),
        ("megaplan.audits.verifiability", "arnold.pipelines.megaplan.audits.verifiability", "audit_criteria"),
    ],
)
def test_legacy_audit_modules_reexport_canonical_symbols(
    legacy_module: str,
    canonical_module: str,
    symbol: str,
) -> None:
    legacy = importlib.import_module(legacy_module)
    canonical = importlib.import_module(canonical_module)
    assert getattr(legacy, symbol) is getattr(canonical, symbol)


def test_legacy_quality_gates_reexports_private_helpers() -> None:
    legacy = importlib.import_module("megaplan.audits.quality_gates")
    canonical = importlib.import_module("arnold.pipelines.megaplan.audits.quality_gates")
    assert legacy._check_file_growth is canonical._check_file_growth
    assert legacy._check_duplicate_functions is canonical._check_duplicate_functions
    assert legacy._check_dead_imports is canonical._check_dead_imports
    assert legacy._check_test_coverage is canonical._check_test_coverage


def test_legacy_audit_engine_reexports_private_totals_helpers() -> None:
    legacy = importlib.import_module("megaplan.audits.audit_engine")
    canonical = importlib.import_module("arnold.pipelines.megaplan.audits.audit_engine")
    assert legacy._compute_totals is canonical._compute_totals
    assert legacy._empty_totals is canonical._empty_totals
    assert legacy._next_index is canonical._next_index
