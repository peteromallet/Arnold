"""Narrow capacity context helpers for heavy-operation call sites."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Mapping

from .capacity import CapacityDecision, CapacityGate, CapacityStatus

__all__ = [
    "CapacityContext",
    "CapacityGateRejected",
    "capacity_delay_metadata",
    "current_capacity_context",
    "gate_capacity",
    "set_capacity_context",
]


class CapacityGateRejected(RuntimeError):
    """Raised when a non-interactive heavy operation is rejected or delayed."""

    def __init__(self, decision: CapacityDecision, metadata: Mapping[str, Any]) -> None:
        self.decision = decision
        self.metadata = dict(metadata)
        super().__init__(str(self.metadata))


@dataclass
class CapacityContext:
    gate: CapacityGate
    lease_id: str
    fencing_token: int
    pool: str = "default"
    units: int = 1
    last_result: MutableMapping[str, Any] | None = None
    lease_store: Any | None = None
    project_id: str | None = None
    worktree_id: str | None = None
    lease_token: str | None = None
    lease_seconds: int = 60
    operation: str | None = None
    release_on_exit: bool = True
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "CapacityContext | None":
        if not isinstance(data, Mapping):
            return None
        gate = data.get("gate")
        if not isinstance(gate, CapacityGate):
            return None
        lease_id = data.get("lease_id")
        fencing_token = data.get("fencing_token")
        if not isinstance(lease_id, str) or not lease_id or not isinstance(fencing_token, int):
            return None
        last_result = data.get("last_result")
        return cls(
            gate=gate,
            lease_id=lease_id,
            fencing_token=fencing_token,
            pool=str(data.get("pool") or "default"),
            units=int(data.get("units") or 1),
            last_result=last_result if isinstance(last_result, MutableMapping) else None,
            lease_store=data.get("lease_store"),
            project_id=data.get("project_id") if isinstance(data.get("project_id"), str) else None,
            worktree_id=data.get("worktree_id") if isinstance(data.get("worktree_id"), str) else None,
            lease_token=data.get("lease_token") if isinstance(data.get("lease_token"), str) else None,
            lease_seconds=int(data.get("lease_seconds") or 60),
            operation=data.get("operation") if isinstance(data.get("operation"), str) else None,
            release_on_exit=bool(data.get("release_on_exit", True)),
            extra=data.get("extra") if isinstance(data.get("extra"), Mapping) else {},
        )


_CAPACITY_CONTEXT: ContextVar[CapacityContext | None] = ContextVar(
    "arnold_capacity_context",
    default=None,
)


def current_capacity_context() -> CapacityContext | None:
    return _CAPACITY_CONTEXT.get()


@contextmanager
def set_capacity_context(context: CapacityContext | Mapping[str, Any] | None) -> Iterator[None]:
    resolved = context if isinstance(context, CapacityContext) else CapacityContext.from_mapping(context)
    token = _CAPACITY_CONTEXT.set(resolved)
    try:
        yield
    finally:
        _CAPACITY_CONTEXT.reset(token)


def capacity_delay_metadata(
    decision: CapacityDecision,
    *,
    operation: str,
    waited_seconds: float = 0.0,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": decision.status.value,
        "reason": decision.reason or "capacity_exhausted",
        "waited_seconds": waited_seconds,
        "grant_required": decision.granted_units or 1,
        "grant_available": max(decision.limit - decision.used_units, 0),
        "used_units": decision.used_units,
        "limit": decision.limit,
        "retry_after_seconds": decision.retry_after_seconds,
        "lease_id": decision.lease_id,
        "fencing_token": decision.fencing_token,
    }


@contextmanager
def gate_capacity(
    operation: str,
    context: CapacityContext | Mapping[str, Any] | None = None,
) -> Iterator[CapacityDecision | None]:
    resolved = (
        context if isinstance(context, CapacityContext)
        else CapacityContext.from_mapping(context) or current_capacity_context()
    )
    if resolved is None:
        yield None
        return

    started = monotonic()
    decision = resolved.gate.acquire(
        resolved.pool,
        lease_id=resolved.lease_id,
        fencing_token=resolved.fencing_token,
        units=resolved.units,
    )
    if not decision.granted:
        metadata = capacity_delay_metadata(
            decision,
            operation=resolved.operation or operation,
            waited_seconds=monotonic() - started,
        )
        _record_capacity_result(resolved, metadata)
        raise CapacityGateRejected(decision, metadata)

    try:
        yield decision
    finally:
        if resolved.release_on_exit:
            resolved.gate.release(
                resolved.pool,
                lease_id=resolved.lease_id,
                fencing_token=resolved.fencing_token,
            )


def _record_capacity_result(context: CapacityContext, metadata: Mapping[str, Any]) -> None:
    if context.last_result is not None:
        context.last_result["capacity"] = dict(metadata)
