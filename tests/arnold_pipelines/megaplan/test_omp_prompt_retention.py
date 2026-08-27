"""Prompt-event retention bounding in the megaplan RPC client subclass.

(occurrence 8e4028a81152, 2026-08-27) The chain-start supervisor grew
102MB → 13.5GB RSS during one in-process revise phase because the stock
``RpcClient`` retains every raw streamed event (tool results, file reads,
message updates) for the whole turn, count-bounded only. Megaplan consumes
only the terminal assistant text and the canonical session messages, so
``_bounded_memory_client_class`` retains a constant-size terminal marker and
rebuilds the turn from ``get_messages()``.

Proves:

* non-terminal streamed events are not retained (no matter how large);
* the retained terminal marker is constant-size and parses back into an
  ``AgentEndEvent`` the wait loop accepts;
* ``_build_prompt_turn`` under the subclass returns the canonical
  ``get_messages()`` snapshot with an empty events tuple;
* ``_import_rpc_client`` returns a subclass (never the stock class), so every
  megaplan worker dispatch uses the bounded client.
"""

from __future__ import annotations

import json
import threading

import pytest

from arnold_pipelines.megaplan.workers.omp import (
    _bounded_memory_client_class,
    _import_rpc_client,
)

pytest.importorskip("omp_rpc")

from omp_rpc import RpcClient  # noqa: E402
from omp_rpc.client import _BoundedHistory  # noqa: E402
from omp_rpc.protocol import parse_notification  # noqa: E402


class _DummyClient:
    """Minimal stand-in exposing exactly the attributes the two overridden
    methods touch. The real client's reader loop dispatches listeners before
    retention, which these tests do not exercise."""

    def __init__(self) -> None:
        self._events = _BoundedHistory(200_000)
        self._event_condition = threading.Condition()
        self._messages: tuple[dict[str, object], ...] = ()

    def get_messages(self) -> tuple[dict[str, object], ...]:
        return self._messages

def _bounded_dummy() -> tuple[object, type]:
    bounded_cls = _bounded_memory_client_class(RpcClient)
    dummy = _DummyClient()
    # _DummyClient first: its get_messages stub must shadow the real RPC
    # method, while the overridden _append_event/_build_prompt_turn still
    # resolve from the bounded subclass (the dummy defines neither).
    dummy.__class__ = type(  # type: ignore[assignment]
        "DummyBounded",
        (_DummyClient, bounded_cls),
        {},
    )
    return dummy, bounded_cls


def test_nonterminal_events_are_not_retained() -> None:
    client, _ = _bounded_dummy()
    huge_payload = {"type": "message_update", "message": {"x": "y" * 512_000}}
    for _ in range(8):
        client._append_event(huge_payload)  # type: ignore[attr-defined]
    assert client._events.snapshot() == ()  # type: ignore[attr-defined]


def test_terminal_marker_is_constant_size_and_parses() -> None:
    client, _ = _bounded_dummy()
    client._append_event(  # type: ignore[attr-defined]
        {
            "type": "agent_end",
            "isTerminal": True,
            "messages": [{"role": "assistant", "content": "z" * 1_000_000}],
        }
    )
    retained = client._events.snapshot()  # type: ignore[attr-defined]
    assert len(retained) == 1
    encoded = json.dumps(retained[0], separators=(",", ":"))
    assert len(encoded) < 256
    event = parse_notification(retained[0])
    assert event.type == "agent_end"
    assert event.is_terminal is True


def test_build_prompt_turn_uses_canonical_messages_not_events() -> None:
    client, _ = _bounded_dummy()
    final = {"role": "assistant", "content": [{"type": "text", "text": "pong"}]}
    client._messages = (  # type: ignore[attr-defined]
        {"role": "user", "content": "ping"},
        final,
    )
    turn = client._build_prompt_turn(())  # type: ignore[attr-defined]
    assert turn.events == ()
    assert turn.assistant_text == "pong"
    assert turn.assistant_message == final
    assert turn.messages == client.get_messages()


def test_import_rpc_client_returns_bounded_subclass() -> None:
    cls = _import_rpc_client()
    assert issubclass(cls, RpcClient)
    assert cls is not RpcClient
    assert cls is _bounded_memory_client_class(RpcClient)
