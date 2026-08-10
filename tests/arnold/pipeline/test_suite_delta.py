"""Tests for neutral suite delta computation."""

from __future__ import annotations

from dataclasses import dataclass

from arnold.pipeline.suite_delta import SuiteDelta, compute_delta


@dataclass
class _Run:
    failures: list[str]
    collected_ids: list[str]
    duration: float


def test_compute_delta_classifies_nodeids() -> None:
    baseline = _Run(
        failures=["test_old_red", "test_deleted_red"],
        collected_ids=["test_old_red", "test_old_green", "test_deleted_red"],
        duration=1.0,
    )
    verification = _Run(
        failures=["test_old_red", "test_new_red"],
        collected_ids=["test_old_red", "test_old_green", "test_new_red", "test_added_green"],
        duration=2.5,
    )

    delta = compute_delta(baseline, verification)

    assert delta == SuiteDelta(
        computable=True,
        newly_failing=("test_new_red",),
        newly_passing=(),
        still_red=("test_old_red",),
        still_green=("test_old_green",),
        deleted_tests=("test_deleted_red",),
        added_tests=("test_added_green", "test_new_red"),
        flakes=(),
        tests_collected=4,
        duration=2.5,
    )


def test_deleted_failing_tests_do_not_count_as_newly_passing() -> None:
    baseline = _Run(
        failures=["test_removed"],
        collected_ids=["test_removed"],
        duration=1.0,
    )
    verification = _Run(failures=[], collected_ids=[], duration=0.5)

    delta = compute_delta(baseline, verification)

    assert delta.newly_passing == ()
    assert delta.deleted_tests == ("test_removed",)


def test_to_dict_serializes_tuples_as_lists() -> None:
    delta = compute_delta(
        _Run(failures=["test_a"], collected_ids=["test_a", "test_b"], duration=1.0),
        _Run(failures=["test_b"], collected_ids=["test_a", "test_b"], duration=3.0),
    )

    assert delta.to_dict() == {
        "computable": True,
        "newly_failing": ["test_b"],
        "newly_passing": ["test_a"],
        "still_red": [],
        "still_green": [],
        "deleted_tests": [],
        "added_tests": [],
        "flakes": [],
        "tests_collected": 2,
        "duration": 3.0,
        "flake_retry_skipped": False,
        "flake_retry_reason": "",
    }
