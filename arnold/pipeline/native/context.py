"""Native runtime compatibility context.

Native execution is the canonical default.  This module is kept only for
backwards-compatible imports from older call sites that still invoke a runtime
guard; the guard is now a no-op.
"""

from __future__ import annotations


class NativeRuntimeDisabledError(RuntimeError):
    """Deprecated compatibility error export.

    Native runtime execution is no longer gated by ``ARNOLD_NATIVE_RUNTIME``,
    and :func:`require_native_runtime` no longer raises this exception.
    """


def require_native_runtime() -> None:
    """Deprecated compatibility no-op for older native entrypoints."""
    return
