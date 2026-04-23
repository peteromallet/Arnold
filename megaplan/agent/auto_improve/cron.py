"""Automated hourly check-in for auto-improve iterations.

Runs all health checks, fixes problems, exports data, and reports.

Usage:
    python -m auto_improve.cron              # dry run (report only)
    python -m auto_improve.cron --fix        # fix problems automatically
    python -m auto_improve.cron --fix --push # fix + push to GitHub
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from auto_improve.probe_keys import KeyStatus, alive_keys, probe_all_keys

# The iteration this cron is monitoring. The suffix can be purely numeric
# ("021") or contain a qualifier ("022-robust", "023-baseline", etc.).
# Directory is always `results/auto-improve/iteration-<ITERATION>`.
ITERATION = "021"
# Full directory-name form expected by `auto_improve.score._normalize_iteration_name`,
# which accepts either a pure-digit id ("021") or an already-prefixed name
# ("iteration-022-robust"). We normalize to the prefixed form so both styles
# work on any scorer invocation.
ITERATION_FULL = ITERATION if ITERATION.startswith("iteration-") else f"iteration-{ITERATION}"
ITER_DIR = Path(f"results/auto-improve/iteration-{ITERATION}")
SCORES_PATH = ITER_DIR / "_watch_scores.json"
MANIFEST_PATH = ITER_DIR / "_task_manifest.json"
PREDS_DIR = ITER_DIR / "_swebench_predictions"
WORKER_LOGS = ITER_DIR / "_worker_logs"
STATE_PATH = ITER_DIR / "_cron_state.json"


# ---------------------------------------------------------------------------
# State file — persists between cron runs for deltas, throughput, stall detection
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    """Load persistent state from previous cron run."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    """Atomically save state file."""
    _atomic_json_write(STATE_PATH, state)


def _atomic_json_write(path: Path, data: dict) -> None:
    """Write JSON atomically via temp file + rename."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run_key_probe_cached(max_age_s: int = 300) -> list[KeyStatus]:
    state = _load_state()
    cached = state.get("key_probe")
    if isinstance(cached, dict):
        try:
            age_s = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["timestamp"])).total_seconds()
            if age_s < max_age_s:
                return [KeyStatus(**result) for result in cached.get("results", [])]
        except Exception:
            pass
    try:
        results = probe_all_keys()
    except Exception as exc:
        print(f"WARNING: key probe failed: {exc}")
        return []
    state["key_probe"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": [asdict(result) for result in results],
    }
    _save_state(state)
    return results


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

def _pgrep(pattern: str) -> list[int]:
    """Find PIDs matching pattern, excluding our own process."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        ).stdout.strip()
        my_pid = os.getpid()
        return [int(p) for p in out.split("\n") if p.strip() and int(p) != my_pid]
    except Exception:
        return []


def check_scores() -> dict:
    """Check current scores and prediction counts."""
    if not SCORES_PATH.exists():
        return {"passed": 0, "failed": 0, "scored": 0, "preds": 0, "unscored": 0}
    try:
        s = json.loads(SCORES_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {"passed": 0, "failed": 0, "scored": 0, "preds": 0, "unscored": 0, "error": "scores file corrupt"}
    passed = sum(1 for t in s["tasks"].values() if t.get("resolved") is True)
    failed = sum(1 for t in s["tasks"].values() if t.get("resolved") is False)
    preds = len(list(PREDS_DIR.glob("*.jsonl"))) if PREDS_DIR.exists() else 0
    scored = passed + failed
    # Only count successful scores (resolved=True/False), not error attempts (resolved=None)
    times = [t.get("scored_at", "") for t in s["tasks"].values() if t.get("scored_at") and t.get("resolved") is not None]
    last_score = max(times) if times else ""
    return {
        "passed": passed,
        "failed": failed,
        "scored": scored,
        "preds": preds,
        "unscored": preds - scored,
        "pass_rate": round(passed * 100 / scored) if scored else 0,
        "last_score": last_score,
    }


def _pid_alive(pid: int) -> bool:
    """Return True if the PID is alive (uses kill -0)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except Exception:
        return False


def _read_iteration_pidfile() -> dict:
    """Read the iteration's pidfile, returning {} on any failure."""
    pidfile = ITER_DIR / "_pidfile.json"
    if not pidfile.exists():
        return {}
    try:
        return json.loads(pidfile.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def check_processes() -> dict:
    """Check which processes are alive — scoped to THIS iteration via the pidfile.

    Uses `_pidfile.json` (written by evals/parallel.py and auto_improve/score.py)
    instead of pgrep, so the count is accurate even when multiple iterations
    are running side-by-side. Dashboard has no pidfile entry, so it still uses
    pgrep — the dashboard is a single global process per host.
    """
    pf = _read_iteration_pidfile()
    worker_pids = [w.get("pid") for w in pf.get("workers", []) if isinstance(w, dict)]
    workers_alive = sum(1 for pid in worker_pids if pid and _pid_alive(pid))
    scorer_pid = pf.get("scorer_pid")
    scorer_alive = 1 if (scorer_pid and _pid_alive(scorer_pid)) else 0
    return {
        "workers": workers_alive,
        "scorers": scorer_alive,
        "dashboard": len(_pgrep("dashboard_web")),
    }


def _modal_apps_active() -> bool:
    """Check if there are active (non-stopped) Modal scoring apps."""
    try:
        out = subprocess.run(
            ["modal", "app", "list", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return False
        apps = json.loads(out.stdout)
        return any(
            a.get("State", "").lower() in ("running", "ephemeral")
            and "swebench" in a.get("Description", "").lower()
            and a.get("Tasks", 0) > 0
            for a in apps
        )
    except Exception:
        return False


def check_scorer_stuck(scores: dict, fix: bool = False) -> str | None:
    """Check if scorer is alive but not making progress."""
    if scores["unscored"] <= 3:
        return None
    last = scores.get("last_score", "")
    if not last:
        issue = "Scorer has never scored but predictions exist"
    else:
        try:
            dt = datetime.fromisoformat(last)
            age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
            if age_min < 30:
                return None
            issue = f"Scorer stuck: {scores['unscored']} unscored, last score {int(age_min)}m ago"
        except Exception:
            issue = f"Scorer may be stuck: {scores['unscored']} unscored"

    # Don't restart if Modal is actively processing — scorer is waiting, not stuck
    if _modal_apps_active():
        return f"{issue} (but Modal is active — not restarting)"

    if fix:
        for pid in _pgrep(f"auto_improve.score.*{ITERATION}"):
            os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        subprocess.Popen(
            [sys.executable, "-m", "auto_improve.score", "--watch", "--iterations", ITERATION_FULL],
            stdout=open(f"/tmp/scorer-{ITERATION}.log", "w"),
            stderr=subprocess.STDOUT,
        )
        return f"FIXED: {issue} — restarted scorer"
    return issue


def _iter_worker_logs() -> list[tuple[int, Path]]:
    """Yield (worker_index, log_path) for every worker-*.stderr.log in the iteration."""
    if not WORKER_LOGS.exists():
        return []
    out: list[tuple[int, Path]] = []
    for log in sorted(WORKER_LOGS.glob("worker-*.stderr.log")):
        stem = log.stem.replace(".stderr", "")
        try:
            idx = int(stem.split("-")[-1])
        except ValueError:
            continue
        out.append((idx, log))
    return out


def check_worker_quota(fix: bool = False) -> list[str]:
    """Check for workers spinning on quota errors."""
    issues = []
    for w, log in _iter_worker_logs():
        try:
            tail = log.read_bytes()[-5000:].decode("utf-8", errors="replace")
            quota_hits = tail.count("Weekly") + tail.count("Monthly Limit")
            if quota_hits > 3:
                if fix:
                    for pid in _pgrep(f"worker-{w}.json"):
                        os.kill(pid, signal.SIGTERM)
                    issues.append(f"FIXED: w{w} quota spinning ({quota_hits} hits) — killed")
                else:
                    issues.append(f"w{w}: quota spinning ({quota_hits} hits)")
        except Exception:
            pass
    return issues


def check_review_bug() -> list[str]:
    """Check for the review template bug returning."""
    issues = []
    for w, log in _iter_worker_logs():
        try:
            tail = log.read_bytes()[-3000:].decode("utf-8", errors="replace")
            hits = tail.count("incomplete review coverage")
            if hits > 0:
                issues.append(f"ALERT: w{w} has {hits} recent review failures")
        except Exception:
            pass
    return issues


def check_worker_staleness() -> list[str]:
    """Check for workers that are alive but not making progress (logs not updating).

    Uses the pidfile to determine which workers are actually alive, so this
    can't false-fire on dead workers whose log files exist but process is gone.
    """
    issues = []
    now = time.time()
    pf = _read_iteration_pidfile()
    live_worker_indexes: set[int] = set()
    for entry in pf.get("workers", []):
        if not isinstance(entry, dict):
            continue
        pid = entry.get("pid")
        worker_id = entry.get("worker_id", "")
        if not pid or not _pid_alive(pid):
            continue
        try:
            idx = int(worker_id.split("-")[-1])
            live_worker_indexes.add(idx)
        except ValueError:
            continue

    for w, log in _iter_worker_logs():
        if w not in live_worker_indexes:
            continue
        try:
            mtime = log.stat().st_mtime
            age_min = (now - mtime) / 60
            if age_min > 30:
                issues.append(f"w{w}: alive but log stale ({int(age_min)}m since last write)")
        except Exception:
            pass
    return issues


def check_limbo(fix: bool = False, prev_state: dict | None = None) -> list[str]:
    """Check for tasks stuck in non-terminal states."""
    if not MANIFEST_PATH.exists():
        return []
    try:
        m = json.loads(MANIFEST_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return ["ALERT: manifest file corrupt or unreadable"]
    s = json.loads(SCORES_PATH.read_text()) if SCORES_PATH.exists() else {"tasks": {}}
    preds = {p.stem for p in PREDS_DIR.glob("*.jsonl")} if PREDS_DIR.exists() else set()

    escalated = [tid for tid, t in m["tasks"].items() if t.get("status") == "done" and tid not in preds]
    errors = [tid for tid, t in m["tasks"].items() if t.get("status") == "error" and t.get("error_count", 0) < 5]

    issues = []
    if escalated:
        issues.append(f"{len(escalated)} escalated tasks (no patch)")
    if errors:
        issues.append(f"{len(errors)} error tasks (retriable)")

    # Requeue loop detection: check if the same task IDs keep getting requeued
    requeue_ids = set(escalated + errors)
    if prev_state and requeue_ids:
        prev_requeued = set(prev_state.get("last_requeued_ids", []))
        cycling = requeue_ids & prev_requeued
        cycle_counts = prev_state.get("requeue_cycle_counts", {})
        for tid in cycling:
            cycle_counts[tid] = cycle_counts.get(tid, 1) + 1
        # Warn about tasks that have cycled 3+ times
        chronic = {tid: n for tid, n in cycle_counts.items() if n >= 3}
        if chronic:
            issues.append(f"ALERT: {len(chronic)} tasks in requeue loop (cycled 3+ times): {', '.join(list(chronic)[:5])}")

    if fix and (escalated or errors):
        for tid in escalated + errors:
            m["tasks"][tid]["status"] = "pending"
            m["tasks"][tid]["worker_id"] = None
            m["tasks"][tid].setdefault("history", []).append(
                {"event": "requeued", "reason": "cron_limbo_requeue"}
            )
        _atomic_json_write(MANIFEST_PATH, m)
        issues = [f"FIXED: requeued {len(escalated)} escalated + {len(errors)} errored tasks"]

    return issues


def check_false_negatives() -> list[str]:
    """Check for failed tasks with patches matching golden."""
    try:
        from auto_improve.check_false_negatives import check_false_negatives
        candidates = check_false_negatives(ITERATION)
        if candidates:
            return [f"ALERT: False negative — {c['task_id']} ({c['similarity']:.0%} match to golden). Verify and resolve as PASS." for c in candidates]
    except Exception:
        pass
    return []


def check_unreviewed_infra_failures() -> list[str]:
    """Flag scoring-exhausted tasks with patches that need manual review."""
    if not SCORES_PATH.exists():
        return []
    try:
        s = json.loads(SCORES_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    preds = {p.stem for p in PREDS_DIR.glob("*.jsonl")} if PREDS_DIR.exists() else set()
    unreviewed = []
    for tid, t in s.get("tasks", {}).items():
        if not isinstance(t, dict) or t.get("resolved") is not None:
            continue
        review = t.get("review", {})
        if isinstance(review, dict) and review.get("reviewed_by") == "human":
            continue
        if tid in preds:
            unreviewed.append(tid)
    if unreviewed:
        return [f"{len(unreviewed)} scoring-exhausted tasks with patches need manual review: {', '.join(unreviewed[:5])}"]
    return []


def _expected_workers() -> int:
    """Get expected worker count from run config."""
    config_path = ITER_DIR / "_run_config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text()).get("workers", 0)
        except Exception:
            pass
    return 0


def restart_dead(procs: dict, fix: bool = False) -> list[str]:
    """Restart any dead processes."""
    issues = []
    if procs["scorers"] == 0:
        issues.append("Scorer dead")
        if fix:
            subprocess.Popen(
                [sys.executable, "-m", "auto_improve.score", "--watch", "--iterations", ITERATION_FULL],
                stdout=open(f"/tmp/scorer-{ITERATION}.log", "w"),
                stderr=subprocess.STDOUT,
            )
            issues[-1] = "FIXED: Scorer dead — restarted"

    if procs["dashboard"] == 0:
        issues.append("Dashboard dead")
        if fix:
            subprocess.Popen(
                [sys.executable, "-m", "auto_improve.dashboard_web", ITERATION, "--port", "8080"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            issues[-1] = "FIXED: Dashboard dead — restarted"

    expected = _expected_workers()
    if procs["workers"] == 0:
        # If the iteration has no pending/claimed work, the experiment is
        # complete and we must NOT respawn workers — otherwise cron spams a
        # "launch, find nothing to do, exit" loop every hour forever.
        manifest_has_work = False
        if MANIFEST_PATH.exists():
            try:
                m = json.loads(MANIFEST_PATH.read_text())
                manifest_has_work = any(
                    t.get("status") in ("pending", "claimed")
                    for t in m.get("tasks", {}).values()
                )
            except (json.JSONDecodeError, OSError):
                manifest_has_work = True  # fail-safe: if unsure, allow restart
        if not manifest_has_work:
            issues.append(f"Iteration complete — all workers exited, nothing to restart")
            return issues
        issues.append("All workers dead")
        if fix:
            pidfile = _read_iteration_pidfile()
            loop_pid = pidfile.get("loop_pid")
            if loop_pid and _pid_alive(loop_pid):
                os.kill(loop_pid, signal.SIGTERM)
                for _ in range(50):
                    if not _pid_alive(loop_pid):
                        break
                    time.sleep(0.1)
                if _pid_alive(loop_pid):
                    os.kill(loop_pid, signal.SIGKILL)
                killed_msg = f"killed orphan parent PID {loop_pid}"
            else:
                killed_msg = "no orphan parent to clean up"
            subprocess.Popen(
                [sys.executable, "-m", "evals.run_evals", "--config",
                 str(ITER_DIR / "_run_config.json"), "-v"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            issues[-1] = f"FIXED: All workers dead — restarted ({killed_msg})"
    elif expected > 0 and procs["workers"] < expected:
        issues.append(f"Only {procs['workers']}/{expected} workers alive — some workers have died")

    return issues


def check_key_capacity(procs: dict, key_probe: list[KeyStatus]) -> list[str]:
    if not key_probe:
        return []
    n_alive = sum(1 for key in key_probe if key.status == "alive")
    workers = procs.get("workers", 0)
    if n_alive < workers:
        return [
            f"Over-provisioned: {workers} workers running but only {n_alive} alive keys. "
            f"Consider killing {workers - n_alive} workers or waiting for recovery."
        ]
    if n_alive > workers and workers < _expected_workers():
        return [f"Under-provisioned: {n_alive} alive keys but only {workers} workers running. Could scale up."]
    return []


def push_to_github() -> str:
    """Export dashboard data and push."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "auto_improve.dashboard_export", ITERATION, "--push"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            return f"Dashboard export failed (rc={result.returncode}): {result.stderr[:200]}"

        result = subprocess.run(
            "git add -A auto_improve/ evals/ tests/ && git diff --cached --quiet || "
            "git commit -m 'auto: update from cron' && git push fork main",
            shell=True, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"Git push failed (rc={result.returncode}): {result.stderr[:200]}"
        return "Pushed"
    except subprocess.TimeoutExpired:
        return "Push failed: timeout"
    except Exception as e:
        return f"Push failed: {e}"


# ---------------------------------------------------------------------------
# Delta / throughput reporting
# ---------------------------------------------------------------------------

def _compute_deltas(scores: dict, prev_state: dict) -> list[str]:
    """Compare current scores to previous run and report deltas."""
    lines = []
    prev_scores = prev_state.get("scores", {})
    if not prev_scores:
        return []

    prev_ts = prev_state.get("timestamp", "")
    if prev_ts:
        try:
            dt = datetime.fromisoformat(prev_ts)
            age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
            lines.append(f"Last cron: {int(age_min)}m ago")
        except Exception:
            pass

    d_scored = scores.get("scored", 0) - prev_scores.get("scored", 0)
    d_passed = scores.get("passed", 0) - prev_scores.get("passed", 0)
    d_preds = scores.get("preds", 0) - prev_scores.get("preds", 0)

    if d_preds > 0 or d_scored > 0:
        lines.append(f"Delta: +{d_preds} preds, +{d_scored} scored (+{d_passed} passed)")
    else:
        lines.append("Delta: no progress since last run")

    # Throughput: tasks per hour
    if prev_ts and d_preds > 0:
        try:
            dt = datetime.fromisoformat(prev_ts)
            hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if hours > 0:
                rate = d_preds / hours
                lines.append(f"Throughput: {rate:.1f} tasks/hour")
        except Exception:
            pass

    return lines


def _detect_stall(scores: dict, prev_state: dict) -> str | None:
    """Detect zero progress across multiple consecutive runs."""
    prev_scores = prev_state.get("scores", {})
    if not prev_scores:
        return None

    d_preds = scores.get("preds", 0) - prev_scores.get("preds", 0)
    if d_preds > 0:
        return None

    # Count consecutive stall runs
    stall_count = prev_state.get("stall_count", 0) + 1
    if stall_count >= 2:
        return f"ALERT: Zero progress for {stall_count} consecutive cron runs — investigate workers"
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    fix = "--fix" in sys.argv
    push = "--push" in sys.argv
    now = datetime.now(timezone.utc).isoformat()

    prev_state = _load_state()
    key_probe = run_key_probe_cached()
    scores = check_scores()
    procs = check_processes()
    alive_count = len(alive_keys(key_probe))

    print(f"=== Iteration {ITERATION} — {now} ===")
    print(f"Scores: {scores['passed']}/{scores['scored']} = {scores.get('pass_rate', 0)}% | preds={scores['preds']} | unscored={scores['unscored']}")
    print(f"Processes: workers={procs['workers']}, scorers={procs['scorers']}, dashboard={procs['dashboard']}")
    print(f"Keys: {alive_count}/{len(key_probe)} alive")
    for result in key_probe:
        if result.status == "alive":
            continue
        reset_suffix = f" | reset_at={result.reset_at}" if result.reset_at else ""
        print(f"  {result.masked_key}: {result.status} | {result.detail}{reset_suffix}")

    # Deltas from previous run
    deltas = _compute_deltas(scores, prev_state)
    if deltas:
        print()
        for line in deltas:
            print(f"  {line}")
    print()

    if scores.get("error"):
        print(f"  ⚠ {scores['error']}")

    all_issues = []

    # Dead processes
    all_issues.extend(restart_dead(procs, fix))
    all_issues.extend(check_key_capacity(procs, key_probe))

    # Scorer stuck
    stuck = check_scorer_stuck(scores, fix)
    if stuck:
        all_issues.append(stuck)

    # Quota spinners
    all_issues.extend(check_worker_quota(fix))

    # Review bug
    all_issues.extend(check_review_bug())

    # Worker staleness (alive but not writing logs)
    all_issues.extend(check_worker_staleness())

    # Limbo tasks (with requeue loop detection)
    all_issues.extend(check_limbo(fix, prev_state))

    # False negatives
    all_issues.extend(check_false_negatives())

    # Scoring-exhausted tasks needing manual review
    all_issues.extend(check_unreviewed_infra_failures())

    # Stall detection (zero progress across runs)
    stall = _detect_stall(scores, prev_state)
    if stall:
        all_issues.append(stall)

    if all_issues:
        print("Issues:")
        for issue in all_issues:
            print(f"  {'✓' if issue.startswith('FIXED') else '⚠'} {issue}")
    else:
        print("No issues found.")

    # Update state for next run
    d_preds = scores.get("preds", 0) - prev_state.get("scores", {}).get("preds", 0)
    cached_state = _load_state()
    new_state = {
        "timestamp": now,
        "scores": scores,
        "procs": procs,
        "key_probe": cached_state.get("key_probe"),
        "stall_count": (prev_state.get("stall_count", 0) + 1) if d_preds == 0 else 0,
        "last_requeued_ids": [
            tid for tid, t in (json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {"tasks": {}}).get("tasks", {}).items()
            if t.get("status") in ("done", "error") and tid not in ({p.stem for p in PREDS_DIR.glob("*.jsonl")} if PREDS_DIR.exists() else set())
        ] if MANIFEST_PATH.exists() else [],
        "requeue_cycle_counts": prev_state.get("requeue_cycle_counts", {}),
    }
    _save_state(new_state)

    if push:
        print()
        result = push_to_github()
        print(result)
        if result != "Pushed":
            print("  ⚠ Push did not succeed — check credentials and remote")


if __name__ == "__main__":
    main()
