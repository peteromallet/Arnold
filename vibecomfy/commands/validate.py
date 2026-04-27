from __future__ import annotations

import argparse
import sys
import traceback

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.format import format_issue


def _cmd_validate(args: argparse.Namespace) -> int:
    schema_provider = None if args.no_schema else get_schema_provider("auto")
    try:
        workflow = load_workflow_any(args.path)
        report = workflow.validate(schema_provider=schema_provider)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(f"python_build_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not report.ok:
        for issue in report.issues:
            print(f"{issue.severity}: {format_issue(issue)}", file=sys.stderr)
        return 1
    print("ok")
    return 0


def register(subparsers) -> None:
    validate = subparsers.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--backend", default="api")
    validate.add_argument("--no-schema", action="store_true", help="Skip schema validation; run structural-only.")
    validate.set_defaults(func=_cmd_validate)
