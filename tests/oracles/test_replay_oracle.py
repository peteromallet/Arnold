from __future__ import annotations

from pathlib import Path
import json

import pytest

import arnold_pipelines.megaplan as megaplan
from arnold_pipelines.megaplan.handlers import override as override_handler
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.blocker_recovery import quality_blocker_id
from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation
from arnold_pipelines.megaplan.quality_resolutions import build_quality_resolution_event
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN
from arnold_pipelines.megaplan.user_actions import build_resolution_event
from tests.conftest import PlanFixture, load_state, make_fake_phase_result
from tests.oracles.replay_oracle import (
    assert_replay_parity,
    capture_legacy_action,
    capture_routed_action,
)


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


def _prepare_recoverable_prereq_blocked(fixture: PlanFixture, *, retry_budget: int = 2) -> None:
    megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
    state = load_state(fixture.plan_dir)
    state["current_state"] = megaplan.STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "fresh_session",
        "retry_budget": retry_budget,
    }
    state["latest_failure"] = {
        "kind": "execution_blocked",
        "blocked_retries_used": 1,
        "max_blocked_retries": retry_budget,
    }
    state["meta"]["user_action_resolutions"] = [
        build_resolution_event(
            action_id="ua_legacy",
            resolution="satisfied",
            tasks=["gate"],
            reason="operator completed gate",
        )
    ]
    write_plan_state(fixture.plan_dir, mode="replace", state=state)
    _write_finalize_with_user_action_gate(fixture.plan_dir)
    make_fake_phase_result(
        fixture.plan_dir,
        exit_kind="blocked_by_prereq",
        blocked_tasks=(
            BlockedTask(task_id="gate", reason="before_execute action is unresolved"),
        ),
    )


def _prepare_recoverable_quality_blocked(fixture: PlanFixture) -> None:
    megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
    deviation = Deviation(
        kind="quality",
        message="Quality check needs human acceptance",
        task_id="T1",
        phase="critique",
    )
    blocker_id = quality_blocker_id(deviation)
    state = load_state(fixture.plan_dir)
    state["current_state"] = megaplan.STATE_BLOCKED
    state["resume_cursor"] = {"phase": "critique", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {"kind": "quality_blocked", "phase": "critique"}
    state["meta"]["quality_gate_resolutions"] = [
        build_quality_resolution_event(
            blocker_id=blocker_id,
            resolution="accepted_with_debt",
            phase="critique",
            evidence=["operator reviewed the quality deviation"],
            debt_note="accepted as non-terminal for replay parity",
        )
    ]
    write_plan_state(fixture.plan_dir, mode="replace", state=state)
    make_fake_phase_result(
        fixture.plan_dir,
        phase="critique",
        exit_kind="blocked_by_quality",
        deviations=(deviation,),
    )


@pytest.mark.replay_oracle
def test_replay_oracle_captures_legacy_action_without_requiring_routed_parity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="add-note",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="add-note",
            note="legacy oracle note",
        ),
    )

    assert legacy.accepted is True
    assert legacy.exception is None
    assert legacy.response["success"] is True
    assert legacy.response["step"] == "override"
    assert legacy.response["summary"] == "Attached note to the plan."
    assert legacy.response["state"] == megaplan.STATE_PLANNED
    assert legacy.response["next_step"] == "critique"
    assert legacy.response["next_step_runtime"]["recommended_next_check_seconds"] == 120
    assert legacy.events == (
        {
            "kind": "override_applied",
            "payload": {
                "action": "add-note",
                "reason": "legacy oracle note",
                "source": "user",
            },
        },
        {
            "kind": "note_added",
            "payload": {"note": "legacy oracle note", "source": "user"},
        },
    )
    assert legacy.state["meta"]["notes"][-1]["note"] == "legacy oracle note"

    assert_replay_parity(legacy=legacy, routed=None)


@pytest.mark.replay_oracle
def test_replay_oracle_captures_legacy_artifacts_for_later_routed_assertions(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )

    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="operator accepted oracle gate risk",
        ),
        artifact_names=("gate.json",),
    )

    assert legacy.accepted is True
    assert legacy.response["state"] == megaplan.STATE_GATED
    assert legacy.response["next_step"] == "finalize"
    assert legacy.artifacts["gate.json"]["recommendation"] == "PROCEED"
    assert legacy.artifacts["gate.json"]["override_forced"] is True
    assert legacy.events[0]["kind"] == "artifact_written"
    assert legacy.events[0]["payload"]["path"].endswith("/gate.json")
    assert legacy.events[0]["payload"]["size_bytes"] > 0
    assert legacy.events[1:] == (
        {
            "kind": "override_applied",
            "payload": {
                "action": "force-proceed",
                "reason": "operator accepted oracle gate risk",
            },
        },
    )

    assert_replay_parity(legacy=legacy, routed=None)


@pytest.mark.replay_oracle
@pytest.mark.parametrize(
    ("action", "invoke"),
    [
        (
            "add-note",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="add-note",
                note="routed oracle note",
            ),
        ),
        (
            "abort",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="abort",
                reason="operator abort reason",
            ),
        ),
        (
            "set-robustness",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-robustness",
                robustness="robust",
                reason="operator raised robustness",
            ),
        ),
        (
            "set-profile",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-profile",
                profile="all-deepseek-pro",
                reason="operator switched profile",
            ),
        ),
        (
            "set-model",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-model",
                phase="critique",
                model="gpt-5.3-codex",
                effort="high",
                reason="operator repinned model",
            ),
        ),
        (
            "set-vendor",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-vendor",
                phase="critique",
                vendor="claude",
                reason="operator swapped vendor",
            ),
        ),
    ],
)
def test_routed_simple_actions_match_legacy_replay_oracle(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    action,
    invoke,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    frozen_now = "2026-01-02T03:04:05Z"
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)

    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action=action,
        invoke=invoke,
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / f"routed-{action}"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    megaplan.handle_plan(
        fresh_fixture.root,
        fresh_fixture.make_args(plan=fresh_fixture.plan_name),
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)

    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action=action,
        invoke=lambda fixture: invoke(fixture),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_force_proceed_from_critiqued_matches_legacy_gate_artifact(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="operator accepted routed gate risk",
        ),
        artifact_names=("gate.json",),
    )
    legacy_gate_bytes = (plan_fixture.plan_dir / "gate.json").read_bytes()

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-force-proceed-critiqued"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    megaplan.handle_plan(fresh_fixture.root, fresh_fixture.make_args(plan=fresh_fixture.plan_name))
    megaplan.handle_critique(fresh_fixture.root, fresh_fixture.make_args(plan=fresh_fixture.plan_name))

    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="operator accepted routed gate risk",
        ),
        artifact_names=("gate.json",),
    )
    routed_gate_bytes = (fresh_fixture.plan_dir / "gate.json").read_bytes()

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "artifacts"),
    )
    assert routed_gate_bytes == legacy_gate_bytes
    assert routed.events[0]["kind"] == "artifact_written"
    assert routed.events[0]["payload"]["path"].endswith("/gate.json")
    assert routed.events[0]["payload"]["size_bytes"] == legacy.events[0]["payload"]["size_bytes"]
    assert routed.events[1:] == legacy.events[1:]


@pytest.mark.replay_oracle
def test_routed_force_proceed_from_blocked_agent_availability_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_blocked(fixture: PlanFixture) -> None:
        megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        megaplan.handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["current_state"] = megaplan.STATE_BLOCKED
        state["last_gate"] = {
            "recommendation": "PROCEED",
            "passed": False,
            "preflight_results": {
                "project_dir_exists": True,
                "project_dir_writable": True,
                "success_criteria_present": True,
                "claude_available": False,
                "codex_available": False,
            },
        }
        write_plan_state(fixture.plan_dir, mode="replace", state=state)

    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_blocked(plan_fixture)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="agent availability was repaired",
        ),
        artifact_names=("gate.json",),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-force-proceed-blocked"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_blocked(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="agent availability was repaired",
        ),
        artifact_names=("gate.json",),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "artifacts"),
    )


@pytest.mark.replay_oracle
def test_routed_force_proceed_strict_notes_guard_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_strict_note(fixture: PlanFixture) -> None:
        megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        megaplan.handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["config"]["strict_notes"] = True
        write_plan_state(fixture.plan_dir, mode="replace", state=state)
        megaplan.handle_override(
            fixture.root,
            fixture.make_args(
                plan=fixture.plan_name,
                override_action="add-note",
                note="operator note must be absorbed",
            ),
        )

    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_strict_note(plan_fixture)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="try anyway",
        ),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-force-proceed-strict"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_strict_note(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="force-proceed",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="force-proceed",
            reason="try anyway",
        ),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "exception", "state", "artifacts", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_recover_blocked_prereq_retry_budget_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_recoverable_prereq_blocked(plan_fixture, retry_budget=2)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="recover-blocked",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="recover-blocked",
            reason="operator resolved prereq blocker",
        ),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-recover-prereq"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_recoverable_prereq_blocked(fresh_fixture, retry_budget=2)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="recover-blocked",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="recover-blocked",
            reason="operator resolved prereq blocker",
        ),
    )

    assert legacy.response["resume_cursor"]["retry_budget"] == 2
    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "artifacts", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_recover_blocked_quality_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_recoverable_quality_blocked(plan_fixture)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="recover-blocked",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="recover-blocked",
            reason="operator accepted quality blocker",
        ),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-recover-quality"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_recoverable_quality_blocked(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="recover-blocked",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="recover-blocked",
            reason="operator accepted quality blocker",
        ),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "artifacts", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_recover_blocked_unknown_phase_preserves_legacy_error(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _prepare_unknown_phase(fixture: PlanFixture) -> None:
        megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["current_state"] = megaplan.STATE_BLOCKED
        state["resume_cursor"] = {"phase": "unknown-phase", "retry_strategy": "fresh_session"}
        write_plan_state(fixture.plan_dir, mode="replace", state=state)

    _prepare_unknown_phase(plan_fixture)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="recover-blocked",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="recover-blocked",
            reason="try unknown phase",
        ),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-recover-unknown"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    _prepare_unknown_phase(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="recover-blocked",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="recover-blocked",
            reason="try unknown phase",
        ),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "exception", "state", "artifacts", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_resume_clarify_prep_only_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_prep_clarification(fixture: PlanFixture) -> None:
        megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["current_state"] = STATE_AWAITING_HUMAN
        state["clarification"] = {
            "intent_summary": "Prep needs a human answer.",
            "questions": ["Which auth library?"],
            "source": "prep",
        }
        state["meta"]["notes"].append(
            {"timestamp": frozen_now, "note": "Use platform auth.", "source": "user"}
        )
        write_plan_state(fixture.plan_dir, mode="replace", state=state)

    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_prep_clarification(plan_fixture)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="resume-clarify",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="resume-clarify",
        ),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-resume-clarify"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_prep_clarification(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="resume-clarify",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="resume-clarify",
        ),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "artifacts", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_replan_matches_legacy_structural_rewrite(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_critiqued_with_note(fixture: PlanFixture) -> None:
        megaplan.handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        megaplan.handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))
        megaplan.handle_override(
            fixture.root,
            fixture.make_args(
                plan=fixture.plan_name,
                override_action="add-note",
                note="rework the deployment structure",
            ),
        )

    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_critiqued_with_note(plan_fixture)
    legacy = capture_legacy_action(
        plan_fixture,
        monkeypatch,
        action="replan",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="replan",
            reason="legacy replan transition",
            note="carry this into replanning",
        ),
    )

    from tests.conftest import _make_plan_fixture_with_robustness

    fresh_root = tmp_path / "routed-replan"
    fresh_root.mkdir()
    fresh_fixture = _make_plan_fixture_with_robustness(
        fresh_root,
        monkeypatch,
        robustness="standard",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    _prepare_critiqued_with_note(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="replan",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="replan",
            reason="legacy replan transition",
            note="carry this into replanning",
        ),
    )

    assert_replay_parity(
        legacy=legacy,
        routed=routed,
        fields=("accepted", "response", "state", "artifacts", "events"),
    )


@pytest.mark.replay_oracle
def test_routed_override_registry_covers_all_ten_characterized_actions() -> None:
    assert set(override_handler._ROUTED_OVERRIDE_ACTIONS) == set(override_handler._OVERRIDE_ACTIONS)
    assert len(override_handler._ROUTED_OVERRIDE_ACTIONS) == 10


@pytest.mark.replay_oracle
@pytest.mark.parametrize(
    ("action", "invoke"),
    [
        (
            "set-profile",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-profile",
                profile="all-deepseek-pro",
                reason="operator switched profile",
            ),
        ),
        (
            "set-model",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-model",
                phase="critique",
                model="gpt-5.3-codex",
                effort="high",
                reason="operator repinned model",
            ),
        ),
        (
            "set-vendor",
            lambda fixture: fixture.make_args(
                plan=fixture.plan_name,
                override_action="set-vendor",
                phase="critique",
                vendor="claude",
                reason="operator swapped vendor",
            ),
        ),
    ],
)
def test_routed_config_mutations_surface_stale_version_conflicts(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    action,
    invoke,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    original_write_plan_state = write_plan_state

    def _racing_write_plan_state(plan_dir: Path, *args, **kwargs):
        current = load_state(plan_dir)
        meta = dict(current.get("_state_meta") or {})
        versions = dict(meta.get("versions") or {})
        versions["config"] = int(versions.get("config") or 0) + 1
        meta["versions"] = versions
        current["_state_meta"] = meta
        original_write_plan_state(plan_dir, mode="replace", state=current)
        return original_write_plan_state(plan_dir, *args, **kwargs)

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.control_interface.write_plan_state",
        _racing_write_plan_state,
    )

    monkeypatch.setenv("MEGAPLAN_CONTROL_INTERFACE_ROUTING", "1")

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_override(plan_fixture.root, invoke(plan_fixture))

    assert excinfo.value.code == "invalid_transition"
    assert excinfo.value.message == "control_transition_conflict"
    assert excinfo.value.extra["conflict"]["key"] == "config"
