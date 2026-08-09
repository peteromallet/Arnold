from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from arnold_pipelines.megaplan.chain import ChainSpec
from scripts.validate_native_representation_conformance import validate_conformance_ledger


ROOT = Path(__file__).resolve().parents[3]
TRACEABILITY_PATH = ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"
SCENARIOS_PATH = ROOT / "docs/arnold/megaplan-native-representation-scenarios.yaml"
ALIGNMENT_PLAN_PATH = ROOT / "docs/arnold/megaplan-native-representation-alignment-plan.md"
REVIEW_EXECUTION_PATH = ROOT / "docs/arnold/megaplan-native-representation-review-execution.md"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _write_evidence_bundle_fixture(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.evidence_bundle.v1",
                "records": records,
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
        "checker": "tests.native_representation_alignment",
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


def _write_conformance_traceability_fixture(path: Path, row_ids: list[str]) -> None:
    path.write_text(
        yaml.safe_dump(
            {
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
                "rows": [
                    {"id": row_id, "proof_artifacts": ["source_excerpt"]}
                    for row_id in row_ids
                ],
            }
        ),
        encoding="utf-8",
    )


def test_traceability_artifact_covers_alignment_matrix_rows() -> None:
    payload = _load_yaml(TRACEABILITY_PATH)
    assert payload["schema"] == "arnold.megaplan_native_representation.traceability.v1"
    assert payload["target_report"] == "docs/arnold/megaplan-native-representation-report.md"
    rows = payload["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 31

    alignment_text = ALIGNMENT_PLAN_PATH.read_text(encoding="utf-8")
    ids: set[str] = set()
    requirements: set[str] = set()
    allowed_statuses = set(payload["status_values"])
    for row in rows:
        assert isinstance(row, dict)
        row_id = row.get("id")
        assert isinstance(row_id, str)
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", row_id)
        assert row_id not in ids
        ids.add(row_id)

        requirement = row.get("requirement")
        assert isinstance(requirement, str) and requirement
        assert requirement not in requirements
        requirements.add(requirement)
        assert f"| {requirement} |" in alignment_text

        assert row.get("status") in allowed_statuses
        assert row["status"] != "missing"
        for key in (
            "owners",
            "milestones",
            "proof_artifacts",
            "false_pass_guard",
            "negative_invariant",
        ):
            assert key in row, row_id
        assert row["owners"]
        assert row["milestones"]
        assert row["proof_artifacts"]
        assert isinstance(row["false_pass_guard"], str) and row["false_pass_guard"]
        assert isinstance(row["negative_invariant"], str) and row["negative_invariant"]


def test_fixed_scenarios_reference_traceability_rows() -> None:
    traceability = _load_yaml(TRACEABILITY_PATH)
    scenarios = _load_yaml(SCENARIOS_PATH)
    assert scenarios["schema"] == "arnold.megaplan_native_representation.scenarios.v1"
    assert scenarios["traceability"] == "docs/arnold/megaplan-native-representation-traceability.yaml"

    row_ids = {row["id"] for row in traceability["rows"]}
    scenario_rows = scenarios["scenarios"]
    assert isinstance(scenario_rows, list)
    assert len(scenario_rows) == 15
    assert [scenario["id"] for scenario in scenario_rows] == [
        f"D{index}-{suffix}"
        for index, suffix in enumerate(
            [
                "prep-plan",
                "critique",
                "gate-preflight",
                "gate-revise",
                "tiebreaker",
                "finalize",
                "execute-dag",
                "execute-gates",
                "review-fanout",
                "review-caps",
                "human-control",
                "runtime-trace",
                "policy-platform",
                "compiler-authoring",
                "handler-extraction",
            ],
            start=1,
        )
    ]

    referenced_rows: set[str] = set()
    for scenario in scenario_rows:
        assert scenario["rows"], scenario["id"]
        unknown = set(scenario["rows"]) - row_ids
        assert not unknown, scenario["id"]
        referenced_rows.update(scenario["rows"])
        assert scenario["required_cases"], scenario["id"]
        assert scenario["topology_requirements"], scenario["id"]
        assert isinstance(scenario["false_pass_guard"], str)
        assert scenario["false_pass_guard"]

    assert row_ids - referenced_rows == set()


def test_chain_handoff_gates_are_executable_and_closeout_owned() -> None:
    payload = _load_yaml(TRACEABILITY_PATH)
    gates = payload.get("chain_handoff_gates")
    assert isinstance(gates, list)
    assert [gate["id"] for gate in gates] == [
        "completion-to-composition",
        "completion-to-platform",
        "composition-to-platform",
    ]

    for gate in gates:
        assert gate["require_manifest"] is True
        upstream = gate["upstream_chain"]
        downstream = ROOT / gate["downstream_chain"]
        closeout_brief = ROOT / gate["closeout_brief"]
        assert downstream.is_file(), gate["id"]
        assert closeout_brief.is_file(), gate["id"]

        downstream_spec = _load_yaml(downstream)
        matching_preconditions = [
            precondition
            for precondition in downstream_spec.get("launch_preconditions", [])
            if precondition.get("kind") == "chain_completed"
            and precondition.get("name") == gate["required_precondition"]
        ]
        assert len(matching_preconditions) == 1, gate["id"]
        precondition = matching_preconditions[0]
        assert precondition["chain"] == upstream
        assert precondition.get("require_manifest") is True

        closeout_text = closeout_brief.read_text(encoding="utf-8")
        assert gate["closeout_milestone"] in {
            milestone
            for row in payload["rows"]
            for milestone in row["milestones"]
        }
        for deliverable in gate["closeout_deliverables"]:
            assert deliverable in closeout_text, (gate["id"], deliverable)
        assert "megaplan chain manifest" in closeout_text, gate["id"]


def test_final_conformance_gate_is_milestone_validation_stage() -> None:
    payload = _load_yaml(TRACEABILITY_PATH)
    gate = payload.get("final_conformance_gate")
    assert isinstance(gate, dict)
    assert gate["id"] == "platform-final-report-conformance"
    assert gate["chain"] == ".megaplan/initiatives/native-platform-followup/chain.yaml"
    assert gate["closeout_milestone"] == "platform-m6"

    chain = ROOT / gate["chain"]
    closeout_brief = ROOT / gate["closeout_brief"]
    assert chain.is_file()
    assert closeout_brief.is_file()
    machine_report = gate["machine_readable_report"]
    assert isinstance(machine_report, dict)
    chain_payload = _load_yaml(chain)
    closeout_label = gate["closeout_brief"].split("/")[-1].removesuffix(".md")
    matching_milestones = [
        milestone
        for milestone in chain_payload["milestones"]
        if milestone["label"] == closeout_label
    ]
    assert matching_milestones
    validation_stages = matching_milestones[0].get("validate")
    assert isinstance(validation_stages, list)
    assert validation_stages == [
        {
            "kind": "final_conformance_gate",
            "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
            "conformance": machine_report["path"],
            "validator": machine_report["validator"],
            "proof_map": ".megaplan/initiatives/native-platform-followup/proof-map.json",
        }
    ]
    parsed_chain = ChainSpec.from_dict(chain_payload)
    parsed_milestone = next(
        milestone for milestone in parsed_chain.milestones if milestone.label == closeout_label
    )
    assert parsed_milestone.validate[0].kind == "final_conformance_gate"
    assert parsed_milestone.validate[0].conformance == machine_report["path"]

    closeout_text = closeout_brief.read_text(encoding="utf-8")
    assert gate["closeout_milestone"] in {
        milestone
        for row in payload["rows"]
        for milestone in row["milestones"]
    }
    for deliverable in gate["closeout_deliverables"]:
        assert deliverable in closeout_text, deliverable
    assert machine_report["path"] in gate["closeout_deliverables"]
    assert machine_report["path"] in closeout_text
    assert machine_report["schema"] in closeout_text
    assert (ROOT / machine_report["validator"]).is_file()
    assert machine_report["validator"] in closeout_text
    assert machine_report["row_status_values"] == ["implemented", "deferred"]
    assert machine_report["implemented_semantic_carriers"] == [
        "canonical_source",
        "declared_policy",
        "audited_pure_phase_body",
    ]
    assert machine_report["deferred_semantic_carriers"] == ["explicit_deferral"]
    for carrier in machine_report["implemented_semantic_carriers"]:
        assert carrier in closeout_text, carrier
    for carrier in machine_report["deferred_semantic_carriers"]:
        assert carrier in closeout_text, carrier
    suffixes = machine_report["carrier_evidence_suffixes"]
    assert suffixes == {
        "canonical_source": [".pypeline"],
        "audited_pure_phase_body": [".py"],
        "declared_policy": [".pypeline", ".py", ".yaml", ".yml", ".json", ".md"],
    }
    for carrier, allowed_suffixes in suffixes.items():
        assert carrier in closeout_text, carrier
        for suffix in allowed_suffixes:
            assert suffix in closeout_text, suffix
    for field in machine_report["required_row_fields"]:
        assert field in closeout_text, field
    for field in machine_report["implemented_required_row_fields"]:
        assert field in closeout_text, field
    for field in machine_report["deferred_required_row_fields"]:
        assert field in closeout_text, field
    for section in gate["required_report_sections"]:
        assert section in closeout_text, section
    assert "megaplan chain manifest" in closeout_text


def test_final_conformance_yaml_validator_accepts_complete_ledger(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof-one.md").write_text("# Proof one\n", encoding="utf-8")
    (tmp_path / "carrier-one.pypeline").write_text("# carrier one\n", encoding="utf-8")
    (tmp_path / "proof-two.md").write_text("# Proof two\n", encoding="utf-8")
    (tmp_path / "blocking-proof.md").write_text("# Blocking proof\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one", "row-two"])
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier-one.pypeline",
                proof_artifact_path="proof-one.md",
            )
        ],
    )
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier-one.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof-one.md"],
                    },
                    {
                        "id": "row-two",
                        "status": "deferred",
                        "semantic_carrier": "explicit_deferral",
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof-two.md"],
                        "downstream_owner": "future-platform-hardening",
                        "blocking_proof": ["blocking-proof.md"],
                        "reason": "operator prerequisite",
                    },
                ],
            }
        ),
        encoding="utf-8",
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


def test_final_conformance_yaml_validator_rejects_false_pass(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    _write_conformance_traceability_fixture(traceability_path, ["row-one", "row-two"])
    _write_evidence_bundle_fixture(evidence_bundle_path, [])
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "deferred",
                        "semantic_carrier": "handler",
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["missing-proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("missing deferred fields" in error for error in errors)
    assert any("deferred semantic_carrier must be one of" in error for error in errors)
    assert any("path does not exist: missing-proof.md" in error for error in errors)
    assert any("cover every traceability id in order" in error for error in errors)


def test_final_conformance_yaml_validator_requires_carrier_evidence_for_implemented(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
    _write_evidence_bundle_fixture(evidence_bundle_path, [])
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "declared_policy",
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("missing implemented fields: carrier_evidence" in error for error in errors)


def test_final_conformance_yaml_validator_rejects_non_code_canonical_source(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="report.md",
                proof_artifact_path="proof.md",
            )
        ],
    )
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["report.md"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("canonical_source requires one of ['.pypeline']" in error for error in errors)


def test_final_conformance_yaml_validator_accepts_declared_policy_artifact(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "policy.yaml").write_text("policy: true\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="declared_policy",
                carrier_path="policy.yaml",
                proof_artifact_path="proof.md",
                policy_object="policy.contract",
            )
        ],
    )
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "declared_policy",
                        "carrier_evidence": ["policy.yaml"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
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


def test_final_conformance_yaml_validator_requires_matching_checker_evidence(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
    _write_evidence_bundle_fixture(evidence_bundle_path, [])
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("implemented rows require current checker evidence" in error for error in errors)
    assert any("carrier_evidence path 'carrier.pypeline' lacks matching current checker evidence" in error for error in errors)


def test_final_conformance_yaml_validator_rejects_path_only_evidence_bundle_records(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
    evidence_bundle_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.evidence_bundle.v1",
                "records": [
                    {
                        "row_id": "row-one",
                        "semantic_carrier": "canonical_source",
                        "kind": "source_checker",
                        "checker": "tests.native_representation_alignment",
                        "carrier_path": "carrier.pypeline",
                        "proof_artifact_path": "proof.md",
                        "source_span": {
                            "path": "carrier.pypeline",
                            "start_line": 1,
                            "end_line": 1,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("carrier_sha256 must be a sha256:<hex> string" in error for error in errors)


def test_final_conformance_yaml_validator_rejects_stale_checker_evidence_hashes(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    carrier_path = tmp_path / "carrier.pypeline"
    carrier_path.write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
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


def test_final_conformance_yaml_validator_rejects_historical_reports_as_authority(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    docs_dir = tmp_path / "docs/arnold"
    docs_dir.mkdir(parents=True)
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    report_path = docs_dir / "megaplan-native-representation-conformance-report.md"
    report_path.write_text("# Historical report\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "declared_policy",
                        "carrier_evidence": [
                            "docs/arnold/megaplan-native-representation-conformance-report.md"
                        ],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("historical conformance report as authority" in error for error in errors)


def test_final_conformance_yaml_validator_uses_traceability_target_report(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    traceability = yaml.safe_load(traceability_path.read_text(encoding="utf-8"))
    traceability["target_report"] = "docs/arnold/custom-native-target.md"
    traceability_path.write_text(yaml.safe_dump(traceability), encoding="utf-8")
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/custom-native-target.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
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


def test_final_conformance_yaml_validator_rejects_stale_target_report(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    traceability = yaml.safe_load(traceability_path.read_text(encoding="utf-8"))
    traceability["target_report"] = "docs/arnold/custom-native-target.md"
    traceability_path.write_text(yaml.safe_dump(traceability), encoding="utf-8")
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any(
        "target_report must be 'docs/arnold/custom-native-target.md'" in error
        for error in errors
    )


def test_final_conformance_yaml_validator_requires_traceability_proof_categories(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    traceability = yaml.safe_load(traceability_path.read_text(encoding="utf-8"))
    traceability["rows"][0]["proof_artifacts"] = ["source_excerpt", "rendered_route"]
    traceability_path.write_text(yaml.safe_dump(traceability), encoding="utf-8")
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any(
        "proof_categories missing traceability labels: rendered_route" in error
        for error in errors
    )


def test_final_conformance_yaml_validator_rejects_unknown_proof_categories(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt", "typoed_label"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any(
        "proof_categories contains unknown labels: typoed_label" in error
        for error in errors
    )


def test_final_conformance_yaml_validator_uses_required_row_field_contract(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.pypeline").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    traceability = yaml.safe_load(traceability_path.read_text(encoding="utf-8"))
    traceability["final_conformance_gate"]["machine_readable_report"][
        "required_row_fields"
    ].append("reviewer_signoff")
    traceability_path.write_text(yaml.safe_dump(traceability), encoding="utf-8")
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any("missing required fields: reviewer_signoff" in error for error in errors)


def test_final_conformance_yaml_validator_uses_status_specific_field_contract(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof-one.md").write_text("# Proof one\n", encoding="utf-8")
    (tmp_path / "carrier-one.pypeline").write_text("# carrier one\n", encoding="utf-8")
    (tmp_path / "proof-two.md").write_text("# Proof two\n", encoding="utf-8")
    (tmp_path / "blocking-proof.md").write_text("# Blocking proof\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one", "row-two"])
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="canonical_source",
                carrier_path="carrier-one.pypeline",
                proof_artifact_path="proof-one.md",
            )
        ],
    )
    traceability = yaml.safe_load(traceability_path.read_text(encoding="utf-8"))
    machine_report = traceability["final_conformance_gate"]["machine_readable_report"]
    machine_report["implemented_required_row_fields"].append("implementation_notes")
    machine_report["deferred_required_row_fields"].append("deferral_review")
    traceability_path.write_text(yaml.safe_dump(traceability), encoding="utf-8")
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "canonical_source",
                        "carrier_evidence": ["carrier-one.pypeline"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof-one.md"],
                    },
                    {
                        "id": "row-two",
                        "status": "deferred",
                        "semantic_carrier": "explicit_deferral",
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof-two.md"],
                        "downstream_owner": "future-platform-hardening",
                        "blocking_proof": ["blocking-proof.md"],
                        "reason": "operator prerequisite",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_conformance_ledger(
        repo_root=tmp_path,
        conformance_path=conformance_path,
        traceability_path=traceability_path,
        evidence_bundle_path=evidence_bundle_path,
    )

    assert any(
        "missing implemented fields: implementation_notes" in error
        for error in errors
    )
    assert any("missing deferred fields: deferral_review" in error for error in errors)


def test_final_conformance_yaml_validator_uses_traceability_suffix_contract(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    evidence_bundle_path = tmp_path / "evidence.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "policy.custom").write_text("policy=true\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
    _write_evidence_bundle_fixture(
        evidence_bundle_path,
        [
            _checker_evidence_record(
                repo_root=tmp_path,
                row_id="row-one",
                semantic_carrier="declared_policy",
                carrier_path="policy.custom",
                proof_artifact_path="proof.md",
                policy_object="custom.policy",
            )
        ],
    )
    traceability = yaml.safe_load(traceability_path.read_text(encoding="utf-8"))
    traceability["final_conformance_gate"]["machine_readable_report"][
        "carrier_evidence_suffixes"
    ]["declared_policy"] = [".custom"]
    traceability_path.write_text(yaml.safe_dump(traceability), encoding="utf-8")
    conformance_path.write_text(
        yaml.safe_dump(
            {
                "schema": "arnold.megaplan_native_representation.conformance.v1",
                "target_report": "docs/arnold/megaplan-native-representation-report.md",
                "traceability": "docs/arnold/megaplan-native-representation-traceability.yaml",
                "rows": [
                    {
                        "id": "row-one",
                        "status": "implemented",
                        "semantic_carrier": "declared_policy",
                        "carrier_evidence": ["policy.custom"],
                        "proof_categories": ["source_excerpt"],
                        "proof_artifacts": ["proof.md"],
                    }
                ],
            }
        ),
        encoding="utf-8",
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


# ---------------------------------------------------------------------------
# T2: Row-status consistency check — markdown ↔ YAML drift detection
# ---------------------------------------------------------------------------

# Known status values from the traceability schema
_VALID_STATUSES = frozenset({"enabled", "implemented", "deferred", "missing"})

# Words that are too short/common to use as proof-drift signals
_PROOF_SKIP_WORDS = frozenset({"and", "or", "the", "for", "with", "test", "tests"})


def _split_markdown_table_row(stripped: str) -> list[str]:
    """Split a markdown pipe-table row into cells.

    Handles the ``| cell | cell | ... |`` format used in the alignment plan
    without assuming a fixed number of columns.  Leading / trailing pipes are
    stripped before splitting so the caller gets only the cell payloads.
    """
    inner = stripped
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [c.strip() for c in inner.split("|")]


def _parse_alignment_table(text: str) -> list[dict[str, str]]:
    """Parse the traceability matrix table from the alignment markdown.

    Returns one dict per data row with keys *requirement*, *status*, *proof_text*.
    The table is located inside the ``## Traceability Matrix`` section.
    """
    matrix_start = text.find("## Traceability Matrix")
    if matrix_start == -1:
        return []

    section = text[matrix_start:]
    header_map: dict[str, int] = {}
    rows: list[dict[str, str]] = []

    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| "):
            if header_map:
                break  # first non-table line after parsing header → end of table
            continue
        if "---" in stripped.split("|")[1] if stripped.startswith("|") else False:
            continue  # separator row

        cells = _split_markdown_table_row(stripped)

        # Detect header row by looking for the first column header
        if cells and "report requirement" in cells[0].strip().lower():
            for idx, cell in enumerate(cells):
                cell_lower = cell.strip().lower()
                first_word = cell_lower.split()[0] if cell_lower.split() else ""
                if first_word == "status":
                    header_map["status"] = idx
                elif "required proof" in cell_lower:
                    header_map["proof"] = idx
                elif "report requirement" in cell_lower:
                    header_map["requirement"] = idx
            continue

        if not header_map:
            continue

        rows.append(
            {
                "requirement": cells[header_map["requirement"]].strip()
                if header_map.get("requirement", -1) < len(cells)
                else "",
                "status": cells[header_map["status"]].strip()
                if header_map.get("status", -1) < len(cells)
                else "",
                "proof_text": cells[header_map["proof"]].strip()
                if header_map.get("proof", -1) < len(cells)
                else "",
            }
        )

    return rows


def _normalize_markdown_status(raw: str) -> str:
    """Extract the canonical status from a markdown status cell.

    Handles plain values (``enabled``) and annotated forms such as
    ``enabled (M3: … handler-purity-gated, unimplemented until structural tests land)``.
    """
    status = raw.strip()
    # Split on first parenthesis or dash to isolate the base status word
    for delim in (" (", "("):
        if delim in status:
            status = status.split(delim)[0].strip()
            break
    return status.lower()


def _proof_label_significant_words(label: str) -> list[str]:
    """Return significant (≥3 char, non-noise) words from a snake_case proof label."""
    words = [w for w in label.replace("_", " ").replace("/", " ").split() if len(w) >= 3]
    return [w.lower() for w in words if w.lower() not in _PROOF_SKIP_WORDS]


def test_markdown_yaml_status_proof_consistency() -> None:
    """Row-status consistency check: fails on status, proof, or deferral drift
    between the alignment markdown and traceability YAML.

    Parses both artifacts, matches rows by requirement text, and verifies:

    * The status value agrees (normalising away markdown annotations).
    * Every YAML ``proof_artifacts`` label has a discernible trace in the
      markdown proof column (significant-word overlap).
    * No requirement exists in only one artifact.
    * Statuses are named in the traceability schema's allowed set.
    """
    payload = _load_yaml(TRACEABILITY_PATH)
    yaml_rows = {row["requirement"]: row for row in payload["rows"]}

    alignment_text = ALIGNMENT_PLAN_PATH.read_text(encoding="utf-8")
    md_rows = _parse_alignment_table(alignment_text)
    md_by_req = {row["requirement"]: row for row in md_rows}

    errors: list[str] = []

    # --- Pass 1: YAML → markdown (every traceability row must have a markdown peer) ---
    for yaml_req, yaml_row in yaml_rows.items():
        md_row = md_by_req.get(yaml_req)
        if md_row is None:
            errors.append(
                f"YAML requirement {yaml_req!r} not found in markdown table"
            )
            continue

        yaml_status = yaml_row["status"]
        md_status_norm = _normalize_markdown_status(md_row["status"])

        # Status drift
        if md_status_norm != yaml_status:
            errors.append(
                f"Status drift for {yaml_req!r}: "
                f"markdown={md_row['status']!r} (normalised={md_status_norm!r}), "
                f"YAML={yaml_status!r}"
            )
        elif yaml_status not in _VALID_STATUSES:
            errors.append(
                f"Unknown status {yaml_status!r} for {yaml_req!r}"
            )

        # Proof drift: each YAML proof_artifact label should leave a trace in
        # the markdown proof column.  We tokenise the label into significant
        # words and require *every* word to appear in the markdown text.
        yaml_proofs: list[str] = yaml_row.get("proof_artifacts", [])
        md_proof_lower = md_row["proof_text"].lower()

        for proof_label in yaml_proofs:
            sig_words = _proof_label_significant_words(proof_label)
            if not sig_words:
                continue
            missing_words = [w for w in sig_words if w not in md_proof_lower]
            if missing_words:
                errors.append(
                    f"Proof drift for {yaml_req!r}: "
                    f"YAML proof_artifact {proof_label!r} — "
                    f"significant words {missing_words!r} not found "
                    f"in markdown proof column"
                )

    # --- Pass 2: markdown → YAML (nothing in the table is unowned) ---
    for md_req in md_by_req:
        if md_req not in yaml_rows:
            errors.append(
                f"Markdown requirement {md_req!r} not found in YAML traceability"
            )

    if errors:
        raise AssertionError(
            f"{len(errors)} consistency drift(s) between alignment markdown "
            f"and traceability YAML:\n" + "\n".join(errors)
        )


def test_review_execution_log_has_no_unaddressed_blockers() -> None:
    review_text = REVIEW_EXECUTION_PATH.read_text(encoding="utf-8")

    for line in review_text.splitlines():
        stripped = line.strip()
        if re.match(r"^- [HD]\d+\b.*: `BLOCK`", stripped):
            raise AssertionError(f"blocking review verdict remains in log: {line}")
        if "returned `BLOCK`" in stripped and not stripped.startswith("No "):
            raise AssertionError(f"blocking review summary remains in log: {line}")

    sections = re.split(r"^## ", review_text, flags=re.MULTILINE)
    for section in sections:
        if "`PASS WITH EDIT`" in section or "PASS WITH\nEDIT" in section:
            assert "edits were applied" in section.lower(), section.splitlines()[0]
