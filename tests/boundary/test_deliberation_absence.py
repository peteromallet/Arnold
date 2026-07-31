"""Retirement gate for the deleted deliberation pipeline."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_deliberation_pipeline_remains_absent() -> None:
    """The retired package and its source tree must not silently return."""
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "arnold" / "pipelines" / "deliberation").exists()
    assert importlib.util.find_spec("arnold.pipelines.deliberation") is None
