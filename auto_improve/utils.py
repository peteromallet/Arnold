"""Shared helpers for the auto-improve experiment loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AUTO_IMPROVE_ROOT = Path(__file__).resolve().parent
ITERATIONS_ROOT = AUTO_IMPROVE_ROOT / "iterations"


def get_iteration_dir(iteration: int) -> Path:
    if iteration < 0:
        raise ValueError("iteration must be non-negative")
    return ITERATIONS_ROOT / f"{iteration:03d}"


def next_iteration() -> int:
    existing = sorted(_existing_iteration_numbers())
    if not existing:
        return 1
    return existing[-1] + 1


def load_scores(iteration: int) -> dict[str, Any]:
    scores_path = get_iteration_dir(iteration) / "scores.json"
    if not scores_path.exists():
        raise FileNotFoundError(f"Scores file not found for iteration {iteration}: {scores_path}")

    payload = json.loads(scores_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Scores file must contain a JSON object: {scores_path}")
    return payload


def compare_scores(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    current_tasks = _task_resolution_map(current)
    previous_tasks = _task_resolution_map(previous)

    shared_task_ids = sorted(current_tasks.keys() & previous_tasks.keys())
    regressions = [task_id for task_id in shared_task_ids if previous_tasks[task_id] and not current_tasks[task_id]]
    improvements = [task_id for task_id in shared_task_ids if not previous_tasks[task_id] and current_tasks[task_id]]
    stable_passed = [task_id for task_id in shared_task_ids if previous_tasks[task_id] and current_tasks[task_id]]
    stable_failed = [task_id for task_id in shared_task_ids if not previous_tasks[task_id] and not current_tasks[task_id]]

    return {
        "regressions": regressions,
        "improvements": improvements,
        "stable": {
            "passed": stable_passed,
            "failed": stable_failed,
            "count": len(stable_passed) + len(stable_failed),
            "passed_count": len(stable_passed),
            "failed_count": len(stable_failed),
        },
        "counts": {
            "regressions": len(regressions),
            "improvements": len(improvements),
            "stable": len(stable_passed) + len(stable_failed),
            "stable_passed": len(stable_passed),
            "stable_failed": len(stable_failed),
            "compared_tasks": len(shared_task_ids),
        },
        "missing_from_previous": sorted(current_tasks.keys() - previous_tasks.keys()),
        "missing_from_current": sorted(previous_tasks.keys() - current_tasks.keys()),
    }


def _existing_iteration_numbers() -> list[int]:
    if not ITERATIONS_ROOT.exists():
        return []

    iteration_numbers: list[int] = []
    for child in ITERATIONS_ROOT.iterdir():
        if child.is_dir() and child.name.isdigit():
            iteration_numbers.append(int(child.name))
    return iteration_numbers


def _task_resolution_map(scores: dict[str, Any]) -> dict[str, bool]:
    tasks = scores.get("tasks")
    if not isinstance(tasks, dict):
        raise ValueError("scores payload must contain a 'tasks' object")

    resolved_by_task: dict[str, bool] = {}
    for task_id, task_payload in tasks.items():
        resolved = task_payload
        if isinstance(task_payload, dict):
            resolved = task_payload.get("resolved")
        if not isinstance(resolved, bool):
            raise ValueError(f"task '{task_id}' must define a boolean resolved value")
        resolved_by_task[task_id] = resolved
    return resolved_by_task
