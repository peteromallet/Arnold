"""One-command dashboard for an auto-improve iteration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    iteration = int(args[0]) if args else _latest_iteration()
    if iteration is None:
        print("No iterations found.", file=sys.stderr)
        return 1

    results_root = Path(f"results/auto-improve/iteration-{iteration:03d}")
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
        print(f"  Tasks: {done} done, {claimed} claimed, {pending} pending, {error} error  ({total} total)")
    else:
        print("  Tasks: manifest not yet written")
        tasks = {}

    # Predictions
    pred_count = len(list(predictions_dir.glob("*.jsonl"))) if predictions_dir.exists() else 0
    print(f"  Predictions: {pred_count}")

    # Scores
    watch_scores_path = results_root / "_watch_scores.json"
    if watch_scores_path.exists():
        ws = json.loads(watch_scores_path.read_text())
        ws_tasks = ws.get("tasks", {})
        resolved = sum(1 for t in ws_tasks.values() if isinstance(t, dict) and t.get("resolved") is True)
        failed = sum(1 for t in ws_tasks.values() if isinstance(t, dict) and t.get("resolved") is False)
        pending_score = sum(1 for t in ws_tasks.values() if isinstance(t, dict) and t.get("resolved") is None)
        scored = resolved + failed
        rate = f"{resolved}/{scored} = {resolved/scored:.0%}" if scored else "n/a"
        parts = [f"  Scored: {rate}"]
        if pending_score:
            parts.append(f"({pending_score} scoring...)")
        print(" ".join(parts))
    else:
        print(f"  Scored: not started")

    # Disk
    st = os.statvfs("/")
    free_gb = (st.f_bavail * st.f_frsize) / (1024**3)
    print(f"  Disk: {free_gb:.0f}GB free")

    # Per-worker status
    print(f"\n{'─' * term_width}")
    print("  WORKER LOGS (last activity)")
    print(f"{'─' * term_width}")
    for w in range(3):
        log = logs_dir / f"worker-{w}.stderr.log"
        if not log.exists():
            print(f"  worker-{w}: (no log)")
            continue
        lines = log.read_text().splitlines()
        # Find last meaningful line (not just "waiting")
        last_meaningful = "(idle)"
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and "waiting" not in stripped and stripped != "|":
                last_meaningful = stripped[:term_width - 14]
                break
        # Also show last line for context
        last_line = lines[-1].strip()[:term_width - 14] if lines else ""
        print(f"  worker-{w}: {last_meaningful}")
        if last_line != last_meaningful and "waiting" in last_line:
            wait_match = last_line.split("waiting (")[-1].rstrip(")")
            print(f"           └─ waiting {wait_match}")

    # Per-task detail
    if tasks:
        print(f"\n{'─' * term_width}")
        print("  TASKS")
        print(f"{'─' * term_width}")
        for task_id, info in sorted(tasks.items()):
            status = info.get("status", "?")
            worker = info.get("worker", "")
            marker = {"done": "✓", "error": "✗", "claimed": "…", "pending": " "}.get(status, "?")
            worker_str = f" ({worker})" if worker else ""
            print(f"  {marker} {task_id}: {status}{worker_str}")

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
