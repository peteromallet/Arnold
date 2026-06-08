"""Thin entry point for running all megaplan agentic scenarios.

Usage::

    python -m arnold.pipelines.megaplan.tests.agentic.run [--actor hermes|fake] [--verbose]

Constructs a MegaplanAdapter and calls :func:`sisypy.run_all` with
the correct paths, actor, and mode. Prints the summary as JSON at end.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sisypy.runner import run_all, RunMode


def main(argv: list[str] | None = None) -> int:
    """Run all megaplan agentic scenarios.

    Returns the process exit code (0 on success, 1 if any scenario FAILED).
    """
    parser = argparse.ArgumentParser(prog="megaplan.tests.agentic.run")
    parser.add_argument(
        "--actor",
        default="deepseek-subagent",
        choices=["deepseek-subagent", "hermes", "fake"],
        help=(
            "Actor dispatcher to use (default: deepseek-subagent — has "
            "file/web/terminal tools; 'hermes' is chat-only)."
        ),
    )
    parser.add_argument(
        "--mode",
        default="structural",
        choices=["structural", "live"],
        help="Run mode (default: structural).",
    )
    parser.add_argument(
        "--names",
        nargs="*",
        default=None,
        help="Restrict to specific scenario names (default: all).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-scenario start/end markers.",
    )
    args = parser.parse_args(argv)

    # __file__ = <repo>/arnold/pipelines/megaplan/tests/agentic/run.py.
    repo_root = Path(__file__).resolve().parents[5]

    # Lazy import so a missing sisypy is caught early with a clear message.
    from arnold.pipelines.megaplan.tests.agentic.adapter import MegaplanAdapter  # noqa: E402

    adapter = MegaplanAdapter(name="megaplan", repo_root=repo_root)
    mode = RunMode(args.mode)

    if args.verbose:
        print(
            f"[agentic] starting actor={args.actor} mode={mode.value} "
            f"scenarios={args.names or 'all'}",
            file=sys.stderr,
            flush=True,
        )

    result = run_all(
        adapter=adapter,
        scenarios_dir=repo_root / "arnold" / "pipelines" / "megaplan" / "tests" / "agentic" / "scenarios",
        briefs_dir=repo_root / "arnold" / "pipelines" / "megaplan" / "tests" / "agentic" / "briefs",
        reports_root=repo_root / ".megaplan-agentic" / "reports",
        actor=args.actor,
        parallel=False,
        mode=mode,
        names=args.names,
    )

    # Always print the summary so the caller sees what happened.
    summary = result.get("summary") if isinstance(result, dict) else None
    if summary is not None:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(json.dumps(result, indent=2, default=str))

    # Exit code: 1 if any scenario failed, else 0.
    collection = (summary or {}).get("collection", {}) if summary else {}
    outcomes = collection.get("outcome_counts") or {}
    failed = outcomes.get("failed", 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
