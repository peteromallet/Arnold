"""Shared ephemeral one-shot context synthesis for the Codex/Shannon adapters.

Both :class:`~arnold.agent.adapters.codex.CodexAdapter` and
:class:`~arnold.agent.adapters.shannon.ShannonAdapter` need to call the real
megaplan workers (``run_codex_step`` / ``run_shannon_step``) for a single
stateless agent turn.  Those workers are written against a persisted
:class:`~arnold_pipelines.megaplan.types.PlanState` plus a ``plan_dir`` and a
schema ``root``.  This module synthesizes the *minimal* ephemeral versions of
all three so a caller can run a one-shot turn given only an
:class:`~arnold.agent.contracts.AgentRequest` — no PlanState required.

Key reuse decisions
--------------------

* We do **not** rebuild any worker argv, env, sandbox, tmux, or prompt logic.
  We call ``run_codex_step`` / ``run_shannon_step`` exactly as the existing
  ``MEGAPLAN_USE_AGENT_DISPATCHER`` closures in
  ``arnold/pipelines/megaplan/workers/_impl.py`` do, and project the returned
  ``WorkerResult`` via ``WorkerResult.to_agent_result()``.
* ``request.prompt`` (optionally prefixed with ``request.system_prompt``) is
  passed as ``prompt_override`` so the heavy prompt-template machinery
  (``create_prompt_components`` + plan files) is bypassed — the worker only
  needs the schema file on disk, which ``ensure_runtime_layout`` writes.
* We use the ``"critique"`` step universally: it is in
  ``STEP_SCHEMA_FILENAMES``, codex permits it under ``read_only=True``, and no
  worker fires its mutating-launch guard for it (those guards are scoped to
  ``execute`` / ``revise`` / ``loop_execute``).

All megaplan imports are **lazy** (inside the functions) so importing
``arnold.agent`` never pulls the heavy ``arnold.agent.run_agent`` (AIAgent) tree
nor the megaplan worker tree at module top level.
"""

from __future__ import annotations

import argparse
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from arnold.agent.contracts import AgentRequest

# The synthesized step. Read-only-safe for codex and non-mutating for both
# workers, so a stateless one-shot turn never trips an execute/engine guard.
_ONESHOT_STEP = "critique"


def build_oneshot_prompt(request: AgentRequest) -> str:
    """Combine ``system_prompt`` + ``prompt`` into a single override string.

    The workers take one stdin prompt; when a ``system_prompt`` is supplied we
    prepend it so the model still sees the system framing.
    """
    prompt = request.prompt or ""
    system = request.system_prompt
    if system:
        return f"{system}\n\n{prompt}"
    return prompt


def oneshot_is_free_text(request: AgentRequest) -> bool:
    """Return ``True`` when the request wants NO structured-output enforcement.

    The tool-free / fence-based consumer (the VibeComfy agent-edit panel) sends
    a system prompt instructing the model to reply with ONE free-form fenced
    call (``batch([done()])``) and parses that raw text itself — it sets no
    output schema.  We treat the absence of an ``output_schema`` as the
    free-text signal, mirroring ``request.output_schema is None``.

    The schema is read from ``request.metadata['output_schema']`` because the
    local :class:`AgentRequest` contract carries per-request hints in
    ``metadata`` (alongside ``toolsets`` etc.).  A future top-level
    ``request.output_schema`` field, if added, takes precedence.

    When a structured caller DOES supply an ``output_schema`` the worker keeps
    its existing schema-driven path (free_text=False).
    """
    schema = getattr(request, "output_schema", None)
    if schema is None:
        schema = (request.metadata or {}).get("output_schema")
    return schema is None


def resolve_oneshot_work_dir(request: AgentRequest) -> Path:
    """Pick the source-code working directory for the one-shot.

    Honours ``request.work_dir`` (carried in ``request.metadata['work_dir']``)
    when present, else falls back to the process cwd. The directory must exist.
    """
    metadata = request.metadata or {}
    work_dir = metadata.get("work_dir")
    if work_dir:
        return Path(work_dir).expanduser().resolve()
    return Path.cwd()


@contextmanager
def oneshot_context(request: AgentRequest) -> Iterator[dict[str, Any]]:
    """Yield a synthesized ``{state, plan_dir, root, args, output_path,
    work_dir, read_only}`` bundle for a single stateless worker call.

    A fresh temporary directory holds the ephemeral plan dir and the schema
    ``root`` (``ensure_runtime_layout`` writes ``<root>/.megaplan/schemas/*``).
    The temp tree is torn down on exit.  The ``state`` is a minimal
    :class:`PlanState`-shaped dict with empty sessions (so the worker treats
    every call as a fresh one-shot).
    """
    # Lazy imports — keep arnold.agent import-safe (no AIAgent / megaplan tree
    # at module top level).
    from arnold_pipelines.megaplan._core import ensure_runtime_layout

    work_dir = resolve_oneshot_work_dir(request)
    read_only = bool(request.read_only)
    free_text = oneshot_is_free_text(request)

    with tempfile.TemporaryDirectory(prefix="arnold-oneshot-") as tmp:
        root = Path(tmp)
        ensure_runtime_layout(root)
        plan_dir = root / ".megaplan" / "plans" / "oneshot"
        plan_dir.mkdir(parents=True, exist_ok=True)

        # Where the worker writes the structured output. The worker also
        # tolerates ``None`` (it allocates its own NamedTemporaryFile), but we
        # supply an explicit path so it lands inside the torn-down tree.
        output_path = plan_dir / "oneshot_output.json"

        model = request.resolved_model or request.model

        # IMPORTANT: the plan name must be UNIQUE per dispatch. Shannon seeds its
        # claude `--session-id` (a UUIDv4) AND its local tmux session name from
        # sha256(state["name"] + step + nonce)
        # (workers/shannon.py::_seeded_rng_for_run, ::_rng_session_id, ~2110). A
        # constant name made every one-shot Claude turn reuse the SAME claude/tmux
        # session id — so after the first turn created that session, every later
        # turn ran `claude --session-id <same>` again, claude refused the
        # duplicate and exited, tmux tore down the pane, and the readiness probe
        # failed with "can't find pane". The name is INTERNAL (never sent to
        # Anthropic — only the derived UUIDv4 is). We match megaplan's normal
        # `<slug>-<timestamp>` plan-name convention and append a short random
        # suffix so back-to-back turns within the same second can't collide.
        plan_name = (
            f"agent-edit-oneshot-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
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
            "state": state,
            "plan_dir": plan_dir,
            "root": root,
            "args": argparse.Namespace(),
            "output_path": output_path,
            "work_dir": work_dir,
            "read_only": read_only,
            "model": model,
            "effort": request.effort,
            "step": _ONESHOT_STEP,
            "prompt": build_oneshot_prompt(request),
            "free_text": free_text,
        }


def project_worker_result(request: AgentRequest, worker_result: Any) -> Any:
    """Project a megaplan ``WorkerResult`` into an :class:`AgentResult`.

    Reuses the existing ``WorkerResult.to_agent_result()`` bridge, then
    overlays request-derived provenance fields the worker bridge leaves blank
    (``rendered_prompt`` falls back to the request prompt; ``provenance``
    records the agent/mode/model triple).
    """
    from arnold.agent.contracts import AgentResult, ResultProvenance

    agent_result = worker_result.to_agent_result()

    # WorkerResult.to_agent_result builds a megaplan AgentResult. It is field
    # compatible with arnold.agent.contracts.AgentResult; re-home it so the
    # adapter always returns the local contract type the dispatcher expects.
    provenance = ResultProvenance(
        agent=request.agent,
        mode=request.mode,
        model=getattr(agent_result, "model_actual", None)
        or request.resolved_model
        or request.model,
        resolved_model=request.resolved_model or request.model,
        effort=request.effort,
        session_id=getattr(agent_result, "session_id", None),
    )

    return AgentResult(
        payload=dict(getattr(agent_result, "payload", {}) or {}),
        raw_output=getattr(agent_result, "raw_output", "") or "",
        duration_ms=int(getattr(agent_result, "duration_ms", 0) or 0),
        cost_usd=float(getattr(agent_result, "cost_usd", 0.0) or 0.0),
        session_id=getattr(agent_result, "session_id", None),
        trace_output=getattr(agent_result, "trace_output", None),
        rendered_prompt=getattr(agent_result, "rendered_prompt", None)
        or request.prompt,
        model_actual=getattr(agent_result, "model_actual", None),
        prompt_tokens=int(getattr(agent_result, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(agent_result, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(agent_result, "total_tokens", 0) or 0),
        shannon_plan=getattr(agent_result, "shannon_plan", None),
        rate_limit=getattr(agent_result, "rate_limit", None),
        provenance=provenance,
    )
