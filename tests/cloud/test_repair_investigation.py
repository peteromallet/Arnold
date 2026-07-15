from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.repair_investigation import (
    EVIDENCE_SOURCE_KINDS,
    MAX_CONTEXT_BYTES,
    META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA,
    REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
    build_meta_investigation_context,
    build_meta_observation_bundle,
    build_investigation_context,
    summarize_investigation_artifacts,
    validate_meta_investigation_context,
    validate_investigator_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    workspace = tmp_path / "workspace"
    plan = "current-m5a"
    spec = workspace / ".megaplan/initiatives/demo/chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    state = workspace / ".megaplan/plans" / plan / "state.json"
    _write(
        state,
        {
            "name": plan,
            "current_state": "blocked",
            "latest_failure": {
                "failure_kind": "execution_blocked",
                "phase": "execute",
                "task_id": "T30",
                "message": "exact CAS receipt error",
            },
            "history": [{"step": "execute", "result": "blocked"}],
        },
    )
    (state.parent / "events.ndjson").write_text("", encoding="utf-8")
    _write(
        workspace / ".megaplan/plans/.chains/chain.json",
        {
            "current_plan_name": plan,
            "current_milestone_index": 1,
            "completed": [{"plan": "m5"}],
            "last_state": "blocked",
            "metadata": {"chain_spec_path": str(spec)},
        },
    )
    repair_data = tmp_path / "repair-data.json"
    _write(
        repair_data,
        {
            "outcome": "repairing",
            "attempts": [
                {
                    "attempt_id": index,
                    "dev_hypothesis": f"prior hypothesis {index}",
                    "dev_summary": [f"prior action {index}"],
                    "problem_signature": {"phase_or_step": "execute"},
                }
                for index in range(10)
            ],
        },
    )
    request = tmp_path / "request.json"
    _write(
        request,
        {
            "request_id": "old-request",
            "problem_signature": {
                "milestone_or_plan": "old-m5",
                "phase_or_step": "review",
            },
            "target": {"plan_name": "old-m5"},
        },
    )
    goal = tmp_path / "goal.json"
    _write(
        goal,
        {
            "goal_id": "goal-1",
            "checkpoint_digest": "abc",
            "target": {"plan_name": plan},
            "frozen_checkpoint": {
                "latest_failure": {"message": "exact frozen execute error"}
            },
        },
    )
    return workspace, spec, repair_data, request, goal


def test_context_is_bounded_and_carries_exact_error_and_recent_repairs(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    assert len(json.dumps(context).encode()) <= MAX_CONTEXT_BYTES
    assert context["exact_error"]["message"] == "exact CAS receipt error"
    assert [item["attempt_id"] for item in context["prior_repairs"]] == [4, 5, 6, 7, 8, 9]
    assert context["request"]["matches_current_target"] is False
    assert context["frozen_checkpoint"]["latest_failure"]["message"] == (
        "exact frozen execute error"
    )
    assert "old-m5" in context["request"]["mismatch_reason"]
    assert len(context["context_digest"]) == 64
    supported_cli = context["safe_repair_boundaries"]["supported_recovery_cli"]
    assert supported_cli == (
        f"python -P -m arnold_pipelines.megaplan chain start --spec {spec} "
        f"--project-dir {workspace}"
    )
    assert context["required_investigator_output"][
        "action_specific_handoff_examples"
    ]["recover_state"]["allowed_mutations"] == [f"supported_cli:{supported_cli}"]


def test_context_normalizes_mapping_validation_from_real_repair_report(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    payload = json.loads(repair_data.read_text(encoding="utf-8"))
    payload["attempts"][-1]["dev_summary"] = None
    payload["attempts"][-1]["dev_report"] = {
        "what_tried": "centralized extracted wrapper dependencies",
        "validation": {
            "focused_tests": "9 passed",
            "exact_selector": "passed",
        },
        "pushed_commit": "1322b318e5b3c98c88ca47b56f7764d2cfc730d1",
    }
    _write(repair_data, payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    latest = context["prior_repairs"][-1]
    assert latest["what_tried"] == ["centralized extracted wrapper dependencies"]
    assert latest["validation"] == [
        "{'focused_tests': '9 passed', 'exact_selector': 'passed'}"
    ]
    assert latest["pushed_commit"] == "1322b318e5b3c98c88ca47b56f7764d2cfc730d1"


def test_fresh_quality_phase_result_is_exact_error_when_latest_failure_cleared(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state = workspace / ".megaplan/plans/current-m5a/state.json"
    payload = json.loads(state.read_text(encoding="utf-8"))
    payload["latest_failure"] = None
    _write(state, payload)
    _write(
        state.parent / "phase_result.json",
        {
            "phase": "execute",
            "exit_kind": "blocked_by_quality",
            "invocation_id": "inv-14",
            "blocked_tasks": [],
            "deviations": [
                {"kind": "quality_gate", "message": "scope_drift_severity=high exact files"}
            ],
        },
    )

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    assert context["exact_error"]["exit_kind"] == "blocked_by_quality"
    assert context["exact_error"]["deviations"][0]["message"] == (
        "scope_drift_severity=high exact files"
    )
    assert context["current_phase_result"]["path"].endswith("phase_result.json")


def test_l1_replan_handoff_carries_fresh_external_ci_failure(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state = workspace / ".megaplan/plans/current-m5a/state.json"
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload["latest_failure"] = None
    _write(state, state_payload)
    request_payload = json.loads(request.read_text(encoding="utf-8"))
    request_payload["problem_signature"] = {
        "milestone_or_plan": "current-m5a",
        "phase_or_step": "review",
    }
    request_payload["target"] = {"plan_name": "current-m5a"}
    _write(request, request_payload)
    access = tmp_path / "meta-observations.json"
    external = tmp_path / "external-state.json"
    external_value = {
        "available": True,
        "pull_request": {
            "headRefOid": "deadbeef",
            "mergeStateStatus": "UNSTABLE",
            "statusCheckRollup": [
                {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"}
            ],
        },
    }
    _write(external, external_value)
    encoded_external = external.read_bytes()
    context_digest = "c" * 64
    _write(
        access,
        {
            "schema_version": "arnold-meta-repair-observation-bundle-v1",
            "context_digest": context_digest,
            "access_verified": True,
            "observations": [
                {
                    "kind": "external_state",
                    "path": str(external),
                    "sha256": hashlib.sha256(encoded_external).hexdigest(),
                    "size_bytes": len(encoded_external),
                    "observed": external_value,
                }
            ],
        },
    )
    payload = json.loads(repair_data.read_text(encoding="utf-8"))
    payload["meta_investigation"] = {
        "access_receipt_path": str(tmp_path / "stale-erased-observations.json"),
        "context_digest": "d" * 64,
    }
    _write(repair_data, payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
        l2_handoff_path=access,
        l2_context_digest=context_digest,
    )

    assert context["exact_error"]["failure_kind"] == "external_pr_ci_guard_failed"
    assert context["custody_status"] == "consistent"
    assert context["custody_contradictions"] == []
    assert context["request"]["stage_transition"] is True
    assert context["request"]["stage_transition_remains_same_goal"] is True
    assert context["goal_continuity"]["status"] == "successor_blocker"
    assert context["goal_continuity"]["same_goal_continuity_valid"] is True
    source = next(
        item for item in context["evidence_sources"] if item["kind"] == "external_state"
    )
    assert source["path"] == str(external)

    external.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="size disagrees|digest disagrees|content disagrees"):
        build_investigation_context(
            workspace=workspace,
            session="custody-control-plane-20260714",
            remote_spec=str(spec),
            repair_data_path=repair_data,
            request_path=request,
            goal_path=goal,
            l2_handoff_path=access,
            l2_context_digest=context_digest,
        )


def test_goal_identity_mismatch_remains_a_custody_contradiction(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    goal_payload = json.loads(goal.read_text(encoding="utf-8"))
    goal_payload["target"]["session"] = "different-session"
    _write(goal, goal_payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    assert context["custody_status"] == "contradictory"
    assert any(
        item["contradiction"] == "repair-goal session identity differs from the current session"
        for item in context["custody_contradictions"]
    )


def _receipt(digest: str = "digest-1", *, target_kind: str = "l1_repair_target") -> dict:
    return {
        "schema_version": REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
        "context_digest": digest,
        "target_kind": target_kind,
        "actual_failure": {
            "classification": "custody_failure",
            "mechanism": "mechanical relaunch ignores a fresh execute worker",
            "error": "worker custody and repair dispatch disagree",
        },
        "evidence_sources": [
            {
                "kind": "plan_state",
                "path": "/workspace/state.json",
                "authority": 4,
                "observed": "fresh execute worker",
            }
        ],
        "custody_status": "contradictory",
        "custody_contradictions": [
            {
                "left_source": "/workspace/state.json",
                "right_source": "/workspace/repair-data.json",
                "contradiction": "worker is fresh while repair claims stopped",
            }
        ],
        "intended_recovery": {
            "predicate": "blocker cleared and accepted progress beyond execute",
            "blocker_cleared_required": True,
            "fresh_progress_required": True,
            "beyond_stage_required": True,
        },
        "safe_repair_target": {
            "kind": "target_workspace",
            "scope": "/workspace",
            "rationale": "failure is in the target task",
        },
        "handoff": {
            "action": "repair_target",
            "allowed_mutations": ["target task implementation"],
            "forbidden_mutations": ["guard weakening"],
        },
        "four_axis": {
            "TRACKED": "pass",
            "FIXED": "fail",
            "INTENT": "pass",
            "CONTEXT": "pass",
        },
        "prior_repairs_considered": ["attempt-11"],
        "preserve_live": False,
        "recommended_action": "repair_target",
        "guard_weakening_risk": "none",
    }


def test_investigator_receipt_is_bound_to_context_and_requires_evidence() -> None:
    receipt = _receipt()

    validated = validate_investigator_receipt(receipt, expected_context_digest="digest-1")
    assert validated["receipt_digest"]
    assert validated["actual_failure"]["classification"] == "custody_failure"
    with pytest.raises(ValueError, match="context digest disagrees"):
        validate_investigator_receipt(receipt, expected_context_digest="digest-2")


def test_failing_external_guard_rejects_state_recovery_handoff() -> None:
    receipt = _receipt(target_kind="l2_repair_system")
    receipt["recommended_action"] = "recover_state"
    receipt["handoff"] = {
        "action": "recover_state",
        "allowed_mutations": ["supported recovery CLI"],
        "forbidden_mutations": ["direct state edit"],
    }
    receipt["safe_repair_target"] = {
        "kind": "repair_custody",
        "scope": "repair custody",
        "rationale": "reconcile stale state",
    }
    observation = {
        "context_digest": "digest-1",
        "observations": [
            {
                "kind": "external_state",
                "observed": {"external_guard": {"status": "failed"}},
            }
        ],
    }
    with pytest.raises(ValueError, match="cannot bypass"):
        validate_investigator_receipt(
            receipt,
            expected_context_digest="digest-1",
            observation_bundle=observation,
        )


def test_context_separates_safe_target_from_handoff_mutation_contract(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    contract = context["required_investigator_output"]["safe_repair_target_by_action"]
    assert contract["replan"] == ["none", "repair_custody"]
    assert contract["recover_state"] == ["plan_state_via_cli", "repair_custody"]
    assert context["required_investigator_output"][
        "handoff_allowed_mutations_by_action"
    ]["replan"] == ["none"]
    assert "action_target_contract" not in context["required_investigator_output"]
    assert "L2/root-cause target" in context["required_investigator_output"][
        "replan_contract"
    ]

    receipt = _receipt()
    receipt["recommended_action"] = "replan"
    receipt["handoff"]["action"] = "replan"
    receipt["handoff"]["allowed_mutations"] = ["none"]
    receipt["safe_repair_target"]["kind"] = "repair_custody"
    validated = validate_investigator_receipt(
        receipt, expected_context_digest="digest-1"
    )
    assert validated["recommended_action"] == "replan"
    assert validated["safe_repair_target"]["kind"] == "repair_custody"

    receipt["custody_status"] = "consistent"
    receipt["custody_contradictions"] = []
    with pytest.raises(ValueError, match="only for contradictory custody"):
        validate_investigator_receipt(
            receipt, expected_context_digest="digest-1"
        )

    wrapper = (
        REPO_ROOT
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "wrappers"
        / "arnold-repair-loop"
    ).read_text(encoding="utf-8")
    assert "replan with safe_repair_target.kind=repair_custody" in wrapper
    assert 'repair_data_set_outcome "deterministic_failure"' in wrapper
    assert "investigator requires L2 replan before any target mutation" in wrapper


def test_unknown_or_guard_weakening_receipt_fails_closed() -> None:
    receipt = _receipt()
    receipt["custody_status"] = "unknown"
    receipt["custody_contradictions"] = []
    with pytest.raises(ValueError, match="unknown custody must fail closed"):
        validate_investigator_receipt(receipt, expected_context_digest="digest-1")

    receipt = _receipt()
    receipt["guard_weakening_risk"] = "identified"
    with pytest.raises(ValueError, match="guard weakening risk must fail closed"):
        validate_investigator_receipt(receipt, expected_context_digest="digest-1")


def test_shared_summary_distinguishes_missing_invalid_and_accepted(tmp_path: Path) -> None:
    assert summarize_investigation_artifacts({})["status"] == "missing"
    context = tmp_path / "context.json"
    receipt_path = tmp_path / "receipt.json"
    context_payload = {"schema_version": "arnold-repair-investigation-context-v1", "target_kind": "l1_repair_target"}
    context_digest = hashlib.sha256(
        json.dumps(context_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context_payload["context_digest"] = context_digest
    _write(context, context_payload)
    _write(receipt_path, _receipt("wrong"))
    repair_data = {
        "investigation": {
            "context_path": str(context),
            "receipt_path": str(receipt_path),
            "context_digest": context_digest,
        }
    }
    assert summarize_investigation_artifacts(repair_data)["status"] == "invalid"
    _write(receipt_path, _receipt(context_digest))
    summary = summarize_investigation_artifacts(repair_data)
    assert summary["status"] == "accepted"
    assert summary["evidence_source_kinds"] == ["plan_state"]
    assert summary["recommended_action"] == "repair_target"


def test_meta_context_uses_common_evidence_and_recovery_semantics(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    marker_dir = tmp_path / "markers"
    goal = marker_dir / "repair-goals" / "demo" / "goal-1.json"
    _write(
        goal,
        {
            "goal_id": "repair-goal-1",
            "checkpoint_digest": "a" * 64,
            "target": {"blocker_id": "blocker-1"},
        },
    )
    _write(
        repair_dir / "demo.repair-data.json",
        {
            "outcome": "running",
            "repair_goal": {
                "goal_id": "repair-goal-1",
                "goal_path": str(goal),
                "checkpoint_digest": "a" * 64,
            },
        },
    )
    _write(marker_dir / "demo.json", {"workspace": "/workspace/demo"})
    context = build_meta_investigation_context(
        session="demo",
        trigger="model_tool_launch_failure",
        repair_data_dir=repair_dir,
        marker_dir=marker_dir,
        arnold_src=REPO_ROOT,
    )
    assert context["target_kind"] == "l2_repair_system"
    assert context["schema_version"] == META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA
    assert context["authorization"]["mutation_authorized"] is False
    assert context["identity"]["repair_goal_id"] == "repair-goal-1"
    assert {item["kind"] for item in context["evidence_refs"]} >= {
        "repair_data", "session_marker", "repair_goal"
    }
    context_path = tmp_path / "meta-context.json"
    _write(context_path, context)
    observation = build_meta_observation_bundle(context_path)
    required = observation["required_receipt_shape"]
    assert required["recommended_action"] == "replan"
    assert required["safe_repair_target"]["kind"] == "repair_custody"
    assert required["handoff"] == {
        "action": "replan",
        "allowed_mutations": ["none"],
        "forbidden_mutations": [
            "direct_chain_state_edit",
            "recover_state",
            "hand_advance_chain",
        ],
    }


def test_pathological_meta_context_stays_tiny_and_reference_only(tmp_path: Path) -> None:
    repair_dir = tmp_path / "repair-data"
    marker_dir = tmp_path / "markers"
    goal = marker_dir / "repair-goals" / "demo" / "goal-pathological.json"
    _write(
        goal,
        {
            "goal_id": "repair-goal-pathological",
            "checkpoint_digest": "b" * 64,
            "target": {"blocker_id": "blocker-pathological"},
            "frozen_checkpoint": {"history": ["goal-history" * 100_000]},
        },
    )
    huge = "broad-status-history-log" * 50_000
    _write(
        repair_dir / "demo.repair-data.json",
        {
            "outcome": "deterministic_failure",
            "attempts": [
                {
                    "attempt_id": index,
                    "failure_context": huge,
                    "post_launch_failure_context": huge,
                    "logs": huge,
                }
                for index in range(3)
            ],
            "repair_goal": {
                "goal_id": "repair-goal-pathological",
                "goal_path": str(goal),
                "checkpoint_digest": "b" * 64,
            },
            "resident_delegation": {
                "custody_id": "custody-1",
                "source_record_id": "message-1",
                "root_run_id": "run-1",
            },
        },
    )
    _write(marker_dir / "demo.json", {"workspace": "/workspace/demo", "history": huge})

    context = build_meta_investigation_context(
        session="demo",
        trigger="l1_custody_failure",
        repair_data_dir=repair_dir,
        marker_dir=marker_dir,
        arnold_src=REPO_ROOT,
    )

    encoded = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    assert len(encoded) < 16 * 1024
    assert len(encoded) <= MAX_CONTEXT_BYTES
    assert huge[:100] not in encoded.decode()
    assert "attempts" not in context
    assert "required_investigator_output" not in context
    assert validate_meta_investigation_context(context)["context_digest"] == context["context_digest"]

    context_path = tmp_path / "meta-context.json"
    _write(context_path, context)
    observation = build_meta_observation_bundle(context_path)
    observed_kinds = {item["kind"] for item in observation["observations"]}
    assert {"resident_delegation", "source_contract"} <= observed_kinds
    assert observed_kinds <= EVIDENCE_SOURCE_KINDS

    receipt = _receipt(context["context_digest"], target_kind="l2_repair_system")
    receipt["evidence_sources"] = observation["observations"]
    assert validate_investigator_receipt(
        receipt, expected_context_digest=context["context_digest"]
    )["target_kind"] == "l2_repair_system"

    context["authorization"]["mutation_authorized"] = True
    with pytest.raises(ValueError, match="must not authorize mutation"):
        validate_meta_investigation_context(context)


def test_repair_loop_embeds_bounded_context_for_sandbox_independent_investigation() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert '<authoritative_repair_context>' in wrapper
    assert 'cat "$INVESTIGATION_CONTEXT_PATH" >> "$INVESTIGATOR_PROMPT_PATH"' in wrapper
    assert "does not depend on filesystem sandbox availability" in wrapper
    assert "<investigation_handoff>" in wrapper


def test_l1_investigation_precedes_every_target_mutation_and_failures_stop() -> None:
    wrapper = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")
    main = wrapper[wrapper.index('ensure_repair_goal_custody || exit 78') :]
    investigation = main.index("run_repair_investigator_turn || investigator_rc=$?")
    for mutation in (
        'repair_source_initiative_if_possible; then',
        'repair_source_workspace_if_possible; then',
        'repair_dependency_manifests_if_possible; then',
        'mechanical_launch_step "0"',
        'run_dev_fix_turn "$iteration"',
    ):
        assert main.index(mutation) > investigation
    assert 'repair_clear_stale_state_if_needed 2>>"$LOG"' not in main
    assert "direct stale-state JSON synchronization is outside the recover_state receipt" in main
    assert "recover_state receipt does not authorize the exact bounded supported CLI" in wrapper
    fail_closed = main[investigation : main.index("GLM_MODEL=", investigation)]
    assert "investigation failed or produced no valid handoff; target remains unchanged" in fail_closed
    assert '"status": "failed"' in wrapper
    assert '"failure_phase": failure_phase' in wrapper
    assert '"error_excerpt": error_excerpt' in wrapper
    assert 'repair_data_set_outcome "fixer_infrastructure_failure"' in wrapper
    assert "require_investigation_before_mutation" in wrapper


def test_l2_requires_read_only_receipt_before_mutating_owner() -> None:
    wrapper = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"
    ).read_text(encoding="utf-8")
    investigate = wrapper.index("if ! run_meta_repair_investigation; then")
    mutation = wrapper.index("dispatching Codex meta-repair", investigate)
    assert "--sandbox read-only" in wrapper[:mutation]
    assert "require_meta_investigation_before_mutation" in wrapper[investigate:mutation]
    assert "L2 investigation failed or returned no valid receipt; refusing all repair mutation" in wrapper
    assert "persist_meta_investigation_failure" in wrapper
    assert "Durable investigate-to-repair handoff" in wrapper


def test_auditor_reuses_shared_investigation_semantics_without_changing_dispatch() -> None:
    auditor = (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor"
    ).read_text(encoding="utf-8")
    assert (
        "from arnold_pipelines.megaplan.cloud.repair_investigation import "
        "summarize_investigation_artifacts"
    ) in auditor
    assert 'summarize_investigation_artifacts(payload, field="investigation")' in auditor
    assert 'summarize_investigation_artifacts(payload, field="meta_investigation")' in auditor
    assert "repair_without_valid_investigation:" in auditor
    assert "meta_repair_without_valid_investigation:" in auditor
    assert '"mode": "autofix_attempted" if (launch_attempted or repair_dispatched) else "report_only"' in auditor
    assert "Autofix mutation blocked; report-only mode confirmed" in auditor


def test_mechanical_fence_keeps_exact_status_channel_clean() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert (
        'log "mechanical relaunch fenced: correct target worker is alive and fresh '
        'session=$session iteration=$iteration" >&2'
    ) in wrapper
    assert (
        'log "mechanical relaunch fenced: deterministic owner circuit requires replan '
        'session=$session iteration=$iteration" >&2'
    ) in wrapper
