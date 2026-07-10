"""Full live text+vision panel smoke test for edit_correctness — GPU only.

Marked ``runpod``.  Excluded from CI (pytest -m intent_ci tests/intent).

Runs the full live text+vision judge panel against ≥1 fixture per family
end-to-end on GPU using real ComfyUI execution and real Anthropic API calls.
Requires ANTHROPIC_API_KEY and a provisioned RunPod pod with ComfyUI installed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.intent import edit_correctness, load_fixture

pytestmark = pytest.mark.runpod

_FIXTURES_ROOT = Path(__file__).parent.parent / "fixtures"
_FAMILIES = ("image", "edit", "video")


@pytest.mark.runpod
@pytest.mark.parametrize("family", _FAMILIES)
def test_edit_correctness_full_panel_wrong_but_faithful(family: str) -> None:
    """edit_correctness with embedded runtime must report fraction < 1.0 for wrong-but-faithful fixtures.

    Takes the first fixture per family only to minimise GPU cost per run.
    Uses the real text+vision judge panel (no stubs) — requires Anthropic API key.
    """
    fixture_paths = sorted((_FIXTURES_ROOT / family).glob("*.json"))
    assert fixture_paths, f"No fixtures found for family {family!r}"

    # ≥1 fixture per family; take first to keep GPU cost bounded
    fixtures = [load_fixture(fixture_paths[0])]

    report = edit_correctness(
        fixtures,
        family=family,
        runtime="embedded",
    )

    # All fixtures are wrong-but-faithful so the judge should return FAIL (pass_=False)
    assert report.fraction < 1.0, (
        f"family={family!r}: live panel should detect wrong-but-faithful edits "
        f"but got fraction={report.fraction} ({report.passed}/{report.total} passed)"
    )
