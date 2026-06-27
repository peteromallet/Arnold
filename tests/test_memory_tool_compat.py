"""Compatibility coverage for the removed local memory tool."""

from __future__ import annotations

import json

from arnold.agent.tools.memory_tool import MemoryStore, memory_tool


def test_legacy_memory_store_is_optional_noop() -> None:
    store = MemoryStore(memory_char_limit=100, user_char_limit=100)

    assert store.load_from_disk() is None
    assert store.format_for_system_prompt("memory") == ""
    assert store.format_for_system_prompt("user") == ""


def test_removed_memory_tool_returns_structured_failure() -> None:
    result = json.loads(memory_tool(action="add", target="memory", content="x"))

    assert result["success"] is False
    assert "removed" in result["error"]
