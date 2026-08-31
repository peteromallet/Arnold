"""Candidate outcome classification and validation.

This module defines the :class:`CandidateOutcome` enum — the set of
possible outcomes for a completion candidate — along with helpers for
outcome classification (terminal vs. non-terminal), supersession
laundering validation, and :class:`SubjectKind`-to-outcome crosswalk
coverage.

.. caution::
   This package is **experimental and non-authoritative** — see
   :mod:`arnold.workflow.completion` for the full disclaimer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Mapping

from arnold.workflow.completion.spec import SubjectKind

# ---------------------------------------------------------------------------
# CandidateOutcome — candidate outcome enumeration
# ---------------------------------------------------------------------------


class CandidateOutcome(StrEnum):
    """The set of possible outcomes for a completion candidate.

    Each outcome represents a distinct resolution state for a shadow or
    live completion evaluation.  Terminal outcomes are those that cannot
    transition to another outcome — the candidate is resolved.
    """

    #: The candidate has been successfully completed.
    SUCCESS = "success"
    #: The candidate is blocked by a declared prerequisite or boundary.
    BLOCKED = "blocked"
    #: The candidate was waived (accepted without full proof).
    WAIVED = "waived"
    #: The candidate was superseded by a named exit record.
    SUPERSEDED_BY_NAMED_EXIT = "superseded_by_named_exit"
    #: The candidate is isolated pending an explicit disposition.
    QUARANTINED = "quarantined"
    #: The candidate has not yet met its declared completion conditions.
    INCOMPLETE = "incomplete"
    #: The candidate's evidence is no longer current for its binding.
    STALE_EVIDENCE = "stale_evidence"
    #: The candidate is usable only with a recorded degraded qualification.
    DEGRADED = "degraded"
    #: The candidate must cross a human review boundary.
    REVIEW_REQUIRED = "review_required"
    #: The candidate must be reworked before it can be evaluated again.
    REWORK_REQUIRED = "rework_required"


class PlatformDisposition(StrEnum):
    """Names from the Platform disposition registry, not candidate outcomes.

    These values mirror the disposition *categories* in
    ``docs/arnold/workflow-execution-mode-dispositions.yaml``.  They remain
    a distinct registry: this shadow-only module does not decide Platform
    enforcement actions.
    """

    ALWAYS_HARD = "always_hard"
    AUTOMATIC = "automatic"
    PRODUCTION_ADMISSION_GATE = "production_admission_gate"
    STABLE_PUBLICATION_GATE = "stable_publication_gate"
    AUTHORING_ADVISORY = "authoring_advisory"
    NON_DURABLE_ONLY = "non_durable_only"


# ---------------------------------------------------------------------------
# Terminal classification
# ---------------------------------------------------------------------------


def is_terminal(outcome: CandidateOutcome) -> bool:
    """Return ``True`` if *outcome* is a terminal (final) outcome.

    Terminal outcomes are those after which no further transitions are
    expected:

    * :attr:`CandidateOutcome.SUCCESS`
    * :attr:`CandidateOutcome.BLOCKED`
    * :attr:`CandidateOutcome.WAIVED`
    * :attr:`CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT`
    """
    return outcome in (
        CandidateOutcome.SUCCESS,
        CandidateOutcome.BLOCKED,
        CandidateOutcome.WAIVED,
        CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
        CandidateOutcome.QUARANTINED,
    )


def is_nonterminal(outcome: CandidateOutcome) -> bool:
    """Return ``True`` when *outcome* requires further evaluation or work."""
    return not is_terminal(outcome)


# ---------------------------------------------------------------------------
# Outcome requiring acceptance
# ---------------------------------------------------------------------------


def outcome_requires_acceptance(outcome: CandidateOutcome) -> bool:
    """Return ``True`` if *outcome* requires an acceptance receipt.

    Outcomes that represent successful resolution or an accepted
    supersession require an acceptance receipt to be considered
    authoritative.  Failure and abandonment do not require acceptance.
    """
    return outcome in (
        CandidateOutcome.SUCCESS,
        CandidateOutcome.WAIVED,
        CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT,
    )


# ---------------------------------------------------------------------------
# Supersession laundering validation
# ---------------------------------------------------------------------------

#: Set of supersession transitions that are **rejected** as laundering.
#:
#: Each entry is a ``(from_outcome, to_outcome)`` pair that is considered
#: an invalid laundering attempt — supersessions that claim a later
#: outcome which is inappropriately weaker than the earlier one.
_LAUNDERING_REJECTED_TRANSITIONS: set[tuple[CandidateOutcome, CandidateOutcome]] = {
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.SUCCESS),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.WAIVED),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.BLOCKED),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.QUARANTINED),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.INCOMPLETE),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.STALE_EVIDENCE),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.DEGRADED),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.REVIEW_REQUIRED),
    (CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT, CandidateOutcome.REWORK_REQUIRED),
}


def validate_supersession(
    superseded_outcome: CandidateOutcome,
    superseding_outcome: CandidateOutcome,
    *,
    intervening_bindings: tuple[str, ...] | None = None,
) -> None:
    """Validate that *superseding_outcome* is a valid supersession of *superseded_outcome*.

    This function enforces the supersession laundering rules: certain
    outcome transitions are considered invalid because they would allow
    a weaker outcome to replace a stronger one (e.g. ``SUCCESS → WAIVED``)
    or would resurrect a candidate from a terminal state without the
    proper authority (e.g. ``SUPERSEDED_BY_NAMED_EXIT → SUCCESS``).

    Parameters
    ----------
    superseded_outcome:
        The outcome being superseded.
    superseding_outcome:
        The outcome that is superseding it.

    Raises
    ------
    ValueError
        If the transition is a laundering attempt.
    """
    pair = (superseded_outcome, superseding_outcome)
    if pair in _LAUNDERING_REJECTED_TRANSITIONS:
        raise ValueError(
            f"Supersession laundering rejected: "
            f"{superseded_outcome.value!r} -> {superseding_outcome.value!r} "
            f"is not a valid transition"
        )
    if (
        superseding_outcome == CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT
        and not intervening_bindings
    ):
        raise ValueError(
            "Supersession laundering rejected: named-exit supersession "
            "requires intervening binding hashes"
        )


def is_laundering(
    superseded_outcome: CandidateOutcome,
    superseding_outcome: CandidateOutcome,
    *,
    intervening_bindings: tuple[str, ...] | None = None,
) -> bool:
    """Return ``True`` if the transition is a laundering attempt.

    This is a non-raising predicate equivalent of
    :func:`validate_supersession`.
    """
    pair = (superseded_outcome, superseding_outcome)
    return (
        pair in _LAUNDERING_REJECTED_TRANSITIONS
        or (
            superseding_outcome == CandidateOutcome.SUPERSEDED_BY_NAMED_EXIT
            and not intervening_bindings
        )
    )


# ---------------------------------------------------------------------------
# SubjectKind-to-outcome crosswalk coverage
# ---------------------------------------------------------------------------

#: Crosswalk table mapping every :class:`SubjectKind` to the set of
#: :class:`CandidateOutcome` values that are applicable to that kind.
#:
#: This table documents which outcomes each subject kind may produce,
#: serving as the source-of-truth for outcome-coverage validation in
#: the shadow engine and lint rules.
SUBJECT_KIND_OUTCOME_CROSSWALK: dict[str, list[str]] = {
    kind.name: [outcome.value for outcome in CandidateOutcome]
    for kind in SubjectKind
}


#: Total, intentionally non-authoritative boundary schema.  C2/S2R may fill
#: these sets only through the Platform contract; C1 records every candidate
#: outcome so an omitted mapping is mechanically visible.
OUTCOME_PLATFORM_DISPOSITIONS: Mapping[
    CandidateOutcome, frozenset[PlatformDisposition]
] = {outcome: frozenset() for outcome in CandidateOutcome}
