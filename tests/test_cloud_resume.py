from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from unittest.mock import Mock

from arnold.pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli
from arnold.pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cloud_parser(subparsers)
    return parser


def _spec(workspace: str = "/workspace/custom") -> CloudSpec:
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace=workspace,
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="high"),
        mode="idle",
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=[],
        railway=RailwaySpec(service="agent", session="agent", project=None),
    )


def test_resume_execute_uses_phase_command_and_plan_flag(monkeypatch) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "resume", "--plan", "plan-x"])
    provider = Mock()
    provider.status_payload.return_value = {"next_step": "execute"}
    provider.ssh_exec.return_value = subprocess.CompletedProcess(
        args=["ssh"],
        returncode=0,
        stdout="",
        stderr="",
    )

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _spec())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec_obj: provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 0
    provider.status_payload.assert_called_once_with(plan="plan-x", workspace="/workspace/custom")
    provider.ssh_exec.assert_called_once_with(
        "cd /workspace/custom && arnold execute --confirm-destructive --user-approved --retry-blocked-tasks --plan plan-x"
    )


def test_resume_review_omits_plan_flag_when_not_supplied(monkeypatch) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "resume"])
    provider = Mock()
    provider.status_payload.return_value = {"next_step": "review"}
    provider.ssh_exec.return_value = subprocess.CompletedProcess(
        args=["ssh"],
        returncode=0,
        stdout="",
        stderr="",
    )

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _spec())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec_obj: provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 0
    provider.status_payload.assert_called_once_with(plan=None, workspace="/workspace/custom")
    provider.ssh_exec.assert_called_once_with("cd /workspace/custom && arnold review")
