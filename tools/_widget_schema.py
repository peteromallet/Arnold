"""Compatibility wrapper for the package-owned positional widget schema."""

from __future__ import annotations

from vibecomfy.porting.widget_aliases import resolve_widget_name
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

__all__ = ["WIDGET_SCHEMA", "resolve_widget_name"]
