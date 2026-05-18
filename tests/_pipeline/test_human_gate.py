"""Unit tests for HumanGateStep pause/resume semantics.

Verifies pause file shape, resume with choice, fresh artifact
re-reads after disk edits, and cleanup after resume.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._pipeline.compiler import compile_pipeline, inject_pipeline_context
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.resume import check_awaiting_user, with_entry
from megaplan._pipeline.schema import PipelineSpec
from megaplan._pipeline.steps.human_gate import HumanGateStep
from megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


def _make_worker(response: str = "worker output"):
    def worker(**kwargs) -> str:
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


# ── HumanGateStep direct tests ─────────────────────────────────────────


class TestHumanGateStep:
    """HumanGateStep: pause file shape, resume choice, cleanup."""

    def test_pause_writes_awaiting_user_json(self, tmp_path: Path):
        """On first run (no resume choice), writes correct awaiting_user.json."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("Revised draft content")

        step = HumanGateStep(
            name="human_decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["continue", "stop"],
            _pipeline_name="writing-panel-strict",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.next == "halt"
        assert result.state_patch.get("_pipeline_paused") is True
        assert result.state_patch.get("_pipeline_paused_stage") == "human_decide"

        awaiting_path = tmp_path / "awaiting_user.json"
        assert awaiting_path.exists()
        data = json.loads(awaiting_path.read_text())

        assert data["pipeline"] == "writing-panel-strict"
        assert data["version"] == 1
        assert data["stage"] == "human_decide"
        assert data["artifact_stage"] == "revise"
        assert data["choices"] == ["continue", "stop"]
        assert data["artifact_path"] is not None
        assert "revise" in data["artifact_path"]
        assert "v1.md" in data["artifact_path"]

    def test_pause_with_missing_artifact(self, tmp_path: Path):
        """When artifact stage has no output yet, artifact_path is None."""
        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="nonexistent",
            _choices=["ok"],
            _pipeline_name="test",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        awaiting_path = tmp_path / "awaiting_user.json"
        data = json.loads(awaiting_path.read_text())
        assert data["artifact_path"] is None

    def test_resume_with_choice_supplied_via_constructor(self, tmp_path: Path):
        """When _resume_choice is set, returns it as the next label."""
        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["continue", "stop"],
            _pipeline_name="test",
            _pipeline_version=1,
            _resume_choice="continue",
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.next == "continue"
        assert result.outputs == {}

    def test_resume_with_choice_from_disk(self, tmp_path: Path):
        """When _resume_choice is None but awaiting_user.json has _resume_choice,
        the step reads from disk."""
        awaiting_data = {
            "pipeline": "test",
            "version": 1,
            "stage": "decide",
            "artifact_stage": "revise",
            "artifact_path": str(tmp_path / "revise" / "v1.md"),
            "choices": ["continue", "stop"],
            "message": "Paused",
            "_resume_choice": "stop",
        }
        (tmp_path / "awaiting_user.json").write_text(json.dumps(awaiting_data))

        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["continue", "stop"],
            _pipeline_name="test",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.next == "stop"
        assert not (tmp_path / "awaiting_user.json").exists()

    def test_resume_cleans_up_awaiting_file(self, tmp_path: Path):
        """Resume path removes awaiting_user.json."""
        awaiting_data = {
            "pipeline": "test",
            "version": 1,
            "stage": "decide",
            "artifact_stage": "revise",
            "artifact_path": str(tmp_path / "revise" / "v1.md"),
            "choices": ["accept"],
            "message": "...",
            "_resume_choice": "accept",
        }
        (tmp_path / "awaiting_user.json").write_text(json.dumps(awaiting_data))

        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["accept"],
            _pipeline_name="test",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.next == "accept"
        assert not (tmp_path / "awaiting_user.json").exists()

    def test_invalid_choice_not_accepted(self, tmp_path: Path):
        """A choice not in _choices list is ignored, falls through to pause."""
        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["continue", "stop"],
            _pipeline_name="test",
            _pipeline_version=1,
            _resume_choice="invalid_choice",
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.next == "halt"
        assert result.state_patch.get("_pipeline_paused") is True

    def test_pause_file_has_required_keys(self, tmp_path: Path):
        """The pause file contains all keys the resume path expects."""
        (tmp_path / "revise").mkdir()
        (tmp_path / "revise" / "v1.md").write_text("content")

        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["yes", "no"],
            _pipeline_name="test-pipe",
            _pipeline_version=2,
            _resume_choice=None,
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        required_keys = {"pipeline", "version", "stage", "artifact_stage",
                         "artifact_path", "choices", "message"}
        assert required_keys.issubset(data.keys())
        assert data["pipeline"] == "test-pipe"
        assert data["version"] == 2
        assert isinstance(data["choices"], list)
        assert len(data["choices"]) == 2


# ── check_awaiting_user helper ─────────────────────────────────────────


class TestCheckAwaitingUser:
    """The check_awaiting_user dispatch gate."""

    def test_returns_none_when_no_file(self, tmp_path: Path):
        assert check_awaiting_user(tmp_path) is None

    def test_returns_data_when_file_present(self, tmp_path: Path):
        data = {
            "pipeline": "test",
            "version": 1,
            "stage": "decide",
            "choices": ["ok"],
            "artifact_stage": "revise",
            "artifact_path": str(tmp_path / "revise" / "v1.md"),
            "message": "paused",
        }
        (tmp_path / "awaiting_user.json").write_text(json.dumps(data))
        result = check_awaiting_user(tmp_path)
        assert result is not None
        assert result["pipeline"] == "test"
        assert result["choices"] == ["ok"]

    def test_returns_none_for_invalid_json(self, tmp_path: Path):
        (tmp_path / "awaiting_user.json").write_text("not json")
        assert check_awaiting_user(tmp_path) is None

    def test_returns_none_for_non_dict(self, tmp_path: Path):
        (tmp_path / "awaiting_user.json").write_text("[1, 2, 3]")
        assert check_awaiting_user(tmp_path) is None


# ── Full pipeline pause/resume via executor ────────────────────────────


class TestPauseResumeInPipeline:
    """Human gate within a pipeline executed via run_pipeline."""

    def test_human_gate_pauses_pipeline(self, tmp_path: Path):
        """When run_pipeline hits a human_gate stage in pause mode,
        it returns halt_reason='awaiting_user'."""
        _ensure_prompt_file(tmp_path, "prompts/write.md")

        # Build pipeline manually: agent → human_gate
        # The agent must NOT return "halt" (or executor terminates before
        # reaching human_gate). We build a custom agent-like step that
        # returns a label matching the edge.
        from dataclasses import dataclass

        @dataclass
        class ChainedAgentStep:
            name: str
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:
                output_dir = ctx.plan_dir / self.name
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / "v1.md"
                output_path.write_text("produced content")
                return StepResult(
                    outputs={self.name: output_path},
                    next="continue",  # Non-halt label for edge dispatch
                )

        write_stage = Stage(
            name="write",
            step=ChainedAgentStep(name="write"),
            edges=(Edge(label="continue", target="decide"),),
        )

        gate_step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="write",
            _choices=["again", "stop"],
            _pipeline_name="pause-test",
            _pipeline_version=1,
            _resume_choice=None,  # Pause mode
        )
        gate_stage = Stage(
            name="decide",
            step=gate_step,
            edges=(
                Edge(label="again", target="write"),
                Edge(label="stop", target="halt"),
            ),
        )

        pipeline = Pipeline(
            stages={"write": write_stage, "decide": gate_stage},
            entry="write",
        )

        plan_dir = tmp_path / "plan"
        ctx = _minimal_ctx(plan_dir)
        ctx = inject_pipeline_context(ctx, "pause-test")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        assert result["halt_reason"] == "awaiting_user"
        assert result["final_stage"] == "decide"
        assert (plan_dir / "awaiting_user.json").exists()

    def test_resume_continue_loops_back(self, tmp_path: Path):
        """Resume with 'again' loops back to write stage, which produces
        a new artifact version. Uses disk-based resume_choice so the
        HumanGateStep consumes it once and pauses on the second encounter."""
        plan_dir = tmp_path / "plan"

        from dataclasses import dataclass

        @dataclass
        class ChainedAgentStep:
            name: str
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:
                output_dir = ctx.plan_dir / self.name
                output_dir.mkdir(parents=True, exist_ok=True)
                existing = [
                    int(f.stem[1:]) for f in output_dir.glob("v*.md")
                    if f.stem[1:].isdigit()
                ]
                version = (max(existing) + 1) if existing else 1
                output_path = output_dir / f"v{version}.md"
                output_path.write_text(f"iteration {version}")
                return StepResult(
                    outputs={self.name: output_path},
                    next="continue",
                )

        write_stage = Stage(
            name="write",
            step=ChainedAgentStep(name="write"),
            edges=(Edge(label="continue", target="decide"),),
        )

        def make_gate_stage(resume_choice=None):
            """Build a decide stage. If resume_choice is None, the step
            checks awaiting_user.json on disk (one-shot)."""
            gate_step = HumanGateStep(
                name="decide",
                kind="decide",
                _artifact_stage="write",
                _choices=["again", "stop"],
                _pipeline_name="loop-test",
                _pipeline_version=1,
                _resume_choice=resume_choice,
            )
            return Stage(
                name="decide",
                step=gate_step,
                edges=(
                    Edge(label="again", target="write"),
                    Edge(label="stop", target="halt"),
                ),
            )

        # ── First run: write → pause at decide ──
        pipeline = Pipeline(
            stages={"write": write_stage, "decide": make_gate_stage()},
            entry="write",
        )
        ctx = _minimal_ctx(plan_dir)
        ctx = inject_pipeline_context(ctx, "loop-test")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["halt_reason"] == "awaiting_user"
        assert (plan_dir / "write" / "v1.md").read_text() == "iteration 1"

        # ── Edit artifact on disk ──
        (plan_dir / "write" / "v1.md").write_text("USER EDITED v1")

        # ── Resume with 'again' via disk ──
        # Write _resume_choice into awaiting_user.json so HumanGateStep
        # reads it from disk and cleans up the file after use.
        awaiting_data = json.loads((plan_dir / "awaiting_user.json").read_text())
        awaiting_data["_resume_choice"] = "again"
        (plan_dir / "awaiting_user.json").write_text(json.dumps(awaiting_data))

        pipeline2 = Pipeline(
            stages={"write": write_stage, "decide": make_gate_stage()},
            entry="decide",
        )

        state2 = dict(result["state"])
        state2.pop("_pipeline_paused", None)
        state2.pop("_pipeline_paused_stage", None)

        ctx2 = StepContext(
            plan_dir=plan_dir,
            state=state2,
            profile={},
            mode="test",
            inputs={},
        )
        ctx2 = inject_pipeline_context(ctx2, "loop-test")

        result2 = run_pipeline(pipeline2, ctx2, artifact_root=plan_dir)
        # Write runs again, producing v2
        assert (plan_dir / "write" / "v2.md").exists()
        assert (plan_dir / "write" / "v2.md").read_text() == "iteration 2"
        # Should pause again (awaiting_user.json was cleaned up by resume,
        # and _resume_choice is not set, so second pass through decide pauses)
        assert result2["halt_reason"] == "awaiting_user"

        # ── Resume with 'stop' → complete ──
        awaiting_data2 = json.loads((plan_dir / "awaiting_user.json").read_text())
        awaiting_data2["_resume_choice"] = "stop"
        (plan_dir / "awaiting_user.json").write_text(json.dumps(awaiting_data2))

        pipeline3 = Pipeline(
            stages={"write": write_stage, "decide": make_gate_stage()},
            entry="decide",
        )

        state3 = dict(result2["state"])
        state3.pop("_pipeline_paused", None)
        state3.pop("_pipeline_paused_stage", None)

        ctx3 = StepContext(
            plan_dir=plan_dir,
            state=state3,
            profile={},
            mode="test",
            inputs={},
        )
        ctx3 = inject_pipeline_context(ctx3, "loop-test")

        result3 = run_pipeline(pipeline3, ctx3, artifact_root=plan_dir)
        assert result3.get("halt_reason") is None
        assert result3["final_stage"] == "decide"


# ── Fresh artifact re-read on resume ───────────────────────────────────


class TestFreshArtifactReRead:
    """Resume re-reads artifact paths fresh from disk."""

    def test_artifact_reread_after_edit(self, tmp_path: Path):
        """Edit artifact on disk between pause and resume; verify fresh read
        when the next stage resolves inputs from disk."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        artifact_path = artifact_dir / "v1.md"
        artifact_path.write_text("Original version")

        # First run: pause
        step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["continue", "stop"],
            _pipeline_name="test",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)
        assert result.next == "halt"
        assert result.state_patch["_pipeline_paused"] is True

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "v1.md" in data["artifact_path"]

        # Edit the artifact on disk
        artifact_path.write_text("EDITED version after human review")

        # Create a new version (v2) — simulating updated stage output
        (artifact_dir / "v2.md").write_text("Fresh re-revised version v2")

        # Now the _latest_artifact function should pick up v2
        from megaplan._pipeline.steps.agent import _latest_artifact
        latest = _latest_artifact(artifact_dir)
        assert latest is not None
        assert latest.name == "v2.md"
        assert latest.read_text() == "Fresh re-revised version v2"

    def test_latest_artifact_rereads_disk(self, tmp_path: Path):
        """_latest_artifact reads from disk each call, not cached."""
        d = tmp_path / "stage"
        d.mkdir()
        (d / "v1.md").write_text("original")

        from megaplan._pipeline.steps.agent import _latest_artifact
        first = _latest_artifact(d)
        assert first is not None
        assert first.read_text() == "original"

        # Edit on disk
        (d / "v1.md").write_text("edited on disk")

        # Re-read
        second = _latest_artifact(d)
        assert second is not None
        assert second.read_text() == "edited on disk"

        # Add new version
        (d / "v2.md").write_text("new version")

        # Re-read — should pick up latest
        third = _latest_artifact(d)
        assert third is not None
        assert third.name == "v2.md"
        assert third.read_text() == "new version"


# ── State snapshot through pause/resume ────────────────────────────────


class TestStateSnapshotThroughPauseResume:
    """Pipeline identity persists in state across pause/resume."""

    def test_state_preserves_pipeline_identity(self, tmp_path: Path):
        """State with pipeline identity survives pause and is present after resume."""
        plan_dir = tmp_path / "plan"

        from dataclasses import dataclass

        @dataclass
        class ChainedAgentStep:
            name: str
            kind: str = "produce"
            prompt_key: str | None = None
            slot: str | None = None

            def run(self, ctx: StepContext) -> StepResult:
                output_dir = ctx.plan_dir / self.name
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "v1.md").write_text("done")
                return StepResult(
                    outputs={self.name: output_dir / "v1.md"},
                    next="continue",
                )

        write_stage = Stage(
            name="write",
            step=ChainedAgentStep(name="write"),
            edges=(Edge(label="continue", target="decide"),),
        )
        gate_step = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="write",
            _choices=["stop"],
            _pipeline_name="identity-preserve",
            _pipeline_version=3,
            _resume_choice=None,
        )
        gate_stage = Stage(
            name="decide",
            step=gate_step,
            edges=(Edge(label="stop", target="halt"),),
        )

        pipeline = Pipeline(
            stages={"write": write_stage, "decide": gate_stage},
            entry="write",
        )

        state = {
            "_pipeline_name": "identity-preserve",
            "_pipeline_version": 3,
            "_content_hash": "hash789",
        }
        ctx = StepContext(
            plan_dir=plan_dir,
            state=state,
            profile={},
            mode="test",
            inputs={},
        )
        ctx = inject_pipeline_context(ctx, "identity-preserve")

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["halt_reason"] == "awaiting_user"

        # State identity preserved
        state_data = json.loads((plan_dir / "state.json").read_text())
        assert state_data.get("_pipeline_name") == "identity-preserve"
        assert state_data.get("_pipeline_version") == 3
        assert state_data.get("_content_hash") == "hash789"

        # Now resume with stop
        gate_step2 = HumanGateStep(
            name="decide",
            kind="decide",
            _artifact_stage="write",
            _choices=["stop"],
            _pipeline_name="identity-preserve",
            _pipeline_version=3,
            _resume_choice="stop",
        )
        gate_stage2 = Stage(
            name="decide",
            step=gate_step2,
            edges=(Edge(label="stop", target="halt"),),
        )
        pipeline2 = Pipeline(
            stages={"write": write_stage, "decide": gate_stage2},
            entry="decide",
        )

        state2 = dict(result["state"])
        state2.pop("_pipeline_paused", None)
        state2.pop("_pipeline_paused_stage", None)

        ctx2 = StepContext(
            plan_dir=plan_dir,
            state=state2,
            profile={},
            mode="test",
            inputs={},
        )
        ctx2 = inject_pipeline_context(ctx2, "identity-preserve")

        result2 = run_pipeline(pipeline2, ctx2, artifact_root=plan_dir)
        assert result2.get("halt_reason") is None

        state_data2 = json.loads((plan_dir / "state.json").read_text())
        assert state_data2.get("_pipeline_name") == "identity-preserve"
        assert state_data2.get("_pipeline_version") == 3
