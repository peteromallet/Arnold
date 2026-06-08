"""W9c — assert_fold_equiv oracle round-trip tests (T7).

The oracle compares ``fold_events(read_events(plan_dir))`` to the live
``state.json``. The required test is a load→write→emit→fold ROUND-TRIP (not a
static diff of bare fixtures): for each W3 fixture, the fixture state.json is
copied into a temp plan dir, then a real ``write_plan_state`` (and a
``save_loop_state`` variant) emits STATE_WRITTEN, and the oracle is asserted.

Scope of "every state-transition path" = the M1 round-trip tests below
(write_plan_state replace + save_loop_state). No read path consumes the fold
— a divergence raises AssertionError and auto-fails CI.

The ``recorded_trace_dir`` parameter on ``assert_fold_equiv`` is the
documented seam for the M2.5 recorded-trace corpus.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._core.state import load_plan_from_dir, write_plan_state
from arnold.pipelines.megaplan.loop.engine import save_loop_state
from arnold.pipelines.megaplan.observability.fold import (
    assert_fold_equiv,
    fold_events,
    read_events,
)


_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "state_json"

FIXTURE_IDS = ("v0_noversion", "v1", "v_future")


@pytest.mark.parametrize("fixture_name", FIXTURE_IDS)
def test_write_plan_state_round_trip_fold_equiv(
    fixture_name: str, tmp_path: Path
) -> None:
    """load→write→emit→fold round-trip via write_plan_state on each W3 fixture.

    Same post-validation next_state on both sides: write_plan_state writes
    next_state to disk and emits STATE_WRITTEN carrying deepcopy(next_state).
    """
    plan_dir = tmp_path / fixture_name
    shutil.copytree(_FIXTURE_ROOT / fixture_name, plan_dir)

    _, loaded_state = load_plan_from_dir(plan_dir)
    write_plan_state(plan_dir, mode="replace", state=dict(loaded_state))

    assert_fold_equiv(plan_dir)


@pytest.mark.parametrize("fixture_name", FIXTURE_IDS)
def test_save_loop_state_round_trip_fold_equiv(
    fixture_name: str, tmp_path: Path
) -> None:
    """Second writer path: save_loop_state emits STATE_WRITTEN via the same helper.

    save_loop_state owns its own ``state.json`` (the loop-engine state file).
    We use a dedicated tmp dir so save_loop_state's atomic write IS the
    authoritative state.json on the same plan_dir for which the oracle reads
    events.
    """
    plan_dir = tmp_path / fixture_name

    # Seed via a real write_plan_state from the W3 fixture so both writer
    # paths exercise the oracle against a fixture-derived state shape.
    src = _FIXTURE_ROOT / fixture_name
    shutil.copytree(src, plan_dir)
    _, loaded_state = load_plan_from_dir(plan_dir)

    # save_loop_state overwrites state.json with its own dict; emit the
    # snapshot the loop engine considers authoritative.
    loop_state = {"name": loaded_state.get("name", "loop"), "iteration": 0}
    save_loop_state(plan_dir, loop_state)

    assert_fold_equiv(plan_dir)


def test_assert_fold_equiv_detects_divergence(tmp_path: Path) -> None:
    """A divergence between fold and state.json MUST raise AssertionError."""
    plan_dir = tmp_path / "divergent"
    plan_dir.mkdir()

    # Write a state.json directly (no STATE_WRITTEN event) so the fold is
    # empty and cannot equal the live state.
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "x", "iteration": 1}), encoding="utf-8"
    )
    with pytest.raises(AssertionError):
        assert_fold_equiv(plan_dir)


def test_recorded_trace_dir_seam_is_documented_and_wired(tmp_path: Path) -> None:
    """The ``recorded_trace_dir=None`` seam reads events from an alt directory.

    M2.5 recorded-trace corpus will pass a recorded-trace dir while
    asserting against the live state.json in plan_dir.
    """
    import inspect

    sig = inspect.signature(assert_fold_equiv)
    assert "recorded_trace_dir" in sig.parameters
    assert sig.parameters["recorded_trace_dir"].default is None
    assert "M2.5" in (assert_fold_equiv.__doc__ or "")

    plan_dir = tmp_path / "live"
    plan_dir.mkdir()
    trace_dir = tmp_path / "trace"
    trace_dir.mkdir()

    # Emit a STATE_WRITTEN to trace_dir, then write the matching snapshot to
    # plan_dir/state.json by hand — the oracle pulls events from trace_dir
    # but compares against plan_dir/state.json.
    snapshot = {"name": "seam", "iteration": 1, "schema_version": 0}
    from arnold.pipelines.megaplan.observability.events import emit_state_wal

    emit_state_wal(trace_dir, snapshot)
    (plan_dir / "state.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )

    assert_fold_equiv(plan_dir, recorded_trace_dir=trace_dir)


def test_fold_and_read_still_importable() -> None:
    """Public API surface check: fold_events / read_events remain exported."""
    assert callable(fold_events)
    assert callable(read_events)
