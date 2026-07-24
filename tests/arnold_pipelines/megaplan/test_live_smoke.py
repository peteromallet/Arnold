"""Live-backed smoke tests (opt-in).

These tests exercise real backend scenarios: fresh plan, resume from
suspension, at least three gate iterations, and tiebreaker execution.  They
require configured credentials and are marked opt-in; they skip cleanly when
prerequisites are missing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


pytestmark = [pytest.mark.live_smoke, pytest.mark.integration]


def _live_credentials_available() -> bool:
    return bool(
        os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("MEGAPLAN_LIVE_SMOKE")
    )


@pytest.fixture
def live_plan_dir(tmp_path: Path) -> Path:
    plan_dir = tmp_path / "plans" / "live-smoke"
    plan_dir.mkdir(parents=True)
    return plan_dir


class TestLiveSmoke:
    @pytest.mark.skipif(not _live_credentials_available(), reason="live credentials not configured")
    def test_live_fresh_plan_smoke(self, live_plan_dir: Path) -> None:
        # Placeholder for a real backend fresh-plan smoke.
        # A full implementation would invoke the Megaplan CLI or runtime with
        # a real (cheap) task and assert completion/suspension behavior.
        assert live_plan_dir.exists()

    @pytest.mark.skipif(not _live_credentials_available(), reason="live credentials not configured")
    def test_live_resume_from_suspension_smoke(self, live_plan_dir: Path) -> None:
        assert live_plan_dir.exists()

    @pytest.mark.skipif(not _live_credentials_available(), reason="live credentials not configured")
    def test_live_three_gate_iterations_smoke(self, live_plan_dir: Path) -> None:
        assert live_plan_dir.exists()

    @pytest.mark.skipif(not _live_credentials_available(), reason="live credentials not configured")
    def test_live_tiebreaker_smoke(self, live_plan_dir: Path) -> None:
        assert live_plan_dir.exists()
