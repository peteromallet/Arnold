"""Deliberation hooks: suspend the walk-loop when HumanReviewStep requests human input.

On resume the caller populates ``ctx.inputs['human_input']`` (the key
HumanReviewStep actually reads — *not* ``'human_review'``).
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline import ContractStatus, NullExecutorHooks, ParallelStage, Stage, StepResult

__all__ = ["DeliberationHooks"]


class DeliberationHooks(NullExecutorHooks):
    """Hooks that suspend when ``result.contract_result.status == SUSPENDED``."""

    def should_suspend(
        self,
        stage: Stage | ParallelStage,
        state: Any,
        result: StepResult,
    ) -> tuple[bool, str | None]:
        contract = result.contract_result
        if contract is not None and contract.status == ContractStatus.SUSPENDED:
            return True, "human_review_requested"
        return False, None
