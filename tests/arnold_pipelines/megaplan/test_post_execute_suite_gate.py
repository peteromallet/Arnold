from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.execute import batch
from arnold_pipelines.megaplan.orchestration import suite_runner
from arnold_pipelines.megaplan.types import CliError


def test_post_execute_suite_preserves_admitted_command_and_collection_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"config": {"phase_timeout_seconds": 10_800}}),
        encoding="utf-8",
    )
    admitted_command = "python -m pytest tests/removed_contract_test.py"
    observed: dict[str, object] = {}

    def fake_run_suite(
        received_project_dir: Path,
        config: dict[str, object],
        *,
        phase: str,
        deadline_seconds: float | None,
        idle_seconds: float | None,
    ) -> suite_runner.SuiteRunResult:
        observed.update(
            project_dir=received_project_dir,
            command=config["test_command"],
            phase=phase,
            deadline_seconds=deadline_seconds,
            idle_seconds=idle_seconds,
        )
        return suite_runner.SuiteRunResult(
            run_id="collection-failure",
            phase=phase,
            command=str(config["test_command"]),
            duration=0.1,
            collected=0,
            collected_ids=[],
            failures=[],
            passes=[],
            status="failed",
            exit_code=2,
            raw_log_path=plan_dir / "collection-failure.log",
            code_hash="sha256:test",
            collections_parse_ok=True,
            collection_errors=["tests/removed_contract_test.py"],
        )

    monkeypatch.setattr(suite_runner, "run_suite", fake_run_suite)
    monkeypatch.setattr(batch.time, "monotonic", lambda: 100.0)

    with pytest.raises(CliError) as exc_info:
        batch._run_batch_validation_jobs(
            plan_dir=plan_dir,
            project_dir=project_dir,
            finalize_data={
                "baseline_test_failures": ["pytest_collection_error"],
                "validation_jobs": [
                    {
                        "id": "VJ1",
                        "kind": "post_execute_suite",
                        "command": admitted_command,
                        "timeout_seconds": 600,
                        "expected_exit_codes": [0],
                        "mutates": False,
                        "writes_files": False,
                    }
                ],
            },
            batch_task_ids=["T-final"],
            is_final_batch=True,
        )

    assert exc_info.value.code == "validation_job_failed"
    assert observed == {
        "project_dir": project_dir,
        "command": admitted_command,
        "phase": "m8a_validation",
        "deadline_seconds": 10_900.0,
        "idle_seconds": None,
    }
