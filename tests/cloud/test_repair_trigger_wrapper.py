from __future__ import annotations

import hashlib
import json
import os
import runpy
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock, release_repair_lock
from arnold_pipelines.megaplan.cloud.six_hour_auditor import enqueue_audit_repair_request

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGER = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-repair-trigger"


def _queue_root(workspace: Path) -> Path:
    return workspace / ".megaplan" / "repair-queue"


def _signature(**overrides: str) -> dict[str, str]:
    base = {
        "failure_kind": "blocked_recovery_not_resolved",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": "m3",
        "gate_recommendation": "",
        "blocked_task_id": "T6",
    }
    base.update(overrides)
    return base


def _write_marker(
    marker_dir: Path,
    workspace: Path,
    session: str = "demo",
    plan_name: str = "m3",
) -> Path:
    marker_dir.mkdir(parents=True, exist_ok=True)
    spec = workspace / "chain.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("name: demo\n", encoding="utf-8")
    (marker_dir / f"{session}.json").write_text(
        json.dumps(
            {
                "session": session,
                "workspace": str(workspace),
                "remote_spec": str(spec),
                "run_kind": "chain",
                "plan_name": plan_name,
            }
        ),
        encoding="utf-8",
    )
    return spec


def _enqueue(marker_dir: Path, workspace: Path, session: str = "demo") -> dict[str, object]:
    return repair_requests.enqueue_repair_request(
        queue_root=_queue_root(workspace),
        marker_dir=marker_dir,
        session=session,
        source="test",
        problem_signature=_signature(),
        root_cause_hint="failure details",
        workspace=workspace,
        run_kind="chain",
        created_at="2026-07-01T00:00:00Z",
    )


def _write_chain_state_for_spec(workspace: Path, spec: Path, *, current_plan_name: str = "m3") -> None:
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(str(spec.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"chain-{digest}.json").write_text(
        json.dumps({"current_plan_name": current_plan_name, "last_state": "blocked"}),
        encoding="utf-8",
    )


def _repair_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "repair-loop"
    log = tmp_path / "repair-args.json"
    effects = tmp_path / "repair-effects"
    stub.write_text(
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
effects = Path({str(effects)!r})
effects.mkdir()
for effect in ("subprocess", "state", "source", "commit", "push"):
    effects.joinpath(effect).write_text("mutated", encoding="utf-8")
Path({str(log)!r}).write_text(json.dumps({{"argv": sys.argv[1:], "request_id": os.environ.get("CLOUD_WATCHDOG_REPAIR_REQUEST_ID", ""), "claim_owner_pid": os.environ.get("CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID", ""), "queue_root": os.environ.get("ARNOLD_REPAIR_QUEUE_ROOT", ""), "marker_dir": os.environ.get("ARNOLD_REPAIR_MARKER_DIR", ""), "repair_session": os.environ.get("ARNOLD_REPAIR_SESSION", ""), "repair_run_kind": os.environ.get("ARNOLD_REPAIR_RUN_KIND", "")}}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return stub


def _custody_attempt_repair_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "custody-repair-loop"
    log = tmp_path / "repair-args.json"
    attempts = tmp_path / "repair-attempts.jsonl"
    stub.write_text(
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "attempt_id": "attempt-" + os.environ["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"][:12],
    "request_id": os.environ["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"],
    "blocker_id": os.environ["CLOUD_WATCHDOG_REPAIR_BLOCKER_ID"],
    "session": sys.argv[1],
    "state": "succeeded",
    "outcome": "complete",
}}
Path({str(attempts)!r}).write_text(json.dumps(payload) + "\\n", encoding="utf-8")
Path({str(log)!r}).write_text(json.dumps({{"argv": sys.argv[1:], **payload}}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return stub


def _failing_repair_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "failing-repair-loop"
    attempts = tmp_path / "failing-repair-attempts.jsonl"
    stub.write_text(
        f"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_lock import inspect_repair_lock

queue_dir = os.environ["ARNOLD_REPAIR_QUEUE_ROOT"]
blocker_id = os.environ["CLOUD_WATCHDOG_REPAIR_BLOCKER_ID"]
lock_dir = repair_requests.active_repair_claim_lock_dir(queue_dir, blocker_id)
owner = inspect_repair_lock(lock_dir).owner
with Path({str(attempts)!r}).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({{"request_id": os.environ["CLOUD_WATCHDOG_REPAIR_REQUEST_ID"]}}) + "\\n")
if isinstance(owner, dict):
    repair_requests.release_active_repair_request_claim(
        queue_dir,
        blocker_id=blocker_id,
        owner=owner,
        expected_pid=int(owner["pid"]),
    )
raise SystemExit(75)
""",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return stub


def _run_trigger(
    marker_dir: Path,
    repair_bin: Path,
    *,
    enabled: bool = False,
    autonomy: bool | None = None,
    lock_dir: Path | None = None,
    env_overrides: dict[str, str] | None = None,
    meta_repair_bin: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    env["ARNOLD_CLOUD_HOT_ENV"] = str(marker_dir / "missing-hot-env")
    if enabled:
        env["ARNOLD_REPAIR_TRIGGER_ENABLED"] = "1"
    else:
        env.pop("ARNOLD_REPAIR_TRIGGER_ENABLED", None)
    if env_overrides:
        env.update(env_overrides)
    if not enabled and not (env_overrides and "ARNOLD_CLOUD_HOT_ENV" in env_overrides):
        env["ARNOLD_REPAIR_TRIGGER_ENABLED"] = "0"
    if autonomy is None and env_overrides and "ARNOLD_CLOUD_HOT_ENV" in env_overrides:
        env.pop("ARNOLD_AUTONOMY", None)
    else:
        env["ARNOLD_AUTONOMY"] = "1" if (enabled if autonomy is None else autonomy) else "0"
    cmd = [
        sys.executable,
        str(TRIGGER),
        "--marker-dir",
        str(marker_dir),
        "--queue-root",
        str(_queue_root(marker_dir.parent / "workspace")),
        "--repair-bin",
        str(repair_bin),
        "--meta-repair-bin",
        str(meta_repair_bin or repair_bin),
    ]
    if lock_dir is not None:
        cmd.extend(["--lock-dir", str(lock_dir)])
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)


def _decisions(marker_dir: Path) -> list[dict[str, object]]:
    queue_dir = _queue_root(marker_dir.parent / "workspace")
    records: list[dict[str, object]] = []
    for path in sorted(repair_requests.decisions_dir(queue_dir).glob("*.json"), key=lambda item: item.name):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def _events(result: subprocess.CompletedProcess[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def _read_json_eventually(path: Path, *, timeout_s: float = 2.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.05)
    raise FileNotFoundError(path)


def _read_terminal_manifest_eventually(
    path: Path, *, timeout_s: float = 5.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("status") in {"completed", "failed", "cancelled", "superseded"}:
                return payload
        time.sleep(0.05)
    raise TimeoutError(path)


def _project_request_custody(marker_dir: Path, request: dict[str, object]) -> dict[str, Any]:
    request_payload = request["request"]
    assert isinstance(request_payload, dict)
    session = str(request_payload["session"])
    target = resolve_current_target(
        session,
        marker_dir=marker_dir,
        repair_data_dir=None,
        session_is_live=lambda _session: False,
        pid_is_live=lambda _pid: False,
    )
    signature = request_payload["problem_signature"]
    assert isinstance(signature, dict)
    current_refs = dict(target.get("current_refs") or {}) if isinstance(target.get("current_refs"), dict) else {}
    target_plan = dict(target.get("plan_state") or {}) if isinstance(target.get("plan_state"), dict) else {}
    current_plan_name = str(
        current_refs.get("current_plan_name")
        or current_refs.get("marker_plan_name")
        or signature.get("milestone_or_plan")
        or ""
    )
    if current_plan_name and not current_refs.get("current_plan_name"):
        current_refs["current_plan_name"] = current_plan_name
    if current_plan_name and not target_plan.get("name"):
        target_plan["name"] = current_plan_name
    normalized_target = dict(target)
    normalized_target["current_refs"] = current_refs
    normalized_target["plan_state"] = target_plan
    plan_state = {
        "name": current_plan_name,
        "current_state": str(current_refs.get("plan_current_state") or signature.get("current_state") or ""),
        "resume_cursor": {"retry_strategy": "manual_review"},
        "latest_failure": {
            "kind": str(signature.get("failure_kind") or ""),
            "phase": str(signature.get("phase_or_step") or ""),
            "metadata": {"blocked_task_id": str(signature.get("blocked_task_id") or "")},
        },
    }
    return repair_contract.project_repair_custody(
        plan_state=plan_state,
        current_target=normalized_target,
        queue_root=_queue_root(marker_dir.parent / "workspace"),
        repair_data_dir=None,
    )


def test_trigger_observes_without_dispatch_when_disabled(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    repair_bin = _repair_stub(tmp_path)

    result = _run_trigger(marker_dir, repair_bin, enabled=False)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    assert "dispatched" not in {item["decision"] for item in _decisions(marker_dir)}
    assert str(spec) in result.stdout
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    # The merged boundary contract treats an explicit manual-review cursor as
    # human-required; merely disabling dispatch cannot relabel that custody as
    # a broken superfixer.
    assert observe["dispatch_decision"] == "human_required"
    assert observe["custody_bucket"] == "repairable_not_repairing"
    assert any(
        event["status"] == "no_actionable_requests"
        for event in _events(result)
        if event["event"] == "repair_trigger"
    )


def test_trigger_reports_current_target_resolution_evidence(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False)

    assert result.returncode == 0, result.stderr
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["status"] == "blocked"
    assert observe["authorized"] is False
    assert observe["target"]["authoritative_source"] == "chain_state"
    assert observe["target"]["target_session"] == "demo"
    assert observe["target"]["current_refs"]["remote_spec"] == str(spec)
    assert observe["dispatch_decision"] == "dispatch_l1_repair"


def test_terminal_request_ids_preserve_self_coalesced_owner_and_skip_distinct_duplicate(
    tmp_path: Path,
) -> None:
    namespace = runpy.run_path(str(TRIGGER))
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"

    queued = _enqueue(marker_dir, workspace)
    replay = repair_requests.enqueue_repair_request(
        queue_root=_queue_root(workspace),
        marker_dir=marker_dir,
        session="demo",
        source="test",
        problem_signature=_signature(),
        root_cause_hint="failure details",
        workspace=workspace,
        run_kind="chain",
        created_at="2026-07-01T00:10:00Z",
    )
    repair_requests.write_decision(
        _queue_root(workspace),
        request_id="duplicate-request",
        decision="coalesced",
        reason="matching problem signature already queued",
        related_request_id=queued["request"]["request_id"],
        created_at="2026-07-01T00:11:00Z",
    )
    repair_requests.write_decision(
        _queue_root(workspace),
        request_id=queued["request"]["request_id"],
        decision="dispatched",
        reason="managed attempt launched",
        created_at="2026-07-01T00:12:00Z",
    )

    terminal_ids = namespace["_terminal_request_ids"](_queue_root(workspace))

    assert replay["status"] == "coalesced"
    assert replay["decision"]["related_request_id"] == queued["request"]["request_id"]
    assert queued["request"]["request_id"] not in terminal_ids
    assert "duplicate-request" in terminal_ids


def test_failed_dispatched_attempt_relaunches_as_distinct_managed_retry(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    plan_name = "m6-exact-contract-and-20260716-1303"
    spec = _write_marker(marker_dir, workspace, plan_name=plan_name)
    _write_chain_state_for_spec(workspace, spec, current_plan_name=plan_name)
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "finalize",
                    "retry_strategy": "repair_phase_contract",
                },
                "latest_failure": {
                    "kind": "deterministic_phase_failure",
                    "phase": "finalize",
                    "message": "critique_finding_identity_reused",
                    "metadata": {"count": 3, "max_attempts": 3},
                },
            }
        ),
        encoding="utf-8",
    )
    queued = repair_requests.enqueue_repair_request(
        queue_root=_queue_root(workspace),
        marker_dir=marker_dir,
        session="demo",
        source="lifecycle_failure",
        workspace=workspace,
        run_kind="chain",
        target={
            "plan_dir": str(plan_dir),
            "plan_name": plan_name,
            "workspace_path": str(workspace),
            "retry_strategy": "repair_phase_contract",
        },
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "finalize",
            "milestone_or_plan": plan_name,
            "gate_recommendation": "repair the deterministic phase contract",
            "blocked_task_id": "phase:finalize",
        },
        root_cause_hint="critique_finding_identity_reused",
    )
    repair_bin = _failing_repair_stub(tmp_path)

    first_result = _run_trigger(marker_dir, repair_bin, enabled=True)
    first_dispatch = next(
        event
        for event in _events(first_result)
        if event["event"] == "repair_trigger_dispatch"
    )
    first_manifest = _read_terminal_manifest_eventually(
        Path(first_dispatch["managed_manifest_path"])
    )

    second_result = _run_trigger(marker_dir, repair_bin, enabled=True)
    second_dispatch = next(
        event
        for event in _events(second_result)
        if event["event"] == "repair_trigger_dispatch"
    )
    second_manifest = _read_terminal_manifest_eventually(
        Path(second_dispatch["managed_manifest_path"])
    )

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert first_manifest["status"] == "failed"
    assert second_manifest["status"] == "failed"
    assert first_dispatch["attempt_ordinal"] == 1
    assert second_dispatch["attempt_ordinal"] == 2
    assert second_dispatch["managed_run_id"] != first_dispatch["managed_run_id"]
    assert second_manifest["retry_of_run_id"] == first_dispatch["managed_run_id"]
    assert second_dispatch["request_id"] == queued["request"]["request_id"]
    attempts = repair_requests.iter_repair_attempts(_queue_root(workspace))
    assert [attempt["managed_run_id"] for attempt in attempts] == [
        first_dispatch["managed_run_id"],
        second_dispatch["managed_run_id"],
    ]


def test_trigger_dispatches_existing_repair_loop_when_enabled(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)
    repair_bin = _repair_stub(tmp_path)

    result = _run_trigger(marker_dir, repair_bin, enabled=True)

    assert result.returncode == 0, result.stderr
    assert "repair_trigger_dispatch" in result.stdout
    dispatch_event = next(
        event for event in _events(result) if event["event"] == "repair_trigger_dispatch"
    )
    managed_manifest = Path(dispatch_event["managed_manifest_path"])
    managed = _read_json_eventually(managed_manifest)
    assert managed["run_id"] == dispatch_event["managed_run_id"]
    assert managed["schema_version"] == "arnold-managed-agent-run-v2"
    assert managed["launch_provenance"]["transport"] == "automatic_system"
    assert managed["links"]["repair_request_id"] == queued["request"]["request_id"]
    assert managed["links"]["blocker_id"] == queued["request"]["blocker_id"]
    dispatched = [item for item in _decisions(marker_dir) if item["decision"] == "dispatched"]
    assert len(dispatched) == 1
    payload = _read_json_eventually(tmp_path / "repair-args.json")
    assert payload["argv"] == ["demo", str(workspace), str(spec)]
    assert payload["request_id"] == queued["request"]["request_id"]
    assert payload["claim_owner_pid"].isdigit()
    assert payload["queue_root"] == str(_queue_root(workspace))
    assert payload["marker_dir"] == str(marker_dir)
    assert payload["repair_session"] == "demo"
    assert payload["repair_run_kind"] == "chain"
    assert not (marker_dir.parent / "repair-queue").exists()


def test_m6_phase_failure_persisted_identity_reaches_claim_and_autofixer_launch(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    plan_name = "m6-exact-contract-and-20260716-1303"
    spec = _write_marker(marker_dir, workspace, plan_name=plan_name)
    _write_chain_state_for_spec(workspace, spec, current_plan_name=plan_name)
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_name,
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "critique",
                    "retry_strategy": "repair_phase_contract",
                },
                "latest_failure": {
                    "kind": "deterministic_phase_failure",
                    "phase": "critique",
                    "message": "duplicate worker-local flag IDs and blank evidence",
                    "metadata": {"count": 3, "max_attempts": 3},
                },
            }
        ),
        encoding="utf-8",
    )
    queued = repair_requests.enqueue_repair_request(
        queue_root=_queue_root(workspace),
        marker_dir=marker_dir,
        session="demo",
        source="lifecycle_failure",
        workspace=workspace,
        run_kind="chain",
        target={
            "plan_dir": str(plan_dir),
            "plan_name": plan_name,
            "workspace_path": str(workspace),
            "retry_strategy": "repair_phase_contract",
        },
        problem_signature={
            "failure_kind": "deterministic_phase_failure",
            "current_state": "blocked",
            "phase_or_step": "critique",
            "milestone_or_plan": plan_name,
            "gate_recommendation": "repair the deterministic phase contract",
            "blocked_task_id": "",
        },
        root_cause_hint="duplicate worker-local flag IDs and blank evidence",
        created_at="2026-07-16T13:35:03Z",
    )

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True)

    assert result.returncode == 0, result.stderr
    request = queued["request"]
    assert request["problem_signature"]["blocked_task_id"] == "phase:critique"
    dispatch = next(
        event for event in _events(result) if event["event"] == "repair_trigger_dispatch"
    )
    manifest = _read_json_eventually(Path(dispatch["managed_manifest_path"]))
    assert manifest["links"]["repair_request_id"] == request["request_id"]
    assert manifest["links"]["blocker_id"] == request["blocker_id"]
    claim_path = repair_requests.active_repair_claim_lock_dir(
        _queue_root(workspace), request["blocker_id"]
    ) / "owner.json"
    claim = _read_json_eventually(claim_path)
    assert claim["request_id"] == request["request_id"]
    assert claim["blocker_id"] == request["blocker_id"]


def test_trigger_suppresses_dispatch_claim_when_worker_is_unavailable(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)

    result = _run_trigger(marker_dir, tmp_path / "missing-repair-loop", enabled=True)

    assert result.returncode == 0, result.stderr
    event = next(item for item in _events(result) if item["event"] == "repair_trigger")
    assert event["status"] == "repair_unavailable"
    decisions = [
        item["decision"]
        for item in _decisions(marker_dir)
        if item["request_id"] == queued["request"]["request_id"]
    ]
    assert "dispatched" not in decisions
    assert repair_requests.iter_repair_attempts(_queue_root(workspace)) == []


def test_l3_actionable_finding_reaches_claim_attempt_and_terminal_decision(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)
    queued = enqueue_audit_repair_request(
        {
            "plan": "m3",
            "session": "demo",
            "workspace": str(workspace),
            "current_state": "blocked",
            "session_header": {"kind": "chain"},
            "deterministic_superfixer_evidence": {
                "actionable": True,
                "accepted_unclaimed_request_ids": ["legacy-request"],
                "retry_budget": {
                    "max_attempts": 3,
                    "remaining_attempts": 2,
                    "claim_max_retries": 3,
                },
            },
            "l3_escalation_gate": {
                "eligible": True,
                "decision": "true_stall",
                "escalation_id": "l3-escalation-demo-m3",
                "evidence_digest": "a" * 64,
                "route": {"promotion_reason": "exhausted_l1_l2_custody"},
            },
        },
        queue_root=_queue_root(workspace),
    )
    assert queued is not None and queued["status"] == "queued"
    request = queued["request"]
    signature = request["problem_signature"]
    plan_dir = workspace / ".megaplan" / "plans" / "m3"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "m3",
                "current_state": "blocked",
                "resume_cursor": {"retry_strategy": "meta_repair"},
                "latest_failure": {
                    "kind": signature["failure_kind"],
                    "phase": signature["phase_or_step"],
                    "metadata": {"blocked_task_id": signature["blocked_task_id"]},
                },
            }
        ),
        encoding="utf-8",
    )

    result = _run_trigger(
        marker_dir,
        _custody_attempt_repair_stub(tmp_path),
        enabled=True,
    )

    assert result.returncode == 0, result.stderr
    assert "repair_trigger_dispatch" in result.stdout, result.stdout + result.stderr
    attempt = _read_json_eventually(tmp_path / "repair-args.json")
    assert attempt["request_id"] == request["request_id"]
    assert attempt["blocker_id"]
    assert attempt["outcome"] == "complete"
    dispatch_event = next(
        event for event in _events(result) if event["event"] == "repair_trigger_dispatch"
    )
    assert dispatch_event["repair_layer"] == "l3"
    assert attempt["argv"] == ["demo", "l3_progress_auditor"]
    managed = _read_json_eventually(Path(dispatch_event["managed_manifest_path"]))
    assert managed["run_kind"] == "automatic_root_cause_repair"
    assert managed["model"] == "gpt-5.6-sol"
    assert managed["difficulty"] == 9
    assert managed["authority"]["child_difficulty_ceiling"] == 9
    assert managed["links"]["audit_escalation_id"] == "l3-escalation-demo-m3"
    claim_path = repair_requests.active_repair_claim_lock_dir(
        _queue_root(workspace), attempt["blocker_id"]
    ) / "owner.json"
    claim = _read_json_eventually(claim_path)
    assert claim["request_id"] == request["request_id"]
    assert claim["blocker_id"] == attempt["blocker_id"]
    decisions = [
        item["decision"]
        for item in _decisions(marker_dir)
        if item["request_id"] == request["request_id"]
    ]
    assert set(decisions) == {"accepted", "dispatched"}
    custody_attempts = repair_requests.iter_repair_attempts(_queue_root(workspace))
    assert len(custody_attempts) == 1
    assert custody_attempts[0]["request_id"] == request["request_id"]
    assert custody_attempts[0]["blocker_id"] == attempt["blocker_id"]
    assert custody_attempts[0]["repair_layer"] == "l3"
    assert custody_attempts[0]["status"] == "launched"
    assert custody_attempts[0]["managed_run_id"] == dispatch_event["managed_run_id"]
    assert custody_attempts[0]["managed_manifest_path"] == dispatch_event["managed_manifest_path"]
    attempt_history = [
        json.loads(line)
        for line in (tmp_path / "repair-attempts.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(attempt_history) == 1
    assert attempt_history[0]["attempt_id"] == attempt["attempt_id"]
    assert attempt_history[0]["request_id"] == attempt["request_id"]
    assert attempt_history[0]["blocker_id"] == attempt["blocker_id"]
    assert attempt_history[0]["outcome"] == "complete"
    assert request["target"]["evidence_cursor"]["accepted_request_ids"] == ["legacy-request"]
    assert request["target"]["retry_budget"]["remaining_attempts"] == 2


def test_trigger_consumes_human_gate_request_from_explicit_central_queue(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    queued = repair_requests.enqueue_human_gate_repair_request(
        queue_root=_queue_root(workspace),
        marker_dir=workspace / ".megaplan" / "plans" / "m3",
        session="demo",
        workspace=workspace,
        run_kind="plan",
        plan_name="m3",
        pipeline_name="megaplan",
        artifact_stage="execute",
        step_name="approval",
        prompt="operator approval required",
    )
    assert queued is not None

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False)

    assert result.returncode == 0, result.stderr
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["request_id"] == queued["request"]["request_id"]
    assert observe["status"] == "blocked"
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}
    assert not (marker_dir.parent / "repair-queue").exists()


@pytest.mark.parametrize(
    ("master_enabled", "path_enabled"),
    ((False, False), (False, True), (True, False), (True, True)),
)
def test_trigger_real_wrapper_master_path_mutation_matrix(
    tmp_path: Path,
    master_enabled: bool,
    path_enabled: bool,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)
    repair_bin = _repair_stub(tmp_path)
    queue_dir = _queue_root(workspace)
    before = {
        path.relative_to(queue_dir): path.read_bytes()
        for path in queue_dir.rglob("*")
        if path.is_file()
    }

    result = _run_trigger(
        marker_dir,
        repair_bin,
        enabled=path_enabled,
        autonomy=master_enabled,
    )

    assert result.returncode == 0, result.stderr
    authorized = master_enabled and path_enabled
    if authorized:
        _read_json_eventually(tmp_path / "repair-args.json")
        effects = tmp_path / "repair-effects"
        assert {path.name for path in effects.iterdir()} == {
            "subprocess", "state", "source", "commit", "push"
        }
        assert '"status": "dispatched"' in result.stdout
        return

    after = {
        path.relative_to(queue_dir): path.read_bytes()
        for path in queue_dir.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (tmp_path / "repair-args.json").exists()
    assert not (tmp_path / "repair-effects").exists()
    assert not (queue_dir / "repair-trigger.lock").exists()
    assert '"status": "dispatched"' not in result.stdout
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["status"] == "blocked"
    assert observe["target"]["current_refs"]["remote_spec"] == str(spec)


def test_trigger_does_not_launch_when_request_claim_is_already_held(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)
    repair_bin = _repair_stub(tmp_path)
    projection = _project_request_custody(marker_dir, queued)
    blocker_id = projection["blocker_id"]
    assert blocker_id
    claim = repair_requests.claim_active_repair_request(
        _queue_root(workspace),
        blocker_id=blocker_id,
        request_id=queued["request"]["request_id"],
        actor="other-trigger",
        session="demo",
        pid=os.getpid(),
    )
    assert claim.claimed

    result = _run_trigger(marker_dir, repair_bin, enabled=True)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    claim_event = next(event for event in _events(result) if event["event"] == "repair_trigger_claim")
    assert claim_event["status"] == "already_claimed"
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}


def test_trigger_skips_actionable_head_without_blocker_id_and_dispatches_next(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(TRIGGER))
    bad = {
        "request_id": "000-bad",
        "session": "legacy-bad",
        "problem_signature_key": "legacy-bad-signature",
    }
    good = {
        "request_id": "001-good",
        "session": "workflow-boundary-contracts",
        "problem_signature_key": "workflow-boundary-signature",
    }
    records = [bad, good]
    emitted: list[dict[str, Any]] = []
    retries: list[tuple[str, str]] = []
    dispatched: list[dict[str, Any]] = []
    trigger_globals = namespace["_scan_under_lock"].__globals__

    monkeypatch.setattr(repair_requests, "iter_repair_requests", lambda *_args, **_kwargs: records)
    monkeypatch.setattr(
        repair_requests,
        "record_unclaimed_request_failure",
        lambda _queue, *, request_id, reason: (
            retries.append((request_id, reason)) or {"status": "retryable", "retry_count": 1}
        ),
    )
    trigger_globals["_terminal_request_ids"] = lambda _queue: set()
    trigger_globals["_resolve_target"] = lambda record, **_kwargs: {"target_session": record["session"]}
    trigger_globals["_classify_request"] = lambda record, _target, **_kwargs: {
        "decision": "actionable",
        "reason": "dead runner",
        "dispatch_decision": "dispatch_l1_repair",
        "dispatch_intent": "dispatch_l1",
        "custody_bucket": "repairable_not_repairing",
        "blocker_id": "" if record["request_id"] == "000-bad" else "blocker-good",
        "blocker_fingerprint": {},
    }
    trigger_globals["_emit"] = lambda payload: emitted.append(dict(payload))
    trigger_globals["_dispatch"] = lambda **kwargs: dispatched.append(dict(kwargs["request"])) or 0

    result = namespace["_scan_under_lock"](
        marker_dir=tmp_path / "markers",
        queue_dir=tmp_path / ".megaplan" / "repair-queue",
        repair_data_dir=None,
        repair_bin=tmp_path / "repair",
        meta_repair_bin=tmp_path / "meta-repair",
        enabled=True,
        authorized=True,
    )

    assert result == 0
    assert retries == [("000-bad", "canonical blocker_id missing")]
    assert dispatched[0]["request_id"] == "001-good"
    assert any(
        event.get("event") == "repair_trigger_claim"
        and event.get("request_id") == "000-bad"
        and event.get("status") == "missing_blocker_id"
        for event in emitted
    )


def test_classify_request_binds_identity_to_exact_request_among_legacy_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = runpy.run_path(str(TRIGGER))
    classify = namespace["_classify_request"]
    trigger_globals = classify.__globals__
    captured: list[dict[str, Any]] = []
    current_request_id = "current-gate-request"
    legacy_request_id = "legacy-identity-free-request"
    fingerprint = {
        "schema_version": "arnold-repair-blocker-fingerprint-v2",
        "target_fingerprint": "target-fingerprint",
        "failure_kind": "phase_failed",
        "phase_or_step": "gate",
        "blocked_task_id": "phase:gate",
    }
    projection = {
        "requests": [
            {
                "request_id": legacy_request_id,
                "active": True,
                "claimable": False,
                "blocker_id": "",
                "blocker_fingerprint": None,
            },
            {
                "request_id": current_request_id,
                "active": True,
                "claimable": True,
                "blocker_id": "blocker:v2:current",
                "blocker_fingerprint": fingerprint,
            },
        ],
        "active_request_ids": [legacy_request_id, current_request_id],
        "claimable_request_ids": [current_request_id],
        "accepted_unclaimed_request_ids": [legacy_request_id, current_request_id],
        # The session-wide projection is intentionally ambiguous.
        "blocker_id": "",
        "blocker_fingerprint": None,
        "custody_bucket": "repairable_not_repairing",
        "terminal_outcomes": [],
    }

    monkeypatch.setitem(trigger_globals, "resolve_run_state", lambda _target: None)
    monkeypatch.setitem(
        trigger_globals,
        "project_repair_custody",
        lambda **_kwargs: projection,
    )

    def fake_dispatch(**kwargs: Any) -> SimpleNamespace:
        custody = dict(kwargs["custody_projection"])
        captured.append(custody)
        actionable = bool(custody.get("blocker_id"))
        return SimpleNamespace(
            decision="dispatch_l1_repair" if actionable else "broken_superfixer",
            rationale=("exact request custody",),
            dispatch_intent="dispatch_l1" if actionable else "broken_superfixer",
            custody_bucket="repairable_not_repairing",
        )

    monkeypatch.setitem(trigger_globals, "classify_repair_dispatch", fake_dispatch)
    monkeypatch.setitem(
        trigger_globals,
        "inspect_repair_lock",
        lambda _path: {"status": "free"},
    )
    queue_dir = tmp_path / ".megaplan" / "repair-queue"
    target = {
        "target_session": "demo",
        "authoritative_source": "chain_state",
        "current_refs": {
            "current_plan_name": "m6-plan",
            "plan_current_state": "gated",
            "workspace": str(tmp_path),
        },
        "plan_state": {
            "name": "m6-plan",
            "current_state": "gated",
            "resume_cursor": {"retry_strategy": "repair_phase_contract"},
        },
        "needs_human": {"present": False},
    }

    current = classify(
        {
            "request_id": current_request_id,
            "session": "demo",
            "problem_signature": {
                "failure_kind": "phase_failed",
                "current_state": "critiqued",
                "phase_or_step": "gate",
                "milestone_or_plan": "m6-plan",
                "blocked_task_id": "phase:gate",
            },
        },
        target,
        queue_dir=queue_dir,
        marker_dir=tmp_path / "markers",
        repair_data_dir=None,
    )
    legacy = classify(
        {
            "request_id": legacy_request_id,
            "session": "demo",
            "problem_signature": {
                "failure_kind": "phase_failed",
                "current_state": "planned",
                "phase_or_step": "critique",
                "milestone_or_plan": "m6-plan",
                "blocked_task_id": "",
            },
        },
        target,
        queue_dir=queue_dir,
        marker_dir=tmp_path / "markers",
        repair_data_dir=None,
    )

    assert current["decision"] == "actionable"
    assert current["blocker_id"] == "blocker:v2:current"
    assert current["blocker_fingerprint"] == fingerprint
    assert captured[0]["active_request_ids"] == [current_request_id]
    assert captured[0]["claimable_request_ids"] == [current_request_id]
    assert captured[0]["accepted_unclaimed_request_ids"] == [current_request_id]
    assert legacy["decision"] == "non_actionable"
    assert legacy["blocker_id"] == ""
    assert captured[1]["active_request_ids"] == [legacy_request_id]
    assert captured[1]["claimable_request_ids"] == []


def test_trigger_keeps_accepted_request_visible_until_dispatchable(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False)

    assert result.returncode == 0, result.stderr
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["request_id"] == queued["request"]["request_id"]
    assert observe["dispatch_intent"] == "dispatch_l1"
    blocked = next(event for event in _events(result) if event["event"] == "repair_trigger")
    assert blocked["reason"] == (
        "L1 mutation requires ARNOLD_AUTONOMY and ARNOLD_REPAIR_TRIGGER_ENABLED"
    )
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}


def test_trigger_routes_typed_supervisor_binding_drift_to_l2(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace, plan_name="m6-plan")
    _write_chain_state_for_spec(workspace, spec, current_plan_name="m6-plan")
    queued = repair_requests.enqueue_repair_request(
        queue_root=_queue_root(workspace),
        marker_dir=marker_dir,
        session="demo",
        source="arnold_supervise_exit",
        workspace=workspace,
        run_kind="chain",
        target={
            "plan_name": "m6-plan",
            "remote_spec": str(spec),
            "workspace": str(workspace),
        },
        problem_signature={
            "failure_kind": "chain_execution_binding_drift",
            "current_state": "process_exited",
            "phase_or_step": "chain_execution_binding",
            "milestone_or_plan": "m6-plan",
            "gate_recommendation": (
                "Explicit operator-authorized content-addressed rebind is required."
            ),
            "blocked_task_id": (
                "chain_execution_binding:editable_runtime_import_root_mismatch"
            ),
            "event_signature": (
                "chain_execution_binding_drift;"
                "active_errors=editable_runtime_import_root_mismatch"
            ),
        },
        root_cause_hint="typed binding drift",
    )
    repair_bin = _repair_stub(tmp_path)
    meta_repair_bin = tmp_path / "meta-repair-loop"
    meta_log = tmp_path / "meta-repair-args.json"
    meta_repair_bin.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        f"Path({str(meta_log)!r}).write_text(json.dumps({{'argv': sys.argv[1:], 'request_id': os.environ.get('CLOUD_WATCHDOG_REPAIR_REQUEST_ID', '')}}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    meta_repair_bin.chmod(meta_repair_bin.stat().st_mode | stat.S_IXUSR)

    result = _run_trigger(
        marker_dir,
        repair_bin,
        enabled=True,
        env_overrides={"ARNOLD_META_REPAIR_ENABLED": "1"},
        meta_repair_bin=meta_repair_bin,
    )

    assert result.returncode == 0, result.stderr
    observe = next(
        event for event in _events(result) if event["event"] == "repair_trigger_observe"
    )
    assert observe["dispatch_decision"] == "broken_superfixer"
    assert observe["dispatch_intent"] == "broken_superfixer"
    dispatch = next(
        event for event in _events(result) if event["event"] == "repair_trigger_dispatch"
    )
    assert dispatch["repair_layer"] == "l2"
    assert dispatch["request_id"] == queued["request"]["request_id"]
    launched = _read_json_eventually(meta_log)
    assert launched["argv"] == ["demo", "l1_custody_failure"]
    assert launched["request_id"] == queued["request"]["request_id"]
    assert not (tmp_path / "repair-args.json").exists()


def test_trigger_loads_hot_env_for_systemd_latency_path(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)
    repair_bin = _repair_stub(tmp_path)
    hot_env = tmp_path / "cloud-hot-env"
    hot_env.write_text(
        "ARNOLD_AUTONOMY=1\nARNOLD_REPAIR_TRIGGER_ENABLED=1\n",
        encoding="utf-8",
    )

    result = _run_trigger(
        marker_dir,
        repair_bin,
        enabled=False,
        env_overrides={"ARNOLD_CLOUD_HOT_ENV": str(hot_env)},
    )

    assert result.returncode == 0, result.stderr
    assert "repair_trigger_dispatch" in result.stdout
    payload = _read_json_eventually(tmp_path / "repair-args.json")
    assert payload["argv"] == ["demo", str(workspace), str(spec)]
    assert payload["request_id"] == queued["request"]["request_id"]
    assert payload["claim_owner_pid"].isdigit()


def test_trigger_coalesces_pending_duplicate_files_under_lock(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    first = _enqueue(marker_dir, workspace)
    queue_dir = _queue_root(workspace)
    first_path = Path(first["path"])
    duplicate = json.loads(first_path.read_text(encoding="utf-8"))
    duplicate["request_id"] = "duplicate-request"
    duplicate["created_at"] = "2026-07-01T00:01:00Z"
    repair_requests.requests_dir(queue_dir).joinpath("duplicate-request.json").write_text(
        json.dumps(duplicate, sort_keys=True),
        encoding="utf-8",
    )

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True)

    assert result.returncode == 0, result.stderr
    coalesced = [item for item in _decisions(marker_dir) if item["decision"] == "coalesced"]
    assert any(item["request_id"] == "duplicate-request" for item in coalesced)


def test_trigger_prefers_typed_actionable_l3_evidence_over_earlier_duplicate(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    first = _enqueue(marker_dir, workspace)
    queue_dir = _queue_root(workspace)
    first_path = Path(first["path"])
    upgraded = json.loads(first_path.read_text(encoding="utf-8"))
    upgraded["request_id"] = "typed-l3-upgrade"
    upgraded["created_at"] = "2026-07-01T00:01:00Z"
    upgraded["source"] = "six_hour_auditor"
    upgraded["target"] = {
        **dict(upgraded.get("target") or {}),
        "deterministic_superfixer_evidence": {"actionable": True},
    }
    repair_requests.requests_dir(queue_dir).joinpath("typed-l3-upgrade.json").write_text(
        json.dumps(upgraded, sort_keys=True),
        encoding="utf-8",
    )

    result = _run_trigger(
        marker_dir,
        _repair_stub(tmp_path),
        enabled=False,
        autonomy=False,
    )

    assert result.returncode == 0, result.stderr
    observations = [
        item for item in _events(result) if item["event"] == "repair_trigger_observe"
    ]
    assert observations[0]["request_id"] == "typed-l3-upgrade"
    duplicate = next(item for item in observations if item.get("observation") == "duplicate_signature")
    assert duplicate["request_id"] == first["request"]["request_id"]
    assert duplicate["related_request_id"] == "typed-l3-upgrade"


def test_trigger_rejects_stale_marker_plan_reference(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    import hashlib

    digest = hashlib.sha1(str(spec.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"chain-{digest}.json").write_text(
        json.dumps({"current_plan_name": "m4", "last_state": "blocked"}),
        encoding="utf-8",
    )

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    stale = [item for item in _decisions(marker_dir) if item["decision"] == "stale"]
    assert len(stale) == 1
    assert "stale_marker_plan_ref" in stale[0]["reason"]


def test_trigger_terminalizes_request_after_chain_advances_to_new_plan(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    marker_path = marker_dir / "demo.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["plan_name"] = "m4"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    _write_chain_state_for_spec(workspace, spec, current_plan_name="m4")

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    stale = [
        item
        for item in _decisions(marker_dir)
        if item["decision"] == "stale"
        and item["request_id"] == queued["request"]["request_id"]
    ]
    assert len(stale) == 1
    assert "target advanced from m3 to m4" in stale[0]["reason"]


def test_trigger_rejects_superseded_request_for_live_sibling(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace, session="demo")
    _write_marker(marker_dir, workspace, session="live-sibling")
    _enqueue(marker_dir, workspace, session="demo")
    fake_tmux = tmp_path / "tmux"
    fake_tmux.write_text(
        """#!/usr/bin/env python3
import sys
raise SystemExit(0 if sys.argv[-1] == "live-sibling" else 1)
""",
        encoding="utf-8",
    )
    fake_tmux.chmod(fake_tmux.stat().st_mode | stat.S_IXUSR)

    result = _run_trigger(
        marker_dir,
        _repair_stub(tmp_path),
        enabled=True,
        env_overrides={"PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"},
    )

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    superseded = [item for item in _decisions(marker_dir) if item["decision"] == "superseded"]
    assert len(superseded) == 1
    assert superseded[0]["related_request_id"] == "live-sibling"
    assert "live sibling session" in superseded[0]["reason"]


def test_trigger_skips_terminal_requests_and_reports_no_actionable(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    queue_dir = _queue_root(workspace)
    repair_requests.write_decision(
        queue_dir,
        request_id=queued["request"]["request_id"],
        decision="stale",
        reason="already handled elsewhere",
        created_at="2026-07-01T00:02:00Z",
    )

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    events = _events(result)
    assert any(event["status"] == "no_actionable_requests" for event in events if event["event"] == "repair_trigger")


def test_trigger_exits_cleanly_when_lock_is_busy(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    lock_dir = tmp_path / "trigger.lock"
    owner = acquire_repair_lock(lock_dir, session="other-trigger", pid=os.getpid())
    assert owner.acquired
    try:
        result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True, lock_dir=lock_dir)
    finally:
        release_repair_lock(lock_dir, owner=owner.owner)

    assert result.returncode == 0, result.stderr
    assert '"status": "busy"' in result.stdout
    assert not (tmp_path / "repair-args.json").exists()
