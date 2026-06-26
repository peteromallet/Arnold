"""Tests for the versioned-artifact helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan._pipeline.artifacts import (
    artifact_dir,
    latest_artifact_path,
    latest_version,
    next_version_path,
    versioned_artifacts,
)
from arnold_pipelines.megaplan._pipeline.types import StepContext


def _ctx(tmp_path: Path) -> StepContext:
    return StepContext(
        plan_dir=tmp_path, state={}, profile=None, mode="code", inputs={},
    )


def test_artifact_dir_creates_subdir(tmp_path: Path) -> None:
    d = artifact_dir(_ctx(tmp_path), "plan")
    assert d == tmp_path / "plan"
    assert d.is_dir()


def test_latest_version_empty_is_zero(tmp_path: Path) -> None:
    assert latest_version(_ctx(tmp_path), "plan", "md") == 0


def test_next_version_path_starts_at_v1(tmp_path: Path) -> None:
    path = next_version_path(_ctx(tmp_path), "plan", "md")
    assert path.name == "v1.md"


def test_next_version_path_increments(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    p1 = next_version_path(ctx, "plan", "md"); p1.write_text("one")
    p2 = next_version_path(ctx, "plan", "md"); p2.write_text("two")
    p3 = next_version_path(ctx, "plan", "md"); p3.write_text("three")
    assert [p1.name, p2.name, p3.name] == ["v1.md", "v2.md", "v3.md"]


def test_versioned_artifacts_returns_in_order(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    next_version_path(ctx, "critique", "json").write_text("{}")
    next_version_path(ctx, "critique", "json").write_text("{}")
    next_version_path(ctx, "critique", "json").write_text("{}")
    items = list(versioned_artifacts(ctx, "critique", "json"))
    assert [p.name for p in items] == ["v1.json", "v2.json", "v3.json"]


def test_latest_artifact_path_returns_highest(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    next_version_path(ctx, "plan", "md").write_text("v1")
    next_version_path(ctx, "plan", "md").write_text("v2")
    latest = latest_artifact_path(ctx, "plan", "md")
    assert latest is not None and latest.name == "v2.md"


def test_latest_artifact_path_none_when_empty(tmp_path: Path) -> None:
    assert latest_artifact_path(_ctx(tmp_path), "plan", "md") is None


def test_different_extensions_have_independent_counters(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    p_md = next_version_path(ctx, "thing", "md")
    p_json = next_version_path(ctx, "thing", "json")
    assert p_md.name == "v1.md"
    assert p_json.name == "v1.json"
