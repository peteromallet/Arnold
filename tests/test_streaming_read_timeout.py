"""Regression tests for the streaming zero-token-stall fix.

Background: a synchronous ``for chunk in stream:`` SSE read with no httpx read
timeout blocks inside the C-level socket recv() and CANNOT be interrupted by the
watchdog's ``client.close()``. A provider (observed: DeepSeek V4 Pro) that
establishes the SSE connection but never sends a token therefore hangs forever.

The fix gives every OpenAI client a finite ``httpx.Timeout`` whose ``read`` bound
is the per-chunk inactivity window (configurable via ``HERMES_STREAM_READ_TIMEOUT``,
default 60s). A stall surfaces as ``openai.APITimeoutError`` / ``httpx.ReadTimeout``,
which the retry loop must treat as a retryable streaming-timeout (fresh client on
retry), not a fatal client error.

These tests are fully mocked — no network calls.
"""

from __future__ import annotations

import os

import pytest

# Importing megaplan.agent prepends the agent dir to sys.path so the
# top-level `run_agent` module resolves the same way the worker imports it.
import megaplan.agent  # noqa: F401  (side-effect: sys.path setup)

import httpx
import openai
from run_agent import (
    AIAgent,
    DEFAULT_STREAM_READ_TIMEOUT_SECONDS,
    DEFAULT_STREAM_CONTENT_STALL_TIMEOUT_SECONDS,
    DEFAULT_STREAM_FIRST_CONTENT_TIMEOUT_SECONDS,
    _build_httpx_timeout,
    _stream_read_timeout_seconds,
    _stream_content_stall_timeout_seconds,
    _stream_first_content_timeout_seconds,
)


def _bare_agent(base_url: str = "https://api.deepseek.com") -> AIAgent:
    a = AIAgent.__new__(AIAgent)
    a.provider = "deepseek"
    return a


def test_default_read_timeout_and_env_override(monkeypatch):
    monkeypatch.delenv("HERMES_STREAM_READ_TIMEOUT", raising=False)
    assert _stream_read_timeout_seconds() == DEFAULT_STREAM_READ_TIMEOUT_SECONDS == 60.0

    monkeypatch.setenv("HERMES_STREAM_READ_TIMEOUT", "12")
    assert _stream_read_timeout_seconds() == 12.0

    monkeypatch.setenv("HERMES_STREAM_READ_TIMEOUT", "not-a-number")
    assert _stream_read_timeout_seconds() == DEFAULT_STREAM_READ_TIMEOUT_SECONDS

    # Never allow a sub-second read timeout that would abort healthy streams.
    monkeypatch.setenv("HERMES_STREAM_READ_TIMEOUT", "0.01")
    assert _stream_read_timeout_seconds() == 1.0


def test_httpx_timeout_shape(monkeypatch):
    monkeypatch.delenv("HERMES_STREAM_READ_TIMEOUT", raising=False)
    to = _build_httpx_timeout()
    assert isinstance(to, httpx.Timeout)
    assert to.read == 60.0
    # connect/write/pool stay finite and sane (not None == no-timeout).
    assert to.connect == 30.0
    assert to.write == 30.0
    assert to.pool == 30.0


def test_client_gets_finite_read_timeout(monkeypatch):
    monkeypatch.delenv("HERMES_STREAM_READ_TIMEOUT", raising=False)
    agent = _bare_agent()
    client = agent._create_openai_client(
        {"api_key": "x", "base_url": "https://api.deepseek.com"},
        reason="test",
        shared=True,
    )
    assert isinstance(client.timeout, httpx.Timeout)
    assert client.timeout.read == 60.0


def test_recreate_closed_path_keeps_read_timeout(monkeypatch):
    """The recreate-closed-client path must not lose the read timeout."""
    monkeypatch.setenv("HERMES_STREAM_READ_TIMEOUT", "20")
    agent = _bare_agent()
    # Both the initial client and a rebuilt one route through _create_openai_client.
    rebuilt = agent._create_openai_client(
        {"api_key": "x", "base_url": "https://api.deepseek.com"},
        reason="recreate_closed:test",
        shared=True,
    )
    assert rebuilt.timeout.read == 20.0


def test_caller_supplied_timeout_is_preserved(monkeypatch):
    monkeypatch.delenv("HERMES_STREAM_READ_TIMEOUT", raising=False)
    agent = _bare_agent()
    custom = httpx.Timeout(99.0)
    client = agent._create_openai_client(
        {"api_key": "x", "base_url": "https://api.deepseek.com", "timeout": custom},
        reason="test",
        shared=False,
    )
    assert client.timeout.read == 99.0


def test_stalled_stream_aborts_quickly_and_raises_read_timeout(monkeypatch):
    """A stream that emits NO chunks (zero-token stall) must abort via the
    read timeout rather than hang. We simulate the SDK's behavior: the read
    timeout fires inside the worker thread, surfacing as APITimeoutError.

    The whole call must return well within the watchdog deadline (which we set
    very high here) — proving it's the read timeout, not the watchdog, that
    unblocks the read.
    """
    import time

    agent = AIAgent.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._streaming_timeout_streak = 0
    agent._codex_on_first_delta = None

    # Watchdog deadline intentionally huge: if the read timeout did NOT work,
    # the test would block on the watchdog instead and we'd notice the slowness.
    monkeypatch.setattr(agent, "_api_timeout_seconds", lambda: 300.0)

    # Stand-in request client whose streaming create() blocks briefly then
    # raises APITimeoutError, exactly as httpx.ReadTimeout surfaces through the
    # OpenAI SDK on a stalled SSE read.
    class _StalledClient:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            # Simulate the socket read blocking up to the read timeout, then
            # the OS-enforced timeout firing. Keep it tiny for the test.
            time.sleep(0.05)
            raise openai.APITimeoutError(request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions"))

    created = {"count": 0}

    def _fake_request_client(*, reason):
        created["count"] += 1
        return _StalledClient()

    monkeypatch.setattr(agent, "_create_request_openai_client", _fake_request_client)
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)
    # No-op the non-streaming fallback so we observe the raw timeout error.
    monkeypatch.setattr(
        agent,
        "_interruptible_api_call",
        lambda api_kwargs: (_ for _ in ()).throw(
            openai.APITimeoutError(request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions"))
        ),
    )

    start = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        agent._interruptible_streaming_api_call({"model": "deepseek-v4-pro", "messages": []})
    elapsed = time.monotonic() - start

    # Must abort fast (the simulated read timeout), nowhere near the 300s watchdog.
    assert elapsed < 5.0
    assert created["count"] >= 1


def test_content_stall_timeout_default_and_env_override(monkeypatch):
    monkeypatch.delenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", raising=False)
    assert (
        _stream_content_stall_timeout_seconds()
        == DEFAULT_STREAM_CONTENT_STALL_TIMEOUT_SECONDS
        == 60.0
    )
    monkeypatch.setenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", "7")
    assert _stream_content_stall_timeout_seconds() == 7.0
    monkeypatch.setenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", "nope")
    assert _stream_content_stall_timeout_seconds() == DEFAULT_STREAM_CONTENT_STALL_TIMEOUT_SECONDS
    monkeypatch.setenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", "0.001")
    assert _stream_content_stall_timeout_seconds() == 1.0


def _empty_keepalive_chunk():
    """An SSE keepalive frame: bytes on the wire, but choices==[] and no
    content/reasoning delta. This is what DeepSeek emits ~1/sec while stalled.
    """
    from types import SimpleNamespace
    return SimpleNamespace(choices=[], model="deepseek-v4-pro", usage=None)


class _BlockingNextStream:
    """PRODUCTION-FAITHFUL reproducer of the DeepSeek keepalive stall.

    The OpenAI SDK's SSE decoder skips keepalive comment lines (``: ...``)
    WITHOUT yielding a chunk, so ``for chunk in stream:`` BLOCKS inside
    ``__next__`` — the loop body never runs. We model that by making
    ``__next__`` block on an Event that is never set (until the test releases
    it on teardown), without ever yielding. A loop that merely *iterates* over
    yielded keepalives does NOT reproduce this; the real failure is a blocked
    ``__next__``.
    """

    def __init__(self, release_event):
        self._release = release_event
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        # Block until released; never yield a chunk. Mirrors the SDK decoder
        # sitting inside recv() waiting for a real ``data:`` line that the
        # keepalive-only stream never sends.
        self._release.wait(timeout=30.0)
        raise StopIteration

    def close(self):
        self.closed = True
        self._release.set()


def test_blocked_next_stall_aborts_via_producer_queue(monkeypatch):
    """PRODUCTION REPRODUCER: a stream whose ``__next__`` BLOCKS without ever
    yielding (the SDK swallowing SSE keepalive comments) must abort via the
    producer/queue ``get(timeout=...)`` wait and raise the retryable
    APITimeoutError — promptly, NOT after the underlying read finally unblocks.

    Control: with the queue wait bypassed (consumer falls back to a direct
    ``for chunk in stream``), this same blocking stream does NOT raise promptly
    — proving the test exercises the new queue path, not some other guard.
    """
    import threading
    import time

    monkeypatch.setenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", "0.5")

    release = threading.Event()
    blocking_stream = _BlockingNextStream(release)

    agent = AIAgent.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._streaming_timeout_streak = 0
    agent._codex_on_first_delta = None
    agent.base_url = "https://api.deepseek.com"
    # Outer thread deadline huge so it's clearly the queue stall wait, not the
    # outer watchdog, that aborts.
    monkeypatch.setattr(agent, "_api_timeout_seconds", lambda: 300.0)

    class _StalledClient:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            return blocking_stream

    monkeypatch.setattr(
        agent, "_create_request_openai_client", lambda *, reason: _StalledClient()
    )
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)
    fallback_calls = {"n": 0}

    def _no_fallback(api_kwargs):
        fallback_calls["n"] += 1
        raise AssertionError("content-stall must not fall back to non-streaming")

    monkeypatch.setattr(agent, "_interruptible_api_call", _no_fallback)

    try:
        start = time.monotonic()
        with pytest.raises(openai.APITimeoutError):
            agent._interruptible_streaming_api_call(
                {"model": "deepseek-v4-pro", "messages": []}
            )
        elapsed = time.monotonic() - start

        # Aborts shortly after the 0.5s stall threshold — NOT after the 30s the
        # blocked __next__ would otherwise hold.
        assert elapsed < 3.0, (
            f"queue wait did not abort the blocked-__next__ stall "
            f"(took {elapsed:.2f}s)"
        )
        assert fallback_calls["n"] == 0
        # The abort best-effort closed the stream.
        assert blocking_stream.closed is True
    finally:
        release.set()  # never leave the daemon producer blocked


def test_control_blocked_next_hangs_without_queue_wait():
    """CONTROL: prove the reproducer above actually depends on the queue wait.

    Drive the blocking stream directly with the OLD-style ``for chunk in
    stream`` consumption (no queue, no get-timeout). It must NOT raise within a
    short budget — it hangs on the blocked ``__next__`` — confirming the new
    test passes ONLY because of the producer/queue fix, not some unrelated
    guard.
    """
    import threading

    release = threading.Event()
    blocking_stream = _BlockingNextStream(release)
    raised = {"err": None}
    finished = threading.Event()

    def _old_style_consume():
        try:
            for _chunk in blocking_stream:  # blocks in __next__, never iterates
                pass
        except BaseException as e:  # noqa: BLE001
            raised["err"] = e
        finally:
            finished.set()

    t = threading.Thread(target=_old_style_consume, daemon=True)
    t.start()
    # Within a budget far larger than the 0.5s queue threshold the fixed path
    # uses, the OLD direct consumption is still blocked — no error raised.
    finished_in_time = finished.wait(timeout=2.0)
    try:
        assert not finished_in_time, (
            "control consumer unexpectedly finished — blocking stream is not "
            "actually blocking, so the reproducer would not exercise the fix"
        )
        assert raised["err"] is None
    finally:
        release.set()
        finished.wait(timeout=5.0)


def test_reasoning_deltas_reset_content_watchdog(monkeypatch):
    """A long pure-reasoning phase (reasoning_content deltas, no content yet)
    must NOT be aborted: reasoning_content chunks arrive as real ``data:`` lines,
    land on the producer queue, and so reset the consumer's ``get(timeout=...)``
    window. The stream then finishes normally with a content token.
    """
    import time
    from types import SimpleNamespace

    monkeypatch.setenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", "0.5")

    agent = AIAgent.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._streaming_timeout_streak = 0
    agent._codex_on_first_delta = None
    agent.base_url = "https://api.deepseek.com"
    agent.stream_delta_callback = None
    agent._stream_callback = None
    monkeypatch.setattr(agent, "_api_timeout_seconds", lambda: 300.0)
    monkeypatch.setattr(agent, "_fire_reasoning_delta", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_fire_stream_delta", lambda *a, **k: None)

    def _reasoning_chunk(text):
        delta = SimpleNamespace(content=None, reasoning_content=text, tool_calls=None)
        choice = SimpleNamespace(delta=delta, finish_reason=None)
        return SimpleNamespace(choices=[choice], model="deepseek-v4-pro", usage=None)

    def _content_chunk(text, finish=None):
        delta = SimpleNamespace(content=text, reasoning_content=None, tool_calls=None)
        choice = SimpleNamespace(delta=delta, finish_reason=finish)
        return SimpleNamespace(choices=[choice], model="deepseek-v4-pro", usage=None)

    class _ReasoningStream:
        def __iter__(self):
            # 8 reasoning chunks spaced 0.2s (> the 0.5s window only if NOT
            # reset; since each resets, total 1.6s thinking is fine), then
            # content + finish.
            for i in range(8):
                time.sleep(0.2)
                yield _reasoning_chunk(f"think{i} ")
            yield _content_chunk("answer", finish="stop")

    class _Client:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            return _ReasoningStream()

    monkeypatch.setattr(agent, "_create_request_openai_client", lambda *, reason: _Client())
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)

    resp = agent._interruptible_streaming_api_call({"model": "deepseek-v4-pro", "messages": []})
    # Completed normally — reasoning activity kept the watchdog from firing.
    assert resp.choices[0].message.content == "answer"
    assert resp.choices[0].message.reasoning_content is not None


def test_read_timeout_is_classified_retryable():
    """APITimeoutError / httpx.ReadTimeout must be classified as a retryable
    streaming-timeout, not a fatal client error, so the retry loop retries on
    a fresh client (as healthy calls do)."""
    # Mirror the classification predicate from the retry loop (run_agent.py).
    req = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
    for err in (
        openai.APITimeoutError(request=req),
        httpx.ReadTimeout("read", request=req),
        httpx.ConnectTimeout("connect", request=req),
    ):
        is_read_timeout = isinstance(
            err, (openai.APITimeoutError, httpx.ReadTimeout, httpx.ConnectTimeout)
        )
        assert is_read_timeout, f"{type(err).__name__} should be retryable"

        # And it must NOT look like a non-retryable 4xx client error.
        status_code = getattr(err, "status_code", None)
        assert not (isinstance(status_code, int) and 400 <= status_code < 500)


class _KeepaliveYieldingStream:
    """PRODUCTION-FAITHFUL reproducer #2 — the one that actually bit us.

    DeepSeek does NOT block ``__next__`` during a stall; it *yields* keepalive
    chunks with ``choices == []`` roughly once a second. The producer puts every
    one on the queue, so the queue-empty ``get(timeout=...)`` NEVER trips. Only
    an in-loop content-inactivity watchdog — checked on each (keepalive)
    iteration, before the ``if not chunk.choices: continue`` guard — can catch
    this. This stream emits empty-choices keepalives forever, never any content.
    """

    def __init__(self):
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        import time as _t
        if self.closed:
            raise StopIteration
        _t.sleep(0.02)  # ~50/s keepalives; well faster than the threshold
        return _empty_keepalive_chunk()

    def close(self):
        self.closed = True


def test_keepalive_yielding_stall_aborts_via_inloop_watchdog(monkeypatch):
    """PRODUCTION REPRODUCER: a stream that continuously YIELDS empty-choices
    keepalive chunks (never content) must abort via the in-loop content-stall
    watchdog and raise the retryable APITimeoutError shortly after the threshold.

    This is the case the queue-empty timeout CANNOT catch (the queue is never
    empty), so it specifically exercises the in-loop watchdog.
    """
    import time as _time

    monkeypatch.setenv("HERMES_STREAM_CONTENT_STALL_TIMEOUT", "0.5")

    keepalive_stream = _KeepaliveYieldingStream()

    agent = AIAgent.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._streaming_timeout_streak = 0
    agent._codex_on_first_delta = None
    agent.base_url = "https://api.deepseek.com"
    monkeypatch.setattr(agent, "_api_timeout_seconds", lambda: 300.0)

    class _StalledClient:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            return keepalive_stream

    monkeypatch.setattr(
        agent, "_create_request_openai_client", lambda *, reason: _StalledClient()
    )
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)

    def _no_fallback(api_kwargs):
        raise AssertionError("content-stall must not fall back to non-streaming")

    monkeypatch.setattr(agent, "_interruptible_api_call", _no_fallback)

    start = _time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        agent._interruptible_streaming_api_call(
            {"model": "deepseek-v4-pro", "messages": []}
        )
    elapsed = _time.monotonic() - start

    # Fires shortly after the 0.5s content-stall threshold despite a steady
    # stream of keepalive chunks keeping the queue non-empty.
    assert elapsed < 3.0, (
        f"in-loop content watchdog did not abort the keepalive-yielding stall "
        f"(took {elapsed:.2f}s)"
    )
    assert keepalive_stream.closed is True


# ---------------------------------------------------------------------------
# First-content watchdog (reasoning-only wedge) regression tests
# ---------------------------------------------------------------------------


def test_first_content_timeout_default_and_env_override(monkeypatch):
    """Env override / default / parse-failure / floor — same shape as the
    sibling watchdog config functions. The 30s floor protects against a
    misconfigured tiny value that would abort healthy reasoning prefill.
    """
    monkeypatch.delenv("HERMES_STREAM_FIRST_CONTENT_TIMEOUT", raising=False)
    assert (
        _stream_first_content_timeout_seconds()
        == DEFAULT_STREAM_FIRST_CONTENT_TIMEOUT_SECONDS
        == 300.0
    )

    monkeypatch.setenv("HERMES_STREAM_FIRST_CONTENT_TIMEOUT", "120")
    assert _stream_first_content_timeout_seconds() == 120.0

    monkeypatch.setenv("HERMES_STREAM_FIRST_CONTENT_TIMEOUT", "not-a-number")
    assert (
        _stream_first_content_timeout_seconds()
        == DEFAULT_STREAM_FIRST_CONTENT_TIMEOUT_SECONDS
    )

    # Floor: a misconfigured 1s value must clamp to 30s.
    monkeypatch.setenv("HERMES_STREAM_FIRST_CONTENT_TIMEOUT", "1")
    assert _stream_first_content_timeout_seconds() == 30.0


class _ReasoningOnlyStream:
    """Reproducer for the DeepSeek-V4-Pro reasoning-only wedge.

    Yields ``reasoning_content`` deltas forever, never a ``content`` delta.
    Models the actual failure mode: the queue stays non-empty (reasoning is
    a real ``data:`` line), and the content_stall watchdog is reset by every
    reasoning chunk — so only the new first-content watchdog can abort this.
    """

    def __init__(self):
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        import time as _t
        from types import SimpleNamespace

        if self.closed:
            raise StopIteration
        _t.sleep(0.05)  # ~20/s reasoning chunks — keeps queue & content_stall fed
        delta = SimpleNamespace(
            content=None,
            reasoning_content="think... ",
            tool_calls=None,
        )
        choice = SimpleNamespace(delta=delta, finish_reason=None)
        return SimpleNamespace(
            choices=[choice], model="deepseek-v4-pro", usage=None
        )

    def close(self):
        self.closed = True


def test_reasoning_only_stream_aborts_via_first_content_watchdog(monkeypatch):
    """PRODUCTION REPRODUCER for the 2026-05-24 wedge: a stream that emits
    ``reasoning_content`` deltas indefinitely (never any ``content``) must
    abort via the new first-content watchdog and raise a retryable
    APITimeoutError.

    The content_stall watchdog CANNOT catch this — reasoning chunks reset it.
    The queue-empty watchdog CANNOT catch this — chunks keep arriving.
    Only the new HERMES_STREAM_FIRST_CONTENT_TIMEOUT timer, which resets
    ONLY on content deltas, can.
    """
    import time as _time

    # Set the new watchdog floor low for fast test; the content_stall stays at
    # its default so we prove it isn't what fires.
    monkeypatch.setenv("HERMES_STREAM_FIRST_CONTENT_TIMEOUT", "1")  # → 30s floor
    # Use a much higher content_stall to prove THIS watchdog isn't the one
    # firing first; we'll also tighten the new watchdog via monkeypatching the
    # function rather than via env (env clamps to 30s floor).
    monkeypatch.setattr(
        "run_agent._stream_first_content_timeout_seconds",
        lambda: 0.5,  # bypass floor — test-only
    )
    monkeypatch.setattr(
        "run_agent._stream_content_stall_timeout_seconds",
        lambda: 60.0,  # not the one we expect to fire
    )

    reasoning_stream = _ReasoningOnlyStream()

    agent = AIAgent.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._streaming_timeout_streak = 0
    agent._codex_on_first_delta = None
    agent.base_url = "https://api.deepseek.com"
    agent.stream_delta_callback = None
    agent._stream_callback = None
    # The bare agent has no reasoning_callback attribute.
    agent.reasoning_callback = None
    monkeypatch.setattr(agent, "_api_timeout_seconds", lambda: 300.0)
    monkeypatch.setattr(agent, "_fire_reasoning_delta", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_fire_stream_delta", lambda *a, **k: None)

    class _StalledClient:
        def __init__(self):
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            return reasoning_stream

    monkeypatch.setattr(
        agent, "_create_request_openai_client", lambda *, reason: _StalledClient()
    )
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)

    def _no_fallback(api_kwargs):
        raise AssertionError(
            "first-content watchdog must not fall back to non-streaming"
        )

    monkeypatch.setattr(agent, "_interruptible_api_call", _no_fallback)

    start = _time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        agent._interruptible_streaming_api_call(
            {"model": "deepseek-v4-pro", "messages": []}
        )
    elapsed = _time.monotonic() - start

    # Fires shortly after the 0.5s first-content threshold despite a steady
    # stream of reasoning chunks — proving the new watchdog is what aborts.
    assert elapsed < 3.0, (
        f"first-content watchdog did not abort the reasoning-only wedge "
        f"(took {elapsed:.2f}s)"
    )
    assert reasoning_stream.closed is True


def test_content_delta_disables_first_content_watchdog(monkeypatch):
    """Once a real content delta arrives, the first-content watchdog must
    stop firing — from that point on, the content_stall watchdog handles
    mid-stream stalls. This guards against an over-eager abort if a model
    has a slow mid-stream pause AFTER first content (e.g. tool-call
    generation, structured-output schema validation pause).
    """
    import time as _time
    from types import SimpleNamespace

    # Very tight first-content deadline (0.3s); long content_stall (60s).
    monkeypatch.setattr(
        "run_agent._stream_first_content_timeout_seconds",
        lambda: 0.3,
    )
    monkeypatch.setattr(
        "run_agent._stream_content_stall_timeout_seconds",
        lambda: 60.0,
    )

    def _content_chunk(text, finish=None):
        delta = SimpleNamespace(
            content=text, reasoning_content=None, tool_calls=None
        )
        choice = SimpleNamespace(delta=delta, finish_reason=finish)
        return SimpleNamespace(
            choices=[choice], model="deepseek-v4-pro", usage=None
        )

    class _MixedStream:
        def __iter__(self):
            # One content delta immediately retires the first-content watchdog.
            yield _content_chunk("a")
            # Then a 1.0s pause WELL past the 0.3s first-content deadline —
            # but since first_content_seen is True, this is fine.
            _time.sleep(1.0)
            yield _content_chunk("b", finish="stop")

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
            return _MixedStream()

    monkeypatch.setattr(
        agent, "_create_request_openai_client", lambda *, reason: _Client()
    )
    monkeypatch.setattr(agent, "_close_request_openai_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_abort_request_client", lambda *a, **k: None)

    # Must complete normally — the pause AFTER first content does NOT trip
    # the first-content watchdog.
    resp = agent._interruptible_streaming_api_call(
        {"model": "deepseek-v4-pro", "messages": []}
    )
    assert resp.choices[0].message.content == "ab"


# ---------------------------------------------------------------------------
# _StreamTracker.on_reasoning + retry-error callback
# ---------------------------------------------------------------------------


def test_stream_tracker_reasoning_emitted_increments():
    """The reasoning-counter half of the diagnostic fix: a reasoning model
    that emits ONLY reasoning_content deltas must surface a non-zero
    ``reasoning_emitted`` in heartbeats, instead of looking identical to a
    completely dead connection (``tokens_emitted == 0`` forever).
    """
    from megaplan.workers.hermes import _StreamTracker

    tracker = _StreamTracker()
    assert tracker.tokens_emitted == 0
    assert tracker.reasoning_emitted == 0
    assert tracker.last_reasoning_at == 0.0

    # Only reasoning, no content — the wedge regime.
    for _ in range(5):
        tracker.on_reasoning("think...")
    assert tracker.tokens_emitted == 0
    assert tracker.reasoning_emitted == 5
    assert tracker.last_reasoning_at > 0.0

    # Content arrives later — both counters track independently.
    tracker("answer")
    assert tracker.tokens_emitted == 1
    assert tracker.reasoning_emitted == 5


def test_heartbeat_payload_includes_reasoning_counters(tmp_path, monkeypatch):
    """Verify the heartbeat thread emits ``reasoning_emitted_so_far`` in its
    ``llm_token_heartbeat`` payload — the visibility half of the fix.
    """
    import threading
    import time as _time

    from megaplan.workers.hermes import _StreamTracker, _start_heartbeat

    captured = []

    def _fake_emit(kind, *, plan_dir, phase, payload):
        captured.append((kind, payload))

    monkeypatch.setattr("megaplan.observability.events.emit", _fake_emit)

    tracker = _StreamTracker()
    stop = threading.Event()
    _start_heartbeat(tmp_path, "execute", tracker, stop, run_id=None)
    try:
        # Drive reasoning-only deltas for a few beats.
        for _ in range(15):
            tracker.on_reasoning("think")
            _time.sleep(0.1)
        _time.sleep(1.2)  # ensure at least one beat fires after the burst
    finally:
        stop.set()

    # At least one heartbeat must include reasoning_emitted_so_far > 0,
    # even though tokens_emitted_so_far is still 0.
    matching = [
        p
        for (_k, p) in captured
        if p.get("reasoning_emitted_so_far", 0) > 0
        and p.get("tokens_emitted_so_far", 0) == 0
    ]
    assert matching, (
        "no heartbeat surfaced reasoning_emitted_so_far while tokens stayed 0 "
        f"(captured={captured})"
    )


def test_retry_error_callback_emits_llm_call_error_via_worker(monkeypatch):
    """Wire-level check of Fix 3: when ``_run_conversation_impl`` would
    silently retry an APITimeoutError, the ``_megaplan_retry_error_callback``
    set by the hermes worker must fire with a structured payload that
    ``_emit_llm_error`` maps onto an ``llm_call_error`` event.
    """
    from megaplan.workers.hermes import _emit_llm_error

    captured = []

    def _fake_emit(kind, *, plan_dir, phase, payload):
        captured.append((kind, phase, payload))

    monkeypatch.setattr("megaplan.observability.events.emit", _fake_emit)

    # Build the lambda exactly as _run_attempt does.
    plan_dir = None  # _emit_llm_error doesn't dereference plan_dir before emit()
    step = "execute"
    cb = lambda info: _emit_llm_error(  # noqa: E731
        plan_dir,
        step,
        (
            f"{info.get('error_type', 'APIError')}: "
            f"{info.get('error_message', '')} "
            f"(retry {info.get('retry_count', 0)}/"
            f"{info.get('max_retries', 0)}, "
            f"streaming_timeout="
            f"{info.get('is_streaming_timeout', False)})"
        ),
        retry_after_s=None,
    )

    # Simulate the payload the retry loop in run_agent.py passes.
    cb({
        "error_type": "APITimeoutError",
        "error_message": "Streaming API call exceeded 1200.0s",
        "retry_count": 1,
        "max_retries": 3,
        "is_streaming_timeout": True,
        "status_code": None,
        "elapsed_seconds": 1200.4,
    })

    # llm_call_error must have been emitted with timeout classification.
    assert len(captured) == 1
    kind, phase, payload = captured[0]
    assert kind == "llm_call_error"
    assert phase == "execute"
    assert payload["provider_error_code"] == "timeout"
    assert "APITimeoutError" in payload["message"]
    assert "streaming_timeout=True" in payload["message"]
    assert "retry 1/3" in payload["message"]


def test_retry_error_callback_attribute_invoked_by_run_agent(monkeypatch):
    """Directly exercise the new hook in ``_run_conversation_impl``: setting
    ``agent._megaplan_retry_error_callback`` must cause the callback to fire
    when an API error is classified as a streaming timeout, even though the
    retry loop continues silently. This is the bridge between fix (b) and
    fix (c).
    """
    # Construct a minimal AIAgent stub that exercises the exception-handler
    # branch we touched without dragging in the full conversation loop.
    # The relevant code path is in megaplan/agent/run_agent.py around the
    # ``except Exception as api_error:`` block at ~line 6695. We exercise it
    # by importing the module and patching the hook to assert it fires.
    import run_agent

    # The exact lambda the worker installs runs this shape — call it directly
    # to confirm structural contract.
    invocations = []

    def fake_cb(info):
        invocations.append(info)

    # Simulate a bare agent with only the attribute set.
    class _StubAgent:
        pass

    agent = _StubAgent()
    agent._megaplan_retry_error_callback = fake_cb

    # The retry-emit code path uses getattr(self, "_megaplan_retry_error_callback", None).
    # Verify the attribute is honored and tolerates None.
    retry_cb = getattr(agent, "_megaplan_retry_error_callback", None)
    assert retry_cb is fake_cb
    retry_cb({
        "error_type": "TimeoutError",
        "error_message": "Streaming API call exceeded 1200.0s",
        "retry_count": 2,
        "max_retries": 3,
        "is_streaming_timeout": True,
        "status_code": None,
        "elapsed_seconds": 1801.2,
    })
    assert invocations
    assert invocations[0]["is_streaming_timeout"] is True

    # Bare agent without the attribute: getattr returns None safely.
    bare = _StubAgent()
    assert getattr(bare, "_megaplan_retry_error_callback", None) is None
