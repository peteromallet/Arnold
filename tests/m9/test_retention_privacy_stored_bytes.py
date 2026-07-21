"""M9 proof tests for retained payload bytes and privacy enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.workflow.durable_refs import (
    DurableRef,
    EncryptionScope,
    validate_durable_ref_byte_access_schema,
)
from arnold.workflow.ledger_migrations import (
    FileBackedPayloadMigrationLog,
    LedgerPayloadMigration,
    MigrationStatus,
    assert_legacy_ref_readable,
)
from arnold.workflow.ledger_payload_store import (
    FileBackedLedgerPayloadStore,
    KeyUnavailableError,
    LegacyHistoryUnbackfillableError,
    LegalHoldError,
    LocalPayloadKeyring,
    PayloadExpiredError,
    PayloadTombstonedError,
    TenantIsolationError,
)
from arnold.workflow.ledger_trace import FileLedgerTrace
from arnold.workflow.payload_policy import RetentionMode, RetentionPayloadPolicy


def _store(tmp_path: Path) -> tuple[
    FileBackedLedgerPayloadStore,
    LocalPayloadKeyring,
    FileLedgerTrace,
]:
    keyring = LocalPayloadKeyring()
    keyring.add_key("tenant-key", 1, b"local-test-key-material", primary=True)
    trace = FileLedgerTrace(tmp_path / "trace.jsonl")
    return (
        FileBackedLedgerPayloadStore(tmp_path / "payloads", keyring, trace=trace),
        keyring,
        trace,
    )


def _ciphertexts(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "payloads" / "objects").glob("*.bin"))


def test_retained_bytes_are_encrypted_and_cross_tenant_access_is_denied(
    tmp_path: Path,
) -> None:
    store, _, trace = _store(tmp_path)
    plaintext = b"tenant secret bytes"
    ref = store.put_bytes(plaintext, tenant_id="tenant-a", workflow_id="workflow-a")

    assert validate_durable_ref_byte_access_schema(ref) == []
    assert plaintext not in _ciphertexts(tmp_path)[0].read_bytes()
    assert store.read_bytes(ref, tenant_id="tenant-a", workflow_id="workflow-a") == plaintext
    with pytest.raises(TenantIsolationError):
        store.read_bytes(ref, tenant_id="tenant-b", workflow_id="workflow-a")

    assert [event.event_type for event in trace.read_all()] == [
        "write",
        "read",
        "scope_check",
    ]
    assert trace.read_all()[-1].outcome == "denied"
    assert trace.read_all()[-1].reason == "tenant mismatch"


def test_legal_hold_and_expiry_preserve_bytes_while_denying_disallowed_access(
    tmp_path: Path,
) -> None:
    store, _, trace = _store(tmp_path)
    held = store.put_bytes(
        b"held bytes",
        tenant_id="tenant-a",
        workflow_id="workflow-a",
        retention_policy=RetentionPayloadPolicy(
            retention_mode=RetentionMode.LEGAL_HOLD,
            legal_hold=True,
        ),
        now_ns=100,
    )
    expiring = store.put_bytes(
        b"short lived",
        tenant_id="tenant-a",
        workflow_id="workflow-a",
        retention_policy=RetentionPayloadPolicy(
            retention_mode=RetentionMode.RUN,
            max_retention_seconds=1,
        ),
        now_ns=1_000,
    )

    with pytest.raises(LegalHoldError):
        store.delete_bytes(held, tenant_id="tenant-a", workflow_id="workflow-a")
    assert _ciphertexts(tmp_path)
    with pytest.raises(PayloadExpiredError):
        store.read_bytes(
            expiring,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            now_ns=1_000 + 2_000_000_000,
        )
    assert _ciphertexts(tmp_path)

    denied = [event for event in trace.read_all() if event.outcome == "denied"]
    assert [(event.event_type, event.reason) for event in denied] == [
        ("delete", "legal hold active"),
        ("read", "expired"),
    ]


def test_missing_key_and_tombstone_are_byte_level_failures(tmp_path: Path) -> None:
    store, _, trace = _store(tmp_path)
    ref = store.put_bytes(b"keyed", tenant_id="tenant-a", workflow_id="workflow-a")

    reader_without_keys = FileBackedLedgerPayloadStore(
        tmp_path / "payloads",
        LocalPayloadKeyring(),
    )
    assert validate_durable_ref_byte_access_schema(ref) == []
    with pytest.raises(KeyUnavailableError):
        reader_without_keys.read_bytes(
            ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )

    tombstoned = store.delete_bytes(
        ref,
        tenant_id="tenant-a",
        workflow_id="workflow-a",
        now_ns=99,
    )
    assert tombstoned.tombstoned_at_ns == 99
    assert _ciphertexts(tmp_path) == []
    with pytest.raises(PayloadTombstonedError):
        store.read_bytes(ref, tenant_id="tenant-a", workflow_id="workflow-a")

    assert [(event.event_type, event.outcome, event.key_version) for event in trace.read_all()] == [
        ("write", "stored", 1),
        ("delete", "tombstoned", 1),
        ("read", "denied", 1),
    ]


def test_schema_valid_metadata_without_backing_bytes_cannot_satisfy_privacy_policy(
    tmp_path: Path,
) -> None:
    store, _, _ = _store(tmp_path)
    ref = DurableRef(
        store_id=store.store_id,
        locator="missing-object",
        digest="sha256:" + "1" * 64,
        encryption_scope=EncryptionScope.TENANT_KEY,
        tenant_id="tenant-a",
        workflow_id="workflow-a",
        key_id="tenant-key",
        key_version=1,
        created_at_ns=1,
    )

    assert validate_durable_ref_byte_access_schema(ref) == []
    with pytest.raises(PayloadTombstonedError):
        store.read_bytes(ref, tenant_id="tenant-a", workflow_id="workflow-a")


def test_interrupted_migration_recovers_and_unbackfillable_history_stays_denied(
    tmp_path: Path,
) -> None:
    store, _, _ = _store(tmp_path)
    migration = LedgerPayloadMigration(
        store,
        FileBackedPayloadMigrationLog(tmp_path / "migration-log"),
    )
    interrupted = migration.migrate_legacy_bytes(
        migration_id="migrate-recoverable",
        legacy_id="legacy-1",
        data=b"legacy bytes",
        tenant_id="tenant-a",
        workflow_id="workflow-a",
        crash_after_write=True,
    )
    missing = migration.mark_unbackfillable(
        migration_id="migrate-missing",
        legacy_id="legacy-missing",
        tenant_id="tenant-a",
        workflow_id="workflow-a",
        reason="legacy sidecar contained digest only",
    )

    assert interrupted.status == MigrationStatus.PAYLOAD_WRITTEN
    recovered = migration.recover_interrupted()
    assert [checkpoint.status for checkpoint in recovered] == [MigrationStatus.COMPLETED]
    assert store.read_bytes(
        recovered[0].ref,
        tenant_id="tenant-a",
        workflow_id="workflow-a",
    ) == b"legacy bytes"
    assert missing.ref is not None
    with pytest.raises(LegacyHistoryUnbackfillableError):
        assert_legacy_ref_readable(missing.ref)
    with pytest.raises(LegacyHistoryUnbackfillableError):
        store.read_bytes(
            missing.ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )
