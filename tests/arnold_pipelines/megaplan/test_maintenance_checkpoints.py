"""Focused Maintenance replayable checkpoint-scheduler tests (M3 Step 6 / T7).

These tests prove the occurrence-bound checkpoint scheduler:

* canonical windows ``immediate`` / ``five_minute`` / ``one_hour`` /
  ``next_three_hour`` in event-time order with half-open due windows anchored
  to the durable effect receipt (inclusive lower bound, exclusive upper
  bound, unbounded canonical horizon);
* legacy ``six_hour`` is a READ alias for ``next_three_hour`` only and never
  a separate scheduled window;
* delayed catch-up returns every overdue checkpoint exactly once, in
  event-time order, as a pure deterministic projection of persisted actions
  (restart replay is byte-stable and a verified window is never re-emitted);
* each due item carries the inherited M7 lease id / custody epoch / fencing
  token verbatim so the executor must reacquire current authority — the
  schedule projection never authorizes an edge by itself (stale epochs are
  never masked by the scheduler).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from arnold_pipelines.megaplan.maintenance.checkpoints import (
    CANONICAL_CHECKPOINT_ORDER,
    CHECKPOINT_WINDOW_DELTAS,
    CheckpointDueItem,
    SIX_HOUR_ALIAS,
    checkpoint_window_bounds,
    completed_checkpoint_windows,
    due_checkpoints,
)
from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointVerificationPayload,
    CheckpointWindowKind,
    OperationalActionKind,
    OperationalEvent,
    RepairRequestPayload,
    canonical_checkpoint_window,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    OwnerRef,
    UtcTime,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ActionTarget,
    LeaseCoordinates,
    OccurrenceCoordinates,
    PolicyVersionCoordinates,
    ProducerPrincipal,
    ProducerRole,
    RunAuthorityCoordinates,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

IMMEDIATE = CheckpointWindowKind.IMMEDIATE
FIVE_MINUTE = CheckpointWindowKind.FIVE_MINUTE
ONE_HOUR = CheckpointWindowKind.ONE_HOUR
NEXT_THREE_HOUR = CheckpointWindowKind.NEXT_THREE_HOUR


def _ts(minutes: float = 0, *, hours: float = 0, seconds: float = 0) -> datetime:
    return T0 + timedelta(minutes=minutes, hours=hours, seconds=seconds)


def _checkpoint_event(
    window: CheckpointWindowKind,
    *,
    event_id: str = "evt-1",
    occurrence_id: str = "occ-1",
) -> OperationalEvent:
    """Build one strict persisted checkpoint-verification action."""
    return OperationalEvent(
        event_id=event_id,
        action_kind=OperationalActionKind.CHECKPOINT_VERIFICATION,
        occurrence=OccurrenceCoordinates(
            occurrence_id=occurrence_id, canonical_digest="a" * 64
        ),
        lease=LeaseCoordinates(lease_id="lease-1", custody_epoch=1),
        run_authority=RunAuthorityCoordinates(run_id="run-1"),
        policy=PolicyVersionCoordinates(policy_version="policy-1"),
        target=ActionTarget(target="chain:session"),
        producer=ProducerPrincipal(
            principal="verifier-1", role=ProducerRole.VERIFIER
        ),
        observed_at=UtcTime(T0),
        payload=CheckpointVerificationPayload(checkpoint=window),
    )


def _repair_request_event(event_id: str = "req-1") -> OperationalEvent:
    """Build one strict non-checkpoint persisted action (ignored by the join)."""
    return OperationalEvent(
        event_id=event_id,
        action_kind=OperationalActionKind.REPAIR_REQUEST,
        occurrence=OccurrenceCoordinates(
            occurrence_id="occ-1", canonical_digest="a" * 64
        ),
        lease=LeaseCoordinates(lease_id="lease-1", custody_epoch=1),
        run_authority=RunAuthorityCoordinates(run_id="run-1"),
        policy=PolicyVersionCoordinates(policy_version="policy-1"),
        target=ActionTarget(target="chain:session"),
        producer=ProducerPrincipal(
            principal="producer-1", role=ProducerRole.REPAIR_PRODUCER
        ),
        observed_at=UtcTime(T0),
        payload=RepairRequestPayload(request_id="req-1"),
    )


# ---------------------------------------------------------------------------
# Canonical schedule vocabulary
# ---------------------------------------------------------------------------


def test_canonical_windows_are_four_in_event_time_order() -> None:
    assert CANONICAL_CHECKPOINT_ORDER == (
        IMMEDIATE,
        FIVE_MINUTE,
        ONE_HOUR,
        NEXT_THREE_HOUR,
    )
    assert SIX_HOUR_ALIAS == "six_hour"
    # Deltas anchored to the durable effect receipt.
    assert CHECKPOINT_WINDOW_DELTAS[IMMEDIATE] == timedelta(0)
    assert CHECKPOINT_WINDOW_DELTAS[FIVE_MINUTE] == timedelta(minutes=5)
    assert CHECKPOINT_WINDOW_DELTAS[ONE_HOUR] == timedelta(hours=1)
    assert CHECKPOINT_WINDOW_DELTAS[NEXT_THREE_HOUR] == timedelta(hours=3)


def test_checkpoint_window_bounds_are_half_open() -> None:
    open_at, close_at = checkpoint_window_bounds(T0, IMMEDIATE)
    assert open_at == T0
    assert close_at == _ts(minutes=5)  # [anchor, anchor+5m)

    open_at, close_at = checkpoint_window_bounds(T0, FIVE_MINUTE)
    assert open_at == _ts(minutes=5)
    assert close_at == _ts(hours=1)  # [anchor+5m, anchor+1h)

    open_at, close_at = checkpoint_window_bounds(T0, ONE_HOUR)
    assert open_at == _ts(hours=1)
    assert close_at == _ts(hours=3)  # [anchor+1h, anchor+3h)

    # The canonical horizon is unbounded (no later window).
    open_at, close_at = checkpoint_window_bounds(T0, NEXT_THREE_HOUR)
    assert open_at == _ts(hours=3)
    assert close_at is None


def test_six_hour_maps_to_next_three_hour_bounds() -> None:
    assert canonical_checkpoint_window("six_hour") is NEXT_THREE_HOUR
    assert checkpoint_window_bounds(T0, "six_hour") == checkpoint_window_bounds(
        T0, NEXT_THREE_HOUR
    )


# ---------------------------------------------------------------------------
# Half-open exact boundaries
# ---------------------------------------------------------------------------


def test_due_set_at_exact_half_open_boundaries() -> None:
    # Just inside the immediate window.
    due = due_checkpoints(anchor_at=T0, now=_ts(minutes=4, seconds=59))
    assert [item.window for item in due] == [IMMEDIATE]
    assert due[0].delayed is False

    # Exactly at the immediate close: immediate is overdue catch-up and
    # five_minute opens (half-open: [anchor+5m, ...) includes 5m exactly).
    due = due_checkpoints(anchor_at=T0, now=_ts(minutes=5))
    assert [item.window for item in due] == [IMMEDIATE, FIVE_MINUTE]
    assert [item.delayed for item in due] == [True, False]

    # Exactly at the five_minute close / one_hour open.
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=1))
    assert [item.window for item in due] == [IMMEDIATE, FIVE_MINUTE, ONE_HOUR]
    assert [item.delayed for item in due] == [True, True, False]

    # Exactly at the one_hour close / next_three_hour open.
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=3))
    assert [item.window for item in due] == [
        IMMEDIATE,
        FIVE_MINUTE,
        ONE_HOUR,
        NEXT_THREE_HOUR,
    ]
    assert [item.delayed for item in due] == [True, True, True, False]

    # The canonical horizon never closes: still on-time due (open horizon).
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=4))
    assert [item.window for item in due] == [
        IMMEDIATE,
        FIVE_MINUTE,
        ONE_HOUR,
        NEXT_THREE_HOUR,
    ]
    assert due[-1].delayed is False


def test_anchor_itself_opens_only_immediate() -> None:
    due = due_checkpoints(anchor_at=T0, now=T0)
    assert [item.window for item in due] == [IMMEDIATE]
    assert due[0].delayed is False
    assert due[0].open_at == T0
    assert due[0].close_at == _ts(minutes=5)


def test_future_anchor_yields_no_due_items() -> None:
    assert due_checkpoints(anchor_at=_ts(hours=1), now=T0) == ()


# ---------------------------------------------------------------------------
# six_hour: read alias only
# ---------------------------------------------------------------------------


def test_six_hour_completed_suppresses_next_three_hour_only() -> None:
    # A legacy completed "six_hour" is read as next_three_hour: it suppresses
    # the canonical horizon and never creates a separate six-hour window.
    due = due_checkpoints(
        anchor_at=T0,
        now=_ts(hours=4),
        completed=["six_hour"],
        lease_id="lease-1",
        custody_epoch=3,
        fencing_token="tok-1",
    )
    assert [item.window for item in due] == [IMMEDIATE, FIVE_MINUTE, ONE_HOUR]
    assert all(item.window.value != "six_hour" for item in due)
    # No separate six-hour window is ever scheduled.
    assert all(
        item.window is not CheckpointWindowKind.NEXT_THREE_HOUR
        or "six_hour" not in (item.window.value,)
        for item in due
    )


def test_unknown_window_names_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown checkpoint window"):
        canonical_checkpoint_window("two_hour")
    with pytest.raises(ValueError, match="unknown checkpoint window"):
        due_checkpoints(anchor_at=T0, now=_ts(hours=1), completed=["two_hour"])


# ---------------------------------------------------------------------------
# Persisted completion and duplicate suppression
# ---------------------------------------------------------------------------


def test_completed_checkpoint_windows_extracts_and_dedupes() -> None:
    events = [
        _checkpoint_event(IMMEDIATE, event_id="e1"),
        _checkpoint_event(IMMEDIATE, event_id="e2"),  # exact retry duplicate
        _checkpoint_event(FIVE_MINUTE, event_id="e3"),
        _repair_request_event(),
    ]
    assert completed_checkpoint_windows(events) == (IMMEDIATE, FIVE_MINUTE)
    # Dicts strict-decode to the same result.
    dicts = [canonical_dumps(event) for event in events]
    assert completed_checkpoint_windows(dicts) == (IMMEDIATE, FIVE_MINUTE)


def test_verified_windows_are_never_reemitted() -> None:
    events = [
        _checkpoint_event(IMMEDIATE, event_id="e1"),
        _checkpoint_event(FIVE_MINUTE, event_id="e2"),
    ]
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=1), events=events)
    assert [item.window for item in due] == [ONE_HOUR]
    assert due[0].delayed is False


def test_duplicate_events_emit_each_due_window_once() -> None:
    events = [
        _checkpoint_event(IMMEDIATE, event_id="e1"),
        _checkpoint_event(IMMEDIATE, event_id="e2"),
    ]
    # immediate is verified (suppressed despite the duplicate retry event);
    # five_minute is open at +10m (inside its half-open window, on time).
    due = due_checkpoints(anchor_at=T0, now=_ts(minutes=10), events=events)
    assert [item.window for item in due] == [FIVE_MINUTE]
    assert due[0].delayed is False
    # Each due window is emitted exactly once.
    windows = [item.window for item in due]
    assert len(windows) == len(set(windows))


def test_malformed_persisted_event_fails_closed() -> None:
    bad = {"event_id": "e9", "action_kind": "checkpoint_verification"}
    with pytest.raises(ValueError):
        completed_checkpoint_windows([bad])
    with pytest.raises(ValueError):
        due_checkpoints(anchor_at=T0, now=_ts(hours=1), events=[bad])


# ---------------------------------------------------------------------------
# Late catch-up and replay safety
# ---------------------------------------------------------------------------


def test_late_catch_up_returns_overdue_windows_once_in_event_time_order() -> None:
    events = [_checkpoint_event(IMMEDIATE, event_id="e1")]
    # At +2h: five_minute is overdue (closed at +1h) -> delayed catch-up;
    # one_hour is still inside its half-open window -> on time.
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=2), events=events)
    assert [item.window for item in due] == [FIVE_MINUTE, ONE_HOUR]
    assert [item.delayed for item in due] == [True, False]
    # Each due checkpoint appears exactly once, in event-time order.
    windows = [item.window for item in due]
    assert len(windows) == len(set(windows))
    # Everything past the one_hour close is catch-up too.
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=4), events=events)
    assert [item.window for item in due] == [
        FIVE_MINUTE,
        ONE_HOUR,
        NEXT_THREE_HOUR,
    ]
    assert [item.delayed for item in due] == [True, True, False]


def test_restart_replay_is_deterministic_and_codec_stable() -> None:
    kwargs: dict[str, Any] = dict(
        anchor_at=T0,
        now=_ts(hours=5),
        completed=["six_hour"],
        occurrence_id="occ-1",
        lease_id="lease-1",
        custody_epoch=3,
        fencing_token="tok-1",
    )
    first = due_checkpoints(**kwargs)
    second = due_checkpoints(**kwargs)  # restart with the same persisted input
    assert first == second
    # Strict codec round-trip: byte-stable replay, same digest.
    for item in first:
        decoded = strict_loads(CheckpointDueItem, canonical_dumps(item))
        assert decoded == item
        assert canonical_digest(decoded) == canonical_digest(item)


# ---------------------------------------------------------------------------
# Inherited authority (mandatory fresh reacquisition)
# ---------------------------------------------------------------------------


def test_due_items_carry_inherited_lease_epoch_fence_verbatim() -> None:
    anchor_ref = OwnerRef(
        owner="repair_custody",
        record_type="effect_receipt",
        locator="receipt://occ-1/1",
        digest="b" * 64,
    )
    due = due_checkpoints(
        anchor_at=T0,
        now=_ts(hours=4),
        occurrence_id="occ-1",
        lease_id="lease-1",
        custody_epoch=3,
        fencing_token="tok-1",
        anchor_ref=anchor_ref,
    )
    assert len(due) == 4
    for item in due:
        assert item.occurrence_id == "occ-1"
        assert item.lease_id == "lease-1"
        assert item.custody_epoch == 3
        assert item.fencing_token == "tok-1"
        assert item.anchor_ref == anchor_ref


def test_stale_epoch_is_never_masked_by_the_scheduler() -> None:
    # The scheduler was persisted with epoch 3; the current epoch has since
    # advanced to 5.  The scheduler still carries the STALE coordinates
    # verbatim: freshness reacquisition is the executor's job, so the stale
    # epoch is never silently promoted or dropped.
    due = due_checkpoints(
        anchor_at=T0,
        now=_ts(hours=4),
        lease_id="lease-1",
        custody_epoch=3,
        fencing_token="tok-1",
    )
    assert due
    assert all(item.custody_epoch == 3 for item in due)
    assert all(item.fencing_token == "tok-1" for item in due)


def test_item_model_rejects_invalid_authority_coordinates() -> None:
    with pytest.raises(ValueError):
        due_checkpoints(
            anchor_at=T0, now=_ts(hours=1), custody_epoch=0
        )
    with pytest.raises(ValueError):
        due_checkpoints(anchor_at=T0, now=_ts(hours=1), lease_id="")
    with pytest.raises(ValueError):
        due_checkpoints(anchor_at=T0, now=_ts(hours=1), fencing_token="")


# ---------------------------------------------------------------------------
# Input validation and policy subsets
# ---------------------------------------------------------------------------


def test_naive_datetimes_fail_closed() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        due_checkpoints(anchor_at=datetime(2026, 8, 15, 12, 0), now=T0)
    with pytest.raises(ValueError, match="UTC offset"):
        due_checkpoints(anchor_at=T0, now=datetime(2026, 8, 15, 12, 0))


def test_events_and_completed_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="not both"):
        due_checkpoints(
            anchor_at=T0,
            now=_ts(hours=1),
            events=[_checkpoint_event(IMMEDIATE)],
            completed=[IMMEDIATE],
        )


def test_policy_subset_limits_the_schedule() -> None:
    due = due_checkpoints(
        anchor_at=T0,
        now=_ts(hours=4),
        policy=[ONE_HOUR],
        completed=[ONE_HOUR],
    )
    assert due == ()
    due = due_checkpoints(anchor_at=T0, now=_ts(hours=4), policy=[ONE_HOUR])
    assert [item.window for item in due] == [ONE_HOUR]
