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
