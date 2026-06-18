"""Typed data contracts for the embedded VibeComfy executor.

These are the public shapes that flow through the classify → research →
implement → reply pipeline.  Every contract is a frozen dataclass with a
canonical ``to_dict()`` serializer so the executor can produce the standard
``success_envelope`` shape without adding new top-level response fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_jsonish(v) for v in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw_jsonish(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(v) for v in value]
    return value


# ── request ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecutorRequest:
    """Public input shape for ``POST /vibecomfy/agent-executor``.

    ``query`` is the only required field.  ``graph`` is the optional current
    canvas (the executor forwards it to ``handle_agent_edit`` through a
    ``{task, query, graph, session_id}`` payload when an implementation turn is
    indicated).
    """

    query: str
    graph: dict[str, Any] | None = None
    session_id: str | None = None
    profile: str | None = None
    idempotency_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": self.query}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.profile is not None:
            payload["profile"] = self.profile
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExecutorRequest":
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("ExecutorRequest requires a non-empty string `query`.")
        graph = payload.get("graph")
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("ExecutorRequest `graph` must be a dict or null.")
        session_id = payload.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("ExecutorRequest `session_id` must be a string or null.")
        profile = payload.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise ValueError("ExecutorRequest `profile` must be a string or null.")
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise ValueError("ExecutorRequest `idempotency_key` must be a string or null.")
        return cls(
            query=query.strip(),
            graph=graph,
            session_id=session_id,
            profile=profile,
            idempotency_key=idempotency_key,
        )


# ── classify decision ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClassifyDecision:
    """Model-driven classification result for an executor request.

    This is always produced by a model call (SD1: no heuristic shortcut).
    ``research`` and ``implement`` are booleans that drive whether those phases
    run; ``reply`` is True when the executor should produce a user-facing
    message (it is always True for respond-only and edit requests alike).

    ``effort`` is a coarse hint from the model ("low" / "medium" / "high")
    that downstream phases may use to select models or token budgets.
    """

    research: bool = False
    implement: bool = False
    reply: bool = True
    effort: str = "low"
    plan_summary: str = ""
    intent: str = "respond"

    def __post_init__(self) -> None:
        if self.effort not in ("low", "medium", "high"):
            object.__setattr__(self, "effort", "low")
        allowed_intents = {"edit", "research", "explain_graph", "respond"}
        if self.intent not in allowed_intents:
            object.__setattr__(self, "intent", "respond")

    def to_dict(self) -> dict[str, Any]:
        return {
            "research": self.research,
            "implement": self.implement,
            "reply": self.reply,
            "effort": self.effort,
            "plan_summary": self.plan_summary,
            "intent": self.intent,
        }

    @classmethod
    def respond_only(cls, *, effort: str = "low", plan_summary: str = "") -> "ClassifyDecision":
        """Convenience: classify as a respond-only turn (no research, no edit)."""
        return cls(research=False, implement=False, reply=True, effort=effort, plan_summary=plan_summary, intent="respond")

    @classmethod
    def edit(cls, *, research: bool = True, effort: str = "medium", plan_summary: str = "") -> "ClassifyDecision":
        """Convenience: classify as an edit turn (with research by default)."""
        return cls(research=research, implement=True, reply=True, effort=effort, plan_summary=plan_summary, intent="edit")


# ── research result ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResearchResult:
    """Aggregated research output from local corpus + optional Hivemind.

    ``sources`` is a deduplicated, score-ordered list of source references.
    ``warnings`` captures non-fatal problems (e.g. Hivemind timeout) so the
    executor can still proceed with local-only results.
    """

    summary: str = ""
    sources: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "sources": _thaw_jsonish(self.sources),
            "warnings": list(self.warnings),
        }


# ── implementation result ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ImplementationResult:
    """Output from the implement phase (graph edit or delta).

    Exactly one of ``graph`` or ``delta`` is populated.  ``message`` is the
    agent-facing explanation (carried into the reply phase for context).
    """

    graph: dict[str, Any] | None = None
    delta: tuple[dict[str, Any], ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "delta", tuple(self.delta))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": self.message}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.delta:
            payload["delta"] = _thaw_jsonish(self.delta)
        return payload


# ── report (nested executor metadata) ────────────────────────────────────────


@dataclass(frozen=True)
class Report:
    """Executor metadata nested under ``report`` in the final envelope.

    Every phase's output is captured here so the envelope stays a stable
    ``{message, outcome, candidate, eligibility, report}`` shape without
    new top-level fields.
    """

    plan: ClassifyDecision = field(default_factory=ClassifyDecision)
    research: ResearchResult | None = None
    implementation: ImplementationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        inner: dict[str, Any] = {"plan": self.plan.to_dict()}
        if self.research is not None:
            inner["research"] = self.research.to_dict()
        if self.implementation is not None:
            inner["implementation"] = self.implementation.to_dict()
        return {"executor": inner}


# ── executor result (final envelope leaf) ────────────────────────────────────


@dataclass(frozen=True)
class ExecutorResult:
    """Final executor output.

    ``ok`` mirrors the existing success/failure convention.  ``report`` carries
    plan + phase outputs.  ``graph`` is the (optionally edited) canvas.
    ``reply`` is the user-facing prose produced by the reply phase.
    """

    ok: bool = True
    report: Report = field(default_factory=Report)
    graph: dict[str, Any] | None = None
    reply: str | None = None
    failure_kind: str | None = None
    failure_stage: str | None = None
    failure_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "report": self.report.to_dict(),
        }
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.reply is not None:
            payload["reply"] = self.reply
        if self.failure_kind is not None:
            payload["failure_kind"] = self.failure_kind
        if self.failure_stage is not None:
            payload["failure_stage"] = self.failure_stage
        if self.failure_message is not None:
            payload["failure_message"] = self.failure_message
        return payload

    @classmethod
    def success(
        cls,
        *,
        report: Report | None = None,
        graph: dict[str, Any] | None = None,
        reply: str | None = None,
    ) -> "ExecutorResult":
        return cls(ok=True, report=report or Report(), graph=graph, reply=reply)

    @classmethod
    def failure(
        cls,
        *,
        kind: str,
        stage: str,
        message: str,
        report: Report | None = None,
    ) -> "ExecutorResult":
        return cls(
            ok=False,
            report=report or Report(),
            failure_kind=kind,
            failure_stage=stage,
            failure_message=message,
        )


__all__ = [
    "ClassifyDecision",
    "ExecutorRequest",
    "ExecutorResult",
    "ImplementationResult",
    "Report",
    "ResearchResult",
]
