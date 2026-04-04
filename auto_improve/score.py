"""Watch and score active auto-improve iterations."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evals.manifest import TaskManifest
from evals.parallel import _set_pidfile_scorer_pid
from evals.watch_scoring import (
    DEFAULT_POLL_INTERVAL,
    _score_single_prediction,
    _utc_now,
    _write_incremental_results,
    load_scores_data,
    refresh_scores_summary,
    write_scorer_status,
)
from evals.watch_scoring_all import discover_active_iterations, find_scorable


DEFAULT_RESULTS_BASE = Path("results") / "auto-improve"
DEFAULT_RESTART_DELAY_SECONDS = 10


def _normalize_iteration_name(value: str) -> str:
    text = value.strip()
    if text.startswith("iteration-"):
        return text
    if text.isdigit():
        return f"iteration-{int(text):03d}"
    raise ValueError(f"Invalid iteration identifier: {value!r}")


def _filtered_active_iterations(base_dir: Path, iteration_filters: set[str] | None) -> list[Path]:
    active = discover_active_iterations(base_dir)
    if not iteration_filters:
        return active
    return [root for root in active if root.name in iteration_filters]


def _sync_registered_roots(active_roots: list[Path], registered_roots: set[Path], scorer_pid: int) -> set[Path]:
    active_set = set(active_roots)
    for root in sorted(active_set - registered_roots):
        _set_pidfile_scorer_pid(root, scorer_pid)
        write_scorer_status(root, "running")
    for root in sorted(registered_roots - active_set):
        _set_pidfile_scorer_pid(root, None)
        write_scorer_status(root, "idle")
    return active_set


def _clear_registered_roots(registered_roots: set[Path], status: str) -> None:
    for root in sorted(registered_roots):
        _set_pidfile_scorer_pid(root, None)
        write_scorer_status(root, status)


def _score_iteration_root(root: Path, run_ids: dict[Path, str], *, use_modal: bool) -> bool:
    scores_data, scorable, _, predictions = find_scorable(root)
    if not scorable:
        return False

    instance_id = scorable[0]
    run_id = run_ids.setdefault(
        root,
        f"hermes-watch-{root.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
    )
    result = _score_single_prediction(
        predictions[instance_id],
        instance_id,
        run_id,
        False,
        use_modal=use_modal,
    )

    scores_data = load_scores_data(root / "_watch_scores.json")
    previous = scores_data.get("tasks", {}).get(instance_id, {})

    # Never overwrite a manual (human) review — the scorer should not clobber
    # decisions made by a reviewer via `python -m auto_improve.review`.
    if isinstance(previous, dict) and isinstance(previous.get("review"), dict):
        if previous["review"].get("reviewed_by") == "human":
            print(f"[{root.name}] {instance_id}: skipped (has human review)", file=sys.stderr)
            return True

    task_entry = {
        "resolved": result["resolved"],
        "scored_at": _utc_now(),
        "attempts": previous.get("attempts", 0) + 1 if isinstance(previous, dict) else 1,
    }
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
    return True


def _run_once(base_dir: Path, *, iteration_filters: set[str] | None, use_modal: bool) -> int:
    active_roots = _filtered_active_iterations(base_dir, iteration_filters)
    registered_roots: set[Path] = set()
    run_ids: dict[Path, str] = {}
    try:
        registered_roots = _sync_registered_roots(active_roots, registered_roots, os.getpid())
        scored = 0
        for root in active_roots:
            if _score_iteration_root(root, run_ids, use_modal=use_modal):
                scored += 1
        if not active_roots:
            print("[auto_improve.score] no active iterations found", file=sys.stderr)
        return scored
    finally:
        _clear_registered_roots(registered_roots, "idle")


def _watch_forever(
    base_dir: Path,
    *,
    iteration_filters: set[str] | None,
    poll_interval: int,
    use_modal: bool,
) -> int:
    run_ids: dict[Path, str] = {}
    registered_roots: set[Path] = set()
    try:
        while True:
            active_roots = _filtered_active_iterations(base_dir, iteration_filters)
            registered_roots = _sync_registered_roots(active_roots, registered_roots, os.getpid())
            scored_any = False
            for root in active_roots:
                if _score_iteration_root(root, run_ids, use_modal=use_modal):
                    scored_any = True
            if not scored_any:
                time.sleep(poll_interval)
    finally:
        _clear_registered_roots(registered_roots, "idle")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch and score active auto-improve iterations.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true", help="Keep watching active iterations for new predictions (default).")
    mode.add_argument("--once", action="store_true", help="Run a single scoring pass over the currently active iterations.")
    parser.add_argument("--iterations", nargs="+", help="Optional iteration filters such as 021 022 or iteration-021.")
    parser.add_argument("--base-dir", default=DEFAULT_RESULTS_BASE.as_posix(), help="Base directory containing iteration-* results roots.")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help=f"Polling interval in seconds (default: {DEFAULT_POLL_INTERVAL}).")
    parser.add_argument("--no-modal", action="store_true", help="Use local Docker scoring instead of Modal.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    import traceback

    args = _parse_args(argv)
    base_dir = Path(args.base_dir).expanduser().resolve()
    iteration_filters = (
        {_normalize_iteration_name(value) for value in args.iterations}
        if args.iterations
        else None
    )

    if args.once:
        _run_once(base_dir, iteration_filters=iteration_filters, use_modal=not args.no_modal)
        return 0

    while True:
        try:
            return _watch_forever(
                base_dir,
                iteration_filters=iteration_filters,
                poll_interval=args.poll_interval,
                use_modal=not args.no_modal,
            )
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            detail = traceback.format_exc()
            print(
                "[auto_improve.score] crash detected; restarting in "
                f"{DEFAULT_RESTART_DELAY_SECONDS}s: {exc!r}\n{detail}",
                file=sys.stderr,
            )
            time.sleep(DEFAULT_RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
