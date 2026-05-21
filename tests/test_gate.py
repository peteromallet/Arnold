from __future__ import annotations

import json

import pytest

import megaplan
import megaplan.orchestration.evaluation
import megaplan.handlers
import megaplan.workers
from megaplan._core import load_plan
from megaplan.workers import WorkerResult
from tests.conftest import (
    PlanFixture,
    debt_registry_path,
    ensure_blocking_flags,
    first_open_significant_flag,
    load_state,
    make_gate_worker_result,
    make_worker_sequence,
    read_json,
)


def test_force_proceed_from_critiqued_writes_override_gate(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["last_gate"] = {"recommendation": "ESCALATE"}
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="executor can resolve remaining issues",
        ),
    )
    gate = read_json(plan_fixture.plan_dir / "gate.json")
    state = load_state(plan_fixture.plan_dir)

    assert response["state"] == megaplan.STATE_GATED
    assert response["orchestrator_guidance"] == "Force-proceed override applied. Proceed to finalize."
    assert gate["override_forced"] is True
    assert gate["recommendation"] == "PROCEED"
    assert gate["orchestrator_guidance"] == "Force-proceed override applied. Proceed to finalize."
    assert state["last_gate"] == {}


def test_force_proceed_registers_unresolved_flags_as_debt(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="executor can resolve remaining issues",
        ),
    )
    registry = read_json(debt_registry_path(plan_fixture.root))

    assert response["debt_entries_added"] >= 1
    assert len(registry["entries"]) >= 1
    assert all(entry["resolved"] is False for entry in registry["entries"])


def test_repeated_force_proceed_increments_existing_debt_instead_of_duplicating(plan_fixture: PlanFixture) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="first pass"),
    )
    first_registry = read_json(debt_registry_path(plan_fixture.root))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="replan", reason="loop back"),
    )
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="second pass"),
    )

    registry = read_json(debt_registry_path(plan_fixture.root))

    assert len(registry["entries"]) == len(first_registry["entries"])
    assert all(entry["occurrence_count"] == 2 for entry in registry["entries"])


def test_gate_proceed_with_accepted_tradeoffs_creates_debt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = ensure_blocking_flags(plan_fixture.plan_dir, 1)[0]
    worker = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Known tradeoff accepted.",
        signals_assessment="Proceeding with one accepted limitation.",
        flag_resolutions=[
            {
                "flag_id": flag["id"],
                "action": "accept_tradeoff",
                "evidence": "",
                "rationale": "The timeout-recovery gap is contained to a low-traffic path and is tracked for a later redesign.",
            }
        ],
        accepted_tradeoffs=[],
        session_id="gate-debt-1",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    registry = read_json(debt_registry_path(plan_fixture.root))

    assert response["recommendation"] == "PROCEED"
    assert response["reprompted"] is False
    assert response["debt_entries_added"] == 1
    assert len(registry["entries"]) == 1
    assert registry["entries"][0]["flag_ids"] == [flag["id"]]
    # Verify phase_result.json is written via _finish_step
    from megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written after gate"
    assert pr.exit_kind == "success"
    assert pr.phase == "gate"


def test_gate_iterate_with_empty_accepted_tradeoffs_creates_no_debt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    worker = WorkerResult(
        payload={
            "recommendation": "ITERATE",
            "rationale": "Still needs plan work.",
            "signals_assessment": "Revisions are still needed.",
            "warnings": [],
            "settled_decisions": [],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
        },
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="gate-debt-2",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["debt_entries_added"] == 0
    assert not debt_registry_path(plan_fixture.root).exists()
    # Verify phase_result.json is written for ITERATE gate too
    from megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written after gate"
    assert pr.exit_kind == "success"
    assert pr.phase == "gate"


def test_gate_proceed_partial_resolutions_still_missing_after_reprompt_downgrades_to_iterate(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flags = ensure_blocking_flags(plan_fixture.plan_dir, 5)
    first_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Three blockers are resolved; the rest can be revisited.",
        signals_assessment="Proceeding after addressing the most important blockers.",
        flag_resolutions=[
            {
                "flag_id": flags[0]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:1 already documents this constraint.",
                "rationale": "",
            },
            {
                "flag_id": flags[1]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:2 already covers this path.",
                "rationale": "",
            },
            {
                "flag_id": flags[2]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:3 already covers the edge case.",
                "rationale": "",
            },
        ],
        session_id="gate-partial-1",
    )
    second_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Still comfortable proceeding.",
        signals_assessment="The remaining blockers are unchanged.",
        flag_resolutions=[
            {
                "flag_id": flags[0]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:1 already documents this constraint.",
                "rationale": "",
            },
            {
                "flag_id": flags[1]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:2 already covers this path.",
                "rationale": "",
            },
            {
                "flag_id": flags[2]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:3 already covers the edge case.",
                "rationale": "",
            },
        ],
        session_id="gate-partial-2",
    )
    call_counter = {"count": 0}
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        make_worker_sequence(
            [
                (first_attempt, "claude", "persistent", False),
                (second_attempt, "claude", "persistent", False),
            ],
            call_counter,
        ),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    carry = read_json(plan_fixture.plan_dir / "gate_carry.json")

    assert response["recommendation"] == "ITERATE"
    assert response["reprompted"] is True
    assert response["next_step"] == "revise"
    assert "[Auto-downgraded from PROCEED:" in response["rationale"]
    assert carry["recommendation"] == "ITERATE"
    assert call_counter["count"] == 2
    assert not debt_registry_path(plan_fixture.root).exists()


def test_gate_retry_does_not_duplicate_weighted_scores(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = ensure_blocking_flags(plan_fixture.plan_dir, 1)[0]

    results = iter(
        [
            (
                WorkerResult(
                    payload={
                        "recommendation": "ESCALATE",
                        "rationale": "stuck",
                        "signals_assessment": "scores are flat",
                        "warnings": [],
                        "settled_decisions": [],
                        "flag_resolutions": [],
                        "accepted_tradeoffs": [],
                    },
                    raw_output="{}",
                    duration_ms=1,
                    cost_usd=0.0,
                    session_id="gate-1",
                ),
                "claude",
                "persistent",
                False,
            ),
            (
                WorkerResult(
                    payload={
                        "recommendation": "PROCEED",
                        "rationale": "user note clarified the issue",
                        "signals_assessment": "same score, but judgment changed",
                        "warnings": [],
                        "settled_decisions": [],
                        "flag_resolutions": [
                            {
                                "flag_id": flag["id"],
                                "action": "accept_tradeoff",
                                "evidence": "",
                                "rationale": "The remaining issue is narrow and intentionally deferred while the clarified note unblocks the rest of the work.",
                            }
                        ],
                        "accepted_tradeoffs": [],
                    },
                    raw_output="{}",
                    duration_ms=1,
                    cost_usd=0.0,
                    session_id="gate-2",
                ),
                "claude",
                "persistent",
                False,
            ),
        ]
    )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", lambda *args, **kwargs: next(results))

    megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="add-note", note="extra context"),
    )
    megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)

    assert len(state["meta"]["weighted_scores"]) == 1


def test_gate_proceed_partial_resolutions_triggers_reprompt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flags = ensure_blocking_flags(plan_fixture.plan_dir, 2)
    first_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="One blocker is resolved; the second needs one more look.",
        signals_assessment="Proceeding after the first blocker was addressed.",
        flag_resolutions=[
            {
                "flag_id": flags[0]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:1 already covers this constraint.",
                "rationale": "",
            }
        ],
        session_id="gate-reprompt-success-1",
    )
    second_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Both blockers are now explicitly resolved.",
        signals_assessment="Proceeding after the retry resolved the remaining blocker.",
        flag_resolutions=[
            {
                "flag_id": flags[0]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:1 already covers this constraint.",
                "rationale": "",
            },
            {
                "flag_id": flags[1]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:2 already covers the remaining blocker.",
                "rationale": "",
            },
        ],
        session_id="gate-reprompt-success-2",
    )
    call_counter = {"count": 0}
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        make_worker_sequence(
            [
                (first_attempt, "claude", "persistent", False),
                (second_attempt, "claude", "persistent", False),
            ],
            call_counter,
        ),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    gate = read_json(plan_fixture.plan_dir / "gate.json")

    assert response["recommendation"] == "PROCEED"
    assert response["reprompted"] is True
    assert gate["reprompted"] is True
    assert call_counter["count"] == 2


def test_gate_proceed_still_missing_after_reprompt_downgrades_to_iterate(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flags = ensure_blocking_flags(plan_fixture.plan_dir, 2)
    first_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Proceeding without explicit blocker coverage.",
        signals_assessment="Proceeding despite unresolved blockers.",
        flag_resolutions=[],
        session_id="gate-downgrade-1",
    )
    second_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Still proceeding without explicit blocker coverage.",
        signals_assessment="Retry still leaves blockers unresolved.",
        flag_resolutions=[],
        session_id="gate-downgrade-2",
    )
    call_counter = {"count": 0}
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        make_worker_sequence(
            [
                (first_attempt, "claude", "persistent", False),
                (second_attempt, "claude", "persistent", False),
            ],
            call_counter,
        ),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    gate = read_json(plan_fixture.plan_dir / "gate.json")

    assert response["recommendation"] == "ITERATE"
    assert response["reprompted"] is True
    assert "[Auto-downgraded from PROCEED:" in response["rationale"]
    assert gate["recommendation"] == "ITERATE"
    assert gate["reprompted"] is True
    assert call_counter["count"] == 2


def test_gate_accept_tradeoff_rubber_stamp_rejected(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = ensure_blocking_flags(plan_fixture.plan_dir, 1)[0]
    state = load_state(plan_fixture.plan_dir)

    result, next_step, _, blocking_unresolved_ids = megaplan.handlers._apply_gate_outcome(
        state,
        {
            "recommendation": "PROCEED",
            "rationale": "Proceed.",
            "passed": True,
            "unresolved_flags": [flag],
            "flag_resolutions": [
                {
                    "flag_id": flag["id"],
                    "action": "accept_tradeoff",
                    "evidence": "",
                    "rationale": "acceptable",
                }
            ],
        },
        robustness="standard",
        plan_dir=plan_fixture.plan_dir,
    )

    assert result == "unresolved_flags"
    assert next_step == "gate"
    assert blocking_unresolved_ids == [flag["id"]]
    assert state["current_state"] == megaplan.STATE_CRITIQUED


def test_gate_accept_tradeoff_concrete_rationale_accepted(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = ensure_blocking_flags(plan_fixture.plan_dir, 1)[0]
    state = load_state(plan_fixture.plan_dir)

    result, next_step, _, blocking_unresolved_ids = megaplan.handlers._apply_gate_outcome(
        state,
        {
            "recommendation": "PROCEED",
            "rationale": "Proceed.",
            "passed": True,
            "unresolved_flags": [flag],
            "flag_resolutions": [
                {
                    "flag_id": flag["id"],
                    "action": "accept_tradeoff",
                    "evidence": "",
                    "rationale": "The remaining limitation is isolated to a non-blocking retry path and is accepted for this iteration.",
                }
            ],
        },
        robustness="standard",
        plan_dir=plan_fixture.plan_dir,
    )

    assert result == "success"
    assert next_step == "finalize"
    assert blocking_unresolved_ids == []
    assert state["current_state"] == megaplan.STATE_GATED


def test_gate_proceed_all_flags_resolved_no_reprompt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = ensure_blocking_flags(plan_fixture.plan_dir, 1)[0]
    worker = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="All blockers are explicitly resolved.",
        signals_assessment="Proceeding with explicit coverage for the blocker.",
        flag_resolutions=[
            {
                "flag_id": flag["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:1 already implements the required guard.",
                "rationale": "",
            }
        ],
        session_id="gate-no-reprompt",
    )
    call_counter = {"count": 0}
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        make_worker_sequence([(worker, "claude", "persistent", False)], call_counter),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert response["recommendation"] == "PROCEED"
    assert response["reprompted"] is False
    assert call_counter["count"] == 1


def test_gate_writes_carry_artifact(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    worker = make_gate_worker_result(
        recommendation="ITERATE",
        rationale="The plan still needs targeted repair before execution. Keep the existing constraints. Recheck after revision.",
        signals_assessment="Open blockers remain.",
        session_id="gate-carry",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    carry_path = plan_fixture.plan_dir / "gate_carry.json"
    carry = read_json(carry_path)
    assert carry_path.stat().st_size <= 5_000
    assert carry["version"] == 1
    assert carry["verdict"] == "ITERATE"
    assert carry["recommendation"] == "ITERATE"


def test_carry_settled_decisions_are_dicts(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    worker = WorkerResult(
        payload={
            "recommendation": "ITERATE",
            "rationale": "Revise once more.",
            "signals_assessment": "Open blockers remain.",
            "warnings": [],
            "settled_decisions": [
                {"id": "SD7", "decision": "Use ContextVar for sandbox cwd", "rationale": "It is thread-safe."}
            ],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
        },
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="gate-carry-dicts",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    carry = read_json(plan_fixture.plan_dir / "gate_carry.json")

    assert carry["settled_decisions"] == [
        {"id": "SD7", "decision": "Use ContextVar for sandbox cwd", "rationale": "It is thread-safe."}
    ]


def test_legacy_string_settled_decisions_auto_promoted(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    worker = WorkerResult(
        payload={
            "recommendation": "ITERATE",
            "rationale": "Revise once more.",
            "signals_assessment": "Open blockers remain.",
            "warnings": [],
            "settled_decisions": ["Use ContextVar for sandbox cwd"],
            "flag_resolutions": [],
            "accepted_tradeoffs": [],
        },
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="gate-carry-legacy",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    with caplog.at_level("WARNING", logger="megaplan"):
        megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    carry = read_json(plan_fixture.plan_dir / "gate_carry.json")

    assert carry["settled_decisions"] == [
        {"id": "SD1", "decision": "Use ContextVar for sandbox cwd", "rationale": ""}
    ]
    assert "auto-promoted 1 legacy string settled_decisions entry" in caplog.text


def test_carry_excludes_dispute_flags(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flags = ensure_blocking_flags(plan_fixture.plan_dir, 3)
    worker = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="All blockers are explicitly resolved.",
        signals_assessment="Proceeding with explicit coverage for every blocker.",
        flag_resolutions=[
            {
                "flag_id": flags[0]["id"],
                "action": "dispute",
                "evidence": "plan_v1.md:1 already implements the required guard.",
                "rationale": "",
            },
            {
                "flag_id": flags[1]["id"],
                "action": "accept_tradeoff",
                "evidence": "",
                "rationale": "This known limitation is isolated to a rare retry path and is intentionally deferred.",
            },
            {
                "flag_id": flags[2]["id"],
                "action": "accept_tradeoff",
                "evidence": "",
                "rationale": "This compatibility issue affects only legacy fixtures and is tracked as follow-up debt.",
            },
        ],
        session_id="gate-carry-flags",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    carry = read_json(plan_fixture.plan_dir / "gate_carry.json")

    assert [item["flag_id"] for item in carry["carried_flags"]] == [flags[1]["id"], flags[2]["id"]]


def test_gate_debt_not_recorded_on_downgrade(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flags = ensure_blocking_flags(plan_fixture.plan_dir, 2)
    first_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Proceeding without explicit blocker coverage.",
        signals_assessment="Proceeding despite unresolved blockers.",
        flag_resolutions=[],
        session_id="gate-no-debt-1",
    )
    second_attempt = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="Still proceeding without explicit blocker coverage.",
        signals_assessment="Retry still leaves blockers unresolved.",
        flag_resolutions=[],
        session_id="gate-no-debt-2",
    )
    call_counter = {"count": 0}
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        make_worker_sequence(
            [
                (first_attempt, "claude", "persistent", False),
                (second_attempt, "claude", "persistent", False),
            ],
            call_counter,
        ),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    assert len(flags) == 2
    assert response["recommendation"] == "ITERATE"
    assert response["debt_entries_added"] == 0
    assert call_counter["count"] == 2
    assert not debt_registry_path(plan_fixture.root).exists()


def test_gate_debt_derived_from_flag_resolutions(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = ensure_blocking_flags(plan_fixture.plan_dir, 1)[0]
    worker = make_gate_worker_result(
        recommendation="PROCEED",
        rationale="The remaining limitation is accepted explicitly.",
        signals_assessment="Proceeding with one explicit accepted tradeoff.",
        flag_resolutions=[
            {
                "flag_id": flag["id"],
                "action": "accept_tradeoff",
                "evidence": "",
                "rationale": "This limitation only affects a rare retry path and is intentionally deferred to the next planning cycle.",
            }
        ],
        accepted_tradeoffs=[],
        session_id="gate-derived-debt",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    registry = read_json(debt_registry_path(plan_fixture.root))

    assert response["recommendation"] == "PROCEED"
    assert response["debt_entries_added"] == 1
    assert len(registry["entries"]) == 1
    assert registry["entries"][0]["flag_ids"] == [flag["id"]]


def test_normalize_flag_record_fills_defaults() -> None:
    record = megaplan.normalize_flag_record({}, "FLAG-099")
    assert record["id"] == "FLAG-099"
    assert record["concern"] == ""
    assert record["category"] == "other"
    assert record["severity_hint"] == "uncertain"
    assert record["evidence"] == ""


def test_normalize_flag_record_sanitises_bad_category() -> None:
    record = megaplan.normalize_flag_record({"category": "banana"}, "FLAG-001")
    assert record["category"] == "other"


def test_normalize_flag_record_sanitises_bad_severity_hint() -> None:
    record = megaplan.normalize_flag_record({"severity_hint": "maybe"}, "FLAG-001")
    assert record["severity_hint"] == "uncertain"


def test_normalize_flag_record_uses_own_id_when_present() -> None:
    record = megaplan.normalize_flag_record({"id": "FLAG-042"}, "FLAG-099")
    assert record["id"] == "FLAG-042"


def test_normalize_flag_record_uses_fallback_for_empty_id() -> None:
    for empty_id in [None, "", "FLAG-000"]:
        record = megaplan.normalize_flag_record({"id": empty_id}, "FLAG-099")
        assert record["id"] == "FLAG-099"


def test_normalize_flag_record_accepts_structured_text_fields() -> None:
    record = megaplan.normalize_flag_record(
        {
            "id": "FLAG-001",
            "concern": ["First concern", {"path": "src/file.ts", "line": 12}],
            "evidence": ["Checked src/file.ts", {"reason": "agent returned structured evidence"}],
        },
        "FLAG-099",
    )

    assert "First concern" in record["concern"]
    assert '"path": "src/file.ts"' in record["concern"]
    assert "Checked src/file.ts" in record["evidence"]
    assert '"reason": "agent returned structured evidence"' in record["evidence"]


def test_update_flags_after_critique_creates_new_flags(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    critique_payload = {
        "flags": [
            {"id": "FLAG-001", "concern": "Missing tests", "category": "correctness", "severity_hint": "likely-significant", "evidence": "No tests found"},
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    from megaplan.flags import update_flags_after_critique

    registry = update_flags_after_critique(plan_fixture.plan_dir, critique_payload, iteration=1)
    assert len(registry["flags"]) >= 1
    flag = next(f for f in registry["flags"] if f["id"] == "FLAG-001")
    assert flag["status"] == "open"
    assert flag["severity"] == "significant"


def test_update_flags_after_critique_verifies_flags(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    from megaplan.flags import update_flags_after_critique

    critique1 = {
        "flags": [{"id": "FLAG-001", "concern": "x", "category": "other", "severity_hint": "likely-significant", "evidence": "y"}],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    update_flags_after_critique(plan_fixture.plan_dir, critique1, iteration=1)
    critique2 = {
        "flags": [],
        "verified_flag_ids": ["FLAG-001"],
        "disputed_flag_ids": [],
    }
    registry = update_flags_after_critique(plan_fixture.plan_dir, critique2, iteration=2)
    flag = next(f for f in registry["flags"] if f["id"] == "FLAG-001")
    assert flag["status"] == "verified"
    assert flag["verified"] is True


def test_update_flags_after_critique_disputes_flags(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    from megaplan.flags import update_flags_after_critique

    critique1 = {
        "flags": [{"id": "FLAG-001", "concern": "x", "category": "other", "severity_hint": "likely-significant", "evidence": "y"}],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    update_flags_after_critique(plan_fixture.plan_dir, critique1, iteration=1)
    critique2 = {
        "flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": ["FLAG-001"],
    }
    registry = update_flags_after_critique(plan_fixture.plan_dir, critique2, iteration=2)
    flag = next(f for f in registry["flags"] if f["id"] == "FLAG-001")
    assert flag["status"] == "disputed"


def test_update_flags_after_critique_reuses_existing_ids(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    from megaplan.flags import update_flags_after_critique

    critique1 = {
        "flags": [{"id": "FLAG-001", "concern": "x", "category": "other", "severity_hint": "likely-significant", "evidence": "y"}],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    update_flags_after_critique(plan_fixture.plan_dir, critique1, iteration=1)
    critique2 = {
        "flags": [{"id": "FLAG-001", "concern": "revised concern", "category": "correctness", "severity_hint": "likely-significant", "evidence": "new evidence"}],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    registry = update_flags_after_critique(plan_fixture.plan_dir, critique2, iteration=2)
    count = sum(1 for f in registry["flags"] if f["id"] == "FLAG-001")
    assert count == 1
    flag = next(f for f in registry["flags"] if f["id"] == "FLAG-001")
    assert flag["concern"] == "revised concern"


def test_update_flags_after_critique_autonumbers_missing_ids(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    from megaplan.flags import update_flags_after_critique

    critique = {
        "flags": [
            {"concern": "no id given", "category": "other", "severity_hint": "likely-minor", "evidence": "test"},
            {"id": "", "concern": "empty id", "category": "other", "severity_hint": "likely-minor", "evidence": "test"},
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    registry = update_flags_after_critique(plan_fixture.plan_dir, critique, iteration=1)
    ids = [f["id"] for f in registry["flags"]]
    assert all(id_.startswith("FLAG-") for id_ in ids)
    assert len(set(ids)) == len(ids)


def test_update_flags_after_critique_severity_from_hint(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    from megaplan.flags import update_flags_after_critique

    critique = {
        "flags": [
            {"id": "FLAG-001", "concern": "major", "category": "other", "severity_hint": "likely-significant", "evidence": "x"},
            {"id": "FLAG-002", "concern": "minor", "category": "other", "severity_hint": "likely-minor", "evidence": "x"},
            {"id": "FLAG-003", "concern": "uncertain", "category": "other", "severity_hint": "uncertain", "evidence": "x"},
        ],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
    }
    registry = update_flags_after_critique(plan_fixture.plan_dir, critique, iteration=1)
    by_id = {f["id"]: f for f in registry["flags"]}
    assert by_id["FLAG-001"]["severity"] == "significant"
    assert by_id["FLAG-002"]["severity"] == "minor"
    assert by_id["FLAG-003"]["severity"] == "significant"


def test_update_flags_after_revise_marks_addressed(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    from megaplan._core import save_flag_registry
    from megaplan.flags import update_flags_after_critique, update_flags_after_revise  # noqa: F811

    save_flag_registry(
        plan_fixture.plan_dir,
        {
            "flags": [
                {
                    "id": "FLAG-001",
                    "concern": "x",
                    "category": "other",
                    "severity_hint": "likely-significant",
                    "evidence": "y",
                    "status": "open",
                    "severity": "significant",
                    "verified": False,
                    "raised_in": "critique_v1.json",
                },
            ]
        },
    )
    registry = update_flags_after_revise(plan_fixture.plan_dir, ["FLAG-001"], plan_file="plan_v2.md", summary="fixed it")
    flag = registry["flags"][0]
    assert flag["status"] == "addressed"
    assert flag["addressed_in"] == "plan_v2.md"


def test_unresolved_significant_flags_filtering() -> None:
    registry = {
        "flags": [
            {"id": "FLAG-001", "severity": "significant", "status": "open"},
            {"id": "FLAG-002", "severity": "minor", "status": "open"},
            {"id": "FLAG-003", "severity": "significant", "status": "verified"},
            {"id": "FLAG-004", "severity": "significant", "status": "disputed"},
            {"id": "FLAG-005", "severity": "significant", "status": "addressed"},
            {"id": "FLAG-006", "severity": "significant", "status": "accepted_tradeoff"},
            {"id": "FLAG-007", "severity": "significant", "status": "gate_disputed"},
        ]
    }
    unresolved = megaplan.unresolved_significant_flags(registry)
    ids = [f["id"] for f in unresolved]
    assert "FLAG-001" in ids
    assert "FLAG-004" in ids
    assert "FLAG-005" in ids
    assert "FLAG-002" not in ids
    assert "FLAG-003" not in ids
    assert "FLAG-006" not in ids
    assert "FLAG-007" not in ids


def test_override_add_note_records_note(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="add-note", note="my note"),
    )
    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    assert any(n["note"] == "my note" for n in state["meta"]["notes"])


def test_add_note_after_abort(plan_fixture: PlanFixture) -> None:
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="abort", reason="done"),
    )
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="add-note", note="postmortem"),
    )
    assert response["success"] is True


def test_abort_sets_terminal_state(plan_fixture: PlanFixture) -> None:
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="abort", reason="no longer needed"),
    )
    assert response["state"] == megaplan.STATE_ABORTED
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == megaplan.STATE_ABORTED


def test_override_set_robustness_updates_config(plan_fixture: PlanFixture) -> None:
    initial_state = load_state(plan_fixture.plan_dir)
    assert initial_state["config"]["robustness"] in megaplan.ROBUSTNESS_LEVELS
    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="set-robustness",
            robustness="light",
            reason="downshifting",
        ),
    )
    assert response["success"] is True
    assert response["robustness"] == "light"
    assert response["previous_robustness"] == initial_state["config"]["robustness"]
    state = load_state(plan_fixture.plan_dir)
    assert state["config"]["robustness"] == "light"
    assert any(
        entry["action"] == "set-robustness" and entry["to"] == "light"
        for entry in state["meta"]["overrides"]
    )


def test_override_set_robustness_rejects_invalid_level(plan_fixture: PlanFixture) -> None:
    with pytest.raises(megaplan.CliError, match="set-robustness"):
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-robustness",
                robustness=None,
            ),
        )


def test_override_set_robustness_blocked_in_terminal_state(plan_fixture: PlanFixture) -> None:
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="abort", reason="done"),
    )
    with pytest.raises(megaplan.CliError, match="terminal state"):
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                override_action="set-robustness",
                robustness="standard",
            ),
        )


def test_override_replan_recovers_failed_state(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = megaplan.STATE_FAILED
    (plan_fixture.plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    response = megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="replan",
            reason="retry after provider interruption",
        ),
    )

    assert response["state"] == megaplan.STATE_PLANNED
    state = load_state(plan_fixture.plan_dir)
    assert state["current_state"] == megaplan.STATE_PLANNED
    assert any(entry["action"] == "replan" for entry in state["meta"]["overrides"])


def test_force_proceed_requires_critiqued_state(plan_fixture: PlanFixture) -> None:
    with pytest.raises(megaplan.CliError, match="critiqued"):
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
        )


def test_force_proceed_requires_success_criteria(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    meta_path = plan_fixture.plan_dir / "plan_v1.meta.json"
    meta = read_json(meta_path)
    meta["success_criteria"] = []
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(megaplan.CliError, match="success criteria"):
        megaplan.handle_override(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
        )


def test_gate_response_surfaces_auto_approve(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_gate(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    assert "auto_approve" in response
    assert response["orchestrator_guidance"].startswith("First iteration; follow gate recommendation: ITERATE.")
    assert "Verify unresolved flags against the plan and project code before accepting." in response["orchestrator_guidance"]
    gate = read_json(plan_fixture.plan_dir / "gate.json")
    assert gate["orchestrator_guidance"] == response["orchestrator_guidance"]


def test_require_state_rejects_invalid_transition(plan_fixture: PlanFixture) -> None:
    with pytest.raises(megaplan.CliError, match="Cannot run"):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))


def test_terminal_states_block_progression(plan_fixture: PlanFixture) -> None:
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="abort", reason="test"),
    )
    with pytest.raises(megaplan.CliError, match="Cannot run"):
        megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))


def test_build_gate_signals_includes_debt_overlaps_when_flags_match(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    flag = first_open_significant_flag(plan_fixture.plan_dir)
    registry = {"entries": []}
    megaplan._core.add_or_increment_debt(
        registry,
        megaplan._core.extract_subsystem_tag(flag["concern"]),
        flag["concern"],
        [flag["id"]],
        plan_fixture.plan_name,
    )
    megaplan._core.save_debt_registry(plan_fixture.root, registry)
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    signals = megaplan.orchestration.evaluation.build_gate_signals(plan_fixture.plan_dir, state, plan_fixture.root)

    assert signals["signals"]["debt_overlaps"]
    assert signals["signals"]["debt_overlaps"][0]["flag_id"] == flag["id"]
