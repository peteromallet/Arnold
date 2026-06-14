"""Tests for arnold.pipeline.builder — neutral graph builder."""

from __future__ import annotations

import pytest

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.declaration_lowering import lower_stage_declarations
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    ReadRef,
    Stage,
    Step,
    StepContext,
    StepResult,
    WriteRef,
)
from arnold.pipeline.step_invocation import StepInvocation


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
        assert p.binding_map is None

    def test_build_derives_binding_map_from_clean_typed_declarations(self):
        b = PipelineBuilder("test", "typed authoring pipeline")
        b.add_stage(
            Stage(
                name="src",
                step=_TrivialStep("src"),
                edges=(Edge(label="done", target="sink"),),
                writes=(Port(name="draft", content_type="text/markdown"),),
            )
        )
        b.add_stage(
            Stage(
                name="sink",
                step=_TrivialStep("sink"),
                edges=(),
                reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            )
        )

        p = b.build(derive_bindings=True)

        assert p.binding_map == {("sink", "draft"): ("src", "draft")}

    @pytest.mark.parametrize(
        ("producer_kwargs", "consumer_kwargs", "expected_produces", "expected_consumes"),
        [
            (
                {"produces": (Port(name="draft", content_type="text/markdown"),)},
                {
                    "consumes": (
                        PortRef(port_name="draft", content_type="text/markdown"),
                    )
                },
                (Port(name="draft", content_type="text/markdown"),),
                (PortRef(port_name="draft", content_type="text/markdown"),),
            ),
            (
                {"writes": (Port(name="draft", content_type="text/markdown"),)},
                {
                    "reads": (
                        PortRef(port_name="draft", content_type="text/markdown"),
                    )
                },
                (Port(name="draft", content_type="text/markdown"),),
                (PortRef(port_name="draft", content_type="text/markdown"),),
            ),
            (
                {
                    "writes": (Port(name="draft", content_type="text/markdown"),),
                    "produces": (Port(name="draft", content_type="text/markdown"),),
                },
                {
                    "reads": (
                        PortRef(port_name="draft", content_type="text/markdown"),
                    ),
                    "consumes": (
                        PortRef(port_name="draft", content_type="text/markdown"),
                    ),
                },
                (Port(name="draft", content_type="text/markdown"),),
                (PortRef(port_name="draft", content_type="text/markdown"),),
            ),
        ],
    )
    def test_build_derives_binding_map_from_effective_lowered_declarations_when_opted_in(
        self,
        producer_kwargs,
        consumer_kwargs,
        expected_produces,
        expected_consumes,
    ):
        producer = Stage(
            name="src",
            step=_TrivialStep("src"),
            edges=(Edge(label="done", target="sink"),),
            **producer_kwargs,
        )
        consumer = Stage(
            name="sink",
            step=_TrivialStep("sink"),
            edges=(),
            **consumer_kwargs,
        )

        assert (
            lower_stage_declarations(producer).effective_produces
            == expected_produces
        )
        assert (
            lower_stage_declarations(consumer).effective_consumes
            == expected_consumes
        )

        legacy_builder = PipelineBuilder("test", "effective authoring pipeline")
        legacy_builder.add_stage(producer)
        legacy_builder.add_stage(consumer)
        assert legacy_builder.build().binding_map is None

        derived_builder = PipelineBuilder("test", "effective authoring pipeline")
        derived_builder.add_stage(producer)
        derived_builder.add_stage(consumer)
        assert derived_builder.build(derive_bindings=True).binding_map == {
            ("sink", "draft"): ("src", "draft")
        }

    def test_build_skips_binding_map_when_declarations_drift(self):
        b = PipelineBuilder("test", "drifted authoring pipeline")
        b.add_stage(
            Stage(
                name="src",
                step=_TrivialStep("src"),
                edges=(Edge(label="done", target="sink"),),
                writes=(Port(name="draft", content_type="text/markdown"),),
                produces=(Port(name="other", content_type="text/markdown"),),
            )
        )
        b.add_stage(
            Stage(
                name="sink",
                step=_TrivialStep("sink"),
                edges=(),
                reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            )
        )

        p = b.build()

        assert p.binding_map is None
        src = p.stages["src"]
        sink = p.stages["sink"]
        assert src.writes == (
            Port(name="draft", content_type="text/markdown"),
        )
        assert src.produces == (
            Port(name="other", content_type="text/markdown"),
        )
        assert sink.reads == (
            PortRef(port_name="draft", content_type="text/markdown"),
        )

    def test_add_caller_supplied_edges_preserves_unrelated_stage_fields(self):
        b = PipelineBuilder("test", "field preservation pipeline")
        invocation = StepInvocation(kind="model", metadata={"prompt": "hi"})
        loop_condition = lambda state: False
        stage = Stage(
            name="a",
            step=_TrivialStep("a"),
            edges=(),
            reads=(ReadRef(name="brief.md"),),
            writes=(WriteRef(name="draft.md"),),
            produces=(Port(name="draft", content_type="text/markdown"),),
            consumes=(PortRef(port_name="brief", content_type="text/markdown"),),
            invocation=invocation,
            required_capabilities=("llm", "fs-read"),
            decision_vocabulary=frozenset({"proceed"}),
            override_vocabulary=frozenset({"abort"}),
            loop_condition=loop_condition,
        )
        b.add_stage(stage)
        b.add_caller_supplied_edges({"a": ["b"]})
        updated = b.build().stages["a"]

        assert updated.edges == (Edge(label="b", target="b"),)
        assert updated.reads == stage.reads
        assert updated.writes == stage.writes
        assert updated.produces == stage.produces
        assert updated.consumes == stage.consumes
        assert updated.invocation == invocation
        assert updated.required_capabilities == stage.required_capabilities
        assert updated.decision_vocabulary == stage.decision_vocabulary
        assert updated.override_vocabulary == stage.override_vocabulary
        assert updated.loop_condition is loop_condition

    def test_auto_link_preserves_unrelated_parallel_stage_fields(self):
        b = PipelineBuilder("test", "parallel field preservation pipeline")
        invocation = StepInvocation(kind="tool", metadata={"action": "fanout"})
        join_fn = lambda results, ctx: StepResult(next="halt")
        loop_condition = lambda state: True
        fanout = ParallelStage(
            name="fanout",
            steps=(_TrivialStep("a"), _TrivialStep("b")),
            join=join_fn,
            edges=(),
            reads=(ReadRef(name="brief.md"),),
            writes=(WriteRef(name="draft.md"),),
            produces=(Port(name="draft", content_type="text/markdown"),),
            consumes=(PortRef(port_name="brief", content_type="text/markdown"),),
            invocation=invocation,
            required_capabilities=("llm", "fs-write"),
            decision_vocabulary=frozenset({"continue"}),
            override_vocabulary=frozenset({"stop"}),
            loop_condition=loop_condition,
        )
        b.add_parallel_stage(fanout, emit_label="done")
        b.add_stage(Stage(name="after", step=_TrivialStep("after"), edges=()))
        updated = b.build().stages["fanout"]

        assert updated.edges == (Edge(label="done", target="after"),)
        assert updated.reads == fanout.reads
        assert updated.writes == fanout.writes
        assert updated.produces == fanout.produces
        assert updated.consumes == fanout.consumes
        assert updated.invocation == invocation
        assert updated.required_capabilities == fanout.required_capabilities
        assert updated.decision_vocabulary == fanout.decision_vocabulary
        assert updated.override_vocabulary == fanout.override_vocabulary
        assert updated.loop_condition is loop_condition

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
        """The neutral builder module must not import arnold.pipelines.megaplan."""
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
