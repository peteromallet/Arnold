"""Deep health check for auto-improve infrastructure.

Surfaces all the problems we keep hitting:
- Worker stalls, deaths, rate limit pressure
- Scorer stuck on failing tasks, unscored backlog
- Modal sandbox failures (auto-skip candidates)
- Manifest corruption (claimed by dead workers)
- Disk pressure

Usage:
    python -m auto_improve.healthcheck                    # all active iterations
    python -m auto_improve.healthcheck iteration-021 022  # specific iterations
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path("results/auto-improve")
WORKSPACE_DIR = Path("evals/workspaces-auto-improve")

# Thresholds
DISK_WARNING_GB = 10
DISK_CRITICAL_GB = 5
WORKER_STALL_SECONDS = 1200  # 20 min
SCORING_STALL_SECONDS = 600  # 10 min
RATE_LIMIT_WARNING = 50  # 429s per worker
RATE_LIMIT_CRITICAL = 200


def _find_active_iterations(args: list[str]) -> list[Path]:
    """Find iteration directories to check."""
    if args:
        dirs = []
        for a in args:
            name = a if a.startswith("iteration-") else f"iteration-{a}"
            d = BASE_DIR / name
            if d.exists():
                dirs.append(d)
        return dirs
    # Auto-detect: has manifest + at least one worker log
    return sorted(
        d for d in BASE_DIR.iterdir()
        if d.is_dir() and (d / "_task_manifest.json").exists()
        and (d / "_worker_logs").exists()
        and any((d / "_worker_logs").glob("*.log"))
    )


def _get_worker_pids() -> dict[int, str]:
    """Get PIDs of running eval worker processes."""
    result = subprocess.run(
        ["ps", "aux"], capture_output=True, text=True, timeout=10
    )
    pids: dict[int, str] = {}
    for line in result.stdout.splitlines():
        if "evals.run_evals" in line and "grep" not in line:
            parts = line.split()
            try:
                pids[int(parts[1])] = line
            except (IndexError, ValueError):
                pass
    return pids


def _get_scorer_pids() -> list[dict[str, Any]]:
    """Get scorer process info."""
    result = subprocess.run(
        ["ps", "aux"], capture_output=True, text=True, timeout=10
    )
    scorers = []
    for line in result.stdout.splitlines():
        if ("watch_scoring" in line or "auto_improve.score" in line) and "python" in line and "grep" not in line:
            parts = line.split()
            try:
                scorers.append({"pid": int(parts[1]), "line": line.strip()})
            except (IndexError, ValueError):
                pass
    return scorers


def _parse_worker_log(log_path: Path) -> dict[str, Any]:
    """Extract health signals from a worker stderr log."""
    if not log_path.exists():
        return {"exists": False}

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Count 429s
    rate_limits = sum(1 for l in lines if "429" in l)

    # Find last activity line (not just "waiting")
    last_activity = ""
    last_waiting = 0
    current_task = ""
    current_phase = ""
    for line in reversed(lines):
        if "waiting" in line:
            m = re.search(r"waiting \((\d+)s\)", line)
            if m and not last_waiting:
                last_waiting = int(m.group(1))
        elif line.strip() and not last_activity:
            last_activity = line.strip()[:120]
        # Find current task/phase
        m = re.search(r"\[([^\]]+)\] (\w+) \(", line)
        if m and not current_task:
            current_task = m.group(1)
            current_phase = m.group(2)

    # Count escalations and errors
    escalations = sum(1 for l in lines if "ESCALATED" in l and "skipping" in l)
    errors = sum(1 for l in lines if "ERROR:" in l or "Max retries" in l)

    # Check if worker finished
    finished = any("Results:" in l for l in lines[-5:]) or any("Summary:" in l for l in lines[-5:])

    return {
        "exists": True,
        "rate_limits": rate_limits,
        "last_waiting_seconds": last_waiting,
        "last_activity": last_activity,
        "current_task": current_task,
        "current_phase": current_phase,
        "escalations": escalations,
        "errors": errors,
        "finished": finished,
        "stalled": last_waiting > WORKER_STALL_SECONDS,
    }


def _check_scoring(iter_dir: Path) -> dict[str, Any]:
    """Check scoring health for an iteration — including throughput and staleness."""
    scores_path = iter_dir / "_watch_scores.json"
    preds_dir = iter_dir / "_swebench_predictions"

    preds = set(p.stem for p in preds_dir.glob("*.jsonl") if p.stem != "all_predictions") if preds_dir.exists() else set()

    if not scores_path.exists():
        return {"scored": 0, "unscored": len(preds), "stuck_tasks": [], "modal_failures": [],
                "scored_last_hour": 0, "oldest_unscored_minutes": 0, "last_score_minutes_ago": None}

    data = json.loads(scores_path.read_text())
    tasks = data.get("tasks", {})
    now = datetime.now(timezone.utc)

    scored = 0
    unscored_ids = []
    stuck_tasks = []
    modal_failures = []
    scored_timestamps = []
    oldest_unscored_age = 0

    for tid in preds:
        entry = tasks.get(tid, {})
        resolved = entry.get("resolved")
        review = entry.get("review", {}) if isinstance(entry, dict) else {}
        is_human_reviewed = isinstance(review, dict) and review.get("reviewed_by") == "human"

        if resolved is not None or is_human_reviewed:
            scored += 1
            # Track when it was scored for throughput
            scored_at = entry.get("scored_at", "")
            if scored_at:
                try:
                    ts = datetime.fromisoformat(scored_at.replace("Z", "+00:00"))
                    scored_timestamps.append(ts)
                except (ValueError, TypeError):
                    pass
        elif isinstance(review, dict) and review.get("category") == "scoring_exhausted":
            scored += 1
        else:
            attempts = entry.get("attempts", 0)
            unscored_ids.append(tid)
            # Check age of prediction file
            pred_path = preds_dir / f"{tid}.jsonl" if preds_dir.exists() else None
            if pred_path and pred_path.exists():
                pred_age_minutes = (time.time() - pred_path.stat().st_mtime) / 60
                oldest_unscored_age = max(oldest_unscored_age, pred_age_minutes)
            # Check if it's a Modal sandbox failure
            stderr = entry.get("stderr", "") if isinstance(entry, dict) else ""
            error = entry.get("error", "") if isinstance(entry, dict) else ""
            if "setup_repo.sh" in stderr or "Error creating sandbox" in stderr or "sandbox" in error.lower():
                modal_failures.append(tid)
            elif attempts >= 3:
                stuck_tasks.append(f"{tid} (attempts={attempts})")

    # Also check for unscored predictions not in the scores file at all
    for tid in preds:
        if tid not in tasks:
            unscored_ids.append(tid)
            pred_path = preds_dir / f"{tid}.jsonl"
            if pred_path.exists():
                pred_age_minutes = (time.time() - pred_path.stat().st_mtime) / 60
                oldest_unscored_age = max(oldest_unscored_age, pred_age_minutes)

    # Throughput: how many scored in the last hour?
    one_hour_ago = now - __import__("datetime").timedelta(hours=1)
    scored_last_hour = sum(1 for ts in scored_timestamps if ts >= one_hour_ago)

    # Last score: how long ago?
    last_score_minutes_ago = None
    if scored_timestamps:
        latest = max(scored_timestamps)
        last_score_minutes_ago = (now - latest).total_seconds() / 60

    return {
        "scored": scored,
        "unscored": len(set(unscored_ids)),
        "unscored_ids": list(set(unscored_ids)),
        "stuck_tasks": stuck_tasks,
        "modal_failures": modal_failures,
        "scored_last_hour": scored_last_hour,
        "oldest_unscored_minutes": round(oldest_unscored_age),
        "last_score_minutes_ago": round(last_score_minutes_ago) if last_score_minutes_ago is not None else None,
    }


def _check_manifest(iter_dir: Path) -> dict[str, Any]:
    """Check manifest health — stale claims, corruption."""
    manifest_path = iter_dir / "_task_manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "error": "no manifest"}

    data = json.loads(manifest_path.read_text())
    tasks = data.get("tasks", {})

    claimed = [(tid, t.get("worker", "?")) for tid, t in tasks.items() if t.get("status") == "claimed"]
    done = sum(1 for t in tasks.values() if t.get("status") == "done")
    pending = sum(1 for t in tasks.values() if t.get("status") == "pending")
    errors = sum(1 for t in tasks.values() if t.get("status") == "error")

    # Tasks that keep failing (high requeue count)
    repeat_failures = []
    for tid, t in tasks.items():
        requeue_count = t.get("requeue_count", 0)
        error_count = t.get("error_count", 0)
        if requeue_count >= 3 or error_count >= 3:
            repeat_failures.append(f"{tid} (requeued={requeue_count}, errors={error_count})")

    return {
        "ok": True,
        "done": done,
        "claimed": len(claimed),
        "pending": pending,
        "errors": errors,
        "total": len(tasks),
        "repeat_failures": repeat_failures,
    }


def _check_disk() -> dict[str, Any]:
    """Check disk space."""
    result = subprocess.run(["df", "-g", "/"], capture_output=True, text=True, timeout=10)
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        try:
            available_gb = int(parts[3])
            return {
                "available_gb": available_gb,
                "warning": available_gb < DISK_WARNING_GB,
                "critical": available_gb < DISK_CRITICAL_GB,
            }
        except (IndexError, ValueError):
            pass
    return {"available_gb": -1, "warning": False, "critical": False}


def main():
    args = sys.argv[1:]
    iterations = _find_active_iterations(args)

    if not iterations:
        print("No active iterations found.")
        return

    issues: list[str] = []
    warnings: list[str] = []

    # === DISK ===
    disk = _check_disk()
    if disk["critical"]:
        issues.append(f"CRITICAL: Disk space {disk['available_gb']}GB — below {DISK_CRITICAL_GB}GB threshold")
    elif disk["warning"]:
        warnings.append(f"Disk space {disk['available_gb']}GB — below {DISK_WARNING_GB}GB warning threshold")

    # === SCORERS ===
    scorers = _get_scorer_pids()
    if not scorers:
        issues.append("NO SCORER RUNNING — predictions will not be scored")

    # === WORKERS ===
    worker_pids = _get_worker_pids()

    print("=" * 70)
    print("  HEALTH CHECK")
    print("=" * 70)
    print()

    # Global status
    print(f"  Disk: {disk['available_gb']}GB free", end="")
    if disk["critical"]:
        print(" ⛔ CRITICAL")
    elif disk["warning"]:
        print(" ⚠️  LOW")
    else:
        print(" ✓")

    print(f"  Workers: {len(worker_pids)} processes", end="")
    print(" ✓" if worker_pids else " ⛔ NONE")

    print(f"  Scorers: {len(scorers)} processes", end="")
    print(" ✓" if scorers else " ⛔ NONE")

    # Scorer log check
    for log_path in [Path("/tmp/scorer_all4.log"), Path("/tmp/scorer_021_023.log"), Path("/tmp/scorer_focused2.log")]:
        if log_path.exists():
            last_line = ""
            for line in reversed(log_path.read_text(errors="replace").splitlines()):
                if line.strip():
                    last_line = line.strip()
                    break
            if last_line:
                print(f"  Scorer last: {last_line[:80]}")
            break

    print()

    # === PER-ITERATION ===
    for iter_dir in iterations:
        iter_name = iter_dir.name
        config_path = iter_dir / "_run_config.json"
        robustness = "?"
        if config_path.exists():
            robustness = json.loads(config_path.read_text()).get("robustness", "?")

        print(f"── {iter_name} ({robustness}) " + "─" * (50 - len(iter_name) - len(robustness)))

        # Manifest
        manifest = _check_manifest(iter_dir)
        if manifest["ok"]:
            print(f"  Tasks: {manifest['done']} done, {manifest['claimed']} claimed, {manifest['pending']} pending, {manifest['errors']} error (of {manifest['total']})")
            for rf in manifest.get("repeat_failures", []):
                print(f"    ⛔ Repeat failure: {rf} — consider replacing")
                issues.append(f"{iter_name}: repeat failure {rf}")
        else:
            print(f"  Tasks: {manifest.get('error', 'unknown')}")
            issues.append(f"{iter_name}: manifest error")

        # Workers
        log_dir = iter_dir / "_worker_logs"
        if log_dir.exists():
            for log_file in sorted(log_dir.glob("*.stderr.log")):
                worker_id = log_file.stem.replace(".stderr", "")
                health = _parse_worker_log(log_file)
                if not health["exists"]:
                    continue

                status_parts = []
                if health["finished"]:
                    status_parts.append("FINISHED")
                elif health["stalled"]:
                    status_parts.append(f"⛔ STALLED ({health['last_waiting_seconds']}s)")
                    issues.append(f"{iter_name}/{worker_id}: stalled for {health['last_waiting_seconds']}s on {health['current_task']} {health['current_phase']}")
                elif health["current_task"]:
                    status_parts.append(f"{health['current_task']} {health['current_phase']}")

                if health["rate_limits"] > RATE_LIMIT_CRITICAL:
                    status_parts.append(f"⛔ 429s={health['rate_limits']}")
                    issues.append(f"{iter_name}/{worker_id}: {health['rate_limits']} rate limits")
                elif health["rate_limits"] > RATE_LIMIT_WARNING:
                    status_parts.append(f"⚠️  429s={health['rate_limits']}")
                    warnings.append(f"{iter_name}/{worker_id}: {health['rate_limits']} rate limits")
                elif health["rate_limits"] > 0:
                    status_parts.append(f"429s={health['rate_limits']}")

                if health["escalations"]:
                    status_parts.append(f"escalated={health['escalations']}")
                if health["errors"]:
                    status_parts.append(f"errors={health['errors']}")

                print(f"  {worker_id}: {' | '.join(status_parts)}")

        # Scoring
        scoring = _check_scoring(iter_dir)
        preds = len([p for p in (iter_dir / "_swebench_predictions").glob("*.jsonl") if p.stem != "all_predictions"]) if (iter_dir / "_swebench_predictions").exists() else 0
        # Use find_scorable to get the REAL count of tasks needing scoring
        from evals.watch_scoring_all import find_scorable as _find_scorable
        try:
            _, actually_scorable, _, _ = _find_scorable(iter_dir)
            real_pending = len(actually_scorable)
        except Exception:
            real_pending = scoring["unscored"]

        score_line = f"  Scoring: {scoring['scored']}/{preds} scored"
        if real_pending > 0:
            score_line += f", {real_pending} awaiting scoring"
        # Throughput
        throughput_parts = []
        if scoring["scored_last_hour"] > 0:
            throughput_parts.append(f"{scoring['scored_last_hour']} scored/hr")
        if scoring["last_score_minutes_ago"] is not None:
            throughput_parts.append(f"last {scoring['last_score_minutes_ago']}m ago")
        if throughput_parts:
            score_line += f" ({', '.join(throughput_parts)})"
        print(score_line)

        # Staleness warnings — only if there are ACTUALLY scorable tasks
        if real_pending > 0:
            if scoring["oldest_unscored_minutes"] > 60:
                hrs = scoring["oldest_unscored_minutes"] / 60
                print(f"    ⚠️  Oldest unscored prediction: {hrs:.1f}h old")
                warnings.append(f"{iter_name}: prediction waiting {hrs:.1f}h to be scored")
            if scoring["last_score_minutes_ago"] is not None and scoring["last_score_minutes_ago"] > 30:
                print(f"    ⚠️  No scores in {scoring['last_score_minutes_ago']}m but {real_pending} pending")
                warnings.append(f"{iter_name}: scorer may be stalled ({scoring['last_score_minutes_ago']}m since last score)")

        if scoring["stuck_tasks"]:
            for st in scoring["stuck_tasks"]:
                print(f"    ⚠️  Stuck: {st}")
                warnings.append(f"{iter_name}: scoring stuck on {st}")

        if scoring["modal_failures"]:
            for mf in scoring["modal_failures"]:
                print(f"    ⛔ Modal failure: {mf} (consider auto-skip)")
                issues.append(f"{iter_name}: Modal sandbox failure on {mf}")

        print()

    # === SUMMARY ===
    if issues or warnings:
        print("=" * 70)
        if issues:
            print(f"  ⛔ {len(issues)} ISSUE(S):")
            for i in issues:
                print(f"     • {i}")
        if warnings:
            print(f"  ⚠️  {len(warnings)} WARNING(S):")
            for w in warnings:
                print(f"     • {w}")
        print("=" * 70)
    else:
        print("=" * 70)
        print("  ✓ All healthy")
        print("=" * 70)


if __name__ == "__main__":
    main()
