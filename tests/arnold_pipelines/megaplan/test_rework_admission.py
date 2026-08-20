from __future__ import annotations

from arnold_pipelines.megaplan.orchestration.rework_admission import (
    reconcile_review_rework,
)


def _item(
    task_id: str,
    *,
    post_status: str | None,
    source: str = "review_flag_reverify",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "target": {
            "kind": "task",
            "task_id": task_id,
            "task_ids": [],
            "id": task_id,
        },
        "issue": f"{task_id} regressed",
        "expected": "green",
        "actual": "red",
        "evidence_file": f"tests/{task_id}.py",
        "flag_id": f"flag-{task_id}",
        "source": source,
        "deterministic_check": (
            {
                "command": f"pytest tests/{task_id}.py",
                "baseline_status": "pass",
                "post_status": post_status,
                "evidence_file": f"tests/{task_id}.py",
            }
            if post_status is not None
            else None
        ),
    }


def test_attempt_70_current_authority_does_not_replay_accepted_tasks() -> None:
    review = {
        "rework_items": [
            _item(f"T{index}", post_status="pass")
            for index in range(1, 47)
        ]
    }

    result = reconcile_review_rework(
        review,
        known_task_ids={f"T{index}" for index in range(1, 47)},
        accepted_task_ids={f"T{index}" for index in range(1, 47)},
        authority_revision="head-70",
        review_revision="head-70",
    )

    assert result.admitted is True
    assert result.runnable_task_ids == ()
    assert len(result.suppressed_task_ids) == 46
    assert {
        row["disposition"] for row in result.dispositions
    } == {"current_authority_satisfies_obligation"}


def test_fresh_regressions_reopen_as_new_generations() -> None:
    review = {"rework_items": [_item("T9", post_status="fail"), _item("T42", post_status="failed")]}

    result = reconcile_review_rework(
        review,
        known_task_ids={"T9", "T42"},
        accepted_task_ids={"T9", "T42"},
        authority_revision="current",
        review_revision="current",
    )

    assert result.admitted is True
    assert result.runnable_task_ids == ("T9", "T42")
    assert all(
        row["disposition"] == "new_regression_generation"
        for row in result.dispositions
    )


def test_failed_with_parenthetical_reopens_as_new_generation() -> None:
    # Reviewer wrote a status with an evidence parenthetical; the matcher must
    # recognize it as failed (mirroring handlers/review.py) instead of
    # mislabeling it accepted_task_reopen_unproven.
    review = {
        "rework_items": [
            _item(
                "T15",
                post_status="failed (AssertionError: extra public has_event, stream_row, tail_event)",
            )
        ]
    }

    result = reconcile_review_rework(
        review,
        known_task_ids={"T15"},
        accepted_task_ids={"T15"},
        authority_revision="current",
        review_revision="current",
    )

    assert result.admitted is True
    assert result.runnable_task_ids == ("T15",)
    assert result.blockers == ()
    assert result.dispositions[0]["disposition"] == "new_regression_generation"


def test_passed_with_parenthetical_is_satisfied() -> None:
    review = {
        "rework_items": [
            _item("T15", post_status="passed (all green)")
        ]
    }

    result = reconcile_review_rework(
        review,
        known_task_ids={"T15"},
        accepted_task_ids={"T15"},
        authority_revision="current",
        review_revision="current",
    )

    assert result.admitted is True
    assert result.runnable_task_ids == ()
    assert result.dispositions[0]["disposition"] == "current_authority_satisfies_obligation"


def test_failover_is_not_a_failed_status() -> None:
    # Prefix matching must not misclassify words like "failover".
    review = {
        "rework_items": [_item("T15", post_status="failover")]
    }

    result = reconcile_review_rework(
        review,
        known_task_ids={"T15"},
        accepted_task_ids={"T15"},
        authority_revision="current",
        review_revision="current",
    )

    assert result.admitted is False
    assert result.blockers[0]["code"] == "accepted_task_reopen_unproven"


def test_bulk_green_suite_becomes_one_validation_job_not_implementation_wave() -> None:
    task_ids = [f"T{index}" for index in range(1, 47)]
    review = {
        "rework_items": [
            {
                **_item("T1", post_status="fail"),
                "task_id": "REVIEW",
                "target": {
                    "kind": "manifest",
                    "id": "green-suite",
                    "task_id": None,
                    "task_ids": task_ids,
                },
            }
        ]
    }

    result = reconcile_review_rework(
        review,
        known_task_ids=set(task_ids),
        accepted_task_ids=set(task_ids),
        authority_revision="current",
        review_revision="current",
    )

    assert result.runnable_task_ids == ()
    assert len(result.validation_jobs) == 1
    assert result.validation_jobs[0]["task_ids"] == task_ids
    assert result.dispositions[0]["disposition"] == "bounded_validation_job"


def test_stale_evidence_window_and_unproven_reopen_fail_closed() -> None:
    review = {"rework_items": [_item("T33", post_status=None)]}

    result = reconcile_review_rework(
        review,
        known_task_ids={"T33"},
        accepted_task_ids={"T33"},
        authority_revision="new-head",
        review_revision="old-head",
    )

    assert result.admitted is False
    assert {row["code"] for row in result.blockers} == {
        "review_evidence_window_stale",
        "accepted_task_reopen_unproven",
    }
    assert result.runnable_task_ids == ()


def test_accepted_debt_is_preserved_without_implementation_replay() -> None:
    review = {
        "rework_items": [
            _item("T33", post_status=None, source="accepted_debt"),
            _item("T43", post_status=None, source="accepted_tradeoff"),
        ]
    }

    result = reconcile_review_rework(
        review,
        known_task_ids={"T33", "T43"},
        accepted_task_ids={"T33", "T43"},
        authority_revision="current",
        review_revision="current",
    )

    assert result.admitted is True
    assert result.runnable_task_ids == ()
    assert result.suppressed_task_ids == ("T33", "T43")
