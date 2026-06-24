"""Guardian inspection handlers for AgentBox operation kinds."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol

from arnold.runtime.durable_ops import OperationState

from agentbox.adapters import load_operation_adapter
from agentbox.config import AgentBoxConfig
from agentbox.guardian.model import (
    GuardianInspectionResult,
    GuardianMaterialTransition,
    GuardianOutcome,
    GuardianRetryCounters,
)
from agentbox.operations import load_agentbox_operation


MEGAPLAN_CHAIN_OPERATION_TYPE = "megaplan_chain"


class GuardianHandler(Protocol):
    """Protocol for inspecting and recovering one AgentBox operation kind."""

    operation_type: str

    async def inspect(
        self,
        config: AgentBoxConfig,
        operation_id: str,
    ) -> GuardianInspectionResult:
        """Inspect the operation and return a structured Guardian result."""
        ...

    async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
        """Attempt a safe non-destructive recovery resume."""
        ...

    def notification_summary(self, result: GuardianInspectionResult) -> str:
        """Return a short human-readable summary for notifications."""
        ...


class UnsupportedOperationTypeDiagnostic:
    """Diagnostic skip result for operation kinds Guardian v0 does not handle."""

    operation_type: str = "unknown"

    async def inspect(
        self,
        config: AgentBoxConfig,
        operation_id: str,
    ) -> GuardianInspectionResult:
        return GuardianInspectionResult(
            operation_id=operation_id,
            outcome=GuardianOutcome.NOOP,
            material_transition=GuardianMaterialTransition.NONE,
            summary=f"Unsupported operation type {self.operation_type!r}; Guardian v0 skips",
        )

    async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
        raise RuntimeError(f"Cannot resume unsupported operation type {self.operation_type!r}")

    def notification_summary(self, result: GuardianInspectionResult) -> str:
        return result.summary


@dataclass(frozen=True)
class MegaplanChainGuardianHandler:
    """Guardian handler delegating to the existing megaplan_chain adapter."""

    operation_type: str = MEGAPLAN_CHAIN_OPERATION_TYPE

    async def inspect(
        self,
        config: AgentBoxConfig,
        operation_id: str,
    ) -> GuardianInspectionResult:
        adapter = self._load_adapter()
        try:
            updated = await _to_thread(adapter.tick, config, operation_id)
            snapshot = adapter.status(config, operation_id)
        except Exception as exc:
            return GuardianInspectionResult(
                operation_id=operation_id,
                outcome=GuardianOutcome.RETRY,
                material_transition=GuardianMaterialTransition.NONE,
                summary=f"Inspection failed: {exc.__class__.__name__}: {exc}",
            )

        classification = snapshot.classification
        transition, outcome = _map_classification(classification)

        return GuardianInspectionResult(
            operation_id=operation_id,
            outcome=outcome,
            material_transition=transition,
            summary=self._summary(snapshot),
            metadata={
                "effective_status": classification.effective_status,
                "reason": classification.reason,
                "operation_state": classification.operation_state.value,
                "persisted_operation_state": updated.state.value,
            },
            inspected_at=datetime.now(UTC),
        )

    async def resume(self, config: AgentBoxConfig, operation_id: str) -> Any:
        adapter = self._load_adapter()
        return await _to_thread(adapter.resume, config, operation_id)

    def notification_summary(self, result: GuardianInspectionResult) -> str:
        metadata = dict(result.metadata)
        effective_status = metadata.get("effective_status", "unknown")
        reason = metadata.get("reason", "unknown")
        return f"Operation {result.operation_id} is {effective_status} ({reason})"

    def _load_adapter(self) -> Any:
        return load_operation_adapter(self.operation_type)

    def _summary(self, snapshot: Any) -> str:
        summarize = getattr(snapshot, "summarize", None)
        if callable(summarize):
            return summarize()
        classification = snapshot.classification
        return f"{snapshot.operation_id}: {classification.effective_status}"


def _map_classification(classification: Any) -> tuple[GuardianMaterialTransition, GuardianOutcome]:
    """Map a chain classification to a Guardian transition/outcome pair."""

    effective_status = getattr(classification, "effective_status", "")
    reason = getattr(classification, "reason", "")
    operation_state = getattr(classification, "operation_state", None)

    if effective_status == "complete" or operation_state is OperationState.SUCCEEDED:
        return GuardianMaterialTransition.COMPLETED, GuardianOutcome.OK

    if effective_status == "failed" or operation_state is OperationState.FAILED:
        return GuardianMaterialTransition.FAILED, GuardianOutcome.FAILED

    if effective_status in {
        "awaiting_human_verify",
        "awaiting_pr_merge",
        "human_prerequisite",
        "quality_gate",
    } or operation_state is OperationState.AWAITING_APPROVAL:
        return GuardianMaterialTransition.STALLED, GuardianOutcome.ESCALATED

    if effective_status == "paused" or reason == "plan_paused":
        return GuardianMaterialTransition.PAUSED, GuardianOutcome.NOOP

    if effective_status == "stale_bookkeeping":
        return GuardianMaterialTransition.STALLED, GuardianOutcome.RETRY

    if operation_state is OperationState.SUSPENDED:
        return GuardianMaterialTransition.STALLED, GuardianOutcome.RETRY

    return GuardianMaterialTransition.NONE, GuardianOutcome.OK


async def _to_thread(callable: Any, *args: Any, **kwargs: Any) -> Any:
    import asyncio

    return await asyncio.to_thread(callable, *args, **kwargs)


class GuardianHandlerRegistry:
    """Registry mapping operation types to Guardian handlers."""

    def __init__(self, handlers: Mapping[str, GuardianHandler] | None = None) -> None:
        self._handlers: dict[str, GuardianHandler] = dict(handlers or {})

    def register(self, handler: GuardianHandler) -> None:
        self._handlers[handler.operation_type] = handler

    def get(self, operation_type: str) -> GuardianHandler:
        handler = self._handlers.get(operation_type)
        if handler is None:
            diagnostic = UnsupportedOperationTypeDiagnostic()
            diagnostic.operation_type = operation_type
            return diagnostic
        return handler

    @property
    def supported_types(self) -> frozenset[str]:
        return frozenset(self._handlers)


def default_guardian_handler_registry() -> GuardianHandlerRegistry:
    registry = GuardianHandlerRegistry()
    registry.register(MegaplanChainGuardianHandler())
    return registry


__all__ = [
    "GuardianHandler",
    "GuardianHandlerRegistry",
    "MEGAPLAN_CHAIN_OPERATION_TYPE",
    "MegaplanChainGuardianHandler",
    "UnsupportedOperationTypeDiagnostic",
    "default_guardian_handler_registry",
]
