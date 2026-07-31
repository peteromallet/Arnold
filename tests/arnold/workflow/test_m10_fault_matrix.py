"""Tests for effect_fault_matrix — M10 provisional fault-matrix validation."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from arnold.workflow.effect_fault_matrix import (
    FaultMatrixReport,
    ScenarioValidationError,
    VALID_CUSTODY_PRECONDITIONS,
    VALID_INJECTION_EDGES,
    VALID_PROVIDER_BEHAVIORS,
    VALID_QUERY_BEHAVIORS,
    VALID_REPLAY_EXPECTATIONS,
    load_and_validate_fault_matrix,
    load_and_validate_inventory_coverage,
    validate_fault_matrix,
    validate_inventory_coverage,
    validate_scenario,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _minimal_valid_scenario(scenario_id: str = "F01") -> dict:
    return {
        "id": scenario_id,
        "label": f"test-{scenario_id}",
        "injection_edge": "dispatch",
        "expected_assertion": "test assertion",
        "provider_behavior": "not_called",
        "query_behavior": "not_applied",
        "custody_precondition": "lease_active",
        "replay_expectation": "action_off",
        "inventory_row_refs": [],
        "action_off": True,
        "note": "Test scenario.",
    }


def _write_matrix(scenarios: list[dict]) -> Path:
    """Write a temporary fault matrix and return the path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump({"schema_version": 1, "scenarios": scenarios}, tmp)
    tmp.close()
    return Path(tmp.name)


# ── Positive tests ──────────────────────────────────────────────────────────


def test_default_fault_matrix_loads() -> None:
    """The default fault-matrix artifact exists and is valid JSON."""
    report = load_and_validate_fault_matrix()
    assert report.scenarios_validated > 0
    assert report.is_valid


def test_default_fault_matrix_has_17_scenarios() -> None:
    """The F01-F17 matrix should contain exactly 17 scenarios."""
    report = load_and_validate_fault_matrix()
    assert report.scenarios_validated == 17, (
        f"Expected 17 scenarios, got {report.scenarios_validated}"
    )


def test_all_default_scenarios_are_action_off() -> None:
    """All scenarios in the default matrix must be action-off in M10."""
    report = load_and_validate_fault_matrix()
    # If there were errors about action_off, they'd be in report.errors
    action_off_errors = [
        e for e in report.errors
        if e.field == "action_off" and "action-off" in e.message.lower()
    ]
    assert len(action_off_errors) == 0, (
        f"Found {len(action_off_errors)} scenarios not action-off"
    )


def test_valid_scenario_passes_validation() -> None:
    """A minimal valid scenario passes validation."""
    scenario = _minimal_valid_scenario()
    errors = validate_scenario(scenario)
    assert errors == []


def test_multiple_valid_scenarios() -> None:
    """All F01-F17 pattern scenarios with valid content pass."""
    scenarios = [_minimal_valid_scenario(f"F{i:02d}") for i in range(1, 18)]
    matrix_path = _write_matrix(scenarios)
    try:
        report = validate_fault_matrix(str(matrix_path))
        assert report.is_valid
        assert report.scenarios_validated == 17
    finally:
        matrix_path.unlink(missing_ok=True)


# ── Negative tests: scenario identity ───────────────────────────────────────


def test_missing_id_field() -> None:
    """Scenario missing 'id' field produces an error."""
    scenario = _minimal_valid_scenario()
    del scenario["id"]
    errors = validate_scenario(scenario)
    assert len(errors) >= 1
    assert any(e.field == "id" for e in errors)


def test_empty_id_field() -> None:
    """Scenario with empty 'id' produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["id"] = ""
    errors = validate_scenario(scenario)
    assert any(e.field == "id" for e in errors)


def test_invalid_id_pattern() -> None:
    """Scenario id not matching Fnn pattern produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["id"] = "scenario-1"
    errors = validate_scenario(scenario)
    assert any(e.field == "id" for e in errors)


# ── Negative tests: injection edge ──────────────────────────────────────────


def test_invalid_injection_edge() -> None:
    """Unknown injection edge produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["injection_edge"] = "unknown_edge"
    errors = validate_scenario(scenario)
    assert any(e.field == "injection_edge" for e in errors)


# ── Negative tests: expected assertion ──────────────────────────────────────


def test_empty_expected_assertion() -> None:
    """Empty expected assertion produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["expected_assertion"] = ""
    errors = validate_scenario(scenario)
    assert any(e.field == "expected_assertion" for e in errors)


# ── Negative tests: provider/query behavior ─────────────────────────────────


def test_invalid_provider_behavior() -> None:
    """Unknown provider behavior produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["provider_behavior"] = "invalid_behavior"
    errors = validate_scenario(scenario)
    assert any(e.field == "provider_behavior" for e in errors)


def test_invalid_query_behavior() -> None:
    """Unknown query behavior produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["query_behavior"] = "invalid_query"
    errors = validate_scenario(scenario)
    assert any(e.field == "query_behavior" for e in errors)


# ── Negative tests: custody precondition ────────────────────────────────────


def test_invalid_custody_precondition() -> None:
    """Unknown custody precondition produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["custody_precondition"] = "unknown_precondition"
    errors = validate_scenario(scenario)
    assert any(e.field == "custody_precondition" for e in errors)


# ── Negative tests: replay expectation ──────────────────────────────────────


def test_invalid_replay_expectation() -> None:
    """Unknown replay expectation produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["replay_expectation"] = "unknown_expectation"
    errors = validate_scenario(scenario)
    assert any(e.field == "replay_expectation" for e in errors)


# ── Negative tests: inventory row refs ──────────────────────────────────────


def test_inventory_row_refs_not_list() -> None:
    """Non-list inventory_row_refs produces an error."""
    scenario = _minimal_valid_scenario()
    scenario["inventory_row_refs"] = "not-a-list"
    errors = validate_scenario(scenario)
    assert any(e.field == "inventory_row_refs" for e in errors)


# ── Negative tests: action-off enforcement ──────────────────────────────────


def test_non_action_off_scenario_rejected() -> None:
    """A scenario with action_off=False is rejected in M10."""
    scenario = _minimal_valid_scenario()
    scenario["action_off"] = False
    errors = validate_scenario(scenario)
    assert any(e.field == "action_off" and "action-off" in e.message.lower() for e in errors)


def test_missing_action_off_field() -> None:
    """Missing action_off field produces an error."""
    scenario = _minimal_valid_scenario()
    del scenario["action_off"]
    errors = validate_scenario(scenario)
    assert any(e.field == "action_off" for e in errors)


# ── Matrix-level negative tests ─────────────────────────────────────────────


def test_missing_scenarios_key() -> None:
    """Matrix without 'scenarios' key produces an error."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump({"schema_version": 1}, tmp)
    tmp.close()
    matrix_path = Path(tmp.name)
    try:
        report = validate_fault_matrix(str(matrix_path))
        assert not report.is_valid
        assert any(e.field == "scenarios" for e in report.errors)
    finally:
        matrix_path.unlink(missing_ok=True)


def test_empty_scenarios_list() -> None:
    """Matrix with empty scenarios list produces an error."""
    matrix_path = _write_matrix([])
    try:
        report = validate_fault_matrix(str(matrix_path))
        assert not report.is_valid
        assert any("empty" in e.message.lower() for e in report.errors)
    finally:
        matrix_path.unlink(missing_ok=True)


def test_nonexistent_file() -> None:
    """Validating a nonexistent file produces an error."""
    report = validate_fault_matrix("/nonexistent/path/matrix.json")
    assert not report.is_valid
    assert len(report.errors) >= 1


def test_invalid_json_file() -> None:
    """Validating an invalid JSON file produces an error."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write("not valid json {{{")
    tmp.close()
    matrix_path = Path(tmp.name)
    try:
        report = validate_fault_matrix(str(matrix_path))
        assert not report.is_valid
    finally:
        matrix_path.unlink(missing_ok=True)


# ── Valid-value-set tests ──────────────────────────────────────────────────


def test_known_injection_edges_non_empty() -> None:
    """VALID_INJECTION_EDGES is non-empty."""
    assert len(VALID_INJECTION_EDGES) > 0


def test_known_provider_behaviors_non_empty() -> None:
    """VALID_PROVIDER_BEHAVIORS is non-empty."""
    assert len(VALID_PROVIDER_BEHAVIORS) > 0


def test_known_query_behaviors_non_empty() -> None:
    """VALID_QUERY_BEHAVIORS is non-empty."""
    assert len(VALID_QUERY_BEHAVIORS) > 0


def test_known_custody_preconditions_non_empty() -> None:
    """VALID_CUSTODY_PRECONDITIONS is non-empty."""
    assert len(VALID_CUSTODY_PRECONDITIONS) > 0


def test_known_replay_expectations_non_empty() -> None:
    """VALID_REPLAY_EXPECTATIONS is non-empty."""
    assert len(VALID_REPLAY_EXPECTATIONS) > 0


# ── Report structure tests ──────────────────────────────────────────────────


def test_fault_matrix_report_properties() -> None:
    """FaultMatrixReport has correct property behavior."""
    report = FaultMatrixReport(scenarios_validated=5)
    assert report.is_valid
    assert report.error_count == 0


def test_fault_matrix_report_with_errors() -> None:
    """FaultMatrixReport with errors is not valid."""
    report = FaultMatrixReport(scenarios_validated=3)
    report.errors.append(
        ScenarioValidationError(scenario_id="F01", field="id", message="test error")
    )
    assert not report.is_valid
    assert report.error_count == 1


# ── Scenario identity uniqueness ────────────────────────────────────────────


def test_default_fault_matrix_ids_are_unique() -> None:
    """All scenario IDs in the default matrix are unique."""
    import json as _json
    from pathlib import Path as _Path

    # Go up 4 levels from tests/arnold/workflow/ to reach project root
    matrix_path = (
        _Path(__file__).resolve().parent.parent.parent.parent
        / "evidence"
        / "m10-f01-f17-fault-matrix.json"
    )
    with open(str(matrix_path), "r") as fh:
        data = _json.load(fh)

    ids = [s["id"] for s in data["scenarios"]]
    assert len(ids) == len(set(ids)), f"Duplicate scenario IDs: {ids}"


def test_default_fault_matrix_sequential_f01_to_f17() -> None:
    """Scenario IDs are F01 through F17."""
    import json as _json
    from pathlib import Path as _Path

    # Go up 4 levels from tests/arnold/workflow/ to reach project root
    matrix_path = (
        _Path(__file__).resolve().parent.parent.parent.parent
        / "evidence"
        / "m10-f01-f17-fault-matrix.json"
    )
    with open(str(matrix_path), "r") as fh:
        data = _json.load(fh)

    ids = [s["id"] for s in data["scenarios"]]
    expected = [f"F{i:02d}" for i in range(1, 18)]
    assert ids == expected, f"Expected {expected}, got {ids}"


# ── Step 18A/18B: inventory coverage join tests ─────────────────────────────


def _project_root() -> Path:
    """Return the project root (4 levels up from this test file)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _write_json(payload: dict, suffix: str = ".json") -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    json.dump(payload, tmp)
    tmp.close()
    return Path(tmp.name)


def _content_hash(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _row_identity(row: dict) -> str | None:
    if row.get("identity"):
        return str(row["identity"])
    if row.get("row_kind") == "boundary_contract" and row.get("boundary_id"):
        return f"bc:{row['boundary_id']}"
    if row.get("row_kind") == "manifest_entry" and row.get("step_id"):
        return f"me:{row['step_id']}"
    return None


def _coverage_artifacts(
    *,
    inventory_rows: list[dict],
    supported_rows: list[dict],
    deferred_rows: list[dict] | None = None,
    scenarios: list[dict] | None = None,
    effect_required: list[str] | None = None,
) -> tuple[Path, Path, Path]:
    """Build temp matrix, inventory, and supported-boundaries artifacts."""
    matrix_scenarios = scenarios if scenarios is not None else [
        _minimal_valid_scenario("F01"),
    ]
    matrix = _write_json({"schema_version": 1, "scenarios": matrix_scenarios})
    inventory = _write_json({"rows": inventory_rows})
    required_identities = effect_required
    if required_identities is None:
        required_identities = [
            str(row["identity"])
            for row in supported_rows
            if row.get("row_kind") == "boundary_contract"
        ]
    inventory_by_identity = {
        identity: row
        for row in inventory_rows
        for identity in [_row_identity(row)]
        if identity is not None
    }
    supported_by_identity = {
        str(row["identity"]): row
        for row in supported_rows
        if row.get("identity")
    }
    scope = [
        {
            "identity": identity,
            "source_hash": _content_hash(inventory_by_identity[identity]),
            "support_hash": _content_hash(supported_by_identity[identity]),
        }
        for identity in required_identities
    ]
    supported = _write_json({
        "meta": {"effect_fault_coverage_scope_hash": _content_hash(scope)},
        "effect_fault_coverage_required": scope,
        "supported": supported_rows,
        "deferred": deferred_rows or [],
    })
    return matrix, inventory, supported


def test_default_inventory_coverage_valid() -> None:
    """Step 18A: the default artifacts reconcile with no join errors."""
    report = load_and_validate_inventory_coverage()
    assert report.is_valid, (
        f"Default inventory coverage join failed: "
        f"{[e.message for e in report.errors]}"
    )
    assert report.scenarios_validated == 17


def test_default_effect_fault_scope_is_exact_and_content_bound() -> None:
    """The M10 compatibility scope is exactly the two real fault consumers."""
    root = _project_root()
    with open(root / "evidence" / "m10-supported-boundaries.json") as fh:
        supported = json.load(fh)
    with open(root / "evidence" / "wbc-boundary-inventory.json") as fh:
        inventory = json.load(fh)

    scope = supported["effect_fault_coverage_required"]
    assert [row["identity"] for row in scope] == [
        "bc:execute_approval",
        "bc:gate_to_revise",
    ]

    inventory_by_identity = {
        identity: row
        for row in inventory["rows"]
        for identity in [_row_identity(row)]
        if identity is not None
    }
    supported_by_identity = {
        row["identity"]: row for row in supported["supported"]
    }
    for row in scope:
        identity = row["identity"]
        assert row["source_hash"] == _content_hash(inventory_by_identity[identity])
        assert row["support_hash"] == _content_hash(supported_by_identity[identity])
    assert supported["meta"]["effect_fault_coverage_scope_hash"] == _content_hash(scope)


def test_default_matrix_status_is_reconciled() -> None:
    """Step 18A: the matrix status is no longer 'provisional'."""
    matrix_path = _project_root() / "evidence" / "m10-f01-f17-fault-matrix.json"
    with open(str(matrix_path)) as fh:
        data = json.load(fh)
    assert data.get("status") == "reconciled", (
        f"Matrix status is {data.get('status')!r}, expected 'reconciled'"
    )


def test_default_matrix_refs_are_populated() -> None:
    """Every default scenario has at least one non-empty inventory_row_ref."""
    matrix_path = _project_root() / "evidence" / "m10-f01-f17-fault-matrix.json"
    with open(str(matrix_path)) as fh:
        data = json.load(fh)
    for s in data["scenarios"]:
        refs = s.get("inventory_row_refs", [])
        assert isinstance(refs, list) and len(refs) >= 1, (
            f"Scenario {s['id']} has empty inventory_row_refs"
        )


def test_inventory_coverage_orphan_ref_rejected() -> None:
    """A scenario ref absent from the inventory is an orphan."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:does_not_exist"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[{"identity": "bc:real_one", "row_kind": "boundary_contract"}],
        supported_rows=[{"identity": "bc:real_one", "row_kind": "boundary_contract"}],
        scenarios=scenarios,
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any("orphan" in e.message.lower() for e in report.errors), (
        f"Expected orphan error, got: {[e.message for e in report.errors]}"
    )


def test_inventory_coverage_missing_boundary_contract_rejected() -> None:
    """A supported boundary contract with no scenario coverage is rejected."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:covered"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "bc:uncovered", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "bc:uncovered", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any(
        "no fault-matrix coverage" in e.message for e in report.errors
    ), f"Expected missing-coverage error, got: {[e.message for e in report.errors]}"


def test_inventory_coverage_deferred_ref_rejected() -> None:
    """A scenario may not reference a deferred (action-off) row."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:covered", "bc:deferred_one"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "bc:deferred_one", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
        ],
        deferred_rows=[
            {"identity": "bc:deferred_one", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any(
        "deferred" in e.message.lower() for e in report.errors
    ), f"Expected deferred error, got: {[e.message for e in report.errors]}"


def test_inventory_coverage_unsupported_ref_rejected() -> None:
    """A scenario may not reference a non-supported inventory row."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:covered", "bc:unsupported"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "bc:unsupported", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any(
        "non-supported" in e.message.lower() for e in report.errors
    ), f"Expected unsupported error, got: {[e.message for e in report.errors]}"


def test_inventory_coverage_valid_when_all_refs_supported() -> None:
    """A fully-covered matrix with all refs supported is valid."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:covered"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert report.is_valid, (
        f"Expected valid coverage, got: {[e.message for e in report.errors]}"
    )


def test_inventory_coverage_step_id_ref_resolves() -> None:
    """References can target step_id form (me:<id>) as well as boundary_id."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["me:step_one", "bc:covered"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "boundary_id": "covered", "row_kind": "boundary_contract"},
            {"identity": "me:step_one", "step_id": "step_one", "row_kind": "manifest_entry"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "me:step_one", "row_kind": "manifest_entry"},
        ],
        scenarios=scenarios,
        effect_required=["bc:covered", "me:step_one"],
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert report.is_valid, (
        f"Expected valid coverage with step_id ref, got: {[e.message for e in report.errors]}"
    )


def test_inventory_coverage_runtime_module_not_required() -> None:
    """runtime_module rows (non-mutating) are not required to have coverage."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:covered"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "rm:unreferenced", "row_kind": "runtime_module"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "rm:unreferenced", "row_kind": "runtime_module"},
        ],
        scenarios=scenarios,
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert report.is_valid, (
        f"Expected valid coverage (runtime_module not required), "
        f"got: {[e.message for e in report.errors]}"
    )


def test_supported_evidence_boundary_does_not_require_effect_fault_ref() -> None:
    """WBC support does not implicitly make an evidence boundary an effect."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:real_effect"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {
                "identity": "bc:real_effect",
                "row_kind": "boundary_contract",
            },
            {
                "identity": "bc:evidence_only",
                "row_kind": "boundary_contract",
            },
        ],
        supported_rows=[
            {"identity": "bc:real_effect", "row_kind": "boundary_contract"},
            {"identity": "bc:evidence_only", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
        effect_required=["bc:real_effect"],
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert report.is_valid, [error.message for error in report.errors]


def test_declared_effect_boundary_without_scenario_is_rejected() -> None:
    """Adding a real effect to the declared scope requires matrix coverage."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:covered"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "bc:new_effect", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:covered", "row_kind": "boundary_contract"},
            {"identity": "bc:new_effect", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
        effect_required=["bc:covered", "bc:new_effect"],
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any(
        "Declared effect boundary 'bc:new_effect' has no fault-matrix coverage"
        in error.message
        for error in report.errors
    )


def test_undeclared_supported_boundary_ref_is_rejected_as_proxy_coverage() -> None:
    """A dummy ref cannot launder an evidence-only boundary into F coverage."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:real_effect", "bc:evidence_only"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:real_effect", "row_kind": "boundary_contract"},
            {"identity": "bc:evidence_only", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:real_effect", "row_kind": "boundary_contract"},
            {"identity": "bc:evidence_only", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
        effect_required=["bc:real_effect"],
    )
    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any(
        "not declared effect-fault-applicable" in error.message
        for error in report.errors
    )


def test_effect_fault_scope_hash_drift_is_visible() -> None:
    """Changing a bound source row without regeneration fails closed."""
    scenarios = [_minimal_valid_scenario("F01")]
    scenarios[0]["inventory_row_refs"] = ["bc:real_effect"]
    matrix, inventory, supported = _coverage_artifacts(
        inventory_rows=[
            {"identity": "bc:real_effect", "row_kind": "boundary_contract"},
        ],
        supported_rows=[
            {"identity": "bc:real_effect", "row_kind": "boundary_contract"},
        ],
        scenarios=scenarios,
        effect_required=["bc:real_effect"],
    )
    with open(inventory) as fh:
        changed_inventory = json.load(fh)
    changed_inventory["rows"][0]["producer_path"] = "changed.py"
    inventory.write_text(json.dumps(changed_inventory), encoding="utf-8")

    report = validate_inventory_coverage(matrix, inventory, supported)
    assert not report.is_valid
    assert any(
        error.field == "effect_fault_coverage_required.source_hash"
        and "source hash drifted" in error.message
        for error in report.errors
    )
