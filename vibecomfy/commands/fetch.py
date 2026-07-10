from __future__ import annotations

import argparse

import vibecomfy.fetch as fetch_assets
from vibecomfy.commands._model_entries import model_entries_for_workflow
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import get_schema_provider


def _cmd_fetch(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.workflow, schema_provider=schema_provider, allow_scratchpad=True)
    entries = model_entries_for_workflow(workflow, args.workflow)
    if args.dry_run:
        for entry in entries:
            path = fetch_assets.local_path(entry)
            if fetch_assets.is_present(entry):
                print(f"present {entry['name']}")
            else:
                print(f"would fetch {entry['name']} -> {path}")
        return 0
    try:
        fetch_assets.download_many(entries, force=args.force)
    except RuntimeError as exc:
        print(exc)
        return 1
    return 0


def register(subparsers) -> None:
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("workflow")
    fetch.add_argument("--force", action="store_true")
    fetch.add_argument("--dry-run", action="store_true")
    fetch.set_defaults(func=_cmd_fetch)


__all__ = ["register"]
