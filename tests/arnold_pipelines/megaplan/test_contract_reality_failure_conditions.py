"""Tests for C1 contract reality preflight failure conditions.

Covers every automatic failure condition defined by the C1 North Star:
- Run Authority manifest/base SHA mismatch
- Route migration disposition gaps
- Dual mutating ownership detection
- Fixture replay mutability
- Producer mapping incompleteness
- Migration milestone coverage
- Hash-without-retained-payload

Every test validates that the corresponding validator emits a stable
diagnostic with the correct code, severity, and evidence reference
without requesting approval or generating waivers.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan.workflows.contract_reality import (
    C1DiagnosticSeverity,
    C1DiagnosticSpec,
    C1PreflightDiagnostic,
    C1PreflightResult,
    C1RealityDiagnosticCode,
    C1_DIAGNOSTIC_SPECS,
    C1_DIAGNOSTIC_SPECS_BY_CODE,
    C1_PINNED_BASE_SHA,
    C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH,
    run_c1_preflight,
    validate_run_authority_manifest,
    validate_route_migration_dispositions,
    validate_dual_mutating_ownership,
    validate_fixture_replay_mutability,
    validate_producer_mapping_completeness,
    validate_migration_coverage,
    validate_hash_without_retained_payload,
)


# ── Diagnostic code registry completeness ───────────────────────────────


def test_all_codes_have_spec_entries() -> None:
    """Every C1RealityDiagnosticCode must have exactly one spec entry."""
    for code in C1RealityDiagnosticCode:
        assert code.value in C1_DIAGNOSTIC_SPECS_BY_CODE, (
            f"missing spec for {code.value}"
        )


def test_all_codes_are_error_severity() -> None:
    """All C1 preflight diagnostic codes must be error severity."""
    for spec in C1_DIAGNOSTIC_SPECS:
        assert spec.severity == C1DiagnosticSeverity.ERROR, (
            f"{spec.code.value} must be error severity; got {spec.severity.value}"
        )


def test_all_specs_have_remediation() -> None:
    """Every C1 diagnostic spec must include remediation guidance."""
    for spec in C1_DIAGNOSTIC_SPECS:
        assert spec.remediation is not None, (
            f"{spec.code.value} is missing remediation"
        )
        assert spec.remediation.strip(), (
            f"{spec.code.value} has empty remediation"
        )


def test_all_codes_are_distinct() -> None:
    """No two C1 diagnostic codes should share the same value."""
    codes = [c.value for c in C1RealityDiagnosticCode]
    assert len(codes) == len(set(codes)), "duplicate diagnostic codes detected"


# ── Pinned prerequisite values ──────────────────────────────────────────


def test_pinned_manifest_hash_is_stable() -> None:
    """The pinned Run Authority manifest hash must be the expected value."""
    assert C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH == "2ed830c5a"


def test_pinned_base_sha_is_stable() -> None:
    """The pinned base SHA must be the expected value."""
    assert C1_PINNED_BASE_SHA == "432760d13a"


# ── C1PreflightDiagnostic invariants ────────────────────────────────────


def test_preflight_diagnostic_rejects_empty_message() -> None:
    """C1PreflightDiagnostic must reject empty messages."""
    with pytest.raises(ValueError, match="message must be non-empty"):
        C1PreflightDiagnostic(
            code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
            severity=C1DiagnosticSeverity.ERROR,
            message="  ",
            evidence_ref="c1.test",
        )


def test_preflight_diagnostic_rejects_empty_evidence_ref() -> None:
    """C1PreflightDiagnostic must reject empty evidence references."""
    with pytest.raises(ValueError, match="evidence_ref must be non-empty"):
        C1PreflightDiagnostic(
            code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
            severity=C1DiagnosticSeverity.ERROR,
            message="test message",
            evidence_ref="",
        )


def test_preflight_diagnostic_is_frozen() -> None:
    """C1PreflightDiagnostic instances must be immutable."""
    diag = C1PreflightDiagnostic(
        code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
        severity=C1DiagnosticSeverity.ERROR,
        message="test message",
        evidence_ref="c1.test",
    )
    with pytest.raises(Exception):
        diag.message = "mutated"  # type: ignore[misc]


def test_preflight_diagnostic_is_error() -> None:
    """Error severity diagnostic reports is_error=True."""
    diag = C1PreflightDiagnostic(
        code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
        severity=C1DiagnosticSeverity.ERROR,
        message="test",
        evidence_ref="c1.test",
    )
    assert diag.is_error is True
    assert diag.is_warning is False


def test_preflight_diagnostic_is_warning() -> None:
    """Warning severity diagnostic reports is_warning=True."""
    diag = C1PreflightDiagnostic(
        code=C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH,
        severity=C1DiagnosticSeverity.WARNING,
        message="test",
        evidence_ref="c1.test",
    )
    assert diag.is_error is False
    assert diag.is_warning is True


# ── C1PreflightResult invariants ────────────────────────────────────────


def test_preflight_result_passed_when_no_errors() -> None:
    """Result passes when all diagnostics are warnings."""
    result = C1PreflightResult(
        diagnostics=(),
        validator_count=7,
        total_diagnostics=0,
        error_count=0,
        warning_count=0,
    )
    assert result.passed is True


def test_preflight_result_not_passed_when_errors() -> None:
    """Result does not pass when there are error diagnostics."""
    result = C1PreflightResult(
        diagnostics=(),
        validator_count=7,
        total_diagnostics=1,
        error_count=1,
        warning_count=0,
    )
    assert result.passed is False


# ── Validator 1: Run Authority manifest / base SHA ──────────────────────


def test_manifest_validator_passes_with_matching_hash_and_sha() -> None:
    """No diagnostics when manifest hash and base SHA match pinned values."""
    result = validate_run_authority_manifest(
        manifest_hash=C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH,
        base_sha=C1_PINNED_BASE_SHA,
    )
    assert len(result) == 0


def test_manifest_validator_flags_mismatched_hash() -> None:
    """Emit diagnostic when manifest hash does not match."""
    result = validate_run_authority_manifest(
        manifest_hash="deadbeef",
        base_sha=C1_PINNED_BASE_SHA,
    )
    assert len(result) == 1
    diag = result[0]
    assert diag.code == C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH
    assert diag.severity == C1DiagnosticSeverity.ERROR
    assert diag.evidence_ref == "c1.handoff.run_authority.manifest_hash"
    assert diag.details["expected"] == C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH
    assert diag.details["observed"] == "deadbeef"


def test_manifest_validator_flags_mismatched_base_sha() -> None:
    """Emit diagnostic when base SHA does not match."""
    result = validate_run_authority_manifest(
        manifest_hash=C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH,
        base_sha="abcdef1234",
    )
    assert len(result) == 1
    diag = result[0]
    assert diag.code == C1RealityDiagnosticCode.RUN_AUTHORITY_BASE_SHA_MISMATCH
    assert diag.severity == C1DiagnosticSeverity.ERROR
    assert diag.evidence_ref == "c1.handoff.run_authority.base_sha"


def test_manifest_validator_flags_both_mismatched() -> None:
    """Emit both diagnostics when both hash and SHA mismatch."""
    result = validate_run_authority_manifest(
        manifest_hash="badhash",
        base_sha="badsha",
    )
    assert len(result) == 2
    codes = {d.code for d in result}
    assert C1RealityDiagnosticCode.RUN_AUTHORITY_MANIFEST_MISMATCH in codes
    assert C1RealityDiagnosticCode.RUN_AUTHORITY_BASE_SHA_MISMATCH in codes


def test_manifest_validator_flags_none_inputs() -> None:
    """Emit diagnostics when inputs are None."""
    result = validate_run_authority_manifest(
        manifest_hash=None,
        base_sha=None,
    )
    assert len(result) == 2


# ── Validator 2: Route migration disposition ────────────────────────────


def test_route_validator_passes_with_enforced_routes() -> None:
    """No diagnostics when all routes have valid enforced dispositions."""
    routes: tuple[Mapping[str, Any], ...] = (
        {"id": "route-1", "disposition": "enforced", "route_family": "execute", "owner_or_reason": "run_authority"},
        {"id": "route-2", "disposition": "shadow-only", "route_family": "status", "owner_or_reason": "monitoring"},
    )
    result = validate_route_migration_dispositions(routes)
    assert len(result) == 0


def test_route_validator_flags_missing_disposition() -> None:
    """Emit diagnostic when a route has no disposition."""
    routes: tuple[Mapping[str, Any], ...] = (
        {"id": "route-missing", "disposition": "", "route_family": "execute", "owner_or_reason": ""},
    )
    result = validate_route_migration_dispositions(routes)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.ROUTE_MIGRATION_DISPOSITION_MISSING
    assert result[0].evidence_ref == "c1.route.route-missing.disposition"


def test_route_validator_flags_invalid_disposition() -> None:
    """Emit diagnostic when a route has an invalid disposition."""
    routes: tuple[Mapping[str, Any], ...] = (
        {"id": "route-bad", "disposition": "invalid-mode", "route_family": "execute", "owner_or_reason": ""},
    )
    result = validate_route_migration_dispositions(routes)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.ROUTE_MIGRATION_DISPOSITION_MISSING
    assert result[0].evidence_ref == "c1.route.route-bad.disposition"


def test_route_validator_flags_warn_only_authority_increasing() -> None:
    """Emit diagnostic when an authority-increasing route is warn-only without migration disposition."""
    routes: tuple[Mapping[str, Any], ...] = (
        {"id": "route-warn-exec", "disposition": "warn-only", "route_family": "execute", "owner_or_reason": ""},
    )
    result = validate_route_migration_dispositions(routes)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.ROUTE_MIGRATION_WARN_ONLY_NON_CONFORMANT
    assert result[0].evidence_ref == "c1.route.route-warn-exec.warn_only_non_conformant"


def test_route_validator_accepts_warn_only_with_migration_disposition() -> None:
    """Warn-only is accepted for authority-increasing when owner/reason is present."""
    routes: tuple[Mapping[str, Any], ...] = (
        {
            "id": "route-warn-ok",
            "disposition": "warn-only",
            "route_family": "execute",
            "owner_or_reason": "M2 deferred: migration planned for C3",
        },
    )
    result = validate_route_migration_dispositions(routes)
    assert len(result) == 0


def test_route_validator_accepts_warn_only_non_authority_increasing() -> None:
    """Warn-only for informational/status routes is acceptable."""
    routes: tuple[Mapping[str, Any], ...] = (
        {"id": "route-info", "disposition": "warn-only", "route_family": "status", "owner_or_reason": ""},
    )
    result = validate_route_migration_dispositions(routes)
    assert len(result) == 0


# ── Validator 3: Dual mutating ownership ─────────────────────────────────


def test_ownership_validator_passes_with_single_owner() -> None:
    """No diagnostics when each surface has one mutating owner."""
    surface_owners: tuple[Mapping[str, Any], ...] = (
        {"surface_name": "state.json", "mutating_owners": ["maintenance"]},
        {"surface_name": "authority.claims", "mutating_owners": ["run_authority"]},
    )
    result = validate_dual_mutating_ownership(surface_owners)
    assert len(result) == 0


def test_ownership_validator_flags_dual_owners() -> None:
    """Emit diagnostic when a surface has multiple mutating owners."""
    surface_owners: tuple[Mapping[str, Any], ...] = (
        {"surface_name": "state.json", "mutating_owners": ["maintenance", "wbc"]},
    )
    result = validate_dual_mutating_ownership(surface_owners)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.DUAL_MUTATING_OWNERSHIP
    assert result[0].evidence_ref == "c1.ownership.state.json.dual_mutating"
    assert result[0].details["surface_name"] == "state.json"
    assert "maintenance" in result[0].details["mutating_owners"]
    assert "wbc" in result[0].details["mutating_owners"]


def test_ownership_validator_ignores_unknown_owner_domains() -> None:
    """Non-mutating domains are ignored when detecting dual ownership."""
    surface_owners: tuple[Mapping[str, Any], ...] = (
        {
            "surface_name": "docs.readme",
            "mutating_owners": ["run_authority", "unknown_tool", "some_other"],
        },
    )
    result = validate_dual_mutating_ownership(surface_owners)
    # Only run_authority is a known mutating domain; no dual ownership.
    assert len(result) == 0


def test_ownership_validator_flags_three_way_conflict() -> None:
    """Emit diagnostic when three mutating owners claim a surface."""
    surface_owners: tuple[Mapping[str, Any], ...] = (
        {
            "surface_name": "conflict_surface",
            "mutating_owners": ["run_authority", "maintenance", "wbc"],
        },
    )
    result = validate_dual_mutating_ownership(surface_owners)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.DUAL_MUTATING_OWNERSHIP


# ── Validator 4: Fixture replay mutability ──────────────────────────────


def test_fixture_validator_passes_read_only_fixtures() -> None:
    """No diagnostics when fixtures are read-only."""
    fixtures: tuple[Mapping[str, Any], ...] = (
        {"ref": "legacy_state", "requires_mutation": False, "has_hidden_fallback": False},
        {"ref": "current_receipt", "requires_mutation": False, "has_hidden_fallback": False},
    )
    result = validate_fixture_replay_mutability(fixtures)
    assert len(result) == 0


def test_fixture_validator_flags_mutation_required() -> None:
    """Emit diagnostic when fixture replay requires mutation."""
    fixtures: tuple[Mapping[str, Any], ...] = (
        {"ref": "mutating_fixture", "requires_mutation": True, "has_hidden_fallback": False},
    )
    result = validate_fixture_replay_mutability(fixtures)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.FIXTURE_REPLAY_MUTABILITY
    assert result[0].evidence_ref == "c1.fixture.mutating_fixture.mutability"


def test_fixture_validator_flags_hidden_fallback() -> None:
    """Emit diagnostic when fixture has hidden fallback."""
    fixtures: tuple[Mapping[str, Any], ...] = (
        {"ref": "fallback_fixture", "requires_mutation": False, "has_hidden_fallback": True},
    )
    result = validate_fixture_replay_mutability(fixtures)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.FIXTURE_REPLAY_MUTABILITY
    assert result[0].evidence_ref == "c1.fixture.fallback_fixture.mutability"


def test_fixture_validator_flags_both_issues() -> None:
    """Emit diagnostics for each fixture with issues."""
    fixtures: tuple[Mapping[str, Any], ...] = (
        {"ref": "mut_fix", "requires_mutation": True, "has_hidden_fallback": False},
        {"ref": "fallback_fix", "requires_mutation": False, "has_hidden_fallback": True},
    )
    result = validate_fixture_replay_mutability(fixtures)
    assert len(result) == 2


# ── Validator 5: Producer mapping completeness ──────────────────────────


def test_producer_validator_passes_when_all_mapped() -> None:
    """No diagnostics when all contracts have producer mappings."""
    contracts: tuple[Mapping[str, Any], ...] = (
        {"contract_id": "prep_to_plan"},
        {"contract_id": "plan_to_critique"},
    )
    producers: tuple[Mapping[str, Any], ...] = (
        {"contract_id": "prep_to_plan", "producer_path": "handlers/prep.py"},
        {"contract_id": "plan_to_critique", "producer_path": "handlers/plan.py"},
    )
    result = validate_producer_mapping_completeness(contracts, producers)
    assert len(result) == 0


def test_producer_validator_flags_unmapped_contract() -> None:
    """Emit diagnostic when a contract has no producer mapping."""
    contracts: tuple[Mapping[str, Any], ...] = (
        {"contract_id": "unmapped_contract"},
    )
    producers: tuple[Mapping[str, Any], ...] = ()
    result = validate_producer_mapping_completeness(contracts, producers)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.PRODUCER_MAPPING_INCOMPLETE
    assert result[0].evidence_ref == "c1.producer.unmapped_contract.unmapped"


def test_producer_validator_flags_multiple_unmapped() -> None:
    """Emit diagnostics for each unmapped contract."""
    contracts: tuple[Mapping[str, Any], ...] = (
        {"contract_id": "unmapped_a"},
        {"contract_id": "unmapped_b"},
    )
    producers: tuple[Mapping[str, Any], ...] = ()
    result = validate_producer_mapping_completeness(contracts, producers)
    assert len(result) == 2
    codes = {d.code for d in result}
    assert len(codes) == 1
    assert C1RealityDiagnosticCode.PRODUCER_MAPPING_INCOMPLETE in codes


# ── Validator 6: Migration coverage ─────────────────────────────────────


def test_migration_validator_passes_with_valid_milestones() -> None:
    """No diagnostics when all producers have valid milestones."""
    supported_producers: tuple[Mapping[str, Any], ...] = (
        {"producer_ref": "prep_handler", "migration_milestone": "C2"},
        {"producer_ref": "plan_handler", "migration_milestone": "C3"},
        {"producer_ref": "execute_handler", "migration_milestone": "C6"},
    )
    result = validate_migration_coverage(supported_producers)
    assert len(result) == 0


def test_migration_validator_flags_missing_milestone() -> None:
    """Emit diagnostic when a producer has no milestone."""
    supported_producers: tuple[Mapping[str, Any], ...] = (
        {"producer_ref": "no_milestone_handler", "migration_milestone": ""},
    )
    result = validate_migration_coverage(supported_producers)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.MIGRATION_MILESTONE_MISSING
    assert result[0].evidence_ref == "c1.migration.no_milestone_handler.milestone_missing"


def test_migration_validator_flags_invalid_milestone() -> None:
    """Emit diagnostic when a producer has an invalid milestone."""
    supported_producers: tuple[Mapping[str, Any], ...] = (
        {"producer_ref": "bad_milestone_handler", "migration_milestone": "C7"},
    )
    result = validate_migration_coverage(supported_producers)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.MIGRATION_MILESTONE_MISSING
    assert result[0].evidence_ref == "c1.migration.bad_milestone_handler.milestone_missing"


def test_migration_validator_flags_unknown_producer() -> None:
    """Emit coverage gap diagnostic for unknown producer ref."""
    supported_producers: tuple[Mapping[str, Any], ...] = (
        {"producer_ref": "", "migration_milestone": ""},
    )
    result = validate_migration_coverage(supported_producers)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.MIGRATION_COVERAGE_GAP
    assert result[0].evidence_ref == "c1.migration.coverage_gap"


# ── Validator 7: Hash-without-retained-payload ──────────────────────────


def test_hash_payload_validator_passes_with_retained_payloads() -> None:
    """No diagnostics when all hashes have retained payloads."""
    payload_refs: tuple[Mapping[str, Any], ...] = (
        {"hash_ref": "sha256:abc123", "has_retained_payload": True},
        {"hash_ref": "sha256:def456", "has_retained_payload": True},
    )
    result = validate_hash_without_retained_payload(payload_refs)
    assert len(result) == 0


def test_hash_payload_validator_flags_missing_retention() -> None:
    """Emit diagnostic when a hash has no retained payload."""
    payload_refs: tuple[Mapping[str, Any], ...] = (
        {"hash_ref": "sha256:orphan_hash", "has_retained_payload": False},
    )
    result = validate_hash_without_retained_payload(payload_refs)
    assert len(result) == 1
    assert result[0].code == C1RealityDiagnosticCode.HASH_WITHOUT_RETAINED_PAYLOAD
    assert result[0].evidence_ref == "c1.payload.sha256:orphan_hash.hash_without_retention"
    assert result[0].details["hash_ref"] == "sha256:orphan_hash"


def test_hash_payload_validator_flags_multiple_orphans() -> None:
    """Emit diagnostics for each hash without retained payload."""
    payload_refs: tuple[Mapping[str, Any], ...] = (
        {"hash_ref": "orphan_1", "has_retained_payload": False},
        {"hash_ref": "orphan_2", "has_retained_payload": False},
    )
    result = validate_hash_without_retained_payload(payload_refs)
    assert len(result) == 2


# ── Composite preflight runner ──────────────────────────────────────────


def test_run_c1_preflight_passes_with_all_valid_inputs() -> None:
    """Composite runner passes when all validators are satisfied."""
    result = run_c1_preflight(
        manifest_hash=C1_PINNED_RUN_AUTHORITY_MANIFEST_HASH,
        base_sha=C1_PINNED_BASE_SHA,
        routes=(
            {"id": "r1", "disposition": "enforced", "route_family": "execute", "owner_or_reason": "ra"},
        ),
        surface_owners=(
            {"surface_name": "state", "mutating_owners": ["maintenance"]},
        ),
        fixtures=(
            {"ref": "legacy", "requires_mutation": False, "has_hidden_fallback": False},
        ),
        contracts=(
            {"contract_id": "prep_to_plan"},
        ),
        producers=(
            {"contract_id": "prep_to_plan", "producer_path": "h/prep.py"},
        ),
        supported_producers=(
            {"producer_ref": "prep_handler", "migration_milestone": "C2"},
        ),
        payload_refs=(
            {"hash_ref": "sha:abc", "has_retained_payload": True},
        ),
    )
    assert result.passed is True
    assert result.error_count == 0
    assert result.validator_count == 7


def test_run_c1_preflight_fails_with_errors() -> None:
    """Composite runner fails when any validator emits errors."""
    result = run_c1_preflight(
        manifest_hash="wrong_hash",
        base_sha=C1_PINNED_BASE_SHA,
    )
    assert result.passed is False
    assert result.error_count >= 1


def test_run_c1_preflight_runs_all_validators_even_with_errors() -> None:
    """Composite runner runs all 7 validators regardless of individual errors."""
    result = run_c1_preflight(
        manifest_hash=None,
        base_sha=None,
    )
    assert result.validator_count == 7
    # At minimum, manifest and base SHA validators produce 2 errors
    assert result.error_count >= 2


# ── No-approval / no-waiver invariants ──────────────────────────────────


def test_diagnostics_do_not_contain_approval_requests() -> None:
    """No diagnostic message should contain approval-related language."""
    result = run_c1_preflight(
        manifest_hash="bad_hash",
        base_sha="bad_sha",
        routes=(
            {"id": "r", "disposition": "warn-only", "route_family": "execute", "owner_or_reason": ""},
        ),
    )
    for diag in result.diagnostics:
        msg_lower = diag.message.lower()
        assert "approve" not in msg_lower, f"diagnostic {diag.code} contains 'approve'"
        assert "approval" not in msg_lower, f"diagnostic {diag.code} contains 'approval'"
        assert "waiver" not in msg_lower, f"diagnostic {diag.code} contains 'waiver'"
        assert "waive" not in msg_lower, f"diagnostic {diag.code} contains 'waive'"


def test_diagnostics_do_not_mutate_state() -> None:
    """Diagnostics are data-only and carry no mutable state references."""
    result = run_c1_preflight(
        manifest_hash="bad_hash",
        base_sha="bad_sha",
    )
    for diag in result.diagnostics:
        # Diagnostics are frozen dataclasses
        assert hasattr(diag, "code")
        assert hasattr(diag, "message")
        # No mutation methods
        assert not hasattr(diag, "mutate")
        assert not hasattr(diag, "apply")
        assert not hasattr(diag, "execute")
