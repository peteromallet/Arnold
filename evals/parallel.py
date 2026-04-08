"""Parallel worker orchestration for SWE-bench eval runs.

Launch separate invocations per model configuration, each with its own
``run_name`` and ``workspace_dir``. That keeps manifests, worker workspaces,
and combined predictions isolated even when multiple model stacks process the
same SWE-bench task list at the same time.
"""

from __future__ import annotations

from collections import Counter
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_improve.probe_keys import alive_keys, format_status_table, load_candidate_keys, probe_keys


MANIFEST_WAIT_TIMEOUT_SECONDS = 4 * 60 * 60
MANIFEST_POLL_INTERVAL_SECONDS = 30
DEFAULT_CLAIM_BATCH_SIZE = 10
WATCH_JOIN_TIMEOUT_SECONDS = 60
PIDFILE_NAME = "_pidfile.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pidfile_path(results_root: Path) -> Path:
    return results_root / PIDFILE_NAME


def _default_pidfile_payload(iteration: str) -> dict[str, Any]:
    return {
        "loop_pid": None,
        "workers": [],
        "scorer_pid": None,
        "started_at": _utc_now(),
        "iteration": iteration,
    }


def _load_pidfile(path: Path, *, iteration: str) -> dict[str, Any]:
    if not path.exists():
        return _default_pidfile_payload(iteration)

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected {path} to contain a JSON object")

    workers = payload.get("workers")
    if not isinstance(workers, list):
        workers = []

    loop_pid = payload.get("loop_pid")
    scorer_pid = payload.get("scorer_pid")
    started_at = payload.get("started_at")
    payload_iteration = payload.get("iteration")
    return {
        "loop_pid": loop_pid if isinstance(loop_pid, int) else None,
        "workers": [entry for entry in workers if isinstance(entry, dict)],
        "scorer_pid": scorer_pid if isinstance(scorer_pid, int) else None,
        "started_at": started_at if isinstance(started_at, str) and started_at.strip() else _utc_now(),
        "iteration": payload_iteration if isinstance(payload_iteration, str) and payload_iteration.strip() else iteration,
    }


def _write_pidfile(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix="_pidfile.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _worker_pid_entry(worker_id: str, proc: subprocess.Popen[Any]) -> dict[str, int | str]:
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, PermissionError):
        pgid = proc.pid
    return {
        "worker_id": worker_id,
        "pid": proc.pid,
        "pgid": pgid,
    }


def _record_pidfile_workers(
    results_root: Path,
    worker_procs: list[tuple[str, subprocess.Popen[Any], Path]],
    *,
    loop_pid: int | None,
    replace_workers: bool,
) -> None:
    path = _pidfile_path(results_root)
    iteration = results_root.name
    payload = _load_pidfile(path, iteration=iteration)
    payload["iteration"] = iteration
    if loop_pid is not None:
        payload["loop_pid"] = loop_pid
        payload["started_at"] = _utc_now()

    new_entries = [_worker_pid_entry(worker_id, proc) for worker_id, proc, _ in worker_procs]
    if replace_workers:
        payload["workers"] = new_entries
    else:
        new_worker_ids = {entry["worker_id"] for entry in new_entries}
        existing_entries = [
            entry
            for entry in payload["workers"]
            if isinstance(entry, dict) and entry.get("worker_id") not in new_worker_ids
        ]
        payload["workers"] = [*existing_entries, *new_entries]

    _write_pidfile(path, payload)


def _remove_pidfile_workers(results_root: Path, worker_ids: list[str]) -> None:
    path = _pidfile_path(results_root)
    if not path.exists():
        return

    payload = _load_pidfile(path, iteration=results_root.name)
    worker_id_set = set(worker_ids)
    payload["workers"] = [
        entry
        for entry in payload["workers"]
        if isinstance(entry, dict) and entry.get("worker_id") not in worker_id_set
    ]
    _write_pidfile(path, payload)


def _set_pidfile_scorer_pid(results_root: Path, scorer_pid: int | None) -> None:
    path = _pidfile_path(results_root)
    payload = _load_pidfile(path, iteration=results_root.name)
    payload["scorer_pid"] = scorer_pid
    _write_pidfile(path, payload)


def _clear_pidfile_runtime_state(results_root: Path, *, clear_scorer: bool = False) -> None:
    path = _pidfile_path(results_root)
    if not path.exists():
        return

    payload = _load_pidfile(path, iteration=results_root.name)
    payload["loop_pid"] = None
    payload["workers"] = []
    if clear_scorer:
        payload["scorer_pid"] = None
    _write_pidfile(path, payload)


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

    if scoring_mode not in {"batch", "watch", "none"}:
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
    manifest = TaskManifest.load_or_create(manifest_path, all_tasks)
    requeued_claims = manifest.requeue_dead_claimed(results_root / "_pidfile.json")
    canonical_config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    canonical_config_path.write_text(json.dumps(canonical_config, indent=2), encoding="utf-8")
    api_keys = _load_api_keys()
    api_keys, workers = _probe_and_filter_keys(api_keys, workers)
    if workers == 0:
        print("No alive keys — aborting parent", file=sys.stderr)
        summary = {
            "mode": "parallel",
            "workers": 0,
            "total_tasks": len(all_tasks),
            "prediction_count": 0,
            "worker_exit_codes": {},
            "all_workers_failed": True,
            "reason": "no_alive_keys",
        }
        summary_path = results_root / "summary_parallel.json"
        summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"\nSummary: {summary_path}", file=sys.stderr)
        return summary
    worker_ids = [f"worker-{i}" for i in range(workers)]
    manifest.reserve_specific_worker_ids(worker_ids)

    print(f"=== Parallel SWE-bench Run ===", file=sys.stderr)
    print(f"Tasks: {len(all_tasks)} | Workers: {workers}", file=sys.stderr)
    print(f"Manifest: {manifest_path}", file=sys.stderr)
    print(f"Canonical config: {canonical_config_path}", file=sys.stderr)
    print(f"Predictions dir: {predictions_dir}", file=sys.stderr)
    if requeued_claims:
        print(
            f"Re-queued {len(requeued_claims)} previously claimed tasks on startup: "
            f"{', '.join(requeued_claims)}",
            file=sys.stderr,
        )

    worker_procs, temp_configs, worker_log_dir = _launch_worker_processes(
        canonical_config_path,
        config.workspace_dir,
        worker_ids,
        predictions_dir,
        manifest_path,
        results_root,
        api_keys=api_keys,
        replace_pidfile_workers=True,
    )

    # Ensure all worker process trees get killed on exit/crash
    import atexit
    atexit.register(_kill_workers, worker_procs, results_root)
    try:
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

        worker_exit_codes = _wait_for_workers(worker_procs, worker_log_dir, manifest_path)
        m_summary = TaskManifest.load(manifest_path).summary()
        pending = m_summary.get("pending", 0)
        claimed = m_summary.get("claimed", 0)
        manifest_done = (pending + claimed) == 0
        all_workers_failed = not manifest_done

        if all_workers_failed:
            for tc in temp_configs:
                tc.unlink(missing_ok=True)
            summary = {
                "mode": "parallel",
                "workers": workers,
                "total_tasks": len(all_tasks),
                "prediction_count": 0,
                "worker_exit_codes": worker_exit_codes,
                "manifest": m_summary,
                "all_workers_failed": True,
                "reason": f"workers exited with manifest pending={pending} claimed={claimed}",
            }
            summary_path = results_root / "summary_parallel.json"
            summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
            print(f"\nSummary: {summary_path}", file=sys.stderr)
            return summary

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

        # Clean up temp configs once worker startup is no longer needed.
        for tc in temp_configs:
            tc.unlink(missing_ok=True)

        if scoring_mode == "none":
            combined_path = predictions_dir / "all_predictions.jsonl"
            done_ids = manifest.done_task_ids()
            prediction_count = _combine_predictions(
                predictions_dir,
                combined_path,
                valid_ids=done_ids or None,
            )
            print(f"\nCombined {prediction_count} predictions into {combined_path}", file=sys.stderr)
            summary = {
                "mode": "parallel",
                "workers": workers,
                "total_tasks": len(all_tasks),
                "prediction_count": prediction_count,
                "worker_exit_codes": worker_exit_codes,
                "scoring": {"mode": "none", "skipped": True},
            }
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
    finally:
        atexit.unregister(_kill_workers)
        _clear_pidfile_runtime_state(results_root)


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

    api_keys = _load_api_keys()
    api_keys, new_workers = _probe_and_filter_keys(api_keys, new_workers)
    if new_workers == 0:
        print("No alive keys — aborting join", file=sys.stderr)
        return {
            "mode": "parallel-join",
            "run_name": run_name,
            "results_root": str(results_root),
            "added_workers": 0,
            "worker_ids": [],
            "manifest": manifest.summary(),
            "worker_exit_codes": {},
            "all_workers_failed": True,
            "reason": "no_alive_keys",
        }
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
        api_keys=api_keys,
        replace_pidfile_workers=False,
    )
    completed = _wait_for_workers(worker_procs, worker_log_dir)
    _remove_pidfile_workers(results_root, worker_ids)

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


def _clean_editable_installs() -> None:
    """Remove editable .pth files leaked by executor pip install -e commands.

    The executor's terminal tool runs in the system Python. When the model
    runs `pip install -e .` to set up a workspace for testing, the editable
    install goes to the global site-packages and can break dependencies
    (e.g., anyio downgrade from a dev sphinx/pytest install).
    """
    import site
    site_packages = Path(site.getsitepackages()[0])
    removed = []
    for pth in site_packages.glob("__editable__*.pth"):
        pth.unlink()
        removed.append(pth.name)
    # Also clean editable finder modules and nspkg.pth files leaked by eval repos
    for pth in site_packages.glob("__editable__*_finder.py"):
        pth.unlink()
        removed.append(pth.name)
    for pth in site_packages.glob("*nspkg.pth"):
        pth.unlink()
        removed.append(pth.name)
    if removed:
        print(f"[parallel] Cleaned {len(removed)} editable installs: {', '.join(removed)}", file=sys.stderr)
    # Also force-reinstall anyio to ensure it's not broken
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "anyio>=4.0", "--force-reinstall", "--quiet"],
        capture_output=True, check=False,
    )


def _preflight_check_megaplan() -> None:
    """Verify megaplan imports correctly before spawning workers."""
    result = subprocess.run(
        [sys.executable, "-c", "from megaplan.cli import cli_entry; print('ok')"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Megaplan pre-flight check failed — fix before running:\n{result.stderr}"
        )
    print("[parallel] Megaplan pre-flight check passed", file=sys.stderr)


def _load_api_keys() -> list[str]:
    """Load candidate keys for launch-time probing and worker-count sizing."""
    # Probe and launcher share load_candidate_keys() so capacity decisions are
    # based on the same pool. Non-default base_url entries in api_keys.json are
    # not independently probed here; that limitation is explicitly out of scope.
    try:
        return load_candidate_keys(provider="zhipu")
    except Exception:
        return []


def _probe_and_filter_keys(
    api_keys: list[str],
    requested_workers: int,
) -> tuple[list[str], int]:
    if not api_keys:
        return api_keys, requested_workers

    results = probe_keys(api_keys, provider="zhipu")
    for result in results:
        reset_suffix = f" reset {result.reset_at}" if result.reset_at else ""
        print(f"  [{result.status}] {result.masked_key}{reset_suffix}", file=sys.stderr)

    alive_key_set = set(alive_keys(results))
    alive_entries = [entry for entry in api_keys if entry in alive_key_set]
    if not alive_entries:
        print(f"[parallel] No alive API keys.\n{format_status_table(results)}", file=sys.stderr)
        return [], 0

    if len(alive_entries) < requested_workers:
        dead_counts = Counter(result.status for result in results if result.status != "alive")
        category_summary = ", ".join(
            f"{dead_counts[status]} {status}"
            for status in ("exhausted", "invalid", "unreachable")
            if dead_counts[status]
        )
        dead_total = len(results) - len(alive_entries)
        print(
            f"[parallel] WARNING: {dead_total}/{len(results)} keys dead ({category_summary}). "
            f"Scaling workers {requested_workers} -> {len(alive_entries)}.",
            file=sys.stderr,
        )
        return alive_entries, len(alive_entries)

    return alive_entries, requested_workers


def _launch_worker_processes(
    original_config_path: str | Path,
    workspace_dir: str,
    worker_ids: list[str],
    predictions_dir: Path,
    manifest_path: Path,
    results_root: Path,
    *,
    api_keys: list[str] | None = None,
    replace_pidfile_workers: bool = False,
) -> tuple[list[tuple[str, subprocess.Popen, Path]], list[Path], Path]:
    _clean_editable_installs()
    _preflight_check_megaplan()
    worker_procs: list[tuple[str, subprocess.Popen, Path]] = []
    temp_configs: list[Path] = []
    worker_log_dir = results_root / "_worker_logs"
    worker_log_dir.mkdir(parents=True, exist_ok=True)

    # API keys are still probed at launch time for worker-count sizing, but
    # workers now resolve keys from the shared megaplan pool at runtime.
    api_keys = api_keys if api_keys is not None else _load_api_keys()
    if api_keys:
        print(
            f"[parallel] {len(api_keys)} alive keys available; workers draw from shared pool",
            file=sys.stderr,
        )

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

        # Guard against executor pip installs polluting global site-packages.
        # The model sometimes runs `pip install -e .` which creates __editable__
        # .pth files that break dependencies (anyio/openai). Tell pip to install
        # into the workspace, not the global Python.
        worker_env["PIP_USER"] = "1"
        worker_env["PYTHONUSERBASE"] = str(worker_workspace / "_pip_user")

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

    _record_pidfile_workers(
        results_root,
        worker_procs,
        loop_pid=os.getpid() if replace_pidfile_workers else None,
        replace_workers=replace_pidfile_workers,
    )

    return worker_procs, temp_configs, worker_log_dir


def _kill_workers(
    worker_procs: list[tuple[str, subprocess.Popen, Path]],
    results_root: Path | None = None,
) -> None:
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
    if results_root is not None:
        _clear_pidfile_runtime_state(results_root)


def _wait_for_workers(
    worker_procs: list[tuple[str, subprocess.Popen, Path]],
    worker_log_dir: Path,
    manifest_path: Path | None = None,
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
                    # Requeue tasks claimed by this crashed worker
                    if manifest_path is not None:
                        try:
                            from evals.manifest import TaskManifest
                            manifest = TaskManifest.load(manifest_path)
                            requeued = manifest.requeue_stale_claimed({worker_id})
                            if requeued:
                                print(
                                    f"  Re-queued {len(requeued)} tasks from crashed {worker_id}: "
                                    f"{', '.join(requeued)}",
                                    file=sys.stderr,
                                )
                        except Exception as exc:
                            print(f"  Warning: failed to requeue tasks from {worker_id}: {exc}", file=sys.stderr)
        if len(completed) < len(worker_procs):
            time.sleep(2)
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
