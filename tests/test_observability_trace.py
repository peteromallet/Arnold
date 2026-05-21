"""Fixture tests for ``megaplan trace`` formatters and filters."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from megaplan.observability.trace import (
    format_json,
    format_pretty,
    format_narrative,
    _since_seconds,
    _relative_timestamp,
)


# ---------------------------------------------------------------------------
# Sample event fixtures
# ---------------------------------------------------------------------------


def _make_event(seq, ts_str, kind, phase=None, payload=None):
    return {
        "seq": seq,
        "ts_utc": ts_str,
        "ts_rel_init_s": float(seq * 10),
        "kind": kind,
        "phase": phase,
        "payload": payload or {},
    }


def _sample_events() -> list[dict]:
    """Return a small hand-crafted set of mixed event kinds."""
    return [
        _make_event(0, "2025-06-01T10:00:00Z", "init", payload={"plan_name": "test-plan"}),
        _make_event(1, "2025-06-01T10:00:01Z", "phase_start", phase="critique", payload={"phase": "critique", "model": "deepseek-v4"}),
        _make_event(2, "2025-06-01T10:00:02Z", "llm_call_start", phase="critique", payload={"provider": "openrouter", "model": "deepseek-v4", "prompt_hash": "abc1234567890def"}),
        _make_event(3, "2025-06-01T10:00:03Z", "llm_token_heartbeat", phase="critique", payload={"tokens_emitted_so_far": 50, "last_token_at": "2025-06-01T10:00:03Z"}),
        _make_event(4, "2025-06-01T10:00:04Z", "llm_token_heartbeat", phase="critique", payload={"tokens_emitted_so_far": 120, "last_token_at": "2025-06-01T10:00:04Z"}),
        _make_event(5, "2025-06-01T10:00:05Z", "llm_token_heartbeat", phase="critique", payload={"tokens_emitted_so_far": 200, "last_token_at": "2025-06-01T10:00:05Z"}),
        _make_event(6, "2025-06-01T10:00:06Z", "llm_call_end", phase="critique", payload={"tokens_in": 500, "tokens_out": 250, "cost_usd": 0.015, "duration_s": 4.0}),
        _make_event(7, "2025-06-01T10:00:07Z", "phase_end", phase="critique", payload={"phase": "critique", "duration_s": 6.0}),
        _make_event(8, "2025-06-01T10:00:08Z", "flag_raised", phase="gate", payload={"flag_id": "FLAG-001", "severity": "warn"}),
        _make_event(9, "2025-06-01T10:00:09Z", "plan_finished"),
    ]


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------


class TestFormatJson:
    def test_one_json_per_event(self):
        events = _sample_events()
        output = format_json(events)
        lines = output.strip().split("\n")
        assert len(lines) == len(events)

        # Each line must be valid JSON
        for line in lines:
            parsed = json.loads(line)
            assert "seq" in parsed
            assert "kind" in parsed

    def test_empty_events(self):
        assert format_json([]) == ""


# ---------------------------------------------------------------------------
# format_pretty
# ---------------------------------------------------------------------------


class TestFormatPretty:
    def test_produces_colored_output_with_timestamps(self):
        events = _sample_events()[:4]  # first few events
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_pretty(events, now=now)
        lines = output.strip().split("\n")
        assert len(lines) == len(events)

        # Should include seq numbers
        for i, line in enumerate(lines):
            assert str(events[i]["seq"]) in line or f"{events[i]['seq']:>5d}" in line

    def test_empty_events(self):
        assert format_pretty([]) == ""

    def test_relative_timestamps_present(self):
        events = _sample_events()[:1]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_pretty(events, now=now)
        # Should contain some relative time
        assert "10s ago" in output or "s ago" in output


# ---------------------------------------------------------------------------
# format_narrative
# ---------------------------------------------------------------------------


class TestFormatNarrative:
    def test_groups_heartbeats(self):
        """Narrative format groups consecutive llm_token_heartbeat events into one summary line."""
        events = _sample_events()
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        lines = output.strip().split("\n")

        # There are 3 heartbeats + 7 other events = 8 lines (heartbeats grouped to 1)
        # Count heartbeat summary lines
        heartbeat_summary_count = sum(1 for line in lines if "Token stream" in line)
        assert heartbeat_summary_count == 1

        # Verify no individual heartbeat lines
        heartbeat_line_count = sum(1 for line in lines if "llm_token_heartbeat" in line.lower())
        assert heartbeat_line_count == 0

    def test_includes_tok_s_rate(self):
        events = _sample_events()
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        assert "tok/s" in output

    def test_empty_events(self):
        output = format_narrative([], now=None)
        assert "no events" in output.lower()

    def test_model_name_in_summary(self):
        events = _sample_events()
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        # The model from llm_call_start before the heartbeats should appear
        assert "deepseek-v4" in output


# ---------------------------------------------------------------------------
# _since_seconds parser
# ---------------------------------------------------------------------------


class TestSinceSeconds:
    def test_seconds(self):
        assert _since_seconds("30s") == 30.0

    def test_minutes(self):
        assert _since_seconds("5m") == 300.0

    def test_hours(self):
        assert _since_seconds("1h") == 3600.0

    def test_days(self):
        assert _since_seconds("2d") == 172800.0

    def test_bare_number(self):
        assert _since_seconds("300") == 300.0

    def test_invalid(self):
        assert _since_seconds("abc") is None

    def test_none(self):
        assert _since_seconds(None) is None


# ---------------------------------------------------------------------------
# _relative_timestamp
# ---------------------------------------------------------------------------


class TestRelativeTimestamp:
    def test_seconds_ago(self):
        now = datetime.fromisoformat("2025-06-01T10:00:30+00:00")
        result = _relative_timestamp("2025-06-01T10:00:00Z", now)
        assert "30s ago" in result or "30" in result

    def test_minutes_ago(self):
        now = datetime.fromisoformat("2025-06-01T10:05:00+00:00")
        result = _relative_timestamp("2025-06-01T10:00:00Z", now)
        assert "m" in result

    def test_invalid_timestamp(self):
        now = datetime.now(timezone.utc)
        result = _relative_timestamp("not-a-timestamp", now)
        assert result == "not-a-timestamp"


# ---------------------------------------------------------------------------
# format_narrative specific event handling
# ---------------------------------------------------------------------------


class TestFormatNarrativeEventSpecifics:
    def test_init_event(self):
        events = [
            _make_event(0, "2025-06-01T10:00:00Z", "init", payload={"plan_name": "my-cool-plan"}),
        ]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        assert "my-cool-plan" in output
        assert "initialized" in output.lower()

    def test_phase_start_event(self):
        events = [
            _make_event(0, "2025-06-01T10:00:00Z", "phase_start", phase="critique", payload={"phase": "critique", "model": "deepseek-v4"}),
        ]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        assert "critique" in output
        assert "started" in output.lower()
        assert "deepseek-v4" in output

    def test_state_transition_event(self):
        events = [
            _make_event(0, "2025-06-01T10:00:00Z", "state_transition", payload={"from": "planned", "to": "planning"}),
        ]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        assert "State transition" in output
        assert "planned" in output
        assert "planning" in output

    def test_llm_call_error_event(self):
        events = [
            _make_event(0, "2025-06-01T10:00:00Z", "llm_call_error", payload={"provider_error_code": "429", "retry_after_s": 30}),
        ]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        assert "error" in output.lower()
        assert "429" in output

    def test_unknown_kind_fallback(self):
        events = [
            _make_event(0, "2025-06-01T10:00:00Z", "weird_custom_kind", payload={"hello": "world"}),
        ]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_narrative(events, now=now)
        # Should fall through to the else branch which prints kind: payload
        # At minimum it should not raise
        assert len(output) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_events_with_no_ts_utc(self):
        """Events without ts_utc still render."""
        events = [
            {"seq": 0, "kind": "init", "phase": None, "payload": {"plan_name": "test"}},
        ]
        output = format_narrative(events, now=None)
        assert "test" in output

    def test_format_pretty_with_unicode_chars(self):
        """Pretty format should use unicode icons."""
        events = [_make_event(0, "2025-06-01T10:00:00Z", "init")]
        now = datetime.fromisoformat("2025-06-01T10:00:10+00:00")
        output = format_pretty(events, now=now)
        # Should at minimum not crash
        assert len(output) > 0
