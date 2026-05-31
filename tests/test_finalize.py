from __future__ import annotations

import json

import pytest

import megaplan
import megaplan.workers
from megaplan.calibration import ModelIdentity, RouteSuggestion, read_capability_claims, route
from megaplan.handlers.finalize import _task_execute_claim_context, _write_finalize_artifacts
from megaplan.observability.evaluand import EvaluandRecord, write_evaluand_event
from megaplan.observability.events import EventKind, read_events
from megaplan.workers import WorkerResult
from tests.conftest import PlanFixture, load_state, read_json


def test_handle_finalize_validates_payload_shape(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    valid_payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the change",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Localized change with an obvious test update → tier 2.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Did it work?",
                "executor_note": "",
                "verdict": "",
            }
        ],
        "meta_commentary": "ok",
    }
    worker = WorkerResult(
        payload=valid_payload,
        raw_output="valid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-valid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    response = megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_FINALIZED
    assert read_json(plan_fixture.plan_dir / "finalize.json")["tasks"][0]["status"] == "pending"


def test_handle_finalize_rejects_invalid_payload(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    invalid_worker = WorkerResult(
        payload={
            "tasks": [
                {
                    "id": "T1",
                    "description": "Broken finalize task",
                    "depends_on": [],
                    "status": "done",
                    "executor_notes": "",
                    "files_changed": [],
                    "commands_run": [],
                    "evidence_files": [],
                    "reviewer_verdict": "",
                }
            ],
            "watch_items": [],
            "sense_checks": [],
        },
        raw_output="invalid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-invalid",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (invalid_worker, "claude", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match="status `pending`"):
        megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    state = load_state(plan_fixture.plan_dir)
    assert state["history"][-1]["result"] == "error"


@pytest.mark.parametrize(
    "task_overrides, expected_match",
    [
        ({"complexity": None, "complexity_justification": "x"}, "integer `complexity` score"),
        ({"complexity": 7, "complexity_justification": "x"}, "integer `complexity` score"),
        ({"complexity": "high", "complexity_justification": "x"}, "integer `complexity` score"),
        ({"complexity": 3, "complexity_justification": ""}, "complexity_justification"),
        ({"complexity": 3}, "complexity_justification"),
    ],
)
def test_handle_finalize_rejects_unadjudicated_complexity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    task_overrides: dict,
    expected_match: str,
) -> None:
    """A finalize task must carry a deliberate 1-5 score AND an argued justification.

    Replaces the old silent coerce-to-5 behaviour for LLM-produced tasks: a missing,
    non-integer, or out-of-range complexity, or an empty justification, now bounces
    finalize instead of defaulting to the most expensive model.
    """
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    task = {
        "id": "T1",
        "description": "Ship the change",
        "depends_on": [],
        "status": "pending",
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
        "reviewer_verdict": "",
    }
    task.update(task_overrides)
    worker = WorkerResult(
        payload={"tasks": [task], "watch_items": [], "sense_checks": []},
        raw_output="unadjudicated finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-unadjudicated",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match=expected_match):
        megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))


def test_handle_finalize_attaches_calibration_route_report_without_mutating_complexity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")

    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the change",
                "depends_on": [],
                "status": "pending",
                "complexity": 3,
                "complexity_justification": "Touches runtime wiring and tests.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="valid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-calibration",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setattr(
        megaplan.handlers.finalize,
        "query_route_if_enabled",
        lambda *args, **kwargs: RouteSuggestion(tier_spec="codex:medium", confidence=0.7),
    )

    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalized = read_json(plan_fixture.plan_dir / "finalize.json")
    task = finalized["tasks"][0]
    assert task["complexity"] == 3
    assert task["complexity_justification"] == "Touches runtime wiring and tests."
    assert task["metadata"]["calibration_route_report"]["authoritative_complexity"] == 3
    assert task["metadata"]["calibration_route_report"]["suggestion"]["tier_spec"] == "codex:medium"


@pytest.mark.parametrize("flag_enabled", [False, True])
def test_handle_finalize_calibration_flag_characterization(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    flag_enabled: bool,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    if flag_enabled:
        monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")
    else:
        monkeypatch.delenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", raising=False)

    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the change",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Localized change.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="valid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-no-calibration",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    if flag_enabled:
        monkeypatch.setattr(
            megaplan.handlers.finalize,
            "query_route_if_enabled",
            lambda *args, **kwargs: RouteSuggestion(tier_spec="codex:medium", confidence=0.7),
        )
    else:
        def _should_not_run(*args, **kwargs):
            raise AssertionError("calibration query should stay disabled when flag is off")

        monkeypatch.setattr(
            megaplan.handlers.finalize,
            "query_route_if_enabled",
            _should_not_run,
        )

    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalized = read_json(plan_fixture.plan_dir / "finalize.json")
    task = finalized["tasks"][0]
    assert task["complexity"] == 2
    assert task["complexity_justification"] == "Localized change."
    report = task.get("metadata", {}).get("calibration_route_report")
    if flag_enabled:
        assert report is not None
        assert report["authoritative_complexity"] == 2
        assert report["suggestion"]["tier_spec"] == "codex:medium"
    else:
        assert report is None


def test_handle_finalize_writes_capability_claim_from_adjudicated_finalize_path(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")

    record = EvaluandRecord(
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="input-hash-v1",
        score=0.91,
        piece_version="piece-v1",
        provenance={"verifier_identity": "judge-mi"},
        taint=(),
    )
    write_evaluand_event("eval-run-1", record, plan_dir=plan_fixture.plan_dir, phase="judge", scope="tests")

    state = load_state(plan_fixture.plan_dir)
    state["history"].append(
        {
            "step": "execute",
            "timestamp": "2026-05-31T00:00:00Z",
            "duration_ms": 5,
            "cost_usd": 1.5,
            "result": "success",
            "output_file": "execution_batch_1.json",
            "batch_complexity": 5,
            "tier_model_spec": "hermes:flash",
            "tier_model_resolved": "resolved::hermes:flash",
            "tier_projected": 2,
            "tier_counterfactual_tag": "explore-42",
        }
    )
    (plan_fixture.plan_dir / "state.json").write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}, indent=2) + "\n",
        encoding="utf-8",
    )

    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the change",
                "depends_on": [],
                "status": "pending",
                "complexity": 3,
                "complexity_justification": "Touches runtime wiring and tests.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
                "metadata": {
                    "evaluand_ref": {
                        "piece_version": "piece-v1",
                        "judge_version": "judge-v1",
                        "rubric_version": "rubric-v1",
                        "input_set_hash": "input-hash-v1",
                    }
                },
            }
        ],
        "watch_items": [],
        "sense_checks": [],
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="valid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-capability-claim",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setattr(
        megaplan.handlers.finalize,
        "query_route_if_enabled",
        lambda *args, **kwargs: RouteSuggestion(tier_spec="codex:medium", confidence=0.7),
    )

    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    claims = read_capability_claims(plan_fixture.plan_dir)
    assert len(claims) == 1
    claim = claims[0]
    assert claim.task_signature == "finalize:task_id=T1:complexity=3"
    assert claim.model_identity == "resolved::hermes:flash"
    assert claim.predicted_tier == 2
    assert claim.routed_model == ModelIdentity("resolved::hermes:flash")
    assert claim.routed_model_identity == "resolved::hermes:flash"
    assert claim.verifier_identity == "judge-mi"
    assert claim.verifier_tier == "4"
    assert claim.taint_class is None
    assert claim.exploration_tag == "explore-42"
    assert claim.low_confidence_signal is False
    assert claim.route_phase == "execute"
    assert claim.routed_tier_spec == "hermes:flash"
    assert claim.cost_usd == 1.5

    claim_events = list(read_events(plan_fixture.plan_dir, kinds=[EventKind.CAPABILITY_CLAIM]))
    assert len(claim_events) == 1
    assert claim_events[0]["phase"] == "execute"

    filtered = read_capability_claims(
        plan_fixture.plan_dir,
        model_identity="resolved::hermes:flash",
    )
    assert filtered == claims
    assert read_capability_claims(
        plan_fixture.plan_dir,
        routed_model=ModelIdentity("resolved::hermes:flash"),
    ) == claims
    suggestion = route(
        claim.task_signature,
        claims=read_capability_claims(plan_fixture.plan_dir),
        tier_models={"execute": {"2": "hermes:flash", "4": "codex:medium"}},
        now=record.recorded_at,
    )
    assert suggestion.tier_spec == "hermes:flash"


def test_finalize_execute_claim_context_accepts_legacy_one_batch_metadata(
    plan_fixture: PlanFixture,
) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["history"].append(
        {
            "step": "execute",
            "output_file": "execution_batch_1.json",
            "batch_complexity": 3,
            "tier_model_spec": "codex:medium",
            "tier_model_resolved": "resolved::codex:medium",
            "tier_projected": 2,
            "tier_exploration_tag": "legacy-one-batch",
        }
    )
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}) + "\n",
        encoding="utf-8",
    )

    context = _task_execute_claim_context(plan_fixture.plan_dir, state)

    assert context["T1"]["counterfactual_tag"] == "legacy-one-batch"
    assert context["T1"]["predicted_tier"] == 2
    assert context["T1"]["routed_tier_spec"] == "codex:medium"
    assert context["T1"]["routed_model_identity"] == "resolved::codex:medium"


def test_finalize_execute_claim_context_accepts_auto_loop_batch_to_tier_metadata(
    plan_fixture: PlanFixture,
) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["history"].append(
        {
            "step": "execute",
            "output_file": "execution.json",
            "batch_to_tier": [
                {
                    "batch_number": 1,
                    "batch_complexity": 5,
                    "tier_model_spec": "codex:high",
                    "resolved_model": "resolved::codex:high",
                    "projected_tier": 4,
                    "counterfactual_tag": "canonical-auto",
                    "low_confidence": True,
                },
                {
                    "batch_number": 2,
                    "batch_complexity": 2,
                    "tier_model_spec": "claude:medium",
                    "resolved_model": "resolved::claude:medium",
                    "exploration_tag": "legacy-auto",
                },
            ],
        }
    )
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T1", "status": "done"}]}) + "\n",
        encoding="utf-8",
    )
    (plan_fixture.plan_dir / "execution_batch_2.json").write_text(
        json.dumps({"task_updates": [{"task_id": "T2", "status": "done"}]}) + "\n",
        encoding="utf-8",
    )

    context = _task_execute_claim_context(plan_fixture.plan_dir, state)

    assert context["T1"]["counterfactual_tag"] == "canonical-auto"
    assert context["T1"]["predicted_tier"] == 4
    assert context["T1"]["routed_tier_spec"] == "codex:high"
    assert context["T1"]["routed_model_identity"] == "resolved::codex:high"
    assert context["T1"]["low_confidence_signal"] is True
    assert context["T2"]["counterfactual_tag"] == "legacy-auto"
    assert context["T2"]["predicted_tier"] == 2
    assert context["T2"]["routed_tier_spec"] == "claude:medium"


def test_handle_finalize_skips_capability_claim_when_evaluand_ref_unavailable(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")

    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the change",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Localized change.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
    }
    worker = WorkerResult(
        payload=payload,
        raw_output="valid finalize payload",
        duration_ms=1,
        cost_usd=0.0,
        session_id="finalize-no-evaluand-ref",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "claude", "persistent", False),
    )
    monkeypatch.setattr(
        megaplan.handlers.finalize,
        "query_route_if_enabled",
        lambda *args, **kwargs: RouteSuggestion(tier_spec="codex:low", confidence=0.6),
    )

    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    assert read_capability_claims(plan_fixture.plan_dir) == ()


def test_after_execute_user_actions_are_handoff_artifact_not_executor_task(
    plan_fixture: PlanFixture,
) -> None:
    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the code change",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "user_actions": [
            {
                "id": "U1",
                "description": "Review and sign off on the generated baseline.",
                "phase": "after_execute",
            }
        ],
        "meta_commentary": "ok",
        "validation": {
            "plan_steps_covered": [
                {
                    "plan_step_summary": "Human sign-off",
                    "finalize_item_ids": ["U1"],
                }
            ],
            "orphan_tasks": [],
            "completeness_notes": "covered",
            "coverage_complete": True,
        },
    }
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"

    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    assert [task["id"] for task in finalize_data["tasks"]] == ["T1", "T2"]
    assert not any(
        "Surface after_execute user_actions" in task["description"]
        for task in finalize_data["tasks"]
    )
    user_actions_md = (plan_fixture.plan_dir / "user_actions.md").read_text(encoding="utf-8")
    assert "## After Execute" in user_actions_md
    assert "Review and sign off" in user_actions_md


def test_finalize_snapshot_remains_pending_after_execute(plan_fixture: PlanFixture) -> None:
    from megaplan._core import load_finalize_snapshot

    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )

    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    snapshot_before_execute = load_finalize_snapshot(plan_fixture.plan_dir)
    assert (plan_fixture.plan_dir / "finalize_snapshot.json").exists()
    assert all(task["status"] == "pending" for task in snapshot_before_execute["tasks"])

    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    finalize_after_execute = read_json(plan_fixture.plan_dir / "finalize.json")
    snapshot_after_execute = load_finalize_snapshot(plan_fixture.plan_dir)

    assert all(task["status"] == "done" for task in finalize_after_execute["tasks"])
    assert snapshot_after_execute == snapshot_before_execute
    assert all(task["status"] == "pending" for task in snapshot_after_execute["tasks"])


def test_render_final_md_pending_partially_done_and_reviewed_states() -> None:
    from megaplan._core import render_final_md

    pending = {
        "tasks": [
            {
                "id": "T1",
                "description": "Do work",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": ["Watch this."],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "question": "Did it work?", "executor_note": "", "verdict": ""}
        ],
        "meta_commentary": "Pending state.",
    }
    partial = {
        **pending,
        "tasks": [
            {
                **pending["tasks"][0],
                "status": "done",
                "executor_notes": "Implemented.",
                "files_changed": ["megaplan/handlers.py"],
            }
        ],
        "sense_checks": [
            {
                **pending["sense_checks"][0],
                "executor_note": "Confirmed execute evidence coverage.",
            }
        ],
    }
    reviewed = {
        **partial,
        "tasks": [
            {
                **partial["tasks"][0],
                "reviewer_verdict": "Pass",
                "evidence_files": ["megaplan/handlers.py"],
            }
        ],
        "sense_checks": [
            {
                **partial["sense_checks"][0],
                "verdict": "Confirmed.",
            }
        ],
    }

    pending_md = render_final_md(pending)
    partial_md = render_final_md(partial)
    reviewed_md = render_final_md(reviewed)

    assert "# Execution Checklist" in pending_md
    assert "## Watch Items" in pending_md
    assert "## Sense Checks" in pending_md
    assert "## Meta" in pending_md
    assert "- [ ] **T1:** Do work" in pending_md
    assert "- [x] **T1:** Do work" in partial_md
    assert "Executor notes: Implemented." in partial_md
    assert "Files changed:" in partial_md
    assert "Executor note: Confirmed execute evidence coverage." in partial_md
    assert "Reviewer verdict: Pass" in reviewed_md
    assert "Evidence files:" in reviewed_md
    assert "Verdict: Confirmed." in reviewed_md


def test_finalize_normalize_complexity_missing_defaults_to_4(plan_fixture: PlanFixture) -> None:
    """Worker response missing complexity writes 4 (Sonnet) in finalize artifacts.

    Auto-injected verification/gate tasks are read-and-check work, not deep
    implementation — Sonnet is capable enough and ~5–10× cheaper than Opus.
    """
    from megaplan.handlers.finalize import _normalize_task_complexity

    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Do work",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "meta_commentary": "ok",
    }
    _normalize_task_complexity(payload)
    assert payload["tasks"][0]["complexity"] == 4


def test_finalize_normalize_complexity_invalid_values_normalized(plan_fixture: PlanFixture) -> None:
    """Non-integer and out-of-range complexity values are normalized to 4 (Sonnet)."""
    from megaplan.handlers.finalize import _normalize_task_complexity

    payload = {
        "tasks": [
            {"id": "T1", "complexity": "high"},
            {"id": "T2", "complexity": 0},
            {"id": "T3", "complexity": 6},
            {"id": "T4", "complexity": None},
            {"id": "T5", "complexity": 3},
        ],
        "watch_items": [],
        "sense_checks": [],
        "meta_commentary": "ok",
    }
    _normalize_task_complexity(payload)
    assert payload["tasks"][0]["complexity"] == 4  # "high" → 4
    assert payload["tasks"][1]["complexity"] == 4  # 0 → 4
    assert payload["tasks"][2]["complexity"] == 4  # 6 → 4
    assert payload["tasks"][3]["complexity"] == 4  # None → 4
    assert payload["tasks"][4]["complexity"] == 3  # valid pass-through


def test_finalize_normalize_complexity_valid_values_pass_through(plan_fixture: PlanFixture) -> None:
    """Valid complexity values 1-5 are left unchanged."""
    from megaplan.handlers.finalize import _normalize_task_complexity

    payload = {
        "tasks": [
            {"id": "T1", "complexity": 1},
            {"id": "T2", "complexity": 2},
            {"id": "T3", "complexity": 3},
            {"id": "T4", "complexity": 4},
            {"id": "T5", "complexity": 5},
        ],
        "watch_items": [],
        "sense_checks": [],
        "meta_commentary": "ok",
    }
    _normalize_task_complexity(payload)
    assert payload["tasks"][0]["complexity"] == 1
    assert payload["tasks"][1]["complexity"] == 2
    assert payload["tasks"][2]["complexity"] == 3
    assert payload["tasks"][3]["complexity"] == 4
    assert payload["tasks"][4]["complexity"] == 5


def test_finalize_artifacts_include_complexity_after_normalization(plan_fixture: PlanFixture) -> None:
    """Full artifact write path normalizes complexity in the written finalize.json."""
    state = load_state(plan_fixture.plan_dir)
    state["config"]["mode"] = "code"

    payload = {
        "tasks": [
            {
                "id": "T1",
                "description": "Ship the code change",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "meta_commentary": "ok",
        "validation": {
            "plan_steps_covered": [],
            "orphan_tasks": [],
            "completeness_notes": "ok",
            "coverage_complete": True,
        },
    }

    _write_finalize_artifacts(plan_fixture.plan_dir, payload, state)

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    snapshot_data = read_json(plan_fixture.plan_dir / "finalize_snapshot.json")

    # Both finalize.json and snapshot should have complexity=4 (Sonnet default) on the
    # original task (model did not score it; safety net defaults to 4 not 5)
    original_tasks = [t for t in finalize_data["tasks"] if t["id"] == "T1"]
    assert len(original_tasks) == 1
    assert original_tasks[0]["complexity"] == 4

    original_snapshot = [t for t in snapshot_data["tasks"] if t["id"] == "T1"]
    assert len(original_snapshot) == 1
    assert original_snapshot[0]["complexity"] == 4

    # Auto-injected tasks (verification, user-action gate) should also have a valid complexity
    for task in finalize_data["tasks"]:
        assert isinstance(task.get("complexity"), int)
        assert 1 <= task["complexity"] <= 5


def test_render_final_md_phase_marks_gaps_only_when_due() -> None:
    from megaplan._core import render_final_md

    data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Do work",
                "depends_on": [],
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
            {
                "id": "T2",
                "description": "Ship work",
                "depends_on": ["T1"],
                "status": "done",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "watch_items": [],
        "sense_checks": [
            {"id": "SC1", "task_id": "T1", "question": "Did it work?", "executor_note": "", "verdict": ""},
            {"id": "SC2", "task_id": "T2", "question": "Was it reviewed?", "executor_note": "", "verdict": ""},
        ],
        "meta_commentary": "Status overview.",
    }

    finalize_md = render_final_md(data)
    execute_md = render_final_md(data, phase="execute")
    review_md = render_final_md(data, phase="review")

    assert "Executor notes: [MISSING]" not in finalize_md
    assert "Reviewer verdict: [PENDING]" not in finalize_md
    assert "## Coverage Gaps" not in finalize_md
    assert "Executor notes: [MISSING]" in execute_md
    assert "Reviewer verdict: [PENDING]" not in execute_md
    assert "Tasks without executor updates: 1" in execute_md
    assert "Executor notes missing: 1" in execute_md
    assert "Sense-check acknowledgments missing: 2" in execute_md
    assert "Reviewer verdict: [PENDING]" in review_md
    assert "Verdict: [PENDING]" in review_md
    assert "Reviewer verdicts pending: 2" in review_md
    assert "Sense-check verdicts pending: 2" in review_md
