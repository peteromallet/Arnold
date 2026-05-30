"""Regression test for the reasoning-then-freeze DeepSeek-V4-Pro execute wedge.

Ticket 01KSV6SF0XBW0JF9ZY6HDWX0X4. The production wedge observed on the
execute path was NOT a clean zero-token stall and NOT a steady keepalive
stream — it was:

  1. The model streams real ``reasoning_content`` deltas for a while
     (``reasoning_emitted_so_far`` climbs to e.g. 1369), then
  2. real generation FREEZES — no further real content/reasoning advances —
     while the SSE channel is kept warm by whitespace-only keepalive deltas
     (" " / "\n") arriving ~1/s.

This regime defeats every *content-keyed* watchdog that resets on chunk
arrival or on a truthy (but whitespace-only) delta. Only a watchdog keyed on
strictly-increasing REAL (non-whitespace) content+reasoning character counts
can catch it. The ``stream_progress_stall`` watchdog is that backstop; this
test proves it aborts the wedge within the bound on the real
``_call_chat_completions`` execute path and surfaces a retryable
APITimeoutError.

Fully mocked — no network.
"""

from __future__ import annotations

import threading
import time as _time
from types import SimpleNamespace

import pytest

import megaplan.agent  # noqa: F401  (side-effect: sys.path setup)

import openai
from run_agent import (
    AIAgent,
    DEFAULT_STREAM_PROGRESS_STALL_TIMEOUT_SECONDS,
    _stream_progress_stall_timeout_seconds,
)


def test_progress_stall_timeout_default_and_env_override(monkeypatch):
    monkeypatch.delenv("HERMES_STREAM_PROGRESS_STALL_TIMEOUT", raising=False)
    assert (
        _stream_progress_stall_timeout_seconds()
        == DEFAULT_STREAM_PROGRESS_STALL_TIMEOUT_SECONDS
        == 120.0
    )
    monkeypatch.setenv("HERMES_STREAM_PROGRESS_STALL_TIMEOUT", "45")
    assert _stream_progress_stall_timeout_seconds() == 45.0
    monkeypatch.setenv("HERMES_STREAM_PROGRESS_STALL_TIMEOUT", "nope")
    assert (
        _stream_progress_stall_timeout_seconds()
        == DEFAULT_STREAM_PROGRESS_STALL_TIMEOUT_SECONDS
    )
    # 30s floor protects against a misconfigured tiny value.
    monkeypatch.setenv("HERMES_STREAM_PROGRESS_STALL_TIMEOUT", "0.01")
    assert _stream_progress_stall_timeout_seconds() == 30.0


def _reasoning_chunk(text):
    delta = SimpleNamespace(content=None, reasoning_content=text, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=None)
    return SimpleNamespace(choices=[choice], model="deepseek-v4-pro", usage=None)


class _ReasoningThenWhitespaceFreezeStream:
    """PRODUCTION REPRODUCER for the reasoning-then-freeze wedge.

    Phase 1: emits a burst of REAL reasoning deltas (advances the real
    reasoning character counter — exactly as the wedge did up to 1369 chars).

    Phase 2: emits WHITESPACE-ONLY reasoning deltas (" ") forever, ~1/s. These
    are truthy chunks (so they keep the producer queue non-empty and reset any
    naive arrival-keyed timer) but carry ZERO real generation progress. This is
    the keepalive pattern that pins ``reasoning_emitted_so_far`` and leaves the
    worker at 0% CPU while ``llm_token_heartbeat`` keeps firing on its own
    wall-clock timer.

    Only the progress-stall watchdog (keyed on real, ``.strip()``-non-empty
    character advancement) can abort this.
    """

    def __init__(self, real_chunks=5, keepalive_period_s=0.05):
        self.closed = False
        self._emitted_real = 0
        self._real_chunks = real_chunks
        self._period = keepalive_period_s

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        if self._emitted_real < self._real_chunks:
            self._emitted_real += 1
            _time.sleep(0.01)
            return _reasoning_chunk(f"real-reasoning-token-{self._emitted_real} ")
        # Phase 2: whitespace-only keepalives forever.
        _time.sleep(self._period)
        return _reasoning_chunk(" ")

    def close(self):
        self.closed = True


def _make_agent(monkeypatch, stream):
    agent = AIAgent.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._streaming_timeout_streak = 0
    agent._codex_on_first_delta = None
    agent.base_url = "https://api.deepseek.com"
    agent.stream_delta_callback = None
    agent._stream_callback = None
    agent.reasoning_callback = None
    monkeypatch.setattr(agent, "_api_timeout_seconds", lambda: 300.0)
    monkeypatch.setattr(agent, "_fire_reasoning_delta", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_fire_stream_delta", lambda *a, **k: None)

    class _Client:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            return stream

    monkeypatch.setattr(
        agent, "_create_request_openai_client", lambda *, reason: _Client()
    )
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)

    def _no_fallback(api_kwargs):
        raise AssertionError(
            "progress-stall must not fall back to non-streaming (double-delivery risk)"
        )

    monkeypatch.setattr(agent, "_interruptible_api_call", _no_fallback)
    return agent


def test_reasoning_then_whitespace_freeze_aborts_via_progress_watchdog(monkeypatch):
    """The wedge: real reasoning advances, then whitespace-only keepalives
    forever. Must abort via the progress-stall watchdog and raise a retryable
    APITimeoutError shortly after the (short, test-only) progress threshold.

    Critically, the OTHER watchdogs are set HIGH so that ONLY the progress
    watchdog can be what fires:
      * content_stall / post_content high (reset by every reasoning chunk,
        including whitespace ones in the buggy regime)
      * first_content high (reasoning is flowing, so it would not fire fast)
    """
    # Progress bound short (must fire); everything else high (must NOT fire).
    monkeypatch.setattr("run_agent._stream_progress_stall_timeout_seconds", lambda: 0.5)
    monkeypatch.setattr("run_agent._stream_content_stall_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr("run_agent._post_content_stall_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr("run_agent._stream_first_content_timeout_seconds", lambda: 60.0)

    stream = _ReasoningThenWhitespaceFreezeStream(real_chunks=5, keepalive_period_s=0.05)
    agent = _make_agent(monkeypatch, stream)

    start = _time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        agent._interruptible_streaming_api_call(
            {"model": "deepseek-v4-pro", "messages": []}
        )
    elapsed = _time.monotonic() - start

    # Aborts shortly after the 0.5s progress threshold — NOT after the 60s the
    # other watchdogs would allow, and NOT after the 300s outer watchdog.
    assert elapsed < 5.0, (
        f"progress-stall watchdog did not abort the reasoning-then-freeze wedge "
        f"(took {elapsed:.2f}s)"
    )
    assert stream.closed is True


class _ReasoningThenBlockedNextStream:
    """PRODUCTION REPRODUCER #2 for the wedge: real reasoning advances, then
    ``__next__`` BLOCKS FOREVER (the 0%-CPU freeze observed in production:
    ``reasoning_emitted_so_far`` pinned at a constant, worker at 0% CPU, no
    further chunks of any kind reach the loop). The producer thread is wedged
    inside ``__next__`` and the consumer's ``chunk_queue.get(timeout=...)`` is
    the only thing that can unblock — it must time out and abort.
    """

    def __init__(self, release, real_chunks=5):
        self._release = release
        self.closed = False
        self._n = 0
        self._real_chunks = real_chunks

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        if self._n < self._real_chunks:
            self._n += 1
            _time.sleep(0.01)
            return _reasoning_chunk(f"real-reasoning-token-{self._n} ")
        # Freeze: block forever, never yielding another chunk (0% CPU).
        self._release.wait(timeout=30.0)
        raise StopIteration

    def close(self):
        self.closed = True
        self._release.set()


def test_reasoning_then_blocked_next_aborts_via_queue_timeout(monkeypatch):
    """The 0%-CPU freeze: real reasoning, then ``__next__`` blocks forever.
    The consumer's ``chunk_queue.get(timeout=...)`` must time out and abort with
    a retryable APITimeoutError shortly after the (short, test-only) progress
    threshold — not after the 30s the blocked ``__next__`` would otherwise hold.
    """
    monkeypatch.setattr("run_agent._stream_progress_stall_timeout_seconds", lambda: 0.5)
    monkeypatch.setattr("run_agent._stream_content_stall_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr("run_agent._post_content_stall_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr("run_agent._stream_first_content_timeout_seconds", lambda: 60.0)

    release = threading.Event()
    stream = _ReasoningThenBlockedNextStream(release, real_chunks=5)
    agent = _make_agent(monkeypatch, stream)

    try:
        start = _time.monotonic()
        with pytest.raises(openai.APITimeoutError):
            agent._interruptible_streaming_api_call(
                {"model": "deepseek-v4-pro", "messages": []}
            )
        elapsed = _time.monotonic() - start
        assert elapsed < 5.0, (
            f"queue-timeout watchdog did not abort the reasoning-then-blocked-next "
            f"freeze (took {elapsed:.2f}s)"
        )
        assert stream.closed is True
    finally:
        release.set()  # never leave the daemon producer blocked


def test_healthy_slow_reasoning_not_aborted_by_progress_watchdog(monkeypatch):
    """Conservative-guard check: a stream making REAL (non-whitespace) reasoning
    progress every iteration, even slowly, must NOT be aborted by the progress
    watchdog — it requires the FULL timeout of ZERO real advancement to fire.
    """
    monkeypatch.setattr("run_agent._stream_progress_stall_timeout_seconds", lambda: 1.0)
    monkeypatch.setattr("run_agent._stream_content_stall_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr("run_agent._post_content_stall_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr("run_agent._stream_first_content_timeout_seconds", lambda: 60.0)

    def _content_chunk(text, finish=None):
        delta = SimpleNamespace(content=text, reasoning_content=None, tool_calls=None)
        choice = SimpleNamespace(delta=delta, finish_reason=finish)
        return SimpleNamespace(choices=[choice], model="deepseek-v4-pro", usage=None)

    class _HealthySlowStream:
        def __iter__(self):
            # Real reasoning every 0.3s for ~1.5s (each resets the 1.0s bound),
            # then real content + finish. No gap exceeds the progress bound.
            for i in range(5):
                _time.sleep(0.3)
                yield _reasoning_chunk(f"thinking-step-{i} ")
            yield _content_chunk("final answer", finish="stop")

    agent = _make_agent(monkeypatch, _HealthySlowStream())
    # Healthy path returns a normal response; the no-fallback guard must not trip.
    monkeypatch.setattr(
        agent, "_interruptible_api_call",
        lambda api_kwargs: (_ for _ in ()).throw(
            AssertionError("healthy stream must not fall back")
        ),
    )

    resp = agent._interruptible_streaming_api_call(
        {"model": "deepseek-v4-pro", "messages": []}
    )
    assert resp.choices[0].message.content == "final answer"
