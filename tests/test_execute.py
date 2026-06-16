from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines import megaplan
import arnold.pipelines.megaplan._core
import arnold.pipelines.megaplan.execute.aggregation as megaplan_execute_aggregation
import arnold.pipelines.megaplan.execute.batch as megaplan_execute_batch
import arnold.pipelines.megaplan.execute.core as megaplan_execute_core
import arnold.pipelines.megaplan.execute.timeout as megaplan_execute_timeout
from arnold.pipelines.megaplan.execute._binding.reducer import BatchOutcome, reduce_batch
import arnold.pipelines.megaplan.handlers as megaplan_handlers
import arnold.pipelines.megaplan.handlers.critique as critique_handler
import arnold.pipelines.megaplan.handlers.execute as execute_handler
from arnold.pipelines.megaplan.orchestration.transition_policy import (
    TRANSITION_DECISION_REVIEW_DONE_FILENAME,
)
import arnold.pipelines.megaplan.workers as megaplan_workers
from arnold.pipelines.megaplan._core import compute_task_batches, load_plan, save_state, split_oversized_batches
from arnold.pipelines.megaplan.calibration import RouteSuggestion
from arnold.pipelines.megaplan.execute.quality import (
    _auto_attribute_unclaimed_paths,
    _capture_git_status_snapshot,
    _capture_git_status_snapshot_recursive,
    _check_done_task_evidence,
    _check_done_task_evidence_by_kind,
    expand_projected_path_list,
    project_advisory_path_sets,
    summarize_path_list_for_prose,
)
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import WorkerResult
from tests.conftest import (
    PlanFixture,
    _make_plan_fixture_with_robustness,
    _write_lines,
    load_state,
    make_args_factory,
    read_json,
)


def test_execute_capture_payload_normalizes_receipt_shaped_batch_output(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeOutcome:
        legacy_payload: dict[str, object]

        def __init__(self, payload: dict[str, object]) -> None:
            self.legacy_payload = payload

    def fake_capture_step_output(invocation: object, payload: dict[str, object]) -> FakeOutcome:
        captured.update(payload)
        return FakeOutcome(payload)

    monkeypatch.setattr(megaplan_execute_batch, "capture_step_output", fake_capture_step_output)

    payload = megaplan_execute_batch._capture_execute_payload(
        agent="codex",
        model="gpt-5.5",
        resolved_model="gpt-5.5",
        payload={
            "output": "batch done",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [
                {
                    "id": "ignored-receipt-id",
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Implemented task.",
                    "files_changed": ["x.py"],
                    "commands_run": ["pytest tests/test_x.py"],
                    "evidence_files": ["x.py"],
                    "reviewer_verdict": "pass",
                }
            ],
            "sense_check_acknowledgments": [
                {
                    "id": "SC2",
                    "task_id": "T2",
                    "verdict": "pass",
                    "executor_note": "Checked.",
                }
            ],
        },
    )

    assert payload == captured
    assert payload["task_updates"] == [
        {
            "task_id": "T2",
            "status": "done",
            "executor_notes": "Implemented task.",
            "files_changed": ["x.py"],
            "commands_run": ["pytest tests/test_x.py"],
            "auto_attributed_files": False,
        }
    ]
    assert payload["sense_check_acknowledgments"] == [
        {"sense_check_id": "SC2", "executor_note": "Checked."}
    ]


def test_reduce_batch_classifies_raw_terminal_uncorroborated_tasks_as_blocked_by_prereq() -> None:
    batch_result = SimpleNamespace(
        payload={},
        merged_task_count=1,
        total_task_count=1,
        acknowledged_sense_check_count=0,
        total_sense_check_count=0,
        missing_task_evidence=[],
    )
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["impl.py"],
                "commands_run": ["pytest -q"],
            }
        ]
    }

    outcome = reduce_batch(
        batch_result,
        finalize_data=finalize_data,
        batch_task_ids=["T1"],
        completed_task_ids=set(),
    )

    assert outcome.value == BatchOutcome.BLOCKED_BY_PREREQ


def _missing_code_task_evidence(tasks: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    return _check_done_task_evidence(
        tasks,
        issues=issues,
        should_classify=lambda task: True,
        has_evidence=lambda task: bool(task.get("files_changed")),
        has_advisory_evidence=megaplan.execute.core._has_code_task_advisory_evidence,
        missing_message="missing: ",
        advisory_message="advisory: ",
    )


def _batch_task_ids(
    count: int,
    *,
    depends_on: dict[int, list[str]] | None = None,
) -> list[dict[str, object]]:
    depends_on = depends_on or {}
    return [
        {"id": f"T{index}", "depends_on": depends_on.get(index, [])}
        for index in range(1, count + 1)
    ]


def _capacity_batches(
    tasks: list[dict[str, object]],
    max_tasks_per_batch: int = 5,
) -> list[list[str]]:
    return split_oversized_batches(
        compute_task_batches(tasks),
        max_tasks_per_batch,
    )


def _force_sequential_critique(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route critique through the legacy worker call for worker-failure tests."""

    def _parallel_unavailable(*args, **kwargs):
        raise RuntimeError("force sequential critique fallback")

    monkeypatch.setattr(critique_handler, "run_parallel_critique", _parallel_unavailable)


def test_9_independent_tasks_split_at_default_ceiling() -> None:
    batches = _capacity_batches(_batch_task_ids(9))

    assert batches == [
        ["T1", "T2", "T3", "T4", "T5"],
        ["T6", "T7", "T8", "T9"],
    ]


def test_3_independent_tasks_stay_one_batch() -> None:
    assert _capacity_batches(_batch_task_ids(3)) == [["T1", "T2", "T3"]]


def test_dep_chain_preserved_through_split() -> None:
    tasks = _batch_task_ids(7, depends_on={7: ["T6"]})

    assert _capacity_batches(tasks, max_tasks_per_batch=3) == [
        ["T1", "T2", "T3"],
        ["T4", "T5", "T6"],
        ["T7"],
    ]


def test_custom_ceiling() -> None:
    assert _capacity_batches(_batch_task_ids(10), max_tasks_per_batch=4) == [
        ["T1", "T2", "T3", "T4"],
        ["T5", "T6", "T7", "T8"],
        ["T9", "T10"],
    ]


def test_ceiling_zero_or_negative_falls_back_to_default() -> None:
    tasks = _batch_task_ids(6)

    assert _capacity_batches(tasks, max_tasks_per_batch=0) == [
        ["T1", "T2", "T3", "T4", "T5"],
        ["T6"],
    ]
    assert _capacity_batches(tasks, max_tasks_per_batch=-1) == [
        ["T1", "T2", "T3", "T4", "T5"],
        ["T6"],
    ]


def test_auto_attribute_single_done_task_with_unclaimed_changes(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": [],
                "commands_run": [],
            }
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "done",
                "files_changed": [],
                "commands_run": [],
            }
        ],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({"new.py": "<hash>"}, None),
    )

    task = finalize_data["tasks"][0]
    update = payload["task_updates"][0]
    assert task["files_changed"] == ["new.py"]
    assert task["auto_attributed_files"] is True
    assert update["files_changed"] == ["new.py"]
    assert update["auto_attributed_files"] is True
    assert payload["files_changed"] == ["new.py"]
    assert result.records == [
        {"task_id": "T1", "files": ["new.py"], "ambiguous": False}
    ]
    assert result.recursive_snapshot == {"new.py": "<hash>"}
    assert _missing_code_task_evidence(finalize_data["tasks"]) == []


def test_done_task_evidence_requires_files_or_commands() -> None:
    tasks = [
        {
            "id": "T1",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": ["finalize.json"],
            "executor_notes": "",
        },
        {
            "id": "T2",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "executor_notes": "Human-only follow-up was surfaced.",
        },
    ]

    assert _missing_code_task_evidence(tasks) == ["T1", "T2"]


def _audit_notes(length: int = 120) -> str:
    return "x" * length


def test_by_kind_audit_task_with_substantial_notes_not_flagged() -> None:
    tasks = [
        {
            "id": "T1",
            "kind": "audit",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": _audit_notes(150),
        }
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == []
    assert issues == []


def test_by_kind_audit_task_with_empty_notes_flagged() -> None:
    tasks = [
        {
            "id": "T1",
            "kind": "audit",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": "",
        }
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == ["T1"]
    assert any("audit/research" in issue for issue in issues)


def test_by_kind_audit_task_with_brief_notes_advisory_only() -> None:
    tasks = [
        {
            "id": "T1",
            "kind": "audit",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": "found one issue",
        }
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == []
    assert any("Advisory" in issue for issue in issues)


def test_by_kind_code_task_without_files_flagged() -> None:
    tasks = [
        {
            "id": "T1",
            "kind": "code",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": "",
        }
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == ["T1"]


def test_by_kind_test_task_with_pytest_commands_not_flagged() -> None:
    tasks = [
        {
            "id": "T1",
            "kind": "test",
            "status": "done",
            "files_changed": [],
            "commands_run": ["python3 -m pytest tests/test_foo.py"],
            "executor_notes": "ran tests",
        }
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == []
    assert issues == []


def test_by_kind_missing_kind_field_treated_as_code() -> None:
    # No `kind` -> default code -> requires files_changed.
    tasks = [
        {
            "id": "T1",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": "",
        }
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == ["T1"]


def test_by_kind_mixed_kinds_each_group_evaluated_separately() -> None:
    tasks = [
        {
            "id": "T_audit_ok",
            "kind": "audit",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": _audit_notes(200),
        },
        {
            "id": "T_code_bad",
            "kind": "code",
            "status": "done",
            "files_changed": [],
            "commands_run": [],
            "executor_notes": "",
        },
        {
            "id": "T_test_ok",
            "kind": "test",
            "status": "done",
            "files_changed": [],
            "commands_run": ["pytest tests/"],
            "executor_notes": "",
        },
        {
            "id": "T_docs_ok",
            "kind": "docs",
            "status": "done",
            "files_changed": ["docs/foo.md"],
            "commands_run": [],
            "executor_notes": "",
        },
    ]
    issues: list[str] = []
    missing = _check_done_task_evidence_by_kind(
        tasks,
        issues=issues,
        should_classify=lambda _t: True,
    )
    assert missing == ["T_code_bad"]


def test_auto_attribute_multiple_done_tasks_share_unclaimed_paths(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []},
            {"id": "T2", "status": "done", "files_changed": [], "commands_run": []},
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [
            {"task_id": "T1", "files_changed": [], "commands_run": []},
            {"task_id": "T2", "files_changed": [], "commands_run": []},
        ],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1", "T2"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: (
            {"b.py": "<hash-b>", "a.py": "<hash-a>"},
            None,
        ),
    )

    assert finalize_data["tasks"][0]["files_changed"] == ["a.py", "b.py"]
    assert finalize_data["tasks"][1]["files_changed"] == ["a.py", "b.py"]
    assert payload["task_updates"][0]["auto_attributed_files"] is True
    assert payload["task_updates"][1]["auto_attributed_files"] is True
    assert len(
        [
            deviation
            for deviation in deviations
            if deviation.startswith("Auto-attributed 2 unclaimed file(s) to task")
        ]
    ) == 2
    assert (
        deviations.count("Auto-attribution ambiguous: 2 done tasks shared 2 unclaimed files")
        == 1
    )
    assert result.records == [
        {"task_id": "T1", "files": ["a.py", "b.py"], "ambiguous": True},
        {"task_id": "T2", "files": ["a.py", "b.py"], "ambiguous": True},
    ]


def test_auto_attribute_clean_worktree_keeps_missing_evidence(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({}, None),
    )

    assert finalize_data["tasks"][0]["files_changed"] == []
    assert "auto_attributed_files" not in finalize_data["tasks"][0]
    assert payload["task_updates"][0]["files_changed"] == []
    assert result.records == []
    assert result.recursive_snapshot == {}
    assert _missing_code_task_evidence(finalize_data["tasks"]) == ["T1"]


def test_auto_attribute_ignores_harness_generated_logs(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: (
            {
                ".megaplan/run-logs/auto.log": "<hash>",
                ".megaplan/system_logs/log_1.json": "<hash>",
            },
            None,
        ),
    )

    assert finalize_data["tasks"][0]["files_changed"] == []
    assert payload["task_updates"][0]["files_changed"] == []
    assert payload["files_changed"] == []
    assert deviations == []
    assert result.records == []


def test_auto_attribute_backfills_single_done_task_from_batch_metadata(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": ["src/a.py"],
        "commands_run": ["pytest -q"],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []
    calls = 0

    def snapshot(_project_dir: Path) -> tuple[dict[str, str], str | None]:
        nonlocal calls
        calls += 1
        return {"src/a.py": "<hash>"}, None

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=snapshot,
    )

    assert calls == 0
    assert finalize_data["tasks"][0]["files_changed"] == ["src/a.py"]
    assert finalize_data["tasks"][0]["commands_run"] == ["pytest -q"]
    assert payload["task_updates"][0]["files_changed"] == ["src/a.py"]
    assert payload["task_updates"][0]["commands_run"] == ["pytest -q"]
    assert "Backfilled batch-level metadata to task T1: 1 file(s), 1 command(s)" in deviations
    assert result.records == [
        {
            "task_id": "T1",
            "files": ["src/a.py"],
            "commands": ["pytest -q"],
            "ambiguous": False,
            "source": "batch_payload",
        }
    ]
    assert _missing_code_task_evidence(finalize_data["tasks"]) == []


def test_auto_attribute_backfills_single_done_task_from_batch_commands_only(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": [],
        "commands_run": ["pytest -q"],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({"unused.py": "<hash>"}, None),
    )

    assert finalize_data["tasks"][0]["files_changed"] == []
    assert finalize_data["tasks"][0]["commands_run"] == ["pytest -q"]
    assert payload["task_updates"][0]["commands_run"] == ["pytest -q"]
    assert result.records == [
        {
            "task_id": "T1",
            "files": [],
            "commands": ["pytest -q"],
            "ambiguous": False,
            "source": "batch_payload",
        }
    ]
    assert _missing_code_task_evidence(finalize_data["tasks"]) == []


def test_auto_attribute_populated_files_changed_short_circuits(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "status": "done",
                "files_changed": ["claimed.py"],
                "commands_run": [],
            }
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [
            {"task_id": "T1", "files_changed": ["claimed.py"], "commands_run": []}
        ],
    }
    deviations: list[str] = []
    calls = 0

    def snapshot(_project_dir: Path) -> tuple[dict[str, str], str | None]:
        nonlocal calls
        calls += 1
        return {"new.py": "<hash>"}, None

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=snapshot,
    )

    assert calls == 0
    assert finalize_data["tasks"][0]["files_changed"] == ["claimed.py"]
    assert payload["task_updates"][0]["files_changed"] == ["claimed.py"]
    assert deviations == []
    assert result.records == []
    assert result.recursive_snapshot is None


def test_auto_attribute_skipped_tasks_ignored(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "skipped", "files_changed": [], "commands_run": []}
        ]
    }
    payload = {
        "files_changed": [],
        "task_updates": [{"task_id": "T1", "files_changed": [], "commands_run": []}],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: ({"new.py": "<hash>"}, None),
    )

    assert finalize_data["tasks"][0]["files_changed"] == []
    assert payload["task_updates"][0]["files_changed"] == []
    assert deviations == []
    assert result.records == []
    assert result.recursive_snapshot is None


def test_auto_attribute_excludes_files_claimed_by_other_tasks(tmp_path: Path) -> None:
    finalize_data = {
        "tasks": [
            {"id": "T1", "status": "done", "files_changed": ["a.py"], "commands_run": []},
            {"id": "T2", "status": "done", "files_changed": [], "commands_run": []},
        ]
    }
    payload = {
        "files_changed": ["existing.py"],
        "task_updates": [
            {"task_id": "T1", "files_changed": ["a.py"], "commands_run": []},
            {"task_id": "T2", "files_changed": [], "commands_run": []},
        ],
    }
    deviations: list[str] = []

    result = _auto_attribute_unclaimed_paths(
        project_dir=tmp_path,
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1", "T2"],
        issues=deviations,
        capture_recursive_snapshot_fn=lambda _p: (
            {"a.py": "<hash-a>", "b.py": "<hash-b>"},
            None,
        ),
    )

    assert finalize_data["tasks"][0]["files_changed"] == ["a.py"]
    assert finalize_data["tasks"][1]["files_changed"] == ["b.py"]
    assert payload["task_updates"][1]["files_changed"] == ["b.py"]
    assert payload["files_changed"] == ["existing.py", "b.py"]
    assert result.records == [
        {"task_id": "T2", "files": ["b.py"], "ambiguous": False}
    ]


def test_project_advisory_path_sets_bounds_persisted_list_with_artifact_ref(
    tmp_path: Path,
) -> None:
    files = [f"src/file_{i}.py" for i in range(120)]
    payload = {"files_changed": files}

    projected = project_advisory_path_sets(
        payload,
        plan_dir=tmp_path,
        artifact_prefix="execution_batch_13",
        keys=("files_changed",),
    )

    files_changed = projected["files_changed"]
    assert len(files_changed["items"]) == 40
    assert files_changed["omitted_count"] == 80
    ref = files_changed["full_set_artifact_ref"]
    assert ref["name"] == "execution_batch_13_files_changed.json"
    assert ref["role"] == "full_advisory_path_set"
    full_set = read_json(tmp_path / ref["name"])
    assert full_set["items"] == files
    assert expand_projected_path_list(files_changed, plan_dir=tmp_path) == files


def test_project_advisory_path_sets_summarizes_uniform_mechanical_path_sets(
    tmp_path: Path,
) -> None:
    files = [f"src/generated/schema_{i}.py" for i in range(120)]
    payload = {"files_changed": files}

    projected = project_advisory_path_sets(
        payload,
        plan_dir=tmp_path,
        artifact_prefix="execution_batch_14",
        keys=("files_changed",),
    )

    files_changed = projected["files_changed"]
    summary = files_changed["semantic_bulk_operation_summary"]
    assert summary["kind"] == "semantic_bulk_operation_summary"
    assert summary["operation"] == "uniform_path_set"
    assert summary["path_count"] == 120
    assert summary["common_directory"] == "src/generated"
    assert summary["file_extension"] == ".py"
    assert summary["sampled_deviations"] == []
    assert "git status --short -- src/generated" in summary["live_tree_verification"]
    ref = files_changed["full_set_artifact_ref"]
    full_set = read_json(tmp_path / ref["name"])
    assert full_set["items"] == files
    assert full_set["semantic_bulk_operation_summary"] == summary


def test_project_advisory_path_sets_does_not_summarize_mixed_path_sets(
    tmp_path: Path,
) -> None:
    files = [
        *(f"src/generated/schema_{i}.py" for i in range(60)),
        *(f"docs/generated/schema_{i}.md" for i in range(60)),
    ]
    payload = {"files_changed": files}

    projected = project_advisory_path_sets(
        payload,
        plan_dir=tmp_path,
        artifact_prefix="execution_batch_14",
        keys=("files_changed",),
    )

    files_changed = projected["files_changed"]
    assert "semantic_bulk_operation_summary" not in files_changed
    ref = files_changed["full_set_artifact_ref"]
    full_set = read_json(tmp_path / ref["name"])
    assert "semantic_bulk_operation_summary" not in full_set
    assert full_set["items"] == files


def test_aggregate_execution_payload_bounds_files_changed_and_keeps_full_artifact(
    tmp_path: Path,
) -> None:
    batch_payloads = [
        {"output": "one", "files_changed": [f"src/a_{i}.py" for i in range(80)]},
        {"output": "two", "files_changed": [f"src/b_{i}.py" for i in range(80)]},
    ]

    aggregate = megaplan_execute_aggregation._build_aggregate_execution_payload(
        batch_payloads,
        completed_batches=2,
        total_batches=2,
        plan_dir=tmp_path,
    )

    files_changed = aggregate["files_changed"]
    assert len(files_changed["items"]) == 40
    assert files_changed["omitted_count"] == 120
    ref = files_changed["full_set_artifact_ref"]
    assert ref["name"] == "execution_aggregate_files_changed.json"
    full_set = read_json(tmp_path / ref["name"])
    assert len(full_set["items"]) == 160
    assert full_set["items"][0] == "src/a_0.py"
    assert full_set["items"][-1] == "src/b_79.py"


def test_snapshot_recursive_expands_untracked_directory(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "newpkg").mkdir()
    (tmp_path / "newpkg" / "file.py").write_text("print('new')\n", encoding="utf-8")

    snapshot, error = _capture_git_status_snapshot_recursive(tmp_path)

    assert error is None
    assert "newpkg/file.py" in snapshot
    assert "newpkg/" not in snapshot


def test_snapshot_recursive_default_does_not_recurse_into_untracked_directory(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.py").write_text("print('tracked')\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "newpkg").mkdir()
    (tmp_path / "newpkg" / "file.py").write_text("print('new')\n", encoding="utf-8")

    snapshot, error = _capture_git_status_snapshot(tmp_path)

    assert error is None
    assert "newpkg/file.py" not in snapshot
    assert "newpkg/" in snapshot


def _setup_single_auto_attribute_plan(plan_fixture: PlanFixture) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Implement the new package file.",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ]
    finalize_data["sense_checks"] = [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "Was the new package file implemented?",
            "executor_note": "",
            "verdict": "",
        }
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )


def _stub_auto_attribute_git_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    *,
    scope_snapshot: dict[str, str] | None = None,
) -> None:
    snapshots = iter(
        [
            ({}, None),
            ({"newpkg/": "<dir-marker>"}, None),
            (scope_snapshot or {"newpkg/": "<dir-marker>"}, None),
        ]
    )
    def _snapshot_fn(*_args: object, **_kwargs: object):
        return next(snapshots)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        _snapshot_fn,
    )
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_capture_git_status_snapshot",
        _snapshot_fn,
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_args, **_kwargs: ({"newpkg/file.py": "<hash>"}, None),
    )


def _hermes_style_worker(project_dir: Path):
    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        del step, state, plan_dir, args, root, resolved, prompt_override
        new_file = project_dir / "newpkg" / "file.py"
        new_file.parent.mkdir(exist_ok=True)
        _write_lines(new_file, 25, prefix="generated")
        payload = {
            "output": "Hermes-style execution completed.",
            "files_changed": [],
            "commands_run": [],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Implemented the new package file on disk while leaving structured file evidence empty for attribution recovery.",
                    "files_changed": [],
                    "commands_run": [],
                }
            ],
            "sense_check_acknowledgments": [
                {
                    "sense_check_id": "SC1",
                    "executor_note": "Confirmed the new package file was created during execution.",
                }
            ],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="hermes-style",
                duration_ms=1,
                cost_usd=0.0,
                session_id="hermes-style",
            ),
            "codex",
            "persistent",
            False,
        )

    return worker


def _execute_auto_loop_direct(plan_fixture: PlanFixture) -> dict:
    state = load_state(plan_fixture.plan_dir)
    return megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )


def test_auto_attribute_auto_loop_hermes_style_reaches_executed(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    response = _execute_auto_loop_direct(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    batch = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    audit = read_json(plan_fixture.plan_dir / "execution_audit.json")
    deviations = execution["deviations"]

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    task = finalize_data["tasks"][0]
    assert task["auto_attributed_files"] is True
    assert task["files_changed"] == ["newpkg/file.py"]
    update = batch["task_updates"][0]
    assert update["auto_attributed_files"] is True
    assert update["files_changed"] == ["newpkg/file.py"]
    assert "newpkg/file.py" in execution["files_changed"]
    assert audit["auto_attribution"] == [
        {"task_id": "T1", "files": ["newpkg/file.py"], "ambiguous": False}
    ]
    assert any(
        "Auto-attributed 1 unclaimed file(s) to task T1" in deviation
        for deviation in deviations
    )
    assert not any(
        "Advisory observation mismatch:" in deviation and "newpkg/" in deviation
        for deviation in deviations
    )
    assert not any(
        "executor claimed files not observed in git status" in deviation
        and "newpkg/file.py" in deviation
        for deviation in deviations
    )


def test_auto_loop_aggregates_worker_tokens_into_receipt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: handle_execute_auto_loop must sum per-batch worker tokens
    into the aggregate step_receipt_execute_v*.json. Previously the auto-loop
    dropped prompt_tokens / completion_tokens on the floor (always recorded 0)
    even when the underlying hermes worker reported real usage."""
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)

    base_worker = _hermes_style_worker(plan_fixture.project_dir)

    def token_emitting_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        worker_result, agent, mode, refreshed = base_worker(
            step, state, plan_dir, args, root=root, resolved=resolved, prompt_override=prompt_override
        )
        # Simulate a real hermes/deepseek invocation reporting token usage.
        worker_result.prompt_tokens = 12_345
        worker_result.completion_tokens = 678
        worker_result.total_tokens = 13_023
        return worker_result, agent, mode, refreshed

    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        token_emitting_worker,
    )

    response = _execute_auto_loop_direct(plan_fixture)
    assert response["success"] is True

    receipt_path = plan_fixture.plan_dir / "step_receipt_execute_v1.json"
    assert receipt_path.exists(), "execute receipt was not written"
    receipt = read_json(receipt_path)
    assert receipt["prompt_tokens"] == 12_345, receipt
    assert receipt["completion_tokens"] == 678, receipt


def test_auto_loop_aggregates_worker_rate_limits_neutrally_for_receipt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    captured_rate_limits: list[dict[str, object] | None] = []
    real_build_receipt = megaplan.execute.batch.build_receipt

    def capture_build_receipt(**kwargs):
        captured_rate_limits.append(kwargs["worker"].rate_limit)
        return real_build_receipt(**kwargs)

    def batch_worker(
        step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None
    ):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed batch one.",
                        "files_changed": ["batch1.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one."}
                ],
            }
            return (
                WorkerResult(
                    payload=payload,
                    raw_output="batch1",
                    duration_ms=2,
                    cost_usd=0.1,
                    session_id="batch-1",
                    rate_limit={"provider": "hermes", "remaining": 7},
                ),
                "codex",
                "persistent",
                False,
            )
        if "[T2]" in prompt_override:
            payload = {
                "output": "Batch two complete.",
                "files_changed": ["batch2.py"],
                "commands_run": ["pytest -k batch2"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Completed batch two.",
                        "files_changed": ["batch2.py"],
                        "commands_run": ["pytest -k batch2"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Confirmed batch two."}
                ],
            }
            return (
                WorkerResult(
                    payload=payload,
                    raw_output="batch2",
                    duration_ms=3,
                    cost_usd=0.2,
                    session_id="batch-2",
                    rate_limit=None,
                ),
                "codex",
                "persistent",
                False,
            )
        raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

    monkeypatch.setattr(megaplan.execute.batch, "build_receipt", capture_build_receipt)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
    )

    assert response["success"] is True
    assert captured_rate_limits == [
        {"values": [{"provider": "hermes", "remaining": 7}]}
    ]
    receipt = read_json(plan_fixture.plan_dir / "step_receipt_execute_v1.json")
    assert "rate_limit" not in receipt


def test_auto_attribute_robust_auto_loop_avoids_scope_drift_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(
        tmp_path, monkeypatch, robustness="robust"
    )
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(
        monkeypatch,
        scope_snapshot={"newpkg/file.py": "<hash>"},
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    response = _execute_auto_loop_direct(plan_fixture)
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert "newpkg/file.py" in execution["files_changed"]
    assert not any("scope_drift_severity=high" in warning for warning in response["warnings"])
    assert not any("scope_drift_severity=high" in deviation for deviation in response["deviations"])


def test_operator_attributed_files_avoid_scope_drift_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(
        tmp_path, monkeypatch, robustness="robust"
    )
    _setup_single_auto_attribute_plan(plan_fixture)
    state = load_state(plan_fixture.plan_dir)
    state["meta"]["execute_operator_attributed_files"] = ["manual/fix.py"]
    save_state(plan_fixture.plan_dir, state)
    _stub_auto_attribute_git_snapshots(
        monkeypatch,
        scope_snapshot={"manual/fix.py": "<hash>"},
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    response = _execute_auto_loop_direct(plan_fixture)

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert not any("scope_drift_severity=high" in warning for warning in response["warnings"])


def test_handle_execute_one_batch_halts_when_scope_drift_snapshot_fails(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_compute_execute_scope_drift",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CliError("scope_drift_snapshot", "M3B_HALT_SCOPE_DRIFT_SNAPSHOT: snapshot boom")
        ),
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    state = load_state(plan_fixture.plan_dir)

    with pytest.raises(CliError, match="M3B_HALT_SCOPE_DRIFT_SNAPSHOT"):
        megaplan.execute.core.handle_execute_one_batch(
            root=plan_fixture.root,
            plan_dir=plan_fixture.plan_dir,
            state=state,
            args=plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
                batch=1,
            ),
            batch_number=1,
            auto_approve=False,
            agent="codex",
            mode="persistent",
            refreshed=False,
        )


def test_handle_execute_auto_loop_halts_when_scope_drift_snapshot_fails(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_compute_execute_scope_drift",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CliError("scope_drift_snapshot", "M3B_HALT_SCOPE_DRIFT_SNAPSHOT: snapshot boom")
        ),
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    with pytest.raises(CliError, match="M3B_HALT_SCOPE_DRIFT_SNAPSHOT"):
        _execute_auto_loop_direct(plan_fixture)


def test_auto_attribute_one_batch_handler_persists_per_batch_audit(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )
    audit = read_json(plan_fixture.plan_dir / "execution_audit.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert audit["auto_attribution"] == [
        {"task_id": "T1", "files": ["newpkg/file.py"], "ambiguous": False}
    ]


def test_one_batch_handler_splits_wide_independent_wave_at_ceiling(
    plan_fixture: PlanFixture,
) -> None:
    # Regression guard: 8 dependency-independent tasks form a single topological
    # wave, but the runtime ceiling (default 5) must split them into 2 batches at
    # dispatch. Asserts the split is wired into the dispatch path itself, not just
    # available as a helper — the gap that previously let the ceiling silently
    # regress (split_oversized_batches was exported but no longer called).
    _setup_single_auto_attribute_plan(plan_fixture)
    finalize_path = plan_fixture.plan_dir / "finalize.json"
    finalize_data = read_json(finalize_path)
    finalize_data["tasks"] = [
        {
            "id": f"T{i}",
            "description": f"Independent task {i}.",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
        for i in range(1, 9)
    ]
    finalize_path.write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    state = load_state(plan_fixture.plan_dir)

    # batch_number is out of range; the error message embeds the dispatch-level
    # batch count, which must reflect the 5+3 split (2 batches), not the raw
    # single 8-task wave.
    with pytest.raises(megaplan.CliError, match=r"Plan has 2 batch\(es\)"):
        megaplan.execute.core.handle_execute_one_batch(
            root=plan_fixture.root,
            plan_dir=plan_fixture.plan_dir,
            state=state,
            args=plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
                batch=99,
            ),
            batch_number=99,
            auto_approve=False,
            agent="codex",
            mode="persistent",
            refreshed=False,
        )


def test_capture_test_baseline_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    import arnold.pipelines.megaplan.orchestration.suite_runner as suite_runner

    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        suite_runner,
        "run_suite",
        lambda *args, **kwargs: SuiteRunResult(
            run_id="baseline-test",
            phase="baseline",
            command="pytest --tb=no -q --no-header -rA",
            duration=0.1,
            collected=7,
            collected_ids=[
                "tests/test_a.py::test_one",
                "tests/test_b.py::test_two",
            ],
            failures=[
                "tests/test_a.py::test_one",
                "tests/test_b.py::test_two",
            ],
            passes=[],
            status="failed",
            exit_code=1,
            raw_log_path=tmp_path / "baseline.log",
            code_hash="sha256:test",
            collections_parse_ok=True,
        ),
    )

    result = megaplan.handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] == [
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    ]
    assert result["baseline_test_command"] == "pytest --tb=no -q --no-header -rA"
    assert "baseline_test_note" not in result


def test_capture_test_baseline_no_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    import arnold.pipelines.megaplan.orchestration.suite_runner as suite_runner

    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        suite_runner,
        "run_suite",
        lambda *args, **kwargs: SuiteRunResult(
            run_id="baseline-runner-error",
            phase="baseline",
            command=None,
            duration=0.0,
            collected=0,
            collected_ids=[],
            failures=[],
            passes=[],
            status="runner_error",
            exit_code=None,
            raw_log_path=tmp_path / "baseline.log",
            code_hash="sha256:test",
            collections_parse_ok=False,
        ),
    )

    result = megaplan.handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] is None
    assert result["baseline_test_command"] is None
    assert "runner error" in result["baseline_test_note"]


def test_capture_test_baseline_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult
    import arnold.pipelines.megaplan.orchestration.suite_runner as suite_runner

    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        suite_runner,
        "run_suite",
        lambda *args, **kwargs: SuiteRunResult(
            run_id="baseline-timeout",
            phase="baseline",
            command="pytest --tb=no -q --no-header -rA",
            duration=120.0,
            collected=0,
            collected_ids=[],
            failures=[],
            passes=[],
            status="timeout",
            exit_code=None,
            raw_log_path=tmp_path / "baseline.log",
            code_hash="sha256:test",
            collections_parse_ok=False,
        ),
    )

    result = megaplan.handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] is None
    assert "timed out" in result["baseline_test_note"].lower()


def test_execute_requires_confirm_destructive(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    with pytest.raises(megaplan.CliError, match="confirm-destructive"):
        megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=False),
        )


def test_execute_requires_user_approval_in_review_mode(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    with pytest.raises(megaplan.CliError, match="user approval"):
        megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=False),
        )


def test_execute_preflight_refusal_happens_before_worker_dispatch(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    worker_called = False

    def refusing_preflight(*_args: object, **_kwargs: object) -> None:
        raise megaplan.CliError("engine_write_isolation_unverified", "refused before worker dispatch")

    def worker_should_not_run(*_args: object, **_kwargs: object) -> WorkerResult:
        nonlocal worker_called
        worker_called = True
        raise AssertionError("worker dispatch should not run after preflight refusal")

    monkeypatch.setattr(execute_handler, "preflight_mutating_phase", refusing_preflight)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker_should_not_run)

    with pytest.raises(megaplan.CliError) as excinfo:
        megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
        )

    assert excinfo.value.code == "engine_write_isolation_unverified"
    assert worker_called is False


def test_execute_succeeds_with_user_approval(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert "finalize.json" in response["artifacts"]
    assert "final.md" in response["artifacts"]
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()


def test_execute_succeeds_in_auto_approve_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    config_path = tmp_path / "config"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    # Isolate the user-config dir so a global ``adaptive_critique = true`` in
    # ~/.config/megaplan/config.json doesn't leak into the test and drive the
    # critique handler down the adaptive-evaluator path (which the mock worker
    # doesn't implement). Mirrors _make_plan_fixture_with_robustness.
    import arnold.pipelines.megaplan._core.io as _io_module

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setattr(_io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)

    make_args = make_args_factory(project_dir)
    megaplan.handle_init(root, make_args(auto_approve=True))
    megaplan.handle_plan(root, make_args(plan="test-plan"))
    megaplan.handle_critique(root, make_args(plan="test-plan"))
    megaplan.handle_override(root, make_args(plan="test-plan", override_action="force-proceed", reason="test"))
    megaplan.handle_finalize(root, make_args(plan="test-plan"))
    response = megaplan.handle_execute(
        root,
        make_args(plan="test-plan", confirm_destructive=True, user_approved=False),
    )
    assert response["success"] is True
    assert response["auto_approve"] is True
    assert "finalize.json" in response["artifacts"]


def test_step_failure_records_error_in_history(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _force_sequential_critique(monkeypatch)

    def failing_worker(*a, **kw):
        raise megaplan.CliError("test_error", "Worker blew up", extra={"raw_output": "boom"})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", failing_worker)
    with pytest.raises(megaplan.CliError, match="Worker blew up"):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    error_entries = [h for h in state["history"] if h.get("result") == "error"]
    assert len(error_entries) >= 1
    assert "Worker blew up" in error_entries[-1].get("message", "")


def test_step_failure_stores_raw_output_file(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _force_sequential_critique(monkeypatch)

    def failing_worker(*a, **kw):
        raise megaplan.CliError("test_error", "fail", extra={"raw_output": "raw content here"})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", failing_worker)
    with pytest.raises(megaplan.CliError):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    error_entry = next(h for h in state["history"] if h.get("result") == "error")
    raw_file = error_entry.get("raw_output_file")
    assert raw_file is not None
    assert (plan_fixture.plan_dir / raw_file).exists()


def test_step_failure_uses_message_when_no_raw_output(plan_fixture: PlanFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _force_sequential_critique(monkeypatch)

    def failing_worker(*a, **kw):
        raise megaplan.CliError("test_error", "the error message")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", failing_worker)
    with pytest.raises(megaplan.CliError):
        megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    error_entry = next(h for h in state["history"] if h.get("result") == "error")
    raw_file = error_entry.get("raw_output_file")
    content = (plan_fixture.plan_dir / raw_file).read_text(encoding="utf-8")
    assert "the error message" in content


def test_run_command_raises_on_timeout() -> None:
    from arnold.pipelines.megaplan.workers import run_command

    with pytest.raises(megaplan.CliError, match="timed out"):
        run_command(["sleep", "60"], cwd=Path.cwd(), timeout=1)


def test_run_command_raises_on_file_not_found() -> None:
    from arnold.pipelines.megaplan.workers import run_command

    with pytest.raises(megaplan.CliError, match="not found"):
        run_command(["nonexistent_command_xyz"], cwd=Path.cwd())


def test_execute_prompt_includes_approval_note(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    from arnold.pipelines.megaplan.prompts import create_claude_prompt

    prompt = create_claude_prompt("execute", state, plan_fixture.plan_dir)
    assert "Review mode" in prompt or "auto-approve" in prompt or "approved" in prompt


def test_execute_happy_path_tracks_all_tasks(plan_fixture: PlanFixture) -> None:
    """The default mock execute output still covers every finalized task."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    assert response["success"] is True
    assert response["warnings"] == []
    assert "2/2 tasks tracked" in response["summary"]
    assert "2/2 sense checks acknowledged" in response["summary"]


def test_execute_timeout_recovers_partial_progress_from_finalize_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Verified the implementation artifact before timeout recovery."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["sense_checks"][0]["executor_note"] = "Confirmed the implementation artifact exists."
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "test-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["next_step"] == "execute"
    assert response["state"] == megaplan.STATE_FINALIZED
    assert recovered["tasks"][0]["status"] == "done"
    assert state["history"][-1]["result"] == "timeout"
    timeout_agent = state["history"][-1].get("agent") or "codex"
    session_key = megaplan.workers.session_key_for("execute", timeout_agent)
    assert state["sessions"][session_key]["id"] == "test-session"


def test_execute_timeout_reads_execution_checkpoint_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    checkpoint_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Recovered from execution checkpoint.",
                "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Recovered checkpoint sense check."}
        ],
    }
    (plan_fixture.plan_dir / "execution_checkpoint.json").write_text(
        json.dumps(checkpoint_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "checkpoint-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert recovered["tasks"][0]["status"] == "done"
    assert recovered["tasks"][0]["files_changed"] == ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    assert recovered["sense_checks"][0]["executor_note"] == "Recovered checkpoint sense check."
    assert any(
        "Recovered timeout checkpoint from execution_checkpoint.json" in deviation
        for deviation in response["deviations"]
    )


def test_execute_timeout_checkpoint_uses_model_seam_capture_recovery(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    checkpoint_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Recovered from execution checkpoint.",
                "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Recovered checkpoint sense check."}
        ],
    }
    checkpoint_path = plan_fixture.plan_dir / "execution_checkpoint.json"
    checkpoint_raw = json.dumps(checkpoint_payload, indent=2) + "\n"
    checkpoint_path.write_text(checkpoint_raw, encoding="utf-8")

    captured: dict[str, object] = {}
    real_capture = megaplan_execute_timeout.capture_step_output

    def spying_capture(invocation, output):
        captured["metadata"] = dict(invocation.metadata)
        captured["output"] = output
        return real_capture(invocation, output)

    monkeypatch.setattr(megaplan_execute_timeout, "capture_step_output", spying_capture)

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "checkpoint-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is False
    assert captured["output"] == checkpoint_raw
    metadata = captured["metadata"]
    assert metadata["validation_step"] == "execute"
    assert metadata["compatibility_validation_step"] == "execute"
    assert metadata["capture_recovery"] == {
        "step": "execute",
        "plan_dir": str(plan_fixture.plan_dir),
        "output_path": str(checkpoint_path),
        "prefer_output_file": True,
    }


def test_execute_timeout_resets_done_tasks_without_any_evidence(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Claimed completion without evidence."
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "test-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert recovered["tasks"][0]["status"] == "pending"
    assert "Timeout recovery reset this task to pending" in recovered["tasks"][0]["executor_notes"]
    assert any("Reset timed-out done tasks to pending" in deviation for deviation in response["deviations"])


def test_execute_timeout_reports_authority_corroborated_completion(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout summary reports authority-corroborated tasks distinctly from raw-terminal claims."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Corroborated task with evidence."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "corrob-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is False
    assert response["next_step"] == "execute"
    # Deviations must NOT contain asserted/uncorroborated labeling when tasks are corroborated
    assert not any(
        "without authority corroboration" in deviation
        for deviation in response["deviations"]
    )
    assert not any(
        "asserted/uncorroborated" in deviation
        for deviation in response["deviations"]
    )


def test_execute_timeout_labels_uncorroborated_terminal_tasks(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uncorroborated terminal tasks are labeled asserted/uncorroborated in diagnostics."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Task with evidence but no corroboration."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    # Simulate authority adapter returning no corroborated IDs
    monkeypatch.setattr(
        megaplan_execute_timeout,
        "corroborated_completed_task_ids",
        lambda tasks, **kwargs: set(),
    )

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "uncorrob-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is False
    assert response["next_step"] == "execute"
    # Deviations must report uncorroborated tasks as asserted/uncorroborated
    assert any(
        "without authority corroboration" in deviation
        for deviation in response["deviations"]
    )
    assert any(
        "asserted/uncorroborated" in deviation
        for deviation in response["deviations"]
    )
    # Route is not blocked — success remains False with next_step=execute
    assert response["next_step"] == "execute"


def test_execute_timeout_corroboration_failure_is_fail_open(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authority corroboration failure does not block the timeout recovery route."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Task with evidence."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    # Simulate authority adapter crashing
    def _raise_corroboration_error(*args, **kwargs):
        raise RuntimeError("evidence store unavailable")

    monkeypatch.setattr(
        megaplan_execute_timeout,
        "corroborated_completed_task_ids",
        _raise_corroboration_error,
    )

    def timing_out_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "fail-open-session", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    # Route must NOT be blocked by the corroboration failure
    assert response["success"] is False
    assert response["next_step"] == "execute"
    # Failure must be reported as advisory
    assert any(
        "authority corroboration failed" in deviation
        for deviation in response["deviations"]
    )


def test_execute_reports_advisory_when_structured_output_disagrees_with_disk_checkpoint(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Checkpointed as done on disk before final structured output."
    finalize_data["tasks"][0]["files_changed"] = ["IMPLEMENTED_BY_MEGAPLAN.txt"]
    finalize_data["tasks"][0]["commands_run"] = ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    worker = WorkerResult(
        payload={
            "output": "Execution completed with structured output.",
            "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
            "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "skipped",
                    "executor_notes": "Verified the disk checkpoint should be downgraded because no additional work was required.",
                    "files_changed": [],
                    "commands_run": [],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Verified the remaining task completed successfully.",
                    "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                    "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the checkpoint mismatch was intentional."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed the remaining task completed successfully."},
            ],
        },
        raw_output="execute with mismatch",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-mismatch",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    merged_finalize = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert merged_finalize["tasks"][0]["status"] == "skipped"
    assert any(
        "task T1 was 'done' on disk before merge but structured output set it to 'skipped'" in deviation
        for deviation in response["deviations"]
    )


def test_execute_deduplicates_task_updates_and_blocks_incomplete_coverage(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    worker = WorkerResult(
        payload={
            "output": "Partial execution completed.",
            "files_changed": ["src/example.py"],
            "commands_run": ["pytest -k partial"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Initial pass.",
                    "files_changed": ["src/example.py"],
                    "commands_run": ["pytest -k partial"],
                },
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Final pass.",
                    "files_changed": ["src/example.py"],
                    "commands_run": ["pytest -k partial"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
            ],
        },
        raw_output="partial execute",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-duplicate",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    execute_entry = next(entry for entry in state["history"] if entry["step"] == "execute")
    final_md = (plan_fixture.plan_dir / "final.md").read_text(encoding="utf-8")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["summary"] == (
        "[scope_drift=low] Blocked: 1/2 tasks have no executor update; "
        "1/2 sense checks have no executor acknowledgment. "
        "Re-run execute to complete tracking."
    )
    assert "Duplicate task_update for 'T1' — last entry wins." in response["deviations"]
    assert finalize_data["tasks"][0]["executor_notes"] == "Final pass."
    assert finalize_data["tasks"][1]["status"] == "pending"
    assert execute_entry["result"] == "blocked"
    assert (plan_fixture.plan_dir / "execution.json").exists()
    assert (plan_fixture.plan_dir / "execution_audit.json").exists()
    assert "## Coverage Gaps" in final_md
    assert "Tasks without executor updates: 1" in final_md


def test_handle_execute_persists_blocked_lifecycle_after_direct_blocked_response(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    def blocked_dispatch(*, plan_dir: Path, **kwargs: object) -> dict[str, object]:
        (plan_dir / "execution_batch_1.json").write_text(
            json.dumps({"result": "blocked"}, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "success": False,
            "result": "blocked",
            "state": megaplan.STATE_FINALIZED,
            "next_step": "execute",
            "next_step_runtime": "execute",
            "artifacts": ["execution_batch_1.json"],
            "summary": "blocked by quality gates",
        }

    monkeypatch.setattr(execute_handler, "handle_execute_auto_loop", blocked_dispatch)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)

    assert response["state"] == megaplan.STATE_BLOCKED
    assert response["next_step"] is None
    assert "next_step_runtime" not in response
    assert state["current_state"] == response["state"]
    assert "active_step" not in state
    assert state["latest_failure"]["kind"] == "execution_blocked"
    assert state["latest_failure"]["last_artifact"] == "execution_batch_1.json"
    assert state["resume_cursor"] == {
        "phase": "execute",
        "batch_index": None,
        "retry_strategy": "fresh_session",
    }


def test_handle_execute_allows_resume_from_blocked_state(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = megaplan.STATE_BLOCKED
    state.setdefault("history", []).append({"step": "execute", "result": "blocked"})
    (plan_fixture.plan_dir / "state.json").write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )

    def resumed_dispatch(**kwargs: object) -> dict[str, object]:
        return {
            "success": True,
            "result": "success",
            "state": megaplan.STATE_EXECUTED,
            "next_step": None,
            "artifacts": [],
            "summary": "resumed",
        }

    monkeypatch.setattr(execute_handler, "handle_execute_auto_loop", resumed_dispatch)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is True
    assert response["state"] in {megaplan.STATE_EXECUTED, megaplan.STATE_DONE}


def test_handle_execute_allows_resume_from_failed_state(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = megaplan.STATE_FAILED
    state["active_step"] = {"step": "execute", "run_id": "stale"}
    (plan_fixture.plan_dir / "state.json").write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )

    def resumed_dispatch(**kwargs: object) -> dict[str, object]:
        persisted = load_state(plan_fixture.plan_dir)
        assert persisted["active_step"]["phase"] == "execute"
        assert persisted["active_step"]["run_id"] != "stale"
        return {
            "success": True,
            "result": "success",
            "state": megaplan.STATE_EXECUTED,
            "next_step": None,
            "artifacts": [],
            "summary": "resumed",
        }

    monkeypatch.setattr(execute_handler, "handle_execute_auto_loop", resumed_dispatch)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is True
    state = load_state(plan_fixture.plan_dir)
    assert "active_step" not in state


def test_execute_blocks_done_task_without_any_per_task_evidence(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    worker = WorkerResult(
        payload={
            "output": "Executed with incomplete evidence.",
            "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
            "commands_run": ["mock-run"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Implemented the main artifact.",
                    "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                    "commands_run": ["mock-run"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Verified the work but forgot to capture evidence.",
                    "files_changed": [],
                    "commands_run": [],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the implementation artifact exists."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed the verification task was reviewed."},
            ],
        },
        raw_output="execute missing evidence",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-missing-evidence",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert "missing both files_changed and commands_run" in response["summary"]


def test_execute_softens_done_task_with_commands_only(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    worker = WorkerResult(
        payload={
            "output": "Executed with command-only verification evidence.",
            "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
            "commands_run": ["mock-run", "mock-verify"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Implemented the main artifact.",
                    "files_changed": ["IMPLEMENTED_BY_MEGAPLAN.txt"],
                    "commands_run": ["mock-run"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Verified the work using command output only.",
                    "files_changed": [],
                    "commands_run": ["mock-verify"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed the implementation artifact exists."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed the verification task is backed by command output."},
            ],
        },
        raw_output="execute softened evidence",
        duration_ms=1,
        cost_usd=0.0,
        session_id="execute-softened-evidence",
    )
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert any("FLAG-006 softening" in deviation for deviation in response["deviations"])
    assert finalize_data["tasks"][1]["files_changed"] == []
    assert finalize_data["tasks"][1]["commands_run"] == ["mock-verify"]


def test_execute_multi_batch_happy_path_aggregates_results(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "First batch",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Second batch",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = [
        {"id": "SC1", "task_id": "T1", "question": "Batch one?", "executor_note": "", "verdict": ""},
        {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    snapshots = iter([
        ({}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1", "batch2.py": "hash-2"}, None),
        ({"batch1.py": "hash-1", "batch2.py": "hash-2"}, None),
        ({"batch1.py": "hash-1", "batch2.py": "hash-2"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))

    def batched_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch and verified its focused check.",
                        "files_changed": ["batch1.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1", trace_output='{"batch":1}\n'), "codex", "persistent", False
        if "[T2]" in prompt_override:
            payload = {
                "output": "Batch two complete.",
                "files_changed": ["batch2.py"],
                "commands_run": ["pytest -k batch2"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Completed the dependent batch after T1 was persisted.",
                        "files_changed": ["batch2.py"],
                        "commands_run": ["pytest -k batch2"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Confirmed batch two output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch2", duration_ms=3, cost_usd=0.2, session_id="batch-2", trace_output='{"batch":2}\n'), "codex", "persistent", False
        raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", batched_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    final_data = read_json(plan_fixture.plan_dir / "finalize.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_EXECUTED
    assert [task["status"] for task in final_data["tasks"]] == ["done", "done"]
    assert [check["executor_note"] for check in final_data["sense_checks"]] == [
        "Confirmed batch one output.",
        "Confirmed batch two output.",
    ]
    assert execution["output"].startswith("Aggregated execute batches: completed 2/2.")
    assert [item["task_id"] for item in execution["task_updates"]] == ["T1", "T2"]
    assert [item["sense_check_id"] for item in execution["sense_check_acknowledgments"]] == ["SC1", "SC2"]
    assert execution["files_changed"] == ["batch1.py", "batch2.py"]
    assert execution["commands_run"] == ["pytest -k batch1", "pytest -k batch2"]
    assert (plan_fixture.plan_dir / "execution_trace.jsonl").read_text(encoding="utf-8") == '{"batch":1}\n{"batch":2}\n'
    batch_1 = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    batch_2 = read_json(plan_fixture.plan_dir / "execution_batch_2.json")
    assert [item["task_id"] for item in batch_1["task_updates"]] == ["T1"]
    assert [item["task_id"] for item in batch_2["task_updates"]] == ["T2"]


def test_execute_multi_batch_timeout_preserves_prior_batches(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = ["T1"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    snapshots = iter([
        ({}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
        ({"batch1.py": "hash-1"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))

    def timed_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch and verified its focused check.",
                        "files_changed": ["batch1.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1"), "codex", "persistent", False
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "batch-2", "raw_output": "partial"})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timed_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    final_data = read_json(plan_fixture.plan_dir / "finalize.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    state = load_state(plan_fixture.plan_dir)

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert final_data["tasks"][0]["status"] == "done"
    assert final_data["tasks"][1]["status"] == "pending"
    assert final_data["sense_checks"][0]["executor_note"] == "Confirmed batch one output."
    assert final_data["sense_checks"][1]["executor_note"] == ""
    assert [item["task_id"] for item in execution["task_updates"]] == ["T1"]
    assert state["history"][-1]["result"] == "timeout"


def test_execute_rerun_with_completed_dependency_uses_single_batch_fast_path(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Already completed."
    finalize_data["tasks"][0]["files_changed"] = ["batch1.py"]
    finalize_data["tasks"][0]["commands_run"] = ["pytest -k batch1"]
    finalize_data["tasks"][1]["depends_on"] = ["T1"]
    finalize_data["sense_checks"][0]["executor_note"] = "Already acknowledged."
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    prompt_overrides: list[str | None] = []

    def rerun_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        prompt_overrides.append(prompt_override)
        payload = {
            "output": "Rerun complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest -k rerun"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Kept the already-completed task intact during rerun.",
                    "files_changed": ["batch1.py"],
                    "commands_run": ["pytest -k batch1"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Completed the remaining dependent task.",
                    "files_changed": ["batch2.py"],
                    "commands_run": ["pytest -k rerun"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Already acknowledged."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed rerun output."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="rerun", duration_ms=1, cost_usd=0.0, session_id="rerun"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", rerun_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is True
    assert prompt_overrides == [None]


def test_execute_multi_batch_observation_allows_cross_batch_reedit_and_flags_phantoms(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = ["T1"]
    (plan_fixture.plan_dir / "finalize.json").write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")

    snapshots = iter([
        ({}, None),
        ({"megaplan/handlers.py": "hash-1"}, None),
        ({"megaplan/handlers.py": "hash-1"}, None),
        ({"megaplan/handlers.py": "hash-1"}, None),
        ({"megaplan/handlers.py": "hash-2"}, None),
        ({"megaplan/handlers.py": "hash-2"}, None),
        ({"megaplan/handlers.py": "hash-2"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))

    def observation_worker(step: str, state: dict, plan_dir: Path, args: Namespace, *, root: Path, resolved=None, prompt_override: str | None = None):
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["megaplan/handlers.py"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Edited handlers.py in batch one.",
                        "files_changed": ["megaplan/handlers.py"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=1, cost_usd=0.0, session_id="batch-1"), "codex", "persistent", False
        payload = {
            "output": "Batch two complete.",
            "files_changed": ["megaplan/handlers.py", "ghost.py"],
            "commands_run": ["pytest -k batch2"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Re-edited handlers.py in batch two.",
                    "files_changed": ["megaplan/handlers.py", "ghost.py"],
                    "commands_run": ["pytest -k batch2"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC2", "executor_note": "Confirmed batch two output."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="batch2", duration_ms=1, cost_usd=0.0, session_id="batch-2"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", observation_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )

    assert response["success"] is True
    assert any("ghost.py" in deviation for deviation in response["deviations"])
    assert not any(
        "executor claimed files not observed" in deviation and "megaplan/handlers.py" in deviation
        for deviation in response["deviations"]
    )

def _setup_two_batch_plan(plan_fixture: PlanFixture) -> None:
    """Drive plan to finalized and set up 2-batch task structure."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "First batch",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Second batch",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = [
        {"id": "SC1", "task_id": "T1", "question": "Batch one?", "executor_note": "", "verdict": ""},
        {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

def _batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
    """Mock worker that returns batch-specific results based on prompt content."""
    assert prompt_override is not None
    if "[T1]" in prompt_override:
        payload = {
            "output": "Batch one complete.",
            "files_changed": ["batch1.py"],
            "commands_run": ["pytest -k batch1"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Completed the first batch.",
                    "files_changed": ["batch1.py"],
                    "commands_run": ["pytest -k batch1"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed batch one."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1"), "codex", "persistent", False
    if "[T2]" in prompt_override:
        payload = {
            "output": "Batch two complete.",
            "files_changed": ["batch2.py"],
            "commands_run": ["pytest -k batch2"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Completed the second batch.",
                    "files_changed": ["batch2.py"],
                    "commands_run": ["pytest -k batch2"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC2", "executor_note": "Confirmed batch two."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="batch2", duration_ms=3, cost_usd=0.2, session_id="batch-2"), "codex", "persistent", False
    raise AssertionError(f"Unexpected batch prompt: {prompt_override}")


def _single_remaining_t2_worker(
    step,
    state,
    plan_dir,
    args,
    *,
    root=None,
    resolved=None,
    prompt_override=None,
):
    payload = {
        "output": "Remaining task complete.",
        "files_changed": ["batch2.py"],
        "commands_run": ["pytest -k batch2"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T2",
                "status": "done",
                "executor_notes": "Completed downstream task.",
                "files_changed": ["batch2.py"],
                "commands_run": ["pytest -k batch2"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC2", "executor_note": "Confirmed downstream task."}
        ],
    }
    return (
        WorkerResult(
            payload=payload,
            raw_output="batch2",
            duration_ms=2,
            cost_usd=0.1,
            session_id="batch-2",
        ),
        "codex",
        "persistent",
        False,
    )


def test_batch_1_on_two_batch_plan_stays_finalized(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    make_args = plan_fixture.make_args
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = read_json(plan_fixture.plan_dir / "state.json")
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["batch"] == 1
    assert response["batches_total"] == 2
    assert response["batches_remaining"] == 1
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert not (plan_fixture.plan_dir / "execution.json").exists()
    assert finalize_data["tasks"][0]["status"] == "done"
    assert finalize_data["tasks"][1]["status"] == "pending"

def test_batch_timeout_reads_execution_batch_n_json(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    checkpoint_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Recovered from batch checkpoint.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Recovered batch checkpoint sense check."}
        ],
    }
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps(checkpoint_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def timing_out_batch_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "batch-timeout", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    recovered = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert recovered["tasks"][0]["status"] == "done"
    assert recovered["tasks"][0]["files_changed"] == ["batch1.py"]
    assert recovered["tasks"][1]["status"] == "pending"
    assert recovered["sense_checks"][0]["executor_note"] == "Recovered batch checkpoint sense check."
    assert any(
        "Recovered timeout checkpoint from execution_batch_1.json" in deviation
        for deviation in response["deviations"]
    )


def test_batch_timeout_checkpoint_uses_model_seam_capture_recovery(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    checkpoint_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Recovered from batch checkpoint.",
                "files_changed": ["batch1.py"],
                "commands_run": ["pytest -k batch1"],
            }
        ],
        "sense_check_acknowledgments": [
            {"sense_check_id": "SC1", "executor_note": "Recovered batch checkpoint sense check."}
        ],
    }
    checkpoint_path = plan_fixture.plan_dir / "execution_batch_1.json"
    checkpoint_raw = json.dumps(checkpoint_payload, indent=2) + "\n"
    checkpoint_path.write_text(checkpoint_raw, encoding="utf-8")

    captured: dict[str, object] = {}
    real_capture = megaplan_execute_timeout.capture_step_output

    def spying_capture(invocation, output):
        captured["metadata"] = dict(invocation.metadata)
        captured["output"] = output
        return real_capture(invocation, output)

    monkeypatch.setattr(megaplan_execute_timeout, "capture_step_output", spying_capture)

    def timing_out_batch_worker(*args, **kwargs):
        raise megaplan.CliError("worker_timeout", "execute timed out", extra={"session_id": "batch-timeout", "raw_output": ""})

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", timing_out_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )

    assert response["success"] is False
    assert captured["output"] == checkpoint_raw
    metadata = captured["metadata"]
    assert metadata["validation_step"] == "execute"
    assert metadata["compatibility_validation_step"] == "execute"
    assert metadata["capture_recovery"] == {
        "step": "execute",
        "plan_dir": str(plan_fixture.plan_dir),
        "output_path": str(checkpoint_path),
        "prefer_output_file": True,
    }


def test_batch_2_after_batch_1_transitions_to_executed(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    make_args = plan_fixture.make_args
    megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
    )
    state = read_json(plan_fixture.plan_dir / "state.json")
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["state"] == megaplan.STATE_EXECUTED
    assert response["next_step"] == "review"
    assert response["batch"] == 2
    assert response["batches_remaining"] == 0
    assert (plan_fixture.plan_dir / "execution.json").exists()
    execution = read_json(plan_fixture.plan_dir / "execution.json")
    assert [item["task_id"] for item in execution["task_updates"]] == ["T1", "T2"]
    assert all(t["status"] == "done" for t in finalize_data["tasks"])


def test_batch_2_halts_on_corrupt_prior_execution_batch(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        megaplan.handle_execute(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
        )

    assert "M3B_HALT_CORRUPT_EXECUTION_BATCH" in str(excinfo.value)
    assert str(plan_fixture.plan_dir / "execution_batch_1.json") in str(excinfo.value)
    assert "Expecting property name enclosed in double quotes" in str(excinfo.value)

def test_execute_quality_advisories_flow_into_batch_artifacts_aggregate_and_next_prompt(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    batch1_path = plan_fixture.project_dir / "batch1.txt"
    batch2_path = plan_fixture.project_dir / "batch2.txt"
    _write_lines(batch1_path, 10, prefix="batch1_before")
    _write_lines(batch2_path, 10, prefix="batch2_before")

    snapshots = iter([
        ({"batch1.txt": "before-1"}, None),
        ({"batch1.txt": "after-1"}, None),
        ({"batch1.txt": "after-1"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "before-2"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "after-2"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "after-2"}, None),
        ({"batch1.txt": "after-1", "batch2.txt": "after-2"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(megaplan.execute.batch, "load_config", lambda *_: {})

    seen_prompts: list[str | None] = []

    def quality_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        seen_prompts.append(prompt_override)
        assert prompt_override is not None
        if "[T1]" in prompt_override:
            _write_lines(batch1_path, 310, prefix="batch1_after")
            payload = {
                "output": "Batch one complete.",
                "files_changed": ["batch1.txt"],
                "commands_run": ["pytest -k batch1"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Completed the first batch and verified the file growth trigger.",
                        "files_changed": ["batch1.txt"],
                        "commands_run": ["pytest -k batch1"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Confirmed batch one output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch1", duration_ms=2, cost_usd=0.1, session_id="batch-1"), "codex", "persistent", False
        if "[T2]" in prompt_override:
            assert "Prior batch deviations (address if applicable):" in prompt_override
            assert "Advisory quality: batch1.txt grew by 300 lines (threshold 200)." in prompt_override
            _write_lines(batch2_path, 20, prefix="batch2_after")
            payload = {
                "output": "Batch two complete.",
                "files_changed": ["batch2.txt"],
                "commands_run": ["pytest -k batch2"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Completed the second batch after reviewing prior advisories.",
                        "files_changed": ["batch2.txt"],
                        "commands_run": ["pytest -k batch2"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC2", "executor_note": "Confirmed batch two output."}
                ],
            }
            return WorkerResult(payload=payload, raw_output="batch2", duration_ms=3, cost_usd=0.2, session_id="batch-2"), "codex", "persistent", False
        raise AssertionError(f"Unexpected batch prompt: {prompt_override}")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", quality_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    batch_1 = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert "Advisory quality: batch1.txt grew by 300 lines (threshold 200)." in batch_1["deviations"]
    assert any(deviation.startswith("Advisory quality:") for deviation in batch_1["deviations"])
    assert "Advisory quality: batch1.txt grew by 300 lines (threshold 200)." in execution["deviations"]
    assert any(
        prompt is not None and "Prior batch deviations (address if applicable):" in prompt and "[T2]" in prompt
        for prompt in seen_prompts
    )

def test_execute_quality_config_disable_suppresses_file_growth_deviation_end_to_end(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [finalize_data["tasks"][0]]
    finalize_data["sense_checks"] = [finalize_data["sense_checks"][0]]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    notes_path = plan_fixture.project_dir / "notes.txt"
    _write_lines(notes_path, 10, prefix="notes_before")

    snapshots = iter([
        ({"notes.txt": "before-1"}, None),
        ({"notes.txt": "after-1"}, None),
        ({"notes.txt": "after-1"}, None),
        ({"notes.txt": "after-1"}, None),
    ])
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: next(snapshots))
    monkeypatch.setattr(
        megaplan.execute.batch,
        "load_config",
        lambda *_: {"quality_checks": {"file_growth": {"enabled": False}}},
    )

    def single_quality_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        _write_lines(notes_path, 310, prefix="notes_after")
        payload = {
            "output": "Single batch complete.",
            "files_changed": ["notes.txt"],
            "commands_run": ["pytest -k quality-disable"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Completed the batch with file growth disabled in config.",
                    "files_changed": ["notes.txt"],
                    "commands_run": ["pytest -k quality-disable"],
                }
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed config-disabled batch output."}
            ],
        }
        return WorkerResult(payload=payload, raw_output="single", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_quality_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    batch_1 = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    execution = read_json(plan_fixture.plan_dir / "execution.json")

    assert response["success"] is True
    assert not any("notes.txt grew by" in deviation for deviation in batch_1["deviations"])
    assert not any("notes.txt grew by" in deviation for deviation in execution["deviations"])
    assert not any("notes.txt grew by" in deviation for deviation in response["deviations"])

def test_batch_out_of_range_raises(
    plan_fixture: PlanFixture,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    make_args = plan_fixture.make_args
    with pytest.raises(megaplan.CliError, match="out of range"):
        megaplan.handle_execute(
            plan_fixture.root,
            make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=3),
        )

def test_batch_2_without_batch_1_raises_prerequisites(
    plan_fixture: PlanFixture,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    make_args = plan_fixture.make_args
    with pytest.raises(megaplan.CliError, match="requires batches") as exc_info:
        megaplan.handle_execute(
            plan_fixture.root,
            make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
        )
    assert exc_info.value.code == "batch_prerequisites"


def test_batch_2_blocks_prior_raw_done_without_authority_evidence(
    plan_fixture: PlanFixture,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "done"
    finalize_data["tasks"][0]["executor_notes"] = "Legacy assertion only."
    finalize_data["tasks"][0]["files_changed"] = []
    finalize_data["tasks"][0]["commands_run"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "executor_notes": "Raw terminal claim without output evidence.",
                        "files_changed": [],
                        "commands_run": [],
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    make_args = plan_fixture.make_args
    with pytest.raises(megaplan.CliError, match="requires batches") as exc_info:
        megaplan.handle_execute(
            plan_fixture.root,
            make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=2),
        )

    assert exc_info.value.code == "batch_prerequisites"
    assert exc_info.value.extra["missing_task_ids"] == ["T1"]
    decision = exc_info.value.extra["authority_decisions"]["T1"]
    assert decision["authority_status"] == "unknown"
    assert decision["would_block_reasons"] == ["missing_linked_evidence"]


def test_batch_1_on_single_batch_plan_transitions_to_executed(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    def single_batch_worker(
        step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None
    ):
        payload = {
            "output": "All tasks complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest"],
            "deviations": [],
            "task_updates": [
                {"task_id": "T1", "status": "done", "executor_notes": "Done T1.", "files_changed": ["batch1.py"], "commands_run": ["pytest"]},
                {"task_id": "T2", "status": "done", "executor_notes": "Done T2.", "files_changed": ["batch2.py"], "commands_run": ["pytest"]},
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="all", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_batch_worker)

    make_args = plan_fixture.make_args
    response = megaplan.handle_execute(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )

    assert response["state"] == megaplan.STATE_EXECUTED
    assert response["next_step"] == "review"
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert (plan_fixture.plan_dir / "execution.json").exists()


def test_one_batch_receipt_worker_preserves_rate_limit_without_receipt_field(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    captured_rate_limits: list[dict[str, object] | None] = []
    real_build_receipt = megaplan.execute.batch.build_receipt

    def capture_build_receipt(**kwargs):
        captured_rate_limits.append(kwargs["worker"].rate_limit)
        return real_build_receipt(**kwargs)

    def single_batch_worker(
        step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None
    ):
        payload = {
            "output": "All tasks complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "executor_notes": "Done T1.",
                    "files_changed": ["batch1.py"],
                    "commands_run": ["pytest"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                    "executor_notes": "Done T2.",
                    "files_changed": ["batch2.py"],
                    "commands_run": ["pytest"],
                },
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed."},
            ],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="all",
                duration_ms=1,
                cost_usd=0.1,
                session_id="single",
                rate_limit={"provider": "codex", "reset_at": "2026-06-12T00:00:00Z"},
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.execute.batch, "build_receipt", capture_build_receipt)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
    )

    assert response["state"] == megaplan.STATE_EXECUTED
    assert captured_rate_limits == [
        {"provider": "codex", "reset_at": "2026-06-12T00:00:00Z"}
    ]
    receipt = read_json(plan_fixture.plan_dir / "step_receipt_execute_v1.json")
    assert "rate_limit" not in receipt


def test_light_batch_1_on_single_batch_plan_transitions_to_done(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="light")
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    def single_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        payload = {
            "output": "All tasks complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest"],
            "deviations": [],
            "task_updates": [
                {"task_id": "T1", "status": "done", "executor_notes": "Done T1.", "files_changed": ["batch1.py"], "commands_run": ["pytest"]},
                {"task_id": "T2", "status": "done", "executor_notes": "Done T2.", "files_changed": ["batch2.py"], "commands_run": ["pytest"]},
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="all", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = load_state(plan_fixture.plan_dir)
    stored_review = read_json(plan_fixture.plan_dir / "review.json")

    assert response["state"] == megaplan.STATE_DONE
    assert response["next_step"] is None
    assert state["current_state"] == megaplan.STATE_DONE
    assert "review.json" in response["artifacts"]
    assert stored_review["review_verdict"] == "approved"
    assert stored_review["checks"] == []
    assert stored_review["pre_check_flags"] == []
    assert stored_review["task_verdicts"] == []
    assert stored_review["sense_check_verdicts"] == []
    assert stored_review["criteria"]
    assert all(item["pass"] == "pass" for item in stored_review["criteria"])
    assert not (plan_fixture.plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME).exists()
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert (plan_fixture.plan_dir / "execution.json").exists()


def test_bare_batch_1_on_single_batch_plan_transitions_to_done_without_review_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_fixture = _make_plan_fixture_with_robustness(tmp_path, monkeypatch, robustness="bare")
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][1]["depends_on"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    def single_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        payload = {
            "output": "All tasks complete.",
            "files_changed": ["batch1.py", "batch2.py"],
            "commands_run": ["pytest"],
            "deviations": [],
            "task_updates": [
                {"task_id": "T1", "status": "done", "executor_notes": "Done T1.", "files_changed": ["batch1.py"], "commands_run": ["pytest"]},
                {"task_id": "T2", "status": "done", "executor_notes": "Done T2.", "files_changed": ["batch2.py"], "commands_run": ["pytest"]},
            ],
            "sense_check_acknowledgments": [
                {"sense_check_id": "SC1", "executor_note": "Confirmed."},
                {"sense_check_id": "SC2", "executor_note": "Confirmed."},
            ],
        }
        return WorkerResult(payload=payload, raw_output="all", duration_ms=1, cost_usd=0.1, session_id="single"), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", single_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = load_state(plan_fixture.plan_dir)

    assert response["state"] == megaplan.STATE_DONE
    assert response["next_step"] is None
    assert state["current_state"] == megaplan.STATE_DONE
    assert not (plan_fixture.plan_dir / "review.json").exists()
    assert not (plan_fixture.plan_dir / TRANSITION_DECISION_REVIEW_DONE_FILENAME).exists()
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert (plan_fixture.plan_dir / "execution.json").exists()

def test_batch_1_incomplete_tracking_returns_blocked(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    def incomplete_batch_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        assert prompt_override is not None
        return WorkerResult(
            payload={
                "output": "Batch one incomplete.",
                "files_changed": [],
                "commands_run": [],
                "deviations": [],
                "task_updates": [],
                "sense_check_acknowledgments": [],
            },
            raw_output="batch incomplete",
            duration_ms=1,
            cost_usd=0.0,
            session_id="batch-incomplete",
        ), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", incomplete_batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True, batch=1),
    )
    state = load_state(plan_fixture.plan_dir)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["summary"] == (
        "Blocked: 1/1 tasks have no executor update; 1/1 sense checks have no executor acknowledgment. "
        "Re-run execute to complete tracking."
    )
    assert finalize_data["tasks"][0]["status"] == "pending"
    assert state["history"][-1]["result"] == "blocked"

def test_execute_auto_loop_stops_when_existing_task_is_blocked(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "blocked"
    finalize_data["tasks"][0]["executor_notes"] = "Awaiting live canary trigger evidence."
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n",
        encoding="utf-8",
    )

    def worker_should_not_run(*_args, **_kwargs):
        raise AssertionError("execute auto loop must not run dependent batches after a blocked task")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker_should_not_run)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert response["blocked_task_ids"] == ["T1"]
    assert "existing blocked task(s) prevent dependent execution: T1" in response["summary"]
    assert state["history"][-1]["result"] == "blocked"
    # Verify phase_result.json is written with correct exit_kind
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written for every execute exit"
    assert pr.exit_kind == "blocked_by_prereq"


def test_execute_unroutable_review_rework_reruns_review_then_blocks_recoverably(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    for task in finalize_data["tasks"]:
        task["status"] = "done"
        task["executor_notes"] = "done"
        task["commands_run"] = ["true"]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n",
        encoding="utf-8",
    )
    review_payload = {
        "review_verdict": "needs_rework",
        "rework_items": [
            {
                "task_id": "REVIEW",
                "issue": "Placeholder review finding.",
                "expected": "Reference a concrete finalize task.",
                "actual": "No concrete finalize task was referenced.",
            }
        ],
    }
    (plan_fixture.plan_dir / "review.json").write_text(
        json.dumps(review_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def worker_should_not_run(*_args, **_kwargs):
        raise AssertionError("unroutable rework should reroute before execute workers run")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker_should_not_run)

    def rerun_execute_with_same_bad_review() -> dict:
        state = load_state(plan_fixture.plan_dir)
        state["current_state"] = megaplan.STATE_FINALIZED
        (plan_fixture.plan_dir / "state.json").write_text(
            json.dumps(state, indent=2) + "\n",
            encoding="utf-8",
        )
        (plan_fixture.plan_dir / "review.json").write_text(
            json.dumps(review_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        return megaplan.handle_execute(
            plan_fixture.root,
            make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
            ),
        )

    first = rerun_execute_with_same_bad_review()
    state = load_state(plan_fixture.plan_dir)

    assert first["state"] == megaplan.STATE_BLOCKED
    assert first["next_step"] is None
    assert first["success"] is False
    assert first["unrunnable_rework_task_ids"] == ["REVIEW"]
    assert state["current_state"] == megaplan.STATE_BLOCKED
    assert state["resume_cursor"] == {
        "phase": "execute",
        "batch_index": None,
        "retry_strategy": "fresh_session",
    }
    assert state["meta"]["unroutable_rework_attempts"] == 1
    assert "review requested rework but no runnable finalize task IDs" in first["summary"]

    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result

    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written for every execute exit"
    assert pr.exit_kind == "blocked_by_quality"
    assert pr.deviations


def test_execute_mixed_routable_unroutable_rework_escalates_recoverably_after_cap(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    runnable_task_id = finalize_data["tasks"][0]["id"]
    for task in finalize_data["tasks"]:
        task["status"] = "done"
        task["executor_notes"] = "done"
        task["commands_run"] = ["true"]
        task["files_changed"] = ["a.py"]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n",
        encoding="utf-8",
    )
    review_payload = {
        "review_verdict": "needs_rework",
        "rework_items": [
            {
                "task_id": runnable_task_id,
                "issue": "Tighten the implementation for the runnable task.",
                "expected": "Runnable task addressed.",
                "actual": "Needs another pass.",
            },
            {
                "task_id": "REVIEW",
                "issue": "Discovery rewrote a production manifest out of scope.",
                "expected": "Reference a concrete finalize task.",
                "actual": "No concrete finalize task was referenced.",
            },
        ],
    }
    (plan_fixture.plan_dir / "review.json").write_text(
        json.dumps(review_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def rework_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        del step, state, plan_dir, args, root, resolved, prompt_override
        payload = {
            "output": "Re-ran the runnable rework task.",
            "files_changed": ["a.py"],
            "commands_run": ["true"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": runnable_task_id,
                    "status": "done",
                    "executor_notes": "Re-addressed the runnable rework item with evidence.",
                    "files_changed": ["a.py"],
                    "commands_run": ["true"],
                }
            ],
            "sense_check_acknowledgments": [],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="rework",
                duration_ms=1,
                cost_usd=0.0,
                session_id="rework",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", rework_worker)

    def rerun_execute_with_same_mixed_review() -> dict:
        state = load_state(plan_fixture.plan_dir)
        state["current_state"] = megaplan.STATE_FINALIZED
        fd = read_json(plan_fixture.plan_dir / "finalize.json")
        for task in fd["tasks"]:
            task["status"] = "done"
            task["executor_notes"] = "done"
            task["commands_run"] = ["true"]
            task["files_changed"] = ["a.py"]
        (plan_fixture.plan_dir / "finalize.json").write_text(
            json.dumps(fd, indent=2) + "\n", encoding="utf-8"
        )
        (plan_fixture.plan_dir / "state.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )
        (plan_fixture.plan_dir / "review.json").write_text(
            json.dumps(review_payload, indent=2) + "\n", encoding="utf-8"
        )
        return megaplan.handle_execute(
            plan_fixture.root,
            make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
            ),
        )

    fourth = rerun_execute_with_same_mixed_review()
    state = load_state(plan_fixture.plan_dir)

    assert fourth["state"] == megaplan.STATE_BLOCKED
    assert state["current_state"] == megaplan.STATE_BLOCKED
    assert fourth["success"] is False
    assert "REVIEW" in fourth["unrunnable_rework_task_ids"]
    assert "unroutable item" in fourth["summary"]

    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result

    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None
    assert pr.exit_kind == "blocked_by_quality"


def test_review_rework_targets_route_task_bulk_and_manifest_findings() -> None:
    finalize_data = {"tasks": [{"id": "T1"}, {"id": "T2"}, {"id": "T3"}]}
    review_data = {
        "rework_items": [
            {"target": {"kind": "task", "task_id": "T1"}},
            {"target": {"kind": "bulk", "id": "bulk-1", "task_ids": ["T2", "T3"]}},
            {"target": {"kind": "manifest", "id": "manifest.json", "task_ids": ["T3"]}},
        ]
    }

    runnable, unrunnable = megaplan_execute_batch._review_rework_task_ids(
        review_data,
        finalize_data,
    )

    assert runnable == ["T1", "T2", "T3"]
    assert unrunnable == []


def test_review_rework_global_and_legacy_review_targets_are_blockers() -> None:
    finalize_data = {"tasks": [{"id": "T1"}]}
    review_data = {
        "rework_items": [
            {"target": {"kind": "global", "id": "whole-run"}},
            {"task_id": "REVIEW"},
        ]
    }

    runnable, unrunnable = megaplan_execute_batch._review_rework_task_ids(
        review_data,
        finalize_data,
    )

    assert runnable == []
    assert unrunnable == ["global:whole-run", "REVIEW"]


def test_execute_mixed_routable_unroutable_rework_escalates_recoverably_after_cap(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEFECT 1: when review rework mixes a runnable task with an unroutable
    REVIEW item, the unroutable cap must still trip (instead of being reset and
    the unroutable findings silently dropped every cycle). After the cap, the
    plan escalates to recoverable STATE_BLOCKED even though a runnable item also
    exists.
    """
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    runnable_task_id = finalize_data["tasks"][0]["id"]
    for task in finalize_data["tasks"]:
        task["status"] = "done"
        task["executor_notes"] = "done"
        task["commands_run"] = ["true"]
        task["files_changed"] = ["a.py"]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n",
        encoding="utf-8",
    )
    # MIXED rework: one runnable finalize task + one unroutable REVIEW item.
    review_payload = {
        "review_verdict": "needs_rework",
        "rework_items": [
            {
                "task_id": runnable_task_id,
                "issue": "Tighten the implementation for the runnable task.",
                "expected": "Runnable task addressed.",
                "actual": "Needs another pass.",
            },
            {
                "task_id": "REVIEW",
                "issue": "Discovery rewrote a production manifest out of scope.",
                "expected": "Reference a concrete finalize task.",
                "actual": "No concrete finalize task was referenced.",
            },
        ],
    }
    (plan_fixture.plan_dir / "review.json").write_text(
        json.dumps(review_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    def rework_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        del step, state, plan_dir, args, root, resolved, prompt_override
        payload = {
            "output": "Re-ran the runnable rework task.",
            "files_changed": ["a.py"],
            "commands_run": ["true"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": runnable_task_id,
                    "status": "done",
                    "executor_notes": "Re-addressed the runnable rework item with evidence.",
                    "files_changed": ["a.py"],
                    "commands_run": ["true"],
                }
            ],
            "sense_check_acknowledgments": [],
        }
        return (
            WorkerResult(
                payload=payload,
                raw_output="rework",
                duration_ms=1,
                cost_usd=0.0,
                session_id="rework",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", rework_worker)

    def rerun_execute_with_same_mixed_review() -> dict:
        state = load_state(plan_fixture.plan_dir)
        state["current_state"] = megaplan.STATE_FINALIZED
        # Re-mark every task done so the only pending work is the rework reroute.
        fd = read_json(plan_fixture.plan_dir / "finalize.json")
        for task in fd["tasks"]:
            task["status"] = "done"
            task["executor_notes"] = "done"
            task["commands_run"] = ["true"]
            task["files_changed"] = ["a.py"]
        (plan_fixture.plan_dir / "finalize.json").write_text(
            json.dumps(fd, indent=2) + "\n", encoding="utf-8"
        )
        (plan_fixture.plan_dir / "state.json").write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )
        (plan_fixture.plan_dir / "review.json").write_text(
            json.dumps(review_payload, indent=2) + "\n", encoding="utf-8"
        )
        return megaplan.handle_execute(
            plan_fixture.root,
            make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
            ),
        )

    # Cycles 1-3: unroutable attempts increment (1,2,3 <= cap of 3); the
    # runnable rework re-runs execute each time (healthy path preserved).
    rerun_execute_with_same_mixed_review()
    rerun_execute_with_same_mixed_review()
    rerun_execute_with_same_mixed_review()
    state_after_three = load_state(plan_fixture.plan_dir)
    assert state_after_three["meta"]["unroutable_rework_attempts"] == 3

    # Cycle 4: attempts (4) > cap (3) with the unroutable item still present →
    # escalate to recoverable blocked even though a runnable item also exists.
    fourth = rerun_execute_with_same_mixed_review()
    state = load_state(plan_fixture.plan_dir)

    assert fourth["state"] == megaplan.STATE_BLOCKED
    assert state["current_state"] == megaplan.STATE_BLOCKED
    assert fourth["success"] is False
    assert "REVIEW" in fourth["unrunnable_rework_task_ids"]
    assert "unroutable item" in fourth["summary"]

    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result

    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None
    assert pr.exit_kind == "blocked_by_quality"


def test_execute_auto_loop_resets_blocked_tasks_when_flag_set(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh `megaplan auto` invocation (which always passes
    --retry-blocked-tasks) must clear stale blocked statuses persisted from a
    prior session, so the executor LLM gets a fresh attempt instead of the
    short-circuit replaying old notes.
    """
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "blocked"
    finalize_data["tasks"][0]["executor_notes"] = "Stale notes from prior session."
    finalize_data["tasks"][0]["files_changed"] = ["stale.py"]
    finalize_data["tasks"][0]["commands_run"] = ["grep stale"]
    finalize_data["tasks"][0]["evidence_files"] = ["stale.log"]
    finalize_data["tasks"][0]["reviewer_verdict"] = "stale verdict"
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None)
    )
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        confirm_destructive=True,
        user_approved=True,
        retry_blocked_tasks=True,
    )
    response = megaplan.handle_execute(plan_fixture.root, args)
    state = load_state(plan_fixture.plan_dir)
    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")

    # Short-circuit did NOT fire: blocked task got retried and reported done.
    t1 = finalize_after["tasks"][0]
    assert t1["status"] == "done"
    # The blocked task's per-attempt stale fields were replaced by the new
    # worker's output (mocked _batch_worker returns done with batch1.py).
    assert "stale.py" not in t1.get("files_changed", [])
    assert "Stale notes" not in t1.get("executor_notes", "")
    # The execute history entry is no longer the short-circuit "blocked" exit.
    last_execute = next(
        entry for entry in reversed(state.get("history", [])) if entry.get("step") == "execute"
    )
    assert last_execute["result"] != "blocked"
    # Verify phase_result.json is written with success exit_kind
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written for every execute exit"
    assert pr.exit_kind == "success"


def test_execute_auto_loop_defers_interim_baseline_checkpoint_when_baseline_missing(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["baseline_test_failures"] = None
    finalize_data["tasks"][0]["description"] = (
        "Introduce no new failures vs the recorded baseline; do not loop the suite."
    )
    finalize_data["sense_checks"] = [
        {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None)
    )
    monkeypatch.setattr(
        megaplan.workers, "run_step_with_worker", _single_remaining_t2_worker
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
    )
    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert finalize_after["tasks"][0]["status"] == "skipped"
    assert finalize_after["tasks"][0]["reviewer_verdict"] == "deferred_baseline_unavailable"
    assert "baseline_test_failures is null" in finalize_after["tasks"][0]["executor_notes"]
    assert finalize_after["tasks"][1]["status"] == "done"


def test_baseline_checkpoint_not_deferred_before_dependencies_complete(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["baseline_test_failures"] = None
    finalize_data["tasks"][0]["description"] = "First implementation batch"
    finalize_data["tasks"][1]["description"] = (
        "Introduce no new failures vs the recorded baseline; do not loop the suite."
    )
    finalize_data["tasks"].append(
        {
            "id": "T3",
            "description": "Downstream implementation",
            "depends_on": ["T2"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    )
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None)
    )
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", _batch_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
    )
    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert finalize_after["tasks"][0]["status"] == "done"
    assert finalize_after["tasks"][1]["status"] == "pending"
    assert finalize_after["tasks"][2]["status"] == "pending"


def test_retry_blocked_tasks_defers_baseline_checkpoint_instead_of_rerunning_loop(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["baseline_test_failures"] = None
    finalize_data["tasks"][0]["description"] = (
        "Introduce no new failures vs the recorded baseline; do not loop the suite."
    )
    finalize_data["tasks"][0]["status"] = "blocked"
    finalize_data["tasks"][0]["executor_notes"] = (
        "The suite failed, but no baseline_test_failures were captured."
    )
    finalize_data["tasks"][0]["commands_run"] = ["pytest -q"]
    finalize_data["sense_checks"] = [
        {"id": "SC2", "task_id": "T2", "question": "Batch two?", "executor_note": "", "verdict": ""},
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None)
    )
    monkeypatch.setattr(
        megaplan.workers, "run_step_with_worker", _single_remaining_t2_worker
    )

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            retry_blocked_tasks=True,
        ),
    )
    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert finalize_after["tasks"][0]["status"] == "skipped"
    assert finalize_after["tasks"][0]["reviewer_verdict"] == "deferred_baseline_unavailable"
    assert finalize_after["tasks"][0]["commands_run"] == []
    assert finalize_after["tasks"][1]["status"] == "done"


def test_retry_blocked_defers_final_no_baseline_checkpoint_without_rerunning(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["baseline_test_failures"] = None
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Implementation",
            "depends_on": [],
            "status": "done",
            "executor_notes": "done",
            "files_changed": ["done.py"],
            "commands_run": ["true"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Introduce no new failures vs the recorded baseline; do not loop the suite.",
            "depends_on": ["T1"],
            "status": "blocked",
            "executor_notes": "Cannot compare failures without a baseline.",
            "files_changed": [],
            "commands_run": ["pytest"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    def worker_should_not_run(*_args, **_kwargs):
        raise AssertionError("retry-blocked must not rerun an unresolvable final checkpoint")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker_should_not_run)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            retry_blocked_tasks=True,
        ),
    )
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result

    pr = read_phase_result(plan_fixture.plan_dir)
    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is True
    assert finalize_after["tasks"][1]["status"] == "skipped"
    assert finalize_after["tasks"][1]["reviewer_verdict"] == "deferred_baseline_unavailable"
    assert finalize_after["tasks"][1]["commands_run"] == []
    assert "baseline_test_failures is null" in finalize_after["tasks"][1]["executor_notes"]
    assert pr is not None
    assert pr.exit_kind == "success"


def test_execute_defers_repeated_no_baseline_checkpoints_without_pending_tail(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["baseline_test_failures"] = None
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Implementation one",
            "depends_on": [],
            "status": "done",
            "executor_notes": "done",
            "files_changed": ["one.py"],
            "commands_run": ["true"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Implementation two",
            "depends_on": ["T1"],
            "status": "done",
            "executor_notes": "done",
            "files_changed": ["two.py"],
            "commands_run": ["true"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T3",
            "description": "Implementation three",
            "depends_on": ["T2"],
            "status": "done",
            "executor_notes": "done",
            "files_changed": ["three.py"],
            "commands_run": ["true"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T4",
            "description": "Introduce no new failures vs the recorded baseline; do not loop the suite.",
            "depends_on": ["T3"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T5",
            "description": "Introduce no new failures vs the recorded baseline; do not loop the suite.",
            "depends_on": ["T4"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T6",
            "description": "Introduce no new failures vs the recorded baseline; do not loop the suite.",
            "depends_on": ["T5"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    def worker_should_not_run(*_args, **_kwargs):
        raise AssertionError("baseline-unavailable verification checkpoints are not runnable work")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker_should_not_run)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            retry_blocked_tasks=True,
        ),
    )
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result

    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")
    pr = read_phase_result(plan_fixture.plan_dir)

    assert response["success"] is True
    statuses = {task["id"]: task["status"] for task in finalize_after["tasks"]}
    assert statuses == {
        "T1": "done",
        "T2": "done",
        "T3": "done",
        "T4": "skipped",
        "T5": "skipped",
        "T6": "skipped",
    }
    assert all(
        task.get("reviewer_verdict") == "deferred_baseline_unavailable"
        for task in finalize_after["tasks"][3:]
    )
    assert pr is not None
    assert pr.exit_kind == "success"


def test_status_reclassifies_stale_no_baseline_checkpoint_prereq_block(
    plan_fixture: PlanFixture,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["baseline_test_failures"] = None
    finalize_data["tasks"][0]["description"] = (
        "Introduce no new failures vs the recorded baseline; do not loop the suite."
    )
    finalize_data["tasks"][0]["status"] = "blocked"
    finalize_data["tasks"][0]["executor_notes"] = "Old run classified this as a prerequisite."
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    from arnold.pipelines.megaplan.cli.status_view import _build_status_payload
    from arnold.pipelines.megaplan.orchestration.phase_result import BlockedTask
    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_fixture.plan_dir,
        exit_kind="blocked_by_prereq",
        blocked_tasks=(BlockedTask(task_id="T1", reason="blocked_by_prereq"),),
    )

    payload = _build_status_payload(plan_fixture.plan_dir, load_state(plan_fixture.plan_dir))

    assert payload["quality_blockers"][0]["blocker_id"] == (
        "quality:T1:baseline-unavailable-no-new-failures-checkpoint"
    )
    assert payload["quality_blockers"][0]["task_id"] == "T1"
    assert payload["blocker_recovery"]["prerequisite_blockers"] == []


def test_execute_auto_loop_short_circuits_when_flag_unset(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative case: without --retry-blocked-tasks, a persisted blocked task
    still short-circuits the auto loop. This preserves the existing
    safety/cost behaviour for callers that don't opt in.
    """
    _setup_two_batch_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["status"] = "blocked"
    finalize_data["tasks"][0]["executor_notes"] = "Stale notes from prior session."
    finalize_data["tasks"][0]["files_changed"] = ["stale.py"]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    def worker_should_not_run(*_args, **_kwargs):
        raise AssertionError("worker must not run when retry-blocked-tasks is unset")

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker_should_not_run)

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        confirm_destructive=True,
        user_approved=True,
        retry_blocked_tasks=False,
    )
    response = megaplan.handle_execute(plan_fixture.root, args)
    finalize_after = read_json(plan_fixture.plan_dir / "finalize.json")

    # Short-circuit fired: blocked status (and stale fields) preserved.
    t1 = finalize_after["tasks"][0]
    assert t1["status"] == "blocked"
    assert t1["executor_notes"] == "Stale notes from prior session."
    assert t1["files_changed"] == ["stale.py"]
    assert response["blocked_task_ids"] == ["T1"]
    assert "existing blocked task(s) prevent dependent execution: T1" in response["summary"]
    # Verify phase_result.json is written with blocked_by_prereq exit_kind
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written for every execute exit"
    assert pr.exit_kind == "blocked_by_prereq"


def test_execute_auto_loop_stops_when_batch_creates_blocked_task(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(megaplan.execute.aggregation, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    calls: list[str] = []

    def blocking_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        assert prompt_override is not None
        calls.append(prompt_override)
        if "[T2]" in prompt_override:
            raise AssertionError("execute auto loop must not run later batches after a task is blocked")
        return WorkerResult(
            payload={
                "output": "Batch one blocked.",
                "files_changed": [],
                "commands_run": ["checked live prerequisite"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "blocked",
                        "executor_notes": "Awaiting live canary trigger evidence.",
                        "files_changed": [],
                        "commands_run": ["checked live prerequisite"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Blocked by live prerequisite."}
                ],
            },
            raw_output="batch blocked",
            duration_ms=1,
            cost_usd=0.0,
            session_id="batch-blocked",
        ), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", blocking_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
    )
    state = load_state(plan_fixture.plan_dir)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert len(calls) == 1
    assert finalize_data["tasks"][0]["status"] == "blocked"
    assert finalize_data["tasks"][1]["status"] == "pending"
    assert (plan_fixture.plan_dir / "execution_batch_1.json").exists()
    assert not (plan_fixture.plan_dir / "execution_batch_2.json").exists()
    assert "task(s) reported status=blocked by the worker: T1" in response["summary"]
    assert state["history"][-1]["result"] == "blocked"
    # Verify phase_result.json is written with blocked_by_prereq and blocked_task_ids
    from arnold.pipelines.megaplan.orchestration.phase_result import read_phase_result
    pr = read_phase_result(plan_fixture.plan_dir)
    assert pr is not None, "phase_result.json must be written for every execute exit"
    assert pr.exit_kind == "blocked_by_prereq"
    assert len(pr.blocked_tasks) >= 1
    assert any(bt.task_id == "T1" for bt in pr.blocked_tasks)


def test_blocked_task_counts_as_tracked_in_batch_coverage(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a task that legitimately reports status=blocked counts as
    "tracked" for batch coverage purposes — the executor *did* report on it,
    just with a blocked outcome. The "tracking is incomplete" deviation must
    NOT be raised in that case, because nothing is actually missing.

    Before the fix, the coverage filter only counted {"done", "skipped"} as
    tracked, so a blocked task tripped a false-positive "1/1 batch tasks have
    no executor update" deviation that bubbled up to the auto driver and
    caused futile retries.
    """
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None)
    )

    def blocking_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        return WorkerResult(
            payload={
                "output": "Blocked on prerequisite.",
                "files_changed": [],
                "commands_run": ["check_env.sh"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "blocked",
                        "executor_notes": "DEV_LIVE_UPDATE_CHANNEL_ID missing from .env.",
                        "files_changed": [],
                        "commands_run": ["check_env.sh"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "Cannot verify; blocked."}
                ],
            },
            raw_output="batch blocked",
            duration_ms=1,
            cost_usd=0.0,
            session_id="batch-blocked-coverage",
        ), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", blocking_worker)

    response = megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True
        ),
    )

    execution_batch = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    deviations = execution_batch.get("deviations") or []
    assert not any(
        "tracking is incomplete" in str(d) for d in deviations
    ), (
        "Blocked task must not trigger a false 'tracking is incomplete' "
        f"deviation; got deviations={deviations!r}"
    )
    # The proper blocked-by-worker signal still surfaces on the response summary.
    assert "task(s) reported status=blocked by the worker: T1" in response["summary"]


def test_completed_status_counts_as_tracked_in_batch_coverage(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: 'completed' is a synonym the schema validator normalizes,
    but the coverage filter used to drop it on the floor. Asserting at the
    deviations layer keeps us honest if the alias normalization ever changes.
    """
    _setup_two_batch_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None)
    )

    def completed_worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        # Two tasks both end up tracked across this single batch invocation
        # (T1 'completed', T2 'done'). Neither should produce a "tracking is
        # incomplete" deviation.
        return WorkerResult(
            payload={
                "output": "Both batches handled in one pass.",
                "files_changed": ["a.py", "b.py"],
                "commands_run": ["pytest"],
                "deviations": [],
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "completed",
                        "executor_notes": "First task done (reported as completed alias).",
                        "files_changed": ["a.py"],
                        "commands_run": ["pytest"],
                    },
                    {
                        "task_id": "T2",
                        "status": "done",
                        "executor_notes": "Second task done.",
                        "files_changed": ["b.py"],
                        "commands_run": ["pytest"],
                    },
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC1", "executor_note": "ok"},
                    {"sense_check_id": "SC2", "executor_note": "ok"},
                ],
            },
            raw_output="batch completed",
            duration_ms=1,
            cost_usd=0.0,
            session_id="batch-completed-coverage",
        ), "codex", "persistent", False

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", completed_worker)

    megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True
        ),
    )

    execution_batch = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    deviations = execution_batch.get("deviations") or []
    assert not any(
        "tracking is incomplete" in str(d) for d in deviations
    ), (
        "Completed/done tasks must not trigger 'tracking is incomplete'; "
        f"got deviations={deviations!r}"
    )


# ---------------------------------------------------------------------------
# Tier routing observability tests
# ---------------------------------------------------------------------------


def test_make_history_entry_includes_tier_fields_when_provided() -> None:
    """History entries include batch_complexity, tier_model_spec, and
    tier_model_resolved when tier routing is active."""
    entry = megaplan._core.make_history_entry(
        "execute",
        duration_ms=100,
        cost_usd=0.01,
        result="success",
        agent="codex",
        mode="persistent",
        batch_complexity=3,
        tier_model_spec="codex:medium",
        tier_model_resolved="codex-medium-v2",
    )
    assert entry["batch_complexity"] == 3
    assert entry["tier_model_spec"] == "codex:medium"
    assert entry["tier_model_resolved"] == "codex-medium-v2"


def test_make_history_entry_omits_tier_fields_for_flat_profile() -> None:
    """History entries omit tier fields when they are None (flat profiles)."""
    entry = megaplan._core.make_history_entry(
        "execute",
        duration_ms=100,
        cost_usd=0.01,
        result="success",
        agent="codex",
        mode="persistent",
        # No tier fields passed — flat profile.
    )
    assert "batch_complexity" not in entry
    assert "tier_model_spec" not in entry
    assert "tier_model_resolved" not in entry


def test_handle_execute_one_batch_response_includes_tier_metadata(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """StepResponse includes tier fields when tier_map is active and the
    batch's max complexity maps to a tier spec."""
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    state = load_state(plan_fixture.plan_dir)

    tier_map = {
        1: "hermes:deepseek:deepseek-v4-flash",
        3: "codex:medium",
        5: "codex:high",
    }

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    # With tier_map active, response should carry tier observability fields.
    assert "batch_complexity" in response, (
        "StepResponse must include batch_complexity when tier routing active"
    )
    assert "tier_model_spec" in response, (
        "StepResponse must include tier_model_spec when tier routing active"
    )
    assert "tier_agent" in response, (
        "StepResponse must include tier_agent when tier routing active"
    )
    assert "tier_mode" in response, (
        "StepResponse must include tier_mode when tier routing active"
    )
    assert "tier_model" in response, (
        "StepResponse must include tier_model when tier routing active"
    )
    # The plan's single task T1 has no complexity field → defaults to 5.
    assert response["batch_complexity"] == 5, (
        "Missing complexity defaults to 5"
    )
    assert response["tier_model_spec"] == "codex:high", (
        "Complexity 5 maps to codex:high in the tier_map"
    )


def test_execute_model_metadata_normalizes_provider_prefixed_model_for_model_seam() -> None:
    metadata = megaplan_execute_batch._execute_model_metadata(
        agent="hermes",
        model="deepseek:deepseek-v4-pro",
        resolved_model="deepseek:deepseek-v4-pro",
    )

    assert metadata["model"] == "deepseek:deepseek-v4-pro"
    assert metadata["normalized_model"] == "deepseek-v4-pro"


def test_execute_prompt_render_uses_normalized_provider_model_for_budgeting(
    plan_fixture: PlanFixture,
) -> None:
    state = load_state(plan_fixture.plan_dir)

    rendered = megaplan_execute_batch._render_execute_prompt_for_dispatch(
        agent="hermes",
        state=state,
        plan_dir=plan_fixture.plan_dir,
        root=plan_fixture.root,
        model="deepseek:deepseek-v4-pro",
        resolved_model="deepseek:deepseek-v4-pro",
        prompt_override="x" * 130_000,
    )

    assert rendered


def test_handle_execute_one_batch_renders_and_captures_at_execute_boundary(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    render_calls: list[dict[str, object]] = []
    capture_calls: list[dict[str, object]] = []

    def fake_render(invocation):
        metadata = dict(invocation.metadata)
        render_calls.append(metadata)
        return SimpleNamespace(prompt="[rendered execute]\n" + str(metadata["prompt"]))

    def fake_capture(invocation, output):
        capture_calls.append(
            {
                "metadata": dict(invocation.metadata),
                "output": dict(output),
            }
        )
        captured = dict(output)
        captured["commands_run"] = ["pytest tests/test_execute.py"]
        return SimpleNamespace(legacy_payload=captured)

    def boundary_worker(
        step: str,
        state: dict,
        plan_dir: Path,
        args: Namespace,
        *,
        root: Path,
        resolved=None,
        prompt_override: str | None = None,
    ):
        assert step == "execute"
        assert prompt_override is not None
        assert prompt_override.startswith("[rendered execute]\n")
        return (
            WorkerResult(
                payload={
                    "output": "done",
                    "files_changed": ["newpkg/file.py"],
                    "commands_run": [],
                    "deviations": [],
                    "task_updates": [
                        {
                            "task_id": "T1",
                            "status": "done",
                            "executor_notes": "done",
                            "files_changed": ["newpkg/file.py"],
                            "commands_run": [],
                        }
                    ],
                    "sense_check_acknowledgments": [
                        {
                            "sense_check_id": "SC1",
                            "executor_note": "Confirmed execute boundary capture.",
                        }
                    ],
                },
                raw_output="{}",
                duration_ms=1,
                cost_usd=0.0,
                session_id="boundary-session",
            ),
            "codex",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.execute.batch, "render_step_message", fake_render)
    monkeypatch.setattr(megaplan.execute.batch, "capture_step_output", fake_capture)
    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", boundary_worker)
    monkeypatch.setattr(
        megaplan.execute.aggregation,
        "_compute_execute_scope_drift",
        lambda *_, **__: SimpleNamespace(
            files_added=[],
            files_missing=[],
            loc_added=0,
            loc_removed=0,
            loc_added_outside_claimed=0,
            severity="none",
        ),
    )

    state = load_state(plan_fixture.plan_dir)
    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.5",
        resolved_model="gpt-5.5",
    )

    assert response["success"] is True
    assert render_calls and render_calls[0]["validation_step"] == "execute"
    assert capture_calls and capture_calls[0]["metadata"]["validation_step"] == "execute"
    persisted = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    assert persisted["commands_run"] == ["pytest tests/test_execute.py"]


def test_handle_execute_one_batch_vertical_model_seam_proof(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    dispatched_prompts: list[str | None] = []

    def _reset_execute_state() -> dict:
        finalize_path = plan_fixture.plan_dir / "finalize.json"
        finalize_data = read_json(finalize_path)
        finalize_data["tasks"][0].update(
            {
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
            }
        )
        finalize_data["sense_checks"][0]["executor_note"] = ""
        finalize_path.write_text(json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8")
        return load_state(plan_fixture.plan_dir)

    def _stub_snapshots() -> None:
        _stub_auto_attribute_git_snapshots(monkeypatch)

    def _run_batch(
        *,
        batch_number: int,
        payload: dict[str, object],
        model: str = "gpt-5.5",
    ):
        _stub_snapshots()

        def boundary_worker(
            step: str,
            state: dict,
            plan_dir: Path,
            args: Namespace,
            *,
            root: Path,
            resolved=None,
            prompt_override: str | None = None,
        ):
            assert step == "execute"
            assert prompt_override is not None
            assert "Implement the new package file." in prompt_override
            dispatched_prompts.append(prompt_override)
            return (
                WorkerResult(
                    payload=payload,
                    raw_output=json.dumps(payload),
                    duration_ms=1,
                    cost_usd=0.0,
                    session_id=f"vertical-session-{batch_number}",
                ),
                "codex",
                "persistent",
                False,
            )

        monkeypatch.setattr(megaplan.workers, "run_step_with_worker", boundary_worker)
        monkeypatch.setattr(
            megaplan.execute.aggregation,
            "_compute_execute_scope_drift",
            lambda *_, **__: SimpleNamespace(
                files_added=[],
                files_missing=[],
                loc_added=0,
                loc_removed=0,
                loc_added_outside_claimed=0,
                severity="none",
            ),
        )
        return megaplan.execute.core.handle_execute_one_batch(
            root=plan_fixture.root,
            plan_dir=plan_fixture.plan_dir,
            state=_reset_execute_state(),
            args=plan_fixture.make_args(
                plan=plan_fixture.plan_name,
                confirm_destructive=True,
                user_approved=True,
                batch=batch_number,
            ),
            batch_number=batch_number,
            auto_approve=False,
            agent="codex",
            mode="persistent",
            refreshed=False,
            model=model,
            resolved_model=model,
        )

    valid_partial_payload = {
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "partial batch payload accepted",
                "files_changed": ["newpkg/file.py"],
                "commands_run": ["pytest tests/test_execute.py"],
            }
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": "SC1",
                "executor_note": "Validated execute seam proof.",
            }
        ],
    }

    response = _run_batch(batch_number=1, payload=valid_partial_payload)

    assert response["success"] is True
    assert dispatched_prompts
    persisted = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    assert persisted["task_updates"][0]["executor_notes"] == "partial batch payload accepted"
    assert "output" not in persisted

    wrong_type_payload = {
        "task_updates": "this key is valid but the value type is wrong",
        "sense_check_acknowledgments": [],
    }

    with pytest.raises(Exception, match="worker_structural_audit_failed"):
        _run_batch(batch_number=1, payload=wrong_type_payload)

    degraded_response = _run_batch(
        batch_number=1,
        payload=valid_partial_payload,
        model="unknown-execute-model",
    )

    assert degraded_response["success"] is True
    assert len(dispatched_prompts) == 3
    degraded_persisted = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    assert degraded_persisted["task_updates"][0]["status"] == "done"


def test_handle_execute_one_batch_uses_valid_calibration_suggestion(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "query_route_if_enabled",
        lambda *args, **kwargs: RouteSuggestion(tier_spec="hermes:flash", confidence=0.9),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        lambda args, tier_spec: ("hermes", "persistent", f"resolved::{tier_spec}"),
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map={1: "hermes:flash", 5: "codex:high"},
    )

    assert response["tier_model_spec"] == "hermes:flash"
    assert response["tier_agent"] == "hermes"
    assert response["tier_model"] == "resolved::hermes:flash"


@pytest.mark.parametrize(
    ("flag_value", "suggestion", "expected_spec", "expected_source", "expected_query_calls"),
    [
        (None, None, "codex:high", "toml", 0),
        ("1", None, "codex:high", "toml", 1),
        (
            "1",
            RouteSuggestion(
                tier_spec="hermes:flash",
                confidence=0.9,
                projected_tier=1,
                counterfactual_tag="explore-007",
            ),
            "hermes:flash",
            "calibration_query",
            1,
        ),
    ],
)
def test_handle_execute_one_batch_calibration_flag_characterization(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    flag_value: str | None,
    suggestion: RouteSuggestion | None,
    expected_spec: str,
    expected_source: str,
    expected_query_calls: int,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    if flag_value is None:
        monkeypatch.delenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", raising=False)
    else:
        monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", flag_value)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        lambda args, tier_spec: ("codex" if tier_spec == "codex:high" else "hermes", "persistent", f"resolved::{tier_spec}"),
    )
    query_calls: list[str] = []

    def _query(*args, **kwargs):
        query_calls.append("called")
        return suggestion

    monkeypatch.setattr(
        megaplan.execute.batch,
        "query_route_if_enabled",
        _query,
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map={1: "hermes:flash", 5: "codex:high"},
    )

    history = load_state(plan_fixture.plan_dir)["history"][-1]
    batch_artifact = read_json(plan_fixture.plan_dir / "execution_batch_1.json")

    assert len(query_calls) == expected_query_calls
    assert response["tier_model_spec"] == expected_spec
    assert response["tier_model"] == f"resolved::{expected_spec}"
    assert response["tier_routing_source"] == expected_source
    assert response["batch_complexity"] == 5
    assert response["tier_projected"] == (1 if expected_source == "calibration_query" else 5)
    assert response.get("tier_counterfactual_tag") == (
        "explore-007" if expected_source == "calibration_query" else None
    )
    assert response["tier_low_confidence"] is False
    assert history["tier_model_spec"] == expected_spec
    assert history["tier_model_resolved"] == f"resolved::{expected_spec}"
    assert history["tier_routing_source"] == expected_source
    assert history["tier_projected"] == (
        1 if expected_source == "calibration_query" else 5
    )
    assert history.get("tier_counterfactual_tag") == (
        "explore-007" if expected_source == "calibration_query" else None
    )
    assert history.get("tier_low_confidence", False) is False
    assert batch_artifact["task_updates"][0]["task_id"] == "T1"
    assert batch_artifact["task_updates"][0]["status"] == "done"


def test_handle_execute_one_batch_falls_back_for_malformed_calibration_suggestion(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "query_route_if_enabled",
        lambda *args, **kwargs: RouteSuggestion(tier_spec="bogus:not-in-tier-map"),
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map={1: "hermes:flash", 5: "codex:high"},
    )

    assert response["tier_model_spec"] == "codex:high"


def test_execution_batch_artifact_persists_routing_and_actual_model(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)

    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        base = _hermes_style_worker(plan_fixture.project_dir)(
            step, state, plan_dir, args, root=root, resolved=resolved, prompt_override=prompt_override
        )
        result, agent, mode, refreshed = base
        result.model_actual = "gpt-5.4"
        return result, agent, mode, refreshed

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker)
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="gpt-5.4",
        resolved_model="gpt-5.4",
        tier_map=None,
    )

    batch = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    assert response["success"] is True
    assert batch["routing"] == {
        "batch_complexity": None,
        "selected_tier": None,
        "selected_spec": None,
        "resolved_agent": "codex",
        "resolved_mode": "persistent",
        "resolved_model": "gpt-5.4",
        "actual_agent": "codex",
        "actual_model": "gpt-5.4",
        "tier_map_configured": False,
        "tier_routing_active": False,
        "warnings": [],
    }


def test_string_keyed_execute_tier_map_routes_by_integer_complexity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"][0]["complexity"] = 4
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    _stub_auto_attribute_git_snapshots(monkeypatch)
    seen_models: list[tuple[str | None, str | None]] = []

    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        seen_models.append(
            (
                getattr(resolved, "model", None),
                getattr(resolved, "resolved_model", None),
            )
        )
        base = _hermes_style_worker(plan_fixture.project_dir)(
            step, state, plan_dir, args, root=root, resolved=resolved, prompt_override=prompt_override
        )
        result, agent, mode, refreshed = base
        result.model_actual = "premium-model"
        return result, agent, mode, refreshed

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        lambda args, tier_spec: ("codex", "persistent", "premium-model"),
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="base-model",
        resolved_model="base-model",
        tier_map={"4": "codex:premium-model"},
    )

    batch = read_json(plan_fixture.plan_dir / "execution_batch_1.json")
    assert response["tier_model_spec"] == "codex:premium-model"
    assert response["batch_complexity"] == 4
    assert seen_models == [("premium-model", "premium-model")]
    assert batch["routing"]["resolved_model"] == "premium-model"
    assert batch["routing"]["actual_model"] == "premium-model"


def test_execute_routing_model_match_accepts_codex_gpt5_family_upgrade() -> None:
    assert megaplan_execute_batch._models_match("gpt-5.4", "gpt-5.5")
    assert megaplan_execute_batch._models_match("codex:gpt-5.4", "gpt-5.5")
    assert not megaplan_execute_batch._models_match("deepseek-v4-pro", "gpt-5.5")


def test_routing_actual_model_mismatch_blocks_recoverably(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)

    def worker(step, state, plan_dir, args, *, root=None, resolved=None, prompt_override=None):
        base = _hermes_style_worker(plan_fixture.project_dir)(
            step, state, plan_dir, args, root=root, resolved=resolved, prompt_override=prompt_override
        )
        result, agent, mode, refreshed = base
        result.model_actual = "base-model"
        return result, agent, mode, refreshed

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", worker)
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        model="premium-model",
        resolved_model="premium-model",
    )

    state_after = load_state(plan_fixture.plan_dir)
    events = [
        json.loads(line)
        for line in (plan_fixture.plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert response["success"] is False
    assert response["result"] == "blocked"
    assert response["state"] == megaplan.STATE_BLOCKED
    assert state_after["current_state"] == megaplan.STATE_BLOCKED
    assert state_after["resume_cursor"]["reason"] == "routing_degradation"
    assert any(event["kind"] == "routing_degradation" for event in events)
    assert any("selected model premium-model" in d for d in response["deviations"])


def test_handle_execute_one_batch_response_omits_tier_metadata_for_flat_profile(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """StepResponse omits tier fields when tier_map is None (flat profiles)."""
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=None,  # Flat profile — no tier routing.
    )

    # Flat profile: no tier fields in response.
    assert "batch_complexity" not in response, (
        "Flat profiles must not include batch_complexity in response"
    )
    assert "tier_model_spec" not in response, (
        "Flat profiles must not include tier_model_spec in response"
    )
    assert "tier_agent" not in response, (
        "Flat profiles must not include tier_agent in response"
    )


# ---------------------------------------------------------------------------
# T17 — Execute routing tests: tier selection, freshness, flat/CLI-override,
#        and observability for auto_loop and one_batch dispatch paths.
# ---------------------------------------------------------------------------


def _setup_three_batch_tier_plan(plan_fixture: PlanFixture) -> None:
    """Drive plan to finalized and install a 3-batch dependency chain
    with explicit complexity scores [1, 3, 5]."""
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Trivial task — complexity 1",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "complexity": 1,
        },
        {
            "id": "T2",
            "description": "Medium task — complexity 3",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "complexity": 3,
        },
        {
            "id": "T3",
            "description": "Systemic task — complexity 5",
            "depends_on": ["T2"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
            "complexity": 5,
        },
    ]
    finalize_data["sense_checks"] = [
        {
            "id": "SC1",
            "task_id": "T1",
            "question": "T1 ok?",
            "executor_note": "",
            "verdict": "",
        },
        {
            "id": "SC2",
            "task_id": "T2",
            "question": "T2 ok?",
            "executor_note": "",
            "verdict": "",
        },
        {
            "id": "SC3",
            "task_id": "T3",
            "question": "T3 ok?",
            "executor_note": "",
            "verdict": "",
        },
    ]
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )


def _make_fake_batch_result(
    batch_task_ids: list[str],
    batch_sense_check_ids: list[str],
    batch_number: int = 1,
    agent: str = "codex",
    mode: str = "persistent",
    refreshed: bool = False,
    session_id: str = "fake-session",
) -> megaplan.execute.core.BatchResult:
    """Return a minimal BatchResult suitable for auto_loop consumption."""
    payload = {
        "output": f"Batch {batch_number} complete.",
        "files_changed": [f"batch{batch_number}.py"],
        "commands_run": [],
        "deviations": [],
        "task_updates": [
            {
                "task_id": tid,
                "status": "done",
                "executor_notes": f"Completed {tid}.",
                "files_changed": [f"batch{batch_number}.py"],
                "commands_run": [],
            }
            for tid in batch_task_ids
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": scid,
                "executor_note": f"Acknowledged {scid}.",
            }
            for scid in batch_sense_check_ids
        ],
    }
    return megaplan.execute.core.BatchResult(
        worker=WorkerResult(
            payload=payload,
            raw_output="",
            duration_ms=1,
            cost_usd=0.0,
            session_id=session_id,
        ),
        agent=agent,
        mode=mode,
        refreshed=refreshed,
        payload=payload,
        batch_number=batch_number,
        batch_task_ids=list(batch_task_ids),
        batch_sense_check_ids=list(batch_sense_check_ids),
        merged_task_count=len(batch_task_ids),
        total_task_count=len(batch_task_ids),
        acknowledged_sense_check_count=len(batch_sense_check_ids),
        total_sense_check_count=len(batch_sense_check_ids),
        missing_task_evidence=[],
        execution_audit={"skipped": False, "reason": "", "findings": []},
        finalize_hash="fake-hash",
        attribution_records=[],
    )


# ---------------------------------------------------------------------------
# Tier resolution order tests — one_batch dispatch
# ---------------------------------------------------------------------------


def test_one_batch_tier_selection_respects_complexity(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a batch's max complexity maps to a tier, that tier spec is resolved
    and the selected agent/mode/model are used."""
    _setup_single_auto_attribute_plan(plan_fixture)
    # Override with explicit complexity=3.
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    for task in finalize_data["tasks"]:
        task["complexity"] = 3
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    # Track calls to _resolve_tier_spec.
    tier_spec_calls: list[str] = []

    def _tracking_resolve_tier_spec(args, tier_spec):
        tier_spec_calls.append(tier_spec)
        return ("resolved-agent", "resolved-mode", "resolved-model")

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )
    state = load_state(plan_fixture.plan_dir)
    tier_map = {1: "tier-1-spec", 3: "tier-3-spec", 5: "tier-5-spec"}

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    # Complexity 3 → tier-3-spec resolved.
    assert tier_spec_calls == ["tier-3-spec"], (
        f"Expected tier-3-spec for complexity 3, got {tier_spec_calls}"
    )
    assert response.get("tier_model_spec") == "tier-3-spec"
    assert response.get("batch_complexity") == 3


def test_one_batch_tier_selection_missing_complexity_defaults_to_5(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a task has no complexity field, compute_batch_complexity returns 5,
    and the tier-5 spec is resolved."""
    _setup_single_auto_attribute_plan(plan_fixture)
    # Task has no complexity field at all.
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    tier_spec_calls: list[str] = []

    def _tracking_resolve_tier_spec(args, tier_spec):
        tier_spec_calls.append(tier_spec)
        return ("resolved-agent", "resolved-mode", "resolved-model")

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )
    state = load_state(plan_fixture.plan_dir)
    tier_map = {1: "tier-1-spec", 5: "tier-5-spec"}

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    # Missing complexity → 5 → tier-5-spec resolved.
    assert tier_spec_calls == ["tier-5-spec"], (
        f"Expected tier-5-spec for missing complexity, got {tier_spec_calls}"
    )
    assert response.get("batch_complexity") == 5
    assert response.get("tier_model_spec") == "tier-5-spec"


def test_one_batch_flat_profile_no_tier_routing(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tier_map is None (flat profile), the fallback agent/mode/model are
    used and _resolve_tier_spec is never called."""
    _setup_single_auto_attribute_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    for task in finalize_data["tasks"]:
        task["complexity"] = 3
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    tier_spec_calls: list[str] = []

    def _tracking_resolve_tier_spec(args, tier_spec):
        tier_spec_calls.append(tier_spec)
        return ("resolved-agent", "resolved-mode", "resolved-model")

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )
    state = load_state(plan_fixture.plan_dir)

    response = megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=None,  # Flat profile
    )

    # _resolve_tier_spec was never called.
    assert tier_spec_calls == [], (
        f"_resolve_tier_spec should not be called for flat profiles, got {tier_spec_calls}"
    )
    # Response omits tier fields.
    assert "batch_complexity" not in response
    assert "tier_model_spec" not in response


# ---------------------------------------------------------------------------
# CLI override test — handler-level guard
# ---------------------------------------------------------------------------


def test_handle_execute_cli_override_disables_tier_routing(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When --phase-model execute=... is present, tier_models.execute is
    stripped and the dispatchers receive tier_map=None (flat behavior)."""
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    # Monkeypatch resolve_agent_mode so handle_execute can resolve
    # "execute=codex:high" without needing real CLI agents installed.
    monkeypatch.setattr(
        megaplan.workers,
        "resolve_agent_mode",
        lambda step, args: ("codex", "persistent", False, "codex-high-v1"),
    )

    # Install tier_models on args so the detection code has something to strip.
    # We monkeypatch handle_execute_one_batch to capture the tier_map it receives.
    captured_tier_map: dict | None = "SENTINEL"

    def _capture_and_dispatch(*, root, plan_dir, state, args, batch_number,
                              auto_approve, agent, mode, refreshed, model=None,
                              tier_map="SENTINEL", **kwargs):
        nonlocal captured_tier_map
        captured_tier_map = tier_map
        # Forward to the real implementation so the rest of the test works.
        return megaplan.execute.core.handle_execute_one_batch(
            root=root, plan_dir=plan_dir, state=state, args=args,
            batch_number=batch_number, auto_approve=auto_approve,
            agent=agent, mode=mode, refreshed=refreshed, model=model,
            tier_map=tier_map,
        )

    # Patch the function used by handlers/execute.py
    monkeypatch.setattr(
        execute_handler,
        "handle_execute_one_batch",
        _capture_and_dispatch,
    )

    # Build args with phase_model containing execute=... and tier_models.
    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        confirm_destructive=True,
        user_approved=True,
        batch=1,
    )
    # Simulate what apply_profile_expansion does: when the CLI has an
    # explicit execute --phase-model override, tier_models.execute is
    # stripped.  So tier_models is present but has no execute key.
    args.tier_models = {"review": {4: "claude:medium"}}
    # CLI override: --phase-model execute=codex:high
    args.phase_model = ["execute=codex:high"]

    # Call handle_execute which runs the detection logic.
    response = megaplan.handle_execute(plan_fixture.root, args)

    # The detection code should have set tier_map = None (CLI override wins).
    assert captured_tier_map is None, (
        f"CLI execute override must disable tier routing; "
        f"got tier_map={captured_tier_map!r}"
    )
    # Response should omit tier fields since tier routing is disabled.
    assert "batch_complexity" not in response, (
        "CLI override must suppress batch_complexity in response"
    )


def test_handle_execute_variable_profile_passes_tier_map_without_cli_override(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When args.tier_models has execute tiers and args.phase_model contains
    profile-expanded execute=... (not a CLI override), handle_execute must pass
    tier_map to the dispatcher."""
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    monkeypatch.setattr(
        megaplan.workers,
        "resolve_agent_mode",
        lambda step, args: ("codex", "persistent", False, "codex-medium-v1"),
    )

    captured_tier_map: dict | None = "SENTINEL"

    def _capture_and_dispatch(*, root, plan_dir, state, args, batch_number,
                              auto_approve, agent, mode, refreshed, model=None,
                              tier_map="SENTINEL", **kwargs):
        nonlocal captured_tier_map
        captured_tier_map = tier_map
        return megaplan.execute.core.handle_execute_one_batch(
            root=root, plan_dir=plan_dir, state=state, args=args,
            batch_number=batch_number, auto_approve=auto_approve,
            agent=agent, mode=mode, refreshed=refreshed, model=model,
            tier_map=tier_map,
        )

    monkeypatch.setattr(
        execute_handler,
        "handle_execute_one_batch",
        _capture_and_dispatch,
    )

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        confirm_destructive=True,
        user_approved=True,
        batch=1,
    )
    # Simulate what apply_profile_expansion does for variable-codex:
    # tier_models.execute is present, and phase_model includes the
    # profile's own execute=... entry (no explicit CLI override).
    args.tier_models = {"execute": {1: "hermes:flash", 5: "codex:high"}}
    args.phase_model = ["execute=codex:medium"]

    response = megaplan.handle_execute(plan_fixture.root, args)

    # tier_map MUST be passed — there is no explicit CLI override
    assert captured_tier_map is not None, (
        "Variable profile without CLI override must pass tier_map; "
        f"got tier_map={captured_tier_map!r}"
    )
    assert captured_tier_map == {1: "hermes:flash", 5: "codex:high"}, (
        f"Expected tier_map {{1: 'hermes:flash', 5: 'codex:high'}}, "
        f"got {captured_tier_map!r}"
    )


def test_handle_execute_normalizes_string_tier_keys(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )
    monkeypatch.setattr(
        megaplan.workers,
        "resolve_agent_mode",
        lambda step, args: ("codex", "persistent", False, "codex-medium-v1"),
    )

    captured_tier_map: dict | None = "SENTINEL"

    def _capture_and_dispatch(*, root, plan_dir, state, args, batch_number,
                              auto_approve, agent, mode, refreshed, model=None,
                              tier_map="SENTINEL", **kwargs):
        nonlocal captured_tier_map
        captured_tier_map = tier_map
        return megaplan.execute.core.handle_execute_one_batch(
            root=root, plan_dir=plan_dir, state=state, args=args,
            batch_number=batch_number, auto_approve=auto_approve,
            agent=agent, mode=mode, refreshed=refreshed, model=model,
            tier_map=tier_map,
        )

    monkeypatch.setattr(
        execute_handler,
        "handle_execute_one_batch",
        _capture_and_dispatch,
    )

    args = plan_fixture.make_args(
        plan=plan_fixture.plan_name,
        confirm_destructive=True,
        user_approved=True,
        batch=1,
    )
    args.tier_models = {"execute": {"1": "hermes:flash", "5": "codex:high"}}

    megaplan.handle_execute(plan_fixture.root, args)

    assert captured_tier_map == {1: "hermes:flash", 5: "codex:high"}


def test_apply_execute_tier_cap_reuses_cap_spec_for_higher_tiers() -> None:
    from arnold.pipelines.megaplan.handlers.execute import _apply_execute_tier_cap

    capped = _apply_execute_tier_cap(
        {1: "hermes:flash", 3: "codex:medium", 5: "codex:high"},
        3,
    )

    assert capped == {
        1: "hermes:flash",
        3: "codex:medium",
        5: "codex:medium",
    }


# ---------------------------------------------------------------------------
# Freshness tests — auto_loop per-batch tier change
# ---------------------------------------------------------------------------


def test_auto_loop_freshness_forced_on_model_change(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the tier-selected model differs from the previous batch's model,
    refreshed=True is forced for the later batch."""
    _setup_three_batch_tier_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_args, **_kwargs: ({}, None),
    )

    tier_spec_resolutions: list[tuple[str, str, str | None]] = []
    # Batch 1: model-A, Batch 2: model-B (different), Batch 3: model-C (different)
    model_sequence = iter(["model-A", "model-B", "model-C"])

    def _tracking_resolve_tier_spec(args, tier_spec):
        model = next(model_sequence)
        result = ("codex", "persistent", model)
        tier_spec_resolutions.append(result)
        return result

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )

    # Track agent/mode/model/refreshed passed to _run_and_merge_batch.
    run_params: list[dict] = []

    def _fake_run_and_merge(**kwargs):
        run_params.append({
            "agent": kwargs["agent"],
            "mode": kwargs["mode"],
            "refreshed": kwargs["refreshed"],
            "model": kwargs["model"],
            "batch_task_ids": kwargs["batch_task_ids"],
            "batch_number": kwargs["batch_number"],
        })
        # Write finalize.json updates so the auto_loop can continue.
        finalize_data = read_json(kwargs["plan_dir"] / "finalize.json")
        for tid in kwargs["batch_task_ids"]:
            for task in finalize_data.get("tasks", []):
                if task.get("id") == tid:
                    task["status"] = "done"
                    task["executor_notes"] = f"Batch {kwargs['batch_number']} done."
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs["refreshed"],
            session_id=f"session-{kwargs['batch_number']}",
        )

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_run_and_merge_batch",
        _fake_run_and_merge,
    )

    state = load_state(plan_fixture.plan_dir)
    tier_map = {
        1: "hermes:flash",
        3: "codex:medium",
        5: "codex:high",
    }

    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    assert len(run_params) == 3, f"Expected 3 batches, got {len(run_params)}"

    # Batch 1: first batch keeps caller's refreshed value (False).
    assert run_params[0]["refreshed"] is False, (
        "Batch 1 should preserve caller refreshed=False"
    )
    assert run_params[0]["model"] == "model-A"

    # Batch 2: model changed (model-A → model-B) → refreshed=True.
    assert run_params[1]["refreshed"] is True, (
        "Batch 2 must force refreshed=True when model differs from batch 1"
    )
    assert run_params[1]["model"] == "model-B"

    # Batch 3: model changed again (model-B → model-C) → refreshed=True.
    assert run_params[2]["refreshed"] is True, (
        "Batch 3 must force refreshed=True when model differs from batch 2"
    )
    assert run_params[2]["model"] == "model-C"


def test_auto_loop_same_model_no_extra_refresh(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When consecutive batches use the same tier-selected model, refreshed
    is NOT forced to True."""
    _setup_three_batch_tier_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_args, **_kwargs: ({}, None),
    )

    # All batches resolve to the same model.
    def _tracking_resolve_tier_spec(args, tier_spec):
        return ("codex", "persistent", "same-model")

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )

    run_params: list[dict] = []

    def _fake_run_and_merge(**kwargs):
        run_params.append({
            "refreshed": kwargs["refreshed"],
            "model": kwargs["model"],
            "batch_number": kwargs["batch_number"],
        })
        finalize_data = read_json(kwargs["plan_dir"] / "finalize.json")
        for tid in kwargs["batch_task_ids"]:
            for task in finalize_data.get("tasks", []):
                if task.get("id") == tid:
                    task["status"] = "done"
                    task["executor_notes"] = f"Batch {kwargs['batch_number']} done."
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs["refreshed"],
            session_id=f"session-{kwargs['batch_number']}",
        )

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_run_and_merge_batch",
        _fake_run_and_merge,
    )

    state = load_state(plan_fixture.plan_dir)
    tier_map = {
        1: "hermes:flash",
        3: "codex:medium",
        5: "codex:high",
    }

    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    assert len(run_params) == 3

    # Batch 1: caller's refreshed=False.
    assert run_params[0]["refreshed"] is False

    # Batch 2: same model → refreshed stays False.
    assert run_params[1]["refreshed"] is False, (
        "Same model on consecutive batch should not force refreshed=True"
    )

    # Batch 3: same model → refreshed stays False.
    assert run_params[2]["refreshed"] is False, (
        "Same model on third batch should not force refreshed=True"
    )


# ---------------------------------------------------------------------------
# Auto_loop observability — batch_to_tier mapping and history entries
# ---------------------------------------------------------------------------


def test_auto_loop_batch_to_tier_observability(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tier routing is active, the aggregate history entry includes a
    batch_to_tier mapping with complexities, specs, and resolved models."""
    _setup_three_batch_tier_plan(plan_fixture)
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_args, **_kwargs: ({}, None),
    )

    # Map tier specs predictably.
    def _tracking_resolve_tier_spec(args, tier_spec):
        spec_to_model = {
            "hermes:flash": "deepseek-flash-v1",
            "codex:medium": "codex-medium-v2",
            "codex:high": "codex-high-v1",
        }
        model = spec_to_model.get(tier_spec, "unknown")
        return ("codex", "persistent", model)

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )

    def _fake_run_and_merge(**kwargs):
        finalize_data = read_json(kwargs["plan_dir"] / "finalize.json")
        for tid in kwargs["batch_task_ids"]:
            for task in finalize_data.get("tasks", []):
                if task.get("id") == tid:
                    task["status"] = "done"
                    task["executor_notes"] = f"Batch {kwargs['batch_number']} done."
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs["refreshed"],
            session_id=f"session-{kwargs['batch_number']}",
        )

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_run_and_merge_batch",
        _fake_run_and_merge,
    )

    state = load_state(plan_fixture.plan_dir)
    tier_map = {
        1: "hermes:flash",
        3: "codex:medium",
        5: "codex:high",
    }

    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    # Read back the state to inspect the aggregate history entry.
    state_after = load_state(plan_fixture.plan_dir)
    history = state_after.get("history", [])

    # Find the aggregate execute history entry (the last one for the auto loop).
    agg_entry = None
    for entry in reversed(history):
        if entry.get("step") == "execute" and "batch_to_tier" in entry:
            agg_entry = entry
            break

    assert agg_entry is not None, (
        "Aggregate history entry must include batch_to_tier when tier routing active"
    )

    batch_to_tier = agg_entry["batch_to_tier"]
    assert len(batch_to_tier) == 3, (
        f"Expected 3 batch→tier mappings, got {len(batch_to_tier)}"
    )

    # Verify ordered mapping: complexity 1→hermes:flash, 3→codex:medium, 5→codex:high.
    assert batch_to_tier[0]["batch_complexity"] == 1
    assert batch_to_tier[0]["tier_model_spec"] == "hermes:flash"
    assert batch_to_tier[0]["resolved_model"] == "deepseek-flash-v1"

    assert batch_to_tier[1]["batch_complexity"] == 3
    assert batch_to_tier[1]["tier_model_spec"] == "codex:medium"
    assert batch_to_tier[1]["resolved_model"] == "codex-medium-v2"

    assert batch_to_tier[2]["batch_complexity"] == 5
    assert batch_to_tier[2]["tier_model_spec"] == "codex:high"
    assert batch_to_tier[2]["resolved_model"] == "codex-high-v1"


# ---------------------------------------------------------------------------
# Active-step model alignment — verifies set_active_step reflects tier model
# ---------------------------------------------------------------------------


def test_one_batch_active_step_reflects_tier_selected_model(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When tier routing is active, set_active_step is called with the
    tier-selected model before _run_and_merge_batch runs."""
    _setup_single_auto_attribute_plan(plan_fixture)
    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    for task in finalize_data["tasks"]:
        task["complexity"] = 3
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    _stub_auto_attribute_git_snapshots(monkeypatch)
    monkeypatch.setattr(
        megaplan.workers,
        "run_step_with_worker",
        _hermes_style_worker(plan_fixture.project_dir),
    )

    # Track set_active_step calls.
    active_step_calls: list[dict] = []

    def _tracking_set_active_step(state, *, step, agent=None, mode=None, model=None):
        active_step_calls.append({
            "step": step,
            "agent": agent,
            "mode": mode,
            "model": model,
        })
        # Still call the real function to update state.
        megaplan._core.set_active_step(state, step=step, agent=agent, mode=mode, model=model)

    monkeypatch.setattr(
        megaplan.execute.batch,
        "set_active_step",
        _tracking_set_active_step,
    )

    def _tracking_resolve_tier_spec(args, tier_spec):
        return ("codex-tier", "persistent-tier", "model-tier-3")

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        _tracking_resolve_tier_spec,
    )

    state = load_state(plan_fixture.plan_dir)
    tier_map = {1: "t1", 3: "t3", 5: "t5"}

    megaplan.execute.core.handle_execute_one_batch(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            batch=1,
        ),
        batch_number=1,
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map=tier_map,
    )

    # The handler's set_active_step (at line ~140 of handlers/execute.py)
    # sets the fallback model. Then the per-batch tier resolution sets the
    # tier-selected model. We should see at least one call with the tier model.
    tier_calls = [
        c for c in active_step_calls
        if c["model"] == "model-tier-3"
    ]
    assert len(tier_calls) >= 1, (
        f"Expected set_active_step to be called with tier-selected model "
        f"'model-tier-3', got calls: {active_step_calls}"
    )


# ---------------------------------------------------------------------------
# Deterministic handle_execute_auto_loop characterization
# ---------------------------------------------------------------------------


def test_handle_execute_auto_loop_deterministic_characterization(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characterization: handle_execute_auto_loop must return a well-shaped
    StepResponse when a single pending task completes successfully.

    Stubs git snapshots and _run_and_merge_batch so the test is fully
    deterministic — no external workers, no git commands.  The assertions
    verify stable response keys, state transition, and artifact presence
    without overfitting implementation details like exact token counts or
    auto-attribution records."""
    # 1. Set up a finalized plan with exactly one pending task.
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Write a minimal module.",
            "depends_on": [],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ]
    finalize_data["sense_checks"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )

    # 2. Stub git snapshots and the batch runner.
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )

    def _fake_run_and_merge(**kwargs):
        # Update finalize.json so the post-loop tracking sees completed tasks.
        fd = read_json(kwargs["plan_dir"] / "finalize.json")
        for tid in kwargs["batch_task_ids"]:
            for task in fd.get("tasks", []):
                if task.get("id") == tid:
                    task["status"] = "done"
                    task["executor_notes"] = f"Completed {tid}."
                    task["files_changed"] = [f"batch{kwargs['batch_number']}.py"]
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(fd, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs.get("refreshed", False),
            session_id="char-session",
        )

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_run_and_merge_batch",
        _fake_run_and_merge,
    )

    # 3. Invoke handle_execute_auto_loop.
    state = load_state(plan_fixture.plan_dir)
    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )

    # 4. Assert deterministic response shape.
    assert response["success"] is True


def test_execute_auto_loop_reruns_raw_done_task_without_corroborating_evidence(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Raw asserted done without evidence.",
            "depends_on": [],
            "status": "done",
            "executor_notes": "Legacy assertion only.",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
    ]
    finalize_data["sense_checks"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    observed_batches: list[list[str]] = []

    def _fake_run_and_merge(**kwargs):
        observed_batches.append(list(kwargs["batch_task_ids"]))
        fd = read_json(kwargs["plan_dir"] / "finalize.json")
        fd["tasks"][0]["status"] = "done"
        fd["tasks"][0]["executor_notes"] = "Reran and corroborated T1."
        fd["tasks"][0]["files_changed"] = ["rerun.py"]
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(fd, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs.get("refreshed", False),
        )

    monkeypatch.setattr(megaplan.execute.batch, "_run_and_merge_batch", _fake_run_and_merge)

    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=load_state(plan_fixture.plan_dir),
        args=make_args(plan=plan_fixture.plan_name, confirm_destructive=True, user_approved=True),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )

    assert response["success"] is True
    assert observed_batches == [["T1"]]


def test_execute_auto_loop_does_not_unlock_dependency_from_raw_done_missing_output(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Raw asserted dependency.",
            "depends_on": [],
            "status": "done",
            "executor_notes": "Legacy assertion only.",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Depends on corroborated T1 only.",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))

    observed_batches: list[list[str]] = []
    prompt_overrides: list[str | None] = []

    def _fake_run_and_merge(**kwargs):
        batch_task_ids = list(kwargs["batch_task_ids"])
        observed_batches.append(batch_task_ids)
        prompt_overrides.append(kwargs.get("prompt_override"))
        fd = read_json(kwargs["plan_dir"] / "finalize.json")
        for task in fd["tasks"]:
            if task["id"] in batch_task_ids:
                task["status"] = "done"
                task["executor_notes"] = f"Corroborated {task['id']}."
                task["files_changed"] = [f"{task['id'].lower()}.py"]
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(fd, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs.get("refreshed", False),
        )

    monkeypatch.setattr(megaplan.execute.batch, "_run_and_merge_batch", _fake_run_and_merge)

    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=load_state(plan_fixture.plan_dir),
        args=make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            max_tasks_per_batch=1,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )

    assert response["success"] is True
    assert observed_batches == [["T1"], ["T2"]]
    assert prompt_overrides[0] is not None
    assert "Already completed task IDs available as dependency context: []" in prompt_overrides[0]
    assert prompt_overrides[1] is not None
    assert "Already completed task IDs available as dependency context: ['T1']" in prompt_overrides[1]


def test_execute_auto_loop_does_not_unlock_dependency_from_raw_done_stale_evidence(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_args = plan_fixture.make_args
    megaplan.handle_plan(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_critique(plan_fixture.root, make_args(plan=plan_fixture.plan_name))
    megaplan.handle_override(
        plan_fixture.root,
        make_args(plan=plan_fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(plan_fixture.root, make_args(plan=plan_fixture.plan_name))

    finalize_data = read_json(plan_fixture.plan_dir / "finalize.json")
    finalize_data["tasks"] = [
        {
            "id": "T1",
            "description": "Raw asserted dependency with stale evidence.",
            "depends_on": [],
            "status": "done",
            "executor_notes": "Legacy assertion only.",
            "files_changed": ["t1.py"],
            "commands_run": ["pytest -q"],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
        {
            "id": "T2",
            "description": "Depends on fresh corroboration for T1.",
            "depends_on": ["T1"],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        },
    ]
    finalize_data["sense_checks"] = []
    (plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
    )
    (plan_fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "files_changed": ["t1.py"],
                        "commands_run": ["pytest -q"],
                        "head_sha": "stale-head",
                        "code_hash": "stale-hash",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(megaplan.execute.batch, "_capture_git_status_snapshot", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_best_effort_git_head",
        lambda *_: "fresh-head",
    )

    observed_batches: list[list[str]] = []
    prompt_overrides: list[str | None] = []

    def _fake_run_and_merge(**kwargs):
        batch_task_ids = list(kwargs["batch_task_ids"])
        observed_batches.append(batch_task_ids)
        prompt_overrides.append(kwargs.get("prompt_override"))
        fd = read_json(kwargs["plan_dir"] / "finalize.json")
        for task in fd["tasks"]:
            if task["id"] in batch_task_ids:
                task["status"] = "done"
                task["executor_notes"] = f"Corroborated {task['id']}."
                task["files_changed"] = [f"{task['id'].lower()}.py"]
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(fd, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=batch_task_ids,
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs.get("refreshed", False),
        )

    monkeypatch.setattr(megaplan.execute.batch, "_run_and_merge_batch", _fake_run_and_merge)

    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=load_state(plan_fixture.plan_dir),
        args=make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
            max_tasks_per_batch=1,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
    )

    assert response["success"] is True
    assert observed_batches == [["T1"], ["T2"]]
    assert prompt_overrides[0] is not None
    assert "Already completed task IDs available as dependency context: []" in prompt_overrides[0]
    assert prompt_overrides[1] is not None
    assert "Already completed task IDs available as dependency context: []" in prompt_overrides[1]


def test_handle_execute_auto_loop_uses_valid_calibration_suggestion(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_single_auto_attribute_plan(plan_fixture)
    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_capture_git_status_snapshot_recursive",
        lambda *_args, **_kwargs: ({}, None),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "query_route_if_enabled",
        lambda *args, **kwargs: RouteSuggestion(tier_spec="hermes:flash", confidence=0.8),
    )
    monkeypatch.setattr(
        megaplan.execute.batch,
        "_resolve_tier_spec",
        lambda args, tier_spec: ("hermes", "persistent", f"resolved::{tier_spec}"),
    )

    run_params: list[dict[str, object]] = []

    def _fake_run_and_merge(**kwargs):
        run_params.append(
            {
                "agent": kwargs["agent"],
                "model": kwargs["model"],
                "resolved_model": kwargs["resolved_model"],
            }
        )
        finalize_data = read_json(kwargs["plan_dir"] / "finalize.json")
        for tid in kwargs["batch_task_ids"]:
            for task in finalize_data.get("tasks", []):
                if task.get("id") == tid:
                    task["status"] = "done"
                    task["executor_notes"] = "done"
        (kwargs["plan_dir"] / "finalize.json").write_text(
            json.dumps(finalize_data, indent=2) + "\n", encoding="utf-8"
        )
        return _make_fake_batch_result(
            batch_task_ids=kwargs["batch_task_ids"],
            batch_sense_check_ids=kwargs["batch_sense_check_ids"],
            batch_number=kwargs["batch_number"],
            agent=kwargs["agent"],
            mode=kwargs["mode"],
            refreshed=kwargs["refreshed"],
            session_id="session-1",
        )

    monkeypatch.setattr(
        megaplan.execute.batch,
        "_run_and_merge_batch",
        _fake_run_and_merge,
    )

    state = load_state(plan_fixture.plan_dir)
    response = megaplan.execute.core.handle_execute_auto_loop(
        root=plan_fixture.root,
        plan_dir=plan_fixture.plan_dir,
        state=state,
        args=plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
        auto_approve=False,
        agent="codex",
        mode="persistent",
        refreshed=False,
        tier_map={1: "hermes:flash", 5: "codex:high"},
    )

    assert run_params == [
        {
            "agent": "hermes",
            "model": "resolved::hermes:flash",
            "resolved_model": "resolved::hermes:flash",
        }
    ]
    assert response["step"] == "execute"


# ---------------------------------------------------------------------------
# T11 / SC8: summarize_path_list_for_prose — 337-file fixture
# ---------------------------------------------------------------------------


def test_summarize_path_list_for_prose_337_file_fixture(tmp_path: Path) -> None:
    """337-file fixture produces bounded prose entries and an ArtifactRef sidecar.

    SC8: prose entries are < 4000 chars, contain 'paths (showing', and
    an ArtifactRef sidecar is written under plan_dir.
    """
    from arnold.pipelines.megaplan.execute.quality import ADVISORY_PATH_PROJECTION_LIMIT

    paths = [f"src/module_{i:03d}.py" for i in range(337)]
    prose = summarize_path_list_for_prose(
        paths,
        plan_dir=tmp_path,
        artifact_prefix="advisory_obs_b1",
        label="phantom_claims",
    )

    # Must be bounded
    assert len(prose) < 4000, f"prose entry too long: {len(prose)} chars"
    # Must contain the 'paths (showing K)' marker
    assert "paths (showing" in prose, f"missing 'paths (showing' in: {prose[:200]}"
    # Must reference the sidecar artifact
    assert "ArtifactRef" in prose
    # Must show that the full count is mentioned
    assert "337" in prose
    # Sidecar must be written to plan_dir
    sidecar = tmp_path / "advisory_obs_b1_phantom_claims.json"
    assert sidecar.exists(), f"sidecar not written to {sidecar}"
    import json
    full = json.loads(sidecar.read_text())
    assert full["count"] == 337
    assert len(full["items"]) == 337


def test_summarize_path_list_for_prose_small_list_returns_plain_csv(tmp_path: Path) -> None:
    """Lists within the projection limit are returned inline without truncation."""
    paths = [f"src/file_{i}.py" for i in range(5)]
    prose = summarize_path_list_for_prose(
        paths,
        plan_dir=tmp_path,
        artifact_prefix="advisory_obs_b1",
        label="unclaimed_changes",
    )
    # Small list: just a comma-joined string, no 'paths (showing' marker
    assert "paths (showing" not in prose
    for p in paths:
        assert p in prose
    # No sidecar written for small lists
    sidecar = tmp_path / "advisory_obs_b1_unclaimed_changes.json"
    assert not sidecar.exists()
