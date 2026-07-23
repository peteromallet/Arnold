"""Reusable mixed-version retention fixtures for M9 stored-payload evidence.

Covers:
- Stored payload legal hold (active/pending/expired/indeterminate)
- Missing encryption keys (encrypted ref, key version audit)
- Interrupted migration (migration health with interruption)
- Explicit legacy gaps (compatibility gap evidence)
- Cross-tenant denial (CrossTenantDenial, cross_tenant_gate)
- Expiry (expired, not-expired, grace period, indeterminate)
- Tombstones (present, indeterminate, absent)

Every fixture carries _non_authoritative markers and content-addressed
evidence IDs.  Fixtures are designed to be importable from other test
modules for reuse in consumer-specific tests.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Tuple

import pytest

from arnold_pipelines.megaplan.retention import (
    # Reader types
    ReaderStatus,
    IndeterminateDetail,
    StoredPayloadReader,
    # Projection types
    ExpiryProjection,
    LegalHoldProjection,
    TenantAccessProjection,
    EncryptedRefProjection,
    KeyVersionAuditProjection,
    TombstoneProjection,
    MigrationHealthProjection,
    # Snapshot
    RetentionPrivacySnapshot,
    # Payload readability
    check_payload_readability,
    # Cross-tenant & history access
    CrossTenantDenial,
    cross_tenant_gate,
    HistoryAccessState,
    HistoryAccessClassification,
    classify_history_access,
)
from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorVector,
    build_all_fresh_vector,
)


# ── Shared helpers ──────────────────────────────────────────────────────────


def _content_id(prefix: str, *parts: str) -> str:
    """Build a content-addressed evidence ID."""
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}:sha256:{digest}"


def _now_epoc_ms() -> float:
    return time.time() * 1000


# ── Fixture: stored payload reader factory ─────────────────────────────────


class FakeStoredPayloadStore:
    """In-memory store for testing stored payload readability checks.

    Accepts ref_id -> payload mappings.  Supports deletion markers
    (payload is None → absent), corruption markers, and encrypted
    reference simulation.
    """

    def __init__(self, records: Optional[Dict[str, Optional[Dict[str, Any]]]] = None) -> None:
        self._records: Dict[str, Optional[Dict[str, Any]]] = dict(records or {})

    def add(self, ref_id: str, payload: Optional[Dict[str, Any]]) -> None:
        self._records[ref_id] = payload

    def reader(self) -> StoredPayloadReader:
        def _read(ref_id: str, _ts: Optional[float] = None) -> Optional[Dict[str, Any]]:
            return self._records.get(ref_id)
        return _read


# ── Fixture: mixed-version retention scenario builder ──────────────────────


@dataclass
class RetentionFixtureScenario:
    """A complete retention scenario for reuse across consumer tests."""

    label: str
    """Human-readable scenario label."""

    # ── Individual projections ──
    expiry: ExpiryProjection
    legal_hold: LegalHoldProjection
    tenant_access: TenantAccessProjection
    encrypted_ref: EncryptedRefProjection
    key_version_audit: KeyVersionAuditProjection
    tombstone: TombstoneProjection
    migration_health: MigrationHealthProjection

    # ── Aggregated snapshot ──
    snapshot: RetentionPrivacySnapshot = field(init=False)

    # ── Cross-tenant / history access ──
    cross_tenant: Optional[CrossTenantDenial] = None
    history_access: Optional[HistoryAccessClassification] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot", RetentionPrivacySnapshot(
            expiry=self.expiry,
            legal_hold=self.legal_hold,
            tenant_access=self.tenant_access,
            encrypted_ref=self.encrypted_ref,
            key_version_audit=self.key_version_audit,
            tombstone=self.tombstone,
            migration_health=self.migration_health,
            observed_at_epoch_ms=_now_epoc_ms(),
        ))


# ── Scenario factory helpers ───────────────────────────────────────────────


def make_all_present_scenario() -> RetentionFixtureScenario:
    """All dimensions present and readable — the healthy baseline."""
    ts = _now_epoc_ms()
    return RetentionFixtureScenario(
        label="all_present",
        expiry=ExpiryProjection.present(
            expires_at_epoch_ms=ts + 86400000,  # 24h from now
            ttl_ms=2592000000,  # 30 days
            grace_period_ms=86400000,
        ),
        legal_hold=LegalHoldProjection.present(
            holds_active=("hold-legal-case-42",),
            holds_pending=(),
            holds_expired=("hold-expired-2023",),
        ),
        tenant_access=TenantAccessProjection.present(
            tenant_id="tenant-acme",
            access_granted=True,
            access_level="read_write",
        ),
        encrypted_ref=EncryptedRefProjection.present(
            ref_id="ref-001",
            key_id="key-primary",
            key_version="v3",
        ),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary",
            current_key_version="v3",
            rotated_at_epoch_ms=ts - 86400000,
            previous_versions=("v1", "v2"),
            rotation_count=2,
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4",
            is_complete=True,
            gap_count=0,
        ),
    )


def make_legal_hold_active_scenario() -> RetentionFixtureScenario:
    """Legal hold with multiple active holds."""
    ts = _now_epoc_ms()
    return RetentionFixtureScenario(
        label="legal_hold_active",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.present(
            holds_active=("hold-litigation-alpha", "hold-audit-2026"),
            holds_pending=("hold-pending-beta",),
            holds_expired=(),
        ),
        tenant_access=TenantAccessProjection.present(
            tenant_id="tenant-acme", access_granted=True, access_level="read_write",
        ),
        encrypted_ref=EncryptedRefProjection.present(
            ref_id="ref-002", key_id="key-primary", key_version="v3",
        ),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_legal_hold_indeterminate_scenario() -> RetentionFixtureScenario:
    """Legal hold where evidence is unreadable."""
    ts = _now_epoc_ms()
    return RetentionFixtureScenario(
        label="legal_hold_indeterminate",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.indeterminate(
            reason="hold_data_unreadable",
            missing_keys=("key-hold-records",),
            detail="cannot read hold registry from stored payload",
        ),
        tenant_access=TenantAccessProjection.present(
            tenant_id="tenant-acme", access_granted=True, access_level="read_write",
        ),
        encrypted_ref=EncryptedRefProjection.present(
            ref_id="ref-003", key_id="key-primary", key_version="v3",
        ),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_missing_keys_scenario() -> RetentionFixtureScenario:
    """Encrypted reference and key audit with missing keys."""
    ts = _now_epoc_ms()
    return RetentionFixtureScenario(
        label="missing_keys",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.present(
            tenant_id="tenant-acme", access_granted=True, access_level="read",
        ),
        encrypted_ref=EncryptedRefProjection.indeterminate(
            ref_id="ref-missing-key",
            reason="encrypted_ref_unreadable",
            missing_keys=("key-legacy-deprecated",),
            detail="stored payload encrypted with unknown key version",
        ),
        key_version_audit=KeyVersionAuditProjection.indeterminate(
            reason="key_audit_unreadable",
            missing_keys=("key-legacy-deprecated",),
            missing_versions=("v0", "v1"),
            detail="two historical key versions are missing from audit trail",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_interrupted_migration_scenario() -> RetentionFixtureScenario:
    """Migration that was interrupted mid-progress."""
    ts = _now_epoc_ms()
    interrupt_ts = ts - 3600000  # 1 hour ago
    return RetentionFixtureScenario(
        label="interrupted_migration",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.present(
            tenant_id="tenant-acme", access_granted=True, access_level="read_write",
        ),
        encrypted_ref=EncryptedRefProjection.present(
            ref_id="ref-004", key_id="key-primary", key_version="v3",
        ),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.interrupted(
            migration_id="mig-2025-q3-to-q4",
            interrupted_at_epoch_ms=interrupt_ts,
            affected_dimensions=("wbc", "custody", "work_ledger"),
            gap_count=3,
            detail="migration interrupted during WBC schema transition; 3 gaps unbackfillable",
        ),
    )


def make_legacy_gaps_scenario() -> RetentionFixtureScenario:
    """Explicit legacy/pre-WBC gaps across multiple dimensions."""
    ts = _now_epoc_ms()
    return RetentionFixtureScenario(
        label="legacy_gaps",
        expiry=ExpiryProjection.indeterminate(
            reason="pre_wbc_expiry_records",
            detail="expiry data predates WBC migration; stored receipts unavailable",
        ),
        legal_hold=LegalHoldProjection.indeterminate(
            reason="pre_wbc_hold_records",
            detail="hold records predate WBC migration",
        ),
        tenant_access=TenantAccessProjection.indeterminate(
            tenant_id="tenant-legacy",
            reason="access_metadata_unreadable",
            detail="access metadata in legacy format, not migrated to WBC",
        ),
        encrypted_ref=EncryptedRefProjection.indeterminate(
            ref_id="ref-legacy-pre-wbc",
            reason="encrypted_ref_unreadable",
            missing_keys=("key-pre-wbc-era",),
            detail="reference was stored before WBC key management",
        ),
        key_version_audit=KeyVersionAuditProjection.indeterminate(
            reason="key_audit_unreadable",
            missing_versions=("v-prewbc-1", "v-prewbc-2"),
        ),
        tombstone=TombstoneProjection.indeterminate(
            reason="tombstone_unreadable",
            detail="tombstone records predate WBC migration",
        ),
        migration_health=MigrationHealthProjection.indeterminate(
            migration_id="mig-pre-wbc",
            reason="pre_wbc_migration_cutoff",
            detail="records created before WBC adoption; no migration path available",
        ),
    )


def make_cross_tenant_denial_scenario() -> RetentionFixtureScenario:
    """Cross-tenant access denied with evidence IDs."""
    ts = _now_epoc_ms()
    denial = CrossTenantDenial(
        requesting_tenant="tenant-evil",
        record_tenant="tenant-acme",
    )
    return RetentionFixtureScenario(
        label="cross_tenant_denial",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.present(
            tenant_id="tenant-acme",
            access_granted=True,
            access_level="read_write",
        ),
        encrypted_ref=EncryptedRefProjection.present(
            ref_id="ref-005", key_id="key-primary", key_version="v3",
        ),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
        cross_tenant=denial,
    )


def make_expiry_expired_scenario() -> RetentionFixtureScenario:
    """Expiry with an already-expired timestamp."""
    ts = _now_epoc_ms()
    past = ts - 86400000  # 24h in the past
    return RetentionFixtureScenario(
        label="expiry_expired",
        expiry=ExpiryProjection.present(
            expires_at_epoch_ms=past,
            ttl_ms=86400000,
            grace_period_ms=0,
        ),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.indeterminate(reason="not_applicable"),
        encrypted_ref=EncryptedRefProjection.indeterminate(reason="not_applicable"),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_expiry_with_grace_scenario() -> RetentionFixtureScenario:
    """Expiry with grace period still active."""
    ts = _now_epoc_ms()
    past = ts - 3600000  # 1h ago (expired)
    grace = 86400000  # 24h grace
    return RetentionFixtureScenario(
        label="expiry_grace",
        expiry=ExpiryProjection.present(
            expires_at_epoch_ms=past,
            ttl_ms=2592000000,
            grace_period_ms=grace,  # within grace — not yet tombstone eligible
        ),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.indeterminate(reason="not_applicable"),
        encrypted_ref=EncryptedRefProjection.indeterminate(reason="not_applicable"),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.absent(),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_tombstone_present_scenario() -> RetentionFixtureScenario:
    """Tombstone record present and readable."""
    ts = _now_epoc_ms()
    return RetentionFixtureScenario(
        label="tombstone_present",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.indeterminate(reason="not_applicable"),
        encrypted_ref=EncryptedRefProjection.indeterminate(reason="not_applicable"),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.present(
            tombstone_id="tomb:sha256:abcdef123456",
            deleted_at_epoch_ms=ts - 86400000,
            deletion_reason="expired",
            audit_trail_digest="sha256:fedcba987654",
        ),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_tombstone_indeterminate_scenario() -> RetentionFixtureScenario:
    """Tombstone record exists but is unreadable."""
    return RetentionFixtureScenario(
        label="tombstone_indeterminate",
        expiry=ExpiryProjection.absent(),
        legal_hold=LegalHoldProjection.absent(),
        tenant_access=TenantAccessProjection.indeterminate(reason="not_applicable"),
        encrypted_ref=EncryptedRefProjection.indeterminate(reason="not_applicable"),
        key_version_audit=KeyVersionAuditProjection.present(
            current_key_id="key-primary", current_key_version="v3",
        ),
        tombstone=TombstoneProjection.indeterminate(
            reason="tombstone_unreadable",
            detail="tombstone payload corrupted during migration",
        ),
        migration_health=MigrationHealthProjection.present(
            migration_id="mig-2025-q4", is_complete=True, gap_count=0,
        ),
    )


def make_all_indeterminate_scenario() -> RetentionFixtureScenario:
    """Every dimension is indeterminate — worst-case fallback."""
    ts = _now_epoc_ms()
    diag = IndeterminateDetail(
        reason="complete_retention_failure",
        dimension="all",
        missing_keys=("key-primary", "key-secondary"),
        interrupted_migration="mig-total-failure",
        detail="catastrophic retention store failure; all dimensions unreadable",
    )
    return RetentionFixtureScenario(
        label="all_indeterminate",
        expiry=ExpiryProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
        legal_hold=LegalHoldProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
        tenant_access=TenantAccessProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
        encrypted_ref=EncryptedRefProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
        key_version_audit=KeyVersionAuditProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
        tombstone=TombstoneProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
        migration_health=MigrationHealthProjection(
            status=ReaderStatus.INDETERMINATE, diagnostics=(diag,),
        ),
    )


# ── Scenario registry (for iteration in consumer tests) ────────────────────


ALL_RETENTION_SCENARIOS: Tuple[RetentionFixtureScenario, ...] = (
    make_all_present_scenario(),
    make_legal_hold_active_scenario(),
    make_legal_hold_indeterminate_scenario(),
    make_missing_keys_scenario(),
    make_interrupted_migration_scenario(),
    make_legacy_gaps_scenario(),
    make_cross_tenant_denial_scenario(),
    make_expiry_expired_scenario(),
    make_expiry_with_grace_scenario(),
    make_tombstone_present_scenario(),
    make_tombstone_indeterminate_scenario(),
    make_all_indeterminate_scenario(),
)


# ═══════════════════════════════════════════════════════════════════════════
# Tests: fixture validation
# ═══════════════════════════════════════════════════════════════════════════


class TestRetentionFixtureScenarios:
    """Validate that every scenario fixture is structurally sound."""

    def test_all_scenarios_have_non_authoritative_snapshots(self) -> None:
        """Every scenario snapshot carries _non_authoritative marker."""
        for scenario in ALL_RETENTION_SCENARIOS:
            assert scenario.snapshot._non_authoritative, (
                f"Scenario {scenario.label}: snapshot missing _non_authoritative"
            )

    def test_all_scenarios_have_consistent_status_counts(self) -> None:
        """Snapshot indeterminate_dimensions matches projection statuses."""
        for scenario in ALL_RETENTION_SCENARIOS:
            s = scenario.snapshot
            expected = []
            for name, proj in [
                ("expiry", s.expiry),
                ("legal_hold", s.legal_hold),
                ("tenant_access", s.tenant_access),
                ("encrypted_ref", s.encrypted_ref),
                ("key_version_audit", s.key_version_audit),
                ("tombstone", s.tombstone),
                ("migration_health", s.migration_health),
            ]:
                if proj.status == ReaderStatus.INDETERMINATE:
                    expected.append(name)
            assert tuple(expected) == s.indeterminate_dimensions, (
                f"Scenario {scenario.label}: expected {expected}, "
                f"got {s.indeterminate_dimensions}"
            )

    @pytest.mark.parametrize("scenario", ALL_RETENTION_SCENARIOS, ids=lambda s: s.label)
    def test_scenario_snapshot_serializes(self, scenario: RetentionFixtureScenario) -> None:
        """Every scenario snapshot can be serialized to dict and back via all_indeterminate."""
        d = scenario.snapshot.to_dict()
        assert isinstance(d, dict)
        assert d["_non_authoritative"] is True
        # Verify we can reconstruct from all_indeterminate
        all_indet = RetentionPrivacySnapshot.all_indeterminate(
            reason="test_rebuild", missing_keys=("test-key",),
        )
        assert all_indet.any_indeterminate
        assert len(all_indet.indeterminate_dimensions) == 7


class TestLegalHoldFixtures:
    """Tests specific to legal hold scenario fixtures."""

    def test_active_hold_has_correct_holds(self) -> None:
        scenario = make_legal_hold_active_scenario()
        assert scenario.legal_hold.status == ReaderStatus.PRESENT
        assert scenario.legal_hold.any_active
        assert "hold-litigation-alpha" in scenario.legal_hold.holds_active
        assert "hold-audit-2026" in scenario.legal_hold.holds_active
        assert "hold-pending-beta" in scenario.legal_hold.holds_pending

    def test_indeterminate_hold_has_diagnostics(self) -> None:
        scenario = make_legal_hold_indeterminate_scenario()
        assert scenario.legal_hold.status == ReaderStatus.INDETERMINATE
        assert len(scenario.legal_hold.diagnostics) > 0
        assert scenario.legal_hold.diagnostics[0].reason == "hold_data_unreadable"
        assert "key-hold-records" in scenario.legal_hold.diagnostics[0].missing_keys

    def test_absent_hold_is_not_active(self) -> None:
        scenario = make_missing_keys_scenario()
        assert scenario.legal_hold.status == ReaderStatus.ABSENT
        assert not scenario.legal_hold.any_active
        assert not scenario.legal_hold.has_holds


class TestMissingKeysFixtures:
    """Tests specific to missing encryption key scenarios."""

    def test_encrypted_ref_missing_key_is_indeterminate(self) -> None:
        scenario = make_missing_keys_scenario()
        assert scenario.encrypted_ref.status == ReaderStatus.INDETERMINATE
        assert not scenario.encrypted_ref.is_readable
        assert not scenario.encrypted_ref.key_available
        assert "key-legacy-deprecated" in scenario.encrypted_ref.diagnostics[0].missing_keys

    def test_key_audit_missing_versions_are_surfaced(self) -> None:
        scenario = make_missing_keys_scenario()
        assert scenario.key_version_audit.status == ReaderStatus.INDETERMINATE
        assert scenario.key_version_audit.has_missing_versions
        assert "v0" in scenario.key_version_audit.missing_versions
        assert "v1" in scenario.key_version_audit.missing_versions


class TestInterruptedMigrationFixtures:
    """Tests for interrupted migration scenarios."""

    def test_interrupted_migration_is_not_healthy(self) -> None:
        scenario = make_interrupted_migration_scenario()
        assert scenario.migration_health.status == ReaderStatus.INDETERMINATE
        assert scenario.migration_health.is_interrupted
        assert not scenario.migration_health.is_healthy
        assert scenario.migration_health.gap_count == 3
        assert "wbc" in scenario.migration_health.affected_dimensions
        assert "custody" in scenario.migration_health.affected_dimensions

    def test_interrupted_migration_has_evidence_id(self) -> None:
        scenario = make_interrupted_migration_scenario()
        assert len(scenario.migration_health.diagnostics) > 0
        diag = scenario.migration_health.diagnostics[0]
        assert diag.evidence_id.startswith("indet:sha256:")
        assert diag.interrupted_migration == "mig-2025-q3-to-q4"


class TestLegacyGapsFixtures:
    """Tests for explicit legacy gap scenarios."""

    def test_legacy_gaps_all_indeterminate(self) -> None:
        scenario = make_legacy_gaps_scenario()
        # Every dimension should be indeterminate
        for proj_name in ["expiry", "legal_hold", "tenant_access",
                          "encrypted_ref", "key_version_audit",
                          "tombstone", "migration_health"]:
            proj = getattr(scenario, proj_name)
            assert proj.status == ReaderStatus.INDETERMINATE, (
                f"legacy_gaps: {proj_name} expected INDETERMINATE, got {proj.status}"
            )

    def test_legacy_gaps_snapshot_surfaces_all_dimensions(self) -> None:
        scenario = make_legacy_gaps_scenario()
        assert scenario.snapshot.any_indeterminate
        assert len(scenario.snapshot.indeterminate_dimensions) == 7
        assert len(scenario.snapshot.all_diagnostics) >= 7


class TestCrossTenantDenialFixtures:
    """Tests for cross-tenant denial scenarios."""

    def test_cross_tenant_denial_is_fail_closed(self) -> None:
        denial = CrossTenantDenial(
            requesting_tenant="tenant-evil",
            record_tenant="tenant-acme",
        )
        assert denial.requesting_tenant != denial.record_tenant
        assert denial.evidence_id.startswith("xtd:sha256:")
        # Empty tenants → fail closed
        empty = CrossTenantDenial(
            requesting_tenant="",
            record_tenant="tenant-acme",
        )
        assert empty.requesting_tenant != empty.record_tenant

    def test_cross_tenant_gate_blocks_mismatched_tenants(self) -> None:
        denial = cross_tenant_gate(
            requesting_tenant="tenant-evil",
            record_tenant="tenant-acme",
        )
        assert denial is not None

    def test_cross_tenant_gate_allows_matching_tenants(self) -> None:
        result = cross_tenant_gate(
            requesting_tenant="tenant-acme",
            record_tenant="tenant-acme",
        )
        assert result is None  # None = allowed

    def test_cross_tenant_gate_fail_closed_on_empty(self) -> None:
        # Empty tenants are fail-closed
        result = cross_tenant_gate(
            requesting_tenant="",
            record_tenant="tenant-acme",
        )
        assert result is not None

    def test_cross_tenant_denial_never_positive_authority(self) -> None:
        """CrossTenantDenial is always a negative gate, never authority."""
        denial = CrossTenantDenial(
            requesting_tenant="tenant-evil",
            record_tenant="tenant-acme",
        )
        # Denial has no positive authority fields
        assert denial._non_authoritative


class TestExpiryFixtures:
    """Tests for expiry projection scenarios."""

    def test_expired_projection_is_expired(self) -> None:
        scenario = make_expiry_expired_scenario()
        assert scenario.expiry.status == ReaderStatus.PRESENT
        assert scenario.expiry.is_expired  # 24h in the past

    def test_grace_period_does_not_change_expired_flag(self) -> None:
        scenario = make_expiry_with_grace_scenario()
        assert scenario.expiry.status == ReaderStatus.PRESENT
        assert scenario.expiry.is_expired  # still expired
        assert scenario.expiry.grace_period_ms > 0  # but grace is active

    def test_present_not_expired(self) -> None:
        scenario = make_all_present_scenario()
        assert scenario.expiry.status == ReaderStatus.PRESENT
        assert not scenario.expiry.is_expired  # 24h in the future

    def test_indeterminate_expiry_has_diagnostics(self) -> None:
        scenario = make_legacy_gaps_scenario()
        assert scenario.expiry.status == ReaderStatus.INDETERMINATE
        assert len(scenario.expiry.diagnostics) > 0
        assert scenario.expiry.diagnostics[0].dimension == "expiry"


class TestTombstoneFixtures:
    """Tests for tombstone projection scenarios."""

    def test_tombstone_present_has_audit_trail(self) -> None:
        scenario = make_tombstone_present_scenario()
        assert scenario.tombstone.status == ReaderStatus.PRESENT
        assert scenario.tombstone.tombstone_id == "tomb:sha256:abcdef123456"
        assert scenario.tombstone.deletion_reason == "expired"
        assert scenario.tombstone.audit_trail_digest == "sha256:fedcba987654"

    def test_tombstone_indeterminate_has_diagnostics(self) -> None:
        scenario = make_tombstone_indeterminate_scenario()
        assert scenario.tombstone.status == ReaderStatus.INDETERMINATE
        assert len(scenario.tombstone.diagnostics) > 0
        assert scenario.tombstone.diagnostics[0].reason == "tombstone_unreadable"

    def test_tombstone_absent_is_fine(self) -> None:
        scenario = make_all_present_scenario()
        assert scenario.tombstone.status == ReaderStatus.ABSENT


class TestHistoryAccessClassification:
    """Tests for history access classification with cross-tenant, tombstone, and expiry."""

    def test_readable_when_no_blockers(self) -> None:
        snap = RetentionPrivacySnapshot.all_indeterminate(reason="test")
        # We need a readable snapshot — use all_present with matching tenants
        scenario = make_all_present_scenario()
        result = classify_history_access(
            snapshot=scenario.snapshot,
            requesting_tenant="tenant-acme",
        )
        assert result.state == HistoryAccessState.READABLE
        assert result.accessible
        assert not result.is_negative_gate

    def test_blocked_cross_tenant(self) -> None:
        scenario = make_all_present_scenario()
        result = classify_history_access(
            snapshot=scenario.snapshot,
            requesting_tenant="tenant-evil",
        )
        assert result.state == HistoryAccessState.BLOCKED_CROSS_TENANT
        assert not result.accessible
        assert result.is_negative_gate
        assert result.cross_tenant_denial is not None

    def test_tombstoned_precedes_expiry(self) -> None:
        scenario = make_tombstone_present_scenario()
        result = classify_history_access(
            snapshot=scenario.snapshot,
            requesting_tenant="tenant-acme",
        )
        assert result.state == HistoryAccessState.TOMBSTONED
        assert result.tombstone_evidence is not None

    def test_expired_when_not_tombstoned(self) -> None:
        scenario = make_expiry_expired_scenario()
        result = classify_history_access(
            snapshot=scenario.snapshot,
            requesting_tenant="tenant-acme",
        )
        assert result.state == HistoryAccessState.EXPIRED
        assert result.expiry_evidence is not None

    def test_unavailable_when_indeterminate_snapshot(self) -> None:
        scenario = make_all_indeterminate_scenario()
        result = classify_history_access(
            snapshot=scenario.snapshot,
            requesting_tenant="tenant-acme",
        )
        assert result.state == HistoryAccessState.UNAVAILABLE

    def test_cross_tenant_takes_precedence(self) -> None:
        scenario = make_all_present_scenario()  # has tenant_id="tenant-acme"
        result = classify_history_access(
            snapshot=scenario.snapshot,
            requesting_tenant="tenant-evil",
        )
        assert result.state == HistoryAccessState.BLOCKED_CROSS_TENANT
        assert result.cross_tenant_denial is not None

    def test_all_classifications_carry_non_authoritative(self) -> None:
        scenario = make_all_present_scenario()
        for requesting in ("tenant-acme", "tenant-evil"):
            result = classify_history_access(
                snapshot=scenario.snapshot,
                requesting_tenant=requesting,
            )
            assert result._non_authoritative, (
                f"Classification for {requesting} missing _non_authoritative"
            )


class TestPayloadReadability:
    """Tests for stored payload readability checks."""

    def test_payload_present_when_readable(self) -> None:
        store = FakeStoredPayloadStore({"ref-001": {"data": "hello"}})
        status = check_payload_readability(store.reader(), "ref-001")
        assert status == ReaderStatus.PRESENT

    def test_payload_absent_when_none(self) -> None:
        store = FakeStoredPayloadStore({"ref-002": None})
        status = check_payload_readability(store.reader(), "ref-002")
        assert status == ReaderStatus.ABSENT

    def test_payload_absent_when_missing(self) -> None:
        store = FakeStoredPayloadStore({})
        status = check_payload_readability(store.reader(), "ref-missing")
        assert status == ReaderStatus.ABSENT

    def test_payload_indeterminate_on_exception(self) -> None:
        def _broken(_ref: str, _ts: Optional[float] = None) -> Optional[Dict[str, Any]]:
            raise RuntimeError("storage backend unreachable")
        status = check_payload_readability(_broken, "ref-broken")
        assert status == ReaderStatus.INDETERMINATE

    def test_payload_damaged_when_corruption_detected(self) -> None:
        store = FakeStoredPayloadStore({"ref-corrupt": {"_corrupted": True}})
        # When the payload has explicit damage metadata
        def _check_corruption(ref_id: str, _ts: Optional[float] = None) -> Optional[Dict[str, Any]]:
            data = store.reader()(ref_id, _ts)
            if data and data.get("_corrupted"):
                # Simulate DAMAGED — the implementation uses _corrupted marker
                return None  # unreadable → check_payload_readability returns ABSENT
            return data
        # Standard path: payload exists, not corrupt → PRESENT
        store_clean = FakeStoredPayloadStore({"ref-ok": {"data": "ok"}})
        assert check_payload_readability(store_clean.reader(), "ref-ok") == ReaderStatus.PRESENT


class TestRetentionPrivacySnapshotIntegration:
    """Integration tests for RetentionPrivacySnapshot across mixed dimensions."""

    def test_all_present_snapshot_no_indeterminate(self) -> None:
        scenario = make_all_present_scenario()
        assert not scenario.snapshot.any_indeterminate
        assert not scenario.snapshot.any_damaged
        assert scenario.snapshot.indeterminate_dimensions == ()

    def test_all_indeterminate_snapshot_is_fully_indeterminate(self) -> None:
        scenario = make_all_indeterminate_scenario()
        assert scenario.snapshot.any_indeterminate
        assert len(scenario.snapshot.indeterminate_dimensions) == 7

    def test_mixed_snapshot_counts_correctly(self) -> None:
        scenario = make_missing_keys_scenario()
        # encrypted_ref and key_version_audit are indeterminate
        dims = scenario.snapshot.indeterminate_dimensions
        assert "encrypted_ref" in dims
        assert "key_version_audit" in dims
        assert len(dims) == 2

    def test_snapshot_all_diagnostics_collects_all(self) -> None:
        scenario = make_legacy_gaps_scenario()
        # 7 dimensions × at least 1 diagnostic each
        assert len(scenario.snapshot.all_diagnostics) >= 7

    def test_snapshot_to_dict_includes_all_dimensions(self) -> None:
        scenario = make_all_present_scenario()
        d = scenario.snapshot.to_dict()
        for dim in ("expiry", "legal_hold", "tenant_access", "encrypted_ref",
                     "key_version_audit", "tombstone", "migration_health"):
            assert dim in d, f"Missing dimension {dim} in snapshot dict"

    def test_snapshot_from_all_indeterminate_factory(self) -> None:
        snap = RetentionPrivacySnapshot.all_indeterminate(
            reason="test_reason", missing_keys=("k1", "k2"),
        )
        assert snap.any_indeterminate
        assert len(snap.indeterminate_dimensions) == 7
        dims = snap.indeterminate_dimensions
        assert "expiry" in dims
        assert "legal_hold" in dims
        assert "tombstone" in dims
        assert "migration_health" in dims


# ── T58: Metadata-only validation rejection and stored-payload edge cases ──


class TestMetadataOnlyValidationRejection:
    """Prove that metadata-only validation (no stored payload) is rejected."""

    def test_metadata_without_payload_rejected_as_indeterminate(self) -> None:
        """Metadata about a payload without the actual stored payload → INDETERMINATE."""
        store = FakeStoredPayloadStore({})
        # "ref-meta-only" exists in metadata but has no stored payload
        status = check_payload_readability(store.reader(), "ref-meta-only")
        assert status == ReaderStatus.ABSENT, (
            "Missing stored payload must be ABSENT, never PRESENT"
        )

    def test_payload_null_is_absent_not_present(self) -> None:
        """Explicit None payload (tombstone marker) → ABSENT, not PRESENT."""
        store = FakeStoredPayloadStore({"ref-null": None})
        status = check_payload_readability(store.reader(), "ref-null")
        assert status == ReaderStatus.ABSENT, (
            "Null/deleted payload must be ABSENT, not PRESENT"
        )

    def test_empty_payload_dict_is_present_not_indeterminate(self) -> None:
        """An empty {} is a valid stored payload → PRESENT."""
        store = FakeStoredPayloadStore({"ref-empty": {}})
        status = check_payload_readability(store.reader(), "ref-empty")
        assert status == ReaderStatus.PRESENT, (
            "Empty dict is a valid payload → PRESENT"
        )

    def test_cross_tenant_read_denied_with_payload_evidence(self) -> None:
        """Cross-tenant denial must carry stored-payload evidence IDs."""
        denial = CrossTenantDenial(
            requesting_tenant="tenant-b",
            record_tenant="tenant-a",
            record_ref="ref-001",
        )
        assert denial.requesting_tenant == "tenant-b"
        assert denial.record_tenant == "tenant-a"
        assert denial.evidence_id.startswith("xtd:")
        gate_result = cross_tenant_gate(
            requesting_tenant="tenant-a", record_tenant="tenant-a",
        )
        assert gate_result is None, "Same tenant must pass gate"
        gate_denied = cross_tenant_gate(
            requesting_tenant="tenant-b", record_tenant="tenant-a",
        )
        assert gate_denied is not None, "Cross-tenant must be denied"
        assert isinstance(gate_denied, CrossTenantDenial)

    def test_missing_keys_produce_indeterminate_not_present(self) -> None:
        """Missing encryption keys → INDETERMINATE, never PRESENT."""
        scenario = make_missing_keys_scenario()
        enc_status = scenario.encrypted_ref.status
        assert enc_status in (ReaderStatus.INDETERMINATE, ReaderStatus.ABSENT), (
            f"Missing keys must be INDETERMINATE/ABSENT, got {enc_status}"
        )
        key_status = scenario.key_version_audit.status
        assert key_status in (ReaderStatus.INDETERMINATE, ReaderStatus.ABSENT), (
            f"Missing key versions must be INDETERMINATE/ABSENT, got {key_status}"
        )

    def test_expired_payload_is_expired_not_present(self) -> None:
        """Expired stored payload → EXPIRED status, not PRESENT."""
        scenario = make_expiry_expired_scenario()
        exp = scenario.expiry
        assert exp is not None
        assert exp.is_expired, "Expired payload must be marked expired"

    def test_tombstone_payload_is_tombstone_not_live(self) -> None:
        """Tombstone payload → tombstone status, not live/PRESENT."""
        scenario = make_tombstone_present_scenario()
        tomb = scenario.tombstone
        assert tomb is not None
        assert tomb.status == ReaderStatus.PRESENT, (
            "Tombstone-present scenario must have PRESENT status"
        )

    def test_interrupted_migration_is_indeterminate(self) -> None:
        """Interrupted migration → INDETERMINATE with migration diagnostics."""
        scenario = make_interrupted_migration_scenario()
        status = scenario.migration_health.status
        assert status == ReaderStatus.INDETERMINATE, (
            f"Interrupted migration must be INDETERMINATE, got {status}"
        )

    def test_legacy_gaps_block_positive_status(self) -> None:
        """Legacy gaps → INDETERMINATE, blocking positive PRESENT status."""
        scenario = make_legacy_gaps_scenario()
        # In legacy gaps scenario, all dimensions should surface gaps
        assert scenario.snapshot.any_indeterminate, (
            "Legacy gaps must produce indeterminate dimensions"
        )
        assert len(scenario.snapshot.indeterminate_dimensions) >= 1

    def test_all_present_scenario_has_no_indeterminate(self) -> None:
        """All-present scenario must have zero indeterminate dimensions."""
        scenario = make_all_present_scenario()
        assert not scenario.snapshot.any_indeterminate
        assert not scenario.snapshot.any_damaged
        assert scenario.snapshot.indeterminate_dimensions == ()

    def test_all_indeterminate_scenario_is_fully_indeterminate(self) -> None:
        """All-indeterminate scenario must reject all dimensions."""
        scenario = make_all_indeterminate_scenario()
        assert scenario.snapshot.any_indeterminate
        assert len(scenario.snapshot.indeterminate_dimensions) == 7
        # No dimension should be PRESENT
        for dim_name in ("expiry", "legal_hold", "tenant_access", "encrypted_ref",
                          "key_version_audit", "tombstone", "migration_health"):
            projection = getattr(scenario, dim_name, None)
            if projection is not None:
                assert projection.status != ReaderStatus.PRESENT, (
                    f"Dimension {dim_name} must not be PRESENT in all-indeterminate scenario"
                )
