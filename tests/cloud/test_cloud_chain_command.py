from __future__ import annotations

import argparse
import json
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.cloud.cli import (
    _bootstrap_launch_command,
    _chain_anchor_uploads,
    _chain_project_root,
    _chain_start_command,
    _derive_chain_launch_context,
    _durable_megaplan_uploads,
    _derive_bootstrap_session_name,
    _latest_failure_from_plan_status,
    _normalized_chain_upload_spec,
    _phase_model_by_label_from_preflight,
    _remote_chain_upload_path,
    _remote_chain_workspace_path,
    _resolve_resume_workspace,
    _run_sync_megaplan,
    _run_bootstrap_wrapper,
    _status_should_use_chain,
    _validate_chain_spec_location,
    cloud_chain_status_payload,
)
from arnold_pipelines.megaplan.cloud.spec import (
    ChainSubSpec,
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from arnold_pipelines.megaplan.cloud.preflight import resolve_cloud_chain_runtime_dependencies
from arnold_pipelines.megaplan.types import CliError


def test_chain_start_command_sources_cloud_hot_env_before_launch() -> None:
    command = _chain_start_command(
        "/workspace/project/.megaplan/initiatives/demo/chain.yaml",
        project_dir="/workspace/project",
        engine_dir="/workspace/arnold",
    )

    assert "if [ -f /workspace/.cloud-hot-env ]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in command
    assert "cd /workspace/arnold &&" in command
    assert "MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start" in command


def test_remote_chain_upload_path_anchors_relative_initiatives_to_workspace() -> None:
    path = _remote_chain_upload_path(
        ".megaplan/initiatives/god-file-splits/briefs/m1.md",
        source_workspace="/workspace",
        target_workspace="/workspace/vibecomfy-god-file-splits",
    )

    assert path == "/workspace/vibecomfy-god-file-splits/.megaplan/initiatives/god-file-splits/briefs/m1.md"


def test_remote_chain_workspace_path_preserves_spec_relative_path() -> None:
    path = _remote_chain_workspace_path(
        Path("/workspace/.megaplan/initiatives/god-file-splits/chain.yaml"),
        local_root=Path("/workspace"),
        target_workspace="/workspace/vibecomfy-god-file-splits",
    )

    assert path == "/workspace/vibecomfy-god-file-splits/.megaplan/initiatives/god-file-splits/chain.yaml"


def test_bootstrap_launch_command_writes_plan_marker_and_relaunch_command() -> None:
    command = _bootstrap_launch_command(
        workspace="/workspace/vibecomfy-per-workflow-window-chat-20260628",
        remote_idea_path="/workspace/vibecomfy-per-workflow-window-chat-20260628/idea.txt",
        plan_name="per-workflow-window-chat-cloud-20260628",
        robustness="full",
        session_name="vibecomfy-per-workflow-window-chat",
        engine_dir="/workspace/arnold",
    )

    assert "/workspace/.megaplan/cloud-sessions/vibecomfy-per-workflow-window-chat.json" in command
    assert '"run_kind": "plan"' in command
    assert '"plan_name": "per-workflow-window-chat-cloud-20260628"' in command
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan per-workflow-window-chat-cloud-20260628" in command
    assert "arnold init --project-dir /workspace/vibecomfy-per-workflow-window-chat-20260628" in command
    assert "--name per-workflow-window-chat-cloud-20260628" in command


def test_run_bootstrap_wrapper_writes_marker_using_repo_named_session(tmp_path: Path, monkeypatch) -> None:
    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("Per workflow window chat", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []
    archive_names: list[str] = []

    class CaptureProvider:
        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def upload_archive(self, src: Path, dest_dir: str) -> None:
            uploads.append((src, dest_dir))
            with tarfile.open(src, "r:gz") as tar:
                archive_names.extend(sorted(tar.getnames()))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    spec = SimpleNamespace(
        repo=SimpleNamespace(
            url="https://github.com/example/vibecomfy-per-workflow-window-chat.git",
            workspace="/workspace/vibecomfy-per-workflow-window-chat-20260628",
        ),
        megaplan=SimpleNamespace(src_path="/workspace/arnold"),
        secrets=[],
    )
    args = argparse.Namespace(
        idea_file=str(idea_file),
        plan_name="per-workflow-window-chat-cloud-20260628",
        robustness="full",
    )
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._ensure_repo_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._relay_output", lambda *_args, **_kwargs: None)

    assert _derive_bootstrap_session_name(spec) == "vibecomfy-per-workflow-window-chat"
    assert _run_bootstrap_wrapper(args, spec, CaptureProvider()) == 0
    assert uploads == [(idea_file.resolve(), "/workspace/vibecomfy-per-workflow-window-chat-20260628/idea.txt")]
    assert len(commands) == 1
    assert "/workspace/.megaplan/cloud-sessions/vibecomfy-per-workflow-window-chat.json" in commands[0]


def test_chain_anchor_uploads_follow_chain_spec_directory(tmp_path: Path) -> None:
    spec_dir = tmp_path / ".megaplan" / "initiatives" / "demo"
    spec_dir.mkdir(parents=True)
    (spec_dir / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    (spec_dir / "m1-northstar.md").write_text("milestone star\n", encoding="utf-8")
    (spec_dir / "idea.md").write_text("idea\n", encoding="utf-8")
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: idea.md\n"
        "    anchors:\n"
        "      north_star: m1-northstar.md\n",
        encoding="utf-8",
    )

    chain_spec = chain_module.load_spec(spec_path)
    uploads = _chain_anchor_uploads(
        spec_path,
        "/workspace/chain-123/app/.megaplan/initiatives/demo/chain.yaml",
        chain_spec,
    )

    assert uploads == [
        (spec_dir / "NORTHSTAR.md", "/workspace/chain-123/app/.megaplan/initiatives/demo/NORTHSTAR.md"),
        (spec_dir / "m1-northstar.md", "/workspace/chain-123/app/.megaplan/initiatives/demo/m1-northstar.md"),
    ]


def test_normalized_chain_upload_spec_materializes_preflight_phase_map(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n",
        encoding="utf-8",
    )
    preflight = {
        "milestones": [
            {
                "label": "m1",
                "resolved_phase_map": {
                    "plan": "codex",
                    "revise": "codex",
                    "execute": "codex",
                },
            }
        ]
    }

    upload_path = _normalized_chain_upload_spec(
        spec_path,
        base_branch="main",
        source_workspace="/workspace/app",
        target_workspace="/workspace/chain-123/app",
        phase_model_by_label=_phase_model_by_label_from_preflight(preflight),
    )
    try:
        normalized = yaml.safe_load(upload_path.read_text(encoding="utf-8"))
    finally:
        upload_path.unlink(missing_ok=True)

    milestone = normalized["milestones"][0]
    assert milestone["idea"] == ".megaplan/initiatives/demo/briefs/m1.md"
    assert milestone["phase_model"] == [
        "plan=codex",
        "revise=codex",
        "execute=codex",
    ]


def test_cloud_preflight_expands_vendor_depth_like_init() -> None:
    chain_spec = chain_module.ChainSpec.from_dict(
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": "idea.md",
                    "vendor": "codex",
                    "depth": "high",
                }
            ]
        }
    )

    summary = resolve_cloud_chain_runtime_dependencies(
        chain_spec,
        project_dir=None,
        cloud_default_agent="codex",
    )

    phase_map = summary["milestones"][0]["resolved_phase_map"]
    assert phase_map["plan"] == "codex:high"
    assert phase_map["revise"] == "codex:high"
    assert phase_map["execute"] == "codex"


def test_chain_project_root_uses_spec_git_repo_not_caller_root(tmp_path: Path) -> None:
    app_root = tmp_path / "app"
    caller_root = tmp_path / "arnold"
    spec_dir = app_root / "docs" / "chains" / "demo"
    spec_dir.mkdir(parents=True)
    caller_root.mkdir()
    subprocess.run(["git", "init"], cwd=app_root, check=True, capture_output=True, text=True)
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")

    assert _chain_project_root(spec_path, caller_root) == app_root.resolve()


def test_cloud_chain_spec_location_requires_durable_initiatives_tree(tmp_path: Path) -> None:
    project = tmp_path / "app"
    valid = project / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    loose = project / "chain.yaml"
    legacy = project / ".megaplan" / "briefs" / "demo" / "chain.yaml"
    valid.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    valid.write_text("milestones: []\n", encoding="utf-8")
    legacy.write_text("milestones: []\n", encoding="utf-8")
    loose.write_text("milestones: []\n", encoding="utf-8")

    _validate_chain_spec_location(valid, project)
    _validate_chain_spec_location(legacy, project, allow_legacy_briefs_layout=True)
    with pytest.raises(CliError) as excinfo:
        _validate_chain_spec_location(loose, project)

    assert excinfo.value.code == "chain_spec_layout_violation"


def test_durable_megaplan_uploads_exclude_runtime_state(tmp_path: Path) -> None:
    project = tmp_path / "app"
    (project / ".megaplan" / "initiatives" / "demo").mkdir(parents=True)
    (project / ".megaplan" / "tickets").mkdir(parents=True)
    (project / ".megaplan" / "ideas").mkdir(parents=True)
    (project / ".megaplan" / "plans" / "run").mkdir(parents=True)
    (project / ".megaplan" / "initiatives" / "demo" / "chain.yaml").write_text("milestones: []\n", encoding="utf-8")
    (project / ".megaplan" / "tickets" / "T.md").write_text("ticket\n", encoding="utf-8")
    (project / ".megaplan" / "ideas" / "idea.md").write_text("idea\n", encoding="utf-8")
    (project / ".megaplan" / "plans" / "run" / "state.json").write_text("{}\n", encoding="utf-8")

    uploads = _durable_megaplan_uploads(project, "/workspace/demo/app")
    remotes = [remote for _local, remote in uploads]

    assert "/workspace/demo/app/.megaplan/initiatives/demo/chain.yaml" in remotes
    assert "/workspace/demo/app/.megaplan/tickets/T.md" in remotes
    assert "/workspace/demo/app/.megaplan/ideas/idea.md" in remotes
    assert all("/.megaplan/plans/" not in remote for remote in remotes)


def test_sync_megaplan_uses_derived_chain_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "app"
    spec_dir = project / ".megaplan" / "initiatives" / "demo"
    spec_dir.mkdir(parents=True)
    spec_path = spec_dir / "chain.yaml"
    idea_path = spec_dir / "briefs" / "m1.md"
    idea_path.parent.mkdir()
    spec_path.write_text(
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n",
        encoding="utf-8",
    )
    idea_path.write_text("idea\n", encoding="utf-8")
    (project / ".megaplan" / "tickets").mkdir()
    (project / ".megaplan" / "tickets" / "ticket.md").write_text("ticket\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    chain_spec = chain_module.load_spec(spec_path)
    cloud_spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )
    expected = _derive_chain_launch_context(
        root=project,
        spec=cloud_spec,
        local_spec_path=spec_path,
        chain_spec=chain_spec,
    )
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []
    archive_names: list[str] = []

    class CaptureProvider:
        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess([], 0, "", "")

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def upload_archive(self, src: Path, dest_dir: str) -> None:
            uploads.append((src, dest_dir))
            with tarfile.open(src, "r:gz") as tar:
                archive_names.extend(sorted(tar.getnames()))

    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._ensure_repo_checkout", lambda *_args, **_kwargs: None)

    result = _run_sync_megaplan(
        project,
        argparse.Namespace(
            spec=str(spec_path),
            workspace=None,
            clean=True,
            allow_loose_chain_spec=False,
            allow_legacy_briefs_layout=False,
        ),
        cloud_spec,
        CaptureProvider(),
    )

    assert result == 0
    assert commands and "rm -rf" in commands[0]
    assert uploads and uploads[0][1] == expected.workspace
    assert ".megaplan/initiatives/demo/chain.yaml" in archive_names
    assert ".megaplan/tickets/ticket.md" in archive_names


def test_status_auto_uses_chain_for_chain_mode() -> None:
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="chain",
        chain=ChainSubSpec(spec="/workspace/app/chain.yaml"),
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )

    assert _status_should_use_chain(Path("/repo"), argparse.Namespace(chain=False, remote_spec=None, cloud_yaml=None), spec)


def test_status_auto_uses_chain_for_remote_spec_override() -> None:
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )

    assert _status_should_use_chain(
        Path("/repo"),
        argparse.Namespace(chain=False, remote_spec="/workspace/app/chain.yaml", cloud_yaml=None),
        spec,
    )


class _ResumeProvider:
    def __init__(self, chain_state: dict) -> None:
        self.chain_state = chain_state

    def read_remote_file(self, _path: str) -> str:
        return json.dumps(self.chain_state)

    def ssh_exec(self, _command: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, "", "")


def test_cloud_resume_uses_chain_marker_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )
    marker = {
        "workspace": "/workspace/chain-51d959cf/vibecomfy",
        "remote_spec": "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml",
    }
    chain_state = chain_module.ChainState(
        current_plan_name="milestone-demo",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
    ).to_dict()

    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._load_marker", lambda *_args: marker)

    workspace = _resolve_resume_workspace(
        Path("/repo"),
        argparse.Namespace(plan="milestone-demo"),
        spec,
        _ResumeProvider(chain_state),
    )

    assert workspace == "/workspace/chain-51d959cf/vibecomfy"


def test_latest_failure_summary_bubbles_plan_state_message() -> None:
    summary = _latest_failure_from_plan_status(
        {
            "status": "stalled",
            "latest_failure": {
                "kind": "agent_deps_missing",
                "phase": "plan",
                "message": "Claude routes through Shannon, but bun is missing",
                "metadata": {"ignored": True},
            },
        }
    )

    assert summary == {
        "kind": "agent_deps_missing",
        "phase": "plan",
        "message": "Claude routes through Shannon, but bun is missing",
        "raw": {
            "kind": "agent_deps_missing",
            "phase": "plan",
            "message": "Claude routes through Shannon, but bun is missing",
            "metadata": {"ignored": True},
        },
    }


class _StatusProvider:
    def __init__(self, *, remote_spec: str, chain_yaml: str, chain_state: dict, plan_status: dict) -> None:
        self.remote_spec = remote_spec
        self.state_path = str(chain_module._state_path_for(Path(remote_spec)))
        self.chain_yaml = chain_yaml
        self.chain_state = chain_state
        self.plan_status = plan_status

    def read_remote_file(self, path: str) -> str:
        if path == self.remote_spec:
            return self.chain_yaml
        if path == self.state_path:
            return json.dumps(self.chain_state)
        raise OSError(f"unexpected remote file: {path}")

    def status_payload(self, *, plan: str | None, workspace: str) -> dict:
        assert plan == "milestone-demo"
        assert workspace == "/workspace/chain-51d959cf/vibecomfy"
        return dict(self.plan_status)

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        if "tmux has-session" in command:
            return subprocess.CompletedProcess([], 0, "dead\n", "")
        if command.startswith("stat "):
            return subprocess.CompletedProcess([], 0, "unavailable\n", "")
        if "verify-human" in command:
            return subprocess.CompletedProcess([], 0, "{}", "")
        return subprocess.CompletedProcess([], 1, "", "unexpected command")


def test_cloud_chain_status_payload_exposes_plan_latest_failure() -> None:
    remote_spec = "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml"
    chain_yaml = (
        "milestones:\n"
        "  - label: m1\n"
        "    idea: idea.md\n"
    )
    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name="milestone-demo",
        last_state="prepped",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
        chain_session="megaplan-chain-demo",
    ).to_dict()
    plan_status = {
        "status": "stalled",
        "latest_failure": {
            "kind": "agent_deps_missing",
            "message": "Claude routes through Shannon, but bun is missing",
            "phase": "plan",
        },
    }
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )

    payload = cloud_chain_status_payload(
        Path("/repo"),
        argparse.Namespace(remote_spec=remote_spec, cloud_yaml=None),
        spec,
        _StatusProvider(
            remote_spec=remote_spec,
            chain_yaml=chain_yaml,
            chain_state=chain_state,
            plan_status=plan_status,
        ),
    )

    assert payload["latest_failure"]["message"] == "Claude routes through Shannon, but bun is missing"
    assert payload["plan_status"] == plan_status
