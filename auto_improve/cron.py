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
import time
from datetime import datetime, timezone
from pathlib import Path

ITERATION = "021"
ITER_DIR = Path(f"results/auto-improve/iteration-{ITERATION}")
SCORES_PATH = ITER_DIR / "_watch_scores.json"
MANIFEST_PATH = ITER_DIR / "_task_manifest.json"
PREDS_DIR = ITER_DIR / "_swebench_predictions"
WORKER_LOGS = ITER_DIR / "_worker_logs"


def _pgrep(pattern: str) -> list[int]:
    """Find PIDs matching pattern."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        ).stdout.strip()
        return [int(p) for p in out.split("\n") if p.strip()]
    except Exception:
        return []


def check_scores() -> dict:
    """Check current scores and prediction counts."""
    if not SCORES_PATH.exists():
        return {"passed": 0, "failed": 0, "scored": 0, "preds": 0, "unscored": 0}
    s = json.loads(SCORES_PATH.read_text())
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
        for pid in _pgrep("auto_improve.score.*021"):
            os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        subprocess.Popen(
            ["python", "-m", "auto_improve.score", "--watch", "--iterations", ITERATION],
            stdout=open("/tmp/scorer-021.log", "w"),
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
                    # Find and kill this worker
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


def check_limbo(fix: bool = False) -> list[str]:
    """Check for tasks stuck in non-terminal states."""
    if not MANIFEST_PATH.exists():
        return []
    m = json.loads(MANIFEST_PATH.read_text())
    s = json.loads(SCORES_PATH.read_text()) if SCORES_PATH.exists() else {"tasks": {}}
    preds = {p.stem for p in PREDS_DIR.glob("*.jsonl")} if PREDS_DIR.exists() else set()

    escalated = [tid for tid, t in m["tasks"].items() if t.get("status") == "done" and tid not in preds]
    errors = [tid for tid, t in m["tasks"].items() if t.get("status") == "error" and t.get("error_count", 0) < 5]

    issues = []
    if escalated:
        issues.append(f"{len(escalated)} escalated tasks (no patch)")
    if errors:
        issues.append(f"{len(errors)} error tasks (retriable)")

    if fix and (escalated or errors):
        for tid in escalated + errors:
            m["tasks"][tid]["status"] = "pending"
            m["tasks"][tid]["worker_id"] = None
            m["tasks"][tid].setdefault("history", []).append(
                {"event": "requeued", "reason": "cron_limbo_requeue"}
            )
        json.dump(m, open(MANIFEST_PATH, "w"), indent=2)
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
                stdout=open("/tmp/scorer-021.log", "w"),
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
        # Push code
        subprocess.run(
            "git add -A auto_improve/ evals/ tests/ && git diff --cached --quiet || "
            "git commit -m 'auto: update from cron' && git push fork main",
            shell=True, capture_output=True, timeout=60,
        )
        return "Pushed"
    except Exception as e:
        return f"Push failed: {e}"


def main():
    fix = "--fix" in sys.argv
    push = "--push" in sys.argv

    scores = check_scores()
    procs = check_processes()

    print(f"=== Iteration {ITERATION} ===")
    print(f"Scores: {scores['passed']}/{scores['scored']} = {scores['pass_rate']}% | preds={scores['preds']} | unscored={scores['unscored']}")
    print(f"Processes: workers={procs['workers']}, scorers={procs['scorers']}, dashboard={procs['dashboard']}")
    print()

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

    # Limbo tasks
    all_issues.extend(check_limbo(fix))

    # False negatives
    all_issues.extend(check_false_negatives())

    if all_issues:
        print("Issues:")
        for issue in all_issues:
            print(f"  {'✓' if issue.startswith('FIXED') else '⚠'} {issue}")
    else:
        print("No issues found.")

    if push:
        print()
        print(push_to_github())


if __name__ == "__main__":
    main()
