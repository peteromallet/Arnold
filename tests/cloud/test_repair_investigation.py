from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.repair_investigation import (
    MAX_CONTEXT_BYTES,
    REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
    build_meta_investigation_context,
    build_investigation_context,
    summarize_investigation_artifacts,
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
    source = tmp_path / "arnold"
    source.mkdir()
    _write(repair_dir / "demo.repair-data.json", {"outcome": "running"})
    _write(marker_dir / "demo.json", {"workspace": "/workspace/demo"})
    context = build_meta_investigation_context(
        session="demo",
        trigger="model_tool_launch_failure",
        repair_data_dir=repair_dir,
        marker_dir=marker_dir,
        arnold_src=source,
    )
    assert context["target_kind"] == "l2_repair_system"
    assert context["custody_status"] == "contradictory"
    assert context["intended_recovery"]["beyond_stage_required"] is True
    assert {item["kind"] for item in context["evidence_sources"]} >= {
        "repair_data", "session_marker", "source_tree"
    }


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
        'repair_clear_stale_state_if_needed 2>>"$LOG"',
        'mechanical_launch_step "0"',
        'run_dev_fix_turn "$iteration"',
    ):
        assert main.index(mutation) > investigation
    fail_closed = main[investigation : main.index("GLM_MODEL=", investigation)]
    assert "investigation failed or produced no valid handoff; target remains unchanged" in fail_closed
    assert '"status": "failed"' in wrapper
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
