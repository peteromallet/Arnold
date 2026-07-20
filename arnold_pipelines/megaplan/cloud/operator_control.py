"""Bounded local/on-box session control for durable operator pause."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.chain.operator_pause import pause_chain, resume_chain


def _stop_owned_pidfile(path: Path, *, session: str) -> bool:
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except (OSError, ValueError):
        return False
    if session not in cmdline or not any(
        token in cmdline for token in ("arnold-repair-loop", "arnold-meta-repair-loop")
    ):
        return False
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def pause_session(
    *, spec: Path, workspace: Path, session: str, marker_path: Path, reason: str, actor: str
) -> dict[str, Any]:
    result = pause_chain(spec, workspace, reason=reason, actor=actor)
    stopped = subprocess.run(
        ["tmux", "kill-session", "-t", session], capture_output=True, text=True, check=False
    ).returncode == 0
    marker_dir = marker_path.parent
    repair_stopped = any(
        _stop_owned_pidfile(path, session=session)
        for path in (
            marker_dir / f"{session}.repair-loop.pid",
            marker_dir / f"{session}.meta-repair.pid",
        )
    )
    marker = _load_marker(marker_path)
    marker["operator_pause"] = result["authority"]
    marker["should_run"] = False
    _write_marker(marker_path, marker)
    return {**result, "session": session, "runner_stopped": stopped, "repair_stopped": repair_stopped}


def resume_session(
    *,
    spec: Path,
    workspace: Path,
    session: str,
    marker_path: Path,
    actor: str,
    no_push: bool = False,
) -> dict[str, Any]:
    result = resume_chain(spec, workspace, actor=actor)
    marker = _load_marker(marker_path)
    relaunch = str(marker.get("relaunch_command") or marker.get("launch_command") or "").strip()
    if not relaunch:
        raise RuntimeError("session marker has no canonical relaunch command")
    if subprocess.run(["tmux", "has-session", "-t", session], check=False).returncode == 0:
        raise RuntimeError("session already has a live runner")
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
    subprocess.run(
        tmux_command,
        check=True,
    )
    marker.pop("operator_pause", None)
    marker["should_run"] = True
    _write_marker(marker_path, marker)
    return {
        **result,
        "session": session,
        "runner_started": True,
        "no_push": no_push,
    }


def _load_marker(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def _write_marker(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


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
        else resume_session(**common, no_push=args.no_push)
    )
    print(json.dumps({"success": True, **payload}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
