from __future__ import annotations

import json
import multiprocessing as mp
import time
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._core.hermes_fanout import scatter_gather, scatter_gather_checks, scatter_gather_processes


def _process_unit(index, unit):
    if unit == "fail":
        raise RuntimeError("process failed")
    return index, {"unit": unit, "status": "complete"}, 0.1, 1, 2, 3


def _slow_process_unit(index, unit):
    if unit == "slow":
        time.sleep(5)
    return index, {"unit": unit, "status": "complete"}, 0.1, 1, 2, 3


def _ignore_term_process_unit(index, unit):
    if unit == "ignore-term":
        import signal

        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(5)
    return index, {"unit": unit, "status": "complete"}, 0.1, 1, 2, 3


def _structured_process_unit(index, unit):
    metadata = unit["metadata"]
    metrics = unit["metrics"]
    return (
        index,
        {
            "unit": metadata["name"],
            "status": "complete",
            "tags": list(metadata["tags"]),
            "sources": list(metadata["sources"]),
        },
        metrics["cost"],
        metrics["prompt_tokens"],
        metrics["completion_tokens"],
        metrics["total_tokens"],
    )


def _track_concurrency_process_unit(index, unit):
    if "counter_path" in unit:
        import fcntl

        counter_path = Path(unit["counter_path"])
        lock_path = Path(unit["lock_path"])

        def _update(delta: int) -> None:
            with lock_path.open("a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    if counter_path.exists():
                        data = json.loads(counter_path.read_text(encoding="utf-8"))
                    else:
                        data = {"active": 0, "peak": 0}
                    data["active"] += delta
                    data["peak"] = max(data["peak"], data["active"])
                    counter_path.write_text(json.dumps(data), encoding="utf-8")
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        _update(1)
        try:
            time.sleep(unit["sleep_seconds"])
            return index, {"unit": unit["name"], "status": "complete"}, 0.0, 0, 0, 0
        finally:
            _update(-1)

    lock = unit["lock"]
    active = unit["active"]
    peak = unit["peak"]
    with lock:
        active.value += 1
        if active.value > peak.value:
            peak.value = active.value
    try:
        time.sleep(unit["sleep_seconds"])
        return index, {"unit": unit["name"], "status": "complete"}, 0.0, 0, 0, 0
    finally:
        with lock:
            active.value -= 1


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
    assert result.total_cost == pytest.approx(0.6)
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


def test_scatter_gather_processes_accepts_picklable_top_level_callable_and_payloads() -> None:
    units = [
        {
            "metadata": {
                "name": "alpha",
                "tags": ["triage", "docs"],
                "sources": ["brief.md", "state.idea"],
            },
            "metrics": {
                "cost": 0.15,
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        },
        {
            "metadata": {
                "name": "beta",
                "tags": ["tests"],
                "sources": ["plan_v1.meta.json"],
            },
            "metrics": {
                "cost": 0.05,
                "prompt_tokens": 3,
                "completion_tokens": 2,
                "total_tokens": 5,
            },
        },
    ]

    result = scatter_gather_processes(
        units=units,
        run_unit_fn=_structured_process_unit,
        max_concurrent=2,
    )

    assert result.ordered_results == [
        {
            "unit": "alpha",
            "status": "complete",
            "tags": ["triage", "docs"],
            "sources": ["brief.md", "state.idea"],
        },
        {
            "unit": "beta",
            "status": "complete",
            "tags": ["tests"],
            "sources": ["plan_v1.meta.json"],
        },
    ]
    assert result.total_cost == pytest.approx(0.2)
    assert result.total_prompt_tokens == 14
    assert result.total_completion_tokens == 9
    assert result.total_tokens == 23


def test_scatter_gather_processes_honors_max_concurrent(tmp_path: Path) -> None:
    counter_path = tmp_path / "counter.json"
    lock_path = tmp_path / "counter.lock"
    counter_path.write_text(json.dumps({"active": 0, "peak": 0}), encoding="utf-8")
    units = [
        {
            "name": f"unit-{idx}",
            "sleep_seconds": 0.1,
            "counter_path": str(counter_path),
            "lock_path": str(lock_path),
        }
        for idx in range(4)
    ]

    result = scatter_gather_processes(
        units=units,
        run_unit_fn=_track_concurrency_process_unit,
        max_concurrent=2,
    )
    peak_value = json.loads(counter_path.read_text(encoding="utf-8"))["peak"]

    assert peak_value == 2
    assert result.ordered_results == [
        {"unit": "unit-0", "status": "complete"},
        {"unit": "unit-1", "status": "complete"},
        {"unit": "unit-2", "status": "complete"},
        {"unit": "unit-3", "status": "complete"},
    ]
    assert result.total_cost == 0.0
    assert result.total_prompt_tokens == 0
    assert result.total_completion_tokens == 0
    assert result.total_tokens == 0


def test_scatter_gather_processes_returns_empty_result_without_processes() -> None:
    result = scatter_gather_processes(units=[], run_unit_fn=_process_unit)

    assert result.ordered_results == []
    assert result.side_results == []
    assert result.total_cost == 0.0
    assert result.total_prompt_tokens == 0
    assert result.total_completion_tokens == 0
    assert result.total_tokens == 0


def test_scatter_gather_processes_times_out_unit_and_continues_siblings() -> None:
    units = ["slow", "fast"]

    started = time.monotonic()
    result = scatter_gather_processes(
        units=units,
        run_unit_fn=_slow_process_unit,
        max_concurrent=1,
        timeout_seconds=3.0,
        hard_kill_grace_seconds=0.05,
        on_unit_error=lambda index, exc: (
            {"unit": units[index], "status": "error", "error": str(exc)},
            0.0,
            0,
            0,
            0,
        ),
    )
    elapsed = time.monotonic() - started

    assert elapsed < 7.0
    assert result.ordered_results == [
        {
            "unit": "slow",
            "status": "error",
            "error": "process unit 0 timed out after 3.000s",
        },
        {"unit": "fast", "status": "complete"},
    ]
    assert result.total_cost == pytest.approx(0.1)
    assert result.total_prompt_tokens == 1
    assert result.total_completion_tokens == 2
    assert result.total_tokens == 3


def test_scatter_gather_processes_kills_unit_after_grace_and_continues() -> None:
    units = ["ignore-term", "fast"]

    started = time.monotonic()
    result = scatter_gather_processes(
        units=units,
        run_unit_fn=_ignore_term_process_unit,
        max_concurrent=1,
        timeout_seconds=3.0,
        hard_kill_grace_seconds=0.05,
        on_unit_error=lambda index, exc: (
            {"unit": units[index], "status": "error", "error": str(exc)},
            0.0,
            0,
            0,
            0,
        ),
    )
    elapsed = time.monotonic() - started

    assert elapsed < 7.0, f"Expected kill path under {7.0}s, got {elapsed:.3f}s"
    assert result.ordered_results == [
        {
            "unit": "ignore-term",
            "status": "error",
            "error": "process unit 0 timed out after 3.000s",
        },
        {"unit": "fast", "status": "complete"},
    ]
