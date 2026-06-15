"""Ephemeral one-shot context synthesis for Megaplan-backed adapters.

Codex and Shannon one-shot adapters call existing Megaplan workers without
exposing ``PlanState`` to Arnold callers. This module builds the smallest
temporary Megaplan-shaped context needed for one worker turn.
"""

from __future__ import annotations

import argparse
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from arnold.agent.contracts import AgentRequest, AgentResult, ResultProvenance
from arnold.pipelines.megaplan._core import ensure_runtime_layout

_ONESHOT_STEP = "critique"


def build_oneshot_prompt(request: AgentRequest) -> str:
    """Combine system and user prompts into the single worker prompt."""

    prompt = request.prompt or ""
    if request.system_prompt:
        return f"{request.system_prompt}\n\n{prompt}"
    return prompt


def oneshot_is_free_text(request: AgentRequest) -> bool:
    """Return true when the caller did not request structured output."""

    schema = getattr(request, "output_schema", None)
    if schema is None:
        schema = (request.metadata or {}).get("output_schema")
    return schema is None


def resolve_oneshot_work_dir(request: AgentRequest) -> Path:
    """Resolve the source working directory for a one-shot worker turn."""

    work_dir = (request.metadata or {}).get("work_dir")
    if work_dir:
        return Path(work_dir).expanduser().resolve()
    return Path.cwd().resolve()


@contextmanager
def oneshot_context(request: AgentRequest) -> Iterator[dict[str, Any]]:
    """Yield a temporary Megaplan worker context for a single stateless turn."""

    work_dir = resolve_oneshot_work_dir(request)
    model = request.resolved_model or request.model

    with tempfile.TemporaryDirectory(prefix="arnold-oneshot-") as tmp:
        root = Path(tmp)
        ensure_runtime_layout(root)
        plan_dir = root / ".megaplan" / "plans" / "oneshot"
        plan_dir.mkdir(parents=True, exist_ok=True)
        output_path = plan_dir / "oneshot_output.json"
        plan_name = (
            f"agent-oneshot-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
            f"-{uuid.uuid4().hex[:6]}"
        )

        state: dict[str, Any] = {
            "name": plan_name,
            "idea": request.prompt or "",
            "current_state": "critiqued",
            "iteration": 0,
            "created_at": "1970-01-01T00:00:00Z",
            "config": {
                "project_dir": str(work_dir),
                "auto_approve": True,
                "robustness": "standard",
                "mode": "code",
            },
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {
                "significant_counts": [],
                "weighted_scores": [],
                "plan_deltas": [],
                "recurring_critiques": [],
                "total_cost_usd": 0.0,
                "overrides": [],
                "notes": [],
            },
        }

        yield {
            "args": argparse.Namespace(),
            "effort": request.effort,
            "free_text": oneshot_is_free_text(request),
            "model": model,
            "output_path": output_path,
            "plan_dir": plan_dir,
            "prompt": build_oneshot_prompt(request),
            "read_only": bool(request.read_only),
            "root": root,
            "state": state,
            "step": _ONESHOT_STEP,
            "work_dir": work_dir,
        }


def project_worker_result(request: AgentRequest, worker_result: Any) -> AgentResult:
    """Project a Megaplan ``WorkerResult`` into the neutral Arnold contract."""

    session_id = getattr(worker_result, "session_id", None)
    model_actual = (
        getattr(worker_result, "model_actual", None)
        or request.resolved_model
        or request.model
    )
    return AgentResult(
        payload=dict(getattr(worker_result, "payload", {}) or {}),
        raw_output=getattr(worker_result, "raw_output", "") or "",
        duration_ms=int(getattr(worker_result, "duration_ms", 0) or 0),
        cost_usd=float(getattr(worker_result, "cost_usd", 0.0) or 0.0),
        session_id=session_id,
        trace_output=getattr(worker_result, "trace_output", None),
        rendered_prompt=getattr(worker_result, "rendered_prompt", None)
        or request.prompt,
        model_actual=model_actual,
        prompt_tokens=int(getattr(worker_result, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(worker_result, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(worker_result, "total_tokens", 0) or 0),
        shannon_plan=getattr(worker_result, "shannon_plan", None),
        provenance=ResultProvenance(
            agent=request.agent,
            mode=request.mode,
            model=getattr(worker_result, "model_actual", None) or request.model,
            resolved_model=model_actual,
            effort=request.effort,
            session_id=session_id,
        ),
    )


__all__ = [
    "build_oneshot_prompt",
    "oneshot_context",
    "oneshot_is_free_text",
    "project_worker_result",
    "resolve_oneshot_work_dir",
]
