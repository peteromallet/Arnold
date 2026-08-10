"""Shared helpers for the Pythonic vibecomfy-executor pipeline.

These utilities are intentionally decoupled from any step class so the
pipeline stages stay small and the orchestration logic is easy to read.

Runtime note: the current ``arnold run`` CLI still executes this pipeline
through the legacy Megaplan executor, so helpers read ``ctx.plan_dir`` and
``ctx.profile`` (Megaplan :class:`StepContext` fields) rather than the
neutral ``ctx.artifact_root``.  The pipeline graph itself is built with the
modern :class:`~arnold.pipeline.builder.PipelineBuilder` and typed ports.
"""

from __future__ import annotations

import json
import os
import sys
import types
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from arnold.agent import dispatch
from arnold.agent.contracts import AgentRequest
from arnold.pipelines.megaplan._pipeline.types import (
    StepContext as _StepContext,
    StepResult as _StepResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HIVEMIND_API_URL = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"
_HIVEMIND_API_KEY = "sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx"

_RESEARCH_SYSTEM_MESSAGE = (
    "You are a research assistant. You have access to web search, file "
    "search, and a Hivemind search tool for the Banodoco community "
    "knowledge corpus about generative video/image tooling (Wan, LTX, "
    "ComfyUI, etc.). Investigate the user's query across any relevant "
    "sources. When you have enough information, provide a concise final "
    "research summary and cite the sources you used."
)

# ---------------------------------------------------------------------------
# State / input helpers
# ---------------------------------------------------------------------------


def _state(ctx: _StepContext) -> dict[str, Any]:
    return dict(ctx.state) if isinstance(ctx.state, Mapping) else {}


def _query(ctx: _StepContext) -> str:
    return str(_state(ctx).get("query") or ctx.inputs.get("query") or "")


def _plan(ctx: _StepContext) -> dict[str, bool]:
    plan = _state(ctx).get("plan")
    if isinstance(plan, Mapping):
        return {
            "research": bool(plan.get("research", False)),
            "implement": bool(plan.get("implement", False)),
            "reply": True,
        }
    return {"research": False, "implement": False, "reply": True}


def _load_graph(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        g = dict(raw)
        return g.get("graph", g)
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                g = json.loads(text)
            except Exception:
                return None
            return g.get("graph", g) if isinstance(g, Mapping) else None
        path = Path(text)
    elif isinstance(raw, (Path, os.PathLike)):
        path = Path(raw)
    else:
        return None

    if not path.is_absolute():
        path = Path.cwd() / path
    if path.is_file():
        try:
            g = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return g.get("graph", g) if isinstance(g, Mapping) else None
    return None


def _graph(ctx: _StepContext) -> dict[str, Any] | None:
    return _state(ctx).get("graph") or _load_graph(ctx.inputs.get("graph"))


def _summarize_graph(graph: Mapping[str, Any]) -> str:
    nodes = graph.get("nodes", []) if isinstance(graph, Mapping) else []
    counts: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_type = node.get("type") or node.get("class_type")
        if node_type:
            counts[str(node_type)] = counts.get(str(node_type), 0) + 1
    if not counts:
        return "Workflow contains no nodes."
    return "Workflow nodes:\n" + "\n".join(
        f"- {t}: {c}" for t, c in sorted(counts.items())
    )


# ---------------------------------------------------------------------------
# Artifact helpers
# ---------------------------------------------------------------------------


def _artifact_path(ctx: _StepContext, filename: str) -> Path:
    root = Path(ctx.plan_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / filename


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Agent dispatch
# ---------------------------------------------------------------------------


def _extract_text(result: Any) -> str:
    if isinstance(result, Mapping):
        for key in ("final_response", "response", "content", "text"):
            val = result.get(key)
            if val:
                return str(val)
        # Some Hermes/OpenRouter runs leave final_response empty but populate
        # the assistant content in the message list.
        messages = result.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, Mapping) and msg.get("role") == "assistant":
                    content = msg.get("content")
                    if content:
                        return str(content)
    return str(result)


def _resolve_stage_spec(
    ctx: _StepContext,
    stage_name: str,
    default_spec: str,
) -> tuple[str, str | None, dict[str, Any], str | None] | None:
    """Return ``(canonical_agent, model, agent_kwargs, effort)`` for a stage."""
    profile: Mapping[str, Any] = ctx.profile if isinstance(ctx.profile, Mapping) else {}
    spec_str = str(profile.get(stage_name) or default_spec).strip()
    if not spec_str:
        return None

    from arnold.pipelines.megaplan.types import parse_agent_spec

    try:
        spec = parse_agent_spec(spec_str)
    except Exception:
        return None

    effort: str | None = None
    if spec.effort:
        effort = spec.effort

    if spec.agent == "hermes":
        model = spec.model or "deepseek:deepseek-v4-pro"
        try:
            from arnold.pipelines.megaplan.runtime.key_pool import resolve_model

            resolved_model, agent_kwargs = resolve_model(model)
        except Exception:
            return None
        return "hermes", resolved_model, agent_kwargs, effort

    if spec.agent == "codex":
        model = spec.model or "gpt-5.5"
        return "codex", model, {"provider": "openai-codex"}, effort

    if spec.agent in {"claude", "shannon"}:
        model = spec.model or "claude-opus-4-7"
        agent = "shannon" if spec.agent == "shannon" else "claude"
        return agent, model, {"provider": "anthropic"}, effort

    return None


def _call_agent(
    ctx: _StepContext,
    stage_name: str,
    prompt: str,
    system: str | None = None,
    *,
    default_spec: str = "hermes:deepseek:deepseek-v4-pro",
) -> str:
    """Dispatch a single prompt to the stage's configured agent."""
    spec = _resolve_stage_spec(ctx, stage_name, default_spec)
    if spec is None:
        raise RuntimeError(f"Could not resolve agent spec for stage {stage_name!r}")

    agent, model, agent_kwargs, effort = spec

    if agent in {"codex", "claude", "shannon"}:
        request = AgentRequest(
            agent=agent,
            mode="default",
            model=model,
            effort=effort,
            read_only=True,
            prompt=prompt,
            system_prompt=system,
        )
        return dispatch(request).raw_output

    # Hermes path: in-process AIAgent (still required for OpenRouter models).
    from arnold.agent.run_agent import AIAgent

    ai_agent = AIAgent(
        model=model,
        skip_context_files=True,
        quiet_mode=True,
        **agent_kwargs,
    )
    if system:
        result = ai_agent.run_conversation(prompt, system_message=system)
    else:
        result = ai_agent.run_conversation(prompt)
    return _extract_text(result)


# ---------------------------------------------------------------------------
# Research helpers
# ---------------------------------------------------------------------------


def _hivemind_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []

    headers = {
        "apikey": _HIVEMIND_API_KEY,
        "Authorization": f"Bearer {_HIVEMIND_API_KEY}",
        "Accept": "application/json",
    }

    def _fetch(table: str, q: str, *, kind: str | None = None) -> list[dict[str, Any]]:
        or_value = f"(title.ilike.*{q}*,body.ilike.*{q}*)"
        params: dict[str, str] = {
            "select": "kind,title,body,item_id,source,author,context,url,created_at",
            "or": or_value,
            "limit": str(limit),
        }
        if kind is not None:
            params["kind"] = f"eq.{kind}"
        encoded = urllib.parse.urlencode(params, safe="()*.,:='")
        url = f"{_HIVEMIND_API_URL}/{table}?{encoded}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

    distillations = _fetch("unified_feed", query, kind="distillation")
    if distillations:
        return distillations
    return _fetch("unified_feed", query)


def _format_tool_result(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Tool result: no results found."
    lines = [f"Tool result: {len(items)} items"]
    for idx, item in enumerate(items, 1):
        title = item.get("title") or item.get("body", "")[:60]
        kind = item.get("kind", "unknown")
        source = item.get("source", "unknown")
        body = item.get("body", "") or ""
        snippet = body[:400].replace("\n", " ")
        if len(body) > 400:
            snippet += "…"
        lines.append(f"  [{idx}] {title} ({kind}/{source}): {snippet}")
    return "\n".join(lines)


def _summarize_research_results(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return f"No Hivemind results found for: {query}\n"

    lines = [f"# Hivemind research summary for: {query}\n"]
    for idx, item in enumerate(results, 1):
        title = item.get("title") or item.get("body", "")[:60]
        body = item.get("body", "") or ""
        source = item.get("source", "unknown")
        kind = item.get("kind", "unknown")
        created = item.get("created_at", "")
        url = item.get("url", "")
        lines.append(f"## {idx}. {title} ({kind} / {source})")
        if created:
            lines.append(f"- **When**: {created}")
        if url:
            lines.append(f"- **URL**: {url}")
        snippet = body[:600].replace("\n", " ")
        if len(body) > 600:
            snippet += "…"
        lines.append(f"- **Snippet**: {snippet}\n")
    return "\n".join(lines)


def _extract_tool_calls(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    messages = result.get("messages") if isinstance(result, Mapping) else None
    if not isinstance(messages, list):
        return calls
    for msg in messages:
        if not isinstance(msg, Mapping) or msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") if isinstance(tc, Mapping) else None
            if not isinstance(fn, Mapping):
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {"raw": fn.get("arguments")}
            calls.append(
                {
                    "name": fn.get("name"),
                    "arguments": args,
                    "id": tc.get("id"),
                }
            )
    return calls


def _register_hivemind_tool(agent: Any) -> None:
    tool_def = {
        "type": "function",
        "function": {
            "name": "hivemind_search",
            "description": (
                "Search the Banodoco Hivemind community knowledge corpus about "
                "generative video/image tooling (Wan, LTX, ComfyUI, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return.",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    }
    agent.tools = list(agent.tools or [])
    if not any(
        t.get("function", {}).get("name") == "hivemind_search" for t in agent.tools
    ):
        agent.tools.append(tool_def)
    agent.register_synthetic_tool_handler(
        "hivemind_search",
        lambda function_args, **kwargs: _format_tool_result(
            _hivemind_search(str(function_args.get("query", "")), limit=int(function_args.get("limit", 10)))
        ),
        description="Search the Banodoco Hivemind knowledge corpus.",
    )


def _call_research_agent(
    ctx: _StepContext,
    query: str,
    graph_summary: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Run research for *query* and return (summary, tool_calls)."""
    spec = _resolve_stage_spec(ctx, "research", "hermes:deepseek:deepseek-v4-pro")

    prompt_parts = ["Research this query and provide a concise summary."]
    if graph_summary:
        prompt_parts.append(
            "The user has provided a ComfyUI workflow graph. Use the node "
            f"summary below to focus your research.\nWorkflow node summary:\n{graph_summary}\n"
        )
    prompt_parts.append(f"Query: {query}")
    prompt = "\n\n".join(prompt_parts)

    # Native agent families (codex / claude / shannon) do not get tool access in
    # this lightweight path; we do a single direct Hivemind search and feed the
    # results into the prompt.
    if spec is None or spec[0] in {"codex", "claude", "shannon"}:
        results = _hivemind_search(query)
        search_context = _format_tool_result(results)
        full_prompt = f"{prompt}\n\n{search_context}\n\nProvide a concise research summary."
        try:
            summary = _call_agent(ctx, "research", full_prompt, _RESEARCH_SYSTEM_MESSAGE)
        except Exception:
            summary = _summarize_research_results(query, results)
        return summary, [{"tool": "hivemind_search", "query": query, "hits": len(results)}]

    # Hermes path: give the agent a real tool it can call multiple times.
    _, model, agent_kwargs, _ = spec
    from arnold.agent.run_agent import AIAgent

    ai_agent = AIAgent(
        model=model,
        enabled_toolsets=["web", "file"],
        skip_context_files=True,
        quiet_mode=True,
        **agent_kwargs,
    )
    _register_hivemind_tool(ai_agent)
    result = ai_agent.run_conversation(
        prompt,
        system_message=_RESEARCH_SYSTEM_MESSAGE,
    )
    summary = _extract_text(result)
    tool_calls = _extract_tool_calls(result) if isinstance(result, Mapping) else []
    if not tool_calls:
        tool_calls = [{"tool": "hivemind_search", "query": query, "hits": 0}]
    return summary, tool_calls


# ---------------------------------------------------------------------------
# VibeComfy edit helpers
# ---------------------------------------------------------------------------


class _FakeRouteRegistrar:
    def get(self, path): return lambda f: f
    def post(self, path): return lambda f: f
    def put(self, path): return lambda f: f
    def delete(self, path): return lambda f: f


def _ensure_vibecomfy_importable() -> None:
    import logging

    logging.getLogger("vibecomfy.comfy_nodes").setLevel(logging.ERROR)

    if "vibecomfy.comfy_nodes.agent.routes" not in sys.modules:
        fake = types.ModuleType("vibecomfy.comfy_nodes.agent.routes")
        fake.__dict__.update({
            "get": _FakeRouteRegistrar().get,
            "post": _FakeRouteRegistrar().post,
            "put": _FakeRouteRegistrar().put,
            "delete": _FakeRouteRegistrar().delete,
        })
        sys.modules["vibecomfy.comfy_nodes.agent.routes"] = fake

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "vibecomfy" / "__init__.py").is_file():
            root = str(parent)
            if root not in sys.path:
                sys.path.insert(0, root)
            break


def _import_edit_functions() -> tuple[Any, Any, Any]:
    _ensure_vibecomfy_importable()
    from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
    from vibecomfy.comfy_nodes.agent.provider import (
        ensure_sentence_message,
        extract_batch_fence,
    )
    return handle_agent_edit, extract_batch_fence, ensure_sentence_message


def _format_edit_messages(messages: list[dict[str, str]]) -> tuple[str | None, str]:
    system_message: str | None = None
    parts: list[str] = []
    for idx, msg in enumerate(messages):
        role = str(msg.get("role", "user"))
        content = str(msg.get("content", ""))
        if role == "system" and idx == 0:
            system_message = content
        else:
            parts.append(f"{role.upper()}: {content}")
    return system_message, "\n\n".join(parts)


def _parse_edit_client_output(text: str) -> dict[str, str]:
    try:
        _, extract_batch_fence, ensure_sentence_message = _import_edit_functions()
    except Exception as exc:
        return {
            "batch": f'clarify("Could not load edit parsers: {exc}")',
            "message": f"Could not load edit parsers: {exc}",
        }

    try:
        batch, prose = extract_batch_fence(text)
    except Exception:
        batch = text.strip()
        prose = ""
    prose = ensure_sentence_message(prose, fallback="Edit turn completed.")
    return {"batch": batch, "message": prose}


def _resolve_native_edit_client(
    agent: str,
    model: str | None,
    effort: str | None,
) -> Any:
    def _client(messages: list[dict[str, str]]) -> dict[str, str]:
        if not messages:
            return {"batch": "clarify('No messages provided.')", "message": "No messages."}

        system_message, prompt = _format_edit_messages(messages)
        request = AgentRequest(
            agent=agent,
            mode="default",
            model=model,
            effort=effort,
            read_only=True,
            prompt=prompt,
            system_prompt=system_message or "You are an expert ComfyUI workflow editor.",
        )
        try:
            result = dispatch(request)
            text = result.raw_output
        except Exception as exc:
            return {
                "batch": f'clarify("{agent} dispatch edit client error: {exc}")',
                "message": f"{agent} dispatch edit client error: {exc}",
            }
        return _parse_edit_client_output(text)

    return _client


def _resolve_edit_client(ctx: _StepContext) -> Any | None:
    """Build a deepseek_client callable for VibeComfy's agent-edit loop."""
    spec = _resolve_stage_spec(ctx, "implement", "hermes:deepseek:deepseek-v4-pro")
    if spec is None:
        return None
    agent, resolved_model, agent_kwargs, effort = spec

    if agent in {"codex", "claude", "shannon"}:
        return _resolve_native_edit_client(agent, resolved_model, effort)

    # Hermes path: in-process AIAgent.
    try:
        from arnold.agent.run_agent import AIAgent

        ai_agent = AIAgent(
            model=resolved_model,
            enabled_toolsets=[],
            skip_context_files=True,
            quiet_mode=True,
            **agent_kwargs,
        )
    except Exception:
        return None

    def _client(messages: list[dict[str, str]]) -> dict[str, str]:
        if not messages:
            return {"batch": "clarify('No messages provided.')", "message": "No messages."}

        system_message: str | None = None
        if messages[0].get("role") == "system":
            system_message = str(messages[0].get("content", ""))
            remaining = messages[1:]
        else:
            remaining = list(messages)

        if remaining and remaining[-1].get("role") == "user":
            user_message = str(remaining[-1].get("content", ""))
            conversation_history = remaining[:-1]
        else:
            user_message = "\n\n".join(str(m.get("content", "")) for m in remaining)
            conversation_history = []

        try:
            if system_message:
                result = ai_agent.run_conversation(
                    user_message,
                    system_message=system_message,
                    conversation_history=conversation_history,
                )
            else:
                result = ai_agent.run_conversation(
                    user_message,
                    conversation_history=conversation_history,
                )
            text = _extract_text(result)
        except Exception as exc:
            return {
                "batch": f'clarify("Edit client error: {exc}")',
                "message": f"Edit client error: {exc}",
            }
        return _parse_edit_client_output(text)

    return _client
