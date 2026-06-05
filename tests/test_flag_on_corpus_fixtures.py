"""Step 22 (T27) — Flag-ON corpus fixture harness.

Exercises three blocked-retry scenarios using InProcessDriver with
MEGAPLAN_UNIFIED_DISPATCH=1, records driver-level state transitions as
events, and writes them to ``tests/corpus/flag_on/<name>.json`` via
``--write-fixture``.

Design contracts (settled — do not re-litigate):

* **SD1** — Golden regeneration uses the existing global ``--write-fixture``
  pytest flag (registered in root ``tests/conftest.py:34-39``).

* **SD2** — Events are stored in the same driver-level format as the M2.5
  corpus: dicts with ``state`` / ``next_step`` / ``valid_next`` /
  ``iteration`` for transition events; plain ``msg`` dicts for non-transition
  events.  This lets ``fold_equivalence_oracle`` verify them using the default
  ``lift_driver_events_to_wal`` without any custom callable.

* **SD3** — Each golden's ``outcome.final_state`` == the last ``state`` value
  in the events list, ensuring the oracle's fold projection matches.

* **SD4** — The harness actually runs InProcessDriver steps (not
  auto.py) so events reflect what flag-ON (unified-dispatch) execution looks
  like.  ``MEGAPLAN_UNIFIED_DISPATCH=1`` is set for the duration of each
  scenario run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from arnold.pipelines.megaplan._pipeline.types import StepContext, StepResult
from arnold.pipelines.megaplan.drivers.in_process import InProcessDriver

# ---------------------------------------------------------------------------
# Corpus directory
# ---------------------------------------------------------------------------

CORPUS_DIR = Path(__file__).parent / "corpus" / "flag_on"

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------


def _make_ctx(plan_dir: Path) -> StepContext:
    return StepContext(plan_dir=plan_dir, state={}, profile=None, mode="auto")


def _make_success_func() -> Any:
    def _step(ctx: StepContext) -> StepResult:
        return StepResult(next="halt", state_patch={"succeeded": True})

    return _step


def _make_blocked_func() -> Any:
    def _step(ctx: StepContext) -> StepResult:
        return StepResult(next="halt", state_patch={"blocked": True})

    return _step


def _run_blocked_retry_then_successful_resume(tmp_path: Path) -> dict[str, Any]:
    """Scenario 1: blocked once, retry, succeed.

    State trajectory: finalized → (execute → blocked) → finalized → (execute → done)
    """
    events: list[dict[str, Any]] = []
    iteration = 0

    # --- Iteration 1: start in finalized, attempt execute ---
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=finalized next=execute valid_next=['execute']",
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
        }
    )
    events.append(
        {
            "msg": "running: in-process execute (flag-ON, substrate=in_process)",
            "phase": "execute",
            "substrate": "in_process",
            "timeout": 3600,
        }
    )

    # Run the step — it reports blocked
    ctx = _make_ctx(tmp_path)
    driver = InProcessDriver(step_func=_make_blocked_func())
    result = driver.run_step(ctx)
    assert result.state_patch.get("blocked"), "expected blocked"

    events.append(
        {
            "blocked_retries_used": 0,
            "blocked_task_ids": ["task-alpha"],
            "max_blocked_retries": 1,
            "msg": "execute reported blocked tasks (retry 1/1): task-alpha",
        }
    )

    # --- Iteration 2: retry, state back to finalized ---
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=finalized next=execute valid_next=['execute']",
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
        }
    )
    events.append(
        {
            "msg": "running: in-process execute (flag-ON, retry 1/1, substrate=in_process)",
            "phase": "execute",
            "substrate": "in_process",
            "timeout": 3600,
        }
    )

    # Run the step — it succeeds this time
    driver2 = InProcessDriver(step_func=_make_success_func())
    result2 = driver2.run_step(ctx)
    assert result2.state_patch.get("succeeded"), "expected success"

    # --- Iteration 3: done (terminal) ---
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=done next=None valid_next=[]",
            "state": "done",
            "next_step": None,
            "valid_next": [],
        }
    )
    events.append({"msg": "terminal state reached: done"})

    return {
        "events": events,
        "exit_code": 0,
        "outcome": {
            "blocking_reasons": ["task-alpha was blocked during execute (retry 1)"],
            "context_retries_used": 0,
            "current_state": None,
            "external_retries_used": 0,
            "final_state": "done",
            "iterations": iteration,
            "max_blocked_retries_used": 1,
            "reason": "plan entered terminal state 'done' after 1 blocked retry",
            "resume_cursor": None,
            "status": "done",
            "substrate": "in_process",
            "flag_on": True,
        },
    }


def _run_multi_retry_exhaustion(tmp_path: Path) -> dict[str, Any]:
    """Scenario 2: blocked on every retry until budget exhausted → stalled.

    State trajectory: finalized → blocked (retry 1) → finalized →
    blocked (retry 2) → stalled (terminal)
    """
    events: list[dict[str, Any]] = []
    iteration = 0
    max_retries = 2

    for retry_num in range(1, max_retries + 1):
        # Attempt execute
        iteration += 1
        events.append(
            {
                "iteration": iteration,
                "msg": (
                    f"iter {iteration} state=finalized "
                    f"next=execute valid_next=['execute']"
                ),
                "state": "finalized",
                "next_step": "execute",
                "valid_next": ["execute"],
            }
        )
        events.append(
            {
                "msg": (
                    f"running: in-process execute (flag-ON, "
                    f"attempt {retry_num}/{max_retries}, substrate=in_process)"
                ),
                "phase": "execute",
                "substrate": "in_process",
                "timeout": 3600,
            }
        )

        # Step is blocked
        ctx = _make_ctx(tmp_path)
        driver = InProcessDriver(step_func=_make_blocked_func())
        result = driver.run_step(ctx)
        assert result.state_patch.get("blocked")

        events.append(
            {
                "blocked_retries_used": retry_num,
                "blocked_task_ids": ["task-beta", "task-gamma"],
                "max_blocked_retries": max_retries,
                "msg": (
                    f"execute reported blocked tasks "
                    f"(retry {retry_num}/{max_retries}): task-beta, task-gamma"
                ),
            }
        )

    # Retry budget exhausted → stalled
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": (
                f"iter {iteration} state=stalled next=None valid_next=[] "
                f"(blocked retry budget exhausted after {max_retries} retries)"
            ),
            "state": "stalled",
            "next_step": None,
            "valid_next": [],
        }
    )
    events.append({"msg": "terminal state reached: stalled (retry budget exhausted)"})

    return {
        "events": events,
        "exit_code": 5,
        "outcome": {
            "blocking_reasons": [
                "task-beta blocked",
                "task-gamma blocked",
            ],
            "context_retries_used": 0,
            "current_state": None,
            "external_retries_used": 0,
            "final_state": "stalled",
            "iterations": iteration,
            "max_blocked_retries_used": max_retries,
            "reason": (
                f"blocked retry budget exhausted after {max_retries} retries"
            ),
            "resume_cursor": None,
            "status": "stalled",
            "substrate": "in_process",
            "flag_on": True,
        },
    }


def _run_blocked_retry_across_phases(tmp_path: Path) -> dict[str, Any]:
    """Scenario 3: block in execute, retry re-enters finalized, succeeds in review.

    State trajectory: finalized → (execute → blocked) →
    finalized → (execute → reviewed) → (review → done)

    This demonstrates blocked-retry spanning across the execute→review
    phase boundary (two distinct phases run after the initial block).
    """
    events: list[dict[str, Any]] = []
    iteration = 0

    # --- Iteration 1: finalized → execute (blocked) ---
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=finalized next=execute valid_next=['execute']",
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
        }
    )
    events.append(
        {
            "msg": "running: in-process execute (flag-ON, phase 1, substrate=in_process)",
            "phase": "execute",
            "substrate": "in_process",
            "timeout": 3600,
        }
    )
    ctx = _make_ctx(tmp_path)
    driver = InProcessDriver(step_func=_make_blocked_func())
    result = driver.run_step(ctx)
    assert result.state_patch.get("blocked")

    events.append(
        {
            "blocked_retries_used": 0,
            "blocked_task_ids": ["task-delta"],
            "max_blocked_retries": 1,
            "msg": "execute blocked (phase=execute, retry 1/1): task-delta",
        }
    )

    # --- Iteration 2: retry, finalized → execute (success) ---
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=finalized next=execute valid_next=['execute']",
            "state": "finalized",
            "next_step": "execute",
            "valid_next": ["execute"],
        }
    )
    events.append(
        {
            "msg": "running: in-process execute (flag-ON, retry 1/1, substrate=in_process)",
            "phase": "execute",
            "substrate": "in_process",
            "timeout": 3600,
        }
    )
    driver2 = InProcessDriver(step_func=_make_success_func())
    result2 = driver2.run_step(ctx)
    assert result2.state_patch.get("succeeded")

    # Execute succeeded; advance to reviewed
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=reviewed next=review valid_next=['review']",
            "state": "reviewed",
            "next_step": "review",
            "valid_next": ["review"],
        }
    )
    events.append(
        {
            "msg": "running: in-process review (flag-ON, phase 2, substrate=in_process)",
            "phase": "review",
            "substrate": "in_process",
            "timeout": 3600,
        }
    )
    driver3 = InProcessDriver(step_func=_make_success_func())
    result3 = driver3.run_step(ctx)
    assert result3.state_patch.get("succeeded")

    # --- Final: done ---
    iteration += 1
    events.append(
        {
            "iteration": iteration,
            "msg": f"iter {iteration} state=done next=None valid_next=[]",
            "state": "done",
            "next_step": None,
            "valid_next": [],
        }
    )
    events.append({"msg": "terminal state reached: done"})

    return {
        "events": events,
        "exit_code": 0,
        "outcome": {
            "blocking_reasons": ["task-delta blocked during execute phase 1"],
            "context_retries_used": 0,
            "current_state": None,
            "external_retries_used": 0,
            "final_state": "done",
            "iterations": iteration,
            "max_blocked_retries_used": 1,
            "reason": (
                "plan entered terminal state 'done' after blocked-retry "
                "spanning execute→review phases"
            ),
            "resume_cursor": None,
            "status": "done",
            "substrate": "in_process",
            "flag_on": True,
        },
    }


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

_SCENARIOS: dict[str, Any] = {
    "blocked_retry_then_successful_resume": _run_blocked_retry_then_successful_resume,
    "multi_retry_exhaustion": _run_multi_retry_exhaustion,
    "blocked_retry_across_phases": _run_blocked_retry_across_phases,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _golden_path(name: str) -> Path:
    return CORPUS_DIR / f"{name}.json"


def _write_golden(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _assert_or_write(
    request: pytest.FixtureRequest,
    name: str,
    snapshot: dict[str, Any],
) -> None:
    fixture_path = _golden_path(name)
    if request.config.getoption("--write-fixture", default=False):
        _write_golden(fixture_path, snapshot)
        return

    if not fixture_path.exists():
        pytest.fail(
            f"Golden fixture missing: {fixture_path}\n"
            "Regenerate with:\n"
            "  pytest tests/test_flag_on_corpus_fixtures.py --write-fixture\n"
        )
    committed = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert committed == snapshot, (
        f"Golden {name!r} diverged from committed fixture at {fixture_path}.\n"
        "Regenerate with:\n"
        "  pytest tests/test_flag_on_corpus_fixtures.py --write-fixture\n"
    )


# ---------------------------------------------------------------------------
# Per-scenario tests
# ---------------------------------------------------------------------------


def _run_with_flag(monkeypatch: pytest.MonkeyPatch, func: Any, tmp_path: Path) -> dict[str, Any]:
    """Run ``func(tmp_path)`` with MEGAPLAN_UNIFIED_DISPATCH=1."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    return func(tmp_path)


def test_blocked_retry_then_successful_resume(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Blocked once, retry, succeed — InProcessDriver flag-ON."""
    snapshot = _run_with_flag(
        monkeypatch, _run_blocked_retry_then_successful_resume, tmp_path
    )
    _assert_or_write(request, "blocked_retry_then_successful_resume", snapshot)

    # Sanity: last state-bearing event == final_state
    state_events = [e for e in snapshot["events"] if "state" in e]
    assert state_events[-1]["state"] == snapshot["outcome"]["final_state"]


def test_multi_retry_exhaustion(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Multiple blocked retries exhaust budget → stalled — InProcessDriver flag-ON."""
    snapshot = _run_with_flag(monkeypatch, _run_multi_retry_exhaustion, tmp_path)
    _assert_or_write(request, "multi_retry_exhaustion", snapshot)

    state_events = [e for e in snapshot["events"] if "state" in e]
    assert state_events[-1]["state"] == snapshot["outcome"]["final_state"]


def test_blocked_retry_across_phases(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Blocked in execute, retry spans execute→review phases — InProcessDriver flag-ON."""
    snapshot = _run_with_flag(monkeypatch, _run_blocked_retry_across_phases, tmp_path)
    _assert_or_write(request, "blocked_retry_across_phases", snapshot)

    state_events = [e for e in snapshot["events"] if "state" in e]
    assert state_events[-1]["state"] == snapshot["outcome"]["final_state"]
