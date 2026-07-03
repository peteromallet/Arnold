"""Meta-repair policy guards: recursion prevention and commit gating.

These guards enforce two key safety invariants:

1. **Recursion prevention** — Meta-repair MUST NOT recurse.  When a
   meta-repair context already exists for a session the system escalates
   to a durable human escalation (``NEEDS_HUMAN``) instead of launching
   another meta-repair attempt.

2. **Commit/push gating** — Commit and push paths through meta-repair
   honor ``META_REPAIR_COMMIT_ENABLED``.  The gate defaults on for
   autonomous cloud repair, but remains a separate explicit opt-out from
   ``META_REPAIR_ENABLED`` so operators can disable persistence without
   disabling diagnosis.

These guards are intentionally separate from the core ``meta_repair``
module so they can be tested in isolation and invoked at every layer
that could trigger a recursive or destructive action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from arnold_pipelines.megaplan.cloud.feature_flags import (
    meta_repair_commit_enabled,
)
from arnold_pipelines.megaplan.cloud.repair_contract import (
    NEEDS_HUMAN,
    load_json,
)


# ---------------------------------------------------------------------------
# Recursion guard
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecursionCheckResult:
    """Result of a meta-repair recursion safety check.

    When *recursing* is ``True`` the system MUST NOT launch another
    meta-repair attempt for *session*.  Instead it should produce a
    durable human escalation (``NEEDS_HUMAN``) recording the existing
    meta-repair record IDs in the escalation evidence.
    """

    session: str
    recursing: bool
    existing_meta_repair_ids: tuple[str, ...] = field(default_factory=tuple)
    recommendation: str = ""

    @property
    def should_escalate(self) -> bool:
        """``True`` when the caller should escalate to human instead of recursing."""
        return self.recursing


def check_meta_repair_recursion(
    session: str,
    *,
    repair_data_dir: str | Path,
    max_meta_repair_attempts: int = 1,
) -> RecursionCheckResult:
    """Check whether meta-repair would recurse for *session*.

    Scans ``repair-data/meta/`` for existing meta-repair records that
    belong to *session*.  When the number of existing records is *>=*
    *max_meta_repair_attempts* the result flags recursion and recommends
    escalation to ``NEEDS_HUMAN``.

    Args:
        session: The repair session identifier.
        repair_data_dir: Root of the repair-data tree.
        max_meta_repair_attempts: Maximum number of meta-repair attempts
            allowed before escalation (default ``1`` — no recursion at all).

    Returns:
        A :class:`RecursionCheckResult` with the verdict.
    """
    repair_root = Path(repair_data_dir)
    meta_dir = repair_root / "meta"

    if not meta_dir.is_dir():
        return RecursionCheckResult(
            session=session,
            recursing=False,
            recommendation="no prior meta-repair records; safe to proceed",
        )

    # Collect meta-repair record IDs for this session
    matching_ids: list[str] = []
    for record_file in sorted(meta_dir.glob("*.json")):
        try:
            data = load_json(record_file, default={})
            if isinstance(data, dict) and data.get("session") == session:
                record_id = record_file.stem
                matching_ids.append(record_id)
        except Exception:
            # Corrupt/unreadable file — still counts as evidence
            matching_ids.append(record_file.stem)

    recursing = len(matching_ids) >= max_meta_repair_attempts

    if recursing:
        recommendation = (
            f"Meta-repair recursion detected for session {session!r}: "
            f"found {len(matching_ids)} existing meta-repair record(s) "
            f"({', '.join(matching_ids)}), threshold={max_meta_repair_attempts}. "
            f"Escalate to {NEEDS_HUMAN!r} instead of launching another meta-repair."
        )
    else:
        recommendation = (
            f"Found {len(matching_ids)} existing meta-repair record(s) "
            f"for session {session!r}, below threshold {max_meta_repair_attempts}; "
            f"safe to proceed."
        )

    return RecursionCheckResult(
        session=session,
        recursing=recursing,
        existing_meta_repair_ids=tuple(matching_ids),
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Commit/push gating
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitGateResult:
    """Result of checking whether meta-repair may commit or push changes."""

    allowed: bool
    reason: str
    flag_name: str = "ARNOLD_META_REPAIR_COMMIT_ENABLED"


def can_commit_changes(
    *,
    session: str = "",
) -> CommitGateResult:
    """Check whether meta-repair is permitted to commit changes.

    Returns a :class:`CommitGateResult` with ``allowed=False`` when
    ``META_REPAIR_COMMIT_ENABLED`` is explicitly off.  Even when meta-repair
    itself is enabled, commits honor this separate opt-out gate.

    Args:
        session: Optional session for context (included in the reason string).
    """
    enabled = meta_repair_commit_enabled()

    if enabled:
        reason = "META_REPAIR_COMMIT_ENABLED is on; commits are permitted"
        if session:
            reason += f" (session={session})"
    else:
        reason = (
            "META_REPAIR_COMMIT_ENABLED is off; "
            "commits are not permitted"
        )
        if session:
            reason += f" (session={session})"

    return CommitGateResult(
        allowed=enabled,
        reason=reason,
    )


def can_push_changes(
    *,
    session: str = "",
) -> CommitGateResult:
    """Check whether meta-repair is permitted to push changes.

    Uses the same gate as :func:`can_commit_changes` — push is a strict
    superset of commit and requires ``META_REPAIR_COMMIT_ENABLED``.

    Args:
        session: Optional session for context (included in the reason string).
    """
    result = can_commit_changes(session=session)

    if result.allowed:
        return CommitGateResult(
            allowed=True,
            reason=(
                "META_REPAIR_COMMIT_ENABLED is on; "
                "push is permitted (same gate as commit)"
                + (f" (session={session})" if session else "")
            ),
        )
    else:
        return CommitGateResult(
            allowed=False,
            reason=(
                "META_REPAIR_COMMIT_ENABLED is off; "
                "push is not permitted (same gate as commit)"
                + (f" (session={session})" if session else "")
            ),
        )


__all__ = [
    "CommitGateResult",
    "RecursionCheckResult",
    "can_commit_changes",
    "can_push_changes",
    "check_meta_repair_recursion",
]
