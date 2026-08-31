"""Tests for CandidateOutcome, terminal classification, supersession laundering, crosswalk.

Exercises classification, terminal vs non-terminal, supersession laundering
rejection, and SubjectKind-to-outcome crosswalk coverage.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

import pytest

from arnold.workflow.completion.outcomes import (
    CandidateOutcome,
    SUBJECT_KIND_OUTCOME_CROSSWALK,
    is_laundering,
    is_terminal,
    outcome_requires_acceptance,
    validate_supersession,
)


# ---------------------------------------------------------------------------
# CandidateOutcome — enum values
# ---------------------------------------------------------------------------


class TestCandidateOutcome:
    """CandidateOutcome enum values."""

    def test_all_outcomes(self) -> None:
        """All CandidateOutcome variants are present."""
        outcomes = set(CandidateOutcome)
        assert len(outcomes) == 10
        assert CandidateOutcome.SUCCESS in outcomes
        assert CandidateOutcome.BLOCKED in outcomes
        assert CandidateOutcome.WAIVED in outcomes
        assert CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT in outcomes
        assert CandidateOutcome.QUARANTINED in outcomes
        assert CandidateOutcome.INCOMPLETE in outcomes

    def test_values(self) -> None:
        """String values for each outcome."""
        assert CandidateOutcome.SUCCESS.value == "success"
        assert CandidateOutcome.BLOCKED.value == "blocked"
        assert CandidateOutcome.WAIVED.value == "waived"
        assert CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT.value == "superseded_by_named_exit"
        assert CandidateOutcome.QUARANTINED.value == "quarantined"
        assert CandidateOutcome.INCOMPLETE.value == "incomplete"
        assert CandidateOutcome.STALE_EVIDENCE.value == "stale_evidence"
        assert CandidateOutcome.DEGRADED.value == "degraded"
        assert CandidateOutcome.REVIEW_REQUIRED.value == "review_required"
        assert CandidateOutcome.REWORK_REQUIRED.value == "rework_required"


# ---------------------------------------------------------------------------
# Terminal classification
# ---------------------------------------------------------------------------


class TestIsTerminal:
    """is_terminal outcome classification."""

    def test_success_is_terminal(self) -> None:
        """SUCCESS is terminal."""
        assert is_terminal(CandidateOutcome.SUCCESS) is True

    def test_blocked_is_terminal(self) -> None:
        """BLOCKED is terminal."""
        assert is_terminal(CandidateOutcome.BLOCKED) is True

    def test_waived_is_terminal(self) -> None:
        """WAIVED is terminal."""
        assert is_terminal(CandidateOutcome.WAIVED) is True

    def test_superseded_is_terminal(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT is terminal."""
        assert is_terminal(CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT) is True

    def test_quarantined_is_terminal(self) -> None:
        """QUARANTINED is terminal."""
        assert is_terminal(CandidateOutcome.QUARANTINED) is True

    def test_incomplete_is_not_terminal(self) -> None:
        """INCOMPLETE is not terminal."""
        assert is_terminal(CandidateOutcome.INCOMPLETE) is False

    def test_five_terminal_outcomes(self) -> None:
        """Five outcomes classified as terminal."""
        terminal_count = sum(
            1 for o in CandidateOutcome if is_terminal(o)
        )
        assert terminal_count == 5


# ---------------------------------------------------------------------------
# Outcome requires acceptance
# ---------------------------------------------------------------------------


class TestOutcomeRequiresAcceptance:
    """outcome_requires_acceptance classification."""

    def test_success_requires_acceptance(self) -> None:
        """SUCCESS requires acceptance."""
        assert outcome_requires_acceptance(CandidateOutcome.SUCCESS) is True

    def test_waived_requires_acceptance(self) -> None:
        """WAIVED requires acceptance."""
        assert outcome_requires_acceptance(CandidateOutcome.WAIVED) is True

    def test_superseded_requires_acceptance(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT requires acceptance."""
        assert outcome_requires_acceptance(CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT) is True

    def test_blocked_does_not_require_acceptance(self) -> None:
        """BLOCKED does not require acceptance."""
        assert outcome_requires_acceptance(CandidateOutcome.BLOCKED) is False

    def test_quarantined_does_not_require_acceptance(self) -> None:
        """QUARANTINED does not require acceptance."""
        assert outcome_requires_acceptance(CandidateOutcome.QUARANTINED) is False

    def test_incomplete_does_not_require_acceptance(self) -> None:
        """INCOMPLETE does not require acceptance."""
        assert outcome_requires_acceptance(CandidateOutcome.INCOMPLETE) is False

    def test_three_require_acceptance(self) -> None:
        """Three outcomes require acceptance."""
        count = sum(
            1 for o in CandidateOutcome if outcome_requires_acceptance(o)
        )
        assert count == 3


# ---------------------------------------------------------------------------
# Supersession laundering validation
# ---------------------------------------------------------------------------


class TestValidateSupersession:
    """validate_supersession rejects laundering transitions."""

    def test_valid_supersession_success_to_blocked(self) -> None:
        """SUCCESS -> BLOCKED is valid (no exception)."""
        # Should not raise
        validate_supersession(
            CandidateOutcome.SUCCESS,
            CandidateOutcome.BLOCKED,
        )

    def test_valid_supersession_incomplete_to_success(self) -> None:
        """INCOMPLETE -> SUCCESS is valid."""
        validate_supersession(
            CandidateOutcome.INCOMPLETE,
            CandidateOutcome.SUCCESS,
        )

    def test_rejects_superseded_to_success(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT -> SUCCESS is laundering."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.SUCCESS,
            )

    def test_rejects_superseded_to_waived(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT -> WAIVED is laundering."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.WAIVED,
            )

    def test_rejects_superseded_to_blocked(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT -> BLOCKED is laundering."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.BLOCKED,
            )

    def test_rejects_superseded_to_quarantined(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT -> QUARANTINED is laundering."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.QUARANTINED,
            )

    def test_rejects_superseded_to_success_again(self) -> None:
        """A named-exit supersession cannot be resurrected."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.SUCCESS,
            )

    def test_rejects_superseded_to_waived_again(self) -> None:
        """A named-exit supersession cannot be waived."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.WAIVED,
            )

    def test_rejects_superseded_to_superseded(self) -> None:
        """A named-exit supersession needs an intervening binding."""
        with pytest.raises(ValueError, match="laundering"):
            validate_supersession(
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
                CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
            )


# ---------------------------------------------------------------------------
# is_laundering — non-raising predicate
# ---------------------------------------------------------------------------


class TestIsLaundering:
    """is_laundering predicate."""

    def test_detects_laundering(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT -> SUCCESS is laundering."""
        assert is_laundering(
            CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
            CandidateOutcome.SUCCESS,
        ) is True

    def test_clean_transition(self) -> None:
        """SUCCESS -> BLOCKED is not laundering."""
        assert is_laundering(
            CandidateOutcome.SUCCESS,
            CandidateOutcome.BLOCKED,
        ) is False

    def test_superseded_to_success(self) -> None:
        """SUPERSEDED_BY_NAMED_EXIT -> SUCCESS is laundering."""
        assert is_laundering(
            CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
            CandidateOutcome.SUCCESS,
        ) is True


# ---------------------------------------------------------------------------
# SubjectKind-to-outcome crosswalk coverage
# ---------------------------------------------------------------------------


class TestSubjectKindOutcomeCrosswalk:
    """SUBJECT_KIND_OUTCOME_CROSSWALK coverage."""

    def test_coverage_for_workflow(self) -> None:
        """WORKFLOW has every candidate outcome."""
        outcomes = set(SUBJECT_KIND_OUTCOME_CROSSWALK["WORKFLOW"])
        assert "success" in outcomes
        assert "blocked" in outcomes
        assert "waived" in outcomes
        assert "superseded_by_named_exit" in outcomes
        assert "quarantined" in outcomes
        assert "incomplete" in outcomes

    def test_coverage_for_step(self) -> None:
        """STEP has every candidate outcome."""
        outcomes = set(SUBJECT_KIND_OUTCOME_CROSSWALK["STEP"])
        assert len(outcomes) == len(CandidateOutcome)

    def test_coverage_for_dynamic_task(self) -> None:
        """DYNAMIC_TASK uses the complete outcome crosswalk."""
        outcomes = set(SUBJECT_KIND_OUTCOME_CROSSWALK["DYNAMIC_TASK"])
        assert len(outcomes) == len(CandidateOutcome)
        assert "success" in outcomes
        assert "blocked" in outcomes

    def test_coverage_for_effect(self) -> None:
        """EFFECT uses the complete outcome crosswalk."""
        outcomes = set(SUBJECT_KIND_OUTCOME_CROSSWALK["EFFECT"])
        assert len(outcomes) == len(CandidateOutcome)
        assert "success" in outcomes
        assert "blocked" in outcomes

    def test_coverage_for_human_boundary(self) -> None:
        """HUMAN_BOUNDARY has every candidate outcome."""
        outcomes = set(SUBJECT_KIND_OUTCOME_CROSSWALK["HUMAN_BOUNDARY"])
        assert len(outcomes) == len(CandidateOutcome)

    def test_crosswalk_keys_match_subject_kinds(self) -> None:
        """Crosswalk keys cover every SubjectKind value."""
        from arnold.workflow.completion.spec import SubjectKind
        crosswalk_keys = set(SUBJECT_KIND_OUTCOME_CROSSWALK)
        for kind in SubjectKind:
            assert kind.name in crosswalk_keys, (
                f"SubjectKind.{kind.name} not in crosswalk"
            )
