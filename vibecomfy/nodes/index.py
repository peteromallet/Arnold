from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from vibecomfy.index_types import CustomNodeExampleRow, RuntimeNodeRow


def index_custom_node_examples(root: str | Path = "custom_nodes") -> list[CustomNodeExampleRow]:
    root = Path(root)
    folders = ["example_workflows", "workflow", "workflows", "example", "examples"]
    entries: list[CustomNodeExampleRow] = []
    if not root.exists():
        return entries
    for pack in root.iterdir():
        if not pack.is_dir():
            continue
        for folder in folders:
            candidate = pack / folder
            if candidate.exists():
                for path in candidate.rglob("*.json"):
                    entries.append({"id": path.stem, "path": str(path), "source": "custom_node", "pack": pack.name})
    return entries


def index_runtime_nodes() -> list[RuntimeNodeRow]:
    executable = shutil.which("comfyui")
    if executable is None:
        sibling = Path(sys.executable).with_name("comfyui")
        executable = str(sibling) if sibling.exists() else None
    if executable is None:
        return []
    proc = subprocess.run([executable, "nodes", "ls", "--format", "json"], text=True, capture_output=True)
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def write_json(path: str | Path, data: object) -> None:
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
