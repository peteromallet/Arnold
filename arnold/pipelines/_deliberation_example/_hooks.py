"""Deliberation hooks: suspend the native walk-loop when HumanReviewStep requests human input.

Uses the native runtime hook protocol (:class:`~arnold.pipeline.native.hooks.NativeRuntimeHooks`)
instead of the graph-era ``ExecutorHooks`` protocol.  No ``ContractStatus``,
``NullExecutorHooks``, ``ParallelStage``, ``Stage``, or ``StepResult`` imports.
"""

from __future__ import annotations

from typing import Any

from arnold.pipeline.native.hooks import NullNativeRuntimeHooks
from arnold.pipeline.native.ir import NativeInstruction

__all__ = ["DeliberationHooks"]


class DeliberationHooks(NullNativeRuntimeHooks):
    """Native runtime hooks that suspend when the *human_review* phase completes.

    Extends :class:`NullNativeRuntimeHooks` (the native protocol default) and
    overrides :meth:`should_suspend` to inspect the phase name.  When the
    completed phase is ``human_review`` and the result's ``contract_result``
    has status ``SUSPENDED``, the hook signals the native runtime to suspend.
    """

    def should_suspend(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        """Suspend when human_review phase produces a SUSPENDED result."""
        if getattr(instr, "name", None) != "human_review":
            return False, None

        contract = getattr(result, "contract_result", None)
        if contract is not None:
            status = getattr(contract, "status", None)
            from arnold.pipeline.types import ContractStatus

            if status is ContractStatus.SUSPENDED:
                return True, "human_review_requested"
        return False, None
