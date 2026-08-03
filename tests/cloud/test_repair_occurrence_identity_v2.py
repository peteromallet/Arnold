from __future__ import annotations

import ast
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan.cloud import repair_lock, repair_requests, simple_fixer
from arnold_pipelines.megaplan.cloud.wrappers import repair_delegation
from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan._core.state import set_active_step
from arnold_pipelines.megaplan.cloud.liveness_lease import LivenessLeasePublisher
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey


def _target(*, attempt: str = "1", fence: str = "7") -> CustodyTargetKey:
    return CustodyTargetKey(
        environment="cloud-a",
        session="session-a",
        chain="chain-a",
        plan_revision="rev-a",
        phase="execute",
        task="T1",
        attempt=attempt,
        normalized_failure_kind="execute_failed",
        blocker_or_phase_result_hash="sha256:blocker-a",
        fence=fence,
        chain_identity="chain-incarnation-a",
    )


def _identity(
    *,
    attempt: str = "1",
    fence: int = 7,
    run_incarnation_id: str = "run-incarnation-a",
    custody_epoch: int = 3,
) -> dict[str, object]:
    result = repair_requests.build_normalized_repair_identity(
        target=_target(attempt=attempt, fence=str(fence)),
        run_id="session-a",
        run_revision="rev-a",
        run_incarnation_id=run_incarnation_id,
        coordinator_attempt_id=f"coordinator:{attempt}",
        fence_token=fence,
        wbc_attempt_reference=f"wbc:{attempt}",
        run_authority_grant_id="grant-a",
        lease_id="lease-a",
        custody_epoch=custody_epoch,
    )
    assert result is not None
    return result


def _signature() -> dict[str, str]:
    return {
        "failure_kind": "execute_failed",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": "plan-a",
        "gate_recommendation": "",
        "blocked_task_id": "T1",
    }


def _queue(tmp_path: Path) -> Path:
    return tmp_path / ".megaplan" / "repair-queue"


def test_normalized_identity_binds_run_attempt_epoch_and_ignores_provider_trivia() -> None:
    identity = _identity()
    with_provider = {
        **identity,
        "provider": "zhipu",
        "model": "glm-5.2",
        "backend": "hermes",
    }

    assert repair_requests.normalize_repair_identity(with_provider) == identity
    assert repair_requests.repair_identity_key(with_provider) == repair_requests.repair_identity_key(identity)
    assert repair_requests.repair_identity_key(_identity(attempt="2")) != repair_requests.repair_identity_key(identity)
    assert repair_requests.repair_identity_key(
        _identity(run_incarnation_id="run-incarnation-b")
    ) != repair_requests.repair_identity_key(identity)
    assert repair_requests.repair_identity_key(
        _identity(custody_epoch=4)
    ) != repair_requests.repair_identity_key(identity)


def test_legacy_f01_identity_is_read_only_and_enqueue_rejects_it(tmp_path: Path) -> None:
    legacy = _target().to_dict()

    assert repair_requests.normalize_repair_identity(legacy) is None
    result = repair_requests.enqueue_repair_request(
        queue_root=_queue(tmp_path),
        session="session-a",
        source="legacy-producer",
        problem_signature=_signature(),
        repair_identity=legacy,
    )

    assert result["status"] == "zero_authority_rejected"
    assert not list((_queue(tmp_path) / "requests").glob("*.json"))


def test_enqueue_claim_restart_and_fence_are_bound_to_one_identity(tmp_path: Path) -> None:
    queue = _queue(tmp_path)
    identity = _identity()
    queued = repair_requests.enqueue_repair_request(
        queue_root=queue,
        session="session-a",
        source="test-producer",
        problem_signature=_signature(),
        repair_identity=identity,
    )
    request = queued["request"]

    missing = repair_requests.claim_active_repair_request(
        queue,
        blocker_id=request["blocker_id"],
        request_id=request["request_id"],
        actor="repair-a",
        session="session-a",
    )
    wrong = repair_requests.claim_active_repair_request(
        queue,
        blocker_id=request["blocker_id"],
        request_id=request["request_id"],
        actor="repair-a",
        session="session-a",
        repair_identity=_identity(attempt="2"),
    )
    claimed = repair_requests.claim_active_repair_request(
        queue,
        blocker_id=request["blocker_id"],
        request_id=request["request_id"],
        actor="repair-a",
        session="session-a",
        repair_identity=identity,
    )
    restarted = repair_requests.claim_active_repair_request(
        queue,
        blocker_id=request["blocker_id"],
        request_id=request["request_id"],
        actor="repair-a",
        session="session-a",
        repair_identity=identity,
    )

    assert missing.status == "stale"
    assert wrong.status == "stale"
    assert claimed.claimed
    assert restarted.already_claimed
    assert claimed.owner["repair_identity_key"] == request["repair_identity_key"]


def test_simple_fixer_and_delegation_reject_legacy_but_accept_current_identity(
    tmp_path: Path,
) -> None:
    legacy = simple_fixer.SimpleFixerOccurrence(target=_target())
    rejected_claim = simple_fixer.claim_singleton_occurrence(
        str(_queue(tmp_path)),
        legacy,
        actor="test",
        request_id="request-a",
        session="session-a",
    )
    legacy_delegation = repair_delegation.RepairDelegation(
        caller_kind="controller",
        caller_id="controller-a",
        target=_target(),
    )
    rejected_delegation = repair_delegation.delegate_to_simple_fixer(
        legacy_delegation,
        queue_dir=str(_queue(tmp_path)),
        mutate=lambda occurrence: occurrence.occurrence_fingerprint + ":changed",
    )

    current = simple_fixer.build_simple_fixer_occurrence(_identity())
    assert current is not None
    claim = simple_fixer.claim_singleton_occurrence(
        str(_queue(tmp_path)),
        current,
        actor="test",
        request_id="request-b",
        session="session-a",
    )

    assert rejected_claim.outcome == "rejected_identity"
    assert rejected_delegation.outcome == "zero_authority_rejected"
    assert claim.claimed


class _LeaseStore:
    def __init__(self, *, namespace: str, process_start: str, expired: bool = False) -> None:
        self.lease = SimpleNamespace(
            is_expired=expired,
            owner_host="host-a",
            owner_pid="41",
            owner_boot_id="boot-a",
            custody_epoch=3,
            expires_at="2099-01-01T00:00:00Z",
        )
        self.event = SimpleNamespace(
            payload={
                "owner_pid_namespace": namespace,
                "owner_process_start_ticks": process_start,
            }
        )

    def current_lease(self, lease_id: str):
        return self.lease if lease_id == "lease-a" else None

    def load_history(self, lease_id: str):
        return [self.event] if lease_id == "lease-a" else []


def _lock_owner(*, namespace: str = "pid:[a]", process_start: str = "100") -> dict[str, object]:
    return {
        "hostname": "host-a",
        "pid": 41,
        "boot_id": "boot-a",
        "pid_namespace": namespace,
        "process_start_ticks": process_start,
    }


def test_authoritative_lease_rejects_pid_reuse_and_two_namespace_collision() -> None:
    store = _LeaseStore(namespace="pid:[a]", process_start="100")

    authorized, _ = repair_lock.validate_lease_authority(
        store, "lease-a", _lock_owner()
    )
    reused, reused_diag = repair_lock.validate_lease_authority(
        store, "lease-a", _lock_owner(process_start="101")
    )
    foreign, foreign_diag = repair_lock.validate_lease_authority(
        store, "lease-a", _lock_owner(namespace="pid:[b]")
    )

    assert authorized
    assert not reused and reused_diag["reason"] == "owner_process_start_mismatch"
    assert not foreign and foreign_diag["reason"] == "owner_pid_namespace_mismatch"


def test_authoritative_lease_rejects_expiry_and_missing_incarnation() -> None:
    expired, expired_diag = repair_lock.validate_lease_authority(
        _LeaseStore(namespace="pid:[a]", process_start="100", expired=True),
        "lease-a",
        _lock_owner(),
    )
    missing, missing_diag = repair_lock.validate_lease_authority(
        _LeaseStore(namespace="", process_start=""),
        "lease-a",
        _lock_owner(),
    )

    assert not expired and expired_diag["reason"] == "lease_expired"
    assert not missing and missing_diag["reason"] == "lease_process_incarnation_missing"


def test_manual_producer_and_effect_boundaries_have_no_legacy_positive_path() -> None:
    from arnold_pipelines.megaplan.cloud import manual_repair_trigger

    manual_source = inspect.getsource(manual_repair_trigger)
    assert "enqueue_repair_request(" not in manual_source
    assert "_build_manual_trigger_occurrence_target" not in manual_source

    claim_source = inspect.getsource(repair_requests.claim_active_repair_request)
    claim_tree = ast.parse(claim_source)
    assert any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", "") == "ActiveRepairClaimResult"
        for node in ast.walk(claim_tree)
    )
    mutation_source = inspect.getsource(simple_fixer.SimpleFixerSession.attempt_mutation)
    assert "not self.occurrence.authoritative" in mutation_source


def test_managed_lifecycle_failure_publishes_identity_then_claims_and_delegates(
    tmp_path: Path, monkeypatch
) -> None:
    """Ordinary managed failure has a positive path; legacy evidence does not."""
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    marker_dir = workspace / ".megaplan" / "cloud-sessions"
    queue = workspace / ".megaplan" / "repair-queue"
    plan_dir.mkdir(parents=True)
    marker_dir.mkdir(parents=True)
    marker = {
        "session": "managed-demo",
        "workspace": str(workspace),
        "remote_spec": str(workspace / "chain.yaml"),
        "run_kind": "chain",
        "identity_digest": "sha256:managed-demo",
        "started_at": "2026-08-03T00:00:00Z",
    }
    (marker_dir / "managed-demo.json").write_text(
        json.dumps(marker), encoding="utf-8"
    )
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "managed-demo")
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(marker_dir))
    monkeypatch.setenv("ARNOLD_REPAIR_QUEUE_ROOT", str(queue))
    monkeypatch.setenv("ARNOLD_REPAIR_RUN_KIND", "chain")
    monkeypatch.setenv("ARNOLD_CHAIN_SPEC", marker["remote_spec"])

    publisher = LivenessLeasePublisher(
        "managed-demo", marker_dir=marker_dir, target_pid=os.getpid()
    )
    publisher.publish_once()
    state = {
        "name": "demo-plan",
        "current_state": "finalized",
        "history": [],
        "sessions": {},
        "meta": {},
    }
    set_active_step(
        state,
        step="finalize",
        agent="codex",
        mode="persistent",
        run_id="managed-run-1",
    )
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    auto._record_lifecycle_failure(
        plan_dir=plan_dir,
        kind="finalize_failed",
        message="finalize failed at the managed boundary",
        current_state="blocked",
        phase="finalize",
        resume_cursor={"phase": "finalize", "retry_strategy": "rerun_phase"},
        metadata={"blocked_task_id": "phase:finalize"},
    )

    persisted_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    identity = repair_requests.normalize_repair_identity(
        persisted_state.get("repair_identity")
    )
    records = repair_requests.iter_repair_requests(queue)
    assert identity is not None
    assert len(records) == 1
    request = records[0]
    assert request["repair_identity_key"] == repair_requests.repair_identity_key(identity)

    claim = repair_requests.claim_active_repair_request(
        queue,
        blocker_id=request["blocker_id"],
        request_id=request["request_id"],
        actor="watchdog",
        session="managed-demo",
        repair_identity=identity,
    )
    assert claim.claimed

    occurrence = simple_fixer.build_simple_fixer_occurrence(identity)
    assert occurrence is not None
    delegation = repair_delegation.RepairDelegation(
        caller_kind="live_watchdog",
        caller_id="managed-demo",
        target=occurrence.target,
        repair_identity=identity,
    )
    delegated = repair_delegation.delegate_to_simple_fixer(
        delegation,
        queue_dir=str(queue),
        mutate=lambda current: current.occurrence_fingerprint + ":advanced",
    )
    assert delegated.outcome == "delegated"

    legacy = repair_requests.enqueue_repair_request(
        queue_root=queue,
        session="managed-demo",
        source="legacy",
        problem_signature=_signature(),
        repair_identity=occurrence.target.to_dict(),
    )
    assert legacy["status"] == "zero_authority_rejected"
