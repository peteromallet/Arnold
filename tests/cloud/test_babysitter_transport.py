"""Focused T2.4 babysitter transport honesty fixtures.

Disposable tmp_path roots and monkeypatched subprocess/PID/probe seams only.
No cloud, live chain, candidate, selector, marker, lease, or runtime mutation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.cloud.babysitter import launch
from arnold_pipelines.megaplan.cloud.babysitter.routing import resolve_babysitter_routing


def _failing_bwrap(*_args, **_kwargs):
    return SimpleNamespace(returncode=1)


def _ctx(tmp_path: Path, *, occurrence: str = "occ-1", extra: dict | None = None) -> dict:
    ctx = {
        "session": "demo-session",
        "occurrence": occurrence,
        "run_id": "run-1",
        "run_root": tmp_path / "run",
        "plan": "demo-plan",
        "run_kind": "chain",
        "workspace": str(tmp_path / "ws"),
        "remote_spec": "",
        "mode": "superfixer",
        "model": "hermes:deepseek:deepseek-v4-flash",
        "routing": resolve_babysitter_routing({}),
        "launched_at": "2026-08-21T00:00:00Z",
        "engine_root": Path(__file__).resolve().parents[2],
        "difficulty": 8,
        "investigator_sandbox": launch.SANDBOX_DANGER_FULL_ACCESS,
    }
    if extra:
        ctx.update(extra)
    ctx["run_root"].mkdir(parents=True, exist_ok=True)
    Path(ctx["workspace"]).mkdir(parents=True, exist_ok=True)
    return ctx


def _write_plan_state(workspace: Path, plan: str, payload: dict) -> Path:
    plan_dir = workspace / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    path = plan_dir / "state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_bwrap_probe_failure_selects_danger_full_access() -> None:
    assert launch.probe_bwrap_userns(run=_failing_bwrap) is False
    assert launch.investigator_sandbox_flag(run=_failing_bwrap) == "danger-full-access"
    argv = launch.investigator_exec_argv(
        sandbox=launch.investigator_sandbox_flag(run=_failing_bwrap),
        investigator_model="codex:gpt-5.6-luna",
    )
    assert argv[argv.index("--sandbox") + 1] == "danger-full-access"
    assert "read-only" not in argv


def test_pid_live_rejects_invalid_nonpositive_boolean_without_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_pid: int, _sig: int) -> None:
        raise AssertionError("os.kill must not run for invalid pids")

    monkeypatch.setattr(launch.os, "kill", boom)
    assert launch._pid_live(None) is False
    assert launch._pid_live(0) is False
    assert launch._pid_live(-3) is False
    assert launch._pid_live(True) is False
    assert launch._pid_live(False) is False
    assert launch._pid_live("12") is False


def test_pid_live_treats_permission_as_live_and_lookup_as_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_kill(pid: int, _sig: int) -> None:
        if pid == 11:
            raise PermissionError("denied")
        if pid == 12:
            raise ProcessLookupError("gone")
        if pid == 13:
            raise OSError("other")

    monkeypatch.setattr(launch.os, "kill", fake_kill)
    monkeypatch.setattr(launch.Path, "read_text", lambda self, encoding="utf-8": "1 (x) S 0")
    assert launch._pid_live(11) is True
    assert launch._pid_live(12) is False
    assert launch._pid_live(13) is False


def test_pid_live_treats_zombie_stat_as_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launch.os, "kill", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(launch.Path, "read_text", lambda self, encoding="utf-8": "99 (dead) Z 1")
    assert launch._pid_live(99) is False


def test_phantom_pid_reclaim_does_not_stand_down(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    receipt = {
        "occurrence_digest": ctx["occurrence"],
        "status": "running",
        "babysitter_pid": 4242,
        "supervisor_pid": os.getpid(),
    }
    _write_receipt(ctx["run_root"] / launch.LAUNCH_RECEIPT_NAME.format(session=ctx["session"]), receipt)
    monkeypatch.setattr(launch, "_pid_live", lambda pid: False)
    classified = launch.classify_owner_receipt(receipt)
    assert classified["active_owner"] is False
    assert classified["reclaimable"] is True
    assert classified["status"] == "failed"
    assert launch._dedup_already_running(ctx) is False


def test_live_pid_stand_down(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(tmp_path)
    live_pid = os.getpid() + 100000
    receipt = {
        "occurrence_digest": ctx["occurrence"],
        "status": "launched",
        "babysitter_pid": live_pid,
        "supervisor_pid": 1,
    }
    _write_receipt(ctx["run_root"] / launch.LAUNCH_RECEIPT_NAME.format(session=ctx["session"]), receipt)
    monkeypatch.setattr(launch, "_pid_live", lambda pid: pid == live_pid)
    classified = launch.classify_owner_receipt(receipt)
    assert classified["active_owner"] is True
    assert classified["reclaimable"] is False
    assert launch._dedup_already_running(ctx) is True


def test_supervisor_pid_does_not_override_dead_babysitter_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = {
        "status": "running",
        "babysitter_pid": 7,
        "supervisor_pid": os.getpid(),
    }
    monkeypatch.setattr(launch, "_pid_live", lambda pid: pid == os.getpid())
    classified = launch.classify_owner_receipt(receipt)
    assert classified["active_owner"] is False
    assert classified["reclaimable"] is True


def test_false_success_rc_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "ws"
    _write_plan_state(
        workspace,
        "demo-plan",
        {
            "current_state": "blocked",
            "latest_failure": {"kind": "stall_detected", "fingerprint": "fp-still"},
        },
    )
    ctx = _ctx(tmp_path, extra={"workspace": str(workspace), "plan": "demo-plan"})
    honesty = launch.evaluate_canonical_honesty(ctx)
    status, rc, reason = launch.terminal_transport_result(
        worker_rc=0,
        managed_terminal="completed",
        honesty=honesty,
    )
    assert honesty["still_blocked"] is True
    assert status == "failed"
    assert rc == 1
    assert "plan still blocked" in reason
    payload = launch._receipt_payload(ctx, status=status, returncode=rc, false_success_reason=reason)
    assert payload["status"] == "failed"
    assert payload["returncode"] != 0


def test_fingerprint_mismatch_fails_from_canonical_state(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "product.txt").write_text("before", encoding="utf-8")
    _write_plan_state(
        workspace,
        "demo-plan",
        {
            "current_state": "blocked",
            "latest_failure": {"kind": "stall_detected", "fingerprint": "fp-pre"},
        },
    )
    ctx = _ctx(
        tmp_path,
        extra={
            "workspace": str(workspace),
            "plan": "demo-plan",
            "occurrence": "fp-pre",
            "pre_failure_fingerprint": "fp-pre",
        },
    )
    pre = launch.product_tree_fingerprint(workspace)
    (workspace / "product.txt").write_text("after-mutation", encoding="utf-8")
    honesty = launch.evaluate_canonical_honesty(ctx, pre_fingerprint=pre)
    status, rc, reason = launch.terminal_transport_result(
        worker_rc=0,
        managed_terminal="completed",
        honesty=honesty,
    )
    assert honesty["fingerprint_mismatch"] is True
    assert "product_tree_fingerprint_mismatch" in reason
    assert status == "failed"
    assert rc == 1
    # Matching/unchanged failure fingerprint also fails closed from canonical state.
    (workspace / "product.txt").write_text("before", encoding="utf-8")
    unchanged = launch.evaluate_canonical_honesty(ctx, pre_fingerprint=pre)
    assert unchanged["fingerprint_mismatch"] is True
    assert "failure_fingerprint_unchanged" in unchanged["reason"]


def test_still_blocked_target_closure_refusal_ignores_rewritten_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    _write_plan_state(
        workspace,
        "demo-plan",
        {
            "current_state": "blocked",
            "latest_failure": {"kind": "stall_detected", "fingerprint": "fp-1"},
        },
    )
    ctx = _ctx(tmp_path, extra={"workspace": str(workspace), "plan": "demo-plan"})
    rewritten = launch._receipt_payload(ctx, status="completed", returncode=0)
    honesty = launch.evaluate_canonical_honesty(ctx)
    status, rc, reason = launch.terminal_transport_result(
        worker_rc=0,
        managed_terminal="completed",
        honesty=honesty,
    )
    assert rewritten["status"] == "completed"
    assert honesty["still_blocked"] is True
    assert status == "failed"
    assert rc != 0
    assert "plan still blocked" in reason


def test_launch_babysitter_writes_failed_nonzero_on_false_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    run_root = tmp_path / "run"
    goal = tmp_path / "goal.md"
    goal.write_text("prove movement", encoding="utf-8")
    _write_plan_state(
        workspace,
        "demo-plan",
        {
            "current_state": "blocked",
            "latest_failure": {"kind": "stall_detected", "fingerprint": "fp-1"},
        },
    )

    class _Spec:
        pass

    def fake_run_managed_command(spec) -> int:
        managed_id = "managed-run"
        manifest_dir = run_root / managed_id
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps({"status": "completed"}), encoding="utf-8"
        )
        return 0

    monkeypatch.setattr(launch, "probe_bwrap_userns", lambda **_kwargs: False)
    monkeypatch.setattr(launch, "_resolve_engine_root", lambda: Path(__file__).resolve().parents[2])
    monkeypatch.setattr(launch, "_dedup_already_running", lambda _ctx: False)
    monkeypatch.setattr(launch, "stable_managed_run_id", lambda *_args, **_kwargs: "managed-run")
    monkeypatch.setattr(launch, "_managed_spec", lambda *args, **kwargs: _Spec())
    monkeypatch.setattr(launch, "run_managed_command", fake_run_managed_command)
    monkeypatch.setenv("ARNOLD_BABYSITTER_SESSION", "demo-session")

    rc = launch.launch_babysitter(
        [
            "--session",
            "demo-session",
            "--workspace",
            str(workspace),
            "--plan",
            "demo-plan",
            "--occurrence",
            "fp-1",
            "--run-root",
            str(run_root),
            "--goal-file",
            str(goal),
        ]
    )
    receipt_path = run_root / launch.LAUNCH_RECEIPT_NAME.format(session="demo-session")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert rc == 1
    assert payload["status"] == "failed"
    assert payload["returncode"] == 1
    assert payload["returncode"] != 0


def test_launch_babysitter_stands_down_only_for_live_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir()
    live_pid = 55555
    _write_receipt(
        run_root / launch.LAUNCH_RECEIPT_NAME.format(session="demo-session"),
        {
            "occurrence_digest": "occ-live",
            "status": "running",
            "babysitter_pid": live_pid,
        },
    )
    monkeypatch.setattr(launch, "_pid_live", lambda pid: pid == live_pid)
    monkeypatch.setattr(
        launch,
        "run_managed_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must stand down")),
    )
    rc = launch.launch_babysitter(
        [
            "--session",
            "demo-session",
            "--occurrence",
            "occ-live",
            "--run-root",
            str(run_root),
            "--goal-file",
            str(tmp_path / "missing.md"),
        ]
    )
    assert rc == 0
