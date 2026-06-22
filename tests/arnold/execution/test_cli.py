"""CLI tests for T25-T26."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from arnold.cli.execution import main
from arnold.manifest import WorkflowManifest, WorkflowNode


def _manifest_json(tmp_path: Path, nodes: list[WorkflowNode]) -> Path:
    manifest = WorkflowManifest(id="cli-demo", nodes=tuple(nodes))
    path = tmp_path / "manifest.json"
    path.write_text(manifest.to_json(), encoding="utf-8")
    return path


def test_cli_run_manifest_completes(tmp_path: Path) -> None:
    manifest_path = _manifest_json(tmp_path, [WorkflowNode(id="a", kind="noop")])
    artifact_root = tmp_path / "artifacts"

    rc = main(["run-manifest", "--manifest", str(manifest_path), "--artifact-root", str(artifact_root)])

    assert rc == 0
    assert (artifact_root / "events.ndjson").exists()


def test_cli_run_manifest_with_state_store(tmp_path: Path) -> None:
    manifest_path = _manifest_json(tmp_path, [WorkflowNode(id="a", kind="noop")])
    artifact_root = tmp_path / "artifacts"
    state_store_dir = tmp_path / "runs"

    rc = main(
        [
            "run-manifest",
            "--manifest",
            str(manifest_path),
            "--artifact-root",
            str(artifact_root),
            "--state-store-dir",
            str(state_store_dir),
        ]
    )

    assert rc == 0
    assert any(state_store_dir.iterdir())


def test_cli_run_manifest_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    artifact_root = tmp_path / "artifacts"

    rc = main(["run-manifest", "--manifest", str(missing), "--artifact-root", str(artifact_root)])

    assert rc == 2


def test_cli_module_invocation(tmp_path: Path) -> None:
    manifest_path = _manifest_json(tmp_path, [WorkflowNode(id="a", kind="noop")])
    artifact_root = tmp_path / "artifacts"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "arnold.cli.execution",
            "run-manifest",
            "--manifest",
            str(manifest_path),
            "--artifact-root",
            str(artifact_root),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["state"] == "completed"
    assert parsed["manifest_id"] == "cli-demo"


def test_cli_exits_nonzero_on_run_failure(tmp_path: Path) -> None:
    from arnold.execution.backend import LocalJournalBackend, NodeOutcome, NodeState

    manifest_path = _manifest_json(tmp_path, [WorkflowNode(id="fail", kind="task")])
    artifact_root = tmp_path / "artifacts"

    backend = LocalJournalBackend()
    backend._execute_node_payload = lambda coordinate, node, context: NodeOutcome(state=NodeState.FAILED, error="boom")  # type: ignore[method-assign]

    # Patch the CLI's default backend by overriding the entrypoint directly.
    from arnold.cli import execution as cli_module
    original_cmd = cli_module._cmd_run_manifest

    from arnold.execution import ExecutionRegistries

    def patched_cmd(args):
        manifest = cli_module._load_manifest(Path(args.manifest))
        state_store = cli_module.FileStateStore(args.state_store_dir) if args.state_store_dir else None
        result = backend.run_manifest(
            manifest,
            artifact_root=Path(args.artifact_root),
            registries=ExecutionRegistries(),
            state_store=state_store,
        )
        cli_module._print_result(result)
        return 0 if result.state.value == "completed" else 1

    cli_module._cmd_run_manifest = patched_cmd
    try:
        rc = main(
            [
                "run-manifest",
                "--manifest",
                str(manifest_path),
                "--artifact-root",
                str(artifact_root),
            ]
        )
    finally:
        cli_module._cmd_run_manifest = original_cmd

    assert rc != 0
    parsed = json.loads((artifact_root / "events.ndjson").read_text().splitlines()[-1])
    assert parsed["kind"] == "run_failed"
