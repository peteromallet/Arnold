from __future__ import annotations

import argparse

from vibecomfy.commands.index_files import IndexReadError, print_index_error
from vibecomfy.commands._workflow_path import load_workflow_index_rows
from vibecomfy.registry.ready import ready_template_ids


def _cmd_workflows_list(args: argparse.Namespace) -> int:
    rows = []
    if args.ready:
        for template_id in ready_template_ids()[: args.limit]:
            print(f"{template_id}\tready\tready_templates/{template_id}.py")
        return 0
    try:
        rows.extend(load_workflow_index_rows())
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    for row in rows[: args.limit]:
        print(f"{row.get('id')}\t{row.get('media_type', '-')}\t{row.get('path')}")
    return 0


def register(subparsers) -> None:
    workflows = subparsers.add_parser("workflows")
    workflows_sub = workflows.add_subparsers(dest="subcmd", required=True)
    workflows_list = workflows_sub.add_parser("list")
    workflows_list.add_argument("--limit", type=int, default=200)
    workflows_list.add_argument("--ready", action="store_true")
    workflows_list.set_defaults(func=_cmd_workflows_list)
