from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

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


def _local_spec() -> CloudSpec:
    return CloudSpec(
        provider="local",
        repo=RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode="idle",
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=[],
        railway=RailwaySpec(service="agent", session="agent", project=None),
        local=LocalSpec(compose_project="local-smoke", workdir="workspace"),
        toolchains=[],
    )


def test_local_build_reuses_persistent_materialized_dir_and_destroy_preserves_markers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    parser = _parser()
    provider_calls: list[tuple[str, Path | None]] = []
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: local\n", encoding="utf-8")

    class DummyProvider:
        supports_session = False

        def build(self, deploy_dir: Path) -> int:
            provider_calls.append(("build", deploy_dir))
            return 0

        def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
            del secrets
            provider_calls.append(("deploy", deploy_dir))
            return 0

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            provider_calls.append(("exec", None))
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=command, stderr="")

        def attach(self) -> int:
            raise AssertionError("attach should not be called")

        def logs(self, *, follow: bool = True) -> int:
            raise AssertionError("logs should not be called")

        def status_payload(self, *, plan: str | None, workspace: str) -> dict:
            del plan, workspace
            raise AssertionError("status should not be called")

        def down(self) -> int:
            provider_calls.append(("down", None))
            return 0

        def destroy(self, *, volume: str | None = None) -> int:
            provider_calls.append(("destroy", None))
            return 0

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _local_spec())
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: DummyProvider())

    build_args = parser.parse_args(["cloud", "build", "--cloud-yaml", str(cloud_yaml_path)])
    exec_args = parser.parse_args(["cloud", "exec", "--cloud-yaml", str(cloud_yaml_path), "pwd"])
    down_args = parser.parse_args(["cloud", "down", "--cloud-yaml", str(cloud_yaml_path)])
    destroy_args = parser.parse_args(["cloud", "destroy", "--yes", "--cloud-yaml", str(cloud_yaml_path)])

    assert run_cloud_cli(tmp_path, build_args) == 0
    first_deploy_dir = provider_calls[0][1]
    assert first_deploy_dir == _persistent_deploy_dir(_local_spec())
    assert run_cloud_cli(tmp_path, exec_args) == 0
    assert run_cloud_cli(tmp_path, down_args) == 0
    assert run_cloud_cli(tmp_path, build_args) == 0
    assert provider_calls[3][1] == first_deploy_dir

    marker_dir = _marker_dir(cloud_yaml_path)
    marker_file = marker_dir / "last_chain.json"
    marker_file.write_text(json.dumps({"remote_spec": "/workspace/chain.yaml"}), encoding="utf-8")
    assert run_cloud_cli(tmp_path, destroy_args) == 0
    assert marker_file.exists()
    assert not first_deploy_dir.exists()


def test_marker_dir_is_stable_for_same_cloud_yaml_path_across_provider_switches(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")

    railway_marker = _marker_dir(cloud_yaml_path)
    local_marker = _marker_dir(cloud_yaml_path)

    assert railway_marker == local_marker
    assert railway_marker.name == local_marker.name
