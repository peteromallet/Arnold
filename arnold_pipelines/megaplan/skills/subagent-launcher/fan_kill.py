#!/usr/bin/env python3
"""Send SIGTERM (default) or SIGKILL (`--hard`) to a running ``fan.py``.

Reads ``<output-dir>/_fan.pid`` and signals the parent. With ``--hard`` it
sends SIGKILL to the parent and also walks any per-task ``<stem>.pid`` files
(processes-mode children) to make sure stuck tasks die. With the default
SIGTERM it waits up to 30s for the parent's pidfile to disappear (clean
shutdown) before giving up.

Usage:
    PYENV_VERSION=3.11.11 python fan_kill.py --output-dir=/tmp/results
    PYENV_VERSION=3.11.11 python fan_kill.py --output-dir=/tmp/results --hard
"""

from __future__ import annotations

import argparse
import errno
import os
import signal
import sys
import time
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


def _signal(pid: int, sig: int) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return False
    except OSError as exc:
        print(f"fan_kill: kill({pid}, {sig}) failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--output-dir", required=True, help="fan.py --output-dir target")
    ap.add_argument("--hard", action="store_true", help="SIGKILL instead of SIGTERM")
    ap.add_argument("--timeout", type=float, default=30.0, help="wait seconds (SIGTERM only)")
    args = ap.parse_args()

    out_dir = Path(args.output_dir).expanduser().resolve()
    pidfile = out_dir / "_fan.pid"
    if not pidfile.exists():
        print(f"fan_kill: no pidfile at {pidfile}", file=sys.stderr)
        return 2

    try:
        parent_pid = int(pidfile.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        print(f"fan_kill: could not read pidfile: {exc}", file=sys.stderr)
        return 2

    if not _pid_alive(parent_pid):
        print(f"fan_kill: parent PID {parent_pid} not alive; cleaning stale pidfile")
        try:
            pidfile.unlink()
        except OSError:
            pass
        return 0

    sig = signal.SIGKILL if args.hard else signal.SIGTERM
    print(f"fan_kill: sending {'SIGKILL' if args.hard else 'SIGTERM'} to parent PID {parent_pid}")
    _signal(parent_pid, sig)

    if args.hard:
        # Also reap per-task children (processes mode). Best effort.
        for child_pidfile in out_dir.glob("*.pid"):
            if child_pidfile.name == "_fan.pid":
                continue
            try:
                cpid = int(child_pidfile.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
            if _pid_alive(cpid):
                print(f"fan_kill: SIGKILL child PID {cpid} ({child_pidfile.name})")
                _signal(cpid, signal.SIGKILL)
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
