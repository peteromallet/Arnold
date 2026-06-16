#!/usr/bin/env python3
"""End-to-end simulation of the live watchdog repair + relaunch + recheck flow.

This script creates a synthetic blocked plan, runs the watchdog against it with a
fake megaplan CLI, and verifies the watchdog:

  1. Detects the blocked plan
  2. Assesses issue difficulty and selects a repair model
  3. Executes the repair (auto/resume)
  4. Relaunches the plan
  5. Waits and rechecks
  6. Confirms the plan is now running
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_fake_megaplan_cli(bin_dir: Path) -> Path:
    """Create a fake ``megaplan`` CLI that simulates repairs in the test repo."""
    script = bin_dir / "megaplan"
    script.write_text(
        """#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Discover project dir from env or cwd.
project_dir = os.environ.get("MEGAPLAN_PROJECT_DIR", os.getcwd())
plan_dir = os.environ.get("MEGAPLAN_PLAN_DIR", project_dir)
state_path = Path(plan_dir) / "state.json"
lock_path = Path(plan_dir) / ".plan.lock"
events_path = Path(plan_dir) / "events.ndjson"

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def read_state():
    try:
        return json.loads(state_path.read_text())
    except Exception:
        return {}

def write_state(state):
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

def append_event(kind, payload=None):
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a") as f:
        f.write(json.dumps({
            "kind": kind,
            "payload": payload or {},
            "ts_utc": now_utc(),
        }) + "\\n")

cmd = sys.argv[1] if len(sys.argv) > 1 else ""

if cmd == "doctor":
    print(f"[fake megaplan doctor] plan_dir={plan_dir} state={read_state().get('current_state')}")
    sys.exit(0)

if cmd == "watchdog-worker":
    plan_dir = sys.argv[2] if len(sys.argv) > 2 else plan_dir
    # Keep this process alive so the watchdog sees a live megaplan-correlated
    # worker for the plan. Detach I/O so the repair runner returns promptly.
    with open(os.devnull, "w") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())
    while True:
        time.sleep(600)

if cmd in ("auto", "resume"):
    state = read_state()
    # Remove stale lock if present.
    if lock_path.exists():
        lock_path.unlink()
        print(f"[fake megaplan {cmd}] removed stale lock")
    # Mark plan as executing.
    state["current_state"] = "executing"
    state["active_step"] = {
        "phase": "execute",
        "agent": "hermes",
        "mode": "persistent",
        "run_id": "sim-run-001",
        "worker_pid": 0,
        "started_at": now_utc(),
    }
    write_state(state)
    append_event("phase_start", {"phase": "execute"})
    # Start a fake worker process so the next watchdog scan sees a live process.
    # Re-exec this same CLI so the worker is categorized as megaplan and can be
    # correlated to the plan. Detach I/O so the repair runner returns promptly.
    worker = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "watchdog-worker", str(plan_dir)],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    state["active_step"]["worker_pid"] = worker.pid
    write_state(state)
    append_event("worker_started", {"worker_pid": worker.pid})
    print(f"[fake megaplan {cmd}] relaunched plan, worker_pid={worker.pid}")
    sys.exit(0)

if cmd == "chain":
    print("[fake megaplan chain] noop")
    sys.exit(0)

print(f"[fake megaplan] unknown command: {cmd}")
sys.exit(1)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _setup_blocked_plan(repo_dir: Path) -> Path:
    """Create a plan directory that looks blocked with a stale lock."""
    from datetime import datetime, timezone

    plan_dir = repo_dir / ".megaplan" / "plans" / "sim-blocked-plan"
    plan_dir.mkdir(parents=True)

    state = {
        "name": "sim-blocked-plan",
        "current_state": "blocked",
        "block_details": {"is_blocked": True, "recoverable_via": ["auto", "resume"]},
    }
    _write_json(plan_dir / "state.json", state)

    # Stale lock older than 300s threshold.
    lock_path = plan_dir / ".plan.lock"
    lock_path.write_text("", encoding="utf-8")
    old = time.time() - 600
    os.utime(lock_path, (old, old))

    # Recent activity so the plan is classified as a live PLAN_ISSUE rather than
    # DEAD_OR_DISAPPEARED.
    now = datetime.now(timezone.utc).isoformat()
    events = [
        {"kind": "phase_start", "payload": {"phase": "execute"}, "ts_utc": now},
        {"kind": "step_started", "payload": {"step": "agent_turn"}, "ts_utc": now},
    ]
    (plan_dir / "events.ndjson").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8"
    )

    return plan_dir


def _run_watchdog(args: list[str], env: dict[str, str]) -> dict[str, object]:
    """Run the watchdog CLI and return the combined report."""
    result = subprocess.run(
        [sys.executable, "-B", str(REPO_ROOT / "scripts" / "megaplan_live_watchdog.py"), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise RuntimeError(f"watchdog failed with rc={result.returncode}")
    # The report path is the last argument after --report-path or --report-path=.
    report_arg = next(a for a in args if a.startswith("--report-path"))
    if "=" in report_arg:
        report_path = Path(report_arg.split("=", 1)[1])
    else:
        report_path = Path(args[args.index("--report-path") + 1])
    return json.loads(report_path.read_text())


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        repo_dir = tmp / "sim-repo"
        bin_dir = tmp / "bin"
        bin_dir.mkdir()

        fake_cli = _make_fake_megaplan_cli(bin_dir)
        plan_dir = _setup_blocked_plan(repo_dir)

        registry_path = tmp / "registry.ndjson"
        report_path = tmp / "report.json"
        log_path = tmp / "watchdog.log"

        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"

        print("=== Setup ===")
        print(f"repo_dir={repo_dir}")
        print(f"plan_dir={plan_dir}")
        print(f"fake_cli={fake_cli}")

        print("\n=== Running watchdog (repair + 10s recheck) ===")
        report = _run_watchdog(
            [
                "--once",
                f"--roots={repo_dir}",
                f"--registry-path={registry_path}",
                f"--report-path={report_path}",
                f"--log-path={log_path}",
                "--repair-runner=subprocess",
                "--recheck-after-seconds=10",
                "--lookback-hours=0",
            ],
            env,
        )

        print(f"\n=== Report iterations: {len(report['reports'])} ===")
        for idx, r in enumerate(report["reports"], start=1):
            print(f"\n--- Iteration {idx} ---")
            print(f"plans_found: {r['plans_found']}")
            print(f"currently_running: {r.get('currently_running', [])}")
            print(f"problem_incidents: {len(r['problem_incidents'])}")
            print(f"cleanup_candidates: {len(r['cleanup_candidates'])}")
            print(f"transitions: {len(r['transitions'])}")
            for t in r["transitions"]:
                print(
                    f"  {t['plan_id']}: {t['previous_status']} -> {t['current_status']} "
                    f"(state: {t['previous_state']} -> {t['current_state']})"
                )
            for p in r["problem_incidents"]:
                decision = p.get("decision", {})
                ctx = decision.get("verdict", {}).get("action", {}).get("context", {})
                print(
                    f"  repair for {p['plan_id']}: "
                    f"difficulty={ctx.get('difficulty')}, model={ctx.get('model')}, "
                    f"cmd={decision.get('recommended_command')}, allowed={decision.get('verdict', {}).get('allowed')}"
                )
            for rr in r.get("repair_results", []):
                print(f"  repair result: {rr['plan_id']} -> {rr['final_outcome']} ({rr['attempt_count']} attempts)")
                for a in rr.get("attempts", []):
                    print(f"    attempt: {a.get('command')} -> {a.get('status')}")

        print("\n=== Final state ===")
        final_state = json.loads((plan_dir / "state.json").read_text())
        print(json.dumps(final_state, indent=2))

        print("\n=== Verification ===")
        final_running = report.get("final_currently_running", [])
        rc = 0 if "sim-blocked-plan" in final_running else 1
        if rc == 0:
            print("PASS: sim-blocked-plan is running after repair + recheck")
        else:
            print("FAIL: sim-blocked-plan is NOT in final_currently_running")

        # Best-effort cleanup of the detached fake worker so we do not leave
        # orphaned processes behind after the temp directory is removed.
        final_state = json.loads((plan_dir / "state.json").read_text())
        worker_pid = final_state.get("active_step", {}).get("worker_pid")
        if worker_pid:
            try:
                os.kill(worker_pid, 9)
                print(f"cleaned up worker pid={worker_pid}")
            except ProcessLookupError:
                pass
        return rc


if __name__ == "__main__":
    sys.exit(main())
