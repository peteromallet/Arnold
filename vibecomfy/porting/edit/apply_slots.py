from __future__ import annotations

from typing import Any, Mapping

from vibecomfy.porting.widgets.schema import effective_widget_names_for_class


def _find_named_slot_index(slots: Any, name: str) -> int | None:
    if not isinstance(slots, list):
        return None
    for index, item in enumerate(slots):
        if isinstance(item, dict) and item.get("name") == name:
            return index
    return None


def _widget_name_for_input(slot: Any) -> str | None:
    if not isinstance(slot, Mapping):
        return None
    widget = slot.get("widget")
    if not isinstance(widget, Mapping):
        return None
    name = widget.get("name")
    return str(name) if isinstance(name, str) and name else None


def _widget_index_for_field(class_type: str, field_name: str) -> int | None:
    widget_names = effective_widget_names_for_class(class_type, allow_object_info_fallback=True)
    for index, name in enumerate(widget_names):
        if name == field_name:
            return index
    return None


def _widget_index_from_input_stubs(inputs: Any, field_name: str) -> int | None:
    if not isinstance(inputs, list):
        return None
    widget_index = 0
    for slot in inputs:
        widget_name = _widget_name_for_input(slot)
        if widget_name is None:
            continue
        if widget_name == field_name:
            return widget_index
        widget_index += 1
    return None


def _reorder_names(node: Mapping[str, Any], class_type: str, axis: str) -> tuple[str, ...] | None:
    if axis == "widgets":
        values = node.get("widgets_values")
        if not isinstance(values, list):
            return None
        names = list(effective_widget_names_for_class(class_type, allow_object_info_fallback=True))
        if len(names) < len(values):
            recovered = _widget_names_from_input_stubs(node.get("inputs"))
            if len(recovered) >= len(values):
                names = recovered
        if len(names) != len(values) or any(not name for name in names):
            return None
        return tuple(names)

    outputs = node.get("outputs")
    if not isinstance(outputs, list):
        return None
    names: list[str] = []
    for output in outputs:
        if not isinstance(output, Mapping):
            return None
        name = output.get("name")
        if not isinstance(name, str) or not name:
            return None
        names.append(name)
    if len(set(names)) != len(names):
        return None
    return tuple(names)


def _widget_names_from_input_stubs(inputs: Any) -> list[str]:
    if not isinstance(inputs, list):
        return []
    names: list[str] = []
    for slot in inputs:
        name = _widget_name_for_input(slot)
        if name is not None:
            names.append(name)
    return names


def _linked_widget_names(inputs: Any) -> set[str]:
    if not isinstance(inputs, list):
        return set()
    names: set[str] = set()
    for slot in inputs:
        if not isinstance(slot, Mapping):
            continue
        if not isinstance(slot.get("link"), int):
            continue
        name = _widget_name_for_input(slot)
        if name is not None:
            names.add(name)
    return names
