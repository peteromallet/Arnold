"""Compatibility re-exports for neutral workflow reference primitives."""

from __future__ import annotations

from arnold.manifest.refs import (
    EdgeRef,
    HookRef,
    ImportRef,
    ManifestCoordinate,
    ManifestCursor,
    NodeRef,
    RefDiagnosticError,
    SourceRef,
    SourceSpan,
    ValueRef,
    _require_ref_segment,
    canonical_alias,
    manifest_coordinate,
)

__all__ = [
    "EdgeRef",
    "HookRef",
    "ImportRef",
    "ManifestCoordinate",
    "ManifestCursor",
    "NodeRef",
    "RefDiagnosticError",
    "SourceRef",
    "SourceSpan",
    "ValueRef",
    "_require_ref_segment",
    "canonical_alias",
    "manifest_coordinate",
]
