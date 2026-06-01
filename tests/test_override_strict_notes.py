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
from pathlib import Path

import pytest

import megaplan
from megaplan._core import now_utc
from tests.conftest import PlanFixture, _make_plan_fixture_with_robustness, load_state


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
    # Set model for the critique phase (defaults to codex)
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
    assert any("critique=codex:gpt-5.3-codex:high" in pm for pm in phase_models), \
        f"Expected critique=codex:gpt-5.3-codex:high in {phase_models}"
    # Override meta entry is recorded
    overrides = state.get("meta", {}).get("overrides", [])
    model_overrides = [o for o in overrides if o.get("action") == "set-model"]
    assert len(model_overrides) >= 1
    latest = model_overrides[-1]
    assert latest["phase"] == "critique"
    assert latest["new_spec"] == "codex:gpt-5.3-codex:high"
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
    # First, set a phase_model entry that makes 'prep' use shannon
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-model",
            phase="prep",
            model="claude-opus-4-7",
            reason="make prep use claude first",
        ),
    )
    # Now directly write a shannon entry into phase_model to simulate a shannon phase
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
