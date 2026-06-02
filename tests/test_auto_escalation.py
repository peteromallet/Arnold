"""Tests for megaplan.auto_escalation."""
from __future__ import annotations

from megaplan.auto_escalation import (
    CATEGORY_POLICY,
    FailureCategory,
    classify_failure,
)
from megaplan.auto import DEFAULT_MAX_BLOCKED_RETRIES
from megaplan.orchestration.phase_result import BlockedTask, Deviation, ExitKind


# ─── Helpers ────────────────────────────────────────────────────────────────


def _dev(kind: str, message: str = "") -> Deviation:
    return Deviation(kind=kind, message=message)


def _bt(task_id: str) -> BlockedTask:
    return BlockedTask(task_id=task_id, reason="test")


# ─── Every ExitKind value ────────────────────────────────────────────────────


def test_success_returns_none_category() -> None:
    cat, ids = classify_failure(ExitKind.success.value, [], [])
    assert cat is None
    assert ids == []


def test_blocked_by_prereq_category() -> None:
    cat, ids = classify_failure(ExitKind.blocked_by_prereq.value, [], [_bt("T1"), _bt("T2")])
    assert cat == FailureCategory.blocked_by_prereq
    assert ids == ["T1", "T2"]


def test_blocked_by_quality_defaults_to_semantic() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("quality_gate", "wrong approach taken")],
        [_bt("T3")],
    )
    assert cat == FailureCategory.blocked_by_quality_semantic
    assert ids == ["T3"]


def test_timeout_category() -> None:
    cat, ids = classify_failure(ExitKind.timeout.value, [], [])
    assert cat == FailureCategory.timeout
    assert ids == []


def test_context_exhausted_category() -> None:
    cat, ids = classify_failure(ExitKind.context_exhausted.value, [], [])
    assert cat == FailureCategory.context_exhausted
    assert ids == []


def test_internal_error_category() -> None:
    cat, ids = classify_failure(ExitKind.internal_error.value, [], [])
    assert cat == FailureCategory.internal_error
    assert ids == []


def test_external_error_category() -> None:
    cat, ids = classify_failure(ExitKind.external_error.value, [], [])
    assert cat == FailureCategory.external_error
    assert ids == []


def test_review_non_convergence_policy_escalates() -> None:
    assert CATEGORY_POLICY[FailureCategory.review_non_convergence].escalate is True
    assert CATEGORY_POLICY[FailureCategory.review_non_convergence].retries_first == 0


# ─── Structured drift kind wins over substring ───────────────────────────────


def test_structured_scope_drift_kind_classifies_as_drift() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("scope_drift", "task output was incorrect")],
        [_bt("T5")],
    )
    assert cat == FailureCategory.blocked_by_quality_drift
    assert ids == []


def test_structured_unrelated_files_kind_classifies_as_drift() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("unrelated_files", "some description")],
        [_bt("T6")],
    )
    assert cat == FailureCategory.blocked_by_quality_drift
    assert ids == []


def test_structured_out_of_scope_kind_classifies_as_drift() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("out_of_scope", "")],
        [],
    )
    assert cat == FailureCategory.blocked_by_quality_drift


def test_structured_drift_kind_wins_over_non_drift_message() -> None:
    # kind='scope_drift' wins even with a generic message
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("scope_drift", "completely unrelated message")],
        [_bt("T7")],
    )
    assert cat == FailureCategory.blocked_by_quality_drift
    assert ids == []


# ─── Substring fallback only when kind absent ────────────────────────────────


def test_quality_gate_kind_with_drift_message_uses_fallback() -> None:
    # 'quality_gate' is not in drift kinds, so fallback checks message
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("quality_gate", "scope drift detected in modified files")],
        [_bt("T8")],
    )
    assert cat == FailureCategory.blocked_by_quality_drift
    assert ids == []


def test_no_drift_kind_no_drift_message_is_semantic() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("quality_gate", "tests missing evidence")],
        [_bt("T9")],
    )
    assert cat == FailureCategory.blocked_by_quality_semantic
    assert ids == ["T9"]


def test_unrelated_files_message_token_triggers_fallback() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("quality_gate", "unrelated files were modified")],
        [],
    )
    assert cat == FailureCategory.blocked_by_quality_drift


def test_out_of_scope_message_token_triggers_fallback() -> None:
    cat, ids = classify_failure(
        ExitKind.blocked_by_quality.value,
        [_dev("quality_gate", "changes were out of scope")],
        [],
    )
    assert cat == FailureCategory.blocked_by_quality_drift


# ─── blocked_by_prereq via BlockedTask propagation ───────────────────────────


def test_blocked_by_prereq_propagates_all_task_ids() -> None:
    blocked = [_bt("A"), _bt("B"), _bt("C")]
    cat, ids = classify_failure(ExitKind.blocked_by_prereq.value, [], blocked)
    assert cat == FailureCategory.blocked_by_prereq
    assert ids == ["A", "B", "C"]


def test_blocked_task_task_id_read_via_getattr() -> None:
    class FakeBT:
        task_id = "X9"

    cat, ids = classify_failure(ExitKind.blocked_by_prereq.value, [], [FakeBT()])
    assert ids == ["X9"]


# ─── Empty / malformed inputs ────────────────────────────────────────────────


def test_none_exit_kind_returns_none_category() -> None:
    cat, ids = classify_failure(None, [], [])
    assert cat is None
    assert ids == []


def test_unknown_exit_kind_returns_none_category() -> None:
    cat, ids = classify_failure("some_future_kind", [], [])
    assert cat is None
    assert ids == []


def test_empty_deviations_and_blocked_for_semantic() -> None:
    cat, ids = classify_failure(ExitKind.blocked_by_quality.value, [], [])
    assert cat == FailureCategory.blocked_by_quality_semantic
    assert ids == []


# ─── Categories without per-task signal return failing_task_ids=[] ───────────


def test_categories_without_per_task_signal_return_empty_ids() -> None:
    no_task_signal = (
        ExitKind.context_exhausted,
        ExitKind.timeout,
        ExitKind.internal_error,
        ExitKind.external_error,
    )
    for ek in no_task_signal:
        _, ids = classify_failure(ek.value, [], [_bt("T99")])
        assert ids == [], f"{ek} should not propagate task IDs"


# ─── Policy table sanity ─────────────────────────────────────────────────────


def test_blocked_by_prereq_policy_no_escalate() -> None:
    assert CATEGORY_POLICY[FailureCategory.blocked_by_prereq].escalate is False


def test_blocked_by_quality_drift_policy_no_escalate() -> None:
    assert CATEGORY_POLICY[FailureCategory.blocked_by_quality_drift].escalate is False


def test_blocked_by_quality_semantic_escalates_after_retries() -> None:
    policy = CATEGORY_POLICY[FailureCategory.blocked_by_quality_semantic]
    assert policy.escalate is True
    assert policy.retries_first == DEFAULT_MAX_BLOCKED_RETRIES


def test_context_exhausted_escalates_immediately() -> None:
    policy = CATEGORY_POLICY[FailureCategory.context_exhausted]
    assert policy.escalate is True
    assert policy.retries_first == 0


def test_internal_error_has_one_retry_before_escalate() -> None:
    policy = CATEGORY_POLICY[FailureCategory.internal_error]
    assert policy.escalate is True
    assert policy.retries_first == 1


def test_external_error_no_escalate() -> None:
    assert CATEGORY_POLICY[FailureCategory.external_error].escalate is False


def test_all_categories_present_in_policy() -> None:
    for cat in FailureCategory:
        assert cat in CATEGORY_POLICY, f"{cat} missing from CATEGORY_POLICY"
