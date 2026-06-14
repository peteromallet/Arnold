"""Arnold unified agent dispatcher — public surface.

This module re-exports the canonical contracts, the concrete dispatcher,
and the adapter seam.  A module-level default dispatcher is pre-registered
with ``DeepSeekAdapter`` at agent key ``"hermes"`` so that the majority of
callers can use the shortcut :func:`dispatch` / :func:`register` functions
without constructing their own :class:`ArnoldDispatcher`.

Usage::

    from arnold.agent import dispatch, register
    from arnold.agent.contracts import AgentRequest

    result = dispatch(AgentRequest(agent="hermes", mode="default", prompt="hello"))

No imports from ``arnold.pipelines.megaplan`` (zero-leak gate).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical contracts (single home for all wire-format types)
# ---------------------------------------------------------------------------

from arnold.agent.contracts import (
    AgentDispatcher,
    AgentMode,
    AgentRequest,
    AgentResult,
    AgentSpec,
    CostUsage,
    FanoutResult,
    FanoutUnit,
    PREMIUM_AGENT,
    ResultProvenance,
    TokenUsage,
    format_agent_spec,
    parse_agent_spec,
    scatter_agent_units,
)

# ---------------------------------------------------------------------------
# Concrete dispatcher
# ---------------------------------------------------------------------------

from arnold.agent.dispatcher import ArnoldDispatcher

# ---------------------------------------------------------------------------
# Adapter seam
# ---------------------------------------------------------------------------

from arnold.agent.adapters import (
    BackendAdapter,
    CodexAdapter,
    EventEmitter,
    KeySource,
    SessionStore,
    ShannonAdapter,
)
from arnold.agent.adapters.deepseek import DeepSeekAdapter

# ---------------------------------------------------------------------------
# Module-level default dispatcher (pre-registered with DeepSeekAdapter)
# ---------------------------------------------------------------------------

_default = ArnoldDispatcher()
"""Module-level default dispatcher — shared across the process.

Pre-registered adapters:
* ``"hermes"`` → :class:`DeepSeekAdapter` (always available).
* ``"codex"`` → :class:`CodexAdapter`.
* ``"claude"`` / ``"shannon"`` → :class:`ShannonAdapter`.
"""

_default.register("hermes", DeepSeekAdapter())
_default.register("codex", CodexAdapter())
_default.register("claude", ShannonAdapter(session_agent="claude"))
_default.register("shannon", ShannonAdapter(session_agent="shannon"))


def dispatch(request: AgentRequest) -> AgentResult:
    """Shortcut for :meth:`_default.dispatch`."""
    return _default.dispatch(request)


def register(agent: str, adapter: BackendAdapter) -> None:
    """Shortcut for :meth:`_default.register`."""
    _default.register(agent, adapter)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Contracts
    "AgentDispatcher",
    "AgentMode",
    "AgentRequest",
    "AgentResult",
    "AgentSpec",
    "CostUsage",
    "FanoutResult",
    "FanoutUnit",
    "PREMIUM_AGENT",
    "ResultProvenance",
    "TokenUsage",
    "format_agent_spec",
    "parse_agent_spec",
    "scatter_agent_units",
    # Dispatcher
    "ArnoldDispatcher",
    # Adapters
    "BackendAdapter",
    "CodexAdapter",
    "DeepSeekAdapter",
    "EventEmitter",
    "KeySource",
    "SessionStore",
    "ShannonAdapter",
    # Module-level helpers
    "dispatch",
    "register",
]
