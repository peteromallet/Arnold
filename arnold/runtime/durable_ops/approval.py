"""Approval link contracts for durable operation runs.

Resident confirmations are scheduled-job-backed in the compatibility layer.
Arnold stores only this external link: provider label plus confirmation request
ID.  Approval storage and resolution remain owned by the external provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["ApprovalLink"]


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
