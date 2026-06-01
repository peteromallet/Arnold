"""W9b — fold_events and read_events unit tests."""
from pathlib import Path

from megaplan.observability.fold import fold_events, read_events
from megaplan.observability.events import EventKind, emit_state_wal


def _make_state_written_event(seq: int, snapshot: dict) -> dict:
    return {
        "seq": seq,
        "kind": EventKind.STATE_WRITTEN,
        "payload": {"state": snapshot, "effect_class": "state_write", "taint": "trusted"},
    }


def _make_other_event(seq: int, kind: str = "phase_start") -> dict:
    return {"seq": seq, "kind": kind, "payload": {}}


# ---------------------------------------------------------------------------
# fold_events tests
# ---------------------------------------------------------------------------

def test_fold_events_empty_returns_empty_dict():
    assert fold_events([]) == {}


def test_fold_events_single_state_written():
    snapshot = {"name": "p", "iteration": 1}
    events = [_make_state_written_event(seq=0, snapshot=snapshot)]
    assert fold_events(events) == snapshot


def test_fold_events_last_snapshot_wins():
    first = {"name": "p", "iteration": 1}
    second = {"name": "p", "iteration": 2}
    events = [
        _make_state_written_event(seq=0, snapshot=first),
        _make_state_written_event(seq=1, snapshot=second),
    ]
    assert fold_events(events) == second


def test_fold_events_last_wins_regardless_of_list_order():
    """fold_events must sort by seq, not rely on list order."""
    first = {"name": "p", "iteration": 1}
    second = {"name": "p", "iteration": 2}
    # Provide in reverse order
    events = [
        _make_state_written_event(seq=5, snapshot=second),
        _make_state_written_event(seq=3, snapshot=first),
    ]
    assert fold_events(events) == second


def test_fold_events_ignores_other_kinds():
    snapshot = {"name": "p", "iteration": 7}
    events = [
        _make_other_event(seq=0, kind="init"),
        _make_state_written_event(seq=1, snapshot=snapshot),
        _make_other_event(seq=2, kind="phase_start"),
        _make_other_event(seq=3, kind="state_transition"),  # coarse kind, must be ignored
        _make_other_event(seq=4, kind="cost_recorded"),
    ]
    assert fold_events(events) == snapshot


def test_fold_events_no_state_written_returns_empty():
    events = [
        _make_other_event(seq=0, kind="init"),
        _make_other_event(seq=1, kind="phase_start"),
    ]
    assert fold_events(events) == {}


def test_fold_events_is_pure_no_side_effects():
    """Calling fold_events must not mutate the input list."""
    snapshot = {"name": "p", "iteration": 1}
    events = [_make_state_written_event(seq=0, snapshot=snapshot)]
    original_len = len(events)
    fold_events(events)
    assert len(events) == original_len


# ---------------------------------------------------------------------------
# read_events tests
# ---------------------------------------------------------------------------

def test_read_events_missing_file_returns_empty(tmp_path: Path):
    assert read_events(tmp_path) == []


def test_read_events_returns_ordered_events(tmp_path: Path):
    # Write two STATE_WRITTEN events via the real journal
    snap1 = {"name": "p", "iteration": 1, "current_state": "initialized",
              "idea": "x", "created_at": "2026-01-01T00:00:00Z",
              "config": {}, "sessions": {}, "plan_versions": [],
              "history": [], "meta": {}}
    snap2 = {**snap1, "iteration": 2}
    emit_state_wal(tmp_path, snap1)
    emit_state_wal(tmp_path, snap2)

    evs = read_events(tmp_path)
    assert len(evs) == 2
    # Must be in seq order
    assert evs[0]["seq"] < evs[1]["seq"]
    assert evs[0]["kind"] == EventKind.STATE_WRITTEN
    assert evs[1]["kind"] == EventKind.STATE_WRITTEN


def test_read_events_and_fold_round_trip(tmp_path: Path):
    snap1 = {"name": "p", "iteration": 1, "current_state": "initialized",
              "idea": "x", "created_at": "2026-01-01T00:00:00Z",
              "config": {}, "sessions": {}, "plan_versions": [],
              "history": [], "meta": {}}
    snap2 = {**snap1, "iteration": 2}
    emit_state_wal(tmp_path, snap1)
    emit_state_wal(tmp_path, snap2)

    evs = read_events(tmp_path)
    result = fold_events(evs)
    assert result["iteration"] == 2
