"""End-to-end tests for the Python ``epic-blitz`` pipeline.

Drives the pipeline built by
:func:`megaplan.pipelines.epic_blitz.build_pipeline` directly
through :func:`megaplan._pipeline.executor.run_pipeline`. Mocks the
model layer by injecting a fake worker onto every
:class:`AgentStep` / :class:`PanelReviewerStep` after construction.

Verifies:

* (a) 15 reviewer artifacts (5×3 panels) at correct paths.
* (b) 3 revision artifacts at correct paths.
* (c) run_pipeline terminates normally at readiness with no awaiting_user.
* (d) Fake worker records prove panel outputs feed corresponding revision steps.
"""

from __future__ import annotations

from pathlib import Path

from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.steps.agent import AgentStep
from megaplan._pipeline.steps.panel import PanelReviewerStep
from megaplan._pipeline.types import ParallelStage, Pipeline, Stage, StepContext
from megaplan.pipelines.epic_blitz import build_pipeline


# ── Helpers ────────────────────────────────────────────────────────────

def _recording_worker():
    """Return a worker callable that records (step_name, inputs) per invocation.

    Each call appends a dict to the ``calls`` list on the closure so
    we can assert dependency flow after the pipeline finishes.
    """
    calls: list[dict] = []

    def worker(**kwargs: object) -> str:
        calls.append({
            "step_name": kwargs.get("step_name", ""),
            "inputs": {k: str(v) for k, v in kwargs.get("inputs", {}).items()},
        })
        return "mocked output"

    worker.calls = calls  # type: ignore[attr-defined]
    return worker


def _patch_workers(pipeline: Pipeline, worker: object) -> None:
    """Inject *worker* onto every AgentStep / PanelReviewerStep in *pipeline*.

    Same pattern as test_writing_panel_e2e.py:_patch_workers.
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


def _setup_draft(plan_dir: Path, content: str = "# Epic Draft\n\nAn epic to test the blitz pipeline.\n") -> Path:
    plan_dir.mkdir(parents=True, exist_ok=True)
    draft_path = plan_dir / "draft.md"
    draft_path.write_text(content)
    return draft_path


def _fresh_ctx(plan_dir: Path, draft_path: Path) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={"_pipeline_name": "epic-blitz", "_pipeline_version": 1},
        profile={},
        mode="code",
        inputs={"draft": draft_path},
    )


# ── End-to-end tests ──────────────────────────────────────────────────


class TestEpicBlitzE2E:
    """Drive the epic-blitz pipeline end-to-end with a recording mocked worker."""

    def test_full_run_terminates_normally_at_readiness(self, tmp_path: Path) -> None:
        """Pipeline runs all 6 stages and terminates cleanly at readiness.

        No HumanDecisionStep exists, so run_pipeline must NOT produce
        ``halt_reason='awaiting_user'``.
        """
        pipeline = build_pipeline()
        worker = _recording_worker()
        _patch_workers(pipeline, worker)

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        # Normal termination — no human gate pause
        assert result["final_stage"] == "readiness"
        assert "halt_reason" not in result, (
            f"unexpected halt_reason={result.get('halt_reason')!r}"
        )

        # No awaiting_user.json
        assert not (plan_dir / "awaiting_user.json").exists(), (
            "epic-blitz has no human gates; awaiting_user.json must not exist"
        )

    def test_15_reviewer_artifacts_exist_at_correct_paths(self, tmp_path: Path) -> None:
        """All 5×3=15 reviewer v1.md files are written under their panel/reviewer subdirs."""
        pipeline = build_pipeline()
        worker = _recording_worker()
        _patch_workers(pipeline, worker)

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        # High panel (5 reviewers)
        high_reviewers = [
            "existing_system_reuse", "conceptual_fit", "missing_abstraction",
            "epic_decomposition", "strategic_risk",
        ]
        for rid in high_reviewers:
            path = plan_dir / "high_panel" / rid / "v1.md"
            assert path.exists(), f"missing high_panel/{rid}/v1.md"

        # Mid panel (5 reviewers)
        mid_reviewers = [
            "codebase_convention_fit", "data_artifact_model", "orchestration_semantics",
            "agent_model_assignment", "blast_radius",
        ]
        for rid in mid_reviewers:
            path = plan_dir / "mid_panel" / rid / "v1.md"
            assert path.exists(), f"missing mid_panel/{rid}/v1.md"

        # Low panel (5 reviewers)
        low_reviewers = [
            "implementation_feasibility", "testability", "edge_cases",
            "cli_ux_details", "migration_backcompat",
        ]
        for rid in low_reviewers:
            path = plan_dir / "low_panel" / rid / "v1.md"
            assert path.exists(), f"missing low_panel/{rid}/v1.md"

    def test_3_revision_artifacts_exist_at_correct_paths(self, tmp_path: Path) -> None:
        """high_revise/v1.md, mid_revise/v1.md, readiness/v1.md all exist."""
        pipeline = build_pipeline()
        worker = _recording_worker()
        _patch_workers(pipeline, worker)

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        assert (plan_dir / "high_revise" / "v1.md").exists()
        assert (plan_dir / "mid_revise" / "v1.md").exists()
        assert (plan_dir / "readiness" / "v1.md").exists()

    def test_fake_worker_records_prove_dependency_flow(self, tmp_path: Path) -> None:
        """Recording worker proves high_revise saw draft+high_panel.*,
        mid_revise saw high_revise+mid_panel.*, readiness saw mid_revise+low_panel.*."""
        pipeline = build_pipeline()
        worker = _recording_worker()
        _patch_workers(pipeline, worker)

        plan_dir = tmp_path / "run"
        draft_path = _setup_draft(plan_dir)
        ctx = _fresh_ctx(plan_dir, draft_path)

        run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        calls: list[dict] = worker.calls  # type: ignore[union-attr]

        # ── High panel reviewers consume 'draft' ──
        high_panel_calls = [c for c in calls if c["step_name"].startswith("high_panel.")]
        assert len(high_panel_calls) == 5, f"expected 5 high panel calls, got {len(high_panel_calls)}"
        for c in high_panel_calls:
            assert "draft" in c["inputs"], (
                f"high_panel reviewer {c['step_name']} missing 'draft' input; got {list(c['inputs'])}"
            )

        # ── Mid panel reviewers consume 'high_revise' ──
        mid_panel_calls = [c for c in calls if c["step_name"].startswith("mid_panel.")]
        assert len(mid_panel_calls) == 5, f"expected 5 mid panel calls, got {len(mid_panel_calls)}"
        for c in mid_panel_calls:
            assert "high_revise" in c["inputs"], (
                f"mid_panel reviewer {c['step_name']} missing 'high_revise' input; got {list(c['inputs'])}"
            )

        # ── Low panel reviewers consume 'mid_revise' ──
        low_panel_calls = [c for c in calls if c["step_name"].startswith("low_panel.")]
        assert len(low_panel_calls) == 5, f"expected 5 low panel calls, got {len(low_panel_calls)}"
        for c in low_panel_calls:
            assert "mid_revise" in c["inputs"], (
                f"low_panel reviewer {c['step_name']} missing 'mid_revise' input; got {list(c['inputs'])}"
            )

        # ── high_revise consumes 'draft' + high_panel.* ──
        high_revise_calls = [c for c in calls if c["step_name"] == "high_revise"]
        assert len(high_revise_calls) == 1, f"expected 1 high_revise call, got {len(high_revise_calls)}"
        hr_inputs = high_revise_calls[0]["inputs"]
        assert "draft" in hr_inputs, f"high_revise missing 'draft'; got {list(hr_inputs)}"
        # high_panel.* should expand to reviewer outputs
        assert any(k.startswith("high_panel.") for k in hr_inputs), (
            f"high_revise missing high_panel.* refs; got {list(hr_inputs)}"
        )

        # ── mid_revise consumes 'high_revise' + mid_panel.* ──
        mid_revise_calls = [c for c in calls if c["step_name"] == "mid_revise"]
        assert len(mid_revise_calls) == 1, f"expected 1 mid_revise call, got {len(mid_revise_calls)}"
        mr_inputs = mid_revise_calls[0]["inputs"]
        assert "high_revise" in mr_inputs, f"mid_revise missing 'high_revise'; got {list(mr_inputs)}"
        assert any(k.startswith("mid_panel.") for k in mr_inputs), (
            f"mid_revise missing mid_panel.* refs; got {list(mr_inputs)}"
        )

        # ── readiness consumes 'mid_revise' + low_panel.* ──
        readiness_calls = [c for c in calls if c["step_name"] == "readiness"]
        assert len(readiness_calls) == 1, f"expected 1 readiness call, got {len(readiness_calls)}"
        rd_inputs = readiness_calls[0]["inputs"]
        assert "mid_revise" in rd_inputs, f"readiness missing 'mid_revise'; got {list(rd_inputs)}"
        assert any(k.startswith("low_panel.") for k in rd_inputs), (
            f"readiness missing low_panel.* refs; got {list(rd_inputs)}"
        )
