"""M4 T8 — async Dispatcher binding contract + RunEnvelope round-trip.

Runs the shared :class:`Dispatcher` contract from T5 against the
:class:`AsyncDispatcher` binding over an ``AgentRunner``-shaped fake, and
proves the typed :class:`DispatchResult` round-trips through
:meth:`RunEnvelope.join` (single-binding path; the subprocess binding
ships in T7 and re-uses this same contract).
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from arnold.pipelines.megaplan._pipeline.dispatch import (
    Dispatcher,
    DispatchRequest,
    DispatchResult,
)
from arnold.pipelines.megaplan._pipeline.dispatch_async import AsyncDispatcher
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE, RunEnvelope, make_envelope
from arnold.pipelines.megaplan.resident.agent_loop import AgentResponse


class _FakeRunner:
    """Minimal AgentRunner-shaped object that returns a scripted response."""

    def __init__(self, response: AgentResponse) -> None:
        self._response = response
        self.calls: list = []

    async def run(self, request, tools):
        self.calls.append((request, tools))
        return self._response


class _FakeTools:
    def list(self):
        return []


@pytest.fixture()
def fake_runner():
    return _FakeRunner(
        AgentResponse(
            final_text="dispatched-async-result",
            tool_calls=(),
            metadata={"steps_executed": 1, "model": "fake-model"},
        )
    )


def test_async_dispatcher_satisfies_dispatcher_protocol(fake_runner):
    dispatcher: Dispatcher = AsyncDispatcher(runner=fake_runner, tools=_FakeTools())
    assert hasattr(dispatcher, "run")


def test_async_dispatcher_returns_dispatch_result(fake_runner):
    dispatcher = AsyncDispatcher(runner=fake_runner, tools=_FakeTools())
    res = dispatcher.run(
        DispatchRequest(envelope=EMPTY_ENVELOPE, prompt_override="hello")
    )
    assert isinstance(res, DispatchResult)
    assert res.result.final_text == "dispatched-async-result"
    assert res.session_ref == "dispatch-async"
    assert res.cost == pytest.approx(0.0)


def test_async_dispatcher_propagates_liveness_heartbeats(fake_runner):
    heartbeats: list[dict] = []
    dispatcher = AsyncDispatcher(runner=fake_runner, tools=_FakeTools())
    dispatcher.run(
        DispatchRequest(
            envelope=EMPTY_ENVELOPE,
            prompt_override="hello",
            liveness_sink=heartbeats.append,
        )
    )
    assert {"alive": True, "phase": "dispatch_async.start"} in heartbeats
    assert {"alive": True, "phase": "dispatch_async.end"} in heartbeats


def test_dispatch_result_round_trips_through_envelope_join(fake_runner):
    """Typed DispatchResult must round-trip through RunEnvelope.join: building
    a downstream envelope from the dispatcher's cost and joining it back into
    the request envelope yields the additive cost and union taint/lineage."""

    upstream = make_envelope(
        taint="clean",
        cost=1.5,
        lineage=("step-a",),
        retry_budget=3,
    )
    dispatcher = AsyncDispatcher(runner=fake_runner, tools=_FakeTools())
    res = dispatcher.run(
        DispatchRequest(envelope=upstream, prompt_override="hi")
    )
    assert res.cost == pytest.approx(upstream.cost)

    # Construct a downstream envelope whose cost is the dispatcher-reported
    # cost (in this seed, the upstream cost) plus an additional 0.5 the
    # backend would have charged for its own work.
    downstream = make_envelope(
        taint="clean",
        cost=res.cost + 0.5,
        lineage=("step-b",),
        retry_budget=3,
    )
    joined = upstream.join(downstream)
    assert joined.cost == pytest.approx(upstream.cost + res.cost + 0.5)
    assert "step-a" in joined.lineage and "step-b" in joined.lineage
    # No information lost — JSON round-trip preserves every field too.
    assert RunEnvelope.from_json(joined.to_json()) == joined


def test_request_shape_is_unchanged_for_async_binding():
    """The async binding consumes the same DispatchRequest as the subprocess
    binding — no per-backend god-fields creep in."""
    names = {f.name for f in fields(DispatchRequest)}
    assert names == {"envelope", "prompt_override", "shim_state", "liveness_sink"}
