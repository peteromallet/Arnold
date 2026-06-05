"""T3 — State fixture corpus load-and-resume tests.

Three fixtures (v0_noversion, v1, v_future) each exercise a different
schema_version scenario; all must load via load_plan_from_dir without raising.
No companion events.ndjson is shipped — the W9 oracle (T7) generates the
matching event stream via round-trip.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._core.state import load_plan_from_dir

_FIXTURE_ROOT = Path(__file__).parent

FIXTURE_DIRS = [
    pytest.param(_FIXTURE_ROOT / "v0_noversion", id="v0_noversion"),
    pytest.param(_FIXTURE_ROOT / "v1", id="v1"),
    pytest.param(_FIXTURE_ROOT / "v_future", id="v_future"),
]


@pytest.mark.parametrize("fixture_dir", FIXTURE_DIRS)
def test_fixture_has_no_events_ndjson(fixture_dir: Path) -> None:
    """INPUT-STATE fixtures only — no companion events.ndjson."""
    assert not (fixture_dir / "events.ndjson").exists(), (
        f"{fixture_dir.name}/events.ndjson must not exist in M1 fixtures"
    )


@pytest.mark.parametrize("fixture_dir", FIXTURE_DIRS)
def test_load_and_resume(fixture_dir: Path, tmp_path: Path) -> None:
    """load_plan_from_dir succeeds for each fixture without ValidationError."""
    plan_dir = tmp_path / fixture_dir.name
    shutil.copytree(fixture_dir, plan_dir)

    plan_dir_out, state = load_plan_from_dir(plan_dir)

    assert plan_dir_out == plan_dir
    assert isinstance(state, dict)
    assert state.get("name"), "loaded state must have a non-empty name"
    assert "current_state" in state
