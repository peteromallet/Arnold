"""Falsification test: every wrong-but-faithful fixture must ALLOW through the refusal spine.

Marked with the ``comfy`` marker — requires the pinned ``[comfy]`` optional
dependency and VIBECOMFY_COMFY_SMOKE=1 to run.

Run:
    VIBECOMFY_COMFY_SMOKE=1 pytest -m comfy tests/intent/test_falsification.py
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.comfy

_FIXTURE_ROOT = Path(__file__).parent / "fixtures"
_FAMILIES = ("image", "edit", "video")


def _all_fixtures() -> list[Path]:
    return sorted(
        Path(p)
        for p in glob.glob(str(_FIXTURE_ROOT / "*" / "*.json"))
        if Path(p).parent.name in _FAMILIES
    )


def test_fixture_count_and_family_distribution():
    """Exactly 15 fixtures, 5 per family — verified before any spine probe."""
    fixtures = _all_fixtures()
    assert len(fixtures) == 15, f"Expected 15 fixtures, got {len(fixtures)}: {fixtures}"
    for family in _FAMILIES:
        family_fixtures = [f for f in fixtures if f.parent.name == family]
        assert len(family_fixtures) == 5, (
            f"Expected 5 fixtures for family '{family}', got {len(family_fixtures)}"
        )


@pytest.mark.parametrize("fixture_path", _all_fixtures(), ids=lambda p: p.stem)
def test_refusal_spine_allows_wrong_but_faithful(fixture_path: Path):
    """probe_refusal_spine must return ALLOW for every fixture in the corpus."""
    from vibecomfy.intent._fixture import load_fixture
    from vibecomfy.intent._refusal_spine_probe import probe_refusal_spine

    fixture = load_fixture(fixture_path)
    verdict = probe_refusal_spine(fixture.pre_ui, fixture.post_ui, fixture.intended_delta)
    assert verdict == "ALLOW", (
        f"Fixture {fixture.id!r} got {verdict!r} — intended_delta may not match "
        f"what the oracle sees as changed."
    )
