"""Validation baseline admission tests — pre-dispatch admission vs strict enforcement.

Proves the M8A execute admission gate accepts pytest exit code 1 ONLY when
every observed failed node ID is a member of the plan's non-empty baseline
(``baseline_known_failures_only``), while deferred/final rechecks and sweeps
stay strict (never subtract) and every ambiguous edge fails closed.

Coverage target: ``arnold_pipelines.megaplan.execute.batch._run_batch_validation_jobs``
(admission kwarg) + ``_baseline_known_failures_only`` + ``_validation_failure_ids``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    CliError,
    _baseline_known_failures_only,
    _run_batch_validation_jobs,
    _validation_failure_ids,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

BASELINE = [
    "tests/a/test_x.py::test_one",
    "tests/a/test_x.py::test_two",
    "tests/a/test_x.py::test_three",
    "tests/a/test_x.py::test_four",
    "tests/a/test_x.py::test_five",
    "tests/a/test_x.py::test_six",
    "tests/b/test_y.py::test_seven",
]

KNOWN_FAILURES = BASELINE[:6]
NEW_FAILURE = "tests/c/test_z.py::test_brand_new"


def _finalize_data(*, baseline: object = BASELINE, extra_jobs: list[dict] | None = None) -> dict:
    """Minimal finalize payload: no ``tasks`` key (legacy path), baseline present."""
    return {
        "validation_jobs": [
            {
                "id": "VJ4",
                "kind": "narrow_recheck",
                "command": "pytest tests/a/test_x.py",
                "selectors": ["tests/a/test_x.py"],
                "max_seconds": 60,
                "max_runs": 1,
                "reason": "Narrow recheck T3",
                "task_id": "T3",
                "writes_files": False,
                "mutates": False,
            },
            *(extra_jobs or []),
        ],
        "baseline_test_failures": baseline,
    }


def _fake_result(
    *,
    exit_code: int | None = 1,
    failures: list[str] | None = None,
    status: str = "failed",
    collection_errors: list[str] | None = None,
    timeout_reason: str | None = None,
) -> SuiteRunResult:
    return SuiteRunResult(
        run_id="fake-run-admission",
        phase="m8a_validation",
        command="pytest tests/a/test_x.py",
        duration=0.1,
        collected=10,
        collected_ids=list(failures or []) + ["tests/a/test_x.py::test_pass"],
        failures=list(failures or []),
        passes=["tests/a/test_x.py::test_pass"],
        status=status,  # type: ignore[arg-type]
        exit_code=exit_code,
        raw_log_path=Path("/tmp/fake_raw_admission.log"),
        code_hash="sha256:aaa",
        collections_parse_ok=True,
        collection_errors=collection_errors,
        timeout_reason=timeout_reason,
    )


def _run_vj(tmp_path: Path, *, result: SuiteRunResult, admission: bool = False) -> list[dict]:
    """Run the VJ4 narrow_recheck job through the real helper with mocks."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    finalize_data = _finalize_data()
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=result,
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev-1", "event_class": "validation"},
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
            ):
                return _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T3"],
                    is_final_batch=False,
                    admission=admission,
                )


# ---------------------------------------------------------------------------
# Classifier unit tests
# ---------------------------------------------------------------------------


def test_validation_failure_ids_normalizes_strings_and_node_id_records() -> None:
    assert _validation_failure_ids(["a::b", "c::d"]) == ["a::b", "c::d"]
    assert _validation_failure_ids([{"node_id": "a::b"}]) == ["a::b"]
    assert _validation_failure_ids(None) is None
    assert _validation_failure_ids([]) is None
    assert _validation_failure_ids(["a::b", 7]) is None
    assert _validation_failure_ids(["a::b", ""]) is None
    assert _validation_failure_ids([{"node_id": 7}]) is None


def test_baseline_classifier_admits_only_known_ids() -> None:
    assert _baseline_known_failures_only(
        exit_code=1,
        failed_test_ids=KNOWN_FAILURES,
        baseline_test_failures=BASELINE,
        collection_errors=[],
        timeout_reason=None,
        status="failed",
    ) == sorted(KNOWN_FAILURES)


def test_baseline_classifier_blocks_new_failure() -> None:
    assert _baseline_known_failures_only(
        exit_code=1,
        failed_test_ids=KNOWN_FAILURES + [NEW_FAILURE],
        baseline_test_failures=BASELINE,
        collection_errors=[],
        timeout_reason=None,
        status="failed",
    ) is None


@pytest.mark.parametrize(
    ("kwargs", "label"),
    [
        ({"exit_code": 2}, "exit code 2 (collection/usage)"),
        ({"exit_code": 5}, "exit code 5 (no tests collected)"),
        ({"exit_code": None}, "null exit code"),
        ({"status": "timeout"}, "timeout status"),
        ({"status": "runner_error"}, "runner error status"),
        ({"timeout_reason": "deadline"}, "timeout reason"),
        ({"collection_errors": ["pytest_collection_error"]}, "collection errors"),
        ({"baseline_test_failures": None}, "null baseline"),
        ({"baseline_test_failures": []}, "empty baseline"),
        ({"baseline_test_failures": "not-a-list"}, "malformed baseline"),
        ({"failed_test_ids": []}, "empty observed failures"),
        ({"failed_test_ids": None}, "null observed failures"),
    ],
)
def test_baseline_classifier_fails_closed(kwargs: dict, label: str) -> None:
    base = dict(
        exit_code=1,
        failed_test_ids=KNOWN_FAILURES,
        baseline_test_failures=BASELINE,
        collection_errors=[],
        timeout_reason=None,
        status="failed",
    )
    base.update(kwargs)
    # baseline_test_failures lives at the top level of the classifier kwargs,
    # but the parametrize above uses a shorter key for readability.
    if "baseline_test_failures" in kwargs and kwargs["baseline_test_failures"] is not None:
        base["baseline_test_failures"] = kwargs["baseline_test_failures"]
    assert _baseline_known_failures_only(**base) is None, f"must fail closed: {label}"


# ---------------------------------------------------------------------------
# Integration: _run_batch_validation_jobs with admission=True at pre-dispatch
# ---------------------------------------------------------------------------


def test_predispatch_admits_only_baseline_failures_and_preserves_exit_code(
    tmp_path: Path,
) -> None:
    evidence = _run_vj(
        tmp_path,
        result=_fake_result(failures=KNOWN_FAILURES),
        admission=True,
    )
    assert len(evidence) == 1
    row = evidence[0]
    assert row["job_id"] == "VJ4"
    assert row["kind"] == "narrow_recheck"
    # The real result is preserved — admission never rewrites the exit code.
    assert row["exit_code"] == 1
    assert row["status"] == "baseline_known_failures_only"
    assert row["admission"] == "pre_dispatch"
    assert row["subtracted_test_ids"] == sorted(KNOWN_FAILURES)
    assert row["new_failed_test_ids"] == []
    assert row["baseline_test_failures_count"] == len(BASELINE)


def test_predispatch_blocks_when_any_failure_is_new(tmp_path: Path) -> None:
    with pytest.raises(CliError) as exc_info:
        _run_vj(
            tmp_path,
            result=_fake_result(failures=KNOWN_FAILURES + [NEW_FAILURE]),
            admission=True,
        )
    assert exc_info.value.code == "validation_job_failed"


@pytest.mark.parametrize(
    "result_kwargs",
    [
        {"status": "timeout", "exit_code": None, "timeout_reason": "deadline"},
        {"exit_code": 2, "status": "runner_error"},
        {"collection_errors": ["pytest_collection_error"]},
        {"failures": []},
    ],
)
def test_predispatch_admission_fails_closed_without_usable_pytest_evidence(
    tmp_path: Path, result_kwargs: dict,
) -> None:
    with pytest.raises(CliError) as exc_info:
        _run_vj(
            tmp_path,
            result=_fake_result(**result_kwargs),
            admission=True,
        )
    assert exc_info.value.code == "validation_job_failed"


def test_predispatch_admission_fails_closed_on_null_and_empty_baseline(
    tmp_path: Path,
) -> None:
    for i, baseline in enumerate((None, [], "not-a-list")):
        plan_dir = tmp_path / f"plan_{i}"
        project_dir = tmp_path / f"project_{i}"
        plan_dir.mkdir()
        project_dir.mkdir()
        finalize_data = _finalize_data(baseline=baseline)
        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=_fake_result(failures=KNOWN_FAILURES),
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-1", "event_class": "validation"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    with pytest.raises(CliError) as exc_info:
                        _run_batch_validation_jobs(
                            plan_dir=plan_dir,
                            project_dir=project_dir,
                            finalize_data=finalize_data,
                            batch_task_ids=["T3"],
                            is_final_batch=False,
                            admission=True,
                        )
                    assert exc_info.value.code == "validation_job_failed"


def test_predispatch_admission_does_not_apply_to_post_execute_suite(
    tmp_path: Path,
) -> None:
    """Admission is narrow_recheck-only: a failing post-execute suite blocks."""
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    finalize_data = {
        "validation_jobs": [
            {
                "id": "VJ1",
                "kind": "post_execute_suite",
                "command": "pytest tests/a/test_x.py",
                "selectors": ["tests/a/test_x.py"],
                "max_seconds": 60,
                "writes_files": False,
                "mutates": False,
            },
        ],
        "baseline_test_failures": BASELINE,
    }
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=_fake_result(failures=KNOWN_FAILURES),
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev-1", "event_class": "validation"},
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
            ):
                with pytest.raises(CliError) as exc_info:
                    _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T3"],
                        is_final_batch=True,
                        admission=True,
                    )
                assert exc_info.value.code == "validation_job_failed"


# ---------------------------------------------------------------------------
# Strictness: deferred recheck / final sweep callers never subtract
# ---------------------------------------------------------------------------


def test_deferred_and_final_rechecks_remain_strict(tmp_path: Path) -> None:
    """Default admission=False (the deferred/sweep call sites) still blocks."""
    with pytest.raises(CliError) as exc_info:
        _run_vj(
            tmp_path,
            result=_fake_result(failures=KNOWN_FAILURES),
            admission=False,
        )
    assert exc_info.value.code == "validation_job_failed"
