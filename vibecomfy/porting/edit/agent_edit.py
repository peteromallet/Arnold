"""Public headless entry point for agent-edit functionality.

Re-exports :func:`handle_agent_edit` and supporting helpers from
``vibecomfy.comfy_nodes.agent.edit`` without importing the routes module.
This module is safe to import when ``VIBECOMFY_HEADLESS=1`` is set because
the underlying ``edit.py`` does not depend on ``aiohttp`` or the ComfyUI
``PromptServer``.

Usage::

    from vibecomfy.porting.edit.agent_edit import handle_agent_edit

    result = handle_agent_edit(
        {"task": "...", "graph": {...}},
        schema_provider=my_provider,
        deepseek_client=my_client,
    )
"""

from __future__ import annotations

# ── Primary headless export ──────────────────────────────────────────────
from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit

# ── Public helpers also re-exported for headless consumers ───────────────
from vibecomfy.comfy_nodes.agent.edit import (  # noqa: F401 — re-export
    AgentEditState,
    DeepSeekClient,
    TerminalClarifySplit,
    read_session_bundle,
    read_session_chat,
    read_session_json,
    split_terminal_clarify,
)

__all__ = [
    "AgentEditState",
    "DeepSeekClient",
    "TerminalClarifySplit",
    "handle_agent_edit",
    "read_session_bundle",
    "read_session_chat",
    "read_session_json",
    "split_terminal_clarify",
]
