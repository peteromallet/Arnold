"""Tests for the ``reversible`` PlanStateWriteMode + snapshot/restore +
restorable_boundary (M3 Step 15 / T20).

Coverage:
  - write_plan_state(mode="reversible") snapshot-then-replace
  - snapshot(plan_dir) / restore(plan_dir, snapshot_id) round-trip
  - distinct .state-versions/ namespace (no collision with executor's
    sibling forensic-backup ``state.json.corrupt-executor-backup``)
  - PlanStateWriteMode Literal lists 9 modes including "reversible"
  - restorable_boundary raises under subprocess_isolated OR fanout
  - restorable_boundary noop under in_process / no-substrate / no-fanout
  - explicit anti-silent-no-op: a reversible write MUST always record
    the snapshot id in ``_state_meta['last_snapshot']`` and MUST overwrite
    state.json on disk (no silent skip even when state matches existing)
"""

from __future__ import annotations

import json
import typing

import pytest

from megaplan._core.state import (
    PlanStateWriteMode,
    RestorableBoundaryViolation,
    _STATE_VERSIONS_DIRNAME,
    _state_versions_dir,
    plan_state_lock_path,
    restorable_boundary,
    restore,
    snapshot,
    write_plan_state,
)


def _initial_state() -> dict:
    return {
        "schema_version": 0,
        "current_state": "initialized",
        "iteration": 1,
        "config": {"project_dir": "/tmp/x"},
    }


@pytest.fixture
def plan_dir(tmp_path):
    d = tmp_path / "plans" / "plan-1"
    d.mkdir(parents=True)
    return d


# ---------------------------------------------------------------------------
# PlanStateWriteMode literal lock
# ---------------------------------------------------------------------------


def test_plan_state_write_mode_includes_reversible():
    args = set(typing.get_args(PlanStateWriteMode))
    assert "reversible" in args
    assert len(args) == 9


# ---------------------------------------------------------------------------
# write_plan_state(mode="reversible") snapshot-then-replace
# ---------------------------------------------------------------------------


def test_reversible_requires_state(plan_dir):
    with pytest.raises(TypeError, match="state is required"):
        write_plan_state(plan_dir, mode="reversible")


def test_reversible_first_write_no_prior_state(plan_dir):
    next_state = write_plan_state(plan_dir, mode="reversible", state=_initial_state())
    assert next_state["current_state"] == "initialized"
    assert next_state["_state_meta"]["last_snapshot"] is None
    # no .state-versions/ created because there was nothing to snapshot
    assert not _state_versions_dir(plan_dir).exists()
    # on-disk content matches in-memory
    on_disk = json.loads((plan_dir / "state.json").read_text())
    assert on_disk["current_state"] == "initialized"


def test_reversible_snapshot_then_replace(plan_dir):
    write_plan_state(plan_dir, mode="replace", state=_initial_state())
    new = dict(_initial_state())
    new["iteration"] = 2
    new["current_state"] = "planned"

    next_state = write_plan_state(plan_dir, mode="reversible", state=new)

    snapshot_id = next_state["_state_meta"]["last_snapshot"]
    assert isinstance(snapshot_id, str) and len(snapshot_id) == 32
    snap_path = _state_versions_dir(plan_dir) / f"{snapshot_id}.json"
    assert snap_path.exists()

    # snapshot captures the PRIOR (initialized, iter=1) state
    snap = json.loads(snap_path.read_text())
    assert snap["current_state"] == "initialized"
    assert snap["iteration"] == 1

    # state.json now reflects the new payload
    on_disk = json.loads((plan_dir / "state.json").read_text())
    assert on_disk["current_state"] == "planned"
    assert on_disk["iteration"] == 2
    assert on_disk["_state_meta"]["last_snapshot"] == snapshot_id


def test_reversible_does_not_collide_with_forensic_backup(plan_dir):
    # the executor's forensic backup writes a SIBLING of state.json
    # named state.json.corrupt-executor-backup; our snapshot blobs
    # live under .state-versions/<id>.json. The two namespaces must
    # never overlap.
    write_plan_state(plan_dir, mode="replace", state=_initial_state())
    new = dict(_initial_state())
    new["iteration"] = 9
    next_state = write_plan_state(plan_dir, mode="reversible", state=new)

    forensic = plan_dir / "state.json.corrupt-executor-backup"
    assert not forensic.exists()
    assert _STATE_VERSIONS_DIRNAME == ".state-versions"
    assert _state_versions_dir(plan_dir).name == _STATE_VERSIONS_DIRNAME
    assert _state_versions_dir(plan_dir).is_dir()
    # snapshot path uses .state-versions/, NOT the .corrupt-executor-backup name
    snap_id = next_state["_state_meta"]["last_snapshot"]
    assert (_state_versions_dir(plan_dir) / f"{snap_id}.json").exists()


# ---------------------------------------------------------------------------
# Anti-silent-no-op: explicit invariant
# ---------------------------------------------------------------------------


def test_reversible_anti_silent_no_op(plan_dir):
    """A reversible write of an IDENTICAL payload must NOT be skipped.

    The whole point of the mode is that an outer ``restorable_boundary``
    can rely on a snapshot id being present after every call. If the write
    silently no-ops (because the next_state happened to equal existing),
    no snapshot is captured and rollback becomes impossible. This test
    locks the invariant: same input twice in a row produces two distinct
    snapshot ids and two snapshot blobs on disk.
    """
    initial = _initial_state()
    write_plan_state(plan_dir, mode="replace", state=initial)

    first = write_plan_state(plan_dir, mode="reversible", state=dict(initial))
    second = write_plan_state(plan_dir, mode="reversible", state=dict(initial))

    snap1 = first["_state_meta"]["last_snapshot"]
    snap2 = second["_state_meta"]["last_snapshot"]
    assert snap1 is not None
    assert snap2 is not None
    assert snap1 != snap2

    versions_dir = _state_versions_dir(plan_dir)
    written = {p.stem for p in versions_dir.glob("*.json")}
    assert snap1 in written
    assert snap2 in written
    assert len(written) >= 2


# ---------------------------------------------------------------------------
# snapshot / restore round-trip
# ---------------------------------------------------------------------------


def test_snapshot_returns_none_when_no_state(plan_dir):
    assert snapshot(plan_dir) is None


def test_snapshot_and_restore_round_trip(plan_dir):
    write_plan_state(plan_dir, mode="replace", state=_initial_state())
    snap_id = snapshot(plan_dir)
    assert snap_id is not None

    # mutate
    mutated = dict(_initial_state())
    mutated["current_state"] = "planned"
    mutated["iteration"] = 7
    write_plan_state(plan_dir, mode="replace", state=mutated)
    on_disk = json.loads((plan_dir / "state.json").read_text())
    assert on_disk["current_state"] == "planned"

    # restore
    restored = restore(plan_dir, snap_id)
    assert restored["current_state"] == "initialized"
    assert restored["iteration"] == 1
    on_disk_after = json.loads((plan_dir / "state.json").read_text())
    assert on_disk_after["current_state"] == "initialized"
    assert on_disk_after["iteration"] == 1


def test_restore_missing_snapshot_raises(plan_dir):
    write_plan_state(plan_dir, mode="replace", state=_initial_state())
    from megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        restore(plan_dir, "deadbeef" * 4)
    assert exc_info.value.code == "missing_snapshot"


def test_snapshot_uses_plan_state_lock(plan_dir, tmp_path):
    # take a snapshot then assert the lock file exists alongside the plan
    # (proves plan_state_lock() ran)
    write_plan_state(plan_dir, mode="replace", state=_initial_state())
    snapshot(plan_dir)
    assert plan_state_lock_path(plan_dir).exists()


# ---------------------------------------------------------------------------
# restorable_boundary
# ---------------------------------------------------------------------------


def test_restorable_boundary_no_op_default():
    # no substrate pinned, no fanout active -> entering is fine
    from megaplan.drivers import reset_substrate

    reset_substrate()
    with restorable_boundary("op_a"):
        pass


def test_restorable_boundary_raises_under_subprocess_isolated(monkeypatch):
    import megaplan.drivers as drivers

    # bypass select_driver's flag gate by pinning the substrate directly
    drivers.reset_substrate()
    monkeypatch.setattr(drivers, "_current_substrate", "subprocess_isolated")
    try:
        with pytest.raises(RestorableBoundaryViolation) as exc_info:
            with restorable_boundary("op_b"):
                pass
        assert "op_b" in str(exc_info.value)
        assert "subprocess_isolated" in str(exc_info.value)
    finally:
        drivers.reset_substrate()


def test_restorable_boundary_raises_under_active_fanout():
    from megaplan._pipeline.envelope import _fanout_active_ctx
    from megaplan.drivers import reset_substrate

    reset_substrate()
    token = _fanout_active_ctx.set(True)
    try:
        with pytest.raises(RestorableBoundaryViolation) as exc_info:
            with restorable_boundary("op_c"):
                pass
        assert "op_c" in str(exc_info.value)
        assert "fanout_active=True" in str(exc_info.value)
    finally:
        _fanout_active_ctx.reset(token)


def test_restorable_boundary_in_process_substrate_ok(monkeypatch):
    import megaplan.drivers as drivers

    drivers.reset_substrate()
    monkeypatch.setattr(drivers, "_current_substrate", "in_process")
    try:
        with restorable_boundary("op_d"):
            pass
    finally:
        drivers.reset_substrate()


def test_restorable_boundary_check_precedes_body():
    """The boundary error MUST be raised at ``__enter__`` time, before
    the protected body runs. This pins the ordering invariant: the
    Governor's BudgetExceeded (raised inside the body) can only fire if
    the boundary check passed first."""
    import megaplan.drivers as drivers

    drivers._current_substrate = "subprocess_isolated"
    body_ran = False
    try:
        with pytest.raises(RestorableBoundaryViolation):
            with restorable_boundary("op_e"):
                nonlocal_marker = True  # noqa: F841
                body_ran = True  # pragma: no cover
        assert body_ran is False
    finally:
        drivers.reset_substrate()
