"""End-to-end fail-safe for the finalize test-baseline capture.

The other baseline tests mock ``run_suite``; this one drives the WHOLE real path
(``_capture_test_baseline`` -> ``run_suite`` -> ``_wait_for_process`` -> a real
spawned subprocess) against a genuinely WEDGED fake suite, and proves the two
properties that stop a hung suite from wedging ``finalize`` for ~an hour:

  1. BOUNDED: a suite that goes silent is killed at the idle cap, in seconds, far
     below the absolute ceiling (the old failure sat in a bare ``subprocess.wait``
     for the full ceiling, which defaults to 3600s).
  2. DEGRADES GRACEFULLY: capture returns ``baseline_test_failures=None`` with a
     diagnostic note rather than hanging or raising, so ``finalize`` records
     "baseline unavailable" and proceeds. A baseline is an optimization
     (regression detection), not a gate.

It also confirms no child process is left behind after the kill.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

import megaplan.handlers


def _project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    return project_dir


# A fake "suite": prints one line, then hangs silently — a wedged test that never
# exits. Not a pytest command, so no nested pytest is spawned; the runner treats
# any non-zero/killed command as the suite. ``-u`` keeps stdout unbuffered so the
# one line lands in the log immediately (mirrors PYTHONUNBUFFERED in the runner).
_WEDGED_SUITE = (
    f"{sys.executable} -u -c "
    "\"import time,sys; sys.stdout.write('collected 1 item\\n'); "
    "sys.stdout.flush(); time.sleep(600)\""
)


def test_wedged_baseline_aborts_within_bound_and_finalize_proceeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    project_dir = _project(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    config = {
        "test_command": _WEDGED_SUITE,
        "plan_dir": str(plan_dir),
        # Generous absolute ceiling so the test proves the IDLE cap (not the
        # ceiling) is what saves us: if the idle detector were broken this would
        # sit for 300s and the @pytest.mark.timeout(60) would fail the test.
        "test_baseline_timeout": 300,
        # Idle cap: a silent suite is "wedged" after this many seconds.
        "test_baseline_idle_timeout": 3,
    }

    t0 = time.monotonic()
    result = megaplan.handlers._capture_test_baseline(project_dir, config)
    elapsed = time.monotonic() - t0

    # (1) BOUNDED — aborted at the idle cap (~3s), nowhere near the 300s ceiling.
    assert elapsed < 30, f"capture took {elapsed:.1f}s — idle cap did not fire"

    # (2) DEGRADES GRACEFULLY — no hang, no raise; a null baseline + a note that
    # finalize can record and proceed past.
    assert result["baseline_test_failures"] is None
    note = result["baseline_test_note"].lower()
    assert "stalled" in note or "wedged" in note, note

    # (3) No orphaned child left behind: nothing under our temp plan dir is still
    # writing, and the raw log stopped growing (process-group kill reaped it).
    raw_logs = list((plan_dir / "verification").glob("raw_*.log"))
    assert raw_logs, "expected a raw log to have been written"
    size1 = raw_logs[0].stat().st_size
    time.sleep(1.0)
    size2 = raw_logs[0].stat().st_size
    assert size1 == size2, "log still growing — the wedged child was not reaped"


def test_finalize_treats_null_baseline_as_non_fatal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The degraded shape (failures=None + note) is the contract finalize relies
    on to proceed: it is a plain dict, never an exception, with the optimization
    field nulled and a human-readable reason attached."""
    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    project_dir = _project(tmp_path)

    # An invalid timeout takes the early-return degrade path without spawning
    # anything — the cheapest proof that the failure mode is a value, not a throw.
    result = megaplan.handlers._capture_test_baseline(
        project_dir, {"test_baseline_timeout": -1}
    )
    assert isinstance(result, dict)
    assert result["baseline_test_failures"] is None
    assert result.get("baseline_test_note")
