"""Security broker contract types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from arnold.security.redaction import redact_mapping, redact_text


class ActionVerdict(str, Enum):
    """Stable broker decision vocabulary for covered actions."""

    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class RetentionPolicy(str, Enum):
    """How long the broker may retain the redacted action record."""

    TRANSIENT = "transient"
    AUDIT = "audit"
    DURABLE = "durable"


class RedactionStatus(str, Enum):
    """Whether an agent-visible result has been scrubbed."""

    SANITIZED = "sanitized"


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """Broker-facing description of a high-risk action request."""

    action_type: str
    provider: str | None = None
    repo: str | None = None
    branch: str | None = None
    command: tuple[str, ...] = ()
    force: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.action_type:
            raise ValueError("action_type is required")
        object.__setattr__(self, "command", tuple(str(item) for item in self.command))
        object.__setattr__(self, "metadata", redact_mapping(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Sanitized broker result visible to the agent process."""

    verdict: ActionVerdict
    summary: str
    action_id: str | None = None
    effect_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    redaction_status: RedactionStatus = RedactionStatus.SANITIZED
    retention_policy: RetentionPolicy = RetentionPolicy.AUDIT

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("summary is required")
        object.__setattr__(self, "summary", redact_text(self.summary))
        object.__setattr__(self, "effect_refs", tuple(str(item) for item in self.effect_refs))
        object.__setattr__(self, "metadata", redact_mapping(dict(self.metadata)))

    def to_json(self) -> dict[str, Any]:
        """Serialize a stable, sanitized payload for logs and responses."""

        payload: dict[str, Any] = {
            "verdict": self.verdict.value,
            "summary": self.summary,
            "effect_refs": list(self.effect_refs),
            "metadata": dict(self.metadata),
            "redaction_status": self.redaction_status.value,
            "retention_policy": self.retention_policy.value,
        }
        if self.action_id is not None:
            payload["action_id"] = self.action_id
        return payload


__all__ = [
    "ActionRequest",
    "ActionResult",
    "ActionVerdict",
    "RedactionStatus",
    "RetentionPolicy",
]
