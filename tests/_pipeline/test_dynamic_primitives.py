"""Unit tests for the five dynamic primitives added in T2.

Covers the distinctive behaviour of each primitive in isolation, using
lightweight stub Steps and synthetic artifact files. Pattern mirrors
``tests/_pipeline/test_patterns.py`` (single-purpose stubs, frozen
``StepContext``, ``StepResult``-based observation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pytest

from megaplan._pipeline.patterns import (
    dynamic_fanout,
    iterate_until_consensus,
    paired_round,
    panel_from_artifact,
    weighted_vote,
)
from megaplan._pipeline.subloop import SubloopStep
from megaplan._pipeline.types import (
    GateRecommendation,
    Stage,
    StepContext,
    StepResult,
    PipelineVerdict,
)


# ── Stub steps ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _SectionStep:
    """Specialisable per-spec stub: writes a per-section artifact."""

    name: str = "section"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    section_id: str = ""
    section_title: str = ""

    def run(self, ctx: StepContext) -> StepResult:
        sid = self.section_id or "default"
        out = Path(ctx.plan_dir) / f"{sid}.md"
        out.write_text(f"# {self.section_title or sid}\n")
        return StepResult(outputs={sid: out}, next="done")


@dataclass(frozen=True)
class _GeneratorStep:
    """Emits ``specs`` via state_patch (in-memory list path)."""

    name: str = "generator"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    specs: tuple[Mapping[str, Any], ...] = ()

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(state_patch={"specs": list(self.specs)}, next="done")


@dataclass(frozen=True)
class _ReviewerStep:
    """Emits a PipelineVerdict with reviewer_id payload — feeds weighted_vote."""

    name: str = "reviewer"
    kind: str = "judge"
    prompt_key: str | None = None
    slot: str | None = None
    reviewer_id: str = ""
    recommendation: GateRecommendation = "proceed"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            verdict=PipelineVerdict(
                score=1.0,
                recommendation=self.recommendation,
                payload={"reviewer_id": self.reviewer_id},
            ),
            next=self.recommendation,
        )


@dataclass
class _AggregateStep:
    """Stateful stub for iterate_until_consensus tests.

    Emits a PipelineVerdict whose ``per_reviewer_recommendations`` payload is
    drawn from ``recs_per_call`` — one list per invocation. After the
    list is exhausted, the last entry is reused so trailing iterations
    have well-defined output.
    """

    name: str = "panel_aggregate"
    kind: str = "judge"
    prompt_key: str | None = None
    slot: str | None = None
    recs_per_call: list[list[GateRecommendation]] = field(default_factory=list)
    call_count: int = 0

    def run(self, ctx: StepContext) -> StepResult:
        idx = min(self.call_count, max(0, len(self.recs_per_call) - 1))
        recs = self.recs_per_call[idx] if self.recs_per_call else []
        self.call_count += 1
        # Aggregate verdict's recommendation is whichever is most-common
        # at the per-reviewer level (any tie-break is fine here — the
        # primitive consults the ratio, not the aggregate label).
        top: GateRecommendation = recs[0] if recs else "proceed"
        return StepResult(
            verdict=PipelineVerdict(
                score=1.0,
                recommendation=top,
                payload={"per_reviewer_recommendations": list(recs)},
            ),
            next=top,
        )


@dataclass(frozen=True)
class _AdvocateStep:
    """Advocate stub for paired_round: writes its argument to a file and
    records which prior advocate's artifact (if any) it observed.

    The recorded value is exposed via ``ctx.state['_paired_round_log']``
    so the test can assert that ``sees_other=True`` actually injects
    the prior turn's output into the next advocate's inputs.
    """

    name: str = "advocate"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    label: str = "arg"

    def run(self, ctx: StepContext) -> StepResult:
        prior_seen: list[str] = []
        if isinstance(ctx.inputs, Mapping):
            for k in ctx.inputs.keys():
                if k.startswith("prior."):
                    prior_seen.append(k)
        log = ctx.state.setdefault("_paired_round_log", {}) if isinstance(ctx.state, dict) else {}
        if isinstance(log, dict):
            log[self.name] = sorted(prior_seen)
        out = Path(ctx.plan_dir) / f"{self.name}.md"
        out.write_text(f"# argument from {self.name}\n")
        return StepResult(outputs={self.label: out}, next="done")


# ── (a) panel_from_artifact ────────────────────────────────────────────


class TestPanelFromArtifact:
    def test_reads_n_reviewers_from_json_and_runs_n_specialised_steps(
        self, tmp_path: Path
    ) -> None:
        # Write a 4-reviewer spec list to a JSON artifact under tmp_path.
        artifact = tmp_path / "specs.json"
        artifact.write_text(
            json.dumps(
                [
                    {"section_id": "alpha", "section_title": "Alpha"},
                    {"section_id": "beta", "section_title": "Beta"},
                    {"section_id": "gamma", "section_title": "Gamma"},
                    {"section_id": "delta", "section_title": "Delta"},
                ]
            )
        )

        observed: list[StepResult] = []

        def _collect_join(results: list[StepResult], ctx: StepContext) -> StepResult:
            observed.extend(results)
            return StepResult(next="next")

        primitive = panel_from_artifact(
            artifact_ref="sections",
            base_template=_SectionStep(),
            join=_collect_join,
            name="reviewer_panel",
        )
        # Committed SubloopStep shape — not conditional.
        assert isinstance(primitive, SubloopStep)

        ctx = StepContext(
            plan_dir=tmp_path,
            state={},
            profile=None,
            mode="test",
            inputs={"sections": artifact},
        )
        result = primitive.run(ctx)
        assert result.next == "next"

        # Four specialised steps fired — one per spec, with section_id
        # threaded through dataclasses.replace and reflected in each
        # output filename.
        assert len(observed) == 4
        produced_paths = sorted(
            str(next(iter(r.outputs.values()))) for r in observed
        )
        assert produced_paths == sorted(
            str(tmp_path / f"{sid}.md") for sid in ("alpha", "beta", "gamma", "delta")
        )

    def test_missing_artifact_raises(self, tmp_path: Path) -> None:
        primitive = panel_from_artifact(
            artifact_ref="missing",
            base_template=_SectionStep(),
            join=lambda results, ctx: StepResult(next="next"),
            name="panel",
        )
        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        with pytest.raises(LookupError):
            primitive.run(ctx)


# ── (b) dynamic_fanout ─────────────────────────────────────────────────


class TestDynamicFanout:
    def test_consumes_generator_specs_and_fans_out_base_prompt(
        self, tmp_path: Path
    ) -> None:
        generator = _GeneratorStep(
            specs=(
                {"section_id": "intro", "section_title": "Introduction"},
                {"section_id": "body", "section_title": "Body"},
                {"section_id": "conclusion", "section_title": "Conclusion"},
            ),
        )

        observed: list[StepResult] = []

        def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
            observed.extend(results)
            merged: dict[str, Path] = {}
            for r in results:
                for k, v in r.outputs.items():
                    merged[k] = v
            return StepResult(outputs=merged, next="critique")

        primitive = dynamic_fanout(
            generator=generator,
            base_prompt=_SectionStep(),
            join=_join,
            name="section_drafts",
        )
        # Committed SubloopStep shape — not conditional.
        assert isinstance(primitive, SubloopStep)

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        result = primitive.run(ctx)
        assert result.next == "critique"
        # One base_prompt invocation per spec — generator-driven N.
        assert len(observed) == 3
        # Each specialised step wrote its per-spec artifact (proves the
        # spec keys actually flowed via dataclasses.replace).
        for sid in ("intro", "body", "conclusion"):
            assert sid in result.outputs
            assert Path(result.outputs[sid]).exists()


# ── (c) weighted_vote ──────────────────────────────────────────────────


class TestWeightedVote:
    def test_higher_weighted_verdict_wins_when_raw_counts_differ(
        self, tmp_path: Path
    ) -> None:
        # Raw counts: 2 'iterate' vs 1 'proceed' — iterate would win by
        # majority_vote. But weights swing the result: proceed-weight=5,
        # iterate-weight=1 each (total iterate=2).
        weights = {"alice": 1.0, "bob": 1.0, "carol": 5.0}
        join_fn = weighted_vote(weights)

        results = [
            _ReviewerStep(reviewer_id="alice", recommendation="iterate").run(
                StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
            ),
            _ReviewerStep(reviewer_id="bob", recommendation="iterate").run(
                StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
            ),
            _ReviewerStep(reviewer_id="carol", recommendation="proceed").run(
                StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
            ),
        ]

        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        merged = join_fn(results, ctx)
        assert merged.verdict is not None
        assert merged.verdict.recommendation == "proceed"
        assert merged.next == "proceed"

    def test_empty_panel_resolves_to_tiebreaker(self, tmp_path: Path) -> None:
        join_fn = weighted_vote({"alice": 1.0})
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        merged = join_fn([], ctx)
        assert merged.verdict is not None
        assert merged.verdict.recommendation == "tiebreaker"


# ── (d) iterate_until_consensus ────────────────────────────────────────


class TestIterateUntilConsensus:
    def test_exits_when_panel_reaches_min_agreement(self, tmp_path: Path) -> None:
        # Pass 1: 2/4 = 0.5 (below 0.8 threshold).
        # Pass 2: 4/4 = 1.0 (above) — exit here.
        panel = _AggregateStep(
            recs_per_call=[
                ["proceed", "proceed", "iterate", "iterate"],
                ["proceed", "proceed", "proceed", "proceed"],
            ]
        )
        primitive = iterate_until_consensus(
            panel=panel, min_agreement=0.8, max_iters=5, name="consensus_loop"
        )
        assert isinstance(primitive, SubloopStep)
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        result = primitive.run(ctx)
        assert result.next == "halt"
        # Exited at iteration 2 with full agreement.
        assert panel.call_count == 2
        assert result.state_patch["consensus:consensus_loop:iterations"] == 2
        assert result.state_patch["consensus:consensus_loop:agreement"] == 1.0

    def test_runs_to_max_iters_when_consensus_never_reached(
        self, tmp_path: Path
    ) -> None:
        # Every pass is 50/50 — never crosses the threshold.
        panel = _AggregateStep(
            recs_per_call=[["proceed", "iterate"]],
        )
        primitive = iterate_until_consensus(
            panel=panel, min_agreement=0.9, max_iters=3, name="never_converges"
        )
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        result = primitive.run(ctx)
        # Falls through after max_iters; no halt by consensus.
        assert panel.call_count == 3
        assert result.state_patch["consensus:never_converges:iterations"] == 3
        # Final agreement was 0.5 (under threshold).
        assert result.state_patch["consensus:never_converges:agreement"] == 0.5

    def test_accepts_stage_wrapper(self, tmp_path: Path) -> None:
        panel = _AggregateStep(
            recs_per_call=[["proceed", "proceed", "proceed"]],
        )
        stage = Stage(name="panel_stage", step=panel, edges=())
        primitive = iterate_until_consensus(
            panel=stage, min_agreement=0.5, max_iters=2, name="stage_consensus"
        )
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        result = primitive.run(ctx)
        assert result.next == "halt"
        assert panel.call_count == 1


# ── (e) paired_round ───────────────────────────────────────────────────


class TestPairedRound:
    def test_sees_other_injects_prior_outputs_into_next_advocates_context(
        self, tmp_path: Path
    ) -> None:
        alice = _AdvocateStep(name="alice", label="arg")
        bob = _AdvocateStep(name="bob", label="arg")
        stage = paired_round([alice, bob], sees_other=True, name="debate")
        assert isinstance(stage, Stage)

        state: dict[str, Any] = {}
        ctx = StepContext(
            plan_dir=tmp_path, state=state, profile=None, mode="t", inputs={}
        )
        stage.step.run(ctx)
        log = state["_paired_round_log"]
        # Alice runs first — no prior turn to inject.
        assert log["alice"] == []
        # Bob runs second — sees alice's prior output under prior.<label>.
        assert log["bob"] == ["prior.arg"]

    def test_sees_other_false_skips_prior_injection(self, tmp_path: Path) -> None:
        alice = _AdvocateStep(name="alice", label="arg")
        bob = _AdvocateStep(name="bob", label="arg")
        stage = paired_round([alice, bob], sees_other=False, name="solo_round")

        state: dict[str, Any] = {}
        ctx = StepContext(
            plan_dir=tmp_path, state=state, profile=None, mode="t", inputs={}
        )
        stage.step.run(ctx)
        log = state["_paired_round_log"]
        # Neither advocate sees a prior.* input under sees_other=False.
        assert log["alice"] == []
        assert log["bob"] == []

    def test_outputs_keyed_by_advocate_then_label(self, tmp_path: Path) -> None:
        alice = _AdvocateStep(name="alice", label="arg")
        bob = _AdvocateStep(name="bob", label="arg")
        stage = paired_round([alice, bob], sees_other=True, name="round")

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="t", inputs={}
        )
        result = stage.step.run(ctx)
        # paired_round accumulates outputs under {advocate.name}.{label}.
        assert "alice.arg" in result.outputs
        assert "bob.arg" in result.outputs

    def test_empty_advocates_raises(self) -> None:
        with pytest.raises(ValueError):
            paired_round([], sees_other=True, name="empty")
