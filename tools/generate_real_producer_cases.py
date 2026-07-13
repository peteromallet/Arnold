#!/usr/bin/env python3
"""Generate real_producer_cases.bundle.json from captured bundles.

Creates at least one healthy and one broken real producer-driven case
for each required phase family. Each broken case corrupts exactly one
required artifact/state/receipt relation without mutating source directories.
"""

import copy
import json
import os
from pathlib import Path

FIXTURE_DIR = Path("tests/fixtures/workflow_boundary_contracts")
OUTPUT_FILE = FIXTURE_DIR / "real_producer_cases.bundle.json"

# Mapping: phase_family -> source bundle filename
PHASE_FAMILY_MAP = {
    "prep": "captured_bundle_025_prep_to_plan.json",
    "plan_revise": "captured_bundle_029_revise_to_critique.json",
    "critique_gate": "captured_bundle_015_gate_to_revise.json",
    "tiebreaker": "captured_bundle_030_tiebreaker_challenger_to_synthesis.json",
    "execute": "captured_bundle_005_execute_approval.json",
    "finalize": "captured_bundle_013_finalize_artifacts.json",
    "review": "captured_bundle_028_review_human_verification.json",
    "override": "captured_bundle_017_override_adopt_execution_authority.json",
}

# Corruption specifications: one per phase family, each corrupts exactly one relation
# Relation types: artifact, state, receipt
CORRUPTIONS = {
    "prep": {
        "corruption_id": "missing_receipt_outcome",
        "target_relation": "receipt",
        "description": "Receipt outcome field removed — breaks receipt relation by removing the completion verdict from the boundary receipt.",
        "apply": lambda bundle: _remove_receipt_field(bundle, "outcome"),
    },
    "plan_revise": {
        "corruption_id": "boundary_id_mismatch",
        "target_relation": "receipt",
        "description": "Receipt boundary_id changed to mismatched value — breaks receipt relation by making the receipt's declared boundary inconsistent with the manifest.",
        "apply": lambda bundle: _change_receipt_field(bundle, "boundary_id", "WRONG_boundary_id"),
    },
    "critique_gate": {
        "corruption_id": "missing_capability_effects",
        "target_relation": "artifact",
        "description": "Manifest capability_effects removed — breaks artifact relation by removing the declared effects that tie manifest to receipts and phase results.",
        "apply": lambda bundle: _remove_manifest_field(bundle, "capability_effects"),
    },
    "tiebreaker": {
        "corruption_id": "missing_state",
        "target_relation": "state",
        "description": "State artifact removed entirely — breaks state relation by removing the state snapshot that receipts reference.",
        "apply": lambda bundle: _remove_artifact(bundle, "state"),
    },
    "execute": {
        "corruption_id": "missing_exit_kind",
        "target_relation": "artifact",
        "description": "Phase result exit_kind removed — breaks artifact relation by removing the phase completion signal that receipts depend on.",
        "apply": lambda bundle: _remove_phase_result_field(bundle, "exit_kind"),
    },
    "finalize": {
        "corruption_id": "missing_invocation_id",
        "target_relation": "receipt",
        "description": "Receipt invocation_id removed — breaks receipt relation by removing invocation identity that links receipt to phase_result.",
        "apply": lambda bundle: _remove_receipt_field(bundle, "invocation_id"),
    },
    "review": {
        "corruption_id": "empty_state_observation",
        "target_relation": "state",
        "description": "Receipt state_observation emptied — breaks state relation by severing the receipt's link to observable state.",
        "apply": lambda bundle: _set_receipt_field(bundle, "state_observation", {}),
    },
    "override": {
        "corruption_id": "missing_workflow_id",
        "target_relation": "receipt",
        "description": "Receipt workflow_id removed — breaks receipt relation by removing workflow scope identity.",
        "apply": lambda bundle: _remove_receipt_field(bundle, "workflow_id"),
    },
}


def _get_first_receipt(bundle: dict) -> dict:
    """Get the first boundary receipt from the bundle."""
    receipts = bundle.get("artifacts", {}).get("boundary_receipts", {})
    for key, val in receipts.items():
        if isinstance(val, dict):
            return val
    return {}


def _set_first_receipt(bundle: dict, receipt: dict) -> None:
    """Set the first boundary receipt in the bundle."""
    receipts = bundle.get("artifacts", {}).get("boundary_receipts", {})
    for key in receipts:
        receipts[key] = receipt
        break


def _remove_receipt_field(bundle: dict, field: str) -> dict:
    """Remove a field from the first boundary receipt."""
    b = copy.deepcopy(bundle)
    receipt = _get_first_receipt(b)
    receipt.pop(field, None)
    _set_first_receipt(b, receipt)
    return b


def _change_receipt_field(bundle: dict, field: str, value) -> dict:
    """Change a field value in the first boundary receipt."""
    b = copy.deepcopy(bundle)
    receipt = _get_first_receipt(b)
    receipt[field] = value
    _set_first_receipt(b, receipt)
    return b


def _set_receipt_field(bundle: dict, field: str, value) -> dict:
    """Set a field value in the first boundary receipt."""
    b = copy.deepcopy(bundle)
    receipt = _get_first_receipt(b)
    receipt[field] = value
    _set_first_receipt(b, receipt)
    return b


def _remove_manifest_field(bundle: dict, field: str) -> dict:
    """Remove a field from the manifest."""
    b = copy.deepcopy(bundle)
    manifest = b.get("artifacts", {}).get("manifest", {})
    if isinstance(manifest, dict):
        manifest.pop(field, None)
    return b


def _remove_phase_result_field(bundle: dict, field: str) -> dict:
    """Remove a field from the phase_result."""
    b = copy.deepcopy(bundle)
    pr = b.get("artifacts", {}).get("phase_result", {})
    if isinstance(pr, dict):
        pr.pop(field, None)
    return b


def _remove_artifact(bundle: dict, artifact_key: str) -> dict:
    """Remove an entire artifact section."""
    b = copy.deepcopy(bundle)
    b.get("artifacts", {}).pop(artifact_key, None)
    return b


def load_bundle(filename: str) -> dict:
    """Load a captured bundle JSON file."""
    path = FIXTURE_DIR / filename
    with open(path) as f:
        return json.load(f)


def compute_expected_status(phase_family: str, corruption: dict) -> str:
    """Determine the expected compatibility status for a broken case.

    Based on the evaluator logic in boundary_compatibility.py:
    - Missing state -> UNKNOWN (critical category)
    - Missing capability_effects -> INCOMPATIBLE (MANIFEST_CAPABILITY_EFFECTS_MISSING)
    - Missing receipt fields -> INCOMPATIBLE (RECEIPT_*_MISSING)
    - Boundary ID mismatch -> INCOMPATIBLE (BOUNDARY_ID_MISMATCH)
    - Missing exit_kind -> INCOMPATIBLE (PHASE_RESULT_EXIT_KIND_MISSING)
    """
    target = corruption["target_relation"]
    corruption_id = corruption["corruption_id"]

    # Missing state is a critical category — evaluator returns UNKNOWN
    if corruption_id == "missing_state":
        return "unknown"

    # All other corruptions produce INCOMPATIBLE results
    return "incompatible"


def compute_expected_diagnostics(phase_family: str, corruption: dict, source_bundle: dict) -> list:
    """Return the expected diagnostic codes for a broken case.

    Includes both the corruption-introduced diagnostic and any pre-existing
    structural issues in the source bundle.
    """
    corruption_id = corruption["corruption_id"]

    corruption_diag_map = {
        "missing_receipt_outcome": ["CBC008_RECEIPT_OUTCOME_MISSING"],
        "boundary_id_mismatch": ["CBC005_BOUNDARY_ID_MISMATCH"],
        "missing_capability_effects": ["CBC009_MANIFEST_CAPABILITY_EFFECTS_MISSING"],
        "missing_state": ["CBC004_MISSING_STATE"],
        "missing_exit_kind": ["CBC010_PHASE_RESULT_EXIT_KIND_MISSING"],
        "missing_invocation_id": ["CBC007_RECEIPT_INVOCATION_ID_MISSING"],
        "empty_state_observation": [],  # state_observation emptied doesn't map to a single CBC
        "missing_workflow_id": ["CBC006_RECEIPT_WORKFLOW_ID_MISSING"],
    }
    diags = list(corruption_diag_map.get(corruption_id, []))

    # Check for pre-existing issues in the source bundle that the evaluator
    # would also flag (these are NOT introduced by our corruption).
    art = source_bundle.get("artifacts", {})
    pr = art.get("phase_result", {})
    if "exit_kind" not in pr and "CBC010_PHASE_RESULT_EXIT_KIND_MISSING" not in diags:
        diags.append("CBC010_PHASE_RESULT_EXIT_KIND_MISSING")

    return sorted(diags)


def _detect_pre_existing_issues(source_bundle: dict) -> list:
    """Detect pre-existing structural issues in a source bundle.

    These are issues that exist in the real producer data before any
    corruption is applied. They are NOT introduced by T18.
    """
    issues = []
    art = source_bundle.get("artifacts", {})
    pr = art.get("phase_result", {})
    if "exit_kind" not in pr:
        issues.append("CBC010_PHASE_RESULT_EXIT_KIND_MISSING")
    manifest = art.get("manifest", {})
    if "capability_effects" not in manifest:
        issues.append("CBC009_MANIFEST_CAPABILITY_EFFECTS_MISSING")
    if "state" not in art:
        issues.append("CBC004_MISSING_STATE")
    receipts = art.get("boundary_receipts", {})
    for rval in receipts.values():
        if isinstance(rval, dict):
            if "outcome" not in rval:
                issues.append("CBC008_RECEIPT_OUTCOME_MISSING")
            if "invocation_id" not in rval:
                issues.append("CBC007_RECEIPT_INVOCATION_ID_MISSING")
            if "workflow_id" not in rval:
                issues.append("CBC006_RECEIPT_WORKFLOW_ID_MISSING")
        break
    return sorted(set(issues))


def main():
    cases = []

    for phase_family in [
        "prep", "plan_revise", "critique_gate", "tiebreaker",
        "execute", "finalize", "review", "override",
    ]:
        source_file = PHASE_FAMILY_MAP[phase_family]
        corruption_spec = CORRUPTIONS[phase_family]

        # Load the source bundle
        source_bundle = load_bundle(source_file)
        boundary_id = source_bundle.get("artifacts", {}).get("manifest", {}).get("boundary_id", "unknown")
        # Strip bundle to just artifacts for the case (source and unknown_markers are capture metadata)
        healthy_artifacts = copy.deepcopy(source_bundle.get("artifacts", {}))

        # ── Healthy case ──
        healthy_case = {
            "case_id": f"healthy_{phase_family}",
            "phase_family": phase_family,
            "case_type": "healthy",
            "source_bundle": source_file,
            "boundary_id": boundary_id,
            "description": f"Real producer-driven healthy case for {phase_family} phase family from {source_file}.",
            "expected_compatibility": "compatible",
            "expected_diagnostics": [],
            "artifacts": healthy_artifacts,
        }
        cases.append(healthy_case)

        # ── Broken case ──
        corrupted_bundle = corruption_spec["apply"](source_bundle)
        corrupted_artifacts = corrupted_bundle.get("artifacts", {})
        expected_status = compute_expected_status(phase_family, corruption_spec)
        expected_diags = compute_expected_diagnostics(phase_family, corruption_spec, source_bundle)

        # Detect pre-existing structural issues in the source bundle
        source_pre_existing = _detect_pre_existing_issues(source_bundle)

        broken_case = {
            "case_id": f"broken_{phase_family}_{corruption_spec['corruption_id']}",
            "phase_family": phase_family,
            "case_type": "broken",
            "source_bundle": source_file,
            "boundary_id": boundary_id,
            "corruption": {
                "corruption_id": corruption_spec["corruption_id"],
                "target_relation": corruption_spec["target_relation"],
                "description": corruption_spec["description"],
            },
            "source_pre_existing_issues": source_pre_existing,
            "description": f"Broken case: {corruption_spec['description']}",
            "expected_compatibility": expected_status,
            "expected_diagnostics": expected_diags,
            "artifacts": corrupted_artifacts,
        }
        cases.append(broken_case)

    # Build the output bundle
    output = {
        "meta": {
            "schema_version": "wbc.real_producer_cases.v1",
            "description": (
                "Real producer-driven healthy and broken cases for each boundary "
                "contract phase family. Healthy cases are extracted directly from "
                "captured producer bundles. Each broken case corrupts exactly one "
                "required artifact/state/receipt relation without mutating source "
                "plan directories. Designed for use with CompatibilityEvaluator "
                "to verify that structural corruptions are correctly detected."
            ),
            "generated_by": "C1 Contract Reality Reconciliation — T18",
            "timestamp_utc": "2026-07-11T20:00:00Z",
            "phase_families": [
                "prep", "plan_revise", "critique_gate", "tiebreaker",
                "execute", "finalize", "review", "override",
            ],
            "total_cases": len(cases),
            "healthy_count": len([c for c in cases if c["case_type"] == "healthy"]),
            "broken_count": len([c for c in cases if c["case_type"] == "broken"]),
            "corruption_discipline": (
                "Each broken case corrupts exactly one required artifact/state/"
                "receipt relation. No case corrupts more than one relation. "
                "Source plan directories are never mutated — all corruptions "
                "are applied in-memory to deep copies."
            ),
        },
        "cases": cases,
    }

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, sort_keys=True)

    print(f"Generated {OUTPUT_FILE}")
    print(f"  Total cases: {len(cases)}")
    for c in cases:
        print(f"  {c['case_id']}: {c['case_type']} -> expected {c['expected_compatibility']}")


if __name__ == "__main__":
    main()
