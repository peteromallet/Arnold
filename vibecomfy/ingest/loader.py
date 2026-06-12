from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_workflow_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Workflow {path} did not decode to a JSON object")
    return data


# Back-compat alias documented by the agent skill.
load_template = load_workflow_json
