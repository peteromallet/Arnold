"""``folder_audit`` — native-first directory-tree audit pipeline.

Stages
------
* ``ingest`` — walk a target directory and produce a tree.
* ``audit`` — classify each entry level-by-level with a pluggable worker.
* ``emit`` — write ``audit.json`` and ``audit.md`` to the artifact root.
"""

from __future__ import annotations

from arnold.pipelines.folder_audit.pipeline import build_pipeline
from arnold.pipelines.folder_audit.steps import (
    AuditStep,
    EmitStep,
    IngestStep,
    _build_tree,
    _compute_summary,
    _default_worker,
    _summarize_children,
)

# ── Package metadata ────────────────────────────────────────────────────

name: str = "folder-audit"
"""Canonical pipeline name (hyphenated)."""

description: str = "Audit a directory tree, classify files, and emit a structured report."
"""Short description surfaced in the pipeline registry."""

default_profile: str | None = None
"""No default profile; worker is supplied at runtime."""

recommended_profiles: tuple[str, ...] = ()
"""No recommended profiles."""

supported_modes: tuple[str, ...] = ("native",)
"""Supported execution modes."""

driver: tuple[str, ...] = ("native", "dispatch+emit")
"""Execution driver spec — native execution by default."""

entrypoint: str = "build_pipeline"
"""Default entrypoint callable name."""

arnold_api_version: str = "1.0"
"""Arnold API version this manifest targets."""

capabilities: tuple[str, ...] = ("audit", "folder-audit", "tree-walk")
"""Declared pipeline capabilities."""


__all__ = [
    "AuditStep",
    "EmitStep",
    "IngestStep",
    "_build_tree",
    "_compute_summary",
    "_default_worker",
    "_summarize_children",
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
