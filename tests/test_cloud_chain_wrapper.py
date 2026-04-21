from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from megaplan.cloud.cli import (
    _marker_dir,
    _persistent_deploy_dir,
    build_cloud_parser,
    run_cloud_cli,
)
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


def _write_chain_spec(path: Path, milestones: list[dict[str, str]]) -> None:
    path.write_text(yaml.safe_dump({"milestones": milestones}), encoding="utf-8")


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
                return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout="started\n", stderr="")

        monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path, name=provider_name: _cloud_spec(name))
        monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: StubProvider())

        args = parser.parse_args(
            ["cloud", "chain", str(spec_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml_path)]
        )
        assert run_cloud_cli(tmp_path, args) == 0

        assert uploads == [
            (idea_dir / "ideas" / "foundation.txt", "/workspace/app/ideas/foundation.txt"),
            (idea_dir / "external.txt", "/opt/external.txt"),
            (spec_path, "/workspace/app/chain.yaml"),
        ]
        assert commands == [
            "cd /workspace/app && megaplan chain start --spec /workspace/app/chain.yaml"
        ]
        marker_payload = json.loads((_marker_dir(cloud_yaml_path) / "last_chain.json").read_text(encoding="utf-8"))
        assert marker_payload["remote_spec"] == "/workspace/app/chain.yaml"
        if provider_name == "local":
            assert _persistent_deploy_dir(_cloud_spec("local")).exists()


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
        "cd /workspace/app && megaplan init --project-dir /workspace/app --idea-file /workspace/app/idea.txt --auto-start --robustness standard --name custom"
    ]
