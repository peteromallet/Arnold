"""Tests for the --strict-notes flag and its enforcement in override force-proceed.

Covers:
* Force-proceed rejects when an unabsorbed user note exists.
* Driver-attributed notes are not blocking.
* A revise consumes the note and unblocks force-proceed.
* When the last gate ESCALATEd, force-proceed requires --user-approved.
* With strict_notes off (default), behavior is unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan._core import now_utc, save_state
from arnold.pipelines.megaplan.orchestration.phase_result import BlockedTask, ExternalError
from arnold.pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN, STATE_PREPPED
from arnold.pipelines.megaplan.user_actions import build_resolution_event
from tests.conftest import PlanFixture, load_state
from tests.conftest import make_fake_phase_result


def _enable_strict_notes(plan_dir: Path) -> None:
    state = load_state(plan_dir)
    state["config"]["strict_notes"] = True
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _last_gate(state: dict, recommendation: str) -> dict:
    state["last_gate"] = {"recommendation": recommendation}
    return state


def _force_proceed_args(plan_fixture: PlanFixture, **overrides: object):
    return plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        override_action="force-proceed",
        reason="test",
        **overrides,
    )


def _drive_to_critiqued(plan_fixture: PlanFixture) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))


def test_force_proceed_rejects_unabsorbed_user_note(plan_fixture: PlanFixture) -> None:
    _drive_to_critiqued(plan_fixture)
    _enable_strict_notes(plan_fixture.plan_dir)

    # Attach a user-source note (the override default).
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="reconsider the deployment story",
        ),
    )

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(plan_fixture.root, _force_proceed_args(plan_fixture))
    assert excinfo.value.code == "unabsorbed_notes_exist"


def test_force_proceed_allows_driver_note(plan_fixture: PlanFixture) -> None:
    _drive_to_critiqued(plan_fixture)
    _enable_strict_notes(plan_fixture.plan_dir)

    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="audit-trail breadcrumb from the auto driver",
            source="driver",
        ),
    )

    response = megaplan.handle_override(
        plan_fixture.root, _force_proceed_args(plan_fixture)
    )
    assert response["state"] == megaplan.STATE_GATED


def test_force_proceed_after_revise_consumes_note(plan_fixture: PlanFixture) -> None:
    """A user note attached then absorbed by a revise should not block force-proceed."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    # Attach a note while critiqued, then run revise (consumes the note),
    # critique again to land back at critiqued, then force-proceed.
    megaplan.handle_override(
        plan_fixture.root,
        make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="please tighten the rollback plan",
        ),
    )
    # Need an ITERATE gate so revise transitions cleanly. Run gate first.
    megaplan.handle_gate(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_revise(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    _enable_strict_notes(plan_fixture.plan_dir)

    response = megaplan.handle_override(
        plan_fixture.root, _force_proceed_args(plan_fixture)
    )
    assert response["state"] == megaplan.STATE_GATED


def test_force_proceed_post_escalate_requires_user_approved(plan_fixture: PlanFixture) -> None:
    _drive_to_critiqued(plan_fixture)

    # Patch in last_gate=ESCALATE and turn strict on.
    state = load_state(plan_fixture.plan_dir)
    state["config"]["strict_notes"] = True
    state["last_gate"] = {"recommendation": "ESCALATE"}
    (plan_fixture.plan_dir / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(plan_fixture.root, _force_proceed_args(plan_fixture))
    assert excinfo.value.code == "escalate_requires_user_approval"

    # With --user-approved, the same call must succeed.
    response = megaplan.handle_override(
        plan_fixture.root, _force_proceed_args(plan_fixture, user_approved=True)
    )
    assert response["state"] == megaplan.STATE_GATED


def test_force_proceed_off_default_unchanged(plan_fixture: PlanFixture) -> None:
    """Regression guard: with strict_notes=False (default), the historical
    flow still allows force-proceed past a user note + ESCALATE gate."""
    _drive_to_critiqued(plan_fixture)

    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="user concern",
        ),
    )
    state = load_state(plan_fixture.plan_dir)
    state["last_gate"] = {"recommendation": "ESCALATE"}
    (plan_fixture.plan_dir / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    # Default fixture is strict_notes-unset (code mode default = off).
    response = megaplan.handle_override(
        plan_fixture.root, _force_proceed_args(plan_fixture)
    )
    assert response["state"] == megaplan.STATE_GATED


# ---------------------------------------------------------------------------
# Override set-model round-trip tests (T13)
# ---------------------------------------------------------------------------


def test_set_model_round_trip_persists_phase_model(plan_fixture: PlanFixture) -> None:
    """set-model writes state.config.phase_model and a subsequent read sees the new spec."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    # Set model for the critique phase; the implicit premium default now
    # resolves through the effective vendor before persistence.
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-model",
            phase="critique",
            model="gpt-5.3-codex",
            effort="high",
            reason="test set-model round trip",
        ),
    )
    assert response["success"] is True
    assert response["phase"] == "critique"
    assert "gpt-5.3-codex" in response["new_spec"]
    assert "high" in response["new_spec"]
    # Read back state and confirm phase_model is persisted
    state = load_state(plan_fixture.plan_dir)
    phase_models = state["config"].get("phase_model") or []
    assert any("critique=claude:gpt-5.3-codex:high" in pm for pm in phase_models), \
        f"Expected critique=claude:gpt-5.3-codex:high in {phase_models}"
    # Override meta entry is recorded
    overrides = state.get("meta", {}).get("overrides", [])
    model_overrides = [o for o in overrides if o.get("action") == "set-model"]
    assert len(model_overrides) >= 1
    latest = model_overrides[-1]
    assert latest["phase"] == "critique"
    assert latest["new_spec"] == "claude:gpt-5.3-codex:high"
    assert latest["reason"] == "test set-model round trip"


def test_set_model_accepts_full_premium_agent_spec(plan_fixture: PlanFixture) -> None:
    """set-model can switch premium vendors when --model is a full agent spec."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-model",
            phase="critique",
            model="claude:sonnet",
            reason="switch critic vendor",
        ),
    )

    assert response["success"] is True
    assert response["new_spec"] == "claude:sonnet"
    state = load_state(plan_fixture.plan_dir)
    assert "critique=claude:sonnet" in (state["config"].get("phase_model") or [])
    assert "critique=codex:claude:sonnet" not in (state["config"].get("phase_model") or [])


def test_set_model_removes_matching_execute_tier_map(plan_fixture: PlanFixture) -> None:
    """A phase pin must be authoritative over batched execute tier routing."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["config"]["tier_models"] = {
        "execute": {
            "1": "hermes:deepseek:deepseek-v4-flash",
            "2": "hermes:deepseek:deepseek-v4-pro",
            "4": "codex:gpt-5.4",
        },
        "critique": {
            "1": "hermes:deepseek:deepseek-v4-flash",
        },
    }
    save_state(plan_fixture.plan_dir, state)

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-model",
            phase="execute",
            model="codex:gpt-5.5",
            reason="pin execute to codex",
        ),
    )

    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    assert "execute=codex:gpt-5.5" in (state["config"].get("phase_model") or [])
    assert "execute" not in state["config"]["tier_models"]
    assert "critique" in state["config"]["tier_models"]


def test_set_model_uses_concrete_default_vendor_for_unpinned_premium_phase(
    plan_fixture: PlanFixture,
) -> None:
    """set-model should resolve symbolic defaults before inferring the phase agent."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-model",
            phase="plan",
            model="claude-opus-4-7",
            reason="pin default premium phase",
        ),
    )

    assert response["success"] is True
    assert response["new_spec"] == "claude:claude-opus-4-7"
    state = load_state(plan_fixture.plan_dir)
    assert "plan=claude:claude-opus-4-7" in (state["config"].get("phase_model") or [])


def test_set_model_infers_codex_from_profile_vendor_expansion(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    root, project_dir = bootstrap_fixture
    args = make_args_factory(project_dir)
    init_response = megaplan.handle_init(root, args(vendor="codex"))
    plan_name = init_response["plan"]
    plan_dir = megaplan.plans_root(root) / plan_name

    megaplan.handle_plan(root, args(plan=plan_name))

    response = megaplan.handle_override(
        root,
        args(
            plan=plan_name,
            override_action="set-model",
            phase="plan",
            model="gpt-5.5",
            reason="pin codex vendor plan phase",
        ),
    )

    assert response["success"] is True
    assert response["new_spec"] == "codex:gpt-5.5"
    state = load_state(plan_dir)
    assert "plan=codex:gpt-5.5" in (state["config"].get("phase_model") or [])


def test_set_model_rejects_non_premium_full_agent_spec(plan_fixture: PlanFixture) -> None:
    """set-model is for claude/codex specs, not hermes or shannon model strings."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-model",
                phase="critique",
                model="hermes:deepseek:deepseek-v4-pro",
                reason="should use phase-model instead",
            ),
        )

    assert excinfo.value.code == "invalid_args"
    assert "claude/codex" in excinfo.value.message


def test_set_model_rejects_shannon_phase(plan_fixture: PlanFixture) -> None:
    """set-model rejects phases inferred as shannon via phase_model override."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    # Directly write a shannon entry into phase_model to simulate a shannon phase
    state = load_state(plan_fixture.plan_dir)
    state["config"]["phase_model"] = ["prep=shannon"]
    import json
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    # Now set-model on the shannon-inferred prep phase should fail
    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-model",
                phase="prep",
                model="claude-opus-4-7",
                reason="should fail for shannon phase",
            ),
        )
    assert excinfo.value.code == "invalid_args"
    assert "shannon" in str(excinfo.value.message).lower() or "only supported for claude/codex" in str(excinfo.value.message).lower()


def test_set_model_rejects_hermes_phase(plan_fixture: PlanFixture) -> None:
    """set-model rejects phases inferred as hermes via phase_model override."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    # Directly write a hermes entry into phase_model to simulate a hermes phase
    state = load_state(plan_fixture.plan_dir)
    state["config"]["phase_model"] = ["feedback=hermes:openai/gpt-5"]
    import json
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-model",
                phase="feedback",
                model="some-model",
                reason="should fail for hermes phase",
            ),
        )
    assert excinfo.value.code == "invalid_args"
    assert "hermes" in str(excinfo.value.message).lower() or "only supported for claude/codex" in str(excinfo.value.message).lower()


def test_set_model_rejects_reserved_effort_token_as_model(plan_fixture: PlanFixture) -> None:
    """set-model --model cannot be a reserved effort token like 'high'."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-model",
                phase="plan",
                model="low",  # reserved effort token
                reason="should fail",
            ),
        )
    assert excinfo.value.code == "invalid_args"
    assert "effort token" in str(excinfo.value.message).lower() or "reserved" in str(excinfo.value.message).lower()


def test_set_model_rejects_vendor_token_as_model(plan_fixture: PlanFixture) -> None:
    """set-model --model codex is an agent/vendor token, not a concrete model."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-model",
                phase="critique",
                model="codex",
                effort="high",
                reason="should use set-vendor instead",
            ),
        )

    assert excinfo.value.code == "invalid_args"
    assert "names an agent" in excinfo.value.message
    state = load_state(plan_fixture.plan_dir)
    assert "critique=codex:codex:high" not in (state["config"].get("phase_model") or [])


def _capture_override_events(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    def _emit(kind: str, *, plan_dir: Path, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        event = {"kind": kind, "payload": payload, **kwargs}
        events.append(event)
        return event

    monkeypatch.setattr("arnold.pipelines.megaplan.observability.events.emit", _emit)
    return events


def _latest_override(state: dict[str, Any], action: str) -> dict[str, Any]:
    overrides = state.get("meta", {}).get("overrides", [])
    matches = [entry for entry in overrides if entry.get("action") == action]
    assert matches, f"expected at least one {action!r} override entry"
    return matches[-1]


def _write_state(plan_dir: Path, state: dict[str, Any]) -> None:
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _write_finalize_with_user_action_gate(plan_dir: Path) -> None:
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "gate",
                        "description": "Verify before_execute prerequisites",
                        "depends_on": [],
                        "status": "pending",
                    },
                    {
                        "id": "T1",
                        "description": "Task 1",
                        "depends_on": ["gate"],
                        "status": "pending",
                    },
                ],
                "user_actions": [
                    {
                        "id": "ua_legacy",
                        "description": "Approve deployment",
                        "phase": "before_execute",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_override_actions_registry_excludes_engine_drift_commands() -> None:
    from arnold.pipelines.megaplan.cli.parser import build_parser
    from arnold.pipelines.megaplan.planning.operations import override_catalog

    assert set(megaplan.handlers.override._OVERRIDE_ACTIONS) == {
        "add-note",
        "abort",
        "adopt-execution",
        "force-proceed",
        "replan",
        "recover-blocked",
        "resume-clarify",
        "set-robustness",
        "set-profile",
        "set-model",
        "set-vendor",
    }
    assert len(megaplan.handlers.override._OVERRIDE_ACTIONS) == 11
    catalog = override_catalog()
    removed_overlap_action = "waive-" + "engine-" + "overlap"
    removed_refresh_action = "refresh-" + "engine-pin"
    assert removed_overlap_action not in catalog
    assert removed_refresh_action not in catalog
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["override", removed_overlap_action, "--reason", "test"])
    with pytest.raises(SystemExit):
        parser.parse_args(["override", removed_refresh_action, "--reason", "test"])


def test_other_override_actions_unchanged_add_note(plan_fixture: PlanFixture) -> None:
    """add-note still works exactly as before."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="a user observation",
        ),
    )
    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    notes = state.get("meta", {}).get("notes", [])
    assert any("a user observation" in n.get("note", "") for n in notes)


def test_other_override_actions_unchanged_force_proceed(plan_fixture: PlanFixture) -> None:
    """force-proceed still works as before."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="integration test",
        ),
    )
    assert response["success"] is True


def test_other_override_actions_unchanged_replan(plan_fixture: PlanFixture) -> None:
    """replan still works as before."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="replan",
            reason="need to restructure",
        ),
    )
    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    overrides = state.get("meta", {}).get("overrides", [])
    assert any(o.get("action") == "replan" for o in overrides)


def test_legacy_force_proceed_writes_gate_artifact_and_preserves_strict_notes(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _drive_to_critiqued(plan_fixture)
    _enable_strict_notes(plan_fixture.plan_dir)
    events = _capture_override_events(monkeypatch)

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="operator accepted gate risk",
        ),
    )

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_GATED
    assert response["next_step"] == "finalize"
    assert response["orchestrator_guidance"] == (
        "Force-proceed override applied. Proceed to finalize."
    )
    gate = json.loads((plan_fixture.plan_dir / "gate.json").read_text(encoding="utf-8"))
    assert gate["recommendation"] == "PROCEED"
    assert gate["override_forced"] is True
    assert gate["rationale"] == "operator accepted gate risk"
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == megaplan.STATE_GATED
    assert state["last_gate"] == {}
    assert _latest_override(state, "force-proceed")["reason"] == "operator accepted gate risk"
    assert events[-1:] == [
        {
            "kind": "override_applied",
            "payload": {
                "action": "force-proceed",
                "reason": "operator accepted gate risk",
            },
        }
    ]


def test_legacy_force_proceed_strict_notes_still_rejects_unabsorbed_note(
    plan_fixture: PlanFixture,
) -> None:
    _drive_to_critiqued(plan_fixture)
    _enable_strict_notes(plan_fixture.plan_dir)
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="operator added a blocking concern",
        ),
    )

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="force-proceed",
                reason="try anyway",
            ),
        )

    assert excinfo.value.code == "unabsorbed_notes_exist"
    assert "run revise (or replan / step-edit) before force-proceed" in excinfo.value.message


def test_legacy_replan_absorbs_notes_and_records_transition_event(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _drive_to_critiqued(plan_fixture)
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="add-note",
            note="rework the deployment structure",
        ),
    )
    events = _capture_override_events(monkeypatch)

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="replan",
            reason="legacy replan transition",
            note="carry this into replanning",
        ),
    )

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_PLANNED
    assert response["next_step"] == "critique"
    assert response["plan_file"].endswith(".md")
    assert "Edit " in response["message"]
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == megaplan.STATE_PLANNED
    assert state["last_gate"] == {}
    assert any(note.get("note") == "carry this into replanning" for note in state["meta"]["notes"])
    latest = _latest_override(state, "replan")
    assert latest["reason"] == "legacy replan transition"
    assert events == [
        {
            "kind": "override_applied",
            "payload": {"action": "replan", "reason": "legacy replan transition"},
        }
    ]


def test_legacy_recover_blocked_parses_phase_result_and_restores_execute_predecessor(
    plan_fixture: PlanFixture,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = megaplan.STATE_BLOCKED
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {"kind": "execution_blocked"}
    state["meta"]["user_action_resolutions"] = [
        build_resolution_event(
            action_id="ua_legacy",
            resolution="satisfied",
            tasks=["gate"],
            reason="operator completed legacy gate",
        )
    ]
    _write_state(plan_fixture.plan_dir, state)
    _write_finalize_with_user_action_gate(plan_fixture.plan_dir)
    make_fake_phase_result(
        plan_fixture.plan_dir,
        exit_kind="blocked_by_prereq",
        blocked_tasks=(
            BlockedTask(task_id="gate", reason="before_execute action is unresolved"),
        ),
    )

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="recover-blocked",
            reason="operator resolved blocker",
        ),
    )

    assert response["success"] is True
    assert response["action"] == "recover-blocked"
    assert response["previous_state"] == megaplan.STATE_BLOCKED
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["phase"] == "execute"
    assert response["next_step"] == "execute"
    assert response["resume_cursor"] == {"phase": "execute", "retry_strategy": "fresh_session"}
    assert [blocker["blocker_id"] for blocker in response["blockers"]] == [
        "prereq:ua_legacy:gate"
    ]
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == megaplan.STATE_FINALIZED
    assert "latest_failure" not in state
    assert "active_step" not in state
    latest = _latest_override(state, "recover-blocked")
    assert latest["from_state"] == megaplan.STATE_BLOCKED
    assert latest["to_state"] == megaplan.STATE_FINALIZED
    assert latest["resume_cursor"] == {"phase": "execute", "retry_strategy": "fresh_session"}
    assert latest["blocker_ids"] == ["prereq:ua_legacy:gate"]


def test_legacy_recover_blocked_external_error_requires_resume_message(
    plan_fixture: PlanFixture,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = megaplan.STATE_BLOCKED
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "wait_and_retry"}
    state["latest_failure"] = {"kind": "external_error", "phase": "execute"}
    _write_state(plan_fixture.plan_dir, state)
    _write_finalize_with_user_action_gate(plan_fixture.plan_dir)
    make_fake_phase_result(
        plan_fixture.plan_dir,
        exit_kind="external_error",
        external_error=ExternalError(
            provider="deepseek",
            error_kind="rate_limit",
            message="429 Too Many Requests",
        ),
    )

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="recover-blocked",
                reason="try blocker recovery",
            ),
        )

    assert excinfo.value.code == "external_error_resume_required"
    assert "fix provider/profile settings if needed" in excinfo.value.message
    assert excinfo.value.extra["phase_result_exit_kind"] == "external_error"
    assert excinfo.value.extra["resume_command"] == (
        f"megaplan resume --plan {plan_fixture.plan_name}"
    )
    assert load_state(plan_fixture.plan_dir)["current_state"] == megaplan.STATE_BLOCKED


def test_legacy_resume_clarify_discriminates_prep_from_verify(
    plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = STATE_AWAITING_HUMAN
    state["clarification"] = {
        "intent_summary": "Prep needs a human answer.",
        "questions": ["Which auth library?"],
        "source": "prep",
    }
    state["meta"]["notes"].append(
        {"timestamp": now_utc(), "note": "Use platform auth.", "source": "user"}
    )
    _write_state(plan_fixture.plan_dir, state)
    events = _capture_override_events(monkeypatch)

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="resume-clarify",
        ),
    )

    assert response["success"] is True
    assert response["state"] == STATE_PREPPED
    assert response["next_step"] == "plan"
    assert "warnings" not in response
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == STATE_PREPPED
    assert _latest_override(state, "resume-clarify")["action"] == "resume-clarify"
    assert events == [
        {"kind": "override_applied", "payload": {"action": "resume-clarify"}}
    ]

    state["current_state"] = STATE_AWAITING_HUMAN
    state["clarification"] = {
        "intent_summary": "Criteria verification needed.",
        "questions": ["Is this sufficient?"],
        "source": "criteria",
    }
    _write_state(plan_fixture.plan_dir, state)

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="resume-clarify",
            ),
        )

    assert excinfo.value.code == "invalid_transition"
    assert "use verify-human for criteria-verification awaiting_human states" in (
        excinfo.value.message
    )


def test_other_override_actions_unchanged_set_robustness(plan_fixture: PlanFixture) -> None:
    """set-robustness still works as before."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-robustness",
            robustness="full",
            reason="increase robustness",
        ),
    )
    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    assert state["config"].get("robustness") == "full"


def test_other_override_actions_unchanged_set_profile(plan_fixture: PlanFixture) -> None:
    """set-profile still works as before."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-profile",
            profile="all-deepseek-pro",
            reason="switch profile",
        ),
    )
    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    assert state["config"].get("profile") == "all-deepseek-pro"


def test_set_profile_persists_concrete_phase_models(plan_fixture: PlanFixture) -> None:
    """Symbolic premium profile entries are resolved before persistence."""
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["config"]["vendor"] = "codex"
    state["config"]["depth"] = "high"
    save_state(plan_fixture.plan_dir, state)

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-profile",
            profile="premium",
            reason="switch to symbolic premium",
        ),
    )

    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    phase_models = state["config"].get("phase_model") or []
    assert phase_models
    assert all("premium" not in spec for spec in phase_models)
    assert any(spec.startswith("critique=codex:") for spec in phase_models)
    assert state["config"]["vendor"] == "codex"


@pytest.mark.parametrize(
    ("name", "invoke", "expected_events"),
    [
        (
            "add-note",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="add-note",
                note="legacy path note",
            ),
            [
                {"kind": "override_applied", "payload": {"action": "add-note", "reason": "legacy path note", "source": "user"}},
                {"kind": "note_added", "payload": {"note": "legacy path note", "source": "user"}},
            ],
        ),
        (
            "abort",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="abort",
                reason="legacy abort",
            ),
            [
                {"kind": "override_applied", "payload": {"action": "abort", "reason": "legacy abort"}},
            ],
        ),
        (
            "set-robustness",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-robustness",
                robustness="full",
                reason="legacy robustness",
            ),
            [
                {"kind": "override_applied", "payload": {"action": "set-robustness", "from": "full", "to": "full", "reason": "legacy robustness"}},
            ],
        ),
        (
            "set-profile",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-profile",
                profile="all-deepseek-pro",
                reason="legacy profile",
            ),
            [
                {"kind": "override_applied", "payload": {"action": "set-profile", "from": None, "to": "all-deepseek-pro", "reason": "legacy profile"}},
            ],
        ),
        (
            "set-model",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-model",
                phase="critique",
                model="gpt-5.3-codex",
                effort="high",
                reason="legacy model",
            ),
            [],
        ),
        (
            "set-vendor",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-vendor",
                phase="critique",
                vendor="claude",
                reason="legacy vendor",
            ),
            [],
        ),
    ],
)
def test_legacy_override_actions_characterization(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    invoke: Callable[[PlanFixture], Any],
    expected_events: list[dict[str, Any]],
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    before = load_state(plan_fixture.plan_dir)
    events = _capture_override_events(monkeypatch)

    response = megaplan.handle_override(plan_fixture.root, invoke(plan_fixture))
    state = load_state(plan_fixture.plan_dir)

    if name == "add-note":
        assert response["success"] is True
        assert response["step"] == "override"
        assert response["summary"] == "Attached note to the plan."
        assert response["state"] == megaplan.STATE_PLANNED
        assert response["next_step"] == "critique"
        assert any(
            note.get("note") == "legacy path note" and note.get("source") == "user"
            for note in state.get("meta", {}).get("notes", [])
        )
        latest = _latest_override(state, "add-note")
        assert latest["note"] == "legacy path note"
        assert latest["source"] == "user"
    elif name == "abort":
        assert response == {
            "success": True,
            "step": "override",
            "summary": "Plan aborted.",
            "next_step": None,
            "state": megaplan.STATE_ABORTED,
        }
        assert state["current_state"] == megaplan.STATE_ABORTED
        assert _latest_override(state, "abort")["reason"] == "legacy abort"
    elif name == "set-robustness":
        assert response["success"] is True
        assert response["state"] == megaplan.STATE_PLANNED
        assert response["previous_robustness"] == before["config"]["robustness"]
        assert response["robustness"] == "full"
        assert response["next_step"] == "critique"
        assert state["config"]["robustness"] == "full"
        latest = _latest_override(state, "set-robustness")
        assert latest["from"] == before["config"]["robustness"]
        assert latest["to"] == "full"
        assert latest["reason"] == "legacy robustness"
    elif name == "set-profile":
        assert response["success"] is True
        assert response["state"] == megaplan.STATE_PLANNED
        assert response["previous_profile"] is None
        assert response["profile"] == "all-deepseek-pro"
        assert response["next_step"] == "critique"
        assert state["config"]["profile"] == "all-deepseek-pro"
        assert state["config"]["phase_model"]
        latest = _latest_override(state, "set-profile")
        assert latest["from"] is None
        assert latest["to"] == "all-deepseek-pro"
        assert latest["reason"] == "legacy profile"
    elif name == "set-model":
        assert response["success"] is True
        assert response["state"] == megaplan.STATE_PLANNED
        assert response["phase"] == "critique"
        assert response["previous_spec"] == "claude"
        assert response["new_spec"] == "codex:gpt-5.3-codex:high"
        assert response["next_step"] == "critique"
        assert "critique=codex:gpt-5.3-codex:high" in (state["config"].get("phase_model") or [])
        latest = _latest_override(state, "set-model")
        assert latest["phase"] == "critique"
        assert latest["previous_spec"] == "claude"
        assert latest["new_spec"] == "codex:gpt-5.3-codex:high"
        assert latest["reason"] == "legacy model"
    elif name == "set-vendor":
        assert response["success"] is True
        assert response["state"] == megaplan.STATE_PLANNED
        assert response["phase"] == "critique"
        assert response["previous_spec"] == "claude"
        assert response["new_spec"] == "claude"
        assert response["next_step"] == "critique"
        assert "critique=claude" in (state["config"].get("phase_model") or [])
        latest = _latest_override(state, "set-vendor")
        assert latest["phase"] == "critique"
        assert latest["previous_spec"] == "claude"
        assert latest["new_spec"] == "claude"
        assert latest["reason"] == "legacy vendor"
    else:
        raise AssertionError(f"Unhandled characterization case: {name}")

    assert events == expected_events, f"{name} emitted unexpected events"
