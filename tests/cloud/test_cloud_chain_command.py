from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tarfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.cloud.cli import (
    _atomic_marker_write_command,
    _bootstrap_launch_command,
    _chain_anchor_uploads,
    _chain_launch_verification_command,
    _chain_project_root,
    _chain_start_command,
    _cloud_chains_command,
    _cloud_session_plan_state,
    _derive_chain_launch_context,
    _durable_megaplan_uploads,
    _derive_bootstrap_session_name,
    _latest_failure_from_plan_status,
    _materialize_canonical_epic_input,
    _normalized_chain_upload_spec,
    _phase_model_by_label_from_preflight,
    _filter_cloud_sessions_since,
    _parse_cloud_status_since,
    _provider_for_action,
    _remote_chain_upload_path,
    _remote_chain_workspace_path,
    _resolve_resume_workspace,
    _run_cloud_chains,
    _run_chain_wrapper,
    _run_epic_chain_wrapper,
    _run_preflight,
    _run_sync_megaplan,
    _run_launch_epic_wrapper,
    _run_bootstrap_wrapper,
    _status_should_use_chain,
    _tmux_chain_launch_command,
    _tmux_chain_stop_for_fresh_command,
    _validate_chain_spec_location,
    _verify_configured_megaplan_ref_advertised,
    build_cloud_parser,
    cloud_chain_status_payload,
    run_cloud_cli,
)
from arnold_pipelines.megaplan.fallback_chains import encode_phase_model_value
from arnold_pipelines.megaplan.cloud.spec import (
    ChainSubSpec,
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)


def test_on_box_chain_uses_direct_agentbox_transport() -> None:
    from arnold_pipelines.megaplan.cloud.providers.on_box import OnBoxProvider

    provider = _provider_for_action(
        _cloud_spec(),
        argparse.Namespace(cloud_action="chain", on_box=True, session=None),
    )

    assert isinstance(provider, OnBoxProvider)


def test_fresh_chain_stop_is_identity_guarded_before_reset() -> None:
    command = _tmux_chain_stop_for_fresh_command(
        session_name="demo-chain",
        marker_path="/workspace/.megaplan/cloud-sessions/demo-chain.json",
        identity_digest="digest-123",
    )

    assert "tmux has-session -t demo-chain" in command
    assert "grep -F digest-123" in command
    assert "tmux kill-session -t demo-chain" in command
    assert "refusing fresh reset" in command
    assert "exit 17" in command
from arnold_pipelines.megaplan.cloud.preflight import resolve_cloud_chain_runtime_dependencies
from arnold_pipelines.megaplan.types import CliError


def _cloud_spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", branch="main"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets=[],
        ssh=SshSpec(host="testhost"),
    )


def _cloud_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cloud_parser(subparsers)
    return parser


def test_cloud_status_and_chains_accept_compact_since_flags() -> None:
    status_args = _cloud_parser().parse_args(["cloud", "status", "--all", "--compact", "--since", "12h"])
    chains_args = _cloud_parser().parse_args(["cloud", "chains", "--compact", "--since", "12h"])

    assert status_args.cloud_action == "status"
    assert status_args.all is True
    assert status_args.compact is True
    assert status_args.since == "12h"
    assert chains_args.cloud_action == "chains"
    assert chains_args.compact is True
    assert chains_args.since == "12h"


def test_chain_start_command_sources_cloud_hot_env_before_launch() -> None:
    command = _chain_start_command(
        "/workspace/project/.megaplan/initiatives/demo/chain.yaml",
        project_dir="/workspace/project",
        engine_dir="/workspace/arnold",
    )

    assert "if [ -f /workspace/.cloud-hot-env ]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in command
    assert 'ENGINE_DIR="${MEGAPLAN_RUNTIME_SRC:-}"' in command
    assert 'if [ -z "$ENGINE_DIR" ]; then ENGINE_DIR=/workspace/arnold; fi;' in command
    assert 'cd /workspace/project && PYTHONSAFEPATH=1 PYTHONPATH="$ENGINE_DIR:${PYTHONPATH:-}"' in command
    assert "MEGAPLAN_TRUSTED_CONTAINER=1 python -P -m arnold_pipelines.megaplan chain start" in command


def test_tmux_chain_launch_default_marker_records_run_kind() -> None:
    command = _tmux_chain_launch_command(
        "/workspace/project",
        "/workspace/project/.megaplan/initiatives/demo/chain.yaml",
        session_name="demo-chain",
        identity_digest="abc123",
    )

    marker_json = re.search(r"payload = json.loads\('([^']+)'\)", command)

    assert marker_json is not None
    marker = json.loads(marker_json.group(1))
    assert marker["run_kind"] == "chain"
    assert marker["notification_context"]["audience"] == "test_only"
    assert marker["notification_context"]["reason"] == "pytest_environment"


def test_atomic_marker_writer_can_be_followed_by_shell_operator(tmp_path: Path) -> None:
    marker = tmp_path / "markers" / "demo.json"
    command = _atomic_marker_write_command(
        str(marker),
        {"session": "demo", "run_kind": "chain"},
    )

    result = subprocess.run(
        ["bash", "-lc", f"{command}; test -s {marker}"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(marker.read_text()) == {
        "run_kind": "chain",
        "session": "demo",
    }


def test_preflight_phase_model_materialization_preserves_profile_tier_routing() -> None:
    result = _phase_model_by_label_from_preflight(
        {
            "milestones": [
                {
                    "label": "m1",
                    "profile": "premium",
                    "explicit_phase_model": [],
                    "resolved_phase_map": {
                        "execute": "codex:gpt-5.4",
                        "plan": "codex:high",
                    },
                }
            ]
        }
    )

    assert result == {}


def test_preflight_phase_model_materialization_keeps_explicit_profile_pins() -> None:
    result = _phase_model_by_label_from_preflight(
        {
            "milestones": [
                {
                    "label": "m1",
                    "profile": "premium",
                    "explicit_phase_model": ["prep=hermes:deepseek:deepseek-v4-pro"],
                    "resolved_phase_map": {
                        "execute": "codex:gpt-5.4",
                        "prep": "hermes:deepseek:deepseek-v4-pro",
                    },
                }
            ]
        }
    )

    assert result == {"m1": ["prep=hermes:deepseek:deepseek-v4-pro"]}


def test_preflight_phase_model_materialization_keeps_cloud_default_without_profile() -> None:
    result = _phase_model_by_label_from_preflight(
        {
            "milestones": [
                {
                    "label": "m1",
                    "profile": None,
                    "explicit_phase_model": [],
                    "resolved_phase_map": {
                        "execute": "codex:medium",
                        "plan": "codex:high",
                    },
                }
            ]
        }
    )

    assert result == {"m1": ["execute=codex:medium", "plan=codex:high"]}


def test_preflight_phase_model_materialization_preserves_explicit_encoded_chain_without_profile() -> None:
    encoded_execute = encode_phase_model_value(
        "execute",
        ["codex:gpt-5.4", "claude:sonnet"],
    )

    result = _phase_model_by_label_from_preflight(
        {
            "milestones": [
                {
                    "label": "m1",
                    "profile": None,
                    "explicit_phase_model": [encoded_execute],
                    "resolved_phase_chains": {
                        "plan": ["codex:high"],
                        "execute": ["codex:gpt-5.4", "claude:sonnet"],
                    },
                    "resolved_phase_map": {
                        "plan": "codex:high",
                        "execute": "codex:gpt-5.4",
                    },
                }
            ]
        }
    )

    assert result == {"m1": [encoded_execute, "plan=codex:high"]}


def test_launch_epic_rejects_missing_north_star(tmp_path: Path) -> None:
    app = tmp_path / "app"
    brief_dir = app / ".megaplan" / "initiatives" / "demo"
    brief_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=app, check=True, capture_output=True, text=True)
    (brief_dir / "m1.md").write_text("M1\n", encoding="utf-8")

    with pytest.raises(Exception) as excinfo:
        _materialize_canonical_epic_input(
            root=tmp_path,
            spec=_cloud_spec(),
            spec_or_dir=str(brief_dir),
        )

    assert getattr(excinfo.value, "code", "") == "missing_north_star"
    assert "NORTHSTAR.md" in getattr(excinfo.value, "message", str(excinfo.value))


def test_launch_epic_materializes_canonical_layout_from_brief_dir(tmp_path: Path) -> None:
    app = tmp_path / "app"
    brief_dir = app / "incoming" / "research-plan-execute-epic"
    brief_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=app, check=True, capture_output=True, text=True)
    (brief_dir / "NORTHSTAR.md").write_text("North star\n", encoding="utf-8")
    (brief_dir / "m1-contracts.md").write_text("M1\n", encoding="utf-8")
    (brief_dir / "m2-routing.md").write_text("M2\n", encoding="utf-8")

    materialized = _materialize_canonical_epic_input(
        root=tmp_path,
        spec=_cloud_spec(),
        spec_or_dir=str(brief_dir),
    )

    assert materialized.generated_chain is True
    assert materialized.slug == "research-plan-execute-epic"
    assert materialized.spec_path == app / ".megaplan" / "initiatives" / "research-plan-execute-epic" / "chain.yaml"
    raw = yaml.safe_load(materialized.spec_path.read_text(encoding="utf-8"))
    assert raw["anchors"] == {"north_star": "NORTHSTAR.md"}
    assert raw["milestones"][0]["idea"] == ".megaplan/initiatives/research-plan-execute-epic/briefs/m1-contracts.md"
    assert (materialized.brief_dir / "NORTHSTAR.md").is_file()
    assert (materialized.brief_dir / "briefs" / "m2-routing.md").is_file()
    assert str(materialized.spec_path) in materialized.created_files


class _LaunchEpicProvider:
    def __init__(self) -> None:
        self.uploads: list[tuple[Path, str]] = []
        self.remote_files: set[str] = set()
        self.markers: dict[str, dict] = {}

    def upload_file(self, src: Path, dest: str) -> None:
        self.uploads.append((src, dest))
        self.remote_files.add(dest)

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        if "MEGAPLAN_RESET" in command:
            return subprocess.CompletedProcess([], 0, "", "")
        if "MEGAPLAN_WATCHDOG_TRACKING" in command:
            marker = re.search(r"marker_path = pathlib\.Path\('([^']+)'\)", command).group(1)
            workspace = re.search(r"workspace = pathlib\.Path\('([^']+)'\)", command).group(1)
            remote_spec = re.search(r"remote_spec = pathlib\.Path\('([^']+)'\)", command).group(1)
            payload = self.markers.get(marker, {})
            errors = []
            if not payload:
                errors.append("marker missing")
            if remote_spec not in self.remote_files:
                errors.append("remote_spec missing")
            if payload.get("workspace") != workspace:
                errors.append("workspace mismatch")
            if payload.get("remote_spec") != remote_spec:
                errors.append("remote_spec mismatch")
            result = {
                "tracked": not errors,
                "errors": errors,
                "marker_path": marker,
                "workspace": workspace,
                "remote_spec": remote_spec,
                "session": payload.get("session"),
            }
            return subprocess.CompletedProcess([], 0 if result["tracked"] else 1, json.dumps(result) + "\n", "")
        if "MEGAPLAN_VERIFY" in command:
            result = {
                "session_alive": True,
                "advanced_past_init": True,
                "chain_log": "/workspace/log",
                "state_present": True,
                "plan_dirs": ["m1"],
            }
            return subprocess.CompletedProcess([], 0, json.dumps(result) + "\n", "")
        if "tmux new-session" in command or "session already running for this chain" in command:
            marker_path, marker_payload = _parse_marker_write(command)
            self.markers[marker_path] = marker_payload
            return subprocess.CompletedProcess([], 0, "started session\n", "")
        return subprocess.CompletedProcess([], 0, "", "")


def shlex_split_one(value: str) -> str:
    import shlex

    parsed = shlex.split(value)
    assert len(parsed) == 1
    return parsed[0]


def _parse_marker_write(command: str) -> tuple[str, dict]:
    marker_match = re.search(
        r"path = pathlib\.Path\((?P<path>'(?:\\'|[^'])*')\)\s+payload = json\.loads\((?P<payload>'(?:\\'|[^'])*')\)",
        command,
        re.DOTALL,
    )
    assert marker_match, command
    return ast.literal_eval(marker_match.group("path")), json.loads(ast.literal_eval(marker_match.group("payload")))


def test_launch_epic_end_to_end_uploads_canonical_spec_and_tracks_watchdog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "app"
    brief_dir = app / ".megaplan" / "initiatives" / "demo"
    brief_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=app, check=True, capture_output=True, text=True)
    (brief_dir / "NORTHSTAR.md").write_text("North star\n", encoding="utf-8")
    (brief_dir / "m1.md").write_text("M1\n", encoding="utf-8")

    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._sync_launch_head_to_editable_install_branch", lambda *_a, **_k: {"status": "skipped"})
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._ensure_repo_checkout", lambda *_a, **_k: None)
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._run_remote_dependency_check", lambda *_a, **_k: [])
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli.seed_codex_oauth", lambda *_a, **_k: {"status": "skipped"})
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._remote_repo_head", lambda *_a, **_k: {"branch": "main", "head": "abc123"})
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._relay_output", lambda *_a, **_k: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

    provider = _LaunchEpicProvider()
    rc = _run_launch_epic_wrapper(
        tmp_path,
        argparse.Namespace(
            spec_or_dir=str(brief_dir),
            slug=None,
            fresh=True,
            no_git_refresh=True,
            no_editable_install_sync=True,
            cloud_yaml=str(app / "cloud.yaml"),
        ),
        _cloud_spec(),
        provider,
    )

    assert rc == 0
    uploaded_remote_paths = {remote for _local, remote in provider.uploads}
    remote_spec = next(path for path in uploaded_remote_paths if path.endswith("/.megaplan/initiatives/demo/chain.yaml"))
    assert "/workspace/demo-" in remote_spec
    marker = next(marker for marker in provider.markers.values() if marker["remote_spec"] == remote_spec)
    assert marker["run_kind"] == "chain"
    assert marker["allow_human_gates"] is False
    assert "python -P -m arnold_pipelines.megaplan chain start" in marker["relaunch_command"]
    assert f"--spec {remote_spec}" in marker["relaunch_command"]
    assert remote_spec in provider.remote_files


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
    assert phase_map["plan"] == "codex:gpt-5.6-sol:high"
    assert phase_map["revise"] == "codex:gpt-5.6-sol:high"
    assert phase_map["execute"] == "codex:gpt-5.6-sol:high"


def test_cloud_preflight_reports_dependencies_for_every_spec_in_each_chain() -> None:
    chain_spec = chain_module.ChainSpec.from_dict(
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": "idea.md",
                    "phase_model": [
                        encode_phase_model_value("plan", ["codex:high", "claude:sonnet"]),
                        encode_phase_model_value("prep", ["hermes:deepseek:deepseek-v4-pro", "codex"]),
                    ],
                }
            ]
        }
    )

    summary = resolve_cloud_chain_runtime_dependencies(
        chain_spec,
        project_dir=None,
        cloud_default_agent="codex",
    )

    milestone = summary["milestones"][0]
    assert milestone["resolved_phase_map"]["plan"] == "codex:high"
    assert milestone["resolved_phase_chains"]["plan"] == ["codex:high", "claude:sonnet"]
    assert sorted(summary["required_agents"]) == ["claude", "codex", "hermes"]
    assert "bun" in summary["runtime_commands"]
    assert "codex" in summary["runtime_commands"]
    assert "claude" in summary["runtime_commands"]
    assert "DEEPSEEK_API_KEY" in summary["env_hints"]


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
    valid.parent.mkdir(parents=True)
    valid.write_text("milestones: []\n", encoding="utf-8")
    loose.write_text("milestones: []\n", encoding="utf-8")

    _validate_chain_spec_location(valid, project)
    with pytest.raises(CliError) as excinfo:
        _validate_chain_spec_location(loose, project)

    assert excinfo.value.code == "chain_spec_layout_violation"


def test_chain_launch_verification_classifies_editable_refresh_dirty() -> None:
    command = _chain_launch_verification_command(
        workspace="/workspace/demo/app",
        session_name="megaplan-chain-demo",
        state_path="/workspace/demo/app/.megaplan/plans/.chains/chain-state.json",
        log_path="/workspace/demo/app/.megaplan/cloud-chain-megaplan-chain-demo.log",
        attempts=1,
        sleep_seconds=0,
    )

    assert "editable_install_refresh_dirty" in command
    assert "[megaplan-refresh] refusing editable install refresh" in command
    assert '"log_tail"' in command


def test_durable_megaplan_uploads_exclude_runtime_state(tmp_path: Path) -> None:
    project = tmp_path / "app"
    (project / ".megaplan" / "initiatives" / "demo").mkdir(parents=True)
    (project / ".megaplan" / "tickets").mkdir(parents=True)
    (project / ".megaplan" / "ideas").mkdir(parents=True)
    (project / ".megaplan" / "plans" / "run").mkdir(parents=True)
    (project / ".megaplan" / "initiatives" / "demo" / "chain.yaml").write_text("milestones: []\n", encoding="utf-8")
    (project / ".megaplan" / "tickets" / "T.md").write_text("ticket\n", encoding="utf-8")
    (project / ".megaplan" / "ideas" / "idea.md").write_text("idea\n", encoding="utf-8")
    (project / ".megaplan" / "ideas" / "._idea.md").write_text("appledouble\n", encoding="utf-8")
    (project / ".megaplan" / "tickets" / "._T.md").write_text("appledouble\n", encoding="utf-8")
    (project / ".megaplan" / "initiatives" / "demo" / ".DS_Store").write_text("finder\n", encoding="utf-8")
    (project / ".megaplan" / "plans" / "run" / "state.json").write_text("{}\n", encoding="utf-8")

    uploads = _durable_megaplan_uploads(project, "/workspace/demo/app")
    remotes = [remote for _local, remote in uploads]

    assert "/workspace/demo/app/.megaplan/initiatives/demo/chain.yaml" in remotes
    assert "/workspace/demo/app/.megaplan/tickets/T.md" in remotes
    assert "/workspace/demo/app/.megaplan/ideas/idea.md" in remotes
    assert all("/.megaplan/plans/" not in remote for remote in remotes)
    assert all("/._" not in remote for remote in remotes)
    assert all(not remote.endswith(".DS_Store") for remote in remotes)


def test_cloud_preflight_reports_remote_imports_profile_warning_and_expected_spec(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "app"
    spec_dir = project / ".megaplan" / "initiatives" / "demo"
    spec_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    (spec_dir / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    (spec_dir / "briefs").mkdir()
    (spec_dir / "briefs" / "m1.md").write_text("idea\n", encoding="utf-8")
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n"
        "    phase_model:\n"
        "      - plan=claude\n"
        "      - revise=codex\n"
        "      - execute=codex\n",
        encoding="utf-8",
    )
    commands: list[str] = []

    class PreflightProvider:
        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "MEGAPLAN_IMPORT_CHECK" in command:
                payload = {
                    "checks": {
                        "arnold_pipelines.megaplan": True,
                        "arnold_pipelines.megaplan.cli": True,
                        "arnold.pipelines.megaplan": False,
                    },
                    "errors": [],
                }
                return subprocess.CompletedProcess([], 0, json.dumps(payload) + "\n", "")
            return subprocess.CompletedProcess([], 0, "\n", "")

    rc = _run_preflight(
        project,
        argparse.Namespace(
            spec=str(spec_path),
            skip_remote=False,
            allow_loose_chain_spec=False,
        ),
        _cloud_spec(),
        PreflightProvider(),
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["canonical_layout"] is True
    assert payload["remote"]["expected_remote_spec"].endswith("/.megaplan/initiatives/demo/chain.yaml")
    assert payload["remote"]["import_check"]["status"] == "ok"
    assert any("Codex-only cloud workers should use profile all-codex" in warning for warning in payload["warnings"])
    assert any("MEGAPLAN_IMPORT_CHECK" in command for command in commands)


def test_cloud_preflight_fails_on_stale_remote_import(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "app"
    spec_dir = project / ".megaplan" / "initiatives" / "demo"
    spec_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    (spec_dir / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    (spec_dir / "briefs").mkdir()
    (spec_dir / "briefs" / "m1.md").write_text("idea\n", encoding="utf-8")
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n",
        encoding="utf-8",
    )

    class StaleProvider:
        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "MEGAPLAN_IMPORT_CHECK" in command:
                payload = {
                    "checks": {
                        "arnold_pipelines.megaplan": False,
                        "arnold_pipelines.megaplan.cli": False,
                        "arnold.pipelines.megaplan": True,
                    },
                    "errors": ["missing modern arnold_pipelines.megaplan import"],
                }
                return subprocess.CompletedProcess([], 1, json.dumps(payload) + "\n", "")
            return subprocess.CompletedProcess([], 0, "\n", "")

    rc = _run_preflight(
        project,
        argparse.Namespace(
            spec=str(spec_path),
            skip_remote=False,
            allow_loose_chain_spec=False,
        ),
        _cloud_spec(),
        StaleProvider(),
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["success"] is False
    assert "missing modern arnold_pipelines.megaplan import" in payload["errors"]


def test_cloud_preflight_reports_engine_ref_check_when_remote_checks_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "app"
    spec_dir = project / ".megaplan" / "initiatives" / "demo"
    spec_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    (spec_dir / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    (spec_dir / "briefs").mkdir()
    (spec_dir / "briefs" / "m1.md").write_text("idea\n", encoding="utf-8")
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._verify_configured_megaplan_ref_advertised",
        lambda *_a, **_k: {
            "status": "ok",
            "repo": "https://github.com/example/arnold.git",
            "requested_ref": "editible-install",
            "advertised_ref": "refs/heads/editible-install",
            "commit": "abc123",
            "ref_kind": "branch",
        },
    )

    class PreflightProvider:
        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "MEGAPLAN_IMPORT_CHECK" in command:
                payload = {
                    "checks": {
                        "arnold_pipelines.megaplan": True,
                        "arnold_pipelines.megaplan.cli": True,
                        "arnold.pipelines.megaplan": False,
                    },
                    "errors": [],
                }
                return subprocess.CompletedProcess([], 0, json.dumps(payload) + "\n", "")
            return subprocess.CompletedProcess([], 0, "\n", "")

    rc = _run_preflight(
        project,
        argparse.Namespace(
            spec=str(spec_path),
            skip_remote=False,
            allow_loose_chain_spec=False,
            cloud_yaml=str(project / "cloud.yaml"),
        ),
        replace(
            _cloud_spec(),
            megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref="editible-install"),
        ),
        PreflightProvider(),
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["remote"]["engine_ref_check"]["advertised_ref"] == "refs/heads/editible-install"


def test_verify_configured_megaplan_ref_accepts_full_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._ls_remote_refs",
        lambda repo, refs: subprocess.CompletedProcess(
            [],
            0,
            "abc123\trefs/heads/editible-install\n",
            "",
        ),
    )

    result = _verify_configured_megaplan_ref_advertised(
        replace(
            _cloud_spec(),
            megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref="refs/heads/editible-install"),
        )
    )

    assert result["status"] == "ok"
    assert result["advertised_ref"] == "refs/heads/editible-install"
    assert result["ref_kind"] == "full_ref"


def test_verify_configured_megaplan_ref_accepts_fetchable_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    commit = "a" * 40
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._probe_remote_commit",
        lambda repo, requested: subprocess.CompletedProcess([], 0, "", ""),
    )

    result = _verify_configured_megaplan_ref_advertised(
        replace(
            _cloud_spec(),
            megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref=commit),
        )
    )

    assert result == {
        "status": "ok",
        "repo": "https://github.com/example/arnold.git",
        "requested_ref": commit,
        "commit": commit,
        "ref_kind": "commit",
        "verification": "fetch",
    }


def test_verify_configured_megaplan_ref_rejects_unfetchable_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    commit = "b" * 40
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._probe_remote_commit",
        lambda repo, requested: subprocess.CompletedProcess([], 128, "", "fatal: not our ref"),
    )

    with pytest.raises(CliError) as excinfo:
        _verify_configured_megaplan_ref_advertised(
            replace(
                _cloud_spec(),
                megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref=commit),
            )
        )

    assert excinfo.value.code == "engine_commit_unfetchable"
    assert excinfo.value.extra["engine_ref_check"]["reason"] == "raw_sha_unfetchable"


def test_verify_configured_megaplan_ref_rejects_ambiguous_short_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._ls_remote_refs",
        lambda repo, refs: subprocess.CompletedProcess(
            [],
            0,
            "abc123\trefs/heads/editible-install\n"
            "def456\trefs/tags/editible-install\n",
            "",
        ),
    )

    spec = replace(
        _cloud_spec(),
        megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref="editible-install")
    )
    with pytest.raises(CliError) as excinfo:
        _verify_configured_megaplan_ref_advertised(spec)

    assert excinfo.value.code == "engine_ref_ambiguous"


class _RefFailureProvider:
    def __init__(self) -> None:
        self.uploads: list[tuple[Path, str]] = []
        self.markers: dict[str, dict] = {}

    def upload_file(self, src: Path, dest: str) -> None:
        self.uploads.append((src, dest))

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        if "MEGAPLAN_MARKER_WRITE" in command:
            marker_path, marker_payload = _parse_marker_write(command)
            self.markers[marker_path] = marker_payload
            return subprocess.CompletedProcess([], 0, "", "")
        if "MEGAPLAN_PRELAUNCH_MARKER_GUARD" in command:
            return subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {
                        "session_alive": False,
                        "marker_present": False,
                        "identity_matches": False,
                        "marker_read_error": "",
                    }
                )
                + "\n",
                "",
            )
        raise AssertionError(command)


def test_cloud_chain_persists_failed_launch_outcome_when_engine_ref_is_not_advertised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "app"
    spec_dir = project / ".megaplan" / "initiatives" / "demo"
    spec_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    (spec_dir / "NORTHSTAR.md").write_text("north star\n", encoding="utf-8")
    (spec_dir / "briefs").mkdir()
    (spec_dir / "briefs" / "m1.md").write_text("idea\n", encoding="utf-8")
    spec_path = spec_dir / "chain.yaml"
    spec_path.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/demo/briefs/m1.md\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._ensure_repo_checkout", lambda *_a, **_k: None)
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._run_remote_dependency_check", lambda *_a, **_k: [])
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli.seed_codex_oauth", lambda *_a, **_k: {"status": "skipped"})
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._remote_repo_head", lambda *_a, **_k: {"branch": "main", "head": "abc123"})
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._relay_output", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._verify_configured_megaplan_ref_advertised",
        lambda *_a, **_k: (_ for _ in ()).throw(
            CliError(
                "engine_ref_not_advertised",
                "Configured cloud megaplan.ref 'editible-install' is not advertised by https://github.com/example/arnold.git.",
                extra={
                    "engine_ref_check": {
                        "status": "failed",
                        "repo": "https://github.com/example/arnold.git",
                        "requested_ref": "editible-install",
                    }
                },
            )
        ),
    )

    provider = _RefFailureProvider()
    cloud_spec = replace(
        _cloud_spec(),
        megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref="editible-install")
    )
    with pytest.raises(CliError) as excinfo:
        _run_chain_wrapper(
            project,
            argparse.Namespace(
                spec=str(spec_path),
                idea_dir=None,
                fresh=False,
                no_git_refresh=False,
                no_editable_install_sync=True,
                force_clean_editable_install=False,
                allow_loose_chain_spec=False,
                allow_template_placeholders=False,
                allow_human_gates=False,
                cloud_yaml=str(project / "cloud.yaml"),
                _canonicalized_epic=True,
                _generated_canonical_files=[],
            ),
            cloud_spec,
            provider,
        )

    assert excinfo.value.code == "engine_ref_not_advertised"
    assert provider.markers
    marker = next(iter(provider.markers.values()))
    assert marker["remote_spec"].endswith("/.megaplan/initiatives/demo/chain.yaml")
    assert marker["launch_outcome"]["status"] == "failed"
    assert marker["launch_outcome"]["code"] == "engine_ref_not_advertised"
    assert "not advertised" in marker["launch_outcome"]["detail"]


def test_cloud_epic_chain_persists_failed_launch_outcome_when_engine_ref_is_not_advertised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "app"
    child_dir = project / ".megaplan" / "initiatives" / "child"
    parent_dir = project / ".megaplan" / "initiatives" / "demo"
    child_dir.mkdir(parents=True)
    parent_dir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    (child_dir / "NORTHSTAR.md").write_text("child north star\n", encoding="utf-8")
    (child_dir / "briefs").mkdir()
    (child_dir / "briefs" / "m1.md").write_text("idea\n", encoding="utf-8")
    child_spec = child_dir / "chain.yaml"
    child_spec.write_text(
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: .megaplan/initiatives/child/briefs/m1.md\n",
        encoding="utf-8",
    )
    (parent_dir / "NORTHSTAR.md").write_text("parent north star\n", encoding="utf-8")
    epic_spec = parent_dir / "epic-chain.yaml"
    epic_spec.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "epics:\n"
        "  - id: child\n"
        "    spec: ../child/chain.yaml\n"
        "on_failure:\n"
        "  abort: stop_epic_chain\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._ensure_repo_checkout", lambda *_a, **_k: None)
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli.seed_codex_oauth", lambda *_a, **_k: {"status": "skipped"})
    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.cli._relay_output", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._verify_configured_megaplan_ref_advertised",
        lambda *_a, **_k: (_ for _ in ()).throw(
            CliError(
                "engine_ref_not_advertised",
                "Configured cloud megaplan.ref 'editible-install' is not advertised by https://github.com/example/arnold.git.",
                extra={
                    "engine_ref_check": {
                        "status": "failed",
                        "repo": "https://github.com/example/arnold.git",
                        "requested_ref": "editible-install",
                    }
                },
            )
        ),
    )

    class EpicRefFailureProvider(_RefFailureProvider):
        def upload_archive(self, src: Path, dest: str) -> None:
            self.uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if command.startswith("rm -rf "):
                return subprocess.CompletedProcess([], 0, "", "")
            return super().ssh_exec(command)

    provider = EpicRefFailureProvider()
    cloud_spec = replace(
        _cloud_spec(),
        megaplan=MegaplanSpec(repo="https://github.com/example/arnold.git", ref="editible-install"),
    )
    with pytest.raises(CliError) as excinfo:
        _run_epic_chain_wrapper(
            project,
            argparse.Namespace(
                spec=str(epic_spec),
                fresh=False,
                no_editable_install_sync=True,
                one=False,
                cloud_yaml=str(project / "cloud.yaml"),
            ),
            cloud_spec,
            provider,
        )

    assert excinfo.value.code == "engine_ref_not_advertised"
    assert provider.markers
    marker = next(iter(provider.markers.values()))
    assert marker["run_kind"] == "epic_chain"
    assert marker["launch_outcome"]["status"] == "failed"
    assert marker["launch_outcome"]["code"] == "engine_ref_not_advertised"


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
    def __init__(
        self,
        *,
        remote_spec: str,
        chain_yaml: str,
        chain_state: dict,
        plan_status: dict,
        runner_probe: str = "dead\n",
    ) -> None:
        self.remote_spec = remote_spec
        self.state_path = str(chain_module._state_path_for(Path(remote_spec)))
        self.chain_yaml = chain_yaml
        self.chain_state = chain_state
        self.plan_status = plan_status
        self.runner_probe = runner_probe

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
            return subprocess.CompletedProcess([], 0, self.runner_probe, "")
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


def test_cloud_resume_uses_resume_command_for_failed_plan(monkeypatch, tmp_path: Path) -> None:
    commands: list[str] = []

    class Provider:
        def status_payload(self, *, plan: str | None, workspace: str) -> dict:
            assert plan == "milestone-demo"
            assert workspace == "/workspace/chain-51d959cf/vibecomfy"
            return {
                "state": "failed",
                "next_step": "review",
                "valid_next": ["review"],
            }

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._load_cloud_spec",
        lambda root, args: _cloud_spec(),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._provider_for_action",
        lambda spec, args: Provider(),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.cli._resolve_resume_workspace",
        lambda root, args, spec, provider: "/workspace/chain-51d959cf/vibecomfy",
    )

    args = _cloud_parser().parse_args(["cloud", "resume", "--plan", "milestone-demo"])

    rc = run_cloud_cli(tmp_path, args)

    assert rc == 0
    assert commands == [
        "cd /workspace/chain-51d959cf/vibecomfy && arnold resume --plan milestone-demo"
    ]


def test_cloud_chain_status_payload_treats_live_process_as_alive_runner() -> None:
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
            plan_status={"status": "running"},
            runner_probe="process_alive\n",
        ),
    )

    assert payload["runner"]["status"] == "alive"
    assert payload["runner"]["tmux_status"] == "missing"
    assert payload["runner"]["process_status"] == "alive"
    assert payload["effective_status"] == "running"


def test_cloud_chains_command_lists_marker_only_live_process_sessions() -> None:
    script = _cloud_chains_command()

    assert "marker_dir.glob(\"*.json\")" in script
    assert "process_status" in script
    assert "tmux_status" in script
    assert '" chain start" in line' in script
    assert '" epic-chain start" in line' in script
    assert "def _effective_session_status(payload):" in script
    assert "return \"running\"" in script


def test_cloud_chains_command_prefers_live_runner_over_stale_done_plan_pointer() -> None:
    script = _cloud_chains_command()

    status_fn = script[script.index("def _effective_session_status(payload):") :]
    live_runner_check = 'payload.get("tmux_status") == "alive" or payload.get("process_status") == "alive"'
    stale_done_check = 'if current_state == "done":'

    assert status_fn.index(live_runner_check) < status_fn.index(stale_done_check)


def test_cloud_chains_command_lists_all_canonical_markers_not_only_default_prefix() -> None:
    script = _cloud_chains_command()

    assert "name.startswith" not in script
    assert "sessions_by_name.setdefault(name, _payload_for(name))" in script
    assert "untracked_tmux_sessions" in script


def test_cloud_chains_command_derives_display_name_from_initiative_path() -> None:
    script = _cloud_chains_command()

    assert "def _display_name(payload):" in script
    assert '{"initiatives", "briefs"}' in script
    assert '"display_name"' in script


def test_cloud_chains_command_includes_should_run_and_watchdog_repair_state() -> None:
    script = _cloud_chains_command()

    assert "def _load_watchdog_sessions():" in script
    assert "watchdog_by_session" in script
    assert '"watchdog_evidence"' in script
    assert '"watchdog_repairing"' in script
    assert '"should_be_running"' in script
    assert "def _should_be_running(payload):" in script
    assert "should_be_running_count" in script
    assert "watchdog_repairing_count" in script


def test_cloud_chains_command_explains_policy_and_user_action_blocks() -> None:
    script = _cloud_chains_command()

    assert "def _policy_evidence(remote_spec):" in script
    assert '"merge_policy"' in script
    assert '"driver_auto_approve"' in script
    assert "def _operator_status(payload):" in script
    assert "blocked_prep_clarification" in script
    assert "clarification_question_count" in script
    assert '"operator_summary"' in script
    assert '"next_action"' in script
    assert "human_gate_misconfigured" in script
    assert "not payload.get(\"allow_human_gates\")" in script


# ── T11: sidecar classification & evidence field tests ──────────────────


def test_cloud_chains_command_uses_canonical_session_marker_filter() -> None:
    """The generated script must import and call ``is_canonical_session_marker_path``
    to exclude canonical sidecar JSONs from session listing."""
    script = _cloud_chains_command()

    assert "from arnold_pipelines.megaplan.cloud.session_markers import is_canonical_session_marker_path" in script
    assert "is_canonical_session_marker_path(marker)" in script


def test_cloud_chains_command_emits_latest_plan_state_evidence() -> None:
    script = _cloud_chains_command()

    assert "def _latest_plan_state_evidence(workspace):" in script
    assert '"latest_plan_state"' in script
    assert '"active_phase"' in script
    assert '".megaplan" / "plans"' in script
    assert 'plans_dir.glob("*/state.json")' in script


def test_cloud_chains_command_emits_event_activity_evidence() -> None:
    script = _cloud_chains_command()

    assert "def _event_activity_evidence(workspace, plan_name):" in script
    assert '"event_activity_evidence"' in script
    assert '"event_activity_status"' in script
    assert 'plans" / plan_name / "events.ndjson"' in script
    assert 'plan_name = latest_plan_state.get("plan")' in script


def test_cloud_chains_command_emits_separate_evidence_fields() -> None:
    """Every session row must emit distinct ``marker_evidence``, ``tmux_evidence``,
    ``process_evidence``, ``chain_health_evidence``, and ``active_step_evidence`` fields."""
    script = _cloud_chains_command()

    assert '"marker_evidence"' in script
    assert '"tmux_evidence"' in script
    assert '"process_evidence"' in script
    assert '"chain_health_evidence"' in script
    assert '"active_step_evidence"' in script
    # Status convenience mirrors
    assert '"marker_status"' in script
    assert '"tmux_status"' in script
    assert '"process_status"' in script
    assert '"chain_health_status"' in script
    assert '"active_step_status"' in script


def test_cloud_status_since_parser_accepts_duration() -> None:
    now = _parse_cloud_status_since("2026-07-04T12:00:00Z")
    assert now is not None

    cutoff = _parse_cloud_status_since("12h", now=now)

    assert cutoff is not None
    assert cutoff.isoformat() == "2026-07-04T00:00:00+00:00"


def test_cloud_status_since_filter_uses_real_plan_state_not_watchdog_mtime() -> None:
    payload = {
        "sessions": [
            {
                "session": "old-but-reobserved",
                "status": "complete",
                "watchdog_repairing": False,
                "should_be_running": False,
                "watchdog_evidence": {"updated_at": "2026-07-04T08:00:00Z"},
                "latest_plan_state": {
                    "status": "present",
                    "updated_at": "2026-07-03T08:00:00Z",
                    "plan": "old-plan",
                    "state": "done",
                },
                "operator_status": {"status": "complete"},
            },
            {
                "session": "recent",
                "status": "complete",
                "watchdog_repairing": False,
                "should_be_running": False,
                "latest_plan_state": {
                    "status": "present",
                    "updated_at": "2026-07-04T04:00:00Z",
                    "plan": "recent-plan",
                    "state": "done",
                },
                "operator_status": {"status": "complete"},
            },
        ]
    }
    since = _parse_cloud_status_since("2026-07-04T00:00:00Z")

    _filter_cloud_sessions_since(payload, since)

    assert [item["session"] for item in payload["sessions"]] == ["recent"]
    assert payload["unfiltered_session_count"] == 2
    assert payload["summary"] == {"complete": 1}


def test_cloud_status_since_filter_prefers_event_activity_over_stale_state() -> None:
    payload = {
        "sessions": [
            {
                "session": "active-prep",
                "status": "running",
                "watchdog_repairing": False,
                "should_be_running": True,
                "latest_plan_state": {
                    "status": "present",
                    "updated_at": "2026-07-03T08:00:00Z",
                    "plan": "active-plan",
                    "state": "initialized",
                },
                "event_activity_evidence": {
                    "status": "present",
                    "updated_at": "2026-07-04T04:00:00Z",
                    "phase": "prep-research",
                    "kind": "llm_token_heartbeat",
                },
                "operator_status": {"status": "running_phase"},
            }
        ]
    }
    since = _parse_cloud_status_since("2026-07-04T00:00:00Z")

    _filter_cloud_sessions_since(payload, since)

    assert [item["session"] for item in payload["sessions"]] == ["active-prep"]
    assert payload["sessions"][0]["real_activity_at"] == "2026-07-04T04:00:00Z"


def test_cloud_session_plan_state_prefers_event_phase_over_initialized_state() -> None:
    assert (
        _cloud_session_plan_state(
            {
                "latest_plan_state": {"status": "present", "state": "initialized"},
                "event_activity_evidence": {
                    "status": "present",
                    "phase": "prep-research",
                    "kind": "llm_token_heartbeat",
                },
            }
        )
        == "prep-research"
    )


def test_cloud_session_plan_state_uses_latest_state_active_phase_fallback() -> None:
    assert (
        _cloud_session_plan_state(
            {
                "latest_plan_state": {
                    "status": "present",
                    "state": "initialized",
                    "active_phase": "prep-distill",
                },
                "event_activity_evidence": {"status": "missing"},
                "active_step_evidence": {"status": "missing"},
            }
        )
        == "prep-distill"
    )


def test_cloud_chains_command_treats_initialized_as_known_nonterminal_state() -> None:
    script = _cloud_chains_command()

    assert '{"initialized", "prepped", "planned", "gated", "finalized", "executed", "reviewed", "stopped"}' in script
    assert '"initialized",\n            "prepped",' in script


class _CloudChainsProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        assert "_latest_plan_state_evidence" in command
        return subprocess.CompletedProcess([], 0, json.dumps(self.payload) + "\n", "")


def test_cloud_status_all_compact_since_filters_payload_and_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "success": True,
        "sessions": [
            {
                "session": "old",
                "display_name": "old",
                "status": "complete",
                "watchdog_repairing": False,
                "should_be_running": False,
                "workspace": "/workspace/old",
                "latest_plan_state": {
                    "status": "present",
                    "updated_at": "2026-07-03T08:00:00Z",
                    "plan": "old-plan",
                    "state": "done",
                },
                "operator_status": {"status": "complete"},
            },
            {
                "session": "running",
                "display_name": "running",
                "status": "running",
                "watchdog_repairing": True,
                "should_be_running": True,
                "workspace": "/workspace/running",
                "latest_plan_state": {
                    "status": "present",
                    "updated_at": "2026-07-04T04:00:00Z",
                    "plan": "active-plan",
                    "state": "initialized",
                },
                "event_activity_evidence": {
                    "status": "present",
                    "updated_at": "2026-07-04T04:05:00Z",
                    "phase": "prep-research",
                    "kind": "llm_token_heartbeat",
                },
                "operator_status": {"status": "running_repairing"},
            },
        ],
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
    args = argparse.Namespace(since="2026-07-04T00:00:00Z", compact=True)

    assert _run_cloud_chains(spec, _CloudChainsProvider(payload), args=args) == 0

    captured = capsys.readouterr()
    assert "cloud sessions: 1 since=2026-07-04T00:00:00Z filtered_from=2" in captured.err
    assert "session=running" in captured.err
    assert "activity_state=prep-research" in captured.err
    assert "session=old" not in captured.err
    emitted = json.loads(captured.out)
    assert [item["session"] for item in emitted["sessions"]] == ["running"]
    assert emitted["should_be_running_count"] == 1


def test_cloud_chains_command_marker_only_sessions_have_process_dead_tmux_missing() -> None:
    """When only a marker exists (no tmux, no process), the row must show
    tmux=missing and process=dead (or unknown), not omit the fields."""
    script = _cloud_chains_command()

    # tmux_evidence defaults to missing when session not in tmux_names
    assert '"tmux_evidence": {"status": "alive" if name in tmux_names else "missing"}' in script
    # process_evidence calls _process_status which returns alive/dead/unknown
    assert "def _process_status(remote_spec, workspace=\"\", plan_name=\"\"):" in script
    assert '"process_evidence"' in script


def test_cloud_chain_status_payload_exposes_separate_evidence_fields() -> None:
    """``cloud_chain_status_payload`` must return separate marker_evidence,
    tmux_evidence, process_evidence, and active_step_evidence keys."""
    remote_spec = "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml"
    chain_yaml = "milestones:\n  - label: m1\n    idea: idea.md\n"
    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name="milestone-demo",
        last_state="prepped",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
        chain_session="megaplan-chain-demo",
    ).to_dict()
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets={},
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
            plan_status={"status": "running"},
            runner_probe="dead\n",
        ),
    )

    assert "marker_evidence" in payload
    assert "tmux_evidence" in payload
    assert "process_evidence" in payload
    assert "active_step_evidence" in payload
    # marker_evidence structure
    assert isinstance(payload["marker_evidence"], dict)
    assert "status" in payload["marker_evidence"]
    # tmux_evidence structure
    assert isinstance(payload["tmux_evidence"], dict)
    assert "status" in payload["tmux_evidence"]
    # process_evidence structure
    assert isinstance(payload["process_evidence"], dict)
    assert "status" in payload["process_evidence"]
    # active_step_evidence structure
    assert isinstance(payload["active_step_evidence"], dict)
    assert "status" in payload["active_step_evidence"]


def test_cloud_chain_status_payload_tmux_alive_sets_tmux_evidence_and_process_unknown() -> None:
    """When tmux is alive, ``tmux_evidence`` is *alive* while ``process_evidence``
    is *unknown* (not dead, not alive)."""
    remote_spec = "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml"
    chain_yaml = "milestones:\n  - label: m1\n    idea: idea.md\n"
    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name="milestone-demo",
        last_state="prepped",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
        chain_session="megaplan-chain-demo",
    ).to_dict()
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets={},
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
            plan_status={"status": "running"},
            runner_probe="tmux_alive\n",
        ),
    )

    assert payload["tmux_evidence"]["status"] == "alive"
    assert payload["process_evidence"]["status"] == "unknown"
    assert payload["runner"]["tmux_status"] == "alive"
    assert payload["runner"]["process_status"] == "unknown"


def test_cloud_chain_status_payload_active_step_from_plan_status() -> None:
    """``active_step_evidence`` must reflect the active step from plan status
    when available."""
    remote_spec = "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml"
    chain_yaml = "milestones:\n  - label: m1\n    idea: idea.md\n"
    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name="milestone-demo",
        last_state="prepped",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
        chain_session="megaplan-chain-demo",
    ).to_dict()
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets={},
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
            plan_status={
                "status": "running",
                "active_step": {
                    "phase": "execute",
                    "name": "run_tests",
                    "attempt": 2,
                    "worker_pid": 4242,
                },
            },
            runner_probe="dead\n",
        ),
    )

    assert payload["active_step_evidence"]["status"] == "present"
    assert payload["active_step_evidence"]["phase"] == "execute"
    assert payload["active_step_evidence"]["name"] == "run_tests"
    assert payload["active_step_evidence"]["attempt"] == 2
    assert payload["active_step_evidence"]["worker_pid"] == 4242


def test_cloud_chain_status_payload_active_step_absent_when_missing() -> None:
    """``active_step_evidence.status`` is *absent* when plan status has no active step."""
    remote_spec = "/workspace/chain-51d959cf/vibecomfy/.megaplan/initiatives/demo/chain.yaml"
    chain_yaml = "milestones:\n  - label: m1\n    idea: idea.md\n"
    chain_state = chain_module.ChainState(
        current_milestone_index=0,
        current_plan_name="milestone-demo",
        last_state="prepped",
        resolved_workspace="/workspace/chain-51d959cf/vibecomfy",
        chain_session="megaplan-chain-demo",
    ).to_dict()
    spec = CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(),
        secrets={},
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
            plan_status={"status": "running"},
            runner_probe="dead\n",
        ),
    )

    assert payload["active_step_evidence"]["status"] == "absent"
