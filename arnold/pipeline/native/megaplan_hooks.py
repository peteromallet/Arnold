"""Compatibility re-export of Megaplan native hooks for the native runtime.

This module re-exports :class:`~arnold.pipelines.megaplan.native_hooks.MegaplanNativeRuntimeHooks`
(and its compatibility alias ``MegaplanNativeHooks``) so callers referencing
``arnold.pipeline.native.megaplan_hooks`` continue to resolve the canonical
implementation at ``arnold.pipelines.megaplan.native_hooks``.

The canonical module is ``arnold.pipelines.megaplan.native_hooks``.
This file exists only as a backward-compatible alias.

Milestone: m3-megaplan-runtime-hooks
"""

from __future__ import annotations

from arnold.pipelines.megaplan.native_hooks import (  # noqa: F401 — re-export
    MegaplanNativeHooks,
    MegaplanNativeRuntimeHooks,
)

__all__ = [
    "MegaplanNativeRuntimeHooks",
    "MegaplanNativeHooks",
]
