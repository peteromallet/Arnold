"""Normalize per-iteration SWE-bench scores for the auto-improve loop."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.consolidate import consolidate

from auto_improve.utils import AUTO_IMPROVE_ROOT, get_iteration_dir


REPO_ROOT = AUTO_IMPROVE_ROOT.parent
TASKS_PATH = AUTO_IMPROVE_ROOT / "tasks.json"
DEFAULT_RESULTS_BASE = REPO_ROOT / "results" / "auto-improve"
GLOBAL_SCORING_LOGS_ROOT = REPO_ROOT / "logs" / "run_evaluation"


def results_root_for_iteration(iteration: int) -> Path:
    return DEFAULT_RESULTS_BASE / f"iteration-{iteration:03d}"


def score_iteration(
    *,
    iteration: int,
    results_root: str | Path | None = None,
) -> dict[str, Any]:
    resolved_results_root = (
        Path(results_root).expanduser().resolve()
        if results_root is not None
        else results_root_for_iteration(iteration).resolve()
    )

    iteration_dir = get_iteration_dir(iteration)
    iteration_dir.mkdir(parents=True, exist_ok=True)

    normalized_scores = build_normalized_scores(
        iteration=iteration,
        results_root=resolved_results_root,
    )
    output_path = iteration_dir / "scores.json"
    output_path.write_text(json.dumps(normalized_scores, indent=2) + "\n", encoding="utf-8")

    return {
        "iteration": iteration,
        "results_root": str(resolved_results_root),
        "scores_path": str(output_path),
        "scores": normalized_scores,
    }


def build_normalized_scores(
    *,
    iteration: int,
    results_root: str | Path,
) -> dict[str, Any]:
    resolved_results_root = Path(results_root).expanduser().resolve()
    raw_watch_scores = _load_watch_scores(resolved_results_root)
    manifest_payload = _load_manifest_payload(resolved_results_root)
    ordered_task_ids = _ordered_task_ids(manifest_payload)

    if raw_watch_scores is not None:
        return _normalize_scores_payload(
            iteration=iteration,
            raw_task_payloads=raw_watch_scores.get("tasks", {}),
            ordered_task_ids=ordered_task_ids,
            manifest_payload=manifest_payload,
            timestamp=_normalize_timestamp(raw_watch_scores.get("last_updated")),
        )

    consolidated_dir = consolidate_with_scoped_logs(resolved_results_root)
    consolidated_scores = _load_consolidated_scores(consolidated_dir)
    return _normalize_scores_payload(
        iteration=iteration,
        raw_task_payloads=consolidated_scores,
        ordered_task_ids=ordered_task_ids,
        manifest_payload=manifest_payload,
        timestamp=_consolidated_timestamp(consolidated_dir),
    )


def snapshot_watch_scoring_logs(results_root: str | Path) -> Path | None:
    resolved_results_root = Path(results_root).expanduser().resolve()
    raw_watch_scores = _load_watch_scores(resolved_results_root)
    if raw_watch_scores is None:
        return None

    run_id = raw_watch_scores.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return None

    source_root = GLOBAL_SCORING_LOGS_ROOT / run_id
    if not source_root.exists():
        return None

    destination_root = resolved_results_root / "_scoring_logs"
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / run_id
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source_root, destination)
    return destination_root


def consolidate_with_scoped_logs(results_root: str | Path) -> Path:
    resolved_results_root = Path(results_root).expanduser().resolve()
    scoped_logs_root = resolved_results_root / "_scoring_logs"
    if not scoped_logs_root.exists():
        raise FileNotFoundError(
            "Cannot run scoped consolidate fallback because the iteration results "
            f"directory is missing {scoped_logs_root}."
        )
    return consolidate(resolved_results_root, logs_root=scoped_logs_root)


def infer_iteration(results_root: str | Path) -> int | None:
    resolved_results_root = Path(results_root).expanduser().resolve()
    name = resolved_results_root.name
    if name.startswith("iteration-"):
        suffix = name.removeprefix("iteration-")
        if suffix.isdigit():
            return int(suffix)

    config_path = resolved_results_root / "_run_config.json"
    if config_path.exists():
        payload = _load_json_object(config_path)
        run_name = payload.get("run_name")
        if isinstance(run_name, str) and run_name.startswith("iteration-"):
            suffix = run_name.removeprefix("iteration-")
            if suffix.isdigit():
                return int(suffix)

    return None


def _normalize_scores_payload(
    *,
    iteration: int,
    raw_task_payloads: dict[str, Any],
    ordered_task_ids: list[str],
    manifest_payload: dict[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    if not isinstance(raw_task_payloads, dict):
        raise ValueError("Expected task payloads to be a JSON object keyed by instance ID")

    manifest_tasks = manifest_payload.get("tasks", {})
    if not isinstance(manifest_tasks, dict):
        manifest_tasks = {}

    normalized_tasks: dict[str, dict[str, Any]] = {}
    error_count = 0
    failed_count = 0
    resolved_count = 0

    for task_id in ordered_task_ids:
        raw_task = raw_task_payloads.get(task_id)
        manifest_entry = manifest_tasks.get(task_id, {})
        status = _derive_task_status(raw_task, manifest_entry)
        if status == "resolved":
            resolved_count += 1
        elif status == "error":
            error_count += 1
        else:
            failed_count += 1

        entry: dict[str, Any] = {
            "resolved": status == "resolved",
            "status": status,
        }
        if isinstance(raw_task, dict) and isinstance(raw_task.get("error"), str):
            entry["error"] = raw_task["error"]
        normalized_tasks[task_id] = entry

    total = len(normalized_tasks)
    pass_rate = round(resolved_count / total, 4) if total else 0.0
    return {
        "iteration": iteration,
        "timestamp": timestamp,
        "total": total,
        "resolved": resolved_count,
        "failed": failed_count,
        "errors": error_count,
        "pass_rate": pass_rate,
        "tasks": normalized_tasks,
    }


def _derive_task_status(raw_task: Any, manifest_entry: Any) -> str:
    if isinstance(raw_task, dict):
        resolved = raw_task.get("resolved")
        if resolved is True:
            return "resolved"
        if resolved is False:
            return "failed"
        return "error"

    manifest_status = None
    if isinstance(manifest_entry, dict):
        manifest_status = manifest_entry.get("status")

    if manifest_status == "error":
        return "error"
    if manifest_status == "done":
        return "failed"
    if manifest_status in {"pending", "claimed"}:
        return "error"
    return "failed"


def _ordered_task_ids(manifest_payload: dict[str, Any]) -> list[str]:
    default_task_ids = _load_default_task_ids()
    manifest_tasks = manifest_payload.get("tasks", {})
    manifest_task_ids = manifest_tasks.keys() if isinstance(manifest_tasks, dict) else []

    ordered = [task_id for task_id in default_task_ids]
    extras = sorted(task_id for task_id in manifest_task_ids if task_id not in set(default_task_ids))
    ordered.extend(extras)
    return ordered


def _load_default_task_ids() -> list[str]:
    payload = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"Expected {TASKS_PATH} to contain a JSON list of task IDs")
    return payload


def _load_manifest_payload(results_root: Path) -> dict[str, Any]:
    manifest_path = results_root / "_task_manifest.json"
    if not manifest_path.exists():
        return {"tasks": {}}
    return _load_json_object(manifest_path)


def _load_watch_scores(results_root: Path) -> dict[str, Any] | None:
    watch_scores_path = results_root / "_watch_scores.json"
    if not watch_scores_path.exists():
        return None
    return _load_json_object(watch_scores_path)


def _load_consolidated_scores(consolidated_dir: Path) -> dict[str, dict[str, Any]]:
    scores_path = consolidated_dir / "scores.json"
    payload = _load_json_object(scores_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected consolidated scores at {scores_path} to be a JSON object")
    return payload


def _consolidated_timestamp(consolidated_dir: Path) -> str:
    summary_path = consolidated_dir / "summary.json"
    if summary_path.exists():
        payload = _load_json_object(summary_path)
        return _normalize_timestamp(payload.get("timestamp"))
    return _utc_now()


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected {path} to contain a JSON object")
    return payload


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return _utc_now()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize iteration scores from watch scoring or scoped consolidation fallback."
    )
    parser.add_argument("--iteration", type=int, help="Iteration number to normalize into auto_improve/iterations/NNN.")
    parser.add_argument("--results-dir", help="Optional results directory override.")
    args = parser.parse_args(argv)

    if args.iteration is None and not args.results_dir:
        parser.error("Provide --iteration N or --results-dir PATH.")

    iteration = args.iteration
    if args.results_dir:
        results_root = Path(args.results_dir).expanduser().resolve()
        if iteration is None:
            iteration = infer_iteration(results_root)
            if iteration is None:
                parser.error("Could not infer iteration number from --results-dir; pass --iteration explicitly.")
    else:
        assert iteration is not None
        results_root = results_root_for_iteration(iteration).resolve()

    assert iteration is not None
    result = score_iteration(iteration=iteration, results_root=results_root)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
