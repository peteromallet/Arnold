"""Review-gate external human-gate tests (occurrence gateway-public-import-20260815T1430Z).

Proves the structural invariant: machine failures consume the review rework
budget; genuine external human gates (add_human_halt / human_halt / nsa-1)
consume neither the budget nor model discretion and park at
``awaiting_human_verify`` (agent_actionable:false) — never ``done``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.handlers.review import (
    _resolve_review_outcome,
)
from arnold_pipelines.megaplan.orchestration.external_gates import (
    contains_human_gate_marker,
    is_external_human_north_star_action,
    is_external_human_rework_item,
)
from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN_VERIFY


def _state_with_rework_history(rework_count: int) -> dict:
    return {
        "history": [
            {"step": "review", "result": "needs_rework"}
            for _ in range(rework_count)
        ],
        "config": {},
        "current_state": "executed",
    }


def _nsa1_rework_item() -> dict:
    return {
        "target": {"kind": "bulk", "id": "bulk-nsa1-human-halt", "task_ids": ["T42", "T43"]},
        "task_id": "T42",
        "issue": "Blocking North Star action NSA-1 is not concretely resolved",
        "deterministic_check": {
            "command": "rg -n 'NSA-1' docs scripts/reshape/s1_gate.py",
            "baseline_status": "failed",
            "post_status": "failed",
        },
    }


def _nsa1_north_star_action() -> dict:
    return {
        "id": "NSA-1",
        "action_type": "add_human_halt",
        "severity": "blocking",
        "status": "unresolved",
    }


def _machine_rework_item() -> dict:
    return {
        "issue": "blocking rework",
        "deterministic_check": {
            "command": "pytest",
            "baseline_status": "failed",
            "post_status": "failed",
        },
    }


class TestExternalHumanGateReviewRouting:
    def test_human_halt_only_parks_awaiting_human_verify(self, tmp_path: Path) -> None:
        """Cap exhausted + only human-gate blockers → awaiting_human_verify, NOT done."""
        state = _state_with_rework_history(3)  # at default cap
        decision = _resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state=state,
            issues=[],
            criteria=[],
            infrastructure_failure=False,
            rework_items=[_nsa1_rework_item()],
            north_star_actions=[_nsa1_north_star_action()],
        )
        assert decision.result == ReviewDecisionResult.SUCCESS
        assert decision.next_state == STATE_AWAITING_HUMAN_VERIFY
        assert decision.next_state != "done"
        assert decision.external_gates
        gate = decision.external_gates[0]
        assert gate["agent_actionable"] is False
        assert gate["criterion_id"] == "NSA-1"

    def test_unresolved_add_human_halt_action_cannot_close_out(self, tmp_path: Path) -> None:
        """Verdict pass but unresolved add_human_halt action → park, never done."""
        state = _state_with_rework_history(0)
        decision = _resolve_review_outcome(
            tmp_path,
            "pass",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state=state,
            issues=[],
            criteria=[{"priority": "must", "pass": "pass", "name": "ok"}],
            infrastructure_failure=False,
            rework_items=[],
            north_star_actions=[_nsa1_north_star_action()],
        )
        assert decision.result == ReviewDecisionResult.SUCCESS
        assert decision.next_state == STATE_AWAITING_HUMAN_VERIFY
        assert decision.external_gates[0]["criterion_id"] == "NSA-1"

    def test_mixed_machine_and_human_blockers_remains_blocked(self, tmp_path: Path) -> None:
        """Machine blocker + human gate at exhausted cap → still blocked."""
        state = _state_with_rework_history(3)
        decision = _resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state=state,
            issues=[],
            criteria=[],
            infrastructure_failure=False,
            rework_items=[_machine_rework_item(), _nsa1_rework_item()],
            north_star_actions=[],
        )
        assert decision.result == ReviewDecisionResult.BLOCKED
        assert decision.next_state != STATE_AWAITING_HUMAN_VERIFY

    def test_non_human_blockers_preserve_existing_cap_behavior(self, tmp_path: Path) -> None:
        """No human markers → unchanged blocked behavior at exhausted cap."""
        state = _state_with_rework_history(3)
        decision = _resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state=state,
            issues=[],
            criteria=[{"priority": "must", "pass": False, "id": "C1", "criterion": "must pass"}],
            infrastructure_failure=False,
            rework_items=[_machine_rework_item()],
            north_star_actions=[],
        )
        assert decision.result == ReviewDecisionResult.BLOCKED
        assert decision.external_gates == ()

    def test_does_not_defer_arbitrary_human_wording(self, tmp_path: Path) -> None:
        """Prose mentioning 'human' without a marker stays machine-actionable."""
        state = _state_with_rework_history(3)
        decision = _resolve_review_outcome(
            tmp_path,
            "needs_rework",
            verdict_count=1,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state=state,
            issues=[],
            criteria=[],
            infrastructure_failure=False,
            rework_items=[
                {
                    "issue": "human readable output is missing",
                    "deterministic_check": {
                        "command": "pytest",
                        "baseline_status": "failed",
                        "post_status": "failed",
                    },
                }
            ],
            north_star_actions=[],
        )
        assert decision.result == ReviewDecisionResult.BLOCKED
        assert decision.external_gates == ()


class TestExternalGateClassifier:
    def test_marker_spelling_variants_are_equivalent(self) -> None:
        for raw in (
            {"target": {"id": "north-star-human-halt"}},
            {"flag_id": "NSA-1"},
            {"source": "nsa-1"},
            {"action_type": "add_human_halt"},
            {"id": "human_halt"},
        ):
            assert is_external_human_rework_item(raw), raw

    def test_marker_does_not_match_similar_but_distinct_tokens(self) -> None:
        assert not contains_human_gate_marker("nsa_10")
        assert not contains_human_gate_marker("non_human_haltx")
        assert not contains_human_gate_marker("the output is human readable")
        assert not is_external_human_rework_item({"issue": "human-readable docs"})

    def test_resolved_north_star_action_is_not_a_gate(self) -> None:
        resolved = dict(_nsa1_north_star_action())
        resolved["status"] = "accepted"
        assert not is_external_human_north_star_action(resolved)
        assert is_external_human_north_star_action(_nsa1_north_star_action())
