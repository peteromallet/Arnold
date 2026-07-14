from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud.progress_auditor_controller import (
    TriggerResult,
    _refresh_owner_topology,
    run_escalation_controller,
)
from tests.cloud.test_progress_auditor_escalation import (
    _owner_topology,
    _true_stall,
    _valid_manifest,
)


def test_prior_active_execution_receipt_is_refreshed_from_manifest_liveness(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "execution-owner" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"status": "running", "pid": 99999999, "worker_pid": 99999998}),
        encoding="utf-8",
    )
    topology = _owner_topology(active=True)
    topology["execution_owners"][0]["manifest_path"] = str(manifest)

    refreshed = _refresh_owner_topology({"owner_topology": topology})

    assert refreshed["owner_topology"]["active_controller_count"] == 0
    assert refreshed["owner_topology"]["execution_owners"][0]["status"] == "interrupted"
    assert refreshed["owner_topology"]["execution_owners"][0]["observed_live"] is False


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
                    "owner_topology": _owner_topology(),
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
    advanced["chain_state_summary"]["current"]["current_milestone_index"] = 2
    advanced["chain_state_summary"]["current"]["state_digest"] = "8" * 64
    advanced["accepted_event_seq"] = 11
    advanced["accepted_event_digest"] = "6" * 64

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


def test_duplicate_plan_shadows_share_one_target_controller(tmp_path: Path) -> None:
    current = _true_stall()
    shadow = _true_stall()
    shadow["plan"] = "m1-completed-shadow"
    shadow["current_state"] = "done"
    calls = 0

    def runner(argv):
        nonlocal calls
        calls += 1
        request_id = argv[-1]
        from arnold_pipelines.megaplan.cloud.progress_auditor_escalation import classify_true_stall

        gate = classify_true_stall(current)
        manifest_path = tmp_path / "managed" / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = _valid_manifest(gate)
        manifest.update({"run_id": "managed-root", "manifest_path": str(manifest_path), "status": "running"})
        manifest["links"]["repair_request_id"] = request_id
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return TriggerResult(
            returncode=0,
            stdout=json.dumps({
                "event": "repair_trigger_dispatch",
                "status": "dispatched",
                "request_id": request_id,
                "managed_run_id": "managed-root",
                "managed_manifest_path": str(manifest_path),
            }),
            stderr="",
        )

    result = run_escalation_controller(
        {"findings": [current, shadow], "green_checks": []},
        state_root=tmp_path / "state",
        queue_root=tmp_path / ".megaplan" / "repair-queue",
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
    )

    assert calls == 1
    assert result["l3_escalation_summary"]["dispatched"] == 1
    assert result["l3_escalation_summary"]["items"][1]["decision"] == "duplicate_target_observation"
