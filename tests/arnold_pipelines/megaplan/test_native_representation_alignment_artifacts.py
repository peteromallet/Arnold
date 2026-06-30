from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

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
                            "canonical_source": [".py"],
                            "audited_pure_phase_body": [".py"],
                            "declared_policy": [".py", ".yaml", ".yml", ".json", ".md"],
                        },
                    }
                },
                "rows": [{"id": row_id} for row_id in row_ids],
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


def test_final_conformance_gate_is_closeout_owned() -> None:
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

    closeout_text = closeout_brief.read_text(encoding="utf-8")
    assert gate["closeout_milestone"] in {
        milestone
        for row in payload["rows"]
        for milestone in row["milestones"]
    }
    for deliverable in gate["closeout_deliverables"]:
        assert deliverable in closeout_text, deliverable
    machine_report = gate["machine_readable_report"]
    assert isinstance(machine_report, dict)
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
        "canonical_source": [".py"],
        "audited_pure_phase_body": [".py"],
        "declared_policy": [".py", ".yaml", ".yml", ".json", ".md"],
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
    (tmp_path / "proof-one.md").write_text("# Proof one\n", encoding="utf-8")
    (tmp_path / "carrier-one.py").write_text("# carrier one\n", encoding="utf-8")
    (tmp_path / "proof-two.md").write_text("# Proof two\n", encoding="utf-8")
    (tmp_path / "blocking-proof.md").write_text("# Blocking proof\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one", "row-two"])
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
                        "carrier_evidence": ["carrier-one.py"],
                        "proof_artifacts": ["proof-one.md"],
                    },
                    {
                        "id": "row-two",
                        "status": "deferred",
                        "semantic_carrier": "explicit_deferral",
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
        )
        == []
    )


def test_final_conformance_yaml_validator_rejects_false_pass(tmp_path: Path) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    _write_conformance_traceability_fixture(traceability_path, ["row-one", "row-two"])
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
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    )

    assert any("missing implemented fields: carrier_evidence" in error for error in errors)


def test_final_conformance_yaml_validator_rejects_non_code_canonical_source(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "report.md").write_text("# Report\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
    )

    assert any("canonical_source requires one of ['.py']" in error for error in errors)


def test_final_conformance_yaml_validator_accepts_declared_policy_artifact(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "policy.yaml").write_text("policy: true\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
        )
        == []
    )


def test_final_conformance_yaml_validator_uses_traceability_target_report(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.py").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
                        "carrier_evidence": ["carrier.py"],
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
        )
        == []
    )


def test_final_conformance_yaml_validator_rejects_stale_target_report(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "carrier.py").write_text("# carrier\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
                        "carrier_evidence": ["carrier.py"],
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
    )

    assert any(
        "target_report must be 'docs/arnold/custom-native-target.md'" in error
        for error in errors
    )


def test_final_conformance_yaml_validator_uses_traceability_suffix_contract(
    tmp_path: Path,
) -> None:
    traceability_path = tmp_path / "traceability.yaml"
    conformance_path = tmp_path / "conformance.yaml"
    (tmp_path / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (tmp_path / "policy.custom").write_text("policy=true\n", encoding="utf-8")
    _write_conformance_traceability_fixture(traceability_path, ["row-one"])
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
        )
        == []
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
