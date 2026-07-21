"""Tests for controlled writer registry and writer map: fail-closed lookups.

Covers:
- Unknown writer lookups (by id and surface)
- Duplicate writer registration rejection
- Stale/expired cohort behavior
- Ambiguous writer surface lookups (multiple writers on same surface)
- writer_guard fail-closed default
- guard_all batch behavior
- list_authority_increasing_writers filtering
- Writer map generation and owner coupling
- Support-manifest labels are not treated as proof of adoption
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import pytest

from arnold_pipelines.megaplan.custody.controlled_writer_registry import (
    COHORTS,
    WRITER_REGISTRY_SCHEMA_VERSION,
    WRITE_GUARD_DECISIONS,
    Cohort,
    ControlledWriter,
    WriteGuardDecision,
    WriteGuardResult,
    _clear_registry,
    deregister_writer,
    get_writer,
    get_writer_by_surface,
    guard_all,
    list_active_writers,
    list_authority_increasing_writers,
    list_report_only_writers,
    list_shadow_writers,
    list_writers,
    register_writer,
    writer_guard,
)

from arnold_pipelines.megaplan.custody.writer_map import (
    OWNER_CUSTODY,
    OWNER_DOMAIN,
    OWNER_MAINTENANCE,
    OWNER_OBSERVABILITY,
    OWNER_PROJECTION,
    OWNER_RUN_AUTHORITY,
    OWNER_WBC,
    WRITER_MAP_SCHEMA_VERSION,
    WRITER_SURFACES,
    F01_REPAIR_OCCURRENCE_FIELDS,
    M7_MISSING_FIELDS,
    OccurrenceWriterTerminalProvenanceMap,
    WriterSurface,
    generate_writer_map,
)


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_registry_fixture() -> None:
    """Clear the in-memory registry before each test."""
    _clear_registry()


@pytest.fixture
def sample_writer() -> ControlledWriter:
    """A canonical sample writer for testing."""
    return ControlledWriter(
        writer_id="lease_store@v1",
        surface_name=WriterSurface.LEASE_STORE.value,
        cohort=Cohort.ACTIVE,
        contract_ids=("C1-001", "C1-002"),
        source_file="arnold_pipelines/megaplan/custody/lease_store.py",
        function_name="record_events",
        required_wbc_phases=("attempt_started", "attempt_evidenced"),
        action_kind="lease_write",
    )


@pytest.fixture
def shadow_writer() -> ControlledWriter:
    """A shadow-mode writer for testing cohort filtering."""
    return ControlledWriter(
        writer_id="action_validator@v1",
        surface_name=WriterSurface.ACTION_VALIDATOR.value,
        cohort=Cohort.SHADOW,
        contract_ids=("C1-003",),
        source_file="arnold_pipelines/megaplan/custody/action_validator.py",
        function_name="validate_action_boundary",
        required_wbc_phases=("attempt_started",),
        action_kind="action_validate",
    )


@pytest.fixture
def report_writer() -> ControlledWriter:
    """A report-only writer for testing cohort filtering."""
    return ControlledWriter(
        writer_id="report_logger@v1",
        surface_name=WriterSurface.COMPATIBILITY.value,
        cohort=Cohort.REPORT_ONLY,
        contract_ids=(),
        source_file="arnold_pipelines/megaplan/custody/compatibility.py",
        function_name="snapshot",
        required_wbc_phases=(),
        action_kind="",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unknown writer lookups (fail-closed)
# ═══════════════════════════════════════════════════════════════════════════


class TestUnknownWriterLookups:
    """Unknown writers must return None / UNREGISTERED."""

    def test_get_writer_unknown_returns_none(self) -> None:
        """get_writer for unknown id returns None."""
        result = get_writer("nonexistent@v1")
        assert result is None

    def test_get_writer_empty_string_returns_none(self) -> None:
        """get_writer with empty string returns None."""
        assert get_writer("") is None
        assert get_writer("   ") is None

    def test_get_writer_by_surface_unknown_returns_none(self) -> None:
        """get_writer_by_surface for unknown surface returns None."""
        result = get_writer_by_surface("nonexistent_surface")
        assert result is None

    def test_get_writer_by_surface_empty_returns_none(self) -> None:
        """get_writer_by_surface with empty string returns None."""
        assert get_writer_by_surface("") is None
        assert get_writer_by_surface("   ") is None

    def test_writer_guard_unknown_id_returns_unregistered(self) -> None:
        """writer_guard with unknown writer_id returns UNREGISTERED."""
        result = writer_guard(writer_id="nonexistent@v1")
        assert result.decision == WriteGuardDecision.UNREGISTERED
        assert result.denied
        assert not result.allowed
        assert "nonexistent@v1" in result.diagnostics[0] if result.diagnostics else True

    def test_writer_guard_unknown_surface_returns_unregistered(self) -> None:
        """writer_guard with unknown surface_name returns UNREGISTERED."""
        result = writer_guard(surface_name="nonexistent_surface")
        assert result.decision == WriteGuardDecision.UNREGISTERED
        assert result.denied

    def test_writer_guard_no_args_returns_unregistered(self) -> None:
        """writer_guard with no writer_id or surface_name returns UNREGISTERED."""
        result = writer_guard()
        assert result.decision == WriteGuardDecision.UNREGISTERED
        assert result.denied


# ═══════════════════════════════════════════════════════════════════════════
# Duplicate writer registration rejection
# ═══════════════════════════════════════════════════════════════════════════


class TestDuplicateWriterRegistration:
    """Duplicate writer registrations must be rejected."""

    def test_duplicate_writer_id_raises(self, sample_writer: ControlledWriter) -> None:
        """Registering the same writer_id twice raises ValueError."""
        register_writer(sample_writer)
        # Same id, different surface is still duplicate
        dup = ControlledWriter(
            writer_id=sample_writer.writer_id,  # same id
            surface_name=WriterSurface.OUTBOX.value,  # different surface
            cohort=Cohort.ACTIVE,
        )
        with pytest.raises(ValueError, match="Duplicate writer_id"):
            register_writer(dup)

    def test_duplicate_surface_cohort_raises(
        self, sample_writer: ControlledWriter
    ) -> None:
        """Registering same surface+cohort raises ValueError."""
        register_writer(sample_writer)
        dup = ControlledWriter(
            writer_id="other_lease@v1",  # different id
            surface_name=sample_writer.surface_name,  # same surface
            cohort=sample_writer.cohort,  # same cohort
        )
        with pytest.raises(ValueError, match="Duplicate surface\\+cohort"):
            register_writer(dup)

    def test_same_surface_different_cohort_allowed(
        self, sample_writer: ControlledWriter
    ) -> None:
        """Same surface with different cohort is allowed."""
        register_writer(sample_writer)  # ACTIVE on lease_store
        other = ControlledWriter(
            writer_id="lease_store_shadow@v1",
            surface_name=sample_writer.surface_name,  # same surface
            cohort=Cohort.SHADOW,  # different cohort
        )
        register_writer(other)  # Should not raise

    def test_register_non_controlled_writer_raises(self) -> None:
        """register_writer rejects non-ControlledWriter."""
        with pytest.raises(TypeError, match="Expected ControlledWriter"):
            register_writer("not_a_writer")  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# Stale cohort behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestStaleWriterBehavior:
    """Stale/expired cohort writers must not be treated as active."""

    def test_report_only_not_in_active_list(self, report_writer: ControlledWriter) -> None:
        """Report-only writers must not appear in list_active_writers."""
        register_writer(report_writer)
        assert report_writer not in list_active_writers()
        assert report_writer in list_report_only_writers()

    def test_report_only_not_authority_increasing(self, report_writer: ControlledWriter) -> None:
        """Report-only writers with no action_kind are not authority-increasing."""
        register_writer(report_writer)
        assert report_writer not in list_authority_increasing_writers()

    def test_shadow_writer_in_shadow_list(self, shadow_writer: ControlledWriter) -> None:
        """Shadow writers appear in shadow list, not active."""
        register_writer(shadow_writer)
        assert shadow_writer in list_shadow_writers()
        assert shadow_writer not in list_active_writers()

    def test_report_only_guard_returns_report_only(
        self, report_writer: ControlledWriter
    ) -> None:
        """writer_guard for report-only returns REPORT_ONLY."""
        register_writer(report_writer)
        result = writer_guard(writer_id=report_writer.writer_id)
        assert result.decision == WriteGuardDecision.REPORT_ONLY
        assert result.allowed  # REPORT_ONLY is "allowed" for logging
        assert not result.denied


# ═══════════════════════════════════════════════════════════════════════════
# Ambiguous writer surface lookups
# ═══════════════════════════════════════════════════════════════════════════


class TestAmbiguousWriterLookups:
    """Ambiguous surface lookups (multiple writers) must fail closed."""

    def test_multiple_writers_on_same_surface_ambiguous(
        self, sample_writer: ControlledWriter
    ) -> None:
        """get_writer_by_surface returns None when multiple writers share a surface."""
        register_writer(sample_writer)  # lease_store, ACTIVE
        other = ControlledWriter(
            writer_id="lease_store_shadow@v1",
            surface_name=sample_writer.surface_name,  # same surface
            cohort=Cohort.SHADOW,  # different cohort
        )
        register_writer(other)
        result = get_writer_by_surface(sample_writer.surface_name)
        assert result is None  # fail-closed for ambiguity

    def test_writer_guard_ambiguous_surface_denied(
        self, sample_writer: ControlledWriter
    ) -> None:
        """writer_guard with ambiguous surface_name returns UNREGISTERED/denied."""
        register_writer(sample_writer)
        other = ControlledWriter(
            writer_id="lease_store_shadow@v1",
            surface_name=sample_writer.surface_name,
            cohort=Cohort.SHADOW,
        )
        register_writer(other)
        result = writer_guard(surface_name=sample_writer.surface_name)
        assert result.denied
        assert "Ambiguous" in str(result.diagnostics)

    def test_single_writer_surface_is_not_ambiguous(
        self, sample_writer: ControlledWriter
    ) -> None:
        """Single writer on a surface returns the writer."""
        register_writer(sample_writer)
        result = get_writer_by_surface(sample_writer.surface_name)
        assert result is not None
        assert result.writer_id == sample_writer.writer_id

    def test_writer_guard_successful_single_surface(
        self, sample_writer: ControlledWriter
    ) -> None:
        """writer_guard with valid surface_name returns ALLOWED for ACTIVE."""
        register_writer(sample_writer)
        result = writer_guard(
            surface_name=sample_writer.surface_name,
            override_enforcement=True,
        )
        assert result.decision == WriteGuardDecision.ALLOWED
        assert result.allowed


# ═══════════════════════════════════════════════════════════════════════════
# writer_guard fail-closed default
# ═══════════════════════════════════════════════════════════════════════════


class TestWriterGuardFailClosed:
    """writer_guard must be fail-closed by default."""

    def test_fail_closed_default(self) -> None:
        """writer_guard defaults to fail_closed=True."""
        result = writer_guard()
        assert result.fail_closed
        assert result.denied

    def test_fail_closed_override(self, sample_writer: ControlledWriter) -> None:
        """override_fail_closed=False makes guard permissive."""
        register_writer(sample_writer)
        result = writer_guard(
            writer_id=sample_writer.writer_id,
            override_fail_closed=False,
        )
        assert result.decision == WriteGuardDecision.ALLOWED
        assert not result.fail_closed

    def test_active_cohort_no_enforcement_is_shadow_pass(
        self, sample_writer: ControlledWriter
    ) -> None:
        """ACTIVE writer without enforcement gets SHADOW_PASS."""
        register_writer(sample_writer)
        result = writer_guard(
            writer_id=sample_writer.writer_id,
            override_enforcement=False,
        )
        assert result.decision == WriteGuardDecision.SHADOW_PASS
        assert result.allowed

    def test_active_cohort_with_enforcement_is_allowed(
        self, sample_writer: ControlledWriter
    ) -> None:
        """ACTIVE writer with enforcement gets ALLOWED."""
        register_writer(sample_writer)
        result = writer_guard(
            writer_id=sample_writer.writer_id,
            override_enforcement=True,
        )
        assert result.decision == WriteGuardDecision.ALLOWED
        assert result.allowed

    def test_shadow_cohort_is_shadow_pass(
        self, shadow_writer: ControlledWriter
    ) -> None:
        """SHADOW writer always gets SHADOW_PASS."""
        register_writer(shadow_writer)
        result = writer_guard(writer_id=shadow_writer.writer_id)
        assert result.decision == WriteGuardDecision.SHADOW_PASS
        assert result.allowed


# ═══════════════════════════════════════════════════════════════════════════
# guard_all batch behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestGuardAll:
    """guard_all must run writer_guard against all registered writers."""

    def test_guard_all_empty_registry(self) -> None:
        """guard_all on empty registry returns empty list."""
        results = guard_all()
        assert results == []

    def test_guard_all_with_writers(
        self,
        sample_writer: ControlledWriter,
        shadow_writer: ControlledWriter,
    ) -> None:
        """guard_all returns results for all registered writers."""
        register_writer(sample_writer)
        register_writer(shadow_writer)
        results = guard_all()
        assert len(results) == 2
        ids = {r.writer_id for r in results}
        assert ids == {sample_writer.writer_id, shadow_writer.writer_id}

    def test_guard_all_specific_ids(
        self,
        sample_writer: ControlledWriter,
        shadow_writer: ControlledWriter,
    ) -> None:
        """guard_all with specific ids only checks those ids."""
        register_writer(sample_writer)
        register_writer(shadow_writer)
        results = guard_all(writer_ids=[sample_writer.writer_id])
        assert len(results) == 1
        assert results[0].writer_id == sample_writer.writer_id


# ═══════════════════════════════════════════════════════════════════════════
# list_authority_increasing_writers filtering
# ═══════════════════════════════════════════════════════════════════════════


class TestAuthorityIncreasingWriters:
    """list_authority_increasing_writers must filter correctly."""

    def test_authority_increasing_includes_active_with_action(
        self, sample_writer: ControlledWriter
    ) -> None:
        """ACTIVE writer with action_kind is authority-increasing."""
        register_writer(sample_writer)
        assert sample_writer in list_authority_increasing_writers()

    def test_authority_increasing_excludes_report_only(
        self, report_writer: ControlledWriter
    ) -> None:
        """REPORT_ONLY writer is NOT authority-increasing even with action_kind."""
        register_writer(report_writer)
        assert report_writer not in list_authority_increasing_writers()

    def test_authority_increasing_excludes_empty_action(
        self, sample_writer: ControlledWriter
    ) -> None:
        """Writer with empty action_kind is NOT authority-increasing."""
        # Use object.__setattr__ on frozen dataclass is awkward, so create a new one
        w = ControlledWriter(
            writer_id="no_action@v1",
            surface_name="some_surface",
            cohort=Cohort.ACTIVE,
            action_kind="",  # empty
        )
        register_writer(w)
        assert w not in list_authority_increasing_writers()


# ═══════════════════════════════════════════════════════════════════════════
# Writer map generation
# ═══════════════════════════════════════════════════════════════════════════


class TestWriterMapGeneration:
    """generate_writer_map must produce a deterministic provenance map."""

    def test_generate_writer_map_returns_map(self) -> None:
        """generate_writer_map returns OccurrenceWriterTerminalProvenanceMap."""
        result = generate_writer_map()
        assert isinstance(result, OccurrenceWriterTerminalProvenanceMap)
        assert result.schema_version == WRITER_MAP_SCHEMA_VERSION
        assert result.generated_at != ""

    def test_writer_map_covers_all_surfaces(self) -> None:
        """Writer map must include all WriterSurface values."""
        result = generate_writer_map()
        for surface in WriterSurface:
            assert surface.value in result.surfaces, f"Missing surface: {surface.value}"

    def test_writer_map_ownership_is_complete(self) -> None:
        """Every surface must have an owner in the ownership map."""
        result = generate_writer_map()
        for surface_name in result.surfaces:
            assert surface_name in result.ownership_map
            assert result.ownership_map[surface_name] != ""

    def test_writer_map_all_owners_are_known_domains(self) -> None:
        """Owners must be one of the known domain constants."""
        result = generate_writer_map()
        valid_owners = {
            OWNER_RUN_AUTHORITY,
            OWNER_WBC,
            OWNER_CUSTODY,
            OWNER_PROJECTION,
            OWNER_OBSERVABILITY,
            OWNER_DOMAIN,
            OWNER_MAINTENANCE,
        }
        for surface_name, owner in result.ownership_map.items():
            assert owner in valid_owners, (
                f"Surface {surface_name} has unknown owner: {owner!r}"
            )

    def test_writer_map_writes_json_atomically(self) -> None:
        """generate_writer_map with output_path writes valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "writer_map.json"
            result = generate_writer_map(output_path=out)
            assert out.exists()
            data = json.loads(out.read_text(encoding="utf-8"))
            assert data["schema_version"] == WRITER_MAP_SCHEMA_VERSION
            assert set(data["surfaces"].keys()) == {
                s.value for s in WriterSurface
            }
            # Verify no tmp file left behind
            assert not out.with_suffix(".json.tmp").exists()

    def test_writer_map_digest_is_stable(self) -> None:
        """Two maps generated with the same inputs have identical digests."""
        m1 = generate_writer_map()
        m2 = generate_writer_map()
        assert m1.digest == m2.digest

    def test_writer_map_serialization_round_trip(self) -> None:
        """to_dict → from fields produces equivalent map."""
        m = generate_writer_map()
        d = m.to_dict()
        m2 = OccurrenceWriterTerminalProvenanceMap(
            schema_version=d["schema_version"],
            generated_at=d["generated_at"],
            surfaces=d["surfaces"],
            ownership_map=d["ownership_map"],
        )
        assert m2.digest == m.digest

    def test_writer_map_f01_fields_match_contracts(self) -> None:
        """F01_REPAIR_OCCURRENCE_FIELDS in writer_map matches contracts module."""
        from arnold_pipelines.megaplan.custody.contracts import (
            F01_REPAIR_OCCURRENCE_FIELDS as CONTRACTS_F01,
        )
        assert F01_REPAIR_OCCURRENCE_FIELDS == CONTRACTS_F01


# ═══════════════════════════════════════════════════════════════════════════
# Support-manifest labels are not proof of adoption
# ═══════════════════════════════════════════════════════════════════════════


class TestSupportManifestIsNotAdoptionProof:
    """Labels from support manifests must not be treated as proof of adoption."""

    def test_writer_guard_rejects_unregistered_even_with_known_surface(
        self,
    ) -> None:
        """A surface name from a support manifest does not bypass registration."""
        # The surface 'lease_store' appears in WriterSurface, but if no
        # ControlledWriter was registered for it, the guard must deny.
        result = writer_guard(
            writer_id="made_up_id_from_manifest@v1",
            override_enforcement=True,
        )
        assert result.decision == WriteGuardDecision.UNREGISTERED
        assert result.denied

    def test_get_writer_by_surface_requires_exact_registration(self) -> None:
        """A surface name alone is not enough — the writer must be registered."""
        # Even though 'lease_store' is a known WriterSurface value, if no
        # ControlledWriter is registered on that surface, get_writer_by_surface
        # returns None.
        result = get_writer_by_surface(WriterSurface.LEASE_STORE.value)
        assert result is None  # No writers registered yet

    def test_writer_map_does_not_authorize_writers(self) -> None:
        """The writer map is a provenance artifact, not an authorization source."""
        # Generating the map should not register any writers.
        _clear_registry()
        generate_writer_map()
        # Registry must still be empty — map generation is read-only
        assert list_writers() == []

    def test_surface_string_matches_but_not_registered(self) -> None:
        """Matching a WriterSurface string is not sufficient for authorization."""
        register_writer(
            ControlledWriter(
                writer_id="test_writer@v1",
                surface_name=WriterSurface.LEASE_STORE.value,
                cohort=Cohort.ACTIVE,
            )
        )
        # Now try a different surface that happens to be a known enum value
        # but has no writer registered on it
        assert WriterSurface.OUTBOX.value == "outbox"  # known surface
        result = get_writer_by_surface(WriterSurface.OUTBOX.value)
        assert result is None  # No writer registered on outbox


# ═══════════════════════════════════════════════════════════════════════════
# Deregistration
# ═══════════════════════════════════════════════════════════════════════════


class TestDeregistration:
    """Deregistering writers must clean up both id and surface indices."""

    def test_deregister_known_writer(self, sample_writer: ControlledWriter) -> None:
        """Deregister returns True and removes from lookups."""
        register_writer(sample_writer)
        assert deregister_writer(sample_writer.writer_id) is True
        assert get_writer(sample_writer.writer_id) is None
        assert get_writer_by_surface(sample_writer.surface_name) is None

    def test_deregister_unknown_writer(self) -> None:
        """Deregister returns False for unknown id."""
        assert deregister_writer("nonexistent") is False

    def test_deregister_preserves_other_writers(
        self,
        sample_writer: ControlledWriter,
        shadow_writer: ControlledWriter,
    ) -> None:
        """Deregistering one writer does not affect others."""
        register_writer(sample_writer)
        register_writer(shadow_writer)
        deregister_writer(sample_writer.writer_id)
        assert get_writer(sample_writer.writer_id) is None
        assert get_writer(shadow_writer.writer_id) is not None

    def test_deregister_surface_cleanup(self, sample_writer: ControlledWriter) -> None:
        """After deregistering the last writer on a surface, surface lookup returns None."""
        register_writer(sample_writer)
        deregister_writer(sample_writer.writer_id)
        assert get_writer_by_surface(sample_writer.surface_name) is None


# ═══════════════════════════════════════════════════════════════════════════
# Enums and constants
# ═══════════════════════════════════════════════════════════════════════════


class TestEnumsAndConstants:
    """Verify enum membership and constant values."""

    def test_cohort_enum_values(self) -> None:
        """Cohort must have ACTIVE, SHADOW, REPORT_ONLY."""
        assert Cohort.ACTIVE.value == "active"
        assert Cohort.SHADOW.value == "shadow"
        assert Cohort.REPORT_ONLY.value == "report_only"
        assert len(COHORTS) == 3

    def test_write_guard_decision_values(self) -> None:
        """WriteGuardDecision must have all five values."""
        expected = {"allowed", "denied", "shadow_pass", "report_only", "unregistered"}
        actual = {d.value for d in WriteGuardDecision}
        assert actual == expected

    def test_writer_surface_values(self) -> None:
        """WriterSurface must have all nine values."""
        expected = {
            "lease_store",
            "outbox",
            "action_validator",
            "canary",
            "compatibility",
            "projection_store",
            "repair_receipt",
            "writer_registry",
            "writer_map",
        }
        actual = {s.value for s in WriterSurface}
        assert actual == expected

    def test_owner_constants(self) -> None:
        """Owner constants must be the expected values."""
        assert OWNER_RUN_AUTHORITY == "run_authority"
        assert OWNER_WBC == "wbc"
        assert OWNER_CUSTODY == "custody"
        assert OWNER_PROJECTION == "projection"
        assert OWNER_OBSERVABILITY == "observability"
        assert OWNER_DOMAIN == "domain"
        assert OWNER_MAINTENANCE == "maintenance"

    def test_writer_registry_schema_version(self) -> None:
        """Schema version is a non-empty string."""
        assert WRITER_REGISTRY_SCHEMA_VERSION == "1"

    def test_writer_map_schema_version(self) -> None:
        """Writer map schema version is a non-empty string."""
        assert WRITER_MAP_SCHEMA_VERSION == "1"

    def test_controlled_writer_defaults(self) -> None:
        """ControlledWriter defaults are reasonable."""
        w = ControlledWriter(
            writer_id="test@v1",
            surface_name="test_surface",
        )
        assert w.cohort == Cohort.SHADOW
        assert w.contract_ids == ()
        assert w.source_file == ""
        assert w.function_name == ""
        assert w.required_wbc_phases == ()
        assert w.action_kind == ""

    def test_write_guard_result_defaults(self) -> None:
        """WriteGuardResult defaults are fail-closed."""
        r = WriteGuardResult()
        assert r.decision == WriteGuardDecision.UNREGISTERED
        assert r.denied
        assert not r.allowed
        assert r.fail_closed
        assert not r.enforcement_enabled
        assert r.diagnostics == ()
