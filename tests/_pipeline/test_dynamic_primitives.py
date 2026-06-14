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

from arnold.pipeline import ContractResult
from arnold.pipeline.types import ContractStatus, Suspension
import arnold.pipelines.megaplan._pipeline.patterns as patterns_module
from arnold.pipelines.megaplan._pipeline.patterns import (
    dynamic_fanout,
    iterate_until_consensus,
    paired_round,
    panel_from_artifact,
    weighted_vote,
)
from arnold.pipelines.megaplan._pipeline.subloop import SubloopStep
from arnold.pipelines.megaplan._pipeline.types import (
    ReduceResult,
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
    recommendation: str = "proceed"

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
    recs_per_call: list[list[str]] = field(default_factory=list)
    contract_results_per_call: list[ContractResult | None] = field(default_factory=list)
    call_count: int = 0

    def run(self, ctx: StepContext) -> StepResult:
        idx = min(self.call_count, max(0, len(self.recs_per_call) - 1))
        recs = self.recs_per_call[idx] if self.recs_per_call else []
        contract_result = None
        if self.contract_results_per_call:
            contract_idx = min(
                self.call_count,
                max(0, len(self.contract_results_per_call) - 1),
            )
            contract_result = self.contract_results_per_call[contract_idx]
        self.call_count += 1
        # Aggregate verdict's recommendation is whichever is most-common
        # at the per-reviewer level (any tie-break is fine here — the
        # primitive consults the ratio, not the aggregate label).
        top: str = recs[0] if recs else "proceed"
        return StepResult(
            verdict=PipelineVerdict(
                score=1.0,
                recommendation=top,
                payload={"per_reviewer_recommendations": list(recs)},
            ),
            contract_result=contract_result,
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
    contract_result: ContractResult | None = None

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
        return StepResult(
            outputs={self.label: out},
            contract_result=self.contract_result,
            next="done",
        )


def _contract(
    status: ContractStatus,
    *,
    cursor: dict[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> ContractResult:
    suspension = None
    if status is ContractStatus.SUSPENDED:
        suspension = Suspension(
            kind="human",
            awaitable="user",
            prompt="Paused",
            resume_cursor=json.dumps(cursor or {"phase": "gate"}),
        )
    return ContractResult(
        status=status,
        suspension=suspension,
        payload=dict(payload or {}),
    )


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
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Untyped 'specs' state_patch channel is flag-OFF only; the typed
        # Port path is covered by TestDynamicFanoutTypedPort below.
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "")
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


class TestDynamicFanoutTypedPort:
    """T12: flag-ON generative Reduce[T] round-trip via the typed Port
    ``last_fanout_results`` — generator emits the typed channel (no
    untyped ``state_patch['specs']``), and the join's StepResult carries
    the per-spec results out on the same Port.
    """

    def test_typed_port_roundtrip_no_untyped_specs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        from arnold.pipelines.megaplan._pipeline.pattern_dynamic import (
            LAST_FANOUT_RESULTS_PORT,
            _DynamicFanoutStep,
        )

        @dataclass(frozen=True)
        class _TypedGen:
            name: str = "gen"
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None
            specs: tuple[Mapping[str, Any], ...] = ()

            def run(self, ctx: StepContext) -> StepResult:
                # Emit ONLY on the typed Port — no untyped 'specs' key.
                return StepResult(
                    state_patch={LAST_FANOUT_RESULTS_PORT.name: list(self.specs)},
                    next="done",
                )

        gen = _TypedGen(
            specs=(
                {"section_id": "a", "section_title": "A"},
                {"section_id": "b", "section_title": "B"},
            ),
        )

        def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
            return StepResult(state_patch={}, next="critique")

        primitive = dynamic_fanout(
            generator=gen, base_prompt=_SectionStep(), join=_join, name="fo"
        )
        assert isinstance(primitive, _DynamicFanoutStep)
        # Stage-level produces declares the typed Port.
        assert LAST_FANOUT_RESULTS_PORT in primitive.produces

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        result = primitive.run(ctx)
        # Joined StepResult carries last_fanout_results on its state_patch
        # via the typed Port; the untyped 'specs' channel is NOT touched.
        assert LAST_FANOUT_RESULTS_PORT.name in result.state_patch
        assert "specs" not in result.state_patch
        carried = result.state_patch[LAST_FANOUT_RESULTS_PORT.name]
        assert isinstance(carried, list) and len(carried) == 2


# ── (c) weighted_vote ──────────────────────────────────────────────────


@pytest.mark.parametrize("typed_ports", [False, True])
class TestWeightedVote:
    def test_higher_weighted_verdict_wins_when_raw_counts_differ(
        self, tmp_path: Path, typed_ports: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1" if typed_ports else "")
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
        if typed_ports:
            payload = merged.verdict.payload
            assert isinstance(payload, dict)
            reduce_result = payload["reduce_result"]
            assert isinstance(reduce_result, ReduceResult)
            assert reduce_result.value == "proceed"
            assert merged.verdict.recommendation is None
        else:
            assert merged.verdict.recommendation == "proceed"
        assert merged.next == "proceed"

    def test_empty_panel_resolves_to_tiebreaker(
        self, tmp_path: Path, typed_ports: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1" if typed_ports else "")
        join_fn = weighted_vote({"alice": 1.0})
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        merged = join_fn([], ctx)
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

    def test_preserves_contract_result_from_deciding_iteration(
        self, tmp_path: Path
    ) -> None:
        first = ContractResult(payload={"step": 1})
        second = ContractResult(payload={"step": 2})
        panel = _AggregateStep(
            recs_per_call=[
                ["proceed", "iterate"],
                ["proceed", "proceed"],
            ],
            contract_results_per_call=[first, second],
        )
        primitive = iterate_until_consensus(
            panel=panel, min_agreement=0.8, max_iters=3, name="contract_loop"
        )
        ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")

        result = primitive.run(ctx)

        assert result.contract_result is second

    def test_preserves_earlier_suspended_contract_until_executor_can_observe_it(
        self, tmp_path: Path
    ) -> None:
        suspended = _contract(
            ContractStatus.SUSPENDED,
            cursor={"phase": "review", "attempt": 1},
        )
        panel = _AggregateStep(
            recs_per_call=[
                ["iterate", "proceed"],
                ["proceed", "proceed"],
            ],
            contract_results_per_call=[suspended, _contract(ContractStatus.COMPLETED)],
        )
        primitive = iterate_until_consensus(
            panel=panel, min_agreement=0.8, max_iters=3, name="suspend_then_finish"
        )

        result = primitive.run(
            StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        )

        assert result.contract_result is not None
        assert result.contract_result.status is ContractStatus.SUSPENDED
        assert result.contract_result.suspension is suspended.suspension
        pending = result.contract_result.payload["pending_suspensions"]
        assert pending == [
            {
                "child_id": "iteration_1",
                "status": "suspended",
                "cursor": json.dumps({"phase": "review", "attempt": 1}),
                "suspension": suspended.suspension.to_json(),
            }
        ]

    def test_preserves_earlier_failed_contract_when_later_iteration_completes(
        self, tmp_path: Path
    ) -> None:
        failed = _contract(
            ContractStatus.FAILED,
            payload={"reason": "blocked"},
        )
        panel = _AggregateStep(
            recs_per_call=[
                ["iterate", "proceed"],
                ["proceed", "proceed"],
            ],
            contract_results_per_call=[failed, _contract(ContractStatus.COMPLETED)],
        )
        primitive = iterate_until_consensus(
            panel=panel, min_agreement=0.8, max_iters=3, name="fail_then_finish"
        )

        result = primitive.run(
            StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t")
        )

        assert result.contract_result is not None
        assert result.contract_result.status is ContractStatus.FAILED
        source_contracts = result.contract_result.payload["source_contracts"]
        assert source_contracts[0]["child_id"] == "iteration_1"
        assert source_contracts[0]["status"] == "failed"


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
        bob_contract = ContractResult(payload={"winner": "bob"})
        bob = _AdvocateStep(name="bob", label="arg", contract_result=bob_contract)
        stage = paired_round([alice, bob], sees_other=True, name="round")

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="t", inputs={}
        )
        result = stage.step.run(ctx)
        # paired_round accumulates outputs under {advocate.name}.{label}.
        assert "alice.arg" in result.outputs
        assert "bob.arg" in result.outputs
        assert result.contract_result is bob_contract

    def test_preserves_earlier_suspended_advocate_contract(self, tmp_path: Path) -> None:
        suspended = _contract(
            ContractStatus.SUSPENDED,
            cursor={"phase": "alice", "attempt": 2},
        )
        alice = _AdvocateStep(name="alice", label="arg", contract_result=suspended)
        bob = _AdvocateStep(
            name="bob",
            label="arg",
            contract_result=_contract(ContractStatus.COMPLETED),
        )
        stage = paired_round([alice, bob], sees_other=True, name="round")

        result = stage.step.run(
            StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t", inputs={})
        )

        assert result.contract_result is not None
        assert result.contract_result.status is ContractStatus.SUSPENDED
        assert result.contract_result.suspension is suspended.suspension
        pending = result.contract_result.payload["pending_suspensions"]
        assert pending[0]["child_id"] == "alice"
        assert pending[0]["cursor"] == json.dumps({"phase": "alice", "attempt": 2})

    def test_preserves_earlier_failed_advocate_contract(self, tmp_path: Path) -> None:
        failed = _contract(
            ContractStatus.FAILED,
            payload={"reason": "no_consensus"},
        )
        alice = _AdvocateStep(name="alice", label="arg", contract_result=failed)
        bob = _AdvocateStep(
            name="bob",
            label="arg",
            contract_result=_contract(ContractStatus.COMPLETED),
        )
        stage = paired_round([alice, bob], sees_other=True, name="round")

        result = stage.step.run(
            StepContext(plan_dir=tmp_path, state={}, profile=None, mode="t", inputs={})
        )

        assert result.contract_result is not None
        assert result.contract_result.status is ContractStatus.FAILED
        source_contracts = result.contract_result.payload["source_contracts"]
        assert source_contracts[0]["child_id"] == "alice"
        assert source_contracts[0]["status"] == "failed"

    def test_empty_advocates_raises(self) -> None:
        with pytest.raises(ValueError):
            paired_round([], sees_other=True, name="empty")


def test_patterns_facade_reexports_dynamic_private_helpers() -> None:
    assert patterns_module._specialize_step is not None
    assert patterns_module._read_specs_from_path is not None
    assert patterns_module._extract_specs_from_result is not None
    assert patterns_module._PanelFromArtifactStep is not None
    assert patterns_module._DynamicFanoutStep is not None
    assert patterns_module._agreement_ratio is not None
    assert patterns_module._ConsensusStep is not None
    assert patterns_module._PairedRoundStep is not None


# ── T9: Fanout metadata shape tests ───────────────────────────────────────


class TestFanoutMetadataShape:
    """Verify that Arnold fanout metadata dataclasses have the expected shapes."""

    def test_fanout_spec_schema_shape(self) -> None:
        from arnold.pipeline.pattern_dynamic import FanoutSpecSchema

        schema = FanoutSpecSchema(
            keys=("section_id", "section_title"),
            required=("section_id",),
        )
        assert schema.keys == ("section_id", "section_title")
        assert schema.required == ("section_id",)
        # Defaults
        default = FanoutSpecSchema()
        assert default.keys == ()
        assert default.required == ()

    def test_fanout_concurrency_shape(self) -> None:
        from arnold.pipeline.pattern_dynamic import FanoutConcurrency

        c = FanoutConcurrency(mode="thread", max_workers=4)
        assert c.mode == "thread"
        assert c.max_workers == 4
        # Default
        default = FanoutConcurrency()
        assert default.mode == "sequential"
        assert default.max_workers is None

    def test_fanout_governor_limits_shape(self) -> None:
        from arnold.pipeline.pattern_dynamic import FanoutGovernorLimits

        limits = FanoutGovernorLimits(
            max_fanout_width=10,
            max_total_steps=50,
            max_sequential_steps=20,
        )
        assert limits.max_fanout_width == 10
        assert limits.max_total_steps == 50
        assert limits.max_sequential_steps == 20
        # Defaults are all None
        default = FanoutGovernorLimits()
        assert default.max_fanout_width is None
        assert default.max_total_steps is None
        assert default.max_sequential_steps is None

    def test_fanout_metadata_bundle(self) -> None:
        from arnold.pipeline.pattern_dynamic import (
            FanoutConcurrency,
            FanoutGovernorLimits,
            FanoutJoinContract,
            FanoutMetadata,
            FanoutSpecSchema,
            FanoutSpecialization,
        )

        meta = FanoutMetadata(
            schema=FanoutSpecSchema(keys=("a",), required=("a",)),
            specialization=FanoutSpecialization(spec_keys=("a",)),
            concurrency=FanoutConcurrency(mode="thread", max_workers=8),
            governor_limits=FanoutGovernorLimits(max_fanout_width=100),
            join_contract=FanoutJoinContract(arity="many", result_kind="reduce"),
        )
        assert meta.schema.keys == ("a",)
        assert meta.concurrency.mode == "thread"
        assert meta.concurrency.max_workers == 8
        assert meta.governor_limits.max_fanout_width == 100
        assert meta.join_contract.result_kind == "reduce"

    def test_output_port_stability(self) -> None:
        """LAST_FANOUT_RESULTS_PORT has a stable name and content_type."""
        from arnold.pipeline.pattern_dynamic import LAST_FANOUT_RESULTS_PORT

        assert LAST_FANOUT_RESULTS_PORT.name == "last_fanout_results"
        assert LAST_FANOUT_RESULTS_PORT.content_type == "application/x-fanout-results+json"


# ── T9: Sequential default ordering test ──────────────────────────────────


class TestFanoutSequentialDefault:
    """Verify that the default mode is sequential and results preserve order."""

    def test_sequential_default_preserves_spec_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "")
        # Generator emits specs in a known order
        generator = _GeneratorStep(
            specs=(
                {"section_id": "first", "section_title": "First"},
                {"section_id": "second", "section_title": "Second"},
                {"section_id": "third", "section_title": "Third"},
            ),
        )
        order_log: list[str] = []

        @dataclass(frozen=True)
        class _OrderedStep:
            name: str = "ordered"
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None
            section_id: str = ""

            def run(self, ctx: StepContext) -> StepResult:
                order_log.append(self.section_id)
                out = Path(ctx.plan_dir) / f"{self.section_id}.md"
                out.write_text(f"# {self.section_id}\n")
                return StepResult(outputs={self.section_id: out}, next="done")

        def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
            return StepResult(next="halt")

        primitive = dynamic_fanout(
            generator=generator,
            base_prompt=_OrderedStep(),
            join=_join,
            name="ordered_fanout",
        )
        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        result = primitive.run(ctx)
        assert result.next == "halt"
        # Sequential mode preserves spec order
        assert order_log == ["first", "second", "third"]


# ── T9: Thread concurrency ordering test ──────────────────────────────────


class TestFanoutThreadConcurrency:
    """Verify that thread-mode fanout produces results in spec order."""

    def test_thread_mode_preserves_result_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        from arnold.pipelines.megaplan._pipeline.pattern_dynamic import _DynamicFanoutStep

        import time

        @dataclass(frozen=True)
        class _SlowStep:
            name: str = "slow"
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None
            section_id: str = ""

            def run(self, ctx: StepContext) -> StepResult:
                # Introduce a tiny sleep to simulate work
                time.sleep(0.01)
                return StepResult(
                    outputs={self.section_id: self.section_id},
                    next="done",
                )

        @dataclass(frozen=True)
        class _ThreadedGen:
            name: str = "gen"
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:
                from arnold.pipeline.pattern_dynamic import LAST_FANOUT_RESULTS_PORT

                return StepResult(
                    state_patch={
                        LAST_FANOUT_RESULTS_PORT.name: [
                            {"section_id": "a"},
                            {"section_id": "b"},
                            {"section_id": "c"},
                            {"section_id": "d"},
                        ]
                    },
                    next="done",
                )

        def _join(results: list[StepResult], ctx: StepContext) -> StepResult:
            return StepResult(next="halt")

        primitive = dynamic_fanout(
            generator=_ThreadedGen(),
            base_prompt=_SlowStep(),
            join=_join,
            name="threaded_fanout",
        )
        assert isinstance(primitive, _DynamicFanoutStep)

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        result = primitive.run(ctx)
        assert result.next == "halt"

        # Verify typed port carries results in order
        from arnold.pipeline.pattern_dynamic import LAST_FANOUT_RESULTS_PORT

        carried = result.state_patch.get(LAST_FANOUT_RESULTS_PORT.name)
        assert carried is not None
        assert len(carried) == 4
        # Results should be indexed by position, preserving spec order
        output_ids = []
        for r in carried:
            if hasattr(r, "outputs"):
                for k in r.outputs:
                    output_ids.append(k)
        assert output_ids == ["a", "b", "c", "d"]


# ── T9: Reducer synthesis coverage ────────────────────────────────────────


class TestReducerSynthesis:
    """Verify that joins receive ordered per-spec results and emit typed aggregates."""

    def test_join_receives_ordered_per_spec_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "")
        generator = _GeneratorStep(
            specs=(
                {"section_id": "s1", "section_title": "One"},
                {"section_id": "s2", "section_title": "Two"},
            ),
        )

        join_inputs: list[list[StepResult]] = []

        def _recording_join(
            results: list[StepResult], ctx: StepContext
        ) -> StepResult:
            join_inputs.append(list(results))
            return StepResult(next="halt")

        primitive = dynamic_fanout(
            generator=generator,
            base_prompt=_SectionStep(),
            join=_recording_join,
            name="reducer_fanout",
        )
        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        primitive.run(ctx)

        assert len(join_inputs) == 1
        assert len(join_inputs[0]) == 2
        # Results should be in spec order: s1 then s2
        sid_order = []
        for r in join_inputs[0]:
            for k in r.outputs:
                sid_order.append(k)
        assert sid_order == ["s1", "s2"]

    def test_reducer_emits_typed_aggregate_with_typed_ports_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")
        from arnold.pipelines.megaplan._pipeline.pattern_dynamic import _DynamicFanoutStep

        @dataclass(frozen=True)
        class _TypedGen:
            name: str = "gen"
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:
                from arnold.pipeline.pattern_dynamic import LAST_FANOUT_RESULTS_PORT

                return StepResult(
                    state_patch={
                        LAST_FANOUT_RESULTS_PORT.name: [
                            {"section_id": "x", "section_title": "X"},
                            {"section_id": "y", "section_title": "Y"},
                        ]
                    },
                    next="done",
                )

        aggregate_result: dict = {}

        def _aggregate_join(
            results: list[StepResult], ctx: StepContext
        ) -> StepResult:
            aggregate_result["count"] = len(results)
            aggregate_result["keys"] = sorted(
                k for r in results for k in (getattr(r, "outputs", {}) or {})
            )
            return StepResult(
                verdict=PipelineVerdict(score=1.0, recommendation="proceed"),
                next="proceed",
            )

        primitive = dynamic_fanout(
            generator=_TypedGen(),
            base_prompt=_SectionStep(),
            join=_aggregate_join,
            name="aggregate_fanout",
        )
        assert isinstance(primitive, _DynamicFanoutStep)

        ctx = StepContext(
            plan_dir=tmp_path, state={}, profile=None, mode="test", inputs={}
        )
        result = primitive.run(ctx)

        assert aggregate_result["count"] == 2
        assert aggregate_result["keys"] == ["x", "y"]
        assert result.next == "proceed"
        assert result.verdict is not None


# ── T9: Governor-limit carrier reporting ──────────────────────────────────


class TestGovernorLimitCarrier:
    """Verify that FanoutGovernorLimits is a pure data carrier (no enforcement)."""

    def test_governor_limits_is_pure_data_carrier(self) -> None:
        from arnold.pipeline.pattern_dynamic import FanoutGovernorLimits

        limits = FanoutGovernorLimits(
            max_fanout_width=5,
            max_total_steps=25,
            max_sequential_steps=10,
        )
        # Verify it's frozen (immutable)
        with pytest.raises(Exception):
            limits.max_fanout_width = 99  # type: ignore[misc]

    def test_governor_limits_fields_are_nullable(self) -> None:
        from arnold.pipeline.pattern_dynamic import FanoutGovernorLimits

        limits = FanoutGovernorLimits()
        assert limits.max_fanout_width is None
        assert limits.max_total_steps is None
        assert limits.max_sequential_steps is None
