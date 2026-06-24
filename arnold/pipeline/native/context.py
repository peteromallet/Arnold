"""Native runtime context and guard plumbing.

Provides the guard that gates high-level native execution behind the
``ARNOLD_NATIVE_RUNTIME`` feature flag.  Compiler, graph-projection,
and IR imports remain usable in unit tests without the flag — only
the runtime entrypoints call the guard.
"""

from __future__ import annotations

import os

from arnold.pipeline.native.flags import native_runtime_enabled


class NativeRuntimeDisabledError(RuntimeError):
    """Raised when native runtime execution is attempted without the flag.

    Set ``ARNOLD_NATIVE_RUNTIME=1`` to enable high-level native runtime
    execution.  Compiler and graph helpers are not affected.
    """


def require_native_runtime() -> None:
    """Raise :class:`NativeRuntimeDisabledError` if the feature flag is off.

    Call this at the top of high-level native runtime entrypoints.
    Do **not** call it in compiler, graph-projection, or IR modules —
    those must remain usable in unit tests without the flag.

    Raises:
        NativeRuntimeDisabledError: When ``ARNOLD_NATIVE_RUNTIME`` is
            not set to ``'1'``.
    """
    if not native_runtime_enabled():
        value = os.environ.get("ARNOLD_NATIVE_RUNTIME", "")
        if value == "0":
            raise NativeRuntimeDisabledError(
                "ARNOLD_NATIVE_RUNTIME is set to 0. "
                "Omit the variable or set ARNOLD_NATIVE_RUNTIME=1 to enable native runtime execution."
            )
        raise NativeRuntimeDisabledError(
            "ARNOLD_NATIVE_RUNTIME is not set. "
            "Set ARNOLD_NATIVE_RUNTIME=1 to enable native runtime execution."
        )
