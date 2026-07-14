"""T11: sidecar / status evidence field contract tests for ``cloud status --chain``."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan import chain as chain_module
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
    def __init__(
        self,
        *,
        remote_spec: str,
        chain_yaml: str,
        chain_state: dict,
        plan_status: dict,
        runner_probe: str = "dead\n",
    ) -> None:
        self.remote_spec = remote_spec
        self.state_path = str(chain_module._state_path_for(Path(remote_spec)))
        self.chain_yaml = chain_yaml
        self.chain_state = chain_state
        self.plan_status = plan_status
        self.runner_probe = runner_probe

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
            return subprocess.CompletedProcess([], 0, self.runner_probe, "")
        if command.startswith("stat "):
            return subprocess.CompletedProcess([], 0, "unavailable\n", "")
        if "verify-human" in command:
            return subprocess.CompletedProcess([], 0, "{}", "")
        return subprocess.CompletedProcess([], 1, "", "unexpected command")


def _payload(
    *,
    plan_status: dict | None = None,
    runner_probe: str = "dead\n",
) -> dict:
    remote_spec = "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml"
    chain_yaml = "milestones:\n  - label: m1\n    idea: idea.md\n"
    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name="milestone-demo",
        last_state="prepped",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
        chain_session="megaplan-chain-demo",
    ).to_dict()
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets={},
        ssh=SshSpec(host="testhost"),
    )
    return cloud_chain_status_payload(
        Path("/repo"),
        argparse.Namespace(remote_spec=remote_spec, cloud_yaml=None),
        spec,
        _StatusProvider(
            remote_spec=remote_spec,
            chain_yaml=chain_yaml,
            chain_state=chain_state,
            plan_status=plan_status or {"status": "running"},
            runner_probe=runner_probe,
        ),
    )


# ── evidence field separation ───────────────────────────────────────────


def test_cloud_status_payload_has_all_four_evidence_keys() -> None:
    payload = _payload()

    for key in ("marker_evidence", "tmux_evidence", "process_evidence", "active_step_evidence"):
        assert key in payload, f"missing evidence key: {key}"
        assert isinstance(payload[key], dict), f"{key} must be a dict"


def test_marker_evidence_reporting_structure() -> None:
    """``marker_evidence`` always carries a ``status`` key."""
    payload = _payload()

    me = payload["marker_evidence"]
    assert "status" in me
    # When no local marker exists, status is "missing"
    assert me["status"] in ("present", "missing", "invalid")


def test_tmux_evidence_status_reflects_runner_probe() -> None:
    """``tmux_evidence.status`` must reflect the runner probe outcome."""
    payload_dead = _payload(runner_probe="dead\n")
    assert payload_dead["tmux_evidence"]["status"] == "missing"

    payload_alive = _payload(runner_probe="tmux_alive\n")
    assert payload_alive["tmux_evidence"]["status"] == "alive"

    payload_process = _payload(runner_probe="process_alive\n")
    assert payload_process["tmux_evidence"]["status"] == "missing"


def test_process_evidence_status_reflects_runner_probe() -> None:
    """``process_evidence.status`` must reflect the runner probe outcome."""
    payload_dead = _payload(runner_probe="dead\n")
    assert payload_dead["process_evidence"]["status"] == "dead"

    payload_alive = _payload(runner_probe="tmux_alive\n")
    assert payload_alive["process_evidence"]["status"] == "unknown"

    payload_process = _payload(runner_probe="process_alive\n")
    assert payload_process["process_evidence"]["status"] == "alive"


def test_active_step_evidence_present_with_active_step() -> None:
    payload = _payload(
        plan_status={
            "status": "running",
            "active_step": {"phase": "plan", "name": "design", "attempt": 1, "worker_pid": 1234},
        },
    )
    assert payload["active_step_evidence"]["status"] == "present"
    assert payload["active_step_evidence"]["phase"] == "plan"
    assert payload["active_step_evidence"]["name"] == "design"


def test_active_step_evidence_absent_without_active_step() -> None:
    payload = _payload(plan_status={"status": "running"})
    assert payload["active_step_evidence"]["status"] == "absent"


def test_evidence_fields_are_separate_not_merged() -> None:
    """Each evidence field is a separate top-level key, not merged into the
    runner or status dict."""
    payload = _payload()

    assert "marker_evidence" in payload
    assert "tmux_evidence" in payload
    assert "process_evidence" in payload
    assert "active_step_evidence" in payload
    # These should NOT be nested under a single "evidence" key
    assert not isinstance(payload.get("evidence"), dict) or "evidence" not in payload


def test_marker_only_session_shows_all_evidence_fields() -> None:
    """Even when only a marker exists (no tmux, no process), all four evidence
    fields are present with appropriate status values."""
    payload = _payload(runner_probe="dead\n")

    # tmux is missing
    assert payload["tmux_evidence"]["status"] == "missing"
    # process is dead
    assert payload["process_evidence"]["status"] == "dead"
    # marker_evidence may be missing (because no local marker file was created)
    assert "status" in payload["marker_evidence"]
    # active_step may be absent
    assert "status" in payload["active_step_evidence"]


# ── S4: semantic health and custody rendered separately ────────────────────


def test_detailed_format_renders_lifecycle_separate_from_semantic_health() -> None:
    """Detailed format renders lifecycle/activity and semantic_health as distinct lines."""
    from arnold_pipelines.megaplan.cloud.status_format import (
        format_cloud_status_detailed,
    )

    snap = {
        "generated_at": "2026-07-14T01:00:00Z",
        "source": "test",
        "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
        "sessions": [
            {
                "session": "demo",
                "status": "running",
                "current_plan": "test-plan",
                "completed_count": 1,
                "milestone_count": 3,
                "lifecycle_state": "finalized",
                "activity_phase": "execute",
                "semantic_health": {
                    "schema": "arnold.workflow.cloud_counts_summary.v1",
                    "session_id": "demo",
                    "fingerprint": "abc123def456",
                    "total_count": 3,
                    "counts_by_boundary": {},
                    "counts_by_phase": {},
                    "counts_by_kind": {"ERROR": 2, "WARNING": 1},
                    "counts_by_repair_domain": {},
                },
                "custody_state": "repairing",
                "repair_state": "active",
                "progress": {},
                "evidence": {"marker": "/tmp/marker"},
                "tmux": True,
                "process": True,
                "latest_activity": "2026-07-14T00:59:00Z",
                "operator_next": "",
            }
        ],
        "degraded": None,
    }

    detailed = format_cloud_status_detailed(snap)

    # Lifecycle and activity appear as a distinct line, separate from semantic_health.
    assert "lifecycle: finalized" in detailed
    assert "activity: execute" in detailed
    # Semantic health appears as its own line with findings count and fingerprint.
    assert "semantic_health:" in detailed
    assert "findings=3" in detailed
    assert "fp=abc123def456" in detailed
    # Custody/repair rendered separately from process liveness.
    assert "custody=repairing" in detailed


def test_detailed_format_warns_unmanaged_process() -> None:
    """Detailed format emits unmanaged-process warning when process alive but no tmux."""
    from arnold_pipelines.megaplan.cloud.status_format import (
        format_cloud_status_detailed,
    )

    snap = {
        "generated_at": "2026-07-14T01:00:00Z",
        "source": "test",
        "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
        "sessions": [
            {
                "session": "stray",
                "status": "running",
                "current_plan": "test-plan",
                "completed_count": 0,
                "milestone_count": 1,
                "lifecycle_state": "planned",
                "activity_phase": "execute",
                "custody_state": "",
                "repair_state": "none",
                "progress": {},
                "evidence": {"marker": "/tmp/marker"},
                "tmux": False,
                "process": True,
                "latest_activity": "2026-07-14T00:59:00Z",
                "operator_next": "",
            }
        ],
        "degraded": None,
    }

    detailed = format_cloud_status_detailed(snap)

    assert "warnings:" in detailed
    assert "unmanaged-process" in detailed


def test_detailed_format_warns_stale_active_step() -> None:
    """Detailed format emits stale active-step warning when activity is old."""
    from arnold_pipelines.megaplan.cloud.status_format import (
        format_cloud_status_detailed,
    )

    snap = {
        "generated_at": "2026-07-14T01:00:00Z",
        "source": "test",
        "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
        "sessions": [
            {
                "session": "stale-session",
                "status": "running",
                "current_plan": "test-plan",
                "completed_count": 0,
                "milestone_count": 1,
                "lifecycle_state": "executed",
                "activity_phase": "execute",
                "custody_state": "",
                "repair_state": "none",
                "progress": {},
                "evidence": {"marker": "/tmp/marker"},
                "tmux": True,
                "process": True,
                "latest_activity": "2026-07-14T00:00:00Z",  # 1h ago → stale
                "operator_next": "",
            }
        ],
        "degraded": None,
    }

    detailed = format_cloud_status_detailed(snap)

    assert "warnings:" in detailed
    assert "stale active-step" in detailed


def test_short_format_includes_compact_s4_tags() -> None:
    """Short/Discord format includes compact S4 tags for findings and custody."""
    from arnold_pipelines.megaplan.cloud.status_format import (
        format_cloud_status_short,
    )

    snap = {
        "generated_at": "2026-07-14T01:00:00Z",
        "source": "test",
        "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
        "sessions": [
            {
                "session": "demo",
                "status": "running",
                "current_plan": "test-plan",
                "completed_count": 1,
                "milestone_count": 3,
                "lifecycle_state": "finalized",
                "activity_phase": "execute",
                "semantic_health": {
                    "schema": "arnold.workflow.cloud_counts_summary.v1",
                    "session_id": "demo",
                    "fingerprint": "abc123def456",
                    "total_count": 3,
                    "counts_by_boundary": {},
                    "counts_by_phase": {},
                    "counts_by_kind": {},
                    "counts_by_repair_domain": {},
                },
                "custody_state": "repairing",
                "repair_state": "active",
                "progress": {},
                "evidence": {"marker": "/tmp/marker"},
                "tmux": True,
                "process": True,
                "latest_activity": "2026-07-14T00:59:00Z",
                "operator_next": "",
            }
        ],
        "degraded": None,
    }

    chunks = format_cloud_status_short(snap)
    combined = " ".join(chunks)

    assert "[SH:3]" in combined
    assert "[custody:repairing]" in combined
    assert "[repair:active]" in combined


def test_short_format_warns_unmanaged_process_compact() -> None:
    """Short format includes unmanaged-process warning as compact tag."""
    from arnold_pipelines.megaplan.cloud.status_format import (
        format_cloud_status_short,
    )

    snap = {
        "generated_at": "2026-07-14T01:00:00Z",
        "source": "test",
        "summary": {"running": 1, "repairing": 0, "blocked": 0, "attention": 0, "complete": 0},
        "sessions": [
            {
                "session": "stray",
                "status": "running",
                "current_plan": "test-plan",
                "completed_count": 0,
                "milestone_count": 1,
                "lifecycle_state": "planned",
                "activity_phase": "execute",
                "custody_state": "",
                "repair_state": "none",
                "progress": {},
                "evidence": {"marker": "/tmp/marker"},
                "tmux": False,
                "process": True,
                "latest_activity": "2026-07-14T00:59:00Z",
                "operator_next": "",
            }
        ],
        "degraded": None,
    }

    chunks = format_cloud_status_short(snap)
    combined = " ".join(chunks)

    assert "[⚠unmanaged]" in combined
