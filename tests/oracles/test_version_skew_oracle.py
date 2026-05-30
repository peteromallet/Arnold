"""Version-skew oracle (T29 / hinge-gate done-criterion).

Pins the byte-stability contract for crossing the M3 driver-version boundary:
``megaplan/_legacy_subprocess/`` (version A, the hermetic snapshot of the
auto.py watcher block) and ``InProcessDriver`` under
``MEGAPLAN_UNIFIED_DISPATCH=1`` (version B, the new in-process driver) MUST
agree on the on-disk plan state — ``state.json``, ``cursor``, ``lineage`` —
when a run is killed mid-blocked-retry under one version and resumed under
the other.

Both directions are exercised:

* **A → B**: launch the worker under ``legacy_supervise_subprocess`` with an
  idle timeout that fires mid-blocked-retry (one retry written + a long
  sleep), confirm ``PHASE_TIMEOUT_EXIT_CODE`` + ``kill_group`` fires, then
  resume the same plan_dir under the in-process driver flag-ON.

* **B → A**: launch the worker under the in-process driver flag-ON, simulate
  a kill at the same mid-blocked-retry checkpoint, then resume under
  ``legacy_supervise_subprocess`` until natural completion.

Both directions MUST yield ``state.json`` byte-identical to a pure-B
baseline run from the initial state.

Marked ``hinge_gate`` so the chain-CI selector picks it up alongside the
crash-isolation oracle (T28), the workflow-topology parity gate (T10), the
R1 authority-flip suite (T25), and the fold-equivalence oracle (T26) as a
hinge-gate done-criterion: red here auto-halts the hinge gate.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

import megaplan._legacy_subprocess as legacy
from megaplan._legacy_subprocess import (
    PHASE_TIMEOUT_EXIT_CODE,
    legacy_supervise_subprocess,
)
from megaplan._pipeline.flags import unified_dispatch_on
from megaplan._pipeline.types import StepContext, StepResult
from megaplan.drivers.in_process import InProcessDriver


pytestmark = pytest.mark.hinge_gate


# ---------------------------------------------------------------------------
# Worker — shared on-disk state machine.
#
# State shape (pinned, sorted-key JSON, indent=2):
#   {
#     "cursor": int,            # phase index completed (0..phases_total)
#     "lineage": [str, ...],    # append-only audit trail
#     "phases_total": int,
#     "retries_target": int,    # blocked-retry budget for phase 1
#     "retries_used": int,
#   }
#
# Mutation semantics (must be byte-identical across A and B):
#   - "one_retry_then_sleep": increment retries_used by 1, append
#       f"retry@step{cursor}", atomically rewrite state.json, then sleep so
#       the supervising version kills us mid-blocked-retry.
#   - "complete": drain remaining retries (each writes), then drain remaining
#       phases (each advances cursor and appends f"phase{cursor}").
#
# Both A and B drive the SAME mutation routine. A invokes it via
# legacy_supervise_subprocess spawning the worker script; B invokes it via
# InProcessDriver calling _worker_complete / _worker_one_retry_then_sleep.
# ---------------------------------------------------------------------------


WORKER_SCRIPT = textwrap.dedent(
    """
    import json, sys, time
    from pathlib import Path

    plan_dir = Path(sys.argv[1])
    mode = sys.argv[2]
    sf = plan_dir / "state.json"

    def _read():
        return json.loads(sf.read_text())

    def _write(state):
        # Atomic-ish rewrite; sort_keys + indent=2 pin the byte layout.
        tmp = sf.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True, indent=2))
        tmp.replace(sf)

    state = _read()
    if mode == "one_retry_then_sleep":
        if state["retries_used"] < state["retries_target"]:
            state["retries_used"] += 1
            state["lineage"].append("retry@step{}".format(state["cursor"]))
            _write(state)
        # Idle-sleep so the legacy supervisor's idle_timeout fires.
        time.sleep(60)
    elif mode == "complete":
        while state["retries_used"] < state["retries_target"]:
            state["retries_used"] += 1
            state["lineage"].append("retry@step{}".format(state["cursor"]))
            _write(state)
        while state["cursor"] < state["phases_total"]:
            state["cursor"] += 1
            state["lineage"].append("phase{}".format(state["cursor"]))
            _write(state)
    else:
        raise SystemExit("unknown mode: " + mode)
    """
).strip()


# Mirror of the worker mutation routine for the in-process driver.
def _state_path(plan_dir: Path) -> Path:
    return plan_dir / "state.json"


def _read_state(plan_dir: Path) -> dict[str, Any]:
    return json.loads(_state_path(plan_dir).read_text())


def _write_state(plan_dir: Path, state: dict[str, Any]) -> None:
    sf = _state_path(plan_dir)
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=2))
    tmp.replace(sf)


def _worker_one_retry_then_sleep(plan_dir: Path) -> None:
    state = _read_state(plan_dir)
    if state["retries_used"] < state["retries_target"]:
        state["retries_used"] += 1
        state["lineage"].append("retry@step{}".format(state["cursor"]))
        _write_state(plan_dir, state)


def _worker_complete(plan_dir: Path) -> None:
    state = _read_state(plan_dir)
    while state["retries_used"] < state["retries_target"]:
        state["retries_used"] += 1
        state["lineage"].append("retry@step{}".format(state["cursor"]))
        _write_state(plan_dir, state)
    while state["cursor"] < state["phases_total"]:
        state["cursor"] += 1
        state["lineage"].append("phase{}".format(state["cursor"]))
        _write_state(plan_dir, state)


INITIAL_STATE: dict[str, Any] = {
    "cursor": 0,
    "lineage": [],
    "phases_total": 3,
    "retries_target": 2,
    "retries_used": 0,
}


def _seed(plan_dir: Path) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    _write_state(plan_dir, dict(INITIAL_STATE, lineage=list(INITIAL_STATE["lineage"])))


def _write_worker(tmp_path: Path) -> Path:
    worker = tmp_path / "_version_skew_worker.py"
    worker.write_text(WORKER_SCRIPT)
    return worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_spawn_to_worker(
    monkeypatch: pytest.MonkeyPatch, worker: Path, plan_dir: Path, mode: str
) -> None:
    """Redirect ``megaplan._legacy_subprocess.spawn`` so the legacy supervisor
    runs OUR worker script instead of ``python -m megaplan``.

    The legacy watcher loop (timeout / idle_timeout / kill_group / heartbeat)
    is exercised verbatim; only the spawned argv changes.
    """
    real_spawn = legacy.spawn

    def _redirected(argv: list[str], **kw: Any) -> Any:  # noqa: ANN401
        new_argv = [sys.executable, str(worker), str(plan_dir), mode]
        return real_spawn(new_argv, **kw)

    monkeypatch.setattr(legacy, "spawn", _redirected)


def _baseline_pure_b(tmp_path: Path) -> bytes:
    """Pure-B baseline: in-process driver runs the worker straight through
    from INITIAL_STATE. The returned bytes are the byte-stable target every
    crossing direction must match."""
    plan_dir = tmp_path / "baseline"
    _seed(plan_dir)

    def step(ctx: StepContext) -> StepResult:
        _worker_complete(ctx.plan_dir)
        return StepResult(next="halt")

    InProcessDriver(step_func=step).run_step(
        StepContext(plan_dir=plan_dir, state={}, profile=None, mode="auto")
    )
    return _state_path(plan_dir).read_bytes()


# ---------------------------------------------------------------------------
# Direction 1: A → B  (start via legacy_supervise_subprocess, resume in-process)
# ---------------------------------------------------------------------------


def test_a_to_b_resume_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "a_to_b"
    _seed(plan_dir)
    worker = _write_worker(tmp_path)
    _patch_spawn_to_worker(monkeypatch, worker, plan_dir, "one_retry_then_sleep")

    # --- Version A: legacy supervisor runs the worker until idle-killed
    # mid-blocked-retry. The worker writes ONE retry then sleeps; idle_timeout
    # fires, kill_group reaps, exit_code == PHASE_TIMEOUT_EXIT_CODE.
    t0 = time.monotonic()
    rc, _stdout, stderr = legacy_supervise_subprocess(
        ["ignored-arg"],
        cwd=plan_dir,
        idle_timeout=1.0,
        timeout=15.0,
        liveness_plan_dir=plan_dir,
    )
    elapsed = time.monotonic() - t0
    assert rc == PHASE_TIMEOUT_EXIT_CODE, (rc, stderr)
    assert elapsed < 10.0, "idle_timeout must fire before wall timeout"
    assert "idle timed out" in stderr

    # Mid-flight checkpoint: exactly one retry recorded, cursor not advanced.
    mid_state = _read_state(plan_dir)
    assert mid_state["retries_used"] == 1
    assert mid_state["cursor"] == 0
    assert mid_state["lineage"] == ["retry@step0"]

    # --- Version B: in-process driver flag-ON resumes from the partial state.
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    assert unified_dispatch_on()

    def step(ctx: StepContext) -> StepResult:
        _worker_complete(ctx.plan_dir)
        return StepResult(next="halt")

    InProcessDriver(step_func=step).run_step(
        StepContext(plan_dir=plan_dir, state={}, profile=None, mode="auto")
    )

    # Byte-stable vs pure-B baseline.
    baseline = _baseline_pure_b(tmp_path)
    assert _state_path(plan_dir).read_bytes() == baseline


# ---------------------------------------------------------------------------
# Direction 2: B → A  (start under in-process flag-ON, resume via legacy)
# ---------------------------------------------------------------------------


def test_b_to_a_resume_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_dir = tmp_path / "b_to_a"
    _seed(plan_dir)

    # --- Version B: in-process driver writes ONE retry (mid-blocked-retry
    # checkpoint), then "stops" — we model the kill by simply not invoking
    # _worker_complete. The in-process driver has no kill-group: stopping
    # is a deliberate return.
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    assert unified_dispatch_on()

    def step_partial(ctx: StepContext) -> StepResult:
        _worker_one_retry_then_sleep(ctx.plan_dir)
        return StepResult(next="halt")

    InProcessDriver(step_func=step_partial).run_step(
        StepContext(plan_dir=plan_dir, state={}, profile=None, mode="auto")
    )

    mid_state = _read_state(plan_dir)
    assert mid_state["retries_used"] == 1
    assert mid_state["cursor"] == 0
    assert mid_state["lineage"] == ["retry@step0"]

    # Take flag back OFF for the version-A leg so we can prove the resume
    # path does not depend on MEGAPLAN_UNIFIED_DISPATCH being set.
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    assert not unified_dispatch_on()

    # --- Version A: legacy supervisor resumes the same plan_dir under
    # mode=complete; the worker drains remaining retries + phases then exits
    # naturally (no timeout, no kill_group).
    worker = _write_worker(tmp_path)
    _patch_spawn_to_worker(monkeypatch, worker, plan_dir, "complete")
    rc, _stdout, stderr = legacy_supervise_subprocess(
        ["ignored-arg"],
        cwd=plan_dir,
        idle_timeout=10.0,
        timeout=20.0,
        liveness_plan_dir=plan_dir,
    )
    assert rc == 0, (rc, stderr)

    baseline = _baseline_pure_b(tmp_path)
    assert _state_path(plan_dir).read_bytes() == baseline


# ---------------------------------------------------------------------------
# Sanity: baseline is itself byte-stable across two pure-B runs.
# ---------------------------------------------------------------------------


def test_pure_b_baseline_is_deterministic(tmp_path: Path) -> None:
    a = _baseline_pure_b(tmp_path / "a")
    b = _baseline_pure_b(tmp_path / "b")
    assert a == b
    # And carries the expected final shape.
    final = json.loads(a.decode("utf-8"))
    assert final["cursor"] == INITIAL_STATE["phases_total"]
    assert final["retries_used"] == INITIAL_STATE["retries_target"]
    assert final["lineage"] == [
        "retry@step0",
        "retry@step0",
        "phase1",
        "phase2",
        "phase3",
    ]
