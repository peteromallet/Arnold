"""Terminate auto-improve loop, worker, and scorer processes."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from evals.parallel import _clear_pidfile_runtime_state, _load_pidfile, _set_pidfile_scorer_pid


DEFAULT_RESULTS_BASE = Path("results") / "auto-improve"
KILL_WAIT_SECONDS = 3


def _normalize_iteration_name(value: str) -> str:
    text = value.strip()
    if text.startswith("iteration-"):
        return text
    if text.isdigit():
        return f"iteration-{int(text):03d}"
    raise ValueError(f"Invalid iteration identifier: {value!r}")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pgid_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_pid(pid: int, sig: signal.Signals) -> None:
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _signal_pgid(pgid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _scan_ps_candidates(iteration_dir: Path) -> list[tuple[int, str]]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    matches: list[tuple[int, str]] = []
    markers = (iteration_dir.name, str(iteration_dir))
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            pid_text, command = stripped.split(None, 1)
        except ValueError:
            continue
        if not any(marker in command for marker in markers):
            continue
        if not any(token in command for token in ("auto_improve.loop", "auto_improve.score", "evals.run_evals")):
            continue
        try:
            matches.append((int(pid_text), command))
        except ValueError:
            continue
    return matches


def _iteration_dir(base_dir: Path, iteration_name: str) -> Path:
    return base_dir / iteration_name


def _collect_iteration_dirs(base_dir: Path, args: argparse.Namespace) -> list[Path]:
    if args.all:
        return sorted(path for path in base_dir.glob("iteration-*") if path.is_dir())
    return [_iteration_dir(base_dir, _normalize_iteration_name(args.iteration))]


def _kill_from_pidfile(iteration_dir: Path, *, dry_run: bool) -> tuple[bool, int | None]:
    pidfile = iteration_dir / "_pidfile.json"
    payload = _load_pidfile(pidfile, iteration=iteration_dir.name)
    loop_pid = payload.get("loop_pid")
    scorer_pid = payload.get("scorer_pid")
    workers = payload.get("workers", [])
    killed_scorer_pid: int | None = None
    saw_targets = False

    if isinstance(loop_pid, int) and _pid_alive(loop_pid):
        saw_targets = True
        print(f"[{iteration_dir.name}] loop pid={loop_pid} via os.kill()", file=sys.stderr)
        if not dry_run:
            _signal_pid(loop_pid, signal.SIGTERM)
    for worker in workers:
        pgid = worker.get("pgid")
        worker_id = worker.get("worker_id", "worker")
        if not isinstance(pgid, int) or not _pgid_alive(pgid):
            continue
        saw_targets = True
        print(f"[{iteration_dir.name}] worker {worker_id} pgid={pgid} via os.killpg()", file=sys.stderr)
        if not dry_run:
            _signal_pgid(pgid, signal.SIGTERM)
    if isinstance(scorer_pid, int) and _pid_alive(scorer_pid):
        saw_targets = True
        killed_scorer_pid = scorer_pid
        print(
            f"[{iteration_dir.name}] scorer pid={scorer_pid} via os.kill() "
            "(warning: this scorer may be shared with other iterations)",
            file=sys.stderr,
        )
        if not dry_run:
            _signal_pid(scorer_pid, signal.SIGTERM)

    if not dry_run and saw_targets:
        time.sleep(KILL_WAIT_SECONDS)
        if isinstance(loop_pid, int) and _pid_alive(loop_pid):
            _signal_pid(loop_pid, signal.SIGKILL)
        for worker in workers:
            pgid = worker.get("pgid")
            if isinstance(pgid, int) and _pgid_alive(pgid):
                _signal_pgid(pgid, signal.SIGKILL)
        if isinstance(scorer_pid, int) and _pid_alive(scorer_pid):
            _signal_pid(scorer_pid, signal.SIGKILL)
        _clear_pidfile_runtime_state(iteration_dir, clear_scorer=killed_scorer_pid is not None)

    return saw_targets, killed_scorer_pid


def _kill_from_ps_scan(iteration_dir: Path, *, dry_run: bool) -> bool:
    matches = _scan_ps_candidates(iteration_dir)
    if not matches:
        print(f"[{iteration_dir.name}] no pidfile and no matching ps candidates found", file=sys.stderr)
        return False

    print(
        f"[{iteration_dir.name}] warning: pidfile missing, falling back to imprecise ps scan",
        file=sys.stderr,
    )
    for pid, command in matches:
        print(f"[{iteration_dir.name}] fallback pid={pid} command={command}", file=sys.stderr)
        if not dry_run and _pid_alive(pid):
            _signal_pid(pid, signal.SIGTERM)
    if not dry_run:
        time.sleep(KILL_WAIT_SECONDS)
        for pid, _ in matches:
            if _pid_alive(pid):
                _signal_pid(pid, signal.SIGKILL)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terminate auto-improve loop, worker, and scorer processes.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--iteration", help="Iteration to stop, such as 021 or iteration-021.")
    target.add_argument("--all", action="store_true", help="Stop every iteration with a pidfile under results/auto-improve.")
    parser.add_argument("--base-dir", default=DEFAULT_RESULTS_BASE.as_posix(), help="Base directory containing iteration-* result directories.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be killed without sending any signals.")
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir).expanduser().resolve()
    iteration_dirs = _collect_iteration_dirs(base_dir, args)
    killed_any = False
    killed_scorer_pids: set[int] = set()

    for iteration_dir in iteration_dirs:
        pidfile = iteration_dir / "_pidfile.json"
        if pidfile.exists():
            saw_targets, killed_scorer_pid = _kill_from_pidfile(iteration_dir, dry_run=args.dry_run)
            killed_any = killed_any or saw_targets
            if killed_scorer_pid is not None and not args.dry_run:
                killed_scorer_pids.add(killed_scorer_pid)
            continue
        killed_any = _kill_from_ps_scan(iteration_dir, dry_run=args.dry_run) or killed_any

    if not args.dry_run and killed_scorer_pids:
        for iteration_dir in iteration_dirs:
            pidfile = iteration_dir / "_pidfile.json"
            if not pidfile.exists():
                continue
            payload = _load_pidfile(pidfile, iteration=iteration_dir.name)
            if payload.get("scorer_pid") in killed_scorer_pids:
                _set_pidfile_scorer_pid(iteration_dir, None)

    if not killed_any:
        print("No live loop, worker, or scorer processes found.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
