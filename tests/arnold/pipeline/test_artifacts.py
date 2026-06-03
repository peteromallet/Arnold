"""Tests for ``arnold.pipeline.artifacts`` (M3a T7)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.artifacts import (
    _artifact_root_as_plan_dir,
    artifact_dir,
    artifact_path,
    latest_artifact,
    next_version,
    write_versioned,
)
from arnold.pipeline.types import StepContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_root() -> str:
    with tempfile.TemporaryDirectory() as d:
        yield d


def _ctx(artifact_root: str, **overrides: Any) -> StepContext:
    kwargs: dict[str, Any] = {
        "artifact_root": artifact_root,
        "state": {},
        "inputs": {},
        **overrides,
    }
    return StepContext(**kwargs)


# ---------------------------------------------------------------------------
# artifact_dir / artifact_path
# ---------------------------------------------------------------------------


class TestArtifactDir:
    def test_creates_directory(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        out = artifact_dir(ctx, "review", "verdict")
        assert out == Path(tmp_root) / "review" / "verdict"
        assert out.is_dir()

    def test_uses_artifact_root(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        out = artifact_dir(ctx, "stage_a", "output")
        assert str(out).startswith(tmp_root)


class TestArtifactPath:
    def test_constructs_path(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        p = artifact_path(ctx, "plan", "draft", version=3, suffix="md")
        assert p == Path(tmp_root) / "plan" / "draft" / "v3.md"
        assert p.parent.is_dir()  # parent created

    def test_does_not_create_file(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        p = artifact_path(ctx, "stage", "label", version=1, suffix="json")
        assert not p.exists()  # only parent dir, not the file itself


# ---------------------------------------------------------------------------
# next_version / latest_artifact
# ---------------------------------------------------------------------------


class TestNextVersion:
    def test_returns_1_when_no_artifacts(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        v = next_version(ctx, "stage", "output", "md")
        assert v == 1

    def test_returns_next_after_existing(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        # Write v1, v2, v3
        for n in (1, 2, 3):
            d = Path(tmp_root) / "stage" / "output"
            d.mkdir(parents=True, exist_ok=True)
            (d / f"v{n}.md").write_text(f"content {n}")
        v = next_version(ctx, "stage", "output", "md")
        assert v == 4

    def test_ignores_other_suffix(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        d = Path(tmp_root) / "stage" / "out"
        d.mkdir(parents=True, exist_ok=True)
        (d / "v1.md").write_text("md")
        (d / "v1.json").write_text("json")
        assert next_version(ctx, "stage", "out", "md") == 2
        assert next_version(ctx, "stage", "out", "json") == 2


class TestLatestArtifact:
    def test_returns_none_when_no_artifacts(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        assert latest_artifact(ctx, "stage", "out", "md") is None

    def test_returns_highest_version(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        d = Path(tmp_root) / "stage" / "out"
        d.mkdir(parents=True, exist_ok=True)
        (d / "v1.md").write_text("1")
        (d / "v3.md").write_text("3")
        (d / "v2.md").write_text("2")
        latest = latest_artifact(ctx, "stage", "out", "md")
        assert latest is not None
        assert latest.name == "v3.md"

    def test_returns_none_when_dir_missing(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        assert latest_artifact(ctx, "nonexistent", "label", "md") is None


# ---------------------------------------------------------------------------
# write_versioned
# ---------------------------------------------------------------------------


class TestWriteVersioned:
    def test_writes_content_and_returns_path(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        path = write_versioned(ctx, "plan", "draft", "# Hello", "md")
        assert path.name == "v1.md"
        assert path.read_text() == "# Hello"

    def test_auto_increments(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        p1 = write_versioned(ctx, "plan", "draft", "first", "md")
        p2 = write_versioned(ctx, "plan", "draft", "second", "md")
        assert p1.name == "v1.md"
        assert p2.name == "v2.md"

    def test_explicit_version(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        path = write_versioned(
            ctx, "stage", "label", "explicit", "json", version=42
        )
        assert path.name == "v42.json"
        assert path.read_text() == "explicit"

    def test_atomic_write_uses_tmp(self, tmp_root: str) -> None:
        ctx = _ctx(tmp_root)
        path = write_versioned(ctx, "s", "l", "data", "txt")
        # tmp file should not exist after replace
        tmp = path.with_suffix(path.suffix + ".tmp")
        assert not tmp.exists()
        assert path.read_text() == "data"


# ---------------------------------------------------------------------------
# Megaplan bridge adapter
# ---------------------------------------------------------------------------


class TestBridgeAdapter:
    def test_artifact_root_as_plan_dir_returns_artifact_root(self) -> None:
        ctx = _ctx("/tmp/my_plan")
        result = _artifact_root_as_plan_dir(ctx)
        assert result == "/tmp/my_plan"

    def test_artifact_root_as_plan_dir_is_string(self) -> None:
        ctx = _ctx("/tmp/foo")
        result = _artifact_root_as_plan_dir(ctx)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Neutral steps fail if they access plan_dir
# ---------------------------------------------------------------------------


class TestNeutralStepsPlanDirGuard:
    """Prove that Arnold-neutral StepContext has artifact_root, NOT plan_dir.

    Any neutral Step that tries to access ``ctx.plan_dir`` will get an
    ``AttributeError`` because the field does not exist on the Arnold
    ``StepContext``.  This test guards against accidental drift.
    """

    def test_step_context_has_no_plan_dir(self) -> None:
        ctx = _ctx("/tmp/test")
        with pytest.raises(AttributeError):
            _ = ctx.plan_dir  # type: ignore[attr-defined]

    def test_step_context_has_artifact_root(self) -> None:
        ctx = _ctx("/tmp/test")
        assert ctx.artifact_root == "/tmp/test"


# ---------------------------------------------------------------------------
# Bridge steps still receive plan_dir
# ---------------------------------------------------------------------------


class TestBridgeStepPlanDir:
    """Megaplan bridge callers can construct a legacy StepContext with plan_dir.

    The bridge adapter provides artifact_root as a plan_dir-compatible
    string, and Megaplan code can feed it into the legacy constructor.
    This test simulates that flow without importing megaplan.
    """

    def test_bridge_adapter_provides_plan_dir_value(self) -> None:
        """_artifact_root_as_plan_dir gives a value usable as plan_dir."""
        arnold_ctx = _ctx("/tmp/bridge_test")
        plan_dir_str = _artifact_root_as_plan_dir(arnold_ctx)
        # In real bridge code this would be:
        #   mega_ctx = MegaplanStepContext(plan_dir=Path(plan_dir_str), ...)
        # Here we just verify the value is correct.
        assert plan_dir_str == "/tmp/bridge_test"
        assert Path(plan_dir_str).as_posix() == "/tmp/bridge_test"


# ---------------------------------------------------------------------------
# Boundary
# ---------------------------------------------------------------------------


class TestArtifactsBoundary:
    def test_artifacts_module_has_no_megaplan_import(self) -> None:
        import ast

        src = (
            Path(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "artifacts.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("megaplan"), (
                            f"artifacts.py imports megaplan: {alias.name!r}"
                        )
                else:
                    assert node.module is None or not node.module.startswith(
                        "megaplan"
                    ), (
                        f"artifacts.py imports from megaplan: {node.module!r}"
                    )

    def test_artifacts_module_has_no_forbidden_literals(self) -> None:
        import ast

        forbidden = frozenset(
            {"planning", "proceed", "iterate", "tiebreaker", "escalate"}
        )
        src = (
            Path(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "artifacts.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in forbidden, (
                    f"artifacts.py contains forbidden literal: {node.value!r}"
                )
