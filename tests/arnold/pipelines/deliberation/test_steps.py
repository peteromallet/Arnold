"""Tests for the deliberation QuestionGen stage and helpers (T6).

Covers:
- parse_llm_json: direct JSON, ```json fenced, embedded object, error cases
- build_question_gen_stage: Stage shape, AgentStep config, edges
- load_questions: happy path, missing dir, no artifacts, empty file, parse failure
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline.steps.agent import AgentStep
from arnold.pipeline.steps.human_gate import HumanGateStep
from arnold.pipeline.types import Edge, Stage, StepContext

from arnold.pipelines.deliberation.steps import (
    build_draft_plan_stage,
    build_human_gate_stage,
    build_question_gen_stage,
    load_questions,
    parse_llm_json,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _fake_worker(
    prompt: str = "",
    step_name: str = "",
    pipeline_name: str = "",
    inputs: dict[str, str] | None = None,
    mode: str = "",
) -> str:
    """A no-op worker that echoes the prompt for test purposes."""
    return prompt


def _mock_prompt_source(ctx: StepContext, params: Any = None) -> str:
    return "Generate questions for: test idea"


# ── parse_llm_json ─────────────────────────────────────────────────────────


class TestParseLlmJson:
    """parse_llm_json extracts JSON dicts from various LLM output shapes."""

    def test_direct_json_object(self) -> None:
        result = parse_llm_json('{"questions": [{"q": "what?", "rationale": "why"}]}')
        assert result == {"questions": [{"q": "what?", "rationale": "why"}]}

    def test_direct_json_with_whitespace(self) -> None:
        result = parse_llm_json(
            '  \n\n  {"questions": [{"q": "x", "rationale": "y"}]}  \n'
        )
        assert result == {"questions": [{"q": "x", "rationale": "y"}]}

    def test_fenced_json_block(self) -> None:
        result = parse_llm_json(
            'Some preamble text\n```json\n{"questions": [{"q": "Q?", "rationale": "R"}]}\n```\nSome trailing text'
        )
        assert result == {"questions": [{"q": "Q?", "rationale": "R"}]}

    def test_fenced_json_block_with_extra_spaces(self) -> None:
        result = parse_llm_json(
            'Here is the output:\n\n```json\n{"key": "value"}\n```\n\nDone.'
        )
        assert result == {"key": "value"}

    def test_embedded_json_object(self) -> None:
        """An un-fenced JSON object embedded in prose is still found."""
        result = parse_llm_json(
            'The response is {"questions": [{"q": "E?", "rationale": "E"}]} end.'
        )
        assert result == {"questions": [{"q": "E?", "rationale": "E"}]}

    def test_first_object_wins_with_multiple(self) -> None:
        """When multiple objects exist, the first dict is returned."""
        result = parse_llm_json('{"first": true} some text {"second": false}')
        assert result == {"first": True}

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_llm_json("")

    def test_rejects_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_llm_json("   \n  \t  ")

    def test_rejects_array_only(self) -> None:
        with pytest.raises(ValueError, match="valid JSON object"):
            parse_llm_json("[1, 2, 3]")

    def test_rejects_scalar_only(self) -> None:
        with pytest.raises(ValueError, match="valid JSON object"):
            parse_llm_json('"just a string"')

    def test_rejects_unparsable_text(self) -> None:
        with pytest.raises(ValueError, match="valid JSON object"):
            parse_llm_json("This is not JSON at all.")


# ── build_question_gen_stage ───────────────────────────────────────────────


class TestBuildQuestionGenStage:
    """build_question_gen_stage produces a correctly-shaped Stage."""

    def test_returns_stage(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert isinstance(stage, Stage)

    def test_stage_name(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert stage.name == "question_gen"

    def test_step_is_agent_step(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert isinstance(stage.step, AgentStep)

    def test_step_name(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert stage.step.name == "question_gen"

    def test_step_output_label(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert stage.step._output_label == "questions"

    def test_step_output_suffix(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert stage.step._output_suffix == "json"

    def test_step_prompt_source(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert stage.step._prompt_source is _mock_prompt_source

    def test_step_worker(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert stage.step._worker is _fake_worker

    def test_edges(self) -> None:
        stage = build_question_gen_stage(_mock_prompt_source, _fake_worker)
        assert len(stage.edges) == 1
        edge = stage.edges[0]
        assert isinstance(edge, Edge)
        assert edge.label == "done"
        assert edge.target == "human_gate"


# ── load_questions ─────────────────────────────────────────────────────────


class TestLoadQuestions:
    """load_questions discovers and parses versioned JSON artifacts."""

    def _write_artifact(
        self, root: Path, stage: str, version: int, data: dict[str, Any]
    ) -> None:
        questions_dir = root / stage / "questions"
        questions_dir.mkdir(parents=True, exist_ok=True)
        path = questions_dir / f"v{version}.json"
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_loads_latest_version(self, tmp_path: Path) -> None:
        self._write_artifact(tmp_path, "question_gen", 1, {"questions": []})
        self._write_artifact(
            tmp_path, "question_gen", 2,
            {"questions": [{"q": "Q2?", "rationale": "second"}]},
        )
        result = load_questions(str(tmp_path))
        assert result == {"questions": [{"q": "Q2?", "rationale": "second"}]}

    def test_loads_only_version(self, tmp_path: Path) -> None:
        self._write_artifact(
            tmp_path, "question_gen", 1,
            {"questions": [{"q": "only?", "rationale": "solo"}]},
        )
        result = load_questions(str(tmp_path))
        assert result == {"questions": [{"q": "only?", "rationale": "solo"}]}

    def test_skips_non_versioned_files(self, tmp_path: Path) -> None:
        self._write_artifact(
            tmp_path, "question_gen", 1,
            {"questions": [{"q": "v1?", "rationale": "first"}]},
        )
        # Write a noise file that doesn't match v*.json
        noise_dir = tmp_path / "question_gen" / "questions"
        (noise_dir / "README.txt").write_text("not json")
        result = load_questions(str(tmp_path))
        assert result == {"questions": [{"q": "v1?", "rationale": "first"}]}

    def test_custom_stage_name(self, tmp_path: Path) -> None:
        self._write_artifact(
            tmp_path, "my_gen", 1,
            {"questions": [{"q": "custom?", "rationale": "custom"}]},
        )
        result = load_questions(str(tmp_path), stage_name="my_gen")
        assert result == {"questions": [{"q": "custom?", "rationale": "custom"}]}

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        self._write_artifact(
            tmp_path, "question_gen", 1,
            {"questions": [{"q": "path?", "rationale": "p"}]},
        )
        result = load_questions(tmp_path)
        assert result == {"questions": [{"q": "path?", "rationale": "p"}]}

    # ── error cases ───────────────────────────────────────────────────

    def test_raises_on_missing_directory(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="directory not found"):
            load_questions(str(tmp_path / "nonexistent"))

    def test_raises_on_empty_directory(self, tmp_path: Path) -> None:
        questions_dir = tmp_path / "question_gen" / "questions"
        questions_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError, match="No versioned JSON artifacts"):
            load_questions(str(tmp_path))

    def test_raises_on_empty_file(self, tmp_path: Path) -> None:
        questions_dir = tmp_path / "question_gen" / "questions"
        questions_dir.mkdir(parents=True, exist_ok=True)
        (questions_dir / "v1.json").write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_questions(str(tmp_path))

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        questions_dir = tmp_path / "question_gen" / "questions"
        questions_dir.mkdir(parents=True, exist_ok=True)
        (questions_dir / "v1.json").write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="valid JSON object"):
            load_questions(str(tmp_path))

    def test_raises_on_array_instead_of_object(self, tmp_path: Path) -> None:
        questions_dir = tmp_path / "question_gen" / "questions"
        questions_dir.mkdir(parents=True, exist_ok=True)
        (questions_dir / "v1.json").write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="valid JSON object"):
            load_questions(str(tmp_path))


# ── Integration: stage produces artifact that load_questions can read ──────


class TestQuestionGenRoundTrip:
    """End-to-end: AgentStep writes and load_questions reads back."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """build_question_gen_stage → AgentStep.run → load_questions."""

        def echo_json_worker(
            prompt: str = "",
            step_name: str = "",
            pipeline_name: str = "",
            inputs: dict[str, str] | None = None,
            mode: str = "",
        ) -> str:
            return json.dumps({"received_prompt": prompt})

        stage = build_question_gen_stage(_mock_prompt_source, echo_json_worker)
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )
        result = stage.step.run(ctx)
        assert result.next == "done"

        # load_questions should read back what the worker wrote
        loaded = load_questions(str(tmp_path))
        assert isinstance(loaded, dict)
        assert "received_prompt" in loaded

    def test_round_trip_with_json_worker(self, tmp_path: Path) -> None:
        """Worker returns JSON string; load_questions parses it correctly."""

        def json_worker(
            prompt: str = "",
            step_name: str = "",
            pipeline_name: str = "",
            inputs: dict[str, str] | None = None,
            mode: str = "",
        ) -> str:
            return json.dumps({
                "questions": [
                    {"q": "What is the goal?", "rationale": "Scope clarity"},
                    {"q": "What are the risks?", "rationale": "Risk assessment"},
                ]
            })

        stage = build_question_gen_stage(_mock_prompt_source, json_worker)
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )
        stage.step.run(ctx)

        loaded = load_questions(str(tmp_path))
        assert loaded == {
            "questions": [
                {"q": "What is the goal?", "rationale": "Scope clarity"},
                {"q": "What are the risks?", "rationale": "Risk assessment"},
            ]
        }


# ── build_human_gate_stage (T7) ────────────────────────────────────────────


class TestBuildHumanGateStage:
    """build_human_gate_stage produces a correctly-shaped Stage with HumanGateStep."""

    def test_returns_stage(self) -> None:
        stage = build_human_gate_stage()
        assert isinstance(stage, Stage)

    def test_stage_name(self) -> None:
        stage = build_human_gate_stage()
        assert stage.name == "human_gate"

    def test_step_is_human_gate_step(self) -> None:
        stage = build_human_gate_stage()
        assert isinstance(stage.step, HumanGateStep)

    def test_step_name(self) -> None:
        stage = build_human_gate_stage()
        assert stage.step.name == "human_gate"

    def test_step_artifact_stage(self) -> None:
        stage = build_human_gate_stage()
        assert stage.step._artifact_stage == "question_gen"

    def test_step_choices(self) -> None:
        stage = build_human_gate_stage()
        assert stage.step._choices == ["answers_collected"]

    def test_step_checkpoint_filename(self) -> None:
        stage = build_human_gate_stage()
        assert stage.step._checkpoint_filename == "awaiting_user.json"

    def test_step_prompt_is_set(self) -> None:
        stage = build_human_gate_stage()
        assert isinstance(stage.step._prompt, str)
        assert len(stage.step._prompt) > 0
        assert "answers.json" in stage.step._prompt

    def test_edges(self) -> None:
        stage = build_human_gate_stage()
        assert len(stage.edges) == 1
        edge = stage.edges[0]
        assert isinstance(edge, Edge)
        assert edge.label == "answers_collected"
        assert edge.target == "draft_plan"

    def test_halt_on_first_run(self, tmp_path: Path) -> None:
        """HumanGateStep returns next='halt' on first invocation (no resume)."""
        stage = build_human_gate_stage()
        # Set runtime fields that would be injected by the pipeline builder
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
        # awaiting_user.json should have been written
        checkpoint = tmp_path / "awaiting_user.json"
        assert checkpoint.exists()

    def test_resume_with_valid_choice(self, tmp_path: Path) -> None:
        """HumanGateStep returns the resume choice when _resume_choice is set."""
        stage = build_human_gate_stage()
        stage.step._pipeline_name = "deliberation"
        stage.step._pipeline_version = 1

        # First run — halt
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={},
        )
        result1 = stage.step.run(ctx)
        assert result1.next == "halt"

        # Simulate resume by setting _resume_choice on the step instance
        stage.step._resume_choice = "answers_collected"
        result2 = stage.step.run(ctx)
        assert result2.next == "answers_collected"
        # Checkpoint should be cleaned up after successful resume
        checkpoint = tmp_path / "awaiting_user.json"
        assert not checkpoint.exists()


# ── build_draft_plan_stage (T7) ────────────────────────────────────────────


def _passthrough_worker(
    prompt: str = "",
    step_name: str = "",
    pipeline_name: str = "",
    inputs: dict[str, str] | None = None,
    mode: str = "",
) -> str:
    """No-op worker that echoes the prompt for test purposes."""
    return prompt


class TestBuildDraftPlanStage:
    """build_draft_plan_stage produces a correctly-shaped Stage with AgentStep."""

    def test_returns_stage(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert isinstance(stage, Stage)

    def test_stage_name(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert stage.name == "draft_plan"

    def test_step_is_agent_step(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert isinstance(stage.step, AgentStep)

    def test_step_name(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert stage.step.name == "draft_plan"

    def test_step_output_label(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert stage.step._output_label == "plan"

    def test_step_output_suffix(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert stage.step._output_suffix == "json"

    def test_step_input_refs(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert stage.step._input_refs == ["questions", "answers"]

    def test_step_prompt_source(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert stage.step._prompt_source is _mock_prompt_source

    def test_edges(self) -> None:
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        assert len(stage.edges) == 1
        edge = stage.edges[0]
        assert isinstance(edge, Edge)
        assert edge.label == "done"
        assert edge.target == "layer_0_synth"


class TestDraftPlanPreconditionGuard:
    """The worker wrapper validates answers.json before delegating."""

    def _make_ctx(
        self, tmp_path: Path, *, answers_data: dict[str, Any] | None = None
    ) -> StepContext:
        """Create a StepContext with questions.json and (optionally) answers.json."""
        questions_path = tmp_path / "questions.json"
        questions_path.write_text(
            json.dumps({"questions": [{"q": "Q?", "rationale": "R"}]}),
            encoding="utf-8",
        )
        ctx_inputs: dict[str, Any] = {"questions": str(questions_path)}
        if answers_data is not None:
            answers_path = tmp_path / "answers.json"
            answers_path.write_text(json.dumps(answers_data), encoding="utf-8")
            ctx_inputs["answers"] = str(answers_path)
        return StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs=ctx_inputs,
        )

    def test_guard_passes_with_valid_answers_json(self, tmp_path: Path) -> None:
        """Worker runs successfully when answers.json exists and is valid JSON."""
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        ctx = self._make_ctx(
            tmp_path,
            answers_data={"answers": [{"q": "Q?", "a": "Answer"}]},
        )
        result = stage.step.run(ctx)
        assert result.next == "done"

    def test_guard_raises_when_answers_key_missing(self, tmp_path: Path) -> None:
        """Raises ValueError when 'answers' key is absent from ctx.inputs."""
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        ctx = self._make_ctx(tmp_path, answers_data=None)  # no answers key
        with pytest.raises(ValueError, match="answers key not found"):
            stage.step.run(ctx)

    def test_guard_raises_when_answers_json_missing(self, tmp_path: Path) -> None:
        """Raises ValueError when answers.json does not exist at the given path."""
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={"questions": str(tmp_path / "questions.json"), "answers": str(tmp_path / "nonexistent.json")},
        )
        # Create questions.json so the questions path is valid
        (tmp_path / "questions.json").write_text(
            json.dumps({"questions": []}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="answers.json not found"):
            stage.step.run(ctx)

    def test_guard_raises_when_answers_json_empty(self, tmp_path: Path) -> None:
        """Raises ValueError when answers.json is empty."""
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        answers_path = tmp_path / "answers.json"
        answers_path.write_text("", encoding="utf-8")
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={
                "questions": str(tmp_path / "questions.json"),
                "answers": str(answers_path),
            },
        )
        (tmp_path / "questions.json").write_text(
            json.dumps({"questions": []}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="answers.json is empty"):
            stage.step.run(ctx)

    def test_guard_raises_when_answers_json_malformed(self, tmp_path: Path) -> None:
        """Raises ValueError when answers.json is not valid JSON."""
        stage = build_draft_plan_stage(_mock_prompt_source, _passthrough_worker)
        answers_path = tmp_path / "answers.json"
        answers_path.write_text("not valid json {{{", encoding="utf-8")
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={
                "questions": str(tmp_path / "questions.json"),
                "answers": str(answers_path),
            },
        )
        (tmp_path / "questions.json").write_text(
            json.dumps({"questions": []}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="answers.json is not valid JSON"):
            stage.step.run(ctx)

    def test_guard_enriches_inputs_with_file_content(self, tmp_path: Path) -> None:
        """The guard replaces path strings with file contents before delegating."""
        captured_inputs: dict[str, Any] = {}

        def capturing_worker(
            prompt: str = "",
            step_name: str = "",
            pipeline_name: str = "",
            inputs: dict[str, str] | None = None,
            mode: str = "",
        ) -> str:
            captured_inputs["inputs"] = inputs
            return prompt

        stage = build_draft_plan_stage(_mock_prompt_source, capturing_worker)
        questions_path = tmp_path / "questions.json"
        questions_path.write_text('{"questions":[{"q":"Q","rationale":"R"}]}', encoding="utf-8")
        answers_path = tmp_path / "answers.json"
        answers_path.write_text('{"answers":[{"q":"Q","a":"A"}]}', encoding="utf-8")
        ctx = StepContext(
            artifact_root=str(tmp_path),
            state={},
            mode="default",
            inputs={
                "questions": str(questions_path),
                "answers": str(answers_path),
            },
        )
        stage.step.run(ctx)

        worker_inputs = captured_inputs.get("inputs", {})
        # Paths should have been replaced with file contents
        assert "questions" in worker_inputs
        assert "answers" in worker_inputs
        assert "Q" in worker_inputs["questions"]
        assert "A" in worker_inputs["answers"]
        # Should NOT contain paths anymore
        assert str(tmp_path) not in worker_inputs["questions"]
        assert str(tmp_path) not in worker_inputs["answers"]
