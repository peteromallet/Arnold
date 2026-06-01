"""Unit tests for HumanDecisionStep pause/resume semantics.

Verifies pause file shape, resume with choice, fresh artifact
re-reads after disk edits, and cleanup after resume.

Pipelines under test are constructed via the canonical
:meth:`Pipeline.builder` API (T16): the YAML compiler / PipelineSpec
path is gone, ``inject_pipeline_context`` is not needed because the
builder threads ``_pipeline_name`` onto each step directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.resume import check_awaiting_user, with_entry
from megaplan._pipeline.steps.human_gate import HumanDecisionStep
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)


def _minimal_ctx(plan_dir: Path, inputs: dict | None = None) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={},
        profile={},
        mode="test",
        inputs=inputs or {},
    )


def _build_pause_resume_pipeline(
    pipeline_name: str,
    *,
    worker,
    pipeline_dir: Path,
    on_continue_target: str = "write",
    options: tuple[str, ...] = ("again", "stop"),
) -> Pipeline:
    """Build the canonical ``write → decide`` pause/resume pipeline via
    :meth:`Pipeline.builder`.

    The ``write`` stage is an :class:`AgentStep` whose worker callback
    supplies the per-iteration content; the ``decide`` stage is a
    :class:`HumanDecisionStep` whose ``options`` map to either a loop-back
    target or ``"halt"``."""
    (pipeline_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (pipeline_dir / "prompts" / "write.md").write_text("write prompt")

    edges_map = {opt: (on_continue_target if opt == options[0] else "halt") for opt in options}

    builder = (
        Pipeline.builder(
            pipeline_name,
            pipeline_dir=pipeline_dir,
            worker=worker,
            pipeline_version=1,
        )
        .agent("write", prompt="prompts/write.md", inputs=[])
        .human_gate(
            "decide",
            artifact="write",
            options=list(options),
            edges=edges_map,
        )
    )
    return builder.build()


def _make_iteration_worker():
    """Return a worker callable that emits ``"iteration N"`` for the
    Nth invocation, plus a counter visible to the caller."""
    state = {"calls": 0}

    def worker(prompt, step_name, pipeline_name, inputs, mode):  # noqa: ANN001
        state["calls"] += 1
        return f"iteration {state['calls']}"

    return worker, state


# ── HumanDecisionStep direct tests ─────────────────────────────────────


class TestHumanDecisionStep:
    """HumanDecisionStep: pause file shape, resume choice, cleanup."""

    def test_pause_writes_awaiting_user_json(self, tmp_path: Path):
        """On first run (no resume choice), writes correct awaiting_user.json."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("Revised draft content")

        step = HumanDecisionStep(
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
        step = HumanDecisionStep(
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
        step = HumanDecisionStep(
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

        step = HumanDecisionStep(
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

        step = HumanDecisionStep(
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
        step = HumanDecisionStep(
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

        step = HumanDecisionStep(
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
    """Human gate within a Pipeline.builder()-constructed pipeline executed
    via run_pipeline.

    Asserts the full pause/resume protocol end-to-end:

    * ``awaiting_user.json`` written on pause
    * ``_pipeline_paused: True`` state patch lands in ``state.json``
    * :func:`with_entry` re-entry on resume
    * input-swap-on-continue semantics (disk edits visible after resume)
    """

    def test_human_gate_pauses_pipeline(self, tmp_path: Path):
        """When run_pipeline hits a human_gate stage in pause mode,
        it returns halt_reason='awaiting_user'."""
        plan_dir = tmp_path / "plan"
        pipeline_dir = tmp_path / "pipeline"

        worker, _ = _make_iteration_worker()
        pipeline = _build_pause_resume_pipeline(
            "pause-test",
            worker=worker,
            pipeline_dir=pipeline_dir,
        )
        # Builder-locked invariants: human_gate stage owns its edges
        # and the agent auto-links via the natural "done" label.
        decide_stage = pipeline.stages["decide"]
        assert isinstance(decide_stage, Stage)
        assert isinstance(decide_stage.step, HumanDecisionStep)
        write_stage = pipeline.stages["write"]
        assert any(
            e.label == "done" and e.target == "decide"
            for e in write_stage.edges
        )

        ctx = _minimal_ctx(plan_dir)
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        assert result["halt_reason"] == "awaiting_user"
        assert result["final_stage"] == "decide"
        assert (plan_dir / "awaiting_user.json").exists()

        # State patch lands in state.json on pause.
        state_data = json.loads((plan_dir / "state.json").read_text())
        assert state_data.get("_pipeline_paused") is True
        assert state_data.get("_pipeline_paused_stage") == "decide"

        # awaiting_user.json shape carries the canonical fields.
        data = json.loads((plan_dir / "awaiting_user.json").read_text())
        assert data["pipeline"] == "pause-test"
        assert data["stage"] == "decide"
        assert data["choices"] == ["again", "stop"]

    def test_resume_continue_loops_back(self, tmp_path: Path):
        """Resume with 'again' uses :func:`with_entry` to re-enter at the
        decide stage, then loops back to write, producing a new artifact
        version. Verifies input-swap-on-continue semantics: the on-disk
        v1 edit is visible after resume."""
        plan_dir = tmp_path / "plan"
        pipeline_dir = tmp_path / "pipeline"

        worker, worker_state = _make_iteration_worker()
        pipeline = _build_pause_resume_pipeline(
            "loop-test",
            worker=worker,
            pipeline_dir=pipeline_dir,
        )

        # ── First run: write → pause at decide ──
        ctx = _minimal_ctx(plan_dir)
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["halt_reason"] == "awaiting_user"
        assert (plan_dir / "write" / "v1.md").read_text() == "iteration 1"
        assert worker_state["calls"] == 1

        # ── Edit artifact on disk (input-swap) ──
        (plan_dir / "write" / "v1.md").write_text("USER EDITED v1")

        # ── Resume with 'again' via disk ──
        awaiting_data = json.loads((plan_dir / "awaiting_user.json").read_text())
        awaiting_data["_resume_choice"] = "again"
        (plan_dir / "awaiting_user.json").write_text(json.dumps(awaiting_data))

        # Use with_entry() to re-enter at the decide stage on resume.
        resumed = with_entry(pipeline, "decide")
        assert resumed.entry == "decide"
        # with_entry preserves the rest of the graph identity.
        assert set(resumed.stages) == set(pipeline.stages)

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
        result2 = run_pipeline(resumed, ctx2, artifact_root=plan_dir)

        # The 'again' resume routed decide→write; the write worker fired
        # a second time and produced v2.
        assert (plan_dir / "write" / "v2.md").exists()
        assert (plan_dir / "write" / "v2.md").read_text() == "iteration 2"
        assert worker_state["calls"] == 2
        # Input-swap visible: the edited v1 still holds the user's edit
        # (the executor did not clobber it).
        assert (plan_dir / "write" / "v1.md").read_text() == "USER EDITED v1"
        # Should pause again at decide (decide's _resume_choice is single-use).
        assert result2["halt_reason"] == "awaiting_user"

        # ── Resume with 'stop' via disk → complete ──
        awaiting_data2 = json.loads((plan_dir / "awaiting_user.json").read_text())
        awaiting_data2["_resume_choice"] = "stop"
        (plan_dir / "awaiting_user.json").write_text(json.dumps(awaiting_data2))

        resumed2 = with_entry(pipeline, "decide")
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
        result3 = run_pipeline(resumed2, ctx3, artifact_root=plan_dir)
        assert result3.get("halt_reason") is None
        assert result3["final_stage"] == "decide"
        # 'stop' routed to halt without firing the worker again.
        assert worker_state["calls"] == 2


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
        step = HumanDecisionStep(
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
        from megaplan._pipeline.step_helpers import latest_artifact as _latest_artifact
        latest = _latest_artifact(artifact_dir)
        assert latest is not None
        assert latest.name == "v2.md"
        assert latest.read_text() == "Fresh re-revised version v2"

    def test_latest_artifact_rereads_disk(self, tmp_path: Path):
        """_latest_artifact reads from disk each call, not cached."""
        d = tmp_path / "stage"
        d.mkdir()
        (d / "v1.md").write_text("original")

        from megaplan._pipeline.step_helpers import latest_artifact as _latest_artifact
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
        """State with pipeline identity survives pause and is present after resume.
        Verifies the ``_pipeline_paused: True`` state patch on pause AND the
        :func:`with_entry` re-entry path on resume."""
        plan_dir = tmp_path / "plan"
        pipeline_dir = tmp_path / "pipeline"

        worker, _ = _make_iteration_worker()
        pipeline = _build_pause_resume_pipeline(
            "identity-preserve",
            worker=worker,
            pipeline_dir=pipeline_dir,
            options=("stop",),
            on_continue_target="halt",
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

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["halt_reason"] == "awaiting_user"

        # State identity preserved AND pause patch present.
        state_data = json.loads((plan_dir / "state.json").read_text())
        assert state_data.get("_pipeline_name") == "identity-preserve"
        assert state_data.get("_pipeline_version") == 3
        assert state_data.get("_content_hash") == "hash789"
        assert state_data.get("_pipeline_paused") is True
        assert state_data.get("_pipeline_paused_stage") == "decide"

        # Resume via disk-based _resume_choice and with_entry() re-entry.
        awaiting_data = json.loads((plan_dir / "awaiting_user.json").read_text())
        awaiting_data["_resume_choice"] = "stop"
        (plan_dir / "awaiting_user.json").write_text(json.dumps(awaiting_data))

        resumed = with_entry(pipeline, "decide")
        assert resumed.entry == "decide"

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

        result2 = run_pipeline(resumed, ctx2, artifact_root=plan_dir)
        assert result2.get("halt_reason") is None

        state_data2 = json.loads((plan_dir / "state.json").read_text())
        assert state_data2.get("_pipeline_name") == "identity-preserve"
        assert state_data2.get("_pipeline_version") == 3
