"""Compatibility shim for the canonical ``select-tournament`` builder."""

from __future__ import annotations

from arnold.pipelines.megaplan.pipelines.select_tournament.pipeline import (
    DEFAULT_CANDIDATES,
    build_pipeline,
)


__all__ = [
    "DEFAULT_CANDIDATES",
    "build_pipeline",
]
