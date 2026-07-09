from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
TRACEABILITY_PATH = ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"
CONFORMANCE_PATH = ROOT / "docs/arnold/megaplan-native-representation-conformance.yaml"

TRACEABILITY_EXPECTATIONS = {
    "shadow-topology": {
        "proof_artifacts": (
            "shadow_topology_diff",
            "review_signoff",
            "parity_notes",
        ),
        "false_pass_guard_terms": ("handler-backed runtime",),
        "negative_invariant_terms": ("accepted shadow topology",),
    },
    "handler-purity-audit": {
        "proof_artifacts": (
            "handler_inventory",
            "purity_scan",
            "source_excerpts",
            "reviewer_signoff",
        ),
        "false_pass_guard_terms": ("native nodes", "control flow"),
        "negative_invariant_terms": (
            "current_state",
            "next_step",
            "workflow_transition",
            "run_parallel",
            "auto-loop dispatch",
            "override action dispatch",
        ),
    },
    "human-decision-suspension": {
        "proof_artifacts": (
            "process_death_resume_test",
            "rendered_suspension_points",
            "boundary_receipt_test",
        ),
        "false_pass_guard_terms": ("runtime state",),
        "negative_invariant_terms": (
            "canonical source plus boundary receipts",
            "status/CLI hints",
            "compatibility shells",
        ),
    },
    "execute-approval-gates": {
        "proof_artifacts": (
            "approval_tests",
            "no_review_golden",
            "deferred_human_golden",
            "boundary_receipt_test",
        ),
        "false_pass_guard_terms": ("CLI or manifest bridge",),
        "negative_invariant_terms": (
            "declared execute gates and boundary receipts",
            "CLI handlers",
            "manifest backend routing",
        ),
    },
    "review-retry-cap-outcomes": {
        "proof_artifacts": (
            "infra_retry_golden",
            "repeated_failure_cap_golden",
            "force_proceed_block_tests",
            "authority_boundary_test",
        ),
        "false_pass_guard_terms": ("handler/control state", "authority receipts"),
        "negative_invariant_terms": (
            "review route policy and cap authority receipts",
            "handler refs",
            "auto next-step hints",
            "compatibility bridges",
        ),
    },
    "override-action-surface": {
        "proof_artifacts": (
            "override_matrix",
            "action_route_tests",
            "authority_boundary_test",
        ),
        "false_pass_guard_terms": ("components", "route bindings"),
        "negative_invariant_terms": (
            "override matrix",
            "canonical source",
            "authority receipts",
            "components",
            "handler refs",
            "route bindings",
            "manifest routing",
            "CLI handlers",
            "compatibility bridges",
        ),
    },
    "autodrive-event-liveness": {
        "proof_artifacts": (
            "event_replay_test",
            "liveness_policy_test",
            "status_projection_parity",
            "cursor_projection_test",
        ),
        "false_pass_guard_terms": ("state, status, or CLI projection",),
        "negative_invariant_terms": (
            "source-derived workflow events and cursors",
            "auto next-step derivation",
            "CLI handlers",
            "projected native shells",
        ),
    },
    "source-path-reconciliation": {
        "proof_artifacts": (
            "path_reconciliation_table",
            "import_smoke_test",
            "native_shell_negative_test",
        ),
        "false_pass_guard_terms": ("projected native shells",),
        "negative_invariant_terms": (
            "native-shell negative test",
            "Pipeline.native_program",
            "workflow.py shims",
        ),
    },
}

CONFORMANCE_EXPECTATIONS = {
    "shadow-topology": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "tests/arnold_pipelines/megaplan/fixtures/megaplan_m4_topology.yaml",
            "tests/arnold_pipelines/megaplan/test_compositional_workflow.py",
        ),
    },
    "handler-purity-audit": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/handlers/plan.py",
            "arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py",
        ),
        "proof_artifacts": (
            "tests/arnold_pipelines/megaplan/test_semantics_carrier.py",
            "arnold_pipelines/megaplan/handlers/plan.py",
            "arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py",
        ),
    },
    "human-decision-suspension": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "tests/arnold_pipelines/megaplan/test_resume_routing.py",
            "tests/arnold_pipelines/megaplan/test_semantic_health.py",
        ),
    },
    "execute-approval-gates": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "arnold_pipelines/megaplan/workflows/boundary_contracts.py",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "tests/arnold_pipelines/megaplan/test_workflows_planning.py",
            "tests/arnold_pipelines/megaplan/test_boundary_contracts.py",
        ),
    },
    "review-retry-cap-outcomes": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "arnold_pipelines/megaplan/workflows/boundary_contracts.py",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "tests/arnold_pipelines/megaplan/test_workflows_planning.py",
            "tests/arnold_pipelines/megaplan/test_boundary_contracts.py",
            "tests/arnold_pipelines/megaplan/test_s6_override_routing.py",
        ),
    },
    "override-action-surface": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "arnold_pipelines/megaplan/workflows/override_matrix.py",
            "arnold_pipelines/megaplan/workflows/boundary_contracts.py",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/override_matrix.py",
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "tests/arnold_pipelines/megaplan/test_override_action_matrix.py",
            "tests/arnold_pipelines/megaplan/test_s6_override_routing.py",
            "tests/arnold_pipelines/megaplan/test_boundary_contracts.py",
        ),
    },
    "autodrive-event-liveness": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/events.py",
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/events.py",
            "tests/arnold_pipelines/megaplan/test_s6_auto_event_consumption.py",
            "tests/arnold_pipelines/megaplan/test_workflow_events.py",
            "tests/arnold_pipelines/megaplan/test_observability_events_projection.py",
            "tests/arnold_pipelines/megaplan/test_status_cli.py",
        ),
    },
    "source-path-reconciliation": {
        "carrier_evidence": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
        ),
        "proof_artifacts": (
            "arnold_pipelines/megaplan/workflows/workflow.pypeline",
            "tests/arnold_pipelines/megaplan/test_source_path_reconciliation.py",
            "tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py",
            "tests/arnold_pipelines/megaplan/test_native_contract.py",
        ),
    },
}

FORBIDDEN_PROOF_SOURCES = (
    "arnold_pipelines/megaplan/workflows/components.py",
    "arnold_pipelines/megaplan/runtime/manifest_backend.py",
    "arnold_pipelines/megaplan/route_dispatch.py",
    "arnold_pipelines/megaplan/auto.py",
    "arnold_pipelines/megaplan/cli/__init__.py",
    "arnold_pipelines/megaplan/cli/status_view.py",
    "arnold_pipelines/megaplan/pipeline.py",
    "arnold_pipelines/megaplan/workflows/workflow.py",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _row_map(path: Path) -> dict[str, dict[str, Any]]:
    rows = _load_yaml(path)["rows"]
    assert isinstance(rows, list)
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        assert isinstance(row, dict)
        row_id = row.get("id")
        assert isinstance(row_id, str)
        mapping[row_id] = row
    return mapping


def _validate_s6_conformance_rows(rows: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row_id, expectation in CONFORMANCE_EXPECTATIONS.items():
        row = rows[row_id]
        carrier_evidence = tuple(row["carrier_evidence"])
        proof_artifacts = tuple(row["proof_artifacts"])

        if carrier_evidence != expectation["carrier_evidence"]:
            errors.append(
                f"{row_id} carrier_evidence drifted: "
                f"expected {expectation['carrier_evidence']}, got {carrier_evidence}"
            )
        if proof_artifacts != expectation["proof_artifacts"]:
            errors.append(
                f"{row_id} proof_artifacts drifted: "
                f"expected {expectation['proof_artifacts']}, got {proof_artifacts}"
            )

        for path in carrier_evidence + proof_artifacts:
            if path.startswith("docs/arnold/"):
                errors.append(f"{row_id} cites doc-only proof source {path}")
            for forbidden in FORBIDDEN_PROOF_SOURCES:
                if path == forbidden:
                    errors.append(f"{row_id} cites forbidden S6 proof source {path}")
    return errors


def test_s6_traceability_rows_encode_row_level_reproof_contracts() -> None:
    rows = _row_map(TRACEABILITY_PATH)

    for row_id, expectation in TRACEABILITY_EXPECTATIONS.items():
        row = rows[row_id]
        assert tuple(row["proof_artifacts"]) == expectation["proof_artifacts"]
        for term in expectation["false_pass_guard_terms"]:
            assert term in row["false_pass_guard"], (row_id, term)
        for term in expectation["negative_invariant_terms"]:
            assert term in row["negative_invariant"], (row_id, term)


def test_s6_conformance_rows_use_only_row_level_source_policy_and_boundary_evidence() -> None:
    errors = _validate_s6_conformance_rows(_row_map(CONFORMANCE_PATH))
    assert errors == []


@pytest.mark.parametrize(
    ("row_id", "field", "bad_path"),
    [
        ("shadow-topology", "carrier_evidence", "arnold_pipelines/megaplan/pipeline.py"),
        ("shadow-topology", "proof_artifacts", "arnold_pipelines/megaplan/workflows/workflow.py"),
        ("handler-purity-audit", "carrier_evidence", "arnold_pipelines/megaplan/workflows/components.py"),
        ("handler-purity-audit", "proof_artifacts", "arnold_pipelines/megaplan/route_dispatch.py"),
        ("override-action-surface", "carrier_evidence", "arnold_pipelines/megaplan/workflows/components.py"),
        ("override-action-surface", "proof_artifacts", "arnold_pipelines/megaplan/route_dispatch.py"),
        ("execute-approval-gates", "proof_artifacts", "arnold_pipelines/megaplan/runtime/manifest_backend.py"),
        ("autodrive-event-liveness", "proof_artifacts", "arnold_pipelines/megaplan/auto.py"),
        ("autodrive-event-liveness", "proof_artifacts", "arnold_pipelines/megaplan/cli/status_view.py"),
        ("source-path-reconciliation", "carrier_evidence", "arnold_pipelines/megaplan/pipeline.py"),
        ("source-path-reconciliation", "proof_artifacts", "arnold_pipelines/megaplan/workflows/workflow.py"),
    ],
)
def test_s6_conformance_rows_reject_legacy_proof_carriers(
    row_id: str,
    field: str,
    bad_path: str,
) -> None:
    rows = deepcopy(_row_map(CONFORMANCE_PATH))
    mutated = rows[row_id]
    mutated[field] = [*mutated[field], bad_path]

    errors = _validate_s6_conformance_rows(rows)

    assert any(row_id in error and bad_path in error for error in errors)
