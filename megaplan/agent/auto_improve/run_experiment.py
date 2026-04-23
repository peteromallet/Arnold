"""Run a single auto-improve SWE-bench iteration."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
from pathlib import Path
from typing import Any

from evals.parallel import run_parallel_workers

from auto_improve.score_experiment import (
    consolidate_with_scoped_logs,
    results_root_for_iteration,
    score_iteration,
    snapshot_watch_scoring_logs,
)
from auto_improve.utils import AUTO_IMPROVE_ROOT, get_iteration_dir


REPO_ROOT = AUTO_IMPROVE_ROOT.parent
BASE_CONFIG_PATH = AUTO_IMPROVE_ROOT / "base_config.json"
TASKS_PATH = AUTO_IMPROVE_ROOT / "tasks.json"
WORKSPACES_BASE_DIR = REPO_ROOT / "evals" / "workspaces-auto-improve"
RESULTS_DIR_CONFIG_VALUE = Path("results") / "auto-improve"
WORKSPACE_DIR_CONFIG_PREFIX = Path("evals") / "workspaces-auto-improve"


def build_materialized_config(
    *,
    iteration: int,
    workers: int,
    task_count: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    config = _load_json_value(BASE_CONFIG_PATH)
    if not isinstance(config, dict):
        raise ValueError(f"Expected {BASE_CONFIG_PATH} to contain a JSON object")

    config["workers"] = workers
    config["run_name"] = f"iteration-{iteration:03d}"
    config["results_dir"] = RESULTS_DIR_CONFIG_VALUE.as_posix()
    config["workspace_dir"] = (WORKSPACE_DIR_CONFIG_PREFIX / f"iteration-{iteration:03d}").as_posix()
    config["evals_to_run"] = _load_task_ids(count=task_count, seed=seed)
    return config


def prepare_iteration(
    *,
    iteration: int,
    workers: int,
    task_count: int | None = None,
    seed: int | None = None,
) -> dict[str, Path | dict[str, Any]]:
    iteration_dir = get_iteration_dir(iteration)
    iteration_dir.mkdir(parents=True, exist_ok=True)

    config = build_materialized_config(
        iteration=iteration,
        workers=workers,
        task_count=task_count,
        seed=seed,
    )
    config_path = iteration_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    results_root = results_root_for_iteration(iteration).resolve()
    workspace_root = (WORKSPACES_BASE_DIR / f"iteration-{iteration:03d}").resolve()
    results_root.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)
    _ensure_results_symlink(iteration_dir / "results", results_root)

    return {
        "config": config,
        "config_path": config_path,
        "iteration_dir": iteration_dir,
        "results_root": results_root,
        "workspace_root": workspace_root,
    }


def run_iteration(
    *,
    iteration: int,
    workers: int,
    dry_run: bool,
    skip_scoring: bool = False,
    task_count: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    prepared = prepare_iteration(
        iteration=iteration,
        workers=workers,
        task_count=task_count,
        seed=seed,
    )
    config_path = prepared["config_path"]
    results_root = prepared["results_root"]
    workspace_root = prepared["workspace_root"]
    iteration_dir = prepared["iteration_dir"]
    config = prepared["config"]

    if dry_run:
        return {
            "mode": "dry-run",
            "iteration": iteration,
            "config_path": str(config_path),
            "iteration_dir": str(iteration_dir),
            "results_root": str(results_root),
            "workspace_root": str(workspace_root),
            "config": config,
        }

    _guard_against_stale_run_artifacts(results_root=results_root, workspace_root=workspace_root)
    os.chdir(REPO_ROOT)

    run_summary = run_parallel_workers(
        config_path,
        eval_names=None,
        workers=workers,
        scoring_mode="none" if skip_scoring else "watch",
    )

    scoped_logs_root = None
    consolidated_dir = None
    score_result = None
    if skip_scoring:
        return {
            "mode": "run",
            "iteration": iteration,
            "config_path": str(config_path),
            "results_root": str(results_root),
            "workspace_root": str(workspace_root),
            "scoped_logs_root": None,
            "consolidated_dir": None,
            "run_summary": run_summary,
            "score_result": None,
        }

    scoped_logs_root = snapshot_watch_scoring_logs(results_root)
    if scoped_logs_root is None:
        raise FileNotFoundError(
            "Watch scoring completed without a scoped log snapshot. "
            "Expected _watch_scores.json with a run_id and matching logs/run_evaluation/<run_id> artifacts."
        )

    consolidated_dir = consolidate_with_scoped_logs(results_root)
    _copy_consolidated_to_iteration(consolidated_dir, iteration_dir / "consolidated")

    score_result = score_iteration(iteration=iteration, results_root=results_root)
    return {
        "mode": "run",
        "iteration": iteration,
        "config_path": str(config_path),
        "results_root": str(results_root),
        "workspace_root": str(workspace_root),
        "scoped_logs_root": str(scoped_logs_root) if scoped_logs_root is not None else None,
        "consolidated_dir": str(consolidated_dir) if consolidated_dir is not None else None,
        "run_summary": run_summary,
        "score_result": score_result,
    }


def _load_json_value(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_task_ids(count: int | None = None, seed: int | None = None) -> list[str]:
    payload = _load_json_value(TASKS_PATH)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"Expected {TASKS_PATH} to contain a JSON list of task IDs")
    if count is None:
        return payload
    if count < 1:
        raise ValueError("--tasks must be at least 1")
    if count > len(payload):
        raise ValueError(f"--tasks cannot exceed the task pool size ({len(payload)})")
    return random.Random(seed).sample(payload, count)


def _ensure_results_symlink(link_path: Path, target_path: Path) -> None:
    if link_path.is_symlink():
        if link_path.resolve() == target_path.resolve():
            return
        link_path.unlink()
    elif link_path.exists():
        raise FileExistsError(f"Cannot create results symlink because {link_path} already exists")

    link_path.symlink_to(target_path, target_is_directory=True)


def _stale_result_artifacts(results_root: Path) -> list[Path]:
    return [
        results_root / "_task_manifest.json",
        results_root / "_watch_scores.json",
        results_root / "_swebench_predictions",
        results_root / "_scoring_logs",
        results_root / "consolidated",
    ]


def _workspace_contents(workspace_root: Path) -> list[Path]:
    if not workspace_root.exists():
        return []
    return sorted(workspace_root.iterdir(), key=lambda path: path.name)


def _guard_against_stale_run_artifacts(*, results_root: Path, workspace_root: Path) -> None:
    stale_results = _stale_result_artifacts(results_root)
    if any(path.exists() for path in stale_results):
        raise FileExistsError(
            "Iteration results directory already contains run artifacts. "
            f"Choose a new iteration or clean {results_root} before rerunning."
        )

    if _workspace_contents(workspace_root):
        raise FileExistsError(
            "Iteration workspace directory is not empty. "
            f"Choose a new iteration or clean {workspace_root} before rerunning."
        )


def _copy_consolidated_to_iteration(source_dir: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)


def _delete_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def clean_iteration(iteration: int, *, dry_run: bool = True) -> dict[str, Any]:
    iteration_dir = get_iteration_dir(iteration)
    results_root = results_root_for_iteration(iteration).resolve()
    workspace_root = (WORKSPACES_BASE_DIR / f"iteration-{iteration:03d}").resolve()

    result_artifacts = _stale_result_artifacts(results_root)
    workspace_entries = _workspace_contents(workspace_root)
    existing_result_artifacts = [path for path in result_artifacts if path.exists()]
    deletions = [*existing_result_artifacts, *workspace_entries]

    for path in result_artifacts:
        state = "exists" if path.exists() else "missing"
        print(f"[results:{state}] {path}")
    if workspace_entries:
        for path in workspace_entries:
            print(f"[workspace:exists] {path}")
    else:
        print(f"[workspace:empty] {workspace_root}")

    if not dry_run:
        for path in deletions:
            _delete_path(path)

    return {
        "mode": "clean",
        "iteration": iteration,
        "dry_run": dry_run,
        "iteration_dir": str(iteration_dir),
        "results_root": str(results_root),
        "workspace_root": str(workspace_root),
        "deleted": [str(path) for path in deletions] if not dry_run else [],
        "would_delete": [str(path) for path in deletions] if dry_run else [],
        "result_artifacts": [
            {"path": str(path), "exists": path.exists()}
            for path in result_artifacts
        ],
        "workspace_entries": [str(path) for path in workspace_entries],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an auto-improve SWE-bench iteration with watch-mode scoring."
    )
    parser.add_argument("--iteration", type=int, required=True, help="Iteration number to run.")
    parser.add_argument("--workers", type=int, default=3, help="Parallel worker count (default: 3).")
    parser.add_argument("--tasks", type=int, help="Randomly sample N tasks from auto_improve/tasks.json.")
    parser.add_argument("--seed", type=int, help="Optional RNG seed for deterministic --tasks sampling.")
    parser.add_argument("--dry-run", action="store_true", help="Write config and directories without launching workers.")
    parser.add_argument("--skip-scoring", action="store_true", help="Launch workers without watch scoring and skip post-run normalization.")
    parser.add_argument("--clean", action="store_true", help="Show or remove stale iteration artifacts instead of running.")
    parser.add_argument("--force", action="store_true", help="Apply --clean deletions. Without this flag, cleaning is a dry run.")
    args = parser.parse_args(argv)

    if args.clean:
        result = clean_iteration(args.iteration, dry_run=not args.force)
    else:
        result = run_iteration(
            iteration=args.iteration,
            workers=args.workers,
            dry_run=args.dry_run,
            skip_scoring=args.skip_scoring,
            task_count=args.tasks,
            seed=args.seed,
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
