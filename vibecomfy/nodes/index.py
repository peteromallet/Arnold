from __future__ import annotations

import json
import subprocess
from pathlib import Path

from vibecomfy.comfy_command import comfyui_command, has_comfyui_runtime
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
    if not has_comfyui_runtime():
        return []
    proc = subprocess.run([*comfyui_command(), "nodes", "ls", "--format", "json"], text=True, capture_output=True)
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []
