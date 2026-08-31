"""Tests for completion fixture classes and precondition assertion.
"""

from __future__ import annotations

import pytest

from arnold.workflow.completion.fixtures import (
    FalseDoneFixture,
    ReviewExecutableFixture,
    UnrelatedEvidencePreservationFixture,
    corrupted_shadow_precondition,
)
from arnold.workflow.completion.outcomes import CandidateOutcome
from arnold.workflow.completion.shadow import evaluate_shadow
from arnold.workflow.completion.spec import SubjectKind
from arnold.workflow.completion.source_declaration import (
    SourceDeclaration,
    SubjectDeclaration,
)


# ---------------------------------------------------------------------------
# FalseDoneFixture — rejection of done without accepted attempt
# ---------------------------------------------------------------------------


class TestFalseDoneFixture:
    """FalseDoneFixture verifies false-done rejection."""

    def test_create_default(self) -> None:
        fixture = FalseDoneFixture.create_default()
        assert fixture.outcome == CandidateOutcome.SUCCESS
        assert fixture.is_terminal is True
        assert fixture.requires_acceptance is True

    def test_assert_not_accepted_no_receipt(self) -> None:
        """Without acceptance receipt, assertion passes (candidate rejected)."""
        fixture = FalseDoneFixture.create_default()
        # This should pass without exception
        fixture.assert_not_accepted(False)

    def test_assert_not_accepted_with_receipt_raises(self) -> None:
        """With acceptance receipt, assertion fails — fixture is misconfigured."""
        fixture = FalseDoneFixture.create_default()
        with pytest.raises(AssertionError, match="has_acceptance_receipt=True"):
            fixture.assert_not_accepted(True)

    def test_invalid_outcome_raises(self) -> None:
        with pytest.raises(ValueError, match="SUCCESS"):
            FalseDoneFixture(
                source_decl=FalseDoneFixture.create_default().source_decl,
                spec=FalseDoneFixture.create_default().spec,
                outcome=CandidateOutcome.BLOCKED,
            )


# ---------------------------------------------------------------------------
# ReviewExecutableFixture — REVIEW rejected as executable
# ---------------------------------------------------------------------------


class TestReviewExecutableFixture:
    """ReviewExecutableFixture verifies REVIEW rejection."""

    def test_create_default(self) -> None:
        fixture = ReviewExecutableFixture.create_default()
        assert fixture.source_decl.kind == SubjectKind.HUMAN_BOUNDARY

    def test_assert_rejected_as_executable(self) -> None:
        """HUMAN_BOUNDARY subject is rejected as executable."""
        fixture = ReviewExecutableFixture.create_default()
        fixture.assert_rejected_as_executable()

    def test_non_human_boundary_raises(self) -> None:
        """Non-HUMAN_BOUNDARY kind raises AssertionError."""
        source = SourceDeclaration(
            source_id="fixture:bad-review",
            kind=SubjectKind.STEP,
            canonical_name="bad_review",
        )
        from arnold.workflow.completion.spec import make_completion_spec
        spec = make_completion_spec(
            obligation_id="fixture:bad-review:obl",
            subject_kind=SubjectKind.STEP,
            canonical_name="bad_review",
        )
        fixture = ReviewExecutableFixture(source_decl=source, spec=spec)
        with pytest.raises(AssertionError, match="HUMAN_BOUNDARY"):
            fixture.assert_rejected_as_executable()


# ---------------------------------------------------------------------------
# UnrelatedEvidencePreservationFixture — evidence preservation
# ---------------------------------------------------------------------------


class TestUnrelatedEvidencePreservationFixture:
    """UnrelatedEvidencePreservationFixture verifies evidence preservation."""

    def test_create_default(self) -> None:
        fixture = UnrelatedEvidencePreservationFixture.create_default()
        assert len(fixture.unrelated_evidence_ids) == 2

    def test_assert_preserved_all_present(self) -> None:
        fixture = UnrelatedEvidencePreservationFixture.create_default()
        fixture.assert_preserved(fixture.unrelated_evidence_ids)

    def test_assert_preserved_missing_evidence(self) -> None:
        fixture = UnrelatedEvidencePreservationFixture.create_default()
        with pytest.raises(AssertionError, match="not preserved"):
            fixture.assert_preserved(())

    def test_assert_preserved_partial_missing(self) -> None:
        fixture = UnrelatedEvidencePreservationFixture.create_default()
        all_ids = fixture.unrelated_evidence_ids
        with pytest.raises(AssertionError, match="not preserved"):
            fixture.assert_preserved((all_ids[0],))


# ---------------------------------------------------------------------------
# Corrupted-shadow precondition assertion
# ---------------------------------------------------------------------------


class TestCorruptedShadowPrecondition:
    """corrupted_shadow_precondition fails corrupted, passes real."""

    @pytest.fixture
    def valid_inventory(self) -> tuple[SubjectDeclaration, ...]:
        source = SourceDeclaration(
            source_id="valid-step-001",
            kind=SubjectKind.STEP,
            canonical_name="valid_step",
        )
        decl = SubjectDeclaration(
            source=source,
            subject_kind=SubjectKind.STEP,
            subject_instance_id="valid-inst-1",
            declaration_id="valid-decl-1",
        )
        return (decl,)

    @pytest.fixture
    def corrupted_inventory(self) -> tuple[SubjectDeclaration, ...]:
        """Corrupted by passing a plain string instead of SubjectDeclaration."""
        return ("not-a-subject-declaration",)  # type: ignore[assignment]

    def test_corrupted_fails_valid_passes(
        self, valid_inventory, corrupted_inventory,
    ) -> None:
        """Corrupted input raises, valid input passes afterward."""
        corrupted_shadow_precondition(
            evaluate_fn=evaluate_shadow,
            valid_inventory=valid_inventory,
            corrupted_inventory=corrupted_inventory,
        )

    def test_both_valid_raises(self, valid_inventory) -> None:
        """Two valid inventories causes the assertion to raise (corrupted didn't fail)."""
        with pytest.raises(AssertionError, match="did not raise"):
            corrupted_shadow_precondition(
                evaluate_fn=evaluate_shadow,
                valid_inventory=valid_inventory,
                corrupted_inventory=valid_inventory,
            )

    def test_corrupted_raises_on_second(self) -> None:
        """If valid input fails after corrupted succeeds, assertion raises."""
        empty: tuple[SubjectDeclaration, ...] = ()

        def failing_eval(  # type: ignore[explicit-any]
            inventory: tuple[SubjectDeclaration, ...],
        ) -> None:
            if len(inventory) == 0:
                raise ValueError("empty inventory")
            raise TypeError("unexpected input")

        with pytest.raises(AssertionError, match="raised"):
            corrupted_shadow_precondition(
                evaluate_fn=failing_eval,
                valid_inventory=empty,
                corrupted_inventory=("bad",),  # type: ignore[assignment]
            )

    def test_corrupted_missing_fields_raises(self) -> None:
        """SubjectDeclaration with missing required fields raises during construction."""
        with pytest.raises(ValueError):
            SourceDeclaration(
                source_id="",
                kind=SubjectKind.STEP,
                canonical_name="",
            )
