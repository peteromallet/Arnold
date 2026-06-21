"""Content type registration contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RetentionPolicy(StrEnum):
    """Neutral retention policy labels."""

    EPHEMERAL = "ephemeral"
    RUN = "run"
    AUDIT = "audit"
    LEGAL_HOLD = "legal_hold"


@dataclass(frozen=True)
class RetentionPin:
    """Reason a generated artifact must be retained."""

    policy: RetentionPolicy
    reason: str


@dataclass(frozen=True)
class ContentTypeRegistration:
    """Content type schema registration."""

    type_id: str
    schema_version: str
    schema_hash: str
    retention_policy: RetentionPolicy = RetentionPolicy.RUN
