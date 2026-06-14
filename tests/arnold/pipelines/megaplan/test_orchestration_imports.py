"""Canonical orchestration module import checks."""

from __future__ import annotations

import importlib

import pytest


# ── canonical symbol exports ─────────────────────────────────────────────

@pytest.mark.parametrize(
    ("canonical_module", "symbol"),
    [
        # phase_result / recovery / progress (T4)
        (
            "arnold.pipelines.megaplan.orchestration.phase_result",
            "ExitKind",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.phase_result",
            "PhaseResult",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.phase_result_classify",
            "classify_external_error_chain",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.recovery_policy",
            "RecoveryPolicy",
        ),
        # gate checks / signals / evaluation / iteration (T5)
        (
            "arnold.pipelines.megaplan.orchestration.gate_checks",
            "run_gate_checks",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.gate_checks",
            "build_gate_artifact",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.gate_signals",
            "build_gate_signals",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.gate_signals",
            "flag_weight",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.execution_evidence",
            "validate_execution_evidence",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.rubber_stamp",
            "is_rubber_stamp",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.plan_structure",
            "validate_plan_structure",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.iteration_pressure",
            "compute_iteration_pressure",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.critique_status",
            "annotate_unverifiable_checks",
        ),
        # verifiability / feedback / parallel_critique / tiebreaker (T7)
        (
            "arnold.pipelines.megaplan.orchestration.verifiability",
            "audit_criteria",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.feedback",
            "parse_feedback",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.parallel_critique",
            "run_parallel_critique",
        ),
        (
            "arnold.pipelines.megaplan.orchestration.tiebreaker",
            "run_tiebreaker_cli",
        ),
        # prep_research (T7)
        (
            "arnold.pipelines.megaplan.orchestration.prep_research",
            "run_prep_orchestration",
        ),
        # evaluation facade with subprocess monkeypatch compatibility (T5)
        (
            "arnold.pipelines.megaplan.orchestration.execution_evidence",
            "validate_execution_evidence",
        ),
    ],
)
def test_canonical_orchestration_symbols_exist(
    canonical_module: str,
    symbol: str,
) -> None:
    """Canonical arnold.pipelines.megaplan.orchestration.* module attributes resolve."""
    canonical = importlib.import_module(canonical_module)
    assert hasattr(canonical, symbol)


# ── evaluation facade special-case ──────────────────────────────────────

def test_evaluation_facade_reexports_gate_checks_symbols() -> None:
    """The canonical evaluation module re-exports gate_checks symbols."""
    evaluation = importlib.import_module("arnold.pipelines.megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.gate_checks"
    )
    assert evaluation.run_gate_checks is canonical.run_gate_checks
    assert evaluation.build_gate_artifact is canonical.build_gate_artifact
    assert evaluation.build_orchestrator_guidance is canonical.build_orchestrator_guidance


def test_evaluation_facade_reexports_gate_signals_symbols() -> None:
    evaluation = importlib.import_module("arnold.pipelines.megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.gate_signals"
    )
    assert evaluation.build_gate_signals is canonical.build_gate_signals
    assert evaluation.flag_weight is canonical.flag_weight


def test_evaluation_facade_reexports_plan_structure_symbols() -> None:
    evaluation = importlib.import_module("arnold.pipelines.megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.plan_structure"
    )
    assert evaluation.validate_plan_structure is canonical.validate_plan_structure
    assert evaluation.parse_plan_sections is canonical.parse_plan_sections
    assert evaluation.PlanSection is canonical.PlanSection


def test_evaluation_facade_reexports_rubber_stamp() -> None:
    evaluation = importlib.import_module("arnold.pipelines.megaplan.orchestration.evaluation")
    canonical = importlib.import_module(
        "arnold.pipelines.megaplan.orchestration.rubber_stamp"
    )
    assert evaluation.is_rubber_stamp is canonical.is_rubber_stamp


def test_evaluation_facade_preserves_subprocess_module_attribute() -> None:
    """The evaluation module keeps ``subprocess`` as a module attribute for monkeypatching."""
    import subprocess

    evaluation = importlib.import_module("arnold.pipelines.megaplan.orchestration.evaluation")
    assert evaluation.subprocess is subprocess, (
        "evaluation.subprocess must reference the real subprocess module"
    )


# ── monkeypatch compatibility ───────────────────────────────────────────
# Note: Most orchestration facades use ``from canonical import *`` (thin
# facade pattern).  Monkeypatching through the legacy facade works for
# consumers that ``import arnold.pipelines.megaplan.orchestration.X`` or ``from
# megaplan.orchestration.X import symbol`` — the patched attribute is
# visible on the legacy module.  It does NOT propagate to the canonical
# module object (unlike the sys.modules aliasing used by review.parallel
# and execute.* facades).


def test_legacy_gate_checks_monkeypatch_visible_through_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.orchestration.gate_checks is visible to importers."""
    import arnold.pipelines.megaplan.orchestration.gate_checks as legacy

    sentinel = object()
    monkeypatch.setattr(legacy, "run_gate_checks", sentinel)
    # The patched attribute is visible on the legacy module
    assert legacy.run_gate_checks is sentinel


def test_legacy_phase_result_monkeypatch_visible_through_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.orchestration.phase_result is visible to importers."""
    import arnold.pipelines.megaplan.orchestration.phase_result as legacy

    sentinel = object()
    monkeypatch.setattr(legacy, "PhaseResult", sentinel)
    assert legacy.PhaseResult is sentinel


def test_legacy_evaluation_monkeypatch_visible_through_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatching megaplan.orchestration.evaluation is visible to importers."""
    import arnold.pipelines.megaplan.orchestration.evaluation as legacy

    sentinel = object()
    monkeypatch.setattr(legacy, "run_gate_checks", sentinel)
    assert legacy.run_gate_checks is sentinel
