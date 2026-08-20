"""Bounded local/on-box session control for durable operator pause."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.chain.operator_pause import (
    pause_chain,
    reconcile_quiesced_plan_pause,
    resume_chain,
)
from arnold_pipelines.megaplan.cloud.relaunch_resolution import marker_relaunch_command


RESUME_HOLD_KEY = "operator_resume_hold"
RESUME_HOLD_SCHEMA = "arnold.megaplan.operator-resume-hold.v1"
_POST_LAUNCH_GRACE_SECONDS = 0.25


def _resume_hold(
    *,
    spec: Path,
    workspace: Path,
    session: str,
    resume_authority: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": RESUME_HOLD_SCHEMA,
        "active": True,
        "session": session,
        "spec": str(spec.resolve(strict=False)),
        "workspace": str(workspace.resolve(strict=False)),
        "resume_authority": resume_authority,
    }


def _runner_survives_launch(session: str) -> bool:
    probe = ["tmux", "has-session", "-t", session]
    if subprocess.run(probe, check=False).returncode != 0:
        return False
    time.sleep(_POST_LAUNCH_GRACE_SECONDS)
    return subprocess.run(probe, check=False).returncode == 0


def _stop_owned_pidfile(path: Path, *, session: str) -> bool:
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
        cmdline = (
            Path(f"/proc/{pid}/cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode(errors="replace")
        )
    except (OSError, ValueError):
        return False
    if session not in cmdline or not any(
        token in cmdline for token in ("arnold-babysitter",)
    ):
        return False
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def pause_session(
    *,
    spec: Path,
    workspace: Path,
    session: str,
    marker_path: Path,
    reason: str,
    actor: str,
) -> dict[str, Any]:
    marker, marker_sha256 = _load_marker(marker_path)
    result = pause_chain(spec, workspace, reason=reason, actor=actor)
    stopped = (
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )
    marker_dir = marker_path.parent
    repair_stopped = any(
        _stop_owned_pidfile(path, session=session)
        for path in (
            marker_dir / f"{session}.repair-loop.pid",
            marker_dir / f"{session}.meta-repair.pid",
        )
    )
    # tmux can return from kill-session while the terminated runner is
    # flushing its final in-memory state.  Give that bounded flush a chance to
    # land, then converge only the dead-owned writer race.  Arbitrary plan
    # changes remain fail-closed in reconcile_quiesced_plan_pause().
    time.sleep(_POST_LAUNCH_GRACE_SECONDS)
    plan_reconciled = reconcile_quiesced_plan_pause(
        spec,
        workspace,
        session=session,
        authority=result["authority"],
    )
    marker["operator_pause"] = result["authority"]
    marker["should_run"] = False
    _write_marker(marker_path, marker, expected_sha256=marker_sha256)
    return {
        **result,
        "session": session,
        "runner_stopped": stopped,
        "repair_stopped": repair_stopped,
        "plan_reconciled": plan_reconciled,
    }


def resume_session(
    *,
    spec: Path,
    workspace: Path,
    session: str,
    marker_path: Path,
    actor: str,
    no_push: bool = False,
    start_runner: bool = True,
) -> dict[str, Any]:
    marker, marker_sha256 = _load_marker(marker_path)
    relaunch: str | None = None
    if start_runner:
        relaunch = marker_relaunch_command(marker)
        if not relaunch:
            raise RuntimeError("session marker relaunch command is stale or unavailable")
        if (
            subprocess.run(["tmux", "has-session", "-t", session], check=False).returncode
            == 0
        ):
            raise RuntimeError("session already has a live runner")
    hold = marker.get(RESUME_HOLD_KEY)
    hold = hold if isinstance(hold, dict) else None
    if hold is not None:
        if (
            hold.get("schema_version") != RESUME_HOLD_SCHEMA
            or hold.get("active") is not True
            or hold.get("session") != session
            or hold.get("spec") != str(spec.resolve(strict=False))
            or hold.get("workspace") != str(workspace.resolve(strict=False))
            or not isinstance(hold.get("resume_authority"), dict)
        ):
            raise RuntimeError("operator resume hold is invalid or targets another session")
        result = resume_chain(
            spec,
            workspace,
            actor=actor,
            verify_execution_binding=start_runner,
            expected_resume_authority=hold["resume_authority"],
        )
    elif marker.get("should_run") is False and not isinstance(marker.get("operator_pause"), dict):
        # Compatibility for authority-cleared holds created before the typed
        # marker receipt existed.  Require the complete canonical marker
        # identity; arbitrary marker-only stops remain fail-closed.
        marker_session = marker.get("chain_session") or marker.get("session")
        if (
            marker_session != session
            or marker.get("remote_spec") != str(spec.resolve(strict=False))
            or marker.get("workspace") != str(workspace.resolve(strict=False))
            or marker.get("retired") is True
            or marker.get("superseded") is True
        ):
            raise RuntimeError("legacy authority-cleared hold lacks exact session custody")
        result = resume_chain(
            spec,
            workspace,
            actor=actor,
            verify_execution_binding=start_runner,
            allow_legacy_authority_cleared_hold=True,
        )
    else:
        result = resume_chain(
            spec,
            workspace,
            actor=actor,
            verify_execution_binding=start_runner,
        )
    if not start_runner:
        marker.pop("operator_pause", None)
        marker["should_run"] = False
        marker[RESUME_HOLD_KEY] = _resume_hold(
            spec=spec,
            workspace=workspace,
            session=session,
            resume_authority=result["resume_authority"],
        )
        _write_marker(marker_path, marker, expected_sha256=marker_sha256)
        return {
            **result,
            "session": session,
            "runner_started": False,
            "no_push": no_push,
            "authority_only": True,
        }
    assert relaunch is not None
    queue_root = Path(
        os.environ.get("ARNOLD_REPAIR_QUEUE_ROOT")
        or marker_path.parent.parent / "repair-queue"
    )
    managed_env = {
        "ARNOLD_REPAIR_QUEUE_ROOT": str(queue_root),
        "ARNOLD_REPAIR_MARKER_DIR": str(marker_path.parent),
        "ARNOLD_REPAIR_SESSION": session,
        "ARNOLD_REPAIR_RUN_KIND": str(marker.get("run_kind") or "chain"),
    }
    if no_push:
        # A no-push chain resume deliberately stays on the current milestone
        # checkout. In chain.run_chain this disables PR branch preparation,
        # whose cleanup step otherwise resets tracked and untracked WIP before
        # checking out the remote milestone branch.
        managed_env["MEGAPLAN_CHAIN_NO_PUSH"] = "1"
    tmux_command = ["tmux", "new-session", "-d", "-s", session, "-c", str(workspace)]
    for key, value in managed_env.items():
        tmux_command.extend(["-e", f"{key}={value}"])
    tmux_command.append(relaunch)
    # Publish the final launch-authorizing marker before dispatch.  Runtime
    # attestation binds the marker's stable launch identity, while this CAS
    # prevents a concurrent pause/rebind from being overwritten.
    marker.pop("operator_pause", None)
    marker.pop(RESUME_HOLD_KEY, None)
    marker["should_run"] = True
    launched_marker_sha256 = _write_marker(
        marker_path,
        marker,
        expected_sha256=marker_sha256,
    )
    try:
        subprocess.run(tmux_command, check=True)
        alive = _runner_survives_launch(session)
        if not alive:
            raise RuntimeError("session runner exited before post-launch liveness confirmation")
    except Exception:
        # Restore a resumable stopped marker.  CAS prevents this failure path
        # from overwriting a concurrent pause, rebind, or successful relaunch.
        stopped, stopped_sha256 = _load_marker(marker_path)
        if stopped_sha256 != launched_marker_sha256:
            raise RuntimeError(
                "session marker changed concurrently after launch dispatch; "
                "refusing to restore stale stop authority"
            )
        stopped["should_run"] = False
        stopped[RESUME_HOLD_KEY] = _resume_hold(
            spec=spec,
            workspace=workspace,
            session=session,
            resume_authority=result["resume_authority"],
        )
        _write_marker(marker_path, stopped, expected_sha256=stopped_sha256)
        raise
    return {
        **result,
        "session": session,
        "runner_started": True,
        "no_push": no_push,
    }


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_marker(path: Path) -> tuple[dict[str, Any], str]:
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"session marker is unreadable or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("session marker must be a JSON object")
    return value, _sha256(encoded)


def _write_marker(
    path: Path,
    value: dict[str, Any],
    *,
    expected_sha256: str,
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".runtime-cutover.lock")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            current = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"session marker disappeared during update: {path}"
            ) from exc
        observed_sha256 = _sha256(current)
        if observed_sha256 != expected_sha256:
            raise RuntimeError(
                "session marker changed concurrently: "
                f"expected {expected_sha256}, observed {observed_sha256}"
            )
        encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return _sha256(encoded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pause", "resume"))
    parser.add_argument("--spec", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--reason", default="operator requested pause")
    parser.add_argument("--actor", default="operator")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "resume with MEGAPLAN_CHAIN_NO_PUSH=1 so an existing dirty "
            "milestone checkout is not reset for PR branch preparation"
        ),
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="clear durable pause authority without starting the chain runner",
    )
    args = parser.parse_args(argv)
    common = {
        "spec": Path(args.spec),
        "workspace": Path(args.workspace),
        "session": args.session,
        "marker_path": Path(args.marker),
        "actor": args.actor,
    }
    payload = (
        pause_session(**common, reason=args.reason)
        if args.action == "pause"
        else resume_session(
            **common,
            no_push=args.no_push,
            start_runner=not args.no_start,
        )
    )
    print(json.dumps({"success": True, **payload}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
