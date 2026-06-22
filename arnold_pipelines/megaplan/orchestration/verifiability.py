"""Verifiability audit — pure-Python capability matching for success criteria."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

from arnold_pipelines.megaplan.runtime.capabilities import ALL_CAPABILITIES, HUMAN_CAPABILITIES


@dataclass
class CriterionAudit:
    criterion_idx: int
    verdict: str  # "machine_verifiable" | "human_only" | "unverifiable_no_worker"
    rationale: str
    missing_caps: list[str] = field(default_factory=list)


def audit_criteria(
    criteria: list[dict[str, Any]],
    worker_caps: dict[str, set[str]],
) -> list[CriterionAudit]:
    """For each criterion, check requires ⊆ union of all worker verifies sets.

    Returns a CriterionAudit per criterion with verdict:
      - machine_verifiable: all required caps covered by at least one worker
      - human_only: all required caps exist in registry but some need human workers
      - unverifiable_no_worker: some required caps not satisfiable by any known worker
    """
    all_worker_caps = set()
    for caps in worker_caps.values():
        all_worker_caps |= caps

    results: list[CriterionAudit] = []
    for idx, criterion in enumerate(criteria):
        requires = set(criterion.get("requires", []))
        if not requires:
            results.append(CriterionAudit(
                criterion_idx=idx,
                verdict="machine_verifiable",
                rationale="No capabilities required (empty requires).",
            ))
            continue

        missing_from_workers = requires - all_worker_caps
        if not missing_from_workers:
            results.append(CriterionAudit(
                criterion_idx=idx,
                verdict="machine_verifiable",
                rationale="All required capabilities covered by configured workers.",
            ))
        elif missing_from_workers <= HUMAN_CAPABILITIES:
            results.append(CriterionAudit(
                criterion_idx=idx,
                verdict="human_only",
                rationale="Some required capabilities need human verification.",
                missing_caps=sorted(missing_from_workers),
            ))
        else:
            truly_unknown = missing_from_workers - HUMAN_CAPABILITIES
            results.append(CriterionAudit(
                criterion_idx=idx,
                verdict="unverifiable_no_worker",
                rationale="Required capabilities not satisfiable by any known worker.",
                missing_caps=sorted(missing_from_workers),
            ))

    return results


def classify_criteria(
    criteria: list[dict[str, Any]],
    worker_caps: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split criteria into (machine_verifiable, human_deferred).

    machine_verifiable includes criteria with verdict machine_verifiable.
    human_deferred includes human_only and unverifiable_no_worker.
    """
    audits = audit_criteria(criteria, worker_caps)
    machine: list[dict[str, Any]] = []
    human: list[dict[str, Any]] = []
    for audit, criterion in zip(audits, criteria):
        if audit.verdict == "machine_verifiable":
            machine.append(criterion)
        else:
            human.append(criterion)
    return machine, human


def validate_requires(
    criteria: list[dict[str, Any]],
    registry: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """Check all requires entries are known capability strings.

    Returns list of issue strings. Flags must criteria with empty requires
    as deprecation warnings.
    """
    if registry is None:
        registry = ALL_CAPABILITIES

    issues: list[str] = []
    for idx, criterion in enumerate(criteria):
        requires = criterion.get("requires", [])
        priority = criterion.get("priority", "")

        if priority == "must" and not requires:
            msg = (
                f"Criterion {idx} ({criterion.get('criterion', '?')}): "
                f"must-priority criterion has empty requires — "
                f"add requires to enable automated verification."
            )
            issues.append(msg)
            warnings.warn(msg, DeprecationWarning, stacklevel=2)

        for cap in requires:
            if cap not in registry:
                issues.append(
                    f"Criterion {idx} ({criterion.get('criterion', '?')}): "
                    f"unknown capability '{cap}' in requires."
                )

    return issues
