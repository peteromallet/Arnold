"""Feature flag helpers for the native Python pipeline runtime.

Centralized single source of truth for ``ARNOLD_NATIVE_RUNTIME`` and
future native-runtime feature flags. All callers must import from here
rather than calling ``os.getenv`` directly.
"""

from __future__ import annotations

import os


def native_runtime_enabled() -> bool:
    """Return whether the high-level native runtime is enabled.

    Native execution is the default after M7.  The legacy
    ``ARNOLD_NATIVE_RUNTIME=1`` value is still accepted.  Explicitly set
    ``ARNOLD_NATIVE_RUNTIME=0`` to disable the high-level runtime for
    backwards-compatibility testing.
    """

    value = os.getenv("ARNOLD_NATIVE_RUNTIME", "")
    if value == "0":
        return False
    return True
