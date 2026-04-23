"""Shared helpers for the auto-improve experiment loop."""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from evals.benchmarks.swe_bench import SWEBenchBackend


AUTO_IMPROVE_ROOT = Path(__file__).resolve().parent
ITERATIONS_ROOT = AUTO_IMPROVE_ROOT / "iterations"
TASKS_PATH = AUTO_IMPROVE_ROOT / "tasks.json"
VERIFIED_DATASET = "princeton-nlp/SWE-bench_Verified"
ANCHOR_TASK_COUNT = 10
RETRY_TASK_COUNT = 5
NEW_TASK_COUNT = 5
TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[0-9]+$")


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


def suggest_task_rotation(
    prior_iteration_scores: dict[str, Any],
    full_task_pool: list[str],
    *,
    historical_scores: list[dict[str, Any]] | None = None,
    attempted_task_ids: set[str] | None = None,
    seed: int | None = None,
) -> list[str]:
    """Suggest a 20-task rotation: 10 anchors, 5 retries, 5 new tasks."""
    valid_task_ids = _validated_task_pool(full_task_pool)
    historical_scores = historical_scores or []

    anchor_sources = [prior_iteration_scores, *historical_scores]
    anchors = _select_from_scores(
        anchor_sources,
        desired_count=ANCHOR_TASK_COUNT,
        task_filter=_resolved_task_ids,
        valid_task_ids=valid_task_ids,
        strict=False,
    )
    if len(anchors) < ANCHOR_TASK_COUNT:
        anchors.extend(
            _select_from_scores(
                anchor_sources,
                desired_count=ANCHOR_TASK_COUNT - len(anchors),
                task_filter=_attempted_task_ids_in_order,
                valid_task_ids=valid_task_ids,
                excluded_task_ids=set(anchors),
                strict=False,
            )
        )
    if len(anchors) < ANCHOR_TASK_COUNT:
        raise ValueError(f"Need {ANCHOR_TASK_COUNT} anchor tasks, found {len(anchors)}.")

    retries = _select_from_scores(
        anchor_sources,
        desired_count=RETRY_TASK_COUNT,
        task_filter=_retry_task_ids,
        valid_task_ids=valid_task_ids,
        excluded_task_ids=set(anchors),
        strict=False,
    )
    if len(retries) < RETRY_TASK_COUNT:
        retries.extend(
            _select_from_scores(
                anchor_sources,
                desired_count=RETRY_TASK_COUNT - len(retries),
                task_filter=_attempted_task_ids_in_order,
                valid_task_ids=valid_task_ids,
                excluded_task_ids=set(anchors) | set(retries),
                strict=False,
            )
        )
    if len(retries) < RETRY_TASK_COUNT:
        raise ValueError(f"Need {RETRY_TASK_COUNT} retry tasks, found {len(retries)}.")

    attempted = set(attempted_task_ids or _attempted_task_ids(anchor_sources))
    new_candidates = sorted(valid_task_ids - attempted - set(anchors) - set(retries))
    if len(new_candidates) < NEW_TASK_COUNT:
        raise ValueError(
            f"Need at least {NEW_TASK_COUNT} unseen tasks, found {len(new_candidates)}."
        )

    rng = random.Random(seed)
    new_tasks = rng.sample(new_candidates, k=NEW_TASK_COUNT)
    suggestion = anchors + retries + new_tasks
    _ensure_valid_task_ids(suggestion, valid_task_ids)
    if len(suggestion) != ANCHOR_TASK_COUNT + RETRY_TASK_COUNT + NEW_TASK_COUNT:
        raise ValueError("Rotation suggestion must contain exactly 20 tasks.")
    if len(set(suggestion)) != len(suggestion):
        raise ValueError("Rotation suggestion contained duplicate task IDs.")
    return suggestion


def _validated_task_pool(full_task_pool: list[str]) -> set[str]:
    if not isinstance(full_task_pool, list) or not all(isinstance(task_id, str) for task_id in full_task_pool):
        raise ValueError("full_task_pool must be a list of task IDs")
    return {task_id for task_id in full_task_pool if task_id}


def _select_from_scores(
    score_payloads: list[dict[str, Any]],
    *,
    desired_count: int,
    task_filter,
    valid_task_ids: set[str],
    excluded_task_ids: set[str] | None = None,
    strict: bool = True,
) -> list[str]:
    selected: list[str] = []
    seen = set(excluded_task_ids or ())
    for scores in score_payloads:
        for task_id in task_filter(scores):
            if task_id in seen or task_id not in valid_task_ids:
                continue
            selected.append(task_id)
            seen.add(task_id)
            if len(selected) == desired_count:
                return selected
    if strict and len(selected) < desired_count:
        raise ValueError(f"Need {desired_count} tasks, found {len(selected)}.")
    return selected


def _resolved_task_ids(scores: dict[str, Any]) -> list[str]:
    return [
        task_id
        for task_id, payload in _task_entries(scores)
        if payload.get("resolved") is True
    ]


def _retry_task_ids(scores: dict[str, Any]) -> list[str]:
    return [
        task_id
        for task_id, payload in _task_entries(scores)
        if payload.get("resolved") is False and not _is_infra_error(payload)
    ]


def _attempted_task_ids(score_payloads: list[dict[str, Any]]) -> set[str]:
    attempted: set[str] = set()
    for scores in score_payloads:
        attempted.update(task_id for task_id, _ in _task_entries(scores))
    return attempted


def _attempted_task_ids_in_order(scores: dict[str, Any]) -> list[str]:
    return [task_id for task_id, _ in _task_entries(scores)]


def _task_entries(scores: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    tasks = scores.get("tasks")
    if not isinstance(tasks, dict):
        raise ValueError("scores payload must contain a 'tasks' object")
    return [
        (task_id, payload)
        for task_id, payload in tasks.items()
        if isinstance(task_id, str) and isinstance(payload, dict)
    ]


def _is_infra_error(task_payload: dict[str, Any]) -> bool:
    error_category = task_payload.get("error_category")
    if isinstance(error_category, str) and error_category.strip():
        return True
    return task_payload.get("status") == "error"


def _ensure_valid_task_ids(task_ids: list[str], valid_task_ids: set[str]) -> None:
    invalid = [task_id for task_id in task_ids if task_id not in valid_task_ids]
    if invalid:
        raise ValueError(f"Unknown SWE-bench Verified task IDs: {', '.join(sorted(invalid))}")


def _load_verified_task_pool() -> list[str]:
    try:
        backend = SWEBenchBackend()
        dataset = backend._load_dataset(VERIFIED_DATASET)
    except (ImportError, ModuleNotFoundError):
        return _load_local_verified_task_pool()

    task_ids = [
        str(row["instance_id"])
        for row in dataset
        if isinstance(row, dict) and isinstance(row.get("instance_id"), str)
    ]
    _ensure_valid_task_ids(task_ids, set(task_ids))
    return task_ids


def _load_local_verified_task_pool() -> list[str]:
    """Fallback task corpus when Hugging Face dataset deps are unavailable."""
    task_ids: set[str] = set()
    results_root = AUTO_IMPROVE_ROOT.parent / "results"

    _add_candidate_task_id(task_ids, _load_json_file(TASKS_PATH))

    for scores_path in ITERATIONS_ROOT.glob("*/scores.json"):
        _add_candidate_task_id(task_ids, _load_json_file(scores_path))

    for task_dir in ITERATIONS_ROOT.glob("*/consolidated/tasks/*"):
        _add_candidate_task_id(task_ids, task_dir.name)

    if results_root.exists():
        for manifest_path in results_root.rglob("_task_manifest.json"):
            _add_candidate_task_id(task_ids, _load_json_file(manifest_path))
        for json_path in results_root.rglob("*.json"):
            _add_candidate_task_id(task_ids, _load_json_file(json_path))
        for jsonl_path in results_root.rglob("*.jsonl"):
            _add_candidate_task_id(task_ids, _load_jsonl_records(jsonl_path))
        for worker_task_dir in results_root.glob("**/worker-*/*"):
            _add_candidate_task_id(task_ids, worker_task_dir.name)

    if not task_ids:
        raise RuntimeError(
            "Could not load any SWE-bench task IDs from the local corpus fallback."
        )
    return sorted(task_ids)


def _load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _load_jsonl_records(path: Path) -> list[Any]:
    records: list[Any] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


def _add_candidate_task_id(task_ids: set[str], payload: Any) -> None:
    if isinstance(payload, str):
        if TASK_ID_PATTERN.fullmatch(payload):
            task_ids.add(payload)
        return
    if isinstance(payload, dict):
        instance_id = payload.get("instance_id")
        if isinstance(instance_id, str) and TASK_ID_PATTERN.fullmatch(instance_id):
            task_ids.add(instance_id)
        tasks = payload.get("tasks")
        if isinstance(tasks, dict):
            for task_id in tasks:
                if isinstance(task_id, str) and TASK_ID_PATTERN.fullmatch(task_id):
                    task_ids.add(task_id)
        for value in payload.values():
            if isinstance(value, (dict, list)):
                _add_candidate_task_id(task_ids, value)
        return
    if isinstance(payload, list):
        for item in payload:
            _add_candidate_task_id(task_ids, item)


def _load_score_history(iteration: int) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for existing_iteration in sorted(
        (value for value in _existing_iteration_numbers() if value <= iteration),
        reverse=True,
    ):
        history.append(load_scores(existing_iteration))
    return history


def _suggest_rotation_for_iteration(iteration: int) -> list[str]:
    score_history = _load_score_history(iteration)
    if not score_history:
        raise FileNotFoundError(f"No scores found for iteration {iteration}.")
    prior_scores = score_history[0]
    full_task_pool = _load_verified_task_pool()
    attempted = _attempted_task_ids(score_history)
    return suggest_task_rotation(
        prior_scores,
        full_task_pool,
        historical_scores=score_history[1:],
        attempted_task_ids=attempted,
        seed=iteration,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto-improve utilities.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest_rotation_parser = subparsers.add_parser(
        "suggest-rotation",
        help="Print a suggested tasks.json rotation for a completed iteration.",
    )
    suggest_rotation_parser.add_argument(
        "--iteration",
        type=int,
        required=True,
        help="Completed iteration to use as the anchor/retry source.",
    )

    args = parser.parse_args(argv)

    if args.command == "suggest-rotation":
        print(json.dumps(_suggest_rotation_for_iteration(args.iteration), indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
