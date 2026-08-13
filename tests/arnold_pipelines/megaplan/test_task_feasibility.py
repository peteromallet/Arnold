from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    assert_admitted_task_feasibility,
    compile_task_feasibility,
    plan_hash,
    task_contract_hash,
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


def test_non_mapping_dependency_evidence_rejected_as_routing() -> None:
    """A dependency_reasons entry that is not a Mapping must be rejected
    with routing_dependency_forbidden — it is not semantic evidence."""
    task = _task("T2", depends_on=["T1"])
    task["dependency_reasons"]["T1"] = "just a string, not evidence"  # type: ignore[dict-item]
    report = compile_task_feasibility(_payload([_task("T1"), task]))
    codes = _codes(report)
    assert "routing_dependency_forbidden" in codes
    assert report["admitted"] is False


def test_non_semantic_kind_rejected_as_routing_forbidden() -> None:
    """A dependency with a kind outside _DEPENDENCY_KINDS must be rejected
    with routing_dependency_forbidden."""
    task = _task("T2", depends_on=["T1"])
    task["dependency_reasons"]["T1"]["kind"] = "routing"
    report = compile_task_feasibility(_payload([_task("T1"), task]))
    codes = _codes(report)
    assert "routing_dependency_forbidden" in codes
    assert "dependency_reason_invalid" not in codes
    assert report["admitted"] is False


@pytest.mark.parametrize(
    "valid_kind",
    ["consumes_output", "write_conflict", "human_prerequisite"],
)
def test_semantic_dependency_kinds_are_admitted(valid_kind: str) -> None:
    """All three semantic dependency kinds must produce an admitted graph
    when the rest of the evidence is well-formed."""
    task = _task("T2", depends_on=["T1"])
    task["dependency_reasons"]["T1"]["kind"] = valid_kind
    task["dependency_reasons"]["T1"]["reason"] = f"Semantic reason for {valid_kind}."
    task["dependency_reasons"]["T1"]["required_output"] = "src/t1.py"
    report = compile_task_feasibility(_payload([_task("T1"), task]))
    assert report["admitted"] is True
    assert "routing_dependency_forbidden" not in _codes(report)


def test_routing_group_is_non_authoritative_metadata_only() -> None:
    """routing_group must never create or authorize a dependency edge.
    It may only suppress the unordered-write-overlap diagnostic when
    two tasks share identical routing_group values."""
    left = _task("T1", paths=["src/shared.py"])
    right = _task("T2", paths=["src/shared.py"])
    # Without routing_group: must warn about unordered overlap
    report = compile_task_feasibility(_payload([left, right]))
    assert "write_overlap_unordered" in _codes(report)

    # With a shared routing_group: overlap diagnostic suppressed
    left["routing_group"] = right["routing_group"] = "shared-contract"
    report = compile_task_feasibility(_payload([left, right]))
    assert report["admitted"] is True
    assert "write_overlap_unordered" not in _codes(report)

    # routing_group must never manufacture a dependency edge
    assert right.get("depends_on", []) == []
    assert report["edge_count"] == 0


def test_report_diagnostic_ordering_is_deterministic() -> None:
    """Multiple compilations of the same payload must produce identical
    diagnostic lists in the same order."""
    tasks = []
    for i in range(1, 5):
        task = _task(f"T{i}", depends_on=[f"T{i-1}"] if i > 1 else [], minutes=1)
        if i == 3:
            # Inject a routing reason
            task["dependency_reasons"][f"T{i-1}"]["reason"] = "Keep T3 and T2 in same batch."
        if i == 4:
            # Inject non-Mapping evidence
            task["dependency_reasons"] = {f"T{i-1}": None}  # type: ignore[dict-item]
        tasks.append(task)

    report_a = compile_task_feasibility(_payload(tasks))
    report_b = compile_task_feasibility(_payload(tasks))

    assert report_a["diagnostics"] == report_b["diagnostics"]
    assert report_a["task_contract_hash"] == report_b["task_contract_hash"]
    assert report_a["admitted"] == report_b["admitted"]


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


def test_feasibility_failure_enters_narrow_planner_repair(tmp_path: Path) -> None:
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

    assert response["result"] == "planner_repair_required"
    assert response["next_step"] == "finalize"
    assert response["details"]["code"] == "finalized_task_feasibility_failed"
    assert response["details"]["accepted_authority_preserved"] is True
    assert response["details"]["implementation_dispatch_allowed"] is False
    assert (plan_dir / "finalize_revise_feedback.json").exists()
    assert (plan_dir / "planner_repair.json").exists()


# ---------------------------------------------------------------------------
# Planner-repair circuit-open — lifecycle repair identity (producer window)
# ---------------------------------------------------------------------------


def _lifecycle_lease() -> dict[str, object]:
    """One immutable runner lease binding (matches active_step + live reread)."""
    return {
        "schema": "arnold.megaplan.active_step_runner_lease.v1",
        "session": "finalize-session",
        "marker_dir": "/workspace/.megaplan/cloud-sessions",
        "marker_binding": "sha256:marker-binding-1",
        "lease_id": "lease-finalize-1",
        "runner_fence": 1,
        "runner_container_id": "container-1",
        "pid_namespace_id": "pidns-1",
        "target_process_start_identity": "boot:4242",
    }


def _lifecycle_active_step(
    *,
    run_id: str = "run-finalize-1",
    invocation_id: str = "inv-finalize-1",
) -> dict[str, object]:
    """The lifecycle active step persisted by ``set_active_step`` at entry."""
    return {
        "phase": "finalize",
        "agent": "finalizer",
        "mode": "default",
        "run_id": run_id,
        "invocation_id": invocation_id,
        "worker_pid": 4242,
        "started_at": "2026-08-13T00:00:00Z",
        "attempt": 2,
        "last_activity_at": "2026-08-13T00:00:01Z",
        "last_activity_kind": "started",
        "orphan_fence": {"run_id": run_id, "invocation_id": invocation_id},
        "runner_incarnation": {
            "schema": "arnold.megaplan.runner_incarnation.v1",
            "host_id": "host-1",
            "pid_namespace_id": "pidns-1",
            "worker_pid": 4242,
            "worker_process_start_identity": "boot:4242",
        },
        "runner_lease": _lifecycle_lease(),
    }


def _circuit_open_state(
    plan_dir: Path,
    repo: Path,
    *,
    with_active_step: bool,
    invocation_id: str = "inv-finalize-1",
) -> dict:
    state = {
        "name": "p",
        "iteration": 1,
        "current_state": "gated",
        "config": {"mode": "code", "project_dir": str(repo)},
        "meta": {
            "current_invocation_id": invocation_id,
            "planner_repair": {
                "schema": "megaplan.planner_repair",
                "schema_version": 1,
                "candidate_id": "candidate:abc",
                "failure_fingerprint": "fp-1",
                "occurrences": 2,
                "circuit_open": True,
                "accepted_authority_preserved": True,
                "implementation_dispatch_allowed": False,
            },
        },
        "history": [],
        "sessions": {},
    }
    if with_active_step:
        state["active_step"] = _lifecycle_active_step(invocation_id=invocation_id)
    (plan_dir / "task_feasibility.json").write_text("{}", encoding="utf-8")
    return state


def test_finalize_circuit_open_persists_normalizable_repair_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The open-circuit finalize rejection mints a v1 repair identity from the
    lifecycle active step + live runner lease (auto._record_lifecycle_failure
    pattern) and persists it where the watchdog dispatch can derive it."""
    from arnold_pipelines.megaplan._core import phase_runtime
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        derive_repair_identity,
        normalize_repair_identity,
    )
    from arnold_pipelines.megaplan.handlers import finalize
    from arnold_pipelines.megaplan.workers import WorkerResult

    monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "finalize-session")
    monkeypatch.setenv("ARNOLD_CHAIN_SPEC", "/workspace/initiative/chain.yaml")
    monkeypatch.setattr(
        phase_runtime,
        "current_runner_lease_binding",
        lambda: _lifecycle_lease(),
    )

    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = _circuit_open_state(plan_dir, repo, with_active_step=True)
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

    response = finalize._route_finalize_task_feasibility_failure_to_revise(
        plan_dir,
        state,
        worker,
        finalize.TaskFeasibilityError(report),
    )

    assert response["result"] == "planner_repair_blocked"
    assert response["next_step"] == "override recover-blocked"
    assert response["details"]["repair_identity_persisted"] is True
    assert state["current_state"] == "blocked"
    assert state["latest_failure"]["kind"] == "deterministic_phase_failure"
    assert state["latest_failure"]["phase"] == "finalize"
    assert state["resume_cursor"] == {
        "phase": "finalize",
        "retry_strategy": "repair_phase_contract",
    }
    assert state["meta"]["planner_repair"]["circuit_open"] is True

    persisted = state["meta"].get("repair_identity")
    assert isinstance(persisted, dict)
    normalized = normalize_repair_identity(persisted)
    assert normalized is not None
    assert normalized["occurrence"]["contract_type"] == "repair_occurrence_key"
    assert state["meta"]["repair_identity_provenance"][
        "authority_source"
    ] == "finalize_planner_repair_circuit_open_owner"
    # The watchdog dispatch path derives the exact envelope from plan state.
    derived = derive_repair_identity(plan_state=state)
    assert derived == normalized
    # And the failure path persists it to state.json (via _finish_step /
    # record_step_failure), which is the durable source the watchdog reads.
    from arnold_pipelines.megaplan._core.io import read_json

    persisted_state = read_json(plan_dir / "state.json")
    assert isinstance(persisted_state, dict)
    disk_identity = (persisted_state.get("meta") or {}).get("repair_identity")
    assert normalize_repair_identity(disk_identity) == normalized
    assert persisted_state["latest_failure"]["kind"] == "deterministic_phase_failure"
    assert persisted_state["resume_cursor"] == {
        "phase": "finalize",
        "retry_strategy": "repair_phase_contract",
    }


def test_finalize_circuit_open_fail_closed_without_active_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No lifecycle active step / live lease → identity is NOT minted, but the
    failure records (latest_failure, resume_cursor, planner_repair) are."""
    from arnold_pipelines.megaplan._core import phase_runtime
    from arnold_pipelines.megaplan.handlers import finalize
    from arnold_pipelines.megaplan.workers import WorkerResult

    monkeypatch.setattr(
        phase_runtime,
        "current_runner_lease_binding",
        lambda: None,
    )

    repo = tmp_path / "repo"
    plan_dir = repo / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = _circuit_open_state(plan_dir, repo, with_active_step=False)
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

    response = finalize._route_finalize_task_feasibility_failure_to_revise(
        plan_dir,
        state,
        worker,
        finalize.TaskFeasibilityError(report),
    )

    assert response["result"] == "planner_repair_blocked"
    assert response["details"]["repair_identity_persisted"] is False
    assert "repair_identity" not in state["meta"]
    assert state["latest_failure"]["kind"] == "deterministic_phase_failure"
    assert state["resume_cursor"] == {
        "phase": "finalize",
        "retry_strategy": "repair_phase_contract",
    }
    assert state["meta"]["planner_repair"]["circuit_open"] is True
    assert (plan_dir / "finalize_revise_feedback.json").exists()


# ---------------------------------------------------------------------------
# M8A — DAG seriality gate: 30-task / 29-edge Transaction Spine rejection
# ---------------------------------------------------------------------------


def test_transaction_spine_30_task_29_edge_seriality_gate_rejected() -> None:
    """The 30-task fully-serial Transaction Spine shape must be rejected.

    Seriality 1.0 with >=8 tasks triggers ``serial_graph_unjustified``,
    and the estimated dispatch budget will also exceed the phase timeout.
    """
    from tests.fixtures.m8a import transaction_spine_serial

    payload = transaction_spine_serial()
    report = compile_task_feasibility(payload)

    assert report["task_count"] == 30
    assert report["edge_count"] == 29
    assert report["max_width"] == 1
    assert report["critical_path_task_count"] == 30
    assert report["seriality"] == 1.0
    assert report["admitted"] is False
    codes = _codes(report)
    assert "serial_graph_unjustified" in codes
    assert "critical_path_infeasible" in codes
    assert "dispatch_budget_infeasible" in codes


def test_seriality_at_8_tasks_single_file_each_is_rejected() -> None:
    """8 fully-linear tasks (seriality=1.0) hits the floor threshold."""
    tasks = [
        _task(f"T{i}", depends_on=([f"T{i - 1}"] if i > 1 else []), minutes=3)
        for i in range(1, 9)
    ]
    report = compile_task_feasibility(_payload(tasks))
    assert report["task_count"] == 8
    assert report["seriality"] == 1.0
    assert "serial_graph_unjustified" in _codes(report)


def test_seriality_below_threshold_with_diamond_is_admitted() -> None:
    """A diamond-shaped DAG with 9 tasks and seriality < 1.0 is admitted."""
    tasks = [
        _task("T1", minutes=3),
        _task("T2", depends_on=["T1"], minutes=3),
        _task("T3", depends_on=["T1"], minutes=3),
        _task("T4", depends_on=["T2", "T3"], minutes=3),
        _task("T5", depends_on=["T4"], minutes=3),
        _task("T6", depends_on=["T4"], minutes=3),
        _task("T7", depends_on=["T5", "T6"], minutes=3),
        _task("T8", depends_on=["T7"], minutes=3),
        _task("T9", depends_on=["T7"], minutes=3),
    ]
    report = compile_task_feasibility(_payload(tasks))
    assert report["task_count"] == 9
    assert report["seriality"] < 1.0
    assert report["admitted"] is True


# ---------------------------------------------------------------------------
# M8A — Content-hash identical recompilation
# ---------------------------------------------------------------------------


def test_content_hash_is_deterministic_across_recompilations() -> None:
    """The task_contract_hash must be byte-stable across repeated compilations."""
    payload = _payload([_task(f"T{i}", minutes=5) for i in range(1, 6)])
    first = compile_task_feasibility(payload)
    second = compile_task_feasibility(payload)
    third = compile_task_feasibility(payload)

    assert first["task_contract_hash"] == second["task_contract_hash"]
    assert second["task_contract_hash"] == third["task_contract_hash"]
    assert first["admitted"] is True
    assert second["admitted"] is True


def test_content_hash_changes_when_task_list_differs() -> None:
    """Adding or removing a task produces a different contract hash."""
    base = _payload([_task("T1"), _task("T2")])
    mutated = _payload([_task("T1"), _task("T2"), _task("T3")])

    base_hash = compile_task_feasibility(base)["task_contract_hash"]
    mutated_hash = compile_task_feasibility(mutated)["task_contract_hash"]
    assert base_hash != mutated_hash


def test_content_hash_changes_when_validation_jobs_differ() -> None:
    """Changes to validation_jobs must be reflected in the contract hash."""
    payload_a = _payload([_task("T1")])
    payload_a["validation_jobs"] = [
        {"id": "v1", "kind": "post_execute_suite", "command": "pytest", "reason": "final"}
    ]
    payload_b = _payload([_task("T1")])
    payload_b["validation_jobs"] = []

    hash_a = compile_task_feasibility(payload_a)["task_contract_hash"]
    hash_b = compile_task_feasibility(payload_b)["task_contract_hash"]
    assert hash_a != hash_b


def test_compile_task_feasibility_report_is_deterministic() -> None:
    """The full feasibility report must be deterministic byte-for-byte."""
    import json

    payload = _payload([_task(f"T{i}", minutes=5) for i in range(1, 4)])
    report_a = json.dumps(compile_task_feasibility(payload), sort_keys=True)
    report_b = json.dumps(compile_task_feasibility(payload), sort_keys=True)
    assert report_a == report_b


# ---------------------------------------------------------------------------
# M8A — Complexity 7/8/9 split-or-fail
# ---------------------------------------------------------------------------


def test_complexity_7_with_valid_checkpoint_is_admitted() -> None:
    """A complexity-7 task with a valid checkpoint contract passes feasibility."""
    task = _task("T7", complexity=7)
    report = compile_task_feasibility(_payload([task]))
    assert report["admitted"] is True


def test_complexity_8_with_valid_checkpoint_is_admitted() -> None:
    """A complexity-8 task with a valid checkpoint contract passes feasibility."""
    task = _task("T8", complexity=8)
    report = compile_task_feasibility(_payload([task]))
    assert report["admitted"] is True


def test_complexity_9_with_valid_checkpoint_is_admitted() -> None:
    """A complexity-9 task with a valid checkpoint contract passes feasibility."""
    task = _task("T9", complexity=9)
    report = compile_task_feasibility(_payload([task]))
    assert report["admitted"] is True


def test_complexity_7_without_checkpoint_is_rejected() -> None:
    """A complexity-7 task missing the checkpoint contract is rejected."""
    task = _task("T7b", complexity=7)
    task["checkpoint"] = {"required": False, "max_interval_seconds": 300, "records": []}
    report = compile_task_feasibility(_payload([task]))
    assert report["admitted"] is False
    assert "task_checkpoint_required" in _codes(report)


def test_complexity_7_with_missing_checkpoint_records_is_rejected() -> None:
    """A complexity-7 task whose checkpoint is missing required records fails."""
    task = _task("T7c", complexity=7)
    task["checkpoint"] = {
        "required": True,
        "max_interval_seconds": 300,
        "records": ["completed_subobjectives", "output_hashes"],  # incomplete
    }
    report = compile_task_feasibility(_payload([task]))
    assert report["admitted"] is False
    assert "task_checkpoint_required" in _codes(report)


def test_complexity_7_with_invalid_interval_is_rejected() -> None:
    """A complexity-7 task with a checkpoint interval > 300s is rejected."""
    task = _task("T7d", complexity=7)
    task["checkpoint"]["max_interval_seconds"] = 301
    report = compile_task_feasibility(_payload([task]))
    assert report["admitted"] is False
    assert "task_checkpoint_required" in _codes(report)


def test_m8a_complexity_7_8_9_fixture_split_or_fail_cases() -> None:
    """The M8A complexity-7-8-9 fixture admits valid tasks and rejects the invalid one."""
    from tests.fixtures.m8a import complexity_7_8_9_cases

    payload = complexity_7_8_9_cases()
    report = compile_task_feasibility(payload)

    # T7 (complexity=7), T8 (complexity=8), T9 (complexity=9) — all have valid checkpoints
    # T7b (complexity=7 — no checkpoint) should be rejected
    diag_by_task: dict[str, list[str]] = {}
    for diag in report["diagnostics"]:
        tid = diag.get("task_id", "")
        diag_by_task.setdefault(tid, []).append(diag["code"])

    # The fixture contains 4 tasks total (T7, T8, T9, T7b)
    assert report["task_count"] == 4
    assert report["admitted"] is False  # T7b fails

    # T7, T8, T9 should have no diagnostics against them
    for admitted_id in ("T7", "T8", "T9"):
        assert admitted_id not in diag_by_task or all(
            c == "task_objective_oversized" for c in diag_by_task.get(admitted_id, [])
        ), f"{admitted_id} should not have checkpoint failures"

    # T7b should fail with task_checkpoint_required
    assert "task_checkpoint_required" in diag_by_task.get("T7b", [])


# ---------------------------------------------------------------------------
# M8A — Post-finalize graph mutation prevents worker dispatch
# ---------------------------------------------------------------------------


def test_post_finalize_write_set_mutation_prevents_dispatch() -> None:
    """A mutation to a task's write_set after finalize changes the contract hash."""
    payload = _payload([_task("T1"), _task("T2", depends_on=["T1"])])
    payload["graph_report"] = compile_task_feasibility(payload)

    # First call succeeds — graph hasn't been mutated
    assert assert_admitted_task_feasibility(payload) is not None

    # Mutate a task's write_set
    mutated = deepcopy(payload)
    mutated["tasks"][1]["write_set"]["paths"] = ["src/divergent.py"]
    with pytest.raises(ValueError, match="hash differs"):
        assert_admitted_task_feasibility(mutated)


def test_post_finalize_added_task_prevents_dispatch() -> None:
    """Adding a task after finalize changes the contract hash."""
    payload = _payload([_task("T1")])
    payload["graph_report"] = compile_task_feasibility(payload)

    assert assert_admitted_task_feasibility(payload) is not None

    mutated = deepcopy(payload)
    mutated["tasks"].append(_task("T2"))
    with pytest.raises(ValueError, match="hash differs"):
        assert_admitted_task_feasibility(mutated)


def test_post_finalize_dependency_chain_mutation_prevents_dispatch() -> None:
    """Altering a dependency edge after finalize changes the contract hash."""
    payload = _payload([
        _task("T1"),
        _task("T2", depends_on=["T1"]),
        _task("T3", depends_on=["T2"]),
    ])
    payload["graph_report"] = compile_task_feasibility(payload)
    assert assert_admitted_task_feasibility(payload) is not None

    # Remove a dependency (leaves orphaned dependency_reason — fails feasibility)
    mutated = deepcopy(payload)
    mutated["tasks"][2]["depends_on"] = ["T1"]  # was ["T2"]
    with pytest.raises(ValueError, match="no longer passes feasibility"):
        assert_admitted_task_feasibility(mutated)


def test_post_finalize_complexity_change_prevents_dispatch() -> None:
    """Changing a task's complexity after finalize changes the contract hash."""
    payload = _payload([_task("T1", complexity=4)])
    payload["graph_report"] = compile_task_feasibility(payload)
    assert assert_admitted_task_feasibility(payload) is not None

    mutated = deepcopy(payload)
    mutated["tasks"][0]["complexity"] = 7
    with pytest.raises(ValueError, match="no longer passes feasibility"):
        assert_admitted_task_feasibility(mutated)


# ---------------------------------------------------------------------------
# Step 7H-a: additive seed_epoch / plan_hash fields and epoch fencing
# ---------------------------------------------------------------------------


def test_compile_emits_additive_seed_epoch_and_plan_hash() -> None:
    """seed_epoch and plan_hash are additive receipt fields in the report."""
    payload = _payload([_task("T1")])
    payload["seed_epoch"] = "epoch-abc-123"
    payload["source"] = {"kind": "git", "head": "deadbeef"}
    report = compile_task_feasibility(payload)
    assert report["seed_epoch"] == "epoch-abc-123"
    assert isinstance(report["plan_hash"], str)
    assert report["plan_hash"].startswith("sha256:")


def test_seed_epoch_defaults_to_none_when_absent() -> None:
    """Without seed_epoch in the payload the report field is None."""
    report = compile_task_feasibility(_payload([_task("T1")]))
    assert report["seed_epoch"] is None
    # plan_hash is still emitted (binds None seed_epoch)
    assert report["plan_hash"].startswith("sha256:")


def test_plan_hash_binds_seed_epoch_while_contract_hash_does_not() -> None:
    """Changing seed_epoch changes plan_hash but NOT task_contract_hash."""
    base = _payload([_task("T1")])
    base["seed_epoch"] = "epoch-v1"
    with_epoch_v2 = deepcopy(base)
    with_epoch_v2["seed_epoch"] = "epoch-v2"

    assert task_contract_hash(base) == task_contract_hash(with_epoch_v2)
    assert plan_hash(base) != plan_hash(with_epoch_v2)


def test_plan_hash_binds_source_while_contract_hash_does_not() -> None:
    """Changing source changes plan_hash but NOT task_contract_hash."""
    base = _payload([_task("T1")])
    base["seed_epoch"] = "epoch-1"
    base["source"] = {"kind": "git", "head": "aaa"}
    with_source_b = deepcopy(base)
    with_source_b["source"] = {"kind": "git", "head": "bbb"}

    assert task_contract_hash(base) == task_contract_hash(with_source_b)
    assert plan_hash(base) != plan_hash(with_source_b)


def test_assert_admitted_matched_epoch_is_accepted() -> None:
    """A matching current_epoch passes through without error."""
    payload = _payload([_task("T1")])
    payload["seed_epoch"] = "epoch-current"
    payload["graph_report"] = compile_task_feasibility(payload)
    report = assert_admitted_task_feasibility(payload, current_epoch="epoch-current")
    assert report is not None
    assert report["seed_epoch"] == "epoch-current"


def test_assert_admitted_stale_epoch_is_rejected() -> None:
    """A mismatched current_epoch (stale/conflicted) raises ValueError."""
    payload = _payload([_task("T1")])
    payload["seed_epoch"] = "epoch-current"
    payload["graph_report"] = compile_task_feasibility(payload)
    with pytest.raises(ValueError, match="seed_epoch mismatch"):
        assert_admitted_task_feasibility(payload, current_epoch="epoch-stale")


def test_assert_admitted_v2_with_none_epoch_is_rejected() -> None:
    """v2 + explicitly absent attestation (current_epoch=None) is rejected."""
    payload = _payload([_task("T1")])
    payload["seed_epoch"] = "epoch-current"
    payload["graph_report"] = compile_task_feasibility(payload)
    with pytest.raises(ValueError, match="seed_epoch attestation required"):
        assert_admitted_task_feasibility(payload, current_epoch=None)


def test_assert_admitted_v1_with_none_epoch_escapes() -> None:
    """v1 + current_epoch=None returns None (escape hatch regardless of epoch)."""
    payload = {"task_contract_version": 1, "tasks": [], "validation_jobs": []}
    assert assert_admitted_task_feasibility(payload, current_epoch=None) is None


def test_assert_admitted_unset_epoch_is_backward_compatible() -> None:
    """Unset current_epoch (sentinel) preserves prior behavior for v2 plans."""
    payload = _payload([_task("T1")])
    payload["seed_epoch"] = "epoch-current"
    payload["graph_report"] = compile_task_feasibility(payload)
    # No current_epoch passed — must not raise even though seed_epoch is present.
    report = assert_admitted_task_feasibility(payload)
    assert report is not None


def test_m8a_report_backward_compat_task_contract_hash_stable() -> None:
    """m8a_report reads task_contract_hash from compile output; it is stable."""
    # Simulate the m8a_report consumption pattern:
    # feasibility = compile_task_feasibility(payload, config)
    # feasibility.get("task_contract_hash")
    payload_a = _payload([_task("T1")])
    payload_a["seed_epoch"] = "epoch-x"
    payload_b = _payload([_task("T1")])
    # No seed_epoch
    report_a = compile_task_feasibility(payload_a)
    report_b = compile_task_feasibility(payload_b)
    # task_contract_hash must be identical (additive fields don't perturb it)
    assert report_a["task_contract_hash"] == report_b["task_contract_hash"]
    # But plan_hash and seed_epoch differ
    assert report_a["plan_hash"] != report_b["plan_hash"]
    assert report_a["seed_epoch"] == "epoch-x"
    assert report_b["seed_epoch"] is None


def test_critique_custody_backward_compat_hash_stable() -> None:
    """critique_custody uses task_contract_hash(payload); it is stable."""
    # Simulate the critique_custody consumption pattern:
    # task_contract_hash(payload)
    payload_a = _payload([_task("T1")])
    payload_a["seed_epoch"] = "epoch-y"
    payload_b = _payload([_task("T1")])
    # Adding seed_epoch must not change task_contract_hash
    assert task_contract_hash(payload_a) == task_contract_hash(payload_b)
