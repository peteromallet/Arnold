from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from scripts.generate_native_representation_evidence import (
    SPLIT_OUTCOME_CATEGORIES,
    generate_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[3]
CONFORMANCE_PATH = ROOT / "docs/arnold/megaplan-native-representation-conformance.yaml"
TRACEABILITY_PATH = ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"
SCENARIOS_PATH = ROOT / "docs/arnold/megaplan-native-representation-scenarios.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def test_split_outcome_manifest_covers_required_categories_with_executable_records() -> None:
    payload = _load_yaml(SCENARIOS_PATH)
    scenario_rows = payload["scenarios"]
    scenario_ids = {scenario["id"] for scenario in scenario_rows}
    rows_by_scenario = {
        scenario["id"]: set(scenario["rows"])
        for scenario in scenario_rows
    }

    assert payload["split_outcome_categories"] == list(SPLIT_OUTCOME_CATEGORIES)
    assert isinstance(payload["split_outcome_refresh_rule"], str) and payload["split_outcome_refresh_rule"]
    assert isinstance(payload["split_outcome_authority_rule"], str) and payload["split_outcome_authority_rule"]

    records = payload["split_outcome_records"]
    assert isinstance(records, list)
    assert len(records) == len(SPLIT_OUTCOME_CATEGORIES)

    covered_categories: set[str] = set()
    for record in records:
        record_id = record["id"]
        assert record["route_authority"] is False, record_id
        assert record["expected_outcomes"], record_id
        assert record["scenario_refs"], record_id
        assert set(record["scenario_refs"]) <= scenario_ids, record_id
        assert record["row_ids"], record_id
        allowed_rows = {
            row_id
            for scenario_id in record["scenario_refs"]
            for row_id in rows_by_scenario[scenario_id]
        }
        assert set(record["row_ids"]) <= allowed_rows, record_id
        assert record["executable_modules"], record_id
        for module in record["executable_modules"]:
            module_path = ROOT / module["path"]
            assert module_path.is_file(), (record_id, module["path"])
            assert module["case_ids"], (record_id, module["path"])
        for fixture_path in record["deterministic_fixture_paths"]:
            assert (ROOT / fixture_path).is_file(), (record_id, fixture_path)
        for source_path in record["source_warrant_paths"]:
            assert (ROOT / source_path).is_file(), (record_id, source_path)
        covered_categories.update(record["path_classes"])

    assert covered_categories == set(SPLIT_OUTCOME_CATEGORIES)


def test_generate_evidence_bundle_emits_stable_split_outcome_hashes() -> None:
    first = generate_evidence_bundle(
        conformance_path=CONFORMANCE_PATH,
        traceability_path=TRACEABILITY_PATH,
        repo_root=ROOT,
    )
    second = generate_evidence_bundle(
        conformance_path=CONFORMANCE_PATH,
        traceability_path=TRACEABILITY_PATH,
        repo_root=ROOT,
    )

    assert first["scenario_hashes"] == second["scenario_hashes"]

    payload = _load_yaml(SCENARIOS_PATH)
    records = payload["split_outcome_records"]
    hashes_by_id = {record["record_id"]: record for record in first["scenario_hashes"]}

    assert set(hashes_by_id) == {record["id"] for record in records}
    for record in records:
        evidence = hashes_by_id[record["id"]]
        assert evidence["path_classes"] == sorted(set(record["path_classes"]))
        assert evidence["scenario_refs"] == sorted(set(record["scenario_refs"]))
        assert evidence["row_ids"] == sorted(set(record["row_ids"]))
        assert evidence["expected_outcomes"] == sorted(set(record["expected_outcomes"]))
        assert evidence["route_authority"] is False
        assert evidence["scenario_manifest_path"] == (
            "docs/arnold/megaplan-native-representation-scenarios.yaml"
        )
        assert evidence["scenario_manifest_sha256"] == _sha256(SCENARIOS_PATH)
        assert evidence["record_sha256"].startswith("sha256:")
        for module in evidence["executable_modules"]:
            assert module["sha256"] == _sha256(ROOT / module["path"])
            assert module["case_ids"]
        for entry in evidence["deterministic_fixture_hashes"]:
            assert entry["sha256"] == _sha256(ROOT / entry["path"])
        for entry in evidence["source_warrant_hashes"]:
            assert entry["sha256"] == _sha256(ROOT / entry["path"])


def test_split_outcome_hashes_do_not_compete_with_source_or_contract_authority() -> None:
    bundle = generate_evidence_bundle(
        conformance_path=CONFORMANCE_PATH,
        traceability_path=TRACEABILITY_PATH,
        repo_root=ROOT,
    )

    scenario_manifest_path = "docs/arnold/megaplan-native-representation-scenarios.yaml"
    approved_carrier_paths = {entry["path"] for entry in bundle["approved_carriers"]}
    checker_carrier_paths = {entry["carrier_path"] for entry in bundle["records"]}
    contract_paths = {entry["contract_path"] for entry in bundle["boundary_contract_records"]}

    assert scenario_manifest_path not in approved_carrier_paths
    assert scenario_manifest_path not in checker_carrier_paths
    assert scenario_manifest_path not in contract_paths
    assert all(record["route_authority"] is False for record in bundle["scenario_hashes"])
