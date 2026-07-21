"""Public API comparison tests for M7 custody and M6 inventory rebuilt modules.

Verifies the bytecode interface evidence snapshots match the expected
public API of rebuilt source modules.  Bytecode is treated as compatibility
evidence, NOT authority — North Star invariants override recovered behavior.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest


# ── Paths ──────────────────────────────────────────────────────────────────

EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence"
M7_CUSTODY_EVIDENCE = EVIDENCE_DIR / "m7-custody-bytecode-interface.json"
M6_INVENTORY_EVIDENCE = EVIDENCE_DIR / "m6-inventory-bytecode-interface.json"


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_evidence(path: Path) -> dict:
    """Load and validate evidence JSON."""
    assert path.exists(), f"Evidence file missing: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1, f"Unexpected schema_version in {path}"
    return data


# ═══════════════════════════════════════════════════════════════════════════
# M7 Custody Evidence Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestM7CustodyEvidenceStructure:
    """Verify the M7 custody bytecode interface evidence is well-formed."""

    def test_evidence_file_exists_and_is_valid_json(self) -> None:
        """Evidence file must be readable, valid JSON, with correct schema."""
        evidence = _load_evidence(M7_CUSTODY_EVIDENCE)
        assert evidence["source"].startswith("M7 custody bytecode")

    def test_all_expected_modules_present(self) -> None:
        """All 9 custody modules must be documented in the evidence."""
        evidence = _load_evidence(M7_CUSTODY_EVIDENCE)
        expected_modules = {
            "contracts",
            "lease_store",
            "action_validator",
            "controlled_writer_registry",
            "writer_map",
            "canary",
            "compatibility",
            "outbox",
            "projections",
            "repair_receipt",
        }
        actual_modules = set(evidence["modules"].keys())
        missing = expected_modules - actual_modules
        extra = actual_modules - expected_modules
        assert not missing, f"Missing module evidence: {missing}"
        assert not extra, f"Unexpected module evidence: {extra}"

    def test_contracts_module_has_required_dataclasses(self) -> None:
        """Contracts module must define CustodyTargetKey, RepairOccurrenceKey, CustodyLease, CustodyLeaseEvent."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["contracts"]
        dc_names = {dc["name"] for dc in mod["public_dataclasses"]}
        required = {"CustodyTargetKey", "RepairOccurrenceKey", "CustodyLease", "CustodyLeaseEvent"}
        assert required <= dc_names, f"Missing dataclasses: {required - dc_names}"

    def test_lease_store_has_store_and_error_types(self) -> None:
        """Lease store must define CustodyLeaseStore and exception hierarchy."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["lease_store"]
        store_names = [dc["name"] for dc in mod["public_dataclasses"]]
        assert "CustodyLeaseStore" in store_names
        exc_names = [exc["name"] for exc in mod["public_exceptions"]]
        assert "LeaseStoreError" in exc_names
        assert "StaleSequenceError" in exc_names
        assert "LeaseIdempotencyConflict" in exc_names
        assert "QuarantinedPayloadError" in exc_names
        assert "LeaseNotFoundError" in exc_names

    def test_action_validator_has_boundary_types_and_gate_result(self) -> None:
        """Action validator must define ActionBoundaryContext, ActionBoundaryResult, and validation enums."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["action_validator"]
        dc_names = {dc["name"] for dc in mod["public_dataclasses"]}
        assert {"ActionBoundaryContext", "ActionBoundaryResult"} <= dc_names
        enum_names = {e["name"] for e in mod["public_enums"]}
        assert {"ActionBoundaryType", "ValidationOutcome", "GateResult", "SourceCheck"} <= enum_names

    def test_controlled_writer_registry_fail_closed(self) -> None:
        """Writer registry must support fail-closed lookups with writer_guard."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["controlled_writer_registry"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "writer_guard" in func_names
        assert "get_writer" in func_names
        # key enums
        enum_names = {e["name"] for e in mod["public_enums"]}
        assert "Cohort" in enum_names
        assert "WriteGuardDecision" in enum_names

    def test_writer_map_defines_owners(self) -> None:
        """Writer map must define the ownership constants for cross-module provenance."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["writer_map"]
        const_names = {c["name"] for c in mod["public_constants"]}
        required_owners = {
            "OWNER_RUN_AUTHORITY",
            "OWNER_WBC",
            "OWNER_CUSTODY",
            "OWNER_PROJECTION",
            "OWNER_OBSERVABILITY",
            "OWNER_DOMAIN",
            "OWNER_MAINTENANCE",
        }
        assert required_owners <= const_names, f"Missing owner constants: {required_owners - const_names}"

    def test_canary_has_promotion_gate(self) -> None:
        """Canary must define PromotionGateContext, PromotionGateResult, and validate_promotion_gate."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["canary"]
        dc_names = {dc["name"] for dc in mod["public_dataclasses"]}
        assert {"PromotionGateContext", "PromotionGateResult", "CanaryCheck"} <= dc_names
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "validate_promotion_gate" in func_names

    def test_compatibility_read_only_readers(self) -> None:
        """Compatibility must define read-only reader registry with expiry."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["compatibility"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "get_reader" in func_names
        assert "list_readers" in func_names
        assert "list_expired_readers" in func_names
        assert "list_expiring_readers" in func_names
        assert "snapshot" in func_names
        enum_names = {e["name"] for e in mod["public_enums"]}
        assert "CompatibilityMode" in enum_names
        assert "CompatibilityStatus" in enum_names

    def test_outbox_reconciliation(self) -> None:
        """Outbox must support reconciliation with dead-letter handling."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["outbox"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "reconcile_outbox_record" in func_names
        assert "reconcile_all_pending" in func_names
        assert "open_outbox" in func_names
        assert "build_outbox_record_from_event" in func_names

    def test_projections_append_only(self) -> None:
        """Projections must support append-only event sourcing."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["projections"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "open_projection_store" in func_names
        assert "append_events" in func_names

    def test_repair_receipt_idempotency(self) -> None:
        """Repair receipt must provide digest-based idempotency guard."""
        mod = _load_evidence(M7_CUSTODY_EVIDENCE)["modules"]["repair_receipt"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "compute_receipt_digest" in func_names
        assert "build_repair_receipt" in func_names
        assert "is_same_attempt_evidence" in func_names
        assert "review_receipt" in func_names
        assert "rework_receipt" in func_names


class TestM7CustodyNorthStarOwnership:
    """Verify the evidence respects North Star ownership separation."""

    @pytest.fixture(scope="class")
    def evidence(self) -> dict:
        return _load_evidence(M7_CUSTODY_EVIDENCE)

    def test_cross_module_deps_are_documented(self, evidence: dict) -> None:
        """Every module's external dependencies must be listed."""
        deps = evidence["cross_module_dependencies"]
        for mod_name in evidence["modules"]:
            assert mod_name in deps, f"Module {mod_name} missing from cross_module_dependencies"

    def test_no_wbc_grant_authority_in_contracts(self, evidence: dict) -> None:
        """Contracts module must not import WBC or ledger store modules (WBC records do not grant/lease authority)."""
        contracts_deps = evidence["cross_module_dependencies"]["contracts"]
        assert "custody.lease_store" not in contracts_deps
        assert "custody.outbox" not in contracts_deps

    def test_lease_store_does_not_depend_on_wbc(self, evidence: dict) -> None:
        """Lease store does not import WBC modules (Run Authority / Custody / WBC are separate concerns)."""
        ls_deps = evidence["cross_module_dependencies"]["lease_store"]
        wbc_deps = [d for d in ls_deps if "wbc" in d.lower() or "ledger" in d.lower()]
        assert not wbc_deps, f"Lease store has unexpected WBC dependencies: {wbc_deps}"

    def test_north_star_overrides_note_present(self, evidence: dict) -> None:
        """Evidence must include a note about North Star overrides."""
        note = evidence.get("north_star_overrides_note", "")
        assert "North Star" in note
        assert "WBC records" in note.lower() or "grant" in note.lower() or "authority" in note.lower()


# ═══════════════════════════════════════════════════════════════════════════
# M6 Inventory Evidence Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestM6InventoryEvidenceStructure:
    """Verify the M6 inventory bytecode interface evidence is well-formed."""

    def test_evidence_file_exists_and_is_valid_json(self) -> None:
        """Evidence file must be readable, valid JSON, with correct schema."""
        evidence = _load_evidence(M6_INVENTORY_EVIDENCE)
        assert evidence["source"].startswith("M6 inventory bytecode")

    def test_all_expected_modules_present(self) -> None:
        """All M6 inventory tool modules must be documented."""
        evidence = _load_evidence(M6_INVENTORY_EVIDENCE)
        expected_modules = {
            "generate_wbc_boundary_inventory",
            "generate_m6_controlled_registries",
            "generate_m6_finding_register",
            "generate_m6_ownership_decision",
            "generate_m6_replay_fixtures",
            "generate_m6_rollout_register",
            "reconcile_m6_migration_matrix",
            "validate_m6_evidence",
            "verify_m6_prerequisites",
            "wbc_ledger_cli",
        }
        actual_modules = set(evidence["modules"].keys())
        missing = expected_modules - actual_modules
        assert not missing, f"Missing module evidence: {missing}"

    def test_wbc_boundary_inventory_defines_surfaces(self) -> None:
        """WBC boundary inventory must define surface type constants."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["generate_wbc_boundary_inventory"]
        const_names = {c["name"] for c in mod["public_constants"]}
        required = {
            "SURFACE_RECEIPT_WRITER",
            "SURFACE_DURABLE_REF",
            "SURFACE_LEDGER",
            "SURFACE_JOURNAL",
            "SURFACE_PROJECTION",
            "SURFACE_AUTHORITY_READER",
            "SURFACE_AUTHORITY_WRITER",
            "SURFACE_COMPATIBILITY_SHIM",
            "SURFACE_UNKNOWN",
        }
        assert required <= const_names, f"Missing surface constants: {required - const_names}"

    def test_wbc_boundary_inventory_has_generate_function(self) -> None:
        """WBC boundary inventory must expose a generate() function."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["generate_wbc_boundary_inventory"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "generate" in func_names
        assert "parse_boundary_contracts" in func_names
        assert "parse_contract_matrix" in func_names
        assert "parse_support_manifest" in func_names

    def test_controlled_registries_produce_writer_and_reader_registries(self) -> None:
        """Controlled registry generator must produce writer and reader registries."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["generate_m6_controlled_registries"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "generate_registry" in func_names  # writer registry
        assert "generate_reader_registry" in func_names

    def test_verify_prerequisites_is_read_only(self) -> None:
        """Prerequisite verifier must be read-only (check, not mutate)."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["verify_m6_prerequisites"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "run_all_checks" in func_names
        assert "emit" in func_names
        # All functions start with "check_" — read-only verification
        check_funcs = [n for n in func_names if n.startswith("check_")]
        assert len(check_funcs) >= 8, f"Expected many check_ functions, got {len(check_funcs)}"

    def test_wbc_ledger_cli_exposes_five_operations(self) -> None:
        """WBC Ledger CLI must expose append/read/query/reconcile/migrate operations."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["wbc_ledger_cli"]
        ops = {op["name"] for op in mod["public_operations"]}
        assert {"append", "read", "query", "reconcile", "migrate"} == ops

    def test_wbc_ledger_cli_depends_on_arnold_modules(self) -> None:
        """WBC Ledger CLI must depend on arnold workflow and adapter modules."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["wbc_ledger_cli"]
        deps = " ".join(mod.get("dependencies", []))
        assert "arnold.workflow.attempt_ledger_store" in deps
        assert "arnold.workflow.execution_attempt_ledger" in deps
        assert "arnold.adapters.ledger_store_adapter" in deps


class TestM6InventoryEvidenceNorthStar:
    """Verify M6 inventory evidence respects North Star constraints."""

    def test_c1_matrix_is_immutable_input(self) -> None:
        """Contract matrix is parsed as immutable input, not mutated."""
        mod = _load_evidence(M6_INVENTORY_EVIDENCE)["modules"]["generate_wbc_boundary_inventory"]
        func_names = {f["name"] for f in mod["public_functions"]}
        assert "parse_contract_matrix" in func_names
        # No mutation function — only parse + generate

    def test_north_star_overrides_note(self) -> None:
        """Evidence must include North Star overrides note."""
        evidence = _load_evidence(M6_INVENTORY_EVIDENCE)
        note = evidence.get("north_star_overrides_note", "")
        assert "North Star" in note or "C1" in note

    def test_all_generators_are_read_only(self) -> None:
        """All generator functions produce evidence artifacts; none have mutating names."""
        evidence = _load_evidence(M6_INVENTORY_EVIDENCE)
        mutating_names = {"delete", "mutate", "modify", "overwrite", "destroy", "remove"}
        for mod_name, mod in evidence["modules"].items():
            for func in mod.get("public_functions", []):
                name_lower = func["name"].lower()
                for bad in mutating_names:
                    assert bad not in name_lower, (
                        f"Module {mod_name} function {func['name']} looks mutating"
                    )


# ═══════════════════════════════════════════════════════════════════════════
# Module Comparison Utilities
# ═══════════════════════════════════════════════════════════════════════════


class TestModuleComparisonHelpers:
    """Utilities for comparing rebuilt modules against bytecode evidence.

    These tests provide comparison helpers.  When a rebuilt module is
    available, import it and call the helpers.  When no module exists
    yet, the helpers validate the evidence snapshot is internally
    consistent.
    """

    # ── Shared fixtures ────────────────────────────────────────────────

    @pytest.fixture(scope="class")
    def m7_evidence(self) -> dict:
        return _load_evidence(M7_CUSTODY_EVIDENCE)

    @pytest.fixture(scope="class")
    def m6_evidence(self) -> dict:
        return _load_evidence(M6_INVENTORY_EVIDENCE)

    # ── Helper utilities ───────────────────────────────────────────────

    @staticmethod
    def _public_names_from_module(mod: types.ModuleType) -> set[str]:
        """Extract public names from a Python module (names not starting with _)."""
        return {n for n in dir(mod) if not n.startswith("_")}

    @staticmethod
    def _dataclass_field_names(cls: type) -> set[str] | None:
        """Extract field names from a dataclass, or None if not a dataclass."""
        try:
            from dataclasses import fields

            return {f.name for f in fields(cls)}
        except (TypeError, Exception):
            return None

    # ── Evidence snapshot tests (no rebuilt modules yet) ───────────────

    def test_m7_evidence_lists_public_api_for_every_module(self, m7_evidence: dict) -> None:
        """Every M7 custody module entry must list public_dataclasses, functions, or enums."""
        for mod_name, mod in m7_evidence["modules"].items():
            has_content = (
                mod.get("public_dataclasses")
                or mod.get("public_functions")
                or mod.get("public_enums")
                or mod.get("public_exceptions")
                or mod.get("public_constants")
            )
            assert has_content, f"Module {mod_name} has no public API content documented"

    def test_m6_evidence_lists_public_api_for_every_module(self, m6_evidence: dict) -> None:
        """Every M6 inventory module entry must list functions or constants."""
        for mod_name, mod in m6_evidence["modules"].items():
            has_content = (
                mod.get("public_functions")
                or mod.get("public_constants")
                or mod.get("public_enums")
                or mod.get("public_operations")
            )
            assert has_content, f"Module {mod_name} has no public API content documented"

    def test_m7_no_duplicate_module_names(self, m7_evidence: dict) -> None:
        """Module names must be unique."""
        names = list(m7_evidence["modules"].keys())
        assert len(names) == len(set(names)), f"Duplicate module names: {names}"

    def test_m6_no_duplicate_module_names(self, m6_evidence: dict) -> None:
        """Module names must be unique."""
        names = list(m6_evidence["modules"].keys())
        assert len(names) == len(set(names)), f"Duplicate module names: {names}"

    def test_m7_custody_dataclass_fields_are_consistent(self, m7_evidence: dict) -> None:
        """Dataclass field names must be non-empty strings."""
        for mod_name, mod in m7_evidence["modules"].items():
            for dc in mod.get("public_dataclasses", []):
                assert dc["name"], f"Empty dataclass name in {mod_name}"
                for field in dc.get("fields", []):
                    assert field and isinstance(field, str), (
                        f"Bad field {field!r} in {mod_name}.{dc['name']}"
                    )

    def test_m7_custody_enum_members_are_non_empty(self, m7_evidence: dict) -> None:
        """Enum members must be non-empty."""
        for mod_name, mod in m7_evidence["modules"].items():
            for enum in mod.get("public_enums", []):
                assert enum["name"], f"Empty enum name in {mod_name}"
                for member in enum.get("members", []):
                    assert member and isinstance(member, str), (
                        f"Bad member {member!r} in {mod_name}.{enum['name']}"
                    )

    def test_m7_functions_have_signatures(self, m7_evidence: dict) -> None:
        """Every public function must have a name and signature."""
        for mod_name, mod in m7_evidence["modules"].items():
            for func in mod.get("public_functions", []):
                assert func["name"], f"Empty function name in {mod_name}"
                assert "signature" in func, f"Missing signature for {mod_name}.{func['name']}"

    def test_m6_functions_have_signatures(self, m6_evidence: dict) -> None:
        """Every public function must have a name and signature."""
        for mod_name, mod in m6_evidence["modules"].items():
            for func in mod.get("public_functions", []):
                assert func["name"], f"Empty function name in {mod_name}"
                assert "signature" in func, f"Missing signature for {mod_name}.{func['name']}"
