"""Fixture-backed graph projection parity.

This is control-flow parity, NOT drift-provably-zero. The fixture is a
recorded reference for workflow_next over the robustness x prep/feedback
x state x verdict matrix; the realized graph projection must keep
matching that reference.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan._core.topology import RealizedGraph, RunTopologyConfig, predecessors

FIXTURE = Path(__file__).parent / "fixtures" / "workflow_next_matrix.json"
LABEL = "control-flow parity, NOT drift-provably-zero"


def _state_from_case(case: dict) -> dict:
    verdict = case["verdict"]
    gate_payloads = {
        "unset": {},
        "iterate": {"recommendation": "ITERATE"},
        "escalate": {"recommendation": "ESCALATE"},
        "tiebreaker": {"recommendation": "TIEBREAKER"},
        "proceed": {"recommendation": "PROCEED", "passed": True},
        "proceed_blocked": {
            "recommendation": "PROCEED",
            "passed": False,
            "preflight_results": {},
        },
        "proceed_agent_availability_blocked": {
            "recommendation": "PROCEED",
            "passed": False,
            "preflight_results": {
                "claude_available": False,
                "codex_available": True,
            },
        },
        "malformed_gate": "not-a-dict",
    }
    return {
        "current_state": case["state"],
        "config": {
            "robustness": case["robustness"],
            "with_prep": case["with_prep"],
            "with_feedback": case["with_feedback"],
        },
        "last_gate": gate_payloads[verdict],
    }


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_fixture_exists_and_labels_control_flow_parity() -> None:
    payload = _load_fixture()

    assert payload["label"] == LABEL
    dims = payload["dimensions"]
    expected_cases = (
        len(dims["robustness"])
        * len(dims["modes"])
        * len(dims["states"])
        * len(dims["verdicts"])
    )
    assert len(payload["cases"]) == expected_cases

    covered = {
        (
            case["robustness"],
            case["with_prep"],
            case["with_feedback"],
            case["state"],
            case["verdict"],
        )
        for case in payload["cases"]
    }
    assert len(covered) == expected_cases
    assert any(case["verdict"] == "escalate" for case in payload["cases"])
    assert any(case["verdict"] == "proceed_blocked" for case in payload["cases"])
    assert any(case["state"] == "blocked" for case in payload["cases"])


def test_realized_graph_next_steps_matches_recorded_workflow_next_matrix() -> None:
    payload = _load_fixture()

    for case in payload["cases"]:
        graph = RealizedGraph(
            RunTopologyConfig(
                robustness=case["robustness"],
                with_prep=case["with_prep"],
                with_feedback=case["with_feedback"],
            )
        )
        assert graph.next_steps(_state_from_case(case)) == case["next_steps"], (
            f"mismatch at robustness={case['robustness']} "
            f"with_prep={case['with_prep']} "
            f"with_feedback={case['with_feedback']} "
            f"state={case['state']} verdict={case['verdict']}"
        )


def test_recovery_predecessor_projection_matches_recorded_fixture() -> None:
    payload = _load_fixture()

    for stage, expected in payload["recovery_predecessors"].items():
        assert predecessors(stage, policy="recovery") == expected
    assert payload["recovery_predecessors"]["feedback"] == "reviewed"
