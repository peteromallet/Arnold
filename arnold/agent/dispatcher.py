"""Concrete agent dispatcher — ``ArnoldDispatcher``.

Implements :class:`arnold.agent.contracts.AgentDispatcher` Protocol.
Stateless apart from the adapter registry; callers inject adapters via
``register()`` and then call ``dispatch()`` with an ``AgentRequest``.

No imports from ``arnold.pipelines.megaplan`` (zero-leak gate).
"""

from __future__ import annotations

from arnold.agent.adapters import BackendAdapter
from arnold.agent.contracts import AgentRequest, AgentResult


class ArnoldDispatcher:
    """Agent dispatcher that routes ``AgentRequest`` → ``AgentResult``.

    Satisfies the :class:`~arnold.agent.contracts.AgentDispatcher` Protocol
    so it can be used anywhere a structural ``AgentDispatcher`` is expected.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BackendAdapter] = {}

    def register(self, agent: str, adapter: BackendAdapter) -> None:
        """Register a backend adapter for *agent*.

        Args:
            agent: Agent key (e.g. ``"hermes"``, ``"codex"``, ``"claude"``).
            adapter: Callable ``(AgentRequest) -> AgentResult``.
        """
        self._adapters[agent] = adapter

    def dispatch(self, request: AgentRequest) -> AgentResult:
        """Dispatch *request* to the registered adapter.

        Args:
            request: The agent request to dispatch.

        Returns:
            The :class:`AgentResult` produced by the adapter.

        Raises:
            LookupError: If no adapter is registered for ``request.agent``.
        """
        try:
            adapter = self._adapters[request.agent]
        except KeyError:
            raise LookupError(
                f"no adapter registered for agent={request.agent!r}"
            ) from None
        return adapter(request)
