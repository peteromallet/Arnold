"""Compatibility mode enum — extracted to a leaf module to break import cycles.

The canonical definition lives here so that both ``step_contracts.py`` and
``model_seam.py`` can import it without creating a cycle.
"""

from __future__ import annotations

from enum import Enum


class CompatibilityMode(str, Enum):
    """Whether a step still relies on legacy compatibility repair."""

    NATIVE = "native"
    LEGACY = "legacy"
