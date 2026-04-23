"""Standalone manual scorer for active auto-improve iterations; restart manually and do not run beside per-iteration watch_scoring."""
from __future__ import annotations
import argparse, sys, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from evals.manifest import TaskManifest
from evals.watch_scoring import (
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TIMEOUT,
    _score_single_prediction,
    _utc_now,
    _write_incremental_results,
    find_retryable_tasks,
    load_scores_data,
    refresh_scores_summary,
)

def discover_active_iterations(base_dir: str | Path) -> list[Path]:
    active: list[Path] = []
    for root in sorted(Path(base_dir).expanduser().resolve().glob("iteration-*")):
        if not (root / "_task_manifest.json").exists():
            continue
        _, scorable, summary, _ = find_scorable(root)
        if summary.get("pending", 0) or summary.get("claimed", 0) or scorable:
            active.append(root)
    return active

def find_scorable(results_root: str | Path) -> tuple[dict[str, Any], list[str], dict[str, int], dict[str, Path]]:
    root = Path(results_root).expanduser().resolve()
    manifest = TaskManifest.load(root / "_task_manifest.json")
    scores_data = load_scores_data(root / "_watch_scores.json")
    predictions = {path.stem: path for path in (root / "_swebench_predictions").glob("*.jsonl") if path.name != "all_predictions.jsonl"}
    retryable, exhausted, changed = find_retryable_tasks(scores_data, predictions)
    scores_data = refresh_scores_summary(manifest, scores_data)
    if changed:
        _write_incremental_results(root, scores_data)
    scorable = sorted(
        instance_id
        for instance_id in manifest.done_task_ids()
        if ((instance_id not in scores_data.get("tasks", {}) and instance_id not in exhausted) or instance_id in retryable) and instance_id in predictions
    )
    return scores_data, scorable, manifest.summary(), predictions

def watch_all(base_dir: str | Path, *, poll_interval: int = DEFAULT_POLL_INTERVAL, timeout: int = DEFAULT_TIMEOUT) -> int:
    run_ids: dict[Path, str] = {}
    started_at, cursor, stop_reason = time.monotonic(), 0, "completed"
    try:
        while True:
            if time.monotonic() - started_at > timeout:
                stop_reason = "timeout"
                break
            active = discover_active_iterations(base_dir)
            if not active:
                break
            ordered = active[cursor % len(active) :] + active[: cursor % len(active)]
            for offset, root in enumerate(ordered):
                scores_data, scorable, _, predictions = find_scorable(root)
                if not scorable:
                    continue
                instance_id = scorable[0]
                run_id = run_ids.setdefault(root, f"hermes-watch-{root.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}")
                result = _score_single_prediction(predictions[instance_id], instance_id, run_id, False, use_modal=True)
                # Re-read scores from disk to avoid overwriting results written by concurrent processes
                scores_data = load_scores_data(root / "_watch_scores.json")
                previous = scores_data.get("tasks", {}).get(instance_id, {})
                task_entry = {"resolved": result["resolved"], "scored_at": _utc_now(), "attempts": previous.get("attempts", 0) + 1}
                for key in ("error", "error_category", "returncode"):
                    if result.get(key) is not None:
                        task_entry[key] = result[key]
                for key in ("stderr", "stdout"):
                    if result.get(key):
                        task_entry[key] = result[key][-1000:]
                scores_data["run_id"] = run_id
                scores_data.setdefault("tasks", {})[instance_id] = task_entry
                scores_data = refresh_scores_summary(TaskManifest.load(root / "_task_manifest.json"), scores_data)
                _write_incremental_results(root, scores_data)
                status = "RESOLVED" if result["resolved"] is True else "FAILED" if result["resolved"] is False else "ERROR"
                print(f"[{root.name}] {instance_id}: {status}", file=sys.stderr)
                cursor = (cursor + offset + 1) % len(active)
                break
            else:
                time.sleep(poll_interval)
                continue
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    print(f"[watch_scoring_all] {stop_reason.upper()}", file=sys.stderr)
    return 0 if stop_reason == "completed" else 130 if stop_reason == "interrupted" else 1

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch all active auto-improve iterations and score predictions incrementally.")
    parser.add_argument("--base-dir", default="results/auto-improve", help="Base directory containing iteration-* results dirs.")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL}).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Maximum watch duration in seconds (default: {DEFAULT_TIMEOUT}).")
    return watch_all(**vars(parser.parse_args(argv)))

if __name__ == "__main__":
    raise SystemExit(main())
