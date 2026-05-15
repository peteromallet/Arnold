from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from megaplan.cloud.cli import (
    _ensure_repo_command,
    _marker_dir,
    _persistent_deploy_dir,
    build_cloud_parser,
    run_cloud_cli,
)
from megaplan.cloud.template import render_ensure_repo_command
from megaplan.cloud.spec import (
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


def _write_chain_spec(path: Path, milestones: list[dict[str, str]], *, base_branch: str | None = None) -> None:
    payload: dict[str, object] = {"milestones": milestones}
    if base_branch is not None:
        payload["base_branch"] = base_branch
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _json_payload_from_output(output: str) -> dict[str, object]:
    return json.loads(output[output.index("{"):])


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

        monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path, name=provider_name: _cloud_spec(name))
        monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

        args = parser.parse_args(
            ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
        )
        assert run_cloud_cli(tmp_path, args) == 0

        assert uploads[:2] == [
            (idea_dir / "ideas" / "foundation.txt", "/workspace/app/ideas/foundation.txt"),
            (idea_dir / "external.txt", "/opt/external.txt"),
        ]
        assert uploads[2][1] == "/workspace/app/chain.yaml"
        ensure_command = _ensure_repo_command(_cloud_spec(provider_name))
        assert commands[0] == ensure_command
        assert "command -v" in commands[1]
        assert "codex" in commands[1]
        assert "tmux" in commands[1]
        assert "shannon" not in commands[1]
        assert "claude" not in commands[1]
        assert "bun" not in commands[1]
        assert "git -C /workspace/app rev-parse --abbrev-ref HEAD" in commands[2]
        assert "git -C /workspace/app rev-parse HEAD" in commands[2]
        assert commands[3] == (
            "mkdir -p /workspace/app/.megaplan && "
            "if tmux has-session -t megaplan-chain 2>/dev/null; then "
            "echo 'megaplan-chain session already running'; "
            "else "
            "tmux new-session -d -s megaplan-chain -c /workspace/app "
            "'MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec /workspace/app/chain.yaml >> .megaplan/cloud-chain.log 2>&1'; "
            "echo 'started megaplan-chain session'; "
            "fi"
        )
        marker_payload = json.loads((_marker_dir(cloud_yaml_path) / "last_chain.json").read_text(encoding="utf-8"))
        assert marker_payload["remote_spec"] == "/workspace/app/chain.yaml"
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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert len(yaml.safe_load(spec_path.read_text(encoding="utf-8"))["milestones"]) == 3
    assert len(commands) == 4
    assert commands[0] == _ensure_repo_command(_cloud_spec("railway"))
    assert "command -v" in commands[1]
    assert "git -C /workspace/app rev-parse --abbrev-ref HEAD" in commands[2]
    assert "MEGAPLAN_TRUSTED_CONTAINER=1 megaplan chain start --spec /workspace/app/chain.yaml" in commands[3]


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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    payload = _json_payload_from_output(capsys.readouterr().out)
    assert payload["event"] == "cloud_chain_launched"
    assert payload["remote_spec"] == "/workspace/app/chain.yaml"
    assert payload["current_milestone"] == "m1"
    assert payload["plan_name"] is None
    assert payload["pr_number"] is None
    assert payload["repo"] == {
        "url": "https://github.com/example/app.git",
        "branch": "setup/cloud",
        "workspace": "/workspace/app",
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
    assert payload["tmux"] == {"session": "megaplan-chain", "status": "started"}


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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert yaml.safe_load(spec_path.read_text(encoding="utf-8")) == {
        "milestones": [{"label": "m1", "idea": "/workspace/app/ideas/foundation.txt"}],
    }
    assert uploaded_specs["/workspace/app/chain.yaml"]["base_branch"] == "setup/cloud"
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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert uploaded_specs["/workspace/app/chain.yaml"]["base_branch"] == "release/candidate"
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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: object())

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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: cloud_spec)
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

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
                    stdout="bun claude shannon tmux\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "agent_deps_missing"
    assert payload["missing_commands"] == ["bun", "claude", "shannon", "tmux"]
    assert payload["missing_env"] == []
    assert "ANTHROPIC_API_KEY" in payload["preflight"]["env_hints"]
    assert "cloud.yaml agents.default does not override" in payload["preflight"]["warning"]
    assert commands[0] == _ensure_repo_command(_cloud_spec("railway"))
    assert "command -v" in commands[1]
    assert "bun" in commands[1]
    assert "claude" in commands[1]
    assert "shannon" in commands[1]
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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

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
    assert commands[0] == _ensure_repo_command(_cloud_spec("railway"))
    assert "command -v" in commands[1]
    assert "codex" in commands[1]
    assert "tmux" in commands[1]
    assert "shannon" not in commands[1]
    assert "claude" not in commands[1]
    assert "bun" not in commands[1]
    assert "tmux new-session" not in " ".join(commands)
    assert uploads == []


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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(["cloud", "bootstrap", str(idea_file), "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 0

    assert uploads == [(idea_file, "/workspace/app/idea.txt")]
    assert commands == [
        _ensure_repo_command(_cloud_spec("railway")),
        "cd /workspace/app && megaplan init --project-dir /workspace/app --idea-file /workspace/app/idea.txt --auto-start --robustness standard"
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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(
        ["cloud", "bootstrap", str(idea_file), "--plan-name", "custom", "--cloud-yaml", str(cloud_yaml_path)]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    assert commands == [
        _ensure_repo_command(_cloud_spec("railway")),
        "cd /workspace/app && megaplan init --project-dir /workspace/app --idea-file /workspace/app/idea.txt --auto-start --robustness standard --name custom"
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

    monkeypatch.setattr("megaplan.cloud.cli.get_provider", provider_factory)

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
        "cd /workspace/megaplan && megaplan init --project-dir /workspace/megaplan --idea-file /workspace/megaplan/idea.txt --auto-start --robustness standard"
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

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec("railway"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

    args = parser.parse_args(["cloud", "bootstrap", str(idea_file), "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "provider_failed"
    assert "ensure repo checkout failed" in payload["message"]
    assert uploads == []
    assert commands == [_ensure_repo_command(_cloud_spec("railway"))]
