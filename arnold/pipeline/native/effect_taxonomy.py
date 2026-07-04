"""Side-effect operation taxonomy and idempotency-key derivation.

Defines the canonical operation vocabulary for side-effecting native steps
and a stable default derivation for idempotency keys when none is supplied
explicitly via the decorator.
"""

from __future__ import annotations

from typing import Literal, get_args

# ── Operation taxonomy ──────────────────────────────────────────────────

# Canonical operation type literals for side-effecting native steps.
# These are the only values accepted as ``operation`` on a step decorator
# or in the compiled IR.  Extend this set when new side-effect types are
# introduced; do NOT add ad-hoc strings at the call site.

_OPERATION_LITERALS = (
    "file_write",
    "git_branch_create",
    "git_commit",
    "git_worktree_op",
)

Operation = Literal[
    "file_write",
    "git_branch_create",
    "git_commit",
    "git_worktree_op",
]

# ── Effect class taxonomy ───────────────────────────────────────────────

_EFFECT_CLASS_LITERALS = (
    "filesystem_mutation",
    "git_repo_mutation",
    "network_side_effect",
    "external_service_call",
)

EffectClass = Literal[
    "filesystem_mutation",
    "git_repo_mutation",
    "network_side_effect",
    "external_service_call",
]

# ── Validation helpers ──────────────────────────────────────────────────


def is_valid_operation(value: str) -> bool:
    """Return ``True`` if *value* is a recognised operation type."""
    return value in _OPERATION_LITERALS


def is_valid_effect_class(value: str) -> bool:
    """Return ``True`` if *value* is a recognised effect class."""
    return value in _EFFECT_CLASS_LITERALS


# ── Default idempotency-key derivation ──────────────────────────────────


def derive_idempotency_key(
    step_path: str,
    operation: str,
    target: str | None = None,
) -> str:
    """Derive a stable, deterministic idempotency key from step identity.

    The key is constructed from the canonical step path, operation, and
    optional target.  It uses ``/`` as a delimiter and is designed to be
    stable across recompilations, code renames, and replay — **provided**
    the step path is derived from stable machine-identity segments.

    Parameters
    ----------
    step_path:
        Stable machine-identity path for the step (e.g. ``root/validate``).
        This MUST use ``/``-delimited machine-identity segments, not display
        labels.
    operation:
        Canonical operation from the taxonomy (e.g. ``file_write``).
    target:
        Optional stable target identifier (e.g. a relpath, branch name, or
        artifact logical-root id).  When ``None``, the target component is
        omitted from the key.

    Returns
    -------
    str
        A stable idempotency key string suitable for use in the effect
        ledger and checkpoint metadata.
    """
    if target:
        return f"{step_path}:{operation}:{target}"
    return f"{step_path}:{operation}"
