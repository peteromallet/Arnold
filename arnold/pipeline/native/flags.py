"""Runtime selection compatibility helpers for Arnold pipelines."""

from __future__ import annotations

import os


def native_runtime_enabled() -> bool:
    """Deprecated compatibility helper for old native opt-out checks.

    Native execution is canonical by default.  This function remains only for
    backwards-compatible callers that still inspect ``ARNOLD_NATIVE_RUNTIME``;
    it must not be used as an opt-in gate for native dispatch.
    """

    value = os.getenv("ARNOLD_NATIVE_RUNTIME", "")
    if value == "0":
        return False
    return True


def force_legacy_runtime() -> bool:
    """Return True when ARNOLD_FORCE_LEGACY=true (canonical graph fallback)."""

    return os.getenv("ARNOLD_FORCE_LEGACY", "").strip().lower() == "true"
