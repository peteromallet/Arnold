"""Canonical TimelineConfig schema (Python).

TS+Zod is the source of truth. Python TypedDicts in `generated.py` are emitted
by `scripts/gen_python_types.py` from `timeline.schema.json`.
"""

from __future__ import annotations

from .materialize import OUTPUT_FILE_DEFAULT, materialize_output
from .theme import deep_merge_theme, merge_generation, resolve_theme
from .validate import load_schema, validate_timeline

try:  # generated.py is produced by codegen; absent in a fresh checkout.
    from .generated import (  # type: ignore[attr-defined]
        AssetEntry,
        Theme,
        ThemeOverrides,
        TimelineClip,
        TimelineConfig,
        TimelineOutput,
    )
except ImportError:  # pragma: no cover
    AssetEntry = dict  # type: ignore[assignment,misc]
    Theme = dict  # type: ignore[assignment,misc]
    ThemeOverrides = dict  # type: ignore[assignment,misc]
    TimelineClip = dict  # type: ignore[assignment,misc]
    TimelineConfig = dict  # type: ignore[assignment,misc]
    TimelineOutput = dict  # type: ignore[assignment,misc]

__all__ = [
    "AssetEntry",
    "OUTPUT_FILE_DEFAULT",
    "Theme",
    "ThemeOverrides",
    "TimelineClip",
    "TimelineConfig",
    "TimelineOutput",
    "deep_merge_theme",
    "load_schema",
    "materialize_output",
    "merge_generation",
    "resolve_theme",
    "validate_timeline",
]
