"""End-to-end tests for the deliberation 10-stage DAG (T11).

Covers:
- Full pipeline DAG construction and stage ordering
- Suspend/resume contract: persist_resume_cursor + awaiting_user.json + answers.json
- On-disk cursor: resume_cursor.json readback
- Journal projection: fold_journal with state events
- Usage aggregation: panel_usage via _usage_extractor on PanelReviewerStep
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.pattern_joins import aggregate_panel_join
from arnold.pipeline.resume import persist_resume_cursor, read_resume_cursor
from arnold.pipeline.steps.agent import AgentStep
from arnold.pipeline.steps.human_gate import HumanGateStep
from arnold.pipeline.steps.panel import PanelReviewerStep
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from arnold.runtime.event_journal import (
    NdjsonEventSink,
    read_event_journal,
)
from arnold.runtime.semantic_replay import semantic_equivalent
from arnold.runtime.wal_fold import (
    fold_journal,
    last_state_snapshot_projector,
)

from arnold.pipelines.deliberation.pipelines import build_initial_pipeline
from arnold.pipelines.deliberation.steps import (
    build_critique_panel_stage,
    build_draft_plan_stage,
    build_human_gate_stage,
    build_question_gen_stage,
    build_skeptical_synthesis_stage,
    load_questions,
    reconstruct_plan_from_journal,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _noop_worker(
    prompt: str = "",
    step_name: str = "",
    pipeline_name: str = "",
    inputs: dict[str, str] | None = None,
    mode: str = "",
) -> str:
    """A no-op worker that echoes the prompt for test purposes."""
    return prompt


def _json_worker(data: dict[str, Any]) -> Any:
    """Return a worker that always produces a specific JSON dict."""

    def worker(
        prompt: str = "",
        step_name: str = "",
        pipeline_name: str = "",
        inputs: dict[str, str] | None = None,
        mode: str = "",
    ) -> str:
        return json.dumps(data)

    return worker


def _noop_prompt_source(ctx: StepContext, params: Any = None) -> str:
    return "dummy prompt"


# ── Profile for building the full pipeline ──────────────────────────────────


_DUMMY_PROFILE: dict[str, Any] = {
    "question_gen": "dummy",
    "draft_plan": "dummy",
    "layer_high_panel": "high",
    "layer_high_synth": "dummy",
    "layer_mid_panel": "mid",
    "layer_mid_synth": "dummy",
    "layer_low_panel": "low",
    "layer_low_synth": "dummy",
    "final_report": "dummy",
}

_EXPECTED_ORDER: tuple[str, ...] = (
    "question_gen",
    "human_gate",
    "draft_plan",
    "layer_high_panel",
    "layer_high_synth",
    "layer_mid_panel",
    "layer_mid_synth",
    "layer_low_panel",
    "layer_low_synth",
    "final_report",
)


def _stage_by_name(pipeline: Pipeline, name: str) -> Stage | ParallelStage:
    """Get a stage by name from the pipeline's stages dict."""
    return pipeline.stages[name]


# ── Full DAG construction ───────────────────────────────────────────────────


class TestFullDagConstruction:
    """build_initial_pipeline produces the correct 10-stage DAG."""

    def test_builds_pipeline_with_correct_entry(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        assert isinstance(pipeline, Pipeline)
        assert pipeline.entry == "question_gen"

    def test_ten_stages_in_ordering(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        # pipeline.stages is a dict; check all expected names are present
        stage_names = sorted(pipeline.stages.keys())
        assert len(pipeline.stages) == 10
        assert stage_names == sorted(_EXPECTED_ORDER)

    def test_first_stage_is_question_gen(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        first = _stage_by_name(pipeline, "question_gen")
        assert isinstance(first, Stage)
        assert isinstance(first.step, AgentStep)

    def test_human_gate_stage_has_halting_step(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        hg = _stage_by_name(pipeline, "human_gate")
        assert isinstance(hg, Stage)
        assert isinstance(hg.step, HumanGateStep)
        assert "answers_collected" in hg.step._choices

    def test_panel_stages_are_parallel(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        panel_stages = [
            s for s in pipeline.stages.values() if isinstance(s, ParallelStage)
        ]
        assert len(panel_stages) == 3  # high, mid, low
        for ps in panel_stages:
            assert len(ps.steps) > 0
            assert all(isinstance(s, PanelReviewerStep) for s in ps.steps)

    def test_final_report_has_halt_edge(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        fr = _stage_by_name(pipeline, "final_report")
        assert any(e.target == "halt" for e in fr.edges)

    def test_edges_chain_correctly(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        # Build edges by source name
        edges_by_source: dict[str, list[Edge]] = {}
        for name, stage in pipeline.stages.items():
            edges_by_source[name] = list(stage.edges)

        # question_gen → human_gate
        assert any(
            e.label == "done" and e.target == "human_gate"
            for e in edges_by_source["question_gen"]
        )
        # human_gate → draft_plan
        assert any(
            e.label == "answers_collected" and e.target == "draft_plan"
            for e in edges_by_source["human_gate"]
        )
        # draft_plan → layer_high_panel
        assert any(
            e.label == "done" and e.target == "layer_high_panel"
            for e in edges_by_source["draft_plan"]
        )
        # layer_high_panel → layer_high_synth
        assert any(
            e.label == "panel_done" and e.target == "layer_high_synth"
            for e in edges_by_source["layer_high_panel"]
        )
        # layer_high_synth → layer_mid_panel
        assert any(
            e.label == "done" and e.target == "layer_mid_panel"
            for e in edges_by_source["layer_high_synth"]
        )
        # layer_low_synth → final_report
        assert any(
            e.label == "done" and e.target == "final_report"
            for e in edges_by_source["layer_low_synth"]
        )
        # final_report → halt
        assert any(
            e.label == "done" and e.target == "halt"
            for e in edges_by_source["final_report"]
        )

    def test_resource_bundle_attached(self) -> None:
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        assert pipeline.resource_bundles is not None
        assert len(pipeline.resource_bundles) >= 1


# ── Suspend / resume contract ───────────────────────────────────────────────


class TestSuspendResumeContract:
    """The HumanGateStep suspend/resume flow works end-to-end."""

    def test_human_gate_writes_awaiting_user_checkpoint(self, tmp_path: Path) -> None:
        stage = build_human_gate_stage()
        stage.step._pipeline_name = "deliberation"
        stage.step._pipeline_version = 1
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )
        result = stage.step.run(ctx)
        assert result.next == "halt"
        checkpoint = tmp_path / "awaiting_user.json"
        assert checkpoint.exists()

        data = json.loads(checkpoint.read_text())
        assert data["pipeline"] == "deliberation"
        assert data["stage"] == "human_gate"
        assert "answers_collected" in data["choices"]

    def test_human_gate_resume_with_choice(self, tmp_path: Path) -> None:
        stage = build_human_gate_stage()
        stage.step._pipeline_name = "deliberation"
        stage.step._pipeline_version = 1
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )

        # First run — halt
        result1 = stage.step.run(ctx)
        assert result1.next == "halt"

        # Set resume choice and run again
        stage.step._resume_choice = "answers_collected"
        result2 = stage.step.run(ctx)
        assert result2.next == "answers_collected"
        # Checkpoint should be cleaned up
        checkpoint = tmp_path / "awaiting_user.json"
        assert not checkpoint.exists()

    def test_human_gate_resume_from_disk_checkpoint(self, tmp_path: Path) -> None:
        """Resume works when _resume_choice is read from the on-disk checkpoint."""
        stage = build_human_gate_stage()
        stage.step._pipeline_name = "deliberation"
        stage.step._pipeline_version = 1
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )

        # First run — halt, writes checkpoint to disk
        stage.step.run(ctx)

        # Manually inject _resume_choice into the on-disk checkpoint
        checkpoint_path = tmp_path / "awaiting_user.json"
        data = json.loads(checkpoint_path.read_text())
        data["_resume_choice"] = "answers_collected"
        checkpoint_path.write_text(json.dumps(data))

        # Create a fresh stage instance (simulating new process)
        stage2 = build_human_gate_stage()
        stage2.step._pipeline_name = "deliberation"
        stage2.step._pipeline_version = 1
        result = stage2.step.run(ctx)
        assert result.next == "answers_collected"
        assert not checkpoint_path.exists()

    def test_persist_resume_cursor(self, tmp_path: Path) -> None:
        path = persist_resume_cursor(
            tmp_path,
            stage="human_gate",
            resume_cursor="my-opaque-cursor",
            extra_field="extra_value",
        )
        assert path.exists()
        assert path.name == "resume_cursor.json"

        data = read_resume_cursor(tmp_path)
        assert data is not None
        assert data["stage"] == "human_gate"
        assert data["resume_cursor"] == "my-opaque-cursor"
        assert data["extra_field"] == "extra_value"

    def test_read_resume_cursor_none_when_missing(self, tmp_path: Path) -> None:
        assert read_resume_cursor(tmp_path) is None

    def test_full_suspend_resume_with_answers(self, tmp_path: Path) -> None:
        """End-to-end: question_gen → human_gate suspend → write answers → resume."""
        # Stage 1: question_gen produces questions
        qg_stage = build_question_gen_stage(
            _noop_prompt_source,
            _json_worker({"questions": [{"q": "What?", "rationale": "scope"}]}),
        )
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )
        qg_result = qg_stage.step.run(ctx)
        assert qg_result.next == "done"

        # Verify questions were written
        questions = load_questions(str(tmp_path))
        assert "questions" in questions

        # Stage 2: human_gate suspends
        hg_stage = build_human_gate_stage()
        hg_stage.step._pipeline_name = "deliberation"
        hg_stage.step._pipeline_version = 1
        hg_result = hg_stage.step.run(ctx)
        assert hg_result.next == "halt"

        # Persist resume cursor
        persist_resume_cursor(tmp_path, stage="human_gate")

        # User writes answers.json
        answers_path = tmp_path / "answers.json"
        answers_path.write_text(
            json.dumps({"answers": [{"q": "What?", "a": "A thing"}]})
        )

        # Verify answers.json exists and is valid
        assert answers_path.exists()
        parsed = json.loads(answers_path.read_text())
        assert "answers" in parsed

        # Verify resume cursor is readable
        cursor = read_resume_cursor(tmp_path)
        assert cursor is not None
        assert cursor["stage"] == "human_gate"

        # Stage 2 resume: inject choice and re-run
        hg_stage.step._resume_choice = "answers_collected"
        hg_result2 = hg_stage.step.run(ctx)
        assert hg_result2.next == "answers_collected"

        # Stage 3: draft_plan with guard validates answers
        dp_stage = build_draft_plan_stage(_noop_prompt_source, _noop_worker)
        dp_ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={
                "questions": str(tmp_path / "question_gen" / "questions"),
                "answers": str(answers_path),
            },
        )
        # Guard should pass — answers.json exists and is valid
        dp_result = dp_stage.step.run(dp_ctx)
        assert dp_result.next == "done"


# ── Journal projection ──────────────────────────────────────────────────────


class TestJournalProjection:
    """The event journal correctly records synthesis state and can be replayed."""

    def test_journal_records_state_events(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)

        # Emulate a synthesis stage emitting state events
        sink.emit(
            "state",
            payload={
                "layer": 0,
                "state": {"plan_version": 1, "sections": []},
                "plan_version": 1,
            },
            phase="layer_0_synth",
        )
        sink.emit(
            "state",
            payload={
                "layer": 0,
                "state": {"plan_version": 2, "sections": [{"title": "A"}]},
                "plan_version": 2,
            },
            phase="layer_0_synth",
        )

        events = read_event_journal(tmp_path)
        assert len(events) >= 2

        # Fold to get the last state snapshot
        result = fold_journal(
            events,
            kind_filter="state",
            projector=last_state_snapshot_projector,
            initial=None,
        )
        assert isinstance(result, dict)
        assert result.get("plan_version") == 2
        assert result.get("sections") == [{"title": "A"}]

    def test_reconstruct_plan_from_journal(self, tmp_path: Path) -> None:
        sink = NdjsonEventSink(tmp_path)

        # Write two synthesis state events
        sink.emit(
            "state",
            payload={
                "layer": 0,
                "state": {"plan_version": 0, "sections": [{"title": "draft"}]},
                "plan_version": 0,
            },
            phase="layer_0_synth",
        )
        sink.emit(
            "state",
            payload={
                "layer": 1,
                "state": {"plan_version": 1, "sections": [{"title": "revised"}]},
                "plan_version": 1,
            },
            phase="layer_1_synth",
        )

        plan = reconstruct_plan_from_journal(tmp_path)
        assert plan is not None
        assert plan["plan_version"] == 1
        assert plan["sections"][0]["title"] == "revised"

    def test_reconstruct_returns_none_without_state_events(self, tmp_path: Path) -> None:
        # No events — should be None
        plan = reconstruct_plan_from_journal(tmp_path)
        assert plan is None

    def test_reconstruct_returns_none_when_no_events_file(self, tmp_path: Path) -> None:
        plan = reconstruct_plan_from_journal(tmp_path / "nonexistent")
        assert plan is None

    def test_synthesis_stage_emits_journal_events(self, tmp_path: Path) -> None:
        """build_skeptical_synthesis_stage with a real NdjsonEventSink emits events."""
        sink = NdjsonEventSink(tmp_path)
        stage = build_skeptical_synthesis_stage(
            layer=0,
            next_target="next_stage",
            prompt_source=_noop_prompt_source,
            worker=_json_worker({
                "plan_version": 1,
                "sections": [{"title": "Plan", "content": "content"}],
                "changelog": [
                    {
                        "critique": "needs clarity",
                        "verdict": "accept",
                        "reason": "valid",
                        "applied_change": "clarified",
                    }
                ],
            }),
            journal=sink,
        )

        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={
                "plan": json.dumps({"plan_version": 0}),
                "panel_reviews": json.dumps([]),
            },
        )
        result = stage.step.run(ctx)
        assert result.next == "done"

        # Verify a state event was emitted to the journal
        events = read_event_journal(tmp_path)
        state_events = [e for e in events if e.get("kind") == "state"]
        assert len(state_events) >= 1
        assert state_events[0].get("phase") == "layer_0_synth"

    def test_synthesis_stage_fallback_writes_raw_output(self, tmp_path: Path) -> None:
        """When worker returns non-JSON, raw_output is stored in the event."""
        sink = NdjsonEventSink(tmp_path)
        stage = build_skeptical_synthesis_stage(
            layer=0,
            next_target="next_stage",
            prompt_source=_noop_prompt_source,
            worker=_noop_worker,  # returns prompt text, not JSON
            journal=sink,
        )
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={
                "plan": "{}",
                "panel_reviews": "{}",
            },
        )
        stage.step.run(ctx)

        events = read_event_journal(tmp_path)
        state_events = [e for e in events if e.get("kind") == "state"]
        assert len(state_events) >= 1
        payload = state_events[0].get("payload", {})
        assert "raw_output" in payload


# ── Usage aggregation ──────────────────────────────────────────────────────


class TestUsageAggregation:
    """Panel usage aggregation works via _usage_extractor on PanelReviewerStep."""

    def _make_usage_extractor(self, tokens: dict[str, float]) -> Any:
        def extractor(**kwargs: Any) -> dict[str, float]:
            return tokens
        return extractor

    def test_aggregate_panel_join_sums_usage_keys(self) -> None:
        join_fn = aggregate_panel_join(
            next_label="panel_done",
            usage_keys=("input_tokens", "output_tokens"),
        )

        results = [
            StepResult(
                outputs={"reviewer_1": "/tmp/r1"},
                next="done",
                state_patch={"input_tokens": 100, "output_tokens": 50},
            ),
            StepResult(
                outputs={"reviewer_2": "/tmp/r2"},
                next="done",
                state_patch={"input_tokens": 200, "output_tokens": 80},
            ),
            StepResult(
                outputs={"reviewer_3": "/tmp/r3"},
                next="done",
                state_patch={"input_tokens": 50, "output_tokens": 20},
            ),
        ]

        result = join_fn(results, StepContext(
            artifact_root="/tmp",
            state={},
            mode="default",
            inputs={},
        ))

        assert result.next == "panel_done"
        assert result.state_patch["panel_usage"] == {
            "input_tokens": 350.0,
            "output_tokens": 150.0,
        }
        # Outputs from all children preserved
        assert "reviewer_1" in result.outputs
        assert "reviewer_2" in result.outputs
        assert "reviewer_3" in result.outputs

    def test_aggregate_panel_join_no_usage_keys(self) -> None:
        join_fn = aggregate_panel_join(next_label="panel_done")
        results = [
            StepResult(
                outputs={"r1": "/tmp/r1"},
                next="done",
                state_patch={},
            ),
        ]
        result = join_fn(results, StepContext(
            artifact_root="/tmp",
            state={},
            mode="default",
            inputs={},
        ))
        assert result.next == "panel_done"
        assert result.state_patch["panel_usage"] == {}

    def test_panel_reviewer_step_with_usage_extractor(self, tmp_path: Path) -> None:
        """PanelReviewerStep with _usage_extractor merges usage into state_patch."""
        step = PanelReviewerStep(
            name="test_reviewer",
            kind="produce",
            prompt_key="test",
            _prompt_source=_noop_prompt_source,
            _pipeline_name="deliberation",
            _input_refs=["plan"],
            _reviewer_id="tester",
            _worker=_noop_worker,
            _mode="default",
            _usage_extractor=self._make_usage_extractor(
                {"input_tokens": 42, "output_tokens": 7}
            ),
        )

        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={"plan": "{}"},
        )
        result = step.run(ctx)
        # PanelReviewerStep.run returns "halt" (not "done") because
        # routing is handled by the ParallelStage join function.
        assert result.next == "halt"
        assert result.state_patch.get("input_tokens") == 42
        assert result.state_patch.get("output_tokens") == 7

    def test_agent_step_with_usage_extractor(self, tmp_path: Path) -> None:
        """AgentStep with _usage_extractor merges usage into state_patch."""
        step = AgentStep(
            name="test_agent",
            kind="produce",
            prompt_key="test",
            _prompt_source=_noop_prompt_source,
            _output_label="test",
            _output_suffix="json",
            _worker=_noop_worker,
            _usage_extractor=self._make_usage_extractor(
                {"cost_usd": 0.05}
            ),
        )

        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )
        result = step.run(ctx)
        assert result.next == "done"
        assert result.state_patch.get("cost_usd") == 0.05

    def test_panel_steps_have_usage_extractor_set(self) -> None:
        """Panel reviewer steps in the full pipeline can have _usage_extractor set."""
        pipeline = build_initial_pipeline(
            profile=_DUMMY_PROFILE,
            workers={"dummy": _noop_worker},
        )
        for stage in pipeline.stages.values():
            if isinstance(stage, ParallelStage):
                for step in stage.steps:
                    assert isinstance(step, PanelReviewerStep)
                    # By default, _usage_extractor is None
                    assert step._usage_extractor is None
                    # But it can be set
                    step._usage_extractor = self._make_usage_extractor(
                        {"input_tokens": 1}
                    )
                    assert step._usage_extractor is not None


# ── Full pipeline profile binding ──────────────────────────────────────────


class TestProfileBinding:
    """The pipeline binds profile keys to stages correctly."""

    def test_profile_with_dict_panel_config(self) -> None:
        profile = {
            "question_gen": "dummy",
            "draft_plan": "dummy",
            "layer_high_panel": {
                "abstraction_level": "high",
                "panel_personas": ["critic_a", "critic_b"],
            },
            "layer_high_synth": "dummy",
            "layer_mid_panel": "mid",
            "layer_mid_synth": "dummy",
            "layer_low_panel": "low",
            "layer_low_synth": "dummy",
            "final_report": "dummy",
        }
        pipeline = build_initial_pipeline(
            profile=profile,
            workers={"dummy": _noop_worker},
        )
        assert pipeline.entry == "question_gen"
        # The high panel should have exactly 2 reviewers
        high_panel = _stage_by_name(pipeline, "layer_high_panel")
        assert isinstance(high_panel, ParallelStage)
        assert len(high_panel.steps) == 2

    def test_profile_missing_agent_raises(self) -> None:
        profile = {
            "question_gen": "nonexistent",
        }
        with pytest.raises(ValueError, match="no such worker"):
            build_initial_pipeline(
                profile=profile,
                workers={"dummy": _noop_worker},
            )

    def test_profile_missing_worker_key_raises(self) -> None:
        with pytest.raises(ValueError, match="no such worker"):
            build_initial_pipeline(
                profile=_DUMMY_PROFILE,
                workers={},
            )


class TestSemanticReplay:
    """Semantic-replay: byte-inequality vs structural equivalence."""

    #: Documented ignore paths — version fields and timestamps that are
    #: expected to vary between runs without changing the semantics.
    SEMANTIC_IGNORE_PATHS: frozenset[str] = frozenset({
        "plan_version",
        "changelog.2.plan_version",
    })

    def _make_synth_output(
        self,
        *,
        verdict_override: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build a realistic skeptical-synthesis output dict.

        The returned dict matches the schema from
        :data:`arnold.pipelines.deliberation.steps._SYNTHESIS_PROMPT`.
        """
        changelog = [
            {
                "critique": "The plan lacks measurable success criteria.",
                "verdict": "accept",
                "reason": "Measurable criteria are essential for evaluation.",
                "applied_change": "Added a 'Success Metrics' section.",
            },
            {
                "critique": "The timeline is unrealistically aggressive.",
                "verdict": "reframe",
                "reason": "Timeline concern is valid but needs concrete adjustment.",
                "applied_change": "Extended Phase 2 by two weeks.",
            },
            {
                "critique": "The budget estimate should use 2024 figures.",
                "verdict": "accept",
                "reason": "Outdated figures undermine credibility.",
                "applied_change": "Updated all budget numbers to 2024 projections.",
            },
        ]
        if verdict_override:
            for entry in changelog:
                entry.update(verdict_override)

        return {
            "plan_version": 2,
            "sections": [
                {
                    "title": "Executive Summary",
                    "content": "This plan outlines the Q3 product launch...",
                },
                {
                    "title": "Success Metrics",
                    "content": "Target: 50k MAU within 90 days of launch.",
                },
            ],
            "changelog": changelog,
        }

    # ── semantic_equivalent unit tests ──────────────────────────────────

    def test_identical_dicts_are_equivalent(self) -> None:
        d = self._make_synth_output()
        eq, diffs = semantic_equivalent(d, d)
        assert eq is True
        assert diffs == []

    def test_byte_different_but_equivalent(self) -> None:
        """Two serializations of the same structure are semantically equal."""
        d = self._make_synth_output()
        # Produce byte-different representations
        compact = json.dumps(d, separators=(",", ":"))
        pretty = json.dumps(d, indent=2, sort_keys=True)
        assert compact != pretty  # byte-inequality

        a = json.loads(compact)
        b = json.loads(pretty)
        eq, diffs = semantic_equivalent(a, b)
        assert eq is True
        assert diffs == []

    def test_version_path_ignored(self) -> None:
        """plan_version differences are ignored when listed in ignore_paths."""
        a = self._make_synth_output()
        b = self._make_synth_output()
        b["plan_version"] = 99  # different version

        # Without ignore_paths — should fail
        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        assert "plan_version" in diffs[0]

        # With ignore_paths — should pass
        eq, diffs = semantic_equivalent(
            a, b, ignore_paths=self.SEMANTIC_IGNORE_PATHS,
        )
        assert eq is True
        assert diffs == []

    def test_mutated_verdict_detected(self) -> None:
        """A changed changelog verdict is reported with its path."""
        a = self._make_synth_output()
        b = self._make_synth_output()
        # Mutate the first changelog entry's verdict
        b["changelog"][0]["verdict"] = "reject"

        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        # Path should point to the mutated field
        assert any("changelog" in d and "verdict" in d for d in diffs), (
            f"Expected path containing 'changelog'/'verdict', got {diffs}"
        )

    def test_mutated_section_content_detected(self) -> None:
        """A changed section content is reported with its path."""
        a = self._make_synth_output()
        b = self._make_synth_output()
        b["sections"][0]["content"] = "Completely different text."

        eq, diffs = semantic_equivalent(a, b)
        assert eq is False
        assert any("sections" in d and "content" in d for d in diffs), (
            f"Expected path containing 'sections'/'content', got {diffs}"
        )

    def test_ignore_paths_documented(self) -> None:
        """SEMANTIC_IGNORE_PATHS is a documented frozenset of dotted paths."""
        assert isinstance(self.SEMANTIC_IGNORE_PATHS, frozenset)
        assert "plan_version" in self.SEMANTIC_IGNORE_PATHS

    def test_full_semantic_replay_with_pipeline_outputs(self, tmp_path: Path) -> None:
        """Two pipeline runs with semantically equivalent workers produce
        equivalent outputs despite byte-level differences."""
        plan_data = {
            "plan_version": 1,
            "sections": [
                {"title": "Plan A", "content": "The plan content."},
            ],
            "changelog": [
                {
                    "critique": "Needs more detail.",
                    "verdict": "accept",
                    "reason": "Valid point.",
                    "applied_change": "Added detail to section.",
                },
            ],
        }

        def compact_worker(**kwargs: Any) -> str:
            return json.dumps(plan_data, separators=(",", ":"))

        def pretty_worker(**kwargs: Any) -> str:
            return json.dumps(plan_data, indent=2)

        # Build two pipelines with different workers
        profile: dict[str, Any] = {
            "question_gen": "compact",
            "draft_plan": "compact",
            "layer_high_panel": "high",
            "layer_high_synth": "compact",
            "layer_mid_panel": "mid",
            "layer_mid_synth": "compact",
            "layer_low_panel": "low",
            "layer_low_synth": "compact",
            "final_report": "compact",
        }

        workers_a = {"compact": compact_worker}
        workers_b = {"compact": pretty_worker}

        pipeline_a = build_initial_pipeline(
            profile=profile, workers=workers_a,
        )
        pipeline_b = build_initial_pipeline(
            profile=profile, workers=workers_b,
        )

        # Check that both pipelines have the same DAG structure
        assert pipeline_a.entry == pipeline_b.entry
        assert set(pipeline_a.stages.keys()) == set(pipeline_b.stages.keys())

        # Run question_gen stage on both and compare
        ctx_a = StepContext(
            artifact_root=str(tmp_path / "run_a"),
            state={},
            mode="default",
            inputs={},
        )
        ctx_b = StepContext(
            artifact_root=str(tmp_path / "run_b"),
            state={},
            mode="default",
            inputs={},
        )

        (tmp_path / "run_a").mkdir(parents=True, exist_ok=True)
        (tmp_path / "run_b").mkdir(parents=True, exist_ok=True)

        qg_a = pipeline_a.stages["question_gen"]
        qg_b = pipeline_b.stages["question_gen"]

        # Run both
        qg_a.step.run(ctx_a)
        qg_b.step.run(ctx_b)

        # Load outputs — they should be semantically equivalent
        questions_a = load_questions(str(tmp_path / "run_a"))
        questions_b = load_questions(str(tmp_path / "run_b"))

        eq, diffs = semantic_equivalent(questions_a, questions_b)
        assert eq is True
        assert diffs == []

    def test_semantic_equivalent_rejects_type_mismatch(self) -> None:
        """Type mismatch (dict vs list) is reported as False."""
        eq, diffs = semantic_equivalent({"key": "val"}, ["not", "a", "dict"])
        assert eq is False

    def test_semantic_equivalent_rejects_key_mismatch(self) -> None:
        """Extra/missing keys are reported as False."""
        eq, diffs = semantic_equivalent({"a": 1}, {"a": 1, "b": 2})
        assert eq is False

    def test_semantic_equivalent_rejects_list_length_mismatch(self) -> None:
        """Different-length lists are reported as False."""
        eq, diffs = semantic_equivalent([1, 2], [1, 2, 3])
        assert eq is False
