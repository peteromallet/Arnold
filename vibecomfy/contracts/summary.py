from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkflowSummary:
    """Typed, LLM-generated summary for a VibeWorkflow.

    Design (SD1/SD2):
    - Stored as a dict under ``workflow.metadata['summary']`` for backward
      compatibility with existing metadata consumers and JSON serialization.
    - Only ``title``, ``description``, and ``tags`` are LLM-generated.
    - ``task_type``, ``media_type``, ``flags``, and ``complexity`` are derived
      deterministically from the workflow structure.
    """

    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    task_type: str = "other"
    media_type: str = "image"
    flags: dict[str, bool] = field(default_factory=dict)
    complexity: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowSummary":
        """Construct a WorkflowSummary from a dict (e.g. deserialized JSON)."""
        return cls(
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            tags=_coerce_str_list(data.get("tags")),
            task_type=str(data.get("task_type", "other")),
            media_type=str(data.get("media_type", "image")),
            flags=_coerce_flags(data.get("flags")),
            complexity=int(data.get("complexity", 1)),
        )


def _coerce_str_list(value: Any) -> list[str]:
    """Coerce a value to a list of strings, skipping non-string items."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _coerce_flags(value: Any) -> dict[str, bool]:
    """Coerce a value to a dict of str→bool."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, bool] = {}
    for k, v in value.items():
        if isinstance(k, str):
            result[k] = bool(v)
    return result
