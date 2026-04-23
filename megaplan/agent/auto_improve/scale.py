"""Scale an iteration to more tasks and ensure workers + scorer are running.

Usage:
    python -m auto_improve.scale --iteration 021 --to 500      # scale to 500 tasks total
    python -m auto_improve.scale --iteration 021 --to 500 --workers 3  # with 3 workers
    python -m auto_improve.scale --iteration 021 --to 500 --dry-run    # preview only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path("results/auto-improve")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scale an iteration to more tasks and ensure workers + scorer are running"
    )
    parser.add_argument("--iteration", required=True, help="Iteration to scale (e.g., 021)")
    parser.add_argument("--to", type=int, required=True, dest="target", help="Target total task count (e.g., 500)")
    parser.add_argument("--workers", type=int, default=3, help="Number of workers to ensure running (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    iter_name = args.iteration if args.iteration.startswith("iteration-") else f"iteration-{args.iteration}"
    iter_path = BASE_DIR / iter_name
    manifest_path = iter_path / "_task_manifest.json"
    config_path = iter_path / "_run_config.json"

    if not manifest_path.exists():
        print(f"Iteration not found: {iter_path}", file=sys.stderr)
        return 1

    # 1. Count current tasks
    manifest = json.loads(manifest_path.read_text())
    current_count = len(manifest.get("tasks", {}))
    to_add = args.target - current_count

    print(f"=== Scale {iter_name} ===")
    print(f"  Current tasks: {current_count}")
    print(f"  Target: {args.target}")
    print(f"  To add: {max(0, to_add)}")

    # 2. Add tasks if needed
    if to_add > 0:
        if args.dry_run:
            print(f"  [dry-run] Would add {to_add} random tasks")
        else:
            result = subprocess.run(
                [sys.executable, "-m", "auto_improve.add_tasks",
                 "--iteration", args.iteration, "--count", str(to_add)],
                capture_output=True, text=True,
            )
            print(result.stdout.strip() if result.stdout else f"  Added {to_add} tasks")
            if result.returncode != 0:
                print(f"  Error: {result.stderr.strip()}", file=sys.stderr)
                return 1
    elif to_add <= 0:
        print(f"  Already at {current_count} tasks (>= {args.target})")

    # 3. Check workers
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
    worker_count = sum(1 for line in ps.stdout.splitlines()
                       if "evals.run_evals" in line and iter_name in line and "grep" not in line)
    print(f"\n  Workers running: {worker_count} (target: {args.workers})")

    workers_to_start = args.workers - worker_count
    if workers_to_start > 0:
        if args.dry_run:
            print(f"  [dry-run] Would start {workers_to_start} workers")
        else:
            if not config_path.exists():
                print(f"  No config at {config_path} — cannot start workers", file=sys.stderr)
                return 1
            for i in range(workers_to_start):
                subprocess.Popen(
                    [sys.executable, "-m", "evals.run_evals", "--config", str(config_path), "-v"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                time.sleep(1)
            print(f"  Started {workers_to_start} workers")
    else:
        print(f"  Workers OK")

    # 4. Check scorer
    scorer_count = sum(1 for line in ps.stdout.splitlines()
                       if ("auto_improve.score" in line or "watch_scoring" in line)
                       and "python" in line and "grep" not in line)
    print(f"\n  Scorer running: {'yes' if scorer_count else 'no'}")

    if not scorer_count:
        if args.dry_run:
            print(f"  [dry-run] Would start scorer")
        else:
            subprocess.Popen(
                [sys.executable, "-m", "auto_improve.score", "--watch",
                 "--iterations", args.iteration],
                stdout=subprocess.DEVNULL,
                stderr=open("/tmp/scorer.log", "w"),
                start_new_session=True,
            )
            print(f"  Started scorer")
    else:
        print(f"  Scorer OK")

    print(f"\n  Done. Monitor with: python -m auto_improve.healthcheck {iter_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
