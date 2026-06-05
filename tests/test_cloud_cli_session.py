from __future__ import annotations

import argparse
import json
from pathlib import Path

from arnold.pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli
from arnold.pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    LocalSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cloud_parser(subparsers)
    return parser


def _base_spec(provider: str) -> CloudSpec:
    kwargs = {
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
        kwargs["local"] = LocalSpec(compose_project="local-demo", workdir="workspace")
    if provider == "ssh":
        kwargs["ssh"] = SshSpec(host="deploy.example.com")
    return CloudSpec(**kwargs)


def test_session_flag_help_is_capability_based() -> None:
    parser = _parser()
    cloud_parser = parser._subparsers._group_actions[0].choices["cloud"]
    attach_parser = cloud_parser._subparsers._group_actions[0].choices["attach"]
    session_action = next(action for action in attach_parser._actions if action.dest == "session")

    assert "providers that support sessions" in session_action.help
    assert "Railway" not in session_action.help


def test_session_override_is_accepted_for_railway(monkeypatch) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "attach", "--session", "debug-session"])
    provider = type(
        "RailwayStub",
        (),
        {"supports_session": True, "attach": lambda self: 0},
    )()
    captured_specs: list[CloudSpec] = []

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _base_spec("railway"))

    def fake_get_provider(_name: str, spec: CloudSpec):
        captured_specs.append(spec)
        return provider

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", fake_get_provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 0
    assert len(captured_specs) == 2
    assert captured_specs[0].railway is not None
    assert captured_specs[0].railway.session == "agent"
    assert captured_specs[1].railway is not None
    assert captured_specs[1].railway.session == "debug-session"


def test_session_override_is_rejected_when_railway_provider_lacks_session_support(
    monkeypatch, capsys
) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "attach", "--session", "debug-session"])
    captured_specs: list[CloudSpec] = []
    captured_names: list[str] = []

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _base_spec("railway"))

    def fake_get_provider(_name: str, spec: CloudSpec):
        captured_names.append(_name)
        captured_specs.append(spec)
        return type(
            "RailwayWithoutSessionsStub",
            (),
            {"supports_session": False, "attach": lambda self: 0},
        )()

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", fake_get_provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 1
    assert captured_names == ["railway"]
    assert len(captured_specs) == 1
    assert captured_specs[0].railway is not None
    assert captured_specs[0].railway.session == "agent"
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "invalid_args"
    assert payload["message"] == "--session is only supported for provider: railway"


def test_session_override_is_rejected_for_local(monkeypatch, capsys) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "attach", "--session", "debug-session"])
    captured_specs: list[CloudSpec] = []
    captured_names: list[str] = []
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _base_spec("local"))

    def fake_get_provider(_name: str, spec: CloudSpec):
        captured_names.append(_name)
        captured_specs.append(spec)
        return type(
            "LocalStub",
            (),
            {"supports_session": False, "attach": lambda self: 0},
        )()

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", fake_get_provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 1
    assert captured_names == ["local"]
    assert len(captured_specs) == 1
    assert captured_specs[0].railway is not None
    assert captured_specs[0].railway.session == "agent"
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "invalid_args"
    assert payload["message"] == "--session is only supported for provider: railway"


def test_session_override_is_rejected_for_ssh(monkeypatch, capsys) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "attach", "--session", "debug-session"])
    captured_specs: list[CloudSpec] = []
    captured_names: list[str] = []
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _base_spec("ssh"))

    def fake_get_provider(_name: str, spec: CloudSpec):
        captured_names.append(_name)
        captured_specs.append(spec)
        return type(
            "SshStub",
            (),
            {"supports_session": False, "attach": lambda self: 0},
        )()

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", fake_get_provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 1
    assert captured_names == ["ssh"]
    assert len(captured_specs) == 1
    assert captured_specs[0].railway is not None
    assert captured_specs[0].railway.session == "agent"
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "invalid_args"
    assert payload["message"] == "--session is only supported for provider: railway"


def test_session_override_uses_provider_capability_not_provider_name(monkeypatch) -> None:
    parser = _parser()
    args = parser.parse_args(["cloud", "attach", "--session", "debug-session"])
    captured_specs: list[CloudSpec] = []
    captured_names: list[str] = []

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _base_spec("local"))

    def fake_get_provider(_name: str, spec: CloudSpec):
        captured_names.append(_name)
        captured_specs.append(spec)
        return type(
            "SessionCapableStub",
            (),
            {"supports_session": True, "attach": lambda self: 0},
        )()

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", fake_get_provider)

    assert run_cloud_cli(Path("/tmp/project"), args) == 0
    assert captured_names == ["local", "local"]
    assert len(captured_specs) == 2
    assert captured_specs[0].provider == "local"
    assert captured_specs[0].railway is not None
    assert captured_specs[0].railway.session == "agent"
    assert captured_specs[1].provider == "local"
    assert captured_specs[1].railway is not None
    assert captured_specs[1].railway.session == "debug-session"
