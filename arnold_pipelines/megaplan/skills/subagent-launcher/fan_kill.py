#!/usr/bin/env python3
"""Send SIGTERM (default) or SIGKILL (`--hard`) to a running ``fan.py``.

Reads ``<output-dir>/_fan.pid`` and signals the parent. With ``--hard`` it
sends SIGKILL to the parent and also walks any per-task ``<stem>.pid`` files
(processes-mode children) to make sure stuck tasks die. With the default
SIGTERM it waits up to 30s for the parent's pidfile to disappear (clean
shutdown) before giving up.

Usage:
    python fan_kill.py --output-dir=/tmp/results --workspace=/workspace \
        --ledger-root=/workspace/.megaplan/incident-ledger \
        --marker=/workspace/.megaplan/cloud-sessions/demo.json --session=demo
    python fan_kill.py --output-dir=/tmp/results --hard --workspace=/workspace \
        --ledger-root=/workspace/.megaplan/incident-ledger \
        --marker=/workspace/.megaplan/cloud-sessions/demo.json --session=demo
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any



def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, RuntimeError):
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


def _process_start_identity(pid: int) -> str:
    """Return the canonical, unprefixed process incarnation token."""
    from arnold_pipelines.megaplan.watchdog.worker_identity import read_process_start_identity
    return str(read_process_start_identity(pid) or "")


def _read_cmdline(pid: int) -> str:
    return (
        Path(f"/proc/{pid}/cmdline")
        .read_bytes()
        .replace(b"\0", b" ")
        .decode(errors="replace")
    )


def _target_snapshot(
    pidfile: Path,
    *,
    expected_pid: int | None = None,
    expected_group: int | None = None,
    expected_start: str | None = None,
    expected_cmdline: str | None = None,
) -> tuple[int, int, str, str]:
    """Read all identity fields used by the final ledger-locked preflight."""
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
        cmdline = _read_cmdline(pid)
        group = os.getpgid(pid)
    except (OSError, ProcessLookupError, ValueError) as exc:
        raise ValueError("fan target pidfile/process identity is unavailable") from exc
    if expected_pid is not None and pid != expected_pid:
        raise ValueError("fan target pidfile PID changed")
    if not cmdline or "fan.py" not in cmdline:
        raise ValueError("fan target command line is not owned by fan.py")
    if expected_group is not None and group != expected_group:
        raise ValueError("fan target process group changed")
    start = _process_start_identity(pid)
    if not start:
        raise ValueError("fan target process start identity is unavailable")
    if expected_start is not None and start != expected_start:
        raise ValueError("fan target process incarnation changed")
    if expected_cmdline is not None and cmdline != expected_cmdline:
        raise ValueError("fan target command line changed")
    return pid, group, start, cmdline


def _resolve_authority(
    *,
    marker: Path,
    marker_dir: Path,
    session: str,
    pid: int,
    start: str,
):
    from arnold_pipelines.megaplan.incident.authority import resolve_signal_authority

    return resolve_signal_authority(
        site_id="fan-kill",
        session=session,
        marker_path=marker,
        target_kind="non_worker",
        victim_pid=pid,
        victim_process_start_identity=start,
        marker_dir=marker_dir,
    )


def _signal(
    pid: int,
    sig: int,
    *,
    ledger: Any = None,
    lifecycle_identity: str = "fan-kill",
    preflight: Any = None,
    evidence: dict[str, Any] | None = None,
) -> bool:
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[4])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from arnold_pipelines.megaplan.incident.disposition import signal_process
        if ledger is not None:
            from datetime import datetime, timezone
            from arnold_pipelines.megaplan.incident.disposition import signal_non_worker
            from arnold_pipelines.megaplan.incident.schema import NonWorkerSignalDisposition
            label = signal.Signals(sig).name
            start = _process_start_identity(pid)
            if not start:
                return False
            disposition = NonWorkerSignalDisposition(
                disposition_id=hashlib.sha256(
                    json.dumps([lifecycle_identity, pid, start, label], separators=(",", ":")).encode()
                ).hexdigest(),
                subject="non_worker_lifecycle",
                lifecycle_identity=lifecycle_identity,
                killer_identity=f"fan-kill:{os.getpid()}",
                cause_kind="lifecycle_shutdown",
                signal=label,
                victim_pid_or_group=str(pid),
                victim_process_start_identity=start,
                observed_at=datetime.now(timezone.utc).isoformat(),
                evidence={"source": "fan_kill", "pidfile_owned": True, **(evidence or {})},
            )
            signal_non_worker(
                ledger, disposition,
                signal_fn=lambda: signal_process(pid, sig),
                preflight=preflight,
            )
            return True
        # This private adapter is only authorized when the caller supplies the
        # ledger-bound lifecycle context.  Never retain the old PID-only door.
        return False
    except ProcessLookupError:
        return False
    except OSError as exc:
        print(f"fan_kill: kill({pid}, {sig}) failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--output-dir", required=True, help="fan.py --output-dir target")
    ap.add_argument("--workspace", help="canonical workspace root bound by the marker")
    ap.add_argument("--ledger-root", help="canonical workspace/.megaplan/incident-ledger")
    ap.add_argument("--marker", help="canonical session marker JSON")
    ap.add_argument("--session", help="marker-bound session identifier")
    ap.add_argument("--hard", action="store_true", help="SIGKILL instead of SIGTERM")
    ap.add_argument("--timeout", type=float, default=30.0, help="wait seconds (SIGTERM only)")
    args = ap.parse_args()

    if not all((args.workspace, args.ledger_root, args.marker, args.session)):
        print(
            "fan_kill: refusing signal; explicit workspace, ledger-root, marker, "
            "and session authority are required",
            file=sys.stderr,
        )
        return 78

    out_dir = Path(args.output_dir).expanduser().resolve()
    workspace = Path(args.workspace).expanduser().resolve()
    ledger_root = Path(args.ledger_root).expanduser().resolve()
    marker_path = Path(args.marker).expanduser().resolve()
    expected_ledger_root = workspace / ".megaplan" / "incident-ledger"
    if (
        not workspace.is_dir()
        or not out_dir.is_relative_to(workspace)
        or ledger_root != expected_ledger_root
        or not ledger_root.is_dir()
        or not marker_path.is_file()
    ):
        print("fan_kill: refusing signal; authority paths are not canonical", file=sys.stderr)
        return 78
    pidfile = out_dir / "_fan.pid"
    if not pidfile.exists():
        print(f"fan_kill: no pidfile at {pidfile}", file=sys.stderr)
        return 2

    try:
        parent_pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        print(f"fan_kill: could not read pidfile: {exc}", file=sys.stderr)
        return 2

    try:
        initial_pid, initial_group, initial_start, initial_cmdline = _target_snapshot(
            pidfile, expected_pid=parent_pid
        )
        authority = _resolve_authority(
            marker=marker_path,
            marker_dir=marker_path.parent,
            session=args.session,
            pid=initial_pid,
            start=initial_start,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"fan_kill: refusing signal; authority validation failed: {exc}", file=sys.stderr)
        return 78

    if not _pid_alive(parent_pid):
        print(f"fan_kill: parent PID {parent_pid} not alive; cleaning stale pidfile")
        try:
            pidfile.unlink()
        except OSError:
            pass
        return 0

    sig = signal.SIGKILL if args.hard else signal.SIGTERM
    # fan_kill controls only pidfiles created by fan.py.  Persist a typed
    # lifecycle disposition before every such signal; it is never a worker
    # disposition and cannot impersonate an admitted receipt.
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    cleanup_ledger = IncidentLedger(workspace)
    lifecycle_identity = f"fan-kill:{out_dir}"

    def final_preflight(_records: list[dict[str, Any]]) -> None:
        try:
            current = _target_snapshot(
                pidfile,
                expected_pid=initial_pid,
                expected_group=initial_group,
                expected_start=initial_start,
                expected_cmdline=initial_cmdline,
            )
            if current[2] != authority.victim_process_start_identity:
                raise ValueError("marker target incarnation changed")
            # The marker digest is checked by the authority resolver at
            # admission; retain a byte-for-byte digest fence for the final
            # door while the ledger lock is held.
            import hashlib as _hashlib
            if _hashlib.sha256(marker_path.read_bytes()).hexdigest() != authority.marker_sha256:
                raise ValueError("marker changed before signal")
        except (OSError, ValueError, RuntimeError) as exc:
            from arnold_pipelines.megaplan.incident.disposition import SignalDispositionError
            raise SignalDispositionError(str(exc)) from exc

    print(f"fan_kill: sending {'SIGKILL' if args.hard else 'SIGTERM'} to parent PID {parent_pid}")
    if not _signal(
        parent_pid,
        sig,
        ledger=cleanup_ledger,
        lifecycle_identity=lifecycle_identity,
        preflight=final_preflight,
        evidence={"workspace": str(workspace), "marker": str(marker_path), "session": args.session},
    ):
        return 78

    if args.hard:
        # Child pidfiles have no canonical per-child marker in fan.py.  Never
        # fall back to PID-only cleanup; an explicit child authority is needed.
        for child_pidfile in out_dir.glob("*.pid"):
            if child_pidfile.name == "_fan.pid":
                continue
            try:
                cpid = int(child_pidfile.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            if _pid_alive(cpid):
                print(
                    f"fan_kill: refusing child PID {cpid} ({child_pidfile.name}); "
                    "no explicit child authority marker",
                    file=sys.stderr,
                )
        # Hard kill: don't wait — parent might be unkillable in some states.
        return 0

    # Graceful: wait for the pidfile to disappear (parent cleans it in finally).
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        if not pidfile.exists():
            print(f"fan_kill: parent exited cleanly")
            return 0
        if not _pid_alive(parent_pid):
            print(f"fan_kill: parent PID {parent_pid} gone; pidfile may be stale")
            return 0
        time.sleep(0.25)

    print(
        f"fan_kill: parent PID {parent_pid} still alive after {args.timeout}s — "
        f"re-run with --hard if needed",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
