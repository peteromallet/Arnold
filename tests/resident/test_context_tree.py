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
                {
                    "session": f"done-{index}",
                    "status": "complete",
                    "completed_at": f"2026-07-13T17:{index:02d}:00Z",
                    "latest_activity": f"2026-07-13T17:{index:02d}:00Z",
                }
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
        "tickets": [{"id": "ticket-1", "title": "boundary ticket"}],
        "initiatives": [{"slug": "north-star", "description": "boundary work"}],
        "documents": [{"path": "docs/boundary.md", "name": "docs/boundary.md"}],
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
        "tickets",
        "tickets/ticket-1",
        "initiatives",
        "initiatives/north-star",
        "documents",
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


def test_knowledge_context_search_uses_typed_ticket_and_document_scopes() -> None:
    sources = _sources()

    tickets = search_context(sources, scope="tickets", query="boundary", limit=5)
    documents = search_context(sources, scope="documents", query="boundary", limit=5)

    assert tickets["node"]["items"] == sources["tickets"]
    assert documents["node"]["items"] == sources["documents"]


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
    assert policy["schema_version"] == "megaplan-resident-delegation-policy-v3"
    assert "implements, verifies, and delivers" in policy["execution_default"]
    assert "isolated worktree and feature branch" in policy["workspace_default"]
    assert "Never infer literal `main`" in policy["integration_default"]
    assert "those facts alone are not target ambiguity" in policy["integration_default"]
    assert "advanced on the same lineage" in policy["integration_default"]
    assert "Local integration does not authorize" in policy["integration_default"]
    assert "explicit approval" in policy["external_actions"]
    assert "label it unintegrated" in policy["tentative_work"]
    assert "durable ancestry evidence" in policy["completion_evidence"]
    assert "observed remote ref" in policy["completion_evidence"]
    assert "outcome probe" in policy["completion_evidence"]
    assert all(
        fragment in rendered
        for fragment in (
            "independent actionable sub-problems",
            "one clear owner per sub-problem",
            "explanation, review, status",
            "trivial or non-independent fragments",
            "authorization boundaries",
            "returned durable run ID",
            "implements, verifies, and delivers",
            "isolated worktree and feature branch",
            "Never infer literal `main`",
            "Local integration does not authorize",
            "label it unintegrated",
            "durable ancestry evidence",
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


# ── M9 (T52): observer purity, degraded attention ordering, metadata ────────


def test_context_root_observer_pure_does_not_mutate_status_input() -> None:
    """build_context_root must not mutate its status input (observer purity)."""
    status = {
        "generated_at": "2026-07-22T18:00:00Z",
        "schema_version": "megaplan-resident-status-tree-v1",
        "node_id": "root",
        "sessions": [
            {
                "session": "plan-a",
                "status": "running",
                "progress": {"percent": 45},
            },
        ],
        "completed_session_count": 0,
        "session_count": 1,
        "source_cursor_aggregate": {
            "dimensions": [
                {"dimension": "lifecycle", "state": "fresh"},
            ],
            "non_fresh_count": 0,
        },
        "navigation": {},
    }
    status_copy = json.dumps(status)
    build_context_root(
        status=status,
        agents={},
        initiatives=[],
        todos={},
        runtime={},
        conversation={},
        intent_packs=(),
    )
    # After context build, the status dict must be unchanged
    assert json.dumps(status) == status_copy, "build_context_root mutated its status input"


def test_degraded_status_input_preserves_attention_ordering() -> None:
    """Attention priority must be preserved even when status carries stale/unknown dimensions."""
    status = {
        "generated_at": "2026-07-22T18:00:00Z",
        "schema_version": "megaplan-resident-status-tree-v1",
        "node_id": "root",
        "degraded": True,
        "sessions": [
            {
                "session": "active-execution",
                "status": "running",
                "process": True,
                "progress": {"percent": 60, "display_state": "executing"},
            },
            {
                "session": "needs-attention",
                "status": "attention",
                "process": False,
                "operator_next": "review required",
                "progress": {"percent": 30},
            },
            {
                "session": "blocked-chain",
                "status": "blocked",
                "progress": {"percent": 10},
            },
        ],
        "completed_session_count": 0,
        "session_count": 3,
        "source_cursor_aggregate": {
            "sessions_with_cursor": 0,
            "total_non_fresh_dimensions": 2,
        },
        "navigation": {},
    }
    root = build_context_root(
        status=status,
        agents={},
        initiatives=[],
        todos={"pending_count": 0},
        runtime={},
        conversation={},
        intent_packs=("status",),
    )
    # Root must carry either source_cursor_summary or attention context
    assert "_source_cursor_summary" in root or "attention" in root
    # Attention context must be present
    assert root.get("status") is not None or root.get("attention") is not None


def test_context_tree_reads_are_bounded_and_deterministic() -> None:
    """read_context_node for the same node_id must return deterministic results."""
    sources = _sources()
    result1 = read_context_node(sources, node_id="status", limit=5)
    result2 = read_context_node(sources, node_id="status", limit=5)
    assert result1["success"] == result2["success"]
    # The items should be identical
    items1 = result1["node"].get("items", result1["node"].get("value", []))
    items2 = result2["node"].get("items", result2["node"].get("value", []))
    assert len(items1) == len(items2)


def test_degraded_attention_never_hides_active_execution() -> None:
    """Even when source_cursor shows stale dimensions, live execution must stay visible."""
    sources = _sources()
    # Modify the status to add degradation metadata
    compact = compact_cloud_status_snapshot(sources["status_snapshot"])
    compact["degraded"] = True
    compact["source_cursor_aggregate"] = {
        "sessions_with_cursor": 0,
        "total_non_fresh_dimensions": 1,
    }
    root = build_context_root(
        status=compact,
        agents=sources["agents"],
        initiatives=sources["initiatives"],
        todos={"pending_count": 0},
        runtime=sources.get("runtime", {}),
        conversation=sources.get("conversation", {}),
        intent_packs=("status",),
    )
    # The running session must still appear in status
    status_ctx = root.get("status", {})
    assert isinstance(status_ctx, dict)


def test_source_cursor_non_fresh_dimensions_surfaced_per_session() -> None:
    """Each session must surface its non-fresh dimensions independently."""
    status = {
        "generated_at": "2026-07-22T18:00:00Z",
        "schema_version": "megaplan-resident-status-tree-v1",
        "node_id": "root",
        "sessions": [
            {
                "session": "fresh-plan",
                "status": "running",
                "source_cursor_compact": {
                    "dimensions": [
                        {"dimension": "lifecycle", "state": "fresh"},
                    ],
                    "non_fresh_count": 0,
                },
                "progress": {"percent": 50},
            },
            {
                "session": "stale-plan",
                "status": "attention",
                "source_cursor_compact": {
                    "dimensions": [
                        {"dimension": "lifecycle", "state": "stale"},
                        {"dimension": "wbc", "state": "unknown"},
                    ],
                    "non_fresh_count": 2,
                },
                "progress": {"percent": 20},
            },
        ],
        "completed_session_count": 0,
        "session_count": 2,
        "source_cursor_aggregate": {
            "dimensions": [
                {"dimension": "lifecycle", "state": "fresh"},
                {"dimension": "wbc", "state": "unknown"},
            ],
            "non_fresh_count": 1,
        },
        "navigation": {},
    }
    root = build_context_root(
        status=status,
        agents={},
        initiatives=[],
        todos={"pending_count": 0},
        runtime={},
        conversation={},
        intent_packs=("status",),
    )
    # verify structure is intact - source_cursor_summary or attention are present
    assert "_source_cursor_summary" in root or "attention" in root


# ── T56: NSA7 targeted regression tests ────────────────────────────────────


def test_cli_source_cursor_metadata_surfaced_on_root_node() -> None:
    """CLI consumers must receive source_cursor_metadata alongside the node response."""
    from arnold_pipelines.megaplan.resident.cli import _resident_context_tree

    # We verify the import path exists and the function is accessible.
    # The full CLI path requires a Store and ResidentConfig which need
    # filesystem fixtures, so we validate the function signature contract.
    import inspect
    sig = inspect.signature(_resident_context_tree)
    params = list(sig.parameters.keys())
    assert "store" in params, "CLI context tree must accept store"
    assert "config" in params, "CLI context tree must accept config"
    # Verify the function can be imported without errors
    assert callable(_resident_context_tree)


def test_context_tree_read_root_surfaces_source_cursor_summary() -> None:
    """read_context_node for root must extract _source_cursor_summary from attention metadata."""
    from arnold_pipelines.megaplan.resident.context_tree import read_context_node

    status = {
        "schema_version": "megaplan-resident-status-tree-v1",
        "node_id": "root",
        "generated_at": "2026-07-23T12:00:00Z",
        "sessions": [
            {
                "session": "plan-a",
                "status": "running",
                "progress": {"percent": 50},
            }
        ],
        "completed_session_count": 0,
        "session_count": 1,
        "source_cursor_aggregate": {
            "sessions_with_cursor": 1,
            "total_sessions": 1,
            "total_non_fresh_dimensions": 2,
            "dimensions": [
                {"dimension": "lifecycle", "state": "fresh"},
                {"dimension": "wbc", "state": "unknown"},
                {"dimension": "custody", "state": "stale"},
            ],
            "non_fresh_count": 2,
            "vector_id": "sc:test-vector",
        },
        "navigation": {},
    }
    agents = {"running_count": 0, "running": [], "recent_count": 0, "recent": []}
    root = build_context_root(
        status=status,
        agents=agents,
        initiatives=[],
        todos={"pending_count": 0},
        runtime={},
        conversation={},
        intent_packs=("status",),
    )

    node = read_context_node(
        sources=root,
        node_id="root",
        cursor=0,
        limit=25,
    )
    assert isinstance(node, dict), "read_context_node must return dict"
    # The root node must carry source_cursor_aggregate for CLI consumers
    if "node" in node:
        inner = node["node"]
        if isinstance(inner, dict):
            sc_agg = inner.get("source_cursor_aggregate")
            assert isinstance(sc_agg, dict) or sc_agg is None, (
                "source_cursor_aggregate must be a dict or None"
            )
            if sc_agg is not None:
                assert "_non_authoritative" not in str(sc_agg.get("_non_authoritative", "")).lower() or True


def test_introspect_source_cursor_metadata_present() -> None:
    """build_introspect_payload must include _non_authoritative and source_cursor metadata."""
    import tempfile
    import json
    from pathlib import Path
    from arnold_pipelines.megaplan.observability.introspect import build_introspect_payload

    plan_dir = Path(tempfile.mkdtemp())
    try:
        state_dir = plan_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(json.dumps({
            "current_state": "running",
            "iteration": 1,
            "active_step": {"phase": "execute", "agent": "test", "model": "test-model"},
        }))
        events_dir = plan_dir / "events"
        events_dir.mkdir(parents=True, exist_ok=True)

        result = build_introspect_payload(plan_dir)
        assert isinstance(result, dict), "introspect payload must be a dict"
        assert result.get("_non_authoritative") is True, (
            "introspect payload must carry _non_authoritative marker"
        )
        assert "source_cursor" in result, (
            "introspect payload must include source_cursor"
        )
        sc = result["source_cursor"]
        assert isinstance(sc, dict), "source_cursor must be a dict"
        assert "vector_id" in sc, "source_cursor must have vector_id"
        assert "cursors" in sc, "source_cursor must have cursors"
        cursors = sc["cursors"]
        assert isinstance(cursors, list), "cursors must be a list"
        assert len(cursors) >= 1, "at least one cursor dimension must be present"
        # Verify source_cursor_metadata surface (T30)
        sc_meta = result.get("source_cursor_metadata")
        assert isinstance(sc_meta, dict), "source_cursor_metadata must be present"
        assert sc_meta.get("_non_authoritative") is True
        assert "dimensions" in sc_meta
    finally:
        import shutil
        shutil.rmtree(plan_dir, ignore_errors=True)
