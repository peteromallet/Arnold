"""Codex adapter — wraps the real ``run_codex_step`` worker for a one-shot turn.

Conforms to :data:`arnold.agent.adapters.BackendAdapter`
(``Callable[[AgentRequest], AgentResult]``) and is a first-class peer of
:class:`~arnold.agent.adapters.deepseek.DeepSeekAdapter`.

What it reuses (it does NOT reimplement)
----------------------------------------

The codex CLI argv build, sandbox/workspace flags, ``_codex_child_env``,
pre-first-byte / idle watchdogs, output parsing and ``WorkerResult``
construction all live in
``arnold_pipelines.megaplan.workers._impl.run_codex_step``.  This adapter
calls that function exactly the way the existing
``MEGAPLAN_USE_AGENT_DISPATCHER`` closure (``_codex_to_agent_result``) does,
synthesizing only the minimal ephemeral one-shot context (fresh non-persistent
session, ``read_only`` from the request, a tempdir output path, schema layout)
via :mod:`arnold.agent.adapters._oneshot`.

Import-safety
-------------

All megaplan / worker imports are **lazy** (inside ``__call__``) so importing
``arnold.agent`` never pulls the heavy worker tree (or the ``AIAgent`` tree, or
a ``utils`` top-level module that collides with the ComfyUI host) at import
time.
"""

from __future__ import annotations

from arnold.agent.adapters import _oneshot
from arnold.agent.contracts import AgentRequest, AgentResult


class CodexAdapter:
    """Adapts the real ``run_codex_step`` worker into the ``BackendAdapter`` seam.

    A single ``__call__`` runs one stateless Codex turn: it synthesizes an
    ephemeral PlanState + plan_dir + schema root, calls ``run_codex_step``
    one-shot (fresh, non-persistent), and projects the returned
    ``WorkerResult`` to an :class:`AgentResult`.
    """

    def __call__(self, request: AgentRequest) -> AgentResult:
        # Lazy import: keep arnold.agent import-safe.
        from arnold_pipelines.megaplan.workers import run_codex_step

        with _oneshot.oneshot_context(request) as ctx:
            worker_result = run_codex_step(
                ctx["step"],
                ctx["state"],
                ctx["plan_dir"],
                root=ctx["root"],
                persistent=False,
                fresh=True,
                json_trace=False,
                prompt_override=ctx["prompt"],
                prompt_kwargs=None,
                effort=ctx["effort"],
                model=ctx["model"],
                read_only=ctx["read_only"],
                output_path=ctx["output_path"],
                free_text=ctx["free_text"],
            )
            return _oneshot.project_worker_result(request, worker_result)
