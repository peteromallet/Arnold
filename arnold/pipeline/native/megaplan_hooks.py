"""Megaplan-specific hooks for the native runtime.

This module adapts Megaplan semantics (state merge, overrides, step-IO policy,
envelope joining, subloop promotion/suspension-lift, and loop guards) to the
native runtime hook points defined in `arnold.pipeline.native.hooks`.

Milestone: m3-megaplan-runtime-hooks
"""

from __future__ import annotations
