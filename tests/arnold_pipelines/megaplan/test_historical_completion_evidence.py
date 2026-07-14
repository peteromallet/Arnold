from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.chain.spec import ChainSpec, ChainState, MilestoneSpec
from arnold_pipelines.megaplan._core.io import atomic_write_json, execute_batch_artifact_path
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    CompletionContext,
    CompletionSubject,
    GreenSuiteProvider,
    LandedDiffProvider,
    compute_verdict,
)
from arnold_pipelines.megaplan.orchestration.suite_runner import run_suite


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _commit(root: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return _git(root, "rev-parse", "HEAD")


def test_landed_diff_binds_historical_head_not_later_checkout_head(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    base = _commit(root, "base")
    (root / "milestone.py").write_text("MILESTONE = True\n", encoding="utf-8")
    landed_head = _commit(root, "milestone (#12)")
    (root / "successor.py").write_text("SUCCESSOR = True\n", encoding="utf-8")
    _commit(root, "later successor")

    plan_dir = root / ".megaplan" / "plans" / "historical"
    plan_dir.mkdir(parents=True)
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "files_changed": ["milestone.py"],
                        "executor_notes": "Implemented the milestone change.",
                    }
                ],
                "sense_checks": [],
            }
        ),
        encoding="utf-8",
    )

    verdict = compute_verdict(
        plan_dir=plan_dir,
        project_dir=root,
        state={"config": {"mode": "code"}},
        subject=CompletionSubject(kind="milestone", name="m1", to_state="done"),
        mode="enforce",
        providers=(LandedDiffProvider(),),
        git_base_ref=base,
        git_head_ref=landed_head,
    )

    assert verdict.accepted is True
    details = verdict.evidence[0].details
    assert details["evidence_window"]["head_sha"] == landed_head
    assert details["files_in_committed_range"] == ["milestone.py"]
    assert "successor.py" not in details["files_in_diff"]


def test_chain_verify_uses_recorded_milestone_base_for_squash_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    main_base = _commit(root, "main base")
    main_branch = _git(root, "branch", "--show-current")

    subprocess.run(["git", "checkout", "-b", "feature"], cwd=root, check=True, capture_output=True)
    (root / "preexisting-repair.py").write_text("REPAIRED = True\n", encoding="utf-8")
    milestone_base = _commit(root, "repair present before milestone")
    (root / "milestone.py").write_text("MILESTONE = True\n", encoding="utf-8")
    _commit(root, "milestone work")

    subprocess.run(["git", "checkout", main_branch], cwd=root, check=True, capture_output=True)
    assert _git(root, "rev-parse", "HEAD") == main_base
    subprocess.run(["git", "merge", "--squash", "feature"], cwd=root, check=True, capture_output=True)
    landed_head = _commit(root, "milestone (#12)")

    plan_dir = root / ".megaplan" / "plans" / "historical"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "config": {"mode": "code", "project_dir": str(root)},
                "meta": {"chain_policy": {"milestone_base_sha": milestone_base}},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "files_changed": ["milestone.py"],
                        "executor_notes": "Implemented the milestone change.",
                    }
                ],
                "sense_checks": [],
            }
        ),
        encoding="utf-8",
    )

    payload = chain_module._verify_completed_chain(
        root,
        root / "chain.yaml",
        ChainSpec(milestones=[MilestoneSpec(label="m1", idea="m1.md")]),
        ChainState(
            completion_contract_mode="enforce",
            completed=[
                {
                    "label": "m1",
                    "plan": "historical",
                    "status": "done",
                    "landed_head_sha": landed_head,
                }
            ],
        ),
    )

    assert payload["divergence_count"] == 0
    milestone = payload["milestones"][0]
    assert milestone["accepted"] is True
    assert milestone["evidence_window"]["base_sha"] == milestone_base
    assert milestone["files_in_committed_range"] == ["milestone.py"]
    assert "preexisting-repair.py" not in milestone["files_in_diff"]


def test_chain_verify_uses_landed_parent_when_target_advanced(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    milestone_base = _commit(root, "milestone base")
    main_branch = _git(root, "branch", "--show-current")

    subprocess.run(["git", "checkout", "-b", "feature"], cwd=root, check=True, capture_output=True)
    (root / "milestone.py").write_text("MILESTONE = True\n", encoding="utf-8")
    _commit(root, "milestone work")

    subprocess.run(["git", "checkout", main_branch], cwd=root, check=True, capture_output=True)
    (root / "unrelated-main.py").write_text("UNRELATED = True\n", encoding="utf-8")
    landed_parent = _commit(root, "unrelated target branch work")
    subprocess.run(["git", "merge", "--squash", "feature"], cwd=root, check=True, capture_output=True)
    landed_head = _commit(root, "milestone (#13)")

    plan_dir = root / ".megaplan" / "plans" / "historical"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "config": {"mode": "code", "project_dir": str(root)},
                "meta": {"chain_policy": {"milestone_base_sha": milestone_base}},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "files_changed": ["milestone.py"],
                        "executor_notes": "Implemented the milestone change.",
                    }
                ],
                "sense_checks": [],
            }
        ),
        encoding="utf-8",
    )

    payload = chain_module._verify_completed_chain(
        root,
        root / "chain.yaml",
        ChainSpec(milestones=[MilestoneSpec(label="m1", idea="m1.md")]),
        ChainState(
            completion_contract_mode="enforce",
            completed=[
                {
                    "label": "m1",
                    "plan": "historical",
                    "status": "done",
                    "landed_head_sha": landed_head,
                }
            ],
        ),
    )

    assert payload["divergence_count"] == 0
    milestone = payload["milestones"][0]
    assert milestone["accepted"] is True
    assert milestone["evidence_window"]["base_sha"] == landed_parent
    assert milestone["diff_base_source"] == "landed_parent_after_milestone_base"
    assert milestone["files_in_committed_range"] == ["milestone.py"]
    assert "unrelated-main.py" not in milestone["files_in_diff"]


def test_exact_head_batch_supersedes_stale_finalize_task_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    base = _commit(root, "base")
    (root / "milestone.py").write_text("MILESTONE = True\n", encoding="utf-8")
    stale_head = _commit(root, "execution head")
    (root / "milestone.py").write_text("MILESTONE = 'landed'\n", encoding="utf-8")
    landed_head = _commit(root, "landed head")

    plan_dir = root / ".megaplan" / "plans" / "historical"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "config": {"mode": "code", "project_dir": str(root)},
                "meta": {"chain_policy": {"milestone_base_sha": base}},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "commands_run": ["python stale_check.py"],
                        "executor_notes": "Original evidence at the execution head.",
                        "head_sha": stale_head,
                    }
                ],
                "sense_checks": [],
            }
        ),
        encoding="utf-8",
    )
    artifact = execute_batch_artifact_path(plan_dir, 1, ["T1"])
    atomic_write_json(
        artifact,
        {
            "output": "Exact landed-head reconciliation passed.",
            "files_changed": [],
            "commands_run": ["python landed_check.py"],
            "deviations": [],
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "commands_run": ["python landed_check.py"],
                    "files_changed": [],
                    "executor_notes": "Reconciled at the landed head.",
                    "head_sha": landed_head,
                }
            ],
            "sense_check_acknowledgments": [],
            "head_sha": landed_head,
        },
        _plan_dir=plan_dir,
    )

    done, reason = chain_module._latest_execution_batch_all_tasks_done(
        plan_dir,
        project_dir_override=root,
        authoritative_head=landed_head,
    )

    assert done is True, reason


def test_suite_runner_imports_subject_checkout_before_editable_engine(
    tmp_path: Path, monkeypatch
) -> None:
    subject = tmp_path / "subject"
    engine = tmp_path / "engine"
    subject.mkdir()
    engine.mkdir()
    (subject / "subject_module.py").write_text("VALUE = 'subject'\n", encoding="utf-8")
    (engine / "subject_module.py").write_text("VALUE = 'engine'\n", encoding="utf-8")
    (subject / "test_subject.py").write_text(
        "import subject_module\n\n"
        "def test_subject_root_wins():\n"
        "    assert subject_module.VALUE == 'subject'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(engine))

    result = run_suite(
        subject,
        {"test_command": "pytest test_subject.py", "plan_dir": str(subject / ".plan")},
        phase="verification",
        deadline_seconds=time.monotonic() + 60,
    )

    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.failures == []


def test_failed_plan_resume_uses_plan_phase_timeout(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        chain_module,
        "_plan_current_state_from_payload",
        lambda root, plan: "failed",
    )

    def fake_run_command(root, cmd, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(chain_module, "_run_command", fake_run_command)

    chain_module._recover_failed_plan_before_drive(
        tmp_path,
        "historical-plan",
        writer=lambda message: None,
    )

    assert observed["timeout"] == 1800


def test_verification_does_not_reuse_legacy_short_baseline_timeout(
    tmp_path: Path,
) -> None:
    ctx = CompletionContext(
        plan_dir=tmp_path / "plan",
        project_dir=tmp_path,
        state={"config": {"test_baseline_timeout": 900}},
        subject=CompletionSubject(kind="plan", name="p", to_state="done"),
    )

    _config, timeout = GreenSuiteProvider._suite_config_and_timeout(ctx)

    assert timeout == 3600
