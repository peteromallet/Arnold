"""Codex adapter backed by Megaplan's Codex worker."""

from __future__ import annotations

from arnold.agent.contracts import AgentRequest, AgentResult
from arnold.pipelines.megaplan.agent_adapters import _oneshot


class CodexAdapter:
    """BackendAdapter implementation backed by Megaplan's Codex worker."""

    def __call__(self, request: AgentRequest) -> AgentResult:
        from arnold.pipelines.megaplan.workers import run_codex_step

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


__all__ = ["CodexAdapter"]
