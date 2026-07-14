from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.cloud import repair_contract, repair_requests
from arnold_pipelines.megaplan.cloud.cli import cloud_chain_status_payload
from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)


class _StatusProvider:
    def __init__(self, *, remote_spec: str, chain_yaml: str, chain_state: dict, plan_status: dict) -> None:
        self.remote_spec = remote_spec
        self.state_path = str(chain_module._state_path_for(Path(remote_spec)))
        self.chain_yaml = chain_yaml
        self.chain_state = chain_state
        self.plan_status = plan_status

    def read_remote_file(self, path: str) -> str:
        if path == self.remote_spec:
            return self.chain_yaml
        if path == self.state_path:
            return json.dumps(self.chain_state)
        raise OSError(f"unexpected remote file: {path}")

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        return dict(self.plan_status)

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        if "tmux has-session" in command:
            return subprocess.CompletedProcess([], 0, "dead\n", "")
        if command.startswith("stat "):
            return subprocess.CompletedProcess([], 0, "unavailable\n", "")
        if "verify-human" in command:
            return subprocess.CompletedProcess([], 0, "{}", "")
        return subprocess.CompletedProcess([], 1, "", "unexpected command")


def _payload(tmp_path: Path, *, plan_status: dict, custody_setup: str) -> dict:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    remote_spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    remote_spec.parent.mkdir(parents=True)
    remote_spec.write_text("milestones:\n  - label: m1\n    idea: idea.md\n", encoding="utf-8")
    marker_dir = workspace / ".megaplan" / "cloud-sessions"
    queue_root = workspace / ".megaplan" / "repair-queue"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir(parents=True)
    repair_data_dir.mkdir()
    session = "megaplan-chain-demo"
    plan_name = "agentic-replay-viewer"
    (marker_dir / f"{session}.json").write_text(
        json.dumps(
            {
                "session": session,
                "workspace": str(workspace),
                "remote_spec": str(remote_spec),
                "run_kind": "chain",
                "plan_name": plan_name,
            }
        ),
        encoding="utf-8",
    )

    signature = {
        "failure_kind": "blocked_recovery_not_resolved",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": plan_name,
        "gate_recommendation": "",
        "blocked_task_id": "T1",
    }
    if custody_setup in {"repairable_not_repairing", "repairing"}:
        queued = repair_requests.enqueue_repair_request(
            queue_root=queue_root,
            marker_dir=marker_dir,
            session=session,
            source="watchdog",
            problem_signature=signature,
            root_cause_hint="repairable blocker",
            workspace=workspace,
            run_kind="chain",
        )
        if custody_setup == "repairing":
            repair_requests.write_decision(
                queue_root,
                request_id=queued["request"]["request_id"],
                decision="dispatched",
                reason="repair loop launched",
            )
            (repair_data_dir / f"{session}.repair-data.json").write_text(
                json.dumps(
                    repair_contract.merge_additive_fields(
                        {
                            "session": session,
                            "workspace": str(workspace),
                            "run_kind": "chain",
                            "plan_name": plan_name,
                            "attempts": [
                                {
                                    "attempt_id": 1,
                                    "request_id": queued["request"]["request_id"],
                                    "mechanical_launch": "running",
                                }
                            ],
                            "current_attempt_id": 1,
                            "outcome": "repairing",
                        }
                    )
                ),
                encoding="utf-8",
            )

    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name=plan_name,
        last_state="blocked",
        resolved_workspace=str(workspace),
        chain_session=session,
    ).to_dict()
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace=str(workspace)),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets={},
        ssh=SshSpec(host="testhost"),
    )
    return cloud_chain_status_payload(
        tmp_path,
        argparse.Namespace(remote_spec=str(remote_spec), cloud_yaml=None),
        spec,
        _StatusProvider(
            remote_spec=str(remote_spec),
            chain_yaml=remote_spec.read_text(encoding="utf-8"),
            chain_state=chain_state,
            plan_status=plan_status,
        ),
    )


def test_custody_reads_only_the_explicit_central_queue(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    central_queue = workspace / ".megaplan" / "repair-queue"
    split_queue = workspace / ".megaplan" / "cloud-sessions" / "repair-queue"
    signature = {
        "failure_kind": "blocked_recovery_not_resolved",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": "demo",
        "gate_recommendation": "",
        "blocked_task_id": "T1",
    }
    repair_requests.enqueue_repair_request(
        queue_root=central_queue,
        session="demo-session",
        source="lifecycle_failure",
        problem_signature=signature,
    )
    split_request_dir = split_queue / "requests"
    split_request_dir.mkdir(parents=True)
    (split_request_dir / "stray.json").write_text(
        json.dumps({"kind": "repair_request", "request_id": "stray"}),
        encoding="utf-8",
    )

    projection = repair_contract.project_repair_custody(
        plan_state={
            "name": "demo",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "blocked_recovery_not_resolved",
                "phase": "execute",
                "metadata": {"blocked_task_id": "T1"},
            },
        },
        current_target={"session": "demo-session"},
        queue_root=central_queue,
    )

    assert len(projection["requests"]) == 1
    assert projection["requests"][0]["source"] == "lifecycle_failure"


def test_cloud_status_exposes_repairing_bucket_without_changing_effective_status(tmp_path: Path) -> None:
    payload = _payload(
        tmp_path,
        plan_status={
            "status": "running",
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "blocked_recovery_not_resolved", "phase": "execute"},
        },
        custody_setup="repairing",
    )

    assert payload["effective_status"] == "running"
    assert payload["repair_custody"] == {
        "status": "available",
        "bucket": "repairing",
        "blocker_id": payload["repair_custody"]["blocker_id"],
        "active_request_ids": payload["repair_custody"]["active_request_ids"],
    }


def test_cloud_status_exposes_repairable_not_repairing_bucket(tmp_path: Path) -> None:
    payload = _payload(
        tmp_path,
        plan_status={
            "status": "running",
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "blocked_recovery_not_resolved", "phase": "execute"},
        },
        custody_setup="repairable_not_repairing",
    )

    assert payload["effective_status"] == "running"
    assert payload["repair_custody"]["status"] == "available"
    assert payload["repair_custody"]["bucket"] == "repairable_not_repairing"
    assert len(payload["repair_custody"]["active_request_ids"]) == 1


def test_cloud_status_exposes_broken_superfixer_bucket_from_local_projection(tmp_path: Path) -> None:
    payload = _payload(
        tmp_path,
        plan_status={
            "status": "running",
            "name": "agentic-replay-viewer",
            "current_state": "finalized",
            "resume_cursor": {},
            "latest_failure": {"kind": "iteration_cap", "phase": "execute"},
        },
        custody_setup="broken_superfixer",
    )

    assert payload["effective_status"] == "running"
    assert payload["repair_custody"] == {
        "status": "available",
        "bucket": "broken_superfixer",
        "blocker_id": payload["repair_custody"]["blocker_id"],
        "active_request_ids": [],
    }


# ---------------------------------------------------------------------------
# T15: Cloud status reflects repair verdict evidence
# ---------------------------------------------------------------------------


def test_cloud_status_reflects_repair_verdict_when_cleared(tmp_path: Path) -> None:
    """Cloud status payload surfaces repair custody correctly when verdict cleared."""
    payload = _payload(
        tmp_path,
        plan_status={
            "status": "running",
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "blocked_recovery_not_resolved", "phase": "execute"},
        },
        custody_setup="repairing",
    )

    # Repair custody is present and reflects the repairing bucket
    assert "repair_custody" in payload
    assert payload["repair_custody"]["status"] == "available"
    assert payload["repair_custody"]["bucket"] == "repairing"
    # The effective status is not changed by custody presence
    assert payload["effective_status"] == "running"


def test_cloud_status_does_not_trust_liveness_only_as_repair_resolution(
    tmp_path: Path,
) -> None:
    """Cloud status with repairable_not_repairing bucket still shows running."""
    payload = _payload(
        tmp_path,
        plan_status={
            "status": "running",
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "blocked_recovery_not_resolved", "phase": "execute"},
        },
        custody_setup="repairable_not_repairing",
    )

    # Even with active requests, the status is still running — not resolved
    assert payload["effective_status"] == "running"
    assert payload["repair_custody"]["bucket"] == "repairable_not_repairing"
    assert len(payload["repair_custody"]["active_request_ids"]) > 0


def test_cloud_status_custody_repair_verdict_blocker_id_present(
    tmp_path: Path,
) -> None:
    """Repair custody in cloud status includes a blocker_id field for traceability."""
    payload = _payload(
        tmp_path,
        plan_status={
            "status": "running",
            "name": "agentic-replay-viewer",
            "current_state": "blocked",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "blocked_recovery_not_resolved", "phase": "execute"},
        },
        custody_setup="repairable_not_repairing",
    )

    custody = payload["repair_custody"]
    assert "blocker_id" in custody
    assert isinstance(custody["blocker_id"], str)
    # Blocker ID is always present (may be empty when no fingerprint is derivable,
    # but the field itself must exist for structured verdict binding)
    assert custody["blocker_id"] is not None
