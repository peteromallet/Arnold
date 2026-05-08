"""Compile-equivalence checker for ready-template conversion.

Lifted from `tests/test_ready_templates.py` so the converter and the test
can share the same counters. `compile_equivalent(api_a, api_b)` returns
`(True, [])` if both API dicts represent the same workflow modulo node-id
renumbering and ordering, otherwise `(False, [diff_strings])`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


# UI-only node classes the converter strips at IR build. Match the
# stripped set in `tools/format_as_python.py`.
UI_ONLY = frozenset(
    {
        "Note",
        "MarkdownNote",
    }
)


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    nid_s = str(nid)
    return all(p.isdigit() for p in nid_s.split(":"))


def _is_ui_only(class_type: str) -> bool:
    return class_type in UI_ONLY


def _canonical_key(class_type: str, key: str) -> str | None:
    """Translate widget_N → canonical name when the schema knows it.

    Lets the equality check treat `LoadImage.widget_0='x'` and
    `LoadImage.image='x'` as the same logical input — necessary for
    the converter, which promotes widget_X to canonical names.

    Returns None when the position is a UI-only widget (e.g. KSampler
    `control_after_generate` at index 1) so callers can drop it; both
    sides should normalise the same way to keep equivalence stable.
    """
    if not key.startswith("widget_"):
        return key
    try:
        from vibecomfy.porting.widget_aliases import resolve_widget_name
    except Exception:
        return key
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return key
    return resolve_widget_name(class_type, idx)


def _class_type_counter(api: dict) -> Counter[str]:
    return Counter(
        node["class_type"]
        for node in api.values()
        if not _is_ui_only(node.get("class_type", ""))
    )


def _widget_value_counter(api: dict) -> Counter[tuple[str, str, str]]:
    values: Counter[tuple[str, str, str]] = Counter()
    for node in api.values():
        class_type = node.get("class_type")
        if _is_ui_only(class_type):
            continue
        for key, value in node.get("inputs", {}).items():
            if _is_link(value):
                continue
            canonical = _canonical_key(class_type, key)
            if canonical is None:
                continue  # UI-only widget; drop from both sides for stable equivalence
            values[(class_type, canonical, repr(value))] += 1
    return values


def _topology_counter(api: dict) -> Counter[tuple[str, str, str, int]]:
    topology: Counter[tuple[str, str, str, int]] = Counter()
    for _node_id, node in api.items():
        class_type = node.get("class_type")
        if _is_ui_only(class_type):
            continue
        for key, value in node.get("inputs", {}).items():
            if not _is_link(value):
                continue
            source = api.get(str(value[0]), {})
            source_class = source.get("class_type")
            if _is_ui_only(source_class):
                continue
            canonical = _canonical_key(class_type, key)
            if canonical is None:
                continue  # UI-only widget edge — shouldn't happen in practice but defensive.
            topology[(class_type, canonical, source_class, int(value[1]))] += 1
    return topology


def compile_equivalent(api_a: dict, api_b: dict) -> tuple[bool, list[str]]:
    """Compare two compiled API workflows for semantic equivalence.

    Returns ``(True, [])`` if both API dicts have the same class-type
    multiset, the same widget value multiset (per (class, key, repr)), and
    the same topology (per (target_class, target_input, source_class,
    source_slot)).

    Returns ``(False, diffs)`` with one human-readable diff line per
    mismatching counter group when not equivalent.
    """
    diffs: list[str] = []

    classes_a, classes_b = _class_type_counter(api_a), _class_type_counter(api_b)
    if classes_a != classes_b:
        only_a = (classes_a - classes_b)
        only_b = (classes_b - classes_a)
        if only_a:
            diffs.append(f"class_types only in A: {dict(only_a)}")
        if only_b:
            diffs.append(f"class_types only in B: {dict(only_b)}")

    widgets_a, widgets_b = _widget_value_counter(api_a), _widget_value_counter(api_b)
    if widgets_a != widgets_b:
        only_a = (widgets_a - widgets_b)
        only_b = (widgets_b - widgets_a)
        # Cap the diff lines to keep output actionable.
        for key, count in list(only_a.items())[:10]:
            diffs.append(f"widget_value only in A x{count}: {key}")
        for key, count in list(only_b.items())[:10]:
            diffs.append(f"widget_value only in B x{count}: {key}")
        if len(only_a) > 10 or len(only_b) > 10:
            diffs.append(f"... (additional widget_value diffs truncated; +{len(only_a) + len(only_b) - 20})")

    topo_a, topo_b = _topology_counter(api_a), _topology_counter(api_b)
    if topo_a != topo_b:
        only_a = (topo_a - topo_b)
        only_b = (topo_b - topo_a)
        for key, count in list(only_a.items())[:10]:
            diffs.append(f"topology only in A x{count}: {key}")
        for key, count in list(only_b.items())[:10]:
            diffs.append(f"topology only in B x{count}: {key}")
        if len(only_a) > 10 or len(only_b) > 10:
            diffs.append(f"... (additional topology diffs truncated; +{len(only_a) + len(only_b) - 20})")

    return (not diffs, diffs)


__all__ = [
    "compile_equivalent",
    "_class_type_counter",
    "_widget_value_counter",
    "_topology_counter",
]
