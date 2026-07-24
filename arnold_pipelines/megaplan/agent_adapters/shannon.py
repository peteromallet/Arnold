"""Shannon/Claude adapter backed by Megaplan's Shannon worker."""

from __future__ import annotations

from arnold.agent.contracts import AgentRequest, AgentResult
from arnold_pipelines.megaplan.agent_adapters import _oneshot


class ShannonAdapter:
    """BackendAdapter implementation backed by Megaplan's Shannon worker."""

    def __init__(self, *, session_agent: str = "claude") -> None:
        self._session_agent = session_agent

    @classmethod
    def is_available(cls) -> bool:
        from arnold_pipelines.megaplan._core import is_shannon_available

        return is_shannon_available()

    def __call__(self, request: AgentRequest) -> AgentResult:
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
                free_text=ctx["free_text"],
            )
        return _oneshot.project_worker_result(request, worker_result)


__all__ = ["ShannonAdapter"]
