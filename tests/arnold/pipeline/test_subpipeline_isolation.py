"""M3c T12: Arnold subpipeline isolation tests.

Prove that child artifacts stay in child scope and that only promoted
StateDelta values enter parent state.  Zero megaplan imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold.pipeline.state import StateDelta, apply_delta
from arnold.pipeline.subpipeline import (
    ChildRunResult,
    SubpipelineInvocation,
    promote,
    run_subpipeline,
)
from arnold.pipeline.types import StepContext, StepResult


# ── Arnold-only stub pipeline for isolation tests ────────────────────────


@dataclass
class _IsolatedChildStep:
    """A simple child step that writes an artifact inside its own context."""

    name: str = "child_worker"
    kind: str = "produce"

    def run(self, ctx: StepContext) -> StepResult:
        root = Path(ctx.artifact_root)
        child_file = root / "child_owned_artifact.txt"
        child_file.parent.mkdir(parents=True, exist_ok=True)
        child_file.write_text("child-secret")
        return StepResult(
            outputs={"child_out": str(child_file)},
            next="halt",
            state_patch={"child_score": 0.95, "child_label": "processed"},
        )


class _IsolatedChildPipeline:
    """Minimal Arnold Pipeline-like object whose run() directly calls its step."""

    def __init__(self) -> None:
        self.name = "isolated_child"
        self.entry = "child_worker"
        self.stages: dict[str, Any] = {"child_worker": _IsolatedChildStep()}

    def run(self, ctx: StepContext) -> dict[str, Any]:
        stage = self.stages[self.entry]
        result = stage.run(ctx)
        return {
            "final_stage": "child_worker",
            "state": dict(result.state_patch),
            "artifacts": {
                k: Path(v) for k, v in (result.outputs or {}).items()
            },
            "status": "completed",
        }


class _DuckParentContext:
    """Non-dataclass context with package-owned attributes."""

    def __init__(self, *, artifact_root: str, state: Mapping[str, Any]) -> None:
        self.artifact_root = artifact_root
        self.state = state
        self.inputs = {}
        self.capability_scope = {"network": False}
        self.package_runtime = object()


# ── Tests ────────────────────────────────────────────────────────────────


class TestChildArtifactIsolation:
    """Prove that child artifacts are NOT accessible from parent scope."""

    def test_child_artifact_written_under_child_root_not_parent(
        self, tmp_path: Path
    ) -> None:
        """Child writes to its own artifact_root subdir; parent root is clean."""
        child = _IsolatedChildPipeline()
        parent_root = tmp_path / "parent"
        parent_root.mkdir()

        ctx = StepContext(
            artifact_root=str(parent_root),
            state={"parent_key": "parent_value"},
        )

        invocation = SubpipelineInvocation(
            child_pipeline=child,
            artifact_subdir="isolated_run",
        )

        result = run_subpipeline(invocation, ctx)

        assert result.status == "completed"

        # Child artifact exists under child's subdir
        child_root = parent_root / "isolated_run"
        child_file = child_root / "child_owned_artifact.txt"
        assert child_file.exists(), (
            f"Child artifact should exist at {child_file}"
        )
        assert child_file.read_text() == "child-secret"

        # Parent root does NOT have the child file directly
        parent_file = parent_root / "child_owned_artifact.txt"
        assert not parent_file.exists(), (
            "Child artifact leaked into parent root — "
            "isolation violated"
        )

    def test_child_artifact_path_not_in_parent_state_by_default(
        self, tmp_path: Path
    ) -> None:
        """Child result artifacts are not automatically merged into parent state."""
        child = _IsolatedChildPipeline()
        parent_root = tmp_path / "parent2"
        parent_root.mkdir()

        ctx = StepContext(
            artifact_root=str(parent_root),
            state={"parent_key": "parent_value"},
        )

        invocation = SubpipelineInvocation(
            child_pipeline=child,
            artifact_subdir="isolated_run_2",
        )

        result = run_subpipeline(invocation, ctx)

        # The parent state is unchanged — child artifacts don't leak
        assert "child_out" not in ctx.state, (
            "Child artifact key leaked into parent state"
        )
        assert "child_score" not in ctx.state, (
            "Child state key leaked into parent state"
        )

    def test_child_final_state_not_shared_with_parent_state(
        self, tmp_path: Path
    ) -> None:
        """Child's final_state is a separate reference, not parent's state."""
        child = _IsolatedChildPipeline()
        parent_root = tmp_path / "parent3"
        parent_root.mkdir()

        parent_state = {"parent_key": "parent_value"}
        ctx = StepContext(
            artifact_root=str(parent_root),
            state=parent_state,
        )

        invocation = SubpipelineInvocation(
            child_pipeline=child,
            artifact_subdir="isolated_run_3",
        )

        result = run_subpipeline(invocation, ctx)

        # Child state exists in result, but parent state was not mutated
        assert "child_score" in result.final_state
        assert "child_score" not in parent_state
        assert parent_state["parent_key"] == "parent_value"


class TestStateDeltaPromotion:
    """Prove that only promoted StateDelta values enter parent state."""

    def test_promote_returns_delta_without_mutating_parent(
        self, tmp_path: Path
    ) -> None:
        """promote() returns a StateDelta; parent state dict is unmodified."""
        child_result = ChildRunResult(
            final_state={"child_score": 0.95, "child_label": "processed"},
            final_stage="child_worker",
            artifacts={"child_out": tmp_path / "result.json"},
            status="completed",
        )
        parent_state = {"parent_key": "parent_value"}
        original = dict(parent_state)

        delta = promote(
            child_result,
            parent_state,
            output_map={"child_out": "promoted_child_out"},
        )

        # Delta returned, parent state unchanged
        assert isinstance(delta, StateDelta)
        assert parent_state == original, (
            "promote() mutated the parent state dict"
        )

    def test_apply_delta_merges_promoted_values_only(self) -> None:
        """Only the promoted keys from the delta enter parent state."""
        parent = {"parent_key": "parent_value", "unrelated": 42}
        child_result = ChildRunResult(
            final_state={"child_score": 0.88, "child_label": "vetted"},
        )

        delta = promote(child_result, parent)
        new_state = apply_delta(dict(parent), delta)

        # Promoted child state keys present
        assert new_state["child_score"] == 0.88
        assert new_state["child_label"] == "vetted"
        # Parent keys preserved
        assert new_state["parent_key"] == "parent_value"
        assert new_state["unrelated"] == 42

    def test_promoted_values_override_parent_keys_explicitly(self) -> None:
        """When promote delta keys collide with parent keys, delta wins."""
        parent = {"score": 0.5, "label": "old"}
        child_result = ChildRunResult(
            final_state={"score": 0.99, "label": "new"},
        )

        delta = promote(child_result, parent)
        new_state = apply_delta(dict(parent), delta)

        # Child promoted values override parent keys
        assert new_state["score"] == 0.99
        assert new_state["label"] == "new"

    def test_promote_empty_child_yields_delta_with_only_state(self) -> None:
        """Promote with no output_map and empty state yields minimal delta."""
        child_result = ChildRunResult(
            final_state={},
            status="completed",
        )
        delta = promote(child_result, {})
        assert isinstance(delta, StateDelta)
        # Empty state yields no patches (since final_state is empty dict)
        assert len(delta.patches) == 0

    def test_promote_with_output_map_maps_artifacts(self) -> None:
        """output_map entries appear as promoted keys in the delta."""
        artifact_path = Path("/tmp/fake/result.json")  # existence not checked
        child_result = ChildRunResult(
            final_state={"child_score": 0.91},
            artifacts={"child_out": artifact_path, "unmapped_out": Path("/tmp/fake/other.json")},
        )

        delta = promote(
            child_result,
            {},
            output_map={"child_out": "promoted_child_out"},
        )

        patches = list(delta.patches)
        # First patch: final_state
        assert patches[0] == {"child_score": 0.91}
        # Second patch: mapped artifact
        assert patches[1] == {"promoted_child_out": str(artifact_path)}
        # unmapped_out is NOT in any patch
        all_keys = set()
        for p in patches:
            all_keys.update(p.keys())
        assert "unmapped_out" not in all_keys


class TestRunSubpipelineIsolation:
    """End-to-end isolation: run_subpipeline + promote together."""

    def test_full_isolation_workflow(self, tmp_path: Path) -> None:
        """Run child → promote → apply_delta; parent root stays clean."""
        child = _IsolatedChildPipeline()
        parent_root = tmp_path / "parent_full"
        parent_root.mkdir()

        parent_state = {"parent_key": "original"}
        ctx = StepContext(
            artifact_root=str(parent_root),
            state=parent_state,
        )

        invocation = SubpipelineInvocation(
            child_pipeline=child,
            input_map={"parent_key": "child_key"},
            artifact_subdir="full_iso_run",
        )

        child_result = run_subpipeline(invocation, ctx)

        # Child ran successfully
        assert child_result.status == "completed"
        assert child_result.final_state["child_score"] == 0.95

        # Promote and apply
        delta = promote(child_result, parent_state)
        new_parent = apply_delta(dict(parent_state), delta)

        # Only promoted child values are in new parent state
        assert new_parent["child_score"] == 0.95
        assert new_parent["child_label"] == "processed"
        assert new_parent["parent_key"] == "original"

        # Parent artifact root does not have child artifacts
        child_file_in_parent = parent_root / "child_owned_artifact.txt"
        assert not child_file_in_parent.exists(), (
            "Child artifact leaked into parent root"
        )

        # Child artifacts exist only under child subdir
        child_root = parent_root / "full_iso_run"
        child_file = child_root / "child_owned_artifact.txt"
        assert child_file.exists()
        assert child_file.read_text() == "child-secret"

    def test_multiple_child_runs_dont_cross_contaminate(
        self, tmp_path: Path
    ) -> None:
        """Two subpipeline runs should not share state."""
        child = _IsolatedChildPipeline()
        parent_root = tmp_path / "parent_multi"
        parent_root.mkdir()

        ctx = StepContext(
            artifact_root=str(parent_root),
            state={},
        )

        # First child run
        inv1 = SubpipelineInvocation(
            child_pipeline=child,
            artifact_subdir="run_1",
        )
        r1 = run_subpipeline(inv1, ctx)
        assert r1.status == "completed"

        # Second child run — separate subdir
        inv2 = SubpipelineInvocation(
            child_pipeline=child,
            artifact_subdir="run_2",
        )
        r2 = run_subpipeline(inv2, ctx)
        assert r2.status == "completed"

        # Each run has its own artifact
        assert (parent_root / "run_1" / "child_owned_artifact.txt").exists()
        assert (parent_root / "run_2" / "child_owned_artifact.txt").exists()

        # Promoted deltas are independent
        d1 = promote(r1, {})
        d2 = promote(r2, {})
        assert d1 == d2  # Same child produces same final_state

    def test_duck_context_preserves_package_owned_attributes(
        self, tmp_path: Path
    ) -> None:
        """Child contexts inherit arbitrary non-dataclass parent attributes."""
        parent_root = tmp_path / "parent_duck"
        parent_root.mkdir()
        ctx = _DuckParentContext(
            artifact_root=str(parent_root),
            state={"parent_key": "parent_value"},
        )
        captured: dict[str, Any] = {}

        def runner(
            _pipeline: Any,
            child_ctx: Any,
            child_root: Path | None,
        ) -> ChildRunResult:
            captured["ctx"] = child_ctx
            captured["child_root"] = child_root
            return ChildRunResult(status="completed")

        invocation = SubpipelineInvocation(
            child_pipeline=_IsolatedChildPipeline(),
            input_map={"parent_key": "child_key"},
            artifact_subdir="duck_child",
        )

        result = run_subpipeline(invocation, ctx, runner=runner)

        assert result.status == "completed"
        child_ctx = captured["ctx"]
        assert child_ctx is not ctx
        assert child_ctx.artifact_root == str(parent_root / "duck_child")
        assert child_ctx.inputs == {"child_key": "parent_value"}
        assert child_ctx.capability_scope == {"network": False}
        assert child_ctx.package_runtime is ctx.package_runtime
        assert captured["child_root"] == parent_root / "duck_child"


# ── Boundary verification ────────────────────────────────────────────────


class TestNoMegaplanImports:
    """Verify this test file has zero megaplan imports."""

    def test_no_megaplan_imports_in_this_file(self) -> None:
        import ast
        from pathlib import Path as P

        src = P(__file__)
        tree = ast.parse(src.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("megaplan"), (
                        f"Isolation test imports megaplan: {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith(
                    "megaplan"
                ), (
                    f"Isolation test imports from megaplan: {node.module!r}"
                )
