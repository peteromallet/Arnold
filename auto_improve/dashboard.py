"""One-command dashboard for an auto-improve iteration.

Usage:
    python -m auto_improve.dashboard          # latest iteration overview
    python -m auto_improve.dashboard 4        # iteration 004 overview
    python -m auto_improve.dashboard --task django__django-12325  # inspect one task
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.watch_scoring import classify_task, load_scores_data


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]

    # Parse --task flag
    task_id = None
    iteration_arg = None
    i = 0
    while i < len(args):
        if args[i] == "--task" and i + 1 < len(args):
            task_id = args[i + 1]
            i += 2
        else:
            iteration_arg = args[i]
            i += 1

    iteration = int(iteration_arg) if iteration_arg else _latest_iteration()
    if iteration is None:
        print("No iterations found.", file=sys.stderr)
        return 1

    results_root = Path(f"results/auto-improve/iteration-{iteration:03d}")

    if task_id:
        return _inspect_task(results_root, task_id, iteration)

    return _show_dashboard(results_root, iteration)


def _show_dashboard(results_root: Path, iteration: int) -> int:
    manifest_path = results_root / "_task_manifest.json"
    predictions_dir = results_root / "_swebench_predictions"
    logs_dir = results_root / "_worker_logs"

    term_width = shutil.get_terminal_size((80, 24)).columns
    print(f"{'=' * term_width}")
    print(f"  AUTO-IMPROVE ITERATION {iteration:03d}")
    print(f"{'=' * term_width}")

    # Workers
    try:
        ps = subprocess.run(
            ["pgrep", "-f", "run_evals"],
            capture_output=True, text=True,
        )
        worker_count = len(ps.stdout.strip().splitlines()) if ps.stdout.strip() else 0
    except Exception:
        worker_count = "?"
    print(f"\n  Workers alive: {worker_count}")

    # Manifest
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        tasks = manifest.get("tasks", {})
        states: dict[str, int] = {}
        for v in tasks.values():
            s = v.get("status", "?")
            states[s] = states.get(s, 0) + 1
        total = len(tasks)
        done = states.get("done", 0)
        error = states.get("error", 0)
        claimed = states.get("claimed", 0)
        pending = states.get("pending", 0)
        # Count done-with-prediction vs escalated
        pred_ids = set()
        if predictions_dir.exists():
            pred_ids = {f.stem for f in predictions_dir.glob("*.jsonl")}
        done_with_patch = sum(1 for tid, v in tasks.items() if v.get("status") == "done" and tid in pred_ids)
        escalated = done - done_with_patch
        done_str = f"{done} done"
        if escalated > 0:
            done_str = f"{done_with_patch} done, {escalated} escalated"
        print(f"  Tasks: {done_str}, {claimed} claimed, {pending} pending, {error} error  ({total} total)")
    else:
        print("  Tasks: manifest not yet written")
        tasks = {}

    # Predictions
    pred_count = len(list(predictions_dir.glob("*.jsonl"))) if predictions_dir.exists() else 0
    print(f"  Predictions: {pred_count}")

    # Scores — show both raw and adjusted (if exclusions exist)
    watch_scores_path = results_root / "_watch_scores.json"
    if watch_scores_path.exists():
        ws = load_scores_data(watch_scores_path)
        ws_tasks = ws.get("tasks", {})
        states = {
            tid: classify_task(info)
            for tid, info in ws_tasks.items()
            if isinstance(info, dict)
        }
        resolved = sum(1 for state in states.values() if state == "pass")
        failed = sum(1 for state in states.values() if state == "fail")
        excluded = sum(
            1 for t in ws_tasks.values()
            if isinstance(t, dict)
            and isinstance(t.get("review"), dict)
            and t["review"].get("excluded_from_pass_rate")
        )
        pending_score = sum(1 for state in states.values() if state in {"pending", "error"})
        scored = resolved + failed
        rate = f"{resolved}/{scored} = {resolved/scored:.0%}" if scored else "n/a"
        parts = [f"  Scored: {rate}"]
        if excluded:
            adj_scored = scored - excluded
            adj_resolved = resolved
            # Excluded tasks might be fails we're excluding
            excluded_fails = sum(
                1
                for tid, t in ws_tasks.items()
                if isinstance(t, dict)
                and states.get(tid) == "fail"
                and isinstance(t.get("review"), dict)
                and t["review"].get("excluded_from_pass_rate")
            )
            adj_failed = failed - excluded_fails
            adj_rate = f"{adj_resolved}/{adj_scored} = {adj_resolved/adj_scored:.0%}" if adj_scored else "n/a"
            parts.append(f"| Adjusted: {adj_rate} ({excluded} excluded)")
        if pending_score:
            parts.append(f"({pending_score} scoring...)")
        print(" ".join(parts))
        # Show exclusions prominently
        if excluded:
            print(f"\n  EXCLUSIONS ({excluded}):")
            for tid, info in sorted(ws_tasks.items()):
                review = info.get("review")
                if isinstance(review, dict) and review.get("excluded_from_pass_rate"):
                    print(f"    {tid}: {review.get('category', '?')} — {review.get('explanation', '')[:80]}")
    else:
        print(f"  Scored: not started")

    # Scorer status
    scorer_status_path = results_root / "_scorer_status.json"
    scorer_label = None
    if scorer_status_path.exists():
        try:
            ss = json.loads(scorer_status_path.read_text())
            status = ss.get("status", "")
            if status == "dead":
                scorer_label = f"DEAD ⛔ — {ss.get('detail', '')[:80]}"
            elif "restarting" in status:
                scorer_label = f"RESTARTING ⚠ ({status})"
            elif status == "running":
                ps_check = subprocess.run(["pgrep", "-f", "watch_scoring|auto_improve.score"], capture_output=True, text=True)
                scorer_label = "alive" if ps_check.stdout.strip() else "NOT RUNNING ⚠ (stale status)"
            elif status == "completed":
                scorer_label = "completed"
            else:
                scorer_label = status
        except Exception:
            pass
    if scorer_label is None:
        try:
            ps_scorer = subprocess.run(["pgrep", "-f", "watch_scoring|auto_improve.score"], capture_output=True, text=True)
            scorer_label = "alive" if ps_scorer.stdout.strip() else "NOT RUNNING ⚠"
        except Exception:
            scorer_label = "unknown"
    print(f"  Scorer: {scorer_label}")

    # Disk
    st = os.statvfs("/")
    free_gb = (st.f_bavail * st.f_frsize) / (1024**3)
    print(f"  Disk: {free_gb:.0f}GB free")

    # Per-worker status with rate limit count
    print(f"\n{'─' * term_width}")
    print("  WORKER LOGS (last activity)")
    print(f"{'─' * term_width}")
    worker_logs = sorted(logs_dir.glob("worker-*.stderr.log")) if logs_dir.exists() else []
    for log in worker_logs:
        w = log.stem.replace(".stderr", "")
        try:
            log_text = log.read_text(errors="replace")
        except Exception:
            print(f"  {w}: (unreadable)")
            continue
        lines = log_text.splitlines()
        # Count rate limit hits
        rate_limits = sum(1 for l in lines if "429" in l or "Rate limit" in l)
        # Find last meaningful line
        last_meaningful = "(idle)"
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and "waiting" not in stripped and stripped != "|":
                last_meaningful = stripped[:term_width - 14]
                break
        last_line = lines[-1].strip()[:term_width - 14] if lines else ""
        rl_tag = f" [429s: {rate_limits}]" if rate_limits > 0 else ""
        print(f"  {w}: {last_meaningful}{rl_tag}")
        if last_line != last_meaningful and "waiting" in last_line:
            wait_match = last_line.split("waiting (")[-1].rstrip(")")
            print(f"           └─ waiting {wait_match}")

    # Per-task detail with phase info and score
    if tasks:
        print(f"\n{'─' * term_width}")
        print("  TASKS")
        print(f"{'─' * term_width}")

        # Load scores for enrichment
        ws_tasks = {}
        if watch_scores_path.exists():
            try:
                ws_tasks = json.loads(watch_scores_path.read_text()).get("tasks", {})
            except Exception:
                pass

        for task_id, info in sorted(tasks.items()):
            status = info.get("status", "?")
            worker = info.get("worker", "")
            marker = {"done": "✓", "error": "✗", "claimed": "…", "pending": " "}.get(status, "?")
            worker_str = f" ({worker})" if worker else ""

            # Enrich done tasks with outcome
            extra = ""
            if status == "done":
                if task_id in pred_ids:
                    score_info = ws_tasks.get(task_id)
                    if score_info:
                        r = score_info.get("resolved")
                        review = score_info.get("review")
                        is_excluded = isinstance(review, dict) and review.get("excluded_from_pass_rate")
                        if r is True:
                            extra = " → PASS"
                        elif r is False and is_excluded:
                            extra = f" → FAIL [EXCLUDED: {review.get('category', '?')}]"
                        elif r is False:
                            extra = " → FAIL"
                        elif r is None:
                            extra = " → scoring..."
                    else:
                        extra = " → awaiting score"
                else:
                    extra = " → escalated (no patch)"
                    marker = "⊘"

            print(f"  {marker} {task_id}: {status}{worker_str}{extra}")

    # Quick health alerts — flag issues, point to healthcheck for details
    alerts = []
    # Scorer dead?
    try:
        ps_scorer = subprocess.run(["pgrep", "-f", "watch_scoring|auto_improve.score"], capture_output=True, text=True)
        if not ps_scorer.stdout.strip():
            alerts.append("⛔ Scorer not running — predictions won't be scored")
    except Exception:
        pass
    # Rate limit pressure?
    total_429s = 0
    for log in worker_logs:
        try:
            total_429s += sum(1 for l in log.read_text(errors="replace").splitlines() if "429" in l)
        except Exception:
            pass
    if total_429s > 500:
        alerts.append(f"⛔ Heavy rate limiting ({total_429s} total 429s)")
    elif total_429s > 100:
        alerts.append(f"⚠️  Rate limiting active ({total_429s} total 429s)")
    # Disk?
    if free_gb < 5:
        alerts.append(f"⛔ Disk critically low ({free_gb:.0f}GB)")
    elif free_gb < 10:
        alerts.append(f"⚠️  Disk space low ({free_gb:.0f}GB)")
    # Stalled workers?
    for log in worker_logs:
        try:
            lines = log.read_text(errors="replace").splitlines()
            for line in reversed(lines):
                m = re.search(r"waiting \((\d+)s\)", line)
                if m and int(m.group(1)) > 1200:
                    w = log.stem.replace(".stderr", "")
                    alerts.append(f"⚠️  {w} stalled ({m.group(1)}s waiting)")
                break
        except Exception:
            pass
    # Unscored predictions?
    if watch_scores_path.exists():
        unscored = pred_count - sum(1 for s in states.values() if s in ("pass", "fail", "exhausted"))
        if unscored > 3:
            alerts.append(f"⚠️  {unscored} predictions waiting to be scored")

    if alerts:
        print(f"\n{'─' * term_width}")
        print("  ALERTS")
        print(f"{'─' * term_width}")
        for a in alerts:
            print(f"  {a}")
        print(f"\n  Run `python -m auto_improve.healthcheck` for deep diagnosis")

    print(f"\n{'=' * term_width}")
    return 0


def _inspect_task(results_root: Path, task_id: str, iteration: int) -> int:
    """Deep inspection of a single task — phases, outcome, patch summary."""
    term_width = shutil.get_terminal_size((80, 24)).columns
    print(f"{'=' * term_width}")
    print(f"  TASK: {task_id}")
    print(f"{'=' * term_width}")

    # Find task dir across workers
    task_dir = None
    for worker_dir in sorted(results_root.glob("worker-*")):
        candidate = worker_dir / task_id
        if candidate.is_dir():
            task_dir = candidate
            break

    if task_dir is None:
        print(f"\n  Task not found in any worker directory.")
        return 1

    # Find the run dir (timestamped)
    run_dirs = sorted(task_dir.iterdir())
    if not run_dirs:
        print(f"\n  No run directory found.")
        return 1
    run_dir = run_dirs[0]
    print(f"\n  Worker: {task_dir.parent.name}")
    print(f"  Run dir: {run_dir.name}")

    # Summary
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        notes = summary.get("notes", [])
        phases = summary.get("phases", [])

        # Phase trail
        print(f"\n  Phases ({len(phases)}):")
        for p in phases:
            phase = p.get("phase", "?")
            duration_ms = p.get("duration_ms", 0)
            duration_s = duration_ms / 1000 if duration_ms else 0
            iteration_num = p.get("iteration", 1)
            iter_tag = f" (iter {iteration_num})" if iteration_num > 1 else ""
            print(f"    {phase}{iter_tag}: {duration_s:.0f}s")

        # Notes
        if notes:
            print(f"\n  Notes:")
            for note in notes:
                print(f"    {str(note)[:term_width - 6]}")
    else:
        print(f"\n  No summary.json found.")

    # Megaplan state
    state_path = run_dir / "megaplan" / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        print(f"\n  Megaplan state: {state.get('current_state', '?')}")
        print(f"  Iteration: {state.get('iteration', 1)}")

    # Gate result
    for gate_file in sorted(run_dir.glob("megaplan/gate_v*.json")):
        gate_data = json.loads(gate_file.read_text())
        # recommendation can be top-level or nested under "gate"
        rec = gate_data.get("recommendation") or gate_data.get("gate", {}).get("recommendation", "?")
        summary_text = gate_data.get("summary") or gate_data.get("gate", {}).get("summary", "")
        print(f"\n  Gate ({gate_file.name}): {rec}")
        if summary_text:
            print(f"    {str(summary_text)[:term_width - 6]}")

    # Critique summary
    for critique_file in sorted(run_dir.glob("megaplan/critique_v*.json")):
        critique = json.loads(critique_file.read_text())
        checks = critique.get("checks", [])
        flagged = sum(
            1 for c in checks
            for f in c.get("findings", [])
            if f.get("flagged")
        )
        total_findings = sum(len(c.get("findings", [])) for c in checks)
        print(f"\n  Critique ({critique_file.name}): {flagged} flagged / {total_findings} findings")

    # Patch
    patch_path = run_dir / "git" / "diff.patch"
    if not patch_path.exists():
        # Try consolidated
        patch_path = run_dir / "patch.diff"
    if patch_path.exists():
        patch_text = patch_path.read_text(errors="replace")
        lines = patch_text.splitlines()
        files_changed = [l.split(" b/")[-1] for l in lines if l.startswith("diff --git")]
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        print(f"\n  Patch: {len(files_changed)} files, +{additions}/-{deletions} lines")
        for f in files_changed:
            print(f"    {f}")
    else:
        print(f"\n  Patch: not found")

    # Score + Review
    watch_scores_path = results_root / "_watch_scores.json"
    if watch_scores_path.exists():
        ws = json.loads(watch_scores_path.read_text())
        score_info = ws.get("tasks", {}).get(task_id)
        if score_info:
            r = score_info.get("resolved")
            status = "PASS" if r else ("FAIL" if r is False else "ERROR")
            print(f"\n  Score: {status} (attempts={score_info.get('attempts', 1)})")
            if score_info.get("error"):
                print(f"    Error: {str(score_info['error'])[:200]}")
            # Show review/exclusion
            review = score_info.get("review")
            if isinstance(review, dict):
                print(f"\n  Review:")
                print(f"    Category: {review.get('category', '?')}")
                print(f"    Excluded from pass rate: {review.get('excluded_from_pass_rate', False)}")
                print(f"    Explanation: {review.get('explanation', '')}")
                print(f"    Reviewed by: {review.get('reviewed_by', '?')}")
                print(f"    Reviewed at: {review.get('reviewed_at', '?')}")
        else:
            print(f"\n  Score: not yet scored")

    print(f"\n{'=' * term_width}")
    return 0


def _latest_iteration() -> int | None:
    iterations_dir = Path("auto_improve/iterations")
    if not iterations_dir.exists():
        return None
    nums = []
    for child in iterations_dir.iterdir():
        if child.is_dir() and child.name.isdigit():
            nums.append(int(child.name))
    return max(nums) if nums else None


if __name__ == "__main__":
    raise SystemExit(main())
