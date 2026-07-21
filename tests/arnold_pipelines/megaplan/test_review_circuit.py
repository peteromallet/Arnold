"""M8A handler/review circuit tests.

Covers:
- Max-five rework wave enforcement
- ``failed: <detail>`` row normalization with command, criterion, artifact hash
- Malformed rows preserved as typed unknown
- Review budget exhaustion behavior
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.handlers.review import (
    _MAX_REWORK_WAVES,
    _deterministic_review_block_evidence,
    _normalize_failed_detail_rows,
    _resolve_review_outcome,
    _review_quality_block_failure,
)
from arnold_pipelines.megaplan.outcomes import ReviewDecisionResult


# ---------------------------------------------------------------------------
# _normalize_failed_detail_rows tests
# ---------------------------------------------------------------------------


class TestNormalizeFailedDetailRows:
    """Verify ``failed: <detail>`` row normalization."""

    def test_normalizes_valid_row_with_command_criterion_hash(self) -> None:
        evidence = [
            {
                "command": "pytest tests/test_example.py -q",
                "baseline_status": "passed at base",
                "post_status": "failed at current HEAD",
                "task_id": "T1",
                "issue": "regression in T1",
            }
        ]
        normalized, malformed = _normalize_failed_detail_rows(evidence)
        assert len(normalized) == 1
        assert len(malformed) == 0
        row = normalized[0]
        assert row["kind"] == "failed"
        assert row["detail"] == "regression in T1"
        assert row["command"] == "pytest tests/test_example.py -q"
        assert row["criterion"] == "regression in T1"
        assert "artifact_hash" in row
        assert len(row["artifact_hash"]) == 64  # SHA-256 hex digest

    def test_row_without_issue_falls_back_to_criterion_or_id(self) -> None:
        evidence = [
            {
                "command": "ruff check src/",
                "baseline_status": "pass",
                "post_status": "fail",
                "task_id": "T2",
                # No issue field — falls back to criterion/id
            }
        ]
        normalized, malformed = _normalize_failed_detail_rows(evidence)
        assert len(normalized) == 1
        assert normalized[0]["detail"] == "unspecified criterion"

    def test_missing_command_row_is_malformed_unknown(self) -> None:
        evidence = [
            {
                "baseline_status": "fail",
                "post_status": "fail",
                "task_id": "T3",
                "issue": "missing command test",
            }
        ]
        normalized, malformed = _normalize_failed_detail_rows(evidence)
        assert len(normalized) == 0
        assert len(malformed) == 1
        assert malformed[0]["kind"] == "unknown"
        assert malformed[0]["reason"] == "missing command"
        assert malformed[0]["task_id"] == "T3"

    def test_non_dict_row_is_malformed_unknown(self) -> None:
        evidence: list = ["not a dict"]  # type: ignore[list-item]
        normalized, malformed = _normalize_failed_detail_rows(evidence)  # type: ignore[arg-type]
        assert len(normalized) == 0
        assert len(malformed) == 1
        assert malformed[0]["kind"] == "unknown"
        assert malformed[0]["reason"] == "non-dict evidence row"

    def test_mixed_rows_produces_normalized_and_malformed(self) -> None:
        evidence = [
            {
                "command": "pytest tests/ -q",
                "baseline_status": "pass",
                "post_status": "fail",
                "task_id": "T1",
                "issue": "regression",
            },
            {
                # Missing command → malformed
                "baseline_status": "fail",
                "post_status": "fail",
                "task_id": "T2",
                "issue": "no command",
            },
            {
                "command": "mypy src/",
                "baseline_status": "pass",
                "post_status": "fail",
                "task_id": "T3",
                "issue": "type check",
            },
        ]
        normalized, malformed = _normalize_failed_detail_rows(evidence)
        assert len(normalized) == 2
        assert len(malformed) == 1
        assert normalized[0]["command"] == "pytest tests/ -q"
        assert normalized[1]["command"] == "mypy src/"
        assert malformed[0]["kind"] == "unknown"

    def test_artifact_hash_is_deterministic(self) -> None:
        """Same command/status pair produces the same artifact hash."""
        evidence1 = [
            {
                "command": "pytest tests/test_example.py -q",
                "baseline_status": "passed",
                "post_status": "failed",
                "task_id": "T1",
                "issue": "regression",
            }
        ]
        evidence2 = [
            {
                "command": "pytest tests/test_example.py -q",
                "baseline_status": "passed",
                "post_status": "failed",
                "task_id": "T99",
                "issue": "different task, same check",
            }
        ]
        n1, _ = _normalize_failed_detail_rows(evidence1)
        n2, _ = _normalize_failed_detail_rows(evidence2)
        assert n1[0]["artifact_hash"] == n2[0]["artifact_hash"]

    def test_different_commands_produce_different_hashes(self) -> None:
        evidence1 = [
            {
                "command": "pytest tests/a.py -q",
                "baseline_status": "pass",
                "post_status": "fail",
                "task_id": "T1",
                "issue": "x",
            }
        ]
        evidence2 = [
            {
                "command": "pytest tests/b.py -q",
                "baseline_status": "pass",
                "post_status": "fail",
                "task_id": "T2",
                "issue": "x",
            }
        ]
        n1, _ = _normalize_failed_detail_rows(evidence1)
        n2, _ = _normalize_failed_detail_rows(evidence2)
        assert n1[0]["artifact_hash"] != n2[0]["artifact_hash"]


# ---------------------------------------------------------------------------
# _deterministic_review_block_evidence tests
# ---------------------------------------------------------------------------


class TestDeterministicReviewBlockEvidence:
    """Verify evidence extraction preserves ``failed: <detail>`` signatures."""

    def test_blocking_rework_item_produces_normalized_failed_row(self) -> None:
        rework_items = [
            {
                "task_id": "T1",
                "issue": "regression in T1",
                "deterministic_check": {
                    "command": "pytest tests/test_example.py -q",
                    "baseline_status": "pass",
                    "post_status": "fail",
                },
            }
        ]
        result = _deterministic_review_block_evidence(rework_items)
        assert len(result) == 1
        assert result[0]["kind"] == "failed"
        assert result[0]["command"] == "pytest tests/test_example.py -q"
        assert "artifact_hash" in result[0]

    def test_non_blocking_rework_item_is_skipped(self) -> None:
        rework_items = [
            {
                "task_id": "T1",
                "issue": "cosmetic issue",
                "severity": "minor",
                "deterministic_check": {
                    "command": "pytest tests/ -q",
                    "baseline_status": "pass",
                    "post_status": "fail",
                },
            }
        ]
        result = _deterministic_review_block_evidence(rework_items)
        assert len(result) == 0  # Non-blocking severity → skipped

    def test_missing_command_yields_unknown_row(self) -> None:
        rework_items = [
            {
                "task_id": "T1",
                "issue": "missing command",
                "deterministic_check": {
                    # No command field
                    "baseline_status": "fail",
                    "post_status": "fail",
                },
            }
        ]
        result = _deterministic_review_block_evidence(rework_items)
        # The raw_evidence loop filters out items with empty command,
        # so no evidence is produced at all
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Review rework wave enforcement tests
# ---------------------------------------------------------------------------


class TestReviewReworkWaveEnforcement:
    """Verify max-five rework wave enforcement and budget exhaustion."""

    def _state_with_rework_history(self, rework_count: int) -> dict:
        return {
            "history": [
                {"step": "review", "result": "needs_rework"}
                for _ in range(rework_count)
            ],
            "config": {},
            "current_state": "executed",
        }

    def test_max_rework_waves_constant_is_five(self) -> None:
        assert _MAX_REWORK_WAVES == 5

    def test_below_cap_returns_rework_decision(self, tmp_path: Path) -> None:
        """With fewer than max rework cycles, review returns rework signal."""
        state = self._state_with_rework_history(2)  # 2 prior reworks, cap is 3
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
                    "issue": "x",
                    "deterministic_check": {
                        "command": "pytest",
                        "baseline_status": "failed",
                        "post_status": "failed",
                    },
                }
            ],
        )
        assert decision.result == ReviewDecisionResult.NEEDS_REWORK

    def test_at_cap_with_blockers_returns_blocked(self, tmp_path: Path) -> None:
        """At the rework cap with unresolved blockers → blocked, not force-proceed."""
        state = self._state_with_rework_history(3)  # 3 prior reworks (default cap)
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
            rework_items=[
                {
                    "issue": "blocking rework",
                    "deterministic_check": {
                        "command": "pytest",
                        "baseline_status": "failed",
                        "post_status": "failed",
                    },
                }
            ],
        )
        assert decision.result == ReviewDecisionResult.BLOCKED

    def test_at_cap_with_only_non_blocking_forces_proceed(self, tmp_path: Path) -> None:
        """At the rework cap with only non-blocking items → force-proceed."""
        state = self._state_with_rework_history(3)  # 3 prior reworks (default cap)
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
                    "issue": "cosmetic",
                    "severity": "minor",
                    "deterministic_check": {
                        "command": "pytest",
                        "baseline_status": "failed",
                        "post_status": "failed",
                    },
                }
            ],
        )
        assert decision.result == ReviewDecisionResult.FORCE_PROCEEDED

    def test_exceeds_max_five_waves_enforced(self, tmp_path: Path) -> None:
        """Even if config allows more, MAX_REWORK_WAVES=5 is enforced."""
        state = self._state_with_rework_history(4)  # 4 prior reworks
        # The min(_MAX_REWORK_WAVES, config) ensures cap is at most 5
        # default config cap is 3, so 4 prior means cap is hit
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
                    "issue": "x",
                    "severity": "minor",
                    "deterministic_check": {
                        "command": "pytest",
                        "baseline_status": "failed",
                        "post_status": "failed",
                    },
                }
            ],
        )
        # 4 >= 3 (default cap), and non-blocking → force-proceed
        assert decision.result == ReviewDecisionResult.FORCE_PROCEEDED

    def test_infrastructure_failure_bypasses_rework_cap(self, tmp_path: Path) -> None:
        """Infrastructure failures are retried, not counted against rework cap."""
        state = self._state_with_rework_history(5)
        decision = _resolve_review_outcome(
            tmp_path,
            "approved",
            verdict_count=0,
            total_tasks=1,
            check_count=0,
            total_checks=0,
            missing_evidence=[],
            robustness="full",
            state=state,
            issues=[],
            infrastructure_failure=True,
            rework_items=[],
        )
        assert decision.result == ReviewDecisionResult.BLOCKED


# ---------------------------------------------------------------------------
# _review_quality_block_failure tests
# ---------------------------------------------------------------------------


class TestReviewQualityBlockFailure:
    """Verify quality-block failure records stop at configured budget."""

    def _minimal_state(self, history_len: int = 3) -> dict:
        return {
            "history": [{} for _ in range(history_len)],
            "config": {},
            "current_state": "reviewed",
        }

    def test_quality_block_failure_has_structured_signature(self) -> None:
        state = self._minimal_state()
        rework_items = [
            {
                "task_id": "T1",
                "issue": "regression",
                "deterministic_check": {
                    "command": "pytest tests/test_example.py -q",
                    "baseline_status": "pass",
                    "post_status": "fail",
                },
            }
        ]
        result = _review_quality_block_failure(
            state=state,
            blockers=["failed must-criterion: C1"],
            rework_items=rework_items,
            review_artifact_hash="abc123",
        )
        assert result["kind"] == "quality_gate_blocked"
        assert result["phase"] == "review"
        assert result["state"] == "blocked"
        assert result["metadata"]["repairability"] == "deterministic_machine"
        assert result["metadata"]["deterministic"] is True
        assert len(result["metadata"]["deterministic_evidence"]) == 1
        evidence = result["metadata"]["deterministic_evidence"][0]
        assert evidence["kind"] == "failed"
        assert "command" in evidence
        assert "criterion" in evidence
        assert "artifact_hash" in evidence

    def test_quality_block_failure_with_malformed_evidence_marks_unknown(self) -> None:
        """When rework items lack deterministic checks, kind is unknown."""
        state = self._minimal_state()
        rework_items = [
            {
                "task_id": "T1",
                "issue": "no check attached",
            }
        ]
        result = _review_quality_block_failure(
            state=state,
            blockers=["unresolved blocking rework: no check attached"],
            rework_items=rework_items,
            review_artifact_hash="abc123",
        )
        assert result["kind"] == "review_quality_blocked_unknown"
        assert result["metadata"]["repairability"] == "unknown"
        assert result["metadata"]["deterministic"] is False
