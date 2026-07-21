"""Migration helpers for ledger payload byte backing.

The migration layer is explicit about histories that cannot be backfilled.
It writes recoverable checkpoints before storing bytes so interrupted local
migrations can resume from stored bytes instead of inventing metadata success.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from arnold.manifest.manifests import canonical_json
from arnold.workflow.durable_refs import DurableRef
from arnold.workflow.ledger_payload_store import (
    FileBackedLedgerPayloadStore,
    LegacyHistoryUnbackfillableError,
)
from arnold.workflow.payload_policy import RetentionPayloadPolicy


MIGRATION_SCHEMA_VERSION = "arnold.workflow.ledger_payload_migration.v1"


class MigrationStatus(StrEnum):
    STARTED = "started"
    PAYLOAD_WRITTEN = "payload_written"
    COMPLETED = "completed"
    UNBACKFILLABLE = "unbackfillable"


@dataclass(frozen=True)
class PayloadMigrationCheckpoint:
    migration_id: str
    legacy_id: str
    tenant_id: str
    workflow_id: str
    status: MigrationStatus
    ref: DurableRef | None = None
    reason: str | None = None
    updated_at_ns: int = 0
    schema_version: str = MIGRATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "migration_id": self.migration_id,
            "legacy_id": self.legacy_id,
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "updated_at_ns": self.updated_at_ns,
            "schema_version": self.schema_version,
        }
        if self.ref is not None:
            payload["ref"] = self.ref.to_dict()
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PayloadMigrationCheckpoint":
        ref_payload = payload.get("ref")
        ref = durable_ref_from_dict(ref_payload) if isinstance(ref_payload, dict) else None
        return cls(
            migration_id=payload["migration_id"],
            legacy_id=payload["legacy_id"],
            tenant_id=payload["tenant_id"],
            workflow_id=payload["workflow_id"],
            status=MigrationStatus(payload["status"]),
            ref=ref,
            reason=payload.get("reason"),
            updated_at_ns=payload.get("updated_at_ns", 0),
            schema_version=payload.get("schema_version", MIGRATION_SCHEMA_VERSION),
        )


class FileBackedPayloadMigrationLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def write(self, checkpoint: PayloadMigrationCheckpoint) -> None:
        target = self._path(checkpoint.migration_id)
        target.write_text(canonical_json(checkpoint.to_dict()), encoding="utf-8")

    def read(self, migration_id: str) -> PayloadMigrationCheckpoint | None:
        path = self._path(migration_id)
        if not path.exists():
            return None
        return PayloadMigrationCheckpoint.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def list_checkpoints(self) -> list[PayloadMigrationCheckpoint]:
        checkpoints: list[PayloadMigrationCheckpoint] = []
        for path in sorted(self.path.glob("*.json")):
            checkpoints.append(
                PayloadMigrationCheckpoint.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            )
        return checkpoints

    def _path(self, migration_id: str) -> Path:
        if not migration_id.strip() or "/" in migration_id or "\\" in migration_id:
            raise ValueError("migration_id must be a simple non-empty identifier")
        return self.path / f"{migration_id}.json"


class LedgerPayloadMigration:
    def __init__(
        self,
        store: FileBackedLedgerPayloadStore,
        log: FileBackedPayloadMigrationLog,
    ) -> None:
        self.store = store
        self.log = log

    def migrate_legacy_bytes(
        self,
        *,
        migration_id: str,
        legacy_id: str,
        data: bytes,
        tenant_id: str,
        workflow_id: str,
        retention_policy: RetentionPayloadPolicy | None = None,
        crash_after_write: bool = False,
    ) -> PayloadMigrationCheckpoint:
        self._write_checkpoint(
            migration_id=migration_id,
            legacy_id=legacy_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status=MigrationStatus.STARTED,
        )
        ref = self.store.put_bytes(
            data,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            retention_policy=retention_policy,
        )
        written = self._write_checkpoint(
            migration_id=migration_id,
            legacy_id=legacy_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status=MigrationStatus.PAYLOAD_WRITTEN,
            ref=ref,
        )
        if crash_after_write:
            return written
        return self._write_checkpoint(
            migration_id=migration_id,
            legacy_id=legacy_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status=MigrationStatus.COMPLETED,
            ref=ref,
        )

    def mark_unbackfillable(
        self,
        *,
        migration_id: str,
        legacy_id: str,
        tenant_id: str,
        workflow_id: str,
        reason: str,
    ) -> PayloadMigrationCheckpoint:
        if not reason.strip():
            raise ValueError("reason is required for unbackfillable legacy history")
        ref = unbackfillable_legacy_ref(
            legacy_id=legacy_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            reason=reason,
        )
        return self._write_checkpoint(
            migration_id=migration_id,
            legacy_id=legacy_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status=MigrationStatus.UNBACKFILLABLE,
            ref=ref,
            reason=reason,
        )

    def recover_interrupted(self) -> list[PayloadMigrationCheckpoint]:
        recovered: list[PayloadMigrationCheckpoint] = []
        for checkpoint in self.log.list_checkpoints():
            if checkpoint.status != MigrationStatus.PAYLOAD_WRITTEN:
                continue
            if checkpoint.ref is None:
                continue
            self.store.read_bytes(
                checkpoint.ref,
                tenant_id=checkpoint.tenant_id,
                workflow_id=checkpoint.workflow_id,
            )
            recovered.append(
                self._write_checkpoint(
                    migration_id=checkpoint.migration_id,
                    legacy_id=checkpoint.legacy_id,
                    tenant_id=checkpoint.tenant_id,
                    workflow_id=checkpoint.workflow_id,
                    status=MigrationStatus.COMPLETED,
                    ref=checkpoint.ref,
                )
            )
        return recovered

    def _write_checkpoint(
        self,
        *,
        migration_id: str,
        legacy_id: str,
        tenant_id: str,
        workflow_id: str,
        status: MigrationStatus,
        ref: DurableRef | None = None,
        reason: str | None = None,
    ) -> PayloadMigrationCheckpoint:
        checkpoint = PayloadMigrationCheckpoint(
            migration_id=migration_id,
            legacy_id=legacy_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status=status,
            ref=ref,
            reason=reason,
            updated_at_ns=time.time_ns(),
        )
        self.log.write(checkpoint)
        return checkpoint


def unbackfillable_legacy_ref(
    *,
    legacy_id: str,
    tenant_id: str,
    workflow_id: str,
    reason: str,
) -> DurableRef:
    digest = "sha256:" + ("0" * 64)
    return DurableRef(
        store_id="arnold.workflow.legacy_history",
        locator=legacy_id,
        digest=digest,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        metadata={
            "legacy_history": "unbackfillable",
            "legacy_history_unbackfillable": True,
            "unbackfillable_reason": reason,
        },
    )


def durable_ref_from_dict(payload: dict[str, Any]) -> DurableRef:
    return DurableRef(
        store_id=payload["store_id"],
        locator=payload["locator"],
        digest=payload.get("digest", ""),
        schema_type=payload.get("schema_type", "application/octet-stream"),
        media_type=payload.get("media_type", "application/octet-stream"),
        size_bytes=payload.get("size_bytes"),
        encryption_scope=payload.get("encryption_scope", "none"),
        access_scope=payload.get("access_scope", "workflow"),
        privacy_class=payload.get("privacy_class", "internal"),
        retention_class=payload.get("retention_class", "run"),
        availability_class=payload.get("availability_class", "standard"),
        tenant_id=payload.get("tenant_id"),
        workflow_id=payload.get("workflow_id"),
        key_id=payload.get("key_id"),
        key_version=payload.get("key_version"),
        created_at_ns=payload.get("created_at_ns"),
        expires_at_ns=payload.get("expires_at_ns"),
        legal_hold=payload.get("legal_hold", False),
        tombstoned_at_ns=payload.get("tombstoned_at_ns"),
        ref_version=payload.get("ref_version", "arnold.workflow.durable_ref.v1"),
        metadata=payload.get("metadata", {}),
    )


def assert_legacy_ref_readable(ref: DurableRef) -> None:
    if ref.metadata.get("legacy_history") == "unbackfillable" or ref.metadata.get(
        "legacy_history_unbackfillable"
    ):
        raise LegacyHistoryUnbackfillableError(
            "Legacy history has no recoverable stored bytes"
        )


__all__ = [
    "FileBackedPayloadMigrationLog",
    "LedgerPayloadMigration",
    "MIGRATION_SCHEMA_VERSION",
    "MigrationStatus",
    "PayloadMigrationCheckpoint",
    "assert_legacy_ref_readable",
    "durable_ref_from_dict",
    "unbackfillable_legacy_ref",
]
