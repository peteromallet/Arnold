"""Real-path liveness regression for the Hermes streaming heartbeat.

Production bug (2026-05-23): on a live `megaplan auto` execute phase routed to
Hermes/DeepSeek, `state.json`'s `active_step.last_activity_at` stayed frozen at
the phase-start timestamp for the entire 8+ minute batch. The phase-idle monitor
(`auto._run_megaplan`) watches the `state.json` mtime via `_plan_liveness_mtime`
and false-stalled the healthy batch.

Root cause: a silently-streaming provider (DeepSeek execute, `quiet_mode=True`)
writes nothing to stderr, so the `_ActivityStream` stderr wrapper never fires.
The only other liveness path was `_start_heartbeat`, whose beat thread emitted an
`LLM_TOKEN_HEARTBEAT` *observability event* but never touched `state.json`. So no
artifact mtime advanced and `touch_active_step` was never called on this path.

This test exercises the genuine chain end-to-end without a network/provider:

    set_active_step (the way handlers/execute.py:134 sets it)
      -> save_state_merge_meta (persist to a real on-disk state.json)
      -> the real _StreamTracker + real _start_heartbeat thread, keyed by the
         on-disk run_id, driven by *silent* token chunks (no stderr writes)
      -> real touch_active_step
      -> assert state.json on disk has last_activity_at + mtime that ADVANCE.

It also pins the heartbeat's two guards: a wedged stream (no new tokens) must
NOT keep the phase alive, and a run_id that does not match the on-disk
active_step must NOT clobber it (stale-worker guard).
"""

from __future__ import annotations

import threading
import time

import pytest

from megaplan._core import (
    atomic_write_json,
    read_json,
    save_state_merge_meta,
    set_active_step,
)
from megaplan.workers.hermes import _StreamTracker, _start_heartbeat


def _seed_state(plan_dir):
    """Build + persist a minimal real state.json with an execute active_step,
    exactly the way handlers.execute does at the top of the phase."""
    state = {
        "name": "liveness-test",
        "config": {"project_dir": str(plan_dir), "mode": "code"},
        "meta": {},
        "history": [],
        "sessions": {},
        "iteration": 1,
    }
    run_id = set_active_step(
        state, step="execute", agent="hermes", mode="persistent", model="deepseek:deepseek-v4-pro"
    )
    save_state_merge_meta(plan_dir, state)
    return state, run_id


def _wait_until(predicate, timeout=10.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_silent_stream_heartbeat_advances_state_on_disk(tmp_path):
    plan_dir = tmp_path
    state, run_id = _seed_state(plan_dir)
    state_path = plan_dir / "state.json"

    before = read_json(state_path)["active_step"]
    frozen_activity = before["last_activity_at"]
    frozen_mtime = state_path.stat().st_mtime

    tracker = _StreamTracker()
    stop = threading.Event()
    # Real heartbeat thread, keyed by the on-disk run_id, just like run_hermes_step.
    _start_heartbeat(plan_dir, "execute", tracker, stop, run_id=run_id)
    try:
        # Simulate a SILENT but ALIVE stream: provider emits token chunks via the
        # stream_callback (no stderr writes at all). This is the DeepSeek path.
        def _emit_tokens():
            for _ in range(50):
                if stop.is_set():
                    return
                tracker("chunk")  # increments tokens_emitted, last_token_at
                time.sleep(0.1)

        emitter = threading.Thread(target=_emit_tokens, daemon=True)
        emitter.start()

        # The beat fires every ~1s. Within a few seconds the on-disk
        # last_activity_at must move past the frozen phase-start timestamp.
        advanced = _wait_until(
            lambda: read_json(state_path)["active_step"]["last_activity_at"] != frozen_activity,
            timeout=8.0,
        )
        assert advanced, "state.json active_step.last_activity_at never advanced during a live silent stream"

        after = read_json(state_path)["active_step"]
        assert after["last_activity_kind"] == "llm_stream"
        assert after["run_id"] == run_id  # guard preserved: same run, in-place update
        # The phase-idle monitor watches the file mtime — it must advance too.
        assert state_path.stat().st_mtime > frozen_mtime
    finally:
        stop.set()
        emitter.join(timeout=2)


def test_wedged_stream_does_not_keep_phase_alive(tmp_path):
    """No new tokens => no touch. A genuinely stuck stream must still be
    allowed to idle-timeout rather than being held alive forever."""
    plan_dir = tmp_path
    state, run_id = _seed_state(plan_dir)
    state_path = plan_dir / "state.json"
    frozen_activity = read_json(state_path)["active_step"]["last_activity_at"]

    tracker = _StreamTracker()  # never emits a token
    stop = threading.Event()
    _start_heartbeat(plan_dir, "execute", tracker, stop, run_id=run_id)
    try:
        # Give the beat several cycles. With zero tokens it must never touch state.
        time.sleep(3.0)
        assert (
            read_json(state_path)["active_step"]["last_activity_at"] == frozen_activity
        ), "wedged stream (no tokens) should not advance last_activity_at"
    finally:
        stop.set()


def test_stale_run_id_does_not_clobber_active_step(tmp_path):
    """A heartbeat whose run_id differs from the on-disk active_step must
    no-op (the stale-worker guard in touch_active_step)."""
    plan_dir = tmp_path
    state, run_id = _seed_state(plan_dir)
    state_path = plan_dir / "state.json"
    frozen = read_json(state_path)["active_step"]
    frozen_activity = frozen["last_activity_at"]

    tracker = _StreamTracker()
    stop = threading.Event()
    # Wrong run_id: a stale worker from a superseded run.
    _start_heartbeat(plan_dir, "execute", tracker, stop, run_id="stale-run-id-deadbeef")
    try:
        def _emit():
            for _ in range(40):
                if stop.is_set():
                    return
                tracker("chunk")
                time.sleep(0.1)

        emitter = threading.Thread(target=_emit, daemon=True)
        emitter.start()
        time.sleep(3.0)
        current = read_json(state_path)["active_step"]
        assert current["last_activity_at"] == frozen_activity, "stale run_id must not bump the current active_step"
        assert current["run_id"] == run_id
    finally:
        stop.set()
        emitter.join(timeout=2)
