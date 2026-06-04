"""Compatibility checks for canonical orchestration modules and legacy facades."""

from __future__ import annotations

import importlib

import pytest


# ── module identity and symbol re-export ─────────────────────────────────

@pytest.mark.parametrize(
    ("legacy_module", "canonical_module", "symbol"),
    [
        # phase_result / recovery / progress (T4)
        (
            "megaplan.orchestration.phase_result",
            "arnold.pipelines.megaplan.orchestration.phase_result",
            "ExitKind",
        ),
        (
            "megaplan.orchestration.phase_result",
            "arnold.pipelines.megaplan.orchestration.phase_result",
            "PhaseResult",
        ),
        (
            "megaplan.orchestration.phase_result_classify",
            "arnold.pipelines.megaplan.orchestration.phase_result_classify",
            "classify_external_error_chain",
        ),
        (
            "megaplan.orchestration.recovery_policy",
            "arnold.pipelines.megaplan.orchestration.recovery_policy",
            "RecoveryPolicy",
        ),
        # gate checks / signals / evaluation / iteration (T5)
        (
            "megaplan.orchestration.gate_checks",
            "arnold.pipelines.megaplan.orchestration.gate_checks",
            "run_gate_checks",
        ),
        (
            "megaplan.orchestration.gate_checks",
            "arnold.pipelines.megaplan.orchestration.gate_checks",
            "build_gate_artifact",
        ),
        (
            "megaplan.orchestration.gate_signals",
            "arnold.pipelines.megaplan.orchestration.gate_signals",
            "build_gate_signals",
        ),
        (
            "megaplan.orchestration.gate_signals",
            "arnold.pipelines.megaplan.orchestration.gate_signals",
            "flag_weight",
        ),
        (
            "megaplan.orchestration.execution_evidence",
            "arnold.pipelines.megaplan.orchestration.execution_evidence",
            "validate_execution_evidence",
        ),
        (
            "megaplan.orchestration.rubber_stamp",
            "arnold.pipelines.megaplan.orchestration.rubber_stamp",
            "is_rubber_stamp",
        ),
        (
            "megaplan.orchestration.plan_structure",
            "arnold.pipelines.megaplan.orchestration.plan_structure",
            "validate_plan_structure",
        ),
        (
            "megaplan.orchestration.iteration_pressure",
            "arnold.pipelines.megaplan.orchestration.iteration_pressure",
            "compute_iteration_pressure",
        ),
        (
            "megaplan.orchestration.critique_status",
            "arnold.pipelines.megaplan.orchestration.critique_status",
            "annotate_unverifiable_checks",
        ),
        # verifiability / feedback / parallel_critique / tiebreaker (T7)
        (
            "megaplan.orchestration.verifiability",
            "arnold.pipelines.megaplan.orchestration.verifiability",
            "audit_criteria",
        ),
        (
            "megaplan.orchestration.feedback",
            "arnold.pipelines.megaplan.orchestration.feedback",
            "parse_feedback",
        ),
        (
            "megaplan.orchestration.parallel_critique",
            "arnold.pipelines.megaplan.orchestration.parallel_critique",
            "run_parallel_critique",
        ),
        (
            "megaplan.orchestration.tiebreaker",
            "arnold.pipelines.megaplan.orchestration.tiebreaker",
            "run_tiebreaker_cli",
        ),
        # prep_research (T7)
        (
            "megaplan.orchestration.prep_research",
            "arnold.pipelines.megaplan.orchestration.prep_research",
            "run_prep_orchestration",
        ),
        # evaluation facade with subprocess monkeypatch compatibility (T5)
        (
            "megaplan.orchestration.evaluation",
            "arnold.pipelines.megaplan.orchestration.execution_evidence",
            "validate_execution_evidence",
        ),
    ],
)
def test_legacy_orchestration_symbols_reexport_canonical_symbols(
    legacy_module: str,
    canonical_module: str,
    symbol: str,
) -> None:
    """Legacy megaplan.orchestration.* module attributes resolve to canonical objects."""
    legacy = importlib.import_module(legacy_module)
    canonical = importlib.import_module(canonical_module)
    assert getattr(legacy, symbol) is getattr(canonical, symbol), (
        f"{legacy_module}.{symbol} is not {canonical_module}.{symbol}"
    )


# ── evaluation facade special-case ──────────────────────────────────────

def test_evaluation_facade_reexports_gate_checks_symbols() -> None:
    """The evaluation compatibility facade re-exports gate_checks symbols."""
    legacy = importlib.import_module("megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.gate_checks"
    )
    assert legacy.run_gate_checks is canonical.run_gate_checks
    assert legacy.build_gate_artifact is canonical.build_gate_artifact
    assert legacy.build_orchestrator_guidance is canonical.build_orchestrator_guidance


def test_evaluation_facade_reexports_gate_signals_symbols() -> None:
    legacy = importlib.import_module("megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.gate_signals"
    )
    assert legacy.build_gate_signals is canonical.build_gate_signals
    assert legacy.flag_weight is canonical.flag_weight


def test_evaluation_facade_reexports_plan_structure_symbols() -> None:
    legacy = importlib.import_module("megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.plan_structure"
    )
    assert legacy.validate_plan_structure is canonical.validate_plan_structure
    assert legacy.parse_plan_sections is canonical.parse_plan_sections
    assert legacy.PlanSection is canonical.PlanSection


def test_evaluation_facade_reexports_rubber_stamp() -> None:
    legacy = importlib.import_module("megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.rubber_stamp"
    )
    assert legacy.is_rubber_stamp is canonical.is_rubber_stamp


def test_evaluation_facade_preserves_subprocess_module_attribute() -> None:
    """The evaluation facade keeps ``subprocess`` as a module attribute for monkeypatch compat."""
    import subprocess

    legacy = importlib.import_module("megaplan.orchestration.evaluation")
    assert legacy.subprocess is subprocess, (
        "evaluation.subprocess must reference the real subprocess module"
    )


# ── monkeypatch compatibility ───────────────────────────────────────────
# Note: Most orchestration facades use ``from canonical import *`` (thin
# facade pattern).  Monkeypatching through the legacy facade works for
# consumers that ``import megaplan.orchestration.X`` or ``from
# megaplan.orchestration.X import symbol`` — the patched attribute is
# visible on the legacy module.  It does NOT propagate to the canonical
# module object (unlike the sys.modules aliasing used by review.parallel
# and execute.* facades).


def test_legacy_gate_checks_monkeypatch_visible_through_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.orchestration.gate_checks is visible to importers."""
    import megaplan.orchestration.gate_checks as legacy

    sentinel = object()
    monkeypatch.setattr(legacy, "run_gate_checks", sentinel)
    # The patched attribute is visible on the legacy module
    assert legacy.run_gate_checks is sentinel


def test_legacy_phase_result_monkeypatch_visible_through_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.orchestration.phase_result is visible to importers."""
    import megaplan.orchestration.phase_result as legacy

    sentinel = object()
    monkeypatch.setattr(legacy, "PhaseResult", sentinel)
    assert legacy.PhaseResult is sentinel


def test_legacy_evaluation_monkeypatch_visible_through_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.orchestration.evaluation is visible to importers."""
    import megaplan.orchestration.evaluation as legacy

    sentinel = object()
    monkeypatch.setattr(legacy, "run_gate_checks", sentinel)
    assert legacy.run_gate_checks is sentinel
