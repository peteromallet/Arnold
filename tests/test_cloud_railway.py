from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from megaplan.cloud.providers.railway import RailwayProvider
from megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
)
from megaplan.types import CliError


def _spec(*, project: str | None = None, secrets: list[str] | None = None) -> CloudSpec:
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(
            url="https://github.com/example/app.git",
            branch="main",
            workspace="/workspace/foo",
        ),
        agents={"default": "codex"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode="idle",
        megaplan=MegaplanSpec(ref="main"),
        resources=ResourcesSpec(volume="agent-volume", port=8080),
        secrets=secrets or [],
        railway=RailwaySpec(service="svc", session="ses", project=project),
    )


def test_build_uses_docker_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)

    provider = RailwayProvider(_spec())
    assert provider.build(tmp_path) == 0
    assert calls == [
        (
            ["docker", "build", "-t", "megaplan-cloud-svc", str(tmp_path)],
            {"cwd": None, "capture_output": True, "text": True, "check": False},
        )
    ]


def test_deploy_without_project_sets_variables_and_ups(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)

    provider = RailwayProvider(_spec(secrets=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]))
    assert provider.deploy(
        tmp_path,
        secrets={"OPENAI_API_KEY": "openai-secret", "ANTHROPIC_API_KEY": "anthropic-secret"},
    ) == 0

    assert [argv for argv, _kwargs in calls] == [
        ["/usr/bin/railway", "variables", "--service", "svc", "--set", "OPENAI_API_KEY=openai-secret"],
        ["/usr/bin/railway", "variables", "--service", "svc", "--set", "ANTHROPIC_API_KEY=anthropic-secret"],
        ["/usr/bin/railway", "up", "--service", "svc", "--detach", "--ci"],
    ]
    assert all(kwargs["cwd"] == tmp_path for _argv, kwargs in calls)


def test_deploy_with_project_links_once_before_upload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)

    provider = RailwayProvider(_spec(project="my-proj", secrets=["OPENAI_API_KEY"]))
    provider.deploy(tmp_path, secrets={"OPENAI_API_KEY": "secret"})

    assert calls == [
        ["/usr/bin/railway", "link", "--project", "my-proj"],
        ["/usr/bin/railway", "variables", "--service", "svc", "--set", "OPENAI_API_KEY=secret"],
        ["/usr/bin/railway", "up", "--service", "svc", "--detach", "--ci"],
    ]


def test_ssh_attach_logs_and_status_payload_use_expected_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        if argv[:2] == ["/usr/bin/railway", "ssh"] and "--" in argv:
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=json.dumps({"next_step": "review"}),
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)

    provider = RailwayProvider(_spec())
    provider.ssh_exec("pwd")
    assert provider.attach() == 0
    assert provider.logs(follow=True) == 0
    assert provider.logs(follow=False) == 0
    assert provider.status_payload(plan=None, workspace="/workspace/foo") == {"next_step": "review"}
    assert provider.status_payload(plan="P", workspace="/workspace/foo") == {"next_step": "review"}

    assert [argv for argv, _kwargs in calls] == [
        ["/usr/bin/railway", "ssh", "--service", "svc", "--session", "ses", "--", "pwd"],
        ["/usr/bin/railway", "ssh", "--service", "svc", "--session", "ses"],
        ["/usr/bin/railway", "logs", "--service", "svc"],
        ["/usr/bin/railway", "logs", "--service", "svc", "--lines", "200"],
        ["/usr/bin/railway", "ssh", "--service", "svc", "--session", "ses", "--", "cd /workspace/foo && megaplan status"],
        ["/usr/bin/railway", "ssh", "--service", "svc", "--session", "ses", "--", "cd /workspace/foo && megaplan status --plan P"],
    ]
    assert calls[1][1]["capture_output"] is False


def test_down_and_destroy_use_expected_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)

    provider = RailwayProvider(_spec())
    assert provider.down() == 0
    assert provider.destroy(volume=None) == 0
    assert provider.destroy(volume="agent-volume") == 0

    assert calls == [
        ["/usr/bin/railway", "down", "--service", "svc"],
        ["/usr/bin/railway", "down", "--service", "svc"],
        ["/usr/bin/railway", "down", "--service", "svc"],
        ["/usr/bin/railway", "volume", "delete", "agent-volume"],
    ]


def test_missing_binary_raises_provider_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: None)

    with pytest.raises(CliError, match="https://docs.railway.app/develop/cli"):
        RailwayProvider(_spec())


def test_deploy_missing_secret_fails_before_any_railway_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)
    monkeypatch.delenv("MISSING_ENV", raising=False)

    provider = RailwayProvider(_spec(secrets=["MISSING_ENV"]))
    missing_value = os.environ.get("MISSING_ENV", "")
    with pytest.raises(CliError, match="MISSING_ENV"):
        provider.deploy(tmp_path, secrets={"MISSING_ENV": missing_value})
    assert calls == []


def test_destroy_volume_delete_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if argv[:3] == ["/usr/bin/railway", "volume", "delete"]:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="delete failed")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr("megaplan.cloud.providers.railway.shutil.which", lambda _name: "/usr/bin/railway")
    monkeypatch.setattr("megaplan.cloud.providers.railway.subprocess.run", fake_run)

    provider = RailwayProvider(_spec())
    with pytest.raises(CliError, match="delete failed"):
        provider.destroy(volume="x")
