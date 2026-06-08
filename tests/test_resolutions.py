"""Focused tests for the M1 Core Resolution Contract (T7).

Covers:
  (a) persistence / helper tests
  (b) CLI validation tests
  (c) batch execute prompt tests
  (d) single execute prompt tests
  (e) finalize gate task tests
  (f) progress / status tests
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
import arnold.pipelines.megaplan.cli as megaplan_cli
import arnold.pipelines.megaplan.workers as megaplan_workers
from arnold.pipelines.megaplan._core import read_json
from arnold.pipelines.megaplan.handlers.finalize import _ensure_user_actions_pre_gate_task
from arnold.pipelines.megaplan.prompts.execute import _execute_batch_prompt, _execute_prompt
from arnold.pipelines.megaplan.resolutions import (
    FALLBACK_STATES,
    HARD_BLOCK_STATES,
    USER_ACTION_RESOLUTIONS_FILE,
    load_user_action_resolutions,
    resolution_applies_to_task,
    resolution_recommended_action,
    save_user_action_resolutions,
    upsert_user_action_resolution,
)
from arnold.pipelines.megaplan.types import CliError
from tests.conftest import load_state, read_json as conftest_read_json


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _write_finalize_json(plan_dir: Path, *, tasks=None, user_actions=None, sense_checks=None):
    """Write a minimal finalize.json into *plan_dir*."""
    data = {
        "tasks": tasks or [
            {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending",
             "executor_notes": "", "files_changed": [], "commands_run": [], "evidence_files": [],
             "reviewer_verdict": ""},
            {"id": "T2", "description": "Do the other thing", "depends_on": ["T1"], "status": "pending",
             "executor_notes": "", "files_changed": [], "commands_run": [], "evidence_files": [],
             "reviewer_verdict": ""},
        ],
        "watch_items": [],
        "sense_checks": sense_checks or [],
        "user_actions": user_actions or [],
        "meta_commentary": "test plan",
        "validation": {"plan_steps_covered": [], "orphan_tasks": [], "completeness_notes": "", "coverage_complete": True},
    }
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "finalize.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_minimal_state(plan_dir: Path, *, project_dir: Path, auto_approve: bool = True, mode: str = "code"):
    """Write a minimal state.json for execute prompts."""
    state = {
        "name": "test",
        "current_state": "finalized",
        "iteration": 1,
        "idea": "Test idea for resolution contract.",
        "meta": {},
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": auto_approve,
            "mode": mode,
        },
        "history": [],
        "plan_versions": [{"file": "plan.md"}],
    }
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    # Also write a minimal plan meta file so latest_plan_meta_path resolves
    (plan_dir / "plan.meta.json").write_text(json.dumps({"plan": "test"}), encoding="utf-8")


def _make_args(**overrides) -> Namespace:
    """Create a Namespace for CLI resolve command tests."""
    data = {
        "plan": None,
        "idea": "test",
        "name": "test-plan",
        "project_dir": "/tmp",
        "auto_approve": None,
        "robustness": None,
        "agent": None,
        "ephemeral": False,
        "fresh": False,
        "persist": False,
        "confirm_destructive": True,
        "user_approved": False,
        "confirm_self_review": False,
        "batch": None,
        "override_action": None,
        "note": None,
        "reason": "",
        "strict_notes": None,
        "source": "user",
        "user_action_action": None,
        "action": None,
        "state": None,
        "fallback_mode": "",
        "applies_to_task_ids": "",
        "instructions": "",
        "created_by": "cli",
    }
    data.update(overrides)
    return Namespace(**data)


def _batch_state(project_dir: Path, auto_approve: bool = True):
    return {
        "name": "test",
        "current_state": "finalized",
        "iteration": 1,
        "idea": "Test idea.",
        "meta": {},
        "config": {"project_dir": str(project_dir), "auto_approve": auto_approve, "mode": "code"},
        "history": [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# (a) Persistence / helper tests
# ══════════════════════════════════════════════════════════════════════════════

class TestResolutionPersistence:
    """Write update, deterministic upserts, and malformed artifact rejection."""

    def test_load_returns_empty_dict_when_file_is_absent(self, tmp_path: Path):
        result = load_user_action_resolutions(tmp_path)
        assert result == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        resolutions = {
            "U1": {"action_id": "U1", "state": "accepted_blocked", "reason": "ok", "fallback_mode": "skip",
                   "applies_to_task_ids": [], "instructions": "", "created_at": "2025-01-01T00:00:00Z",
                   "created_by": "cli"},
        }
        save_user_action_resolutions(tmp_path, resolutions)
        loaded = load_user_action_resolutions(tmp_path)
        assert loaded == resolutions
        assert (tmp_path / USER_ACTION_RESOLUTIONS_FILE).exists()

    def test_upsert_creates_new_resolution(self, tmp_path: Path):
        result = upsert_user_action_resolution(
            tmp_path, "U1", "accepted_blocked", reason="accepted because X",
            fallback_mode="skip", instructions="proceed anyway",
        )
        assert "U1" in result
        assert result["U1"]["state"] == "accepted_blocked"
        assert result["U1"]["reason"] == "accepted because X"
        assert result["U1"]["fallback_mode"] == "skip"
        assert result["U1"]["instructions"] == "proceed anyway"
        assert result["U1"]["action_id"] == "U1"
        assert "created_at" in result["U1"]

    def test_upsert_preserves_created_at_on_update(self, tmp_path: Path):
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="first")
        first = load_user_action_resolutions(tmp_path)
        first_ts = first["U1"]["created_at"]

        upsert_user_action_resolution(tmp_path, "U1", "satisfied", reason="updated")
        second = load_user_action_resolutions(tmp_path)

        assert second["U1"]["state"] == "satisfied"
        assert second["U1"]["reason"] == "updated"
        assert second["U1"]["created_at"] == first_ts

    def test_upsert_merges_non_explicit_fields_with_prior(self, tmp_path: Path):
        upsert_user_action_resolution(
            tmp_path, "U1", "accepted_blocked", reason="original",
            fallback_mode="mock", instructions="do mock",
        )
        upsert_user_action_resolution(tmp_path, "U1", "satisfied")
        loaded = load_user_action_resolutions(tmp_path)
        assert loaded["U1"]["state"] == "satisfied"
        assert loaded["U1"]["reason"] == "original"
        assert loaded["U1"]["fallback_mode"] == "mock"
        assert loaded["U1"]["instructions"] == "do mock"

    def test_multiple_resolutions_in_one_file(self, tmp_path: Path):
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="r1")
        upsert_user_action_resolution(tmp_path, "U2", "waived", reason="r2")
        loaded = load_user_action_resolutions(tmp_path)
        assert len(loaded) == 2
        assert loaded["U1"]["state"] == "accepted_blocked"
        assert loaded["U2"]["state"] == "waived"

    def test_upsert_rejects_unsupported_state(self, tmp_path: Path):
        with pytest.raises(CliError, match="Unsupported resolution state"):
            upsert_user_action_resolution(tmp_path, "U1", "bogus_state")

    def test_malformed_json_raises_cli_error(self, tmp_path: Path):
        path = tmp_path / USER_ACTION_RESOLUTIONS_FILE
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(CliError, match="Failed to parse"):
            load_user_action_resolutions(tmp_path)

    def test_non_object_artifact_raises_cli_error(self, tmp_path: Path):
        path = tmp_path / USER_ACTION_RESOLUTIONS_FILE
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(CliError, match="must be a JSON object"):
            load_user_action_resolutions(tmp_path)

    def test_non_string_key_raises_cli_error(self, tmp_path: Path):
        path = tmp_path / USER_ACTION_RESOLUTIONS_FILE
        path.write_text('{"": {"state": "satisfied", "reason": "x"}}', encoding="utf-8")
        with pytest.raises(CliError, match="keys must be non-empty strings"):
            load_user_action_resolutions(tmp_path)

    def test_non_object_value_raises_cli_error(self, tmp_path: Path):
        path = tmp_path / USER_ACTION_RESOLUTIONS_FILE
        path.write_text('{"U1": "not an object"}', encoding="utf-8")
        with pytest.raises(CliError, match="must be a JSON object"):
            load_user_action_resolutions(tmp_path)

    def test_unsupported_state_in_loaded_file_raises_cli_error(self, tmp_path: Path):
        path = tmp_path / USER_ACTION_RESOLUTIONS_FILE
        path.write_text('{"U1": {"state": "bogus", "reason": "x"}}', encoding="utf-8")
        with pytest.raises(CliError, match="invalid or missing state"):
            load_user_action_resolutions(tmp_path)


class TestResolutionHelpers:
    """Query helpers: resolution_applies_to_task, resolution_recommended_action."""

    def test_applies_to_task_empty_list_means_all(self):
        resolution = {"applies_to_task_ids": [], "state": "satisfied"}
        assert resolution_applies_to_task(resolution, "T1") is True
        assert resolution_applies_to_task(resolution, "T99") is True

    def test_applies_to_task_explicit_list(self):
        resolution = {"applies_to_task_ids": ["T1", "T2"], "state": "satisfied"}
        assert resolution_applies_to_task(resolution, "T1") is True
        assert resolution_applies_to_task(resolution, "T2") is True
        assert resolution_applies_to_task(resolution, "T3") is False

    def test_applies_to_task_none_resolution(self):
        assert resolution_applies_to_task(None, "T1") is False

    def test_applies_to_task_non_dict(self):
        assert resolution_applies_to_task("not a dict", "T1") is False  # type: ignore[arg-type]

    def test_recommended_action_fallback(self):
        for state in FALLBACK_STATES:
            assert resolution_recommended_action({"state": state}) == "continue_with_fallback"

    def test_recommended_action_satisfied(self):
        assert resolution_recommended_action({"state": "satisfied"}) == "retry_execute"

    def test_recommended_action_rejected(self):
        assert resolution_recommended_action({"state": "rejected"}) == "cannot_continue"

    def test_recommended_action_manual_required(self):
        assert resolution_recommended_action({"state": "manual_required"}) == "awaiting_human"

    def test_recommended_action_missing(self):
        assert resolution_recommended_action(None) == "awaiting_human"
        assert resolution_recommended_action({}) == "awaiting_human"

    def test_applies_to_task_missing_key_means_all(self):
        """Resolution with no ``applies_to_task_ids`` key applies to every task."""
        resolution = {"state": "satisfied"}
        assert resolution_applies_to_task(resolution, "T1") is True
        assert resolution_applies_to_task(resolution, "T99") is True

    def test_applies_to_task_non_list_scope_ignored(self):
        """A non-list ``applies_to_task_ids`` is treated as inapplicable."""
        resolution = {"applies_to_task_ids": "T1", "state": "satisfied"}
        assert resolution_applies_to_task(resolution, "T1") is False

    def test_recommended_action_unknown_state_defaults_to_awaiting_human(self):
        assert resolution_recommended_action({"state": "bogus"}) == "awaiting_human"
        assert resolution_recommended_action({"state": None}) == "awaiting_human"


# ══════════════════════════════════════════════════════════════════════════════
# (b) CLI validation tests
# ══════════════════════════════════════════════════════════════════════════════

class TestCLIValidation:
    """CLI handler validation: rejection paths and confirmed writes."""

    def test_valid_resolve_persists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Successful resolution via handle_user_action writes the file."""
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="accepted_blocked", reason="done", fallback_mode="skip")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        response = megaplan.cli.handle_user_action(tmp_path, args)
        assert response["success"] is True
        assert response["action"] == "resolve"

        resolutions = load_user_action_resolutions(plan_dir)
        assert "U1" in resolutions
        assert resolutions["U1"]["state"] == "accepted_blocked"

    def test_unsupported_state_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="bogus_not_a_state", reason="x")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        with pytest.raises(CliError, match="Unsupported resolution state"):
            megaplan.cli.handle_user_action(tmp_path, args)

        assert not (plan_dir / USER_ACTION_RESOLUTIONS_FILE).exists()

    def test_unknown_action_id_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U99",
                          state="satisfied", reason="x")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        with pytest.raises(CliError, match="Unknown user action"):
            megaplan.cli.handle_user_action(tmp_path, args)

        assert not (plan_dir / USER_ACTION_RESOLUTIONS_FILE).exists()

    def test_unknown_task_id_in_applies_to_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="satisfied", reason="x", applies_to_task_ids="T99")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        with pytest.raises(CliError, match="Unknown task ID"):
            megaplan.cli.handle_user_action(tmp_path, args)

        assert not (plan_dir / USER_ACTION_RESOLUTIONS_FILE).exists()

    def test_task_id_outside_explicit_blockers_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute",
             "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="satisfied", reason="x", applies_to_task_ids="T2")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        with pytest.raises(CliError, match="not in action"):
            megaplan.cli.handle_user_action(tmp_path, args)

        assert not (plan_dir / USER_ACTION_RESOLUTIONS_FILE).exists()

    def test_before_execute_without_explicit_blockers_accepts_any_task_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """before_execute actions without blocks_task_ids allow any known task ID."""
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Verify infrastructure", "phase": "before_execute"},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="accepted_blocked", reason="x", applies_to_task_ids="T1,T2")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        response = megaplan.cli.handle_user_action(tmp_path, args)
        assert response["success"] is True
        resolutions = load_user_action_resolutions(plan_dir)
        assert resolutions["U1"]["applies_to_task_ids"] == ["T1", "T2"]

    def test_empty_applies_to_task_ids_stored_as_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Empty --applies-to-task-ids results in empty list (applies to all)."""
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="satisfied", reason="x", applies_to_task_ids="")
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        response = megaplan.cli.handle_user_action(tmp_path, args)
        assert response["success"] is True
        resolutions = load_user_action_resolutions(plan_dir)
        assert resolutions["U1"]["applies_to_task_ids"] == []

    @pytest.mark.parametrize("bad_value", ["T1,,T2", ",T1", "T1,", ","])
    def test_malformed_comma_separated_applies_to_task_ids_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_value: str,
    ):
        """Reject --applies-to-task-ids with empty comma entries (e.g. 'T1,,T2')."""
        plan_dir = tmp_path / "plan"
        _write_finalize_json(plan_dir, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1", "T2"]},
        ])
        _write_minimal_state(plan_dir, project_dir=tmp_path)
        monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")

        args = _make_args(plan="plan", user_action_action="resolve", action="U1",
                          state="satisfied", reason="x", applies_to_task_ids=bad_value)
        import arnold.pipelines.megaplan.cli as cli_mod
        monkeypatch.setattr(cli_mod, "load_plan", lambda root, name: (plan_dir, load_state(plan_dir)))
        monkeypatch.setattr(cli_mod, "ensure_runtime_layout", lambda root: None)
        monkeypatch.setattr(megaplan._core, "config_dir", lambda home=None: tmp_path / "config")

        with pytest.raises(CliError, match="empty or malformed"):
            megaplan.cli.handle_user_action(tmp_path, args)

        assert not (plan_dir / USER_ACTION_RESOLUTIONS_FILE).exists()


# ══════════════════════════════════════════════════════════════════════════════
# (c) Batch execute prompt tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBatchExecutePromptResolution:
    """Resolution-aware batch execute prompt rendering."""

    def test_accepted_blocked_emits_fallback_instructions(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="will mock it",
                                      fallback_mode="mock", instructions="Use dummy values")

        prompt = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "resolved as accepted_blocked" in prompt
        assert "FALLBACK MODE: mock" in prompt
        assert "will mock it" in prompt
        assert "Use dummy values" in prompt
        assert "supersedes the generic before_execute" in prompt.lower()

    def test_waived_emits_fallback_instructions(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Manual review", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "waived", reason="not needed",
                                      fallback_mode="skip", instructions="Skip this check")

        prompt = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "resolved as waived" in prompt
        assert "FALLBACK MODE: skip" in prompt

    def test_satisfied_emits_confirmation_note(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "satisfied", reason="verified manually")

        prompt = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "resolved as satisfied" in prompt
        assert "Verify mechanically" in prompt

    def test_unresolved_emits_hard_block_text(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)

        prompt = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "mark this task blocked" in prompt
        assert "awaiting U1" in prompt

    def test_manual_required_emits_hard_block_text(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Manual check", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "manual_required", reason="needs human")

        prompt = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "Resolution state is manual_required" in prompt
        assert "mark this task blocked" in prompt

    def test_rejected_emits_hard_block_text(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Required approval", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "rejected", reason="denied")

        prompt = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "Resolution state is rejected" in prompt
        assert "plan cannot continue" in prompt

    def test_scoping_by_applies_to_task_ids(self, tmp_path: Path):
        """Resolution only affects listed tasks; other blocked tasks stay hard-block."""
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute",
             "blocks_task_ids": ["T1", "T2"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="done",
                                      fallback_mode="mock", applies_to_task_ids=["T1"])

        prompt_t1 = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T1"], completed_task_ids=set(), root=None,
        )
        assert "resolved as accepted_blocked" in prompt_t1

        prompt_t2 = _execute_batch_prompt(
            _batch_state(tmp_path), tmp_path,
            batch_task_ids=["T2"], completed_task_ids=set(), root=None,
        )
        assert "still requires the action to be complete" in prompt_t2


# ══════════════════════════════════════════════════════════════════════════════
# (d) Single execute prompt tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleExecutePromptResolution:
    """Single-execute (_execute_prompt) includes resolution-aware guidance
    for all finalize tasks without requiring batch_task_ids."""

    def test_accepted_blocked_in_single_prompt(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="done", fallback_mode="mock")

        state = {
            "name": "test", "current_state": "finalized", "iteration": 1,
            "idea": "Test idea.", "meta": {},
            "config": {"project_dir": str(tmp_path), "auto_approve": True, "mode": "code"},
            "history": [], "plan_versions": [{"file": "plan.md"}],
        }
        prompt = _execute_prompt(state, tmp_path, root=None)
        assert "resolved as accepted_blocked" in prompt
        assert "FALLBACK MODE: mock" in prompt
        assert "User action prerequisites:" in prompt

    def test_satisfied_in_single_prompt(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "satisfied", reason="done")

        state = {
            "name": "test", "current_state": "finalized", "iteration": 1,
            "idea": "Test idea.", "meta": {},
            "config": {"project_dir": str(tmp_path), "auto_approve": True, "mode": "code"},
            "history": [], "plan_versions": [{"file": "plan.md"}],
        }
        prompt = _execute_prompt(state, tmp_path, root=None)
        assert "resolved as satisfied" in prompt
        assert "Verify mechanically" in prompt

    def test_unresolved_in_single_prompt(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)

        state = {
            "name": "test", "current_state": "finalized", "iteration": 1,
            "idea": "Test idea.", "meta": {},
            "config": {"project_dir": str(tmp_path), "auto_approve": True, "mode": "code"},
            "history": [], "plan_versions": [{"file": "plan.md"}],
        }
        prompt = _execute_prompt(state, tmp_path, root=None)
        assert "mark this task blocked" in prompt

    def test_no_user_actions_renders_cleanly(self, tmp_path: Path):
        _write_finalize_json(tmp_path, user_actions=[])
        _write_minimal_state(tmp_path, project_dir=tmp_path)

        state = {
            "name": "test", "current_state": "finalized", "iteration": 1,
            "idea": "Test idea.", "meta": {},
            "config": {"project_dir": str(tmp_path), "auto_approve": True, "mode": "code"},
            "history": [], "plan_versions": [{"file": "plan.md"}],
        }
        prompt = _execute_prompt(state, tmp_path, root=None)
        assert "No user_action prerequisites" in prompt

    def test_all_task_mapping_policy(self, tmp_path: Path):
        """Single execute applies resolution guidance to ALL finalize tasks."""
        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute",
             "blocks_task_ids": ["T1", "T2"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="done", fallback_mode="mock")

        state = {
            "name": "test", "current_state": "finalized", "iteration": 1,
            "idea": "Test idea.", "meta": {},
            "config": {"project_dir": str(tmp_path), "auto_approve": True, "mode": "code"},
            "history": [], "plan_versions": [{"file": "plan.md"}],
        }
        prompt = _execute_prompt(state, tmp_path, root=None)
        assert "PREREQUISITE for T1" in prompt
        assert "PREREQUISITE for T2" in prompt


# ══════════════════════════════════════════════════════════════════════════════
# (e) Finalize gate task tests
# ══════════════════════════════════════════════════════════════════════════════

class TestFinalizeGateTaskResolution:
    """Injected gate task and sense check mention resolution-aware fallback."""

    def test_gate_task_mentions_user_action_resolutions_json(self):
        payload = {
            "tasks": [
                {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending",
                 "executor_notes": "", "files_changed": [], "commands_run": [], "evidence_files": [],
                 "reviewer_verdict": ""},
            ],
            "watch_items": [],
            "sense_checks": [],
            "user_actions": [
                {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
            ],
            "meta_commentary": "",
            "validation": {"plan_steps_covered": [], "orphan_tasks": [], "completeness_notes": "", "coverage_complete": True},
        }
        state = {"config": {"mode": "code"}, "meta": {}}
        _ensure_user_actions_pre_gate_task(payload, state)

        gate_task = payload["tasks"][0]
        assert "user_action_resolutions.json" in gate_task["description"]
        assert "accepted_blocked and waived actions should proceed" in gate_task["description"]
        assert "satisfied actions are resolved" in gate_task["description"]
        assert "unresolved, manual_required, or rejected actions remain hard stops" in gate_task["description"]

    def test_sense_check_allows_resolutions(self):
        payload = {
            "tasks": [
                {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending",
                 "executor_notes": "", "files_changed": [], "commands_run": [], "evidence_files": [],
                 "reviewer_verdict": ""},
            ],
            "watch_items": [],
            "sense_checks": [],
            "user_actions": [
                {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
            ],
            "meta_commentary": "",
            "validation": {"plan_steps_covered": [], "orphan_tasks": [], "completeness_notes": "", "coverage_complete": True},
        }
        state = {"config": {"mode": "code"}, "meta": {}}
        _ensure_user_actions_pre_gate_task(payload, state)

        assert len(payload["sense_checks"]) == 1
        sc = payload["sense_checks"][0]
        assert "accepted_blocked/waived/satisfied resolution" in sc["question"]
        assert "user_action_resolutions.json" in sc["question"]

    def test_no_before_execute_actions_no_gate_task(self):
        payload = {
            "tasks": [
                {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending",
                 "executor_notes": "", "files_changed": [], "commands_run": [], "evidence_files": [],
                 "reviewer_verdict": ""},
            ],
            "watch_items": [],
            "sense_checks": [],
            "user_actions": [
                {"id": "U1", "description": "After deploy", "phase": "after_execute"},
            ],
            "meta_commentary": "",
            "validation": {"plan_steps_covered": [], "orphan_tasks": [], "completeness_notes": "", "coverage_complete": True},
        }
        state = {"config": {"mode": "code"}, "meta": {}}
        _ensure_user_actions_pre_gate_task(payload, state)

        assert len(payload["tasks"]) == 1
        assert payload["tasks"][0]["id"] == "T1"

    def test_non_code_mode_skips_gate_task(self):
        payload = {
            "tasks": [
                {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending",
                 "executor_notes": "", "files_changed": [], "commands_run": [], "evidence_files": [],
                 "reviewer_verdict": ""},
            ],
            "watch_items": [],
            "sense_checks": [],
            "user_actions": [
                {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
            ],
            "meta_commentary": "",
            "validation": {},
        }
        state = {"config": {"mode": "doc"}, "meta": {}}
        _ensure_user_actions_pre_gate_task(payload, state)
        assert len(payload["tasks"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# (f) Progress / status tests
# ══════════════════════════════════════════════════════════════════════════════

class TestProgressStatusResolution:
    """_compute_user_action_blockers and _build_progress_payload resolution-aware fields."""

    def test_pending_blocked_task_appears_in_blocked_tasks_detail(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)

        tasks = [
            {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"},
            {"id": "T2", "description": "Do the other thing", "depends_on": ["T1"], "status": "pending"},
        ]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)

        assert len(blockers["blocked_tasks_detail"]) == 1
        assert blockers["blocked_tasks_detail"][0]["task_id"] == "T1"
        assert blockers["blocked_tasks_detail"][0]["task_status"] == "pending"
        assert "U1" in blockers["blocked_tasks_detail"][0]["blocking_user_actions"]
        assert blockers["recommended_action"] == "awaiting_human"

    def test_resolution_summary_included(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="ok", fallback_mode="mock")

        tasks = [
            {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"},
            {"id": "T2", "description": "Do the other thing", "depends_on": ["T1"], "status": "pending"},
        ]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)

        summary = blockers["user_action_resolution_summary"]
        assert summary["total_resolutions"] == 1
        assert summary["by_state"]["accepted_blocked"] == 1
        # With fallback resolution and no hard blocks, task not in blocked_detail
        # but recommended_action reflects the fallback
        assert blockers["recommended_action"] == "continue_with_fallback"

    def test_recommended_action_rejected(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "rejected", reason="denied")

        tasks = [{"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"}]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)
        assert blockers["recommended_action"] == "cannot_continue"

    def test_recommended_action_awaiting_human(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "manual_required", reason="needs human")

        tasks = [{"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"}]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)
        assert blockers["recommended_action"] == "awaiting_human"

    def test_recommended_action_retry_execute(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "satisfied", reason="done")

        tasks = [{"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"}]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)
        assert blockers["recommended_action"] == "retry_execute"

    def test_recommended_action_none_without_blockers(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[])
        _write_minimal_state(tmp_path, project_dir=tmp_path)

        tasks = [{"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"}]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)
        assert blockers["recommended_action"] == "none"
        assert blockers["blocked_tasks_detail"] == []

    def test_mixed_satisfied_and_fallback_gives_continue_with_fallback(self, tmp_path: Path):
        """When one action is satisfied and one is accepted_blocked, recommended_action
        should be continue_with_fallback (any fallback present takes precedence)."""
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
            {"id": "U2", "description": "Verify config", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "satisfied", reason="done")
        upsert_user_action_resolution(tmp_path, "U2", "accepted_blocked", reason="will mock", fallback_mode="mock")

        tasks = [{"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"}]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)
        assert blockers["recommended_action"] == "continue_with_fallback"

    def test_resolution_details_for_hard_block_task(self, tmp_path: Path):
        """For a rejected resolution, the task appears in blocked_tasks_detail
        with resolution details accessible."""
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "rejected", reason="denied")

        tasks = [{"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"}]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)

        assert len(blockers["blocked_tasks_detail"]) == 1
        detail = blockers["blocked_tasks_detail"][0]
        assert len(detail["resolutions"]) == 1
        res = detail["resolutions"][0]
        assert res["action_id"] == "U1"
        assert res["state"] == "rejected"
        assert res["reason"] == "denied"
        assert res["recommended_action"] == "cannot_continue"

    def test_build_progress_payload_includes_resolution_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from arnold.pipelines.megaplan.cli import _build_progress_payload
        import arnold.pipelines.megaplan.cli as cli_mod

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Set up .env", "phase": "before_execute", "blocks_task_ids": ["T1"]},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)
        upsert_user_action_resolution(tmp_path, "U1", "accepted_blocked", reason="ok", fallback_mode="mock")

        monkeypatch.setattr(cli_mod, "compute_global_batches", lambda fd: [["T1"], ["T2"]])
        monkeypatch.setattr(cli_mod, "list_batch_artifacts", lambda pd: [])

        state = {
            "name": "test", "current_state": "finalized", "iteration": 1,
            "idea": "Test idea.", "meta": {},
            "config": {"project_dir": str(tmp_path), "auto_approve": True, "mode": "code"},
            "history": [], "plan_versions": [{"file": "plan.md"}],
        }
        progress = _build_progress_payload(tmp_path, state)

        assert "blocked_tasks_detail" in progress
        assert "user_action_resolution_summary" in progress
        assert "recommended_action" in progress
        assert progress["recommended_action"] == "continue_with_fallback"
        assert progress["user_action_resolution_summary"]["total_resolutions"] == 1

    def test_global_before_execute_blockers_attached_to_pending_tasks(self, tmp_path: Path):
        from arnold.pipelines.megaplan.cli import _compute_user_action_blockers

        _write_finalize_json(tmp_path, user_actions=[
            {"id": "U1", "description": "Verify infrastructure", "phase": "before_execute"},
        ])
        _write_minimal_state(tmp_path, project_dir=tmp_path)

        tasks = [
            {"id": "T1", "description": "Do the thing", "depends_on": [], "status": "pending"},
            {"id": "T2", "description": "Do the other thing", "depends_on": ["T1"], "status": "pending"},
        ]
        finalize_data = conftest_read_json(tmp_path / "finalize.json")
        blockers = _compute_user_action_blockers(tmp_path, finalize_data, tasks)

        assert len(blockers["blocked_tasks_detail"]) == 2
        tids = [d["task_id"] for d in blockers["blocked_tasks_detail"]]
        assert "T1" in tids
        assert "T2" in tids
