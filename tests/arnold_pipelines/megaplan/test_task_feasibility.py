from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    assert_admitted_task_feasibility,
    compile_task_feasibility,
)


def _task(
    task_id: str,
    *,
    depends_on: list[str] | None = None,
    minutes: int = 5,
    paths: list[str] | None = None,
    complexity: int = 4,
) -> dict:
    deps = list(depends_on or [])
    return {
        "id": task_id,
        "objective": f"Implement bounded behavior {task_id}.",
        "description": f"Implement bounded behavior {task_id} and its narrow proof.",
        "kind": "code",
        "status": "pending",
        "complexity": complexity,
        "complexity_justification": "One contained module contract.",
        "estimated_minutes": minutes,
        "depends_on": deps,
        "dependency_reasons": {
            dep: {
                "kind": "consumes_output",
                "reason": f"{task_id} imports the contract created by {dep}.",
                "required_output": f"src/{dep.lower()}.py:Contract",
            }
            for dep in deps
        },
        "routing_group": "",
        "write_set": {"paths": paths or [f"src/{task_id.lower()}.py"], "complete": True},
        "narrow_tests": {
            "selectors": [f"tests/test_{task_id.lower()}.py"],
            "max_seconds": 120,
            "max_runs": 2,
        },
        "checkpoint": {
            "required": complexity >= 7,
            "max_interval_seconds": 300,
            "records": (
                [
                    "completed_subobjectives",
                    "remaining_subobjectives",
                    "output_hashes",
                    "test_state",
                ]
                if complexity >= 7
                else []
            ),
        },
    }


def _payload(tasks: list[dict]) -> dict:
    return {"task_contract_version": 2, "tasks": tasks, "validation_jobs": []}


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["diagnostics"]}


def test_wide_independent_graph_remains_wide_and_is_admitted() -> None:
    report = compile_task_feasibility(_payload([_task(f"T{i}") for i in range(1, 8)]))

    assert report["admitted"] is True
    assert report["max_width"] == 7
    assert report["edge_count"] == 0
    assert report["seriality"] == pytest.approx(1 / 7)


def test_concrete_35_task_fully_linear_failure_is_rejected() -> None:
    tasks = [
        _task(f"T{i}", depends_on=([f"T{i - 1}"] if i > 1 else []), minutes=1)
        for i in range(1, 36)
    ]

    report = compile_task_feasibility(_payload(tasks))

    assert report["task_count"] == 35
    assert report["edge_count"] == 34
    assert report["max_width"] == 1
    assert report["critical_path_task_count"] == 35
    assert report["seriality"] == 1.0
    assert "serial_graph_unjustified" in _codes(report)


def test_dependency_requires_semantic_evidence_and_rejects_routing_reason() -> None:
    task = _task("T2", depends_on=["T1"])
    task["dependency_reasons"]["T1"]["reason"] = "Keep separate for model tier routing."
    report = compile_task_feasibility(_payload([_task("T1"), task]))
    assert "routing_dependency_forbidden" in _codes(report)

    del task["dependency_reasons"]["T1"]
    report = compile_task_feasibility(_payload([_task("T1"), task]))
    assert "dependency_reason_missing" in _codes(report)


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda task: task.update(estimated_minutes=16), "task_duration_exceeded"),
        (lambda task: task.update(objective="x; y"), "task_objective_oversized"),
        (lambda task: task["write_set"].update(paths=[f"src/{i}.py" for i in range(6)]), "task_path_budget_exceeded"),
        (lambda task: task["narrow_tests"].update(selectors=[f"tests/test_{i}.py" for i in range(4)]), "task_test_selector_budget_exceeded"),
        (lambda task: task["narrow_tests"].update(max_seconds=121), "task_test_time_budget_exceeded"),
        (lambda task: task["narrow_tests"].update(max_runs=3), "task_test_run_budget_exceeded"),
    ],
)
def test_task_budgets_fail_closed(mutation, code: str) -> None:
    task = _task("T1")
    mutation(task)
    assert code in _codes(compile_task_feasibility(_payload([task])))


def test_overlapping_writes_require_order_or_shared_routing_group() -> None:
    left = _task("T1", paths=["src/shared.py"])
    right = _task("T2", paths=["src/shared.py"])
    report = compile_task_feasibility(_payload([left, right]))
    assert "write_overlap_unordered" in _codes(report)

    left["routing_group"] = right["routing_group"] = "shared-contract"
    assert compile_task_feasibility(_payload([left, right]))["admitted"] is True


def test_execute_recheck_rejects_post_finalize_contract_mutation() -> None:
    payload = _payload([_task("T1")])
    payload["graph_report"] = compile_task_feasibility(payload)
    assert assert_admitted_task_feasibility(payload) is not None

    mutated = deepcopy(payload)
    mutated["tasks"][0]["write_set"]["paths"] = ["src/elsewhere.py"]
    with pytest.raises(ValueError, match="hash differs"):
        assert_admitted_task_feasibility(mutated)


def test_verification_scrubber_preserves_implementation_objective() -> None:
    from arnold_pipelines.megaplan.handlers.finalize import _ensure_verification_task

    task = _task("T1")
    task["description"] = "Implement the parser, then re-run tests until all pass."
    payload = _payload([task])
    _ensure_verification_task(payload, {"config": {"mode": "code"}})

    assert payload["tasks"][0]["description"].startswith("Implement the parser")
    assert "limited by narrow_tests" in payload["tasks"][0]["description"]


def test_model_owned_full_suite_task_is_rejected() -> None:
    task = _task("T1")
    task["kind"] = "test"
    task["objective"] = "Run the full suite and repair failures."
    assert "model_validation_job_forbidden" in _codes(
        compile_task_feasibility(_payload([task]))
    )


def test_runtime_test_budget_blocks_unbounded_or_widened_evidence() -> None:
    from arnold_pipelines.megaplan.execute.merge import _enforce_task_test_budgets

    target = _task("T1")
    valid = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": [
            "timeout 60s pytest tests/test_t1.py",
            "timeout 60s pytest tests/test_t1.py",
        ],
    }
    issues: list[str] = []
    _enforce_task_test_budgets([valid], targets_by_id={"T1": target}, issues=issues)
    assert valid["status"] == "done"
    assert issues == []

    invalid = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "verified",
        "commands_run": ["pytest tests"],
    }
    _enforce_task_test_budgets([invalid], targets_by_id={"T1": target}, issues=issues)
    assert invalid["status"] == "blocked"
    assert "task_test_budget_exhausted" in invalid["executor_notes"]
    assert issues


def test_runtime_write_budget_blocks_undeclared_paths() -> None:
    from arnold_pipelines.megaplan.execute.merge import _enforce_task_write_budgets

    target = _task("T1")
    update = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "implemented",
        "files_changed": ["src/t1.py", "src/escaped.py"],
    }
    issues: list[str] = []
    _enforce_task_write_budgets([update], targets_by_id={"T1": target}, issues=issues)

    assert update["status"] == "blocked"
    assert "task_write_set_violation" in update["executor_notes"]
    assert issues


def test_feasibility_failure_routes_finalize_back_to_revise(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.handlers import finalize
    from arnold_pipelines.megaplan.workers import WorkerResult

    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "p",
        "iteration": 1,
        "current_state": "gated",
        "config": {"mode": "code", "project_dir": str(repo)},
        "meta": {},
        "history": [],
        "sessions": {},
    }
    worker = WorkerResult(
        payload=_payload([_task("T1")]),
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
    )
    report = compile_task_feasibility(
        _payload(
            [
                _task(f"T{i}", depends_on=([f"T{i - 1}"] if i > 1 else []), minutes=1)
                for i in range(1, 9)
            ]
        )
    )
    (plan_dir / "task_feasibility.json").write_text("{}", encoding="utf-8")

    response = finalize._route_finalize_task_feasibility_failure_to_revise(
        plan_dir,
        state,
        worker,
        finalize.TaskFeasibilityError(report),
    )

    assert response["result"] == "plan_contract_revise_needed"
    assert response["next_step"] == "revise"
    assert response["details"]["code"] == "finalized_task_feasibility_failed"
    assert (plan_dir / "finalize_revise_feedback.json").exists()
