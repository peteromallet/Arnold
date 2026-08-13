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
        "run_id": "managed-demo-run-1",
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


def test_cleanup_seed_allows_managed_failure_identity_after_active_step_clear(
    tmp_path: Path, monkeypatch
) -> None:
    """A result cleanup cannot erase the source needed by lifecycle repair."""
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    marker_dir = workspace / ".megaplan" / "cloud-sessions"
    chain_path = workspace / "chain.yaml"
    plan_dir.mkdir(parents=True)
    marker_dir.mkdir(parents=True)
    chain_path.write_text("milestones: []\n", encoding="utf-8")
    marker = {
        "session": "managed-seed",
        "workspace": str(workspace),
        "remote_spec": str(chain_path),
        "run_kind": "chain",
        "run_id": "managed-seed-run-1",
        "identity_digest": "sha256:managed-seed",
        "started_at": "2026-08-03T00:00:00Z",
    }
    (marker_dir / "managed-seed.json").write_text(
        json.dumps(marker), encoding="utf-8"
    )
    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "managed-seed")
    monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(marker_dir))
    queue = workspace / ".megaplan" / "repair-queue"
    monkeypatch.setenv("ARNOLD_REPAIR_QUEUE_ROOT", str(queue))
    monkeypatch.setenv("ARNOLD_REPAIR_RUN_KIND", "chain")
    monkeypatch.setenv("ARNOLD_CHAIN_SPEC", str(chain_path))

    publisher = LivenessLeasePublisher(
        "managed-seed", marker_dir=marker_dir, target_pid=os.getpid()
    )
    publisher.publish_once()
    try:
        state = {
            "name": "demo-plan",
            "current_state": "finalized",
            "plan_revision": "rev-seed",
            "history": [],
            "sessions": {},
            "meta": {},
        }
        set_active_step(
            state,
            step="finalize",
            agent="codex",
            mode="persistent",
            run_id="managed-seed-run-1",
        )
        # The cleanup fallback binds PhaseResult to the explicit occurrence
        # field; retain the same invocation already fenced in meta/orphan_fence.
        state["active_step"]["invocation_id"] = state["meta"]["current_invocation_id"]
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        invocation_id = state["active_step"]["invocation_id"]
        (plan_dir / "phase_result.json").write_text(
            json.dumps(
                {
                    "schema": "megaplan.phase_result",
                    "phase": "finalize",
                    "invocation_id": invocation_id,
                    "exit_kind": "internal_error",
                }
            ),
            encoding="utf-8",
        )

        assert auto._clear_completed_active_step(
            plan_dir,
            "finalize",
            SimpleNamespace(
                phase="finalize",
                invocation_id=invocation_id,
                exit_kind="internal_error",
            ),
        )
        cleared = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert "active_step" not in cleared
        assert cleared["meta"]["repair_identity_seed"]["_non_authoritative"] is True

        auto._record_lifecycle_failure(
            plan_dir=plan_dir,
            kind="phase_failed",
            message="finalize failed after result publication",
            current_state="blocked",
            phase="finalize",
            resume_cursor={"phase": "finalize", "retry_strategy": "rerun_phase"},
            metadata={"blocked_task_id": "phase:finalize"},
        )

        persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        identity = repair_requests.normalize_repair_identity(
            persisted.get("repair_identity")
        )
        assert identity is not None
        records = repair_requests.iter_repair_requests(queue)
        assert len(records) == 1
        assert records[0]["repair_identity_key"] == repair_requests.repair_identity_key(identity)
        assert persisted["latest_failure"]["metadata"]["repair_identity_seed_provenance"][
            "source"
        ] == "active_step_cleanup"
    finally:
        publisher.close()


# ---------------------------------------------------------------------------
# T-0202 — auto enqueue result propagation (persist identity before release)
# ---------------------------------------------------------------------------


def _lifecycle_identity(**overrides: object) -> dict[str, object]:
    """Explicit authority-bearing identity for the lifecycle enqueue path."""
    from tests.cloud.repair_identity_fixtures import repair_identity

    return repair_identity(
        session=overrides.get("session", "enqueue-session"),
        plan=overrides.get("plan", "enqueue-plan"),
        failure_kind=overrides.get("failure_kind", "deterministic_phase_failure"),
        phase=overrides.get("phase", "critique"),
        task=overrides.get("task", "phase:critique"),
    )


def _enqueue_kwargs(
    plan_dir: Path,
    queue_root: Path,
    *,
    session: str = "enqueue-session",
    identity: dict[str, object] | None = None,
    kind: str = "deterministic_phase_failure",
    phase: str = "critique",
) -> dict[str, object]:
    return {
        "plan_dir": plan_dir,
        "queue_root": queue_root,
        "session": session,
        "run_kind": "chain",
        "kind": kind,
        "message": "deterministic phase contract failure",
        "current_state": "blocked",
        "phase": phase,
        "suggested_action": "repair the phase contract",
        "metadata": {
            "blocked_task_id": "phase:critique",
            "repair_identity": identity or _lifecycle_identity(),
        },
        "retry_strategy": "repair_phase_contract",
    }


class TestLifecycleEnqueueResultPropagation:
    """T-0202: every auto enqueue exit carries the canonical request result.

    The canonical shape is ``{request_id, decision_id, repair_identity_key,
    blocker_id}`` plus a typed ``status``/``outcome``; no exit returns bare
    identity-free ``None``.
    """

    def test_main_enqueue_path_returns_ids_that_survive_on_disk(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')
        queue_root = _queue(tmp_path)
        identity = _lifecycle_identity()

        result = _enqueue_lifecycle_failure_request(
            **_enqueue_kwargs(plan_dir, queue_root, identity=identity)
        )

        assert result["status"] == "queued"
        assert result["outcome"] == "queued"
        assert result["request_id"]
        assert result["decision_id"]
        assert result["repair_identity_key"] == repair_requests.repair_identity_key(identity)
        assert result["blocker_id"]

        requests = repair_requests.iter_repair_requests(queue_root)
        assert len(requests) == 1
        request = requests[0]
        assert request["request_id"] == result["request_id"]
        assert request["repair_identity_key"] == result["repair_identity_key"]
        assert request["blocker_id"] == result["blocker_id"]
        decisions = list(
            repair_requests.iter_repair_decisions(queue_root)
        )
        assert any(
            decision["decision_id"] == result["decision_id"]
            and decision["request_id"] == result["request_id"]
            for decision in decisions
        )

    def test_returned_ids_survive_claim(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')
        queue_root = _queue(tmp_path)
        identity = _lifecycle_identity()

        result = _enqueue_lifecycle_failure_request(
            **_enqueue_kwargs(plan_dir, queue_root, identity=identity)
        )

        claim = repair_requests.claim_active_repair_request(
            queue_root,
            blocker_id=result["blocker_id"],
            request_id=result["request_id"],
            actor="watchdog",
            session="enqueue-session",
            repair_identity=identity,
        )
        assert claim.claimed
        assert claim.owner["request_id"] == result["request_id"]

    def test_record_lifecycle_failure_joins_result_before_custody_release(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan import auto

        plan_dir = tmp_path / ".megaplan" / "plans" / "enqueue-plan"
        plan_dir.mkdir(parents=True)
        state = {
            "name": "enqueue-plan",
            "current_state": "critique",
            "history": [],
            "sessions": {},
            "meta": {},
        }
        set_active_step(
            state,
            step="critique",
            agent="codex",
            mode="persistent",
            run_id="run-1",
        )
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        queue_root = _queue(tmp_path)
        identity = _lifecycle_identity()

        result = auto._record_lifecycle_failure(
            plan_dir=plan_dir,
            kind="deterministic_phase_failure",
            message="deterministic phase contract failure",
            current_state="blocked",
            phase="critique",
            resume_cursor={"phase": "critique", "retry_strategy": "repair_phase_contract"},
            suggested_action="repair the phase contract",
            metadata={
                "blocked_task_id": "phase:critique",
                "repair_identity": identity,
            },
        )

        # The canonical result is returned…
        assert result["request_id"]
        assert result["decision_id"]
        assert result["repair_identity_key"] == repair_requests.repair_identity_key(identity)
        assert result["blocker_id"]

        # …and joined into the SAME metadata write that releases custody
        # (record_lifecycle_failure clears active_step), so the IDs survive.
        persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        assert "active_step" not in persisted
        joined = persisted["latest_failure"]["metadata"]["repair_request_identity"]
        assert joined["request_id"] == result["request_id"]
        assert joined["decision_id"] == result["decision_id"]
        assert joined["repair_identity_key"] == result["repair_identity_key"]
        assert joined["blocker_id"] == result["blocker_id"]
        assert joined["status"] == "queued"
        assert joined["outcome"] == "queued"
        assert persisted["latest_failure"]["metadata"]["repair_identity"]
        assert repair_requests.normalize_repair_identity(
            persisted.get("repair_identity")
        ) is not None

    def test_no_plan_dir_exit_is_typed(self) -> None:
        from arnold_pipelines.megaplan import auto

        result = auto._record_lifecycle_failure(
            plan_dir=None,
            kind="stall_detected",
            message="driver stalled",
            current_state="blocked",
            phase="execute",
            resume_cursor=None,
            suggested_action="",
            metadata=None,
        )
        assert result["status"] == "repair_unavailable"
        assert result["outcome"] == "no_plan_dir"
        assert result["request_id"] == ""
        assert result["decision_id"] == ""
        assert result["repair_identity_key"] == ""
        assert result["blocker_id"] == ""

    def test_lifecycle_record_exception_still_carries_enqueue_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan import auto

        plan_dir = tmp_path / ".megaplan" / "plans" / "enqueue-plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "enqueue-plan", "current_state": "critique"}),
            encoding="utf-8",
        )
        queue_root = _queue(tmp_path)
        identity = _lifecycle_identity()

        def _boom(self: object, **kwargs: object) -> dict[str, object]:
            raise OSError("state disk full")

        monkeypatch.setattr(
            auto.PlanRepository, "record_lifecycle_failure", _boom
        )

        result = auto._record_lifecycle_failure(
            plan_dir=plan_dir,
            kind="deterministic_phase_failure",
            message="deterministic phase contract failure",
            current_state="blocked",
            phase="critique",
            resume_cursor=None,
            suggested_action="",
            metadata={
                "blocked_task_id": "phase:critique",
                "repair_identity": identity,
            },
        )

        # The enqueue ran first and its identity is carried, not dropped.
        assert result["request_id"]
        assert result["decision_id"]
        assert result["repair_identity_key"] == repair_requests.repair_identity_key(identity)
        assert result["blocker_id"]
        assert result["lifecycle_record_persisted"] is False
        assert result["lifecycle_record_error_type"] == "OSError"
        assert "disk full" in result["lifecycle_record_error"]
        requests = repair_requests.iter_repair_requests(queue_root)
        assert len(requests) == 1

    def test_queue_disabled_exit_is_typed(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')
        queue_root = _queue(tmp_path)
        identity = _lifecycle_identity()

        with patch(
            "arnold_pipelines.megaplan.cloud.feature_flags.repair_request_queue_enabled",
            return_value=False,
        ):
            result = _enqueue_lifecycle_failure_request(
                **_enqueue_kwargs(plan_dir, queue_root, identity=identity)
            )

        assert result["status"] == "repair_unavailable"
        assert result["outcome"] == "queue_disabled"
        assert result["repair_identity_key"] == repair_requests.repair_identity_key(identity)
        assert result["request_id"] == ""
        assert list((queue_root / "requests").glob("*.json")) == []

    def test_enqueue_exception_becomes_typed_failure(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')
        queue_root = _queue(tmp_path)
        identity = _lifecycle_identity()

        with patch(
            "arnold_pipelines.megaplan.cloud.repair_requests.enqueue_occurrence_bound_repair_request",
            side_effect=RuntimeError("disk full"),
        ):
            result = _enqueue_lifecycle_failure_request(
                **_enqueue_kwargs(plan_dir, queue_root, identity=identity)
            )

        assert result["status"] == "repair_unavailable"
        assert result["outcome"] == "repair_enqueue_failure"
        assert result["error_type"] == "RuntimeError"
        assert "disk full" in result["error"]
        # The occurrence identity still rides along on the failure result.
        assert result["repair_identity_key"] == repair_requests.repair_identity_key(identity)
        assert list((queue_root / "requests").glob("*.json")) == []

    def test_terminal_mirror_without_failure_is_typed(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_terminal_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        result = _enqueue_terminal_failure_request(plan_dir)

        assert result["status"] == "repair_unavailable"
        assert result["outcome"] == "no_terminal_failure_to_mirror"
        assert result["request_id"] == ""

    def test_terminal_mirror_exception_is_typed_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_terminal_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "current_state": "blocked",
                    "latest_failure": {
                        "kind": "quality_gate_blocked",
                        "message": "deterministic review check failed",
                        "phase": "review",
                        "metadata": {"blocked_task_id": "T24"},
                    },
                }
            ),
            encoding="utf-8",
        )

        def _boom(plan_dir: Path) -> tuple[Path, Path, str, str]:
            raise RuntimeError("route exploded")

        monkeypatch.setattr(auto, "_lifecycle_repair_request_route", _boom)

        result = _enqueue_terminal_failure_request(plan_dir)

        assert result["status"] == "repair_unavailable"
        assert result["outcome"] == "repair_enqueue_failure"
        assert result["error_type"] == "RuntimeError"
        assert "route exploded" in result["error"]


def test_canonical_repair_request_identity_resolves_coalesced_related_request():
    """G8 advisory 2: a coalesced decision names the RELATED persisted request,
    never the unwritten candidate record."""
    from arnold_pipelines.megaplan.auto import _canonical_repair_request_identity

    candidate = "candidate-request-1"
    related = "related-persisted-request-2"
    result = {
        "status": "coalesced",
        "request": {"request_id": candidate, "blocker_id": "blocker-x"},
        "decision": {
            "decision_id": "dec-1",
            "status": "coalesced",
            "related_request_id": related,
        },
        "repair_identity_key": "key-1",
    }
    canon = _canonical_repair_request_identity(result)
    assert canon["request_id"] == related, canon
    assert canon["decision_id"] == "dec-1"
    assert canon["blocker_id"] == "blocker-x"
    assert canon["repair_identity_key"] == "key-1"


def test_canonical_repair_request_identity_keeps_candidate_when_not_coalesced():
    from arnold_pipelines.megaplan.auto import _canonical_repair_request_identity

    result = {
        "status": "queued",
        "request": {"request_id": "req-1", "blocker_id": "b-1"},
        "decision": {"decision_id": "d-1", "status": "accepted"},
        "repair_identity_key": "k-1",
    }
    canon = _canonical_repair_request_identity(result)
    assert canon["request_id"] == "req-1"
    assert canon["decision_id"] == "d-1"
