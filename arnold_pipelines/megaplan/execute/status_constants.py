"""Shared status constants for execute task normalization.

This leaf module imports nothing from the megaplan package, so it cannot
cause circular imports.  Both ``model_seam`` (capture pre-processing) and
``execute/merge`` (merge-time value aliasing) import from here, keeping the
single source of truth for alias normalization.

``TERMINAL_TASK_STATUSES`` is the frozen set of canonical terminal task
statuses.  It includes ``completed`` for backward compatibility with
persisted execution-batch artifacts — removing it would break
deserialization of existing ``execution_batch_*.json`` payloads.

``EXECUTE_TASK_STATUS_ALIASES`` maps every legacy/non-canonical status
string that an executor may emit to its canonical form.  Every alias value
is guaranteed to be a member of ``TERMINAL_TASK_STATUSES`` (the subset
invariant).

``normalize_execute_task_status`` is the single-line normalizer:
``isinstance`` guard, then a direct ``dict.get`` lookup — no intermediate
constants, no branching, no megaplan imports.
"""

from __future__ import annotations

TERMINAL_TASK_STATUSES: frozenset[str] = frozenset(
    {"done", "skipped", "completed", "blocked"}
)

EXECUTE_TASK_STATUS_ALIASES: dict[str, str] = {
    "completed": "done",
    "complete": "done",
    "skip": "skipped",
    "verified": "done",
}


def normalize_execute_task_status(value: object) -> object:
    """Return the canonical status for *value* if it is a known alias.

    Canonical statuses pass through unchanged; unknown strings and
    non-string values (including ``None``) are returned as-is.
    """
    if isinstance(value, str):
        return EXECUTE_TASK_STATUS_ALIASES.get(value, value)
    return value
