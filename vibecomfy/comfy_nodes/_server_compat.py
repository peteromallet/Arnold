from __future__ import annotations

"""Compatibility helper for importing ComfyUI's PromptServer.

VibeComfy historically assumed a checkout-style ComfyUI layout where the
running interpreter can do ``from server import PromptServer``. The
pip-installable ComfyUI fork keeps the server class at
``comfy.cmd.server.PromptServer`` and installs a ``sys.modules['server']`` shim
via ``comfy_compatibility.vanilla.prepare_vanilla_environment()``.

This module provides a single import helper that works for both layouts so
VibeComfy custom nodes can register HTTP routes in either environment.
"""


def import_prompt_server():
    """Return ComfyUI's ``PromptServer`` class.

    Tries the legacy checkout-style import first, then activates the
    pip-install compatibility shim if needed, then falls back to importing
    directly from ``comfy.cmd.server``.

    Raises
    ------
    ImportError
        If PromptServer cannot be resolved in any layout.
    """
    try:
        from server import PromptServer

        return PromptServer
    except ImportError:
        pass

    try:
        from comfy_compatibility.vanilla import prepare_vanilla_environment

        prepare_vanilla_environment()
        from server import PromptServer

        return PromptServer
    except Exception:
        pass

    # Final fallback for pip-installed ComfyUI when the shim is not present.
    from comfy.cmd.server import PromptServer

    return PromptServer
