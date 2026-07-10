"""Megaplan names and policy constraints over generic authority contracts.

The subclasses deliberately retain the generic wire contract.  They add only
Megaplan vocabulary and validation; persistence and reduction remain owned by
``arnold_pipelines.run_authority``.
"""

from __future__ import annotations

from dataclasses import dataclass

from arnold_pipelines.run_authority import (
    CapabilityGrant,
    Claim,
    ContractError,
    Decision,
    SubjectAttempt,
)


TASK_RESULT_CAPABILITY = "megaplan.task.result"
SENSE_CHECK_RESULT_CAPABILITY = "megaplan.sense_check.result"
TASK_COMPLETION_CLAIM = "megaplan.task.completion"
SENSE_CHECK_ACK_CLAIM = "megaplan.sense_check.acknowledgment"


@dataclass(frozen=True)
class DispatchGrant(CapabilityGrant):
    """A capability grant whose scope was dispatched by Megaplan."""

    def __post_init__(self) -> None:
        super().__post_init__()
        allowed = {TASK_RESULT_CAPABILITY, SENSE_CHECK_RESULT_CAPABILITY}
        unknown = set(self.capabilities) - allowed
        if unknown:
            raise ContractError(f"unsupported Megaplan dispatch capabilities: {sorted(unknown)}")

    @property
    def dispatch_id(self) -> str:
        return self.grant_id


@dataclass(frozen=True)
class TaskAttempt(SubjectAttempt):
    """Megaplan task-attempt name over a generic subject attempt."""

    @property
    def task_id(self) -> str:
        return self.subject_id

    @property
    def dispatch_id(self) -> str:
        return self.grant_id


@dataclass(frozen=True)
class TaskClaim(Claim):
    """A task completion claim; it is not an accepted completion itself."""

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.claim_type != TASK_COMPLETION_CLAIM:
            raise ContractError(f"TaskClaim requires claim_type {TASK_COMPLETION_CLAIM!r}")

    @property
    def task_id(self) -> str:
        return self.subject_id


@dataclass(frozen=True)
class TaskValidationDecision(Decision):
    """Megaplan validation of one task claim."""

    @property
    def task_id(self) -> str:
        return self.subject_id


__all__ = [
    "DispatchGrant",
    "SENSE_CHECK_ACK_CLAIM",
    "SENSE_CHECK_RESULT_CAPABILITY",
    "TASK_COMPLETION_CLAIM",
    "TASK_RESULT_CAPABILITY",
    "TaskAttempt",
    "TaskClaim",
    "TaskValidationDecision",
]
