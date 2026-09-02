"""Captured M11 contiguous-authority closure fixture."""

from __future__ import annotations

import json
from pathlib import Path

from arnold.workflow.completion.terminals import evaluate_m11_authority_closure


FIXTURE = Path(__file__).parents[2] / "fixtures" / "native_c2" / "m11_contiguous_authority_closure.json"


def test_interior_manifest_gap_fails_complete_capture_set_equality() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = evaluate_m11_authority_closure(fixture)
    assert result.status == "rejected"
    assert not result.accepted
    assert result.capture.missing_ids == tuple(str(value) for value in range(2, 39))
    assert len(result.causal_occurrences) == 1
    assert len(result.repair_frontier) == 1


def test_accepted_attempt_dependency_closure_does_not_multiply_root_cause() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["accepted_attempts"] = []
    result = evaluate_m11_authority_closure(fixture)
    assert result.status == "rejected"
    assert len(result.causal_occurrences) == 1
    assert len(result.repair_frontier) == 1
    assert result.missing_manifest_occurrence.startswith("missing-manifest:")
