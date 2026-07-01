from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_lock import acquire_repair_lock, release_repair_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGER = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-repair-trigger"


def _signature(**overrides: str) -> dict[str, str]:
    base = {
        "failure_kind": "execute_failed",
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


def _repair_stub(tmp_path: Path) -> Path:
    stub = tmp_path / "repair-loop"
    log = tmp_path / "repair-args.json"
    stub.write_text(
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
Path({str(log)!r}).write_text(json.dumps({{"argv": sys.argv[1:], "request_id": os.environ.get("CLOUD_WATCHDOG_REPAIR_REQUEST_ID", "")}}), encoding="utf-8")
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
    if enabled:
        env["ARNOLD_REPAIR_TRIGGER_ENABLED"] = "1"
    else:
        env.pop("ARNOLD_REPAIR_TRIGGER_ENABLED", None)
    if env_overrides:
        env.update(env_overrides)
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


def test_trigger_observes_without_dispatch_when_disabled(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    repair_bin = _repair_stub(tmp_path)

    result = _run_trigger(marker_dir, repair_bin, enabled=False)

    assert result.returncode == 0, result.stderr
    assert "would_dispatch" in result.stdout
    assert not (tmp_path / "repair-args.json").exists()
    assert "dispatched" not in {item["decision"] for item in _decisions(marker_dir)}
    assert str(spec) in result.stdout


def test_trigger_reports_current_target_resolution_evidence(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    import hashlib

    digest = hashlib.sha1(str(spec.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"chain-{digest}.json").write_text(
        json.dumps({"current_plan_name": "m3", "last_state": "blocked"}),
        encoding="utf-8",
    )

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False)

    assert result.returncode == 0, result.stderr
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["status"] == "would_dispatch"
    assert observe["target"]["authoritative_source"] == "chain_state"
    assert observe["target"]["target_session"] == "demo"
    assert observe["target"]["current_refs"]["remote_spec"] == str(spec)


def test_trigger_dispatches_existing_repair_loop_when_enabled(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    repair_bin = _repair_stub(tmp_path)

    result = _run_trigger(marker_dir, repair_bin, enabled=True)

    assert result.returncode == 0, result.stderr
    assert "repair_trigger_dispatch" in result.stdout
    dispatched = [item for item in _decisions(marker_dir) if item["decision"] == "dispatched"]
    assert len(dispatched) == 1
    payload = _read_json_eventually(tmp_path / "repair-args.json")
    assert payload["argv"] == ["demo", str(workspace), str(spec)]
    assert payload["request_id"] == queued["request"]["request_id"]


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
