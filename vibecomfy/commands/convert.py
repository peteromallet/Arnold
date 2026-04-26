from __future__ import annotations

import argparse
from pathlib import Path

from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.schema import get_schema_provider
from vibecomfy.scratchpad_loader import render_scratchpad


def _cmd_convert(args: argparse.Namespace) -> int:
    source = args.workflow
    source_is_path = False
    try:
        resolved = resolve_workflow_path(args.workflow)
        source = resolved
        source_is_path = True
    except FileNotFoundError:
        pass
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    schema_provider = get_schema_provider("auto")
    out.write_text(render_scratchpad(source, source_is_path=source_is_path, schema_provider=schema_provider), encoding="utf-8")
    print(out)
    return 0


def register(subparsers) -> None:
    convert = subparsers.add_parser("convert")
    convert.add_argument("workflow")
    convert.add_argument("--out", required=True)
    convert.set_defaults(func=_cmd_convert)
