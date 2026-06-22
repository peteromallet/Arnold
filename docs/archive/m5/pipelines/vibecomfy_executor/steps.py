"""Query-orchestrator pipeline steps.

Each step is a plain dataclass implementing the neutral Arnold :class:`Step`
protocol (``name``, ``kind``, ``run(ctx) -> StepResult``).  The legacy
Megaplan executor supplies a Megaplan :class:`StepContext`, so the ``run``
methods read ``ctx.plan_dir`` and ``ctx.profile`` for runtime compatibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipelines.megaplan._pipeline.types import (
    StepContext as _StepContext,
    StepResult as _StepResult,
)

from arnold.pipelines.vibecomfy_executor._helpers import (
    _artifact_path,
    _call_agent,
    _call_research_agent,
    _graph,
    _import_edit_functions,
    _plan,
    _query,
    _resolve_edit_client,
    _summarize_graph,
    _write_json,
)


# ---------------------------------------------------------------------------
# Optional injection helpers for tests
# ---------------------------------------------------------------------------


def _classify_heuristic(query: str, graph_summary: str) -> dict[str, bool]:
    q = query.lower()
    respond_only_graph_patterns = [
        "describe this workflow",
        "describe this graph",
        "summarize this workflow",
        "summarize this graph",
        "what is this workflow",
        "what is this graph",
    ]
    if graph_summary and any(p in q for p in respond_only_graph_patterns):
        return {"research": False, "implement": False, "reply": True}

    research_triggers = [
        "best", "settings", "how to", "recommended", "compare", "what is",
        "why", "docs", "documentation", "workflow", "nodes", "node", "lora",
        "training", "wan", "ltx", "vace", "comfy", "kijai", "purpose",
        "describe", "explain", "list",
    ]
    implement_triggers = [
        "add", "create", "fix", "change", "edit", "remove", "delete",
        "refactor", "build", "implement", "update", "make", "generate",
        "apply", "set", "replace", "wire", "connect", "insert", "move",
    ]
    needs_research = any(t in q for t in research_triggers)
    needs_implement = any(t in q for t in implement_triggers)
    if graph_summary and ("this workflow" in q or "this graph" in q):
        needs_research = True
    return {
        "research": needs_research,
        "implement": needs_implement,
        "reply": True,
    }


# ---------------------------------------------------------------------------
# ClassifyStep
# ---------------------------------------------------------------------------


@dataclass
class ClassifyStep:
    """Classify the query into an execution plan."""

    name: str = "classify"
    kind: str = "produce"
    _worker: Callable[..., Any] | None = None

    def run(self, ctx: _StepContext) -> _StepResult:
        query = _query(ctx)
        graph = _graph(ctx)
        graph_summary = _summarize_graph(graph) if graph is not None else ""
        state = _state(ctx)

        if "plan" in state and isinstance(state["plan"], Mapping):
            plan = _plan(ctx)
            return self._done(plan, query, ctx, graph, source="injected")

        if callable(self._worker):
            raw = self._worker(prompt=self._prompt(query, graph_summary), system_message=None, step_name=self.name)
            plan = self._parse_plan(raw, query, graph_summary)
            return self._done(plan, query, ctx, graph, source="worker")

        try:
            raw = _call_agent(
                ctx,
                self.name,
                self._prompt(query, graph_summary),
                default_spec="hermes:deepseek:deepseek-v4-flash",
            )
            plan = self._parse_plan(raw, query, graph_summary)
            source = "worker"
        except Exception:
            plan = _classify_heuristic(query, graph_summary)
            source = "heuristic"

        return self._done(plan, query, ctx, graph, source=source)

    @staticmethod
    def _prompt(query: str, graph_summary: str) -> str:
        parts = [
            "You are a query router. Analyze the user query and decide which of "
            "the following execution steps are needed. Reply with ONLY a JSON "
            "object in this exact shape, no markdown fences:\n"
            '{"research": true|false, "implement": true|false, "reply": true}\n\n'
            "Rules:\n"
            "- research: true if the query asks about facts, best practices, "
            "settings, comparisons, node purposes, or anything where external "
            "community knowledge would help.\n"
            "  If the user is ONLY asking you to describe or summarize a workflow "
            "graph that is already provided, set research to false (the graph itself "
            "is enough to answer).\n"
            "- implement: true if the query asks to change, create, edit, fix, "
            "refactor, build, update, add, remove, or wire something concrete in a "
            "workflow.\n"
            "- reply: ALWAYS true. Every user query must get a textual answer.\n",
        ]
        if graph_summary:
            parts.append(
                "A ComfyUI workflow graph is provided. Use its node summary to "
                "decide whether the question is about the graph (research/reply) "
                "or asks you to mutate it (implement).\n"
                f"Workflow node summary:\n{graph_summary}\n"
            )
        parts.append(f"Query: {query}\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_plan(raw: Any, query: str, graph_summary: str) -> dict[str, bool]:
        text = str(raw)
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        try:
            parsed = json.loads(text.strip())
            return {
                "research": bool(parsed.get("research", False)),
                "implement": bool(parsed.get("implement", False)),
                "reply": bool(parsed.get("reply", True)),
            }
        except Exception:
            return _classify_heuristic(query, graph_summary)

    def _done(
        self,
        plan: dict[str, bool],
        query: str,
        ctx: _StepContext,
        graph: Mapping[str, Any] | None,
        source: str,
    ) -> _StepResult:
        artifact_path = _artifact_path(ctx, "plan.json")
        _write_json(
            artifact_path,
            {"query": query, "plan": plan, "classifier": source},
        )
        state_patch: dict[str, Any] = {"query": query, "plan": plan}
        if graph is not None:
            state_patch["graph"] = graph
        return _StepResult(
            outputs={"plan": artifact_path},
            next="done",
            state_patch=state_patch,
        )


# ---------------------------------------------------------------------------
# ResearchStep
# ---------------------------------------------------------------------------


@dataclass
class ResearchStep:
    """Agentic research with access to the Hivemind corpus."""

    name: str = "research"
    kind: str = "produce"
    _worker: Callable[..., Any] | None = None

    def run(self, ctx: _StepContext) -> _StepResult:
        query = _query(ctx)
        plan = _plan(ctx)
        graph = _graph(ctx)
        graph_summary = _summarize_graph(graph) if graph is not None else ""

        if not plan["research"]:
            summary = "Research skipped: not required by plan."
            artifact_path = _artifact_path(ctx, "research_summary.md")
            artifact_path.write_text(summary, encoding="utf-8")
            return _StepResult(
                outputs={"research_summary": artifact_path},
                next="done",
                state_patch={"research_summary": summary, "research_tool_calls": []},
            )

        if callable(self._worker):
            summary = str(self._worker(prompt=query, system_message=None, step_name=self.name))
            tool_calls: list[dict[str, Any]] = []
        else:
            summary, tool_calls = _call_research_agent(ctx, query, graph_summary)

        artifact_path = _artifact_path(ctx, "research_summary.md")
        artifact_path.write_text(summary, encoding="utf-8")

        raw_path = _artifact_path(ctx, "research_tool_calls.json")
        _write_json(raw_path, {"query": query, "tool_calls": tool_calls})

        return _StepResult(
            outputs={
                "research_summary": artifact_path,
                "research_tool_calls": raw_path,
            },
            next="done",
            state_patch={
                "research_summary": summary,
                "research_tool_calls": tool_calls,
            },
        )


# ---------------------------------------------------------------------------
# ImplementStep
# ---------------------------------------------------------------------------


@dataclass
class ImplementStep:
    """Conditionally produce an implementation artifact or edit a workflow."""

    name: str = "implement"
    kind: str = "produce"
    _worker: Callable[..., Any] | None = None
    _edit_client: Callable[[list[dict[str, str]]], dict[str, str]] | None = None

    def run(self, ctx: _StepContext) -> _StepResult:
        query = _query(ctx)
        plan = _plan(ctx)
        graph = _graph(ctx)

        if not plan["implement"]:
            summary = "Implementation skipped: not required by plan."
            artifact_path = _artifact_path(ctx, "implementation.md")
            artifact_path.write_text(summary, encoding="utf-8")
            return _StepResult(
                outputs={"implementation": artifact_path},
                next="done",
                state_patch={"implementation": summary, "edited_graph": None},
            )

        if graph is not None:
            return self._edit_workflow(ctx, query, graph)

        state = _state(ctx)
        research_summary = state.get("research_summary", "")

        if callable(self._worker):
            implementation = str(self._worker(
                prompt=self._implement_prompt(query, research_summary),
                system_message=None,
                step_name=self.name,
            ))
        else:
            try:
                implementation = _call_agent(
                    ctx,
                    self.name,
                    self._implement_prompt(query, research_summary),
                    default_spec="hermes:deepseek:deepseek-v4-pro",
                )
            except Exception as exc:
                implementation = f"Implementation generation failed: {exc}\n\nQuery: {query}"

        artifact_path = _artifact_path(ctx, "implementation.md")
        artifact_path.write_text(implementation, encoding="utf-8")

        return _StepResult(
            outputs={"implementation": artifact_path},
            next="done",
            state_patch={"implementation": implementation},
        )

    @staticmethod
    def _implement_prompt(query: str, research_summary: str) -> str:
        return (
            "You are an implementation assistant. Produce a concrete, actionable "
            "implementation for the user query. Use the research context below "
            "if relevant. Be specific and include examples or code where helpful.\n\n"
            f"Query: {query}\n\n"
            f"Research context:\n{research_summary}\n\n"
            "Implementation:"
        )

    def _edit_workflow(
        self, ctx: _StepContext, query: str, graph: Mapping[str, Any]
    ) -> _StepResult:
        client = self._edit_client
        if client is None:
            client = _resolve_edit_client(ctx)

        if client is None:
            summary = (
                "Workflow edit could not start: no implement model backend "
                "available. Reverting to placeholder implementation plan."
            )
            implementation = self._placeholder(query, _state(ctx).get("research_summary", ""))
            full = f"{summary}\n\n{implementation}"
            artifact_path = _artifact_path(ctx, "implementation.md")
            artifact_path.write_text(full, encoding="utf-8")
            return _StepResult(
                outputs={"implementation": artifact_path},
                next="done",
                state_patch={"implementation": full, "edited_graph": None},
            )

        task = query
        research_summary = _state(ctx).get("research_summary", "")
        if research_summary:
            task = f"{query}\n\nResearch context:\n{research_summary}"

        session_root = _artifact_path(ctx, "implement_session")
        session_id = f"qo-{Path(ctx.plan_dir).name}"

        try:
            handle_agent_edit, _, _ = _import_edit_functions()
            result = handle_agent_edit(
                {
                    "task": task,
                    "graph": dict(graph),
                    "session_id": session_id,
                    "max_batches": 50,
                    "max_consecutive_errors": 3,
                },
                deepseek_client=client,
                session_root=session_root,
            )
        except Exception as exc:
            summary = f"Workflow edit failed: {exc}"
            artifact_path = _artifact_path(ctx, "implementation.md")
            artifact_path.write_text(summary, encoding="utf-8")
            return _StepResult(
                outputs={"implementation": artifact_path},
                next="done",
                state_patch={"implementation": summary, "edited_graph": None},
            )

        outcome = result.get("outcome") if isinstance(result, Mapping) else {}
        outcome = outcome if isinstance(outcome, Mapping) else {}
        changes = outcome.get("changes") or []
        message = result.get("message") or outcome.get("message") or ""
        report = result.get("report") or {}
        candidate_graph = result.get("graph") or result.get("candidate")

        change_count = len(changes) if isinstance(changes, list) else 0
        summary_lines = [
            "## Workflow edit result",
            "",
            f"Agent message: {message}",
            f"Changes applied: {change_count}",
        ]
        if isinstance(changes, list) and changes:
            summary_lines.append("")
            summary_lines.append("### Changes")
            for ch in changes:
                summary_lines.append(f"- {ch}")
        queue_blockers = report.get("queue_blockers") or []
        if queue_blockers:
            summary_lines.append("")
            summary_lines.append(f"Queue blockers: {queue_blockers}")
        implementation = "\n".join(summary_lines)

        artifact_path = _artifact_path(ctx, "implementation.md")
        artifact_path.write_text(implementation, encoding="utf-8")

        edited_graph_path = _artifact_path(ctx, "edited_graph.json")
        _write_json(edited_graph_path, candidate_graph if candidate_graph else {})

        edit_report_path = _artifact_path(ctx, "edit_report.json")
        _write_json(
            edit_report_path,
            {
                "message": message,
                "changes": changes,
                "report": report,
                "graph_unchanged": result.get("graph_unchanged"),
            },
        )

        return _StepResult(
            outputs={
                "implementation": artifact_path,
                "edited_graph": edited_graph_path,
                "edit_report": edit_report_path,
            },
            next="done",
            state_patch={
                "implementation": implementation,
                "edited_graph": candidate_graph,
                "edit_changes": changes,
                "edit_message": message,
            },
        )

    @staticmethod
    def _placeholder(query: str, research_summary: str) -> str:
        return "\n".join(
            [
                f"# Implementation plan for: {query}",
                "",
                "## Research context",
                research_summary or "(none)",
                "",
                "## Proposed implementation",
                "- Parse the user intent.",
                "- Identify affected files, nodes, or components.",
                "- Apply the minimal change that satisfies the request.",
                "- Validate the result against the original query.",
                "",
                "_This placeholder was emitted because no worker was available. "
                "Run the pipeline with a model backend to generate real implementations._",
            ]
        )


# ---------------------------------------------------------------------------
# ReplyStep
# ---------------------------------------------------------------------------


@dataclass
class ReplyStep:
    """Always run: synthesize the final reply to the user."""

    name: str = "reply"
    kind: str = "produce"
    _worker: Callable[..., Any] | None = None

    def run(self, ctx: _StepContext) -> _StepResult:
        query = _query(ctx)
        plan = _plan(ctx)
        graph = _graph(ctx)
        graph_summary = _summarize_graph(graph) if graph is not None else ""
        state = _state(ctx)
        research_summary = state.get("research_summary", "")
        implementation = state.get("implementation", "")
        edit_changes = state.get("edit_changes")
        edit_message = state.get("edit_message", "")

        try:
            if callable(self._worker):
                reply = str(self._worker(
                    prompt=self._reply_prompt(
                        query, plan, research_summary, implementation,
                        edit_changes, edit_message, graph_summary,
                    ),
                    system_message=None,
                    step_name=self.name,
                ))
            else:
                reply = _call_agent(
                    ctx,
                    self.name,
                    self._reply_prompt(
                        query, plan, research_summary, implementation,
                        edit_changes, edit_message, graph_summary,
                    ),
                    default_spec="hermes:deepseek:deepseek-v4-pro",
                )
        except Exception as exc:
            reply = (
                f"# Reply for: {query}\n\n"
                f"**Execution plan**: research={plan.get('research')}, "
                f"implement={plan.get('implement')}, reply={plan.get('reply')}\n\n"
                "The reply step encountered an error, but the pipeline still "
                f"produced this fallback message.\n\nError: {exc}"
            )

        artifact_path = _artifact_path(ctx, "reply.md")
        artifact_path.write_text(reply, encoding="utf-8")

        return _StepResult(
            outputs={"reply": artifact_path},
            next="halt",
            state_patch={"reply": reply},
        )

    @staticmethod
    def _reply_prompt(
        query: str,
        plan: dict[str, bool],
        research_summary: str,
        implementation: str,
        edit_changes: Any,
        edit_message: str,
        graph_summary: str,
    ) -> str:
        context_parts = [f"Query: {query}"]
        if graph_summary:
            context_parts.append(graph_summary)
        if plan["research"]:
            context_parts.append(f"Research summary:\n{research_summary}")
        if plan["implement"]:
            context_parts.append(f"Implementation:\n{implementation}")
        if edit_changes:
            context_parts.append(
                f"Workflow edit changes ({len(edit_changes)}):\n{edit_changes}\n"
                f"Agent message: {edit_message}"
            )
        context = "\n\n".join(context_parts)
        return (
            "You are a helpful assistant. Write a final reply to the user based "
            "on the query and the execution context below. Be concise, accurate, "
            "and directly address the request.\n\n"
            f"{context}\n\n"
            "Final reply:"
        )


# ---------------------------------------------------------------------------
# Shared state helper (kept at the bottom to avoid forward references)
# ---------------------------------------------------------------------------


def _state(ctx: _StepContext) -> dict[str, Any]:
    return dict(ctx.state) if isinstance(ctx.state, Mapping) else {}


__all__ = [
    "ClassifyStep",
    "ResearchStep",
    "ImplementStep",
    "ReplyStep",
]
