"""Add replacement tasks to a running iteration.

When tasks can't be scored (Modal failures, escalations), add random
replacements so the iteration reaches 20 scored results.

Usage:
    python -m auto_improve.add_tasks --iteration 021 --count 5
    python -m auto_improve.add_tasks --iteration 021 --count 5 --seed 9999
    python -m auto_improve.add_tasks --iteration 021 --tasks django__django-12345 sympy__sympy-67890
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

BASE_DIR = Path("results/auto-improve")
TASKS_PATH = Path("auto_improve/tasks.json")


def _load_all_tasks() -> list[str]:
    if TASKS_PATH.exists():
        data = json.loads(TASKS_PATH.read_text())
        if isinstance(data, list):
            return data
    # Fallback to backup
    backup = TASKS_PATH.with_suffix(".json.bak")
    if backup.exists():
        data = json.loads(backup.read_text())
        if isinstance(data, list):
            return data
    print("Cannot find tasks.json or tasks.json.bak", file=sys.stderr)
    return []


def _iter_path(iteration: str) -> Path:
    name = iteration if iteration.startswith("iteration-") else f"iteration-{iteration}"
    return BASE_DIR / name


def add_tasks(iteration: str, task_ids: list[str]) -> int:
    iter_path = _iter_path(iteration)
    manifest_path = iter_path / "_task_manifest.json"

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text())
    existing = set(manifest.get("tasks", {}).keys())
    added = []

    for tid in task_ids:
        if tid in existing:
            print(f"  Skipping {tid} (already in manifest)")
            continue
        manifest.setdefault("tasks", {})[tid] = {"status": "pending"}
        added.append(tid)

    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Added {len(added)} tasks to {iter_path.name}:")
    for tid in added:
        print(f"  + {tid}")

    if not added:
        print("No new tasks added (all already in manifest)")

    return 0


def add_random_tasks(iteration: str, count: int, seed: int | None = None) -> int:
    iter_path = _iter_path(iteration)
    manifest_path = iter_path / "_task_manifest.json"

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    all_tasks = _load_all_tasks()
    if not all_tasks:
        return 1

    manifest = json.loads(manifest_path.read_text())
    existing = set(manifest.get("tasks", {}).keys())
    available = [t for t in all_tasks if t not in existing]

    if len(available) < count:
        print(f"Only {len(available)} tasks available (requested {count})", file=sys.stderr)
        count = len(available)

    if seed is not None:
        random.seed(seed)
    selected = random.sample(available, count)

    return add_tasks(iteration, selected)


def main() -> int:
    parser = argparse.ArgumentParser(description="Add replacement tasks to an iteration")
    parser.add_argument("--iteration", required=True, help="Iteration (e.g., 021)")
    parser.add_argument("--count", type=int, help="Number of random tasks to add")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--tasks", nargs="+", help="Specific task IDs to add")
    args = parser.parse_args()

    if args.tasks:
        return add_tasks(args.iteration, args.tasks)
    elif args.count:
        return add_random_tasks(args.iteration, args.count, args.seed)
    else:
        print("Specify --count N or --tasks task_id [task_id ...]", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
