"""External effect contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EffectKind(StrEnum):
    """Neutral effect lifecycle kinds."""

    INTENT = "intent"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    COMPENSATION = "compensation"


@dataclass(frozen=True)
class EffectDescriptor:
    """External effect descriptor recorded before execution."""

    effect_id: str
    kind: EffectKind
    target: str
    idempotency_key: str
    payload_schema_hash: str
