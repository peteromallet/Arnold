"""Cancellation primitives for supervisor-managed native runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

__all__ = [
    "CancellationRequested",
    "cancelled_contract_result",
    "cancellation_result_payload",
]


@dataclass(frozen=True)
class CancellationRequested(Exception):
    """Raised at an existing runtime cancellation boundary."""

    boundary: str
    run_path: str
    step_path: str | None = None
    call_site_path: tuple[str, ...] = ()
    instruction_op: str | None = None
    instruction_name: str | None = None
    reason: str = "cancellation_requested"

    def __str__(self) -> str:
        location = self.step_path or self.run_path
        return f"{self.reason} at {self.boundary} ({location})"

    def to_payload(self) -> dict[str, Any]:
        return {
            "cancelled": True,
            "reason": self.reason,
            "boundary": self.boundary,
            "run_path": self.run_path,
            "step_path": self.step_path,
            "call_site_path": list(self.call_site_path),
            "instruction_op": self.instruction_op,
            "instruction_name": self.instruction_name,
        }


def cancellation_result_payload(
    cancellation: CancellationRequested | Mapping[str, Any],
) -> dict[str, Any]:
    """Return JSON-safe metadata for a cancelled runtime outcome."""

    if isinstance(cancellation, CancellationRequested):
        return cancellation.to_payload()
    payload = dict(cancellation)
    payload["cancelled"] = True
    payload.setdefault("reason", "cancellation_requested")
    return payload


def cancelled_contract_result(
    cancellation: CancellationRequested | Mapping[str, Any],
) -> Any:
    """Build the current typed cancelled outcome convention.

    ``ContractStatus`` intentionally remains a three-value discriminant. A
    cancellation is therefore surfaced as a failed contract result whose payload
    carries ``cancelled=true`` and stable boundary/path metadata.
    """

    from arnold.pipeline.types import ContractResult, ContractStatus

    return ContractResult(
        status=ContractStatus.FAILED,
        payload=cancellation_result_payload(cancellation),
        authority_level="runtime",
    )
