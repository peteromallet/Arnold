"""Hermetic native-platform E2E conformance scenario."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from arnold.pipeline.native.reconcile import ReconcileDecision
from arnold.runtime.durable_ops import FileBackedDurableOpsStore, OperationRun, OperationState
from arnold.security.approval import apply_broker_approval_required, resolve_broker_approval
from arnold.security.audit import claim_broker_audit_entry, record_broker_audit_entry
from arnold.security.broker_service import BrokerSecretStore, BrokerService, PROTOCOL_VERSION
from arnold.security.types import ActionResult, ActionVerdict
from arnold.supervisor.capacity import CapacityGate, CapacityPoolConfig, CapacityStatus
from arnold.supervisor.capacity_context import CapacityContext, CapacityGateRejected, gate_capacity
from arnold.supervisor.reconcile import evaluate_expired_takeover
from arnold.supervisor.restart import (
    RestartPolicy,
    evaluate_automatic_restart,
    record_restart_failure,
)
from arnold.supervisor.store import FileProjectLeaseStore
from arnold.workflow.source_compiler import lower_workflow_file
from tests.arnold_pipelines.megaplan.package_resources import resource_path


SECRET_VALUE = "ghp_raw_secret_value"


@dataclass(frozen=True)
class DurableResumeRecord:
    run_id: str
    step_path: str
    lease_token: str
    reconcile_state: str
    audit_refs: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "step_path": self.step_path,
            "lease_token": self.lease_token,
            "reconcile_state": self.reconcile_state,
            "audit_refs": list(self.audit_refs),
        }

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> "DurableResumeRecord":
        return cls(
            run_id=str(payload["run_id"]),
            step_path=str(payload["step_path"]),
            lease_token=str(payload["lease_token"]),
            reconcile_state=str(payload["reconcile_state"]),
            audit_refs=tuple(str(item) for item in payload["audit_refs"]),
        )


def test_local_platform_e2e_conformance_with_deterministic_fakes(tmp_path: Path) -> None:
    clock = datetime(2026, 7, 5, tzinfo=UTC)
    lease_store = FileProjectLeaseStore(tmp_path / "lease-store")
    broker = BrokerService(
        secrets=BrokerSecretStore.from_environment(
            environ={"GITHUB_TOKEN": SECRET_VALUE, "OPENAI_API_KEY": "sk-local-fake"}
        )
    )

    with resource_path(
        "arnold_pipelines.megaplan.workflows",
        "workflow.pypeline",
    ) as workflow_source:
        lowered = lower_workflow_file(workflow_source)
    assert "parallel_map" in {step.kind for step in lowered.steps}
    assert {
        "tiebreaker_researcher",
        "tiebreaker_challenger",
        "tiebreaker_synthesis",
        "tiebreaker_decision",
    } <= {step.id for step in lowered.steps}

    lease = lease_store.claim_project_lease(
        "project-alpha",
        "worktree-main",
        run_id="run-001",
        owner_id="worker-a",
        lease_token="lease-a",
        lease_seconds=30,
        now=clock,
    )
    assert lease.owner_id == "worker-a"
    lease = lease_store.heartbeat_project_lease(
        "project-alpha",
        "worktree-main",
        "lease-a",
        lease_seconds=30,
        progress=True,
        now=clock + timedelta(seconds=10),
    )
    assert lease.last_progress_at == clock + timedelta(seconds=10)

    protected_push = broker.handle_payload(
        {
            "version": PROTOCOL_VERSION,
            "operation": "evaluate_action",
            "request": {
                "action_type": "git_push",
                "repo": "example/repo",
                "branch": "refs/heads/main",
                "command": ["git", "push", "origin", "main"],
            },
        }
    )
    assert protected_push["result"]["verdict"] == ActionVerdict.DENY.value

    force_push = broker.handle_payload(
        {
            "version": PROTOCOL_VERSION,
            "operation": "evaluate_action",
            "request": {
                "action_type": "git_push",
                "repo": "example/repo",
                "branch": "feature/m6",
                "force": True,
            },
        }
    )
    assert force_push["result"]["verdict"] == ActionVerdict.APPROVAL_REQUIRED.value

    ops_store = FileBackedDurableOpsStore(tmp_path / "durable-ops")
    approval_artifacts = tmp_path / "approval-artifacts"
    ops_store.create_operation_run(OperationRun(id="op-force-push", operation_type="git_force_push"))
    awaiting = apply_broker_approval_required(
        ops_store,
        "op-force-push",
        action_result=ActionResult(
            verdict=ActionVerdict.APPROVAL_REQUIRED,
            summary="force push requires broker approval",
            action_id="act-approval",
            metadata={"repo": "example/repo", "branch": "feature/m6", "force": True},
        ),
        artifact_root=approval_artifacts,
    )
    assert awaiting.state is OperationState.AWAITING_APPROVAL
    assert (approval_artifacts / "resume_cursor.json").is_file()
    assert (approval_artifacts / "awaiting_user.json").is_file()

    reloaded_ops_store = FileBackedDurableOpsStore(tmp_path / "durable-ops")
    assert reloaded_ops_store.load_operation_run("op-force-push").state is (
        OperationState.AWAITING_APPROVAL
    )
    approved = resolve_broker_approval(
        reloaded_ops_store,
        "op-force-push",
        "approve",
        action_result=ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary="operator approved force push",
            action_id="act-approved",
            effect_refs=("git-effect:approved",),
        ),
    )
    assert approved.state is OperationState.RUNNING

    reloaded_ops_store.create_operation_run(
        OperationRun(
            id="op-force-push-denied",
            operation_type="git_force_push",
            state=OperationState.AWAITING_APPROVAL,
        )
    )
    denied = resolve_broker_approval(
        reloaded_ops_store,
        "op-force-push-denied",
        "deny",
        action_result=ActionResult(
            verdict=ActionVerdict.DENY,
            summary="operator denied force push",
            action_id="act-denied",
        ),
    )
    assert denied.state is OperationState.FAILED

    proxy = broker.handle_payload(
        {
            "version": PROTOCOL_VERSION,
            "operation": "issue_llm_proxy_credential",
            "provider": "openrouter",
            "proxy_base_url": "http://broker.local/llm/openrouter",
            "upstream_base_url": "https://openrouter.ai/api/v1",
        }
    )
    proxy_auth = proxy["proxy"]["broker_auth"]
    assert proxy_auth.startswith("arnold-broker-")

    record_broker_audit_entry(
        run_id="run-001",
        step_path="megaplan.execute[0]",
        action_id="act-git-1",
        effect_refs=("git-effect:001",),
        git_command_ref="git-command:001",
        git_effect_ref="git-effect:001",
        prompt_ref="prompt:001",
        completion_ref="completion:001",
        metadata={"provider": "openrouter", "credential": SECRET_VALUE},
    )
    audit_ref = claim_broker_audit_entry("run-001", "megaplan.execute[0]")
    assert audit_ref is not None
    assert audit_ref["git_effect_ref"] == "git-effect:001"
    assert SECRET_VALUE not in json.dumps(audit_ref)
    assert SECRET_VALUE not in json.dumps(protected_push)
    assert SECRET_VALUE not in json.dumps(force_push)
    assert SECRET_VALUE not in json.dumps(proxy)

    assert claim_broker_audit_entry("run-001", "megaplan.execute[0]") is None

    resume_path = tmp_path / "durable-resume.json"
    resume_path.write_text(
        json.dumps(
            DurableResumeRecord(
                run_id="run-001",
                step_path="megaplan.execute[0]",
                lease_token="lease-a",
                reconcile_state="pending",
                audit_refs=("git-effect:001", "completion:001"),
            ).to_json(),
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    reloaded_store = FileProjectLeaseStore(tmp_path / "lease-store")
    reloaded_lease = reloaded_store.load_project_lease("project-alpha", "worktree-main")
    interrupted = DurableResumeRecord.from_json(json.loads(resume_path.read_text(encoding="utf-8")))
    assert reloaded_lease.lease_token == interrupted.lease_token

    expired = reloaded_store.load_project_lease("project-alpha", "worktree-main")
    clean_reconcile = ReconcileDecision(
        state="clean",
        action="execute",
        continue_execution=True,
        skip_execution=False,
        detail="deterministic fake clean worktree",
        required_metadata=(),
    )
    takeover = evaluate_expired_takeover(
        expired,
        reconcile_decision=clean_reconcile,
        current_trust_state="trusted",
        now=clock + timedelta(minutes=5),
    )
    assert takeover.allowed is True
    assert takeover.reconcile_state == "clean"
    resumed = reloaded_store.claim_project_lease(
        "project-alpha",
        "worktree-main",
        run_id="run-002",
        owner_id="worker-b",
        lease_token="lease-b",
        lease_seconds=30,
        takeover_validated=takeover.allowed,
        takeover_reason=takeover.reason,
        now=clock + timedelta(minutes=5),
    )
    assert resumed.last_result["expired_takeover"]["previous_owner_id"] == "worker-a"

    blocked_reconcile = ReconcileDecision(
        state="dirty_unknown_changes",
        action="block",
        continue_execution=False,
        skip_execution=False,
        detail="unowned file",
        required_metadata=("owned_paths",),
    )
    blocked = evaluate_expired_takeover(
        resumed,
        reconcile_decision=blocked_reconcile,
        current_trust_state="trusted",
        now=clock + timedelta(minutes=10),
    )
    assert blocked.allowed is False
    assert blocked.reason == "reconcile:dirty_unknown_changes"

    cancellable = reloaded_store.claim_project_lease(
        "project-cancel",
        "worktree-cancel",
        run_id="run-cancel",
        owner_id="worker-cancel",
        lease_token="lease-cancel",
        lease_seconds=30,
        now=clock + timedelta(minutes=5),
    )
    cancelled = reloaded_store.cancel_project_lease(
        cancellable.project_id,
        cancellable.worktree_id,
        lease_token="lease-cancel",
        result={"audit_refs": list(interrupted.audit_refs)},
        now=clock + timedelta(minutes=5, seconds=1),
    )
    assert cancelled.state.value == "cancelled"
    assert cancelled.last_result["audit_refs"] == ["git-effect:001", "completion:001"]

    failed = record_restart_failure(
        reloaded_store,
        resumed,
        lease_token="lease-b",
        reason="worker_crash",
        policy=RestartPolicy(retry_delay_seconds=1, jitter_seconds=0, quarantine_failure_count=2),
        now=clock + timedelta(minutes=5, seconds=5),
        result={"resume": interrupted.to_json()},
    )
    assert failed.next_retry_at is not None
    restart_decision = evaluate_automatic_restart(
        failed,
        now=clock + timedelta(minutes=5, seconds=5, milliseconds=500),
    )
    assert restart_decision.allowed is False
    assert restart_decision.reason == "retry_delay_active"

    reclaimed = reloaded_store.claim_project_lease(
        "project-alpha",
        "worktree-main",
        run_id="run-003",
        owner_id="worker-c",
        lease_token="lease-c",
        lease_seconds=30,
        now=failed.next_retry_at + timedelta(seconds=1),
    )
    first_quarantine_probe = record_restart_failure(
        reloaded_store,
        reclaimed,
        lease_token="lease-c",
        reason="worker_crash",
        policy=RestartPolicy(retry_delay_seconds=0, jitter_seconds=0, quarantine_failure_count=2),
        now=clock + timedelta(minutes=5, seconds=10),
        result={"resume": interrupted.to_json()},
    )
    assert first_quarantine_probe.state.value == "quarantined"
    quarantine_decision = evaluate_automatic_restart(
        first_quarantine_probe,
        now=clock + timedelta(minutes=5, seconds=11),
    )
    assert quarantine_decision.allowed is False
    assert quarantine_decision.manual_clear_required is True

    gate = CapacityGate({"provider": CapacityPoolConfig(name="provider", limit=1, wait=False)})
    held = gate.acquire("provider", lease_id="lease-held", fencing_token=1)
    assert held.status is CapacityStatus.GRANTED
    capacity_result: dict[str, object] = {}
    with pytest.raises(CapacityGateRejected) as rejected:
        with gate_capacity(
            "provider_proxy_call",
            CapacityContext(
                gate=gate,
                pool="provider",
                lease_id="lease-over-capacity",
                fencing_token=1,
                last_result=capacity_result,
            ),
        ):
            raise AssertionError("capacity rejection must not enter protected call")
    assert rejected.value.metadata["reason"] == "capacity_exhausted"
    assert capacity_result["capacity"]["operation"] == "provider_proxy_call"
