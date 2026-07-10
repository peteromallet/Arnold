from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.completion_contract import (
    CompletionContext,
    CompletionSubject,
    EvidenceStatus,
    GreenSuiteProvider,
    WorkerDidWorkProvider,
    compute_verdict,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import _pytest_command


def _ctx(tmp_path, state):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")
    return CompletionContext(
        plan_dir=plan_dir,
        project_dir=tmp_path,
        state=state,
        subject=CompletionSubject(kind="plan", name="p", to_state="done"),
        git_base_ref=None,
    )


def test_green_suite_backfills_scoped_command_from_finalize_selection(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path)}})
    (ctx.plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_command": None,
                "test_selection": {
                    "command_override": "pytest tests/test_narrow.py",
                },
            }
        ),
        encoding="utf-8",
    )

    config, _timeout = GreenSuiteProvider._suite_config_and_timeout(ctx)

    assert config["test_command"] == "pytest tests/test_narrow.py"
    assert config["plan_dir"] == str(ctx.plan_dir)


def test_worker_did_work_reads_execute_batch_artifacts_without_provider_crash(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path)}})
    (ctx.plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "commands_run": ["pytest -q tests/test_narrow.py"],
                        "files_changed": ["src/app.py"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    evidence = WorkerDidWorkProvider().collect(ctx)

    assert evidence.status is EvidenceStatus.satisfied
    assert evidence.details["commands_run"] == 1
    assert evidence.details["files_changed"] == 1


def test_green_suite_prefers_recorded_baseline_command(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path)}})
    (ctx.plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_command": "pytest tests/test_baseline.py",
                "test_selection": {
                    "command_override": "pytest tests/test_selection.py",
                },
            }
        ),
        encoding="utf-8",
    )

    config, _timeout = GreenSuiteProvider._suite_config_and_timeout(ctx)

    assert config["test_command"] == "pytest tests/test_baseline.py"


def test_pytest_command_uses_current_python_for_default_and_bare_pytest():
    default_parts = shlex.split(_pytest_command(None))
    explicit_parts = shlex.split(_pytest_command("pytest tests/test_narrow.py"))

    assert default_parts[:3] == [sys.executable, "-m", "pytest"]
    assert explicit_parts[:4] == [sys.executable, "-m", "pytest", "tests/test_narrow.py"]


def _write_execute_acceptance_contract(plan_dir: Path) -> None:
    (plan_dir / "gate.json").write_text(
        json.dumps(
            {
                "signals": {
                    "execution_acceptance_contract": {
                        "scope": "execute",
                        "verification_mode": "verification_suite",
                        "required_checks": [
                            {
                                "id": "route-metadata",
                                "reason": "must be validated during execute",
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _append_suite_run(
    plan_dir: Path,
    project_dir: Path,
    *,
    phase: str,
    status: str,
    collected: int,
    failures: list[str] | None = None,
    passes: list[str] | None = None,
) -> None:
    from arnold_pipelines.megaplan.orchestration.suite_runs_log import append_suite_run
    from arnold_pipelines.megaplan.orchestration.suite_runner import (
        SuiteRunResult,
        _compute_code_hash,
    )

    raw_log = plan_dir / "verification" / f"{phase}-{status}.log"
    raw_log.parent.mkdir(parents=True, exist_ok=True)
    raw_log.write_text("", encoding="utf-8")
    append_suite_run(
        plan_dir,
        SuiteRunResult(
            run_id=f"{phase}-{status}",
            phase=phase,
            command="pytest -q",
            duration=0.1,
            collected=collected,
            collected_ids=["tests/test_acceptance.py::test_contract"] if collected else [],
            failures=failures or [],
            passes=passes or ([] if not collected else ["tests/test_acceptance.py::test_contract"]),
            status=status,
            exit_code=0 if status in {"passed", "not_applicable"} else 1,
            raw_log_path=raw_log,
            code_hash=_compute_code_hash(project_dir, paths=["src"]),
            collections_parse_ok=True,
        ),
    )


def test_execute_acceptance_contract_blocks_without_verification_coverage(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path), "source_globs": ["src"]}})
    _write_execute_acceptance_contract(ctx.plan_dir)
    _append_suite_run(
        ctx.plan_dir,
        tmp_path,
        phase="verification",
        status="not_applicable",
        collected=0,
    )

    verdict = compute_verdict(
        plan_dir=ctx.plan_dir,
        project_dir=tmp_path,
        state=ctx.state,
        subject=ctx.subject,
    )

    assert verdict.accepted is False
    contract_ref = next(
        ref for ref in verdict.evidence if ref.kind == "execution_acceptance_contract"
    )
    assert contract_ref.status == EvidenceStatus.unsatisfied
    assert "requires verification evidence" in contract_ref.summary


def test_execute_acceptance_contract_passes_with_satisfied_suite(tmp_path):
    ctx = _ctx(tmp_path, {"config": {"project_dir": str(tmp_path), "source_globs": ["src"]}})
    _write_execute_acceptance_contract(ctx.plan_dir)
    _append_suite_run(
        ctx.plan_dir,
        tmp_path,
        phase="verification",
        status="passed",
        collected=1,
    )

    verdict = compute_verdict(
        plan_dir=ctx.plan_dir,
        project_dir=tmp_path,
        state=ctx.state,
        subject=ctx.subject,
    )

    contract_ref = next(
        ref for ref in verdict.evidence if ref.kind == "execution_acceptance_contract"
    )
    assert contract_ref.status == EvidenceStatus.satisfied
    assert verdict.accepted is True
