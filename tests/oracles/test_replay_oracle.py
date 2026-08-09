from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.workflow.execution_attempt_ledger import AttemptEventType
from arnold_pipelines.megaplan._core import set_active_step
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.blocker_recovery import quality_blocker_id
from arnold_pipelines.megaplan.custody.phase_wbc import (
    activate_phase_wbc,
    query_phase_wbc_events,
    suspend_phase_wbc,
)
from arnold_pipelines.megaplan.handlers import override as override_handler
from arnold_pipelines.megaplan.handlers.critique import handle_critique
from arnold_pipelines.megaplan.handlers.override import handle_override
from arnold_pipelines.megaplan.handlers.plan import handle_plan
from arnold_pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation
from arnold_pipelines.megaplan.planning.state import (
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_GATED,
    STATE_PLANNED,
)
from arnold_pipelines.megaplan.quality_resolutions import build_quality_resolution_event
from arnold_pipelines.megaplan.types import CliError
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


def _prepare_recoverable_prereq_blocked(
    fixture: PlanFixture,
    *,
    retry_budget: int = 2,
    timestamp: str | None = None,
) -> None:
    handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
    state = load_state(fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
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
            timestamp=timestamp,
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
    handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
    deviation = Deviation(
        kind="quality",
        message="Quality check needs human acceptance",
        task_id="T1",
        phase="critique",
    )
    blocker_id = quality_blocker_id(deviation)
    state = load_state(fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
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


def _assert_routed_force_proceed_is_custodied(
    *,
    legacy,
    routed,
    from_state: str,
    reason: str,
) -> None:
    """Prove default and flag-enabled delivery share canonical custody."""

    assert legacy.accepted is routed.accepted is True
    assert legacy.response["state"] == routed.response["state"] == STATE_GATED
    for snapshot in (legacy, routed):
        custody = snapshot.state["meta"]["force_proceed_custody"]
        assert custody["schema_version"] == "megaplan.force_proceed_custody.v1"
        assert custody["from_state"] == from_state
        assert custody["reason"] == reason
        assert custody["transaction_id"].startswith("force-proceed:")

    custody = routed.state["meta"]["force_proceed_custody"]
    dispositions = custody["critique_dispositions"]
    assert dispositions
    assert all(row["disposition"] == "waived_to_debt" for row in dispositions)
    assert all(row["reason"] == reason for row in dispositions)

    override = routed.state["meta"]["overrides"][-1]
    assert override["custody_transaction_id"] == custody["transaction_id"]
    assert override["debt_entries_added"] == len(dispositions)

    gate = routed.artifacts["gate.json"]
    resolutions = gate["flag_resolutions"]
    assert {row["flag_id"] for row in resolutions} == {
        row["subject_id"] for row in dispositions
    }
    assert all(row["action"] == "accept_tradeoff" for row in resolutions)


@pytest.mark.replay_oracle
def test_replay_oracle_captures_legacy_action_without_requiring_routed_parity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

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
    assert legacy.response["state"] == STATE_PLANNED
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
def test_default_force_proceed_captures_canonical_custody_and_artifact(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    handle_critique(
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
    assert legacy.response["state"] == STATE_GATED
    assert legacy.artifacts["gate.json"]["recommendation"] == "PROCEED"
    assert legacy.artifacts["gate.json"]["override_forced"] is True
    assert legacy.state["meta"]["force_proceed_custody"]["transaction_id"].startswith(
        "force-proceed:"
    )
    assert legacy.events == (
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
    handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
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
    handle_plan(
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
    handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

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
    handle_plan(fresh_fixture.root, fresh_fixture.make_args(plan=fresh_fixture.plan_name))
    handle_critique(fresh_fixture.root, fresh_fixture.make_args(plan=fresh_fixture.plan_name))

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
    _assert_routed_force_proceed_is_custodied(
        legacy=legacy,
        routed=routed,
        from_state="critiqued",
        reason="operator accepted routed gate risk",
    )
    assert routed.events == (
        {
            "kind": "override_applied",
            "payload": {
                "action": "force-proceed",
                "reason": "operator accepted routed gate risk",
            },
        },
    )


@pytest.mark.replay_oracle
def test_routed_force_proceed_from_blocked_agent_availability_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_blocked(fixture: PlanFixture) -> None:
        handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["current_state"] = STATE_BLOCKED
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

    _assert_routed_force_proceed_is_custodied(
        legacy=legacy,
        routed=routed,
        from_state="blocked",
        reason="agent availability was repaired",
    )


@pytest.mark.replay_oracle
def test_routed_force_proceed_strict_notes_guard_matches_legacy(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_strict_note(fixture: PlanFixture) -> None:
        handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["config"]["strict_notes"] = True
        write_plan_state(fixture.plan_dir, mode="replace", state=state)
        handle_override(
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
    _prepare_recoverable_prereq_blocked(
        plan_fixture,
        retry_budget=2,
        timestamp=frozen_now,
    )
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
    _prepare_recoverable_prereq_blocked(
        fresh_fixture,
        retry_budget=2,
        timestamp=frozen_now,
    )
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
    monkeypatch.setattr("arnold_pipelines.megaplan._core.io.now_utc", lambda: frozen_now)
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
    monkeypatch.setattr("arnold_pipelines.megaplan._core.io.now_utc", lambda: frozen_now)
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
    assert legacy.state["current_state"] == STATE_PLANNED
    assert routed.state["current_state"] == STATE_PLANNED
    assert "clarification" not in legacy.state
    assert "clarification" not in routed.state


@pytest.mark.replay_oracle
def test_routed_recover_blocked_unknown_phase_preserves_legacy_error(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _prepare_unknown_phase(fixture: PlanFixture) -> None:
        handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        state["current_state"] = STATE_BLOCKED
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

    def _prepare_prep_clarification(fixture: PlanFixture) -> str:
        handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        state = load_state(fixture.plan_dir)
        set_active_step(state, step="prep", agent="prep", mode="test")
        metadata = activate_phase_wbc(
            state=state,
            plan_dir=fixture.plan_dir,
            step="prep",
            agent="prep",
        )
        assert metadata is not None
        state["current_state"] = STATE_AWAITING_HUMAN
        state["clarification"] = {
            "intent_summary": "Prep needs a human answer.",
            "questions": ["Which auth library?"],
            "source": "prep",
        }
        suspend_phase_wbc(
            state=state,
            plan_dir=fixture.plan_dir,
            step="prep",
            checkpoint={"clarification": state["clarification"]},
            cursor={"resume_action": "override:resume-clarify"},
            agent="prep",
        )
        state["meta"]["notes"].append(
            {"timestamp": frozen_now, "note": "Use platform auth.", "source": "user"}
        )
        write_plan_state(fixture.plan_dir, mode="replace", state=state)
        return str(metadata["invocation_id"])

    monkeypatch.setattr("arnold_pipelines.megaplan.handlers.override.now_utc", lambda: frozen_now)
    monkeypatch.setattr("arnold_pipelines.megaplan.planning.control_binding.now_utc", lambda: frozen_now)
    legacy_invocation_id = _prepare_prep_clarification(plan_fixture)
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
    routed_invocation_id = _prepare_prep_clarification(fresh_fixture)
    routed = capture_routed_action(
        fresh_fixture,
        monkeypatch,
        action="resume-clarify",
        invoke=lambda fixture: fixture.make_args(
            plan=fixture.plan_name,
            override_action="resume-clarify",
        ),
    )

    assert legacy.accepted is routed.accepted is True
    legacy_response = dict(legacy.response)
    routed_response = dict(routed.response)
    legacy_reentry = legacy_response.pop("phase_wbc_reentry_invocation_id")
    routed_reentry = routed_response.pop("phase_wbc_reentry_invocation_id")
    assert legacy_response == routed_response
    assert legacy_reentry != legacy_invocation_id
    assert routed_reentry != routed_invocation_id
    assert legacy.state["current_state"] == routed.state["current_state"] == "prepped"
    assert "clarification" not in legacy.state
    assert "clarification" not in routed.state
    assert "phase_wbc_suspensions" not in legacy.state["meta"]
    assert "phase_wbc_suspensions" not in routed.state["meta"]
    assert legacy.state["meta"]["overrides"][-1]["phase_wbc_reentry_invocation_id"] == (
        legacy_reentry
    )
    assert routed.state["meta"]["overrides"][-1]["phase_wbc_reentry_invocation_id"] == (
        routed_reentry
    )
    for fixture, invocation_id in (
        (plan_fixture, legacy_invocation_id),
        (fresh_fixture, routed_invocation_id),
    ):
        events = query_phase_wbc_events(
            fixture.plan_dir,
            step="prep",
            invocation_id=invocation_id,
        )
        assert [event.event_type for event in events] == [
            AttemptEventType.STARTED,
            AttemptEventType.SUSPENDED,
            AttemptEventType.RESUMED,
            AttemptEventType.COMPLETED,
        ]
    assert legacy.artifacts == routed.artifacts == {}
    assert legacy.events == routed.events


@pytest.mark.replay_oracle
def test_routed_replan_matches_legacy_structural_rewrite(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen_now = "2026-01-02T03:04:05Z"

    def _prepare_critiqued_with_note(fixture: PlanFixture) -> None:
        handle_plan(fixture.root, fixture.make_args(plan=fixture.plan_name))
        handle_critique(fixture.root, fixture.make_args(plan=fixture.plan_name))
        handle_override(
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
    routed_actions = override_handler._control_routed_override_actions()
    assert set(routed_actions) == (
        set(override_handler._OVERRIDE_ACTIONS) - {"adopt-execution"}
    ) | {"force-proceed"}
    assert "force-proceed" not in override_handler._OVERRIDE_ACTIONS
    assert len(routed_actions) == 10


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
    handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

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

    with pytest.raises(CliError) as excinfo:
        handle_override(plan_fixture.root, invoke(plan_fixture))

    assert excinfo.value.code == "invalid_transition"
    assert excinfo.value.message == "control_transition_conflict"
    assert excinfo.value.extra["conflict"]["key"] == "config"
