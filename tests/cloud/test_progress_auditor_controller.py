from __future__ import annotations

import json
from pathlib import Path
import threading

import pytest

from arnold_pipelines.megaplan.cloud.progress_auditor_controller import (
    TriggerResult,
    run_escalation_controller,
)
from arnold_pipelines.megaplan.cloud.repair_contract import read_jsonl_records
from arnold_pipelines.megaplan.incident.ledger import RuntimeTransitionWriter
from tests.cloud.test_progress_auditor_escalation import (
    _approval_gate_after_superfixer_repair,
    _true_stall,
    _valid_manifest,
)
from tests.cloud.repair_identity_fixtures import repair_identity


def _transition_args(tmp_path: Path) -> tuple[RuntimeTransitionWriter, str]:
    """Real ledger writer + contract digest for the mandatory-emission path.

    G3: the controller's enqueue is only reached when the finding carries a
    validated true-stall gate, so every enqueue-reachable controller test
    injects a durable writer and chain-spec digest via the controller seam.
    """
    writer = RuntimeTransitionWriter(tmp_path / "transition-ledger")
    return writer, "sha256:" + "0" * 64


def test_report_only_and_ordinary_findings_never_create_repair_custody(tmp_path: Path) -> None:
    true_stall = _true_stall()
    ordinary = _true_stall()
    ordinary["session"] = "ordinary-finding"
    ordinary["session_header"]["session"] = "ordinary-finding"
    ordinary["current_target"]["session"] = "ordinary-finding"
    ordinary["current_target"]["tmux_process"] = {
        "session": "ordinary-finding",
        "pid": 4242,
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
        trigger_argv=["/usr/local/bin/arnold-watchdog"],
    )

    assert result["l3_escalation_summary"]["dispatched"] == 0
    assert [item["decision"] for item in result["l3_escalation_summary"]["items"]] == [
        "blocked_authority",
        "report_only",
    ]
    report_only = result["l3_escalation_summary"]["items"][1]
    assert report_only["reason"].startswith("l3_repair_gate_blocked:")
    assert "healthy_live_process" in report_only["reason"]
    assert not (queue / "requests").exists()
    assert not (tmp_path / "audit-escalations").exists()


def test_retroactive_approval_path_never_dispatches_mutating_repair(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"

    for authorized in (False, True):
        result = run_escalation_controller(
            {
                "findings": [_approval_gate_after_superfixer_repair()],
                "green_checks": [],
            },
            state_root=tmp_path / f"audit-escalations-{authorized}",
            queue_root=queue,
            authorized=authorized,
            trigger_argv=["/usr/local/bin/arnold-watchdog"],
        )

        item = result["l3_escalation_summary"]["items"][0]
        assert item["decision"] == "approval_required"
        assert item["repair_dispatched"] is False
        assert item["corrective_path"]["action"] == "await_human_pr_merge"
        assert item["corrective_path"]["repair_dispatch_permitted"] is False

    assert not (queue / "requests").exists()


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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-launch-failure"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
    finding["repair_identity"] = repair_identity(
        session=str(finding.get("session") or "audit-session"),
        plan=str(finding.get("plan") or "audit-plan"),
        failure_kind="L3_TRUE_STALL",
        phase="progress_auditor",
        task="d9-root-repair",
    )
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-d9"),
        chain_spec_sha256="sha256:" + "0" * 64,
    )
    second = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-d9"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-async-start"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-run-id-mismatch"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-reverify"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-reverify"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-escalation-id"),
        chain_spec_sha256="sha256:" + "0" * 64,
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
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-escalation-id"),
        chain_spec_sha256="sha256:" + "0" * 64,
    )

    assert second["l3_escalation_summary"]["dispatched"] == 1
    assert calls == 2
    reconciled = json.loads(first_state_path.read_text(encoding="utf-8"))
    assert reconciled["attempts"][-1]["status"] == "failed"
    assert reconciled["attempts"][-1]["outcome"] == "recovery_not_verified"


def test_controller_appends_l3_drift_evidence(tmp_path: Path) -> None:
    queue = tmp_path / ".megaplan" / "repair-queue"
    state_root = tmp_path / "audit-escalations"
    finding = _true_stall()
    finding["incident_audit"] = {
        "findings": [
            {
                "layer": "reconciler",
                "code": "DRIFT_DETECTED",
                "source_pair": "l2_fix_vs_resolver",
                "contradiction": "false_fixed_l2_result",
                "recommendation": "immediate_repair.repair_attempt",
                "observed": {"resolver_canonical_state": "RUNNING"},
                "expected": {"brief_outcome": "started"},
            }
        ]
    }

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=state_root,
        queue_root=queue,
        authorized=True,
        trigger_argv=None,
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-drift-evidence"),
        chain_spec_sha256="sha256:" + "0" * 64,
    )

    item = result["l3_escalation_summary"]["items"][0]
    sidecar_path = state_root.with_name("audit-escalations.d") / "escalations" / "escalations.jsonl"
    records = read_jsonl_records(sidecar_path)
    assert item["decision"] == "request_queued"
    assert item["repair_evidence_path"] == str(sidecar_path)
    assert records[-1]["reconciler_drift_findings"] == [
        {
            "layer": "reconciler",
            "code": "DRIFT_DETECTED",
            "source_pair": "l2_fix_vs_resolver",
            "contradiction": "false_fixed_l2_result",
            "recommendation": "immediate_repair.repair_attempt",
            "observed": {"resolver_canonical_state": "RUNNING"},
            "expected": {"brief_outcome": "started"},
        }
    ]


# ── T30 / Step 43: trigger argv shim validation ─────────────────────────────


def test_controller_rejects_noncanonical_trigger_argv(tmp_path: Path) -> None:
    """T30 / Step 43: noncanonical trigger argv is rejected as a typed outcome.

    The controller no longer executes arbitrary argv via subprocess.  Each
    legacy binary name, shell token, caller-runner marker, and deep-superfixer
    identity is rejected with a closed ``trigger_argv_rejection_kind`` and a
    delegation-shim ``zero_authority_rejected`` outcome, without dispatching a
    child process or claiming authority from a label, liveness signal, WBC
    receipt, or rebuildable projection.
    """
    noncanonical_cases = [
        (["/usr/local/bin/arnold-watchdog"], "legacy_binary_name"),
        (["sh", "-c", "echo pwn ; rm -rf /"], "shell_token"),
        (
            ["python", "-m", "arnold_pipelines.megaplan.cloud.repair"],
            "caller_runner",
        ),
        (["deep-superfixer-run", "--identity"], "deep_superfixer_identity"),
        (["python", "-m", "module", "--repair-bin", "x"], "legacy_binary_name"),
    ]

    for idx, (argv, expected_kind) in enumerate(noncanonical_cases):
        result = run_escalation_controller(
            {"findings": [_true_stall()], "green_checks": []},
            state_root=tmp_path / f"ws-{idx}" / "audit-escalations",
            queue_root=tmp_path / f"ws-{idx}" / ".megaplan" / "repair-queue",
            authorized=True,
            trigger_argv=argv,
            transition_writer=RuntimeTransitionWriter(tmp_path / f"ledger-argv-{idx}"),
            chain_spec_sha256="sha256:" + "0" * 64,
        )

        item = result["l3_escalation_summary"]["items"][0]
        assert item["decision"] == "trigger_argv_rejected", (
            f"argv={argv} should be rejected; got decision={item['decision']!r}"
        )
        assert item["repair_dispatched"] is False, (
            f"argv={argv} must never dispatch a repair"
        )
        assert item["trigger_argv_rejection_kind"] == expected_kind, (
            f"argv={argv} expected kind {expected_kind!r}; "
            f"got {item.get('trigger_argv_rejection_kind')!r}"
        )
        assert item["delegation_outcome"] == "zero_authority_rejected", (
            f"argv={argv} must carry the shim zero-authority rejection outcome"
        )
        assert result["l3_escalation_summary"]["dispatched"] == 0


def test_controller_canonical_runner_test_seam_still_dispatches(tmp_path: Path) -> None:
    """T30 / Step 43: a caller-supplied trigger_runner remains a controlled
    test seam.  Managed-launch receipts keep flowing through it, so the
    retirement only removes the *arbitrary* (subprocess) default path.
    """
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
                    "managed_run_id": "managed-seam",
                    "managed_manifest_path": str(tmp_path / "missing-seam.json"),
                }
            ),
            stderr="seam runner exercised",
        )

    result = run_escalation_controller(
        {"findings": [_true_stall()], "green_checks": []},
        state_root=tmp_path / "ws-seam" / "audit-escalations",
        queue_root=tmp_path / "ws-seam" / ".megaplan" / "repair-queue",
        authorized=True,
        trigger_argv=["repair-trigger"],
        trigger_runner=runner,
        transition_writer=RuntimeTransitionWriter(tmp_path / "ledger-seam"),
        chain_spec_sha256="sha256:" + "0" * 64,
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert calls, "the supplied test-seam runner must be exercised"
    assert item["decision"] == "launch_failed"
    assert item["repair_dispatched"] is False


# ── G3: mandatory runtime-transition emission on the enqueue path ──────────


def _g3_finding(tmp_path: Path) -> tuple[dict, Path, Path]:
    """True-stall fixture pointed at a real workspace + chain spec.

    A canonical repair identity is attached so the enqueue actually creates
    a queued request — proving the journal events precede the request.
    """
    workspace = tmp_path / "g3-workspace"
    workspace.mkdir()
    spec_path = tmp_path / "g3-chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    finding = _true_stall()
    finding["workspace"] = str(workspace)
    finding["session_header"]["workspace"] = str(workspace)
    finding["session_header"]["remote_spec"] = str(spec_path)
    finding["current_target"]["current_refs"]["remote_spec"] = str(spec_path)
    finding["repair_identity"] = repair_identity(
        session="stuck-chain",
        plan="m2-repair-contract",
        failure_kind="L3_TRUE_STALL",
        phase="progress_auditor",
        task="g3-root-repair",
    )
    return finding, workspace, spec_path


def test_controller_gate_fails_closed_without_workspace(tmp_path: Path) -> None:
    """G3: a true-stall candidate with no workspace cannot satisfy the
    marker-consistency gate, so it stays report_only — no dispatch side
    effect ever occurs without the inputs the journal requires."""
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    del finding["workspace"]

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=None,
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "report_only"
    assert item["repair_dispatched"] is False
    assert not (queue / "requests").exists()


def test_controller_gate_fails_closed_without_spec_reference(tmp_path: Path) -> None:
    """G3: a true-stall candidate with no chain spec reference cannot satisfy
    the marker-consistency gate, so it stays report_only — no request is ever
    created without a spec to derive the contract digest from."""
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    finding["workspace"] = str(tmp_path / "ws")
    finding["session_header"]["workspace"] = str(tmp_path / "ws")
    finding["current_target"]["current_refs"]["workspace"] = str(tmp_path / "ws")
    del finding["session_header"]["remote_spec"]
    del finding["current_target"]["current_refs"]["remote_spec"]

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=None,
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "report_only"
    assert item["repair_dispatched"] is False
    assert not (queue / "requests").exists()


def test_controller_enqueue_blocks_when_spec_is_unreadable(tmp_path: Path) -> None:
    """G3: a spec reference that cannot be digested (missing file) FAILS
    CLOSED before the enqueue side effect."""
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    workspace = tmp_path / "ws"
    missing_spec = tmp_path / "missing-chain.yaml"
    finding["workspace"] = str(workspace)
    finding["session_header"]["workspace"] = str(workspace)
    finding["current_target"]["current_refs"]["workspace"] = str(workspace)
    finding["session_header"]["remote_spec"] = str(missing_spec)
    finding["current_target"]["current_refs"]["remote_spec"] = str(missing_spec)

    with pytest.raises(ValueError, match="chain_spec_sha256 could not be computed"):
        run_escalation_controller(
            {"findings": [finding], "green_checks": []},
            state_root=tmp_path / "audit-escalations",
            queue_root=queue,
            authorized=True,
            trigger_argv=None,
        )
    assert not (queue / "requests").exists()


def test_controller_enqueue_blocks_when_transition_write_fails(tmp_path: Path) -> None:
    """G3: a journal write failure blocks the controller's enqueue — no
    durable runtime.* event means no repair request is created."""
    finding, workspace, _spec_path = _g3_finding(tmp_path)
    queue = tmp_path / ".megaplan" / "repair-queue"
    writer = RuntimeTransitionWriter(workspace)
    # Sabotage the ledger AFTER construction: the journal dir becomes a file.
    import shutil

    ledger_dir = workspace / ".megaplan" / "incident-ledger"
    if ledger_dir.exists():
        shutil.rmtree(ledger_dir)
    ledger_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError, match="runtime transition not durably recorded"):
        run_escalation_controller(
            {"findings": [finding], "green_checks": []},
            state_root=tmp_path / "audit-escalations",
            queue_root=queue,
            authorized=True,
            trigger_argv=None,
            transition_writer=writer,
            chain_spec_sha256="sha256:" + "0" * 64,
        )
    assert not (queue / "requests").exists()


def test_controller_enqueue_constructs_writer_and_emits_before_request(
    tmp_path: Path,
) -> None:
    """G3 production path: the controller constructs the transition writer
    from the finding's workspace, derives chain_spec_sha256 from the finding's
    spec reference, and journals deviation_declared + fallback_considered
    BEFORE the repair request is created."""
    from arnold_pipelines.megaplan.chain.spec import chain_spec_sha256
    from arnold_pipelines.megaplan.cloud.watchdog import iter_incident_runtime_events

    finding, workspace, spec_path = _g3_finding(tmp_path)
    queue = tmp_path / ".megaplan" / "repair-queue"
    digest = chain_spec_sha256(spec_path)

    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=None,
    )

    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "request_queued"
    assert item["repair_request_id"]
    events = iter_incident_runtime_events(workspace)
    assert [event["type"] for event in events] == [
        "runtime.deviation_declared",
        "runtime.fallback_considered",
    ], events
    for event in events:
        assert event["session_id"] == "stuck-chain"
        assert event["failure_class"] == "availability"
        assert event["chain_spec_sha256"] == digest
        assert event["actor"] == "arnold-six-hour-auditor"
    assert "stale_l1_l2_cycle" in events[0]["error"]


def test_controller_enqueue_with_injected_seam_uses_provided_writer_and_digest(
    tmp_path: Path,
) -> None:
    """The controller seam forwards an injected writer + digest verbatim so
    tests (and callers that already resolved the contract digest) never
    re-derive inputs."""
    writer, digest = _transition_args(tmp_path)
    queue = tmp_path / ".megaplan" / "repair-queue"
    finding = _true_stall()
    finding["repair_identity"] = repair_identity(
        session="stuck-chain",
        plan="m2-repair-contract",
        failure_kind="L3_TRUE_STALL",
        phase="progress_auditor",
        task="g3-seam-repair",
    )
    result = run_escalation_controller(
        {"findings": [finding], "green_checks": []},
        state_root=tmp_path / "audit-escalations",
        queue_root=queue,
        authorized=True,
        trigger_argv=None,
        transition_writer=writer,
        chain_spec_sha256=digest,
    )
    item = result["l3_escalation_summary"]["items"][0]
    assert item["decision"] == "request_queued"
    assert item["repair_request_id"]
    from arnold_pipelines.megaplan.cloud.watchdog import iter_incident_runtime_events

    events = iter_incident_runtime_events(tmp_path / "transition-ledger")
    assert [event["type"] for event in events] == [
        "runtime.deviation_declared",
        "runtime.fallback_considered",
    ]
    assert events[0]["chain_spec_sha256"] == digest
