from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.completion_contract import (
    CompletionSubject,
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
