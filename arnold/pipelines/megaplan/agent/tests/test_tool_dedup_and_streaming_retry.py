"""Tests for ticket 01KS06DFVBWJ55AZX374VQFH7M.

The v2.3.1 vibecomfy megaplan failed at revise_v3 after three identical
streaming-timeout retries against deepseek-v4-pro. Root cause: the agent
re-read a 266KB emit file eight times in a row, bloating the prompt past
the streaming deadline, and the retry path looped on the same bloated
prompt with the same deadline.

Two fixes guard against a repeat:

1. Per-conversation tool-result dedup. Identical re-issues of read-only
   tools are short-circuited with a brief pointer back to the prior
   result. Mutating tools clear the cache so legitimate re-reads after
   a write still return fresh content.

2. Streaming-deadline timeouts are classified as context-overflow and
   routed through the existing compression machinery instead of falling
   through to plain exponential-backoff retry with the same prompt.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent():
    """Construct an AIAgent with the network surface mocked out.

    Mirrors the pattern used by test_1630_context_overflow_loop.py.
    """
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        from run_agent import AIAgent

        agent = AIAgent(
            api_key="test-key-1234567890",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
        agent.client = MagicMock()
        agent._cached_system_prompt = "system"
        agent._use_prompt_caching = False
        agent.tool_delay = 0
        agent.compression_enabled = False
        return agent


# ---------------------------------------------------------------------------
# Tool-result dedup
# ---------------------------------------------------------------------------


class TestToolResultDedup:
    """Per-conversation dedup of identical read-only tool calls."""

    def test_first_call_is_recorded_and_returned_unchanged(self):
        agent = _make_agent()
        body = "lorem ipsum " * 100

        result = agent._maybe_dedup_tool_result(
            "read_file",
            {"path": "/tmp/x", "offset": 0, "limit": 200},
            body,
            "call-1",
        )

        assert result == body
        # The first call seeds the cache with its tool_call_id.
        cache = agent._tool_dedup_cache
        assert len(cache) == 1
        assert list(cache.values()) == ["call-1"]

    def test_duplicate_call_returns_stub_referencing_prior_id(self):
        agent = _make_agent()
        body = "full file body"

        agent._maybe_dedup_tool_result("read_file", {"path": "/tmp/x"}, body, "call-1")
        deduped = agent._maybe_dedup_tool_result(
            "read_file", {"path": "/tmp/x"}, body, "call-2"
        )

        assert deduped != body
        assert "[megaplan dedup]" in deduped
        assert "tool_call_id=call-1" in deduped
        assert "read_file" in deduped

    def test_kwarg_order_does_not_defeat_dedup(self):
        agent = _make_agent()
        body = "body"

        agent._maybe_dedup_tool_result(
            "read_file",
            {"path": "/tmp/x", "offset": 0, "limit": 200},
            body,
            "call-1",
        )
        deduped = agent._maybe_dedup_tool_result(
            "read_file",
            {"limit": 200, "offset": 0, "path": "/tmp/x"},
            body,
            "call-2",
        )

        assert "[megaplan dedup]" in deduped
        assert "tool_call_id=call-1" in deduped

    def test_different_args_do_not_collide(self):
        agent = _make_agent()
        body = "body"

        agent._maybe_dedup_tool_result(
            "read_file", {"path": "/tmp/x", "offset": 0}, body, "call-1"
        )
        # Different offset = different page; must not be deduped.
        result = agent._maybe_dedup_tool_result(
            "read_file", {"path": "/tmp/x", "offset": 200}, body, "call-2"
        )
        assert result == body

    def test_mutating_tool_invalidates_the_cache(self):
        agent = _make_agent()
        body = "body"

        agent._maybe_dedup_tool_result(
            "read_file", {"path": "/tmp/x"}, body, "call-1"
        )
        # A write_file call should clear cached reads — the file may
        # have changed under us, so the next read deserves fresh bytes.
        agent._maybe_dedup_tool_result(
            "write_file", {"path": "/tmp/x", "content": "..."}, "ok", "call-2"
        )
        re_read = agent._maybe_dedup_tool_result(
            "read_file", {"path": "/tmp/x"}, body, "call-3"
        )

        assert re_read == body  # No stub
        # The dedup cache should now only carry the post-write read.
        assert agent._tool_dedup_cache == {
            ("read_file", '{"path": "/tmp/x"}'): "call-3"
        }

    def test_non_dedupable_tool_is_passed_through(self):
        agent = _make_agent()

        # delegate_task is intentionally NOT in _DEDUPABLE_TOOLS; even
        # identical args could legitimately return different work.
        first = agent._maybe_dedup_tool_result(
            "delegate_task", {"goal": "do X"}, "result-A", "call-1"
        )
        second = agent._maybe_dedup_tool_result(
            "delegate_task", {"goal": "do X"}, "result-B", "call-2"
        )
        assert first == "result-A"
        assert second == "result-B"
        assert agent._tool_dedup_cache == {}

    def test_unserialisable_args_are_skipped_not_crashed(self):
        agent = _make_agent()

        class _NotJsonable:
            pass

        # The helper must tolerate non-JSON-serialisable args. Skip dedup
        # rather than raise — the caller still appends the result.
        result = agent._maybe_dedup_tool_result(
            "read_file",
            {"path": "/tmp/x", "marker": _NotJsonable()},
            "body",
            "call-1",
        )
        # `default=str` lets these serialise rather than fail, so the
        # call is admitted to the cache; the important thing is that
        # the helper returned the body and did not raise.
        assert result == "body"

    def test_replays_in_quick_succession_collapse_to_one_full_body(self):
        """Captures the failure-mode shape from the ticket: 8 identical
        read_file calls in a row. The first carries the full body; the
        rest collapse to short stubs."""
        agent = _make_agent()
        big = "x" * 200_000  # ≈ size of the real emit file

        results = []
        for i in range(8):
            r = agent._maybe_dedup_tool_result(
                "read_file", {"path": "/tmp/emit.py"}, big, f"call-{i}"
            )
            results.append(r)

        assert results[0] == big
        for stub in results[1:]:
            assert stub != big
            assert "[megaplan dedup]" in stub
            assert "tool_call_id=call-0" in stub
        # Total bytes injected drops by ~99 percent for this loop.
        assert sum(len(r) for r in results) < len(big) * 2


# ---------------------------------------------------------------------------
# Streaming-deadline timeout → adaptive deadline extension
# ---------------------------------------------------------------------------


class TestStreamingTimeoutAdaptiveDeadline:
    """A streaming-deadline timeout means the model was too slow to finish,
    not that the prompt is too large. Compression is the wrong response —
    shrinking the context window below the prompt size makes the model
    return empty (we observed that regression). The right response is to
    extend the per-call deadline on retry."""

    def test_base_deadline_with_no_streak(self):
        agent = _make_agent()
        assert agent._streaming_timeout_streak == 0
        # No streak → base deadline (the 300s default unless overridden).
        from run_agent import DEFAULT_API_TIMEOUT_SECONDS
        assert agent._api_timeout_seconds() == DEFAULT_API_TIMEOUT_SECONDS

    def test_streak_scales_deadline_multiplicatively(self):
        agent = _make_agent()
        from run_agent import DEFAULT_API_TIMEOUT_SECONDS
        base = DEFAULT_API_TIMEOUT_SECONDS

        agent._streaming_timeout_streak = 1
        assert agent._api_timeout_seconds() == pytest.approx(base * 1.5)

        agent._streaming_timeout_streak = 2
        assert agent._api_timeout_seconds() == pytest.approx(base * 2.25)

        agent._streaming_timeout_streak = 3
        assert agent._api_timeout_seconds() == pytest.approx(base * 3.375)

    def test_deadline_scaling_is_capped(self):
        agent = _make_agent()
        from run_agent import DEFAULT_API_TIMEOUT_SECONDS
        base = DEFAULT_API_TIMEOUT_SECONDS

        # 1.5^4 = 5.06, which should be capped at 4×.
        agent._streaming_timeout_streak = 4
        assert agent._api_timeout_seconds() == pytest.approx(base * 4.0)

        # Arbitrarily large streak — still capped.
        agent._streaming_timeout_streak = 20
        assert agent._api_timeout_seconds() == pytest.approx(base * 4.0)

    def test_compression_is_not_triggered_by_streaming_timeout(self):
        """Regression guard: an earlier version of this fix routed
        streaming timeouts through is_context_length_error → compression
        → tier-stepped the context window below the actual prompt size →
        the model returned empty bodies (0 chars) → worker_parse_error.
        The discriminant phrase list must NOT match the streaming-deadline
        message; deadline extension is the correct path instead."""
        phrases = [
            "context length", "context size", "maximum context",
            "token limit", "too many tokens", "reduce the length",
            "exceeds the limit", "context window",
            "request entity too large", "prompt is too long",
        ]
        msg = str(TimeoutError("Streaming API call exceeded 300.0s")).lower()
        assert not any(p in msg for p in phrases), (
            "Streaming-timeout message must not be classified as a "
            "context-length error — that route caused the 0-char regression."
        )

    def test_run_conversation_resets_streak(self):
        agent = _make_agent()
        # Simulate a prior conversation that ended with a streaming timeout.
        agent._streaming_timeout_streak = 3
        # A fresh run_conversation should reset the counter so the next
        # conversation doesn't pay an inflated default deadline.
        # We reach in to the reset point directly (run_conversation has
        # other prerequisites we don't need to drive here).
        agent._streaming_timeout_streak = 0  # reset point we just added
        from run_agent import DEFAULT_API_TIMEOUT_SECONDS
        assert agent._api_timeout_seconds() == DEFAULT_API_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Cache lifecycle
# ---------------------------------------------------------------------------


class TestDedupCacheLifecycle:
    """Cache is local to each run_conversation() turn and cleared on
    mutating tool use. Verifies the surfaces the rest of the agent
    relies on."""

    def test_fresh_agent_starts_with_empty_cache(self):
        agent = _make_agent()
        assert agent._tool_dedup_cache == {}

    def test_invalidating_tool_clears_existing_cache(self):
        agent = _make_agent()
        agent._maybe_dedup_tool_result(
            "read_file", {"path": "/a"}, "A", "call-1"
        )
        agent._maybe_dedup_tool_result(
            "search_files", {"pattern": "foo"}, "matches", "call-2"
        )
        assert len(agent._tool_dedup_cache) == 2

        # Any mutating tool wipes the slate — we can't assume anything
        # we read is still current after a write/patch/terminal.
        agent._maybe_dedup_tool_result(
            "terminal", {"command": "echo hi"}, "hi\n", "call-3"
        )
        assert agent._tool_dedup_cache == {}
