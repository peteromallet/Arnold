"""Machine-verifiable acceptance criteria checker.

Rejects subjective-only must criteria that cannot be mechanically verified.
Used by dispatch (before planning) and by final conformance generation to
ensure every C01-C20 structural criterion carries machine-checkable
requirements.

A must criterion is **subjective-only** and rejected when:
- Its ``requires`` list is empty, OR
- Every capability in ``requires`` resolves to ``subjective_judgment``
  (either directly or because the capability registry does not contain it).

Negatives (former imported-decision rows) are covered by explicitly rejecting
criteria that were previously accepted with ``subjective_judgment`` alone.
Positives (C01-C20) are covered by accepting criteria whose ``requires``
intersects with known machine-verifiable capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

# ── Capability sets ────────────────────────────────────────────────────────

#: Capabilities that are always machine-verifiable.
MACHINE_CAPABILITIES: frozenset[str] = frozenset(
    {
        "read_files",
        "run_tests",
        "run_shell",
        "parse_diff",
        "read_build_output",
        "run_linter",
        "parse_json",
        "execute_binary",
    }
)

#: Capabilities that require human judgment and are excluded from
#: machine-only verification.
HUMAN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "subjective_judgment",
        "human_review",
        "manual_verification",
        "human_approval",
    }
)


@dataclass
class CriterionCheck:
    """Result of checking a single success criterion."""

    index: int
    criterion_id: str
    priority: str
    requires: tuple[str, ...]
    verdict: str  # "acceptable" | "rejected_subjective" | "rejected_empty_requires"
    reason: str


@dataclass
class CriteriaCheckReport:
    """Aggregated result of checking all success criteria."""

    checks: list[CriterionCheck] = field(default_factory=list)
    accepted_count: int = 0
    rejected_count: int = 0

    @property
    def all_accepted(self) -> bool:
        return self.rejected_count == 0


def _normalize_requires(
    value: object,
    *,
    machine_caps: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """Return a sorted tuple of non-empty capability strings from *value*."""
    if machine_caps is None:
        machine_caps = MACHINE_CAPABILITIES
    if not isinstance(value, (list, tuple)):
        return ()
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return tuple(sorted(set(result)))


def _is_subjective_only(
    requires: tuple[str, ...],
    *,
    machine_caps: frozenset[str] | None = None,
    human_caps: frozenset[str] | None = None,
) -> bool:
    """Return True when *requires* contains no machine-verifiable capabilities.

    Empty ``requires`` is also considered subjective-only.
    """
    if machine_caps is None:
        machine_caps = MACHINE_CAPABILITIES
    if human_caps is None:
        human_caps = HUMAN_CAPABILITIES

    if not requires:
        return True

    # If any capability is a known machine capability, it's not subjective-only.
    if any(cap in machine_caps for cap in requires):
        return False

    # If all capabilities are human-only, it's subjective-only.
    remaining = set(requires) - human_caps
    if not remaining:
        return True

    # Unknown capabilities (not in machine or human sets) are treated as
    # potentially subjective — fail closed.
    return True


def check_criteria(
    criteria: Iterable[Mapping[str, Any]],
    *,
    machine_caps: frozenset[str] | None = None,
    human_caps: frozenset[str] | None = None,
) -> CriteriaCheckReport:
    """Check *criteria* for subjective-only must entries.

    A must criterion is **rejected** when:
    - ``requires`` is missing or empty, OR
    - Every capability in ``requires`` is human-only/subjective (not in the
      machine capability set).

    Returns a :class:`CriteriaCheckReport` with per-criterion verdicts.
    """
    if machine_caps is None:
        machine_caps = MACHINE_CAPABILITIES
    if human_caps is None:
        human_caps = HUMAN_CAPABILITIES

    report = CriteriaCheckReport()
    for idx, criterion in enumerate(criteria):
        if not isinstance(criterion, Mapping):
            continue

        priority = str(criterion.get("priority", "")).strip().lower()
        criterion_id = str(criterion.get("criterion", f"criterion-{idx}")).strip()
        requires = _normalize_requires(criterion.get("requires"), machine_caps=machine_caps)

        # Only must criteria are subject to rejection
        if priority != "must":
            check = CriterionCheck(
                index=idx,
                criterion_id=criterion_id,
                priority=priority,
                requires=requires,
                verdict="acceptable",
                reason=f"Non-must priority '{priority}' is not subject to machine-verifiability gate.",
            )
            report.checks.append(check)
            report.accepted_count += 1
            continue

        # Must criteria: reject if subjective-only
        if _is_subjective_only(requires, machine_caps=machine_caps, human_caps=human_caps):
            if not requires:
                reason = (
                    f"Must criterion '{criterion_id}' has empty requires — "
                    f"no machine-verifiable capabilities declared."
                )
            else:
                reason = (
                    f"Must criterion '{criterion_id}' requires only subjective/human "
                    f"capabilities: {', '.join(sorted(requires))}. "
                    f"Add at least one machine-verifiable capability."
                )
            check = CriterionCheck(
                index=idx,
                criterion_id=criterion_id,
                priority=priority,
                requires=requires,
                verdict="rejected_subjective",
                reason=reason,
            )
            report.checks.append(check)
            report.rejected_count += 1
        else:
            check = CriterionCheck(
                index=idx,
                criterion_id=criterion_id,
                priority=priority,
                requires=requires,
                verdict="acceptable",
                reason=f"Must criterion has machine-verifiable capabilities: {', '.join(sorted(set(requires) & machine_caps))}.",
            )
            report.checks.append(check)
            report.accepted_count += 1

    return report


def must_criteria_are_verifiable(
    criteria: Iterable[Mapping[str, Any]],
    *,
    machine_caps: frozenset[str] | None = None,
    human_caps: frozenset[str] | None = None,
) -> bool:
    """Return True when all must criteria carry machine-verifiable requirements.

    Convenience wrapper around :func:`check_criteria`.
    """
    report = check_criteria(criteria, machine_caps=machine_caps, human_caps=human_caps)
    return report.all_accepted


def reject_subjective_criteria(
    criteria: Iterable[Mapping[str, Any]],
    *,
    machine_caps: frozenset[str] | None = None,
    human_caps: frozenset[str] | None = None,
) -> list[str]:
    """Return a list of rejection reasons for subjective-only must criteria.

    Returns an empty list when all must criteria are mechanically verifiable.
    Usable as a gate before dispatch.
    """
    report = check_criteria(criteria, machine_caps=machine_caps, human_caps=human_caps)
    return [
        check.reason
        for check in report.checks
        if check.verdict.startswith("rejected")
    ]


__all__ = [
    "CriterionCheck",
    "CriteriaCheckReport",
    "MACHINE_CAPABILITIES",
    "HUMAN_CAPABILITIES",
    "check_criteria",
    "must_criteria_are_verifiable",
    "reject_subjective_criteria",
]
