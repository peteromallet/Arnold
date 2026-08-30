from __future__ import annotations

from pathlib import Path
import subprocess
from dataclasses import replace

from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    AdmissionRefusal,
    WorkerAdmissionReceipt,
    dispatch_with_admission,
    LaunchResult,
    _normalize_outcome,
    _validate_worker_identity_for_receipt,
)
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome, SchedulingCondition

from tests.cloud.dispatch_test_helpers import request


WORKER = {"host": "host", "pid": 123, "boot_id": "boot"}


def test_cooldown_retries_without_launch_and_then_admits(tmp_path: Path) -> None:
    waits: list[float] = []
    launches: list[int] = []
    now = [0.0]
    cooldowns = iter((2.0, 0.0))

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    def gate(req):
        from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
        return require_production_worker_dispatch_runtime(
            req,
            # consume the injected cooldown deterministically per attempt
        )

    original = request(tmp_path, cooldown_reader=lambda *_: next(cooldowns))
    result = dispatch_with_admission(
        original,
        lambda _context: (launches.append(1), WORKER)[1],
        gate=gate,
        clock=clock,
        sleeper=sleep,
        deadline_s=10,
    )
    assert isinstance(result, DispatchOutcome)
    assert result.kind == "success"
    assert waits == [2.0]
    assert len(launches) == 1


def test_scheduling_expiry_returns_condition_without_launch(tmp_path: Path) -> None:
    launches: list[int] = []
    result = dispatch_with_admission(
        request(tmp_path, cooldown_reader=lambda *_: 5.0),
        lambda _context: launches.append(1),
        clock=lambda: 0.0,
        sleeper=lambda _seconds: None,
        deadline_s=1.0,
    )
    assert isinstance(result, SchedulingCondition)
    assert result.reason == "memory_cooldown"
    assert launches == []


def test_gate_refusal_prevents_final_launch(tmp_path: Path) -> None:
    launches: list[int] = []
    result = dispatch_with_admission(
        request(tmp_path, seed_identity=""),
        lambda _context: launches.append(1),
    )
    assert isinstance(result, AdmissionRefusal)
    assert launches == []


def test_wrapped_integer_is_not_a_typed_success(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from pytest import raises

    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    with raises(ValueError, match="primitive launch results"):
        _normalize_outcome(LaunchResult(accepted=True, value=7, worker_identity=WORKER), receipt, "s", "f")


def test_launchresult_mapping_is_completed_nullable_dispatch_schema(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime

    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    outcome = _normalize_outcome(
        LaunchResult(
            accepted=True,
            value={
                "kind": "success",
                "worker_identity": WORKER,
                "started_at": "started",
                "finished_at": "finished",
                # Nullable DispatchOutcome fields are intentionally omitted;
                # normalization must materialize them as None.
            },
            worker_identity=WORKER,
            started_at="started",
            finished_at="finished",
        ),
        receipt,
        "fallback-start",
        "fallback-finish",
    )
    assert outcome.kind == "success"
    assert outcome.terminal_failure is None
    assert outcome.provider_evidence is None
    assert outcome.reconciliation_event_id is None


def test_launchresult_mapping_missing_required_identity_is_rejected(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from pytest import raises

    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    with raises(ValueError, match="worker identity"):
        _normalize_outcome(
            LaunchResult(
                accepted=True,
                value={"kind": "success", "started_at": "started", "finished_at": "finished"},
            ),
            receipt,
            "s",
            "f",
        )


def test_completed_process_snapshot_is_bound_to_live_child_before_exit(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.workers._impl import capture_process_identity

    child = subprocess.Popen(["/bin/sleep", "2"])
    try:
        # Deliberately lie about argv: capture must use OS-observed identity.
        identity = capture_process_identity(child, ("/bin/echo", "forged"))
        assert identity["process_executable"].endswith("/sleep")
        assert identity["process_argv"][0].endswith("/sleep")
    finally:
        child.terminate()
        child.wait(timeout=5)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    receipt = replace(
        receipt,
        production_intent=True,
        route_liveness_evidence={
            "executable": {
                "executable_path": identity["process_executable"],
                "executable_sha256": identity["process_executable_sha256"],
            }
        },
    )
    assert _validate_worker_identity_for_receipt(identity, receipt)["pid"] == identity["pid"]
    forged = dict(identity, process_executable_sha256="0" * 64)
    import pytest
    with pytest.raises(ValueError, match="machine observation"):
        _validate_worker_identity_for_receipt(forged, receipt)
    import os
    with pytest.raises(ValueError, match="machine observation"):
        _validate_worker_identity_for_receipt(dict(identity, pid=99999999), receipt)
    with pytest.raises(ValueError, match="machine observation"):
        _validate_worker_identity_for_receipt(dict(identity, pid=os.getpid()), receipt)


def test_completed_managed_child_uses_receipt_bound_manifest_attestation(tmp_path: Path) -> None:
    import hashlib
    import json
    from dataclasses import replace
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        _validate_worker_identity_for_receipt,
        require_production_worker_dispatch_runtime,
    )

    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    receipt = replace(receipt, production_intent=True)
    manifest_path = tmp_path / receipt.logical_dispatch_id / "manifest.json"
    manifest_path.parent.mkdir()
    manifest = {
        "schema_version": "arnold-managed-agent-run-v2",
        "custodian": "arnold.megaplan.managed_agent",
        "run_id": receipt.logical_dispatch_id,
        "status": "completed",
        "worker_pid": 99999999,
        "worker_host": "test-host",
        "worker_boot_id": "boot-1",
        "worker_start_ticks": "start-1",
        "worker_identity_verified": True,
        "worker_cmdline_sha256": "a" * 64,
    }
    raw = json.dumps(manifest, sort_keys=True).encode()
    manifest_path.write_bytes(raw)
    identity = {
        "host": "test-host",
        "pid": 99999999,
        "boot_id": "boot-1",
        "process_start_identity": "start-1",
        "verified": True,
        "attestation_source": "managed_agent_manifest",
        "manifest_path": str(manifest_path),
        "managed_run_id": receipt.logical_dispatch_id,
        "managed_manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert _validate_worker_identity_for_receipt(identity, receipt)["pid"] == 99999999


def test_completed_managed_child_rejects_forged_manifest_digest(tmp_path: Path) -> None:
    import pytest
    from dataclasses import replace
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        _validate_worker_identity_for_receipt,
        require_production_worker_dispatch_runtime,
    )

    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    receipt = replace(receipt, production_intent=True)
    identity = {
        "host": "test-host", "pid": 99999999, "boot_id": "boot-1",
        "process_start_identity": "start-1", "verified": True,
        "attestation_source": "managed_agent_manifest",
        "manifest_path": str(tmp_path / receipt.logical_dispatch_id / "manifest.json"),
        "managed_run_id": receipt.logical_dispatch_id,
        "managed_manifest_sha256": "b" * 64,
    }
    with pytest.raises(ValueError, match="manifest"):
        _validate_worker_identity_for_receipt(identity, receipt)
