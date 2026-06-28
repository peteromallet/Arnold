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
    _normalize_execute_capture_payload,
    _repair_missing_user_action_gate,
)
from arnold_pipelines.megaplan.execute.quality import _collect_execute_claimed_paths
from arnold_pipelines.megaplan.model_seam import _normalize_plan_capture_payload
from arnold_pipelines.megaplan.orchestration.plan_structure import (
    PLAN_STRUCTURE_REQUIRED_STEP_ISSUE,
    validate_plan_structure,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    _evidence_from_task_record,
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


def test_execute_completion_authority_uses_execution_window_and_explained_skips(
    tmp_path: Path,
) -> None:
    plan_dir, _tasks, _state = _make_execute_authority_plan(tmp_path)

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
