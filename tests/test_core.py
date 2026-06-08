from __future__ import annotations

import pytest

from arnold.pipelines.megaplan._core import (
    add_or_increment_debt,
    batch_artifact_path,
    compute_batch_complexity,
    compute_global_batches,
    compute_task_batches,
    escalated_subsystems,
    extract_subsystem_tag,
    find_matching_debt,
    list_batch_artifacts,
    load_debt_registry,
    resolve_debt,
)


def _task(task_id: str, depends_on: list[str] | None = None) -> dict[str, object]:
    return {"id": task_id, "depends_on": depends_on or []}


def test_compute_task_batches_linear_chain() -> None:
    tasks = [_task("T1"), _task("T2", ["T1"]), _task("T3", ["T2"])]
    assert compute_task_batches(tasks) == [["T1"], ["T2"], ["T3"]]


def test_compute_task_batches_independent_tasks_share_batch() -> None:
    tasks = [_task("T1"), _task("T2"), _task("T3")]
    assert compute_task_batches(tasks) == [["T1", "T2", "T3"]]


def test_compute_task_batches_diamond_graph() -> None:
    tasks = [
        _task("T1"),
        _task("T2", ["T1"]),
        _task("T3", ["T1"]),
        _task("T4", ["T2", "T3"]),
    ]
    assert compute_task_batches(tasks) == [["T1"], ["T2", "T3"], ["T4"]]


def test_compute_task_batches_cycle_raises() -> None:
    tasks = [_task("T1", ["T2"]), _task("T2", ["T1"])]
    with pytest.raises(ValueError, match="Cyclic dependency graph"):
        compute_task_batches(tasks)


def test_compute_task_batches_unknown_dependency_raises() -> None:
    with pytest.raises(ValueError, match="Unknown dependency ID 'T9'"):
        compute_task_batches([_task("T1", ["T9"])])


def test_compute_task_batches_empty_input_returns_empty_list() -> None:
    assert compute_task_batches([]) == []


def test_compute_task_batches_completed_ids_satisfy_pending_dependencies() -> None:
    tasks = [_task("T2", ["T1"])]
    assert compute_task_batches(tasks, completed_ids={"T1"}) == [["T2"]]


def test_compute_task_batches_completed_ids_allow_parallel_pending_tasks() -> None:
    tasks = [_task("T2", ["T1"]), _task("T3", ["T1"])]
    assert compute_task_batches(tasks, completed_ids={"T1"}) == [["T2", "T3"]]


def test_batch_artifact_path_returns_expected_path(tmp_path) -> None:
    assert batch_artifact_path(tmp_path, 3) == tmp_path / "execution_batch_3.json"


def test_list_batch_artifacts_returns_sorted_existing_paths(tmp_path) -> None:
    batch_three = tmp_path / "execution_batch_3.json"
    batch_one = tmp_path / "execution_batch_1.json"
    batch_two = tmp_path / "execution_batch_2.json"
    for path in (batch_three, batch_one, batch_two):
        path.write_text("{}", encoding="utf-8")
    (tmp_path / "execution_batch_notes.json").write_text("{}", encoding="utf-8")

    assert list_batch_artifacts(tmp_path) == [batch_one, batch_two, batch_three]


def test_compute_global_batches_ignores_completed_status_for_stable_partition() -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "depends_on": []},
            {"id": "T2", "status": "pending", "depends_on": ["T1"]},
            {"id": "T3", "status": "skipped", "depends_on": ["T1"]},
            {"id": "T4", "status": "pending", "depends_on": ["T2", "T3"]},
        ]
    }

    assert compute_global_batches(finalize_data) == [["T1"], ["T2", "T3"], ["T4"]]


def test_load_debt_registry_returns_empty_when_missing(tmp_path) -> None:
    assert load_debt_registry(tmp_path) == {"entries": []}


def test_add_or_increment_debt_creates_new_entry() -> None:
    registry = {"entries": []}

    entry = add_or_increment_debt(
        registry,
        subsystem="Timeout Recovery",
        concern="Timeout recovery: Retry backoff is missing",
        flag_ids=["FLAG-001"],
        plan_id="plan-a",
    )

    assert entry["id"] == "DEBT-001"
    assert entry["subsystem"] == "timeout-recovery"
    assert entry["concern"] == "timeout recovery: retry backoff is missing"
    assert entry["flag_ids"] == ["FLAG-001"]
    assert entry["plan_ids"] == ["plan-a"]
    assert entry["occurrence_count"] == 1
    assert entry["resolved"] is False


def test_add_or_increment_debt_increments_matching_entry() -> None:
    registry = {"entries": []}
    first = add_or_increment_debt(
        registry,
        subsystem="timeout-recovery",
        concern="Timeout recovery: Retry backoff is missing",
        flag_ids=["FLAG-001"],
        plan_id="plan-a",
    )

    second = add_or_increment_debt(
        registry,
        subsystem="timeout-recovery",
        concern="Timeout recovery: retry backoff is missing",
        flag_ids=["FLAG-002"],
        plan_id="plan-b",
    )

    assert second is first
    assert len(registry["entries"]) == 1
    assert second["occurrence_count"] == 2
    assert second["flag_ids"] == ["FLAG-001", "FLAG-002"]
    assert second["plan_ids"] == ["plan-a", "plan-b"]


def test_find_matching_debt_rejects_different_subsystem_even_with_overlap() -> None:
    registry = {"entries": []}
    add_or_increment_debt(
        registry,
        subsystem="timeout-recovery",
        concern="Timeout recovery: Retry backoff is missing",
        flag_ids=["FLAG-001"],
        plan_id="plan-a",
    )

    assert find_matching_debt(
        registry,
        "execute-paths",
        "Timeout recovery: Retry backoff is missing",
    ) is None


@pytest.mark.parametrize(
    ("concern", "expected"),
    [
        ("Timeout recovery: Retry backoff is missing", "timeout-recovery"),
        ("Retry backoff is missing", "untagged"),
        ("Execute paths: queue: drain edge case", "execute-paths"),
    ],
)
def test_extract_subsystem_tag_handles_expected_variants(concern: str, expected: str) -> None:
    assert extract_subsystem_tag(concern) == expected


def test_resolve_debt_sets_resolution_fields() -> None:
    registry = {"entries": []}
    entry = add_or_increment_debt(
        registry,
        subsystem="observation",
        concern="Observation: Missing event logging",
        flag_ids=["FLAG-010"],
        plan_id="plan-a",
    )

    resolved = resolve_debt(registry, entry["id"], "plan-b")

    assert resolved["resolved"] is True
    assert resolved["resolved_by"] == "plan-b"
    assert resolved["resolved_at"] is not None
    assert resolved["updated_at"] == resolved["resolved_at"]


def test_escalated_subsystems_triggers_for_single_high_occurrence_entry() -> None:
    registry = {"entries": []}
    entry = add_or_increment_debt(
        registry,
        subsystem="timeout-recovery",
        concern="Timeout recovery: Retry backoff is missing",
        flag_ids=["FLAG-001"],
        plan_id="plan-a",
    )
    entry["occurrence_count"] = 4

    escalated = escalated_subsystems(registry)

    assert escalated == [("timeout-recovery", 4, [entry])]


def test_escalated_subsystems_triggers_for_multiple_entries_in_same_subsystem() -> None:
    registry = {"entries": []}
    first = add_or_increment_debt(
        registry,
        subsystem="timeout-recovery",
        concern="Timeout recovery: Retry backoff is missing",
        flag_ids=["FLAG-001"],
        plan_id="plan-a",
    )
    second = add_or_increment_debt(
        registry,
        subsystem="timeout-recovery",
        concern="Timeout recovery: Circuit breaker stalls recovery flow",
        flag_ids=["FLAG-002"],
        plan_id="plan-b",
    )
    second["occurrence_count"] = 2

    escalated = escalated_subsystems(registry)

    assert escalated == [("timeout-recovery", 3, [first, second])]


# ---------------------------------------------------------------------------
# compute_batch_complexity tests
# ---------------------------------------------------------------------------


def _ctask(task_id: str, complexity: int) -> dict[str, object]:
    return {"id": task_id, "complexity": complexity}


def test_compute_batch_complexity_independent_batches() -> None:
    """Batches with complexities [1], [3], [5] return 1, 3, 5."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask("T1", 1),
            _ctask("T2", 3),
            _ctask("T3", 5),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 1
    assert compute_batch_complexity(finalize_data, ["T2"]) == 3
    assert compute_batch_complexity(finalize_data, ["T3"]) == 5


def test_compute_batch_complexity_multiple_tasks_returns_max() -> None:
    """Batch with complexities [1, 3, 5] returns 5."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask("T1", 1),
            _ctask("T2", 3),
            _ctask("T3", 5),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1", "T2", "T3"]) == 5


def test_compute_batch_complexity_mixed_dependency_batch() -> None:
    """Batch with complexity [2, 4] returns 4."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask("T1", 2),
            _ctask("T2", 4),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1", "T2"]) == 4


def test_compute_batch_complexity_missing_complexity_defaults_to_5() -> None:
    """Task without 'complexity' field defaults the batch to 5."""
    finalize_data: dict[str, object] = {
        "tasks": [
            {"id": "T1"},
            _ctask("T2", 1),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 5
    assert compute_batch_complexity(finalize_data, ["T1", "T2"]) == 5


def test_compute_batch_complexity_non_integer_complexity_defaults_to_5() -> None:
    """Non-integer complexity defaults batch to 5."""
    finalize_data: dict[str, object] = {
        "tasks": [
            {"id": "T1", "complexity": "high"},
            _ctask("T2", 1),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 5
    assert compute_batch_complexity(finalize_data, ["T1", "T2"]) == 5


def test_compute_batch_complexity_out_of_range_values_default_to_5() -> None:
    """Complexity < 1 or > 5 defaults batch to 5."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask("T1", 0),
            _ctask("T2", 6),
            _ctask("T3", 3),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 5
    assert compute_batch_complexity(finalize_data, ["T2"]) == 5
    # Batch with only valid tasks still works
    assert compute_batch_complexity(finalize_data, ["T3"]) == 3


def test_compute_batch_complexity_missing_task_id_defaults_to_5() -> None:
    """Unknown task ID defaults batch to 5."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask("T1", 2),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T9"]) == 5


def test_compute_batch_complexity_empty_batch_returns_5() -> None:
    """Empty batch returns 5."""
    finalize_data: dict[str, object] = {
        "tasks": [_ctask("T1", 2)]
    }
    assert compute_batch_complexity(finalize_data, []) == 5


def test_compute_batch_complexity_all_valid_tasks_returns_correct_max() -> None:
    """All tasks with valid complexity — standard max behavior."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask("T1", 2),
            _ctask("T2", 4),
            _ctask("T3", 1),
            _ctask("T4", 3),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1", "T3"]) == 2
    assert compute_batch_complexity(finalize_data, ["T2", "T4"]) == 4
    assert compute_batch_complexity(finalize_data, ["T1", "T2", "T3", "T4"]) == 4


# ---------------------------------------------------------------------------
# compute_batch_complexity tier_override tests
# ---------------------------------------------------------------------------


def _ctask_with_override(task_id: str, complexity: int, tier_override: object = None) -> dict[str, object]:
    t: dict[str, object] = {"id": task_id, "complexity": complexity}
    if tier_override is not None:
        t["tier_override"] = tier_override
    return t


def test_compute_batch_complexity_no_override_unchanged() -> None:
    """Without tier_override the result equals the base complexity."""
    finalize_data: dict[str, object] = {
        "tasks": [_ctask_with_override("T1", 3)]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 3


def test_compute_batch_complexity_override_greater_raises_batch_tier() -> None:
    """tier_override > complexity: effective = tier_override."""
    finalize_data: dict[str, object] = {
        "tasks": [_ctask_with_override("T1", 2, tier_override=4)]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 4


def test_compute_batch_complexity_override_less_than_complexity_is_noop() -> None:
    """tier_override <= complexity: effective = complexity (override is no-op)."""
    finalize_data: dict[str, object] = {
        "tasks": [_ctask_with_override("T1", 4, tier_override=2)]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 4


def test_compute_batch_complexity_override_equal_to_complexity_is_noop() -> None:
    """tier_override == complexity: effective = complexity."""
    finalize_data: dict[str, object] = {
        "tasks": [_ctask_with_override("T1", 3, tier_override=3)]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 3


def test_compute_batch_complexity_override_out_of_range_ignored() -> None:
    """tier_override out of 1..5 is silently ignored."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask_with_override("T1", 2, tier_override=0),
            _ctask_with_override("T2", 2, tier_override=6),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 2
    assert compute_batch_complexity(finalize_data, ["T2"]) == 2


def test_compute_batch_complexity_override_non_int_ignored() -> None:
    """Non-integer tier_override is silently ignored."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask_with_override("T1", 2, tier_override="high"),
            _ctask_with_override("T2", 2, tier_override=3.5),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 2
    assert compute_batch_complexity(finalize_data, ["T2"]) == 2


def test_compute_batch_complexity_override_raises_batch_tier_across_tasks() -> None:
    """Batch max is taken after override is applied per task."""
    finalize_data: dict[str, object] = {
        "tasks": [
            _ctask_with_override("T1", 1, tier_override=5),
            _ctask_with_override("T2", 2),
        ]
    }
    assert compute_batch_complexity(finalize_data, ["T1", "T2"]) == 5


def test_compute_batch_complexity_fail_safe_intact_with_missing_complexity() -> None:
    """Missing complexity still returns 5 even when tier_override is present."""
    finalize_data: dict[str, object] = {
        "tasks": [{"id": "T1", "tier_override": 4}]
    }
    assert compute_batch_complexity(finalize_data, ["T1"]) == 5
