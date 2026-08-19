"""M8A execute wiring tests — admission guard, split integration, and mutation rejection.

These tests prove that the ``_guard_execute_batch_admission`` shared helper
prevents worker dispatch when the post-finalize task graph has been mutated,
and that the full admission→split→batch pipeline is wired correctly.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
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
    _partition_review_rework_tasks,
    _review_rework_context,
    _review_rework_task_ids,
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
        ) as mock_run:
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
        assert mock_run.call_args.args[1]["test_command"] == "echo ok"
        assert mock_run.call_args.kwargs["deadline_seconds"] > time.monotonic() + 50
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


def test_batch_validation_defers_missing_selector_declared_as_task_output() -> None:
    """A task's future test file cannot gate the worker that must create it."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import _run_batch_validation_jobs

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        selector = "tests/new_feature/test_entry_gate.py"
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "write_set": {"paths": [selector], "complete": True},
                }
            ],
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": f"pytest {selector}",
                    "selectors": [selector],
                    "max_seconds": 60,
                    "task_id": "T1",
                    "writes_files": False,
                    "mutates": False,
                }
            ],
        }

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
        ) as mock_run:
            evidence = _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                batch_task_ids=["T1"],
            )

        mock_run.assert_not_called()
        assert evidence == [
            {
                "job_id": "VJ1",
                "kind": "narrow_recheck",
                "status": "deferred_task_output",
                "exit_code": None,
                "task_id": "T1",
                "missing_selectors": [selector],
                "reason": "selector_is_declared_task_output",
                "evidence_hash": evidence[0]["evidence_hash"],
            }
        ]
        assert evidence[0]["evidence_hash"].startswith("sha256:")
        assert (plan_dir / "verification" / "validation_VJ1_deferred.json").exists()
    finally:
        shutil.rmtree(plan_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)


def test_batch_validation_rejects_missing_undeclared_selector() -> None:
    """Missing selectors are deferred only when the task promises to create them."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import _run_batch_validation_jobs
    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "write_set": {"paths": ["src/feature.py"], "complete": True},
                }
            ],
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "pytest tests/typo.py",
                    "selectors": ["tests/typo.py"],
                    "max_seconds": 60,
                    "task_id": "T1",
                    "writes_files": False,
                    "mutates": False,
                }
            ],
        }

        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
        ) as mock_run:
            with pytest.raises(CliError, match="not declared task outputs"):
                _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                )

        mock_run.assert_not_called()
    finally:
        shutil.rmtree(plan_dir, ignore_errors=True)
        shutil.rmtree(project_dir, ignore_errors=True)


def _deferred_selector_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    selector = "tests/new_feature/test_entry_gate.py"
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    finalize_data: dict[str, object] = {
        "tasks": [
            {
                "id": "T1",
                "status": "pending",
                "write_set": {"paths": [selector], "complete": True},
            }
        ],
        "validation_jobs": [
            {
                "id": "VJ1",
                "kind": "narrow_recheck",
                "command": f"pytest {selector}",
                "selectors": [selector],
                "max_seconds": 60,
                "task_id": "T1",
                "writes_files": False,
                "mutates": False,
            }
        ],
    }
    return plan_dir, project_dir, finalize_data


def _accepted_task_payload(
    *,
    selector: str,
    files_changed: list[str] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    from arnold_pipelines.megaplan.authority.batch_scope import RESULT_ENVELOPES_KEY
    from arnold_pipelines.megaplan.authority.binding import (
        DispatchIdentity,
        TASK_RESULT_CAPABILITY,
    )
    from arnold_pipelines.megaplan.execute.batch import _task_result_envelope

    entry: dict[str, object] = {
        "task_id": "T1",
        "status": "done",
        "executor_notes": "created the test output",
        "files_changed": list(files_changed if files_changed is not None else [selector]),
        "commands_run": ["pytest"],
    }
    identity = DispatchIdentity.create(
        dispatch_id="dispatch-vj1",
        run_id="run-vj1",
        run_revision="revision-vj1",
        coordinator_attempt_id="coordinator-vj1",
        fence_token=1,
        subject_ids=("T1",),
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="prereq-vj1",
        worker_id="worker-vj1",
    )
    envelope = _task_result_envelope(
        identity=identity,
        entry=entry,
        ordinal=1,
        source="test",
    )
    assert envelope is not None
    entry["authority_validation"] = {
        "outcome": "accepted",
        "envelope_digest": envelope.digest(),
    }
    payload: dict[str, object] = {
        "task_updates": [entry],
        RESULT_ENVELOPES_KEY: [envelope.to_dict()],
    }
    return payload, entry


def test_deferred_selector_reruns_after_accepted_result_envelope(tmp_path: Path) -> None:
    """A declared future selector is revalidated after its accepted output lands."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    assert deferred[0]["status"] == "deferred_task_output"
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    payload, _entry = _accepted_task_payload(selector=selector)
    # In production the merge path updates the finalized task before the
    # deferred recheck.  Mirror that post-merge state here.
    finalize_data["tasks"][0]["status"] = "done"
    fake_result = SuiteRunResult(
        run_id="rerun-vj1",
        phase="narrow_recheck",
        command=f"pytest {selector}",
        duration=0.1,
        collected=1,
        collected_ids=["test_gate"],
        failures=[],
        passes=["test_gate"],
        status="passed",
        exit_code=0,
        raw_log_path=project_dir / "raw.log",
        code_hash="sha256:rerun",
        collections_parse_ok=True,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake_result,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=deferred,
            payload=payload,
            state=state,
        )
    mock_run.assert_called_once()
    assert rerun[0]["status"] == "passed"


def test_deferred_loop_legacy_shape_job_runs_strict_recheck(tmp_path: Path) -> None:
    """A legacy-derived delta job (acceptance_mode None) reruns strict.

    Legacy compiled commands carry the ``timeout <N>s pytest ...`` shape, so
    ``_narrow_recheck_delta_policy`` derives the delta lifecycle for them.
    A deferred record for such a job has no pre-envelope by construction
    (the selector was missing at pre-dispatch); refusing would wedge
    pre-delta plans (occurrence 0a0ce24c3510).  The job was compiled under
    the strict exit-0 contract, so the deferred recheck must run the strict
    gate instead of raising ``delta_policy_deferred_selector_unsupported``.
    """
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    finalize_data["validation_jobs"][0].update(
        {
            "command": f"timeout 120s pytest {selector} --tb=short -q",
            "selectors": [selector],
        }
    )
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    assert deferred[0]["status"] == "deferred_task_output"
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    payload, _entry = _accepted_task_payload(selector=selector)
    finalize_data["tasks"][0]["status"] = "done"
    fake_result = SuiteRunResult(
        run_id="rerun-vj1",
        phase="narrow_recheck",
        command=f"pytest {selector}",
        duration=0.1,
        collected=1,
        collected_ids=["test_gate"],
        failures=[],
        passes=["test_gate"],
        status="passed",
        exit_code=0,
        raw_log_path=project_dir / "raw.log",
        code_hash="sha256:rerun",
        collections_parse_ok=True,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake_result,
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=deferred,
            payload=payload,
            state=state,
        )
    mock_run.assert_called_once()
    assert rerun[0]["status"] == "passed"


def test_deferred_loop_explicit_delta_job_still_refuses(tmp_path: Path) -> None:
    """An EXPLICIT delta job (acceptance_mode set) still refuses deferred rerun."""
    from arnold_pipelines.megaplan.execute.batch import (
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    finalize_data["validation_jobs"][0].update(
        {
            "command": f"timeout 120s pytest {selector} --tb=short -q",
            "selectors": [selector],
            "acceptance_mode": "no_new_failures_delta",
        }
    )
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    payload, _entry = _accepted_task_payload(selector=selector)
    finalize_data["tasks"][0]["status"] = "done"
    with pytest.raises(
        CliError,
        match="delta_policy_deferred_selector_unsupported",
    ):
        _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=deferred,
            payload=payload,
            state=state,
        )


def test_final_sweep_legacy_shape_job_runs_strict_recheck(tmp_path: Path) -> None:
    """Final sweep reruns a legacy-derived delta job with the strict gate."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _sweep_persisted_deferred_selector_jobs,
    )
    from arnold_pipelines.megaplan.orchestration.suite_runner import SuiteRunResult

    plan_dir, project_dir, finalize_data, state, _deferred = _sweep_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    finalize_data["validation_jobs"][0].update(
        {
            "command": f"timeout 120s pytest {selector} --tb=short -q",
            "selectors": [selector],
        }
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    finalize_data["tasks"][0]["status"] = "done"
    fake_result = SuiteRunResult(
        run_id="sweep-vj1",
        phase="narrow_recheck",
        command=f"pytest {selector}",
        duration=0.1,
        collected=1,
        collected_ids=["test_gate"],
        failures=[],
        passes=["test_gate"],
        status="passed",
        exit_code=0,
        raw_log_path=project_dir / "raw.log",
        code_hash="sha256:sweep",
        collections_parse_ok=True,
    )
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite",
        return_value=fake_result,
    ) as mock_run:
        swept = _sweep_persisted_deferred_selector_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            state=state,
        )
    mock_run.assert_called_once()
    assert swept and swept[0]["status"] == "passed"


def test_final_sweep_explicit_delta_job_still_refuses(tmp_path: Path) -> None:
    """Final sweep still refuses an EXPLICIT delta job (fail-closed)."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _sweep_persisted_deferred_selector_jobs,
    )

    plan_dir, project_dir, finalize_data, state, _deferred = _sweep_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    finalize_data["validation_jobs"][0].update(
        {
            "command": f"timeout 120s pytest {selector} --tb=short -q",
            "selectors": [selector],
            "acceptance_mode": "no_new_failures_delta",
        }
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    finalize_data["tasks"][0]["status"] = "done"
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        with pytest.raises(
            CliError,
            match="delta_policy_deferred_selector_unsupported",
        ):
            _sweep_persisted_deferred_selector_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                state=state,
            )
    mock_run.assert_not_called()


def test_canonical_v2_missing_tasks_cannot_bypass_selector_classification(tmp_path: Path) -> None:
    """A malformed canonical graph must not run a selector without an owner."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import _run_batch_validation_jobs

    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    finalize_data = {
        "task_contract_version": 2,
        "validation_jobs": [
            {
                "id": "VJ1",
                "kind": "narrow_recheck",
                "command": "pytest tests/missing.py",
                "selectors": ["tests/missing.py"],
                "task_id": "T1",
                "mutates": False,
                "writes_files": False,
            }
        ],
    }
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        with pytest.raises(CliError, match="without the finalized task graph"):
            _run_batch_validation_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                batch_task_ids=["T1"],
            )
    mock_run.assert_not_called()


def test_post_policy_blocked_task_cannot_release_deferred_selector(tmp_path: Path) -> None:
    """An earlier accepted authority outcome cannot override a later policy block.

    The blocked row must NOT release the deferred selector; the refusal is
    parked as a typed ``post_merge_policy_blocked`` / ``validation_blocked``
    disposition instead of raising a terminal CliError, so the execute
    coordinator can publish its aggregate state and a fresh compliant attempt
    (via ``--retry-blocked-tasks``) can rerun the task.
    """
    from arnold_pipelines.megaplan.execute.batch import (
        _POST_MERGE_POLICY_BLOCKED,
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=_make_state(project_dir),
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    payload, _entry = _accepted_task_payload(selector=selector)
    finalize_data["tasks"][0]["status"] = "blocked"
    results = _rerun_deferred_selector_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        pre_dispatch_results=deferred,
        payload=payload,
        state=_make_state(project_dir),
    )
    # The refusal is parked as a typed validation_blocked disposition.
    assert len(results) == 1
    parked = results[0]
    assert parked["status"] == _POST_MERGE_POLICY_BLOCKED
    assert parked["disposition"] == "validation_blocked"
    assert parked["reason"] == "task_result_blocked_by_post_merge_policy"
    assert parked["task_status"] == "blocked"
    # No pass artifact is minted and the suite runner is not invoked.
    assert not (plan_dir / "verification" / "validation_VJ1_passed.json").exists()
    # The row itself stays blocked.
    assert finalize_data["tasks"][0]["status"] == "blocked"


def test_deferred_selector_blocks_without_accepted_result_envelope(tmp_path: Path) -> None:
    """A COMPLETED task without durable accepted authority cannot release deferral.

    Adopt-miss backstop: once the declaring task is done/completed, a missing
    accepted result envelope is a genuine anomaly and must still block.
    """
    from arnold_pipelines.megaplan.execute.batch import (
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    # The production merge path records the post-merge task outcome before the
    # deferred recheck is eligible to run; a done task with no envelope is the
    # adopt-miss/anomaly case that must keep failing closed.
    finalize_data["tasks"][0]["status"] = "done"
    with pytest.raises(CliError, match="accepted_task_result_envelope_missing"):
        _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=deferred,
            payload={"task_updates": []},
            state=state,
        )


def test_pending_task_parks_deferred_selector_without_accepted_envelope(
    tmp_path: Path,
) -> None:
    """Abort-recovery park: a NOT-complete task with no accepted envelope parks.

    The worker aborted mid-batch (e.g. provider/transport failure) before
    minting an accepted result envelope; the declaring task is still pending.
    The deferred recheck must NOT raise a terminal block (that wedged the plan
    on a task that never completed) and must NOT run the suite; the persisted
    deferred evidence stays unresolved for the next resume to re-dispatch.
    """
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    deferred_artifact = plan_dir / "verification" / "validation_VJ1_deferred.json"
    assert deferred_artifact.exists()
    assert finalize_data["tasks"][0]["status"] == "pending"
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        rerun = _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=deferred,
            payload={"task_updates": []},
            state=state,
        )
    mock_run.assert_not_called()
    assert rerun == []
    # Persisted deferred evidence survives; no resolved validation artifact
    # is minted for a parked job.
    assert deferred_artifact.exists()
    assert not set(
        plan_dir.joinpath("verification").glob("validation_VJ1_*.json")
    ) - {deferred_artifact}


def test_deferred_selector_blocks_empty_accepted_result_files(tmp_path: Path) -> None:
    """An accepted envelope with no claimed files cannot release deferral."""
    from arnold_pipelines.megaplan.execute.batch import (
        _rerun_deferred_selector_validation_jobs,
        _run_batch_validation_jobs,
    )

    plan_dir, project_dir, finalize_data = _deferred_selector_fixture(tmp_path)
    selector = "tests/new_feature/test_entry_gate.py"
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    (project_dir / selector).parent.mkdir(parents=True)
    (project_dir / selector).write_text("def test_gate(): pass\n", encoding="utf-8")
    payload, _entry = _accepted_task_payload(selector=selector, files_changed=[])
    # The production merge path records the post-merge task outcome before
    # deferred selector validation is eligible to run.
    finalize_data["tasks"][0]["status"] = "done"
    with pytest.raises(
        CliError,
        match="accepted_task_result_files_changed_missing_or_empty",
    ):
        _rerun_deferred_selector_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            batch_task_ids=["T1"],
            pre_dispatch_results=deferred,
            payload=payload,
            state=state,
        )


def _sweep_fixture(tmp_path: Path, *, tasks_override: list[dict] | None = None):
    """Plan/project/finalize fixture for final-sweep deferred-selector tests."""
    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
    )

    selector = "tests/new_feature/test_entry_gate.py"
    plan_dir = tmp_path / "plan"
    project_dir = tmp_path / "project"
    plan_dir.mkdir()
    project_dir.mkdir()
    tasks = tasks_override if tasks_override is not None else None
    if tasks is None:
        finalize_data = {
            "tasks": [
                {
                    "id": "T1",
                    "status": "pending",
                    "write_set": {"paths": [selector], "complete": True},
                }
            ],
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": f"pytest {selector}",
                    "selectors": [selector],
                    "max_seconds": 60,
                    "task_id": "T1",
                    "writes_files": False,
                    "mutates": False,
                }
            ],
        }
    else:
        finalize_data = {
            "tasks": tasks,
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": f"pytest {selector}",
                    "selectors": [selector],
                    "max_seconds": 60,
                    "task_id": "T1",
                    "writes_files": False,
                    "mutates": False,
                }
            ],
        }
    state = _make_state(project_dir)
    deferred = _run_batch_validation_jobs(
        plan_dir=plan_dir,
        project_dir=project_dir,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        state=state,
    )
    return plan_dir, project_dir, finalize_data, state, deferred


def test_final_sweep_parks_deferred_selector_while_owner_pending(
    tmp_path: Path,
) -> None:
    """Final sweep parks a deferred selector whose owner is still pending."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _sweep_persisted_deferred_selector_jobs,
    )

    plan_dir, project_dir, finalize_data, state, _deferred = _sweep_fixture(tmp_path)
    deferred_artifact = plan_dir / "verification" / "validation_VJ1_deferred.json"
    assert deferred_artifact.exists()
    assert finalize_data["tasks"][0]["status"] == "pending"
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        swept = _sweep_persisted_deferred_selector_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            state=state,
        )
    mock_run.assert_not_called()
    assert swept == []
    assert deferred_artifact.exists()
    assert not set(
        plan_dir.joinpath("verification").glob("validation_VJ1_*.json")
    ) - {deferred_artifact}


def test_final_sweep_fails_when_completed_owner_never_created_selector(
    tmp_path: Path,
) -> None:
    """Final sweep still fails closed when a DONE owner never created its selector."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _sweep_persisted_deferred_selector_jobs,
    )

    plan_dir, project_dir, finalize_data, state, _deferred = _sweep_fixture(tmp_path)
    finalize_data["tasks"][0]["status"] = "done"
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        with pytest.raises(
            CliError,
            match="declared_selector_output_never_created",
        ):
            _sweep_persisted_deferred_selector_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                state=state,
            )
    mock_run.assert_not_called()


def test_final_sweep_parks_cross_task_selector_while_declaring_task_pending(
    tmp_path: Path,
) -> None:
    """Final sweep parks when a cross-task producer of the selector is pending."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _sweep_persisted_deferred_selector_jobs,
    )

    selector = "tests/new_feature/test_entry_gate.py"
    tasks = [
        {
            "id": "T1",
            "status": "done",
            "write_set": {"paths": [selector], "complete": True},
        },
        {
            "id": "T2",
            "status": "pending",
            "write_set": {"paths": [selector], "complete": True},
        },
    ]
    plan_dir, project_dir, finalize_data, state, _deferred = _sweep_fixture(
        tmp_path, tasks_override=tasks
    )
    deferred_artifact = plan_dir / "verification" / "validation_VJ1_deferred.json"
    assert deferred_artifact.exists()
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        swept = _sweep_persisted_deferred_selector_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data=finalize_data,
            state=state,
        )
    mock_run.assert_not_called()
    assert swept == []
    assert deferred_artifact.exists()
    # Once the cross-task producer completes too, the sweep fails closed.
    finalize_data["tasks"][1]["status"] = "done"
    with patch(
        "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run2:
        with pytest.raises(
            CliError,
            match="declared_selector_output_never_created",
        ):
            _sweep_persisted_deferred_selector_jobs(
                plan_dir=plan_dir,
                project_dir=project_dir,
                finalize_data=finalize_data,
                state=state,
            )
    mock_run2.assert_not_called()


def test_execute_validation_deadlines_use_absolute_monotonic_time() -> None:
    """Suite runner deadlines are absolute, never raw relative timeout values."""
    import inspect

    from arnold_pipelines.megaplan.execute.batch import (
        _run_batch_validation_jobs,
        _run_repair_adoption_check,
    )

    for function in (_run_batch_validation_jobs, _run_repair_adoption_check):
        source = inspect.getsource(function)
        assert "deadline_seconds=float(" not in source
        assert (
            "deadline_seconds=(\n" in source
            or "time.monotonic() + float(" in source
            or "time.monotonic() + _run_deadline_seconds" in source
        )


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
                    with pytest.raises(CliError) as caught:
                        _run_batch_validation_jobs(
                            plan_dir=plan_dir,
                            project_dir=project_dir,
                            finalize_data=finalize_data,
                            batch_task_ids=["T1"],
                            is_final_batch=False,
                            state=state,
                        )

        assert len(evidence_pass) == 1
        # The failing result is persisted as evidence before dispatch is
        # blocked; it is never converted into a productive execution result.
        assert caught.value.code == "validation_job_failed"
        fail_evidence = json.loads(
            next((plan_dir / "verification").glob("validation_VJ1_run-fail.json")).read_text()
        )
        assert evidence_pass[0]["evidence_hash"] != fail_evidence["evidence_hash"]
        assert evidence_pass[0]["status"] == "passed"
        assert fail_evidence["status"] == "failed"
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


def test_repair_adoption_rereads_current_execution_artifacts() -> None:
    """Adoption context comes from current artifacts, never receipt values."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import (
        _reread_current_boundary_conditions,
    )

    plan_dir = Path(tempfile.mkdtemp(prefix="test_repair_adoption_plan_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_repair_adoption_project_"))
    try:
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "config": {"project_dir": str(project_dir)},
                    "latest_failure": None,
                }
            ),
            encoding="utf-8",
        )
        batch_dir = plan_dir / "execute_batches" / "batch_1"
        batch_dir.mkdir(parents=True)
        evidence_path = batch_dir / "tasks_current.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "result_envelopes": [
                        {
                            "dispatch": {
                                "grant": {"run_revision": "sha256:current-plan"}
                            },
                            "claim": {
                                "subject_id": "T16",
                                "payload_hash": "sha256:current-result",
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        stale_receipt = {
            "target": {},
            "plan_revision": "sha256:receipt-plan",
            "task_contract": "receipt-task",
            "tree_commit": "receipt-tree",
            "payload_hash": "sha256:receipt-result",
        }
        boundary_result = SimpleNamespace(checks=[])
        git_result = SimpleNamespace(returncode=0, stdout="current-tree\n")
        with patch(
            "arnold_pipelines.megaplan.custody.action_validator.validate_action_boundary_simple",
            return_value=boundary_result,
        ):
            with patch(
                "arnold_pipelines.megaplan.execute.batch.subprocess.run",
                return_value=git_result,
            ):
                current, diagnostics = _reread_current_boundary_conditions(
                    stale_receipt,
                    plan_dir=plan_dir,
                    task_contract="T16",
                )

        assert current["plan_revision"] == "sha256:current-plan"
        assert current["task_contract"] == "T16"
        assert current["tree_commit"] == "current-tree"
        assert current["test_result_hash"] == "sha256:current-result"
        assert current["blocker_hash"] == ""
        assert diagnostics["sources"]["current_task_result"]["outcome"] == "observed"
        assert all("receipt" not in str(value) for value in current.values())
    finally:
        try:
            for root in (plan_dir, project_dir):
                for path in sorted(root.rglob("*"), reverse=True):
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                root.rmdir()
        except OSError:
            pass


def test_validation_job_mutation_is_rejected_before_suite_boundary() -> None:
    """Mutating declarations fail closed before the deterministic runner."""
    from unittest.mock import patch

    from arnold_pipelines.megaplan.execute.batch import _run_batch_validation_jobs
    from arnold_pipelines.megaplan.types import CliError

    plan_dir = Path(tempfile.mkdtemp(prefix="test_batch_val_"))
    project_dir = Path(tempfile.mkdtemp(prefix="test_batch_proj_"))
    try:
        finalize_data = {
            "validation_jobs": [
                {
                    "id": "VJ1",
                    "kind": "narrow_recheck",
                    "command": "pytest tests/test_t1.py -q",
                    "task_id": "T1",
                    "mutates": True,
                    "writes_files": False,
                }
            ]
        }
        with patch(
            "arnold_pipelines.megaplan.orchestration.suite_runner.run_suite"
        ) as mock_run:
            with pytest.raises(CliError) as caught:
                _run_batch_validation_jobs(
                    plan_dir=plan_dir,
                    project_dir=project_dir,
                    finalize_data=finalize_data,
                    batch_task_ids=["T1"],
                    state=_make_state(project_dir),
                )

        mock_run.assert_not_called()
        assert caught.value.code == "invalid_validation_job"
        assert caught.value.extra == {
            "job_id": "VJ1",
            "invalid_fields": ["mutates"],
            "validation_job_kind": "narrow_recheck",
        }
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


def test_failure_signature_distinguishes_validation_commands() -> None:
    """Equivalent messages from distinct deterministic commands do not collide."""
    from types import SimpleNamespace

    from arnold_pipelines.megaplan.orchestration.recovery_policy import (
        normalize_failure_signature,
    )

    first = SimpleNamespace(message="pytest failed", command="pytest tests/a.py")
    second = SimpleNamespace(message="pytest failed", command="pytest tests/b.py")
    assert normalize_failure_signature("review_quality_block", first) != (
        normalize_failure_signature("review_quality_block", second)
    )


# ---------------------------------------------------------------------------
# M10 Step 7H-b: seed_epoch epoch-fencing, config threading, and v1/None
# admission blocking at the dispatch guard.
# ---------------------------------------------------------------------------


def test_guard_threads_seed_epoch_when_state_attests_and_graph_matches() -> None:
    """When state carries seed_epoch and the finalized graph echoes it, the
    guard admits dispatch without error."""
    tasks = [_task("T1")]
    finalize_data = _payload(tasks)
    finalize_data["seed_epoch"] = "epoch-current"
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()
    state["seed_epoch"] = "epoch-current"

    # Must not raise — matching epoch, valid v2 graph.
    _guard_execute_batch_admission(finalize_data, state)


def test_guard_rejects_stale_seed_epoch_as_cli_error() -> None:
    """A stale/conflicted seed_epoch in state vs the finalized receipt is
    blocked at the dispatch guard before any worker is launched."""
    tasks = [_task("T1")]
    finalize_data = _payload(tasks)
    finalize_data["seed_epoch"] = "epoch-finalized"
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()
    state["seed_epoch"] = "epoch-stale"

    with pytest.raises(CliError, match="seed_epoch mismatch"):
        _guard_execute_batch_admission(finalize_data, state)


def test_guard_blocks_v1_none_admission_escape() -> None:
    """A v1 payload (no task_contract_version=2) is blocked by the guard so
    only fully-admitted v2 graphs reach worker dispatch."""
    finalize_data = {"task_contract_version": 1, "tasks": [], "validation_jobs": []}
    state = _make_state()

    with pytest.raises(CliError, match="v1 task contract is not admitted") as caught:
        _guard_execute_batch_admission(finalize_data, state)
    assert caught.value.code == "finalized_task_graph_changed"
    assert "finalize" in caught.value.valid_next
    assert "revise" in caught.value.valid_next


def test_guard_threads_config_phase_timeout_into_admission() -> None:
    """The guard threads state config into the feasibility verdict — a short
    phase_timeout_seconds that makes the critical path infeasible is respected.

    This guards against the pre-M10 shadow-feasibility bug where config was
    computed but never passed to assert_admitted_task_feasibility.
    """
    # Single task with 5 estimated minutes.
    tasks = [_task("T1", minutes=5)]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)

    # With the default 3600s timeout (60 min), 5 min critical path is fine.
    state_default = _make_state()
    _guard_execute_batch_admission(finalize_data, state_default)

    # With a 240s phase timeout, 5 min critical path > 80% of 4 min → rejected.
    state_short = _make_state()
    state_short["config"]["phase_timeout_seconds"] = 240

    with pytest.raises(CliError, match="critical_path_infeasible"):
        _guard_execute_batch_admission(finalize_data, state_short)


def test_guard_preserves_backward_compat_without_seed_epoch_in_state() -> None:
    """When state has no seed_epoch key, the epoch protocol is not activated
    and a valid v2 graph is admitted (backward-compat for pre-M10 plans)."""
    tasks = [_task("T1"), _task("T2", depends_on=["T1"])]
    finalize_data = _payload(tasks)
    finalize_data["graph_report"] = compile_task_feasibility(finalize_data)
    state = _make_state()
    assert "seed_epoch" not in state

    # Must not raise even though finalize_data has no seed_epoch either.
    _guard_execute_batch_admission(finalize_data, state)


def test_large_review_rework_wave_is_partitioned_without_loss() -> None:
    """The ceiling bounds each dispatch rather than rejecting the review."""
    task_ids = [f"T{index}" for index in range(1, 9)]

    subwaves = _partition_review_rework_tasks(task_ids, ceiling=5)

    assert subwaves == [task_ids[:5], task_ids[5:]]
    assert [task_id for wave in subwaves for task_id in wave] == task_ids
    assert all(len(wave) <= 5 for wave in subwaves)


def test_bulk_review_target_keeps_issue_context_in_each_relevant_subwave() -> None:
    """A bulk finding must not disappear when its top-level task is elsewhere."""
    review_data = {
        "rework_items": [
            {
                "task_id": "T33",
                "target": {
                    "kind": "bulk",
                    "id": "production-topology",
                    "task_ids": ["T33", "T35", "T43"],
                },
                "issue": "Production cadence still uses the obsolete six-hour anchor.",
                "expected": "Use the accepted three-hour topology.",
                "actual": "The generated schedule still says six hours.",
                "evidence_file": "tests/test_schedule.py",
            }
        ]
    }
    finalize_data = {
        "tasks": [
            {"id": "T33", "files_changed": ["src/schedule.py"]},
            {"id": "T35", "files_changed": ["src/generator.py"]},
            {"id": "T43", "files_changed": ["tests/test_schedule.py"]},
        ]
    }

    runnable, unrunnable = _review_rework_task_ids(review_data, finalize_data)
    context = _review_rework_context(review_data, finalize_data, ["T35", "T43"])

    assert runnable == ["T33", "T35", "T43"]
    assert unrunnable == []
    assert len(context["rework_items"]) == 1
    assert context["rework_items"][0]["task_ids"] == ["T35", "T43"]
    assert context["rework_items"][0]["issue"] == review_data["rework_items"][0]["issue"]


def test_bulk_review_target_tracks_nonconvergence_for_every_target_task() -> None:
    """Auto-driver convergence accounting must use the same target expansion."""
    from arnold_pipelines.megaplan.auto import _review_rework_signatures_by_task

    review_data = {
        "review_verdict": "needs_rework",
        "rework_items": [
            {
                "task_id": "REVIEW",
                "target": {
                    "kind": "manifest",
                    "id": "review_evidence.json",
                    "task_ids": ["T1", "T46"],
                },
                "flag_id": "manifest-freshness",
                "issue": "The review evidence manifest is stale.",
            }
        ],
    }

    signatures = _review_rework_signatures_by_task(review_data)

    assert signatures == {
        "T1": {"flag:manifest-freshness"},
        "T46": {"flag:manifest-freshness"},
    }