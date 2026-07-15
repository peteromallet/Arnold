"""Bounded progressive-disclosure context for the Megaplan resident.

The resident prompt contains only :func:`build_context_root`.  Detailed state
stays in its authoritative stores and is exposed through typed, paginated
nodes.  This prevents a status question from carrying every repair record,
conversation message, initiative, tool schema, and policy into every turn.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import json
from typing import Any

from .status_tree import DEFAULT_NODE_LIMIT, MAX_NODE_LIMIT, read_cloud_status_node


CONTEXT_TREE_SCHEMA = "megaplan-resident-context-tree-v1"
MAX_CONTEXT_TEXT_CHARS = 500


DELEGATION_POLICY: dict[str, Any] = {
    "schema_version": "megaplan-resident-delegation-policy-v3",
    "preference": (
        "Default to `launch_subagent` for any user-requested execution work when delegation "
        "adds useful execution. Decompose the query into independent actionable "
        "sub-problems and prefer one resident-managed subagent per sub-problem when delegation "
        "adds useful execution."
    ),
    "ownership": (
        "Assign one clear owner per sub-problem and never create overlapping ownership for the "
        "same sub-problem. For one logical request, name exactly one synthesis/delivery owner; "
        "all implementation and review contributors report durable results to that owner."
    ),
    "task_prompt_contract": (
        "Give each owner an action-oriented task prompt with concrete boundaries, expected outcome, "
        "and verification, plus a purpose-built concise one-line launch description."
    ),
    "aggregation": (
        "For multiple reviewer/implementation launches serving one logical query, launch internal "
        "contributors first and one synthesis/delivery owner last. Only that owner may produce the "
        "user-facing completion; it consolidates contributor result paths into one reply."
    ),
    "launch_evidence": (
        "Durably launch requested execution and make that tool call before replying. Never claim "
        "a launch without its returned durable run ID."
    ),
    "execution_default": (
        "When the user asks to do, fix, implement, land, or activate something, the delegated owner "
        "normally implements, verifies, and delivers the authorized result; it does not stop at advice "
        "or a patch description. Planning, explanation, diagnosis, status, and review requests remain "
        "non-mutating unless the user also requests execution."
    ),
    "workspace_default": (
        "For git-backed mutation, use an isolated worktree and feature branch by default, based on the "
        "verified target revision. Preserve concurrent dirty work and inspect both the project checkout "
        "and any pinned resident runtime before resident-code changes. Work in the current checkout only "
        "when the user explicitly requires it or the repository has no usable worktree workflow and the "
        "mutation is demonstrably isolated from unrelated work."
    ),
    "integration_default": (
        "The target is the branch explicitly named or clearly implied by the request; otherwise use the "
        "launch-time current non-main branch. For resident-source work, a separately pinned clean attached "
        "runtime branch in the same repository is the target over an unrelated dirty project checkout. "
        "Never infer literal `main` from an unspecified target. A dirty, detached, or divergent launch "
        "checkout requires isolation and recorded target discovery; those facts alone are not target "
        "ambiguity. For authorized implementation, revalidate the recorded target ref after verification. "
        "If it advanced on the same lineage, rebase or replay as needed and integrate locally, preferring "
        "fast-forward-only or the repository's documented non-destructive merge method. Keep the verified "
        "commit isolated with an exact enumerated gate only when multiple plausible writable refs remain, "
        "target history was rewritten or conflicts, or authorization differs materially. Local integration "
        "does not authorize a remote push, pull-request merge, deployment, or service restart."
    ),
    "external_actions": (
        "Automatically commit and locally integrate verified implementation when the request clearly "
        "authorizes execution and the target is unambiguous. Push, merge a remote pull request, deploy, "
        "or restart only when the request explicitly implies that effect or an established policy grants "
        "it, and only after exact target and revision reconciliation. Unspecified literal `main`, remote "
        "default-branch mutation, production deployment, destructive cleanup, force operations, credential "
        "changes, and other externally consequential actions require explicit approval."
    ),
    "tentative_work": (
        "For tentative, speculative, review-only, planning-only, or materially ambiguous requests, do not "
        "integrate or perform external effects. Use read-only analysis or an isolated disposable branch "
        "when a prototype is useful, label it unintegrated, and ask for the missing target or authority when "
        "different answers would materially change the delivered result."
    ),
    "completion_evidence": (
        "Before claiming completion, record proportional tests or checks, the reviewed diff, commit SHA, "
        "base and target revisions, and a clean isolated worktree. A local integration claim also requires "
        "durable ancestry evidence that the target branch contains the commit. A push requires the observed "
        "remote ref; deployment or restart requires installed-runtime revision reconciliation, the supported "
        "operation receipt, service health, and an outcome probe. A started command, PID, acknowledgement, "
        "agent prose, or artifact path alone never proves completion."
    ),
    "exceptions": {
        "non_execution": (
            "Do not launch when the user appears to request explanation, review, status, or other "
            "non-execution work."
        ),
        "trivial_or_non_independent": (
            "Do not launch agents for trivial or non-independent fragments where delegation adds "
            "no useful execution."
        ),
        "authorization": (
            "Respect authorization boundaries; delegation never expands the actions the user "
            "authorized."
        ),
    },
}


def delegation_policy_hot_context() -> dict[str, Any]:
    """Return an isolated structured copy for each generated hot context."""

    return {
        **DELEGATION_POLICY,
        "exceptions": dict(DELEGATION_POLICY["exceptions"]),
    }


def _delegation_policy_instruction() -> str:
    exceptions = DELEGATION_POLICY["exceptions"]
    return " ".join(
        (
            str(DELEGATION_POLICY["preference"]),
            str(DELEGATION_POLICY["ownership"]),
            str(DELEGATION_POLICY["task_prompt_contract"]),
            str(DELEGATION_POLICY["aggregation"]),
            str(DELEGATION_POLICY["execution_default"]),
            str(DELEGATION_POLICY["workspace_default"]),
            str(DELEGATION_POLICY["integration_default"]),
            str(DELEGATION_POLICY["external_actions"]),
            str(DELEGATION_POLICY["tentative_work"]),
            str(DELEGATION_POLICY["completion_evidence"]),
            str(exceptions["non_execution"]),
            str(exceptions["trivial_or_non_independent"]),
            str(exceptions["authorization"]),
            str(DELEGATION_POLICY["launch_evidence"]),
            "Classify task_kind and D1-D10: Luna/low only for D1-D3 mechanical work, "
            "Terra/medium by default, Sol/high for D7-D10 or ambiguous/high-risk work.",
        )
    )


POLICY_PACKS: dict[str, str] = {
    "status": (
        "Use context_root.attention/status first and cite generated_at. If stale_banner is present, "
        "emit it first and do not quote frozen numbers. Read only the relevant status child node."
    ),
    "delegation": _delegation_policy_instruction(),
    "restart": (
        "Use only the canonical resident restart command from runtime/restart. Never use pkill, "
        "killall, cgroup-wide stops, or tmux server cleanup; warn that the current turn is interrupted."
    ),
    "conversation": (
        "Recent history is an excerpt. For historical claims, search the authoritative current "
        "conversation. Reply ancestry comes only from immutable preloaded ancestors or read-reply-chain."
    ),
    "initiatives": (
        "A document is speculative/exploratory/durable knowledge and does not approve execution. A ticket "
        "is a specific addressable problem/opportunity/idea, not yet a coordinated plan. An initiative is a "
        "committed coherent outcome with boundaries and success criteria; planning or execution may follow. "
        "Search and reuse related documents, tickets, and initiatives before creating anything. Keep planning "
        "assets under .megaplan/initiatives/<slug>; README.md is the current truth/front door and canonical "
        "index. Use briefs/, research/, decisions/, notes/, handoff/, and assets/. NORTHSTAR.md and chain.yaml "
        "are optional readiness artifacts. Curate subagent findings into canonical documents that cite raw "
        "runs; never store raw run output as current truth or create planning documents under .megaplan/briefs."
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
        (
            "initiatives",
            ("document", "ticket", "initiative", "epic", "brief", "north star", "plan"),
        ),
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
    knowledge_lifecycle: Mapping[str, Any] | None = None,
    recent_activity: Mapping[str, Any] | None = None,
    ticket_count: int = 0,
    document_count: int = 0,
    intent_packs: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the small always-on orientation and navigation node."""

    status_sessions = list((status or {}).get("sessions") or [])
    attention_candidates = [
        row for row in status_sessions
        if isinstance(row, Mapping)
        and (row.get("status") not in {None, "complete", "completed"} or row.get("repairing"))
    ]
    # The status tree groups sessions by classification, so taking its first
    # four rows can hide current work behind older alphabetically ordered
    # attention rows.  The hot root is an orientation surface: prefer live
    # execution/repair, then the newest operator-attention evidence.  Detailed
    # status remains available through the paginated status route.
    attention_candidates.sort(key=_context_attention_priority, reverse=True)
    attention = attention_candidates[:4]
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
                        "node_id",
                        "session",
                        "display_name",
                        "status",
                        "display_state",
                        "review_verdict",
                        "current_plan",
                        "latest_activity",
                        "operator_next",
                        "progress",
                        "repairing",
                    )
                    if row.get(key) is not None
                }
                for row in attention
            ],
            "sessions_omitted_count": max(0, len(attention_candidates) - len(attention)),
            "running_agent_count": (agents or {}).get("running_count", 0),
            "agent_delivery_attention_count": (agents or {}).get("delivery_attention_count", 0),
            "pending_todo_count": (todos or {}).get("pending_count", 0),
        },
        "knowledge_lifecycle": _safe(knowledge_lifecycle or {}, depth=4),
        # Causal initiative activity is intentionally nested (initiative ->
        # document events) but bounded before it reaches this generic guard.
        "recent_knowledge_activity": _safe(recent_activity or {}, depth=7),
        "routes": [
            {"node_id": "status", "contains": "cloud sessions, progress, failures, repair evidence"},
            {"node_id": "agents", "contains": "managed agent lifecycle and delivery"},
            {"node_id": "conversation", "contains": "current transcript and reply/search guidance"},
            {"node_id": "tickets", "contains": "canonical ticket records and authoritative UTC timestamps"},
            {"node_id": "initiatives", "contains": "canonical initiative index and document navigation"},
            {"node_id": "documents", "contains": "durable non-state document inventory"},
            {"node_id": "runtime", "contains": "resident configuration, restart and lifecycle"},
            {"node_id": "todos", "contains": "VP special requests"},
            {"node_id": "capabilities", "contains": "resident tool directory"},
            {"node_id": "policies", "contains": "full operating policy packs"},
        ],
        "counts": {
            "status_sessions": (status or {}).get("session_count", len(status_sessions)),
            "initiatives": len(initiatives or ()),
            "tickets": max(0, ticket_count),
            "documents": max(0, document_count),
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


def _context_attention_priority(row: Mapping[str, Any]) -> tuple[int, float]:
    """Rank bounded root orientation by liveness and authoritative recency."""

    status = str(row.get("status") or "").casefold()
    live = bool(
        row.get("process") is True
        or row.get("tmux") is True
        or row.get("repairing") is True
        or status in {"running", "repairing"}
    )
    needs_attention = status in {"attention", "blocked"}
    latest = row.get("latest_activity")
    timestamp = 0.0
    if isinstance(latest, str) and latest.strip():
        try:
            timestamp = datetime.fromisoformat(
                latest.strip().replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            pass
    return (2 if live else 1 if needs_attention else 0, timestamp)


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
    if head == "tickets":
        tickets = list(sources.get("tickets") or [])
        if not tail:
            return _page(normalized, tickets, cursor, limit)
        match = next(
            (
                row
                for row in tickets
                if isinstance(row, Mapping) and str(row.get("id") or "") == tail
            ),
            None,
        )
        return _node(normalized, _safe(match, depth=4)) if match is not None else _error(normalized, "ticket not found")
    if head == "initiatives":
        initiatives = list(sources.get("initiatives") or [])
        if not tail:
            return _page(normalized, initiatives, cursor, limit)
        match = next(
            (
                row
                for row in initiatives
                if isinstance(row, Mapping) and str(row.get("slug") or "") == tail
            ),
            None,
        )
        return (
            _node(normalized, _safe(match, depth=4))
            if match is not None
            else _error(normalized, "initiative not found")
        )
    if head == "documents":
        if tail:
            return _error(normalized, "document paths are searched within the documents scope")
        return _page(normalized, list(sources.get("documents") or []), cursor, limit)
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

    if scope not in {
        "status",
        "agents",
        "conversation",
        "tickets",
        "initiatives",
        "documents",
        "todos",
        "capabilities",
        "policies",
    }:
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
    elif scope == "tickets":
        values = list(sources.get("tickets") or [])
    elif scope == "initiatives":
        values = list(sources.get("initiatives") or [])
    elif scope == "documents":
        values = list(sources.get("documents") or [])
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
