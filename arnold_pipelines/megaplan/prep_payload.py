"""Helpers for normalizing prep payload compatibility fields."""

from __future__ import annotations

from typing import Any


def suggested_approach_lines(value: Any) -> list[str]:
    """Return non-empty suggested-approach lines from string or list input."""
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                lines.append(text)
        return lines
    text = str(value).strip()
    return [text] if text else []


def render_suggested_approach(value: Any) -> str:
    """Render suggested_approach as readable prompt text."""
    lines = suggested_approach_lines(value)
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    return "\n".join(f"- {line}" for line in lines)

