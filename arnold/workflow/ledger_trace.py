"""Append-only trace records for ledger payload byte access.

The trace is audit evidence only. It records byte-store decisions without
granting read, delete, migration, or retention authority.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.manifest.manifests import canonical_json


LEDGER_TRACE_SCHEMA_VERSION = "arnold.workflow.ledger_payload_trace.v1"


@dataclass(frozen=True)
class LedgerTraceEvent:
    event_type: str
    tenant_id: str
    workflow_id: str
    locator: str
    outcome: str
    reason: str
    key_id: str | None = None
    key_version: int | None = None
    ref_digest: str | None = None
    occurred_at_ns: int = field(default_factory=time.time_ns)
    evidence_id: str = field(default_factory=lambda: f"trace-{uuid.uuid4()}")
    schema_version: str = LEDGER_TRACE_SCHEMA_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_type": self.event_type,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "locator": self.locator,
            "outcome": self.outcome,
            "reason": self.reason,
            "occurred_at_ns": self.occurred_at_ns,
            "evidence_id": self.evidence_id,
            "schema_version": self.schema_version,
        }
        if self.key_id is not None:
            payload["key_id"] = self.key_id
        if self.key_version is not None:
            payload["key_version"] = self.key_version
        if self.ref_digest is not None:
            payload["ref_digest"] = self.ref_digest
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


class FileLedgerTrace:
    """Small JSONL trace writer used by local byte-store tests."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: LedgerTraceEvent) -> LedgerTraceEvent:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(event.to_dict()))
            handle.write("\n")
        return event

    def read_all(self) -> list[LedgerTraceEvent]:
        if not self.path.exists():
            return []
        events: list[LedgerTraceEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            events.append(
                LedgerTraceEvent(
                    event_type=payload["event_type"],
                    tenant_id=payload["tenant_id"],
                    workflow_id=payload["workflow_id"],
                    locator=payload["locator"],
                    outcome=payload["outcome"],
                    reason=payload["reason"],
                    key_id=payload.get("key_id"),
                    key_version=payload.get("key_version"),
                    ref_digest=payload.get("ref_digest"),
                    occurred_at_ns=payload["occurred_at_ns"],
                    evidence_id=payload["evidence_id"],
                    schema_version=payload.get(
                        "schema_version", LEDGER_TRACE_SCHEMA_VERSION
                    ),
                    metadata=payload.get("metadata", {}),
                )
            )
        return events


__all__ = [
    "FileLedgerTrace",
    "LEDGER_TRACE_SCHEMA_VERSION",
    "LedgerTraceEvent",
]
