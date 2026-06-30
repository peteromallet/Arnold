from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
TRACEABILITY_PATH = ROOT / "docs/arnold/megaplan-native-representation-traceability.yaml"
SCENARIOS_PATH = ROOT / "docs/arnold/megaplan-native-representation-scenarios.yaml"
ALIGNMENT_PLAN_PATH = ROOT / "docs/arnold/megaplan-native-representation-alignment-plan.md"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


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
