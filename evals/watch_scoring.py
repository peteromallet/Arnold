"""Incremental watch-mode scoring for manifest-backed SWE-bench runs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.manifest import TaskManifest


DEFAULT_POLL_INTERVAL = 15
DEFAULT_TIMEOUT = 4 * 60 * 60
SCORE_TIMEOUT = 30 * 60
KEEP_IMAGE_PREFIXES = ("sweb.base.", "sweb.env.")


def watch_and_score(
    results_root: str | Path,
    *,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    timeout: int = DEFAULT_TIMEOUT,
    cleanup_docker: bool = True,
    use_modal: bool = True,
) -> dict[str, Any]:
    """Poll for manifest-complete predictions and score them one at a time."""
    root = Path(results_root).expanduser().resolve()
    manifest_path = root / "_task_manifest.json"
    predictions_dir = root / "_swebench_predictions"
    scores_path = root / "_watch_scores.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Watch scorer: missing manifest at {manifest_path}")
    if not predictions_dir.exists():
        raise FileNotFoundError(f"Watch scorer: missing predictions dir at {predictions_dir}")
    manifest = TaskManifest.load(manifest_path)
    run_id = f"hermes-watch-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"

    scores_data = _load_scores_data(scores_path)
    scored_ids = set(scores_data.get("tasks", {}))
    started_at = time.monotonic()
    scores_data["run_id"] = run_id

    scores_data = _refresh_scores_summary(manifest, scores_data)
    _write_incremental_results(root, scores_data)

    stop_reason = "completed"
    try:
        while True:
            manifest_summary = manifest.summary()
            done_ids = manifest.done_task_ids()
            available_predictions = {
                pred_path.stem: pred_path
                for pred_path in predictions_dir.glob("*.jsonl")
                if pred_path.name != "all_predictions.jsonl"
            }
            # Retry tasks that scored None (transient scoring failures) — up to 3 attempts
            retryable_ids = set()
            exhausted_retry_ids = set()
            for iid, entry in scores_data.get("tasks", {}).items():
                if isinstance(entry, dict) and entry.get("resolved") is None:
                    attempts = entry.get("attempts", 1)
                    if attempts < 3 and iid in available_predictions:
                        retryable_ids.add(iid)
                    elif attempts >= 3:
                        exhausted_retry_ids.add(iid)
                        # Mark exhausted tasks for manual review
                        if not entry.get("review"):
                            entry["review"] = {
                                "category": "scoring_exhausted",
                                "explanation": f"Scoring failed {attempts} times: {entry.get('error', 'unknown error')}",
                                "excluded_from_pass_rate": False,
                                "reviewed_by": "auto",
                                "reviewed_at": _utc_now(),
                                "needs_manual_review": True,
                            }
                            _write_incremental_results(root, scores_data)

            scorable_ids = sorted(
                instance_id
                for instance_id in done_ids
                if (
                    (
                        instance_id not in scored_ids
                        and instance_id not in exhausted_retry_ids
                    )
                    or instance_id in retryable_ids
                )
                and instance_id in available_predictions
            )

            for batch_start in range(0, len(scorable_ids), 2):
              batch = scorable_ids[batch_start:batch_start + 2]
              # Score up to 2 tasks in parallel: first on local Docker, second on Modal
              import concurrent.futures
              futures: dict[concurrent.futures.Future, str] = {}
              with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                  for i, instance_id in enumerate(batch):
                      use_local = (i == 0)  # first task goes local, second goes Modal
                      futures[pool.submit(
                          _score_single_prediction,
                          available_predictions[instance_id],
                          instance_id,
                          run_id,
                          cleanup_docker if use_local else False,  # only local cleans Docker
                          use_modal=not use_local,
                      )] = instance_id

              for future in concurrent.futures.as_completed(futures):
                instance_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"resolved": None, "error": str(exc), "returncode": None}
                prev_entry = scores_data.get("tasks", {}).get(instance_id, {})
                prev_attempts = prev_entry.get("attempts", 0) if isinstance(prev_entry, dict) else 0
                task_entry = {
                    "resolved": result["resolved"],
                    "scored_at": _utc_now(),
                    "attempts": prev_attempts + 1,
                }
                if result.get("error"):
                    task_entry["error"] = result["error"]
                if isinstance(result.get("error_category"), str):
                    task_entry["error_category"] = result["error_category"]
                if result.get("returncode") is not None:
                    task_entry["returncode"] = result["returncode"]
                if result.get("stderr"):
                    task_entry["stderr"] = result["stderr"][-1000:]
                if result.get("stdout"):
                    task_entry["stdout"] = result["stdout"][-1000:]
                scores_data.setdefault("tasks", {})[instance_id] = task_entry
                if result["resolved"] is not None:
                    scored_ids.add(instance_id)

                manifest_summary = manifest.summary()
                scores_data = _refresh_scores_summary(manifest, scores_data)
                _write_incremental_results(root, scores_data)
                print(
                    _format_progress_line(
                        scores_data,
                        manifest_summary,
                        instance_id=instance_id,
                        resolved=result["resolved"],
                    ),
                    file=sys.stderr,
                )

            manifest_summary = manifest.summary()
            scores_data = _refresh_scores_summary(manifest, scores_data)
            _write_incremental_results(root, scores_data)

            if manifest.all_done() and not scorable_ids:
                stop_reason = "completed"
                break
            if time.monotonic() - started_at > timeout:
                stop_reason = "timeout"
                break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        stop_reason = "interrupted"

    manifest_summary = manifest.summary()
    scores_data = _refresh_scores_summary(manifest, scores_data)
    scores_data["stop_reason"] = stop_reason
    _write_incremental_results(root, scores_data)
    print(
        _format_stop_line(scores_data, manifest_summary, stop_reason),
        file=sys.stderr,
    )
    return scores_data


def _score_single_prediction(
    pred_path: str | Path,
    instance_id: str,
    run_id: str,
    cleanup_docker: bool,
    use_modal: bool = True,
) -> dict[str, Any]:
    """Score a single per-instance prediction JSONL via the SWE-bench harness."""
    prediction_path = Path(pred_path).expanduser().resolve()
    _cleanup_task_artifacts(run_id, instance_id)
    completed_result: subprocess.CompletedProcess[str] | None = None

    try:
        prediction = _read_prediction_record(prediction_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "instance_id": instance_id,
            "resolved": None,
            "error": f"invalid prediction file: {exc}",
            "returncode": None,
        }

    model_name = prediction.get("model_name_or_path")
    try:
        completed_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "swebench.harness.run_evaluation",
                "--predictions_path",
                str(prediction_path),
                "--instance_ids",
                instance_id,
                "--max_workers",
                "4",
                "--run_id",
                run_id,
                "--dataset_name",
                "princeton-nlp/SWE-bench_Verified",
                "--timeout",
                "3600",
                *(["--modal", "true"] if use_modal else ["--namespace", ""]),
            ],
            capture_output=True,
            text=True,
            timeout=SCORE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        outcome = {
            "instance_id": instance_id,
            "resolved": None,
            "error": f"run_evaluation timed out after {SCORE_TIMEOUT}s",
            "returncode": None,
            "stdout": _normalize_stream(exc.stdout),
            "stderr": _normalize_stream(exc.stderr),
        }
    except OSError as exc:
        outcome = {
            "instance_id": instance_id,
            "resolved": None,
            "error": str(exc),
            "returncode": None,
        }
    else:
        outcome = {
            "instance_id": instance_id,
            "resolved": _parse_swebench_report(instance_id, run_id, model_name),
            "returncode": completed_result.returncode,
            "stdout": completed_result.stdout[-2000:] if completed_result.stdout else "",
            "stderr": completed_result.stderr[-2000:] if completed_result.stderr else "",
        }
        if outcome["resolved"] is None:
            outcome["error"] = "missing or unparseable SWE-bench report"

    if outcome["resolved"] is None:
        outcome["error_category"] = _categorize_scoring_error(completed_result, outcome)

    if cleanup_docker:
        _cleanup_docker_images()

    return outcome


def _categorize_scoring_error(
    result: subprocess.CompletedProcess[str] | None,
    outcome: dict[str, Any],
) -> str:
    """Classify scoring failures for retry/debug summaries."""
    fragments = [
        outcome.get("error"),
        outcome.get("stderr"),
        outcome.get("stdout"),
    ]
    if result is not None:
        fragments.extend([result.stderr, result.stdout])
    message = " ".join(str(fragment) for fragment in fragments if fragment).lower()

    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "report" in message and any(token in message for token in ("parse", "unparseable", "missing", "json")):
        return "report_parse"
    if "modal" in message and any(
        token in message for token in ("sandbox", "mount", "container", "runner", "image", "volume", "app")
    ):
        return "modal_sandbox"
    return "unknown"


def _parse_swebench_report(
    instance_id: str,
    run_id: str,
    model_name: str | None,
) -> bool | None:
    """Parse a single-instance SWE-bench report for resolved status."""
    report_paths: list[Path] = []
    if model_name:
        report_paths.append(
            Path("logs/run_evaluation") / run_id / model_name / instance_id / "report.json"
        )
    report_paths.extend(sorted(Path("logs/run_evaluation").glob(f"{run_id}/*/{instance_id}/report.json")))

    seen: set[Path] = set()
    for report_path in report_paths:
        if report_path in seen or not report_path.exists():
            continue
        seen.add(report_path)
        try:
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if isinstance(report_data, dict):
            resolved_ids = report_data.get("resolved_ids")
            if isinstance(resolved_ids, list):
                return instance_id in resolved_ids

            instance_payload = report_data.get(instance_id)
            if isinstance(instance_payload, dict):
                resolved = instance_payload.get("resolved")
                if isinstance(resolved, bool):
                    return resolved
                status = instance_payload.get("status")
                if isinstance(status, str):
                    normalized = status.strip().lower()
                    if normalized == "resolved":
                        return True
                    if normalized in {"failed", "unresolved"}:
                        return False

            resolved = report_data.get("resolved")
            if isinstance(resolved, bool):
                return resolved

    return None


def _write_incremental_results(results_root: str | Path, scores_data: dict[str, Any]) -> None:
    """Atomically write the watch scoring snapshot to disk."""
    root = Path(results_root).expanduser().resolve()
    output_path = root / "_watch_scores.json"
    payload = dict(scores_data)
    payload["tasks"] = {
        instance_id: payload["tasks"][instance_id]
        for instance_id in sorted(payload.get("tasks", {}))
    }
    payload["last_updated"] = _utc_now()

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=root,
        prefix="_watch_scores.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, output_path)


def _load_scores_data(scores_path: Path) -> dict[str, Any]:
    base = {
        "manifest_total": 0,
        "manifest_done": 0,
        "manifest_error": 0,
        "scored": 0,
        "resolved": 0,
        "failed": 0,
        "errors": 0,
        "error_breakdown": {},
        "pass_rate": 0.0,
        "last_updated": _utc_now(),
        "tasks": {},
    }
    if not scores_path.exists():
        return base

    try:
        loaded = json.loads(scores_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return base

    if not isinstance(loaded, dict):
        return base
    tasks = loaded.get("tasks")
    if not isinstance(tasks, dict):
        tasks = {}

    base.update({key: value for key, value in loaded.items() if key != "tasks"})
    base["tasks"] = {
        str(instance_id): task
        for instance_id, task in tasks.items()
        if isinstance(task, dict)
    }
    return base


def _refresh_scores_summary(manifest: TaskManifest, scores_data: dict[str, Any]) -> dict[str, Any]:
    refreshed = dict(scores_data)
    tasks = dict(scores_data.get("tasks", {}))
    refreshed["tasks"] = tasks

    manifest_summary = manifest.summary()
    manifest_total = manifest_summary.get("total_tasks", len(tasks))
    manifest_done = manifest_summary.get("done", 0)
    manifest_error = manifest_summary.get("error", 0)
    scored = len(tasks)
    resolved = sum(1 for task in tasks.values() if task.get("resolved") is True)
    failed = sum(1 for task in tasks.values() if task.get("resolved") is False)
    errors = sum(1 for task in tasks.values() if task.get("resolved") is None)
    error_breakdown: dict[str, int] = {}
    for task in tasks.values():
        if task.get("resolved") is not None:
            continue
        category = task.get("error_category")
        if not isinstance(category, str) or not category.strip():
            category = "unknown"
        error_breakdown[category] = error_breakdown.get(category, 0) + 1

    refreshed.update(
        {
            "manifest_total": manifest_total,
            "manifest_done": manifest_done,
            "manifest_error": manifest_error,
            "scored": scored,
            "resolved": resolved,
            "failed": failed,
            "errors": errors,
            "error_breakdown": {
                category: error_breakdown[category]
                for category in sorted(error_breakdown)
            },
            "pass_rate": round(resolved / scored, 4) if scored else 0.0,
        }
    )
    return refreshed


def _cleanup_task_artifacts(run_id: str, instance_id: str) -> None:
    run_root = Path("logs/run_evaluation") / run_id
    if not run_root.exists():
        return

    for task_dir in run_root.glob(f"*/{instance_id}"):
        try:
            shutil.rmtree(task_dir, ignore_errors=True)
        except OSError:
            continue


def _read_prediction_record(pred_path: Path) -> dict[str, Any]:
    with pred_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline().strip()
    if not first_line:
        raise ValueError(f"{pred_path} is empty")
    prediction = json.loads(first_line)
    if not isinstance(prediction, dict):
        raise ValueError(f"{pred_path} must contain a JSON object on its first line")
    return prediction


def _cleanup_docker_images() -> None:
    try:
        result = subprocess.run(
            [
                "docker",
                "images",
                "--format",
                "{{.Repository}}:{{.Tag}}",
                "--filter",
                "reference=*sweb*",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        images = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        removable = [
            image
            for image in images
            if not any(image.startswith(prefix) for prefix in KEEP_IMAGE_PREFIXES)
        ]
        if removable:
            subprocess.run(
                ["docker", "rmi", "-f", *removable],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        subprocess.run(
            ["docker", "image", "prune", "-f"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except Exception:
        return


def _format_progress_line(
    scores_data: dict[str, Any],
    manifest_summary: dict[str, int],
    *,
    instance_id: str,
    resolved: bool | None,
) -> str:
    scored = int(scores_data.get("scored", 0))
    resolved_count = int(scores_data.get("resolved", 0))
    pass_rate = resolved_count / scored if scored else 0.0
    manifest_done = manifest_summary.get("done", 0)
    manifest_total = manifest_summary.get("total_tasks", 0)
    manifest_error = manifest_summary.get("error", 0)
    status = "RESOLVED" if resolved is True else "FAILED" if resolved is False else "ERROR"
    return (
        f"[scored {scored} | resolved {resolved_count}/{scored} = {pass_rate:.1%}] "
        f"[manifest {manifest_done}/{manifest_total} done, {manifest_error} error] "
        f"{instance_id}: {status}"
    )


def _format_stop_line(
    scores_data: dict[str, Any],
    manifest_summary: dict[str, int],
    stop_reason: str,
) -> str:
    scored = int(scores_data.get("scored", 0))
    resolved_count = int(scores_data.get("resolved", 0))
    pass_rate = resolved_count / scored if scored else 0.0
    manifest_done = manifest_summary.get("done", 0)
    manifest_total = manifest_summary.get("total_tasks", 0)
    manifest_error = manifest_summary.get("error", 0)
    error_breakdown = scores_data.get("error_breakdown", {})
    error_summary = _format_error_breakdown(error_breakdown)
    return (
        f"[scored {scored} | resolved {resolved_count}/{scored} = {pass_rate:.1%}] "
        f"[manifest {manifest_done}/{manifest_total} done, {manifest_error} error] "
        f"[errors {error_summary}] "
        f"watch: {stop_reason.upper()}"
    )


def _format_error_breakdown(error_breakdown: Any) -> str:
    if not isinstance(error_breakdown, dict) or not error_breakdown:
        return "none"
    parts = [
        f"{category}={count}"
        for category, count in sorted(error_breakdown.items())
        if isinstance(category, str) and isinstance(count, int)
    ]
    return ", ".join(parts) if parts else "none"


def _normalize_stream(stream: str | bytes | None) -> str:
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return stream or ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Watch a manifest-backed SWE-bench results directory and score predictions incrementally."
    )
    parser.add_argument(
        "--results-root",
        required=True,
        help="Path to a results directory containing _task_manifest.json and _swebench_predictions/.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Maximum watch duration in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip Docker image cleanup between scored predictions.",
    )
    args = parser.parse_args(argv)

    results_root = Path(args.results_root).expanduser().resolve()
    manifest_path = results_root / "_task_manifest.json"
    predictions_dir = results_root / "_swebench_predictions"
    if not manifest_path.exists():
        parser.error(f"results root is missing required manifest: {manifest_path}")
    if not predictions_dir.exists():
        parser.error(f"results root is missing required predictions directory: {predictions_dir}")

    manifest = TaskManifest.load(manifest_path)
    manifest_summary = manifest.summary()
    existing_scores = _load_scores_data(results_root / "_watch_scores.json")
    already_scored = len(existing_scores.get("tasks", {}))
    print(
        "Initial manifest status: "
        f"total={manifest_summary.get('total_tasks', 0)} "
        f"done={manifest_summary.get('done', 0)} "
        f"pending={manifest_summary.get('pending', 0)} "
        f"error={manifest_summary.get('error', 0)} "
        f"already_scored={already_scored}",
        file=sys.stderr,
    )

    watch_and_score(
        results_root,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
        cleanup_docker=not args.no_cleanup,
    )
    return 0


def _write_scorer_status(results_root: str | Path | None, status: str, detail: str = "") -> None:
    """Write scorer health status to a file the dashboard can read."""
    if results_root is None:
        return
    status_path = Path(results_root) / "_scorer_status.json"
    try:
        payload = {
            "status": status,
            "detail": detail[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def main_with_restart(argv: list[str] | None = None, max_restarts: int = 10) -> int:
    """Run main() with auto-restart on crash. Gives up after max_restarts."""
    import traceback

    # Parse args early so we can write status files to results_root
    parsed_argv = argv if argv is not None else sys.argv[1:]
    results_root = None
    for i, arg in enumerate(parsed_argv):
        if arg == "--results-root" and i + 1 < len(parsed_argv):
            results_root = parsed_argv[i + 1]

    restarts = 0
    while restarts <= max_restarts:
        try:
            _write_scorer_status(results_root, "running")
            return main(argv)
        except SystemExit as e:
            if e.code == 0:
                _write_scorer_status(results_root, "completed")
                return 0
            restarts += 1
            detail = f"Exit code {e.code}"
            print(
                f"\n{'='*60}\n"
                f"⚠ SCORER CRASHED (restart {restarts}/{max_restarts})\n"
                f"  Reason: {detail}\n"
                f"{'='*60}\n",
                file=sys.stderr,
            )
            _write_scorer_status(results_root, f"restarting ({restarts}/{max_restarts})", detail)
        except KeyboardInterrupt:
            _write_scorer_status(results_root, "interrupted")
            return 130
        except Exception as exc:
            restarts += 1
            tb = traceback.format_exc()
            detail = f"{exc!r}\n{tb}"
            print(
                f"\n{'='*60}\n"
                f"⚠ SCORER CRASHED (restart {restarts}/{max_restarts})\n"
                f"  Exception: {exc!r}\n"
                f"  Traceback:\n{tb}\n"
                f"{'='*60}\n",
                file=sys.stderr,
            )
            _write_scorer_status(results_root, f"restarting ({restarts}/{max_restarts})", detail)
        time.sleep(5)  # Brief pause before restart

    msg = f"Scorer gave up after {max_restarts} restarts"
    print(f"\n{'='*60}\n⛔ {msg}\n{'='*60}\n", file=sys.stderr)
    _write_scorer_status(results_root, "dead", msg)
    return 1


if __name__ == "__main__":
    raise SystemExit(main_with_restart())
