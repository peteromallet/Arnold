from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import vibecomfy.fetch as fetch_assets
from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.ingest.loader import load_template
from vibecomfy.model_assets import extract_from_raw_workflow
from vibecomfy.registry import load_workflow_reference
from vibecomfy.schema import get_schema_provider


def _cmd_fetch(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    workflow = load_workflow_reference(args.workflow, schema_provider=schema_provider, allow_scratchpad=True)
    entries = _model_entries_for_workflow(workflow, args.workflow)
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


def _model_entries_for_workflow(workflow: Any, workflow_ref: str) -> list[dict]:
    entries = workflow.metadata.get("model_assets", [])
    if entries:
        return [entry for entry in entries if isinstance(entry, dict)]
    path = _json_path_for_reference(workflow_ref)
    if path is None:
        return []
    return extract_from_raw_workflow(load_template(path))


def _json_path_for_reference(workflow_ref: str) -> str | None:
    path = Path(workflow_ref)
    if path.suffix.lower() == ".json" and path.is_file():
        return str(path)
    try:
        resolved = Path(resolve_workflow_path(workflow_ref))
    except FileNotFoundError:
        return None
    if resolved.suffix.lower() == ".json" and resolved.is_file():
        return str(resolved)
    return None


def register(subparsers) -> None:
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("workflow")
    fetch.add_argument("--force", action="store_true")
    fetch.add_argument("--dry-run", action="store_true")
    fetch.set_defaults(func=_cmd_fetch)


__all__ = ["register"]
