"""``megaplan run <pipeline-name>`` — CLI for the pipeline registry.

Lets users invoke any registered pipeline from the command line.
Examples::

    megaplan run --list
    megaplan run doc-critique --inputs doc=/tmp/fixture.md --plan-dir /tmp/dcdemo
    megaplan run judges --inputs doc=/tmp/note.md --plan-dir /tmp/jd
    megaplan run my-custom-pipeline --plan-dir /tmp/out --mode joke

When a user registers their own pipeline (via
``register_pipeline("name", builder)``), it shows up here
automatically — no CLI surgery required.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def build_run_parser(subparsers: Any) -> None:
    """Attach the ``megaplan run`` subcommand to the main CLI."""

    parser = subparsers.add_parser(
        "run",
        help="Run a registered Pipeline by name (see --list).",
    )
    parser.add_argument(
        "pipeline_name",
        nargs="?",
        help="Name of the registered pipeline. Omit when using --list.",
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        dest="list_pipelines",
        help="List every registered pipeline + description and exit.",
    )
    parser.add_argument(
        "--plan-dir", default=None,
        help="Where the pipeline writes artifacts. "
             "Defaults to .megaplan/runs/<pipeline-name>/<timestamp>/.",
    )
    parser.add_argument(
        "--inputs", default=None,
        help="Comma-separated key=path pairs threaded into ctx.inputs "
             "(e.g. --inputs doc=/tmp/fixture.md,extra=/tmp/x.json).",
    )
    parser.add_argument(
        "--state", default=None,
        help="JSON string used to seed ctx.state.",
    )
    parser.add_argument(
        "--mode", default="code",
        help="Mode dispatch (code|doc|joke|creative|...).",
    )
    parser.add_argument(
        "--profile", default=None,
        help="Optional profile name to load via load_profile().",
    )
    parser.add_argument(
        "--describe", action="store_true",
        help="Print the pipeline's description without running it.",
    )
    parser.set_defaults(func=cli_run)


def cli_run(args: argparse.Namespace) -> int:
    from megaplan._pipeline.registry import (
        describe_pipeline,
        registered_pipelines,
        run_pipeline_by_name,
    )

    if args.list_pipelines:
        for name in registered_pipelines():
            desc = describe_pipeline(name)
            print(f"  {name:24s} {desc}")
        return 0

    if not args.pipeline_name:
        print(
            "usage: megaplan run <pipeline-name> [--inputs k=v,...] "
            "[--plan-dir PATH]\n"
            "       megaplan run --list",
            file=sys.stderr,
        )
        return 2

    if args.describe:
        desc = describe_pipeline(args.pipeline_name)
        if not desc:
            print(f"(no description registered for {args.pipeline_name!r})")
        else:
            print(desc)
        return 0

    inputs = _parse_inputs(args.inputs)
    state = json.loads(args.state) if args.state else {}

    plan_dir = _resolve_plan_dir(args.plan_dir, args.pipeline_name)
    plan_dir.mkdir(parents=True, exist_ok=True)

    profile = None
    if args.profile:
        from megaplan._pipeline.profile import load_profile
        profile = load_profile(args.profile)

    try:
        result = run_pipeline_by_name(
            args.pipeline_name,
            plan_dir=plan_dir,
            inputs=inputs,
            state=state,
            mode=args.mode,
            profile=profile,
        )
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "pipeline": args.pipeline_name,
        "plan_dir": str(plan_dir),
        "final_stage": result.get("final_stage"),
        "halt_reason": result.get("halt_reason"),
        "state": result.get("state"),
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _parse_inputs(spec: str | None) -> dict[str, Path]:
    if not spec:
        return {}
    inputs: dict[str, Path] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"--inputs entry {pair!r} must be key=value")
        key, value = pair.split("=", 1)
        inputs[key.strip()] = Path(value.strip())
    return inputs


def _resolve_plan_dir(explicit: str | None, pipeline_name: str) -> Path:
    if explicit:
        return Path(explicit)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    return Path(".megaplan") / "runs" / pipeline_name / ts
