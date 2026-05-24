"""Compatibility wrapper for packaged widget schema helpers."""

from __future__ import annotations

from vibecomfy.porting import widget_schema as _widget_schema


WIDGET_SCHEMA = _widget_schema.WIDGET_SCHEMA
resolve_widget_name = _widget_schema.resolve_widget_name


__all__ = ["WIDGET_SCHEMA", "resolve_widget_name"]
