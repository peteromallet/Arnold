"""Runtime infra Protocols — local definitions, megaplan-free.

Defines the adapter seam Protocols for the unified agent dispatcher:

* ``BackendAdapter`` — callable from ``AgentRequest`` to ``AgentResult``.
* ``SessionStore`` / ``KeySource`` / ``EventEmitter`` / ``LivenessTouch`` —
  runtime infrastructure Protocols structurally compatible with megaplan's
  ``agent_runtime/adapters.py`` equivalents.

No imports from ``arnold.pipelines.megaplan`` (zero-leak gate).
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Protocol, runtime_checkable

from arnold.agent.contracts import AgentRequest, AgentResult

# ---------------------------------------------------------------------------
# BackendAdapter — the adapter seam
# ---------------------------------------------------------------------------

BackendAdapter = Callable[[AgentRequest], AgentResult]
"""A callable that accepts an :class:`AgentRequest` and returns an :class:`AgentResult`.

All three backend adapters (DeepSeek, Codex, Shannon) conform to this shape.
"""

# ---------------------------------------------------------------------------
# Runtime infra Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionStore(Protocol):
    """Load/save session state by key."""

    def load(self, key: str) -> Optional[Mapping[str, Any]]: ...

    def save(self, key: str, payload: Mapping[str, Any]) -> None: ...


@runtime_checkable
class KeySource(Protocol):
    """Resolve API keys by agent name."""

    def key_for(self, agent: str) -> Optional[str]: ...


@runtime_checkable
class EventEmitter(Protocol):
    """Emit structured runtime events."""

    def emit(self, kind: str, payload: Mapping[str, Any]) -> None: ...


@runtime_checkable
class LivenessTouch(Protocol):
    """Heartbeat / keep-alive callable."""

    def __call__(self) -> None: ...


# ---------------------------------------------------------------------------
# Concrete adapters
#
# Imported at the bottom, after the seam types above are defined, so adapter
# modules can import the seam types without circular-import failures.
# ---------------------------------------------------------------------------

from arnold.agent.adapters.codex import CodexAdapter
from arnold.agent.adapters.shannon import ShannonAdapter


__all__ = [
    "BackendAdapter",
    "SessionStore",
    "KeySource",
    "EventEmitter",
    "LivenessTouch",
    "CodexAdapter",
    "ShannonAdapter",
]
