from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from scripts.validate_native_representation_conformance import validate_conformance_ledger


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _write_evidence_bundle_fixture(path: Path, records: list[dict[str, Any]]) -> None:
    _write_full_evidence_bundle_fixture(path, records=records)


def _write_full_evidence_bundle_fixture(
    path: Path,
    *,
    records: list[dict[str, Any]],
    boundary_contract_records: list[dict[str, Any]] | None = None,
    boundary_receipt_records: list[dict[str, Any]] | None = None,
    boundary_semantic_health_records: list[dict[str, Any]] | None = None,
    boundary_phase_result_records: list[dict[str, Any]] | None = None,
) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.evidence_bundle.v1",
                "records": records,
                "boundary_contract_records": boundary_contract_records or [],
                "boundary_receipt_records": boundary_receipt_records or [],
                "boundary_semantic_health_records": boundary_semantic_health_records or [],
                "boundary_phase_result_records": boundary_phase_result_records or [],
            }
        ),
        encoding="utf-8",
    )


def _checker_evidence_record(
    *,
    repo_root: Path,
    row_id: str,
    semantic_carrier: str,
    carrier_path: str,
    proof_artifact_path: str,
    policy_object: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "row_id": row_id,
        "semantic_carrier": semantic_carrier,
        "kind": "source_checker",
        "checker": "tests.final_conformance_evidence",
        "carrier_path": carrier_path,
        "carrier_sha256": _sha256(repo_root / carrier_path),
        "proof_artifact_path": proof_artifact_path,
        "proof_artifact_sha256": _sha256(repo_root / proof_artifact_path),
    }
    if policy_object is not None:
        record["policy_object"] = policy_object
    else:
        record["source_span"] = {
            "path": carrier_path,
            "start_line": 1,
            "end_line": 1,
        }
    return record


def _write_traceability_fixture(path: Path, row_id: str = "row-one") -> None:
    _write_traceability_boundary_fixture(path, row_id=row_id)


def _write_traceability_boundary_fixture(
    path: Path,
    *,
    row_id: str = "row-one",
    boundary_effects_required: list[str] | None = None,
    boundary_contract_ids: list[str] | None = None,
) -> None:
    row: dict[str, Any] = {"id": row_id, "proof_artifacts": ["source_excerpt"]}
    if boundary_effects_required is not None:
        row["boundary_effects_required"] = boundary_effects_required
        row["boundary_contract_ids"] = boundary_contract_ids or []
    path.write_text(
        yaml.safe_dump(
            {
                "boundary_effect_values": [
                    "artifact",
                    "state_history",
                    "receipt",
                    "phase_result",
                    "authority",
                    "reducer",
                    "external_effect",
                ],
                "final_conformance_gate": {
                    "machine_readable_report": {
                        "schema": "arnold.megaplan_native_representation.conformance.v1",
                        "row_status_values": ["implemented", "deferred"],
                        "implemented_semantic_carriers": [
                            "canonical_source",
                            "declared_policy",
                            "audited_pure_phase_body",
                        ],
                        "deferred_semantic_carriers": ["explicit_deferral"],
                        "carrier_evidence_suffixes": {
                            "canonical_source": [".pypeline"],
                            "audited_pure_phase_body": [".py"],
                            "declared_policy": [".pypeline", ".py", ".yaml", ".yml", ".json", ".md"],
                        },
                        "required_row_fields": [
                            "id",
                            "status",
                            "semantic_carrier",
                            "proof_categories",
                            "proof_artifacts",
                        ],
                        "implemented_required_row_fields": ["carrier_evidence"],
                        "deferred_required_row_fields": [
                            "downstream_owner",
                            "blocking_proof",
                            "reason",
                        ],
                    }
                },
                "rows": [row],
            }
        ),
        encoding="utf-8",
    )


def _write_conformance_fixture(
    path: Path,
    *,
    row_id: str = "row-one",
    semantic_carrier: str,
    carrier_evidence: list[str],
    proof_artifacts: list[str],
) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": row_id,
                        "status": "implemented",
                        "semantic_carrier": semantic_carrier,
                        "carrier_evidence": carrier_evidence,
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": proof_artifacts,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _legacy_path_status_only_contract_would_pass(
    repo_root: Path,
    *,
    semantic_carrier: str,
    carrier_evidence: list[str],
    proof_artifacts: list[str],
) -> bool:
    # This models the old false-pass contract: approved status/carrier plus existing paths.
    implemented_carriers = {
        "canonical_source",
        "declared_policy",
        "audited_pure_phase_body",
    }
    return semantic_carrier in implemented_carriers and all(
        (repo_root / relative_path).is_file()
        for relative_path in [*carrier_evidence, *proof_artifacts]
    )


def _boundary_contract_record(
    *,
    repo_root: Path,
    row_id: str,
    contract_id: str,
    covered_effects: list[str],
    contract_path: str,
    policy_object: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "row_id": row_id,
        "contract_id": contract_id,
        "covered_effects": covered_effects,
        "contract_path": contract_path,
        "contract_sha256": _sha256(repo_root / contract_path),
    }
    if policy_object is not None:
        record["policy_object"] = policy_object
    else:
        record["source_span"] = {
            "path": contract_path,
            "start_line": 1,
            "end_line": 1,
        }
    return record


def _boundary_receipt_record(
    *,
    repo_root: Path,
    row_id: str,
    contract_id: str,
    covered_effects: list[str],
    receipt_path: str,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "contract_id": contract_id,
        "covered_effects": covered_effects,
        "receipt_path": receipt_path,
        "receipt_sha256": _sha256(repo_root / receipt_path),
    }


def _boundary_semantic_health_record(
    *,
    repo_root: Path,
    row_id: str,
    contract_id: str,
    covered_effects: list[str],
    proof_artifact_path: str,
    status: str = "healthy",
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "contract_id": contract_id,
        "covered_effects": covered_effects,
        "proof_artifact_path": proof_artifact_path,
        "proof_artifact_sha256": _sha256(repo_root / proof_artifact_path),
        "status": status,
    }


def _boundary_phase_result_record(
    *,
    repo_root: Path,
    row_id: str,
    contract_id: str,
    covered_effects: list[str],
    phase_result_path: str,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "contract_id": contract_id,
        "covered_effects": covered_effects,
        "phase_result_path": phase_result_path,
        "phase_result_sha256": _sha256(repo_root / phase_result_path),
    }


def test_validator_accepts_current_row_matched_checker_evidence(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    proof_path = tmp_path / "proof.md"
    carrier_path = tmp_path / "carrier.pypeline"
    proof_path.write_text("# Proof\n", encoding="utf-8")
    carrier_path.write_text("# carrier\n", encoding="utf-8")
    _write_traceability_fixture(traceability_path)
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier.pypeline",
                proof_artifact_path="proof.md",
            )
        ],
    )
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    assert _legacy_path_status_only_contract_would_pass(
        tmp_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )
    assert (
        validate_conformance_ledger(
            repo_root=tmp_path,
            conformance_path=conformance_path,
            traceability_path=traceability_path,
            evidence_bundle_path=evidence_bundle_path,
        )
        == []
    )


def test_validator_rejects_path_only_implemented_proof(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_traceability_fixture(traceability_path)
    _write_evidence_bundle_fixture(evidence_bundle_path, [])
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    assert _legacy_path_status_only_contract_would_pass(
        tmp_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )
    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("implemented rows require current checker evidence" in error for error in errors)
    assert any(
        "carrier_evidence path 'carrier.pypeline' lacks matching current checker evidence" in error
        for error in errors
    )


def test_validator_rejects_stale_checker_evidence(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    carrier_path = tmp_path / "carrier.pypeline"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    carrier_path.write_text("# carrier\n", encoding="utf-8")
    _write_traceability_fixture(traceability_path)
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier.pypeline",
                proof_artifact_path="proof.md",
            )
        ],
    )
    carrier_path.write_text("# carrier changed\n", encoding="utf-8")
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    assert _legacy_path_status_only_contract_would_pass(
        tmp_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )
    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any(
        "lacks current checker evidence with matching hashes and proof artifacts" in error
        for error in errors
    )


def test_validator_rejects_mismatched_checker_evidence(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "other-proof.md").write_text("# Other proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_traceability_fixture(traceability_path)
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier.pypeline",
                proof_artifact_path="other-proof.md",
            )
        ],
    )
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    assert _legacy_path_status_only_contract_would_pass(
        tmp_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )
    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any(
        "lacks current checker evidence with matching hashes and proof artifacts" in error
        for error in errors
    )


def test_validator_rejects_historical_report_as_current_authority(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    docs_dir = tmp_path / "docs/arnold"
    docs_dir.mkdir(parents=True)
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    report_path = docs_dir / "megaplan-native-representation-conformance-report.md"
    report_path.write_text("# Historical report\n", encoding="utf-8")
    _write_traceability_fixture(traceability_path)
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="declared_policy",
                carrier_path="docs/arnold/megaplan-native-representation-conformance-report.md",
                proof_artifact_path="proof.md",
                policy_object="historical.report",
            )
        ],
    )
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="declared_policy",
        carrier_evidence=["docs/arnold/megaplan-native-representation-conformance-report.md"],
        proof_artifacts=["proof.md"],
    )

    assert _legacy_path_status_only_contract_would_pass(
        tmp_path,
        semantic_carrier="declared_policy",
        carrier_evidence=["docs/arnold/megaplan-native-representation-conformance-report.md"],
        proof_artifacts=["proof.md"],
    )
    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("historical conformance report as authority" in error for error in errors)


def test_validator_accepts_boundary_evidence_for_boundary_crossing_row(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    (tmp_path / "boundary-contract.py").write_text("BOUNDARY = True\n", encoding="utf-8")
    (tmp_path / "receipt.json").write_text("{\"receipt\": true}\n", encoding="utf-8")
    (tmp_path / "semantic-health.md").write_text("healthy\n", encoding="utf-8")
    (tmp_path / "phase_result.json").write_text("{\"exit_kind\": \"success\"}\n", encoding="utf-8")
    _write_traceability_boundary_fixture(
        traceability_path,
        boundary_effects_required=["state_history", "receipt", "phase_result"],
        boundary_contract_ids=["prep_to_plan"],
    )
    _write_full_evidence_bundle_fixture(
        evidence_bundle_path,
        records=[
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier.pypeline",
                proof_artifact_path="proof.md",
            )
        ],
        boundary_contract_records=[
            _boundary_contract_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history", "receipt", "phase_result"],
                contract_path="boundary-contract.py",
            )
        ],
        boundary_receipt_records=[
            _boundary_receipt_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["receipt"],
                receipt_path="receipt.json",
            )
        ],
        boundary_semantic_health_records=[
            _boundary_semantic_health_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history", "receipt", "phase_result"],
                proof_artifact_path="semantic-health.md",
            )
        ],
        boundary_phase_result_records=[
            _boundary_phase_result_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history", "phase_result"],
                phase_result_path="phase_result.json",
            )
        ],
    )
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    assert (
        validate_conformance_ledger(
            repo_root=tmp_path,
            conformance_path=conformance_path,
            traceability_path=traceability_path,
            evidence_bundle_path=evidence_bundle_path,
        )
        == []
    )


def test_validator_rejects_boundary_row_without_coherent_boundary_bundle(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    (tmp_path / "boundary-contract.py").write_text("BOUNDARY = True\n", encoding="utf-8")
    _write_traceability_boundary_fixture(
        traceability_path,
        boundary_effects_required=["state_history", "receipt", "phase_result"],
        boundary_contract_ids=["prep_to_plan"],
    )
    _write_full_evidence_bundle_fixture(
        evidence_bundle_path,
        records=[
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier.pypeline",
                proof_artifact_path="proof.md",
            )
        ],
        boundary_contract_records=[
            _boundary_contract_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history", "receipt", "phase_result"],
                contract_path="boundary-contract.py",
            )
        ],
    )
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("lacks coherent boundary receipt evidence" in error for error in errors)
    assert any("lacks coherent boundary semantic-health evidence" in error for error in errors)
    assert any("lacks coherent boundary phase/result evidence" in error for error in errors)


def test_validator_rejects_boundary_evidence_with_wrong_contract_or_effect_coverage(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    (tmp_path / "boundary-contract.py").write_text("BOUNDARY = True\n", encoding="utf-8")
    (tmp_path / "receipt.json").write_text("{\"receipt\": true}\n", encoding="utf-8")
    (tmp_path / "semantic-health.md").write_text("healthy\n", encoding="utf-8")
    (tmp_path / "phase_result.json").write_text("{\"exit_kind\": \"success\"}\n", encoding="utf-8")
    _write_traceability_boundary_fixture(
        traceability_path,
        boundary_effects_required=["state_history", "receipt", "phase_result"],
        boundary_contract_ids=["prep_to_plan"],
    )
    _write_full_evidence_bundle_fixture(
        evidence_bundle_path,
        records=[
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier.pypeline",
                proof_artifact_path="proof.md",
            )
        ],
        boundary_contract_records=[
            _boundary_contract_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="megaplan:suspension",
                covered_effects=["state_history", "receipt", "phase_result"],
                contract_path="boundary-contract.py",
            )
        ],
        boundary_receipt_records=[
            _boundary_receipt_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history"],
                receipt_path="receipt.json",
            )
        ],
        boundary_semantic_health_records=[
            _boundary_semantic_health_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history", "receipt", "phase_result"],
                proof_artifact_path="semantic-health.md",
            )
        ],
        boundary_phase_result_records=[
            _boundary_phase_result_record(
                repo_root=tmp_path,
                row_id="row-one",
                contract_id="prep_to_plan",
                covered_effects=["state_history"],
                phase_result_path="phase_result.json",
            )
        ],
    )
    _write_conformance_fixture(
        conformance_path,
        semantic_carrier="canonical_source",
        carrier_evidence=["carrier.pypeline"],
        proof_artifacts=["proof.md"],
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("contract 'prep_to_plan' lacks coherent boundary contract evidence" in error for error in errors)
    assert any("contract 'prep_to_plan' lacks coherent boundary receipt evidence" in error for error in errors)
    assert any("contract 'prep_to_plan' lacks coherent boundary phase/result evidence" in error for error in errors)
