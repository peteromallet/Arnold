from __future__ import annotations

import json
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.auto import _execute_completion_authority
from arnold_pipelines.megaplan.blocker_recovery import (
    _extract_nodeids,
    evaluate_blocker_recovery,
)
from arnold_pipelines.megaplan.execute.batch import _normalize_execute_capture_payload
from arnold_pipelines.megaplan.execute.quality import _collect_execute_claimed_paths
from arnold_pipelines.megaplan.model_seam import _normalize_plan_capture_payload
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    _evidence_from_task_record,
)
from arnold_pipelines.megaplan.orchestration.execution_evidence import (
    validate_execution_evidence,
)
from arnold_pipelines.megaplan.orchestration.phase_result import Deviation
from arnold_pipelines.megaplan.orchestration.plan_contracts import (
    normalize_contract_payload,
    pre_existing_task_ids_from_contract,
)


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
        {"id": "T1", "files_changed": ["file.txt"]},
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


def test_structured_plan_payload_normalizes_to_canonical_schema() -> None:
    normalized = _normalize_plan_capture_payload(
        {
            "title": "Ship Fix",
            "overview": "Do the work.",
            "steps": [{"title": "Patch", "substeps": [{"instruction": "Edit file"}]}],
            "questions": [{"question": "Any blockers?"}],
            "success_criteria": [{"criterion": "Tests pass", "priority": "must"}],
            "assumptions": [{"assumption": "Repo is clean"}],
        }
    )

    assert "# Ship Fix" in normalized["plan"]
    assert "- Edit file" in normalized["plan"]
    assert normalized["questions"] == ["Any blockers?"]
    assert normalized["success_criteria"] == [
        {"criterion": "Tests pass", "priority": "must", "requires": ["run_tests"]}
    ]
    assert normalized["assumptions"] == ["Repo is clean"]
