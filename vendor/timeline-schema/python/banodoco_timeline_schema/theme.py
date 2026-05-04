"""Theme-merge helpers shared across Banodoco/Reigh.

SD-006a: lives in timeline-schema (NOT composition) so Reigh's read-only Theme
chip can call `resolve_theme` before composition extraction.

Source of truth was `tools/timeline.py:605-673`; this is the canonical version.
The TS twin is `typescript/src/resolveTheme.ts`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def merge_generation(
    theme_generation: Mapping[str, Any] | None,
    per_clip: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(theme_generation, dict):
        merged.update(theme_generation)
    if isinstance(per_clip, dict):
        merged.update(per_clip)
    return merged


def deep_merge_theme(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            merged_block: dict[str, Any] = dict(result[key])
            for sub_key, sub_value in value.items():
                if (
                    sub_key in merged_block
                    and isinstance(merged_block[sub_key], dict)
                    and isinstance(sub_value, dict)
                ):
                    inner = dict(merged_block[sub_key])
                    inner.update(sub_value)
                    merged_block[sub_key] = inner
                else:
                    merged_block[sub_key] = sub_value
            result[key] = merged_block
        else:
            result[key] = value
    return result


def resolve_theme(
    timeline: Mapping[str, Any],
    themes_root: Path | str,
) -> dict[str, Any]:
    """Return the merged theme view: <themes_root>/<slug>/theme.json + overrides."""
    slug = timeline.get("theme") if isinstance(timeline, dict) else None
    if not isinstance(slug, str) or not slug:
        raise ValueError("Timeline.theme must be a non-empty slug")
    theme_path = Path(themes_root) / slug / "theme.json"
    if not theme_path.is_file():
        raise FileNotFoundError(f"Theme {slug!r} not found at {theme_path}")
    base = json.loads(theme_path.read_text(encoding="utf-8"))
    if not isinstance(base, dict):
        raise ValueError(f"Theme file {theme_path} must contain a JSON object")
    overrides = timeline.get("theme_overrides") if isinstance(timeline, dict) else None
    if isinstance(overrides, dict) and overrides:
        return deep_merge_theme(base, overrides)
    return base
