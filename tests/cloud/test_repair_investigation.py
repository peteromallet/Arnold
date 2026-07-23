from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_investigation
from arnold_pipelines.megaplan.cloud.repair_investigation import (
    EVIDENCE_SOURCE_KINDS,
    MAX_CONTEXT_BYTES,
    META_REPAIR_INVESTIGATION_ENVELOPE_SCHEMA,
    REPAIR_INVESTIGATOR_RECEIPT_SCHEMA,
    build_meta_investigation_context,
    build_meta_observation_bundle,
    build_investigation_context,
    build_repair_observation_bundle,
    load_bounded_investigator_receipt,
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
        f"env PYTHONSAFEPATH=1 PYTHONPATH={REPO_ROOT} python -P -m "
        f"arnold_pipelines.megaplan chain start --spec {spec} "
        f"--project-dir {workspace}"
    )
    assert context["required_investigator_output"][
        "action_specific_handoff_examples"
    ]["recover_state"]["allowed_mutations"] == [f"supported_cli:{supported_cli}"]


def test_context_uses_identity_bound_profile_preserving_marker_relaunch(
    tmp_path: Path,
) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    marker_dir = tmp_path / "markers"
    marker_command = (
        "export PYTHONPATH=/runtime/pinned; "
        "python -c \"assert 'pinned-sha'\"; "
        f"python -m arnold_pipelines.megaplan chain start --spec {spec} "
        f"--project-dir {workspace} --no-git-refresh --no-push"
    )
    _write(
        marker_dir / "custody-control-plane-20260714.json",
        {
            "session": "custody-control-plane-20260714",
            "workspace": str(workspace),
            "remote_spec": str(spec),
            "relaunch_command": marker_command,
            "runtime_attestation": {
                "expected_commit": "pinned-sha",
                "expected_import": "/runtime/pinned",
            },
        },
    )
    request_payload = json.loads(request.read_text(encoding="utf-8"))
    request_payload["marker_dir"] = str(marker_dir)
    request_payload["target"] = {
        "plan_name": "current-m5a",
        "configured_profile": "partnered-5",
        "recovery_contract": {"preserve_configured_profile": True},
    }
    _write(request, request_payload)
    state_path = workspace / ".megaplan/plans/current-m5a/state.json"
    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    state_payload["config"] = {"profile": "partnered-5"}
    _write(state_path, state_payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    boundaries = context["safe_repair_boundaries"]
    assert boundaries["supported_recovery_cli"] == marker_command
    assert boundaries["marker_relaunch_binding"] == {
        "verified": True,
        "marker_path": str(marker_dir / "custody-control-plane-20260714.json"),
        "runtime_commit": "pinned-sha",
        "runtime_import": "/runtime/pinned",
        "configured_profile": "partnered-5",
        "profile_preserved": True,
        "no_git_refresh": True,
        "no_push": True,
    }
    context_path = tmp_path / "bounded-context.json"
    _write(context_path, context)
    observation = build_repair_observation_bundle(context_path)
    encoded = json.dumps(observation, sort_keys=True, separators=(",", ":"))
    assert len(encoded.encode()) <= repair_investigation.MAX_OBSERVATION_BUNDLE_BYTES
    recover_mutation = observation["required_receipt_shape"][
        "action_specific_handoff_examples"
    ]["recover_state"]["allowed_mutations"][0]
    assert recover_mutation.count(marker_command) == 1
    assert observation["analysis_context"]["safe_repair_boundaries"][
        "supported_recovery_cli"
    ].startswith("<exact command carried once")


def test_historical_recount_recovery_uses_guarded_override_before_chain_start(
    tmp_path: Path,
) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state_path = workspace / ".megaplan/plans/current-m5a/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    failure_message = "gate structural enum mismatch"
    state["latest_failure"] = {
        "kind": "repeated_failure_signature",
        "metadata": {
            "count": 3,
            "failure_step": "gate",
            "failure_message": failure_message,
        },
    }
    state["resume_cursor"] = {
        "phase": "gate",
        "retry_strategy": "repair_repeated_failure",
    }
    state["history"] = [
        {
            "step": "gate",
            "result": "error",
            "message": failure_message,
            "timestamp": "2026-07-16T15:30:03Z",
        },
        {
            "step": "gate",
            "result": "success",
            "timestamp": "2026-07-16T15:32:13Z",
            "artifact_hash": "fresh-gate-artifact",
        },
    ]
    _write(state_path, state)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    supported_cli = context["safe_repair_boundaries"]["supported_recovery_cli"]
    assert context["historical_failure_recovery"]["applicable"] is True
    assert context["historical_failure_recovery"]["evidence"][
        "historical_failure_index"
    ] == 0
    assert "override recover-blocked" in supported_cli
    assert "--plan current-m5a" in supported_cli
    assert " && " in supported_cli
    assert supported_cli.endswith(
        f"chain start --spec {spec} --project-dir {workspace}"
    )
    assert context["required_investigator_output"][
        "action_specific_handoff_examples"
    ]["recover_state"]["allowed_mutations"] == [f"supported_cli:{supported_cli}"]


def test_verified_deterministic_phase_repair_uses_guarded_override_before_chain_start(
    tmp_path: Path,
) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state_path = workspace / ".megaplan/plans/current-m5a/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["latest_failure"] = {
        "kind": "deterministic_phase_failure",
        "phase": "finalize",
        "fingerprint": "f" * 64,
        "message": "critique_finding_identity_reused",
        "metadata": {"count": 3},
    }
    state["resume_cursor"] = {
        "phase": "finalize",
        "retry_strategy": "repair_phase_contract",
    }
    _write(state_path, state)
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=workspace,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=workspace, check=True
    )
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "verified target repair"],
        cwd=workspace,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    repair_payload = json.loads(repair_data.read_text(encoding="utf-8"))
    repair_payload["attempts"].append(
        {
            "attempt_id": 23,
            "dev_turn_rc": 0,
            "dev_fix_sha": head,
            "problem_signature": {
                "failure_kind": "deterministic_phase_failure",
                "milestone_or_plan": "current-m5a",
                "phase_or_step": "finalize",
            },
            "dev_report": {
                "classification": "live_failure_repaired_in_target_workspace_pending_wrapper_recovery_proof",
                "validation": ["focused tests passed"],
            },
        }
    )
    _write(repair_data, repair_payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    recovery = context["phase_contract_recovery"]
    supported_cli = context["safe_repair_boundaries"]["supported_recovery_cli"]
    assert recovery["applicable"] is True
    assert recovery["repair_evidence"]["dev_fix_sha"] == head
    assert "override recover-blocked" in supported_cli
    assert f"--repair-commit {head}" in supported_cli
    assert (
        f"--failure-fingerprint {recovery['repair_evidence']['failure_fingerprint']}"
        in supported_cli
    )
    assert supported_cli.count(f"PYTHONPATH={REPO_ROOT}") == 2
    assert supported_cli.count("PYTHONSAFEPATH=1") == 2
    assert f"commit {head}" in supported_cli
    assert supported_cli.endswith(
        f"chain start --spec {spec} --project-dir {workspace}"
    )
    assert context["required_investigator_output"][
        "action_specific_handoff_examples"
    ]["recover_state"]["allowed_mutations"] == [f"supported_cli:{supported_cli}"]


def test_l1_broker_observation_is_digest_bound_typed_and_bounded(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )
    context_path = tmp_path / "context.json"
    _write(context_path, context)

    observation = build_repair_observation_bundle(context_path)

    assert observation["schema_version"] == "arnold-repair-observation-bundle-v1"
    assert observation["context_digest"] == context["context_digest"]
    assert observation["access_verified"] is True
    assert observation["required_receipt_shape"]["context_digest"] == context["context_digest"]
    assert observation["external_guard_applicability"] == {
        "applies": False,
        "chain_state": "blocked",
        "failure_kind": "",
        "failure_phase": "execute",
        "reason": "external PR/CI state is corroborating context for the active non-PR blocker",
    }
    assert "must not displace the actual failure" in observation[
        "external_guard_policy"
    ]
    assert {item["kind"] for item in observation["observations"]} >= {
        "plan_state",
        "repair_data",
        "repair_queue",
    }
    assert len(json.dumps(observation, sort_keys=True, separators=(",", ":")).encode()) <= 48 * 1024

    context["exact_error"]["message"] = "tampered"
    _write(context_path, context)
    with pytest.raises(ValueError, match="context digest disagrees"):
        build_repair_observation_bundle(context_path)


def test_l1_broker_observation_fails_closed_above_48_kib(tmp_path: Path) -> None:
    context = {
        "schema_version": "arnold-repair-investigation-context-v1",
        "context_digest": "",
        "session": "demo",
        "goal_id": "goal-demo",
        "target_kind": "l1_repair_target",
        "exact_error": {"message": "x" * 50_000},
        "evidence_sources": [],
        "required_investigator_output": {},
    }
    digest_payload = {key: value for key, value in context.items() if key != "context_digest"}
    context["context_digest"] = hashlib.sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    context_path = tmp_path / "oversized-observation-context.json"
    _write(context_path, context)
    assert context_path.stat().st_size <= MAX_CONTEXT_BYTES

    with pytest.raises(ValueError, match="brokered repair observations exceed 48 KiB"):
        build_repair_observation_bundle(context_path)


def test_external_snapshot_uses_authoritative_chain_pr_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "number": 255,
                    "state": "OPEN",
                    "headRefName": "different-from-local-branch",
                    "statusCheckRollup": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(repair_investigation.subprocess, "run", fake_run)
    snapshot_path = repair_investigation._external_pr_snapshot(
        session="demo",
        workspace=workspace,
        repair_root=tmp_path / "repair-data",
        pull_request_number=255,
    )

    assert commands == [
        [
            "gh",
            "pr",
            "view",
            "255",
            "--json",
            "number,url,state,isDraft,mergeStateStatus,headRefName,headRefOid,"
            "baseRefName,baseRefOid,updatedAt,statusCheckRollup",
        ]
    ]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["available"] is True
    assert snapshot["pull_request"]["number"] == 255
    assert snapshot["query"].startswith("gh pr view 255")


def test_open_green_pr_remains_pending_for_state_recovery() -> None:
    observed = repair_investigation._bounded_observation(
        "external_state",
        json.dumps(
            {
                "available": True,
                "pull_request": {
                    "number": 255,
                    "state": "OPEN",
                    "isDraft": False,
                    "mergeStateStatus": "CLEAN",
                    "headRefOid": "b" * 40,
                    "statusCheckRollup": [
                        {
                            "name": "test",
                            "status": "COMPLETED",
                            "conclusion": "SUCCESS",
                        }
                    ],
                },
            }
        ).encode(),
    )

    assert observed["external_guard"] == {
        "status": "pending",
        "failing_checks": [],
        "pending_checks": [],
        "pr_state": "OPEN",
        "is_draft": False,
        "merge_state": "CLEAN",
        "head_oid": "b" * 40,
    }


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


def test_quality_block_context_carries_bounded_review_rework_evidence(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state = workspace / ".megaplan/plans/current-m5a/state.json"
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload["latest_failure"] = {
        "kind": "review_quality_blocked_unknown",
        "phase": "review",
        "message": "review rework budget exhausted",
    }
    _write(state, state_payload)
    _write(
        state.parent / "phase_result.json",
        {
            "phase": "review",
            "exit_kind": "blocked_by_quality",
            "deviations": [{"kind": "quality_gate", "message": "wrapper gate failed"}],
        },
    )
    _write(
        state.parent / "review.json",
        {
            "review_verdict": "needs_rework",
            "summary": "wrapper continuation opens with fake evidence",
            "issues": ["wrong state loader"],
            "criteria": [
                {
                    "name": "wrapper paths fail closed",
                    "pass": "fail",
                    "evidence": "load_chain_state received the state path",
                }
            ],
            "rework_items": [
                {
                    "task_id": "T24",
                    "issue": "wrapper acceptance gate opens",
                    "expected": "invalid acceptance evidence blocks",
                    "actual": "gate_open=True",
                    "evidence_file": "arnold_pipelines/megaplan/cloud/wrapper_acceptance_gate.py",
                    "deterministic_check": {
                        "command": "python bounded_wrapper_probe.py",
                        "post_status": "failed",
                    },
                }
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

    quality = context["durable_quality_block"]
    assert quality["active"] is True
    assert quality["recover_state_allowed"] is False
    assert quality["review_artifact"]["path"].endswith("review.json")
    assert "recover_state" not in quality["allowed_actions"]
    review_source = next(
        item for item in context["evidence_sources"] if item["kind"] == "review_artifact"
    )
    assert review_source["path"].endswith("review.json")
    assert review_source["observed"]["rework_items"][0]["task_id"] == "T24"
    assert review_source["observed"]["rework_items"][0]["actual"] == "gate_open=True"
    required = context["required_investigator_output"]
    assert required["recommended_action"] == "repair_target"
    assert required["safe_repair_target"]["kind"] == "target_workspace"
    assert required["handoff"]["action"] == "repair_target"
    assert "wrapper_acceptance_gate.py" in required["handoff"]["allowed_mutations"][0]
    assert "recover_state" in required["prohibited_actions"]
    assert len(json.dumps(context).encode()) <= MAX_CONTEXT_BYTES


def test_oversized_review_artifact_fails_closed(tmp_path: Path) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state = workspace / ".megaplan/plans/current-m5a/state.json"
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload["latest_failure"] = {
        "kind": "quality_gate_blocked",
        "phase": "review",
        "message": "blocked",
    }
    _write(state, state_payload)
    (state.parent / "review.json").write_text("x" * (2 * 1024 * 1024 + 1), encoding="utf-8")

    with pytest.raises(ValueError, match="exceeds 2 MiB bound"):
        build_investigation_context(
            workspace=workspace,
            session="custody-control-plane-20260714",
            remote_spec=str(spec),
            repair_data_path=repair_data,
            request_path=request,
            goal_path=goal,
        )


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
    goal_payload = json.loads(goal.read_text(encoding="utf-8"))
    goal_payload["target"].update(
        {
            "session": "custody-control-plane-20260714",
            "workspace": str(workspace),
            "remote_spec": str(spec),
        }
    )
    goal_payload["active_replan_epoch"] = 3
    goal_payload["l2_replans"] = [
        {
            "epoch": 3,
            "context_digest": context_digest,
            "frozen_checkpoint_digest": "abc",
        }
    ]
    _write(goal, goal_payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
        l2_handoff_path=access,
        l2_context_digest=context_digest,
        l2_replan_epoch=3,
    )

    assert context["exact_error"]["failure_kind"] == "external_pr_ci_guard_failed"
    assert context["custody_status"] == "consistent"
    assert context["custody_contradictions"] == []
    assert context["request"]["stage_transition"] is True
    assert context["request"]["stage_transition_remains_same_goal"] is True
    assert context["goal_continuity"]["status"] == "successor_blocker"
    assert context["goal_continuity"]["same_goal_continuity_valid"] is True
    assert context["l2_replan_authorization"] == {
        "verified": True,
        "replan_epoch": 3,
        "context_digest": context_digest,
        "frozen_checkpoint_digest": "abc",
        "allowed_recovery": "recover_state_via_supported_cli_only",
        "forbidden": [
            "direct_state_edit",
            "hand_advance_chain",
            "duplicate_live_worker",
        ],
    }
    source = next(
        item for item in context["evidence_sources"] if item["kind"] == "external_state"
    )
    assert source["path"] == str(external)

    with pytest.raises(ValueError, match="replan authorization is stale"):
        build_investigation_context(
            workspace=workspace,
            session="custody-control-plane-20260714",
            remote_spec=str(spec),
            repair_data_path=repair_data,
            request_path=request,
            goal_path=goal,
            l2_handoff_path=access,
            l2_context_digest=context_digest,
            l2_replan_epoch=2,
        )

    clear_external = {
        "available": True,
        "external_guard": {
            "status": "clear",
            "failing_checks": [],
            "pending_checks": [],
        },
    }
    _write(external, clear_external)
    clear_encoded = external.read_bytes()
    access_payload = json.loads(access.read_text(encoding="utf-8"))
    access_payload["observations"][0].update(
        {
            "sha256": hashlib.sha256(clear_encoded).hexdigest(),
            "size_bytes": len(clear_encoded),
            "observed": clear_external,
        }
    )
    _write(access, access_payload)
    recovery_context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
        l2_handoff_path=access,
        l2_context_digest=context_digest,
        l2_replan_epoch=3,
    )
    assert recovery_context["exact_error"] == {
        "failure_kind": "active_unowned_repair_goal",
        "message": (
            "L2 verified the recovery epoch; no canonical runner is live and "
            "the exact supported recovery CLI has not yet produced accepted progress"
        ),
        "replan_epoch": 3,
    }

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
            l2_replan_epoch=3,
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


def test_investigator_receipt_loader_accepts_only_exact_single_json_fence(
    tmp_path: Path,
) -> None:
    receipt = _receipt()
    fenced = tmp_path / "fenced.json"
    fenced.write_text(
        "```json\n" + json.dumps(receipt, indent=2) + "\n```\n",
        encoding="utf-8",
    )

    assert load_bounded_investigator_receipt(fenced) == receipt

    for index, candidate in enumerate(
        (
            "prose\n" + fenced.read_text(encoding="utf-8"),
            fenced.read_text(encoding="utf-8") + "prose\n",
            "```json\n{}\n```\n```json\n{}\n```\n",
            "```python\n{}\n```\n",
        )
    ):
        invalid = tmp_path / f"invalid-{index}.json"
        invalid.write_text(candidate, encoding="utf-8")
        with pytest.raises(ValueError, match="not valid UTF-8 JSON"):
            load_bounded_investigator_receipt(invalid)


def test_receipt_validator_cli_accepts_exact_single_json_fence(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        "```json\n" + json.dumps(_receipt(), indent=2) + "\n```\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arnold_pipelines.megaplan.cloud.repair_investigation",
            "validate",
            "--receipt",
            str(receipt),
            "--context-digest",
            "digest-1",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["receipt_digest"]


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


def test_nonoperative_external_guard_does_not_displace_gate_recovery() -> None:
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
        "rationale": "reconcile stale repeated-failure accounting",
    }
    observation = {
        "context_digest": "digest-1",
        "external_guard_applicability": {
            "applies": False,
            "reason": "the active blocker is a gate accounting failure",
        },
        "observations": [
            {
                "kind": "external_state",
                "observed": {"external_guard": {"status": "pending"}},
            }
        ],
    }

    validated = validate_investigator_receipt(
        receipt,
        expected_context_digest="digest-1",
        observation_bundle=observation,
    )

    assert validated["recommended_action"] == "recover_state"


def test_l1_bundle_propagates_nonoperative_guard_into_recovery_validation(
    tmp_path: Path,
) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )
    context_path = tmp_path / "context.json"
    _write(context_path, context)
    observation = build_repair_observation_bundle(context_path)
    observation["observations"].append(
        {
            "kind": "external_state",
            "observed": {"external_guard": {"status": "pending"}},
        }
    )
    receipt = _receipt(context["context_digest"], target_kind="l1_repair_target")
    receipt["recommended_action"] = "recover_state"
    receipt["handoff"] = {
        "action": "recover_state",
        "allowed_mutations": [
            f"supported_cli:python -P -m arnold_pipelines.megaplan chain start "
            f"--spec {spec} --project-dir {workspace}"
        ],
        "forbidden_mutations": [
            "direct_chain_state_edit",
            "hand_advance_chain",
            "guard_weakening",
        ],
    }
    receipt["safe_repair_target"] = {
        "kind": "plan_state_via_cli",
        "scope": str(workspace),
        "rationale": "resume through the supported chain command",
    }

    validated = validate_investigator_receipt(
        receipt,
        expected_context_digest=context["context_digest"],
        observation_bundle=observation,
        investigation_context=context,
    )

    assert validated["recommended_action"] == "recover_state"


def test_plan_observation_exposes_failure_superseded_by_same_phase_success() -> None:
    plan_state = {
        "current_state": "blocked",
        "latest_failure": {
            "kind": "repeated_failure_signature",
            "metadata": {
                "count": 3,
                "failure_step": "gate",
                "failure_message": "gate verdict did not match the structural enum",
                "failure_history_index": 0,
            },
        },
        "history": [
            {
                "step": "gate",
                "result": "error",
                "message": "gate verdict did not match the structural enum",
                "timestamp": "2026-07-16T15:30:03Z",
            },
            {
                "step": "gate",
                "result": "success",
                "timestamp": "2026-07-16T15:32:13Z",
                "artifact_hash": "fresh-gate-artifact",
            },
        ],
    }

    observed = repair_investigation._bounded_observation(
        "plan_state", json.dumps(plan_state).encode()
    )

    evidence = observed["superseded_failure_evidence"]
    assert evidence["detected"] is True
    assert evidence["historical_failure_index"] == 0
    assert evidence["failure_step"] == "gate"
    assert "occurrence tracking" in evidence["root_cause_hint"]


def test_external_guard_applicability_follows_current_workflow_phase() -> None:
    blocked_gate = repair_investigation._external_guard_applicability(
        [
            {"kind": "chain_state", "observed": {"last_state": "blocked"}},
            {
                "kind": "plan_state",
                "observed": {
                    "current_phase": "gate",
                    "latest_failure": {"kind": "repeated_failure_signature"},
                },
            },
        ]
    )
    awaiting_pr = repair_investigation._external_guard_applicability(
        [
            {
                "kind": "chain_state",
                "observed": {"last_state": "awaiting_pr_merge"},
            }
        ]
    )
    unknown_stage = repair_investigation._external_guard_applicability([])

    assert blocked_gate["applies"] is False
    assert awaiting_pr["applies"] is True
    assert unknown_stage["applies"] is True


def test_missing_quality_commit_custody_rejects_state_recovery_handoff() -> None:
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
                "observed": {"external_guard": {"status": "clear"}},
            },
            {
                "kind": "repair_goal",
                "observed": {
                    "last_evaluation": {
                        "quality_resolution_commit_custody": {
                            "verified": False,
                            "missing_commits": ["0beb5e8d"],
                        }
                    }
                },
            },
        ],
    }
    with pytest.raises(ValueError, match="missing durable quality-resolution commits"):
        validate_investigator_receipt(
            receipt,
            expected_context_digest="digest-1",
            observation_bundle=observation,
        )

    with pytest.raises(ValueError, match="missing durable quality-resolution commits"):
        validate_investigator_receipt(
            receipt,
            expected_context_digest="digest-1",
            investigation_context={
                "context_digest": "digest-1",
                "current": {
                    "quality_resolution_commit_custody": {
                        "verified": False,
                        "missing_commits": ["0beb5e8d"],
                    }
                },
            },
        )


def test_preserve_live_requires_verified_live_worker_evidence() -> None:
    receipt = _receipt()
    receipt["recommended_action"] = "preserve_live"
    receipt["preserve_live"] = True
    receipt["handoff"] = {
        "action": "preserve_live",
        "allowed_mutations": ["none"],
        "forbidden_mutations": ["all_mutations"],
    }
    receipt["safe_repair_target"] = {
        "kind": "none",
        "scope": "current live worker",
        "rationale": "preserve a verified correct worker",
    }
    observation = {
        "context_digest": "digest-1",
        "observations": [
            {
                "kind": "repair_data",
                "observed": {
                    "target": {
                        "active_step_heartbeat": {
                            "active": False,
                            "pid_live": False,
                        }
                    }
                },
            }
        ],
    }

    with pytest.raises(ValueError, match="without verified live-worker evidence"):
        validate_investigator_receipt(
            receipt,
            expected_context_digest="digest-1",
            observation_bundle=observation,
        )

    observation["observations"][0]["observed"]["target"][
        "active_step_heartbeat"
    ] = {"active": True, "pid_live": True}
    validated = validate_investigator_receipt(
        receipt,
        expected_context_digest="digest-1",
        observation_bundle=observation,
    )
    assert validated["recommended_action"] == "preserve_live"


def test_durable_quality_block_rejects_blind_state_recovery_handoff() -> None:
    receipt = _receipt()
    receipt["actual_failure"]["classification"] = "stale_state"
    receipt["recommended_action"] = "recover_state"
    receipt["handoff"] = {
        "action": "recover_state",
        "allowed_mutations": ["supported_cli:python -m megaplan chain start"],
        "forbidden_mutations": ["direct state edit"],
    }
    receipt["safe_repair_target"] = {
        "kind": "plan_state_via_cli",
        "scope": "supported chain start",
        "rationale": "workspace head changed",
    }
    context = {
        "context_digest": "digest-1",
        "durable_quality_block": {
            "active": True,
            "recover_state_allowed": False,
            "review_artifact": {"path": "/workspace/review.json", "present": True},
        },
    }

    with pytest.raises(ValueError, match="cannot replay a durable review-quality block"):
        validate_investigator_receipt(
            receipt,
            expected_context_digest="digest-1",
            investigation_context=context,
        )


def test_durable_quality_block_allows_receipt_bound_recovery_after_target_repair() -> None:
    head = "b" * 40
    receipt = _receipt()
    receipt["actual_failure"]["classification"] = "stale_state"
    receipt["recommended_action"] = "recover_state"
    receipt["handoff"] = {
        "action": "recover_state",
        "allowed_mutations": ["supported_cli:python -m megaplan chain start"],
        "forbidden_mutations": ["direct state edit"],
    }
    receipt["safe_repair_target"] = {
        "kind": "plan_state_via_cli",
        "scope": "supported chain start",
        "rationale": "the bounded target repair is committed at current HEAD",
    }
    context = {
        "context_digest": "digest-1",
        "current": {"workspace_head": head},
        "durable_quality_block": {
            "active": True,
            "recover_state_allowed": True,
            "repair_evidence": {
                "verified": True,
                "workspace_head": head,
                "dev_fix_sha": head,
                "target_kind": "target_workspace",
                "target_scope": "arnold_pipelines/megaplan/cloud/wrapper_acceptance_gate.py",
                "validation_present": True,
            },
        },
    }

    validated = validate_investigator_receipt(
        receipt,
        expected_context_digest="digest-1",
        investigation_context=context,
    )

    assert validated["recommended_action"] == "recover_state"


def test_phase_contract_recovery_requires_fixed_axis_for_verified_target_repair() -> None:
    receipt = _receipt()
    receipt["actual_failure"]["classification"] = "stale_state"
    receipt["recommended_action"] = "recover_state"
    receipt["handoff"] = {
        "action": "recover_state",
        "allowed_mutations": [
            "supported_cli:python -m arnold_pipelines.megaplan override "
            "recover-blocked && python -m arnold_pipelines.megaplan chain start"
        ],
        "forbidden_mutations": ["direct state edit"],
    }
    receipt["safe_repair_target"] = {
        "kind": "plan_state_via_cli",
        "scope": "supported guarded blocked recovery",
        "rationale": "the validated target repair is committed at current HEAD",
    }
    context = {
        "context_digest": "digest-1",
        "phase_contract_recovery": {
            "applicable": True,
            "repair_evidence": {"verified": True},
        },
    }

    with pytest.raises(ValueError, match="validated target repair is fixed"):
        validate_investigator_receipt(
            receipt,
            expected_context_digest="digest-1",
            investigation_context=context,
        )

    receipt["four_axis"]["FIXED"] = "pass"
    validated = validate_investigator_receipt(
        receipt,
        expected_context_digest="digest-1",
        investigation_context=context,
    )
    assert validated["recommended_action"] == "recover_state"


def test_durable_quality_repair_context_is_bound_to_current_head_and_scope(
    tmp_path: Path,
) -> None:
    workspace, spec, repair_data, request, goal = _fixture(tmp_path)
    state = workspace / ".megaplan/plans/current-m5a/state.json"
    state_payload = json.loads(state.read_text(encoding="utf-8"))
    state_payload.update(
        {
            "current_state": "blocked",
            "active_step": None,
            "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "review_quality_blocked_unknown",
                "phase": "review",
            },
        }
    )
    _write(state, state_payload)
    target_scope = "arnold_pipelines/megaplan/cloud/wrapper_acceptance_gate.py"
    _write(
        state.parent / "review.json",
        {
            "review_verdict": "needs_rework",
            "rework_items": [
                {"task_id": "T24", "evidence_file": target_scope, "issue": "bad gate"}
            ],
        },
    )
    import subprocess

    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "bounded repair"], check=True)
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    payload = json.loads(repair_data.read_text(encoding="utf-8"))
    payload["attempts"].append(
        {
            "attempt_id": 19,
            "dev_turn_rc": 0,
            "dev_fix_sha": head,
            "dev_report": {
                "local_commit": head,
                "safe_repair_target": {"kind": "target_workspace", "scope": target_scope},
                "validation": {"focused": "passed"},
            },
        }
    )
    _write(repair_data, payload)

    context = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )

    quality = context["durable_quality_block"]
    assert quality["recover_state_allowed"] is True
    assert quality["repair_evidence"]["workspace_head"] == head
    assert quality["repair_evidence"]["target_scope"] == target_scope
    assert "recover_state" in quality["allowed_actions"]
    assert (
        context["required_investigator_output"]["recommended_action"]
        == "preserve_live|repair_source|repair_target|recover_state|replan"
    )

    payload["attempts"][-1]["dev_report"]["safe_repair_target"]["scope"] = (
        "unrelated/component.py"
    )
    _write(repair_data, payload)
    mismatched = build_investigation_context(
        workspace=workspace,
        session="custody-control-plane-20260714",
        remote_spec=str(spec),
        repair_data_path=repair_data,
        request_path=request,
        goal_path=goal,
    )
    assert mismatched["durable_quality_block"]["recover_state_allowed"] is False


def test_repair_wrapper_validates_receipt_against_durable_context() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert '--context "$INVESTIGATION_CONTEXT_PATH"' in wrapper
    assert "investigation_context=context" in wrapper


def test_repair_wrapper_enforces_separate_commit_and_push_authority() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert 'COMMIT_REPAIRS="${CLOUD_WATCHDOG_COMMIT_REPAIRS:-1}"' in wrapper
    assert 'PUSH_REPAIRS="${CLOUD_WATCHDOG_PUSH_REPAIRS:-0}"' in wrapper
    assert "git push refused: repair push authority is disabled" in wrapper
    assert "gh pr merge refused: remote merge is outside repair authority" in wrapper
    assert 'PATH="$ARNOLD_REPAIR_DELIVERY_AUTHORITY_PATH:$PATH"' in wrapper
    assert "commit and push them in the repo you changed" not in wrapper
    assert "Do not push, force-push, create or merge a remote PR" in wrapper


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
    examples = context["required_investigator_output"][
        "action_specific_handoff_examples"
    ]
    assert set(examples) == {
        "preserve_live", "replan", "repair_source", "repair_target", "recover_state"
    }
    assert all(
        isinstance(example.get("forbidden_mutations"), list)
        and example["forbidden_mutations"]
        for example in examples.values()
    )

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
    assert summary["actual_failure"]["classification"] == "custody_failure"
    assert summary["actual_failure"]["mechanism"]


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
            "last_evaluation": {
                "quality_resolution_commit_custody": {
                    "verified": False,
                    "required_commits": ["0beb5e8d"],
                    "missing_commits": ["0beb5e8d"],
                }
            },
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
            "meta_investigation": {
                "context_digest": "stale-context-digest-that-must-not-be-reprompted",
                "actual_failure": {"classification": "custody_failure"},
                "recommended_action": "replan",
                "receipt_path": "/tmp/prior-receipt.json",
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
    assert required["context_digest"] == context["context_digest"]
    assert "stale-context-digest-that-must-not-be-reprompted" not in json.dumps(
        observation, sort_keys=True
    )
    repair_observation = next(
        item for item in observation["observations"] if item["kind"] == "repair_data"
    )
    assert repair_observation["observed"]["prior_meta_investigation_summary"] == {
        "actual_failure": {"classification": "custody_failure"},
        "recommended_action": "replan",
        "receipt_path": "/tmp/prior-receipt.json",
    }
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
    assert observation["quality_resolution_commit_custody"]["verified"] is False
    assert "0beb5e8d" in observation["quality_resolution_commit_custody"][
        "missing_commits"
    ]
    assert "Missing durable quality-resolution commits" in observation[
        "quality_commit_policy"
    ]


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


def test_meta_context_prefers_inherited_delegation_over_stale_repair_data(
    tmp_path: Path,
) -> None:
    repair_dir = tmp_path / "repair-data"
    marker_dir = tmp_path / "markers"
    goal = marker_dir / "repair-goals" / "demo" / "goal.json"
    stale = {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "correlation_id": "discord-corr-stale",
        "custody_id": "discord-custody-stale",
        "resident_conversation_id": "rconv_stale",
        "source_record_id": "msg_stale",
        "conversation_key": "discord:dm:123",
        "discord_message_id": "111",
        "reply_to_message_id": "111",
        "dm_user_id": "123",
        "root_run_id": "root-stale",
    }
    inherited = {
        **stale,
        "correlation_id": "discord-corr-current",
        "custody_id": "discord-custody-current",
        "resident_conversation_id": "rconv_current",
        "source_record_id": "msg_current",
        "discord_message_id": "222",
        "reply_to_message_id": "222",
        "root_run_id": "root-current",
    }
    _write(
        goal,
        {
            "goal_id": "repair-goal-current",
            "checkpoint_digest": "a" * 64,
            "target": {"blocker_id": "blocker-current"},
        },
    )
    _write(
        repair_dir / "demo.repair-data.json",
        {
            "repair_goal": {
                "goal_id": "repair-goal-current",
                "checkpoint_digest": "a" * 64,
                "goal_path": str(goal),
            },
            "blocker_id": "blocker-current",
            "resident_delegation": stale,
        },
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write(marker_dir / "demo.json", {"workspace": str(workspace)})

    context = build_meta_investigation_context(
        session="demo",
        trigger="post_fixer_recovery_gate_failed",
        repair_data_dir=repair_dir,
        marker_dir=marker_dir,
        arnold_src=REPO_ROOT,
        resident_delegation=inherited,
    )

    provenance_ref = context["provenance_ref"]
    provenance_path = Path(provenance_ref["path"])
    assert provenance_ref["json_pointer"] == ""
    assert provenance_ref["source_record_id"] == "msg_current"
    assert provenance_ref["root_run_id"] == "root-current"
    assert "resident-delegation-" in provenance_path.name
    assert json.loads(provenance_path.read_text(encoding="utf-8"))[
        "custody_id"
    ] == "discord-custody-current"
    assert "msg_stale" not in provenance_path.read_text(encoding="utf-8")
    validate_meta_investigation_context(context)


def test_repair_loop_uses_bounded_context_pointer_from_sandbox_root() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")

    assert '<authoritative_repair_context>' not in wrapper
    assert 'cat "$INVESTIGATION_CONTEXT_PATH" >> "$INVESTIGATOR_PROMPT_PATH"' not in wrapper
    assert '--project-dir "$RUN_DIR"' in wrapper
    assert '(cd "$RUN_DIR" && "${managed_cmd[@]}")' in wrapper
    assert 'type: arnold-repair-investigation-context' in wrapper
    assert 'sha256: $context_sha256' in wrapper
    assert 'prompt_bytes > 65536' in wrapper
    assert 'bwrap --ro-bind / / true' in wrapper
    assert 'investigator_mode="brokered_no_tools"' in wrapper
    assert '--toolsets ""' in wrapper
    assert "repair_investigation observe" in wrapper
    assert '--context "$INVESTIGATION_CONTEXT_PATH"' in wrapper
    assert '"${context_build_cmd[@]}" >/dev/null 2>"$INVESTIGATION_BUILD_ERROR_PATH"' in wrapper
    assert '--output "$INVESTIGATION_OBSERVATION_PATH" >/dev/null 2>>"$LOG"' in wrapper
    meta_wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"
    ).read_text(encoding="utf-8")
    assert '--output "$META_INVESTIGATION_CONTEXT_PATH" >/dev/null 2>>"$RUN_LOG"' in meta_wrapper
    assert '--output "$META_INVESTIGATION_OBSERVATION_PATH" >/dev/null 2>>"$RUN_LOG"' in meta_wrapper
    assert "<investigation_handoff>" in wrapper


def test_repair_loop_has_one_bounded_invalid_receipt_correction() -> None:
    wrapper = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")
    function = wrapper[
        wrapper.index("run_repair_investigator_turn() {") :
        wrapper.index("\nrun_dev_fix_turn()", wrapper.index("run_repair_investigator_turn() {"))
    ]

    assert ":correction:1" in function
    assert ":correction:2" not in function
    assert "invalid_candidate_receipt; path:" in function
    assert "validator_error; path:" in function
    assert 'cat "$invalid_receipt_path"' in function
    assert 'if [[ "$investigator_mode" == "brokered_no_tools" ]]' in function
    assert '<verified_bounded_observation>' in function
    assert '${validation_output:0:2000}' in function
    assert "invalid_receipt_bytes > 65536" in function
    assert "prompt_bytes > 65536" in function


def test_l1_and_l2_consume_receipts_through_bounded_transport_loader() -> None:
    l1 = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"
    ).read_text(encoding="utf-8")
    l2 = (
        REPO_ROOT
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"
    ).read_text(encoding="utf-8")

    assert l1.count("load_bounded_investigator_receipt") >= 4
    assert l2.count("load_bounded_investigator_receipt") >= 5
    assert 'receipt = json.loads(Path(receipt_path).read_text' not in l1
    assert 'receipt = json.loads(receipt_path.read_text' not in l1
    assert 'json.loads(Path(receipt_path).read_text' not in l2
    assert 'json.loads(pathlib.Path(receipt_path).read_text' not in l2


def test_receipt_validator_rejects_oversized_input_before_json_parse(tmp_path: Path) -> None:
    receipt = tmp_path / "oversized-receipt.json"
    receipt.write_bytes(b'{' + b'"padding":"' + b'x' * 65_536 + b'"}')

    result = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "arnold_pipelines.megaplan.cloud.repair_investigation",
            "validate",
            "--receipt",
            str(receipt),
            "--context-digest",
            "unused",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "investigator receipt exceeds 65536-byte bound" in result.stderr


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
