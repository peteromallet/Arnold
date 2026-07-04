from __future__ import annotations

from pathlib import Path

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
