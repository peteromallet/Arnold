from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.control_interface import DECLARED_OVERRIDE_POLICY_TARGETS
from arnold_pipelines.megaplan.planning.control_binding import (
    planning_control_binding,
    planning_run_state_view,
)
from arnold.control.interface import ControlTransition


def test_blocked_review_recovery_does_not_project_illegal_rerun() -> None:
    state = {
        "name": "demo",
        "current_state": "blocked",
        "config": {},
        "resume_cursor": {
            "phase": "review",
            "retry_strategy": "manual_review",
        },
        "latest_failure": {
            "kind": "blocked_recovery_not_resolved",
            "phase": "recover-blocked",
            "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
        },
    }

    binding = planning_control_binding()
    targets = binding.recover_targets(planning_run_state_view(state))

    assert [target.id for target in targets] == ["recover-blocked"]
    assert targets[0].metadata["target_ref"] == "recovery_predecessor"
    assert targets[0].metadata["policy_route_ref"] == "megaplan.override.recover_blocked"
    assert "target_state" not in targets[0].metadata


def test_resume_clarify_projection_uses_declared_policy_target() -> None:
    state = {
        "name": "demo",
        "current_state": "awaiting_human_verify",
        "config": {},
        "clarification": {"source": "prep"},
        "meta": {},
    }

    targets = planning_control_binding().recover_targets(planning_run_state_view(state))

    assert [target.id for target in targets] == ["resume-clarify"]
    assert targets[0].metadata["target_ref"] == "plan"
    assert targets[0].metadata["policy_route_ref"] == "megaplan.override.resume_clarify"
    assert targets[0].metadata["target_state"] == "prepped"


def test_control_interface_declares_native_policy_targets_without_cursor_authority() -> None:
    assert DECLARED_OVERRIDE_POLICY_TARGETS == {
        "adopt-execution": {
            "route_signal": "adopt_execution",
            "target_ref": "review",
            "policy_route_ref": "megaplan.override.adopt_execution",
        },
        "recover-blocked": {
            "route_signal": "recover_blocked",
            "target_ref": "recovery_predecessor",
            "policy_route_ref": "megaplan.override.recover_blocked",
        },
        "resume-clarify": {
            "route_signal": "resume_clarify",
            "target_ref": "plan",
            "policy_route_ref": "megaplan.override.resume_clarify",
        },
    }


def test_set_profile_preserves_encoded_phase_model_chains(monkeypatch) -> None:
    import arnold_pipelines.megaplan.profiles as profiles_module

    monkeypatch.setattr(profiles_module, "load_profiles", lambda project_dir=None: {"demo": {}})
    monkeypatch.setattr(
        profiles_module,
        "resolve_profile",
        lambda profile_name, profiles: {
            "plan": ["codex:gpt-5.5", "claude:claude-sonnet-4-6"],
            "execute": "codex:gpt-5.5",
        },
    )

    state = {
        "name": "demo",
        "current_state": "planned",
        "config": {"profile": "old", "project_dir": str(Path.cwd())},
        "meta": {},
    }

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(op="override", target_id="set-profile", payload={"profile": "demo"}),
    )

    assert result.accepted is True
    config_delta = next(delta for delta in result.state_deltas if delta.key == "config")
    assert config_delta.value["phase_model"] == [
        'plan=__fallback_json__:["codex:gpt-5.5","claude:claude-sonnet-4-6"]',
        "execute=codex:gpt-5.5",
    ]


def test_set_profile_clears_stale_vendor_for_non_premium_profile(monkeypatch) -> None:
    import arnold_pipelines.megaplan.profiles as profiles_module

    monkeypatch.setattr(profiles_module, "load_profiles", lambda project_dir=None: {"demo": {}})
    monkeypatch.setattr(
        profiles_module,
        "resolve_profile",
        lambda profile_name, profiles: {
            "plan": "hermes:deepseek:deepseek-v4-pro",
            "execute": "hermes:deepseek:deepseek-v4-pro",
        },
    )

    state = {
        "name": "demo",
        "current_state": "planned",
        "config": {
            "profile": "all-claude",
            "project_dir": str(Path.cwd()),
            "vendor": "claude",
        },
        "meta": {},
    }

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(op="override", target_id="set-profile", payload={"profile": "demo"}),
    )

    assert result.accepted is True
    config_delta = next(delta for delta in result.state_deltas if delta.key == "config")
    assert config_delta.value["phase_model"] == [
        "plan=hermes:deepseek:deepseek-v4-pro",
        "execute=hermes:deepseek:deepseek-v4-pro",
    ]
    assert "vendor" not in config_delta.value


def test_set_profile_rewrites_stale_prep_metadata_for_non_premium_profile(monkeypatch) -> None:
    import arnold_pipelines.megaplan.profiles as profiles_module

    monkeypatch.setattr(profiles_module, "load_profiles", lambda project_dir=None: {"demo": {}})
    monkeypatch.setattr(profiles_module, "load_profile_metadata", lambda project_dir=None: {"demo": {}})
    monkeypatch.setattr(
        profiles_module,
        "resolve_profile",
        lambda profile_name, profiles: {
            "plan": "hermes:deepseek:deepseek-v4-pro",
            "execute": "hermes:deepseek:deepseek-v4-pro",
        },
    )
    monkeypatch.setattr(
        profiles_module,
        "_resolve_prep_models_with_inheritance",
        lambda *args, **kwargs: {},
    )

    state = {
        "name": "demo",
        "current_state": "planned",
        "config": {
            "profile": "all-claude",
            "project_dir": str(Path.cwd()),
            "vendor": "claude",
            "prep_models": {
                "triage": "claude:claude-sonnet-4-6",
                "fanout": "claude:claude-sonnet-4-6",
                "distill": "claude:claude-sonnet-4-6",
            },
            "prep_model_resolver_trace": {
                "flat_prep_input": "claude",
                "explicit_prep_models": {"triage": "claude:claude-sonnet-4-6"},
                "resolved_stage_models": {"triage": "claude:claude-sonnet-4-6"},
                "canonical_fallback_used": {"triage": False},
            },
        },
        "meta": {},
    }

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(op="override", target_id="set-profile", payload={"profile": "demo"}),
    )

    assert result.accepted is True
    config_delta = next(delta for delta in result.state_deltas if delta.key == "config")
    assert config_delta.value["prep_models"] == {
        "triage": "hermes:deepseek:deepseek-v4-pro",
        "fanout": "hermes:deepseek:deepseek-v4-pro",
        "distill": "hermes:deepseek:deepseek-v4-pro",
    }
    assert config_delta.value["prep_model_resolver_trace"]["flat_prep_input"] is None
    assert config_delta.value["prep_model_resolver_trace"]["explicit_prep_models"] == {}


def test_set_model_replaces_encoded_chain_with_scalar_spec() -> None:
    state = {
        "name": "demo",
        "current_state": "planned",
        "config": {
            "phase_model": ['plan=__fallback_json__:["codex:gpt-5.5","claude:claude-sonnet-4-6"]'],
        },
        "meta": {},
    }

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="set-model",
            payload={"phase": "plan", "model": "claude-opus-4-7"},
        ),
    )

    assert result.accepted is True
    config_delta = next(delta for delta in result.state_deltas if delta.key == "config")
    assert config_delta.value["phase_model"] == ["plan=claude:claude-opus-4-7"]
    meta_delta = next(delta for delta in result.state_deltas if delta.key == "meta")
    override_entry = meta_delta.value["overrides"][-1]
    assert override_entry["previous_spec"] == '__fallback_json__:["codex:gpt-5.5","claude:claude-sonnet-4-6"]'
    assert override_entry["new_spec"] == "claude:claude-opus-4-7"


def test_replan_transition_clears_stale_loop_state_and_records_latest_plan(monkeypatch) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.planning.control_binding.latest_plan_path",
        lambda plan_dir, state: plan_dir / "plan_v4.md",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.planning.control_binding.now_utc",
        lambda: "2026-01-02T03:04:05Z",
    )

    state = {
        "name": "demo",
        "current_state": "failed",
        "config": {},
        "iteration": 4,
        "plan_versions": [
            {
                "version": 4,
                "file": "plan_v4.md",
                "hash": "sha256:plan",
                "timestamp": "2026-01-02T03:04:05Z",
            }
        ],
        "meta": {"tiebreaker_count": 2, "user_approved_gate": True},
        "last_gate": {"recommendation": "ITERATE"},
        "latest_failure": {"kind": "phase_failed"},
        "resume_cursor": {"phase": "execute", "retry_strategy": "fresh_session"},
        "active_step": {"phase": "execute"},
    }

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="replan",
            payload={
                "plan_dir": str(Path.cwd()),
                "reason": "reset loop",
                "note": "preserve current plan",
            },
        ),
    )

    assert result.accepted is True
    assert result.artifacts["plan_file"].endswith("plan_v4.md")
    assert result.artifacts["remove_state_keys"] == (
        "active_step",
        "latest_failure",
        "resume_cursor",
    )

    current_state_delta = next(delta for delta in result.state_deltas if delta.key == "current_state")
    last_gate_delta = next(delta for delta in result.state_deltas if delta.key == "last_gate")
    meta_delta = next(delta for delta in result.state_deltas if delta.key == "meta")

    assert current_state_delta.value == "planned"
    assert last_gate_delta.value == {}
    assert meta_delta.value["overrides"][-1]["from_state"] == "failed"
    assert meta_delta.value["overrides"][-1]["plan_file"] == "plan_v4.md"
    assert meta_delta.value["notes"][-1]["note"] == "preserve current plan"
    assert "tiebreaker_count" not in meta_delta.value
    assert "user_approved_gate" not in meta_delta.value


def test_replan_transition_accepts_blocked_gate_that_requested_iteration(monkeypatch) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.planning.control_binding.latest_plan_path",
        lambda plan_dir, state: plan_dir / "plan_v7.md",
    )
    state = {
        "name": "demo",
        "current_state": "blocked",
        "config": {},
        "iteration": 7,
        "plan_versions": [{"version": 7, "file": "plan_v7.md"}],
        "meta": {},
        "last_gate": {"recommendation": "ITERATE", "passed": False},
    }

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="replan",
            payload={"plan_dir": str(Path.cwd()), "reason": "repair gate findings"},
        ),
    )

    assert result.accepted is True
    state_delta = next(delta for delta in result.state_deltas if delta.key == "current_state")
    assert state_delta.value == "planned"
