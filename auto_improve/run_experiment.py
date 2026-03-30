"""Run a single auto-improve SWE-bench iteration."""

from __future__ import annotations

import argparse
import json
import os
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


def build_materialized_config(*, iteration: int, workers: int) -> dict[str, Any]:
    config = _load_json_value(BASE_CONFIG_PATH)
    if not isinstance(config, dict):
        raise ValueError(f"Expected {BASE_CONFIG_PATH} to contain a JSON object")

    config["workers"] = workers
    config["run_name"] = f"iteration-{iteration:03d}"
    config["results_dir"] = RESULTS_DIR_CONFIG_VALUE.as_posix()
    config["workspace_dir"] = (WORKSPACE_DIR_CONFIG_PREFIX / f"iteration-{iteration:03d}").as_posix()
    config["evals_to_run"] = _load_task_ids()
    return config


def prepare_iteration(*, iteration: int, workers: int) -> dict[str, Path | dict[str, Any]]:
    iteration_dir = get_iteration_dir(iteration)
    iteration_dir.mkdir(parents=True, exist_ok=True)

    config = build_materialized_config(iteration=iteration, workers=workers)
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


def run_iteration(*, iteration: int, workers: int, dry_run: bool) -> dict[str, Any]:
    prepared = prepare_iteration(iteration=iteration, workers=workers)
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
        scoring_mode="watch",
    )

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


def _load_task_ids() -> list[str]:
    payload = _load_json_value(TASKS_PATH)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"Expected {TASKS_PATH} to contain a JSON list of task IDs")
    return payload


def _ensure_results_symlink(link_path: Path, target_path: Path) -> None:
    if link_path.is_symlink():
        if link_path.resolve() == target_path.resolve():
            return
        link_path.unlink()
    elif link_path.exists():
        raise FileExistsError(f"Cannot create results symlink because {link_path} already exists")

    link_path.symlink_to(target_path, target_is_directory=True)


def _guard_against_stale_run_artifacts(*, results_root: Path, workspace_root: Path) -> None:
    stale_results = [
        results_root / "_task_manifest.json",
        results_root / "_watch_scores.json",
        results_root / "_swebench_predictions",
        results_root / "_scoring_logs",
        results_root / "consolidated",
    ]
    if any(path.exists() for path in stale_results):
        raise FileExistsError(
            "Iteration results directory already contains run artifacts. "
            f"Choose a new iteration or clean {results_root} before rerunning."
        )

    if any(workspace_root.iterdir()):
        raise FileExistsError(
            "Iteration workspace directory is not empty. "
            f"Choose a new iteration or clean {workspace_root} before rerunning."
        )


def _copy_consolidated_to_iteration(source_dir: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an auto-improve SWE-bench iteration with watch-mode scoring."
    )
    parser.add_argument("--iteration", type=int, required=True, help="Iteration number to run.")
    parser.add_argument("--workers", type=int, default=3, help="Parallel worker count (default: 3).")
    parser.add_argument("--dry-run", action="store_true", help="Write config and directories without launching workers.")
    args = parser.parse_args(argv)

    result = run_iteration(iteration=args.iteration, workers=args.workers, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
