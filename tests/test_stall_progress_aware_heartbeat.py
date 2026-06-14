"""Progress-aware stall detection for ``llm_token_heartbeat`` events.

Regression for the 2026-06-10 DeepSeek-V4-Pro execute wedge: a streaming call
froze with ``tokens_emitted_so_far=34`` / ``reasoning_emitted_so_far=2571`` and
then emitted ~4000 *frozen-count* heartbeats over ~28 minutes. Because
``_stall_event_progress_snapshot`` counted any ``LLM_TOKEN_HEARTBEAT`` (and any
open ``llm_call_start``) as progress, the auto-driver's same-state stall counter
never advanced and the genuine wedge was invisible to that backstop.

The fix makes the snapshot progress-aware: a heartbeat advances the progress
cursor only when its token/reasoning counts grow, and an open call only counts
as in-flight while its stream is still growing.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan.auto import _stall_event_progress_snapshot
from arnold.pipelines.megaplan.observability.events import EventKind, emit


def _hb(plan_dir: Path, tokens: int, reasoning: int) -> None:
    emit(
        EventKind.LLM_TOKEN_HEARTBEAT,
        plan_dir,
        phase="execute",
        payload={
            "tokens_emitted_so_far": tokens,
            "last_token_at": 0.0,
            "reasoning_emitted_so_far": reasoning,
            "last_reasoning_at": 0.0,
        },
    )


def test_frozen_count_heartbeats_do_not_advance_progress(tmp_path: Path) -> None:
    """A wedged stream (flat counts) must NOT keep advancing the progress seq."""
    plan_dir = tmp_path
    # Open a streaming call (no matching end -> it stays "in flight").
    emit(
        EventKind.LLM_CALL_START,
        plan_dir,
        phase="execute",
        payload={"provider": "deepseek-v4-pro", "streaming": True, "request_id": None},
    )
    # Stream grows for a while...
    _hb(plan_dir, 10, 1000)
    _hb(plan_dir, 20, 2000)
    _hb(plan_dir, 34, 2571)

    seq_after_growth, in_flight_growth, _kind = _stall_event_progress_snapshot(plan_dir)
    assert in_flight_growth is True  # still streaming -> healthy

    # ...then wedges: many frozen-count heartbeats (the 28-min hang).
    for _ in range(50):
        _hb(plan_dir, 34, 2571)

    seq_after_wedge, in_flight_wedge, _kind2 = _stall_event_progress_snapshot(plan_dir)

    # The progress seq must NOT have advanced across the frozen-count beats:
    # the same-state stall counter will therefore increment and eventually trip.
    assert seq_after_wedge == seq_after_growth, (
        f"frozen-count heartbeats advanced progress seq "
        f"{seq_after_growth} -> {seq_after_wedge}; the wedge is masked"
    )
    # And the wedged open call must NOT keep reporting as in-flight progress.
    assert in_flight_wedge is False, (
        "a wedged open llm call still reported in-flight progress, masking the stall"
    )


def test_growing_count_heartbeats_keep_advancing_progress(tmp_path: Path) -> None:
    """A healthy growing stream must always be seen as progress (no false stall)."""
    plan_dir = tmp_path
    emit(
        EventKind.LLM_CALL_START,
        plan_dir,
        phase="execute",
        payload={"provider": "deepseek-v4-pro", "streaming": True, "request_id": None},
    )
    _hb(plan_dir, 1, 100)
    seq_a, in_flight_a, _ = _stall_event_progress_snapshot(plan_dir)
    assert in_flight_a is True

    # Every subsequent poll observes higher counts -> progress seq advances.
    last_seq = seq_a
    for i in range(2, 12):
        _hb(plan_dir, i, 100 * i)
        seq_now, in_flight_now, _ = _stall_event_progress_snapshot(plan_dir)
        assert in_flight_now is True
        assert seq_now is not None and last_seq is not None and seq_now > last_seq, (
            f"growing-count heartbeat failed to advance progress seq "
            f"({last_seq} -> {seq_now})"
        )
        last_seq = seq_now


def test_precount_heartbeat_shape_fails_open(tmp_path: Path) -> None:
    """A heartbeat payload predating the count fields is treated as progress."""
    plan_dir = tmp_path
    emit(
        EventKind.LLM_CALL_START,
        plan_dir,
        phase="execute",
        payload={"provider": "x", "streaming": True, "request_id": None},
    )
    seq_start, _, _ = _stall_event_progress_snapshot(plan_dir)
    # Legacy heartbeat: no token/reasoning counts in the payload.
    emit(
        EventKind.LLM_TOKEN_HEARTBEAT,
        plan_dir,
        phase="execute",
        payload={"note": "legacy-shape"},
    )
    seq_after, in_flight_after, _ = _stall_event_progress_snapshot(plan_dir)
    assert seq_after is not None and seq_start is not None and seq_after > seq_start
    assert in_flight_after is True
