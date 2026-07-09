from __future__ import annotations

import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.auto import _execute_completion_authority
from arnold_pipelines.megaplan.blocker_recovery import (
    _extract_nodeids,
    evaluate_blocker_recovery,
    find_synthetic_before_execute_gate,
)
from arnold_pipelines.megaplan.execute.batch import (
    _prerequisite_blocked_task_ids,
    _reset_stale_authority_done_tasks,
    _normalize_execute_capture_payload,
    _repair_missing_user_action_gate,
    _resolve_batch_artifact_number,
    _task_to_global_batch_number_map,
)
from arnold_pipelines.megaplan.execute.quality import _collect_execute_claimed_paths
from arnold_pipelines.megaplan.model_seam import _normalize_plan_capture_payload
from arnold_pipelines.megaplan.orchestration.plan_structure import (
    PLAN_STRUCTURE_REQUIRED_STEP_ISSUE,
    validate_plan_structure,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    _authority_divergence_payload,
    _evidence_from_task_record,
    AuthorityDecision,
    EvidenceStatus,
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.orchestration.execution_evidence import (
    validate_execution_evidence,
)
from arnold_pipelines.megaplan.orchestration.phase_result import Deviation
from arnold_pipelines.megaplan.orchestration.plan_contracts import (
    normalize_contract_payload,
    pre_existing_task_ids_from_contract,
)

_PYTEST_API_CMD = "pytest -q tests/arnold/workflow/test_source_compiler_api.py -q"


def _init_git_repo(root: Path) -> tuple[str, str]:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('base')\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/app.py"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    (root / "src" / "app.py").write_text("print('head')\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/app.py"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "head"], cwd=root, check=True, capture_output=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return base, head


def _make_execute_authority_plan(tmp_path: Path) -> tuple[Path, list[dict[str, object]], dict[str, object]]:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    base_sha, _head_sha = _init_git_repo(project_dir)
    plan_dir = project_dir / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state = {
        "config": {"project_dir": str(project_dir)},
        "meta": {"execution_baseline": {"head": base_sha}},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    tasks: list[dict[str, object]] = [
        {
            "id": "t6_add_focused_api_regressions",
            "status": "done",
            "kind": "code",
            "commands_run": [_PYTEST_API_CMD],
        },
        {
            "id": "v3_api_tests",
            "status": "pending",
            "kind": "test",
            "commands_run": [_PYTEST_API_CMD],
            "head_sha": base_sha,
        },
        {
            "id": "v4_optional_diagnostics_contract",
            "status": "skipped",
            "kind": "test",
            "executor_notes": "Skipped by contract: no diagnostic registry or keyword contract changed.",
            "head_sha": base_sha,
        },
    ]
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": tasks}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "t6_add_focused_api_regressions",
                        "status": "done",
                        "commands_run": [_PYTEST_API_CMD],
                        "head_sha": base_sha,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_dir, tasks, state


def test_stale_recorded_test_failure_blocker_drops_when_nodeid_now_passes(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_example.py").write_text(
        "def test_passes():\n    assert True\n", encoding="utf-8"
    )

    deviation = Deviation(
        kind="quality_gate",
        task_id="T1",
        message="tests/test_example.py::test_passes failed at baseline",
    )
    state = {
        "meta": {},
        "config": {"project_dir": str(project_dir), "test_command": "pytest"},
    }

    evaluation = evaluate_blocker_recovery({}, state, deviations=[deviation])

    assert _extract_nodeids(deviation.message) == (
        "tests/test_example.py::test_passes",
    )
    assert evaluation.blockers == ()
    assert evaluation.can_continue is True


def test_phase_coverage_authority_failure_surfaces_as_recovery_blocker(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "execution_batch_14.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T14",
                        "status": "done",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    evaluation = evaluate_blocker_recovery(
        {},
        {"meta": {}, "config": {}},
        plan_dir=plan_dir,
    )

    assert evaluation.can_continue is False
    assert [blocker.message for blocker in evaluation.blockers] == [
        "execution_batch_14.json has no corroborated completed task IDs"
    ]
    assert evaluation.blockers[0].blocker_kind == "quality"


def test_harness_artifact_paths_are_removed_from_execute_claims() -> None:
    payload = _normalize_execute_capture_payload(
        {
            "files_changed": ["src/app.py", ".megaplan/plans/run/state.json"],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "files_changed": ["./.megaplan/system_logs/log.json", "src/app.py"],
                    "evidence_files": [".megaplan/run-logs/out.txt", "evidence.md"],
                }
            ],
        }
    )

    assert payload["files_changed"] == ["src/app.py"]
    assert payload["task_updates"][0]["files_changed"] == ["src/app.py"]
    assert payload["task_updates"][0]["evidence_files"] == ["evidence.md"]
    assert _collect_execute_claimed_paths(
        {"files_changed": ["src/app.py", ".megaplan/plans/run/state.json"]}
    ) == {"src/app.py"}


def test_prerequisite_blocked_task_ids_excludes_harness_generated_blocks() -> None:
    task_ids = _prerequisite_blocked_task_ids(
        [
            {
                "id": "T7",
                "status": "blocked",
                "executor_notes": (
                    "BLOCKED — no files modified.\n"
                    "[harness] status auto-downgraded: deviation contains budget exhausted"
                ),
            },
            {
                "id": "T8",
                "status": "blocked",
                "executor_notes": "Blocked by explicit prerequisite `ua-1`.",
            },
        ],
        active_task_ids={"T7", "T8"},
    )

    assert task_ids == {"T8"}


def test_pre_existing_contract_ids_skip_hollow_done_evidence(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "existing.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "existing.py"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "contract.json").write_text(
        json.dumps({"provides": [], "assumes": [], "pre_existing": ["T1"]}),
        encoding="utf-8",
    )

    audit = validate_execution_evidence(
        {
            "tasks": [
                {
                    "id": "T1",
                    "status": "done",
                    "files_changed": [],
                    "commands_run": [],
                    "executor_notes": "",
                }
            ],
            "sense_checks": [],
        },
        project_dir,
        plan_dir=plan_dir,
    )

    assert normalize_contract_payload({"pre_existing": ["T1", "  T2  ", ""]})[
        "pre_existing"
    ] == ["T1", "T2"]
    assert pre_existing_task_ids_from_contract({"pre_existing": ["T1"]}) == {"T1"}
    assert not any("done tasks" in finding.lower() for finding in audit["findings"])


def test_authority_reader_uses_current_head_when_task_omits_head_sha(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "file.txt").write_text("data\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_dir, text=True).strip()

    refs = _evidence_from_task_record(
        {"id": "T1", "status": "done", "files_changed": ["file.txt"]},
        project_dir / ".megaplan" / "plans" / "p" / "execution.json",
        root=project_dir,
    )

    assert refs
    assert refs[0].details["head_sha"] == head


def test_deferred_baseline_checkpoint_is_not_missing_execute_authority(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "skipped",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    ok, missing = _execute_completion_authority(plan_dir)

    assert ok is True
    assert missing == []


def test_effective_execute_completed_task_ids_accepts_execution_window_and_explained_skips(
    tmp_path: Path,
) -> None:
    plan_dir, tasks, state = _make_execute_authority_plan(tmp_path)

    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=plan_dir,
        project_dir=Path(state["config"]["project_dir"]),
        state=state,
    )

    assert completed >= {
        "t6_add_focused_api_regressions",
        "v3_api_tests",
        "v4_optional_diagnostics_contract",
    }


def test_authority_divergence_payload_ignores_explained_skips() -> None:
    task = {
        "id": "t_baseline_checkpoint",
        "status": "skipped",
        "reviewer_verdict": "deferred_baseline_unavailable",
    }
    decision = AuthorityDecision(
        task_id="t_baseline_checkpoint",
        status=EvidenceStatus.unknown,
        satisfied=False,
        would_block_reasons=("missing_linked_evidence",),
    )

    assert _authority_divergence_payload(task, decision) is None


def test_authority_divergence_payload_ignores_explained_noops() -> None:
    task = {
        "id": "t_optional_watchdog_regression",
        "status": "done",
        "executor_notes": "No code change needed because existing coverage already proves the signal.",
        "files_changed": [],
        "commands_run": [],
    }
    decision = AuthorityDecision(
        task_id="t_optional_watchdog_regression",
        status=EvidenceStatus.unknown,
        satisfied=False,
        would_block_reasons=("missing_linked_evidence",),
    )

    assert _authority_divergence_payload(task, decision) is None


def test_execute_completion_authority_uses_execution_window_and_explained_skips(
    tmp_path: Path,
) -> None:
    plan_dir, _tasks, _state = _make_execute_authority_plan(tmp_path)

    ok, missing = _execute_completion_authority(plan_dir)

    assert ok is True
    assert missing == []


def test_effective_execute_completed_task_ids_marks_explained_noops_authoritative(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    base_sha, _head_sha = _init_git_repo(project_dir)
    plan_dir = project_dir / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state = {
        "config": {"project_dir": str(project_dir)},
        "meta": {"execution_baseline": {"head": base_sha}},
    }
    tasks = [
        {
            "id": "T9",
            "status": "done",
            "kind": "test",
            "executor_notes": "No code change needed. Existing progress-auditor coverage already proves this signal.",
            "files_changed": [],
            "commands_run": [],
        }
    ]

    decisions: dict[str, AuthorityDecision] = {}
    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state,
        decisions=decisions,
    )

    assert completed == {"T9"}
    assert decisions["T9"].authoritative is True
    assert decisions["T9"].status == EvidenceStatus.satisfied
    assert decisions["T9"].diagnostics["execute_completion"] == "explained_noop_completion"


def test_reset_stale_authority_done_tasks_demotes_stale_terminal_successes(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    (project_dir / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=project_dir, check=True, capture_output=True)
    base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_dir, text=True).strip()
    (project_dir / "file.txt").write_text("observed\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "observed"], cwd=project_dir, check=True, capture_output=True)
    observed_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_dir, text=True).strip()
    subprocess.run(["git", "checkout", "-b", "diverged", base_sha], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "file.txt").write_text("diverged\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "diverged"], cwd=project_dir, check=True, capture_output=True)
    plan_dir = project_dir / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state = {
        "config": {"project_dir": str(project_dir)},
        "meta": {"execution_baseline": {"head": base_sha}},
    }
    finalize_data = {
        "tasks": [
            {
                "id": "T2",
                "status": "done",
                "kind": "audit",
                "commands_run": ["pytest tests/test_example.py -q"],
                "executor_notes": "Observed stale external state.",
                "head_sha": observed_head,
            }
        ]
    }
    (plan_dir / "finalize.json").write_text(json.dumps(finalize_data) + "\n", encoding="utf-8")
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T2",
                        "status": "done",
                        "commands_run": ["pytest tests/test_example.py -q"],
                        "head_sha": observed_head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    reset_ids = _reset_stale_authority_done_tasks(
        finalize_data,
        plan_dir=plan_dir,
        root=project_dir,
        state=state,
    )

    assert reset_ids == ["T2"]
    assert finalize_data["tasks"][0]["status"] == "pending"
    assert finalize_data["tasks"][0]["commands_run"] == []


def test_execute_completion_authority_prefers_fresh_execution_evidence_over_stale_finalize(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    (project_dir / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=project_dir, check=True, capture_output=True)
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=project_dir, text=True
    ).strip()

    plan_dir = project_dir / ".megaplan" / "plans" / "plan-mixed-evidence"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "config": {"project_dir": str(project_dir)},
                "meta": {"execution_baseline": {"head": current_head}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    task = {
        "id": "T1",
        "status": "done",
        "kind": "test",
        "commands_run": ["pytest tests/test_example.py -q"],
        "head_sha": "stale-head",
    }
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [task]}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "kind": "test",
                        "commands_run": ["pytest tests/test_example.py -q"],
                        "head_sha": current_head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, missing = _execute_completion_authority(plan_dir)

    assert ok is True
    assert missing == []


def test_execute_completion_authority_accepts_batch_corroboration_for_stale_done_finalize_row(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    (project_dir / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=project_dir, check=True, capture_output=True)
    execute_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=project_dir, text=True
    ).strip()

    plan_dir = project_dir / ".megaplan" / "plans" / "plan-batch-corroboration"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"config": {"project_dir": str(project_dir)}}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "test",
                        "commands_run": ["pytest tests/test_example.py -q"],
                        "head_sha": "stale-head",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "kind": "test",
                        "commands_run": ["pytest tests/test_example.py -q"],
                        "head_sha": execute_head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (project_dir / "after.txt").write_text("after\n", encoding="utf-8")
    subprocess.run(["git", "add", "after.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "after"], cwd=project_dir, check=True, capture_output=True)

    ok, missing = _execute_completion_authority(plan_dir)

    assert ok is True
    assert missing == []


def test_validate_execution_evidence_ignores_stale_pending_finalize_rows(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    (project_dir / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=project_dir, check=True, capture_output=True)
    current_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=project_dir, text=True
    ).strip()

    plan_dir = project_dir / ".megaplan" / "plans" / "plan-stale-finalize-audit"
    plan_dir.mkdir(parents=True)
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T11",
                        "status": "done",
                        "kind": "code",
                        "files_changed": ["file.txt"],
                        "head_sha": current_head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    audit = validate_execution_evidence(
        {
            "tasks": [
                {
                    "id": "T11",
                    "status": "pending",
                    "kind": "code",
                    "executor_notes": "Stale finalize snapshot before execute batch reconciliation.",
                }
            ],
            "sense_checks": [],
        },
        project_dir,
        plan_dir=plan_dir,
    )

    assert not any(
        "Tasks left pending after execute" in finding for finding in audit["findings"]
    )


def test_execute_completion_authority_accepts_explained_noop_done_task(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = project_dir / ".megaplan" / "plans" / "plan-explained-noop"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"config": {"project_dir": str(project_dir)}}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "executor_notes": (
                            "No code change needed. The existing progress-auditor "
                            "fixture already covers this case at the correct layer."
                        ),
                        "files_changed": [],
                        "commands_run": [],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, missing = _execute_completion_authority(plan_dir)

    assert ok is True
    assert missing == []


def test_execute_completion_authority_prefers_recorded_head_when_repo_head_moved_elsewhere(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    (project_dir / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=project_dir, check=True, capture_output=True)
    baseline_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=project_dir, text=True
    ).strip()

    plan_dir = project_dir / ".megaplan" / "plans" / "plan-head-drift"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "config": {"project_dir": str(project_dir)},
                "meta": {"execution_baseline": {"head": baseline_head}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "kind": "test",
                        "commands_run": ["pytest tests/test_example.py -q"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "kind": "test",
                        "commands_run": ["pytest tests/test_example.py -q"],
                        "head_sha": baseline_head,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "checkout", "--orphan", "other-branch"], cwd=project_dir, check=True)
    subprocess.run(["git", "rm", "-rf", "."], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "other.txt").write_text("other\n", encoding="utf-8")
    subprocess.run(["git", "add", "other.txt"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "unrelated"], cwd=project_dir, check=True, capture_output=True
    )

    ok, missing = _execute_completion_authority(plan_dir)

    assert ok is True
    assert missing == []


def test_find_synthetic_before_execute_gate_ignores_baseline_checkpoint_root() -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Introduce no new failures vs the recorded baseline;",
                "depends_on": [],
                "status": "skipped",
            },
            {
                "id": "m7-01",
                "description": "Real work.",
                "depends_on": ["T1"],
                "status": "done",
            },
            {
                "id": "m7-02",
                "description": "More work.",
                "depends_on": ["T1", "m7-01"],
                "status": "pending",
            },
        ]
    }

    assert find_synthetic_before_execute_gate(finalize_data) == (None, ())


def test_execute_repairs_missing_user_action_gate_for_stale_finalize(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = project_dir / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    state = {
        "config": {
            "mode": "code",
            "project_dir": str(project_dir),
        }
    }
    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "description": "Introduce no new failures vs the recorded baseline;",
                "depends_on": [],
                "status": "skipped",
                "reviewer_verdict": "deferred_baseline_unavailable",
            },
            {
                "id": "m7-06-runtime-deletion-target-purge",
                "description": "Delete runtime targets.",
                "depends_on": ["T1"],
                "status": "blocked",
            },
        ],
        "sense_checks": [],
        "watch_items": [],
        "user_actions": [
            {
                "id": "ua-01-reclassify-deletion-targets",
                "description": "Confirm the deletion contract is authoritative.",
                "phase": "before_execute",
                "blocks_task_ids": ["m7-06-runtime-deletion-target-purge"],
                "rationale": "Needed before destructive deletion proceeds.",
                "requires_human_only_reason": "Maintainer decision.",
            }
        ],
    }

    repaired = _repair_missing_user_action_gate(finalize_data, plan_dir, state)

    assert repaired is True
    assert finalize_data["tasks"][0]["description"].startswith("Read user_actions.md.")
    assert finalize_data["tasks"][0]["id"] == "T2"
    assert finalize_data["tasks"][1]["id"] == "T1"
    assert finalize_data["tasks"][2]["id"] == "m7-06-runtime-deletion-target-purge"
    assert "T2" in finalize_data["tasks"][1]["depends_on"]
    assert "T2" in finalize_data["tasks"][2]["depends_on"]
    assert find_synthetic_before_execute_gate(finalize_data) == (
        "T2",
        ("T1", "m7-06-runtime-deletion-target-purge"),
    )
    assert (plan_dir / "finalize.json").is_file()
    assert (plan_dir / "user_actions.md").read_text(encoding="utf-8").startswith(
        "# User Actions"
    )


def test_structured_plan_payload_normalizes_to_canonical_schema() -> None:
    normalized = _normalize_plan_capture_payload(
        {
            "title": "Ship Fix",
            "overview": "Do the work.",
            "steps": [{"title": "Patch", "substeps": [{"instruction": "Edit file"}]}],
            "questions": [{"question": "Any blockers?"}],
            "success_criteria": [{"criterion": "Tests pass", "priority": "must"}],
            "assumptions": [{"assumption": "Repo is clean"}],
            "changed_surfaces": ["src/thing.py"],
            "test_blast_radius": {
                "strategy": "scoped",
                "selectors": [{"kind": "path", "value": "tests/test_thing.py"}],
            },
        }
    )

    assert "# Ship Fix" in normalized["plan"]
    assert "### Step 1: Patch" in normalized["plan"]
    assert "- Edit file" in normalized["plan"]
    assert PLAN_STRUCTURE_REQUIRED_STEP_ISSUE not in validate_plan_structure(
        normalized["plan"]
    )
    assert normalized["questions"] == ["Any blockers?"]
    assert normalized["success_criteria"] == [
        {"criterion": "Tests pass", "priority": "must", "requires": ["run_tests"]}
    ]
    assert normalized["assumptions"] == ["Repo is clean"]
    assert normalized["changed_surfaces"] == ["src/thing.py"]
    assert normalized["test_blast_radius"]["strategy"] == "scoped"


def test_resumed_partial_batch_keeps_original_artifact_number() -> None:
    global_batches = [
        ["T2"],
        ["T1"],
        ["m7-01"],
        ["m7-02", "m7-05"],
        ["m7-03", "m7-06"],
        ["m7-04", "m7-07", "m7-10"],
        ["m7-08"],
    ]
    global_batch_lookup = {
        tuple(batch): index + 1 for index, batch in enumerate(global_batches)
    }

    artifact_number = _resolve_batch_artifact_number(
        ["m7-07"],
        global_batch_lookup=global_batch_lookup,
        task_to_batch_number=_task_to_global_batch_number_map(global_batches),
        batch_index=1,
    )

    assert artifact_number == 6
