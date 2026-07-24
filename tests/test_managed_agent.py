from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from dataclasses import replace
import importlib.util
import re

import pytest

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.incident.projection import rebuild_projections
from arnold_pipelines.megaplan.managed_agent import (
    MANAGED_AGENT_CUSTODIAN,
    MANAGED_AGENT_SCHEMA,
    MANAGED_DIFFICULTY_CEILING_ENV,
    ManagedCommandSpec,
    MACHINE_ORIGIN_SCHEMA,
    RESIDENT_DELEGATION_ENV,
    SEALED_STDIN_PLACEHOLDER,
    machine_origin_provenance,
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
    description: str | None = None,
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
        description=description,
        launch_provenance=machine_origin_provenance(
            origin_kind="repair_loop_worker",
            origin_id=identity,
            component="tests.test_managed_agent",
            trigger_id=identity,
        ),
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
    assert payload["description"] == "fixture managed worker"
    assert payload["completion_delivery"]["status"] == "not_applicable"
    assert payload["launch_provenance"]["schema_version"] == MACHINE_ORIGIN_SCHEMA
    assert payload["launch_provenance"]["transport"] == "automatic_system"
    assert payload["stdin"] == {"kind": "devnull", "sealed": True, "size_bytes": 0}
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


def test_automatic_run_persists_specific_operator_description(tmp_path: Path) -> None:
    item = spec(
        tmp_path,
        identity="described-investigator",
        description=(
            "Read-only investigation of repair_goal_owner_missing for custody-control-plane "
            "at m5a/execute"
        ),
    )

    path, payload, created = reserve_managed_command(item)

    assert created is True
    assert path.exists()
    assert payload["description"] == (
        "Read-only investigation of repair_goal_owner_missing for custody-control-plane "
        "at m5a/execute"
    )


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
        "--origin-kind",
        "repair_loop_worker",
        "--origin-id",
        "duplicate-race",
        "--origin-component",
        "tests.test_managed_agent",
        "--trigger-id",
        "duplicate-race",
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


def test_sealed_stdin_and_placeholder_are_durable(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("sealed prompt\n", encoding="utf-8")
    item = replace(
        spec(tmp_path, identity="sealed-stdin"),
        stdin_path=prompt,
        argv=(
            sys.executable,
            "-c",
            "import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text(), end='')",
            SEALED_STDIN_PLACEHOLDER,
        ),
        require_output=True,
    )

    assert run_managed_command(item) == 0
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    sealed = Path(payload["stdin"]["path"])
    assert sealed.read_text(encoding="utf-8") == "sealed prompt\n"
    assert sealed.stat().st_mode & 0o777 == 0o400
    assert "sealed prompt" in Path(payload["log_path"]).read_text(encoding="utf-8")
    assert payload["launch_contract_sha256"]


def test_same_identity_cannot_change_launch_contract(tmp_path: Path) -> None:
    original = spec(tmp_path, identity="contract-fence")
    reserve_managed_command(original)

    with pytest.raises(RuntimeError, match="launch contract changed"):
        reserve_managed_command(replace(original, model="different-model"))


def test_tampered_sealed_stdin_is_not_projected_as_canonical(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("original", encoding="utf-8")
    item = replace(
        spec(tmp_path, identity="tampered-stdin"),
        stdin_path=prompt,
    )
    assert run_managed_command(item) == 0
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    Path(payload["stdin"]["path"]).write_text("tampered", encoding="utf-8")

    row = list_managed_resident_agents(project_root=tmp_path, workspace_root=None)["recent"][0]
    assert row["evidence_class"] == "legacy_noncanonical"
    assert row["status"] == "noncanonical_legacy"


def test_malformed_or_discord_machine_provenance_fails_closed(tmp_path: Path) -> None:
    item = spec(tmp_path, identity="bad-provenance")
    with pytest.raises(ValueError, match="transport must be automatic_system"):
        reserve_managed_command(
            replace(
                item,
                launch_provenance={
                    **item.launch_provenance,
                    "transport": "discord",
                },
            )
        )


def test_required_output_failure_is_terminal_and_durable(tmp_path: Path) -> None:
    item = replace(
        spec(tmp_path, identity="no-output", code="pass"),
        require_output=True,
    )

    assert run_managed_command(item) == 74
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    result = json.loads(Path(payload["result_path"]).read_text())
    assert payload["status"] == "failed"
    assert payload["error_class"] == "ManagedAgentNoOutput"
    assert result["output_size_bytes"] == 0


def test_active_repair_goal_cannot_be_completed_by_worker_exit(tmp_path: Path) -> None:
    goal_path = tmp_path / "active-repair-goal.json"
    goal_path.write_text(
        json.dumps(
            {
                "goal_id": "goal-active",
                "checkpoint_digest": "checkpoint-active",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )
    item = spec(
        tmp_path,
        identity="active-goal-worker-exit",
        run_kind="automatic_repair",
        links={"repair_goal_path": str(goal_path)},
    )

    assert run_managed_command(item) == 75
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    assert payload["status"] == "failed"
    assert payload["error_class"] == "RepairGoalIncomplete"
    assert payload["semantic_completion"]["status"] == "continuing"
    assert payload["semantic_completion"]["complete"] is False


def test_missing_repair_goal_evidence_fails_closed(tmp_path: Path) -> None:
    item = spec(
        tmp_path,
        identity="missing-goal-worker-exit",
        run_kind="automatic_repair",
        links={"repair_goal_path": str(tmp_path / "missing-goal.json")},
    )

    assert run_managed_command(item) == 75
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    assert payload["status"] == "failed"
    assert payload["repair_goal"]["status"] == "unknown"
    assert payload["semantic_completion"]["complete"] is False


def test_approval_gate_is_terminal_non_success_not_autonomous_failure(
    tmp_path: Path,
) -> None:
    goal_path = tmp_path / "approval-repair-goal.json"
    goal_path.write_text(
        json.dumps(
            {
                "goal_id": "goal-approval",
                "checkpoint_digest": "checkpoint-approval",
                "status": "approval_required",
            }
        ),
        encoding="utf-8",
    )
    item = spec(
        tmp_path,
        identity="approval-goal-worker-exit",
        run_kind="automatic_repair",
        links={"repair_goal_path": str(goal_path)},
    )

    assert run_managed_command(item) == 0
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    assert payload["status"] == "completed"
    assert payload.get("error_class") is None
    assert payload["repair_goal"]["status"] == "approval_required"
    assert payload["semantic_completion"] == {
        "status": "blocked",
        "complete": False,
        "authority": "repair_goal",
        "goal_id": "goal-approval",
        "checkpoint_digest": "checkpoint-approval",
        "reason": "explicit human approval or authorization gate verified",
    }


def test_automatic_child_gets_machine_origin_not_resident_reply_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        RESIDENT_DELEGATION_ENV,
        json.dumps(
            {
                "applicability": "not_applicable",
                "transport": "non_discord",
                "source_kind": "test_parent",
            }
        ),
    )
    item = replace(
        spec(
            tmp_path,
            identity="machine-env",
            code=(
                "import os; "
                "print('resident=' + str('ARNOLD_RESIDENT_DELEGATION_CONTEXT' in os.environ)); "
                "print('machine=' + str('ARNOLD_MANAGED_AGENT_ORIGIN' in os.environ))"
            ),
        ),
        require_output=True,
    )

    assert run_managed_command(item) == 0
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    output = Path(payload["log_path"]).read_text(encoding="utf-8")
    assert "resident=False" in output
    assert "machine=True" in output
    assert payload["upstream_custody"]["applicability"] == "not_applicable"


def test_automatic_v2_without_canonical_contract_is_visible_but_not_live_evidence(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / ".megaplan/plans/resident-subagents/managed-old"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": MANAGED_AGENT_SCHEMA,
                "custodian": MANAGED_AGENT_CUSTODIAN,
                "run_id": "managed-old",
                "run_kind": "automatic_repair",
                "status": "running",
                "created_at": "2026-07-13T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    row = list_managed_resident_agents(project_root=tmp_path, workspace_root=None)["recent"][0]
    assert row["evidence_class"] == "legacy_noncanonical"
    assert row["status"] == "noncanonical_legacy"
    assert row["live"] is False


@pytest.mark.parametrize("split_options", [False, True])
def test_nested_hermes_launch_reenters_shared_manager(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, split_options: bool
) -> None:
    parent = spec(tmp_path, identity="nested-parent")
    assert run_managed_command(parent) == 0
    parent_manifest = manifest_path(tmp_path, parent)
    parent_payload = json.loads(parent_manifest.read_text(encoding="utf-8"))
    prompt = tmp_path / "nested-prompt.md"
    prompt.write_text("research this", encoding="utf-8")
    launcher_path = (
        Path(__file__).resolve().parents[1]
        / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py"
    )
    module_spec = importlib.util.spec_from_file_location("test_hermes_launcher", launcher_path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    monkeypatch.setenv("ARNOLD_MANAGED_AGENT_RUN_ID", parent_payload["run_id"])
    monkeypatch.setenv("ARNOLD_MANAGED_AGENT_MANIFEST", str(parent_manifest))
    monkeypatch.setenv(
        "ARNOLD_MANAGED_AGENT_ORIGIN",
        json.dumps(parent_payload["launch_provenance"]),
    )
    launcher_args = (
        [
            str(launcher_path),
            "--model",
            "deepseek:deepseek-v4-pro",
            "--project_dir",
            str(tmp_path),
            "--query_file",
            str(prompt),
        ]
        if split_options
        else [
            str(launcher_path),
            "--model=deepseek:deepseek-v4-pro",
            f"--project_dir={tmp_path}",
            f"--query_file={prompt}",
        ]
    )
    monkeypatch.setattr(sys, "argv", launcher_args)
    launched: list[str] = []

    def fake_run(command, **_kwargs):
        launched.extend(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module._automatic_managed_reexec() == 0
    assert "automatic_research_subagent" in launched
    assert str(parent_payload["run_id"]) in launched
    assert "@managed-stdin@" in "\n".join(launched)
    assert str(tmp_path.resolve()) in launched


def test_root_authority_ceiling_is_durable_and_inherited_by_child(
    tmp_path: Path,
) -> None:
    item = replace(
        spec(
            tmp_path,
            identity="d9-root-ceiling",
            run_kind="automatic_root_cause_repair",
            code=(
                "import os; "
                f"print(os.environ[{MANAGED_DIFFICULTY_CEILING_ENV!r}])"
            ),
        ),
        difficulty=9,
        child_difficulty_ceiling=9,
        require_output=True,
    )

    assert run_managed_command(item) == 0
    payload = json.loads(manifest_path(tmp_path, item).read_text())
    assert payload["authority"] == {
        "root_difficulty": 9,
        "child_difficulty_ceiling": 9,
        "inherited_ceiling": None,
        "self_escalation_allowed": False,
    }
    assert Path(payload["log_path"]).read_text().strip() == "9"


def test_managed_child_cannot_self_escalate_above_inherited_root_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(MANAGED_DIFFICULTY_CEILING_ENV, "9")
    item = replace(
        spec(tmp_path, identity="illegal-d10-child"),
        difficulty=10,
        child_difficulty_ceiling=10,
    )

    with pytest.raises(ValueError, match="exceeds inherited root ceiling"):
        reserve_managed_command(item)


def test_child_ceiling_cannot_exceed_its_own_root_difficulty(tmp_path: Path) -> None:
    item = replace(
        spec(tmp_path, identity="illegal-ceiling"),
        difficulty=8,
        child_difficulty_ceiling=9,
    )

    with pytest.raises(ValueError, match="cannot exceed root difficulty"):
        reserve_managed_command(item)


def test_real_dispatch_seams_use_shared_supervisor() -> None:
    root = Path(__file__).resolve().parents[1]
    watchdog = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog").read_text()
    repair = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop").read_text()
    meta = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop").read_text()
    trigger = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger").read_text()
    auditor = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor").read_text()
    legacy = (root / "arnold_pipelines/megaplan/cloud/wrappers/arnold-kimi-goal-operator").read_text()
    hermes = (
        root / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py"
    ).read_text()

    assert "--run-kind automatic_repair" in watchdog
    assert "--run-kind automatic_meta_repair" in watchdog
    assert repair.count("--run-kind automatic_repair_retry") >= 2
    assert "--run-kind automatic_meta_repair_worker" in meta
    assert "ManagedCommandSpec(" in meta and "meta_repair_retrigger" in meta
    assert "subprocess.Popen(\n            manager_argv" in trigger
    assert "subprocess.Popen(cmd" not in trigger
    assert "--run-kind automatic_progress_audit_agent" in auditor
    assert "--run-kind automatic_legacy_fixer" in legacy
    assert "automatic_research_subagent" in hermes
    assert "_automatic_managed_reexec" in hermes

    # Actual worker commands may remain as argv passed to the manager.  Every
    # shipped automatic wrapper containing one must also contain the canonical
    # seam; this catches a future direct subprocess regression deterministically.
    for source in (watchdog, repair, meta, auditor, legacy):
        if "codex exec" in source:
            assert "arnold_pipelines.megaplan.managed_agent run" in source

    for name, source in {
        "watchdog": watchdog,
        "repair": repair,
        "meta": meta,
        "auditor": auditor,
        "legacy": legacy,
    }.items():
        lines = source.splitlines()
        launches = [
            index
            for index, line in enumerate(lines)
            if re.search(r"\btimeout\b.*\bcodex exec\b", line)
        ]
        assert launches, f"fixture no longer inventories the {name} Codex worker"
        for index in launches:
            local_launch_block = "\n".join(lines[max(0, index - 60) : index + 61])
            assert "arnold_pipelines.megaplan.managed_agent run" in local_launch_block, (
                f"direct ad-hoc Codex launch escaped the managed seam in {name}:{index + 1}"
            )
