from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud import repair_contract
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock, release_repair_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGER = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-repair-trigger"


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


def _write_marker(marker_dir: Path, workspace: Path, session: str = "demo") -> Path:
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
                "plan_name": "m3",
            }
        ),
        encoding="utf-8",
    )
    return spec


def _enqueue(marker_dir: Path, workspace: Path, session: str = "demo") -> dict[str, object]:
    return repair_requests.enqueue_repair_request(
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
    stub.write_text(
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
Path({str(log)!r}).write_text(json.dumps({{"argv": sys.argv[1:], "request_id": os.environ.get("CLOUD_WATCHDOG_REPAIR_REQUEST_ID", ""), "claim_owner_pid": os.environ.get("CLOUD_WATCHDOG_REPAIR_CLAIM_OWNER_PID", "")}}), encoding="utf-8")
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
    lock_dir: Path | None = None,
    env_overrides: dict[str, str] | None = None,
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
    cmd = [
        sys.executable,
        str(TRIGGER),
        "--marker-dir",
        str(marker_dir),
        "--repair-bin",
        str(repair_bin),
    ]
    if lock_dir is not None:
        cmd.extend(["--lock-dir", str(lock_dir)])
    return subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)


def _decisions(marker_dir: Path) -> list[dict[str, object]]:
    queue_dir = repair_requests.repair_queue_dir(marker_dir)
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
        marker_dir=marker_dir,
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
    assert observe["status"] == "would_dispatch"
    assert observe["target"]["authoritative_source"] == "chain_state"
    assert observe["target"]["target_session"] == "demo"
    assert observe["target"]["current_refs"]["remote_spec"] == str(spec)
    assert observe["dispatch_decision"] == "dispatch_l1_repair"


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
    dispatched = [item for item in _decisions(marker_dir) if item["decision"] == "dispatched"]
    assert len(dispatched) == 1
    payload = _read_json_eventually(tmp_path / "repair-args.json")
    assert payload["argv"] == ["demo", str(workspace), str(spec)]
    assert payload["request_id"] == queued["request"]["request_id"]
    assert payload["claim_owner_pid"].isdigit()


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
        repair_requests.repair_queue_dir(marker_dir),
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
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}


def test_trigger_loads_hot_env_for_systemd_latency_path(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    _write_chain_state_for_spec(workspace, spec)
    repair_bin = _repair_stub(tmp_path)
    hot_env = tmp_path / "cloud-hot-env"
    hot_env.write_text("ARNOLD_REPAIR_TRIGGER_ENABLED=1\n", encoding="utf-8")

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
    queue_dir = repair_requests.repair_queue_dir(marker_dir)
    first_path = Path(first["path"])
    duplicate = json.loads(first_path.read_text(encoding="utf-8"))
    duplicate["request_id"] = "duplicate-request"
    duplicate["created_at"] = "2026-07-01T00:01:00Z"
    repair_requests.requests_dir(queue_dir).joinpath("duplicate-request.json").write_text(
        json.dumps(duplicate, sort_keys=True),
        encoding="utf-8",
    )

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False)

    assert result.returncode == 0, result.stderr
    coalesced = [item for item in _decisions(marker_dir) if item["decision"] == "coalesced"]
    assert any(item["request_id"] == "duplicate-request" for item in coalesced)


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
    queue_dir = repair_requests.repair_queue_dir(marker_dir)
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
