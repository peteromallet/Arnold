"""T5.1 elapsed wall-clock task deadlines with legacy v1 compatibility.

Every state-writing test uses an explicit disposable root and proves it is
not a project, candidate, or live runtime root.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.execute.merge import _enforce_task_test_budgets
from arnold_pipelines.megaplan.execute.test_budget import (
    BUDGET_SEMANTICS_V2,
    CLASSIFICATION_V1,
    CLASSIFICATION_V2,
    STATE_FIELD_V1,
    STATE_FIELD_V2,
    BudgetState,
    classify_narrow_tests,
    classify_task_budget,
    complete_run,
    load_budget_state,
    persist_budget_state,
    run_elapsed_command,
    settle_interrupted_active_run,
    subprocess_timeout_seconds,
    v2_admission_for_command,
)
from arnold_pipelines.megaplan.finalize_contract import FINALIZE_MODEL_OUTPUT_SCHEMA
from arnold_pipelines.megaplan.handlers.finalize import _force_new_plan_elapsed_budget_v2
from arnold_pipelines.megaplan.orchestration.finalize_authority import (
    FinalizeMutationContext,
    _validate_field_ownership,
)
from arnold_pipelines.megaplan.orchestration.task_feasibility import compile_task_feasibility
from arnold_pipelines.megaplan.orchestration.task_splitter import (
    _build_impl_narrow_tests,
    _proof_is_exhausted,
)
from arnold_pipelines.megaplan.orchestration.validation_jobs import _compile_narrow_recheck

REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert_disposable_root(root: Path) -> Path:
    resolved = root.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    assert resolved != REPO_ROOT
    assert REPO_ROOT not in resolved.parents
    assert "runtime-candidates" not in resolved.parts
    assert not (resolved / "arnold_pipelines" / "megaplan").exists()
    sentinel = resolved / ".t51-disposable-root"
    sentinel.write_text("disposable\n", encoding="utf-8")
    assert sentinel.read_text(encoding="utf-8") == "disposable\n"
    return resolved


class FakeClock:
    def __init__(self, *, mono: float = 1000.0, utc: datetime | None = None) -> None:
        self._mono = mono
        self._utc = utc or datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self._mono

    def utcnow(self) -> datetime:
        return self._utc

    def advance(self, seconds: float) -> None:
        self._mono += seconds
        self._utc = self._utc + timedelta(seconds=seconds)


def _v2_narrow(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "selectors": ["tests/test_t1.py"],
        "budget_semantics": BUDGET_SEMANTICS_V2,
        "test_budget_seconds": 5,
        "max_runs": 2,
    }
    payload.update(overrides)
    return payload


def _v1_narrow(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "selectors": ["tests/test_t1.py"],
        "max_seconds": 120,
        "max_runs": 2,
    }
    payload.update(overrides)
    return payload


def _task(task_id: str, narrow: dict[str, object]) -> dict[str, object]:
    return {
        "id": task_id,
        "objective": f"Implement bounded behavior {task_id}.",
        "description": f"Implement bounded behavior {task_id}.",
        "kind": "code",
        "status": "pending",
        "complexity": 4,
        "complexity_justification": "One contained module contract.",
        "estimated_minutes": 5,
        "depends_on": [],
        "dependency_reasons": {},
        "routing_group": "",
        "write_set": {"paths": [f"src/{task_id.lower()}.py"], "complete": True},
        "narrow_tests": narrow,
        "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
    }


def test_fast_large_timeout_is_admitted_under_v2() -> None:
    target = _task("T1", _v2_narrow(test_budget_seconds=5, max_runs=2))
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": [
            "timeout 120 pytest tests/test_t1.py",
            "timeout 120 pytest tests/test_t1.py",
        ],
        "test_run_durations_seconds": [0.2, 0.2],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([entry], targets_by_id={"T1": target}, issues=issues)
    assert entry["status"] == "done"
    assert issues == []
    assert entry["budget_classification"] == CLASSIFICATION_V2
    assert target["budget_classification"] == CLASSIFICATION_V2
    state = entry[STATE_FIELD_V2]
    assert state["consumed_seconds"] == pytest.approx(0.4)
    assert "max_seconds_exceeded" not in {
        item.get("kind") for item in entry.get("task_test_budget_violations", []) or []
    }


def test_slow_small_timeout_is_enforced_by_elapsed_wall_clock() -> None:
    target = _task("T1", _v2_narrow(test_budget_seconds=1, max_runs=2))
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "slow",
        "commands_run": ["timeout 30 pytest tests/test_t1.py"],
        "test_run_durations_seconds": [1.4],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([entry], targets_by_id={"T1": target}, issues=issues)
    assert entry["status"] == "blocked"
    assert "elapsed wall-clock budget exhausted" in entry["executor_notes"]
    kinds = {item["kind"] for item in entry["task_test_budget_violations"]}
    assert "elapsed_budget_exhausted" in kinds
    assert "max_seconds_exceeded" not in kinds


def test_exhausted_before_launch_stops_irrespective_of_declared_timeouts(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "exhausted-before-launch")
    clock = FakeClock()
    task = _task("T1", _v2_narrow(test_budget_seconds=2, max_runs=3))
    persist_budget_state(
        task,
        BudgetState(
            allowed_seconds=2.0,
            consumed_seconds=2.0,
            run_count=1,
            active_run=None,
            updated_at_utc="2026-08-21T12:00:00.000000Z",
        ),
    )
    (root / "state.json").write_text(json.dumps(task[STATE_FIELD_V2]), encoding="utf-8")
    decision, _state = v2_admission_for_command(
        task,
        "timeout 120 pytest tests/test_t1.py",
        run_id="run-1",
        clock=clock,
        command_timeout=120,
    )
    assert decision.admitted is False
    assert decision.kind == "elapsed_budget_exhausted"
    assert decision.remaining_seconds == 0.0
    assert decision.subprocess_timeout_seconds == 0.0


def test_sleep_command_is_capped_by_remaining_budget(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "sleep-slow-command")
    task = _task("T1", _v2_narrow(test_budget_seconds=1, max_runs=2))
    started = time.monotonic()
    decision = run_elapsed_command(
        task,
        f"sleep 5",
        run_id="sleep-1",
        command_timeout=30,
    )
    elapsed = time.monotonic() - started
    assert decision.subprocess_timeout_seconds == pytest.approx(1.0)
    assert elapsed < 2.5
    assert task[STATE_FIELD_V2]["consumed_seconds"] >= 0.5
    assert "monotonic" not in json.dumps(task[STATE_FIELD_V2])
    assert (root / ".t51-disposable-root").exists()


def test_interrupted_subprocess_and_resume_cannot_reset_consumed(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "resume-charge")
    clock = FakeClock()
    task = _task("T1", _v2_narrow(test_budget_seconds=10, max_runs=3))
    first = run_elapsed_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="run-a",
        clock=clock,
        command_timeout=30,
        runner=lambda timeout: 3.0,
    )
    assert first.state is not None
    assert first.state.consumed_seconds == pytest.approx(3.0)
    (root / "after-first.json").write_text(json.dumps(task[STATE_FIELD_V2]), encoding="utf-8")

    decision, launched = v2_admission_for_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="run-b",
        clock=clock,
        command_timeout=30,
    )
    assert decision.admitted is True
    persist_budget_state(task, launched)
    interrupted = json.loads(json.dumps(task[STATE_FIELD_V2]))
    assert interrupted["active_run"]["run_id"] == "run-b"
    (root / "interrupted.json").write_text(json.dumps(interrupted), encoding="utf-8")

    resume_clock = FakeClock(utc=clock.utcnow() + timedelta(seconds=4))
    resumed = load_budget_state(task, clock=resume_clock)
    assert resumed is not None
    assert resumed.active_run is None
    assert resumed.consumed_seconds == pytest.approx(7.0)
    assert resumed.run_count == 2
    persist_budget_state(task, resumed)
    retry = run_elapsed_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="run-c",
        clock=resume_clock,
        command_timeout=30,
        runner=lambda timeout: 0.5,
    )
    assert retry.state is not None
    assert retry.state.consumed_seconds == pytest.approx(7.5)
    assert retry.state.run_count == 3


def test_monotonic_within_process_and_utc_persisted(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "clock-abstraction")
    clock = FakeClock()
    task = _task("T1", _v2_narrow(test_budget_seconds=8, max_runs=2))
    decision, launched = v2_admission_for_command(
        task,
        "timeout 20 pytest tests/test_t1.py",
        run_id="mono-1",
        clock=clock,
        command_timeout=20,
    )
    assert decision.admitted is True
    persist_budget_state(task, launched)
    encoded = json.dumps(task[STATE_FIELD_V2])
    (root / "state.json").write_text(encoded, encoding="utf-8")
    assert "monotonic" not in encoded
    assert launched.active_run is not None
    assert launched.active_run.started_at_utc.endswith("Z")
    completed = complete_run(launched, monotonic_duration_seconds=1.25, clock=clock)
    assert completed.consumed_seconds == pytest.approx(1.25)
    persist_budget_state(task, completed)
    assert "monotonic" not in json.dumps(task[STATE_FIELD_V2])


def test_backward_clock_fails_closed_and_consumes_remaining(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "backward-clock")
    clock = FakeClock()
    task = _task("T1", _v2_narrow(test_budget_seconds=6, max_runs=2))
    _decision, launched = v2_admission_for_command(
        task,
        "timeout 20 pytest tests/test_t1.py",
        run_id="back-1",
        clock=clock,
        command_timeout=20,
    )
    persist_budget_state(task, launched)
    (root / "launched.json").write_text(json.dumps(task[STATE_FIELD_V2]), encoding="utf-8")
    past = FakeClock(utc=clock.utcnow() - timedelta(seconds=30))
    settled = settle_interrupted_active_run(launched, clock=past)
    assert settled.active_run is None
    assert settled.consumed_seconds == pytest.approx(6.0)
    persist_budget_state(task, settled)
    later = v2_admission_for_command(
        task,
        "timeout 20 pytest tests/test_t1.py",
        run_id="back-2",
        clock=past,
        command_timeout=20,
    )[0]
    assert later.admitted is False
    assert later.kind == "elapsed_budget_exhausted"


def test_legacy_v1_classification_visible_and_timeout_sum_retained() -> None:
    target = _task("T1", _v1_narrow())
    classification = classify_narrow_tests(target["narrow_tests"])
    assert classification.visible == CLASSIFICATION_V1
    assert classification.semantics == CLASSIFICATION_V1
    doubled = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": [
            "timeout 120 pytest tests/test_t1.py",
            "timeout 120 pytest tests/test_t1.py",
        ],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([doubled], targets_by_id={"T1": target}, issues=issues)
    assert doubled["status"] == "blocked"
    assert doubled["budget_classification"] == CLASSIFICATION_V1
    assert "declared test timeout total 240s exceeds max_seconds=120" in doubled["executor_notes"]
    assert STATE_FIELD_V2 not in doubled
    assert STATE_FIELD_V2 not in target


def test_legacy_and_v2_never_mix_state_fields(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "no-mix")
    mixed = _v2_narrow()
    mixed[STATE_FIELD_V1] = {"consumed_seconds": 1}
    mixed[STATE_FIELD_V2] = {
        "allowed_seconds": 5,
        "consumed_seconds": 0,
        "run_count": 0,
        "active_run": None,
        "updated_at_utc": "2026-08-21T12:00:00.000000Z",
    }
    (root / "mixed.json").write_text(json.dumps(mixed), encoding="utf-8")
    classification = classify_narrow_tests(mixed)
    assert classification.mixes_state_fields is True
    target = _task("T1", mixed)
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": ["timeout 5 pytest tests/test_t1.py"],
        "test_run_durations_seconds": [0.1],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([entry], targets_by_id={"T1": target}, issues=issues)
    assert entry["status"] == "blocked"
    kinds = {item["kind"] for item in entry["task_test_budget_violations"]}
    assert kinds == {"mixed_budget_state"}


def test_max_runs_and_deadline_enforced_at_same_seam() -> None:
    clock = FakeClock()
    task = _task("T1", _v2_narrow(test_budget_seconds=10, max_runs=1))
    first = run_elapsed_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="r1",
        clock=clock,
        command_timeout=30,
        runner=lambda timeout: 1.0,
    )
    assert first.state is not None
    assert first.state.run_count == 1
    second, state = v2_admission_for_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="r2",
        clock=clock,
        command_timeout=30,
    )
    assert second.admitted is False
    assert second.kind == "max_runs_exceeded"
    assert state is not None
    assert state.consumed_seconds == pytest.approx(1.0)

    exhausted = _task("T2", _v2_narrow(test_budget_seconds=1, max_runs=5))
    persist_budget_state(
        exhausted,
        BudgetState(
            allowed_seconds=1.0,
            consumed_seconds=1.0,
            run_count=0,
            active_run=None,
            updated_at_utc="2026-08-21T12:00:00.000000Z",
        ),
    )
    deadline, _ = v2_admission_for_command(
        exhausted,
        "timeout 30 pytest tests/test_t1.py",
        run_id="r3",
        clock=clock,
        command_timeout=30,
    )
    assert deadline.admitted is False
    assert deadline.kind == "elapsed_budget_exhausted"


def test_subprocess_timeout_is_min_of_command_and_remaining() -> None:
    assert subprocess_timeout_seconds(30, 5) == 5
    assert subprocess_timeout_seconds(2, 10) == 2
    assert subprocess_timeout_seconds(None, 7) == 7
    assert subprocess_timeout_seconds(8, 0) == 0


def test_feasibility_emits_visible_v1_and_v2_classifications() -> None:
    v2 = _task("T1", _v2_narrow())
    v1 = _task("T2", _v1_narrow())
    v2_report = compile_task_feasibility(
        {"task_contract_version": 2, "tasks": [v2], "validation_jobs": []}
    )
    v1_report = compile_task_feasibility(
        {"tasks": [v1], "validation_jobs": []}
    )
    by_id = {row["task_id"]: row for row in v2_report["budget_classifications"] + v1_report["budget_classifications"]}
    assert by_id["T1"]["budget_classification"] == CLASSIFICATION_V2
    assert by_id["T2"]["budget_classification"] == CLASSIFICATION_V1
    assert by_id["T1"]["enforcement_seam"] == "arnold_pipelines.megaplan.execute.test_budget"
    assert "elapsed_wall_clock_v2" in by_id["T1"]["message"]
    assert "declared_timeout_sum_v1" in by_id["T2"]["message"]
    mixed = compile_task_feasibility(
        {"task_contract_version": 2, "tasks": [v1], "validation_jobs": []}
    )
    codes = {item["code"] for item in mixed["diagnostics"]}
    assert "task_test_budget_v2_required" in codes
    assert mixed["admitted"] is False


def test_splitter_and_validation_jobs_describe_seam_without_timeout_sum() -> None:
    v2 = _task("T1", _v2_narrow(test_budget_seconds=8, max_runs=2))
    assert _proof_is_exhausted(v2) is False
    impl = _build_impl_narrow_tests(v2)
    assert impl["budget_semantics"] == BUDGET_SEMANTICS_V2
    assert impl["test_budget_seconds"] == 8
    assert "execute.test_budget" in impl["budget_enforcement_note"] or "elapsed_wall_clock_v2" in impl["budget_enforcement_note"]
    job = _compile_narrow_recheck(v2, existing_jobs=[])
    assert job is not None
    assert job["budget_classification"] == CLASSIFICATION_V2
    assert job["timeout_seconds"] == 8
    assert job["budget_description"]["enforcement_seam"] == "arnold_pipelines.megaplan.execute.test_budget"

    v1 = _task("T2", _v1_narrow(max_seconds=90, max_runs=2))
    v1_job = _compile_narrow_recheck(v1, existing_jobs=[])
    assert v1_job is not None
    assert v1_job["budget_classification"] == CLASSIFICATION_V1
    assert v1_job["timeout_seconds"] == 90

def test_merge_charges_elapsed_from_commands_run_without_duration_list() -> None:
    target = _task("T1", _v2_narrow(test_budget_seconds=5, max_runs=2))
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": ["timeout 30 pytest tests/test_t1.py"],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([entry], targets_by_id={"T1": target}, issues=issues)
    assert entry["status"] == "blocked"
    assert entry[STATE_FIELD_V2]["consumed_seconds"] == pytest.approx(5.0)
    assert entry[STATE_FIELD_V2]["consumed_seconds"] != 0.0
    assert "elapsed_budget_exhausted" in {
        item["kind"] for item in entry["task_test_budget_violations"]
    }


def test_merge_fast_command_under_budget_without_duration_list_stays_done() -> None:
    target = _task("T1", _v2_narrow(test_budget_seconds=5, max_runs=2))
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": ["timeout 2 pytest tests/test_t1.py"],
        "test_run_durations_seconds": [0.2],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([entry], targets_by_id={"T1": target}, issues=issues)
    assert entry["status"] == "done"
    assert issues == []
    assert entry[STATE_FIELD_V2]["consumed_seconds"] == pytest.approx(0.2)
    assert entry[STATE_FIELD_V2]["run_count"] == 1


def test_production_runner_kills_slow_command_and_admits_fast_command(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "prod-slow-fast")
    slow = _task("T1", _v2_narrow(test_budget_seconds=1, max_runs=2))
    started = time.monotonic()
    slow_decision = run_elapsed_command(
        slow,
        "sleep 5",
        run_id="slow",
        command_timeout=30,
    )
    slow_elapsed = time.monotonic() - started
    assert slow_decision.subprocess_timeout_seconds == pytest.approx(1.0)
    assert slow_elapsed < 2.5
    assert slow[STATE_FIELD_V2]["consumed_seconds"] >= 0.5
    assert slow[STATE_FIELD_V2]["run_count"] == 1
    assert slow_decision.admitted is False
    assert slow_decision.kind == "elapsed_budget_exhausted"

    fast = _task("T2", _v2_narrow(test_budget_seconds=5, max_runs=2))
    fast_started = time.monotonic()
    fast_decision = run_elapsed_command(
        fast,
        "true",
        run_id="fast",
        command_timeout=30,
    )
    fast_elapsed = time.monotonic() - fast_started
    assert fast_decision.subprocess_timeout_seconds == pytest.approx(5.0)
    assert fast_elapsed < 2.0
    assert fast[STATE_FIELD_V2]["consumed_seconds"] < 2.0
    assert fast[STATE_FIELD_V2]["run_count"] == 1
    assert fast_decision.admitted is True
    assert (root / ".t51-disposable-root").exists()


def test_admission_stops_at_zero_remaining_budget() -> None:
    task = _task("T1", _v2_narrow(test_budget_seconds=1, max_runs=5))
    first = run_elapsed_command(
        task,
        "sleep 5",
        run_id="first",
        command_timeout=30,
    )
    assert first.admitted is False
    second, state = v2_admission_for_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="second",
        command_timeout=30,
    )
    assert second.admitted is False
    assert second.kind == "elapsed_budget_exhausted"
    assert second.subprocess_timeout_seconds == 0.0
    assert state is not None
    assert state.remaining_seconds() == 0.0


def test_v2_budget_block_is_execute_mutable() -> None:
    before = {
        "tasks": [
            {
                "id": "T1",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
            }
        ]
    }
    after = {
        "tasks": [
            {
                "id": "T1",
                "status": "blocked",
                "executor_notes": "task_test_budget_exhausted",
                "files_changed": [],
                "commands_run": ["timeout 30 pytest tests/test_t1.py"],
                "task_test_budget_exhausted": "elapsed wall-clock budget exhausted",
                "task_test_budget_violations": [{"kind": "elapsed_budget_exhausted"}],
                "budget_classification": CLASSIFICATION_V2,
                "test_budget_state_v2": {
                    "allowed_seconds": 1.0,
                    "consumed_seconds": 1.0,
                    "run_count": 1,
                    "active_run": None,
                    "updated_at_utc": "2026-08-21T12:00:00.000000Z",
                },
                "test_run_durations_seconds": [1.0],
            }
        ]
    }
    context = FinalizeMutationContext(owner="execute", operation="t51-block", attempt_id="a1")
    paths = _validate_field_ownership(before, after, context)
    assert "tasks[T1].task_test_budget_violations" in paths
    assert "tasks[T1].test_budget_state_v2" in paths


def test_new_finalize_schema_requires_elapsed_v2_fields() -> None:
    required = FINALIZE_MODEL_OUTPUT_SCHEMA["properties"]["tasks"]["items"]["properties"]["narrow_tests"]["required"]
    assert "budget_semantics" in required
    assert "test_budget_seconds" in required
    assert "max_runs" in required
    assert "max_seconds" not in required
    properties = FINALIZE_MODEL_OUTPUT_SCHEMA["properties"]["tasks"]["items"]["properties"]["narrow_tests"]["properties"]
    assert "max_seconds" not in properties
    payload = {
        "task_contract_version": 1,
        "tasks": [
            {
                "id": "T1",
                "narrow_tests": {"selectors": ["tests/test_t1.py"], "max_seconds": 90, "max_runs": 2},
            }
        ],
    }
    _force_new_plan_elapsed_budget_v2(payload)
    assert payload["task_contract_version"] == 2
    narrow = payload["tasks"][0]["narrow_tests"]
    assert narrow["budget_semantics"] == BUDGET_SEMANTICS_V2
    assert narrow["test_budget_seconds"] == 90
    assert narrow["max_runs"] == 2
    assert "max_seconds" not in narrow


def test_persisted_top_level_v2_and_nested_v1_is_mixed(tmp_path: Path) -> None:
    root = _assert_disposable_root(tmp_path / "persisted-mix")
    task = _task("T1", _v2_narrow())
    task[STATE_FIELD_V2] = {
        "allowed_seconds": 5,
        "consumed_seconds": 0,
        "run_count": 0,
        "active_run": None,
        "updated_at_utc": "2026-08-21T12:00:00.000000Z",
    }
    task["narrow_tests"][STATE_FIELD_V1] = {"consumed_seconds": 1}
    (root / "mixed.json").write_text(json.dumps(task), encoding="utf-8")
    classification = classify_task_budget(task)
    assert classification.mixes_state_fields is True
    entry = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": ["timeout 5 pytest tests/test_t1.py"],
        "test_run_durations_seconds": [0.1],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([entry], targets_by_id={"T1": task}, issues=issues)
    assert entry["status"] == "blocked"
    assert {item["kind"] for item in entry["task_test_budget_violations"]} == {"mixed_budget_state"}


def test_one_run_count_source_at_complete_and_interrupted_settlement() -> None:
    clock = FakeClock()
    task = _task("T1", _v2_narrow(test_budget_seconds=10, max_runs=3))
    first = run_elapsed_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="r1",
        clock=clock,
        command_timeout=30,
        runner=lambda timeout: 1.0,
    )
    assert first.state is not None
    assert first.state.run_count == 1
    decision, launched = v2_admission_for_command(
        task,
        "timeout 30 pytest tests/test_t1.py",
        run_id="r2",
        clock=clock,
        command_timeout=30,
    )
    assert decision.admitted is True
    persist_budget_state(task, launched)
    resume_clock = FakeClock(utc=clock.utcnow() + timedelta(seconds=2))
    settled = load_budget_state(task, clock=resume_clock)
    assert settled is not None
    assert settled.active_run is None
    assert settled.run_count == 2


def test_live_subprocess_complete_run_does_not_double_charge(tmp_path: Path) -> None:
    """G5-001: persist active_run, suite duration=3 -> consumed==3, run_count==1."""

    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import _run_batch_validation_jobs
    from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

    root = _assert_disposable_root(tmp_path / "g5-001-one-charge")
    plan_dir = root / "plan"
    project_dir = root / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    selector = "tests/test_t1.py"
    selector_path = project_dir / selector
    selector_path.parent.mkdir(parents=True, exist_ok=True)
    selector_path.write_text("def test_ok(): pass\n", encoding="utf-8")

    task = _task("T1", _v2_narrow(test_budget_seconds=10, max_runs=3))
    task["write_set"] = {"paths": [selector], "complete": True}
    command = f"python3 -m pytest {selector} --tb=short -q"
    fake = SuiteRunResult(
        run_id="g5-001",
        phase="m8a_validation",
        command=command,
        duration=3.0,
        collected=1,
        collected_ids=["tests/test_t1.py::test_ok"],
        failures=[],
        passes=["tests/test_t1.py::test_ok"],
        status="passed",
        exit_code=0,
        raw_log_path=project_dir / "raw.log",
        code_hash="sha256:g5-001",
        collections_parse_ok=True,
    )
    finalize_data = {
        "tasks": [task],
        "validation_jobs": [
            {
                "id": "VJ-G5-001",
                "kind": "narrow_recheck",
                "command": command,
                "selectors": [selector],
                "timeout_seconds": 30,
                "task_id": "T1",
                "mutates": False,
                "writes_files": False,
                "expected_exit_codes": [0],
            }
        ],
    }
    state = {
        "name": "g5-001",
        "iteration": 1,
        "current_state": "executing",
        "config": {"mode": "code", "project_dir": str(project_dir)},
        "meta": {},
        "history": [],
        "sessions": {},
    }
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with patch(
            "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            return_value={"event_id": "ev"},
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
            ):
                evidence = _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=state,
                )
    assert evidence
    assert evidence[0]["status"] == "passed"
    charged = load_budget_state(task)
    assert charged is not None
    assert charged.active_run is None
    assert charged.consumed_seconds == 3.0
    assert charged.run_count == 1
    assert charged.remaining_seconds() == 7.0
    assert (root / ".t51-disposable-root").exists()


def test_v2_timeout_180_is_admitted_by_scope_recovery_side_path() -> None:
    """G5-002: legal v2 timeout 180 with budget 200 is not rejected by v1 timeout-sum."""

    from arnold_pipelines.megaplan.execute.batch import (
        _admit_scope_recovery_verification_commands,
    )

    task = _task(
        "T1",
        _v2_narrow(test_budget_seconds=200, max_runs=2),
    )
    command = "timeout 180 pytest tests/test_t1.py --tb=short -q"
    errors = _admit_scope_recovery_verification_commands(task, [command])
    assert errors == []
    decision, launched = v2_admission_for_command(
        task,
        command,
        run_id="g5-002",
        command_timeout=180,
    )
    assert decision.admitted is True
    assert decision.subprocess_timeout_seconds == 180.0
    assert launched is not None
    assert launched.remaining_seconds() == 200.0

    v1 = _task("T2", _v1_narrow(max_seconds=120, max_runs=2))
    v1_errors = _admit_scope_recovery_verification_commands(v1, [command])
    assert any("exceeds per-command maximum" in item for item in v1_errors)


