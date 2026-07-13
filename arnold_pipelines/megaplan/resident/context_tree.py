"""Bounded progressive-disclosure context for the Megaplan resident.

The resident prompt contains only :func:`build_context_root`.  Detailed state
stays in its authoritative stores and is exposed through typed, paginated
nodes.  This prevents a status question from carrying every repair record,
conversation message, initiative, tool schema, and policy into every turn.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from .status_tree import DEFAULT_NODE_LIMIT, MAX_NODE_LIMIT, read_cloud_status_node


CONTEXT_TREE_SCHEMA = "megaplan-resident-context-tree-v1"
MAX_CONTEXT_TEXT_CHARS = 500


POLICY_PACKS: dict[str, str] = {
    "status": (
        "Use context_root.attention/status first and cite generated_at. If stale_banner is present, "
        "emit it first and do not quote frozen numbers. Read only the relevant status child node."
    ),
    "delegation": (
        "For requested execution, durably launch before acknowledging. Classify task_kind and D1-D10: "
        "Luna/low only for D1-D3 mechanical work, Terra/medium by default, Sol/high for D7-D10 or "
        "ambiguous/high-risk work. Never claim a launch without a returned durable run ID."
    ),
    "restart": (
        "Use only the canonical resident restart command from runtime/restart. Never use pkill, "
        "killall, cgroup-wide stops, or tmux server cleanup; warn that the current turn is interrupted."
    ),
    "conversation": (
        "Recent history is an excerpt. For historical claims, search the authoritative current "
        "conversation. Reply ancestry comes only from immutable preloaded ancestors or read-reply-chain."
    ),
    "initiatives": (
        "Keep planning assets under .megaplan/initiatives/<slug> using the canonical subdirectories. "
        "Search and reuse a matching initiative before creating one."
    ),
    "todos": (
        "The todo preview contains pending items, not necessarily due items. Use read_todo_list for the "
        "full retained list and stable item IDs for updates."
    ),
    "root_cause": (
        "Separate evidence, inference, and missing telemetry. Trace the exact message/turn/process records; "
        "do not substitute a generic status summary for the requested causal explanation."
    ),
}


def classify_intent_packs(text: str | None) -> tuple[str, ...]:
    """Select small policy packs deterministically from the current request."""

    lowered = (text or "").casefold()
    packs: list[str] = []
    rules = (
        ("status", ("status", "running", "progress", "what's happening", "what is happening", "active")),
        ("root_cause", ("why", "root cause", "failed", "not reply", "didn't reply", "logs")),
        ("restart", ("restart", "relaunch", "reset", "resident")),
        ("delegation", ("launch", "subagent", "sub-agent", "implement", "fix", "run ", "push")),
        ("conversation", ("message", "reply", "conversation", "said", "history")),
        ("initiatives", ("initiative", "epic", "brief", "north star", "plan")),
        ("todos", ("todo", "to-do", "remind", "recurring", "queue")),
    )
    for name, needles in rules:
        if any(needle in lowered for needle in needles):
            packs.append(name)
    return tuple(packs[:4] or ("conversation",))


def policy_directory() -> dict[str, Any]:
    return {
        "node_id": "policies",
        "packs": [
            {"name": name, "node_id": f"policies/{name}", "summary": value[:120]}
            for name, value in POLICY_PACKS.items()
        ],
    }


def build_context_root(
    *,
    status: Mapping[str, Any] | None,
    agents: Mapping[str, Any] | None,
    initiatives: Sequence[Any] | None,
    todos: Mapping[str, Any] | None,
    runtime: Mapping[str, Any] | None,
    conversation: Mapping[str, Any] | None,
    intent_packs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the small always-on orientation and navigation node."""

    status_sessions = list((status or {}).get("sessions") or [])
    attention = [
        row for row in status_sessions
        if isinstance(row, Mapping)
        and (row.get("status") not in {None, "complete", "completed"} or row.get("repairing"))
    ][:4]
    return {
        "schema_version": CONTEXT_TREE_SCHEMA,
        "node_id": "root",
        "intent_packs": list(intent_packs),
        "attention": {
            "status_generated_at": (status or {}).get("generated_at"),
            "status_stale_banner": (status or {}).get("stale_banner"),
            "sessions": [
                {
                    key: _safe(row.get(key), depth=1)
                    for key in (
                        "node_id", "session", "display_name", "status", "display_state",
                        "current_plan", "latest_activity", "operator_next", "progress", "repairing",
                    )
                    if row.get(key) is not None
                }
                for row in attention
            ],
            "running_agent_count": (agents or {}).get("running_count", 0),
            "agent_delivery_attention_count": (agents or {}).get("delivery_attention_count", 0),
            "pending_todo_count": (todos or {}).get("pending_count", 0),
        },
        "routes": [
            {"node_id": "status", "contains": "cloud sessions, progress, failures, repair evidence"},
            {"node_id": "agents", "contains": "managed agent lifecycle and delivery"},
            {"node_id": "conversation", "contains": "current transcript and reply/search guidance"},
            {"node_id": "initiatives", "contains": "initiative index and documents"},
            {"node_id": "runtime", "contains": "resident configuration, restart and lifecycle"},
            {"node_id": "todos", "contains": "VP special requests"},
            {"node_id": "capabilities", "contains": "resident tool directory"},
            {"node_id": "policies", "contains": "full operating policy packs"},
        ],
        "counts": {
            "status_sessions": (status or {}).get("session_count", len(status_sessions)),
            "initiatives": len(initiatives or ()),
            "running_agents": (agents or {}).get("running_count", 0),
            "recent_agents": (agents or {}).get("recent_count", 0),
        },
        "navigation": {
            "tool": "read_context_node",
            "search_tool": "search_context",
            "cli": "python -P -m arnold_pipelines.megaplan resident context --node '<node_id>'",
            "search_cli": (
                "python -P -m arnold_pipelines.megaplan resident context-search "
                "--scope '<scope>' --query '<query>'"
            ),
            "instruction": "Read or search only the branch needed for the current question.",
        },
        "runtime_orientation": _safe(runtime or {}, depth=1),
        "conversation_orientation": _safe(conversation or {}, depth=1),
    }


def read_context_node(
    sources: Mapping[str, Any],
    *,
    node_id: str = "root",
    cursor: int = 0,
    limit: int = DEFAULT_NODE_LIMIT,
) -> dict[str, Any]:
    """Read one allow-listed context branch; arbitrary paths are never accepted."""

    if cursor < 0 or limit < 1 or limit > MAX_NODE_LIMIT:
        return _error(node_id, f"cursor must be non-negative and limit 1..{MAX_NODE_LIMIT}")
    normalized = (node_id or "root").strip().strip("/") or "root"
    if normalized == "root":
        return {"success": True, "node": sources.get("root")}
    head, _, tail = normalized.partition("/")
    if head == "status":
        delegated = read_cloud_status_node(
            sources.get("status_snapshot"), node_id=tail or "root", cursor=cursor, limit=limit
        )
        if not delegated.get("success"):
            return delegated
        node = dict(delegated["node"] or {})
        old_id = str(node.get("node_id") or "root")
        node["node_id"] = "status" if old_id == "root" else f"status/{old_id}"
        return {"success": True, "node": node}
    if head == "policies":
        if not tail:
            return {"success": True, "node": policy_directory()}
        if tail not in POLICY_PACKS:
            return _error(normalized, "unknown policy pack")
        return _node(normalized, {"name": tail, "instruction": POLICY_PACKS[tail]})
    if head == "agents":
        agents = sources.get("agents") if isinstance(sources.get("agents"), Mapping) else {}
        branch = tail or "running"
        if branch not in {"running", "recent"}:
            return _error(normalized, "unknown agents branch")
        return _page(normalized, list(agents.get(branch) or []), cursor, limit)
    if head == "conversation":
        if tail in {"", "messages"}:
            return _page(normalized, list(sources.get("messages") or []), cursor, limit)
        return _error(normalized, "unknown conversation branch")
    if head == "initiatives":
        return _page(normalized, list(sources.get("initiatives") or []), cursor, limit)
    if head == "todos":
        return _page(normalized, list(sources.get("todos") or []), cursor, limit)
    if head == "capabilities":
        return _page(normalized, list(sources.get("capabilities") or []), cursor, limit)
    if head == "runtime":
        runtime = sources.get("runtime") if isinstance(sources.get("runtime"), Mapping) else {}
        if not tail:
            return _node(normalized, _safe(runtime, depth=3))
        if tail == "restart":
            return _node(normalized, _safe(runtime.get("restart"), depth=3))
        return _error(normalized, "unknown runtime branch")
    return _error(normalized, "unknown context-tree node")


def search_context(
    sources: Mapping[str, Any],
    *,
    scope: str,
    query: str,
    cursor: int = 0,
    limit: int = DEFAULT_NODE_LIMIT,
) -> dict[str, Any]:
    """Bounded text search over an allow-listed context namespace."""

    if scope not in {"status", "agents", "conversation", "initiatives", "todos", "capabilities", "policies"}:
        return _error(scope, "unknown search scope")
    if cursor < 0 or limit < 1 or limit > MAX_NODE_LIMIT:
        return _error(scope, f"cursor must be non-negative and limit 1..{MAX_NODE_LIMIT}")
    values: list[Any]
    if scope == "status":
        values = list((sources.get("status_snapshot") or {}).get("sessions") or [])
    elif scope == "agents":
        agents = sources.get("agents") or {}
        values = list(agents.get("running") or []) + list(agents.get("recent") or [])
    elif scope == "conversation":
        values = list(sources.get("messages") or [])
    elif scope == "initiatives":
        values = list(sources.get("initiatives") or [])
    elif scope == "todos":
        values = list(sources.get("todos") or [])
    elif scope == "capabilities":
        values = list(sources.get("capabilities") or [])
    else:
        values = [{"name": name, "instruction": text} for name, text in POLICY_PACKS.items()]
    needle = query.casefold().strip()
    matches = [value for value in values if needle in json.dumps(value, default=str).casefold()]
    return _page(f"search/{scope}", matches, cursor, limit)


def _safe(value: Any, *, depth: int) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= MAX_CONTEXT_TEXT_CHARS else value[: MAX_CONTEXT_TEXT_CHARS - 1] + "…"
    if depth <= 0:
        return {"omitted_count": len(value)} if isinstance(value, (Mapping, Sequence)) else str(value)
    if isinstance(value, Mapping):
        return {str(k): _safe(v, depth=depth - 1) for k, v in list(value.items())[:20]}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_safe(item, depth=depth - 1) for item in list(value)[:20]]
    return _safe(str(value), depth=depth)


def _node(node_id: str, value: Any) -> dict[str, Any]:
    return {"success": True, "node": {"node_id": node_id, "value": value}}


def _page(node_id: str, values: list[Any], cursor: int, limit: int) -> dict[str, Any]:
    items = [_safe(value, depth=4) for value in values[cursor : cursor + limit]]
    end = cursor + len(items)
    return {
        "success": True,
        "node": {
            "node_id": node_id,
            "items": items,
            "cursor": cursor,
            "next_cursor": end if end < len(values) else None,
            "total_count": len(values),
        },
    }


def _error(node_id: str, message: str) -> dict[str, Any]:
    return {"success": False, "node_id": node_id, "error": message}


__all__ = [
    "CONTEXT_TREE_SCHEMA",
    "POLICY_PACKS",
    "build_context_root",
    "classify_intent_packs",
    "policy_directory",
    "read_context_node",
    "search_context",
]
