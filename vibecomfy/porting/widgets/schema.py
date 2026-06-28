"""Compatibility exports for positional widget schema.

Static compile-time aliases live in :mod:`vibecomfy._compile._widgets`. Porting
keeps object-info fallback here for conversion/codemod callers.
"""

from __future__ import annotations

from vibecomfy._compile._widgets import WIDGET_SCHEMA, WIDGET_SEMANTIC_NAMES


def effective_widget_names_for_class(
    class_type: str,
    *,
    allow_object_info_fallback: bool = False,
) -> list[str | None]:
    """Return ordered widget names for *class_type*.

    Curated static aliases always win. When requested, conversion-only callers
    may fall back to the checked-in object-info index.
    """

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)

    if allow_object_info_fallback:
        from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

        return list(object_info_widget_order(class_type))

    return []


def ui_widget_value_names_for_class(
    class_type: str,
    *,
    allow_object_info_fallback: bool = False,
) -> list[str | None]:
    """Return names aligned to LiteGraph ``widgets_values`` positions.

    Curated ``WIDGET_SCHEMA`` entries are already aligned to actual UI widget
    rows, including ``None`` for UI-only rows that still consume a value slot.
    Raw object_info orders interleave ``None`` placeholders for linked sockets;
    those placeholders do not consume ``widgets_values`` slots, so compact them
    before using object_info as a fallback for named field edits.
    """

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)

    if allow_object_info_fallback:
        from vibecomfy.porting.object_info.consume import object_info_widget_value_order  # noqa: PLC0415

        return list(object_info_widget_value_order(class_type))

    return []


__all__ = [
    "WIDGET_SCHEMA",
    "WIDGET_SEMANTIC_NAMES",
    "effective_widget_names_for_class",
    "ui_widget_value_names_for_class",
]
