"""Tests for arnold.pipeline.builder — neutral graph builder."""

from __future__ import annotations

import pytest

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
)


class _TrivialStep:
    """A Step that returns a simple result."""
    name: str
    kind: str = "produce"

    def __init__(self, name: str, next_label: str = "halt"):
        self.name = name
        self._next = next_label

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next=self._next)


class TestNeutralBuilder:
    """The neutral builder composes a Pipeline without importing megaplan."""

    def test_build_single_stage(self):
        b = PipelineBuilder("test", "single-stage pipeline")
        step = _TrivialStep("hello")
        stage = Stage(name="hello", step=step, edges=())
        b.add_stage(stage)
        p = b.build()
        assert isinstance(p, Pipeline)
        assert p.entry == "hello"
        assert list(p.stages.keys()) == ["hello"]

    def test_build_two_stages_auto_link(self):
        b = PipelineBuilder("test", "two-stage pipeline")
        s1 = Stage(
            name="first",
            step=_TrivialStep("first", next_label="done"),
            edges=(Edge(label="done", target="halt"),),
        )
        s2 = Stage(
            name="second",
            step=_TrivialStep("second"),
            edges=(),
        )
        b.add_stage(s1, emit_label="done")
        b.add_stage(s2)
        p = b.build()
        assert p.entry == "first"
        assert set(p.stages.keys()) == {"first", "second"}
        # Auto-link should have added "done" -> "second" edge on first
        first_stage = p.stages["first"]
        targets = {e.target for e in first_stage.edges}
        assert "second" in targets

    def test_add_parallel_stage(self):
        b = PipelineBuilder("test", "parallel pipeline")
        join_fn = lambda results, ctx: StepResult(next="halt")
        ps = ParallelStage(
            name="fanout",
            steps=(_TrivialStep("a"), _TrivialStep("b")),
            join=join_fn,
            edges=(),
        )
        b.add_parallel_stage(ps)
        p = b.build()
        assert p.entry == "fanout"
        assert isinstance(p.stages["fanout"], ParallelStage)

    def test_add_caller_supplied_edges(self):
        b = PipelineBuilder("test", "edges pipeline")
        s1 = Stage(name="a", step=_TrivialStep("a"), edges=())
        s2 = Stage(name="b", step=_TrivialStep("b"), edges=())
        s3 = Stage(name="c", step=_TrivialStep("c"), edges=())
        b.add_stage(s1)
        b.add_stage(s2)
        b.add_stage(s3)
        b.add_caller_supplied_edges({"a": ["b", "c"]})
        p = b.build()
        a_stage = p.stages["a"]
        targets = {e.target for e in a_stage.edges}
        assert targets == {"b", "c"}

    def test_attach_resource_bundles(self):
        b = PipelineBuilder("test", "resources pipeline")
        b.attach_resource_bundles([{"prompt_dir": "/tmp/prompts"}])
        assert len(b.resource_bundles) == 1
        assert b.resource_bundles[0] == {"prompt_dir": "/tmp/prompts"}

    def test_build_empty_raises(self):
        b = PipelineBuilder("test")
        with pytest.raises(ValueError, match="no stages added"):
            b.build()

    def test_no_megaplan_import(self):
        """The neutral builder module must not import megaplan."""
        import ast
        import sys

        # Check that arnold.pipeline.builder has no megaplan imports
        if "megaplan" in sys.modules:
            # megaplan may already be loaded by other tests; check the module source
            import arnold.pipeline.builder as builder_mod
            src = ast.parse(open(builder_mod.__file__).read())
            for node in ast.walk(src):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = node.module if isinstance(node, ast.ImportFrom) else ""
                    names = [n.name for n in node.names]
                    for name in [module] + names:
                        if name and "megaplan" in str(name):
                            pytest.fail(f"Neutral builder imports megaplan: {name}")
