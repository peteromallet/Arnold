"""``vibecomfy watchdog`` CLI subcommand.

Currently exposes ``watchdog tail <run_id>`` which pretty-prints the dumped
watchdog report for a previously-recorded run. Useful for after-the-fact
triage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _cmd_watchdog_tail(args: argparse.Namespace) -> int:
    run_dir = Path("out/runs") / args.run_id
    target = run_dir / "watchdog.json"
    if not target.exists():
        print(f"watchdog report not found for run: {args.run_id}", file=sys.stderr)
        print(f"  expected: {target}", file=sys.stderr)
        return 1
    text = target.read_text(encoding="utf-8")
    # The first line is the human-readable header. Everything after is JSON.
    header_line, _, body = text.partition("\n")
    print(header_line)
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        # Fallback: file may be just JSON (no header). Try parsing whole text.
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            print(text)
            return 0

    _print_summary(payload)
    if args.full:
        print()
        print("== full report ==")
        print(json.dumps(payload, indent=2, default=str))
    return 0


def _print_summary(payload: dict[str, Any]) -> None:
    state = payload.get("state") or {}
    print()
    print(f"diagnosis        : {payload.get('diagnosis')}")
    print(f"  reason         : {payload.get('diagnosis_reason')}")
    print(f"prompt_id        : {state.get('prompt_id')}")
    print(f"client_id        : {state.get('client_id')}")
    print(f"server_url       : {state.get('server_url')}")
    print(f"connection_state : {state.get('connection_state')}")
    print(f"stop_reason      : {state.get('stop_reason')}")
    print(f"current_node     : {state.get('current_node_id')} ({state.get('current_node_class_type')})")
    elapsed = payload.get("elapsed_seconds")
    elapsed_node = payload.get("elapsed_in_current_node_seconds")
    if isinstance(elapsed, (int, float)):
        print(f"elapsed_total    : {elapsed:.1f}s")
    if isinstance(elapsed_node, (int, float)):
        print(f"elapsed_in_node  : {elapsed_node:.1f}s")
    executed = state.get("executed_node_ids") or []
    cached = state.get("cached_node_ids") or []
    print(f"executed_nodes   : {len(executed)} ({', '.join(map(str, executed[:8]))}{'...' if len(executed) > 8 else ''})")
    print(f"cached_nodes     : {len(cached)}")
    progress = payload.get("recent_progress_events") or []
    if progress:
        last = progress[-1]
        print(f"last_progress    : node={last.get('node_id')} {last.get('value')}/{last.get('max')}")
    samples = payload.get("vram_samples") or []
    if samples:
        last = samples[-1]
        free = last.get("vram_free_bytes")
        total = last.get("vram_total_bytes")
        if isinstance(free, int) and isinstance(total, int) and total > 0:
            print(f"last_vram_sample : free={free / (1024**3):.2f}GB / total={total / (1024**3):.2f}GB")
        else:
            print(f"last_vram_sample : (no GPU stats)")
    last_error = state.get("last_error")
    if last_error:
        print(f"last_error       : {last_error.get('exception_type')} :: {last_error.get('exception_message')}")


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "watchdog",
        help="Inspect runtime watchdog dumps from previous runs.",
    )
    sub = parser.add_subparsers(dest="subcmd", required=True)

    tail = sub.add_parser("tail", help="Pretty-print the dumped watchdog report for a run.")
    tail.add_argument("run_id")
    tail.add_argument(
        "--full",
        action="store_true",
        help="Also print the complete JSON body after the summary.",
    )
    tail.set_defaults(func=_cmd_watchdog_tail)
