from __future__ import annotations

from pathlib import Path
from typing import Any

from vibecomfy.commands._workflow_path import resolve_workflow_path
from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.model_assets import extract_from_raw_workflow


def model_entries_for_workflow(workflow: Any, workflow_ref: str) -> list[dict]:
    entries = getattr(workflow, "metadata", {}).get("model_assets", [])
    if entries:
        return [entry for entry in entries if isinstance(entry, dict)]
    path = _json_path_for_reference(workflow_ref)
    if path is None:
        return []
    return extract_from_raw_workflow(load_workflow_json(path))


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


__all__ = ["model_entries_for_workflow"]
