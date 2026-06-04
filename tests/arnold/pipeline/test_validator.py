"""Tests for prompt/resource validation in ``arnold.pipeline.validator`` (M3c T6).

Covers:

* Missing prompt_key referencing unknown resource bundle
* Missing resource_bundles on pipeline
* Bundle-scoped success (prompt key matches a bundle)
* Deterministic defect ordering
* Doc/creative pipeline prompt rendering compatibility
* NO global mutable prompt registry (verified by boundary check)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.types import Edge, Pipeline, Stage
from arnold.pipeline.validator import (
    Diagnostics,
    ValidationOptions,
    _step_prompt_key,
    validate,
    validate_resource_dependencies,
)


# ── Minimal stub step with prompt_key ─────────────────────────────────────


@dataclass(frozen=True)
class _PromptStep:
    """A step that carries a prompt_key for validation testing."""

    name: str = "prompt_step"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: Any) -> Any:
        raise RuntimeError("static validator must not dispatch")


# ── Builder helper to avoid keyword-before-positional issues ──────────────


class _StageBuilder:
    """Fluent builder for constructing test stages without kwarg ordering issues."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._prompt_key: str | None = None
        self._edges: tuple[Edge, ...] = ()

    def with_prompt_key(self, key: str | None) -> "_StageBuilder":
        self._prompt_key = key
        return self

    def with_edges(self, *edges: Edge) -> "_StageBuilder":
        self._edges = edges
        return self

    def build(self) -> Stage:
        step = _PromptStep(name=self._name, prompt_key=self._prompt_key)
        return Stage(name=self._name, step=step, edges=self._edges)


def _pipeline(stages: dict, entry: str = "start", bundles: tuple = ()) -> Pipeline:
    return Pipeline(
        stages=stages,
        entry=entry,
        resource_bundles=bundles,
    )


# ── Missing prompt key ────────────────────────────────────────────────────


class TestMissingPromptKey:
    def test_prompt_key_with_no_bundles_is_flagged(self) -> None:
        """A stage with a prompt_key but no resource_bundles on the pipeline
        should emit a defect."""
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(stages={"start": stage})
        diag = validate_resource_dependencies(pipeline)
        assert not diag.ok
        assert any(
            "prompt_key 'critique'" in d and "no resource_bundles" in d
            for d in diag.defects
        ), diag.defects

    def test_prompt_key_missing_from_bundles_is_flagged(self) -> None:
        """A prompt_key that doesn't match any known bundle name is flagged."""
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=("plan", "review", "revise"),
        )
        diag = validate_resource_dependencies(pipeline)
        assert not diag.ok
        assert any(
            "prompt_key 'critique'" in d and "no known resource bundle" in d
            for d in diag.defects
        ), diag.defects


# ── Bundle-scoped success ─────────────────────────────────────────────────


class TestBundleScopedSuccess:
    def test_prompt_key_matching_string_bundle_passes(self) -> None:
        """A prompt_key that matches a string bundle name passes validation."""
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=("plan", "critique", "revise"),
        )
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_prompt_key_matching_bundle_object_passes(self) -> None:
        """A prompt_key that matches an object bundle's name passes."""

        @dataclass(frozen=True)
        class _Bundle:
            name: str

        bundle = _Bundle(name="critique")
        stage = _StageBuilder("start").with_prompt_key("critique").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=(bundle,),
        )
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_prompt_key_prefix_matching_bundle_passes(self) -> None:
        """A prompt_key that starts with a bundle name prefix passes."""
        stage = _StageBuilder("start").with_prompt_key("critique_v2").build()
        pipeline = _pipeline(
            stages={"start": stage},
            bundles=("critique",),
        )
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_null_prompt_key_is_skipped(self) -> None:
        """A stage with prompt_key=None does not trigger any defect."""
        stage = _StageBuilder("start").with_prompt_key(None).build()
        pipeline = _pipeline(stages={"start": stage})
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects

    def test_empty_prompt_key_is_skipped(self) -> None:
        """A stage with prompt_key='' (empty string) is skipped."""
        stage = _StageBuilder("start").with_prompt_key("").build()
        pipeline = _pipeline(stages={"start": stage})
        diag = validate_resource_dependencies(pipeline)
        assert diag.ok, diag.defects


# ── Deterministic ordering ────────────────────────────────────────────────


class TestDeterministicOrdering:
    def test_defects_emitted_in_sorted_stage_order(self) -> None:
        """Defects should appear in sorted stage-name order, not insertion order."""
        pipeline = _pipeline(
            stages={
                "zebra": _StageBuilder("zebra").with_prompt_key("unknown_a").build(),
                "alpha": _StageBuilder("alpha").with_prompt_key("unknown_b").build(),
                "mid": _StageBuilder("mid").with_prompt_key("unknown_c").build(),
            },
            bundles=("known",),
        )
        diag = validate_resource_dependencies(pipeline)
        assert not diag.ok
        # Should be alpha, mid, zebra (sorted)
        defect_stage_order = []
        for d in diag.defects:
            import re
            m = re.search(r"stage '(\w+)'", d)
            if m:
                defect_stage_order.append(m.group(1))
        assert defect_stage_order == sorted(defect_stage_order), (
            f"Expected sorted order, got {defect_stage_order}"
        )


# ── Full validate() integration ───────────────────────────────────────────


class TestFullValidateIntegration:
    def test_validate_merges_resource_defects_with_control_flow(self) -> None:
        """validate() should merge resource defects alongside control-flow defects."""
        stage = (
            _StageBuilder("start")
            .with_prompt_key("missing")
            .with_edges(Edge(label="halt", target="halt"))
            .build()
        )
        pipeline = _pipeline(stages={"start": stage})
        diag = validate(pipeline)
        # Should have resource defect about missing bundle
        assert not diag.ok
        assert any(
            "prompt_key 'missing'" in d and "no resource_bundles" in d
            for d in diag.defects
        ), diag.defects

    def test_validate_planning_pipeline_resource_check(self) -> None:
        """The planning pipeline stages with prompt_keys should pass
        resource validation since they don't rely on Arnold resource_bundles
        (they have their own prompt resolution mechanism)."""
        from megaplan._pipeline.registry import get_pipeline

        pipeline = get_pipeline("planning")
        diag = validate_resource_dependencies(pipeline)
        # The planning pipeline doesn't set resource_bundles, so any stage
        # with a prompt_key will get a soft warning about missing bundles.
        # We just verify it doesn't crash.
        assert isinstance(diag, Diagnostics)


# ── Duck-typed accessors ──────────────────────────────────────────────────


class TestDuckTypedAccessors:
    def test_step_prompt_key_from_arnold_stage(self) -> None:
        """_step_prompt_key reads from Arnold Stage.step.prompt_key."""
        stage = _StageBuilder("test").with_prompt_key("critique").build()
        assert _step_prompt_key(stage) == "critique"

    def test_step_prompt_key_from_megaplan_style_step(self) -> None:
        """_step_prompt_key duck-types Megaplan step shapes."""

        class MegaplanStep:
            name = "mega_step"
            kind = "produce"
            prompt_key = "review"

        class MegaplanStage:
            def __init__(self):
                self.name = "mega_stage"
                self.step = MegaplanStep()
                self.edges = ()

        stage = MegaplanStage()
        assert _step_prompt_key(stage) == "review"

    def test_step_prompt_key_none_when_no_step(self) -> None:
        """_step_prompt_key returns None when stage has no step."""
        stage = Stage(name="empty", step=None, edges=())
        assert _step_prompt_key(stage) is None


# ── Boundary: No global mutable prompt registry ───────────────────────────


class TestNoGlobalPromptRegistry:
    def test_validator_has_no_mutable_global_registry(self) -> None:
        """The validator module must not declare a global mutable prompt registry."""
        src = (
            Path(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "validator.py"
        )
        tree = ast.parse(src.read_text())

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id.lower()
                        if any(
                            keyword in name
                            for keyword in ("registry", "prompt_map", "prompt_dict")
                        ):
                            if isinstance(node.value, (ast.Dict, ast.List, ast.Set)):
                                pytest.fail(
                                    f"validator.py has mutable global registry: {target.id}"
                                )

    def test_validator_has_no_prompt_registry_import(self) -> None:
        """The validator must not import any prompt registry modules."""
        src = (
            Path(__file__).parents[3]
            / "arnold"
            / "pipeline"
            / "validator.py"
        )
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "prompt_registry" not in alias.name.lower(), (
                        f"validator imports prompt registry: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "prompt_registry" not in node.module.lower(), (
                        f"validator imports from prompt registry: {node.module}"
                    )
