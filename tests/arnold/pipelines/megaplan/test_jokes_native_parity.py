"""Native runtime coverage for the ``jokes`` pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from arnold.pipeline import StepContext, run_pipeline
from arnold.pipeline.native import NativeExecutionResult, NativeProgram, run_native_pipeline
from arnold.pipelines.megaplan.pipelines.jokes import build_pipeline
from arnold.pipelines.megaplan.pipelines.jokes.steps import JokeStep
from arnold.runtime.envelope import RuntimeEnvelope


def _deterministic_worker(**kwargs: object) -> str:
    step_name = str(kwargs.get("step_name") or "")
    inputs = kwargs.get("inputs") or {}
    input_keys = sorted(str(key) for key in dict(inputs))
    return (
        f"step={step_name}\n"
        f"input_keys={','.join(input_keys)}\n"
        "body=deterministic jokes native output\n"
    )


def _patch_joke_step(monkeypatch: pytest.MonkeyPatch) -> None:
    def _patched_run(self: JokeStep, ctx: StepContext) -> Any:
        state = dict(ctx.state) if isinstance(ctx.state, dict) else {}
        state["joke_topic"] = str(state.get("joke_topic") or self.topic or "default")
        artifacts = state.get("_joke_artifacts")
        state["_joke_artifacts"] = dict(artifacts) if isinstance(artifacts, dict) else {}

        out_dir = Path(ctx.artifact_root) / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        version = len(sorted(out_dir.glob("v*.md"))) + 1
        prompt_path = out_dir / f"prompt_v{version}.md"
        artifact_path = out_dir / f"v{version}.md"

        body = _deterministic_worker(
            step_name=self.name,
            inputs=state["_joke_artifacts"],
        )
        prompt_path.write_text(f"# prompt: {self.prompt_key}\n", encoding="utf-8")
        artifact_path.write_text(body, encoding="utf-8")

        artifacts = dict(state["_joke_artifacts"])
        artifacts[self.name] = str(artifact_path)
        patch: dict[str, Any] = {
            "joke_topic": state["joke_topic"],
            "_joke_artifacts": artifacts,
            "_joke_last_stage": self.name,
        }
        if self.next_label == "halt":
            patch["joke_artifact"] = str(artifact_path)

        from arnold.pipeline import StepResult

        return StepResult(
            outputs={self.name: str(artifact_path), f"{self.name}_prompt": str(prompt_path)},
            next=self.next_label,
            state_patch=patch,
        )

    monkeypatch.setattr(JokeStep, "run", _patched_run)


def _stage_sequence(result: NativeExecutionResult) -> tuple[str, ...]:
    sequence: list[str] = []
    for stage_id in result.stages:
        parts = stage_id.split("__")
        if len(parts) >= 2:
            sequence.append(parts[-2])
    return tuple(sequence)


def test_jokes_pipeline_attaches_direct_native_program() -> None:
    pipeline = build_pipeline(topic="dependency graphs")

    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "jokes"
    assert tuple(pipeline.resource_bundles) == ()
    assert tuple(pipeline.stages) == ("draft", "tighten", "emit")


def test_jokes_native_program_threads_build_topic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_joke_step(monkeypatch)
    pipeline = build_pipeline(topic="dependency graphs")
    assert pipeline.native_program is not None

    result = run_native_pipeline(
        pipeline.native_program,
        artifact_root=tmp_path,
        initial_state={},
    )

    assert _stage_sequence(result) == ("draft", "tighten", "emit")
    assert result.state["joke_topic"] == "dependency graphs"
    assert result.state["_joke_last_stage"] == "emit"
    assert (tmp_path / "emit" / "v1.md").exists()


def test_jokes_executor_uses_native_program_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_joke_step(monkeypatch)
    pipeline = build_pipeline(topic="runtime defaults")
    envelope = RuntimeEnvelope(artifact_root=str(tmp_path))

    result = run_pipeline(pipeline, initial_state={}, envelope=envelope)

    assert result.state["joke_topic"] == "runtime defaults"
    assert result.state["_joke_last_stage"] == "emit"
    assert (tmp_path / "resume_cursor.json").exists() is False
    assert (tmp_path / "emit" / "v1.md").exists()


def test_jokes_native_resume_after_draft(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_joke_step(monkeypatch)
    pipeline = build_pipeline(topic="dependency graphs")
    assert pipeline.native_program is not None

    first = run_native_pipeline(
        pipeline.native_program,
        artifact_root=tmp_path,
        initial_state={},
        max_phases=1,
    )
    assert first.suspended is True
    assert _stage_sequence(first) == ("draft",)
    assert (tmp_path / "draft" / "v1.md").exists()
    assert (tmp_path / "resume_cursor.json").exists()
    cursor = json.loads((tmp_path / "resume_cursor.json").read_text(encoding="utf-8"))
    assert cursor["native"]["pc"] >= 1

    second = run_native_pipeline(
        pipeline.native_program,
        artifact_root=tmp_path,
        resume=True,
    )

    assert second.suspended is False
    assert _stage_sequence(second) == ("draft", "tighten", "emit")
    assert (tmp_path / "emit" / "v1.md").exists()
