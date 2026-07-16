from __future__ import annotations

import json
from pathlib import Path
import threading

from arnold_pipelines.megaplan.cloud.progress_auditor_controller import (
    TriggerResult,
    run_escalation_controller,
)
from tests.cloud.test_progress_auditor_escalation import _true_stall, _valid_manifest


def test_report_only_and_ordinary_findings_never_create_repair_custody(tmp_path: Path) -> None:
    true_stall = _true_stall()
    ordinary = _true_stall()
    ordinary["session"] = "ordinary-finding"
    ordinary["session_header"]["session"] = "ordinary-finding"
    ordinary["current_target"]["session"] = "ordinary-finding"
    ordinary["current_target"]["tmux_process"] = {
        "pid_live": True,
        "session_live": True,
        "live_status": "alive",
    }
    ordinary["events_mtime_age_min"] = 1
    ordinary["reasons"] = ["score regression 8->5"]
    queue = tmp_path / ".megaplan" / "repair-queue"

    result = run_escalation_controller(
        {"findings": [true_stall, ordinary], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=False,
        trigger_argv=["/usr/local/bin/arnold-repair-trigger"],
    )

    assert result["l3_escalation_summary"]["dispatched"] == 0
    assert [item["decision"] for item in result["l3_escalation_summary"]["items"]] == [
        "blocked_authority",
        "report_only",
    ]
    assert not (queue / "requests").exists()
    assert not (tmp_path / "audit-escalations").exists()


def test_launch_failure_is_truthful_without_a_manifest(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    calls: list[list[str]] = []

    def runner(argv):
        calls.append(list(argv))
        request_id = argv[-1]
        return TriggerResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "event": "repair_trigger_dispatch",
                    "status": "launch_failed",
                    "request_id": request_id,
                    "managed_run_id": "managed-missing",
                    "managed_manifest_path": str(tmp_path / "missing-manifest.json"),
                }
            ),
            stderr="FileNotFoundError: managed supervisor never committed a manifest",
        )

    result = run_escalation_controller(
        {"findings": [_true_stall()], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert calls and calls[0][-2] == "--request-id"
    assert item["decision"] == "launch_failed"
    assert item["repair_dispatched"] is False
    assert item["managed_run_id"] == ""
    assert "manifest_schema_version_mismatch" in item["launch_validation_errors"]
    assert result["l3_escalation_summary"]["dispatched"] == 0


def test_valid_canonical_d9_manifest_is_correlated_and_deduped(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    finding["resolver_state"] = {"canonical_state": "UNKNOWN", "confidence": "low"}
    finding["chain_state_summary"]["current"].update(
        {"last_state": "blocked", "pr_number": 255, "pr_state": "open"}
    )
    finding["current_target"]["ci_health"] = {
        "status": "failure", "available": True, "pr_number": 255
    }
    finding["repair_custody_summary"]["retry_budget"] = {
        "claim_retries_used": 0, "claim_retries_remaining": 3
    }
    finding["meta_repair_summary"]["repair_goal"] = {
        "goal_id": "repair-goal-active-unowned",
        "status": "active",
        "owner_live": False,
        "control_action": "investigate",
    }
    finding["acceptance_progress"] = {
        "advanced": False, "accepted_event_age_min": 150
    }
    manifest_path = tmp_path / "workspace" / "manifest.json"
    calls = 0

    def runner(argv):
        nonlocal calls
        calls += 1
        request_id = argv[-1]
        # The escalation id is stable for the immutable fixture.
        from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import classify_true_stall

        gate = classify_true_stall(finding)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = _valid_manifest(gate)
        manifest.update(
            {
                "run_id": "managed-root-repair",
                "manifest_path": str(manifest_path),
                "status": "running",
            }
        )
        manifest["links"]["repair_request_id"] = request_id
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return TriggerResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "event": "repair_trigger_dispatch",
                    "status": "dispatched",
                    "request_id": request_id,
                    "managed_run_id": "managed-root-repair",
                    "managed_manifest_path": str(manifest_path),
                }
            ),
            stderr="",
        )

    first = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )
    second = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )

    first_item = first["l3_escalation_summary"]["items"][0]
    second_item = second["l3_escalation_summary"]["items"][0]
    assert first_item["decision"] == "dispatched"
    assert first_item["repair_dispatched"] is True
    assert first_item["managed_run_id"] == "managed-root-repair"
    assert second_item["decision"] in {"deduplicated_active", "cooldown"}
    assert second_item["repair_dispatched"] is False
    assert calls == 1
    assert len(list((queue / "requests").glob("*.json"))) == 1


def test_dispatched_launch_waits_for_async_managed_start_receipt(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    manifest_path = tmp_path / "workspace" / "manifest.json"
    timers: list[threading.Timer] = []

    def runner(argv):
        request_id = argv[-1]
        from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import classify_true_stall

        gate = classify_true_stall(finding)
        manifest = _valid_manifest(gate)
        manifest.update(
            {
                "run_id": "managed-delayed-root-repair",
                "manifest_path": str(manifest_path),
                "status": "running",
            }
        )
        manifest["links"]["repair_request_id"] = request_id

        def commit_manifest() -> None:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        timer = threading.Timer(0.1, commit_manifest)
        timer.start()
        timers.append(timer)
        return TriggerResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "event": "repair_trigger_dispatch",
                    "status": "dispatched",
                    "request_id": request_id,
                    "managed_run_id": "managed-delayed-root-repair",
                    "managed_manifest_path": str(manifest_path),
                }
            ),
            stderr="",
        )

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )
    for timer in timers:
        timer.join()

    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "dispatched"
    assert item["repair_dispatched"] is True
    assert item["managed_run_id"] == "managed-delayed-root-repair"


def test_dispatched_launch_rejects_trigger_manifest_run_id_mismatch(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    manifest_path = tmp_path / "workspace" / "manifest.json"

    def runner(argv):
        request_id = argv[-1]
        from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import classify_true_stall

        gate = classify_true_stall(finding)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = _valid_manifest(gate)
        manifest.update(
            {
                "run_id": "managed-manifest-run",
                "manifest_path": str(manifest_path),
                "status": "running",
            }
        )
        manifest["links"]["repair_request_id"] = request_id
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return TriggerResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "event": "repair_trigger_dispatch",
                    "status": "dispatched",
                    "request_id": request_id,
                    "managed_run_id": "managed-different-run",
                    "managed_manifest_path": str(manifest_path),
                }
            ),
            stderr="",
        )

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "launch_failed"
    assert item["repair_dispatched"] is False
    assert "trigger_manifest_run_id_mismatch" in item["launch_validation_errors"]


def test_terminal_managed_run_is_reverified_before_any_retry(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    manifest_path = tmp_path / "workspace" / "manifest.json"
    outcome_path = tmp_path / "workspace" / "repair-outcome.json"

    def runner(argv):
        request_id = argv[-1]
        from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import classify_true_stall

        gate = classify_true_stall(finding)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        outcome_path.write_text(
            json.dumps(
                {
                    "fixer_fixed": True,
                    "backstop_fixed": True,
                    "ordinary_retrigger_run_id": "managed-ordinary-repair",
                    "ordinary_retrigger_manifest_path": "/tmp/ordinary-manifest.json",
                    "guard_weakened": False,
                    "guard_changes": [],
                }
            ),
            encoding="utf-8",
        )
        manifest = _valid_manifest(gate)
        manifest.update(
            {
                "run_id": "managed-root-repair",
                "manifest_path": str(manifest_path),
                "status": "running",
            }
        )
        manifest["links"].update(
            {
                "repair_request_id": request_id,
                "repair_outcome_path": str(outcome_path),
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return TriggerResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "event": "repair_trigger_dispatch",
                    "status": "dispatched",
                    "request_id": request_id,
                    "managed_run_id": "managed-root-repair",
                    "managed_manifest_path": str(manifest_path),
                }
            ),
            stderr="",
        )

    first = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )
    assert first["l3_escalation_summary"]["dispatched"] == 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "completed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    advanced = _true_stall()
    advanced["chain_state_summary"]["current"]["completed_count"] = 2
    advanced["events_size"] = 8192

    second = run_escalation_controller(
        {"findings": [advanced], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=lambda _argv: (_ for _ in ()).throw(AssertionError("must not retry")),
    )

    item = second["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "recovery_verified"
    assert item["reverification"]["verified"] is True
    assert item["repair_dispatched"] is False


def test_terminal_attempt_is_closed_when_new_evidence_changes_escalation_id(
    tmp_path: Path,
) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    state_root = tmp_path / "audit-escalations"
    current_finding = _true_stall()
    manifests: list[Path] = []
    calls = 0

    def runner(argv):
        nonlocal calls
        calls += 1
        request_id = argv[-1]
        from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import (
            classify_true_stall,
        )

        gate = classify_true_stall(current_finding)
        manifest_path = tmp_path / f"manifest-{calls}.json"
        manifest = _valid_manifest(gate)
        manifest.update(
            {
                "run_id": f"managed-root-repair-{calls}",
                "manifest_path": str(manifest_path),
                "status": "running",
            }
        )
        manifest["links"]["repair_request_id"] = request_id
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifests.append(manifest_path)
        return TriggerResult(
            returncode=0,
            stdout=json.dumps(
                {
                    "event": "repair_trigger_dispatch",
                    "status": "dispatched",
                    "request_id": request_id,
                    "managed_run_id": manifest["run_id"],
                    "managed_manifest_path": str(manifest_path),
                }
            ),
            stderr="",
        )

    first = run_escalation_controller(
        {"findings": [current_finding], "green_checks": []},
        state_root=state_root,
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )
    assert first["l3_escalation_summary"]["dispatched"] == 1
    first_state_path = next(state_root.glob("*/state.json"))
    terminal_manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    terminal_manifest["status"] = "failed"
    manifests[0].write_text(json.dumps(terminal_manifest), encoding="utf-8")

    current_finding = _true_stall()
    current_finding["deterministic_superfixer_evidence"][
        "accepted_unclaimed_request_ids"
    ] = ["new-failure-fingerprint"]
    second = run_escalation_controller(
        {"findings": [current_finding], "green_checks": []},
        state_root=state_root,
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )

    assert second["l3_escalation_summary"]["dispatched"] == 1
    assert calls == 2
    reconciled = json.loads(first_state_path.read_text(encoding="utf-8"))
    assert reconciled["attempts"][-1]["status"] == "failed"
    assert reconciled["attempts"][-1]["outcome"] == "recovery_not_verified"
