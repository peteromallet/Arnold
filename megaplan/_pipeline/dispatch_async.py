"""M4 T8 — async Dispatcher binding over OpenAICompatibleAgentRunner.run.

Second backend implementing :class:`megaplan._pipeline.dispatch.Dispatcher`,
fanning out off the same protocol as the subprocess binding (T7) so the
executor's join points see a single contract regardless of which backend
serviced the call.

This binding is intentionally thin:

* It accepts an :class:`AgentRunner` (anything with the signature
  ``async def run(request, tools) -> AgentResponse``) and a
  :class:`ToolRegistry`.
* On ``run()`` it builds an :class:`AgentRequest` from the
  :class:`DispatchRequest`'s ``prompt_override`` + ``shim_state``,
  invokes the runner (driving the event loop via :func:`asyncio.run`
  when called from synchronous code), and returns a
  :class:`DispatchResult` whose ``result`` is the :class:`AgentResponse`,
  whose ``cost`` mirrors the envelope's accumulated cost (no live cost
  attribution wired at this step — that lands in T10b), and whose
  ``session_ref`` opaquely carries the resolved conversation id.

A typed-result round-trip through :meth:`RunEnvelope.join` is exercised by
``tests/test_dispatch_async_backend.py``: a fake runner emits a fixed
:class:`AgentResponse`; the dispatcher wraps it in a :class:`DispatchResult`;
the test then constructs a downstream envelope from the result and joins it
back into the request envelope, asserting no information loss across the
shared :class:`Dispatcher` protocol.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from megaplan._pipeline.dispatch import (
    Dispatcher,
    DispatchRequest,
    DispatchResult,
)
from megaplan.resident.agent_loop import AgentRequest, AgentRunner
from megaplan.resident.tool_registry import ToolRegistry


@dataclass
class AsyncDispatcher:
    """Dispatcher binding over an ``async def run(request, tools)`` runner.

    Designed for :class:`megaplan.resident.agent_loop.OpenAICompatibleAgentRunner`
    but accepts any object with a matching ``async def run`` shape — keeps
    the binding test-friendly without dragging in the live OpenAI client.
    """

    runner: AgentRunner
    tools: ToolRegistry
    conversation_id: str = "dispatch-async"
    system_prompt: str = ""

    def run(self, request: DispatchRequest) -> DispatchResult:
        sink = request.liveness_sink
        if sink is not None:
            sink({"alive": True, "phase": "dispatch_async.start"})

        shim = dict(request.shim_state or {})
        hot_context = shim.get("hot_context") or {}
        messages = tuple(shim.get("messages") or ())
        system_prompt = shim.get("system_prompt") or self.system_prompt
        conversation_id = shim.get("conversation_id") or self.conversation_id
        prompt = request.prompt_override
        if prompt is not None:
            messages = messages + ({"role": "user", "content": prompt},)

        agent_request = AgentRequest(
            conversation_id=conversation_id,
            messages=messages,
            system_prompt=system_prompt,
            hot_context=hot_context,
        )

        coro = self.runner.run(agent_request, self.tools)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            response = asyncio.run(coro)
        else:  # pragma: no cover - caller already inside an event loop
            response = asyncio.get_event_loop().run_until_complete(coro)

        if sink is not None:
            sink({"alive": True, "phase": "dispatch_async.end"})

        return DispatchResult(
            result=response,
            cost=float(getattr(request.envelope, "cost", 0.0) or 0.0),
            session_ref=conversation_id,
        )


# Surface-level export — keeps the protocol assertion on the binding type.
_DISPATCHER_BINDING: Optional[Dispatcher] = None
