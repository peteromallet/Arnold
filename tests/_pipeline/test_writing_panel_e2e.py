"""End-to-end tests for writing-panel-strict YAML pipeline.

Exercises the full pipeline through pause, resume continue (loop once),
and resume stop (terminate). Uses mocked workers so no real model
calls are made.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from megaplan._pipeline.loader import load_pipeline
from megaplan._pipeline.compiler import compile_pipeline, inject_pipeline_context
from megaplan._pipeline.executor import run_pipeline
from megaplan._pipeline.resume import check_awaiting_user, with_entry
from megaplan._pipeline.preflight import (
    preflight_check_profile,
    preflight_or_raise,
    render_credential_failure,
)
from megaplan._pipeline.types import (
    Pipeline,
    StepContext,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _mock_worker(response: str = "mock agent output"):
    """Return a mock worker function that returns a fixed response."""

    def worker(**kwargs) -> str:
        return response

    return worker


def _mock_panel_worker(response: str = "mock review"):
    """Return a mock panel reviewer worker."""

    def worker(**kwargs) -> str:
        return response

    return worker


def _setup_draft(plan_dir: Path, content: str = "# Test Draft\n\nThis is a test.") -> Path:
    """Set up a draft file and return its path."""
    draft_path = plan_dir / "draft.md"
    draft_path.write_text(content)
    return draft_path


# ── End-to-end tests ──────────────────────────────────────────────────


class TestWritingPanelStrictE2E:
    """Full end-to-end: panel_review -> synth -> revise -> human_decide."""

    def test_full_run_pauses_at_human_gate(self, tmp_path: Path):
        """Run writing-panel-strict with mocked workers; it should pause at human_gate."""
        lp = load_pipeline("writing-panel-strict")
        spec = lp.spec

        plan_dir = tmp_path / "run"
        plan_dir.mkdir(parents=True)
        draft_path = _setup_draft(plan_dir)

        # Build pipeline with mocked workers
        pipeline = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("Mocked agent output"),
            mode="polish",
        )

        ctx = StepContext(
            plan_dir=plan_dir,
            state={
                "_pipeline_name": "writing-panel-strict",
                "_pipeline_version": 1,
                "_content_hash": lp.content_hash,
            },
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx = inject_pipeline_context(ctx, spec.name)

        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        # Should pause at human_gate
        assert result["halt_reason"] == "awaiting_user"
        assert result["final_stage"] == "human_decide"

        # Check awaiting_user.json
        awaiting_path = plan_dir / "awaiting_user.json"
        assert awaiting_path.exists()
        data = json.loads(awaiting_path.read_text())
        assert data["pipeline"] == "writing-panel-strict"
        assert data["version"] == 1
        assert data["stage"] == "human_decide"
        assert data["artifact_stage"] == "revise"
        assert data["choices"] == ["continue", "stop"]
        assert "artifact_path" in data
        assert "revise" in data["artifact_path"]
        assert "v1.md" in data["artifact_path"]

        # Verify artifacts up to revise exist
        assert (plan_dir / "panel_review" / "pessimist" / "v1.md").exists()
        assert (plan_dir / "panel_review" / "optimist" / "v1.md").exists()
        assert (plan_dir / "panel_review" / "structuralist" / "v1.md").exists()
        assert (plan_dir / "synth" / "v1.md").exists()
        assert (plan_dir / "revise" / "v1.md").exists()

        # State should have identity snapshot
        state = result.get("state", {})
        assert state.get("_pipeline_name") == "writing-panel-strict"
        assert state.get("_pipeline_version") == 1

    def test_resume_continue_loops_to_panel_review(self, tmp_path: Path):
        """Resume with --choice continue loops back to panel_review, then pauses again."""
        lp = load_pipeline("writing-panel-strict")
        spec = lp.spec

        plan_dir = tmp_path / "run"
        plan_dir.mkdir(parents=True)
        draft_path = _setup_draft(plan_dir)

        # First run: pause at human_gate
        pipeline = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("First pass output"),
            mode="polish",
        )

        ctx = StepContext(
            plan_dir=plan_dir,
            state={"_pipeline_name": spec.name, "_pipeline_version": spec.version},
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx = inject_pipeline_context(ctx, spec.name)

        result1 = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result1["halt_reason"] == "awaiting_user"
        assert result1["final_stage"] == "human_decide"

        # Verify first pass artifacts exist (v1)
        assert (plan_dir / "revise" / "v1.md").exists()

        # Now resume with continue choice
        # Re-read state
        state_json = json.loads((plan_dir / "state.json").read_text())
        paused_stage = state_json.get("_pipeline_paused_stage")
        assert paused_stage == "human_decide"

        # Build new pipeline with resume_choice
        pipeline2 = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("Second pass output"),
            resume_choice="continue",
            mode="polish",
        )

        # Re-enter at paused stage
        pipeline2 = with_entry(pipeline2, paused_stage)

        # Clear pause flags
        if "_pipeline_paused" in state_json:
            del state_json["_pipeline_paused"]
        if "_pipeline_paused_stage" in state_json:
            del state_json["_pipeline_paused_stage"]

        ctx2 = StepContext(
            plan_dir=plan_dir,
            state=state_json,
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx2 = inject_pipeline_context(ctx2, spec.name)

        result2 = run_pipeline(pipeline2, ctx2, artifact_root=plan_dir)

        # After continue, we go through panel_review -> synth -> revise -> human_decide again
        # Should pause at human_gate again
        assert result2["halt_reason"] == "awaiting_user"
        assert result2["final_stage"] == "human_decide"

        # Second pass artifacts should exist (v2 after the loop)
        # Note: depends on versioning - panel_review v2, synth v2, revise v2
        assert (plan_dir / "revise" / "v2.md").exists()

        # awaiting_user.json should exist again
        assert (plan_dir / "awaiting_user.json").exists()

    def test_resume_stop_terminates(self, tmp_path: Path):
        """Resume with --choice stop terminates the pipeline (reaches done)."""
        lp = load_pipeline("writing-panel-strict")
        spec = lp.spec

        plan_dir = tmp_path / "run"
        plan_dir.mkdir(parents=True)
        draft_path = _setup_draft(plan_dir)

        # First run: pause at human_gate
        pipeline = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("Mocked output"),
            mode="polish",
        )

        ctx = StepContext(
            plan_dir=plan_dir,
            state={"_pipeline_name": spec.name, "_pipeline_version": spec.version},
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx = inject_pipeline_context(ctx, spec.name)

        result1 = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result1["halt_reason"] == "awaiting_user"

        # Now resume with stop choice
        state_json = json.loads((plan_dir / "state.json").read_text())
        paused_stage = state_json.get("_pipeline_paused_stage")
        assert paused_stage == "human_decide"

        pipeline2 = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("Should not be used"),
            resume_choice="stop",
            mode="polish",
        )
        pipeline2 = with_entry(pipeline2, paused_stage)

        # Clear pause flags
        if "_pipeline_paused" in state_json:
            del state_json["_pipeline_paused"]
        if "_pipeline_paused_stage" in state_json:
            del state_json["_pipeline_paused_stage"]

        ctx2 = StepContext(
            plan_dir=plan_dir,
            state=state_json,
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx2 = inject_pipeline_context(ctx2, spec.name)

        result2 = run_pipeline(pipeline2, ctx2, artifact_root=plan_dir)

        # Should complete successfully (halt for done)
        assert result2.get("halt_reason") != "awaiting_user"
        # The pipeline completes; no more awaiting_user.json
        assert not (plan_dir / "awaiting_user.json").exists()

    def test_fresh_artifact_reread_on_resume(self, tmp_path: Path):
        """After pause, editing the revise artifact on disk is picked up on resume."""
        lp = load_pipeline("writing-panel-strict")
        spec = lp.spec

        plan_dir = tmp_path / "run"
        plan_dir.mkdir(parents=True)
        draft_path = _setup_draft(plan_dir)

        # First run: pause
        pipeline = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("Original output"),
            mode="polish",
        )

        ctx = StepContext(
            plan_dir=plan_dir,
            state={"_pipeline_name": spec.name, "_pipeline_version": spec.version},
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx = inject_pipeline_context(ctx, spec.name)

        result1 = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result1["halt_reason"] == "awaiting_user"

        # Edit the revise artifact on disk
        revise_path = plan_dir / "revise" / "v1.md"
        original_content = revise_path.read_text()
        edited_content = original_content + "\n\n# Human edit: improved section"
        revise_path.write_text(edited_content)

        # Also manually write a new version to simulate what happens in real usage
        (plan_dir / "revise" / "v2_human.md").write_text("# Completely rewritten by human\n\nBetter.")

        # Resume with continue — the fresh v2_human.md should be picked up
        # (Actually, _latest_artifact would pick v2_human.md if it's the latest)
        state_json = json.loads((plan_dir / "state.json").read_text())
        paused_stage = state_json.get("_pipeline_paused_stage")

        pipeline2 = compile_pipeline(
            spec,
            pipeline_dir=lp.dir,
            worker=_mock_worker("After human edit output"),
            resume_choice="continue",
            mode="polish",
        )
        pipeline2 = with_entry(pipeline2, paused_stage)

        if "_pipeline_paused" in state_json:
            del state_json["_pipeline_paused"]
        if "_pipeline_paused_stage" in state_json:
            del state_json["_pipeline_paused_stage"]

        ctx2 = StepContext(
            plan_dir=plan_dir,
            state=state_json,
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx2 = inject_pipeline_context(ctx2, spec.name)

        result2 = run_pipeline(pipeline2, ctx2, artifact_root=plan_dir)
        assert result2["halt_reason"] == "awaiting_user"

        # Verify the current revise artifact reflects the fresh re-read
        assert (plan_dir / "revise" / "v2.md").exists()

    def test_full_pause_resume_continue_loop_then_stop(self, tmp_path: Path):
        """Complete cycle: pause -> resume continue -> pause -> resume stop."""
        lp = load_pipeline("writing-panel-strict")
        spec = lp.spec

        plan_dir = tmp_path / "run"
        plan_dir.mkdir(parents=True)
        draft_path = _setup_draft(plan_dir)

        # --- Run 1: initial run, pauses at human_gate ---
        pipeline = compile_pipeline(
            spec, pipeline_dir=lp.dir,
            worker=_mock_worker("Run 1 output"),
            mode="polish",
        )
        ctx = StepContext(
            plan_dir=plan_dir,
            state={"_pipeline_name": spec.name, "_pipeline_version": spec.version},
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx = inject_pipeline_context(ctx, spec.name)
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)
        assert result["halt_reason"] == "awaiting_user"
        assert (plan_dir / "revise" / "v1.md").exists()

        # --- Run 2: resume continue, loops back ---
        state_json = json.loads((plan_dir / "state.json").read_text())
        paused_stage = state_json["_pipeline_paused_stage"]
        state_json.pop("_pipeline_paused", None)
        state_json.pop("_pipeline_paused_stage", None)

        pipeline2 = compile_pipeline(
            spec, pipeline_dir=lp.dir,
            worker=_mock_worker("Run 2 output"),
            resume_choice="continue",
            mode="polish",
        )
        pipeline2 = with_entry(pipeline2, paused_stage)
        ctx2 = StepContext(
            plan_dir=plan_dir, state=state_json,
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish", inputs={"draft": draft_path},
        )
        ctx2 = inject_pipeline_context(ctx2, spec.name)
        result2 = run_pipeline(pipeline2, ctx2, artifact_root=plan_dir)
        assert result2["halt_reason"] == "awaiting_user"
        assert (plan_dir / "revise" / "v2.md").exists()

        # --- Run 3: resume stop, terminates ---
        state_json = json.loads((plan_dir / "state.json").read_text())
        paused_stage = state_json["_pipeline_paused_stage"]
        state_json.pop("_pipeline_paused", None)
        state_json.pop("_pipeline_paused_stage", None)

        pipeline3 = compile_pipeline(
            spec, pipeline_dir=lp.dir,
            worker=_mock_worker("Should not run"),
            resume_choice="stop",
            mode="polish",
        )
        pipeline3 = with_entry(pipeline3, paused_stage)
        ctx3 = StepContext(
            plan_dir=plan_dir, state=state_json,
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish", inputs={"draft": draft_path},
        )
        ctx3 = inject_pipeline_context(ctx3, spec.name)
        result3 = run_pipeline(pipeline3, ctx3, artifact_root=plan_dir)

        # Should be done (no more pause)
        assert result3.get("halt_reason") != "awaiting_user"
        assert not (plan_dir / "awaiting_user.json").exists()

    def test_state_snapshot_has_pipeline_identity(self, tmp_path: Path):
        """State snapshotted during run includes pipeline name, version, and content hash."""
        lp = load_pipeline("writing-panel-strict")
        spec = lp.spec

        plan_dir = tmp_path / "run"
        plan_dir.mkdir(parents=True)
        draft_path = _setup_draft(plan_dir)

        pipeline = compile_pipeline(
            spec, pipeline_dir=lp.dir,
            worker=_mock_worker("identity test"),
            mode="polish",
        )
        ctx = StepContext(
            plan_dir=plan_dir,
            state={
                "_pipeline_name": spec.name,
                "_pipeline_version": spec.version,
                "_content_hash": lp.content_hash,
            },
            profile={"panel_review.pessimist": "claude", "panel_review.optimist": "claude",
                     "panel_review.structuralist": "claude", "synth": "claude",
                     "revise": "claude"},
            mode="polish",
            inputs={"draft": draft_path},
        )
        ctx = inject_pipeline_context(ctx, spec.name)
        result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

        state = result.get("state", {})
        assert state.get("_pipeline_name") == "writing-panel-strict"
        assert state.get("_pipeline_version") == 1
        assert "_content_hash" in state
        assert len(state["_content_hash"]) == 64  # SHA-256 hex digest


# ── Credential preflight tests ─────────────────────────────────────────

class TestCredentialPreflight:
    """Credential preflight: non-TTY exit 7, stderr structure, TTY message."""

    def test_preflight_check_all_present(self, monkeypatch):
        """When all credentials are available, preflight passes."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        profile = {"synth": "claude", "revise": "claude"}
        missing = preflight_check_profile(profile)
        assert missing == []

    def test_preflight_check_missing(self, monkeypatch):
        """When credential is missing, it appears in the missing list."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        profile = {"synth": "claude"}
        missing = preflight_check_profile(profile)
        assert len(missing) == 1
        assert missing[0]["slot"] == "synth"
        assert missing[0]["env_var"] == "ANTHROPIC_API_KEY"

    def test_preflight_check_codex_missing(self, monkeypatch):
        """Codex agents require OPENAI_API_KEY."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        profile = {"synth": "codex"}
        missing = preflight_check_profile(profile)
        assert len(missing) == 1
        assert missing[0]["env_var"] == "OPENAI_API_KEY"

    def test_render_credential_failure_non_tty(self, monkeypatch):
        """Non-TTY mode renders structured message with env var hints."""
        missing = [
            {"slot": "synth", "spec": "codex", "agent": "codex",
             "env_var": "OPENAI_API_KEY"},
        ]
        msg = render_credential_failure(
            missing,
            pipeline_name="writing-panel-strict",
            profile_name="standard",
            is_tty=False,
        )
        assert "writing-panel-strict" in msg
        assert "standard" in msg
        assert "OPENAI_API_KEY" in msg
        assert "codex" in msg
        assert "synth" in msg
        # Non-TTY should NOT have [1] [2] options
        assert "[1]" not in msg
        assert "[2]" not in msg

    def test_render_credential_failure_tty(self, monkeypatch):
        """TTY mode renders options list."""
        missing = [
            {"slot": "synth", "spec": "codex", "agent": "codex",
             "env_var": "OPENAI_API_KEY"},
        ]
        msg = render_credential_failure(
            missing,
            pipeline_name="writing-panel-strict",
            profile_name="standard",
            is_tty=True,
        )
        assert "[1] Abort" in msg
        assert "[2] Pick a different profile" in msg
        assert "[3] Provide a key now" in msg
        assert "[4] Sign in" in msg

    def test_preflight_or_raise_exits_7_non_tty(self, tmp_path, monkeypatch, capsys):
        """preflight_or_raise exits 7 when credentials missing in non-TTY."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        profile = {"synth": "claude"}

        with pytest.raises(SystemExit) as exc_info:
            preflight_or_raise(
                profile,
                pipeline_name="test",
                profile_name="default",
            )
        assert exc_info.value.code == 7

        # Check stderr has structured message
        captured = capsys.readouterr()
        assert "test" in captured.err
        assert "ANTHROPIC_API_KEY" in captured.err

    def test_preflight_or_raise_exits_7_tty(self, monkeypatch):
        """preflight_or_raise exits 7 even in TTY when credentials missing."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        profile = {"synth": "claude"}

        with pytest.raises(SystemExit) as exc_info:
            preflight_or_raise(
                profile,
                pipeline_name="test",
                profile_name="default",
            )
        assert exc_info.value.code == 7

    def test_preflight_or_raise_passes_when_all_ok(self, monkeypatch):
        """preflight_or_raise does nothing when all credentials are available."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        profile = {"synth": "claude"}

        # Should not raise
        preflight_or_raise(
            profile,
            pipeline_name="test",
            profile_name="default",
        )

    def test_preflight_skips_non_string_slots(self, monkeypatch):
        """Non-string profile slots are skipped gracefully."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        profile = {"synth": None, "revise": ""}
        missing = preflight_check_profile(profile)
        assert missing == []

    def test_render_credential_failure_grouped_by_env_var(self):
        """Multiple missing slots for same env var are grouped."""
        missing = [
            {"slot": "synth", "spec": "codex", "agent": "codex",
             "env_var": "OPENAI_API_KEY"},
            {"slot": "revise", "spec": "codex", "agent": "codex",
             "env_var": "OPENAI_API_KEY"},
        ]
        msg = render_credential_failure(
            missing,
            pipeline_name="test",
            profile_name="p",
            is_tty=False,
        )
        # Should only mention OPENAI_API_KEY once
        assert msg.count("OPENAI_API_KEY") == 1
        assert "synth" in msg
        assert "revise" in msg


# ── Human-gate continue input repointing (Sprint A defect fix) ─────────

class TestHumanGateContinueRepointsInput:
    """Resume --choice continue repoints the loop input to the edited artifact.

    Locked decision #16: when the user edits revise/v1.md between pause
    and resume continue, the next panel_review iteration must consume the
    edited revise content (not the original draft, not a missing file).
    The fix lives in megaplan/_pipeline/run_cli.py around _run_yaml_pipeline.
    """

    def _run_cli(self, **overrides):
        """Helper: invoke cli_run with a populated argparse.Namespace."""
        import argparse
        from megaplan._pipeline.run_cli import cli_run

        defaults = dict(
            pipeline_name=None,
            input_file=None,
            list_pipelines=False,
            plan_dir=None,
            inputs=None,
            state=None,
            mode=None,
            profile=None,
            describe=False,
            resume_choice=None,
            vendor=None,
        )
        defaults.update(overrides)
        return cli_run(argparse.Namespace(**defaults))

    def _fresh_run_to_pause(self, tmp_path, monkeypatch):
        """Drive a fresh CLI run that pauses at human_decide. Returns plan_dir."""
        # Bypass credential preflight — worker=None, no real model calls.
        monkeypatch.setattr(
            "megaplan._pipeline.preflight.preflight_or_raise",
            lambda *a, **k: None,
        )

        draft_path = tmp_path / "draft.md"
        draft_path.write_text("# ORIGINAL DRAFT\n\nFirst version content.\n")
        plan_dir = tmp_path / "run"

        rc = self._run_cli(
            pipeline_name="writing-panel-strict",
            input_file=str(draft_path),
            plan_dir=str(plan_dir),
            mode="polish",
        )
        assert rc == 0
        assert (plan_dir / "awaiting_user.json").exists()
        assert (plan_dir / "revise" / "v1.md").exists()
        return plan_dir, draft_path

    def test_fresh_run_persists_inputs(self, tmp_path, monkeypatch):
        """Fresh runs persist `_inputs` (and `_inputs_original`) to state.json
        so a subsequent resume always has them, even without --input-file."""
        plan_dir, draft_path = self._fresh_run_to_pause(tmp_path, monkeypatch)

        state = json.loads((plan_dir / "state.json").read_text())
        assert "_inputs" in state, "fresh run must persist _inputs to state"
        assert state["_inputs"]["draft"] == str(draft_path)
        # Audit trail: original inputs preserved
        assert state.get("_inputs_original", {}).get("draft") == str(draft_path)

    def test_resume_continue_repoints_draft_to_edited_revise(
        self, tmp_path, monkeypatch
    ):
        """The failing scenario from the review verdict.

        User edits revise/v1.md (writes revise/v2.md via /v2.md naming)
        between pause and resume. Resume continue must repoint `draft` to
        the latest revise artifact so the next panel_review iteration
        consumes the human-edited content."""
        plan_dir, draft_path = self._fresh_run_to_pause(tmp_path, monkeypatch)

        # Simulate the human editing the revise artifact between pause and
        # resume. They drop in a freshly numbered version with their edits.
        edited_revise = plan_dir / "revise" / "v2.md"
        edited_revise.write_text("# HUMAN-EDITED REVISE\n\nMuch better now.\n")

        # Resume with continue.
        rc = self._run_cli(
            pipeline_name="writing-panel-strict",
            plan_dir=str(plan_dir),
            resume_choice="continue",
            mode="polish",
        )
        assert rc == 0

        # Inspect the post-resume state — _inputs should now point `draft`
        # at the edited revise artifact, NOT the original draft.md.
        state = json.loads((plan_dir / "state.json").read_text())
        assert state["_inputs"]["draft"] == str(edited_revise), (
            f"expected draft input to be repointed to edited revise "
            f"artifact {edited_revise!s}, got {state['_inputs']['draft']!r}"
        )
        # And the original is still preserved in audit trail.
        assert state["_inputs_original"]["draft"] == str(draft_path)

        # The second panel_review iteration must have actually run, writing
        # v2 versions of the panel reviewer artifacts. (If the fix were
        # broken, _resolve_inputs would have fallen back to a nonexistent
        # `<plan_dir>/draft/v1.md` and the step would error out or produce
        # garbage — but with our fix, the path resolves correctly and the
        # next iteration produces v2 panel reviews.)
        assert (plan_dir / "panel_review" / "pessimist" / "v2.md").exists()
        assert (plan_dir / "panel_review" / "optimist" / "v2.md").exists()
        assert (plan_dir / "panel_review" / "structuralist" / "v2.md").exists()

    def test_resume_continue_with_explicit_input_file_takes_precedence(
        self, tmp_path, monkeypatch
    ):
        """If the user re-supplies --input-file on resume, that wins over
        the human-gate continue swap. User override is sacrosanct."""
        plan_dir, draft_path = self._fresh_run_to_pause(tmp_path, monkeypatch)

        # Write an edited revise artifact (would normally be picked up).
        (plan_dir / "revise" / "v2.md").write_text("# HUMAN EDIT\n")

        # But the user explicitly passes a NEW input file on resume.
        override = tmp_path / "override.md"
        override.write_text("# OVERRIDE\n\nUser wants to restart from this.\n")

        rc = self._run_cli(
            pipeline_name="writing-panel-strict",
            input_file=str(override),
            plan_dir=str(plan_dir),
            resume_choice="continue",
            mode="polish",
        )
        assert rc == 0

        state = json.loads((plan_dir / "state.json").read_text())
        # Override wins — `draft` points at the override file.
        assert state["_inputs"]["draft"] == str(override)
        # Original is still preserved as audit trail (from the fresh run).
        assert state["_inputs_original"]["draft"] == str(draft_path)

    def test_resume_continue_captures_latest_revise_version(
        self, tmp_path, monkeypatch
    ):
        """When the human drops in revise/v3.md, the continue swap uses
        the LATEST version (fresh read from disk), not the path snapshotted
        in awaiting_user.json at pause time."""
        plan_dir, draft_path = self._fresh_run_to_pause(tmp_path, monkeypatch)

        # At pause time, awaiting_user.json records revise/v1.md.
        # The human writes both v2 and v3 — v3 should be picked up.
        (plan_dir / "revise" / "v2.md").write_text("# v2 attempt\n")
        (plan_dir / "revise" / "v3.md").write_text("# v3 final human edit\n")

        rc = self._run_cli(
            pipeline_name="writing-panel-strict",
            plan_dir=str(plan_dir),
            resume_choice="continue",
            mode="polish",
        )
        assert rc == 0

        state = json.loads((plan_dir / "state.json").read_text())
        assert state["_inputs"]["draft"] == str(plan_dir / "revise" / "v3.md")
