"""Failure-category policy for execute-stage tier escalation.

classify_failure maps an execute PhaseResult's exit information to a
FailureCategory and the failing task IDs.  Pure function; no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from arnold.pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation

from arnold.pipelines.megaplan.auto import DEFAULT_MAX_BLOCKED_RETRIES

_DRIFT_KINDS: frozenset[str] = frozenset({"scope_drift", "unrelated_files", "out_of_scope"})
_DRIFT_TOKENS: tuple[str, ...] = ("scope drift", "unrelated files", "out of scope")

_EK_SUCCESS = "success"
_EK_BLOCKED_BY_QUALITY = "blocked_by_quality"
_EK_BLOCKED_BY_PREREQ = "blocked_by_prereq"
_EK_TIMEOUT = "timeout"
_EK_CONTEXT_EXHAUSTED = "context_exhausted"
_EK_INTERNAL_ERROR = "internal_error"
_EK_EXTERNAL_ERROR = "external_error"


class FailureCategory(StrEnum):
    blocked_by_prereq = auto()
    blocked_by_quality_drift = auto()
    blocked_by_quality_semantic = auto()
    context_exhausted = auto()
    timeout = auto()
    internal_error = auto()
    external_error = auto()


@dataclass(frozen=True)
class CategoryPolicy:
    """Per-category escalation policy."""

    escalate: bool
    retries_first: int


CATEGORY_POLICY: dict[FailureCategory, CategoryPolicy] = {
    FailureCategory.blocked_by_prereq: CategoryPolicy(escalate=False, retries_first=0),
    FailureCategory.blocked_by_quality_drift: CategoryPolicy(escalate=False, retries_first=0),
    FailureCategory.blocked_by_quality_semantic: CategoryPolicy(
        escalate=True, retries_first=DEFAULT_MAX_BLOCKED_RETRIES
    ),
    FailureCategory.context_exhausted: CategoryPolicy(escalate=True, retries_first=0),
    FailureCategory.timeout: CategoryPolicy(escalate=True, retries_first=0),
    FailureCategory.internal_error: CategoryPolicy(escalate=True, retries_first=1),
    FailureCategory.external_error: CategoryPolicy(escalate=False, retries_first=0),
}


def _is_drift(deviations: Sequence[Deviation]) -> bool:
    """True when deviations indicate a scope-drift false positive.

    Structured Deviation.kind wins; substring fallback on message fires only
    when no deviation's kind is in the drift set.
    """
    for dev in deviations:
        kind = getattr(dev, "kind", None)
        if isinstance(kind, str) and kind in _DRIFT_KINDS:
            return True
    # No structured drift kind matched — try message-token fallback
    for dev in deviations:
        msg = (getattr(dev, "message", "") or "").lower()
        if any(token in msg for token in _DRIFT_TOKENS):
            return True
    return False


def classify_failure(
    exit_kind: str | None,
    deviations: Sequence[Deviation],
    blocked_tasks: Sequence[BlockedTask],
) -> tuple[FailureCategory | None, list[str]]:
    """Classify an execute failure and return (category, failing_task_ids).

    Returns (None, []) for success, absent exit_kind, or unrecognised values.
    Categories without per-task signal (context_exhausted, timeout,
    internal_error, external_error) return failing_task_ids=[].
    """
    if not exit_kind or exit_kind == _EK_SUCCESS:
        return None, []

    if exit_kind == _EK_BLOCKED_BY_PREREQ:
        ids = [tid for bt in blocked_tasks if (tid := getattr(bt, "task_id", None))]
        return FailureCategory.blocked_by_prereq, ids

    if exit_kind == _EK_BLOCKED_BY_QUALITY:
        if _is_drift(deviations):
            return FailureCategory.blocked_by_quality_drift, []
        ids = [tid for bt in blocked_tasks if (tid := getattr(bt, "task_id", None))]
        return FailureCategory.blocked_by_quality_semantic, ids

    if exit_kind == _EK_CONTEXT_EXHAUSTED:
        return FailureCategory.context_exhausted, []

    if exit_kind == _EK_TIMEOUT:
        return FailureCategory.timeout, []

    if exit_kind == _EK_INTERNAL_ERROR:
        return FailureCategory.internal_error, []

    if exit_kind == _EK_EXTERNAL_ERROR:
        return FailureCategory.external_error, []

    return None, []
