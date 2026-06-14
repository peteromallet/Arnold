from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from arnold.pipelines.megaplan.cloud.cli import (
    _chain_launch_verification_command,
    _chain_start_command,
    _chain_state_reset_command,
    _ensure_repo_command,
    _marker_dir,
    _normalized_chain_upload_spec,
    _persistent_deploy_dir,
    _tmux_chain_launch_command,
    _tmux_chain_restart_command,
    build_cloud_parser,
    run_cloud_cli,
)
from arnold.pipelines.megaplan.cloud.template import render_ensure_repo_command
from arnold.pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    LocalSpec,
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


def _cloud_spec(provider: str) -> CloudSpec:
    kwargs: dict[str, object] = {
        "provider": provider,
        "repo": RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        "agents": {"default": "codex"},
        "codex": CodexSpec(model="ops-model", reasoning="medium"),
        "mode": "idle",
        "megaplan": MegaplanSpec(ref="main"),
        "resources": ResourcesSpec(volume="agent-volume", port=8080),
        "secrets": [],
        "railway": RailwaySpec(service="agent", session="agent", project=None),
        "toolchains": [],
    }
    if provider == "local":
        kwargs["local"] = LocalSpec(compose_project="local-wrapper", workdir="workspace")
    return CloudSpec(**kwargs)


def test_normalized_chain_upload_spec_overlays_cloud_driver_stall_threshold(
    tmp_path: Path,
) -> None:
    local_spec = tmp_path / "chain.yaml"
    local_spec.write_text(
        yaml.safe_dump(
            {
                "driver": {"max_iterations": 20},
                "milestones": [{"label": "m1", "idea": "/workspace/app/m1.md"}],
            }
        ),
        encoding="utf-8",
    )

    upload_spec = _normalized_chain_upload_spec(
        local_spec,
        base_branch="main",
        driver_overrides={"max_stall_iterations": 17},
    )

    try:
        payload = yaml.safe_load(upload_spec.read_text(encoding="utf-8"))
    finally:
        if upload_spec != local_spec:
            upload_spec.unlink(missing_ok=True)

    assert payload["driver"]["max_iterations"] == 20
    assert payload["driver"]["max_stall_iterations"] == 17


def _write_chain_spec(path: Path, milestones: list[dict[str, str]], *, base_branch: str | None = None) -> None:
    payload: dict[str, object] = {"milestones": milestones}
    if base_branch is not None:
        payload["base_branch"] = base_branch
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _json_payload_from_output(output: str) -> dict[str, object]:
    return json.loads(output[output.index("{"):])


def test_cloud_chain_no_git_refresh_reaches_remote_chain_start() -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "chain", "chain.yaml", "--no-git-refresh"])

    command = _tmux_chain_launch_command(
        "/workspace/app",
        "/workspace/app/chain.yaml",
        no_git_refresh=bool(args.no_git_refresh),
    )

    assert args.no_git_refresh is True
    assert (
        "MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold.pipelines.megaplan chain start "
        "--spec /workspace/app/chain.yaml --no-git-refresh"
    ) in command


def test_cloud_chain_uploads_files_and_writes_marker_for_railway_and_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(
        spec_path,
        [
            {"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"},
            {"label": "m2", "idea": "/opt/external.txt"},
        ],
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    (idea_dir / "external.txt").write_text("external\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")

    for provider_name in ("railway", "local"):
        uploads: list[tuple[Path, str]] = []
        commands: list[str] = []

        class StubProvider:
            supports_session = False

            def upload_file(self, src: Path, dest: str) -> None:
                uploads.append((src, dest))

            def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if "command -v" in command:
                    return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="\n", stderr="")
                if "git -C" in command:
                    return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="main\nabc123\n", stderr="")
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="started\n", stderr="")

        monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path, name=provider_name: _cloud_spec(name))
        monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

        args = parser.parse_args(
            ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
        )
        assert run_cloud_cli(tmp_path, args) == 0

        assert uploads[:2] == [
            (idea_dir / "ideas" / "foundation.txt", "/workspace/chain-8fb6734d/app/ideas/foundation.txt"),
            (idea_dir / "external.txt", "/opt/external.txt"),
        ]
        assert uploads[2][1] == "/workspace/chain-8fb6734d/app/chain.yaml"
        ensure_command = _ensure_repo_command(
            replace(
                _cloud_spec(provider_name),
                repo=replace(_cloud_spec(provider_name).repo, workspace="/workspace/chain-8fb6734d/app"),
            )
        )
        assert commands[0] == ensure_command
        assert "command -v" in commands[1]
        assert "codex" in commands[1]
        assert "tmux" in commands[1]
        assert "shannon" not in commands[1]
        assert "claude" not in commands[1]
        assert "bun" not in commands[1]
        assert "git -C /workspace/chain-8fb6734d/app rev-parse --abbrev-ref HEAD" in commands[2]
        assert "git -C /workspace/chain-8fb6734d/app rev-parse HEAD" in commands[2]
        assert "python3 - <<'MEGAPLAN_RESET'" in commands[3]
        assert ".megaplan/cloud-chain-megaplan-chain-chain-8fb6734d.log" in commands[3]
        assert "tmux has-session -t megaplan-chain-chain-8fb6734d" in commands[4]
        assert "git -C \"$SRC\" pull --ff-only" in commands[4]
        assert "pip install -e \"$SRC\"" in commands[4]
        assert "/usr/local/bin/mp-refresh-megaplan" not in commands[4]
        assert "MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold.pipelines.megaplan chain start --spec /workspace/chain-8fb6734d/app/chain.yaml" in commands[4]
        assert "python3 - <<'MEGAPLAN_VERIFY'" in commands[5]
        marker_payload = json.loads((_marker_dir(cloud_yaml_path) / "last_chain.json").read_text(encoding="utf-8"))
        assert marker_payload["remote_spec"] == "/workspace/chain-8fb6734d/app/chain.yaml"
        assert marker_payload["chain_session"] == "megaplan-chain-chain-8fb6734d"
        if provider_name == "local":
            assert _persistent_deploy_dir(_cloud_spec("local")).exists()


def test_cloud_chain_three_sprint_smoke_dispatches_trusted_container_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "cloud-chain-smoke.yaml"
    _write_chain_spec(
        spec_path,
        [
            {"label": "sprint-1", "idea": "/workspace/app/ideas/sprint-1.md"},
            {"label": "sprint-2", "idea": "/workspace/app/ideas/sprint-2.md"},
            {"label": "sprint-3", "idea": "/workspace/app/ideas/sprint-3.md"},
        ],
    )
    idea_dir = tmp_path / "smoke-ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    for index in range(1, 4):
        (idea_dir / "ideas" / f"sprint-{index}.md").write_text(f"sprint {index}\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            return None

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "command -v" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="\n", stderr="")
            if "git -C" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="main\nabc123\n", stderr="")
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="started\n", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert len(yaml.safe_load(spec_path.read_text(encoding="utf-8"))["milestones"]) == 3
    assert len(commands) == 6
    assert "/workspace/cloud-chain-smoke-4bb0e3d6/app" in commands[0]
    assert "command -v" in commands[1]
    assert "git -C /workspace/cloud-chain-smoke-4bb0e3d6/app rev-parse --abbrev-ref HEAD" in commands[2]
    assert "MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold.pipelines.megaplan chain start --spec /workspace/cloud-chain-smoke-4bb0e3d6/app/chain.yaml" in commands[4]


def test_cloud_chain_prints_launch_provenance_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}])
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    cloud_spec = replace(
        _cloud_spec("railway"),
        repo=replace(_cloud_spec("railway").repo, branch="setup/cloud"),
        megaplan=MegaplanSpec(ref="feature/cloud-runtime"),
    )

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            return None

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "command -v" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="\n", stderr="")
            if "git -C" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="setup/cloud\ndeadbeefcafebabe\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=["ssh"],
                returncode=0,
                stdout="started megaplan-chain session\n",
                stderr="",
            )

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    payload = _json_payload_from_output(capsys.readouterr().out)
    assert payload["event"] == "cloud_chain_launched"
    assert payload["remote_spec"] == "/workspace/chain-c055b7fa/app/chain.yaml"
    assert payload["current_milestone"] == "m1"
    assert payload["plan_name"] is None
    assert payload["pr_number"] is None
    assert payload["repo"] == {
        "url": "https://github.com/example/app.git",
        "branch": "setup/cloud",
        "workspace": "/workspace/chain-c055b7fa/app",
        "head": "deadbeefcafebabe",
        "checked_out_branch": "setup/cloud",
    }
    assert payload["chain"]["base_branch"] == "setup/cloud"
    assert payload["chain"]["resolved_phase_map_summary"][0]["label"] == "m1"
    assert payload["chain"]["resolved_phase_map_summary"][0]["runtime_commands"] == ["codex", "tmux"]
    assert payload["megaplan"] == {
        "ref": "feature/cloud-runtime",
        "install_source": "cloud_image_runtime",
    }
    assert payload["uploaded_idea_count"] == 1
    assert payload["tmux"] == {"session": "megaplan-chain-chain-c055b7fa", "status": "unknown"}
    assert payload["log"]["chain_log"].endswith(
        "/.megaplan/cloud-chain-megaplan-chain-chain-c055b7fa.log"
    )
    assert payload["launch"]["derived_workspace"] is True
    assert payload["launch"]["derived_session"] is True


def test_cloud_chain_injects_repo_branch_into_uploaded_spec_without_mutating_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}])
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    cloud_spec = replace(_cloud_spec("railway"), repo=replace(_cloud_spec("railway").repo, branch="setup/cloud"))
    uploaded_specs: dict[str, dict[str, object]] = {}

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            if dest.endswith("chain.yaml"):
                uploaded_specs[dest] = yaml.safe_load(src.read_text(encoding="utf-8"))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "command -v" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="\n", stderr="")
            if "git -C" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="main\nabc123\n", stderr="")
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="started\n", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert yaml.safe_load(spec_path.read_text(encoding="utf-8")) == {
        "milestones": [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}],
    }
    uploaded = uploaded_specs["/workspace/chain-c055b7fa/app/chain.yaml"]
    assert uploaded["base_branch"] == "setup/cloud"
    assert uploaded["milestones"][0]["idea"] == "/workspace/chain-c055b7fa/app/ideas/foundation.txt"
    marker_payload = json.loads((_marker_dir(cloud_yaml_path) / "last_chain.json").read_text(encoding="utf-8"))
    assert marker_payload["base_branch"] == "setup/cloud"


def test_cloud_chain_preserves_explicit_base_branch_in_uploaded_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(
        spec_path,
        [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}],
        base_branch="release/candidate",
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    cloud_spec = replace(_cloud_spec("railway"), repo=replace(_cloud_spec("railway").repo, branch="setup/cloud"))
    uploaded_specs: dict[str, dict[str, object]] = {}

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            if dest.endswith("chain.yaml"):
                uploaded_specs[dest] = yaml.safe_load(src.read_text(encoding="utf-8"))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "command -v" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="\n", stderr="")
            if "git -C" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="main\nabc123\n", stderr="")
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="started\n", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    uploaded = uploaded_specs["/workspace/chain-c055b7fa/app/chain.yaml"]
    assert uploaded["base_branch"] == "release/candidate"
    assert uploaded["milestones"][0]["idea"] == "/workspace/chain-c055b7fa/app/ideas/foundation.txt"
    marker_payload = json.loads((_marker_dir(cloud_yaml_path) / "last_chain.json").read_text(encoding="utf-8"))
    assert marker_payload["base_branch"] == "release/candidate"


def test_cloud_chain_idea_dir_resolves_repo_relative_paths_without_duplicate_tail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "docs/cloud/ideas/foundation.md"}])
    idea_dir = tmp_path / "docs" / "cloud" / "ideas"
    idea_dir.mkdir(parents=True)
    idea_file = idea_dir / "foundation.md"
    idea_file.write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "command -v" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="\n", stderr="")
            if "git -C" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="main\nabc123\n", stderr="")
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="started\n", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert uploads[0] == (idea_file, "docs/cloud/ideas/foundation.md")


def test_cloud_chain_missing_local_idea_reports_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "/workspace/app/ideas/missing.txt"}])
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: object())

    args = parser.parse_args(["cloud", "chain", str(spec_path), "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "missing_idea_file"
    assert "--idea-dir" in payload["message"]


def test_cloud_chain_missing_repo_relative_idea_reports_tried_paths_before_remote_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "docs/cloud/ideas/missing.md"}])
    idea_dir = tmp_path / "docs" / "cloud" / "ideas"
    idea_dir.mkdir(parents=True)
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "missing_idea_file"
    assert payload["milestone"] == "m1"
    assert str(idea_dir / "docs" / "cloud" / "ideas" / "missing.md") in payload["tried_paths"]
    assert str(tmp_path / "docs" / "cloud" / "ideas" / "missing.md") in payload["tried_paths"]
    assert str(idea_dir / "missing.md") in payload["tried_paths"]
    assert "Invoke from the repository root" in payload["message"]
    assert "--idea-dir" in payload["message"]
    assert commands == []
    assert uploads == []


def test_cloud_chain_preflight_blocks_missing_configured_secret_before_remote_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}])
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    cloud_spec = replace(_cloud_spec("railway"), secrets=["ANTHROPIC_API_KEY"])
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "cloud_preflight_failed"
    assert payload["missing_env"] == ["ANTHROPIC_API_KEY"]
    assert payload["missing_commands"] == []
    assert payload["preflight"]["runtime_commands"] == ["codex", "tmux"]
    assert commands == []
    assert uploads == []


def test_cloud_chain_preflight_blocks_missing_remote_commands_before_tmux(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(
        spec_path,
        [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt", "profile": "premium"}],
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "command -v" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="bun claude tmux\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles._resolve_default_vendor", lambda: "claude")
    monkeypatch.setattr("arnold.pipelines.megaplan.profiles.policy._resolve_default_vendor", lambda: "claude")

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "agent_deps_missing"
    assert payload["missing_commands"] == ["bun", "claude", "tmux"]
    assert payload["missing_env"] == []
    assert "ANTHROPIC_API_KEY" in payload["preflight"]["env_hints"]
    assert "cloud.yaml agents.default does not override" in payload["preflight"]["warning"]
    assert "/workspace/chain-c055b7fa/app" in commands[0]
    assert "command -v" in commands[1]
    assert "bun" in commands[1]
    assert "claude" in commands[1]
    # Post-cutover: Shannon is no longer a PATH-resolved command — it runs
    # from megaplan/vendor/shannon under bun.
    assert "shannon" not in commands[1]
    assert "tmux" in commands[1]
    assert "codex" not in commands[1]
    assert "tmux new-session" not in " ".join(commands)
    assert uploads == []


def test_cloud_chain_preflight_blocks_missing_codex_commands_before_tmux(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path, [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}])
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "command -v" in command:
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="codex tmux\n", stderr="")
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "agent_deps_missing"
    assert payload["missing_commands"] == ["codex", "tmux"]
    assert payload["missing_env"] == []
    assert payload["preflight"]["runtime_commands"] == ["codex", "tmux"]
    assert "OPENAI_API_KEY" in payload["preflight"]["env_hints"]
    assert "/workspace/chain-c055b7fa/app" in commands[0]
    assert "command -v" in commands[1]
    assert "codex" in commands[1]
    assert "tmux" in commands[1]
    assert "shannon" not in commands[1]
    assert "claude" not in commands[1]
    assert "bun" not in commands[1]
    assert "tmux new-session" not in " ".join(commands)
    assert uploads == []


def test_cloud_chain_preflight_codex_vendor_premium_profile_requires_only_openai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Vendor-neutral premium profile with codex vendor → only codex commands, OPENAI_API_KEY."""
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(
        spec_path,
        [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt", "profile": "premium", "vendor": "codex"}],
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "command -v" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="\n",
                    stderr="",
                )
            if "git -C" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="main\nabc123\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    # Preflight should show only codex commands and OPENAI_API_KEY
    payload = _json_payload_from_output(capsys.readouterr().out)
    preflight = payload["chain"]["resolved_phase_map_summary"][0]
    assert preflight["runtime_commands"] == ["codex", "tmux"]
    assert "OPENAI_API_KEY" in preflight["env_hints"]
    assert "ANTHROPIC_API_KEY" not in preflight["env_hints"]


def test_cloud_chain_preflight_apex_profile_requires_both_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Mixed apex profile → both claude and codex commands, both env hints."""
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(
        spec_path,
        [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt", "profile": "apex"}],
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "command -v" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="\n",
                    stderr="",
                )
            if "git -C" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="main\nabc123\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    payload = _json_payload_from_output(capsys.readouterr().out)
    preflight = payload["chain"]["resolved_phase_map_summary"][0]
    assert "claude" in preflight["runtime_commands"]
    assert "codex" in preflight["runtime_commands"]
    assert "bun" in preflight["runtime_commands"]
    assert "tmux" in preflight["runtime_commands"]
    assert "ANTHROPIC_API_KEY" in preflight["env_hints"]
    assert "OPENAI_API_KEY" in preflight["env_hints"]


def test_cloud_chain_preflight_explicit_codex_pins_override_claude_vendor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Concrete codex pins → OPENAI_API_KEY even under claude vendor in chain wrapper."""
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(
        spec_path,
        [{
            "label": "m1",
            "idea": "/workspace/app/ideas/foundation.txt",
            "profile": "premium",
            "vendor": "claude",
            "phase_model": ["execute=codex:high"],
        }],
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "foundation.txt").write_text("foundation\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []
    uploads: list[tuple[Path, str]] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if "command -v" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="\n",
                    stderr="",
                )
            if "git -C" in command:
                return subprocess.CompletedProcess(
                    args=["ssh"],
                    returncode=0,
                    stdout="main\nabc123\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    payload = _json_payload_from_output(capsys.readouterr().out)
    preflight = payload["chain"]["resolved_phase_map_summary"][0]
    assert "codex" in preflight["runtime_commands"]
    assert "OPENAI_API_KEY" in preflight["env_hints"]


def test_cloud_bootstrap_omits_name_when_plan_name_is_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("bootstrap me\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    uploads: list[tuple[Path, str]] = []
    commands: list[str] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="bootstrapped\n", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(["cloud", "bootstrap", str(idea_file), "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 0

    assert uploads == [(idea_file, "/workspace/app/idea.txt")]
    assert commands == [
        _ensure_repo_command(_cloud_spec("railway")),
        "cd /workspace/app && arnold init --project-dir /workspace/app --idea-file /workspace/app/idea.txt --auto-start --robustness standard"
    ]
    assert "--name" not in commands[0]


def test_cloud_bootstrap_includes_name_when_plan_name_is_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("bootstrap me\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    commands: list[str] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            return None

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="bootstrapped\n", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "bootstrap", str(idea_file), "--plan-name", "custom", "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert commands == [
        _ensure_repo_command(_cloud_spec("railway")),
        "cd /workspace/app && arnold init --project-dir /workspace/app --idea-file /workspace/app/idea.txt --auto-start --robustness standard --name custom"
    ]


def test_cloud_bootstrap_repo_overrides_are_in_memory_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("bootstrap me\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    original_yaml = {
        "provider": "railway",
        "repo": {
            "url": "https://github.com/example/original.git",
            "branch": "main",
            "workspace": "/workspace/app",
        },
        "agents": {"default": "codex"},
        "mode": "idle",
    }
    cloud_yaml_path.write_text(yaml.safe_dump(original_yaml), encoding="utf-8")
    seen_specs: list[CloudSpec] = []
    uploads: list[tuple[Path, str]] = []
    commands: list[str] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="bootstrapped\n", stderr="")

    def provider_factory(_name: str, spec: CloudSpec) -> StubProvider:
        seen_specs.append(spec)
        return StubProvider()

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", provider_factory)

    args = parser.parse_args(
        [
            "cloud",
            "bootstrap",
            str(idea_file),
            "--cloud-yaml",
            str(cloud_yaml_path),
            "--repo-url",
            "https://github.com/openai/megaplan.git",
            "--repo-branch",
            "feature/resident",
            "--repo-workspace",
            "/workspace/megaplan",
        ]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert seen_specs[0].repo.url == "https://github.com/openai/megaplan.git"
    assert seen_specs[0].repo.branch == "feature/resident"
    assert seen_specs[0].repo.workspace == "/workspace/megaplan"
    assert uploads == [(idea_file, "/workspace/megaplan/idea.txt")]
    assert commands == [
        _ensure_repo_command(seen_specs[0]),
        "cd /workspace/megaplan && arnold init --project-dir /workspace/megaplan --idea-file /workspace/megaplan/idea.txt --auto-start --robustness standard"
    ]
    assert yaml.safe_load(cloud_yaml_path.read_text(encoding="utf-8")) == original_yaml


def test_direct_cloud_prepare_uses_shared_ensure_repo_command() -> None:
    spec = _cloud_spec("railway")

    assert _ensure_repo_command(spec) == render_ensure_repo_command(spec.repo)


def test_cloud_bootstrap_fails_before_upload_when_ensure_repo_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    idea_file = tmp_path / "idea.txt"
    idea_file.write_text("bootstrap me\n", encoding="utf-8")
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    uploads: list[tuple[Path, str]] = []
    commands: list[str] = []

    class StubProvider:
        supports_session = False

        def upload_file(self, src: Path, dest: str) -> None:
            uploads.append((src, dest))

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(args=["ssh"], returncode=42, stdout="", stderr="clone failed\n")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(["cloud", "bootstrap", str(idea_file), "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "provider_failed"
    assert "ensure repo checkout failed" in payload["message"]
    assert uploads == []
    assert commands == [_ensure_repo_command(_cloud_spec("railway"))]


def test_mp_chain_wrapper_matches_canonical_command(tmp_path: Path) -> None:
    """The wrapper's effective command matches _chain_start_command() output.

    We replace ``python`` with a stub that records its arguments and env,
    then verify that the wrapper produces the same direct module command as
    the canonical ``_chain_start_command()`` helper for both normal and
    --one modes.
    """
    wrapper_path = (
        Path(__file__).parent.parent / "arnold" / "pipelines" / "megaplan" / "cloud" / "wrappers" / "mp-chain"
    )
    spec_path = "/workspace/app/chain.yaml"

    # Stub python: records its arguments + env var to a known file.
    stub_output_file = tmp_path / "stub-output.txt"
    python_stub = tmp_path / "python"
    python_stub.write_text(
        "#!/bin/bash\n"
        f'echo "ARGS=$*" >> {shlex.quote(str(stub_output_file))}'
        "\n"
        f'echo "MEGAPLAN_TRUSTED_CONTAINER=${{MEGAPLAN_TRUSTED_CONTAINER:-unset}}" >> {shlex.quote(str(stub_output_file))}'
        "\n"
    )
    python_stub.chmod(0o755)

    # Include standard bin directories so bash builtins and env are available.
    env = {
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "HOME": str(tmp_path),
    }
    bash_bin = "/bin/bash"

    # ---- without --one ----
    expected_cmd = _chain_start_command(spec_path, one_shot=False)
    (tmp_path / ".megaplan").mkdir(parents=True, exist_ok=True)
    stub_output_file.write_text("")  # clear

    subprocess.run(
        [bash_bin, str(wrapper_path), spec_path],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )

    stub_output = stub_output_file.read_text().strip()
    stub_lines = stub_output.split("\n")
    assert len(stub_lines) >= 2, f"unexpected stub output: {stub_output!r}"
    args_line = stub_lines[0]  # ARGS=chain start --spec <path>
    env_line = stub_lines[1]   # MEGAPLAN_TRUSTED_CONTAINER=1

    assert "MEGAPLAN_TRUSTED_CONTAINER=1" in env_line
    # The wrapper must emit the same direct module arguments as the canonical helper.
    expected_args = "-m arnold.pipelines.megaplan chain start --spec " + spec_path
    assert expected_args in args_line, (
        f"expected args {expected_args!r} in {args_line!r}"
    )
    assert "--one" not in args_line

    # The canonical command must contain the log redirect + env var.
    assert "MEGAPLAN_TRUSTED_CONTAINER=1" in expected_cmd
    assert ".megaplan/cloud-chain.log" in expected_cmd

    # ---- with --one ----
    expected_cmd_one = _chain_start_command(spec_path, one_shot=True)
    stub_output_file.write_text("")  # clear

    subprocess.run(
        [bash_bin, str(wrapper_path), spec_path, "--one"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
    )

    stub_output_one = stub_output_file.read_text().strip()
    stub_lines_one = stub_output_one.split("\n")
    assert len(stub_lines_one) >= 2, f"unexpected stub output: {stub_output_one!r}"
    args_line_one = stub_lines_one[0]

    assert "MEGAPLAN_TRUSTED_CONTAINER=1" in stub_lines_one[1]
    expected_args_one = "-m arnold.pipelines.megaplan chain start --spec " + spec_path + " --one"
    assert expected_args_one in args_line_one, (
        f"expected args {expected_args_one!r} in {args_line_one!r}"
    )

    assert "MEGAPLAN_TRUSTED_CONTAINER=1" in expected_cmd_one
    assert ".megaplan/cloud-chain.log" in expected_cmd_one
    assert "--one" in expected_cmd_one


def test_tmux_chain_restart_refreshes_megaplan_before_one_shot_start() -> None:
    command = _tmux_chain_restart_command("/workspace/app", "/workspace/app/chain.yaml")

    assert "/usr/local/bin/mp-refresh-megaplan" not in command
    assert "source clone missing at $SRC; skipping editable install" in command
    assert "MEGAPLAN_TRUSTED_CONTAINER=1 python -m arnold.pipelines.megaplan chain start --spec /workspace/app/chain.yaml --one" in command
    assert ">> .megaplan/cloud-chain.log 2>&1" in command
    assert "refusing restart" in command


def test_chain_state_reset_command_removes_stalled_unstarted_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    plans = workspace / ".megaplan" / "plans"
    half_plan = plans / "half-init-plan"
    half_plan.mkdir(parents=True)
    state_path = plans / ".chains" / "chain-deadbeef.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "current_milestone_index": 0,
                "current_plan_name": "half-init-plan",
                "last_state": "stalled",
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan").mkdir(exist_ok=True)

    command = _chain_state_reset_command(
        workspace=str(workspace),
        state_path=str(state_path),
        log_relative=".megaplan/reset.log",
    )
    result = subprocess.run(["bash", "-lc", command], text=True, capture_output=True, check=False)

    assert result.returncode == 0
    assert not state_path.exists()
    assert not half_plan.exists()
    log = (workspace / ".megaplan" / "reset.log").read_text(encoding="utf-8")
    assert '"status": "reset"' in log
    assert "stalled-without-completed-milestones" in log


def test_chain_state_reset_command_preserves_progressed_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    state_path = workspace / ".megaplan" / "plans" / ".chains" / "chain-deadbeef.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "current_milestone_index": 1,
                "current_plan_name": "plan-for-m2",
                "last_state": "stalled",
                "completed": [{"label": "m1", "plan": "plan-for-m1", "status": "done"}],
            }
        ),
        encoding="utf-8",
    )

    command = _chain_state_reset_command(
        workspace=str(workspace),
        state_path=str(state_path),
        log_relative=".megaplan/reset.log",
    )
    result = subprocess.run(["bash", "-lc", command], text=True, capture_output=True, check=False)

    assert result.returncode == 0
    assert state_path.exists()
    log = (workspace / ".megaplan" / "reset.log").read_text(encoding="utf-8")
    assert '"status": "preserved"' in log


def test_tmux_chain_launch_refuses_running_different_chain(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux = bin_dir / "tmux"
    tmux.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = has-session ]; then exit 0; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    tmux.chmod(0o755)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = tmp_path / "markers" / "megaplan-chain-a.json"
    marker.parent.mkdir()
    marker.write_text(json.dumps({"identity_digest": "other"}), encoding="utf-8")
    command = _tmux_chain_launch_command(
        str(workspace),
        str(workspace / "chain.yaml"),
        session_name="megaplan-chain-a",
        marker_path=str(marker),
        identity_digest="this-chain",
    )

    result = subprocess.run(
        ["bash", "-lc", command],
        text=True,
        capture_output=True,
        check=False,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
    )

    assert result.returncode == 17
    assert "different chain" in result.stdout


def test_tmux_chain_launch_builds_clone_based_refresh_command() -> None:
    spec = replace(
        _cloud_spec("railway"),
        megaplan=MegaplanSpec(
            ref="feature/cloud-refresh",
            repo="https://github.com/peteromallet/arnold.git",
            src_path="/workspace/shared/arnold",
        ),
    )

    command = _tmux_chain_launch_command(
        "/workspace/app",
        "/workspace/app/chain.yaml",
        session_name="megaplan-chain-a",
        spec=spec,
        log_relative=".megaplan/cloud-chain-megaplan-chain-a.log",
        marker_path="/workspace/.megaplan/cloud-sessions/megaplan-chain-a.json",
        identity_digest="abc123",
    )

    assert "/usr/local/bin/mp-refresh-megaplan" not in command
    assert "SRC=/workspace/shared/arnold" in command
    assert "REPO=https://github.com/peteromallet/arnold.git" in command
    assert "git clone --branch \"$REF\" \"$CLONE_URL\" \"$SRC\"" in command
    assert "x-access-token:${GITHUB_TOKEN}@github.com" in command
    assert "git -C \"$SRC\" pull --ff-only" in command
    assert "pip install -e \"$SRC\"" in command
    assert ">> .megaplan/cloud-chain-megaplan-chain-a.log 2>&1" in command


def test_chain_launch_verification_reports_alive_and_advanced(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tmux = bin_dir / "tmux"
    tmux.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    tmux.chmod(0o755)
    workspace = tmp_path / "workspace"
    state_path = workspace / ".megaplan" / "plans" / ".chains" / "chain-deadbeef.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({"current_milestone_index": 0, "current_plan_name": "plan-m1", "completed": []}),
        encoding="utf-8",
    )
    log_path = workspace / ".megaplan" / "cloud-chain-megaplan-chain-a.log"
    log_path.write_text("driver started\n", encoding="utf-8")
    command = _chain_launch_verification_command(
        workspace=str(workspace),
        session_name="megaplan-chain-a",
        state_path=str(state_path),
        log_path=str(log_path),
        attempts=1,
        sleep_seconds=0,
    )

    result = subprocess.run(
        ["bash", "-lc", command],
        text=True,
        capture_output=True,
        check=False,
        env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["session_alive"] is True
    assert payload["advanced_past_init"] is True
    assert payload["chain_log_size"] > 0
