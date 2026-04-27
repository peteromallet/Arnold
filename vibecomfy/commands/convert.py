from __future__ import annotations

import argparse
from pathlib import Path

from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.cli_loader import _ready_id_for
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.schema import get_schema_provider
from vibecomfy.scratchpad_loader import render_scratchpad, render_scratchpad_from_dict


def _cmd_convert(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    schema_provider = get_schema_provider("auto")
    ready_id = _ready_id_for(args.workflow)
    if ready_id is not None:
        workflow = workflow_from_ready(ready_id)
        text = render_scratchpad_from_dict(workflow.compile("api"), schema_provider=schema_provider)
        out.write_text(text, encoding="utf-8")
        print(out)
        return 0

    source = args.workflow
    source_is_path = False
    try:
        resolved = resolve_workflow_path(args.workflow)
        source = resolved
        source_is_path = True
    except FileNotFoundError:
        pass
    out.write_text(render_scratchpad(source, source_is_path=source_is_path, schema_provider=schema_provider), encoding="utf-8")
    print(out)
    return 0


def register(subparsers) -> None:
    convert = subparsers.add_parser("convert")
    convert.add_argument("workflow")
    convert.add_argument("--out", required=True)
    convert.set_defaults(func=_cmd_convert)
