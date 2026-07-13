from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.incident.projection import rebuild_projections
from arnold_pipelines.megaplan.managed_agent import (
    MANAGED_AGENT_CUSTODIAN,
    MANAGED_AGENT_SCHEMA,
    ManagedCommandSpec,
    reserve_managed_command,
    run_managed_command,
    stable_managed_run_id,
    transition_terminal,
)
from arnold_pipelines.megaplan.resident.subagent import list_managed_resident_agents


def spec(
    root: Path,
    *,
    identity: str,
    code: str = "print('managed-ok')",
    run_kind: str = "automatic_repair_retry",
    lineage: str | None = None,
    links: dict[str, str] | None = None,
) -> ManagedCommandSpec:
    return ManagedCommandSpec(
        run_kind=run_kind,
        identity_key=identity,
        project_dir=root,
        argv=(sys.executable, "-c", code),
        task_kind="root_cause",
        difficulty=8,
        model="gpt-5.6-sol",
        reasoning_effort="high",
        route_class="test_route",
        backend="codex",
        command_display="fixture managed worker",
        links=links or {},
        lineage_key=lineage,
        tee_output=False,
    )


def manifest_path(root: Path, item: ManagedCommandSpec) -> Path:
    run_id = stable_managed_run_id(item.run_kind, item.identity_key)
    return root / ".megaplan" / "plans" / "resident-subagents" / run_id / "manifest.json"


def test_automatic_run_has_full_truthful_lifecycle_and_unified_view(tmp_path: Path) -> None:
    item = spec(
        tmp_path,
        identity="request-1:attempt-1",
        links={
            "repair_request_id": "request-1",
            "blocker_id": "blocker-1",
            "cloud_session": "session-1",
            "chain": "initiative/chain.yaml",
            "plan": "plan-1",
            "phase": "dev_fix",
            "attempt": "1",
        },
    )

    assert run_managed_command(item) == 0

    path = manifest_path(tmp_path, item)
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == MANAGED_AGENT_SCHEMA
    assert payload["custodian"] == MANAGED_AGENT_CUSTODIAN
    assert payload["run_kind"] == "automatic_repair_retry"
    assert payload["status"] == payload["terminal_outcome"] == "completed"
    assert [entry["status"] for entry in payload["status_history"]] == [
        "reserved",
        "launching",
        "running",
        "completed",
    ]
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["reasoning_effort"] == "high"
    assert payload["difficulty"] == 8
    assert payload["completion_delivery"]["status"] == "not_applicable"
    assert payload["links"]["repair_request_id"] == "request-1"
    assert "managed-ok" in Path(payload["full_log_path"]).read_text()
    result = json.loads(Path(payload["result_path"]).read_text())
    assert result["status"] == "completed"

    view = list_managed_resident_agents(project_root=tmp_path, workspace_root=None)
    row = view["recent"][0]
    assert row["run_kind"] == "automatic_repair_retry"
    assert row["status"] == "completed"
    assert row["links"]["blocker_id"] == "blocker-1"
    assert view["delivery_status_counts"] == {"not_applicable": 1}


def test_terminal_failure_is_persisted_with_result(tmp_path: Path) -> None:
    item = spec(tmp_path, identity="failure", code="raise SystemExit(17)")

    assert run_managed_command(item) == 17

    payload = json.loads(manifest_path(tmp_path, item).read_text())
    assert payload["status"] == "failed"
    assert payload["returncode"] == 17
    assert json.loads(Path(payload["result_path"]).read_text())["terminal_outcome"] == "failed"


def test_retry_lineage_is_derived_without_anonymous_replacement(tmp_path: Path) -> None:
    first = spec(tmp_path, identity="retry-1", lineage="request-2:dev")
    second = spec(tmp_path, identity="retry-2", lineage="request-2:dev")
    assert run_managed_command(first) == 0
    assert run_managed_command(second) == 0

    first_payload = json.loads(manifest_path(tmp_path, first).read_text())
    second_payload = json.loads(manifest_path(tmp_path, second).read_text())
    assert second_payload["retry_of_run_id"] == first_payload["run_id"]
    assert second_payload["lineage_key"] == "request-2:dev"


def test_restart_reconciles_same_reserved_run_id(tmp_path: Path) -> None:
    item = spec(tmp_path, identity="restart")
    path, payload, created = reserve_managed_command(item)
    assert created
    payload.update({"status": "running", "pid": 999_999_991, "worker_pid": 999_999_992})
    path.write_text(json.dumps(payload))

    assert run_managed_command(item) == 0

    restarted = json.loads(path.read_text())
    assert restarted["run_id"] == stable_managed_run_id(item.run_kind, item.identity_key)
    assert restarted["restart_count"] == 1
    assert any(
        entry["evidence"] == "restart_reconciled_dead_supervisor_same_run"
        for entry in restarted["status_history"]
    )


def test_restart_adopts_live_worker_without_duplicate_launch(tmp_path: Path) -> None:
    if not Path("/proc").is_dir():
        pytest.skip("managed worker adoption uses Linux procfs identity")
    duplicate_marker = tmp_path / "must-not-launch.txt"
    item = spec(
        tmp_path,
        identity="adopt-live",
        code=f"from pathlib import Path; Path({str(duplicate_marker)!r}).write_text('duplicate')",
    )
    path, payload, _ = reserve_managed_command(item)
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(.25)"])
    try:
        start_ticks = Path(f"/proc/{worker.pid}/stat").read_text().split()[21]
        payload.update(
            {
                "status": "running",
                "pid": 999_999_991,
                "worker_pid": worker.pid,
                "worker_start_ticks": start_ticks,
            }
        )
        path.write_text(json.dumps(payload))

        assert run_managed_command(item) == 1
    finally:
        worker.wait(timeout=5)

    adopted = json.loads(path.read_text())
    assert adopted["terminal_outcome"] == "unknown_after_adoption"
    assert not duplicate_marker.exists()
    assert [entry["status"] for entry in adopted["status_history"]][-2:] == [
        "adopting",
        "unknown",
    ]


@pytest.mark.parametrize("terminal", ["cancelled", "superseded"])
def test_control_plane_terminal_transition_is_truthful(tmp_path: Path, terminal: str) -> None:
    item = spec(tmp_path, identity=terminal)
    path, _, _ = reserve_managed_command(item)

    payload = transition_terminal(path, terminal, reason="fixture authority")

    assert payload["status"] == payload["terminal_outcome"] == terminal
    assert payload["completion_delivery"]["status"] == "not_applicable"
    assert run_managed_command(item) == 143


def test_claim_is_fenced_to_managed_run_and_incident_gets_claim_and_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    queue_dir = repair_requests.repair_queue_dir(marker_dir)
    claim = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="blocker-claim",
        request_id="request-claim",
        actor="watchdog",
        session="session-claim",
        pid=os.getpid(),
        command="arnold-repair-loop session-claim /tmp /tmp/spec",
        cwd=str(tmp_path),
        is_pid_live=lambda pid: pid == os.getpid(),
    )
    assert claim.claimed
    monkeypatch.setenv("CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID", str(os.getpid()))
    monkeypatch.setenv("CLOUD_WATCHDOG_REPAIR_REQUEST_ID", "request-claim")
    item = spec(
        tmp_path,
        identity="request-claim",
        run_kind="automatic_repair",
        links={
            "repair_queue_dir": str(queue_dir),
            "repair_request_id": "request-claim",
            "blocker_id": "blocker-claim",
            "incident_id": "inc-session-claim",
            "cloud_session": "session-claim",
        },
    )

    assert run_managed_command(item) == 0

    owner = json.loads((claim.lock_dir / "owner.json").read_text())
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    assert owner["managed_agent_run_id"] == payload["run_id"]
    assert owner["managed_manifest_path"] == str(manifest_path(tmp_path, item).resolve())
    assert payload["repair_claim"]["fenced_managed_run_id"] == payload["run_id"]
    assert payload["repair_claim"]["request_id"] == "request-claim"
    assert payload["repair_claim"]["blocker_id"] == "blocker-claim"
    projections = rebuild_projections(tmp_path)
    incident = projections["incidents"]["incidents"][0]
    assert [claim["status"] for claim in incident["claims"]] == ["acquired"]
    assert len(incident["attempts"]) == 1
    assert incident["attempts"][0]["attempt_id"] == payload["run_id"]
    attempt_event = next(event for event in incident["events"] if event["type"] == "repair_attempt")
    assert attempt_event["parent"] == [payload["incident_claim_event_id"]]


def _cli(root: Path, marker: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan.managed_agent",
        "run",
        "--run-kind",
        "automatic_repair_retry",
        "--identity-key",
        "duplicate-race",
        "--project-dir",
        str(root),
        "--task-kind",
        "debugging",
        "--difficulty",
        "7",
        "--model",
        "fixture-model",
        "--reasoning-effort",
        "medium",
        "--route-class",
        "fixture",
        "--backend",
        "fixture",
        "--command-display",
        "duplicate race fixture",
        "--",
        sys.executable,
        "-c",
        (
            "from pathlib import Path; import time; "
            f"p=Path({str(marker)!r}); p.open('a').write('launch\\n'); time.sleep(.35)"
        ),
    ]


def test_duplicate_dispatch_race_executes_worker_once(tmp_path: Path) -> None:
    marker = tmp_path / "launches.txt"
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    first = subprocess.Popen(_cli(tmp_path, marker), env=env)
    time.sleep(0.04)
    second = subprocess.Popen(_cli(tmp_path, marker), env=env)
    assert first.wait(timeout=10) == 0
    assert second.wait(timeout=10) == 0

    assert marker.read_text().splitlines() == ["launch"]
    run_root = tmp_path / ".megaplan" / "plans" / "resident-subagents"
    assert len(list(run_root.glob("*/manifest.json"))) == 1


def test_real_dispatch_seams_use_shared_supervisor() -> None:
    root = Path(__file__).resolve().parents[1]
    watchdog = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog").read_text()
    repair = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop").read_text()
    meta = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop").read_text()

    assert "--run-kind automatic_repair" in watchdog
    assert "--run-kind automatic_meta_repair" in watchdog
    assert repair.count("--run-kind automatic_repair_retry") >= 2
    assert "--run-kind automatic_meta_repair_worker" in meta
    assert "ManagedCommandSpec(" in meta and "meta_repair_retrigger" in meta
