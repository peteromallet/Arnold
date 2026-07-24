"""AgentBox version reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def agentbox_version() -> dict[str, Any]:
    """Return the current AgentBox version."""

    version = "0.1.0-dev"
    try:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject.is_file():
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            project = data.get("project", {})
            version = project.get("version", version)
    except Exception:
        pass
    return {"agentbox": version}


__all__ = [
    "agentbox_version",
]
