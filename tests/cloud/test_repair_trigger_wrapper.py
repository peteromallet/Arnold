from __future__ import annotations

import json
import os
import hashlib
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


def _patched_dispatch_env(tmp_path: Path, *, mode: str) -> tuple[dict[str, str], Path]:
    patch_dir = tmp_path / f"py-patches-{mode}"
    patch_dir.mkdir()
    capture_path = tmp_path / f"dispatch-capture-{mode}.json"
    (patch_dir / "sitecustomize.py").write_text(
        """
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan.cloud import repair_contract as _repair_contract
from arnold_pipelines.megaplan.run_state import resolver as _resolver

capture_path = Path(os.environ["ARNOLD_TEST_CAPTURE"])
mode = os.environ["ARNOLD_TEST_MODE"]


def _target_summary(target):
    refs = target.get("current_refs") if isinstance(target.get("current_refs"), dict) else {}
    plan = target.get("plan_state") if isinstance(target.get("plan_state"), dict) else {}
    return {
        "authoritative_source": str(target.get("authoritative_source") or ""),
        "target_session": str(target.get("target_session") or ""),
        "workspace": str(refs.get("workspace") or ""),
        "current_plan_name": str(refs.get("current_plan_name") or ""),
        "plan_name": str(plan.get("name") or ""),
        "plan_present": bool(plan.get("present")),
    }


def _lock_summary(lock_evidence):
    if lock_evidence is None:
        return None
    owner = getattr(lock_evidence, "owner", None)
    owner = owner if isinstance(owner, dict) else {}
    lock_dir = getattr(lock_evidence, "lock_dir", None)
    return {
        "status": getattr(lock_evidence, "status", None),
        "lock_dir": str(lock_dir) if lock_dir is not None else "",
        "owner_session": str(owner.get("session") or ""),
    }


calls = {}
sentinel = SimpleNamespace(
    kind="sentinel",
    canonical_state=SimpleNamespace(name="RUNNING"),
    reason="patched",
    human_required=False,
    human_gate=None,
    stale_sources=(),
)


def _write_capture():
    capture_path.write_text(json.dumps(calls, sort_keys=True), encoding="utf-8")


def _resolve_run_state(evidence):
    calls["resolve_input"] = _target_summary(evidence if isinstance(evidence, dict) else {})
    if mode == "raise":
        calls["resolve_raised"] = True
        _write_capture()
        raise RuntimeError("resolver boom")
    calls["resolve_raised"] = False
    _write_capture()
    return sentinel


def _project_repair_custody(*, plan_state, current_target, canonical_run_state=None, marker_dir=None, repair_data_dir=None, **_kwargs):
    calls["project"] = {
        "canonical_kind": getattr(canonical_run_state, "kind", None),
        "target": _target_summary(current_target if isinstance(current_target, dict) else {}),
        "marker_dir": str(marker_dir) if marker_dir is not None else "",
    }
    _write_capture()
    return {"blocker_id": "bid-1", "blocker_fingerprint": {}, "active_request_ids": ["req-1"]}


def _classify_repair_dispatch(*, canonical_run_state=None, event_plan_dir=None, current_target=None, custody_projection=None, **_kwargs):
    lock_evidence = _kwargs.get("lock_evidence")
    lock_summary = _lock_summary(lock_evidence)
    lock_status = lock_summary["status"] if isinstance(lock_summary, dict) else ""
    if canonical_run_state is None:
        decision = "broken_superfixer"
        dispatch_intent = "broken_superfixer"
    elif lock_status in {"acquired", "busy", "claimed", "already_claimed"}:
        decision = "repairing"
        dispatch_intent = "queue_only"
    else:
        decision = "dispatch_l1_repair"
        dispatch_intent = "dispatch_l1"
    calls["dispatch"] = {
        "canonical_kind": getattr(canonical_run_state, "kind", None),
        "decision": decision,
        "event_plan_dir": str(event_plan_dir) if event_plan_dir is not None else "",
        "target": _target_summary(current_target if isinstance(current_target, dict) else {}),
        "active_request_ids": list((custody_projection or {}).get("active_request_ids") or []),
        "lock_evidence": lock_summary,
    }
    _write_capture()
    return SimpleNamespace(
        decision=decision,
        dispatch_intent=dispatch_intent,
        custody_bucket=(
            "human_required"
            if canonical_run_state is None
            else "repairing"
            if lock_status in {"acquired", "busy", "claimed", "already_claimed"}
            else "repairable_not_repairing"
        ),
        rationale=("patched",) if canonical_run_state is not None else ("canonical provenance missing",),
        blocker_id="bid-1",
        request_id="req-1",
    )


_resolver.resolve_run_state = _resolve_run_state
_repair_contract.project_repair_custody = _project_repair_custody
_repair_contract.classify_repair_dispatch = _classify_repair_dispatch
""",
        encoding="utf-8",
    )
    env = {
        "ARNOLD_TEST_CAPTURE": str(capture_path),
        "ARNOLD_TEST_MODE": mode,
        "PYTHONPATH": f"{patch_dir}{os.pathsep}{REPO_ROOT}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
    }
    return env, capture_path


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
    if not target_plan.get("present") and current_plan_name:
        target_plan["present"] = True
    remote_spec = Path(str(current_refs.get("remote_spec") or ""))
    if remote_spec.exists() and not target_plan.get("fingerprint"):
        target_plan["fingerprint"] = "sha256:" + hashlib.sha256(remote_spec.read_bytes()).hexdigest()
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
    assert "would_dispatch" in result.stdout
    assert not (tmp_path / "repair-args.json").exists()
    assert "dispatched" not in {item["decision"] for item in _decisions(marker_dir)}
    assert str(spec) in result.stdout
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["dispatch_decision"] == "broken_superfixer"
    assert observe["custody_bucket"] == "repairable_not_repairing"


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
    assert observe["dispatch_decision"] == "broken_superfixer"


def test_trigger_dispatches_existing_repair_loop_when_enabled(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    repair_bin = _repair_stub(tmp_path)
    env_overrides, _capture_path = _patched_dispatch_env(tmp_path, mode="capture")

    result = _run_trigger(marker_dir, repair_bin, enabled=True, env_overrides=env_overrides)

    assert result.returncode == 0, result.stderr
    assert "repair_trigger_dispatch" in result.stdout
    dispatched = [item for item in _decisions(marker_dir) if item["decision"] == "dispatched"]
    assert len(dispatched) == 1
    payload = _read_json_eventually(tmp_path / "repair-args.json")
    assert payload["argv"] == ["demo", str(workspace), str(spec)]
    assert payload["request_id"] == queued["request"]["request_id"]


def test_trigger_passes_canonical_provenance_into_custody_and_dispatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)

    env_overrides, capture_path = _patched_dispatch_env(tmp_path, mode="capture")
    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False, env_overrides=env_overrides)

    assert result.returncode == 0, result.stderr
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")

    assert capture["resolve_input"] == {
        "authoritative_source": "marker",
        "target_session": "demo",
        "workspace": str(workspace),
        "current_plan_name": "m3",
        "plan_name": "m3",
        "plan_present": True,
    }
    assert capture["project"]["canonical_kind"] == "sentinel"
    assert capture["project"]["target"] == capture["resolve_input"]
    assert capture["dispatch"]["canonical_kind"] == "sentinel"
    assert capture["dispatch"]["target"] == capture["resolve_input"]
    assert capture["dispatch"]["event_plan_dir"] == str(workspace / ".megaplan" / "plans" / "m3")
    assert capture["dispatch"]["lock_evidence"]["status"] == "missing"
    assert observe["dispatch_decision"] == "dispatch_l1_repair"


def test_trigger_resolver_exception_fails_closed_without_legacy_dispatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    _enqueue(marker_dir, workspace)
    env_overrides, capture_path = _patched_dispatch_env(tmp_path, mode="raise")
    result = _run_trigger(
        marker_dir,
        _repair_stub(tmp_path),
        enabled=True,
        env_overrides=env_overrides,
    )

    assert result.returncode == 0, result.stderr
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert capture["dispatch"]["canonical_kind"] is None
    assert observe["dispatch_decision"] == "broken_superfixer"
    assert observe["dispatch_intent"] == "broken_superfixer"
    assert not (tmp_path / "repair-args.json").exists()
    assert "repair_trigger_dispatch" not in result.stdout
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}


def test_trigger_does_not_launch_when_request_claim_is_already_held(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    repair_bin = _repair_stub(tmp_path)
    claim = repair_requests.claim_active_repair_request(
        repair_requests.repair_queue_dir(marker_dir),
        blocker_id="bid-1",
        request_id=queued["request"]["request_id"],
        actor="other-trigger",
        session="demo",
        pid=os.getpid(),
    )
    assert claim.claimed
    env_overrides, _capture_path = _patched_dispatch_env(tmp_path, mode="capture")

    result = _run_trigger(marker_dir, repair_bin, enabled=True, env_overrides=env_overrides)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "repair-args.json").exists()
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    terminal = next(event for event in _events(result) if event["event"] == "repair_trigger")
    assert observe["request_id"] == queued["request"]["request_id"]
    assert observe["dispatch_decision"] == "repairing"
    assert observe["dispatch_intent"] == "queue_only"
    assert terminal["status"] == "no_actionable_requests"
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}


def test_trigger_keeps_accepted_request_visible_until_dispatchable(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    env_overrides, _capture_path = _patched_dispatch_env(tmp_path, mode="capture")

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=False, env_overrides=env_overrides)

    assert result.returncode == 0, result.stderr
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    assert observe["request_id"] == queued["request"]["request_id"]
    assert observe["dispatch_intent"] == "dispatch_l1"
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}


def test_trigger_passes_busy_lock_evidence_and_suppresses_duplicate_dispatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    queue_dir = repair_requests.repair_queue_dir(marker_dir)
    claim = repair_requests.claim_active_repair_request(
        queue_dir,
        blocker_id="bid-1",
        request_id="req-existing",
        actor="fixture",
        session="other-session",
        pid=os.getpid(),
    )
    assert claim.claimed
    owner_path = claim.lock_dir / "owner.json"
    owner_before = owner_path.read_text(encoding="utf-8")
    env_overrides, capture_path = _patched_dispatch_env(tmp_path, mode="capture")

    result = _run_trigger(marker_dir, _repair_stub(tmp_path), enabled=True, env_overrides=env_overrides)

    assert result.returncode == 0, result.stderr
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    observe = next(event for event in _events(result) if event["event"] == "repair_trigger_observe")
    terminal = next(event for event in _events(result) if event["event"] == "repair_trigger")
    assert capture["dispatch"]["lock_evidence"] == {
        "status": "busy",
        "lock_dir": str(repair_requests.active_repair_claim_lock_dir(queue_dir, "bid-1")),
        "owner_session": "other-session",
    }
    assert owner_path.read_text(encoding="utf-8") == owner_before
    assert observe["dispatch_decision"] == "repairing"
    assert observe["dispatch_intent"] == "queue_only"
    assert observe["custody_bucket"] == "repairing"
    assert terminal["status"] == "no_actionable_requests"
    assert not (tmp_path / "repair-args.json").exists()
    assert {item["decision"] for item in _decisions(marker_dir)} == {"accepted"}
    assert observe["request_id"] == queued["request"]["request_id"]


def test_trigger_loads_hot_env_for_systemd_latency_path(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace"
    spec = _write_marker(marker_dir, workspace)
    queued = _enqueue(marker_dir, workspace)
    repair_bin = _repair_stub(tmp_path)
    hot_env = tmp_path / "cloud-hot-env"
    hot_env.write_text("ARNOLD_REPAIR_TRIGGER_ENABLED=1\n", encoding="utf-8")
    env_overrides, _capture_path = _patched_dispatch_env(tmp_path, mode="capture")
    env_overrides["ARNOLD_CLOUD_HOT_ENV"] = str(hot_env)

    result = _run_trigger(
        marker_dir,
        repair_bin,
        enabled=False,
        env_overrides=env_overrides,
    )

    assert result.returncode == 0, result.stderr
    assert "repair_trigger_dispatch" in result.stdout
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
