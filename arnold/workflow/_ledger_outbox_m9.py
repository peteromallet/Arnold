"""Durable outbox records for payload-store publication.

Outbox records are recovery evidence. They never imply that a payload read,
delete, or migration was authorized unless the byte store re-validates the
current ref, tenant/workflow scope, key version, retention, and tombstone.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from arnold.manifest.manifests import canonical_json
from arnold.workflow.durable_refs import DurableRef
from arnold.workflow.ledger_migrations import durable_ref_from_dict
from arnold.workflow.ledger_outbox import OutboxStatus


LEDGER_OUTBOX_SCHEMA_VERSION = "arnold.workflow.ledger_payload_outbox.v1"



@dataclass(frozen=True)
class LedgerOutboxRecord:
    target: str
    ref: DurableRef
    tenant_id: str
    workflow_id: str
    idempotency_key: str
    status: OutboxStatus = OutboxStatus.PENDING
    record_id: str = field(default_factory=lambda: f"outbox-{uuid.uuid4()}")
    created_at_ns: int = field(default_factory=time.time_ns)
    updated_at_ns: int = field(default_factory=time.time_ns)
    schema_version: str = LEDGER_OUTBOX_SCHEMA_VERSION
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "record_id": self.record_id,
            "target": self.target,
            "ref": self.ref.to_dict(),
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "created_at_ns": self.created_at_ns,
            "updated_at_ns": self.updated_at_ns,
            "schema_version": self.schema_version,
        }
        if self.last_error is not None:
            payload["last_error"] = self.last_error
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LedgerOutboxRecord":
        return cls(
            record_id=payload["record_id"],
            target=payload["target"],
            ref=durable_ref_from_dict(payload["ref"]),
            tenant_id=payload["tenant_id"],
            workflow_id=payload["workflow_id"],
            idempotency_key=payload["idempotency_key"],
            status=OutboxStatus(payload["status"]),
            created_at_ns=payload["created_at_ns"],
            updated_at_ns=payload["updated_at_ns"],
            schema_version=payload.get("schema_version", LEDGER_OUTBOX_SCHEMA_VERSION),
            last_error=payload.get("last_error"),
        )


class FileBackedLedgerOutbox:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def enqueue(
        self,
        *,
        target: str,
        ref: DurableRef,
        tenant_id: str,
        workflow_id: str,
        idempotency_key: str,
    ) -> LedgerOutboxRecord:
        existing = self.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing
        record = LedgerOutboxRecord(
            target=target,
            ref=ref,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
        )
        self._append(record)
        return record

    def mark(
        self,
        record_id: str,
        status: OutboxStatus,
        *,
        last_error: str | None = None,
    ) -> LedgerOutboxRecord:
        records = self.read_all()
        for index, record in enumerate(records):
            if record.record_id != record_id:
                continue
            updated = LedgerOutboxRecord(
                record_id=record.record_id,
                target=record.target,
                ref=record.ref,
                tenant_id=record.tenant_id,
                workflow_id=record.workflow_id,
                idempotency_key=record.idempotency_key,
                status=status,
                created_at_ns=record.created_at_ns,
                updated_at_ns=time.time_ns(),
                schema_version=record.schema_version,
                last_error=last_error,
            )
            records[index] = updated
            self._rewrite(records)
            return updated
        raise KeyError(f"Outbox record {record_id!r} not found")

    def pending(self) -> list[LedgerOutboxRecord]:
        return [r for r in self.read_all() if r.status == OutboxStatus.PENDING]

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> LedgerOutboxRecord | None:
        for record in self.read_all():
            if record.idempotency_key == idempotency_key:
                return record
        return None

    def read_all(self) -> list[LedgerOutboxRecord]:
        if not self.path.exists():
            return []
        records: list[LedgerOutboxRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(LedgerOutboxRecord.from_dict(json.loads(line)))
        return records

    def _append(self, record: LedgerOutboxRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record.to_dict()))
            handle.write("\n")

    def _rewrite(self, records: list[LedgerOutboxRecord]) -> None:
        tmp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(
            "".join(canonical_json(record.to_dict()) + "\n" for record in records),
            encoding="utf-8",
        )
        tmp.replace(self.path)


__all__ = [
    "FileBackedLedgerOutbox",
    "LEDGER_OUTBOX_SCHEMA_VERSION",
    "LedgerOutboxRecord",
    "OutboxStatus",
]
