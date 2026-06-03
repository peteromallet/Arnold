"""Tests for :mod:`megaplan._pipeline.builder` (Phase 1 / Step 5.6).

Three contract assertions per the T6 brief:

* ``Pipeline.builder('x').agent(...).gate(...).build()`` produces the
  same Stage/Edge graph as manual :class:`Pipeline` /
  :class:`Stage` / :class:`Edge` construction.
* ``.panel(... reviewers=[...])`` plumbs ``_panel_reviewer_order`` onto
  the downstream :class:`AgentStep` (private field, per T1.i decision).
* ``.human_gate(... options=['continue','stop'], edges={'continue':
  'panel_review', 'stop': 'done'})`` constructs a :class:`HumanDecisionStep`
  with ``_choices=['continue','stop']`` and a :class:`Stage` carrying
  exactly ``Edge('continue','panel_review')`` and ``Edge('stop','done')``.
  The pipeline tolerates the loop edge from ``human_decide`` back to
  the parent ParallelStage ``panel_review`` (re-entry behaviour locked
  in explicitly).
"""

from __future__ import annotations

from dataclasses import dataclass

from megaplan._pipeline.builder import PipelineBuilder
from megaplan._pipeline.steps.agent import AgentStep
from megaplan._pipeline.steps.human_gate import HumanDecisionStep
from megaplan._pipeline.steps.panel import PanelReviewerStep
from megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


@dataclass
class _StubGateStep:
    """Lightweight Step double used as the gate's underlying Step.

    The builder's ``.gate`` method takes ``step=`` directly and wires
    the four ``kind='decision'`` edges itself, so the Step
    implementation only needs to satisfy the Protocol shape.
    """

    name: str = "gate"
    kind: str = "judge"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult(next="proceed")


# ── (a) builder vs manual equivalence ─────────────────────────────────


class TestBuilderEquivalence:
    def test_agent_then_gate_matches_manual_construction(self) -> None:
        gate_step = _StubGateStep()

        built = (
            Pipeline.builder("equiv")
            .agent("plan", prompt="prompts/plan.md", inputs=["draft"])
            .gate(
                "gate",
                step=gate_step,
                on_proceed="finalize",
                on_iterate="plan",
                on_tiebreaker="tiebreaker",
                on_escalate="halt",
            )
            .build()
        )

        # Manual reference: same shape, edge-for-edge.
        manual_plan = Stage(
            name="plan",
            step=AgentStep(
                name="plan",
                kind="produce",
                prompt_key=None,
                slot=None,
                _prompt_ref="prompts/plan.md",
                _pipeline_name="equiv",
                _input_refs=["draft"],
                _produces="markdown",
                _panel_reviewer_order={},
                _mode="",
            ),
            edges=(Edge(label="done", target="gate"),),
        )
        manual_gate = Stage(
            name="gate",
            step=gate_step,
            edges=(
                Edge(label="proceed", target="finalize", kind="decision"),
                Edge(label="iterate", target="plan", kind="decision"),
                Edge(label="tiebreaker", target="tiebreaker", kind="decision"),
                Edge(label="escalate", target="halt", kind="decision"),
            ),
        )
        expected = Pipeline(
            stages={"plan": manual_plan, "gate": manual_gate},
            entry="plan",
        )

        assert set(built.stages) == set(expected.stages)
        assert built.entry == expected.entry

        # Compare edges verbatim for each stage.
        for stage_name in expected.stages:
            assert built.stages[stage_name].edges == expected.stages[stage_name].edges, (
                stage_name,
                built.stages[stage_name].edges,
                expected.stages[stage_name].edges,
            )

        # The plan-stage Step is an AgentStep with the right wiring.
        plan_step = built.stages["plan"].step
        assert isinstance(plan_step, AgentStep)
        assert plan_step._prompt_ref == "prompts/plan.md"
        assert plan_step._input_refs == ["draft"]
        assert plan_step._pipeline_name == "equiv"

        # The gate stage carries the supplied Step object directly.
        assert built.stages["gate"].step is gate_step


# ── (b) panel → agent reviewer-order plumbing ──────────────────────────


class TestPanelReviewerOrderPlumbing:
    def test_downstream_agent_carries_panel_reviewer_order_private_field(self) -> None:
        built = (
            Pipeline.builder("panel-fanin")
            .input("draft", file=True)
            .panel(
                "panel_review",
                reviewers=[
                    ("pessimist", "prompts/pessimist.md"),
                    ("optimist", "prompts/optimist.md"),
                    ("structuralist", "prompts/structuralist.md"),
                ],
                inputs=["draft"],
                merge="none",
            )
            .agent("synth", prompt="prompts/synth.md", inputs=["panel_review.*"])
            .build()
        )

        panel = built.stages["panel_review"]
        assert isinstance(panel, ParallelStage)
        # Three reviewer Steps in declared order.
        assert tuple(s.name for s in panel.steps) == (
            "panel_review.pessimist",
            "panel_review.optimist",
            "panel_review.structuralist",
        )
        for s in panel.steps:
            assert isinstance(s, PanelReviewerStep)

        synth = built.stages["synth"]
        assert isinstance(synth, Stage)
        synth_step = synth.step
        assert isinstance(synth_step, AgentStep)
        # T1.i lock: builder uses the PRIVATE _panel_reviewer_order field.
        assert synth_step._panel_reviewer_order == {
            "panel_review": ["pessimist", "optimist", "structuralist"],
        }


# ── (c) human_gate construction + loop-edge re-entry ───────────────────


class TestHumanGateConstruction:
    def _build_writing_panel_shape(self) -> Pipeline:
        return (
            Pipeline.builder("hg-loop")
            .input("draft", file=True)
            .panel(
                "panel_review",
                reviewers=[
                    ("pessimist", "prompts/pessimist.md"),
                    ("optimist", "prompts/optimist.md"),
                    ("structuralist", "prompts/structuralist.md"),
                ],
                inputs=["draft"],
            )
            .agent("synth", prompt="prompts/synth.md", inputs=["panel_review.*"])
            .agent("revise", prompt="prompts/revise.md", inputs=["draft", "synth"])
            .human_gate(
                "human_decide",
                artifact="revise",
                options=["continue", "stop"],
                edges={"continue": "panel_review", "stop": "done"},
            )
            .build()
        )

    def test_human_gate_step_carries_choices_and_artifact_stage(self) -> None:
        pipeline = self._build_writing_panel_shape()
        hg_stage = pipeline.stages["human_decide"]
        assert isinstance(hg_stage, Stage)
        hg = hg_stage.step
        assert isinstance(hg, HumanDecisionStep)
        # callers-1 lock: _choices is a plain list of options in order.
        assert hg._choices == ["continue", "stop"]
        assert hg._artifact_stage == "revise"
        assert hg._pipeline_name == "hg-loop"

    def test_human_gate_stage_edges_match_options_and_targets(self) -> None:
        pipeline = self._build_writing_panel_shape()
        hg_stage = pipeline.stages["human_decide"]
        assert isinstance(hg_stage, Stage)
        # Two edges, in caller-declared option order, no recommendation kind.
        assert hg_stage.edges == (
            Edge(label="continue", target="panel_review"),
            Edge(label="stop", target="done"),
        )
        for e in hg_stage.edges:
            assert e.kind == "normal"
            assert e.recommendation is None

    def test_continue_edge_loops_back_to_parallel_stage(self) -> None:
        """The ``continue`` edge must target the parent
        :class:`ParallelStage` ``panel_review`` — locks in the
        executor's existing YAML re-entry behaviour explicitly."""
        pipeline = self._build_writing_panel_shape()
        hg_stage = pipeline.stages["human_decide"]
        assert isinstance(hg_stage, Stage)
        continue_edge = next(e for e in hg_stage.edges if e.label == "continue")
        assert continue_edge.target == "panel_review"
        # The loop target exists in the graph and is a ParallelStage.
        target = pipeline.stages[continue_edge.target]
        assert isinstance(target, ParallelStage)
        assert target.name == "panel_review"

    def test_stop_edge_targets_done(self) -> None:
        pipeline = self._build_writing_panel_shape()
        hg_stage = pipeline.stages["human_decide"]
        assert isinstance(hg_stage, Stage)
        stop_edge = next(e for e in hg_stage.edges if e.label == "stop")
        assert stop_edge.target == "done"


def test_build_with_binding_flag_off_keeps_binding_map_none(monkeypatch):
    """Flag-OFF: build_with_binding returns pipeline with binding_map None."""
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    from megaplan._core.workflow import build_with_binding
    from megaplan._pipeline.types import Edge, Pipeline, Stage

    class _S:
        name = "s"; kind = "produce"; prompt_key = None; slot = None
        produces = (); consumes = ()
        def run(self, ctx):  # pragma: no cover
            raise NotImplementedError

    pipe = Pipeline(
        stages={"s": Stage(name="s", step=_S(), edges=(Edge("done", "halt"),))},
        entry="s",
    )
    out = build_with_binding(pipe)
    assert out is pipe
    assert out.binding_map is None
