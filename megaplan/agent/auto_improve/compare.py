"""Compare two auto-improve iterations using watch scoring snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evals.watch_scoring import classify_task

from auto_improve.score_experiment import DEFAULT_RESULTS_BASE, results_root_for_iteration


def resolve_results_root(value: str) -> Path:
    candidate = value.strip()
    if candidate.isdigit():
        return results_root_for_iteration(int(candidate)).resolve()

    if candidate.startswith("iteration-"):
        suffix = candidate.removeprefix("iteration-")
        if suffix.isdigit():
            return (DEFAULT_RESULTS_BASE / candidate).resolve()

    raise ValueError(
        f"Unsupported iteration value '{value}'. Use NNN or iteration-NNN."
    )


def load_watch_scores(results_root: Path) -> dict[str, Any]:
    watch_scores_path = results_root / "_watch_scores.json"
    if not watch_scores_path.exists():
        raise FileNotFoundError(f"Missing watch scores: {watch_scores_path}")

    payload = json.loads(watch_scores_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected {watch_scores_path} to contain a JSON object")
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        raise ValueError(f"Expected {watch_scores_path} to contain a tasks object")
    return payload


def _task_outcomes(payload: dict[str, Any]) -> dict[str, dict[str, str | bool]]:
    outcomes: dict[str, dict[str, str | bool]] = {}
    tasks = payload.get("tasks", {})
    for task_id, task_payload in tasks.items():
        status = classify_task(task_payload if isinstance(task_payload, dict) else {})
        outcomes[str(task_id)] = {
            "status": status,
            "passed": status == "pass",
        }
    return outcomes


def compare_iterations(a_payload: dict[str, Any], b_payload: dict[str, Any]) -> dict[str, Any]:
    a_tasks = _task_outcomes(a_payload)
    b_tasks = _task_outcomes(b_payload)
    shared_task_ids = sorted(a_tasks.keys() & b_tasks.keys())

    both_pass: list[str] = []
    both_fail: list[str] = []
    regressions: list[dict[str, str]] = []
    improvements: list[dict[str, str]] = []

    for task_id in shared_task_ids:
        a_passed = bool(a_tasks[task_id]["passed"])
        b_passed = bool(b_tasks[task_id]["passed"])
        if a_passed and b_passed:
            both_pass.append(task_id)
            continue
        if a_passed and not b_passed:
            regressions.append(
                {
                    "task_id": task_id,
                    "from_status": str(a_tasks[task_id]["status"]),
                    "to_status": str(b_tasks[task_id]["status"]),
                }
            )
            continue
        if not a_passed and b_passed:
            improvements.append(
                {
                    "task_id": task_id,
                    "from_status": str(a_tasks[task_id]["status"]),
                    "to_status": str(b_tasks[task_id]["status"]),
                }
            )
            continue
        both_fail.append(task_id)

    return {
        "shared_task_ids": shared_task_ids,
        "both_pass": both_pass,
        "both_fail": both_fail,
        "regressions": regressions,
        "improvements": improvements,
        "net_delta": len(improvements) - len(regressions),
    }


def _summary_lines(comparison: dict[str, Any]) -> list[str]:
    return [
        "Summary",
        f"  shared tasks : {len(comparison['shared_task_ids'])}",
        f"  both pass    : {len(comparison['both_pass'])}",
        f"  both fail    : {len(comparison['both_fail'])}",
        f"  regressions  : {len(comparison['regressions'])}",
        f"  improvements : {len(comparison['improvements'])}",
        f"  net delta    : {comparison['net_delta']:+d}",
    ]


def _change_lines(title: str, changes: list[dict[str, str]]) -> list[str]:
    if not changes:
        return [f"{title}", "  none"]

    lines = [title]
    for change in changes:
        lines.append(
            f"  {change['task_id']}: {change['from_status']} -> {change['to_status']}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare per-task pass/fail outcomes between two auto-improve iterations."
    )
    parser.add_argument("iteration_a", help="Baseline iteration: NNN or iteration-NNN.")
    parser.add_argument("iteration_b", help="Candidate iteration: NNN or iteration-NNN.")
    args = parser.parse_args(argv)

    a_root = resolve_results_root(args.iteration_a)
    b_root = resolve_results_root(args.iteration_b)
    comparison = compare_iterations(load_watch_scores(a_root), load_watch_scores(b_root))

    lines = [
        f"A: {a_root.name}",
        f"B: {b_root.name}",
        "",
        *_summary_lines(comparison),
        "",
        *_change_lines("Regressions", comparison["regressions"]),
        "",
        *_change_lines("Improvements", comparison["improvements"]),
    ]
    print("\n".join(lines))
    return 1 if comparison["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
