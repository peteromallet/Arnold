"""Tests for ``panel_parallel()`` topology builder (M3a T21).

``panel_parallel()`` is classified as neutral (T16) but has not yet been
moved to Arnold.  It currently lives in :mod:`megaplan._pipeline.pattern_topology`
and returns Megaplan's :class:`ParallelStage`.

This test exercises its structural properties through the Megaplan import path.
Note: The Megaplan ``ParallelStage`` is a distinct class from the Arnold
``ParallelStage`` (M3a type collision, resolved in M3b).  We test structure,
not executor integration.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.types import StepContext, StepResult
from arnold.pipelines.megaplan._pipeline.types import Edge, ParallelStage


# ---------------------------------------------------------------------------
# Fake reviewer step
# ---------------------------------------------------------------------------


class _ReviewerStep:
    """A step that returns a simple output for panel_parallel join collation."""

    def __init__(self, name: str, outputs: dict[str, Any] | None = None):
        self.name = name
        self.kind = "review"
        self._outputs = outputs or {}

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(outputs=self._outputs, next="halt")


# ---------------------------------------------------------------------------
# panel_parallel tests
# ---------------------------------------------------------------------------


class TestPanelParallel:
    def test_returns_parallel_stage(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("panel", (("reviewer_a", r1),))
        assert isinstance(stage, ParallelStage)
        assert stage.name == "panel"
        assert len(stage.steps) == 1

    def test_multiple_reviewers_fan_out(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1", {"draft": "/tmp/r1.md"})
        r2 = _ReviewerStep("r2", {"draft": "/tmp/r2.md"})
        r3 = _ReviewerStep("r3", {"draft": "/tmp/r3.md"})

        stage = panel_parallel(
            "panel",
            (("a", r1), ("b", r2), ("c", r3)),
        )
        assert len(stage.steps) == 3

    def test_default_next_label_is_next(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("p", (("x", r1),))
        # The join callable should be set
        assert stage.join is not None
        # Verify the join produces the correct next="next" behaviour
        ctx = StepContext(artifact_root="/tmp", state={})
        result = stage.join([StepResult(next="halt", outputs={"k": "v"})], ctx)
        assert result.next == "next"

    def test_custom_next_label(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("p", (("x", r1),), next_label="done")
        ctx = StepContext(artifact_root="/tmp", state={})
        result = stage.join([StepResult(next="halt", outputs={"k": "v"})], ctx)
        assert result.next == "done"

    def test_custom_edges_passed_through(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel(
            "panel",
            (("x", r1),),
            edges=(Edge(label="done", target="halt"),),
        )
        assert len(stage.edges) == 1
        assert stage.edges[0].label == "done"

    def test_max_workers_passed_through(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        r2 = _ReviewerStep("r2")
        stage = panel_parallel("p", (("a", r1), ("b", r2)), max_workers=1)
        assert stage.max_workers == 1

    def test_merge_strategy_accepted_but_ignored(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("p", (("x", r1),), merge_strategy="structural")
        assert isinstance(stage, ParallelStage)  # doesn't crash

    def test_empty_reviewers_works(self) -> None:
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        stage = panel_parallel("empty_panel", ())
        assert len(stage.steps) == 0
        assert isinstance(stage, ParallelStage)

    def test_join_collates_per_reviewer_outputs(self) -> None:
        """The built-in join prefixes each reviewer's outputs with reviewer_id."""
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1", {"draft": "/tmp/d1.md", "score": 0.9})
        r2 = _ReviewerStep("r2", {"draft": "/tmp/d2.md"})

        stage = panel_parallel(
            "panel",
            (("alice", r1), ("bob", r2)),
        )
        ctx = StepContext(artifact_root="/tmp", state={})
        result = stage.join([
            StepResult(outputs={"draft": "/tmp/d1.md", "score": 0.9}),
            StepResult(outputs={"draft": "/tmp/d2.md"}),
        ], ctx)

        # Outputs are prefixed: "alice.draft", "alice.score", "bob.draft"
        assert result.outputs.get("alice.draft") == "/tmp/d1.md"
        assert result.outputs.get("alice.score") == 0.9
        assert result.outputs.get("bob.draft") == "/tmp/d2.md"
        assert result.next == "next"

    def test_join_with_custom_next_label(self) -> None:
        """Join forwards the configured next_label."""
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1", {"x": 1})
        stage = panel_parallel("p", (("a", r1),), next_label="synthesize")
        ctx = StepContext(artifact_root="/tmp", state={})
        result = stage.join([StepResult(outputs={"x": 1})], ctx)
        assert result.next == "synthesize"


# ---------------------------------------------------------------------------
# Boundary — panel_parallel has no Megaplan vocabulary (per T16)
# ---------------------------------------------------------------------------


class TestPanelParallelBoundary:
    def test_panel_parallel_uses_no_forbidden_literals(self) -> None:
        """panel_parallel() uses only neutral types, no gate/tiebreaker."""
        import inspect
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        src = inspect.getsource(panel_parallel)
        forbidden = ["tiebreaker", "proceed", "iterate", "escalate", "planning"]
        for word in forbidden:
            assert word not in src, (
                f"panel_parallel source contains forbidden word: {word!r}"
            )

    def test_panel_parallel_uses_parallel_stage_type(self) -> None:
        """The function body constructs a ParallelStage — the neutral primitive."""
        import inspect
        from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel

        src = inspect.getsource(panel_parallel)
        assert "ParallelStage" in src


# ---------------------------------------------------------------------------
# decision_edges tests (M3b T5)
# ---------------------------------------------------------------------------


class TestDecisionEdges:
    """Tests for :func:`arnold.pipeline.pattern_topology.decision_edges`."""

    def test_empty_decisions_returns_empty_tuple(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges

        result = decision_edges(decisions={})
        assert result == ()

    def test_single_decision_edge(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges

        result = decision_edges(decisions={"approve": "done"})
        assert len(result) == 1
        assert result[0].kind == "decision"
        assert result[0].label == "approve"
        assert result[0].target == "done"

    def test_multiple_decisions_produce_decision_edges(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges

        result = decision_edges(
            decisions={"approve": "merged", "rework": "revise", "manual_review": "human"}
        )
        assert len(result) == 3
        for edge in result:
            assert edge.kind == "decision"
        labels = {e.label for e in result}
        assert labels == {"approve", "rework", "manual_review"}

    def test_override_edges_use_override_prefix(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges

        result = decision_edges(
            decisions={"approve": "done"},
            overrides={"abort": "halt", "force_proceed": "done"},
        )
        # 1 decision + 2 overrides = 3
        assert len(result) == 3

        override_edges = [e for e in result if e.kind == "override"]
        assert len(override_edges) == 2

        labels = {e.label for e in override_edges}
        assert labels == {"override abort", "override force_proceed"}

    def test_decisions_before_overrides_before_fallback(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges
        from arnold.pipeline.types import Edge

        fb = (Edge(label="fallback", target="fb_target", kind="normal"),)
        result = decision_edges(
            decisions={"d1": "t1"},
            overrides={"o1": "t2"},
            fallback_edges=fb,
        )
        assert len(result) == 3
        assert result[0].kind == "decision"
        assert result[1].kind == "override"
        assert result[2].kind == "normal"
        assert result[2].label == "fallback"

    def test_overrides_none_treated_as_empty(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges

        result = decision_edges(
            decisions={"approve": "done"},
            overrides=None,
        )
        assert len(result) == 1
        assert result[0].kind == "decision"

    def test_decisions_preserve_order(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges

        # Use an OrderedDict / dict with known insertion order (Python 3.7+)
        result = decision_edges(
            decisions={"z": "z_target", "a": "a_target", "m": "m_target"}
        )
        assert [e.label for e in result] == ["z", "a", "m"]

    def test_fallback_edges_preserve_their_kind(self) -> None:
        from arnold.pipeline.pattern_topology import decision_edges
        from arnold.pipeline.types import Edge

        fb = (
            Edge(label="custom", target="t1", kind="decision"),
            Edge(label="override custom", target="t2", kind="override"),
        )
        result = decision_edges(decisions={}, fallback_edges=fb)
        assert len(result) == 2
        assert result[0].kind == "decision"
        assert result[0].label == "custom"
        assert result[1].kind == "override"
        assert result[1].label == "override custom"

    def test_no_megaplan_label_literals_in_source(self) -> None:
        """decision_edges() body must not contain Megaplan label literals."""
        import inspect
        from arnold.pipeline.pattern_topology import decision_edges

        src = inspect.getsource(decision_edges)
        # Strip the docstring — it mentions the literals to say they are
        # *not* used.  The body (everything after the triple-quote close)
        # must be clean.
        body = src
        # Find the closing triple quote of the docstring.
        # The docstring uses """ so we look for the second """.
        first = body.find('"""')
        if first != -1:
            second = body.find('"""', first + 3)
            if second != -1:
                body = body[second + 3:]
        forbidden = [
            "proceed", "iterate", "tiebreaker", "escalate",
            "force_proceed", "abort", "replan", "add_note",
        ]
        for word in forbidden:
            assert word not in body, (
                f"decision_edges body contains forbidden Megaplan literal: {word!r}"
            )


# ---------------------------------------------------------------------------
# T6: loop_back_stage tests
# ---------------------------------------------------------------------------


class _FakeStep:
    """Minimal Step for topology tests — doesn't need to run."""

    def __init__(self, name: str = "fake", kind: str = "compute") -> None:
        self.name = name
        self.kind = kind

    def run(self, ctx: StepContext) -> StepResult:
        raise NotImplementedError("test-only stub")


class TestLoopBackStage:
    """Tests for :func:`arnold.pipeline.pattern_topology.loop_back_stage`."""

    def test_basic_stage_with_single_decision_and_loop_back(self) -> None:
        from arnold.pipeline.pattern_topology import loop_back_stage

        step = _FakeStep("gate")
        stage = loop_back_stage(
            name="gate",
            step=step,
            decisions={"approve": "done"},
            on_loop_back="gate",
        )
        assert stage.name == "gate"
        assert stage.step is step
        assert len(stage.edges) == 2  # decision + loop_back
        assert stage.edges[0].kind == "decision"
        assert stage.edges[0].label == "approve"
        assert stage.edges[0].target == "done"
        assert stage.edges[1].kind == "normal"
        assert stage.edges[1].label == "loop_back"
        assert stage.edges[1].target == "gate"

    def test_loop_back_label_is_caller_supplied(self) -> None:
        from arnold.pipeline.pattern_topology import loop_back_stage

        step = _FakeStep("judge")
        stage = loop_back_stage(
            name="judge",
            step=step,
            decisions={"retry": "revise"},
            on_loop_back="judge",
            loop_back_label="iterate",
        )
        assert len(stage.edges) == 2
        loop_edge = stage.edges[1]
        assert loop_edge.kind == "normal"
        assert loop_edge.label == "iterate"  # caller-supplied, not baked in
        assert loop_edge.target == "judge"

    def test_decisions_before_loop_back_before_fallback(self) -> None:
        from arnold.pipeline.pattern_topology import loop_back_stage
        from arnold.pipeline.types import Edge

        step = _FakeStep("gate")
        fb = (Edge(label="extra", target="other", kind="normal"),)
        stage = loop_back_stage(
            name="gate",
            step=step,
            decisions={"proceed": "done", "rework": "revise"},
            on_loop_back="gate",
            fallback_edges=fb,
        )
        # Order: decision, decision, loop_back, fallback
        assert len(stage.edges) == 4
        assert stage.edges[0].kind == "decision"
        assert stage.edges[0].label == "proceed"
        assert stage.edges[1].kind == "decision"
        assert stage.edges[1].label == "rework"
        assert stage.edges[2].kind == "normal"
        assert stage.edges[2].label == "loop_back"
        assert stage.edges[3].kind == "normal"
        assert stage.edges[3].label == "extra"

    def test_overrides_included_before_loop_back(self) -> None:
        from arnold.pipeline.pattern_topology import loop_back_stage

        step = _FakeStep("gate")
        stage = loop_back_stage(
            name="gate",
            step=step,
            decisions={"approve": "done"},
            overrides={"abort": "halt"},
            on_loop_back="gate",
        )
        # decision, override, loop_back
        assert len(stage.edges) == 3
        assert stage.edges[0].kind == "decision"
        assert stage.edges[0].label == "approve"
        assert stage.edges[1].kind == "override"
        assert stage.edges[1].label == "override abort"
        assert stage.edges[2].kind == "normal"
        assert stage.edges[2].label == "loop_back"

    def test_vocabularies_passed_through(self) -> None:
        from arnold.pipeline.pattern_topology import loop_back_stage

        step = _FakeStep("gate")
        stage = loop_back_stage(
            name="gate",
            step=step,
            decisions={"proceed": "done", "iterate": "revise"},
            on_loop_back="gate",
            decision_vocabulary=frozenset({"proceed", "iterate"}),
            override_vocabulary=frozenset({"force_proceed"}),
        )
        assert stage.decision_vocabulary == frozenset({"proceed", "iterate"})
        assert stage.override_vocabulary == frozenset({"force_proceed"})

    def test_loop_back_target_is_caller_supplied_not_hardcoded(self) -> None:
        from arnold.pipeline.pattern_topology import loop_back_stage

        step = _FakeStep("my_stage")
        stage = loop_back_stage(
            name="my_stage",
            step=step,
            decisions={"go": "next"},
            on_loop_back="some_other_stage",  # caller chooses target
            loop_back_label="revisit",
        )
        loop_edge = stage.edges[1]
        assert loop_edge.target == "some_other_stage"

    def test_no_megaplan_label_literals_in_loop_back_stage_source(self) -> None:
        import inspect
        from arnold.pipeline.pattern_topology import loop_back_stage

        src = inspect.getsource(loop_back_stage)
        # Strip the docstring — it mentions literals to disclaim they
        # are NOT used.  The body must be clean.
        body = src
        first = body.find('"""')
        if first != -1:
            second = body.find('"""', first + 3)
            if second != -1:
                body = body[second + 3:]
        forbidden = [
            "proceed", "iterate", "tiebreaker", "escalate",
            "force_proceed", "abort", "replan", "add_note",
        ]
        for word in forbidden:
            assert word not in body, (
                f"loop_back_stage body contains forbidden Megaplan literal: {word!r}"
            )
