from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.control_interface import (
    DECLARED_OVERRIDE_POLICY_TARGETS,
    apply_transition,
)
from arnold_pipelines.megaplan.handlers import override as override_handler
from arnold_pipelines.megaplan.handlers.override import handle_override
from arnold_pipelines.megaplan.planning.control_binding import (
    planning_control_binding,
    planning_run_state_view,
)
from arnold.control.interface import ControlTransition
from arnold_pipelines.megaplan.profiles import load_profile_metadata, load_profiles
from arnold_pipelines.megaplan.types import CliError


def _profile_digest(profile: str, project_dir: Path) -> str:
    profiles = load_profiles(project_dir=project_dir)
    metadata = load_profile_metadata(project_dir=project_dir)
    return hashlib.sha256(
        json.dumps(
            {
                "profile": profile,
                "phase_map": profiles[profile],
                "metadata": metadata.get(profile, {}),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


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


def test_blocked_iterate_gate_projects_replan_without_resume_cursor() -> None:
    state = {
        "name": "demo",
        "current_state": "blocked",
        "config": {},
        "last_gate": {"recommendation": "ITERATE", "passed": False},
        "meta": {},
    }

    targets = planning_control_binding().recover_targets(planning_run_state_view(state))

    assert [target.id for target in targets] == ["replan"]
    assert targets[0].metadata == {
        "kind": "workflow_step",
        "step": "replan",
        "direction": "recovery",
        "actionable": True,
        "target_state": "planned",
        "source": "last_gate.recommendation",
        "operator_action": "replan",
    }


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
        "load_profile_sources",
        lambda project_dir=None: [("project", "demo", {})],
    )
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
        "load_profile_sources",
        lambda project_dir=None: [("project", "demo", {})],
    )
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
    monkeypatch.setattr(
        profiles_module,
        "load_profile_sources",
        lambda project_dir=None: [("project", "demo", {})],
    )
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


def test_same_profile_refresh_rewrites_gated_plan_routing_without_touching_custody(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    cancellation = {
        "step": "finalize",
        "result": "cancelled",
        "attempt": 8,
        "phase_wbc_attempt_id": "attempt-8",
        "invocation_id": "invocation-8",
        "run_id": "run-8",
    }
    state = {
        "name": "demo",
        "current_state": "gated",
        "iteration": 2,
        "config": {
            "project_dir": str(tmp_path),
            "profile": "partnered-5-glm",
            "depth": "high",
            "phase_model": [
                "finalize=codex:gpt-5.6-sol:high",
                "execute=hermes:zhipu:glm-5.2",
            ],
            "tier_models": {
                "execute": {
                    str(tier): "hermes:deepseek:deepseek-v4-pro"
                    for tier in range(1, 11)
                }
            },
        },
        "history": [cancellation],
        "latest_failure": {"kind": "superseded_attempt", "phase": "finalize"},
        "meta": {"overrides": []},
        "_state_meta": {"versions": {"config": 0, "meta": 0}},
    }
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    chain_path = tmp_path / ".megaplan" / "plans" / ".chains" / "chain.json"
    chain_path.parent.mkdir(parents=True)
    chain_before = b'{"last_state":"paused","operator_pause":{"active":true}}\n'
    chain_path.write_bytes(chain_before)
    phase_wbc_path = plan_dir / ".phase_wbc_attempts.sqlite3"
    phase_wbc_before = b"immutable-attempt-8-ledger"
    phase_wbc_path.write_bytes(phase_wbc_before)
    transition = ControlTransition(
        op="override",
        target_id="set-profile",
        payload={
            "profile": "partnered-5-glm",
            "reason": "refresh persisted GLM-only Execute routing",
            "expected_profile_source": "built-in",
            "expected_profile_sha256": _profile_digest("partnered-5-glm", tmp_path),
        },
    )

    result = apply_transition(
        planning_run_state_view(state),
        transition,
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is True
    receipt = result.artifacts["profile_refresh_receipt"]
    assert receipt["same_profile_refresh"] is True
    assert receipt["profile_source"] == "built-in"
    assert receipt["profile_content_sha256"] == _profile_digest(
        "partnered-5-glm", tmp_path
    )
    assert len(receipt["profile_source_candidates"]) == 1
    assert receipt["profile_source_candidates"][0]["source"] == "built-in"
    assert len(receipt["profile_source_candidates"][0]["phase_map_sha256"]) == 64
    assert receipt["from_routing_sha256"] != receipt["to_routing_sha256"]
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    execute_tiers = persisted["config"]["tier_models"]["execute"]
    assert set(execute_tiers) == {str(tier) for tier in range(1, 11)}
    assert all(
        "glm" in json.dumps(spec).lower()
        and "deepseek" not in json.dumps(spec).lower()
        and "codex" not in json.dumps(spec).lower()
        for spec in execute_tiers.values()
    )
    assert "finalize=codex:gpt-5.6-sol:high" in persisted["config"]["phase_model"]
    assert "execute=hermes:zhipu:glm-5.2" in persisted["config"]["phase_model"]
    assert persisted["current_state"] == "gated"
    assert persisted["history"] == [cancellation]
    assert persisted["config"]["profile_binding"] == {
        "profile_source": "built-in",
        "profile_content_sha256": receipt["profile_content_sha256"],
    }
    assert "active_step" not in persisted
    override_receipt = persisted["meta"]["overrides"][-1]
    assert override_receipt["same_profile_refresh"] is True
    assert override_receipt["to_routing_sha256"] == receipt["to_routing_sha256"]
    assert chain_path.read_bytes() == chain_before
    assert phase_wbc_path.read_bytes() == phase_wbc_before

    stale = apply_transition(
        planning_run_state_view(state),
        transition,
        "megaplan",
        plan_dir=plan_dir,
    )
    assert stale.accepted is False
    assert stale.reason == "control_transition_conflict"
    assert stale.artifacts["conflict"]["key"] == "config"
    assert chain_path.read_bytes() == chain_before
    assert phase_wbc_path.read_bytes() == phase_wbc_before


def test_same_profile_refresh_rejects_project_shadow_of_built_in(
    tmp_path: Path,
) -> None:
    project_profile = tmp_path / ".megaplan" / "profiles.toml"
    project_profile.parent.mkdir(parents=True)
    project_profile.write_text(
        """
[profiles.partnered-5-glm]
plan = "hermes:deepseek:deepseek-v4-pro"
execute = "hermes:deepseek:deepseek-v4-pro"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    state = {
        "name": "demo",
        "current_state": "gated",
        "config": {
            "project_dir": str(tmp_path),
            "profile": "partnered-5-glm",
            "phase_model": ["execute=hermes:deepseek:deepseek-v4-pro"],
        },
        "meta": {"overrides": []},
        "_state_meta": {"versions": {"config": 0, "meta": 0}},
    }

    with pytest.raises(CliError) as exc_info:
        planning_control_binding().apply_transition(
            planning_run_state_view(state),
            ControlTransition(
                op="override",
                target_id="set-profile",
                payload={
                    "profile": "partnered-5-glm",
                    "expected_profile_source": "built-in",
                },
            ),
        )

    assert getattr(exc_info.value, "code", None) == "profile_source_mismatch"
    assert state["config"]["phase_model"] == [
        "execute=hermes:deepseek:deepseek-v4-pro"
    ]

def test_default_cli_same_profile_refresh_always_uses_cas_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "demo",
        "current_state": "gated",
        "iteration": 2,
        "config": {
            "project_dir": str(tmp_path),
            "profile": "partnered-5-glm",
            "depth": "high",
            "phase_model": [
                "finalize=codex:gpt-5.6-sol:high",
                "execute=hermes:zhipu:glm-5.2",
            ],
            "tier_models": {
                "execute": {
                    str(tier): "hermes:deepseek:deepseek-v4-pro"
                    for tier in range(1, 11)
                }
            },
        },
        "history": [],
        "meta": {"overrides": []},
        "_state_meta": {"versions": {"config": 0, "meta": 0}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.delenv("MEGAPLAN_CONTROL_INTERFACE_ROUTING", raising=False)
    monkeypatch.setattr(override_handler, "preflight_phase", lambda **_kwargs: None)

    response = handle_override(
        tmp_path,
        argparse.Namespace(
            plan="demo",
            override_action="set-profile",
            profile="partnered-5-glm",
            reason="refresh persisted GLM-only Execute routing",
            expected_profile_source="built-in",
            expected_profile_sha256=_profile_digest("partnered-5-glm", tmp_path),
        ),
    )

    receipt = response["profile_refresh_receipt"]
    assert receipt["same_profile_refresh"] is True
    assert receipt["profile_source"] == "built-in"
    assert receipt["profile_content_sha256"] == _profile_digest(
        "partnered-5-glm", tmp_path
    )
    assert receipt["from_routing_sha256"] != receipt["to_routing_sha256"]
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert all(
        "glm" in json.dumps(spec).lower()
        and "deepseek" not in json.dumps(spec).lower()
        and "codex" not in json.dumps(spec).lower()
        for spec in persisted["config"]["tier_models"]["execute"].values()
    )


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


def test_replan_transition_allows_blocked_iterate_gate(monkeypatch) -> None:
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
            payload={"plan_dir": str(Path.cwd()), "reason": "apply narrow gate fixes"},
        ),
    )

    assert result.accepted is True
    current_state_delta = next(delta for delta in result.state_deltas if delta.key == "current_state")
    meta_delta = next(delta for delta in result.state_deltas if delta.key == "meta")
    assert current_state_delta.value == "planned"
    assert meta_delta.value["overrides"][-1]["from_state"] == "blocked"


def test_replan_transition_rejects_unrelated_blocked_state() -> None:
    state = {
        "name": "demo",
        "current_state": "blocked",
        "config": {},
        "iteration": 1,
        "meta": {},
        "last_gate": {"recommendation": "PROCEED", "passed": False},
    }

    import pytest
    from arnold_pipelines.megaplan.types import CliError

    with pytest.raises(CliError, match="replan requires state"):
        planning_control_binding().apply_transition(
            planning_run_state_view(state),
            ControlTransition(
                op="override",
                target_id="replan",
                payload={"plan_dir": str(Path.cwd()), "reason": "unsafe bypass"},
            ),
        )
