"""Native runtime context compatibility plumbing.

The old guard symbols remain importable for callers that predate native
execution becoming the default.  They no longer gate runtime entrypoints.
"""

from __future__ import annotations

class NativeRuntimeDisabledError(RuntimeError):
    """Deprecated compatibility error type for older guard callers."""


def require_native_runtime() -> None:
    """Compatibility no-op for the removed runtime gate."""

    return None
