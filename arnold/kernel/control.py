"""Control transition contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class ControlTransitionType(StrEnum):
    """Neutral control transition labels."""

    OVERRIDE = "override"
    FALLBACK = "fallback"
    ESCALATION = "escalation"
    SUPERVISOR_PROMOTION = "supervisor-promotion"
    COMPENSATION = "compensation"
    OVERLAY = "overlay"


@dataclass(frozen=True)
class ControlTarget:
    """Target of a control transition."""

    node_ref: str
    edge_ref: str | None = None


@dataclass(frozen=True)
class ControlBinding:
    """Product-registered meaning for a control target."""

    binding_id: str
    target: ControlTarget
    policy_ref: str | None = None


@dataclass(frozen=True)
class ControlTransition:
    """Projected runtime overlay; it does not mutate the manifest."""

    transition_type: ControlTransitionType
    source: ControlTarget
    target: ControlTarget
    trigger: str
    payload_schema_hash: str
    policy_ref: str | None
    idempotency_key: str
    payload: Mapping[str, Any] | None = None
