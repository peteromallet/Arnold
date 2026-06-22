from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from arnold.cli import operators as operators_mod
from arnold.cli import workflow as workflow_cli

DEMO_TARGET = "tests.fixtures.workflow.demo_pipeline:build_pipeline"


def _capture_operator_parser() -> argparse.ArgumentParser:
    parser = None
    original_parse_args = argparse.ArgumentParser.parse_args

    def capture(self, args=None, namespace=None):
        nonlocal parser
        parser = self
        raise SystemExit

    argparse.ArgumentParser.parse_args = capture  # type: ignore[method-assign]
    try:
        try:
            operators_mod.main(["--help"])
        except SystemExit:
            pass
    finally:
        argparse.ArgumentParser.parse_args = original_parse_args

    assert parser is not None
    return parser


def test_operator_subcommand_surface() -> None:
    parser = _capture_operator_parser()
    subparsers_action = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert sorted(subparsers_action.choices) == ["inspect", "override", "status", "trace"]


def test_status_trace_inspect_require_artifact_root(capsys) -> None:
    for cmd in ("status", "trace", "inspect"):
        with pytest.raises(SystemExit):
            operators_mod.main([cmd])
        out, err = capsys.readouterr()
        assert "--artifact-root" in (out + err)


def _populate_run(tmp_path: Path) -> Path:
    artifact_root = tmp_path / "run"
    workflow_rc = workflow_cli.main(
        [
            "run",
            "--module",
            DEMO_TARGET,
            "--artifact-root",
            str(artifact_root),
        ]
    )
    assert workflow_rc == 0
    return artifact_root


def test_operator_status_reports_progress(tmp_path: Path) -> None:
    artifact_root = _populate_run(tmp_path)
    rc = operators_mod.main(["status", "--artifact-root", str(artifact_root)])
    assert rc == 0


def test_operator_trace_prints_events(tmp_path: Path, capsys) -> None:
    artifact_root = _populate_run(tmp_path)
    rc = operators_mod.main(["trace", "--artifact-root", str(artifact_root)])
    assert rc == 0
    out, _ = capsys.readouterr()
    assert out


def test_operator_inspect_reads_manifest(tmp_path: Path) -> None:
    from arnold.manifest import WorkflowManifest, WorkflowNode

    artifact_root = tmp_path / "run"
    artifact_root.mkdir()
    manifest = WorkflowManifest(id="demo", nodes=(WorkflowNode(id="a", kind="noop"),))
    (artifact_root / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    rc = operators_mod.main(["inspect", "--artifact-root", str(artifact_root)])
    assert rc == 0


def test_operator_override_validates_transition(tmp_path: Path) -> None:
    from arnold.manifest import WorkflowManifest, WorkflowNode

    artifact_root = tmp_path / "run"
    artifact_root.mkdir()
    manifest = WorkflowManifest(id="demo", nodes=(WorkflowNode(id="a", kind="noop"),))
    (artifact_root / "manifest.json").write_text(manifest.to_json(), encoding="utf-8")

    rc = operators_mod.main(
        ["override", "--artifact-root", str(artifact_root), "--transition", "resume"]
    )
    assert rc == 0
