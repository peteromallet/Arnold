"""Replayable occurrence-bound checkpoint scheduler (M3 Step 6).

This module computes the *due* checkpoint set for one maintenance occurrence
as a pure, deterministic projection of the persisted event stream.  It never
invents a scheduling lease, never writes a record, and never reacquires or
trusts authority — it only tells the executor *which* canonical checkpoints
are due and *which* inherited M7 lease/epoch/fence coordinates the executor
must re-read before acting.

Canonical windows (locked decision)
-----------------------------------
``immediate``, ``five_minute``, ``one_hour``, and ``next_three_hour`` are the
only schedulable windows, in event-time order (smallest delay first).  Each
window is a *half-open* interval anchored to the durable effect receipt::

    [anchor + delta_k, anchor + delta_{k+1})          (inclusive, exclusive)

with ``next_three_hour`` the unbounded canonical horizon (``close_at=None``).
The legacy ``six_hour`` name is a *read alias* for ``next_three_hour`` (see
:func:`~arnold_pipelines.megaplan.maintenance.events.canonical_checkpoint_window`)
and never schedules a separate six-hour authority window.

Due / catch-up / replay semantics
---------------------------------
A window is *due* once its inclusive lower bound has passed and no persisted
``checkpoint_verification`` action has completed it.  An overdue window
(past its exclusive upper bound) is still returned exactly once as *delayed
catch-up*, in event-time order.  Because the computation reads only persisted
events, restarting with the same inputs returns exactly the same due set
(replay safety) and a completed window is never re-emitted (duplicate
suppression).

Inherited authority
-------------------
Every due item carries the inherited M7 lease id / custody epoch / fencing
token VERBATIM.  The scheduler does not check freshness: carrying the
coordinates is *solely* so the executor must reacquire current authority
before acting — the schedule projection never authorizes an edge by itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointVerificationPayload,
    CheckpointWindowKind,
    OperationalActionKind,
    OperationalEvent,
    SIX_HOUR_ALIAS,
    canonical_checkpoint_window,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    strict_loads,
)

# ---------------------------------------------------------------------------
# Canonical schedule
# ---------------------------------------------------------------------------

#: Canonical checkpoint windows in event-time order (smallest delay first).
#: ``six_hour`` is deliberately absent: it is a read alias for
#: ``next_three_hour`` only and never a separate window.
CANONICAL_CHECKPOINT_ORDER: tuple[CheckpointWindowKind, ...] = (
    CheckpointWindowKind.IMMEDIATE,
    CheckpointWindowKind.FIVE_MINUTE,
    CheckpointWindowKind.ONE_HOUR,
    CheckpointWindowKind.NEXT_THREE_HOUR,
)

#: Nominal delay of each canonical window from the durable effect receipt.
CHECKPOINT_WINDOW_DELTAS: dict[CheckpointWindowKind, timedelta] = {
    CheckpointWindowKind.IMMEDIATE: timedelta(0),
    CheckpointWindowKind.FIVE_MINUTE: timedelta(minutes=5),
    CheckpointWindowKind.ONE_HOUR: timedelta(hours=1),
    CheckpointWindowKind.NEXT_THREE_HOUR: timedelta(hours=3),
}


def _normalize_utc(value: datetime | UtcTime, *, what: str) -> datetime:
    """Normalize *value* to a UTC instant; naive datetimes fail closed."""
    if isinstance(value, UtcTime):
        return value.root
    if not isinstance(value, datetime):
        raise ValueError(f"{what} must be a UtcTime or aware datetime")
    if value.tzinfo is None:
        raise ValueError(
            f"{what} must carry an explicit UTC offset "
            "(naive datetimes are never assumed to be UTC)"
        )
    return value.astimezone(timezone.utc)


def _canonical_window(window: CheckpointWindowKind | str) -> CheckpointWindowKind:
    """Resolve one window input to its canonical kind (alias-aware)."""
    if isinstance(window, CheckpointWindowKind):
        return window
    return canonical_checkpoint_window(window)


def checkpoint_window_bounds(
    anchor_at: datetime | UtcTime,
    window: CheckpointWindowKind | str,
) -> tuple[datetime, datetime | None]:
    """Return the half-open due window ``(open_at, close_at)`` for *window*.

    ``open_at`` is the inclusive lower bound; ``close_at`` is the exclusive
    upper bound (``None`` for the unbounded ``next_three_hour`` horizon).
    *window* is resolved through
    :func:`~arnold_pipelines.megaplan.maintenance.events.canonical_checkpoint_window`,
    so legacy ``six_hour`` naming is a read alias for ``next_three_hour``
    and never a separate window.
    """
    canonical = _canonical_window(window)
    anchor = _normalize_utc(anchor_at, what="anchor_at")
    open_at = anchor + CHECKPOINT_WINDOW_DELTAS[canonical]
    close_at: datetime | None = None
    index = CANONICAL_CHECKPOINT_ORDER.index(canonical)
    if index + 1 < len(CANONICAL_CHECKPOINT_ORDER):
        close_at = anchor + CHECKPOINT_WINDOW_DELTAS[CANONICAL_CHECKPOINT_ORDER[index + 1]]
    return open_at, close_at


# ---------------------------------------------------------------------------
# Persisted completion
# ---------------------------------------------------------------------------


def completed_checkpoint_windows(
    events: Sequence[OperationalEvent | dict[str, Any]],
) -> tuple[CheckpointWindowKind, ...]:
    """Extract the canonical windows verified by persisted actions.

    Every event is strict-decoded (models pass through); only
    ``checkpoint_verification`` actions contribute their canonical window.
    Windows are deduplicated and returned in canonical (event-time) order.
    Any event that is not a strict operational action fails closed with
    ``ValueError`` — completion is never guessed from partial or malformed
    records.
    """
    windows: list[CheckpointWindowKind] = []
    seen: set[CheckpointWindowKind] = set()
    for event in events:
        if isinstance(event, OperationalEvent):
            model = event
        else:
            model = strict_loads(OperationalEvent, event)
        if model.action_kind is not OperationalActionKind.CHECKPOINT_VERIFICATION:
            continue
        payload = model.payload
        if not isinstance(payload, CheckpointVerificationPayload):
            raise ValueError(
                "checkpoint_verification action must carry a "
                "CheckpointVerificationPayload"
            )
        if payload.checkpoint not in seen:
            seen.add(payload.checkpoint)
            windows.append(payload.checkpoint)
    return tuple(
        sorted(windows, key=lambda window: CANONICAL_CHECKPOINT_ORDER.index(window))
    )


# ---------------------------------------------------------------------------
# Due items
# ---------------------------------------------------------------------------


class CheckpointDueItem(BaseModel):
    """One due checkpoint with its half-open window and inherited authority.

    ``open_at``/``close_at`` bound the half-open due window
    (``[open_at, close_at)``); ``close_at`` is ``None`` for the canonical
    ``next_three_hour`` horizon (unbounded).  ``delayed`` is ``True`` when
    the evaluation instant is at or past ``close_at`` (late catch-up).

    The inherited M7 lease id / custody epoch / fencing token are carried
    VERBATIM so the executor must reacquire current authority before acting:
    the schedule projection never authorizes an edge by itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: StrictStr | None = None
    window: CheckpointWindowKind
    open_at: datetime
    close_at: datetime | None = None
    delayed: bool = False
    lease_id: StrictStr | None = None
    custody_epoch: int | None = Field(default=None, ge=1)
    fencing_token: StrictStr | None = None
    anchor_ref: OwnerRef | None = None

    @field_validator("open_at", "close_at")
    @classmethod
    def _validate_window_bounds(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "checkpoint window bounds must carry an explicit UTC offset"
            )
        return value.astimezone(timezone.utc)

    @field_validator("occurrence_id", "lease_id", "fencing_token")
    @classmethod
    def _validate_nonempty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "occurrence_id/lease_id/fencing_token must be non-empty "
                "strings when present"
            )
        return value


def due_checkpoints(
    *,
    anchor_at: datetime | UtcTime,
    now: datetime | UtcTime,
    events: Sequence[OperationalEvent | dict[str, Any]] | None = None,
    completed: Sequence[CheckpointWindowKind | str] | None = None,
    policy: Sequence[CheckpointWindowKind | str] | None = None,
    occurrence_id: str | None = None,
    lease_id: str | None = None,
    custody_epoch: int | None = None,
    fencing_token: str | None = None,
    anchor_ref: OwnerRef | None = None,
) -> tuple[CheckpointDueItem, ...]:
    """Return every due checkpoint in event-time order for one occurrence.

    Windows are half-open intervals ``[anchor + delta_k, anchor + delta_{k+1})``
    anchored to the durable effect receipt time (``anchor_at``), with the
    canonical ``next_three_hour`` horizon unbounded.  A window is *due* once
    its inclusive lower bound has passed and no persisted
    ``checkpoint_verification`` action has completed it; an overdue window
    (past its exclusive upper bound) is still returned exactly once as
    delayed catch-up.  The function is a pure deterministic projection of the
    persisted event stream: replaying the same inputs returns the same due
    set and no scheduling lease is invented.

    ``events`` (persisted actions) and ``completed`` (already-extracted
    windows) are alternative completion sources; supplying both is an error.
    ``completed``/``policy`` entries are resolved through
    :func:`canonical_checkpoint_window`, so ``six_hour`` is a read alias for
    ``next_three_hour`` and never a separate window.

    Each due item carries the inherited M7 lease/epoch/fence coordinates
    VERBATIM — the executor must reacquire current authority before acting;
    the schedule projection never authorizes an edge by itself.
    """
    anchor = _normalize_utc(anchor_at, what="anchor_at")
    instant = _normalize_utc(now, what="now")

    if events is not None and completed is not None:
        raise ValueError("supply either persisted `events` or `completed`, not both")

    if events is not None:
        done = set(completed_checkpoint_windows(events))
    else:
        done = {_canonical_window(window) for window in (completed or ())}

    if policy is None:
        ordered = CANONICAL_CHECKPOINT_ORDER
    else:
        ordered_windows: list[CheckpointWindowKind] = []
        seen: set[CheckpointWindowKind] = set()
        for window in policy:
            canonical = _canonical_window(window)
            if canonical not in seen:
                seen.add(canonical)
                ordered_windows.append(canonical)
        ordered = tuple(
            sorted(ordered_windows, key=lambda w: CANONICAL_CHECKPOINT_ORDER.index(w))
        )

    if occurrence_id is not None and not occurrence_id:
        raise ValueError("occurrence_id must be a non-empty string when present")
    if lease_id is not None and not lease_id:
        raise ValueError("lease_id must be a non-empty string when present")
    if fencing_token is not None and not fencing_token:
        raise ValueError("fencing_token must be a non-empty string when present")
    if custody_epoch is not None and custody_epoch < 1:
        raise ValueError(f"custody_epoch must be >= 1, got {custody_epoch}")

    due: list[CheckpointDueItem] = []
    for window in ordered:
        if window in done:
            continue
        open_at, close_at = checkpoint_window_bounds(anchor, window)
        if instant < open_at:
            continue
        delayed = close_at is not None and instant >= close_at
        due.append(
            CheckpointDueItem(
                occurrence_id=occurrence_id,
                window=window,
                open_at=open_at,
                close_at=close_at,
                delayed=delayed,
                lease_id=lease_id,
                custody_epoch=custody_epoch,
                fencing_token=fencing_token,
                anchor_ref=anchor_ref,
            )
        )
    return tuple(due)


__all__ = [
    "CANONICAL_CHECKPOINT_ORDER",
    "CHECKPOINT_WINDOW_DELTAS",
    "CheckpointDueItem",
    "SIX_HOUR_ALIAS",
    "checkpoint_window_bounds",
    "completed_checkpoint_windows",
    "due_checkpoints",
]
