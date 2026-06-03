"""End-to-end tests for the Python ``writing-panel-strict`` pipeline.

Drives the pipeline built by
:func:`megaplan.pipelines.writing_panel_strict.build_pipeline` directly
through :func:`megaplan._pipeline.executor.run_pipeline`. Mocks the
model layer by injecting a fake worker onto every
:class:`AgentStep` / :class:`PanelReviewerStep` after construction —
the brief calls this the "InProcessHandlerStep substitute" idea, the
Python equivalent of mock workers replacing real model calls.

Verifies:

* (a) Panel→synth fan-in: synth resolves all three reviewer artifacts
  via the builder-plumbed ``_panel_reviewer_order`` so the
  ``panel_review.*`` reference expands to the three reviewer paths.
* (b) End-to-end topology matches the legacy YAML: three parallel
  reviewers → synth → revise → human_decide pauses with
  ``awaiting_user.json``.
* (c) Resume with ``continue`` re-enters the ``panel_review``
  ParallelStage (loop edge) and pauses again; resume with ``stop``
  reaches the executor ``halt`` terminator.
"""

from __future__ import annotations

import json
from pathlib import Path

# M3a partial migration: the writing-panel-strict pipeline uses the megaplan
# builder (.panel()/.agent()/.human_gate()), so its step instances and stage
# types are megaplan bridge types.  HumanDecisionStep is explicitly a megaplan
# bridge (human-gate pause/resume), not an Arnold neutral primitive.
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.resume import with_entry
from megaplan._pipeline.steps.agent import AgentStep
from megaplan._pipeline.steps.human_gate import HumanDecisionStep
from megaplan._pipeline.steps.panel import PanelReviewerStep
from megaplan._pipeline.types import ParallelStage, Pipeline, Stage, StepContext
from megaplan.pipelines.writing_panel_strict import build_pipeline


# ── Helpers ────────────────────────────────────────────────────────────


def _mock_worker(response: str = "mock output") -> object:
    """Return a worker callable that ignores its inputs and returns a fixed string."""

    def worker(**kwargs: object) -> str:
        return response

    return worker


def _patch_workers(pipeline: Pipeline, worker: object) -> None:
    """Inject *worker* onto every AgentStep / PanelReviewerStep in *pipeline*.

    AgentStep / PanelReviewerStep are non-frozen dataclasses (the
    private ``_worker`` field is plain attribute assignment), so the
    pipeline returned by :func:`build_pipeline` can have its model
    calls replaced wholesale after construction.
    """

    for stage in pipeline.stages.values():
        if isinstance(stage, ParallelStage):
            for step in stage.steps:
                if isinstance(step, PanelReviewerStep):
                    step._worker = worker  # type: ignore[assignment]
        elif isinstance(stage, Stage):
            step = stage.step
            if isinstance(step, AgentStep):
                step._worker = worker  # type: ignore[assignment]


def _set_resume_choice(pipeline: Pipeline, stage_name: str, choice: str) -> None:
    """Set ``_resume_choice`` on the named human-gate stage's Step."""
    stage = pipeline.stages[stage_name]
    assert isinstance(stage, Stage)
    step = stage.step
    assert isinstance(step, HumanDecisionStep)
    object.__setattr__(step, "_resume_choice", choice)


def _setup_draft(plan_dir: Path, content: str = "# Test Draft\n\nA prose sample.\n") -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    draft_path = plan_dir / "draft.md"
    draft_path.write_text(content)
    return draft_path


def _fresh_ctx(plan_dir: Path, draft_path: Path) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={"_pipeline_name": "writing-panel-strict", "_pipeline_version": 1},
        profile={},
        mode="polish",
        inputs={"draft": draft_path},
    )


# ── End-to-end tests ──────────────────────────────────────────────────


class TestWritingPanelStrictTopology:
    """Locks the YAML→Python topology: three reviewers → synth → revise → human_decide."""

    def test_stage_graph_matches_yaml_topology(self) -> None:
        pipeline = build_pipeline()

        assert pipeline.entry == "panel_review"
        assert list(pipeline.stages) == [
            "panel_review",
            "synth",
            "revise",
            "human_decide",
        ]

        panel = pipeline.stages["panel_review"]
        assert isinstance(panel, ParallelStage)
        reviewer_ids = [s._reviewer_id for s in panel.steps if isinstance(s, PanelReviewerStep)]
        assert reviewer_ids == ["pessimist", "optimist", "structuralist"]

        # synth's AgentStep carries the builder-plumbed reviewer order so
        # `panel_review.*` expands in reviewer-list order (this is the
        # contract test_builder.py locks at the unit level — re-asserted
        # here at the e2e layer so a regression on the writing-panel
        # pipeline surfaces directly).
        synth_stage = pipeline.stages["synth"]
        assert isinstance(synth_stage, Stage)
        assert isinstance(synth_stage.step, AgentStep)
        assert synth_stage.step._panel_reviewer_order == {
            "panel_review": ["pessimist", "optimist", "structuralist"],
        }
        assert synth_stage.step._input_refs == ["panel_review.*"]

        # human_decide's edges: continue loops back to the ParallelStage,
        # stop hits the executor's "halt" terminator.
        human = pipeline.stages["human_decide"]
        assert isinstance(human, Stage)
        edge_map = {e.label: e.target for e in human.edges}
        assert edge_map == {"continue": "panel_review", "stop": "halt"}


class TestWritingPanelStrictE2E:
    """Drive the pipeline end-to-end with a mocked worker."""

    def test_full_run_pauses_at_human_gate(self, tmp_path: Path) -> None:
        pipeline = build_pipeline()
        _patch_workers(pipeline, _mock_worker("mocked"))

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        assert result["halt_reason"] == "awaiting_user"
        assert result["final_stage"] == "human_decide"

        # (a) Fan-out: each reviewer wrote v1.md under its own subdir.
        assert (plan_dir / "panel_review" / "pessimist" / "v1.md").exists()
        assert (plan_dir / "panel_review" / "optimist" / "v1.md").exists()
        assert (plan_dir / "panel_review" / "structuralist" / "v1.md").exists()

        # (a) Fan-in: synth's rendered prompt embedded each reviewer's
        # path via the `panel_review.*` expansion. The rendered prompt
        # text is interpolated into the artifact written by synth — but
        # the cleanest proof is the synth artifact itself exists and the
        # builder's reviewer-order plumbing made synth's
        # _panel_reviewer_order non-empty (covered above).
        assert (plan_dir / "synth" / "v1.md").exists()
        assert (plan_dir / "revise" / "v1.md").exists()

        # awaiting_user.json structure matches the YAML pipeline's contract.
        awaiting = json.loads((plan_dir / "awaiting_user.json").read_text())
        assert awaiting["pipeline"] == "writing-panel-strict"
        assert awaiting["stage"] == "human_decide"
        assert awaiting["artifact_stage"] == "revise"
        assert awaiting["choices"] == ["continue", "stop"]
        assert "revise" in awaiting["artifact_path"]
        assert "v1.md" in awaiting["artifact_path"]

    def test_resume_continue_re_enters_panel_review_loop(self, tmp_path: Path) -> None:
        """The continue edge re-enters the ParallelStage and pauses again."""
        pipeline = build_pipeline()
        _patch_workers(pipeline, _mock_worker("pass-1"))

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        # First pass: pause at human_decide.
        result1 = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result1["halt_reason"] == "awaiting_user"
        assert result1["state"].get("_pipeline_paused_stage") == "human_decide"
        assert (plan_dir / "revise" / "v1.md").exists()
        state_data1 = json.loads((plan_dir / "state.json").read_text())
        assert state_data1.get("_pipeline_paused_stage") == "human_decide"
        awaiting1 = json.loads((plan_dir / "awaiting_user.json").read_text())
        assert awaiting1["stage"] == "human_decide"

        # Resume with "continue" — the human_gate emits next="continue",
        # which dispatches the Edge('continue','panel_review') loop edge
        # back into the ParallelStage.
        _patch_workers(pipeline, _mock_worker("pass-2"))
        _set_resume_choice(pipeline, "human_decide", "continue")

        # Clear the pause flags that the first pause stamped onto state,
        # mirroring what the resume-CLI path does on the next invocation.
        state_json = json.loads((plan_dir / "state.json").read_text())
        state_json.pop("_pipeline_paused", None)
        state_json.pop("_pipeline_paused_stage", None)

        pipeline_resume = with_entry(pipeline, "human_decide")
        ctx_resume = StepContext(
            plan_dir=plan_dir,
            state=state_json,
            profile={},
            mode="polish",
            inputs={"draft": draft_path},
        )

        result2 = run_pipeline(pipeline_resume, ctx_resume, artifact_root=plan_dir)

        # Loop fired: a second iteration of panel/synth/revise ran and
        # then human_decide paused again.
        assert result2["halt_reason"] == "awaiting_user"
        assert result2["final_stage"] == "human_decide"
        assert result2["state"].get("_pipeline_paused_stage") == "human_decide"
        assert (plan_dir / "panel_review" / "pessimist" / "v2.md").exists()
        assert (plan_dir / "panel_review" / "optimist" / "v2.md").exists()
        assert (plan_dir / "panel_review" / "structuralist" / "v2.md").exists()
        assert (plan_dir / "synth" / "v2.md").exists()
        assert (plan_dir / "revise" / "v2.md").exists()
        state_data2 = json.loads((plan_dir / "state.json").read_text())
        assert state_data2.get("_pipeline_paused_stage") == "human_decide"
        awaiting2 = json.loads((plan_dir / "awaiting_user.json").read_text())
        assert awaiting2["stage"] == "human_decide"

    def test_resume_stop_reaches_halt_terminator(self, tmp_path: Path) -> None:
        """The stop edge reaches the executor's "halt" terminator."""
        pipeline = build_pipeline()
        _patch_workers(pipeline, _mock_worker("only-pass"))

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        # First pass: pause at human_decide.
        result1 = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result1["halt_reason"] == "awaiting_user"
        assert result1["state"].get("_pipeline_paused_stage") == "human_decide"

        # Resume with "stop" — dispatches Edge('stop','halt') and the
        # executor returns without setting halt_reason="awaiting_user".
        _set_resume_choice(pipeline, "human_decide", "stop")
        state_json = json.loads((plan_dir / "state.json").read_text())
        state_json.pop("_pipeline_paused", None)
        state_json.pop("_pipeline_paused_stage", None)

        pipeline_resume = with_entry(pipeline, "human_decide")
        ctx_resume = StepContext(
            plan_dir=plan_dir,
            state=state_json,
            profile={},
            mode="polish",
            inputs={"draft": draft_path},
        )

        result2 = run_pipeline(pipeline_resume, ctx_resume, artifact_root=plan_dir)

        assert result2.get("halt_reason") != "awaiting_user"
        assert result2["final_stage"] == "human_decide"
        # awaiting_user.json was cleaned up by the human_gate resume path.
        assert not (plan_dir / "awaiting_user.json").exists()
