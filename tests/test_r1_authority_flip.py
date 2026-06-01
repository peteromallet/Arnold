"""T25 / Step 20: R1 authority-flip reader shim and StateCacheDrift.

Covers:
- flag-OFF parity: ``read_plan_state_cached(..., mode='authority')`` reads
  ``state.json`` directly, with no fold, no drift event.
- kill+resume byte-identical: when the on-disk cache matches the WAL fold,
  the authority read returns a structurally-equal state and no
  ``STATE_CACHE_DRIFT`` event is emitted.
- drift event: when the cache disagrees with the WAL fold, the cache is
  rewritten with WAL truth and a ``STATE_CACHE_DRIFT`` event is appended
  to the events.ndjson WAL.
- cache_tolerant mode short-circuits the fold entirely (no event).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from megaplan._core.io import atomic_write_json, read_plan_state_cached
from megaplan.observability.events import EventKind, emit_state_wal
from megaplan.observability.fold import rebuild_state_from_wal, read_events


def _read_wal_kinds(plan_dir: Path) -> list[str]:
    return [e.get("kind") for e in read_events(plan_dir)]


def _make_plan(tmp_path: Path, state: dict) -> Path:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    atomic_write_json(plan_dir / "state.json", state)
    return plan_dir


@pytest.fixture(autouse=True)
def _clear_r1_env(monkeypatch):
    # Ensure each test controls the flag explicitly.
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    monkeypatch.delenv("R1_AUTHORITY", raising=False)
    yield


def test_flag_off_reads_disk_directly_no_fold(tmp_path):
    plan_dir = _make_plan(tmp_path, {"current_state": "planned", "v": 1})
    # No WAL written at all — under flag-OFF the shim must NOT try to fold.
    out = read_plan_state_cached(plan_dir, mode="authority")
    assert out == {"current_state": "planned", "v": 1}
    assert _read_wal_kinds(plan_dir) == []


def test_flag_off_parity_with_legacy_read_json(tmp_path):
    state = {"current_state": "executed", "items": [1, 2, 3]}
    plan_dir = _make_plan(tmp_path, state)
    legacy = json.loads((plan_dir / "state.json").read_text())
    shim = read_plan_state_cached(plan_dir, mode="authority")
    assert shim == legacy


def test_flag_on_kill_resume_byte_identical_no_drift_event(tmp_path, monkeypatch):
    state = {"current_state": "executed", "v": 42}
    plan_dir = _make_plan(tmp_path, state)
    emit_state_wal(plan_dir, state)

    monkeypatch.setenv("R1_AUTHORITY", "1")
    out = read_plan_state_cached(plan_dir, mode="authority")
    assert out == state
    # No drift event emitted because cache matches WAL fold.
    assert EventKind.STATE_CACHE_DRIFT not in _read_wal_kinds(plan_dir)
    # Cache content unchanged after read.
    assert json.loads((plan_dir / "state.json").read_text()) == state


def test_flag_on_drift_event_when_cache_diverges(tmp_path, monkeypatch):
    wal_state = {"current_state": "executed", "v": 2}
    plan_dir = _make_plan(tmp_path, {"current_state": "planned", "v": 1})
    # WAL says executed/v=2, cache says planned/v=1 → drift.
    emit_state_wal(plan_dir, wal_state)

    monkeypatch.setenv("R1_AUTHORITY", "1")
    out = read_plan_state_cached(plan_dir, mode="authority")

    # Returned value is WAL truth, not the stale cache.
    assert out == wal_state
    # Cache was rewritten with WAL truth.
    assert json.loads((plan_dir / "state.json").read_text()) == wal_state
    # A STATE_CACHE_DRIFT event was appended.
    kinds = _read_wal_kinds(plan_dir)
    assert EventKind.STATE_CACHE_DRIFT in kinds


def test_cache_tolerant_mode_never_folds_or_emits_drift(tmp_path, monkeypatch):
    # Even with flag ON and divergent cache, cache_tolerant just reads disk.
    plan_dir = _make_plan(tmp_path, {"current_state": "planned", "v": 1})
    emit_state_wal(plan_dir, {"current_state": "executed", "v": 99})
    monkeypatch.setenv("R1_AUTHORITY", "1")

    out = read_plan_state_cached(plan_dir, mode="cache_tolerant")
    assert out == {"current_state": "planned", "v": 1}
    assert EventKind.STATE_CACHE_DRIFT not in _read_wal_kinds(plan_dir)


def test_rebuild_state_from_wal_alias(tmp_path):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    snapshot = {"current_state": "executed", "v": 7}
    emit_state_wal(plan_dir, snapshot)
    assert rebuild_state_from_wal(plan_dir) == snapshot


def test_unknown_mode_raises(tmp_path):
    plan_dir = _make_plan(tmp_path, {})
    with pytest.raises(ValueError):
        read_plan_state_cached(plan_dir, mode="bogus")  # type: ignore[arg-type]


def test_state_cache_drift_registered_in_all_event_kinds():
    from megaplan.observability.events import _ALL_EVENT_KINDS
    assert EventKind.STATE_CACHE_DRIFT in _ALL_EVENT_KINDS
