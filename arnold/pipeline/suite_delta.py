"""Suite delta — nodeid-level diff between baseline and verification.

This module defines the structural :class:`SuiteRunProtocol` that
:func:`compute_delta` requires, the :class:`SuiteDelta` dataclass it
produces, and the pure set-logic :func:`compute_delta` implementation.

All symbols are stdlib+typing only — no Megaplan imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Structural protocol — what compute_delta needs from a suite result
# ---------------------------------------------------------------------------


class SuiteRunProtocol(Protocol):
    """Structural protocol for compute_delta parameters.

    Any type exposing these three attributes is a valid input:

    * ``failures: list[str]`` — nodeids of failing tests.
    * ``collected_ids: list[str]`` — nodeids of all collected tests.
    * ``duration: float`` — wall-clock duration in seconds.

    :class:`~megaplan.orchestration.suite_runner.SuiteRunResult` already
    satisfies this protocol without changes.
    """

    failures: list[str]
    collected_ids: list[str]
    duration: float


# ---------------------------------------------------------------------------
# Suite delta — computed diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SuiteDelta:
    """Computed diff between a baseline and a verification suite run.

    All nodeid sets are tuples of strings.  When *computable* is ``False``
    the nodeid fields are empty and callers MUST treat the delta as
    unavailable (e.g. after a collection-parse failure).
    """

    computable: bool
    newly_failing: tuple[str, ...]
    newly_passing: tuple[str, ...]
    still_red: tuple[str, ...]
    still_green: tuple[str, ...]
    deleted_tests: tuple[str, ...]
    added_tests: tuple[str, ...]
    flakes: tuple[str, ...]
    tests_collected: int
    duration: float
    flake_retry_skipped: bool = False
    flake_retry_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "computable": self.computable,
            "newly_failing": list(self.newly_failing),
            "newly_passing": list(self.newly_passing),
            "still_red": list(self.still_red),
            "still_green": list(self.still_green),
            "deleted_tests": list(self.deleted_tests),
            "added_tests": list(self.added_tests),
            "flakes": list(self.flakes),
            "tests_collected": self.tests_collected,
            "duration": self.duration,
            "flake_retry_skipped": self.flake_retry_skipped,
            "flake_retry_reason": self.flake_retry_reason,
        }


# ---------------------------------------------------------------------------
# compute_delta — pure set-logic diff
# ---------------------------------------------------------------------------


def compute_delta(
    baseline: SuiteRunProtocol,
    verification: SuiteRunProtocol,
) -> SuiteDelta:
    """Compute the nodeid-level diff between *baseline* and *verification*.

    Uses the documented set expressions.  ``newly_passing`` is explicitly
    intersected with ``verification_collected`` so deleted tests can NEVER
    surface as passing.
    """
    baseline_fail: set[str] = set(baseline.failures)
    verification_fail: set[str] = set(verification.failures)
    baseline_collected: set[str] = set(baseline.collected_ids)
    verification_collected: set[str] = set(verification.collected_ids)

    newly_failing = tuple(
        sorted((verification_fail - baseline_fail) & verification_collected)
    )
    newly_passing = tuple(
        sorted((baseline_fail - verification_fail) & verification_collected)
    )
    still_red = tuple(
        sorted(baseline_fail & verification_fail & verification_collected)
    )
    still_green = tuple(
        sorted(
            (baseline_collected & verification_collected)
            - baseline_fail
            - verification_fail
        )
    )
    deleted_tests = tuple(sorted(baseline_collected - verification_collected))
    added_tests = tuple(sorted(verification_collected - baseline_collected))

    return SuiteDelta(
        computable=True,
        newly_failing=newly_failing,
        newly_passing=newly_passing,
        still_red=still_red,
        still_green=still_green,
        deleted_tests=deleted_tests,
        added_tests=added_tests,
        flakes=(),
        tests_collected=len(verification_collected),
        duration=verification.duration,
    )
