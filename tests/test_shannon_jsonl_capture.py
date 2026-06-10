"""Tests for _read_turn_ndjson_from_transcript helper (shannon output capture)."""

from __future__ import annotations

import json
import uuid as uuid_mod
from pathlib import Path

import pytest

from megaplan.workers.shannon import (
    _parse_shannon_ndjson_events,
    _read_turn_ndjson_from_transcript,
)

# ── helpers for building deterministic transcript fixtures ────────────────────


def _user_opener(uuid: str | None = None, text: str = "hello") -> dict:
    """Build a genuine user turn-opener record."""
    return {
        "type": "user",
        "uuid": uuid or str(uuid_mod.uuid4()),
        "message": {
            "content": [
                {"type": "text", "text": text},
            ],
        },
    }


def _assistant_msg(uuid: str, stop_reason: str = "end_turn") -> dict:
    """Build an assistant message record."""
    return {
        "type": "assistant",
        "uuid": uuid,
        "message": {
            "stop_reason": stop_reason,
            "content": [
                {"type": "text", "text": "I did the thing."},
            ],
        },
    }


def _turn_duration(parent_uuid: str) -> dict:
    """Build a system turn_duration record."""
    return {
        "type": "system",
        "subtype": "turn_duration",
        "parentUuid": parent_uuid,
    }


def _tool_use_assistant() -> dict:
    """An assistant record that produces a tool_use block (NOT end_turn)."""
    return {
        "type": "assistant",
        "uuid": str(uuid_mod.uuid4()),
        "message": {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "name": "read_file",
                    "id": "toolu_abc",
                    "input": {"path": "/x"},
                },
            ],
        },
    }


def _tool_result_user(tool_id: str = "toolu_abc") -> dict:
    """A user record that is purely a tool_result (NOT a turn-opener)."""
    return {
        "type": "user",
        "uuid": str(uuid_mod.uuid4()),
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": "output here",
                },
            ],
        },
    }


def _write_ndjson(path: Path, records: list[dict]) -> None:
    """Write records as NDJSON (one JSON object per line) to *path*."""
    lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── (a) happy path ────────────────────────────────────────────────────────────


class TestHappyPath:
    """A straight-line turn: user opener → assistant end_turn → turn_duration."""

    def test_returns_raw_ndjson_for_completed_turn(self, tmp_path: Path) -> None:
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is not None
        # It includes all three records as raw NDJSON lines.
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert len(parsed) == 3
        assert parsed[0]["type"] == "user"
        assert parsed[1]["type"] == "assistant"
        assert parsed[2]["type"] == "system"
        assert parsed[2]["subtype"] == "turn_duration"


# ── (b) tool-use interleaving ─────────────────────────────────────────────────


class TestToolUseInterleaving:
    """Tool-use records between the opener and close do NOT reset the turn."""

    def test_tool_result_does_not_start_new_turn(self, tmp_path: Path) -> None:
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _tool_use_assistant(),
            _tool_result_user(),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is not None
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert len(parsed) == 5  # all records from opener to close inclusive
        types = [r["type"] for r in parsed]
        assert types == ["user", "assistant", "user", "assistant", "system"]

    def test_multiple_tool_use_rounds(self, tmp_path: Path) -> None:
        """Several tool_use/tool_result interleavings — all part of one turn."""
        user_uuid = str(uuid_mod.uuid4())
        final_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _tool_use_assistant(),
            _tool_result_user(tool_id="toolu_1"),
            _tool_use_assistant(),
            _tool_result_user(tool_id="toolu_2"),
            _assistant_msg(uuid=final_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=final_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is not None
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert len(parsed) == 7


# ── (c) in-progress turn (no end_turn) → None ──────────────────────────────────


class TestInProgressTurn:
    def test_no_end_turn_returns_none(self, tmp_path: Path) -> None:
        user_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=str(uuid_mod.uuid4()), stop_reason="tool_use"),
            _tool_result_user(),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is None

    def test_end_turn_without_turn_duration_returns_none(self, tmp_path: Path) -> None:
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            # No turn_duration record follows.
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is None


# ── (d) parentUuid mismatch → None ─────────────────────────────────────────────


class TestParentUuidMismatch:
    def test_mismatched_parent_uuid_returns_none(self, tmp_path: Path) -> None:
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        other_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=other_uuid),  # wrong parentUuid
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is None


# ── (e) malformed trailing partial line tolerated ──────────────────────────────


class TestMalformedTrailingLines:
    def test_trailing_partial_json_tolerated(self, tmp_path: Path) -> None:
        """A trailing incomplete JSON line is skipped — the valid turn is found."""
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        body = "\n".join([json.dumps(r) for r in records]) + "\n"
        # Append a trailing partial / nonsense line.
        body += "{\"broken"
        path.write_text(body, encoding="utf-8")

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is not None
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert len(parsed) == 3
        assert parsed[0]["type"] == "user"
        assert parsed[2]["type"] == "system"

    def test_trailing_garbage_line_skipped(self, tmp_path: Path) -> None:
        """A trailing line that is not JSON at all is tolerated."""
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        body = "\n".join([json.dumps(r) for r in records]) + "\n"
        body += "this is not json at all\n"
        path.write_text(body, encoding="utf-8")

        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is not None
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert len(parsed) == 3


# ── (f) since_user_uuid filter ─────────────────────────────────────────────────


class TestSinceUserUuidFilter:
    def test_filters_older_turn_with_matching_user_uuid(self, tmp_path: Path) -> None:
        """When the most recent completed turn opener matches since_user_uuid,
        return None (no NEWER turn exists)."""
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(str(path), since_user_uuid=user_uuid)
        assert result is None

    def test_returns_newer_turn_when_user_uuid_differs(self, tmp_path: Path) -> None:
        """When since_user_uuid differs from the turn opener, the turn is
        returned (it's a newer turn)."""
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        result = _read_turn_ndjson_from_transcript(
            str(path), since_user_uuid="an-older-uuid"
        )
        assert result is not None
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert parsed[0]["uuid"] == user_uuid

    def test_returns_most_recent_turn_when_two_exist(self, tmp_path: Path) -> None:
        """Two completed turns; only the most recent should be returned."""
        user_uuid_1 = str(uuid_mod.uuid4())
        asst_uuid_1 = str(uuid_mod.uuid4())
        user_uuid_2 = str(uuid_mod.uuid4())
        asst_uuid_2 = str(uuid_mod.uuid4())

        records = [
            # Turn 1
            _user_opener(uuid=user_uuid_1),
            _assistant_msg(uuid=asst_uuid_1, stop_reason="end_turn"),
            _turn_duration(parent_uuid=asst_uuid_1),
            # Turn 2
            _user_opener(uuid=user_uuid_2, text="another question"),
            _assistant_msg(uuid=asst_uuid_2, stop_reason="end_turn"),
            _turn_duration(parent_uuid=asst_uuid_2),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        # Query with turn-1 opener: should skip that, find turn 2.
        result = _read_turn_ndjson_from_transcript(
            str(path), since_user_uuid=user_uuid_1
        )
        assert result is not None
        parsed = [json.loads(ln) for ln in result.strip().split("\n")]
        assert parsed[0]["uuid"] == user_uuid_2

        # Query with turn-2 opener: should find nothing newer.
        result2 = _read_turn_ndjson_from_transcript(
            str(path), since_user_uuid=user_uuid_2
        )
        assert result2 is None


# ── (g) round-trip through _parse_shannon_ndjson_events ────────────────────────


class TestRoundTrip:
    def test_helper_output_parses_cleanly(self, tmp_path: Path) -> None:
        """Feed the NDJSON from _read_turn_ndjson_from_transcript into
        _parse_shannon_ndjson_events and confirm it parses successfully."""
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        records = [
            _user_opener(uuid=user_uuid),
            _tool_use_assistant(),
            _tool_result_user(),
            _assistant_msg(uuid=assistant_uuid, stop_reason="end_turn"),
            _turn_duration(parent_uuid=assistant_uuid),
        ]
        path = tmp_path / "transcript.jsonl"
        _write_ndjson(path, records)

        ndjson = _read_turn_ndjson_from_transcript(str(path))
        assert ndjson is not None

        events = _parse_shannon_ndjson_events(ndjson)
        assert events is not None
        # Should contain the same number of events.
        assert isinstance(events, list)
        assert len(events) == 5
        # Spot-check that the opener and close are present.
        types = [e.get("type") for e in events if isinstance(e, dict) and "type" in e]
        assert "user" in types
        assert "assistant" in types
        assert "system" in types


# ── edge cases ─────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        result = _read_turn_ndjson_from_transcript(str(tmp_path / "nonexistent.jsonl"))
        assert result is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        result = _read_turn_ndjson_from_transcript(str(path))
        assert result is None


# ── integration: transcript capture wired into run_shannon_step ──────────────


class TestTranscriptIntegration:
    """Integration: wire _read_turn_ndjson_from_transcript into run_shannon_step."""

    def test_transcript_parsed_when_stdout_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run_command returns empty stdout (paste-first-turn success) →
        transcript NDJSON is tried and successfully parsed."""
        from unittest.mock import patch

        from megaplan._core import ensure_runtime_layout
        from megaplan.workers import CommandResult, WorkerResult
        from megaplan.workers.shannon import run_shannon_step
        from tests._workers_helpers import _mock_state

        ensure_runtime_layout(tmp_path)
        monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
        monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
        plan_dir, state = _mock_state(tmp_path)

        # Build a valid transcript with a completed turn whose assistant
        # text block carries a valid megaplan execute payload.
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        payload = {
            "output": "transcript-captured",
            "files_changed": ["f.py"],
            "commands_run": ["c.sh"],
            "deviations": [],
            "task_updates": [],
            "sense_check_acknowledgments": [],
        }
        transcript_path = tmp_path / "fake_transcript.jsonl"
        transcript_path.write_text(
            json.dumps(_user_opener(uuid=user_uuid, text="do the thing")) + "\n"
            + json.dumps({
                "type": "assistant",
                "uuid": assistant_uuid,
                "message": {
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": json.dumps(payload)}],
                },
            }) + "\n"
            + json.dumps(_turn_duration(parent_uuid=assistant_uuid)) + "\n",
            encoding="utf-8",
        )

        # Empty stdout: shannon succeeded but paste-first-turn yields no output.
        fake_result = CommandResult(
            command=[],
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=100,
        )

        with patch(
            "megaplan.workers.shannon._claude_transcript_paths",
            return_value=[transcript_path],
        ):
            with patch(
                "megaplan.workers.shannon.run_command",
                return_value=fake_result,
            ):
                result = run_shannon_step(
                    "execute",
                    state,
                    plan_dir,
                    root=tmp_path,
                    fresh=True,
                    prompt_override="return json",
                )

        assert isinstance(result, WorkerResult)
        assert result.payload["output"] == "transcript-captured"
        assert result.payload["files_changed"] == ["f.py"]
        # raw_output carries the transcript NDJSON, not the empty stdout.
        assert "do the thing" in (result.raw_output or "")

    def test_stdout_used_when_transcript_not_completed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When transcript has no completed turn (in-progress, no end_turn),
        fall back to stdout raw."""
        from unittest.mock import patch

        from megaplan._core import ensure_runtime_layout
        from megaplan.workers import CommandResult, WorkerResult
        from megaplan.workers.shannon import run_shannon_step
        from tests._workers_helpers import _mock_state

        ensure_runtime_layout(tmp_path)
        monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
        monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
        plan_dir, state = _mock_state(tmp_path)

        # An in-progress transcript: user + assistant with no end_turn.
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        transcript_path = tmp_path / "in_progress.jsonl"
        transcript_path.write_text(
            json.dumps(_user_opener(uuid=user_uuid, text="hello")) + "\n"
            + json.dumps(
                _assistant_msg(uuid=assistant_uuid, stop_reason="tool_use")
            ) + "\n",
            encoding="utf-8",
        )

        # stdout has a valid result
        stdout_payload = {
            "output": "stdout-fallback",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [],
            "sense_check_acknowledgments": [],
        }
        stdout_raw = json.dumps([{
            "type": "result",
            "subtype": "success",
            "result": json.dumps(stdout_payload),
            "session_id": "test-sid",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }])
        fake_result = CommandResult(
            command=[],
            cwd=tmp_path,
            returncode=0,
            stdout=stdout_raw,
            stderr="",
            duration_ms=100,
        )

        with patch(
            "megaplan.workers.shannon._claude_transcript_paths",
            return_value=[transcript_path],
        ):
            with patch(
                "megaplan.workers.shannon.run_command",
                return_value=fake_result,
            ):
                result = run_shannon_step(
                    "execute",
                    state,
                    plan_dir,
                    root=tmp_path,
                    fresh=True,
                    prompt_override="return json",
                )

        assert isinstance(result, WorkerResult)
        assert result.payload["output"] == "stdout-fallback"

    def test_stdout_used_when_transcript_parse_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When a completed transcript turn exists but its content isn't a valid
        megaplan payload (schema error), fall back to stdout raw."""
        from unittest.mock import patch

        from megaplan._core import ensure_runtime_layout
        from megaplan.workers import CommandResult, WorkerResult
        from megaplan.workers.shannon import run_shannon_step
        from tests._workers_helpers import _mock_state

        ensure_runtime_layout(tmp_path)
        monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
        monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
        plan_dir, state = _mock_state(tmp_path)

        # A completed turn whose assistant text is NOT valid JSON for the
        # megaplan schema — missing required keys.
        user_uuid = str(uuid_mod.uuid4())
        assistant_uuid = str(uuid_mod.uuid4())
        transcript_path = tmp_path / "bad_content.jsonl"
        transcript_path.write_text(
            json.dumps(_user_opener(uuid=user_uuid, text="do the thing")) + "\n"
            + json.dumps({
                "type": "assistant",
                "uuid": assistant_uuid,
                "message": {
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "just some prose, no json"}],
                },
            }) + "\n"
            + json.dumps(_turn_duration(parent_uuid=assistant_uuid)) + "\n",
            encoding="utf-8",
        )

        # stdout has a valid result
        stdout_payload = {
            "output": "stdout-wins",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [],
            "sense_check_acknowledgments": [],
        }
        stdout_raw = json.dumps([{
            "type": "result",
            "subtype": "success",
            "result": json.dumps(stdout_payload),
            "session_id": "test-sid",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }])
        fake_result = CommandResult(
            command=[],
            cwd=tmp_path,
            returncode=0,
            stdout=stdout_raw,
            stderr="",
            duration_ms=100,
        )

        with patch(
            "megaplan.workers.shannon._claude_transcript_paths",
            return_value=[transcript_path],
        ):
            with patch(
                "megaplan.workers.shannon.run_command",
                return_value=fake_result,
            ):
                result = run_shannon_step(
                    "execute",
                    state,
                    plan_dir,
                    root=tmp_path,
                    fresh=True,
                    prompt_override="return json",
                )

        assert isinstance(result, WorkerResult)
        assert result.payload["output"] == "stdout-wins"


