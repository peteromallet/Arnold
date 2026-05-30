"""Live calibration test for the text + vision judge panel.

Runs the full text+vision panel against the 6 calibration fixtures and asserts
that the 3 known-correct edits receive PASS and the 3 known-wrong edits receive FAIL.

This test requires a real Anthropic API key (ANTHROPIC_API_KEY env var) and is
intentionally NOT part of the CI suite.  Gate it behind the existing `runpod`
marker so it only runs in the full GPU / API-key environment:

    pytest -m runpod tests/intent/smoke/test_judge_calibration.py

CI invocation (skipped automatically when API key is absent):
    pytest -m "not runpod" tests/intent/  # skips this file
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.intent._fixture import load_fixture
from vibecomfy.intent.judge import judge_text, judge_vision, panel_verdict

pytestmark = pytest.mark.runpod

_CAL_DIR = Path(__file__).parent.parent / "fixtures" / "calibration"

_FIXTURES = sorted(_CAL_DIR.glob("*.json"))


def _load_all():
    return [load_fixture(p) for p in _FIXTURES]


@pytest.fixture(scope="module")
def calibration_fixtures():
    fxs = _load_all()
    assert len(fxs) == 6, f"Expected 6 calibration fixtures, got {len(fxs)}"
    return fxs


@pytest.mark.parametrize("fixture_path", _FIXTURES, ids=lambda p: p.stem)
def test_calibration_panel(fixture_path):
    """Run the full text+vision panel and assert expected verdict."""
    fx = load_fixture(fixture_path)

    text_v = judge_text(fx.pre_ui, fx.post_ui, fx.nl_intent)
    vision_v = judge_vision([], [], fx.nl_intent)
    pv = panel_verdict(text_v, vision_v)

    expected_pass = fx.expected_text_judge_verdict == "PASS"
    assert pv.pass_ == expected_pass, (
        f"[{fx.id}] expected panel_verdict.pass_={expected_pass}, "
        f"got {pv.pass_}.\n"
        f"  text: pass_={text_v.pass_}, criteria={text_v.criteria}, rationale={text_v.rationale!r}\n"
        f"  vision: pass_={vision_v.pass_}, criteria={vision_v.criteria}"
    )
