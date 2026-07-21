"""Tests for stored-byte payload policy enforcement."""

from __future__ import annotations

import pytest

from arnold.workflow.durable_refs import (
    DurableRef,
    EncryptionScope,
    validate_durable_ref_byte_access_schema,
    validate_durable_ref,
)
from arnold.workflow.ledger_migrations import (
    FileBackedPayloadMigrationLog,
    LedgerPayloadMigration,
    MigrationStatus,
    assert_legacy_ref_readable,
)
from arnold.workflow.ledger_outbox import FileBackedLedgerOutbox, OutboxStatus
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
from arnold.workflow.payload_policy import (
    RetentionMode,
    RetentionPayloadPolicy,
    validate_stored_byte_policy_schema,
)


def _store(tmp_path):
    keyring = LocalPayloadKeyring()
    keyring.add_key("tenant-key", 1, b"local-test-key-material", primary=True)
    trace = FileLedgerTrace(tmp_path / "trace.jsonl")
    store = FileBackedLedgerPayloadStore(tmp_path / "payloads", keyring, trace=trace)
    return store, keyring, trace


def _stored_ciphertext_files(tmp_path):
    return sorted((tmp_path / "payloads" / "objects").glob("*.bin"))


class TestStoredBytePolicy:
    def test_encrypted_reference_roundtrip_uses_key_version_and_stored_bytes(
        self, tmp_path
    ) -> None:
        store, _, trace = _store(tmp_path)
        plaintext = b"secret bytes that must not be stored in clear text"
        ref = store.put_bytes(
            plaintext,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )

        data_files = list((tmp_path / "payloads" / "objects").glob("*.bin"))
        assert len(data_files) == 1
        assert plaintext not in data_files[0].read_bytes()
        assert ref.key_id == "tenant-key"
        assert ref.key_version == 1
        assert ref.encryption_scope == EncryptionScope.TENANT_KEY
        assert store.read_bytes(
            ref, tenant_id="tenant-a", workflow_id="workflow-a"
        ) == plaintext
        assert [event.event_type for event in trace.read_all()] == ["write", "read"]

    def test_cross_tenant_read_is_denied_against_bytes(self, tmp_path) -> None:
        store, _, trace = _store(tmp_path)
        ref = store.put_bytes(
            b"tenant-a payload",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )

        assert validate_durable_ref_byte_access_schema(ref) == []
        with pytest.raises(TenantIsolationError):
            store.read_bytes(
                ref, tenant_id="tenant-b", workflow_id="workflow-a"
            )
        assert [event.event_type for event in trace.read_all()] == [
            "write",
            "scope_check",
        ]
        assert trace.read_all()[-1].outcome == "denied"
        assert store.read_bytes(
            ref, tenant_id="tenant-a", workflow_id="workflow-a"
        ) == b"tenant-a payload"

    def test_legal_hold_blocks_deletion_and_has_no_expiry(self, tmp_path) -> None:
        store, _, trace = _store(tmp_path)
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.LEGAL_HOLD,
            legal_hold=True,
        )
        assert validate_stored_byte_policy_schema(policy) == []
        ref = store.put_bytes(
            b"held",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            retention_policy=policy,
            now_ns=100,
        )

        assert ref.expires_at_ns is None
        assert validate_durable_ref_byte_access_schema(ref) == []
        assert store.read_bytes(
            ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            now_ns=10**21,
        ) == b"held"
        with pytest.raises(LegalHoldError):
            store.delete_bytes(
                ref, tenant_id="tenant-a", workflow_id="workflow-a"
            )
        assert _stored_ciphertext_files(tmp_path)
        assert trace.read_all()[-1].event_type == "delete"
        assert trace.read_all()[-1].outcome == "denied"
        assert trace.read_all()[-1].reason == "legal hold active"

    def test_missing_key_version_denies_encrypted_reference_read(
        self, tmp_path
    ) -> None:
        store, _, _ = _store(tmp_path)
        ref = store.put_bytes(
            b"encrypted",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )
        empty_keyring = LocalPayloadKeyring()
        reader = FileBackedLedgerPayloadStore(tmp_path / "payloads", empty_keyring)

        assert validate_durable_ref_byte_access_schema(ref) == []
        with pytest.raises(KeyUnavailableError):
            reader.read_bytes(
                ref, tenant_id="tenant-a", workflow_id="workflow-a"
            )

    def test_key_version_audit_records_actual_byte_access(self, tmp_path) -> None:
        store, _, trace = _store(tmp_path)
        ref = store.put_bytes(
            b"audited",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )

        assert store.read_bytes(
            ref, tenant_id="tenant-a", workflow_id="workflow-a"
        ) == b"audited"
        store.delete_bytes(ref, tenant_id="tenant-a", workflow_id="workflow-a")

        events = trace.read_all()
        assert [event.event_type for event in events] == ["write", "read", "delete"]
        assert [event.outcome for event in events] == ["stored", "allowed", "tombstoned"]
        for event in events:
            assert event.key_id == "tenant-key"
            assert event.key_version == 1
            assert event.ref_digest == ref.digest
            assert event.locator == ref.locator

    def test_expired_payload_denies_read_before_decrypting(self, tmp_path) -> None:
        store, _, trace = _store(tmp_path)
        policy = RetentionPayloadPolicy(
            retention_mode=RetentionMode.RUN,
            max_retention_seconds=1,
        )
        assert validate_stored_byte_policy_schema(policy) == []
        ref = store.put_bytes(
            b"expires",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            retention_policy=policy,
            now_ns=1_000,
        )

        assert validate_durable_ref_byte_access_schema(ref) == []
        with pytest.raises(PayloadExpiredError):
            store.read_bytes(
                ref,
                tenant_id="tenant-a",
                workflow_id="workflow-a",
                now_ns=1_000 + 2_000_000_000,
            )
        assert _stored_ciphertext_files(tmp_path)
        assert trace.read_all()[-1].event_type == "read"
        assert trace.read_all()[-1].outcome == "denied"
        assert trace.read_all()[-1].reason == "expired"

    def test_tombstone_deletes_bytes_and_blocks_later_reads(self, tmp_path) -> None:
        store, _, trace = _store(tmp_path)
        ref = store.put_bytes(
            b"delete me",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )
        tombstoned_ref = store.delete_bytes(
            ref, tenant_id="tenant-a", workflow_id="workflow-a", now_ns=99
        )

        assert tombstoned_ref.tombstoned_at_ns == 99
        assert list((tmp_path / "payloads" / "objects").glob("*.bin")) == []
        assert validate_durable_ref_byte_access_schema(tombstoned_ref) == []
        with pytest.raises(PayloadTombstonedError):
            store.read_bytes(
                ref, tenant_id="tenant-a", workflow_id="workflow-a"
            )
        assert trace.read_all()[-1].event_type == "read"
        assert trace.read_all()[-1].outcome == "denied"
        assert trace.read_all()[-1].reason == "tombstoned"

    def test_metadata_valid_ref_without_bytes_is_not_sufficient(
        self, tmp_path
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

        assert validate_durable_ref(ref) == []
        assert validate_durable_ref_byte_access_schema(ref) == []
        with pytest.raises(PayloadTombstonedError):
            store.read_bytes(
                ref, tenant_id="tenant-a", workflow_id="workflow-a"
            )


class TestStoredByteMigrations:
    def test_interrupted_migration_recovers_from_written_bytes(self, tmp_path) -> None:
        store, _, _ = _store(tmp_path)
        migration = LedgerPayloadMigration(
            store,
            FileBackedPayloadMigrationLog(tmp_path / "migration-log"),
        )
        interrupted = migration.migrate_legacy_bytes(
            migration_id="migrate-1",
            legacy_id="legacy-1",
            data=b"legacy bytes",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            crash_after_write=True,
        )

        assert interrupted.status == MigrationStatus.PAYLOAD_WRITTEN
        assert interrupted.ref is not None
        assert b"legacy bytes" not in _stored_ciphertext_files(tmp_path)[0].read_bytes()
        recovered = migration.recover_interrupted()
        assert len(recovered) == 1
        assert recovered[0].status == MigrationStatus.COMPLETED
        assert recovered[0].ref is not None
        assert store.read_bytes(
            recovered[0].ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        ) == b"legacy bytes"

    def test_unbackfillable_legacy_history_cannot_be_read(self, tmp_path) -> None:
        store, _, _ = _store(tmp_path)
        migration = LedgerPayloadMigration(
            store,
            FileBackedPayloadMigrationLog(tmp_path / "migration-log"),
        )
        checkpoint = migration.mark_unbackfillable(
            migration_id="migrate-2",
            legacy_id="legacy-missing",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            reason="legacy sidecar contained digest only",
        )

        assert checkpoint.status == MigrationStatus.UNBACKFILLABLE
        assert checkpoint.ref is not None
        assert validate_durable_ref(checkpoint.ref) == []
        assert validate_durable_ref_byte_access_schema(checkpoint.ref) == []
        with pytest.raises(LegacyHistoryUnbackfillableError):
            assert_legacy_ref_readable(checkpoint.ref)
        with pytest.raises(LegacyHistoryUnbackfillableError):
            store.read_bytes(
                checkpoint.ref,
                tenant_id="tenant-a",
                workflow_id="workflow-a",
            )


class TestOutboxAndSchemaValidation:
    def test_outbox_is_idempotent_recovery_evidence_only(self, tmp_path) -> None:
        store, _, _ = _store(tmp_path)
        ref = store.put_bytes(
            b"publish",
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )
        outbox = FileBackedLedgerOutbox(tmp_path / "outbox.jsonl")

        first = outbox.enqueue(
            target="projection-rebuild",
            ref=ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            idempotency_key="publish-1",
        )
        second = outbox.enqueue(
            target="projection-rebuild",
            ref=ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
            idempotency_key="publish-1",
        )
        delivered = outbox.mark(first.record_id, OutboxStatus.DELIVERED)

        assert first.record_id == second.record_id
        assert delivered.status == OutboxStatus.DELIVERED
        assert outbox.pending() == []
        assert store.read_bytes(
            first.ref,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        ) == b"publish"

    def test_metadata_validation_remains_schema_only(self) -> None:
        policy = RetentionPayloadPolicy()
        assert validate_stored_byte_policy_schema(policy) == []

        ref = DurableRef(
            store_id="store",
            locator="locator",
            digest="sha256:" + "1" * 64,
            encryption_scope=EncryptionScope.TENANT_KEY,
            tenant_id="tenant-a",
            workflow_id="workflow-a",
        )
        assert validate_durable_ref_byte_access_schema(ref) == [
            "Encrypted DurableRef requires key_id and key_version metadata"
        ]
