"""Targeted tests comparing native @phase/@decision port declarations
to the current ``build_pipeline()`` stage port semantics.

Each test verifies that a native phase wrapper carries the same
``consumes`` / ``produces`` typed ports as the corresponding
:class:`Stage` in the hand-built pipeline.  Decision vocabularies
are compared for the gate and tiebreaker points.

Failures here mean a native declaration has drifted from the canonical
``build_pipeline()`` — the fix is to update the module-level port tuples
in ``arnold/pipelines/megaplan/pipeline.py``.
"""

from __future__ import annotations

from typing import FrozenSet

from arnold.pipelines.megaplan.pipeline import (
    _CRITIQUE_CONSUMES,
    _CRITIQUE_PRODUCES,
    _EXECUTE_CONSUMES,
    _EXECUTE_PRODUCES,
    _FINALIZE_CONSUMES,
    _FINALIZE_PRODUCES,
    _GATE_CONSUMES,
    _GATE_DECISION_VOCABULARY,
    _GATE_PRODUCES,
    _PLAN_CONSUMES,
    _PLAN_PRODUCES,
    _PREP_CONSUMES,
    _PREP_PRODUCES,
    _REVIEW_CONSUMES,
    _REVIEW_PRODUCES,
    _REVISE_CONSUMES,
    _REVISE_PRODUCES,
    _TIEBREAKER_CONSUMES,
    _TIEBREAKER_DECISION_VOCABULARY,
    _TIEBREAKER_PRODUCES,
    build_pipeline,
)
from arnold.pipeline.native.decorators import (
    get_decision_meta,
    get_phase_meta,
    is_decision,
    is_phase,
)

# ── helpers ────────────────────────────────────────────────────────────────


def _bp_stage_ports(name: str):
    """Return (produces_tuple, consumes_tuple) for *name* from build_pipeline()."""
    pl = build_pipeline()
    stage = pl.stages[name]
    produces = tuple(stage.produces) if stage.produces else ()
    consumes = tuple(stage.consumes) if stage.consumes else ()
    return produces, consumes


def _bp_stage_decision_vocabulary(name: str) -> frozenset[str]:
    """Return the ``decision_vocabulary`` frozenset from build_pipeline()."""
    pl = build_pipeline()
    stage = pl.stages[name]
    return frozenset(stage.decision_vocabulary) if stage.decision_vocabulary else frozenset()


# ═══════════════════════════════════════════════════════════════════════════
# Phase port metadata parity (one test class per phase)
# ═══════════════════════════════════════════════════════════════════════════


class TestPrepPortDeclaration:
    """Native prep phase produces/consumes the same ports as the prep Stage."""

    def test_prep_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("prep")
        assert _PREP_PRODUCES == bp_produces, (
            f"prep produces mismatch:\n"
            f"  native:  {_PREP_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_prep_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("prep")
        assert _PREP_CONSUMES == bp_consumes, (
            f"prep consumes mismatch:\n"
            f"  native:  {_PREP_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestPlanPortDeclaration:
    """Native plan phase produces/consumes the same ports as the plan Stage."""

    def test_plan_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("plan")
        assert _PLAN_PRODUCES == bp_produces, (
            f"plan produces mismatch:\n"
            f"  native:  {_PLAN_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_plan_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("plan")
        assert _PLAN_CONSUMES == bp_consumes, (
            f"plan consumes mismatch:\n"
            f"  native:  {_PLAN_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestCritiquePortDeclaration:
    """Native critique phase produces/consumes the same ports as the critique Stage."""

    def test_critique_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("critique")
        assert _CRITIQUE_PRODUCES == bp_produces, (
            f"critique produces mismatch:\n"
            f"  native:  {_CRITIQUE_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_critique_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("critique")
        assert _CRITIQUE_CONSUMES == bp_consumes, (
            f"critique consumes mismatch:\n"
            f"  native:  {_CRITIQUE_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestGatePortDeclaration:
    """Native gate phase produces/consumes the same ports as the gate Stage."""

    def test_gate_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("gate")
        assert _GATE_PRODUCES == bp_produces, (
            f"gate produces mismatch:\n"
            f"  native:  {_GATE_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_gate_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("gate")
        assert _GATE_CONSUMES == bp_consumes, (
            f"gate consumes mismatch:\n"
            f"  native:  {_GATE_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestRevisePortDeclaration:
    """Native revise phase produces/consumes the same ports as the revise Stage."""

    def test_revise_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("revise")
        assert _REVISE_PRODUCES == bp_produces, (
            f"revise produces mismatch:\n"
            f"  native:  {_REVISE_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_revise_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("revise")
        assert _REVISE_CONSUMES == bp_consumes, (
            f"revise consumes mismatch:\n"
            f"  native:  {_REVISE_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestFinalizePortDeclaration:
    """Native finalize phase produces/consumes the same ports as the finalize Stage."""

    def test_finalize_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("finalize")
        assert _FINALIZE_PRODUCES == bp_produces, (
            f"finalize produces mismatch:\n"
            f"  native:  {_FINALIZE_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_finalize_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("finalize")
        assert _FINALIZE_CONSUMES == bp_consumes, (
            f"finalize consumes mismatch:\n"
            f"  native:  {_FINALIZE_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestExecutePortDeclaration:
    """Native execute phase produces/consumes the same ports as the execute Stage."""

    def test_execute_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("execute")
        assert _EXECUTE_PRODUCES == bp_produces, (
            f"execute produces mismatch:\n"
            f"  native:  {_EXECUTE_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_execute_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("execute")
        assert _EXECUTE_CONSUMES == bp_consumes, (
            f"execute consumes mismatch:\n"
            f"  native:  {_EXECUTE_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestReviewPortDeclaration:
    """Native review phase produces/consumes the same ports as the review Stage."""

    def test_review_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("review")
        assert _REVIEW_PRODUCES == bp_produces, (
            f"review produces mismatch:\n"
            f"  native:  {_REVIEW_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_review_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("review")
        assert _REVIEW_CONSUMES == bp_consumes, (
            f"review consumes mismatch:\n"
            f"  native:  {_REVIEW_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


class TestTiebreakerPortDeclaration:
    """Native tiebreaker phase produces/consumes the same ports as the tiebreaker Stage."""

    def test_tiebreaker_produces_matches_build_pipeline(self) -> None:
        bp_produces, _ = _bp_stage_ports("tiebreaker")
        assert _TIEBREAKER_PRODUCES == bp_produces, (
            f"tiebreaker produces mismatch:\n"
            f"  native:  {_TIEBREAKER_PRODUCES}\n"
            f"  bp:      {bp_produces}"
        )

    def test_tiebreaker_consumes_matches_build_pipeline(self) -> None:
        _, bp_consumes = _bp_stage_ports("tiebreaker")
        assert _TIEBREAKER_CONSUMES == bp_consumes, (
            f"tiebreaker consumes mismatch:\n"
            f"  native:  {_TIEBREAKER_CONSUMES}\n"
            f"  bp:      {bp_consumes}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Decision vocabulary parity
# ═══════════════════════════════════════════════════════════════════════════


class TestDecisionVocabularyDeclaration:
    """Native decision vocabularies match the Stage decision_vocabulary fields."""

    def test_gate_decision_vocabulary_matches_build_pipeline(self) -> None:
        """Gate decision vocabulary mirrors PLANNING_DECISIONS."""
        bp_vocab = _bp_stage_decision_vocabulary("gate")
        assert _GATE_DECISION_VOCABULARY == bp_vocab, (
            f"gate decision vocabulary mismatch:\n"
            f"  native:  {_GATE_DECISION_VOCABULARY}\n"
            f"  bp:      {bp_vocab}"
        )

    def test_tiebreaker_decision_vocabulary_matches_build_pipeline(self) -> None:
        """Tiebreaker decision vocabulary mirrors {iterate, proceed, escalate}."""
        bp_vocab = _bp_stage_decision_vocabulary("tiebreaker")
        assert _TIEBREAKER_DECISION_VOCABULARY == bp_vocab, (
            f"tiebreaker decision vocabulary mismatch:\n"
            f"  native:  {_TIEBREAKER_DECISION_VOCABULARY}\n"
            f"  bp:      {bp_vocab}"
        )

    def test_gate_has_four_decisions(self) -> None:
        """Gate vocabulary contains exactly the four planning decisions."""
        assert _GATE_DECISION_VOCABULARY == frozenset(
            {"proceed", "iterate", "tiebreaker", "escalate"}
        )

    def test_tiebreaker_has_three_decisions(self) -> None:
        """Tiebreaker vocabulary contains exactly three decisions."""
        assert _TIEBREAKER_DECISION_VOCABULARY == frozenset(
            {"iterate", "proceed", "escalate"}
        )


# ═══════════════════════════════════════════════════════════════════════════
# Decorator presence checks
# ═══════════════════════════════════════════════════════════════════════════


class TestNativeWrapperDecoratorPresence:
    """Every native wrapper function must carry the expected decorator markers."""

    def test_all_nine_phases_are_decorated(self) -> None:
        """All nine native phase wrappers are @phase-decorated."""
        from arnold.pipelines.megaplan.pipeline import (
            _native_critique,
            _native_execute,
            _native_finalize,
            _native_gate,
            _native_plan,
            _native_prep,
            _native_review,
            _native_revise,
            _native_tiebreaker,
        )

        phases = {
            "prep": _native_prep,
            "plan": _native_plan,
            "critique": _native_critique,
            "gate": _native_gate,
            "revise": _native_revise,
            "finalize": _native_finalize,
            "execute": _native_execute,
            "review": _native_review,
            "tiebreaker": _native_tiebreaker,
        }

        for name, fn in phases.items():
            assert is_phase(fn), f"{name} wrapper is not @phase-decorated"

    def test_phase_names_match_stage_keys(self) -> None:
        """Native @phase names equal the stage keys in build_pipeline()."""
        from arnold.pipelines.megaplan.pipeline import (
            _native_critique,
            _native_execute,
            _native_finalize,
            _native_gate,
            _native_plan,
            _native_prep,
            _native_review,
            _native_revise,
            _native_tiebreaker,
        )

        phases = {
            "prep": _native_prep,
            "plan": _native_plan,
            "critique": _native_critique,
            "gate": _native_gate,
            "revise": _native_revise,
            "finalize": _native_finalize,
            "execute": _native_execute,
            "review": _native_review,
            "tiebreaker": _native_tiebreaker,
        }

        for expected_name, fn in phases.items():
            meta = get_phase_meta(fn)
            actual = meta["name"] if meta else None
            assert actual == expected_name, (
                f"@phase name mismatch for {expected_name}: "
                f"got {actual!r}"
            )

    def test_gate_decision_is_decorated(self) -> None:
        """_native_gate_decision is @decision-decorated."""
        from arnold.pipelines.megaplan.pipeline import _native_gate_decision

        assert is_decision(_native_gate_decision), (
            "_native_gate_decision is not @decision-decorated"
        )

    def test_tiebreaker_decision_is_decorated(self) -> None:
        """_native_tiebreaker_decision is @decision-decorated."""
        from arnold.pipelines.megaplan.pipeline import (
            _native_tiebreaker_decision,
        )

        assert is_decision(_native_tiebreaker_decision), (
            "_native_tiebreaker_decision is not @decision-decorated"
        )

    def test_decision_names_match(self) -> None:
        """Native @decision names match the expected gate/tiebreaker keys."""
        from arnold.pipelines.megaplan.pipeline import (
            _native_gate_decision,
            _native_tiebreaker_decision,
        )

        gate_meta = get_decision_meta(_native_gate_decision)
        assert gate_meta["name"] == "gate", (
            f"gate decision name mismatch: {gate_meta['name']!r}"
        )

        tb_meta = get_decision_meta(_native_tiebreaker_decision)
        assert tb_meta["name"] == "tiebreaker", (
            f"tiebreaker decision name mismatch: {tb_meta['name']!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Structural quick-checks
# ═══════════════════════════════════════════════════════════════════════════


class TestPortDeclarationSanity:
    """Quick structural invariants for the native port declarations."""

    def test_nine_phases_have_port_declarations(self) -> None:
        """All nine phases have non-None produces/consumes tuples."""
        all_ports = [
            ("prep", _PREP_PRODUCES, _PREP_CONSUMES),
            ("plan", _PLAN_PRODUCES, _PLAN_CONSUMES),
            ("critique", _CRITIQUE_PRODUCES, _CRITIQUE_CONSUMES),
            ("gate", _GATE_PRODUCES, _GATE_CONSUMES),
            ("revise", _REVISE_PRODUCES, _REVISE_CONSUMES),
            ("finalize", _FINALIZE_PRODUCES, _FINALIZE_CONSUMES),
            ("execute", _EXECUTE_PRODUCES, _EXECUTE_CONSUMES),
            ("review", _REVIEW_PRODUCES, _REVIEW_CONSUMES),
            ("tiebreaker", _TIEBREAKER_PRODUCES, _TIEBREAKER_CONSUMES),
        ]
        for name, produces, consumes in all_ports:
            assert isinstance(produces, tuple), (
                f"{name} produces is not a tuple: {type(produces)}"
            )
            assert isinstance(consumes, tuple), (
                f"{name} consumes is not a tuple: {type(consumes)}"
            )

    def test_critique_consumes_three_inputs(self) -> None:
        """Critique is the only stage consuming three upstream ports."""
        assert len(_CRITIQUE_CONSUMES) == 3, (
            f"critique should consume 3 ports, got {len(_CRITIQUE_CONSUMES)}"
        )

    def test_prep_consumes_nothing(self) -> None:
        """Prep is the entry point — consumes nothing."""
        assert len(_PREP_CONSUMES) == 0, (
            f"prep should consume 0 ports, got {len(_PREP_CONSUMES)}"
        )

    def test_review_produces_review_payload(self) -> None:
        """Review produces a review_payload port."""
        assert len(_REVIEW_PRODUCES) == 1
        port = _REVIEW_PRODUCES[0]
        assert port.logical_type == "megaplan.planning.review_payload"

    def test_finalize_and_tiebreaker_both_consume_gate(self) -> None:
        """Both finalize and tiebreaker consume from gate."""
        # They should consume the same logical port from gate
        finalize_consume = _FINALIZE_CONSUMES[0]
        tiebreaker_consume = _TIEBREAKER_CONSUMES[0]
        assert finalize_consume.logical_type == tiebreaker_consume.logical_type, (
            "finalize and tiebreaker should consume the same gate logical type"
        )
