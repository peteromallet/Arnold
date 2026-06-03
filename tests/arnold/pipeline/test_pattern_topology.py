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
from megaplan._pipeline.types import Edge, ParallelStage


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
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("panel", (("reviewer_a", r1),))
        assert isinstance(stage, ParallelStage)
        assert stage.name == "panel"
        assert len(stage.steps) == 1

    def test_multiple_reviewers_fan_out(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1", {"draft": "/tmp/r1.md"})
        r2 = _ReviewerStep("r2", {"draft": "/tmp/r2.md"})
        r3 = _ReviewerStep("r3", {"draft": "/tmp/r3.md"})

        stage = panel_parallel(
            "panel",
            (("a", r1), ("b", r2), ("c", r3)),
        )
        assert len(stage.steps) == 3

    def test_default_next_label_is_next(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("p", (("x", r1),))
        # The join callable should be set
        assert stage.join is not None
        # Verify the join produces the correct next="next" behaviour
        ctx = StepContext(artifact_root="/tmp", state={})
        result = stage.join([StepResult(next="halt", outputs={"k": "v"})], ctx)
        assert result.next == "next"

    def test_custom_next_label(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("p", (("x", r1),), next_label="done")
        ctx = StepContext(artifact_root="/tmp", state={})
        result = stage.join([StepResult(next="halt", outputs={"k": "v"})], ctx)
        assert result.next == "done"

    def test_custom_edges_passed_through(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel(
            "panel",
            (("x", r1),),
            edges=(Edge(label="done", target="halt"),),
        )
        assert len(stage.edges) == 1
        assert stage.edges[0].label == "done"

    def test_max_workers_passed_through(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        r2 = _ReviewerStep("r2")
        stage = panel_parallel("p", (("a", r1), ("b", r2)), max_workers=1)
        assert stage.max_workers == 1

    def test_merge_strategy_accepted_but_ignored(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        r1 = _ReviewerStep("r1")
        stage = panel_parallel("p", (("x", r1),), merge_strategy="structural")
        assert isinstance(stage, ParallelStage)  # doesn't crash

    def test_empty_reviewers_works(self) -> None:
        from megaplan._pipeline.pattern_topology import panel_parallel

        stage = panel_parallel("empty_panel", ())
        assert len(stage.steps) == 0
        assert isinstance(stage, ParallelStage)

    def test_join_collates_per_reviewer_outputs(self) -> None:
        """The built-in join prefixes each reviewer's outputs with reviewer_id."""
        from megaplan._pipeline.pattern_topology import panel_parallel

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
        from megaplan._pipeline.pattern_topology import panel_parallel

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
        from megaplan._pipeline.pattern_topology import panel_parallel

        src = inspect.getsource(panel_parallel)
        forbidden = ["tiebreaker", "proceed", "iterate", "escalate", "planning"]
        for word in forbidden:
            assert word not in src, (
                f"panel_parallel source contains forbidden word: {word!r}"
            )

    def test_panel_parallel_uses_parallel_stage_type(self) -> None:
        """The function body constructs a ParallelStage — the neutral primitive."""
        import inspect
        from megaplan._pipeline.pattern_topology import panel_parallel

        src = inspect.getsource(panel_parallel)
        assert "ParallelStage" in src
