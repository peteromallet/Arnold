from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.cloud.providers.local import LocalProvider
from arnold.pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    LocalSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
)
from arnold.pipelines.megaplan.cloud.template import materialize_deploy_dir
from arnold.pipelines.megaplan.types import CliError


def _spec() -> CloudSpec:
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
        secrets=["OPENAI_API_KEY"],
        local=LocalSpec(compose_project="local-demo", workdir="workspace"),
        toolchains=[],
    )


def test_materialize_deploy_dir_writes_local_compose_file(tmp_path: Path) -> None:
    deploy_dir = tmp_path / "deploy"
    materialize_deploy_dir(_spec(), deploy_dir)

    compose = (deploy_dir / "docker-compose.yaml").read_text(encoding="utf-8")
    assert "agent:" in compose
    assert "./workspace:/workspace/app" in compose
    assert (deploy_dir / "workspace").is_dir()


def test_local_provider_uses_expected_compose_argv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    follow_calls: list[tuple[list[str], Path, list[str]]] = []
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret-token")

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        if argv[-2:] == ["cat", "/workspace/app/idea.txt"]:
            return subprocess.CompletedProcess(argv, 0, stdout="remote idea\n", stderr="")
        if argv[-1] == "cd /workspace/app && arnold status --plan demo-plan":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps({"next_step": "review"}),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.providers.local.shutil.which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.providers.local.subprocess.run", fake_run)
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.cloud.providers.local._logs_follow",
        lambda argv, *, cwd=None, secret_names=(), env=None: follow_calls.append(
            (argv, cwd, list(secret_names))
        )
        or 0,
    )

    provider = LocalProvider(_spec())
    source = tmp_path / "idea.txt"
    source.write_text("hello local\n", encoding="utf-8")
    compose_file = Path.home() / ".megaplan" / "cloud" / "local-demo" / "docker-compose.yaml"
    deploy_dir = compose_file.parent

    assert provider.build(deploy_dir) == 0
    assert provider.deploy(deploy_dir, secrets={"OPENAI_API_KEY": "secret"}) == 0
    provider.ssh_exec("pwd")
    provider.upload_file(source, "/workspace/app/idea.txt")
    assert provider.read_remote_file("/workspace/app/idea.txt") == "remote idea\n"
    assert provider.status_payload(plan="demo-plan", workspace="/workspace/app") == {"next_step": "review"}
    assert provider.attach() == 0
    assert provider.logs(follow=True) == 0
    assert provider.logs(follow=False) == 0
    assert provider.down() == 0
    assert provider.destroy() == 0

    assert calls == [
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "build"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "up", "-d"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "exec", "-T", "agent", "bash", "-lc", "pwd"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            [
                "/usr/bin/docker",
                "compose",
                "-p",
                "local-demo",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "agent",
                "bash",
                "-lc",
                "mkdir -p /workspace/app && base64 -d > /workspace/app/idea.txt",
            ],
            {
                "cwd": deploy_dir,
                "capture_output": True,
                "text": True,
                "check": False,
                "input": base64.b64encode(source.read_bytes()).decode("ascii"),
            },
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "exec", "-T", "agent", "cat", "/workspace/app/idea.txt"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            [
                "/usr/bin/docker",
                "compose",
                "-p",
                "local-demo",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "agent",
                "bash",
                "-lc",
                "cd /workspace/app && arnold status --plan demo-plan",
            ],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "exec", "agent", "tmux", "attach", "-t", "agent"],
            {"cwd": deploy_dir, "capture_output": False, "text": True, "check": False},
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "logs", "--tail", "200", "agent"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "stop"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "down", "--volumes", "--remove-orphans"],
            {"cwd": deploy_dir, "capture_output": True, "text": True, "check": False},
        ),
    ]
    assert follow_calls == [
        (
            ["/usr/bin/docker", "compose", "-p", "local-demo", "-f", str(compose_file), "logs", "-f", "agent"],
            deploy_dir,
            ["OPENAI_API_KEY"],
        )
    ]
    assert (deploy_dir / ".env").read_text(encoding="utf-8") == "PORT=8080\nOPENAI_API_KEY=secret\n"


def test_local_provider_missing_docker_raises_provider_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("arnold.pipelines.megaplan.cloud.providers.local.shutil.which", lambda _name: None)

    with pytest.raises(CliError, match="https://docs.docker.com/get-docker/"):
        LocalProvider(_spec())
