"""Broker audit helpers for native audit record enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from arnold.security.redaction import redact_mapping, redact_text, redact_value
from arnold.security.types import RedactionStatus, RetentionPolicy

__all__ = [
    "BrokerAuditEntry",
    "claim_broker_audit_entry",
    "record_broker_audit_entry",
]


@dataclass(frozen=True, slots=True)
class BrokerAuditEntry:
    """Sanitized broker audit metadata keyed by ``run_id`` and ``step_path``."""

    run_id: str
    step_path: str
    action_id: str | None = None
    effect_refs: tuple[str, ...] = ()
    git_command_ref: str | None = None
    git_effect_ref: str | None = None
    prompt_ref: str | None = None
    completion_ref: str | None = None
    redaction_status: str = RedactionStatus.SANITIZED.value
    retention_policy: str = RetentionPolicy.AUDIT.value
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id is required")
        if not self.step_path:
            raise ValueError("step_path is required")
        object.__setattr__(self, "effect_refs", tuple(str(item) for item in self.effect_refs))
        object.__setattr__(
            self,
            "redaction_status",
            str(self.redaction_status or RedactionStatus.SANITIZED.value),
        )
        object.__setattr__(
            self,
            "retention_policy",
            str(self.retention_policy or RetentionPolicy.AUDIT.value),
        )
        object.__setattr__(
            self,
            "metadata",
            redact_mapping(dict(self.metadata or {})),
        )

    def merge(self, newer: "BrokerAuditEntry") -> "BrokerAuditEntry":
        """Return a stable merge where newer non-empty values win."""

        metadata = dict(self.metadata or {})
        metadata.update(newer.metadata or {})
        return BrokerAuditEntry(
            run_id=self.run_id,
            step_path=self.step_path,
            action_id=newer.action_id or self.action_id,
            effect_refs=newer.effect_refs or self.effect_refs,
            git_command_ref=newer.git_command_ref or self.git_command_ref,
            git_effect_ref=newer.git_effect_ref or self.git_effect_ref,
            prompt_ref=newer.prompt_ref or self.prompt_ref,
            completion_ref=newer.completion_ref or self.completion_ref,
            redaction_status=newer.redaction_status or self.redaction_status,
            retention_policy=newer.retention_policy or self.retention_policy,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a redacted JSON-serializable payload."""

        return {
            "action_id": redact_text(self.action_id) if self.action_id else None,
            "effect_refs": [redact_text(item) for item in self.effect_refs],
            "git_command_ref": redact_text(self.git_command_ref) if self.git_command_ref else None,
            "git_effect_ref": redact_text(self.git_effect_ref) if self.git_effect_ref else None,
            "prompt_ref": redact_text(self.prompt_ref) if self.prompt_ref else None,
            "completion_ref": redact_text(self.completion_ref) if self.completion_ref else None,
            "redaction_status": redact_text(self.redaction_status),
            "retention_policy": redact_text(self.retention_policy),
            "metadata": redact_value(self.metadata or {}),
        }


_BROKER_AUDIT_ENTRIES: dict[tuple[str, str], BrokerAuditEntry] = {}
_BROKER_AUDIT_LOCK = Lock()


def record_broker_audit_entry(
    *,
    run_id: str,
    step_path: str,
    action_id: str | None = None,
    effect_refs: tuple[str, ...] | list[str] = (),
    git_command_ref: str | None = None,
    git_effect_ref: str | None = None,
    prompt_ref: str | None = None,
    completion_ref: str | None = None,
    redaction_status: str = RedactionStatus.SANITIZED.value,
    retention_policy: str = RetentionPolicy.AUDIT.value,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Store a sanitized broker audit entry for later audit join."""

    entry = BrokerAuditEntry(
        run_id=run_id,
        step_path=step_path,
        action_id=action_id,
        effect_refs=tuple(effect_refs),
        git_command_ref=git_command_ref,
        git_effect_ref=git_effect_ref,
        prompt_ref=prompt_ref,
        completion_ref=completion_ref,
        redaction_status=redaction_status,
        retention_policy=retention_policy,
        metadata=metadata,
    )
    key = (entry.run_id, entry.step_path)
    with _BROKER_AUDIT_LOCK:
        existing = _BROKER_AUDIT_ENTRIES.get(key)
        _BROKER_AUDIT_ENTRIES[key] = entry if existing is None else existing.merge(entry)


def claim_broker_audit_entry(run_id: str, step_path: str) -> dict[str, Any] | None:
    """Pop the broker audit payload associated with ``run_id`` and ``step_path``."""

    with _BROKER_AUDIT_LOCK:
        entry = _BROKER_AUDIT_ENTRIES.pop((run_id, step_path), None)
    return None if entry is None else entry.to_dict()
