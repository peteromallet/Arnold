"""Parallel worker orchestration for SWE-bench eval runs.

Launch separate invocations per model configuration, each with its own
``run_name`` and ``workspace_dir``. That keeps manifests, worker workspaces,
and combined predictions isolated even when multiple model stacks process the
same SWE-bench task list at the same time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


MANIFEST_WAIT_TIMEOUT_SECONDS = 4 * 60 * 60
MANIFEST_POLL_INTERVAL_SECONDS = 30
DEFAULT_CLAIM_BATCH_SIZE = 10
WATCH_JOIN_TIMEOUT_SECONDS = 60


def run_parallel_workers(
    config_path: str | Path,
    eval_names: list[str] | None,
    workers: int,
    scoring_mode: str = "batch",
) -> dict[str, Any]:
    """Run SWE-bench evals across N parallel workers, then score predictions."""
    from evals.config import load_config
    from evals.manifest import TaskManifest
    from evals.run_evals import _resolve_benchmark

    if scoring_mode not in {"batch", "watch"}:
        raise ValueError(f"Unsupported scoring_mode: {scoring_mode}")

    config = load_config(config_path)
    benchmark = _resolve_benchmark(config)
    source_root = benchmark.setup_source(config)
    all_tasks = benchmark.list_tasks(source_root, config.evals_to_run, eval_names)

    results_root = Path(config.results_dir).expanduser().resolve()
    if config.run_name:
        results_root = results_root / config.run_name
    results_root.mkdir(parents=True, exist_ok=True)

    manifest_path = results_root / "_task_manifest.json"
    canonical_config_path = results_root / "_run_config.json"
    predictions_dir = results_root / "_swebench_predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    manifest = TaskManifest.create(manifest_path, all_tasks)
    canonical_config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    canonical_config_path.write_text(json.dumps(canonical_config, indent=2), encoding="utf-8")
    worker_ids = [f"worker-{i}" for i in range(workers)]
    manifest.reserve_specific_worker_ids(worker_ids)

    print(f"=== Parallel SWE-bench Run ===", file=sys.stderr)
    print(f"Tasks: {len(all_tasks)} | Workers: {workers}", file=sys.stderr)
    print(f"Manifest: {manifest_path}", file=sys.stderr)
    print(f"Canonical config: {canonical_config_path}", file=sys.stderr)
    print(f"Predictions dir: {predictions_dir}", file=sys.stderr)

    worker_procs, temp_configs, worker_log_dir = _launch_worker_processes(
        canonical_config_path,
        config.workspace_dir,
        worker_ids,
        predictions_dir,
        manifest_path,
        results_root,
    )

    # Ensure all worker process trees get killed on exit/crash
    import atexit
    atexit.register(_kill_workers, worker_procs)

    watch_thread = None
    watch_result_holder: dict[str, Any] = {}
    watch_error_holder: dict[str, BaseException] = {}
    if scoring_mode == "watch":
        import threading
        from evals.watch_scoring import watch_and_score

        def _run_watch_scoring() -> None:
            try:
                watch_result_holder["result"] = watch_and_score(results_root)
            except BaseException as exc:  # pragma: no cover - surfaced in main thread
                watch_error_holder["error"] = exc

        print("\n=== Watch Scoring ===", file=sys.stderr)
        watch_thread = threading.Thread(
            target=_run_watch_scoring,
            name=f"watch-score-{results_root.name}",
            daemon=True,
        )
        watch_thread.start()

    _wait_for_workers(worker_procs, worker_log_dir)

    if scoring_mode == "watch":
        for tc in temp_configs:
            tc.unlink(missing_ok=True)
        watch_join_timeout = WATCH_JOIN_TIMEOUT_SECONDS
        if watch_thread is not None:
            watch_thread.join(timeout=watch_join_timeout)
        if watch_thread is not None and watch_thread.is_alive():
            print(
                "Watch scoring did not finish within the post-worker join window; "
                "using the latest partial _watch_scores.json snapshot.",
                file=sys.stderr,
            )
        if "error" in watch_error_holder:
            raise watch_error_holder["error"]

        watch_scores_path = results_root / "_watch_scores.json"
        if "result" in watch_result_holder:
            score_result = watch_result_holder["result"]
        elif watch_scores_path.exists():
            score_result = json.loads(watch_scores_path.read_text(encoding="utf-8"))
        else:
            score_result = {
                "manifest_total": len(all_tasks),
                "scored": 0,
                "resolved": 0,
                "failed": 0,
                "errors": 0,
                "pass_rate": 0.0,
                "stop_reason": "missing_watch_scores",
                "tasks": {},
            }

        summary = _merge_summaries(results_root, config, all_tasks, score_result)
        summary_path = results_root / "summary_parallel.json"
        summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"\nSummary: {summary_path}", file=sys.stderr)
        return summary

    manifest_wait_timeout = int(
        os.environ.get("HERMES_SWEBENCH_MANIFEST_WAIT_SECONDS", str(MANIFEST_WAIT_TIMEOUT_SECONDS))
    )
    manifest_deadline = time.monotonic() + manifest_wait_timeout
    while not manifest.all_done():
        if time.monotonic() >= manifest_deadline:
            stranded_ids = _stranded_task_ids(manifest_path)
            print(
                "Manifest wait timed out after "
                f"{manifest_wait_timeout}s; proceeding with completed predictions only.",
                file=sys.stderr,
            )
            if stranded_ids:
                print(
                    f"  Stranded task IDs ({len(stranded_ids)}): {', '.join(stranded_ids)}",
                    file=sys.stderr,
                )
            break
        time.sleep(MANIFEST_POLL_INTERVAL_SECONDS)

    # Combine predictions
    combined_path = predictions_dir / "all_predictions.jsonl"
    prediction_count = _combine_predictions(
        predictions_dir,
        combined_path,
        valid_ids=manifest.done_task_ids(),
    )
    print(f"\nCombined {prediction_count} predictions into {combined_path}", file=sys.stderr)

    # Clean up temp configs once worker startup is no longer needed.
    for tc in temp_configs:
        tc.unlink(missing_ok=True)

    if prediction_count == 0:
        print("No predictions generated — skipping scoring", file=sys.stderr)
        return {"predictions": 0, "workers": workers, "tasks": len(all_tasks)}

    # Batch score with SWE-bench
    print(f"\n=== Batch Scoring ({prediction_count} predictions) ===", file=sys.stderr)
    scoring_workers = min(workers, 4)  # Don't overload Docker
    score_result = _run_batch_scoring(combined_path, scoring_workers, results_root)

    # Merge worker summaries
    summary = _merge_summaries(results_root, config, all_tasks, score_result)
    summary_path = results_root / f"summary_parallel.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\nSummary: {summary_path}", file=sys.stderr)

    return summary


def join_parallel_run(
    config_path: str | Path | None,
    run_name: str,
    new_workers: int,
) -> dict[str, Any]:
    """Attach more workers to an existing manifest-backed parallel run."""
    from evals.config import DEFAULT_RESULTS_DIR, load_config
    from evals.manifest import TaskManifest

    if new_workers < 1:
        raise ValueError("--add-workers must be at least 1")

    if config_path:
        requested_config = load_config(config_path)
        results_root = Path(requested_config.results_dir).expanduser().resolve() / run_name
    else:
        requested_config = None
        results_root = Path(DEFAULT_RESULTS_DIR).expanduser().resolve() / run_name

    manifest_path = results_root / "_task_manifest.json"
    canonical_config_path = results_root / "_run_config.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Join target is missing manifest: {manifest_path}. Start the run with manifest-backed parallel mode first."
        )
    if not canonical_config_path.exists():
        raise FileNotFoundError(
            f"Join target is missing canonical config: {canonical_config_path}."
        )

    canonical_config = load_config(canonical_config_path)
    if canonical_config.benchmark != "swe-bench":
        raise ValueError("--join is only supported for SWE-bench parallel runs")

    if requested_config is not None:
        _warn_join_config_mismatch(requested_config, canonical_config, canonical_config_path)

    manifest = TaskManifest.load(manifest_path)
    manifest_summary = manifest.summary()
    remaining = manifest_summary.get("pending", 0) + manifest_summary.get("claimed", 0)
    print(f"=== Join Parallel SWE-bench Run ===", file=sys.stderr)
    print(f"Run: {run_name}", file=sys.stderr)
    print(f"Manifest: {manifest_path}", file=sys.stderr)
    print(
        f"Remaining tasks: {remaining} "
        f"(pending={manifest_summary.get('pending', 0)}, claimed={manifest_summary.get('claimed', 0)}, done={manifest_summary.get('done', 0)})",
        file=sys.stderr,
    )

    worker_ids = manifest.reserve_worker_ids(new_workers)
    print(f"Allocated workers: {', '.join(worker_ids)}", file=sys.stderr)

    predictions_dir_value = getattr(canonical_config, "predictions_dir", "")
    predictions_dir = (
        Path(predictions_dir_value).expanduser().resolve()
        if predictions_dir_value
        else results_root / "_swebench_predictions"
    )
    predictions_dir.mkdir(parents=True, exist_ok=True)

    worker_procs, temp_configs, worker_log_dir = _launch_worker_processes(
        canonical_config_path,
        canonical_config.workspace_dir,
        worker_ids,
        predictions_dir,
        manifest_path,
        results_root,
    )
    completed = _wait_for_workers(worker_procs, worker_log_dir)

    for tc in temp_configs:
        tc.unlink(missing_ok=True)

    return {
        "mode": "parallel-join",
        "run_name": run_name,
        "results_root": str(results_root),
        "added_workers": len(worker_ids),
        "worker_ids": worker_ids,
        "manifest": manifest.summary(),
        "worker_exit_codes": completed,
    }


def _launch_worker_processes(
    original_config_path: str | Path,
    workspace_dir: str,
    worker_ids: list[str],
    predictions_dir: Path,
    manifest_path: Path,
    results_root: Path,
) -> tuple[list[tuple[str, subprocess.Popen, Path]], list[Path], Path]:
    worker_procs: list[tuple[str, subprocess.Popen, Path]] = []
    temp_configs: list[Path] = []
    worker_log_dir = results_root / "_worker_logs"
    worker_log_dir.mkdir(parents=True, exist_ok=True)

    for worker_id in worker_ids:
        temp_config = _write_worker_config(
            original_config_path,
            worker_id,
            predictions_dir,
            manifest_path,
            num_workers=len(worker_ids),
        )
        temp_configs.append(temp_config)
        worker_env = os.environ.copy()
        # Ensure PYTHONPATH includes hermes-agent and megaplan
        hermes_root = str(Path(__file__).resolve().parent.parent)
        megaplan_root = str(Path(__file__).resolve().parent.parent.parent / "megaplan")
        python_paths = [hermes_root, megaplan_root]
        existing = worker_env.get("PYTHONPATH", "")
        if existing:
            python_paths.append(existing)
        worker_env["PYTHONPATH"] = os.pathsep.join(python_paths)
        worker_workspace = Path(workspace_dir).expanduser().resolve() / worker_id
        worker_hermes_home = worker_workspace / "_hermes_home"
        worker_hermes_home.mkdir(parents=True, exist_ok=True)

        real_hermes_home = Path.home() / ".hermes"
        real_env_file = real_hermes_home / ".env"
        if real_env_file.exists():
            import shutil

            shutil.copy2(real_env_file, worker_hermes_home / ".env")
        worker_env["HERMES_HOME"] = str(worker_hermes_home)

        worker_stdout = open(worker_log_dir / f"{worker_id}.stdout.log", "w")
        worker_stderr = open(worker_log_dir / f"{worker_id}.stderr.log", "w")
        proc = subprocess.Popen(
            [sys.executable, "-m", "evals.run_evals", "--config", str(temp_config), "-v"],
            env=worker_env,
            stdout=worker_stdout,
            stderr=worker_stderr,
            cwd=str(Path(__file__).resolve().parent.parent),
            start_new_session=True,  # Own process group — kill -PGID kills all descendants
        )
        worker_procs.append((worker_id, proc, temp_config))
        print(f"  {worker_id} started (PID {proc.pid})", file=sys.stderr)

    return worker_procs, temp_configs, worker_log_dir


def _kill_workers(worker_procs: list[tuple[str, subprocess.Popen, Path]]) -> None:
    """Kill all worker processes and their entire process trees."""
    import signal
    for worker_id, proc, _ in worker_procs:
        if proc.poll() is not None:
            continue
        try:
            # Kill the entire process group (worker + megaplan + hermes descendants)
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    # Give them a moment, then force kill any survivors
    time.sleep(2)
    for worker_id, proc, _ in worker_procs:
        if proc.poll() is not None:
            continue
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _wait_for_workers(
    worker_procs: list[tuple[str, subprocess.Popen, Path]],
    worker_log_dir: Path,
) -> dict[str, int]:
    print(f"\nWaiting for {len(worker_procs)} workers...", file=sys.stderr)
    completed: dict[str, int] = {}
    while len(completed) < len(worker_procs):
        for worker_id, proc, _ in worker_procs:
            if worker_id in completed:
                continue
            retcode = proc.poll()
            if retcode is not None:
                completed[worker_id] = retcode
                status = "OK" if retcode == 0 else f"FAILED (exit {retcode})"
                print(f"  Worker {worker_id}: {status}", file=sys.stderr)
                if retcode != 0:
                    log_path = worker_log_dir / f"{worker_id}.stderr.log"
                    if log_path.exists():
                        tail = log_path.read_text(encoding="utf-8", errors="replace")[-200:]
                        print(f"    {tail}", file=sys.stderr)
        if len(completed) < len(worker_procs):
            time.sleep(10)
    return completed


def _write_worker_config(
    original_config_path: str | Path,
    worker_id: str,
    predictions_dir: Path,
    manifest_path: Path,
    num_workers: int = 3,
) -> Path:
    """Write a temp config JSON for a worker subprocess."""
    original = json.loads(Path(original_config_path).read_text(encoding="utf-8"))
    parent_run_name = original.get("run_name", "parallel")
    original["workers"] = 1  # Prevent recursive spawning
    original["swebench_patch_only"] = True
    original["evals_to_run"] = []
    original["workspace_dir"] = str(
        Path(original.get("workspace_dir", "evals/workspaces")).expanduser().resolve() / worker_id
    )
    original["run_name"] = f"{parent_run_name}/{worker_id}"
    original["manifest_path"] = str(manifest_path)
    original["worker_id"] = worker_id
    # Claim small batches so all workers get tasks. With 20 tasks and 3 workers,
    # batch_size=10 means 2 workers grab everything and the 3rd gets nothing.
    original["claim_batch_size"] = max(1, DEFAULT_CLAIM_BATCH_SIZE // num_workers)
    original["predictions_dir"] = str(predictions_dir)

    temp = Path(tempfile.mktemp(suffix=f"-worker-{worker_id}.json", prefix="swebench-"))
    temp.write_text(json.dumps(original, indent=2), encoding="utf-8")
    return temp


def _combine_predictions(
    predictions_dir: Path,
    output_path: Path,
    valid_ids: set[str] | None = None,
) -> int:
    """Combine all per-task prediction JSONL files into one."""
    count = 0
    seen_ids: set[str] = set()
    with open(output_path, "w", encoding="utf-8") as out:
        for jsonl_file in sorted(predictions_dir.glob("*.jsonl")):
            if jsonl_file.name == "all_predictions.jsonl":
                continue
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    pred = json.loads(line)
                    iid = pred.get("instance_id", "")
                    if valid_ids is not None and iid not in valid_ids:
                        continue
                    if iid and iid not in seen_ids:
                        seen_ids.add(iid)
                        out.write(line + "\n")
                        count += 1
                except json.JSONDecodeError:
                    continue
    return count


def _stranded_task_ids(manifest_path: Path) -> list[str]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks = payload.get("tasks", {})
    stranded = [
        instance_id
        for instance_id, task in tasks.items()
        if task.get("status") in {"pending", "claimed"}
    ]
    return sorted(stranded)


def _warn_join_config_mismatch(
    requested_config: Any,
    canonical_config: Any,
    canonical_config_path: str | Path,
) -> None:
    keys = ("benchmark", "swebench_dataset", "workspace_dir", "results_dir", "models")
    mismatches = [
        key
        for key in keys
        if getattr(requested_config, key, None) != getattr(canonical_config, key, None)
    ]
    if not mismatches:
        return

    joined = ", ".join(mismatches)
    print(
        "WARNING: --config does not match the canonical _run_config.json for this run "
        f"({joined}). Joining with the canonical run config from {canonical_config_path}.",
        file=sys.stderr,
    )


def _run_batch_scoring(
    predictions_path: Path,
    max_workers: int,
    results_root: Path,
) -> dict[str, Any]:
    """Run SWE-bench evaluation on combined predictions."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "swebench.harness.run_evaluation",
                "--predictions_path", str(predictions_path),
                "--max_workers", str(max_workers),
                "--run_id", "hermes-parallel",
                "--namespace", "",
            ],
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hours for batch scoring
            check=False,
        )
        print(result.stdout[-1000:] if result.stdout else "", file=sys.stderr)
        if result.stderr:
            print(result.stderr[-500:], file=sys.stderr)

        # Parse results
        return {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-1000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "error": "batch scoring timed out after 2 hours"}
    except Exception as exc:
        return {"returncode": -1, "error": str(exc)}


def _merge_summaries(
    results_root: Path,
    config: Any,
    all_tasks: list[str],
    score_result: dict[str, Any],
) -> dict[str, Any]:
    """Merge per-worker summaries and scoring results."""
    worker_summaries = []
    for summary_file in sorted(results_root.rglob("summary_*.json")):
        if summary_file.name == "summary_parallel.json":
            continue
        try:
            worker_summaries.append(json.loads(summary_file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue

    # Collect all eval entries
    all_evals = []
    for ws in worker_summaries:
        all_evals.extend(ws.get("evals", []))

    return {
        "mode": "parallel",
        "workers": config.workers,
        "total_tasks": len(all_tasks),
        "predictions_generated": len(all_evals),
        "scoring": score_result,
        "evals": sorted(all_evals, key=lambda e: e.get("eval_name", "")),
    }
