"""Arnold conformance suite — importable check models and assertion helpers.

This package provides the pure-data, opinion-free result types and thin
assertion helpers that let consumers verify Arnold public contracts
(adapter protocol, contract schema, routing vocabulary) without importing
or referencing Megaplan policy, phase names, gate labels, or override
vocabularies.

Exports
-------
* ``ConformanceCheckResult`` — outcome of a single conformance check.
* ``ConformanceSuiteResult`` — aggregate outcome of a suite of checks.
* ``assert_conformance`` — thin assertion helper that raises on failure.
* ``assert_suite_compliant`` — thin assertion helper for suite results.

Boundary contract
-----------------

**Zero Megaplan imports.**  No source file under ``arnold/conformance/``
may contain ``import megaplan`` or ``from megaplan``.  This package is
pure Arnold and must be importable in environments where Megaplan is
not installed.

**Neutral naming.**  Arnold owns only runtime-neutral names; Megaplan
supplies defaults, policy interpretation, and argument translation for
its phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConformanceCheckResult:
    """The outcome of a single conformance check.

    Parameters
    ----------
    check_id:
        A unique identifier for the check (e.g. ``"adapter-protocol"``).
    passed:
        Whether the check passed.
    message:
        A human-readable diagnostic message (empty string when passed).
    details:
        Optional structured details (e.g. a list of missing requirements).
    """

    check_id: str
    passed: bool
    message: str = ""
    details: Optional[Any] = None


@dataclass(frozen=True)
class ConformanceSuiteResult:
    """Aggregate outcome of a suite of conformance checks.

    Parameters
    ----------
    suite_id:
        A unique identifier for the suite (e.g. ``"ar1-media-adapter"``).
    checks:
        The ordered list of individual check results.
    """

    suite_id: str
    checks: tuple[ConformanceCheckResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        """True when every check in the suite passed."""
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> tuple[ConformanceCheckResult, ...]:
        """The subset of checks that did not pass."""
        return tuple(c for c in self.checks if not c.passed)

    @property
    def failure_count(self) -> int:
        """Number of failing checks."""
        return len(self.failures)

    @property
    def check_count(self) -> int:
        """Total number of checks in the suite."""
        return len(self.checks)


# ---------------------------------------------------------------------------
# Thin assertion helpers
# ---------------------------------------------------------------------------


def assert_conformance(result: ConformanceCheckResult) -> None:
    """Raise :class:`AssertionError` when *result* failed.

    Uses the ``check_id`` and ``message`` in the error text for
    diagnostic clarity.
    """
    if not result.passed:
        raise AssertionError(
            f"[{result.check_id}] {result.message or 'check failed'}"
        )


def assert_suite_compliant(suite: ConformanceSuiteResult) -> None:
    """Raise :class:`AssertionError` when the *suite* has any failures.

    The error message lists every failing ``check_id`` and its message.
    """
    if not suite.passed:
        failed_lines = [
            f"  [{c.check_id}] {c.message or 'check failed'}"
            for c in suite.failures
        ]
        raise AssertionError(
            f"Conformance suite '{suite.suite_id}' has {suite.failure_count} "
            f"failure(s):\n" + "\n".join(failed_lines)
        )


# Deferred import — suite runner pulls in routing, join, and checks modules
# which are heavier and should not be loaded at package-init time.
def __getattr__(name: str):
    if name == "run_conformance_suite":
        from arnold.conformance.suite import run_conformance_suite as _fn

        return _fn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ConformanceCheckResult",
    "ConformanceSuiteResult",
    "assert_conformance",
    "assert_suite_compliant",
    "run_conformance_suite",
]
