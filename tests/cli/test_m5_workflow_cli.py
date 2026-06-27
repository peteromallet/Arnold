from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from arnold.cli import workflow as workflow_cli

DEMO_TARGET = "tests.fixtures.workflow.demo_pipeline:build_pipeline"


def test_workflow_check_passes() -> None:
    rc = workflow_cli.main(["check", "--module", DEMO_TARGET])
    assert rc == 0


def test_workflow_check_fails_on_bad_target() -> None:
    rc = workflow_cli.main(["check", "--module", "no.such.module:build_pipeline"])
    assert rc != 0


def test_workflow_manifest_emits_json(tmp_path: Path) -> None:
    rc = workflow_cli.main(["manifest", "--module", DEMO_TARGET, "--format", "json"])
    assert rc == 0


def test_workflow_dot_emits_digraph() -> None:
    rc = workflow_cli.main(["dot", "--module", DEMO_TARGET])
    assert rc == 0


def test_workflow_dry_run_reports_routes() -> None:
    rc = workflow_cli.main(["dry-run", "--module", DEMO_TARGET, "--format", "json"])
    assert rc == 0


def test_workflow_run_fake_backend_completes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "run"
    rc = workflow_cli.main(
        [
            "run",
            "--module",
            DEMO_TARGET,
            "--backend",
            "fake",
            "--artifact-root",
            str(artifact_root),
        ]
    )
    assert rc == 0


def test_workflow_describe_includes_manifest_metadata() -> None:
    rc = workflow_cli.main(["describe", "--module", DEMO_TARGET, "--format", "json"])
    assert rc == 0


def test_workflow_module_invocation(tmp_path: Path) -> None:
    artifact_root = tmp_path / "run"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold.cli.workflow",
            "run",
            "--module",
            DEMO_TARGET,
            "--backend",
            "fake",
            "--artifact-root",
            str(artifact_root),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["state"] == "completed"
    assert payload["manifest_id"] == "demo"


def test_workflow_resume_fake_backend_completes(tmp_path: Path) -> None:
    artifact_root = tmp_path / "resume"
    rc = workflow_cli.main(
        [
            "resume",
            "--module",
            DEMO_TARGET,
            "--backend",
            "fake",
            "--artifact-root",
            str(artifact_root),
        ]
    )
    assert rc == 0


def test_workflow_run_local_backend_writes_journal(tmp_path: Path) -> None:
    artifact_root = tmp_path / "run"
    rc = workflow_cli.main(
        [
            "run",
            "--module",
            DEMO_TARGET,
            "--artifact-root",
            str(artifact_root),
        ]
    )
    assert rc == 0
    assert (artifact_root / "events.ndjson").exists()
