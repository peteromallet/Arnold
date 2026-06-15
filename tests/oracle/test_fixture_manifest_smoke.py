"""Smoke test for golden fixture manifest.

Verifies that all three golden pipeline fixtures exist on disk and
contain the expected top-level fields: scenario, state, artifact_filenames,
json_artifacts, and text_artifacts. The manifest test does NOT run the
pipeline — it only checks fixture structure.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

EXPECTED_FILES = [
    "pipeline_fresh_run.json",
    "pipeline_resume_after_finalize.json",
    "pipeline_iterate.json",
]

REQUIRED_TOP_KEYS = {
    "scenario",
    "state",
    "artifact_filenames",
    "json_artifacts",
    "text_artifacts",
}

REQUIRED_STATE_KEYS = {
    "current_state",
    "iteration",
    "history",
    "config",
}


def test_all_fixture_files_exist():
    """All three expected golden fixture files exist."""
    for filename in EXPECTED_FILES:
        path = FIXTURE_DIR / filename
        assert path.exists(), f"Missing fixture: {path}"


def test_fixtures_have_required_top_keys():
    """Every fixture has the required top-level keys."""
    for filename in EXPECTED_FILES:
        path = FIXTURE_DIR / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = REQUIRED_TOP_KEYS - set(data.keys())
        assert not missing, f"{filename} missing top-level keys: {missing}"


def test_fixtures_have_required_state_keys():
    """Every fixture's state dict has the required keys."""
    for filename in EXPECTED_FILES:
        path = FIXTURE_DIR / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        state = data.get("state", {})
        missing = REQUIRED_STATE_KEYS - set(state.keys())
        assert not missing, f"{filename} state missing keys: {missing}"


def test_iterate_fixture_has_iterate_in_history():
    """The iterate fixture specifically captures an iterate gate recommendation."""
    path = FIXTURE_DIR / "pipeline_iterate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    history = data.get("state", {}).get("history", [])
    recommendations = [
        h.get("recommendation")
        for h in history
        if isinstance(h, dict) and h.get("recommendation")
    ]
    assert "ITERATE" in recommendations, (
        f"Expected ITERATE in history recommendations, got: {recommendations}"
    )


def test_fresh_and_iterate_have_different_scenarios():
    """Fresh and iterate fixtures use different scenario labels."""
    fresh = json.loads(
        (FIXTURE_DIR / "pipeline_fresh_run.json").read_text(encoding="utf-8")
    )
    iterate = json.loads(
        (FIXTURE_DIR / "pipeline_iterate.json").read_text(encoding="utf-8")
    )
    assert fresh["scenario"] == "fresh-run"
    assert iterate["scenario"] == "iterate"
    assert fresh["scenario"] != iterate["scenario"]


def test_fixture_state_fields_have_expected_types():
    """The three field-level comparisons match expected types."""
    for filename in EXPECTED_FILES:
        path = FIXTURE_DIR / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data.get("scenario"), str)
        assert isinstance(data.get("state"), dict)
        assert isinstance(data.get("artifact_filenames"), list)
        assert isinstance(data.get("json_artifacts"), dict)
        assert isinstance(data.get("text_artifacts"), dict)
