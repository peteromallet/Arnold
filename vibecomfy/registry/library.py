from __future__ import annotations

import json
from pathlib import Path

from vibecomfy.ingest.loader import load_template
from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.schema import SchemaProvider
from .ready import workflow_from_ready
from vibecomfy.scratchpad_loader import load_scratchpad


def workflow_from_file(path: str, *, schema_provider: SchemaProvider | None = None):
    raw = load_template(path)
    api = normalize_to_api(raw, schema_provider=schema_provider)
    return convert_to_vibe_format(api, source_path=path, schema_provider=schema_provider)


def workflow_from_template(template_id: str, *, schema_provider: SchemaProvider | None = None):
    try:
        return workflow_from_ready(template_id)
    except KeyError:
        pass

    index_paths = [Path("template_index.json"), Path("external_workflow_index.json")]
    existing_indexes = [path for path in index_paths if path.exists()]
    if not existing_indexes:
        raise FileNotFoundError("No workflow indexes found. Run `vibecomfy sources sync` first.")

    entries = []
    for index_path in existing_indexes:
        entries.extend(json.loads(index_path.read_text(encoding="utf-8")))

    match = next((entry for entry in entries if entry.get("id") == template_id), None)
    if match is None:
        match = next((entry for entry in entries if Path(entry.get("path", "")).stem == template_id), None)
    if not match:
        raise KeyError(f"Workflow template not found: {template_id}")
    raw = load_template(match["path"])
    api = normalize_to_api(raw, schema_provider=schema_provider)
    return convert_to_vibe_format(api, source_path=match["path"], workflow_id=match["id"], schema_provider=schema_provider)


def load_workflow_reference(
    value: str,
    *,
    schema_provider: SchemaProvider | None = None,
    allow_scratchpad: bool = False,
    ready: bool = False,
):
    if ready:
        return workflow_from_ready(value)
    path = Path(value)
    if value.endswith(".json") or (path.exists() and path.suffix.lower() == ".json"):
        return workflow_from_file(str(path), schema_provider=schema_provider)
    if not path.exists():
        try:
            return workflow_from_template(value, schema_provider=schema_provider)
        except (FileNotFoundError, KeyError):
            if not allow_scratchpad:
                raise
    if allow_scratchpad:
        return load_scratchpad(value)
    return workflow_from_template(value, schema_provider=schema_provider)
