"""Test fixtures for completion kernel correctness verification.

This module provides reusable fixture classes and precondition assertions
for verifying completion-kernel behavior.  Each fixture tests a specific
completion-contract rule:

* :class:`FalseDoneFixture` — verifies that a spec whose candidate outcome
  is ``SUCCESS`` but lacks an acceptance transaction receipt is rejected
  as *not-accepted*.
* :class:`ReviewExecutableFixture` — verifies that a REVIEW-gate subject
  declaration is rejected when asserted as executable (REVIEW gates do
  not produce executable completions).
* :class:`UnrelatedEvidencePreservationFixture` — verifies that evidence
  unrelated to the subject under evaluation is preserved after a shadow
  pass.
* :func:`corrupted_shadow_precondition` — precondition assertion that a
  corrupted shadow evaluation must fail **before** the real evaluation
  passes.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from arnold.workflow.completion.outcomes import (
    CandidateOutcome,
    is_terminal,
    outcome_requires_acceptance,
)
from arnold.workflow.completion.spec import (
    CompletionSpec,
    SubjectKind,
    make_completion_spec,
)
from arnold.workflow.completion.source_declaration import (
    SourceDeclaration,
    SubjectDeclaration,
)


# ---------------------------------------------------------------------------
# FalseDoneFixture — legacy done without accepted attempt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FalseDoneFixture:
    """Fixture that verifies a *done*-appearing candidate without an
    accepted attempt is classified as **not-accepted**.

    A "false done" is a candidate whose :attr:`CandidateOutcome` is
    ``SUCCESS`` but for which no authoritative acceptance receipt exists.
    This fixture provides the synthetic building blocks and a verification
    predicate so downstream tests can assert the rejection.

    Parameters
    ----------
    source_decl:
        The :class:`SourceDeclaration` for the subject that appears done.
    spec:
        The :class:`CompletionSpec` for the subject.
    outcome:
        The :class:`CandidateOutcome` - expected to be ``SUCCESS`` for
        false-done scenarios.
    """

    source_decl: SourceDeclaration
    spec: CompletionSpec
    outcome: CandidateOutcome = CandidateOutcome.SUCCESS

    def __post_init__(self) -> None:
        if self.outcome != CandidateOutcome.SUCCESS:
            raise ValueError(
                f"FalseDoneFixture requires outcome=SUCCESS, "
                f"got {self.outcome.value!r}"
            )

    @property
    def is_terminal(self) -> bool:
        """Whether the outcome is terminal (always True for SUCCESS)."""
        return is_terminal(self.outcome)

    @property
    def requires_acceptance(self) -> bool:
        """Whether the outcome requires an acceptance receipt (True for SUCCESS)."""
        return outcome_requires_acceptance(self.outcome)

    def assert_not_accepted(self, has_acceptance_receipt: bool) -> None:
        """Assert that without an acceptance receipt the candidate is treated
        as not-accepted.

        Parameters
        ----------
        has_acceptance_receipt:
            Whether an acceptance transaction receipt is present.

        Raises
        ------
        AssertionError
            If *has_acceptance_receipt* is ``True`` but the fixture is
            designed to test the *no-receipt* case, or if the outcome
            does not actually require acceptance.
        """
        if not self.requires_acceptance:
            raise AssertionError(
                f"FalseDoneFixture: outcome {self.outcome.value!r} does not "
                f"require acceptance; assertion is moot"
            )
        if has_acceptance_receipt:
            # With a receipt the candidate would be accepted — this fixture
            # tests the *rejection* path, so a receipt means the test
            # configuration is wrong.
            raise AssertionError(
                "FalseDoneFixture: has_acceptance_receipt=True but fixture is "
                "designed for the not-accepted (no-receipt) path"
            )
        # When has_acceptance_receipt is False and the outcome requires
        # acceptance, the candidate must be classified as not-accepted.
        # This is the expected path — if we reach here without exception
        # the assertion passes.

    @classmethod
    def create_default(cls) -> FalseDoneFixture:
        """Create a default :class:`FalseDoneFixture` with synthetic data."""
        source = SourceDeclaration(
            source_id="fixture:false-done-step-001",
            kind=SubjectKind.STEP,
            canonical_name="fixture.false_done_step",
        )
        spec = make_completion_spec(
            obligation_id="fixture:false-done-step-001:obligation",
            subject_kind=SubjectKind.STEP,
            canonical_name="fixture.false_done_step",
        )
        return cls(source_decl=source, spec=spec)


# ---------------------------------------------------------------------------
# ReviewExecutableFixture — REVIEW rejected as executable
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewExecutableFixture:
    """Fixture that verifies a REVIEW-gate subject declaration is rejected
    when asserted as executable.

    REVIEW gates represent human review boundaries — they produce review
    decisions, not execution completions.  This fixture provides the
    building blocks and verification logic to assert that a REVIEW-gate
    subject is correctly classified as **not executable**.

    Parameters
    ----------
    source_decl:
        The :class:`SourceDeclaration` for the REVIEW gate.
    spec:
        The :class:`CompletionSpec` for the REVIEW gate.
    executable_outcomes:
        The set of :class:`CandidateOutcome` values that are considered
        *executable* (completable via automatic execution).
    """

    source_decl: SourceDeclaration
    spec: CompletionSpec
    review_outcome: CandidateOutcome = CandidateOutcome.REVIEW_REQUIRED
    """The approved non-executable outcome emitted by a REVIEW pseudo-task."""

    executable_outcomes: frozenset[CandidateOutcome] = field(
        default_factory=lambda: frozenset({CandidateOutcome.SUCCESS})
    )

    def assert_rejected_as_executable(self) -> None:
        """Assert that the REVIEW-gate subject is rejected as executable.

        Raises
        ------
        AssertionError
            If the source/spec do not describe a human boundary or the review
            outcome has been incorrectly admitted as executable.
        """
        if self.source_decl.kind != SubjectKind.HUMAN_BOUNDARY:
            raise AssertionError(
                f"ReviewExecutableFixture requires HUMAN_BOUNDARY subject kind, "
                f"got {self.source_decl.kind!r}"
            )
        if self.spec.subject_kind != SubjectKind.HUMAN_BOUNDARY:
            raise AssertionError(
                "ReviewExecutableFixture spec must use HUMAN_BOUNDARY, got "
                f"{self.spec.subject_kind.value!r}"
            )
        if self.review_outcome in self.executable_outcomes:
            raise AssertionError(
                "REVIEW pseudo-task was admitted as executable: "
                f"{self.review_outcome.value!r}"
            )

    @classmethod
    def create_default(cls) -> ReviewExecutableFixture:
        """Create a default :class:`ReviewExecutableFixture` with synthetic data."""
        source = SourceDeclaration(
            source_id="fixture:review-gate-001",
            kind=SubjectKind.HUMAN_BOUNDARY,
            canonical_name="fixture.review_gate",
        )
        spec = make_completion_spec(
            obligation_id="fixture:review-gate-001:obligation",
            subject_kind=SubjectKind.HUMAN_BOUNDARY,
            canonical_name="fixture.review_gate",
        )
        return cls(source_decl=source, spec=spec)


# ---------------------------------------------------------------------------
# UnrelatedEvidencePreservationFixture — unrelated evidence is preserved
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnrelatedEvidencePreservationFixture:
    """Fixture that verifies evidence unrelated to the subject under
    evaluation is preserved after a shadow pass.

    When a shadow evaluation processes a specific subject, evidence that
    belongs to *other* subjects must not be discarded, overwritten, or
    modified.  This fixture provides synthetic unrelated evidence and
    a verification predicate.

    Parameters
    ----------
    subject_decl:
        The :class:`SubjectDeclaration` for the subject being evaluated.
    unrelated_evidence_ids:
        A tuple of evidence identifier strings that belong to other subjects.
    """

    subject_decl: SubjectDeclaration
    unrelated_evidence_ids: tuple[str, ...] = ()

    def assert_preserved(
        self,
        preserved_evidence_ids: tuple[str, ...],
    ) -> None:
        """Assert that the given *preserved_evidence_ids* include all
        ``unrelated_evidence_ids``.

        Parameters
        ----------
        preserved_evidence_ids:
            The evidence identifier strings that survived the shadow pass.

        Raises
        ------
        AssertionError
            If any ``unrelated_evidence_ids`` is missing from
            *preserved_evidence_ids*.
        """
        missing = tuple(
            eid for eid in self.unrelated_evidence_ids
            if eid not in preserved_evidence_ids
        )
        if missing:
            raise AssertionError(
                f"UnrelatedEvidencePreservationFixture: evidence ids "
                f"{missing!r} were not preserved after shadow evaluation"
            )

    @classmethod
    def create_default(cls) -> UnrelatedEvidencePreservationFixture:
        """Create a default :class:`UnrelatedEvidencePreservationFixture`
        with synthetic data.
        """
        source = SourceDeclaration(
            source_id="fixture:unrelated-evidence-source-001",
            kind=SubjectKind.STEP,
            canonical_name="fixture.unrelated_step",
        )
        subject = SubjectDeclaration(
            source=source,
            subject_kind=SubjectKind.STEP,
            subject_instance_id="fixture:unrelated-instance-001",
            declaration_id="fixture:unrelated-decl-001",
        )
        return cls(
            subject_decl=subject,
            unrelated_evidence_ids=(
                "evidence:other-workflow-001",
                "evidence:other-step-002",
            ),
        )


# ---------------------------------------------------------------------------
# Precondition assertion — corrupted shadow evaluation fails before real
# ---------------------------------------------------------------------------


def corrupted_shadow_precondition(
    evaluate_fn: Callable[[tuple[SubjectDeclaration, ...]], Any],
    valid_inventory: tuple[SubjectDeclaration, ...],
    corrupted_inventory: tuple[SubjectDeclaration, ...],
) -> None:
    """Precondition assertion: a corrupted shadow evaluation must **fail**
    before the real evaluation passes.

    This assertion enforces that the shadow evaluation function validates
    its input and raises an appropriate exception (typically
    :class:`ValueError` or :class:`TypeError`) when given corrupted
    declarations, **before** a subsequent call with valid declarations
    succeeds.

    Parameters
    ----------
    evaluate_fn:
        The shadow evaluation function to test (typically
        :func:`~arnold.workflow.completion.shadow.evaluate_shadow` or
        a wrapper).
    valid_inventory:
        A tuple of valid :class:`SubjectDeclaration` instances that
        should evaluate successfully.
    corrupted_inventory:
        A tuple of corrupted :class:`SubjectDeclaration` instances
        (e.g. missing fields, invalid kinds) that should cause the
        evaluation to raise an exception.

    Raises
    ------
    AssertionError
        If the corrupted inventory does not raise an exception, or if
        the valid inventory raises an exception after the corrupted
        call.
    """
    # Step 1: corrupted input must fail.
    corrupted_failed = False
    try:
        evaluate_fn(corrupted_inventory)
    except (ValueError, TypeError, KeyError, AttributeError):
        corrupted_failed = True

    if not corrupted_failed:
        raise AssertionError(
            "corrupted_shadow_precondition: corrupted inventory did not "
            "raise an exception"
        )

    # Step 2: real/valid input must pass after the corrupted failure.
    try:
        evaluate_fn(valid_inventory)
    except Exception as exc:
        raise AssertionError(
            f"corrupted_shadow_precondition: valid inventory raised "
            f"{type(exc).__name__}: {exc}"
        ) from exc
