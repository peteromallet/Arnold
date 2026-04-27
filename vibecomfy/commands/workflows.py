from __future__ import annotations

import argparse

from vibecomfy.commands._output import emit
from vibecomfy.commands.index_files import IndexReadError, print_index_error
from vibecomfy.commands._workflow_path import load_workflow_index_rows
from vibecomfy.registry.ready import _resolve_ready_path, ready_template_ids


def _cmd_workflows_list(args: argparse.Namespace) -> int:
    rows = []
    if args.ready:
        rows = [
            {"id": template_id, "media_type": "ready", "path": str(_resolve_ready_path(template_id))}
            for template_id in ready_template_ids()[: args.limit]
        ]
        return emit(rows, json=args.json, text_renderer=_render_workflow_rows)
    try:
        rows.extend(load_workflow_index_rows())
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    return emit(rows[: args.limit], json=args.json, text_renderer=_render_workflow_rows)


def _render_workflow_rows(rows: list[dict]) -> str:
    return "\n".join(f"{row.get('id')}\t{row.get('media_type', '-')}\t{row.get('path')}" for row in rows)


def register(subparsers) -> None:
    workflows = subparsers.add_parser("workflows")
    workflows_sub = workflows.add_subparsers(dest="subcmd", required=True)
    workflows_list = workflows_sub.add_parser("list")
    workflows_list.add_argument("--limit", type=int, default=200)
    workflows_list.add_argument("--ready", action="store_true")
    workflows_list.add_argument("--json", action="store_true")
    workflows_list.set_defaults(func=_cmd_workflows_list)
