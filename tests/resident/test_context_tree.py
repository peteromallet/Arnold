from __future__ import annotations

import json
from types import SimpleNamespace

from arnold_pipelines.megaplan.resident.context_tree import (
    build_context_root,
    classify_intent_packs,
    delegation_policy_hot_context,
    read_context_node,
    search_context,
)
from arnold_pipelines.megaplan.resident.status_tree import compact_cloud_status_snapshot
from arnold_pipelines.megaplan.resident.tool_registry import ToolRegistry
from arnold_pipelines.megaplan.resident.runtime import ResidentRuntime


def _sources() -> dict:
    snapshot = {
        "generated_at": "2026-07-13T18:00:00Z",
        "summary": {"running": 1, "complete": 20},
        "sessions": [
            {
                "session": "active-chain",
                "status": "running",
                "process": True,
                "progress": {"percent": 31},
            },
            *[
                {"session": f"done-{index}", "status": "complete", "latest_activity": str(index)}
                for index in range(20)
            ],
        ],
    }
    compact = compact_cloud_status_snapshot(snapshot)
    agents = {
        "running_count": 1,
        "running": [{"run_id": "agent-live", "status": "running"}],
        "recent_count": 1,
        "recent": [{"run_id": "agent-old", "status": "complete"}],
    }
    root = build_context_root(
        status=compact,
        agents=agents,
        initiatives=[{"slug": "north-star"}],
        todos={"pending_count": 1},
        runtime={"model": "sol"},
        conversation={"conversation_id": "c1"},
        intent_packs=("status",),
    )
    return {
        "root": root,
        "status_snapshot": snapshot,
        "agents": agents,
        "messages": [{"content": "the exact Discord failure", "direction": "inbound"}],
        "initiatives": [{"slug": "north-star", "description": "boundary work"}],
        "todos": [{"id": "todo-1", "task": "verify delivery"}],
        "capabilities": [{"name": "read_context_node"}],
        "runtime": {"restart": {"canonical_command": "safe-restart"}},
    }


def test_root_is_small_and_finished_sessions_are_only_a_preview() -> None:
    sources = _sources()
    status = compact_cloud_status_snapshot(sources["status_snapshot"])

    assert [row["session"] for row in status["sessions"]] == ["active-chain"]
    assert status["completed_session_count"] == 20
    assert len(status["completed_sessions_preview"]) == 3
    assert len(json.dumps(sources["root"])) < 10_000


def test_every_context_namespace_is_typed_and_bounded() -> None:
    sources = _sources()
    for node_id in (
        "root",
        "status",
        "status/session/active-chain/progress",
        "agents/running",
        "conversation/messages",
        "initiatives",
        "runtime/restart",
        "todos",
        "capabilities",
        "policies",
        "policies/root_cause",
    ):
        result = read_context_node(sources, node_id=node_id, limit=2)
        assert result["success"], (node_id, result)
        assert result["node"]["node_id"].startswith(node_id.split("/")[0])


def test_context_search_stays_within_requested_scope() -> None:
    sources = _sources()
    result = search_context(sources, scope="conversation", query="Discord", limit=5)

    assert result["success"] is True
    assert result["node"]["total_count"] == 1
    assert "boundary work" not in json.dumps(result)


def test_intent_policy_routing_selects_relevant_packs_only() -> None:
    packs = classify_intent_packs("Why did it fail to reply, and what do the logs show?")

    assert "root_cause" in packs
    assert "conversation" in packs
    assert "todos" not in packs


def test_delegation_policy_pack_preserves_decomposition_and_safety_exceptions() -> None:
    policy = delegation_policy_hot_context()
    sources = _sources()
    rendered = read_context_node(sources, node_id="policies/delegation")["node"]["value"][
        "instruction"
    ]

    assert "independent actionable sub-problems" in policy["preference"]
    assert "one clear owner per sub-problem" in policy["ownership"]
    assert "action-oriented task prompt" in policy["task_prompt_contract"]
    assert "explanation, review, status" in policy["exceptions"]["non_execution"]
    assert "trivial or non-independent fragments" in policy["exceptions"][
        "trivial_or_non_independent"
    ]
    assert "never expands" in policy["exceptions"]["authorization"]
    assert "returned durable run ID" in policy["launch_evidence"]
    assert all(
        fragment in rendered
        for fragment in (
            "independent actionable sub-problems",
            "one clear owner per sub-problem",
            "explanation, review, status",
            "trivial or non-independent fragments",
            "authorization boundaries",
            "returned durable run ID",
        )
    )


def test_empty_tool_registry_catalog_remains_a_directory() -> None:
    assert ToolRegistry().as_compact_catalog() == []


def test_discord_history_excludes_internal_scheduler_inputs_and_caps_size() -> None:
    messages = [
        SimpleNamespace(
            direction="inbound",
            content="internal scheduled VP sweep " + "x" * 8_000,
            discord_message_id=None,
        ),
        SimpleNamespace(
            direction="inbound",
            content="real Discord question",
            discord_message_id="discord-1",
        ),
        SimpleNamespace(
            direction="outbound",
            content="real answer",
            discord_message_id="discord-2",
        ),
    ]
    runtime = object.__new__(ResidentRuntime)
    runtime.config = SimpleNamespace(history_window=10)
    runtime.store = SimpleNamespace(
        list_conversation_messages=lambda *_args, **_kwargs: messages
    )

    history = runtime._build_history("conversation", exclude_ids=(), discord_only=True)

    assert history == (
        {"role": "user", "content": "real Discord question"},
        {"role": "assistant", "content": "real answer"},
    )
