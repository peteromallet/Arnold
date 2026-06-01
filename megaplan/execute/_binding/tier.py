"""Tier binding: complexity scale, rubric reference, and batch-tier selection.

This module is the **only** call site that owns the 1..5 complexity scale.
All other modules treat tier ordinals as opaque integers.
"""

from __future__ import annotations

from typing import Any

from megaplan._core.io import compute_batch_complexity

# ---------------------------------------------------------------------------
# Complexity scale (1..5) and rubric reference
# ---------------------------------------------------------------------------

COMPLEXITY_SCALE = frozenset(range(1, 6))  # 1..5

COMPLEXITY_RUBRIC_REFERENCE = (
    "Adjudicate complexity against the rubric: "
    "1=trivial (single-line change), "
    "2=simple (localized edit in one file), "
    "3=moderate (multi-file with contract concerns), "
    "4=complex (state-machine or cross-cutting change), "
    "5=extreme (architectural or infrastructure change). "
    "Do not omit or guess — every score must be argued from concrete files/risk."
)


# ---------------------------------------------------------------------------
# Hard-reject helpers (extracted from handlers/finalize.py:264–275)
# ---------------------------------------------------------------------------


def validate_task_complexity(
    task: dict[str, Any],
    tid: str,
) -> str | None:
    """Validate that *task* has a well-formed complexity and justification.

    Returns an error message string if the task fails validation,
    or ``None`` if the task passes (i.e. has a valid 1..5 integer
    ``complexity`` and a non-empty ``complexity_justification``).

    The caller is responsible for deciding how to act on the error
    (e.g. calling ``_reject`` inside ``_validate_finalize_payload``).
    """
    complexity = task.get("complexity")
    if not isinstance(complexity, int) or isinstance(complexity, bool) or complexity not in COMPLEXITY_SCALE:
        return (
            f"Finalize task {tid} must include an integer `complexity` score in 1..5 "
            f"(got {complexity!r}). Adjudicate it against the rubric — do not omit or guess."
        )
    justification = task.get("complexity_justification")
    if not isinstance(justification, str) or not justification.strip():
        return (
            f"Finalize task {tid} is missing a non-empty `complexity_justification`. "
            "Every complexity score must be argued from the task's concrete files/risk."
        )
    return None


# ---------------------------------------------------------------------------
# Batch tier selection
# ---------------------------------------------------------------------------


def select_batch_tier(
    finalize_data: dict[str, Any],
    batch_task_ids: list[str],
) -> int:
    """Return the tier ordinal for a batch of task IDs.

    Wraps ``compute_batch_complexity`` from ``megaplan._core.io``,
    preserving its fail-safe → highest-tier behaviour for malformed,
    missing, or out-of-range complexity values.
    """
    return compute_batch_complexity(finalize_data, batch_task_ids)
