from __future__ import annotations

import copy
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold.agent.agent.context_compressor import ContextCompressor, SUMMARY_PREFIX
from arnold.agent.hermes_state import SessionDB
from arnold.agent.run_agent import AIAgent


def _messages() -> list[dict[str, object]]:
    return [
        {"role": "system", "content": "system"},
        {
            "role": "assistant",
            "content": "calling old tool",
            "tool_calls": [
                {
                    "id": "call-old",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-old", "content": "x" * 1_000},
        {"role": "user", "content": "old user request"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "new user request"},
        {"role": "assistant", "content": "new answer"},
        {"role": "user", "content": "tail user"},
        {"role": "assistant", "content": "tail answer"},
    ]


def _compressor(*, previous_summary: str | None = None) -> ContextCompressor:
    compressor = ContextCompressor(
        model="missing-model",
        provider="missing-provider",
        summary_model_override="invalid-summary-model",
        config_context_length=100_000,
        protect_first_n=1,
        protect_last_n=1,
        quiet_mode=True,
    )
    compressor._previous_summary = previous_summary
    return compressor


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("provider is not configured"),
        ValueError("model does not exist"),
    ],
)
def test_summary_provider_or_model_failure_preserves_all_state(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    compressor = _compressor(previous_summary="durable prior summary")

    def fail_call(**kwargs: object) -> object:
        assert kwargs["model"] == "invalid-summary-model"
        raise failure

    monkeypatch.setattr(
        "arnold.agent.agent.context_compressor.call_llm",
        fail_call,
    )

    result = compressor.compress(messages)

    assert result is messages
    assert result == original
    assert compressor.compression_count == 0
    assert compressor._previous_summary == "durable prior summary"
    assert compressor.last_compaction_succeeded is False


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="  \n"))]
        ),
        SimpleNamespace(choices=[]),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        ),
    ],
)
def test_empty_or_malformed_summary_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    response: object,
) -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    compressor = _compressor(previous_summary="prior")
    monkeypatch.setattr(
        "arnold.agent.agent.context_compressor.call_llm",
        lambda **_: response,
    )

    result = compressor.compress(messages)

    assert result is messages
    assert result == original
    assert all(
        not str(message.get("content", "")).startswith(SUMMARY_PREFIX)
        for message in result
    )
    assert compressor.compression_count == 0
    assert compressor._previous_summary == "prior"
    assert compressor.last_compaction_succeeded is False


def test_post_summary_failure_rolls_back_compactor_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    compressor = _compressor(previous_summary="prior")
    monkeypatch.setattr(
        "arnold.agent.agent.context_compressor.call_llm",
        lambda **_: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="valid summary"))]
        ),
    )
    monkeypatch.setattr(
        compressor,
        "_sanitize_tool_pairs",
        lambda _: (_ for _ in ()).throw(ValueError("injected sanitation failure")),
    )

    result = compressor.compress(messages)

    assert result is messages
    assert result == original
    assert compressor.compression_count == 0
    assert compressor._previous_summary == "prior"
    assert compressor.last_compaction_succeeded is False


def test_pre_summary_projection_failure_preserves_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    compressor = _compressor(previous_summary="prior")
    monkeypatch.setattr(
        compressor,
        "_prune_old_tool_results",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("injected pruning failure")
        ),
    )

    result = compressor.compress(messages)

    assert result is messages
    assert result == original
    assert compressor.compression_count == 0
    assert compressor._previous_summary == "prior"
    assert compressor.last_compaction_succeeded is False


def test_non_empty_summary_commits_compactor_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _messages()
    compressor = _compressor(previous_summary="prior")
    monkeypatch.setattr(
        "arnold.agent.agent.context_compressor.call_llm",
        lambda **_: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=" valid summary "))]
        ),
    )

    result = compressor.compress(messages)

    assert result is not messages
    assert len(result) < len(messages)
    assert compressor.compression_count == 1
    assert compressor._previous_summary == "valid summary"
    assert compressor.last_compaction_succeeded is True


class _RecordingSessionDB:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def get_session_title(self, session_id: str) -> str:
        self.events.append(("get_title", session_id))
        return "original"

    def end_session(self, session_id: str, reason: str) -> None:
        self.events.append(("end", session_id, reason))

    def create_session(self, **kwargs: object) -> None:
        self.events.append(("create", kwargs))


def test_failed_summary_does_not_split_or_reset_agent_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    compressor = _compressor(previous_summary="prior")
    db = _RecordingSessionDB()
    todo_calls: list[str] = []
    invalidations: list[str] = []
    agent = SimpleNamespace(
        context_compressor=compressor,
        flush_memories=lambda *args, **kwargs: None,
        _todo_store=SimpleNamespace(
            format_for_injection=lambda: todo_calls.append("called") or "todo"
        ),
        _invalidate_system_prompt=lambda: invalidations.append("called"),
        _build_system_prompt=lambda _: "rebuilt prompt",
        _cached_system_prompt="active prompt",
        _session_db=db,
        session_id="original-session",
        platform="cli",
        model="missing-model",
        _last_flushed_db_idx=7,
        _context_50_warned=True,
        _context_70_warned=True,
    )
    monkeypatch.setattr(
        "arnold.agent.agent.context_compressor.call_llm",
        lambda **_: (_ for _ in ()).throw(RuntimeError("missing provider/model")),
    )

    result, prompt = AIAgent._compress_context(agent, messages, "base prompt")

    assert result is messages
    assert result == original
    assert prompt == "active prompt"
    assert agent.session_id == "original-session"
    assert agent._last_flushed_db_idx == 7
    assert agent._context_50_warned is True
    assert agent._context_70_warned is True
    assert db.events == []
    assert todo_calls == []
    assert invalidations == []


class _FailingSplitSessionDB(_RecordingSessionDB):
    def get_next_title_in_lineage(self, title: str) -> str:
        return f"{title} #2"

    def split_session_for_compression(self, **kwargs: object) -> None:
        self.events.append(("split", kwargs))
        raise OSError("injected persisted split failure")


def test_persisted_split_failure_rolls_back_valid_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = _messages()
    original = copy.deepcopy(messages)
    compressor = _compressor(previous_summary="prior")
    db = _FailingSplitSessionDB()
    agent = SimpleNamespace(
        context_compressor=compressor,
        flush_memories=lambda *args, **kwargs: None,
        _todo_store=SimpleNamespace(format_for_injection=lambda: "todo snapshot"),
        _invalidate_system_prompt=lambda: setattr(agent, "_cached_system_prompt", None),
        _build_system_prompt=lambda _: "rebuilt prompt",
        _cached_system_prompt="active prompt",
        _session_db=db,
        session_id="original-session",
        platform="cli",
        model="missing-model",
        _last_flushed_db_idx=7,
        _context_50_warned=True,
        _context_70_warned=True,
    )
    monkeypatch.setattr(
        "arnold.agent.agent.context_compressor.call_llm",
        lambda **_: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="valid summary"))]
        ),
    )

    result, prompt = AIAgent._compress_context(agent, messages, "base prompt")

    assert result is messages
    assert result == original
    assert prompt == "active prompt"
    assert compressor._previous_summary == "prior"
    assert compressor.compression_count == 0
    assert compressor.last_compaction_succeeded is False
    assert agent.session_id == "original-session"
    assert agent._last_flushed_db_idx == 7
    assert agent._context_50_warned is True
    assert agent._context_70_warned is True
    assert [event[0] for event in db.events] == ["get_title", "split"]


def test_sqlite_compression_split_is_atomic(tmp_path: Path) -> None:
    db = SessionDB(tmp_path / "state.db")
    try:
        db.create_session("old", source="cli", model="model")
        db.create_session("title-owner", source="cli", model="model")
        db.set_session_title("title-owner", "duplicate")

        with pytest.raises(sqlite3.IntegrityError):
            db.split_session_for_compression(
                old_session_id="old",
                new_session_id="failed-child",
                source="cli",
                model="model",
                system_prompt="prompt",
                title="duplicate",
            )

        assert db.get_session("failed-child") is None
        assert db.get_session("old")["ended_at"] is None

        db.split_session_for_compression(
            old_session_id="old",
            new_session_id="child",
            source="cli",
            model="model",
            system_prompt="compacted prompt",
            title="old #2",
        )
        old = db.get_session("old")
        child = db.get_session("child")
        assert old["end_reason"] == "compression"
        assert child["parent_session_id"] == "old"
        assert child["system_prompt"] == "compacted prompt"
        assert child["title"] == "old #2"
    finally:
        db.close()
