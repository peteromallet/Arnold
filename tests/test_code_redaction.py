from __future__ import annotations

import json
import sqlite3

from agent_kit.code_redaction import REDACTION_MARKER, redact_code_secrets
from agent_kit.store.sqlite import SQLiteStore
from agent_kit.tool_kit import ToolContext, ToolRegistry


RAW_OPENAI = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
RAW_GITHUB = "github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdef"
RAW_GITHUB_CLASSIC = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"
RAW_AWS_KEY = "AKIAABCDEFGHIJKLMNOP"
RAW_AWS_SECRET = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"
RAW_HEX = "0123456789abcdef0123456789abcdef0123456789abcdef"


def _source_fixture() -> str:
    return "\n".join(
        [
            f'OPENAI_API_KEY = "{RAW_OPENAI}"',
            f'GITHUB_TOKEN = "{RAW_GITHUB}"',
            f'GH_CLASSIC = "{RAW_GITHUB_CLASSIC}"',
            f'AWS_ACCESS_KEY_ID = "{RAW_AWS_KEY}"',
            f'AWS_SECRET_ACCESS_KEY = "{RAW_AWS_SECRET}"',
            f'BUILD_SHA = "{RAW_HEX}"',
        ]
    )


def _assert_raw_values_absent(value) -> None:
    serialized = json.dumps(value, sort_keys=True)
    for raw in (
        RAW_OPENAI,
        RAW_GITHUB,
        RAW_GITHUB_CLASSIC,
        RAW_AWS_KEY,
        RAW_AWS_SECRET,
        RAW_HEX,
    ):
        assert raw not in serialized
    assert REDACTION_MARKER in serialized


def test_redact_code_secrets_recurses_through_strings() -> None:
    redacted = redact_code_secrets(
        {
            "source": _source_fixture(),
            "nested": [{"payload": ("prefix", _source_fixture())}],
        }
    )

    _assert_raw_values_absent(redacted)


def test_store_persistence_paths_redact_source_like_payloads() -> None:
    store = SQLiteStore(sqlite3.connect(":memory:"))
    turn = store.create_turn(epic_id=None, triggered_by_message_ids=[])
    source = _source_fixture()

    tool_call = store.record_tool_call(
        turn_id=turn["id"],
        tool_name="read_codebase_file",
        operation_kind="read",
        arguments={"path": "app.py", "source": source},
        result={"content": source},
        duration_ms=1,
    )
    log = store.log_system_event(
        level="warn",
        category="external_api",
        event_type="github_rate_limit",
        message="GitHub rate limit approaching",
        details={"source": source},
    )
    artifact = store.create_code_artifact(
        kind="excerpt",
        source="codebase",
        content=source,
        content_summary=source,
        metadata={"source": source},
    )
    cache = store.upsert_api_cache(
        cache_key="read:file",
        content=source,
        content_summary=source,
        metadata={"source": source},
    )
    cache_replay = store.get_api_cache("read:file")

    _assert_raw_values_absent(tool_call)
    _assert_raw_values_absent(log)
    _assert_raw_values_absent(artifact)
    _assert_raw_values_absent(cache)
    _assert_raw_values_absent(cache_replay)

    persisted_payloads = store._conn.execute(
        """
        SELECT arguments || result AS payload FROM tool_calls
        UNION ALL
        SELECT details AS payload FROM system_logs
        UNION ALL
        SELECT content || content_summary || metadata AS payload FROM code_artifacts
        """
    ).fetchall()
    for row in persisted_payloads:
        _assert_raw_values_absent({"payload": row[0]})


def test_tool_wrapper_redacts_model_visible_result_and_audit_rows() -> None:
    store = SQLiteStore(sqlite3.connect(":memory:"))
    turn = store.create_turn(epic_id=None, triggered_by_message_ids=[])
    registry = ToolRegistry()
    source = _source_fixture()

    def read_tool(context, query):
        return {"content": source, "query": query}

    registry.register(
        "read_tool",
        read_tool,
        {"type": "object"},
        operation_kind="read",
    )
    invocation = registry.invoke(
        "read_tool",
        ToolContext(store=store, turn_id=turn["id"], events=[]),
        {"query": source},
    )

    _assert_raw_values_absent(invocation.result)
    _assert_raw_values_absent(invocation.tool_call)
