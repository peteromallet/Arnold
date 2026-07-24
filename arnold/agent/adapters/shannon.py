"""Shannon adapter — wraps the real ``run_shannon_step`` worker for a one-shot.

Conforms to :data:`arnold.agent.adapters.BackendAdapter`
(``Callable[[AgentRequest], AgentResult]``) and is a first-class peer of
:class:`~arnold.agent.adapters.deepseek.DeepSeekAdapter`.  Runs a single
stateless Claude turn through the vendored Shannon (Claude-CLI-in-tmux) path.

What it reuses (it does NOT reimplement)
----------------------------------------

The irreducible Claude context — tmux session, workspace-trust file
(``_ensure_workspace_trusted``), ``ANTHROPIC_API_KEY=""`` subscription path,
``CLAUDE_CONFIG_DIR`` isolation, readiness handshake, paste-race handling and
output parsing — all live inside
``arnold_pipelines.megaplan.workers.shannon.run_shannon_step`` (and the
``run_turn`` executor it drives).  This adapter calls ``run_shannon_step``
exactly the way the existing ``MEGAPLAN_USE_AGENT_DISPATCHER`` closure
(``_shannon_to_agent_result``) does, synthesizing only the minimal ephemeral
one-shot context via :mod:`arnold.agent.adapters._oneshot`.

Availability is delegated to ``is_shannon_available`` (bun + tmux + claude +
the vendored fork).

Import-safety
-------------

All megaplan / worker imports are **lazy** (inside the methods) so importing
``arnold.agent`` never pulls the heavy worker tree at import time.
"""

from __future__ import annotations

from arnold.agent.adapters import _oneshot
from arnold.agent.contracts import AgentRequest, AgentResult


class ShannonAdapter:
    """Adapts the real ``run_shannon_step`` worker into the ``BackendAdapter`` seam.

    Args:
        session_agent: ``"claude"`` routes the worker's Claude-specific session
            handling (subscription path), ``"shannon"`` is the generic vendored
            session. Defaults to ``"claude"``.
    """

    def __init__(self, *, session_agent: str = "claude") -> None:
        self._session_agent = session_agent

    @classmethod
    def is_available(cls) -> bool:
        """Return ``True`` iff the vendored Shannon stack is runnable.

        Delegates to ``arnold_pipelines.megaplan._core.is_shannon_available``
        (bun + tmux + claude on PATH and the vendored fork present).
        """
        from arnold_pipelines.megaplan._core import is_shannon_available

        return is_shannon_available()

    def __call__(self, request: AgentRequest) -> AgentResult:
        # Lazy import: keep arnold.agent import-safe.
        from arnold_pipelines.megaplan.workers.shannon import run_shannon_step

        with _oneshot.oneshot_context(request) as ctx:
            worker_result = run_shannon_step(
                ctx["step"],
                ctx["state"],
                ctx["plan_dir"],
                root=ctx["root"],
                fresh=True,
                prompt_override=ctx["prompt"],
                prompt_kwargs=None,
                effort=ctx["effort"],
                session_agent=self._session_agent,
                model=ctx["model"],
                read_only=ctx["read_only"],
                output_path=ctx["output_path"],
            )
            return _oneshot.project_worker_result(request, worker_result)
