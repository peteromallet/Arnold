from __future__ import annotations

import base64
import json
import shlex
import subprocess
from pathlib import Path

from megaplan.cloud.providers.ssh import SshProvider
from megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)


def _spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
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
        ssh=SshSpec(
            host="deploy.example.com",
            user="deployer",
            port=2222,
            identity_file="/tmp/id_rsa",
            remote_dir="/tmp/megaplan cloud",
            container="agent name $HOME",
        ),
        toolchains=[],
    )


def _ssh_argv() -> list[str]:
    return ["/usr/bin/ssh", "-p", "2222", "-i", "/tmp/id_rsa"]


def test_ssh_provider_build_uses_rsync_and_quoted_remote_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "megaplan.cloud.providers.ssh.shutil.which",
        lambda name: {
            "ssh": "/usr/bin/ssh",
            "scp": "/usr/bin/scp",
            "rsync": "/usr/bin/rsync",
        }.get(name),
    )
    monkeypatch.setattr("megaplan.cloud.providers.ssh.subprocess.run", fake_run)

    provider = SshProvider(_spec())
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir()
    assert provider.build(deploy_dir) == 0

    remote_dir = shlex.quote(_spec().ssh.remote_dir)
    target = "deployer@deploy.example.com"
    assert calls == [
        (
            [*_ssh_argv(), target, f"mkdir -p {remote_dir}"],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [
                "/usr/bin/rsync",
                "-az",
                "-e",
                "/usr/bin/ssh -p 2222 -i /tmp/id_rsa",
                f"{deploy_dir}/",
                f"{target}:{remote_dir}/",
            ],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [
                *_ssh_argv(),
                target,
                f"docker build -t {shlex.quote(_spec().ssh.container)} {remote_dir}",
            ],
            {"capture_output": True, "text": True, "check": False},
        ),
    ]


def test_ssh_provider_build_falls_back_to_scp_with_warning(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "megaplan.cloud.providers.ssh.shutil.which",
        lambda name: {
            "ssh": "/usr/bin/ssh",
            "scp": "/usr/bin/scp",
            "rsync": None,
        }.get(name),
    )
    monkeypatch.setattr("megaplan.cloud.providers.ssh.subprocess.run", fake_run)

    provider = SshProvider(_spec())
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir()
    assert provider.build(deploy_dir) == 0

    remote_dir = shlex.quote(_spec().ssh.remote_dir)
    target = "deployer@deploy.example.com"
    assert "falling back to scp -r" in capsys.readouterr().err
    assert calls[1] == (
        [
            "/usr/bin/scp",
            "-r",
            "-P",
            "2222",
            "-i",
            "/tmp/id_rsa",
            f"{deploy_dir}/.",
            f"{target}:{remote_dir}",
        ],
        {"capture_output": True, "text": True, "check": False},
    )


def test_ssh_provider_lifecycle_and_transfer_commands_are_quoted(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    follow_calls: list[tuple[list[str], list[str]]] = []
    spec = _spec()
    read_inner = f"cat {shlex.quote('/workspace/app/idea.txt')}"
    status_inner = "cd /workspace/app && megaplan status --plan demo-plan"
    upload_inner = (
        f"mkdir -p {shlex.quote('/workspace/app')} && "
        f"base64 -d > {shlex.quote('/workspace/app/idea.txt')}"
    )
    home_inner = "printf '$HOME'"
    exec_home = f"docker exec {shlex.quote(spec.ssh.container)} bash -lc {shlex.quote(home_inner)}"
    remote_cat = (
        f"docker exec {shlex.quote(spec.ssh.container)} bash -lc "
        f"{shlex.quote(read_inner)}"
    )
    remote_status = (
        f"docker exec {shlex.quote(spec.ssh.container)} bash -lc "
        f"{shlex.quote(status_inner)}"
    )
    remote_upload = (
        f"docker exec -i {shlex.quote(spec.ssh.container)} bash -lc "
        f"{shlex.quote(upload_inner)}"
    )

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        if argv[-1] == remote_cat:
            return subprocess.CompletedProcess(argv, 0, stdout="remote file\n", stderr="")
        if argv[-1] == remote_status:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps({"next_step": "review"}),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "megaplan.cloud.providers.ssh.shutil.which",
        lambda name: {
            "ssh": "/usr/bin/ssh",
            "scp": "/usr/bin/scp",
            "rsync": "/usr/bin/rsync",
        }.get(name),
    )
    monkeypatch.setattr("megaplan.cloud.providers.ssh.subprocess.run", fake_run)
    monkeypatch.setattr(
        "megaplan.cloud.providers.ssh._logs_follow",
        lambda argv, *, cwd=None, secret_names=(), env=None: follow_calls.append((argv, list(secret_names))) or 0,
    )

    provider = SshProvider(spec)
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir()
    idea = tmp_path / "idea.txt"
    idea.write_text("hello ssh\n", encoding="utf-8")
    target = "deployer@deploy.example.com"
    env_path = f"{spec.ssh.remote_dir}/.env"

    assert provider.deploy(deploy_dir, secrets={"OPENAI_API_KEY": "secret"}) == 0
    provider.ssh_exec("printf '$HOME'")
    provider.upload_file(idea, "/workspace/app/idea.txt")
    assert provider.read_remote_file("/workspace/app/idea.txt") == "remote file\n"
    assert provider.status_payload(plan="demo-plan", workspace="/workspace/app") == {"next_step": "review"}
    assert provider.attach() == 0
    assert provider.logs(follow=True) == 0
    assert provider.logs(follow=False) == 0
    assert provider.down() == 0
    assert provider.destroy() == 0

    expected_calls = [
        (
            [*_ssh_argv(), target, f"cat > {shlex.quote(env_path)}"],
            {
                "capture_output": True,
                "text": True,
                "check": False,
                "input": "PORT=8080\nOPENAI_API_KEY=secret\n",
            },
        ),
        (
            [*_ssh_argv(), target, f"docker rm -f {shlex.quote(spec.ssh.container)} >/dev/null 2>&1 || true"],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [
                *_ssh_argv(),
                target,
                " ".join(
                    [
                        "docker run -d",
                        f"--name {shlex.quote(spec.ssh.container)}",
                        "--restart unless-stopped",
                        f"--env-file {shlex.quote(env_path)}",
                        "-p 8080:8080",
                        shlex.quote(spec.ssh.container),
                    ]
                ),
            ],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [*_ssh_argv(), target, exec_home],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [
                *_ssh_argv(),
                target,
                remote_upload,
            ],
            {
                "capture_output": True,
                "text": True,
                "check": False,
                "input": base64.b64encode(idea.read_bytes()).decode("ascii"),
            },
        ),
        (
            [*_ssh_argv(), target, remote_cat],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [*_ssh_argv(), target, remote_status],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [*_ssh_argv(), target, f"docker exec -it {shlex.quote(spec.ssh.container)} tmux attach -t agent"],
            {"capture_output": False, "text": True, "check": False},
        ),
        (
            [*_ssh_argv(), target, f"docker logs --tail 200 {shlex.quote(spec.ssh.container)}"],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [*_ssh_argv(), target, f"docker stop {shlex.quote(spec.ssh.container)}"],
            {"capture_output": True, "text": True, "check": False},
        ),
        (
            [
                *_ssh_argv(),
                target,
                f"docker rm -f {shlex.quote(spec.ssh.container)} >/dev/null 2>&1 || true && rm -rf {shlex.quote(spec.ssh.remote_dir)}",
            ],
            {"capture_output": True, "text": True, "check": False},
        ),
    ]
    assert calls == expected_calls
    assert follow_calls == [
        (
            [*_ssh_argv(), target, f"docker logs -f {shlex.quote(spec.ssh.container)}"],
            ["OPENAI_API_KEY"],
        )
    ]
