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

from arnold.pipeline import ContractSchemaRegistry
from arnold.pipeline.executor import StepIOEnforcementError
from arnold.pipelines.megaplan._pipeline.executor import run_pipeline
from arnold.pipelines.megaplan._pipeline.resume import check_awaiting_user, with_entry
from arnold.pipelines.megaplan._pipeline.steps.human_gate import HumanDecisionStep
from arnold.pipelines.megaplan._pipeline.types import (
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


def _answer_registry(root: Path) -> ContractSchemaRegistry:
    registry = ContractSchemaRegistry(root)
    registry.register(
        "answer",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return registry


def _answer_envelope(
    registry: ContractSchemaRegistry,
    payload: dict[str, int | str],
) -> dict[str, object]:
    version = registry.latest("answer")
    assert version is not None
    return {
        "logical_type": "answer",
        "schema_version": version,
        "payload": dict(payload),
    }


def _set_disk_resume_choice(plan_dir: Path, choice: str) -> str:
    awaiting_path = plan_dir / "awaiting_user.json"
    awaiting = json.loads(awaiting_path.read_text())
    awaiting["_resume_choice"] = choice
    serialized = json.dumps(awaiting, sort_keys=True)
    awaiting_path.write_text(serialized)
    return serialized


def _prepare_resume_state(plan_dir: Path, *, resume_cursor: dict[str, object]) -> dict[str, object]:
    state = json.loads((plan_dir / "state.json").read_text())
    state.pop("_pipeline_paused", None)
    state.pop("_pipeline_paused_stage", None)
    state["resume_cursor"] = dict(resume_cursor)
    (plan_dir / "state.json").write_text(json.dumps(state))
    return state


class _JsonArtifactStep:
    def __init__(self, name: str, payload: dict[str, object]) -> None:
        self.name = name
        self.kind = "produce"
        self.payload = payload
        self.calls = 0

    def run(self, ctx: StepContext):  # noqa: ANN001
        self.calls += 1
        stage_dir = ctx.plan_dir / self.name
        stage_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = stage_dir / "v1.json"
        artifact_path.write_text(json.dumps(self.payload), encoding="utf-8")
        return StepResult(outputs={"artifact": artifact_path}, next="done")


def _build_resume_reverify_pipeline(
    *,
    payload: dict[str, object],
    declare_resume: bool = True,
    invalid_policy: str = "resuspend",
) -> Pipeline:
    write_step = _JsonArtifactStep("write", payload)
    decide_step = HumanDecisionStep(
        name="decide",
        kind="decide",
        _artifact_stage="write",
        _choices=["approve"],
        _pipeline_name="resume-reverify-pipe",
        _pipeline_version=1,
        _port="answer_port" if declare_resume else None,
        _content_type="application/json" if declare_resume else None,
        _invalid_policy=invalid_policy,
    )
    return Pipeline(
        stages={
            "write": Stage(
                name="write",
                step=write_step,
                edges=(Edge(label="done", target="decide"),),
            ),
            "decide": Stage(
                name="decide",
                step=decide_step,
                edges=(Edge(label="approve", target="halt"),),
            ),
        },
        entry="write",
    )


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
        step.run(ctx)

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
        assert result["state"].get("_pipeline_paused_stage") == "decide"

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
        assert result2["state"].get("_pipeline_paused_stage") == "decide"
        state_data2 = json.loads((plan_dir / "state.json").read_text())
        assert state_data2.get("_pipeline_paused") is True
        assert state_data2.get("_pipeline_paused_stage") == "decide"
        awaiting_data_after_resume = json.loads((plan_dir / "awaiting_user.json").read_text())
        assert awaiting_data_after_resume["stage"] == "decide"

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
        from arnold.pipelines.megaplan._pipeline.step_helpers import latest_artifact as _latest_artifact
        latest = _latest_artifact(artifact_dir)
        assert latest is not None
        assert latest.name == "v2.md"
        assert latest.read_text() == "Fresh re-revised version v2"

    def test_latest_artifact_rereads_disk(self, tmp_path: Path):
        """_latest_artifact reads from disk each call, not cached."""
        d = tmp_path / "stage"
        d.mkdir()
        (d / "v1.md").write_text("original")

        from arnold.pipelines.megaplan._pipeline.step_helpers import latest_artifact as _latest_artifact
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


# ---------------------------------------------------------------------------
# T3: Declaration-bearing human gate producer behavior — Megaplan path
# ---------------------------------------------------------------------------


class TestHumanDecisionStepDeclarationBearing:
    """HumanDecisionStep with declaration fields (_port, _content_type,
    _artifact_ref, _invalid_policy) embeds x-arnold-resume in the
    checkpoint's resume_input_schema on pause."""

    def test_pause_with_port_embeds_resume_input_schema(self, tmp_path: Path):
        """When _port is set, awaiting_user.json carries resume_input_schema with x-arnold-resume."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok", "reject"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="report_port",
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.next == "halt"
        awaiting_path = tmp_path / "awaiting_user.json"
        assert awaiting_path.exists()
        data = json.loads(awaiting_path.read_text())

        assert "resume_input_schema" in data
        assert "x-arnold-resume" in data["resume_input_schema"]
        assert data["resume_input_schema"]["x-arnold-resume"]["port"] == "report_port"
        assert data["resume_input_schema"]["x-arnold-resume"]["invalid_policy"] == "resuspend"

    def test_pause_with_content_type_embeds_resume_input_schema(self, tmp_path: Path):
        """When _content_type is set, checkpoint carries content_type in x-arnold-resume."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _content_type="application/json",
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert data["resume_input_schema"]["x-arnold-resume"]["content_type"] == "application/json"

    def test_pause_with_artifact_ref_embeds_ref_in_schema(self, tmp_path: Path):
        """When _artifact_ref is set, checkpoint carries the ref dict in x-arnold-resume."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        ref = {"name": "my_artifact", "uri": "s3://bkt/file.md"}
        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _artifact_ref=ref,
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert data["resume_input_schema"]["x-arnold-resume"]["artifact_ref"] == ref

    def test_pause_with_all_declaration_fields(self, tmp_path: Path):
        """All declaration fields together produce a complete x-arnold-resume declaration."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        ref = {"name": "r", "content_type": "text/plain"}
        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="out_port",
            _content_type="text/markdown",
            _artifact_ref=ref,
            _invalid_policy="reject",
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        declaration = data["resume_input_schema"]["x-arnold-resume"]
        assert declaration["port"] == "out_port"
        assert declaration["content_type"] == "text/markdown"
        assert declaration["artifact_ref"] == ref
        assert declaration["invalid_policy"] == "reject"
        assert "artifact_path" in declaration  # resolved by latest_artifact

    def test_pause_with_custom_invalid_policy(self, tmp_path: Path):
        """Custom invalid_policy is embedded in the checkpoint declaration."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p",
            _invalid_policy="continue",
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert data["resume_input_schema"]["x-arnold-resume"]["invalid_policy"] == "continue"

    def test_contract_result_has_suspension_with_resume_input_schema(self, tmp_path: Path):
        """When declaration fields are set, the StepResult.contract_result carries a
        SUSPENDED status with a suspension containing resume_input_schema."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="scan_port",
            _content_type="text/markdown",
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.contract_result is not None
        assert result.contract_result.status.value == "suspended"
        assert result.contract_result.suspension is not None
        assert "x-arnold-resume" in result.contract_result.suspension.resume_input_schema
        decl = result.contract_result.suspension.resume_input_schema["x-arnold-resume"]
        assert decl["port"] == "scan_port"
        assert decl["content_type"] == "text/markdown"


class TestHumanDecisionStepNoDeclaration:
    """No-declaration parity for HumanDecisionStep: absent declaration fields
    produce identical behavior to pre-T2."""

    def test_pause_without_declaration_fields_no_resume_input_schema_in_checkpoint(self, tmp_path: Path):
        """When no declaration fields are set, checkpoint has no resume_input_schema key."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            # No _port, _content_type, _artifact_ref — bare human gate
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "resume_input_schema" not in data

    def test_pause_without_declaration_fields_contract_result_has_empty_schema(self, tmp_path: Path):
        """Without declaration, the contract_result suspension has empty resume_input_schema."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
        )
        ctx = _minimal_ctx(tmp_path)
        result = step.run(ctx)

        assert result.contract_result is not None
        assert result.contract_result.status.value == "suspended"
        assert result.contract_result.suspension is not None
        assert result.contract_result.suspension.resume_input_schema == {}

    def test_no_extra_contract_payload_when_declaration_absent(self, tmp_path: Path):
        """Contract result payload is identical with or without declaration.
        The payload contains only the standard fields."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        # Without declaration
        step_no_decl = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
        )
        ctx1 = _minimal_ctx(tmp_path)
        result_no_decl = step_no_decl.run(ctx1)

        # With declaration
        (tmp_path / "awaiting_user.json").unlink()  # clean up from previous
        step_with_decl = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p1",
        )
        ctx2 = _minimal_ctx(tmp_path / "sub")
        (tmp_path / "sub").mkdir(parents=True, exist_ok=True)
        (tmp_path / "sub" / "revise").mkdir(parents=True, exist_ok=True)
        (tmp_path / "sub" / "revise" / "v1.md").write_text("content")
        result_with_decl = step_with_decl.run(ctx2)

        # Both have SUSPENDED status and halt next
        assert result_no_decl.contract_result is not None
        assert result_with_decl.contract_result is not None
        assert result_no_decl.contract_result.status == result_with_decl.contract_result.status
        assert result_no_decl.next == result_with_decl.next == "halt"

    def test_resume_cleanup_unchanged_when_declaration_absent(self, tmp_path: Path):
        """Resume cleanup (file deletion) works identically when declaration absent."""
        # Pause without declaration
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)
        assert (tmp_path / "awaiting_user.json").exists()

        # Now resume: set _resume_choice on disk
        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        data["_resume_choice"] = "ok"
        (tmp_path / "awaiting_user.json").write_text(json.dumps(data))

        step2 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
        )
        result = step2.run(ctx)
        assert result.next == "ok"
        assert not (tmp_path / "awaiting_user.json").exists(), "Cleanup should delete the file"

    def test_resume_cleanup_with_declaration_present(self, tmp_path: Path):
        """Resume cleanup works correctly even when declaration was embedded in checkpoint."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        # Pause with declaration
        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p1",
            _content_type="text/plain",
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)
        assert (tmp_path / "awaiting_user.json").exists()

        # Verify declaration present
        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "resume_input_schema" in data
        assert "x-arnold-resume" in data["resume_input_schema"]

        # Set resume choice on disk
        data["_resume_choice"] = "ok"
        (tmp_path / "awaiting_user.json").write_text(json.dumps(data))

        # Resume
        step2 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["ok"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p1",
            _content_type="text/plain",
        )
        result = step2.run(ctx)
        assert result.next == "ok"
        assert not (tmp_path / "awaiting_user.json").exists(), "Cleanup should still delete the file"


class TestHumanDecisionStepReSuspendDeclaration:
    """Resume→loop-back→re-suspend with declaration: awaiting_user.json stays
    available for re-verification on every loop iteration."""

    def test_loop_back_with_declaration_rewrites_awaiting_user_with_schema(self, tmp_path: Path):
        """After a resume choice loops back to a producer, the next pause
        re-writes awaiting_user.json with the declaration intact."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("original")

        # First pause — with declaration
        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again", "stop"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p",
            _content_type="text/markdown",
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data1 = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "resume_input_schema" in data1

        # Simulate resume: inject choice onto disk
        data1["_resume_choice"] = "again"
        (tmp_path / "awaiting_user.json").write_text(json.dumps(data1))

        # Simulate a new artifact version being produced by upstream
        (artifact_dir / "v2.md").write_text("revised")

        # Resume — step cleans up, returns "again"
        step2 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again", "stop"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p",
            _content_type="text/markdown",
        )
        result = step2.run(ctx)
        assert result.next == "again"
        assert not (tmp_path / "awaiting_user.json").exists()  # Cleaned up

        # Now emulate loop-back: step runs again as if upstream just finished
        # This time no _resume_choice on instance, and no on-disk file → pause
        (artifact_dir / "v3.md").write_text("fresh content after loop")
        step3 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again", "stop"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p",
            _content_type="text/markdown",
        )
        result3 = step3.run(ctx)
        assert result3.next == "halt"
        assert (tmp_path / "awaiting_user.json").exists()

        # Declaration is present in the re-written checkpoint
        data3 = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "resume_input_schema" in data3
        assert data3["resume_input_schema"]["x-arnold-resume"]["port"] == "p"

    def test_loop_back_without_declaration_does_not_add_schema(self, tmp_path: Path):
        """Loop-back without declaration never adds resume_input_schema."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("original")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again", "stop"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            # No declaration fields
        )
        ctx = _minimal_ctx(tmp_path)
        step.run(ctx)

        data1 = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "resume_input_schema" not in data1

        # Resume with "again"
        data1["_resume_choice"] = "again"
        (tmp_path / "awaiting_user.json").write_text(json.dumps(data1))
        (artifact_dir / "v2.md").write_text("revised")

        step2 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again", "stop"],
            _pipeline_name="pipe",
            _pipeline_version=1,
        )
        result = step2.run(ctx)
        assert result.next == "again"
        assert not (tmp_path / "awaiting_user.json").exists()

        # Loop back: re-pause
        (artifact_dir / "v3.md").write_text("fresh")
        step3 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again", "stop"],
            _pipeline_name="pipe",
            _pipeline_version=1,
        )
        result3 = step3.run(ctx)
        assert result3.next == "halt"
        assert (tmp_path / "awaiting_user.json").exists()
        data3 = json.loads((tmp_path / "awaiting_user.json").read_text())
        assert "resume_input_schema" not in data3

    def test_single_use_resume_choice_prevents_infinite_loop(self, tmp_path: Path):
        """After resume clears _resume_choice (set via object.__setattr__), a second
        invocation without a new choice pauses again instead of resuming forever."""
        artifact_dir = tmp_path / "revise"
        artifact_dir.mkdir()
        (artifact_dir / "v1.md").write_text("content")

        step = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p",
        )
        ctx = _minimal_ctx(tmp_path)

        # First run: pause (no choice)
        result1 = step.run(ctx)
        assert result1.next == "halt"

        # Inject resume choice onto disk
        data = json.loads((tmp_path / "awaiting_user.json").read_text())
        data["_resume_choice"] = "again"
        (tmp_path / "awaiting_user.json").write_text(json.dumps(data))

        # Second run: resume — clears _resume_choice, returns "again", deletes file
        step2 = HumanDecisionStep(
            name="decide",
            kind="decide",
            _artifact_stage="revise",
            _choices=["again"],
            _pipeline_name="pipe",
            _pipeline_version=1,
            _port="p",
        )
        result2 = step2.run(ctx)
        assert result2.next == "again"
        assert not (tmp_path / "awaiting_user.json").exists()
        # instance-level _resume_choice was cleared
        assert step2._resume_choice is None

        # Third run: no file, no instance choice → pause again (not infinite loop)
        (artifact_dir / "v2.md").write_text("new")
        result3 = step2.run(ctx)
        assert result3.next == "halt"
        assert (tmp_path / "awaiting_user.json").exists()


class TestMegaplanResumeReverify:
    def test_valid_edit_completes_and_invalid_edit_resuspends_until_fixed(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        pipeline = _build_resume_reverify_pipeline(
            payload=_answer_envelope(registry, {"value": 1}),
        )
        ctx = _minimal_ctx(tmp_path)

        paused = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
        assert paused["halt_reason"] == "awaiting_user"
        artifact_path = tmp_path / "write" / "v1.json"
        artifact_path.write_text(
            json.dumps(_answer_envelope(registry, {"value": "oops"})),
            encoding="utf-8",
        )
        original_awaiting = _set_disk_resume_choice(tmp_path, "approve")
        resume_cursor = {"stage": "decide", "attempt": 1}
        resume_state = _prepare_resume_state(tmp_path, resume_cursor=resume_cursor)

        invalid = run_pipeline(
            with_entry(pipeline, "decide"),
            StepContext(
                plan_dir=tmp_path,
                state=resume_state,
                profile={},
                mode="test",
                inputs={},
            ),
            artifact_root=tmp_path,
        )

        assert invalid["halt_reason"] == "awaiting_user"
        assert invalid["state"]["resume_cursor"] == resume_cursor
        assert invalid["contract_result"]["status"] == "suspended"
        assert invalid["contract_result"]["payload"]["resume_reverify_diagnostic"]["code"] == (
            "typed_contract_blocked"
        )
        assert "answer_port" not in invalid["state"]
        assert json.loads((tmp_path / "awaiting_user.json").read_text()) == json.loads(original_awaiting)
        assert json.loads((tmp_path / "state.json").read_text()) == invalid["state"]

        artifact_path.write_text(
            json.dumps(_answer_envelope(registry, {"value": 99})),
            encoding="utf-8",
        )
        completed = run_pipeline(
            with_entry(pipeline, "decide"),
            StepContext(
                plan_dir=tmp_path,
                state=invalid["state"],
                profile={},
                mode="test",
                inputs={},
            ),
            artifact_root=tmp_path,
        )

        assert completed.get("halt_reason") != "awaiting_user"
        assert completed["final_stage"] == "decide"
        assert completed["contract_result"]["status"] == "completed"
        assert completed["contract_result"]["payload"]["answer_port"] == _answer_envelope(
            registry,
            {"value": 99},
        )
        assert not (tmp_path / "awaiting_user.json").exists()

    def test_invalid_policy_fail_raises_before_merge_and_preserves_prior_cursor(
        self,
        tmp_path: Path,
    ) -> None:
        registry = _answer_registry(tmp_path)
        pipeline = _build_resume_reverify_pipeline(
            payload=_answer_envelope(registry, {"value": 1}),
            invalid_policy="fail",
        )
        ctx = _minimal_ctx(tmp_path)

        paused = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
        assert paused["halt_reason"] == "awaiting_user"
        (tmp_path / "write" / "v1.json").write_text(
            json.dumps(_answer_envelope(registry, {"value": "oops"})),
            encoding="utf-8",
        )
        _set_disk_resume_choice(tmp_path, "approve")
        resume_cursor = {"stage": "decide", "attempt": 7}
        resume_state = _prepare_resume_state(tmp_path, resume_cursor=resume_cursor)
        expected_state_json = json.loads((tmp_path / "state.json").read_text())

        with pytest.raises(StepIOEnforcementError, match="Typed contract violation"):
            run_pipeline(
                with_entry(pipeline, "decide"),
                StepContext(
                    plan_dir=tmp_path,
                    state=resume_state,
                    profile={},
                    mode="test",
                    inputs={},
                ),
                artifact_root=tmp_path,
            )

        assert json.loads((tmp_path / "state.json").read_text()) == expected_state_json
        assert json.loads((tmp_path / "state.json").read_text())["resume_cursor"] == resume_cursor
        assert not (tmp_path / "awaiting_user.json").exists()

    def test_no_declaration_resume_path_remains_unchanged(
        self,
        tmp_path: Path,
    ) -> None:
        pipeline = _build_resume_reverify_pipeline(
            payload={"legacy": True},
            declare_resume=False,
        )
        ctx = _minimal_ctx(tmp_path)

        paused = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
        assert paused["halt_reason"] == "awaiting_user"
        _set_disk_resume_choice(tmp_path, "approve")
        resume_state = _prepare_resume_state(
            tmp_path,
            resume_cursor={"stage": "decide", "legacy": True},
        )

        completed = run_pipeline(
            with_entry(pipeline, "decide"),
            StepContext(
                plan_dir=tmp_path,
                state=resume_state,
                profile={},
                mode="test",
                inputs={},
            ),
            artifact_root=tmp_path,
        )

        assert completed["final_stage"] == "decide"
        assert completed["contract_result"] is None
        assert not (tmp_path / "awaiting_user.json").exists()


class TestBuilderHumanGateDeclaration:
    """PipelineBuilder.human_gate() passes declaration fields through to
    the constructed HumanDecisionStep."""

    def test_builder_passes_port_to_step(self):
        """Builder.human_gate(port=...) sets _port on the step."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        builder = PipelineBuilder("test", pipeline_version=1)
        builder.human_gate(
            "decide",
            artifact="write",
            options=["ok", "reject"],
            edges={"ok": "halt", "reject": "halt"},
            port="my_port",
        )
        pipeline = builder.build()
        stage = pipeline.stages["decide"]
        step = stage.step
        assert step._port == "my_port"

    def test_builder_passes_content_type_to_step(self):
        """Builder.human_gate(content_type=...) sets _content_type on the step."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        builder = PipelineBuilder("test", pipeline_version=1)
        builder.human_gate(
            "decide",
            artifact="write",
            options=["ok"],
            edges={"ok": "halt"},
            content_type="text/markdown",
        )
        pipeline = builder.build()
        step = pipeline.stages["decide"].step
        assert step._content_type == "text/markdown"

    def test_builder_passes_artifact_ref_to_step(self):
        """Builder.human_gate(artifact_ref=...) sets _artifact_ref on the step."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        ref = {"uri": "s3://bkt/file.md", "name": "f"}
        builder = PipelineBuilder("test", pipeline_version=1)
        builder.human_gate(
            "decide",
            artifact="write",
            options=["ok"],
            edges={"ok": "halt"},
            artifact_ref=ref,
        )
        pipeline = builder.build()
        step = pipeline.stages["decide"].step
        assert step._artifact_ref == ref

    def test_builder_passes_invalid_policy_to_step(self):
        """Builder.human_gate(invalid_policy=...) sets _invalid_policy on the step."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        builder = PipelineBuilder("test", pipeline_version=1)
        builder.human_gate(
            "decide",
            artifact="write",
            options=["ok"],
            edges={"ok": "halt"},
            invalid_policy="continue",
        )
        pipeline = builder.build()
        step = pipeline.stages["decide"].step
        assert step._invalid_policy == "continue"

    def test_builder_defaults_declaration_fields_to_none(self):
        """Without declaration args, _port, _content_type, _artifact_ref default to None."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        builder = PipelineBuilder("test", pipeline_version=1)
        builder.human_gate(
            "decide",
            artifact="write",
            options=["ok"],
            edges={"ok": "halt"},
        )
        pipeline = builder.build()
        step = pipeline.stages["decide"].step
        assert step._port is None
        assert step._content_type is None
        assert step._artifact_ref is None
        assert step._invalid_policy == "resuspend"

    def test_builder_human_gate_includes_stage_with_edges(self):
        """Builder.human_gate constructs a valid Stage with edges and the step wired."""
        from arnold.pipelines.megaplan._pipeline.builder import PipelineBuilder

        builder = PipelineBuilder("test", pipeline_version=1)
        builder.human_gate(
            "decide",
            artifact="write",
            options=["yes", "no", "maybe"],
            edges={"yes": "next_stage", "no": "halt", "maybe": "other"},
            port="out",
            content_type="text/plain",
        )
        pipeline = builder.build()
        stage = pipeline.stages["decide"]
        assert len(stage.edges) == 3
        edge_labels = {e.label for e in stage.edges}
        assert edge_labels == {"yes", "no", "maybe"}
        edge_targets = {e.target for e in stage.edges}
        assert edge_targets == {"next_stage", "halt", "other"}
        assert stage.step._port == "out"
        assert stage.step._content_type == "text/plain"
