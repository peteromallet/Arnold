from __future__ import annotations

from pathlib import Path
from typing import Any

from vibecomfy.commands._index_files import read_index_json


WORKFLOW_INDEX_NAMES = ("workflow_index.json", "external_workflow_index.json")


def load_workflow_index_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index_name in WORKFLOW_INDEX_NAMES:
        rows.extend(read_index_json(Path(index_name), default=[]))
    return rows


def resolve_workflow_path(value: str) -> str:
    if not value.strip():
        raise FileNotFoundError(value)
    path = Path(value)
    if path.is_file():
        return str(path)
    if path.exists():
        raise FileNotFoundError(value)
    match = next((row for row in load_workflow_index_rows() if row.get("id") == value), None)
    if match:
        return str(match["path"])
    raise FileNotFoundError(value)
