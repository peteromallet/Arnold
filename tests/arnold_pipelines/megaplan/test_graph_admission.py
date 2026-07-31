from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.graph_admission import (
    candidate_graph_record,
    record_rejected_candidate,
)


def _payload() -> dict[str, object]:
    return {
        "task_contract_version": 2,
        "tasks": [
            {
                "id": "T15",
                "depends_on": ["T6"],
                "dependency_reasons": {
                    "T6": {"kind": "routing", "reason": "same batch"}
                },
                "write_set": {"paths": ["src/shared.py"], "complete": True},
            }
        ],
        "validation_jobs": [],
        "sense_checks": [],
    }


def _report() -> dict[str, object]:
    return {
        "admitted": False,
        "task_contract_hash": "candidate-hash",
        "diagnostics": [
            {
                "code": "routing_dependency_forbidden",
                "task_ids": ["T15", "T6"],
            },
            {
                "code": "write_overlap_unordered",
                "task_ids": ["T15", "T6"],
                "path": "src/shared.py",
            },
        ],
    }


def test_rejected_candidate_never_replaces_admitted_graph(tmp_path: Path) -> None:
    admitted_finalize = b'{"tasks":[{"id":"T1","status":"done"}]}'
    admitted_feasibility = b'{"admitted":true,"task_contract_hash":"admitted"}'
    (tmp_path / "finalize.json").write_bytes(admitted_finalize)
    (tmp_path / "task_feasibility.json").write_bytes(admitted_feasibility)
    state = {"current_state": "gated", "meta": {"accepted_attempt_count": 46}}

    repair = record_rejected_candidate(tmp_path, state, _payload(), _report())

    assert (tmp_path / "finalize.json").read_bytes() == admitted_finalize
    assert (tmp_path / "task_feasibility.json").read_bytes() == admitted_feasibility
    assert state["meta"]["accepted_attempt_count"] == 46
    assert repair["accepted_authority_preserved"] is True
    assert repair["implementation_dispatch_allowed"] is False
    candidates = list((tmp_path / "finalize_candidates").glob("*.json"))
    assert len(candidates) == 1
    assert json.loads(candidates[0].read_text())["admitted"] is False


def test_identical_candidate_failure_opens_bounded_repair_circuit(tmp_path: Path) -> None:
    state = {"current_state": "gated", "meta": {}}

    first = record_rejected_candidate(tmp_path, state, _payload(), _report())
    second = record_rejected_candidate(tmp_path, state, _payload(), _report())

    assert first["occurrences"] == 1
    assert first["circuit_open"] is False
    assert second["occurrences"] == 2
    assert second["circuit_open"] is True


def test_candidate_identity_is_deterministic() -> None:
    assert candidate_graph_record(_payload(), _report())["candidate_id"] == (
        candidate_graph_record(_payload(), _report())["candidate_id"]
    )
