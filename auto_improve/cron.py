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
from datetime import datetime, timezone
from pathlib import Path

ITERATION = "021"
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
    times = [t.get("scored_at", "") for t in s["tasks"].values() if t.get("scored_at")]
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


def check_processes() -> dict:
    """Check which processes are alive."""
    return {
        "workers": len(_pgrep("run_evals")),
        "scorers": len(_pgrep("auto_improve.score")),
        "dashboard": len(_pgrep("dashboard_web")),
    }


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

    if fix:
        for pid in _pgrep(f"auto_improve.score.*{ITERATION}"):
            os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        subprocess.Popen(
            ["python", "-m", "auto_improve.score", "--watch", "--iterations", ITERATION],
            stdout=open(f"/tmp/scorer-{ITERATION}.log", "w"),
            stderr=subprocess.STDOUT,
        )
        return f"FIXED: {issue} — restarted scorer"
    return issue


def check_worker_quota(fix: bool = False) -> list[str]:
    """Check for workers spinning on quota errors."""
    issues = []
    for w in range(7):
        log = WORKER_LOGS / f"worker-{w}.stderr.log"
        if not log.exists():
            continue
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
    for w in range(7):
        log = WORKER_LOGS / f"worker-{w}.stderr.log"
        if not log.exists():
            continue
        try:
            tail = log.read_bytes()[-3000:].decode("utf-8", errors="replace")
            hits = tail.count("incomplete review coverage")
            if hits > 0:
                issues.append(f"ALERT: w{w} has {hits} recent review failures")
        except Exception:
            pass
    return issues


def check_worker_staleness() -> list[str]:
    """Check for workers that are alive but not making progress (logs not updating)."""
    issues = []
    now = time.time()
    for w in range(7):
        log = WORKER_LOGS / f"worker-{w}.stderr.log"
        if not log.exists():
            continue
        try:
            mtime = log.stat().st_mtime
            age_min = (now - mtime) / 60
            # If log hasn't been written to in 30 minutes but worker process exists
            if age_min > 30 and _pgrep(f"worker-{w}.json"):
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


def restart_dead(procs: dict, fix: bool = False) -> list[str]:
    """Restart any dead processes."""
    issues = []
    if procs["scorers"] == 0:
        issues.append("Scorer dead")
        if fix:
            subprocess.Popen(
                ["python", "-m", "auto_improve.score", "--watch", "--iterations", ITERATION],
                stdout=open(f"/tmp/scorer-{ITERATION}.log", "w"),
                stderr=subprocess.STDOUT,
            )
            issues[-1] = "FIXED: Scorer dead — restarted"

    if procs["dashboard"] == 0:
        issues.append("Dashboard dead")
        if fix:
            subprocess.Popen(
                ["python", "-m", "auto_improve.dashboard_web", ITERATION, "--port", "8080"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            issues[-1] = "FIXED: Dashboard dead — restarted"

    if procs["workers"] == 0:
        issues.append("All workers dead")
        if fix:
            subprocess.Popen(
                ["python", "-m", "evals.run_evals", "--config",
                 str(ITER_DIR / "_run_config.json"), "-v"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            issues[-1] = "FIXED: All workers dead — restarted"

    return issues


def push_to_github() -> str:
    """Export dashboard data and push."""
    try:
        result = subprocess.run(
            ["python", "-m", "auto_improve.dashboard_export", ITERATION, "--push"],
            capture_output=True, text=True, timeout=120,
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
    scores = check_scores()
    procs = check_processes()

    print(f"=== Iteration {ITERATION} — {now} ===")
    print(f"Scores: {scores['passed']}/{scores['scored']} = {scores.get('pass_rate', 0)}% | preds={scores['preds']} | unscored={scores['unscored']}")
    print(f"Processes: workers={procs['workers']}, scorers={procs['scorers']}, dashboard={procs['dashboard']}")

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
    new_state = {
        "timestamp": now,
        "scores": scores,
        "procs": procs,
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
