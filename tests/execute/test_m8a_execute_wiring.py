"""M8A execute wiring tests — admission guard, split integration, and mutation rejection.

These tests prove that the ``_guard_execute_batch_admission`` shared helper
prevents worker dispatch when the post-finalize task graph has been mutated,
and that the full admission→split→batch pipeline is wired correctly.
"""

from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from arnold_pipelines.megaplan._core.io import (
    _has_valid_checkpoint_contract,
    compute_global_batches,
    split_high_complexity_batches,
    split_oversized_batches,
)
from arnold_pipelines.megaplan.execute.batch import (
    CliError,
    _guard_execute_batch_admission,
)
from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    assert_admitted_task_feasibility,
    compile_task_feasibility,
    task_contract_hash,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(
    task_id: str,
    *,
    depends_on: list[str] | None = None,
    minutes: int = 5,
    complexity: int = 4,
) -> dict:
    deps = list(depends_on or [])
    task: dict = {
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
        "write_set": {"paths": [f"src/{task_id.lower()}.py"], "complete": True},
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
    return task


def _payload(tasks: list[dict]) -> dict:
    return {"task_contract_version": 2, "tasks": tasks, "validation_jobs": []}


def _make_state(project_dir: Path | None = None) -> dict:
    return {
        "name": "test-plan",
        "iteration": 1,
        "current_state": "executing",
        "config": {
            "mode": "code",
            "project_dir": str(project_dir or Path("/tmp/test-project")),
        },
        "meta": {},
        "history": [],
        "sessions": {},
    }


# ---------------------------------------------------------------------------
# Post-finalize mutation → guard rejects dispatch
# ---------------------------------------------------------------------------


def test_guard_admits_valid_unchanged_graph() -> None:
    """A valid, unmutated graph passes the guard without raising."""
    tasks = [_task("T1"), _task("T2", depends_on=["T1"])]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    # Must not raise
    _guard_execute_batch_admission(finalize_data, state)


def test_guard_rejects_write_set_mutation_as_cli_error() -> None:
    """Mutating a task's write_set after finalize causes CliError at the guard."""
    tasks = [_task("T1"), _task("T2", depends_on=["T1"])]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    # Mutate write_set — changes contract hash
    mutated = deepcopy(finalize_data)
    mutated["tasks"][1]["write_set"]["paths"] = ["src/divergent.py"]

    with pytest.raises(CliError, match="hash differs"):
        _guard_execute_batch_admission(mutated, state)


def test_guard_rejects_added_task_as_cli_error() -> None:
    """Adding a new task after finalize causes CliError at the guard."""
    tasks = [_task("T1")]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    mutated = deepcopy(finalize_data)
    mutated["tasks"].append(_task("T2"))

    with pytest.raises(CliError, match="hash differs"):
        _guard_execute_batch_admission(mutated, state)


def test_guard_rejects_dependency_removal_as_cli_error() -> None:
    """Removing a dependency edge after finalize causes CliError at the guard."""
    tasks = [_task("T1"), _task("T2", depends_on=["T1"]), _task("T3", depends_on=["T2"])]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    mutated = deepcopy(finalize_data)
    mutated["tasks"][2]["depends_on"] = []

    with pytest.raises(CliError, match="no longer passes feasibility"):
        _guard_execute_batch_admission(mutated, state)


def test_guard_rejects_complexity_change_as_cli_error() -> None:
    """Changing a task's complexity after finalize causes CliError at the guard."""
    tasks = [_task("T1", complexity=4)]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    mutated = deepcopy(finalize_data)
    mutated["tasks"][0]["complexity"] = 8

    with pytest.raises(CliError, match="no longer passes feasibility"):
        _guard_execute_batch_admission(mutated, state)


def test_guard_rejects_estimated_minutes_change_as_cli_error() -> None:
    """Changing a task's estimated_minutes after finalize causes CliError."""
    tasks = [_task("T1", minutes=5)]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    mutated = deepcopy(finalize_data)
    mutated["tasks"][0]["estimated_minutes"] = 15

    with pytest.raises(CliError, match="hash differs"):
        _guard_execute_batch_admission(mutated, state)


def test_guard_clierror_has_valid_next_directions() -> None:
    """The CliError raised by the guard must route to finalize or revise."""
    tasks = [_task("T1")]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    mutated = deepcopy(finalize_data)
    mutated["tasks"][0]["write_set"]["paths"] = ["src/mutated.py"]

    with pytest.raises(CliError) as exc_info:
        _guard_execute_batch_admission(mutated, state)

    assert exc_info.value.valid_next is not None
    assert "finalize" in exc_info.value.valid_next
    assert "revise" in exc_info.value.valid_next
    assert exc_info.value.code == "finalized_task_graph_changed"


def test_guard_rejects_feasibility_failure_on_cyclic_graph() -> None:
    """A cyclic graph that fails feasibility raises CliError at the guard."""
    tasks = [
        _task("T1", depends_on=["T2"]),
        _task("T2", depends_on=["T1"]),
    ]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    with pytest.raises(CliError, match="no longer passes feasibility"):
        _guard_execute_batch_admission(finalize_data, state)


# ---------------------------------------------------------------------------
# split_high_complexity_batches → admission → batch pipeline integration
# ---------------------------------------------------------------------------


def test_full_pipeline_admits_simple_graph_and_computes_batches() -> None:
    """A simple valid graph passes admission and produces correct batches."""
    tasks = [
        _task("T1"),
        _task("T2", depends_on=["T1"]),
        _task("T3", depends_on=["T1"]),
        _task("T4", depends_on=["T2", "T3"]),
        _task("T5", depends_on=["T4"]),
    ]
    finalize_data = _payload(tasks)
    report = compile_task_feasibility(finalize_data)
    assert report["admitted"] is True

    finalize_data["graph_report"] = report
    state = _make_state()
    _guard_execute_batch_admission(finalize_data, state)

    batches = compute_global_batches(finalize_data)
    assert batches == [["T1"], ["T2", "T3"], ["T4"], ["T5"]]


def test_full_pipeline_with_high_complexity_splits_correctly() -> None:
    """A graph with complexity-7 tasks splits them into isolated batches."""
    tasks = [
        _task("T1", complexity=4),
        _task("T7", complexity=7),
        _task("T2", complexity=3, depends_on=["T1", "T7"]),
    ]
    finalize_data = _payload(tasks)
    report = compile_task_feasibility(finalize_data)
    assert report["admitted"] is True

    finalize_data["graph_report"] = report
    state = _make_state()
    _guard_execute_batch_admission(finalize_data, state)

    global_batches = compute_global_batches(finalize_data)
    split_batches = split_oversized_batches(global_batches, max_size=5)
    final_batches = split_high_complexity_batches(split_batches, finalize_data)

    # T7 must be isolated in its own batch
    assert ["T7"] in final_batches
    # T1 must appear (no deps satisfied)
    flat = [tid for batch in final_batches for tid in batch]
    assert "T1" in flat
    assert "T2" in flat


def test_full_pipeline_rejects_mutated_graph_before_batch_computation() -> None:
    """After finalize mutation, the guard rejects before any batch computation runs."""
    tasks = [
        _task("T1"),
        _task("T2", depends_on=["T1"]),
        _task("T3", depends_on=["T2"]),
    ]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()

    # Mutate after finalize — removing dep leaves orphaned dependency_reason
    mutated = deepcopy(finalize_data)
    mutated["tasks"][1]["depends_on"] = []  # T2 no longer depends on T1

    # Guard must reject before we even get to batch computation
    with pytest.raises(CliError, match="no longer passes feasibility"):
        _guard_execute_batch_admission(mutated, state)

    # Prove that the *unmutated* graph still computes batches correctly
    _guard_execute_batch_admission(finalize_data, state)
    batches = compute_global_batches(finalize_data)
    assert batches == [["T1"], ["T2"], ["T3"]]


def test_task_contract_hash_is_sensitive_to_task_fields() -> None:
    """Every task field in the stable contract must affect the hash."""
    base = _payload([_task("T1", complexity=4)])
    base_hash = task_contract_hash(base)

    # Each mutation must produce a different hash
    mutations: list[tuple[str, dict]] = [
        ("complexity", {**base, "tasks": [_task("T1", complexity=5)]}),
        ("minutes", {**base, "tasks": [_task("T1", minutes=10)]}),
        ("objective changes", {
            **base,
            "tasks": [{
                **_task("T1"),
                "objective": "A completely different objective.",
            }],
        }),
        ("write_set changes", {
            **base,
            "tasks": [{
                **_task("T1"),
                "write_set": {"paths": ["src/different.py"], "complete": True},
            }],
        }),
    ]

    for label, mutated_payload in mutations:
        mutated_hash = task_contract_hash(mutated_payload)
        assert mutated_hash != base_hash, f"Hash should differ when {label} changes"


# ---------------------------------------------------------------------------
# _has_valid_checkpoint_contract helper
# ---------------------------------------------------------------------------


def test_has_valid_checkpoint_contract_true_for_valid_complexity_7() -> None:
    """A task with a complete checkpoint contract returns True."""
    task = {
        "checkpoint": {
            "required": True,
            "max_interval_seconds": 300,
            "records": [
                "completed_subobjectives",
                "remaining_subobjectives",
                "output_hashes",
                "test_state",
            ],
        },
    }
    assert _has_valid_checkpoint_contract(task) is True


def test_has_valid_checkpoint_contract_false_when_required_is_false() -> None:
    """A checkpoint with required=False is not valid for complexity >=7."""
    task = {
        "checkpoint": {
            "required": False,
            "max_interval_seconds": 300,
            "records": [
                "completed_subobjectives",
                "remaining_subobjectives",
                "output_hashes",
                "test_state",
            ],
        },
    }
    assert _has_valid_checkpoint_contract(task) is False


def test_has_valid_checkpoint_contract_false_when_interval_too_large() -> None:
    """A checkpoint interval > 300s is invalid."""
    task = {
        "checkpoint": {
            "required": True,
            "max_interval_seconds": 301,
            "records": [
                "completed_subobjectives",
                "remaining_subobjectives",
                "output_hashes",
                "test_state",
            ],
        },
    }
    assert _has_valid_checkpoint_contract(task) is False


def test_has_valid_checkpoint_contract_false_when_interval_zero() -> None:
    """A checkpoint interval of 0 is invalid."""
    task = {
        "checkpoint": {
            "required": True,
            "max_interval_seconds": 0,
            "records": [
                "completed_subobjectives",
                "remaining_subobjectives",
                "output_hashes",
                "test_state",
            ],
        },
    }
    assert _has_valid_checkpoint_contract(task) is False


def test_has_valid_checkpoint_contract_false_when_records_incomplete() -> None:
    """Missing required record kinds invalidates the contract."""
    task = {
        "checkpoint": {
            "required": True,
            "max_interval_seconds": 300,
            "records": ["completed_subobjectives", "output_hashes"],
        },
    }
    assert _has_valid_checkpoint_contract(task) is False


def test_has_valid_checkpoint_contract_false_when_checkpoint_missing() -> None:
    """A task with no checkpoint key returns False."""
    assert _has_valid_checkpoint_contract({}) is False


def test_has_valid_checkpoint_contract_false_when_checkpoint_is_not_dict() -> None:
    """A non-dict checkpoint returns False."""
    assert _has_valid_checkpoint_contract({"checkpoint": "not-a-dict"}) is False


# ---------------------------------------------------------------------------
# assert_admitted_task_feasibility integration
# ---------------------------------------------------------------------------


def test_assert_admitted_returns_none_for_v1_payload() -> None:
    """v1 payloads (no task_contract_version=2) are silently skipped."""
    payload = {"task_contract_version": 1, "tasks": [], "validation_jobs": []}
    assert assert_admitted_task_feasibility(payload) is None


def test_assert_admitted_raises_on_feasibility_failure() -> None:
    """A v2 payload that fails feasibility raises ValueError."""
    payload = _payload([_task("T1", complexity=7)])  # complexity=7 with checkpoint
    # Ensure checkpoint is missing
    payload["tasks"][0]["checkpoint"] = {"required": False, "max_interval_seconds": 300, "records": []}
    with pytest.raises(ValueError, match="no longer passes feasibility"):
        assert_admitted_task_feasibility(payload)


def test_assert_admitted_raises_on_hash_mismatch() -> None:
    """When graph_report.task_contract_hash doesn't match, ValueError is raised."""
    payload = _payload([_task("T1")])
    payload["graph_report"] = {
        "task_contract_hash": "sha256:deadbeef",
        "admitted": True,
        "diagnostics": [],
    }
    with pytest.raises(ValueError, match="hash differs"):
        assert_admitted_task_feasibility(payload)


# ---------------------------------------------------------------------------
# Validation-job integration — batch execution wiring
# ---------------------------------------------------------------------------


def test_batch_validation_jobs_accepts_validation_jobs_from_finalize() -> None:
    """_run_batch_validation_jobs accepts validation_jobs from finalize_data."""
    from unittest.mock import MagicMock, patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "echo ok",
                    "selectors": ["tests/test_t1.py"],
                    "max_seconds": 60,
                    "max_runs": 1,
                    "reason": "Narrow recheck T1",
                    "task_id": "T1",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)
        fake_result = SuiteRunResult(
            run_id="fake-run-001",
            phase="narrow_recheck",
            command="echo ok",
            duration=0.1,
            collected=1,
            collected_ids=["test_a"],
            failures=[],
            passes=["test_a"],
            status="passed",
            exit_code=0,
            raw_log_path=project_dir / "raw_fake.log",
            code_hash="sha256:aaa",
            collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=fake_result,
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-1", "event_class": "validation"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    evidence = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        assert len(evidence) == 1
        assert evidence[0]["job_id"] == "VJ1"
        assert evidence[0]["kind"] == "narrow_recheck"
        assert evidence[0]["status"] == "passed"
        assert evidence[0]["exit_code"] == 0
        assert "evidence_hash" in evidence[0]
        assert evidence[0]["evidence_hash"].startswith("sha256:")
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_batch_validation_skips_post_execute_on_non_final_batch() -> None:
    """Post-execute suite only runs on the final batch."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "post_execute_suite",
                    "command": "echo suite",
                    "selectors": ["tests"],
                    "max_seconds": 3600,
                    "max_runs": 1,
                    "reason": "Full suite.",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)
        fake_result = SuiteRunResult(
            run_id="fake-run-002",
            phase="post_execute_suite",
            command="echo suite",
            duration=0.1, collected=1, collected_ids=["test_x"],
            failures=[], passes=["test_x"], status="passed",
            exit_code=0, raw_log_path=project_dir / "raw.log",
            code_hash="sha256:bbb", collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=fake_result,
        ) as mock_run:
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-suite"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    # Not final batch → post_execute_suite should be skipped
                    evidence = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        # suite_runner must NOT have been called
        mock_run.assert_not_called()
        assert evidence == []
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_batch_validation_runs_post_execute_on_final_batch() -> None:
    """Post-execute suite runs on the final batch."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "post_execute_suite",
                    "command": "echo suite",
                    "selectors": ["tests"],
                    "max_seconds": 3600,
                    "max_runs": 1,
                    "reason": "Full suite.",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)
        fake_result = SuiteRunResult(
            run_id="fake-run-003",
            phase="post_execute_suite",
            command="echo suite",
            duration=0.1, collected=5, collected_ids=["t1", "t2"],
            failures=[], passes=["t1", "t2"], status="passed",
            exit_code=0, raw_log_path=project_dir / "raw.log",
            code_hash="sha256:ccc", collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=fake_result,
        ) as mock_run:
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-final"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    evidence = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=True,
                        state=state,
                    )

        mock_run.assert_called_once()
        assert len(evidence) == 1
        assert evidence[0]["kind"] == "post_execute_suite"
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_batch_validation_skips_narrow_recheck_not_in_batch() -> None:
    """Narrow recheck jobs only run when task_id is in the batch."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "echo t2",
                    "selectors": ["tests/test_t2.py"],
                    "max_seconds": 120,
                    "max_runs": 1,
                    "reason": "Narrow T2",
                    "task_id": "T2",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)
        fake_result = SuiteRunResult(
            run_id="fake-run-004",
            phase="narrow_recheck",
            command="echo t2", duration=0.1, collected=1, collected_ids=[],
            failures=[], passes=[], status="passed",
            exit_code=0, raw_log_path=project_dir / "raw.log",
            code_hash="sha256:ddd", collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=fake_result,
        ) as mock_run:
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    # T2 is NOT in the batch
                    evidence = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        mock_run.assert_not_called()
        assert evidence == []
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_evidence_is_content_addressed_in_batch_context() -> None:
    """Evidence records from _run_batch_validation_jobs have content hashes."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "echo test",
                    "selectors": ["tests/test_t1.py"],
                    "max_seconds": 120,
                    "max_runs": 1,
                    "reason": "Narrow T1",
                    "task_id": "T1",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)

        # Run with pass result
        pass_result = SuiteRunResult(
            run_id="run-pass", phase="narrow_recheck", command="echo test",
            duration=0.5, collected=3, collected_ids=["a", "b", "c"],
            failures=[], passes=["a", "b", "c"], status="passed",
            exit_code=0, raw_log_path=project_dir / "raw_pass.log",
            code_hash="sha256:pass", collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=pass_result,
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-pass"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    evidence_pass = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        # Run with fail result
        fail_result = SuiteRunResult(
            run_id="run-fail", phase="narrow_recheck", command="echo test",
            duration=0.5, collected=3, collected_ids=["a", "b", "c"],
            failures=["a", "b", "c"], passes=[], status="failed",
            exit_code=1, raw_log_path=project_dir / "raw_fail.log",
            code_hash="sha256:fail", collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=fail_result,
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-fail"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    evidence_fail = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        assert len(evidence_pass) == 1
        assert len(evidence_fail) == 1

        # Content hashes must differ for pass vs fail
        assert evidence_pass[0]["evidence_hash"] != evidence_fail[0]["evidence_hash"]
        assert evidence_pass[0]["status"] == "passed"
        assert evidence_fail[0]["status"] == "failed"
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_validation_evidence_is_durable_on_disk() -> None:
    """Evidence artifacts are stored to verification/ directory."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "echo durable",
                    "selectors": ["tests/test_t1.py"],
                    "max_seconds": 120,
                    "max_runs": 1,
                    "reason": "Narrow T1",
                    "task_id": "T1",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)
        fake_result = SuiteRunResult(
            run_id="run-durable", phase="narrow_recheck",
            command="echo durable", duration=0.2, collected=2,
            collected_ids=["x", "y"], failures=[], passes=["x", "y"],
            status="passed", exit_code=0,
            raw_log_path=project_dir / "raw_durable.log",
            code_hash="sha256:dur", collections_parse_ok=True,
        )

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=fake_result,
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
                return_value={"event_id": "ev-dur"},
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                ):
                    _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        # Evidence file should exist on disk
        ver_dir = plan_dir / "verification"
        assert ver_dir.exists()
        artifacts = list(ver_dir.glob("validation_VJ1_*.json"))
        assert len(artifacts) >= 1
        content = json.loads(artifacts[0].read_text(encoding="utf-8"))
        assert content["job_id"] == "VJ1"
        assert content["status"] == "passed"
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_validation_job_runner_error_emits_unavailable_reason() -> None:
    """When suite_runner raises, the batch consumer emits unavailable_reason."""
    from unittest.mock import MagicMock, patch

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "bogus_cmd_that_will_fail",
                    "selectors": ["tests/test_t1.py"],
                    "max_seconds": 120,
                    "max_runs": 1,
                    "reason": "Narrow T1",
                    "task_id": "T1",
                    "writes_files": False,
                },
            ],
        }
        state = _make_state(project_dir)

        mock_emit_unavailable = MagicMock(return_value={"event_id": "ev-una"})

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
            side_effect=RuntimeError("subprocess spawning failed"),
        ):
            with patch(
                "arnold_pipelines.megaplan.observability.work_ledger.emit_validation",
            ):
                with patch(
                    "arnold_pipelines.megaplan.observability.work_ledger.emit_unavailable_reason",
                    mock_emit_unavailable,
                ):
                    evidence = _run_batch_validation_jobs(
                        plan_dir=plan_dir,
                        project_dir=project_dir,
                        finalize_data=finalize_data,
                        batch_task_ids=["T1"],
                        is_final_batch=False,
                        state=state,
                    )

        # Must emit unavailable_reason
        mock_emit_unavailable.assert_called_once()
        # Evidence record must reflect the error
        assert len(evidence) == 1
        assert evidence[0]["status"] == "runner_error"
        assert evidence[0]["exit_code"] is None
        assert "RuntimeError" in evidence[0]["error"]
    finally:
        try:
            for d in (plan_dir, project_dir):
                for f in d.rglob("*"):
                    if f.is_file():
                        f.unlink()
                for f in sorted(d.rglob("*"), reverse=True):
                    if f.is_dir():
                        f.rmdir()
                d.rmdir()
        except OSError:
            pass


def test_batch_validation_no_model_dispatch_path() -> None:
    """_run_batch_validation_jobs does not import or call any worker dispatch."""
    import inspect

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )

    source = inspect.getsource(_run_batch_validation_jobs)
    # No worker dispatch keywords
    assert "dispatch_worker" not in source
    assert "run_worker" not in source
    assert "invoke_model" not in source
    # suite_runner.run_suite is the only subprocess path
    assert "run_suite" in source or "_run_suite" in source
