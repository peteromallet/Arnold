"""Feature flag helpers for the native Python pipeline runtime.

Centralized single source of truth for ``ARNOLD_NATIVE_RUNTIME`` and
future native-runtime feature flags. All callers must import from here
rather than calling ``os.getenv`` directly.
"""

from __future__ import annotations

import os


def native_runtime_enabled() -> bool:
    """Return ``True`` when ``ARNOLD_NATIVE_RUNTIME`` env var is ``'1'``.

    This is the master gate for high-level native runtime execution.
    Compiler, graph-projection, and IR imports do NOT check this flag
    and remain usable in unit tests without it.
    """
    return os.getenv("ARNOLD_NATIVE_RUNTIME") == "1"
