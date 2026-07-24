"""Compatibility helpers for deprecated native runtime flags.

``ARNOLD_NATIVE_RUNTIME`` is retained only for callers that still import
these helpers or set the variable in older wrappers.  It no longer enables
or disables native execution.
"""

from __future__ import annotations

import os


def native_runtime_enabled() -> bool:
    """Return ``True`` for compatibility with the removed runtime flag."""

    return True


def force_legacy_runtime() -> bool:
    """Return whether canonical graph execution is explicitly forced."""

    return os.getenv("ARNOLD_FORCE_LEGACY", "").strip().lower() == "true"
