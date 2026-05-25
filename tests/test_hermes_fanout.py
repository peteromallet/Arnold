from __future__ import annotations

import time

import pytest

from megaplan._core.hermes_fanout import scatter_gather, scatter_gather_checks, scatter_gather_processes


def _process_unit(index, unit):
    if unit == "fail":
        raise RuntimeError("process failed")
    return index, {"unit": unit, "status": "complete"}, 0.1, 1, 2, 3


def test_scatter_gather_returns_ordered_results_and_tolerates_unit_failures() -> None:
    def _submit_units(executor):
        return [
            executor.submit(lambda: (0, {"unit": "a", "status": "complete"}, 0.2, 3, 4, 7)),
            executor.submit(
                lambda: (_ for _ in ()).throw(RuntimeError("timed out while reading files"))
            ),
            executor.submit(
                lambda: (
                    time.sleep(0.02),
                    (2, {"unit": "c", "status": "complete"}, 0.3, 5, 6, 11),
                )[1]
            ),
        ]

    def _submit_side(executor):
        return executor.submit(lambda: ({"summary": "done"}, 0.4, 7, 8, 15))

    result = scatter_gather(
        num_units=3,
        submit_unit_fn=_submit_units,
        side_tasks=[_submit_side],
        on_unit_error=lambda index, exc: (
            {"unit": index, "status": "error", "error": str(exc)},
            0.0,
            0,
            0,
            0,
        ),
    )

    assert result.ordered_results == [
        {"unit": "a", "status": "complete"},
        {"unit": 1, "status": "error", "error": "timed out while reading files"},
        {"unit": "c", "status": "complete"},
    ]
    assert result.side_results == [({"summary": "done"}, 0.4, 7, 8, 15)]
    assert result.total_cost == pytest.approx(0.9)
    assert result.total_prompt_tokens == 15
    assert result.total_completion_tokens == 18
    assert result.total_tokens == 33


def test_scatter_gather_checks_preserves_order_and_flag_union_semantics() -> None:
    def _submit_checks(executor):
        return [
            executor.submit(
                lambda: (
                    time.sleep(0.02),
                    (0, {"id": "a"}, ["FLAG-1", "FLAG-2"], [], 0.1, 1, 2, 3),
                )[1]
            ),
            executor.submit(lambda: (1, {"id": "b"}, ["FLAG-2", "FLAG-3"], ["FLAG-3"], 0.2, 4, 5, 9)),
            executor.submit(lambda: (2, {"id": "c"}, [], ["FLAG-1"], 0.3, 6, 7, 13)),
        ]

    result = scatter_gather_checks(
        num_checks=3,
        submit_check_fn=_submit_checks,
    )

    assert result.ordered_checks == [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert result.verified_flag_ids == ["FLAG-2"]
    assert result.disputed_flag_ids == ["FLAG-3", "FLAG-1"]
    assert result.total_cost == 0.6
    assert result.total_prompt_tokens == 11
    assert result.total_completion_tokens == 14
    assert result.total_tokens == 25


def test_scatter_gather_processes_returns_ordered_sentinels_for_failures() -> None:
    units = ["a", "fail", "c"]

    result = scatter_gather_processes(
        units=units,
        run_unit_fn=_process_unit,
        max_concurrent=2,
        on_unit_error=lambda index, exc: (
            {"unit": units[index], "status": "error", "error": str(exc)},
            0.0,
            0,
            0,
            0,
        ),
    )

    assert result.ordered_results == [
        {"unit": "a", "status": "complete"},
        {"unit": "fail", "status": "error", "error": "process failed"},
        {"unit": "c", "status": "complete"},
    ]
    assert result.total_cost == pytest.approx(0.2)
    assert result.total_prompt_tokens == 2
    assert result.total_completion_tokens == 4
    assert result.total_tokens == 6
