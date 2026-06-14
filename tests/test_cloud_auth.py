from __future__ import annotations

import base64
import argparse
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import yaml

from arnold.pipelines.megaplan.cloud.auth import seed_codex_oauth
from arnold.pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli
from arnold.pipelines.megaplan.cloud.providers.base import DeployReport, DeployStepReport
from arnold.pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
)


def _spec(*, codex_auth: str = "chatgpt") -> CloudSpec:
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(url="https://github.com/example/app.git", workspace="/workspace/app"),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode="idle",
        megaplan=MegaplanSpec(ref="main", codex_auth=codex_auth),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=[],
        railway=RailwaySpec(service="agent", session="agent", project=None),
        toolchains=[],
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_cloud_parser(subparsers)
    return parser


class _Provider:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(["ssh"], 0, stdout="", stderr="")


def test_seed_codex_oauth_constructs_remote_write_commands(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    hermes_dir = home / ".hermes"
    codex_dir.mkdir(parents=True)
    hermes_dir.mkdir(parents=True)
    codex_auth = '{"auth_mode":"chatgpt","tokens":{"access_token":"codex-token"}}'
    hermes_auth = '{"tokens":{"access_token":"hermes-token"}}'
    (codex_dir / "auth.json").write_text(codex_auth, encoding="utf-8")
    (hermes_dir / "auth.json").write_text(hermes_auth, encoding="utf-8")
    provider = _Provider()
    messages: list[str] = []

    result = seed_codex_oauth(_spec(), provider, home=home, writer=messages.append)

    assert result["events"] == [
        {"label": "codex", "status": "seeded"},
        {"label": "hermes", "status": "seeded"},
    ]
    assert len(provider.commands) == 2
    codex_b64 = base64.b64encode(codex_auth.encode("utf-8")).decode("ascii")
    assert f"AUTH_B64={codex_b64}" in provider.commands[0]
    assert "base64 -d" in provider.commands[0]
    assert "/workspace/.creds/codex-auth.json" in provider.commands[0]
    assert "/root/.codex/auth.json" in provider.commands[0]
    assert "codex-token" not in provider.commands[0]
    assert "/workspace/.creds/hermes-auth.json" in provider.commands[1]
    assert "/root/.hermes/auth.json" in provider.commands[1]
    assert "hermes-token" not in provider.commands[1]
    assert any("seeded codex auth" in message for message in messages)


def test_seed_codex_oauth_opt_out_skips_remote_writes(tmp_path: Path) -> None:
    provider = _Provider()
    messages: list[str] = []

    result = seed_codex_oauth(_spec(codex_auth="apikey"), provider, home=tmp_path, writer=messages.append)

    assert result["events"] == [
        {"label": "all", "status": "skipped", "reason": "codex_auth=apikey"},
    ]
    assert provider.commands == []
    assert messages == ["cloud codex OAuth seed: skipped because megaplan.codex_auth=apikey\n"]


def test_seed_codex_oauth_absent_local_creds_cleanly_skip(tmp_path: Path) -> None:
    provider = _Provider()
    messages: list[str] = []

    result = seed_codex_oauth(_spec(), provider, home=tmp_path, writer=messages.append)

    assert result["events"] == [
        {"label": "codex", "status": "skipped", "reason": "absent"},
        {"label": "hermes", "status": "skipped", "reason": "absent"},
    ]
    assert provider.commands == []
    assert any("absent; skipping codex" in message for message in messages)
    assert any("absent; skipping hermes" in message for message in messages)


def test_seed_codex_oauth_uses_megaplan_spec_auth_mode(tmp_path: Path) -> None:
    spec = replace(_spec(), megaplan=replace(_spec().megaplan, codex_auth="apikey"))
    provider = _Provider()

    seed_codex_oauth(spec, provider, home=tmp_path, writer=lambda _message: None)

    assert provider.commands == []


def test_cloud_deploy_invokes_codex_oauth_seed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text(
        """\
provider: railway
repo:
  url: https://github.com/example/app.git
mode: idle
""",
        encoding="utf-8",
    )
    calls: list[str] = []

    class Provider(_Provider):
        def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> int:
            del deploy_dir, secrets
            calls.append("deploy")
            return 0

    provider = Provider()
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.seed_codex_oauth",
        lambda _spec, _provider, **_kwargs: calls.append("seed") or {"events": []},
    )

    args = _parser().parse_args(["cloud", "deploy", "--cloud-yaml", str(cloud_yaml)])

    assert run_cloud_cli(tmp_path, args) == 0
    assert calls == ["deploy", "seed"]


def _last_json_object(output: str) -> dict:
    start = output.rfind("\n{")
    if start == -1:
        start = output.find("{")
    else:
        start += 1
    return json.loads(output[start:])


def test_cloud_deploy_reports_rebuild_and_provider_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text("provider: railway\n", encoding="utf-8")

    class Provider(_Provider):
        supports_session = False

        def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> DeployReport:
            del secrets
            return DeployReport(
                success=True,
                provider="railway",
                service="agent",
                deploy_dir=str(deploy_dir),
                steps=[
                    DeployStepReport(
                        name="set Railway service variables",
                        status="ok",
                        detail="set 1 service var(s)",
                        stdout="variables updated\n",
                    ),
                    DeployStepReport(
                        name="railway up",
                        status="ok",
                        detail="ran railway up --detach --ci",
                        stdout="building image\npushed image sha256:abc123\n",
                    ),
                ],
                image_rebuild="triggered",
                image_ref="sha256:abc123",
                vars_updated=1,
                logs={"command": "arnold cloud logs --no-follow", "service": "agent"},
                verdict="deploy: rebuilt+pushed image sha256:abc123",
            )

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: Provider())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _spec())
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.seed_codex_oauth",
        lambda _spec, _provider, **_kwargs: {"events": []},
    )

    args = _parser().parse_args(["cloud", "deploy", "--cloud-yaml", str(cloud_yaml)])

    assert run_cloud_cli(tmp_path, args) == 0
    output = capsys.readouterr().out
    assert "- render Dockerfile: ok" in output
    assert "- render entrypoint.sh: ok" in output
    assert "- railway up: ok" in output
    assert "building image" in output
    assert "logs:" in output
    assert "deploy: rebuilt+pushed image sha256:abc123" in output
    payload = _last_json_object(output)
    assert payload["image_rebuild"] == "triggered"
    assert payload["image_ref"] == "sha256:abc123"
    assert payload["logs"]["service"] == "agent"


def test_cloud_deploy_reports_vars_only_no_image_rebuild(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text("provider: railway\n", encoding="utf-8")

    class Provider(_Provider):
        supports_session = False

        def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> DeployReport:
            del secrets
            return DeployReport(
                success=True,
                provider="railway",
                service="agent",
                deploy_dir=str(deploy_dir),
                steps=[
                    DeployStepReport(
                        name="set Railway service variables",
                        status="ok",
                        detail="set 1 service var(s)",
                    ),
                    DeployStepReport(
                        name="railway up",
                        status="ok",
                        detail="railway reported no image rebuild",
                        stdout="no changes detected\n",
                    ),
                ],
                image_rebuild="not_triggered",
                no_op=False,
                vars_updated=1,
                logs={"command": "arnold cloud logs --no-follow", "service": "agent"},
                verdict="deploy: vars updated, no image rebuild",
            )

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: Provider())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _spec())
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.seed_codex_oauth",
        lambda _spec, _provider, **_kwargs: {"events": []},
    )

    args = _parser().parse_args(["cloud", "deploy", "--cloud-yaml", str(cloud_yaml)])

    assert run_cloud_cli(tmp_path, args) == 0
    output = capsys.readouterr().out
    assert "deploy: vars updated, no image rebuild" in output
    assert "no changes detected" in output
    payload = _last_json_object(output)
    assert payload["image_rebuild"] == "not_triggered"
    assert payload["no_op"] is False
    assert payload["vars_updated"] == 1


def test_cloud_deploy_reports_no_op(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text("provider: railway\n", encoding="utf-8")

    class Provider(_Provider):
        supports_session = False

        def deploy(self, deploy_dir: Path, *, secrets: dict[str, str]) -> DeployReport:
            del secrets
            return DeployReport(
                success=True,
                provider="railway",
                service="agent",
                deploy_dir=str(deploy_dir),
                steps=[
                    DeployStepReport(
                        name="railway up",
                        status="ok",
                        detail="railway reported no image rebuild",
                        stdout="nothing to deploy\n",
                    ),
                ],
                image_rebuild="not_triggered",
                no_op=True,
                vars_updated=0,
                logs={"command": "arnold cloud logs --no-follow", "service": "agent"},
                verdict="deploy: no-op (nothing changed)",
            )

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: Provider())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _spec())
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.seed_codex_oauth",
        lambda _spec, _provider, **_kwargs: {"events": []},
    )

    args = _parser().parse_args(["cloud", "deploy", "--cloud-yaml", str(cloud_yaml)])

    assert run_cloud_cli(tmp_path, args) == 0
    output = capsys.readouterr().out
    assert "deploy: no-op (nothing changed)" in output
    payload = _last_json_object(output)
    assert payload["image_rebuild"] == "not_triggered"
    assert payload["no_op"] is True


def test_cloud_chain_invokes_codex_oauth_seed_before_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    chain_path = tmp_path / "chain.yaml"
    chain_path.write_text(
        yaml.safe_dump({"milestones": [{"label": "m1", "idea": "/workspace/app/ideas/m1.md"}]}),
        encoding="utf-8",
    )
    idea_dir = tmp_path / "ideas"
    (idea_dir / "ideas").mkdir(parents=True)
    (idea_dir / "ideas" / "m1.md").write_text("m1\n", encoding="utf-8")
    cloud_yaml = tmp_path / "cloud.yaml"
    cloud_yaml.write_text("provider: railway\n", encoding="utf-8")
    calls: list[str] = []

    class Provider(_Provider):
        def upload_file(self, src: Path, dest: str) -> None:
            del src, dest

        def ssh_exec(self, command: str) -> subprocess.CompletedProcess[str]:
            if "tmux has-session" in command:
                calls.append("launch")
                return subprocess.CompletedProcess(["ssh"], 0, stdout="started\n", stderr="")
            if "git -C" in command:
                calls.append("repo-head")
                return subprocess.CompletedProcess(["ssh"], 0, stdout="main\nabc123\n", stderr="")
            return subprocess.CompletedProcess(["ssh"], 0, stdout="\n", stderr="")

    provider = Provider()
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.load_spec", lambda _path: _spec())
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.cli.get_provider", lambda _name, _spec: provider)
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.cli.seed_codex_oauth",
        lambda _spec, _provider: calls.append("seed"),
    )

    args = _parser().parse_args(
        ["cloud", "chain", str(chain_path), "--idea-dir", str(idea_dir), "--cloud-yaml", str(cloud_yaml)]
    )

    assert run_cloud_cli(tmp_path, args) == 0
    assert calls[:2] == ["seed", "repo-head"]
    assert "launch" in calls
