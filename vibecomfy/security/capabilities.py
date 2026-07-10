"""Static capability taxonomy for ComfyUI node classes.

The taxonomy is the read-only side of the capability fence. It maps known
``class_type`` values to edit-time capabilities and treats unknown classes as
``code_exec``-suspect by default. This module has no imports from analysis,
runtime, porting, or registry.
"""

from __future__ import annotations

import re
from typing import Literal

from vibecomfy.security._seed import (
    ALL_SEEDED,
    KNOWN_PASSTHROUGH,
    _OUTPUT_CLASSES_KEYS,
    _SIDE_EFFECTING_RE,
)

Capability = Literal["filesystem_write", "network", "code_exec", "passthrough"]

_NETWORK_RE: re.Pattern[str] = re.compile(r"^(Download.*Load|VHS_LoadVideo.*)$")
_CODE_EXEC_RE: re.Pattern[str] = re.compile(r"^.*Expression$|^.*Eval$")


def _build_taxonomy() -> dict[str, frozenset[Capability]]:
    """Build the frozen capability taxonomy from mirrored seed data."""
    taxonomy: dict[str, frozenset[Capability]] = {}

    for class_type in sorted(ALL_SEEDED):
        if class_type in _OUTPUT_CLASSES_KEYS:
            taxonomy[class_type] = frozenset({"filesystem_write"})
            continue

        if _SIDE_EFFECTING_RE.match(class_type):
            if _NETWORK_RE.match(class_type):
                taxonomy[class_type] = frozenset({"network"})
            elif _CODE_EXEC_RE.match(class_type):
                taxonomy[class_type] = frozenset({"code_exec"})
            else:
                taxonomy[class_type] = frozenset({"filesystem_write"})
            continue

        taxonomy[class_type] = frozenset({"passthrough"})

    return taxonomy


CAPABILITY_TAXONOMY: dict[str, frozenset[Capability]] = _build_taxonomy()


def capabilities_for(class_type: str) -> frozenset[Capability]:
    """Return the capability set for ``class_type``.

    Unknown classes receive the quarantine default from
    :func:`unknown_class_policy`.
    """
    if class_type in CAPABILITY_TAXONOMY:
        return CAPABILITY_TAXONOMY[class_type]
    if class_type in KNOWN_PASSTHROUGH:
        return frozenset({"passthrough"})
    return unknown_class_policy()


def is_side_effecting(class_type: str) -> bool:
    """Return True if ``class_type`` has any non-passthrough capability."""
    caps = capabilities_for(class_type)
    return caps != frozenset({"passthrough"})


def unknown_class_policy() -> frozenset[Capability]:
    """Quarantine default for unknown node classes."""
    return frozenset({"code_exec"})
