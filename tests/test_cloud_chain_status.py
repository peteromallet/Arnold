from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
import yaml

from megaplan import chain as chain_module
from megaplan.cloud.cli import _marker_dir, build_cloud_parser, run_cloud_cli
from megaplan.cloud.spec import (
    ChainSubSpec,
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


def _cloud_spec(*, mode: str = "idle", remote_chain_spec: str | None = None) -> CloudSpec:
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace="/workspace/app",
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode=mode,
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=[],
        railway=RailwaySpec(service="agent", session="agent", project=None),
        chain=ChainSubSpec(spec=remote_chain_spec) if remote_chain_spec is not None else None,
        toolchains=[],
    )


def _write_chain_spec(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "seed": {"plan": "seed-plan-20260421"},
                "milestones": [
                    {"label": "m1", "idea": "/workspace/app/ideas/one.txt"},
                    {"label": "m2", "idea": "/workspace/app/ideas/two.txt"},
                ],
            }
        ),
        encoding="utf-8",
    )


def _expected_payload(spec_path: Path) -> dict:
    spec = chain_module.load_spec(spec_path)
    state = chain_module.load_chain_state(spec_path)
    return {
        "success": True,
        "spec": str(spec_path),
        "milestone_count": len(spec.milestones),
        "seed_plan": spec.seed_plan,
        "chain_state": state.to_dict(),
        "summary": chain_module.format_chain_status(spec, state),
    }


def _write_chain_state(spec_path: Path) -> None:
    chain_module.save_chain_state(
        spec_path,
        chain_module.ChainState(
            current_milestone_index=1,
            current_plan_name="plan-for-m2",
            last_state="done",
            completed=[{"label": "m1", "plan": "plan-for-m1", "status": "done"}],
        ),
    )


class _StubProvider:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads
        self.reads: list[str] = []

    def read_remote_file(self, path: str) -> str:
        self.reads.append(path)
        return self.payloads[path]


def test_cloud_status_chain_honors_explicit_remote_spec_and_matches_local_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    expected = _expected_payload(local_spec_path)

    remote_spec = "/workspace/app/chain.yaml"
    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(expected["chain_state"]),
        }
    )
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    (_marker_dir(cloud_yaml_path) / "last_chain.json").write_text(
        json.dumps({"remote_spec": "/workspace/app/ignored-by-override.yaml"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec(mode="chain", remote_chain_spec="/workspace/app/fallback.yaml"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)

    args = parser.parse_args(
        [
            "cloud",
            "status",
            "--chain",
            "--remote-spec",
            remote_spec,
            "--cloud-yaml",
            str(cloud_yaml_path),
        ]
    )
    assert run_cloud_cli(tmp_path, args) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload == {**expected, "spec": remote_spec}
    assert provider.reads == [str(chain_module._state_path_for(Path(remote_spec))), remote_spec]
    assert "Current milestone: m2 (index 1)" in captured.err


def test_cloud_status_chain_uses_marker_before_cloud_yaml_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/from-marker.yaml"
    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(chain_module.load_chain_state(local_spec_path).to_dict()),
        }
    )
    cloud_yaml_path = tmp_path / "cloud.yaml"
    cloud_yaml_path.write_text("provider: railway\n", encoding="utf-8")
    (_marker_dir(cloud_yaml_path) / "last_chain.json").write_text(
        json.dumps({"remote_spec": remote_spec}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec(mode="chain", remote_chain_spec="/workspace/app/from-cloud-yaml.yaml"))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)

    args = parser.parse_args(["cloud", "status", "--chain", "--cloud-yaml", str(cloud_yaml_path)])
    assert run_cloud_cli(tmp_path, args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["spec"] == remote_spec
    assert provider.reads[0] == str(chain_module._state_path_for(Path(remote_spec)))


def test_cloud_status_chain_falls_back_to_cloud_yaml_chain_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    local_spec_path = tmp_path / "local-chain.yaml"
    _write_chain_spec(local_spec_path)
    _write_chain_state(local_spec_path)
    remote_spec = "/workspace/app/from-cloud-yaml.yaml"
    provider = _StubProvider(
        {
            remote_spec: local_spec_path.read_text(encoding="utf-8"),
            str(chain_module._state_path_for(Path(remote_spec))): json.dumps(chain_module.load_chain_state(local_spec_path).to_dict()),
        }
    )

    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec(mode="chain", remote_chain_spec=remote_spec))
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)

    args = parser.parse_args(["cloud", "status", "--chain"])
    assert run_cloud_cli(tmp_path, args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["spec"] == remote_spec
    assert provider.reads == [str(chain_module._state_path_for(Path(remote_spec))), remote_spec]


def test_cloud_status_chain_errors_when_no_remote_spec_can_be_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = _parser()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("megaplan.cloud.cli.load_spec", lambda _path: _cloud_spec())
    monkeypatch.setattr("megaplan.cloud.cli.get_provider", lambda _name, _spec: _StubProvider({}))

    args = parser.parse_args(["cloud", "status", "--chain"])
    assert run_cloud_cli(tmp_path, args) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "missing_remote_spec"
    assert "run `cloud chain <spec>` first" in payload["message"]
