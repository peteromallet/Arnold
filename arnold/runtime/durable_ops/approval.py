"""Approval link contracts for durable operation runs.

Resident confirmations are scheduled-job-backed in the compatibility layer.
Arnold stores only this external link: provider label plus confirmation request
ID.  Approval storage and resolution remain owned by the external provider.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from arnold.security.types import ActionResult

from .operation import OperationRun, OperationState

__all__ = [
    "ApprovalLink",
    "BROKER_APPROVAL_SUSPENSION_KIND",
    "BrokerApprovalDecision",
    "apply_broker_approval_decision",
    "broker_approval_effect_metadata",
]


BROKER_APPROVAL_SUSPENSION_KIND = "broker_approval_gate"


@dataclass(frozen=True)
class ApprovalLink:
    """Reference to an externally managed confirmation request."""

    provider_label: str
    external_confirmation_request_id: str

    def __post_init__(self) -> None:
        if not self.provider_label:
            raise ValueError("provider_label is required")
        if not self.external_confirmation_request_id:
            raise ValueError("external_confirmation_request_id is required")

    def to_json(self) -> dict[str, str]:
        """Serialize the stable external confirmation identity."""

        return {
            "provider_label": self.provider_label,
            "external_confirmation_request_id": self.external_confirmation_request_id,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ApprovalLink":
        """Deserialize an external confirmation identity link."""

        return cls(
            provider_label=data["provider_label"],
            external_confirmation_request_id=data["external_confirmation_request_id"],
        )


class BrokerApprovalDecision(str, Enum):
    """Durable operation state decisions emitted by the broker approval flow."""

    APPROVAL_REQUIRED = "approval_required"
    APPROVE = "approve"
    DENY = "deny"
    CANCEL = "cancel"


def broker_approval_effect_metadata(action_result: ActionResult) -> dict[str, Any]:
    """Return sanitized effect metadata for a broker approval decision."""

    payload = action_result.to_json()
    return {
        "suspension_kind": BROKER_APPROVAL_SUSPENSION_KIND,
        "broker_action_id": payload.get("action_id"),
        "verdict": payload["verdict"],
        "summary": payload["summary"],
        "effect_refs": list(payload.get("effect_refs", ())),
        "metadata": dict(payload.get("metadata", {})),
        "redaction_status": payload["redaction_status"],
        "retention_policy": payload["retention_policy"],
    }


def apply_broker_approval_decision(
    run: OperationRun,
    decision: BrokerApprovalDecision | str,
    *,
    action_result: ActionResult,
    approval_link: ApprovalLink | None = None,
    suspension_cursor_ref: str | None = None,
    effect_metadata: dict[str, Any] | None = None,
) -> OperationRun:
    """Apply a broker approval decision to a durable operation run.

    Approval-required stores the declared approval link and suspension cursor
    reference, then moves the run to ``AWAITING_APPROVAL``. Approve resumes the
    run, deny fails it, and cancel moves it to the terminal cancelled state.
    """

    normalized = BrokerApprovalDecision(decision)
    target = {
        BrokerApprovalDecision.APPROVAL_REQUIRED: OperationState.AWAITING_APPROVAL,
        BrokerApprovalDecision.APPROVE: OperationState.RUNNING,
        BrokerApprovalDecision.DENY: OperationState.FAILED,
        BrokerApprovalDecision.CANCEL: OperationState.CANCELLED,
    }[normalized]
    effect = dict(effect_metadata or broker_approval_effect_metadata(action_result))
    metadata = dict(run.metadata)
    broker_approval = dict(metadata.get("broker_approval") or {})
    broker_approval.update(
        {
            "decision": normalized.value,
            "suspension_kind": BROKER_APPROVAL_SUSPENSION_KIND,
            "broker_action_id": action_result.action_id,
            "effect": effect,
        }
    )
    if approval_link is not None:
        link_payload = approval_link.to_json()
        metadata["approval"] = link_payload
        metadata["approval_link"] = link_payload
        broker_approval["approval_link"] = link_payload
    if suspension_cursor_ref is not None:
        broker_approval["suspension_cursor_ref"] = str(suspension_cursor_ref)
        metadata["suspension_cursor_ref"] = str(suspension_cursor_ref)
    metadata["broker_action_id"] = action_result.action_id
    metadata["broker_approval"] = broker_approval
    metadata["effect"] = effect
    return replace(run, metadata=metadata).transition_to(target)
