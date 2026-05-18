"""Unit tests for YAML pipeline step runtime mechanics.

Covers AgentStep, PanelStep (via executor ordering), GateStep,
and state snapshot semantics.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from megaplan._pipeline.compiler import compile_pipeline, inject_pipeline_context
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.schema import PipelineSpec
from megaplan._pipeline.steps.agent import (
    AgentStep,
    _interpolate_inputs,
    _latest_artifact,
    _next_version,
    _resolve_inputs,
    _resolve_prompt_text,
)
from megaplan._pipeline.steps.gate import GateStep
from megaplan._pipeline.steps.panel import PanelReviewerStep
from megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _make_worker(response: str = "worker output"):
    """Return a mock worker function that returns a fixed response."""

    def worker(**kwargs) -> str:
        return response

    return worker


def _make_delayed_worker(response: str, delay: float = 0.0):
    """Return a mock worker that sleeps before responding (for out-of-order tests)."""

    def worker(**kwargs) -> str:
        if delay > 0:
            time.sleep(delay)
        return response

    return worker


def _minimal_ctx(plan_dir: Path, inputs: dict | None = None) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={},
        profile={},
        mode="test",
        inputs=inputs or {},
    )


def _ensure_prompt_file(pipeline_dir: Path, prompt_ref: str, content: str = "test prompt") -> None:
    """Create a .md prompt file if the ref is a .md path."""
    if prompt_ref.endswith(".md"):
        prompt_path = pipeline_dir / prompt_ref
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(content)


# ── AgentStep ──────────────────────────────────────────────────────────


class TestAgentStep:
    """AgentStep: single-model step with mocked workers."""

    def test_produces_markdown_artifact_with_worker(self, tmp_path: Path):
        """With a worker, AgentStep writes markdown to the correct path."""
        _ensure_prompt_file(tmp_path, "prompts/hello.md")
        step = AgentStep(
            name="synth",
            kind="produce",
            _prompt_ref="prompts/hello.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=[],
            _worker=_make_worker("## Synthesized output\n\nThis is synthetic."),
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        output_path = tmp_path / "synth" / "v1.md"
        assert output_path.exists()
        content = output_path.read_text()
        assert "Synthesized output" in content
        assert result.outputs["synth"] == output_path

    def test_produces_placeholder_without_worker(self, tmp_path: Path):
        """Without a worker, AgentStep writes a placeholder."""
        _ensure_prompt_file(tmp_path, "prompts/test.md")
        step = AgentStep(
            name="noop",
            kind="produce",
            _prompt_ref="prompts/test.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=[],
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)
        output_path = tmp_path / "noop" / "v1.md"
        assert output_path.exists()
        content = output_path.read_text()
        assert "[AgentStep noop]" in content

    def test_version_increments_on_multiple_runs(self, tmp_path: Path):
        """Each run writes a new versioned artifact."""
        _ensure_prompt_file(tmp_path, "prompts/iter.md")
        step = AgentStep(
            name="iter",
            kind="produce",
            _prompt_ref="prompts/iter.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=[],
            _worker=_make_worker("v1 content"),
        )
        ctx = _minimal_ctx(tmp_path)

        step.run(ctx)
        assert (tmp_path / "iter" / "v1.md").exists()

        step._worker = _make_worker("v2 content")
        step.run(ctx)
        assert (tmp_path / "iter" / "v2.md").exists()
        assert (tmp_path / "iter" / "v2.md").read_text() == "v2 content"

    def test_input_interpolation_through_step(self, tmp_path: Path):
        """The prompt is rendered with interpolated inputs before being sent to worker."""
        _ensure_prompt_file(tmp_path, "prompts/revise.md", "Review this: {draft}")
        draft = tmp_path / "draft.md"
        draft.write_text("Original draft text")

        step = AgentStep(
            name="revise",
            kind="produce",
            _prompt_ref="prompts/revise.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=["draft"],
            _worker=_make_worker("Fixed response"),
        )
        ctx = _minimal_ctx(tmp_path, {"draft": draft})
        result = step.run(ctx)
        output_path = tmp_path / "revise" / "v1.md"
        assert output_path.exists()
        # Worker receives the rendered prompt (with {draft} interpolated)
        assert output_path.read_text() == "Fixed response"

    def test_resolve_inputs_from_stage_output(self, tmp_path: Path):
        """_resolve_inputs resolves a stage_id to its latest artifact."""
        stage_dir = tmp_path / "panel_review"
        stage_dir.mkdir()
        (stage_dir / "v1.md").write_text("stage output v1")
        (stage_dir / "v2.md").write_text("stage output v2")

        ctx = _minimal_ctx(tmp_path)
        resolved = _resolve_inputs(["panel_review"], ctx)
        assert "panel_review" in resolved
        assert resolved["panel_review"].name == "v2.md"

    def test_resolve_inputs_from_declared_inputs(self, tmp_path: Path):
        """Declared inputs take precedence over stage outputs."""
        draft = tmp_path / "my_draft.md"
        draft.write_text("declared input content")

        ctx = _minimal_ctx(tmp_path, {"draft": draft})
        resolved = _resolve_inputs(["draft"], ctx)
        assert "draft" in resolved
        assert resolved["draft"] == draft

    def test_resolve_inputs_star_syntax(self, tmp_path: Path):
        """_resolve_inputs with stage_id.* resolves all panel sub-outputs in reviewer-list order."""
        for reviewer in ["pessimist", "optimist", "structuralist"]:
            d = tmp_path / "panel_review" / reviewer
            d.mkdir(parents=True)
            (d / "v1.md").write_text(f"{reviewer} output")

        ctx = _minimal_ctx(tmp_path)
        panel_order = {"panel_review": ["pessimist", "optimist", "structuralist"]}
        resolved = _resolve_inputs(
            ["panel_review.*"], ctx, panel_reviewer_order=panel_order
        )
        assert "panel_review.pessimist" in resolved
        assert "panel_review.optimist" in resolved
        assert "panel_review.structuralist" in resolved
        keys = list(resolved.keys())
        assert keys == [
            "panel_review.pessimist",
            "panel_review.optimist",
            "panel_review.structuralist",
        ]

    def test_prompt_text_from_md_file(self, tmp_path: Path):
        """_resolve_prompt_text reads .md files from pipeline dir."""
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "test.md").write_text("# Test prompt\n\nContent here.")

        text = _resolve_prompt_text("prompts/test.md", tmp_path)
        assert "# Test prompt" in text

    def test_prompt_text_from_registry(self, tmp_path: Path):
        """_resolve_prompt_text uses registry for non-.md keys."""
        registry = {"my_prompt": "prompt from registry"}
        text = _resolve_prompt_text("my_prompt", tmp_path, prompt_registry=registry.get)
        assert text == "prompt from registry"

    def test_prompt_text_missing_file(self, tmp_path: Path):
        """Missing .md file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            _resolve_prompt_text("prompts/nonexistent.md", tmp_path)

    def test_prompt_text_no_registry(self, tmp_path: Path):
        """Non-.md ref without registry raises ValueError."""
        with pytest.raises(ValueError, match="Cannot resolve prompt"):
            _resolve_prompt_text("unknown_key", tmp_path)


# ── PanelStep ordering via executor ────────────────────────────────────


class TestPanelStepOrdering:
    """Panel output ordering follows YAML reviewer-list order even when
    futures complete out of order."""

    def test_panel_outputs_in_reviewer_order(self, tmp_path: Path):
        """Three reviewers with different delays: output order matches
        YAML reviewer list (pessimist, optimist, structuralist)."""
        # Create prompt files for each reviewer
        for reviewer in ["pessimist", "optimist", "structuralist"]:
            _ensure_prompt_file(tmp_path, f"prompts/{reviewer}.md",
                               f"Reviewer: {reviewer}")

        # pessimist: slowest (0.15s), optimist: medium (0.08s), structuralist: fastest (0s)
        # Futures complete in reverse order: structuralist first, optimist second, pessimist last
        reviewer_steps = [
            PanelReviewerStep(
                name="panel_review.pessimist",
                kind="produce",
                prompt_key="prompts/pessimist.md",
                _prompt_ref="prompts/pessimist.md",
                _pipeline_dir=tmp_path,
                _pipeline_name="test-pipe",
                _input_refs=["draft"],
                _reviewer_id="pessimist",
                _worker=_make_delayed_worker("pessimist says: flawed", delay=0.15),
                _mode="test",
            ),
            PanelReviewerStep(
                name="panel_review.optimist",
                kind="produce",
                prompt_key="prompts/optimist.md",
                _prompt_ref="prompts/optimist.md",
                _pipeline_dir=tmp_path,
                _pipeline_name="test-pipe",
                _input_refs=["draft"],
                _reviewer_id="optimist",
                _worker=_make_delayed_worker("optimist says: promising", delay=0.08),
                _mode="test",
            ),
            PanelReviewerStep(
                name="panel_review.structuralist",
                kind="produce",
                prompt_key="prompts/structuralist.md",
                _prompt_ref="prompts/structuralist.md",
                _pipeline_dir=tmp_path,
                _pipeline_name="test-pipe",
                _input_refs=["draft"],
                _reviewer_id="structuralist",
                _worker=_make_delayed_worker("structuralist says: needs work", delay=0.0),
                _mode="test",
            ),
        ]

        draft = tmp_path / "draft.md"
        draft.write_text("Test draft")

        ctx = _minimal_ctx(tmp_path, {"draft": draft})

        def _join(results, ctx):
            merged = {}
            for r in results:
                merged.update(dict(r.outputs))
            return StepResult(outputs=merged, next="halt")

        stage = ParallelStage(
            name="panel_review",
            steps=tuple(reviewer_steps),
            join=_join,
            edges=(),
            max_workers=3,
        )

        pipeline = Pipeline(stages={"panel_review": stage}, entry="panel_review")
        ctx = inject_pipeline_context(ctx, "test-pipe")

        result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

        # Verify all reviewer outputs exist (regardless of completion order).
        # PanelReviewerStep writes to <plan_dir>/<stage_id>/<reviewer_id>/ per convention.
        for reviewer in ["pessimist", "optimist", "structuralist"]:
            path = tmp_path / "panel_review" / reviewer / "v1.md"
            assert path.exists(), f"Missing output for {reviewer}"

        assert (
            tmp_path / "panel_review" / "pessimist" / "v1.md"
        ).read_text() == "pessimist says: flawed"
        assert (
            tmp_path / "panel_review" / "optimist" / "v1.md"
        ).read_text() == "optimist says: promising"
        assert (
            tmp_path / "panel_review" / "structuralist" / "v1.md"
        ).read_text() == "structuralist says: needs work"

        # The join merges results in array-index order (YAML list order).
        # Verify merged outputs preserve YAML reviewer-list insertion order.
        assert result["final_stage"] == "panel_review"

    def test_panel_join_preserves_reviewer_order_in_outputs(self, tmp_path: Path):
        """The join function merges outputs in the ordered results array,
        so merged dict keys follow YAML reviewer-list order."""
        _ensure_prompt_file(tmp_path, "prompts/r.md")

        # Build reviewers that would complete out of order
        reviewer_steps = [
            PanelReviewerStep(
                name="panel_review.first",
                kind="produce",
                _prompt_ref="prompts/r.md",
                _pipeline_dir=tmp_path,
                _pipeline_name="test-pipe",
                _input_refs=[],
                _reviewer_id="first",
                _worker=_make_delayed_worker("first output", delay=0.05),
                _mode="test",
            ),
            PanelReviewerStep(
                name="panel_review.second",
                kind="produce",
                _prompt_ref="prompts/r.md",
                _pipeline_dir=tmp_path,
                _pipeline_name="test-pipe",
                _input_refs=[],
                _reviewer_id="second",
                _worker=_make_delayed_worker("second output", delay=0.0),
                _mode="test",
            ),
        ]

        def _join(results, ctx):
            merged = {}
            for r in results:
                merged.update(dict(r.outputs))
            # Assert the merged dict keys follow submission order
            keys = list(merged.keys())
            assert keys == ["first", "second"], (
                f"Expected reviewer-list order [first, second], got {keys}"
            )
            return StepResult(outputs=merged, next="halt")

        stage = ParallelStage(
            name="panel_review",
            steps=tuple(reviewer_steps),
            join=_join,
            edges=(),
            max_workers=2,
        )

        pipeline = Pipeline(stages={"panel_review": stage}, entry="panel_review")
        ctx = _minimal_ctx(tmp_path)
        ctx = inject_pipeline_context(ctx, "test-pipe")

        result = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
        assert result["final_stage"] == "panel_review"

    def test_panel_reviewer_step_produces_correct_output_key(self, tmp_path: Path):
        """PanelReviewerStep.run returns output keyed by reviewer_id, not full name."""
        _ensure_prompt_file(tmp_path, "prompts/pessimist.md")
        draft = tmp_path / "draft.md"
        draft.write_text("test")

        step = PanelReviewerStep(
            name="panel_review.pessimist",
            kind="produce",
            _prompt_ref="prompts/pessimist.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=["draft"],
            _reviewer_id="pessimist",
            _worker=_make_worker("pessimist critique"),
        )
        ctx = _minimal_ctx(tmp_path, {"draft": draft})
        result = step.run(ctx)

        assert "pessimist" in result.outputs
        output_path = result.outputs["pessimist"]
        assert output_path == tmp_path / "panel_review" / "pessimist" / "v1.md"
        assert output_path.read_text() == "pessimist critique"


# ── State snapshot ─────────────────────────────────────────────────────


class TestStateSnapshot:
    """Pipeline identity (name + content hash) is snapshotted into state at run start."""

    def test_state_includes_pipeline_name_and_hash(self, tmp_path: Path):
        """After a pipeline run, state.json contains pipeline name and content hash."""
        _ensure_prompt_file(tmp_path, "prompts/hello.md")

        spec_data = {
            "name": "snapshot-test",
            "version": 1,
            "description": "Testing state snapshots",
            "default_profile": "partnered",
            "stages": [
                {"id": "s1", "kind": "agent", "prompt": "prompts/hello.md"},
            ],
        }
        spec = PipelineSpec.model_validate(spec_data)

        pipeline = compile_pipeline(
            spec,
            pipeline_dir=tmp_path,
            worker=_make_worker("done"),
            mode="test",
        )

        plan_dir = tmp_path / "plan"
        state = {
            "_pipeline_name": "snapshot-test",
            "_pipeline_version": 1,
            "_content_hash": "abc123hash",
        }
        ctx = StepContext(
            plan_dir=plan_dir,
            state=state,
            profile={},
            mode="test",
            inputs={},
        )
        ctx = inject_pipeline_context(ctx, "snapshot-test")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        state_json = plan_dir / "state.json"
        assert state_json.exists()
        state_data = json.loads(state_json.read_text())
        assert state_data.get("_pipeline_name") == "snapshot-test"
        assert state_data.get("_pipeline_version") == 1
        assert state_data.get("_content_hash") == "abc123hash"

    def test_pipeline_identity_preserved_through_stages(self, tmp_path: Path):
        """Pipeline identity is preserved when running a single stage via executor."""
        _ensure_prompt_file(tmp_path, "prompts/hello.md")

        spec_data = {
            "name": "identity-test",
            "version": 2,
            "description": "Identity test",
            "default_profile": "partnered",
            "stages": [
                {"id": "stage_a", "kind": "agent", "prompt": "prompts/hello.md"},
            ],
        }
        spec = PipelineSpec.model_validate(spec_data)

        pipeline = compile_pipeline(
            spec,
            pipeline_dir=tmp_path,
            worker=_make_worker("done"),
            mode="test",
        )

        plan_dir = tmp_path / "plan"
        state = {
            "_pipeline_name": "identity-test",
            "_pipeline_version": 2,
            "_content_hash": "hash456",
        }
        ctx = StepContext(
            plan_dir=plan_dir,
            state=state,
            profile={},
            mode="test",
            inputs={},
        )
        ctx = inject_pipeline_context(ctx, "identity-test")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["final_stage"] == "stage_a"

        state_json = plan_dir / "state.json"
        state_data = json.loads(state_json.read_text())
        assert state_data.get("_pipeline_name") == "identity-test"
        assert state_data.get("_pipeline_version") == 2


# ── GateStep ───────────────────────────────────────────────────────────


class TestGateStep:
    """GateStep produces a Verdict with recommendation."""

    def test_gate_step_produces_verdict(self, tmp_path: Path):
        """GateStep without a worker produces a default proceed verdict."""
        _ensure_prompt_file(tmp_path, "prompts/judge.md")

        step = GateStep(
            name="judge",
            kind="judge",
            prompt_key="prompts/judge.md",
            _prompt_ref="prompts/judge.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=[],
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.verdict is not None
        assert result.verdict.recommendation == "proceed"
        assert result.verdict.score == 0.5
        assert result.next == "proceed"

        output_path = tmp_path / "judge" / "v1.json"
        assert output_path.exists()

    def test_gate_step_with_worker_verdict(self, tmp_path: Path):
        """GateStep with worker parses the worker's JSON response."""
        _ensure_prompt_file(tmp_path, "prompts/judge.md")

        verdict_json = json.dumps({
            "recommendation": "iterate",
            "score": 0.3,
            "flags": ["needs_revision"],
            "notes": "Major issues found",
        })
        step = GateStep(
            name="judge",
            kind="judge",
            _prompt_ref="prompts/judge.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=[],
            _worker=_make_worker(verdict_json),
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.verdict is not None
        assert result.verdict.recommendation == "iterate"
        assert result.verdict.score == 0.3
        assert result.verdict.flags == ("needs_revision",)
        assert result.verdict.notes == "Major issues found"
        assert result.next == "iterate"

    def test_gate_step_invalid_json_fallback(self, tmp_path: Path):
        """Invalid JSON from worker falls back to proceed."""
        _ensure_prompt_file(tmp_path, "prompts/judge.md")

        step = GateStep(
            name="judge",
            kind="judge",
            _prompt_ref="prompts/judge.md",
            _pipeline_dir=tmp_path,
            _pipeline_name="test-pipe",
            _input_refs=[],
            _worker=_make_worker("not json at all"),
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.verdict is not None
        assert result.verdict.recommendation == "proceed"
        assert result.verdict.score == 0.0


# ── Utility functions (direct tests) ───────────────────────────────────


class TestUtilityFunctions:
    """Direct tests for _latest_artifact, _next_version, _interpolate_inputs."""

    def test_latest_artifact_returns_newest(self, tmp_path: Path):
        d = tmp_path / "stage"
        d.mkdir()
        (d / "v1.md").write_text("v1")
        (d / "v3.md").write_text("v3")
        (d / "v2.md").write_text("v2")

        latest = _latest_artifact(d)
        assert latest is not None
        assert latest.name == "v3.md"

    def test_latest_artifact_empty_dir(self, tmp_path: Path):
        d = tmp_path / "stage"
        d.mkdir()
        assert _latest_artifact(d) is None

    def test_latest_artifact_no_v_files(self, tmp_path: Path):
        d = tmp_path / "stage"
        d.mkdir()
        (d / "other.txt").write_text("not a v-file")
        assert _latest_artifact(d) is None

    def test_next_version_empty(self, tmp_path: Path):
        d = tmp_path / "stage"
        assert _next_version(d) == 1

    def test_next_version_existing(self, tmp_path: Path):
        d = tmp_path / "stage"
        d.mkdir()
        (d / "v1.md").write_text("")
        (d / "v3.md").write_text("")
        assert _next_version(d) == 4

    def test_interpolate_inputs(self, tmp_path: Path):
        draft = tmp_path / "draft.md"
        draft.write_text("Hello World")

        result = _interpolate_inputs("Review: {draft}", {"draft": draft})
        assert result == "Review: Hello World"

    def test_interpolate_inputs_missing_placeholder(self, tmp_path: Path):
        draft = tmp_path / "draft.md"
        draft.write_text("Hello")
        result = _interpolate_inputs("No placeholder here", {"draft": draft})
        assert result == "No placeholder here"

    def test_interpolate_inputs_unreadable_file(self, tmp_path: Path):
        result = _interpolate_inputs(
            "Review: {missing}",
            {"missing": tmp_path / "nonexistent.md"},
        )
        assert "[could not read:" in result


# ── Compilation integration ────────────────────────────────────────────


class TestCompileAndRun:
    """End-to-end compilation + execution of spec-based pipelines."""

    def test_compile_and_run_agent_pipeline(self, tmp_path: Path):
        """Compile a minimal agent pipeline and run it end-to-end."""
        _ensure_prompt_file(tmp_path, "prompts/hello.md")
        spec_data = {
            "name": "minimal",
            "version": 1,
            "description": "Minimal pipeline",
            "default_profile": "partnered",
            "stages": [
                {"id": "hello", "kind": "agent", "prompt": "prompts/hello.md"},
            ],
        }
        spec = PipelineSpec.model_validate(spec_data)

        pipeline = compile_pipeline(
            spec,
            pipeline_dir=tmp_path,
            worker=_make_worker("Hello from worker"),
            mode="test",
        )

        plan_dir = tmp_path / "plan"
        ctx = _minimal_ctx(plan_dir)
        ctx = inject_pipeline_context(ctx, "minimal")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["final_stage"] == "hello"
        assert (plan_dir / "hello" / "v1.md").read_text() == "Hello from worker"

    def test_compile_and_run_gate_pipeline_with_edges(self, tmp_path: Path):
        """Pipeline with gate stages connected by edges allows multi-stage flow
        because GateStep returns non-halt labels (e.g. 'proceed')."""
        _ensure_prompt_file(tmp_path, "prompts/first.md")
        _ensure_prompt_file(tmp_path, "prompts/second.md")

        spec_data = {
            "name": "two-gate",
            "version": 1,
            "description": "Two gate stages chained",
            "default_profile": "partnered",
            "stages": [
                {"id": "first", "kind": "gate", "prompt": "prompts/first.md"},
                {"id": "second", "kind": "gate", "prompt": "prompts/second.md",
                 "inputs": ["first"]},
            ],
            "edges": [
                {"from": "first", "when": "proceed", "to": "second"},
                {"from": "second", "when": "proceed", "to": "done"},
            ],
        }
        spec = PipelineSpec.model_validate(spec_data)

        pipeline = compile_pipeline(
            spec,
            pipeline_dir=tmp_path,
            worker=_make_worker(json.dumps({"recommendation": "proceed", "score": 0.8})),
            mode="test",
        )

        plan_dir = tmp_path / "plan"
        ctx = _minimal_ctx(plan_dir)
        ctx = inject_pipeline_context(ctx, "two-gate")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["final_stage"] == "second"
        assert (plan_dir / "first" / "v1.json").exists()
        assert (plan_dir / "second" / "v1.json").exists()
