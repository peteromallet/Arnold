"""Scoped-successor derivation for failing bulk rework validation jobs.

A bulk/manifest/global review rework item is admitted as a validation-only
bounded job: the accepted task_ids it names are suppressed, not reopened.
When the deterministic check FAILS at execute time, the engine previously
dead-ended on "a scoped successor task is required" with nothing creating the
successor.  The named accepted tasks ARE the successors — this pins the
derivation (occurrence 1f1f5d10145b, plan m5 frozen-digest regression).
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    _scoped_successors_for_failed_validation,
)


def _job(task_ids: list[str], job_id: str = "bulk-1") -> dict:
    return {
        "id": job_id,
        "command": "pytest tests/foo.py -q",
        "task_ids": task_ids,
        "source_item_index": 0,
        "authority_digest": "digest",
    }


def _pass_result() -> dict:
    return {"exit_code": 0, "error": None, "timed_out": False}


def _fail_result() -> dict:
    return {"exit_code": 1, "error": None, "timed_out": False}


def test_failed_bulk_job_returns_covered_accepted_tasks() -> None:
    jobs = [_job(["T5A", "T6"])]
    results = [_fail_result()]
    assert _scoped_successors_for_failed_validation(
        jobs, results, accepted_task_ids={"T5A", "T6"}
    ) == ["T5A", "T6"]


def test_passing_job_returns_no_successors() -> None:
    jobs = [_job(["T5A", "T6"])]
    results = [_pass_result()]
    assert (
        _scoped_successors_for_failed_validation(
            jobs, results, accepted_task_ids={"T5A", "T6"}
        )
        == []
    )


def test_failed_job_ignores_non_accepted_tasks() -> None:
    # The scoped successor may only reopen tasks that are in the accepted
    # (completed) set — never launder a task that was not already done.
    jobs = [_job(["T5A", "T6", "T99"])]
    results = [_fail_result()]
    assert _scoped_successors_for_failed_validation(
        jobs, results, accepted_task_ids={"T5A"}
    ) == ["T5A"]


def test_multiple_jobs_deduplicates_successors() -> None:
    jobs = [_job(["T5A", "T6"], job_id="bulk-1"), _job(["T6", "T7"], job_id="bulk-2")]
    results = [_fail_result(), _fail_result()]
    assert _scoped_successors_for_failed_validation(
        jobs, results, accepted_task_ids={"T5A", "T6", "T7"}
    ) == ["T5A", "T6", "T7"]


def test_mixed_pass_fail_jobs_only_reopen_failed_coverage() -> None:
    jobs = [_job(["T5A", "T6"], job_id="bulk-pass"), _job(["T8"], job_id="bulk-fail")]
    results = [_pass_result(), _fail_result()]
    assert _scoped_successors_for_failed_validation(
        jobs, results, accepted_task_ids={"T5A", "T6", "T8"}
    ) == ["T8"]


def test_no_jobs_returns_empty() -> None:
    assert _scoped_successors_for_failed_validation([], [], {"T5A"}) == []


@pytest.mark.parametrize(
    "bad_result",
    [
        {"exit_code": 0, "error": "boom", "timed_out": False},
        {"exit_code": 0, "error": None, "timed_out": True},
        {"exit_code": 2, "error": None, "timed_out": False},
    ],
)
def test_error_timeout_nonzero_all_reopen(bad_result: dict) -> None:
    jobs = [_job(["T5A"])]
    results = [bad_result]
    assert _scoped_successors_for_failed_validation(
        jobs, results, accepted_task_ids={"T5A"}
    ) == ["T5A"]
