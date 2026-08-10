"""Targeted unit tests for megaplan._pipeline.patterns.

One test per pattern covering the produced Stage/Edge graph: stage
names, ``Edge.kind`` ('normal' vs 'decision'), and recommendation targets
for decision edges. Explicit regression cases are spelled out for the three
patterns highlighted in the brief:

* ``critique_revise_gate_loop`` — ``gate_extra_edges`` passthrough
  produces exactly the four ``kind='decision'`` edges plus
  every caller-supplied extra edge, in order.
* ``panel_parallel`` — three reviewers produce a :class:`ParallelStage`
  whose join collates per-reviewer outputs as ``{reviewer_id}.{label}``
  in reviewer-list order.
* ``subpipeline_call`` — round-trips a child :class:`Pipeline` via
  :class:`SubloopStep`, with the ``promote`` callable mapping child
  state via the planning binding onto the parent's
  :class:`PipelineVerdict`.

Post-M3b (T12): GateRecommendation typed literal is removed.
Recommendation fields use plain ``str`` throughout.  The ``_promote``
callable returns ``str`` and ``_VerdictStep.recommendation`` is ``str``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold.pipelines.megaplan._pipeline.patterns import (
    alternating_turns,
    critique_revise_gate_loop,
    escalate_if,
    iterate_until,
    majority_vote,
    mode_prompts,
    panel_parallel,
    phase_zero_gate,
    subpipeline_call,
)
import pytest

from arnold.pipelines.megaplan._pipeline.subloop import SubloopStep
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    ReadRef,
    ReduceResult,
    Stage,
    StepContext,
    StepResult,
    PipelineVerdict,
    WriteRef,
)
from arnold.pipeline.step_invocation import StepInvocation


# ── Lightweight Step doubles ───────────────────────────────────────────


@dataclass
class _StubStep:
    """Synthetic Step satisfying the Protocol — emits a fixed
    ``StepResult`` regardless of context. Used wherever the topology
    of the produced graph is what we care about, not Step behaviour."""

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover - not exercised
        return StepResult(next="done")


@dataclass
class _StatePatchStep:
    """Step double that writes ``current_state`` into ``state_patch``.

    Mirrors the runtime shape of ``InProcessHandlerStep`` — the legacy
    handler-backed Step that updates ``state.json`` from a real
    ``handle_<phase>`` call — without the heavyweight plan-dir /
    argparse plumbing those handlers require. Used by the
    ``subpipeline_call`` round-trip test so the parent ``promote``
    callable sees a populated child ``state`` mapping.
    """

    name: str
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    final_state: str = "critiqued"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            outputs={},
            next="halt",
            state_patch={"current_state": self.final_state},
        )


@dataclass
class _VerdictStep:
    """Step that emits a fixed :class:`PipelineVerdict.recommendation`."""

    name: str
    recommendation: str
    kind: str = "judge"
    prompt_key: str | None = None
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            outputs={Path("v1.md").name: ctx.plan_dir / f"{self.name}.md"},
            verdict=PipelineVerdict(score=1.0, recommendation=self.recommendation),
            next=self.recommendation,
        )


# ── critique_revise_gate_loop ──────────────────────────────────────────


class TestCritiqueReviseGateLoop:
    def test_default_shape_three_stages_with_gate_recommendation_edges(self) -> None:
        stages = critique_revise_gate_loop(
            critique_step=_StubStep(name="critique"),
            gate_step=_StubStep(name="gate", kind="decide"),
            revise_step=_StubStep(name="revise"),
            on_proceed="finalize",
            on_iterate="revise",
            on_tiebreaker="tiebreaker",
            on_escalate="halt",
        )

        assert set(stages.keys()) == {"critique", "gate", "revise"}

        # Gate carries exactly the four kind='decision' edges.
        gate_edges = stages["gate"].edges
        assert len(gate_edges) == 4
        assert all(e.kind == "decision" for e in gate_edges)
        label_targets = {e.label: e.target for e in gate_edges}
        assert label_targets == {
            "iterate": "revise",
            "proceed": "finalize",
            "tiebreaker": "tiebreaker",
            "escalate": "halt",
        }

        # Critique falls back to the default Edge("gate","gate").
        critique_edges = stages["critique"].edges
        assert len(critique_edges) == 1
        assert critique_edges[0] == Edge(label="gate", target="gate")
        assert critique_edges[0].kind == "normal"

        # Revise loops back to the default revise_target ('critique').
        revise_edges = stages["revise"].edges
        assert len(revise_edges) == 1
        assert revise_edges[0].target == "critique"
        assert revise_edges[0].kind == "normal"

    def test_gate_extra_edges_passthrough_regression(self) -> None:
        """Regression (a): when caller passes four gate_extra_edges, the
        gate stage carries the four recommendation-kind edges followed by
        the four extra edges in supplied order — eight edges total."""

        extra = (
            # Override edges (kind='override' — reserved literal, not
            # dispatched by today's executor but valid on the graph).
            Edge(label="override force-proceed", target="finalize", kind="override"),
            Edge(label="override abort", target="halt", kind="override"),
            # Label-fallback edges (kind='normal' is the default).
            Edge(label="revise", target="revise"),
            Edge(label="gate", target="finalize"),
        )

        stages = critique_revise_gate_loop(
            critique_step=_StubStep(name="critique"),
            gate_step=_StubStep(name="gate", kind="decide"),
            revise_step=_StubStep(name="revise"),
            on_proceed="finalize",
            on_iterate="revise",
            on_tiebreaker="tiebreaker",
            on_escalate="finalize",
            gate_extra_edges=extra,
        )
        gate_edges = stages["gate"].edges
        assert len(gate_edges) == 8

        # First four edges are the decision edges, in fixed order.
        rec_only = gate_edges[:4]
        assert [e.label for e in rec_only] == [
            "proceed", "iterate", "tiebreaker", "escalate",
        ]
        assert all(e.kind == "decision" for e in rec_only)

        # The last four are the caller-supplied extras, in supplied order.
        assert tuple(gate_edges[4:]) == extra

    def test_critique_fallback_edges_and_custom_revise_target(self) -> None:
        critique_fallbacks = (
            Edge(label="gate_unset:gate", target="gate"),
            Edge(label="gate", target="gate"),
        )
        stages = critique_revise_gate_loop(
            critique_step=_StubStep(name="critique"),
            gate_step=_StubStep(name="gate", kind="decide"),
            revise_step=_StubStep(name="revise"),
            on_proceed="finalize",
            on_iterate="revise",
            on_tiebreaker="tiebreaker",
            on_escalate="halt",
            critique_fallback_edges=critique_fallbacks,
            revise_target="prep",
        )
        assert stages["critique"].edges == critique_fallbacks
        # Revise edge comes from routing plugin (Arnold Edge without recommendation field).
        revise_edges = stages["revise"].edges
        assert len(revise_edges) == 1
        assert revise_edges[0].label == "critique"
        assert revise_edges[0].target == "prep"
        assert revise_edges[0].kind == "normal"


# ── panel_parallel ─────────────────────────────────────────────────────


class TestPanelParallel:
    def test_three_reviewers_fan_out_and_ordered_join(self, tmp_path: Path) -> None:
        """Regression (b): three reviewers produce a :class:`ParallelStage`
        with three sub-steps; the join collates per-reviewer outputs as
        ``{reviewer_id}.{label}`` in reviewer-list order."""

        pessimist = _StubStep(name="panel_review.pessimist")
        optimist = _StubStep(name="panel_review.optimist")
        structuralist = _StubStep(name="panel_review.structuralist")

        stage = panel_parallel(
            "panel_review",
            reviewers=(
                ("pessimist", pessimist),
                ("optimist", optimist),
                ("structuralist", structuralist),
            ),
            edges=(Edge(label="next", target="synth"),),
        )

        assert isinstance(stage, ParallelStage)
        assert stage.name == "panel_review"
        assert stage.steps == (pessimist, optimist, structuralist)
        assert stage.edges == (Edge(label="next", target="synth"),)

        # Drive the join with three per-reviewer StepResults; verify the
        # collated output keys preserve reviewer-list order via insertion
        # order, and that the join emits next='next' for the single
        # downstream synthesis edge.
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
        results = [
            StepResult(outputs={"draft": tmp_path / "pessimist.md"}),
            StepResult(outputs={"draft": tmp_path / "optimist.md"}),
            StepResult(outputs={"draft": tmp_path / "structuralist.md"}),
        ]
        merged = stage.join(results, ctx)
        assert merged.next == "next"

        # Reviewer-list order is reflected in dict insertion order, and
        # each reviewer's outputs are keyed under '<reviewer_id>.<label>'.
        assert list(merged.outputs.keys()) == [
            "pessimist.draft",
            "optimist.draft",
            "structuralist.draft",
        ]
        assert merged.outputs["pessimist.draft"] == tmp_path / "pessimist.md"
        assert merged.outputs["optimist.draft"] == tmp_path / "optimist.md"
        assert merged.outputs["structuralist.draft"] == tmp_path / "structuralist.md"

    def test_custom_next_label(self, tmp_path: Path) -> None:
        stage = panel_parallel(
            "panel",
            reviewers=(("solo", _StubStep(name="panel.solo")),),
            next_label="merge",
        )
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
        merged = stage.join([StepResult(outputs={})], ctx)
        assert merged.next == "merge"

    def test_panel_parallel_preserves_authored_fields(self) -> None:
        invocation = StepInvocation(kind="tool", metadata={"action": "fanout"})
        stage = panel_parallel(
            "panel_review",
            reviewers=(("solo", _StubStep(name="panel.solo")),),
            reads=(PortRef(port_name="draft", content_type="text/markdown"),),
            writes=(Port(name="review", content_type="text/markdown"),),
            invocation=invocation,
            required_capabilities=("model:text", "fs-write"),
        )

        assert isinstance(stage, ParallelStage)
        assert stage.reads == (PortRef(port_name="draft", content_type="text/markdown"),)
        assert stage.writes == (Port(name="review", content_type="text/markdown"),)
        assert stage.invocation == invocation
        assert stage.required_capabilities == ("model:text", "fs-write")


# ── alternating_turns ──────────────────────────────────────────────────


class TestAlternatingTurns:
    def test_linear_chain_with_terminal_loop_back(self) -> None:
        stages = alternating_turns(
            roles=(
                ("a", _StubStep(name="a")),
                ("b", _StubStep(name="b")),
                ("c", _StubStep(name="c")),
            ),
        )
        assert list(stages.keys()) == ["a", "b", "c"]
        assert stages["a"].edges == (Edge(label="b", target="b"),)
        assert stages["b"].edges == (Edge(label="c", target="c"),)
        # Terminal loops back to the first role.
        assert stages["c"].edges == (Edge(label="a", target="a"),)

    def test_loop_target_override(self) -> None:
        stages = alternating_turns(
            roles=(("a", _StubStep(name="a")), ("b", _StubStep(name="b"))),
            loop_target="halt",
        )
        assert stages["b"].edges == (Edge(label="halt", target="halt"),)


# ── subpipeline_call ───────────────────────────────────────────────────


class TestSubpipelineCall:
    def test_round_trip_promote_maps_child_state_to_recommendation(
        self, tmp_path: Path
    ) -> None:
        """Regression (c): the child Pipeline runs under :class:`SubloopStep`
        with its state propagating back via the ``promote`` callable as a
        plain ``str`` recommendation on the parent's :class:`PipelineVerdict`."""

        # Child pipeline: a single Step that publishes
        # ``current_state='critiqued'`` (the shape an InProcessHandlerStep
        # produces when its handler advances the state machine).
        child_step = _StatePatchStep(name="run", final_state="critiqued")
        child = Pipeline(
            stages={"run": Stage(name="run", step=child_step, edges=())},
            entry="run",
        )

        def _promote(state: dict[str, Any]) -> str:
            cs = state.get("current_state", "")
            if cs == "critiqued":
                return "iterate"
            if cs == "aborted":
                return "escalate"
            return "proceed"

        subloop = subpipeline_call(
            child, promote=_promote, artifact_subdir="tiebreaker"
        )
        assert isinstance(subloop, SubloopStep)
        assert subloop.child_pipeline is child
        assert subloop.artifact_subdir == "tiebreaker"
        assert subloop.kind == "subloop"

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test"
        )
        result = subloop.run(ctx)
        assert result.verdict is not None
        assert result.verdict.recommendation == "iterate"
        assert result.next == "iterate"
        # SubloopStep stashes the child state under the subloop:<name>:state key.
        assert (
            result.state_patch[f"subloop:{subloop.name}:recommendation"] == "iterate"
        )

    def test_promote_can_route_to_escalate(self, tmp_path: Path) -> None:
        child_step = _StatePatchStep(name="run", final_state="aborted")
        child = Pipeline(
            stages={"run": Stage(name="run", step=child_step, edges=())},
            entry="run",
        )

        def _promote(state: dict[str, Any]) -> str:
            return "escalate" if state.get("current_state") == "aborted" else "proceed"

        subloop = subpipeline_call(child, promote=_promote)
        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test"
        )
        result = subloop.run(ctx)
        assert result.verdict is not None
        assert result.verdict.recommendation == "escalate"


# ── mode_prompts ───────────────────────────────────────────────────────


class TestModePrompts:
    def test_overlay_swaps_prompt_key_per_mode(self) -> None:
        @dataclass
        class _PromptStep:
            name: str
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
                return StepResult(next="done")

        pipeline = Pipeline(
            stages={
                "draft": Stage(
                    name="draft",
                    step=_PromptStep(name="draft", prompt_key="default"),
                ),
            },
            entry="draft",
        )

        builder = mode_prompts({"polish": {"draft": "polish_prompt"}})
        overlay = builder("polish")
        out = overlay.apply(pipeline)
        new_stage = out.stages["draft"]
        assert isinstance(new_stage, Stage)
        assert new_stage.step.prompt_key == "polish_prompt"

        # Unknown mode yields a no-op overlay (no per-stage entries).
        passthrough = builder("unknown-mode").apply(pipeline)
        ps_stage = passthrough.stages["draft"]
        assert isinstance(ps_stage, Stage)
        assert ps_stage.step.prompt_key == "default"

    def test_overlay_preserves_stage_and_pipeline_fields(self) -> None:
        @dataclass
        class _PromptStep:
            name: str
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
                return StepResult(next="done")

        invocation = StepInvocation(kind="model", metadata={"prompt": "default"})
        loop_condition = lambda state: False
        pipeline = Pipeline(
            stages={
                "draft": Stage(
                    name="draft",
                    step=_PromptStep(name="draft", prompt_key="default"),
                    reads=(ReadRef(name="brief.md"),),
                    writes=(WriteRef(name="draft.md"),),
                    produces=(Port(name="draft", content_type="text/markdown"),),
                    consumes=(PortRef(port_name="brief", content_type="text/markdown"),),
                    invocation=invocation,
                    required_capabilities=("llm", "fs-write"),
                    decision_vocabulary=frozenset({"proceed"}),
                    override_vocabulary=frozenset({"stop"}),
                    loop_condition=loop_condition,
                ),
            },
            entry="draft",
            binding_map={"draft": "binding"},
            resource_bundles=("bundle",),
        )

        overlay = mode_prompts({"polish": {"draft": "polish_prompt"}})("polish")
        out = overlay.apply(pipeline)
        new_stage = out.stages["draft"]
        assert isinstance(new_stage, Stage)
        assert new_stage.step.prompt_key == "polish_prompt"
        assert new_stage.reads == pipeline.stages["draft"].reads
        assert new_stage.writes == pipeline.stages["draft"].writes
        assert new_stage.produces == pipeline.stages["draft"].produces
        assert new_stage.consumes == pipeline.stages["draft"].consumes
        assert new_stage.invocation == invocation
        assert new_stage.required_capabilities == ("llm", "fs-write")
        assert new_stage.decision_vocabulary == frozenset({"proceed"})
        assert new_stage.override_vocabulary == frozenset({"stop"})
        assert new_stage.loop_condition is loop_condition
        assert out.binding_map == pipeline.binding_map
        assert out.resource_bundles == pipeline.resource_bundles


# ── iterate_until ──────────────────────────────────────────────────────


class TestIterateUntil:
    def test_adds_self_loop_and_halt_edge(self) -> None:
        base = Stage(
            name="loop",
            step=_StubStep(name="loop"),
            edges=(Edge(label="next", target="finalize"),),
        )
        wrapped = iterate_until(base, condition=lambda s: True, max_iterations=3)
        assert wrapped.name == "loop"
        labels = [(e.label, e.target) for e in wrapped.edges]
        assert ("next", "finalize") in labels
        assert ("iterate", "loop") in labels
        assert ("halt", "halt") in labels

    def test_preserves_stage_fields_while_adding_loop_edges(self) -> None:
        invocation = StepInvocation(kind="model", metadata={"prompt": "loop"})
        prior_loop_condition = lambda state: False
        base = Stage(
            name="loop",
            step=_StubStep(name="loop"),
            edges=(Edge(label="next", target="finalize"),),
            reads=(ReadRef(name="brief.md"),),
            writes=(WriteRef(name="draft.md"),),
            produces=(Port(name="draft", content_type="text/markdown"),),
            consumes=(PortRef(port_name="brief", content_type="text/markdown"),),
            invocation=invocation,
            required_capabilities=("llm",),
            decision_vocabulary=frozenset({"proceed"}),
            override_vocabulary=frozenset({"stop"}),
            loop_condition=prior_loop_condition,
        )

        wrapped = iterate_until(base, condition=lambda s: True, max_iterations=3)
        assert wrapped.reads == base.reads
        assert wrapped.writes == base.writes
        assert wrapped.produces == base.produces
        assert wrapped.consumes == base.consumes
        assert wrapped.invocation == invocation
        assert wrapped.required_capabilities == base.required_capabilities
        assert wrapped.decision_vocabulary == base.decision_vocabulary
        assert wrapped.override_vocabulary == base.override_vocabulary
        assert wrapped.loop_condition is not None
        assert wrapped.loop_condition is not prior_loop_condition


# ── escalate_if ────────────────────────────────────────────────────────


class TestEscalateIf:
    def test_returns_escape_edge_with_decision_kind_and_label(self) -> None:
        handler = _StubStep(name="escalate_to_human")
        step, edge = escalate_if(lambda s: True, handler)
        assert step is handler
        assert edge.kind == "decision"
        assert edge.label == "escalate"
        assert edge.target == "escalate_to_human"


# ── majority_vote ──────────────────────────────────────────────────────


@pytest.mark.parametrize("typed_ports", [False, True])
class TestMajorityVote:
    def test_strict_majority_wins(
        self, tmp_path: Path, typed_ports: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1" if typed_ports else "")
        join = majority_vote()
        results = [
            StepResult(verdict=PipelineVerdict(score=1.0, recommendation="proceed")),
            StepResult(verdict=PipelineVerdict(score=1.0, recommendation="proceed")),
            StepResult(verdict=PipelineVerdict(score=1.0, recommendation="iterate")),
        ]
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
        merged = join(results, ctx)
        assert merged.verdict is not None
        if typed_ports:
            payload = merged.verdict.payload
            assert isinstance(payload, dict)
            reduce_result = payload["reduce_result"]
            assert isinstance(reduce_result, ReduceResult)
            assert reduce_result.value == "proceed"
            assert reduce_result.label == "proceed"
            assert merged.verdict.recommendation is None
        else:
            assert merged.verdict.recommendation == "proceed"
        assert merged.next == "proceed"

    def test_tie_routes_to_tiebreaker(
        self, tmp_path: Path, typed_ports: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1" if typed_ports else "")
        join = majority_vote()
        results = [
            StepResult(verdict=PipelineVerdict(score=1.0, recommendation="proceed")),
            StepResult(verdict=PipelineVerdict(score=1.0, recommendation="iterate")),
        ]
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
        merged = join(results, ctx)
        assert merged.verdict is not None
        if typed_ports:
            payload = merged.verdict.payload
            assert isinstance(payload, dict)
            reduce_result = payload["reduce_result"]
            assert isinstance(reduce_result, ReduceResult)
            assert reduce_result.value is None
            assert reduce_result.label is None
            assert merged.next == "tiebreaker"
        else:
            assert merged.verdict.recommendation == "tiebreaker"

    def test_empty_panel_routes_to_tiebreaker(
        self, tmp_path: Path, typed_ports: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1" if typed_ports else "")
        join = majority_vote()
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
        merged = join([StepResult()], ctx)
        assert merged.verdict is not None
        if typed_ports:
            payload = merged.verdict.payload
            assert isinstance(payload, dict)
            reduce_result = payload["reduce_result"]
            assert isinstance(reduce_result, ReduceResult)
            assert reduce_result.value is None
            assert merged.next == "tiebreaker"
        else:
            assert merged.verdict.recommendation == "tiebreaker"


# ── phase_zero_gate ────────────────────────────────────────────────────


class TestPhaseZeroGate:
    def test_emits_pass_fail_and_on_pass_fallback_edges(self) -> None:
        stage = phase_zero_gate(
            _StubStep(name="prep"),
            on_pass="plan",
            on_fail="halt",
        )
        labels = [(e.label, e.target) for e in stage.edges]
        assert labels == [
            ("pass", "plan"),
            ("fail", "halt"),
            ("plan", "plan"),
        ]
        assert all(e.kind == "normal" for e in stage.edges)

    def test_no_redundant_fallback_when_on_pass_is_keyword_label(self) -> None:
        stage = phase_zero_gate(_StubStep(name="prep"), on_pass="pass", on_fail="fail")
        labels = [(e.label, e.target) for e in stage.edges]
        assert labels == [("pass", "pass"), ("fail", "fail")]
