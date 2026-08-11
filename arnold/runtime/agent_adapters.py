"""Runtime adapter seam Protocols for the agent dispatcher.

Defines the neutral adapter seam:

* ``BackendAdapter`` — callable from ``AgentRequest`` to ``AgentResult``.
* ``SessionStore`` / ``KeySource`` / ``EventEmitter`` / ``LivenessTouch`` —
  runtime infrastructure Protocols structurally compatible with megaplan's
  ``agent_runtime/adapters.py`` equivalents.

No imports from ``arnold_pipelines.megaplan`` (zero-leak gate).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from arnold.runtime.agent_contracts import AgentRequest, AgentResult

# ---------------------------------------------------------------------------
# BackendAdapter — the adapter seam
# ---------------------------------------------------------------------------

@runtime_checkable
class BackendAdapter(Protocol):
    """A callable that accepts an AgentRequest and returns an AgentResult."""

    def __call__(self, request: AgentRequest) -> AgentResult: ...

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


__all__ = [
    "BackendAdapter",
    "SessionStore",
    "KeySource",
    "EventEmitter",
    "LivenessTouch",
]
