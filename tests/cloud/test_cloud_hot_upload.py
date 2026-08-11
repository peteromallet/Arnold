"""Tests for SSH cloud hot-upload operator helper."""

from __future__ import annotations

from arnold_pipelines.megaplan.cloud.spec import (
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RepoSpec,
    ResourcesSpec,
    SshSpec,
)
from scripts.cloud_hot_upload import Remote, recreate_container


def _ssh_spec() -> CloudSpec:
    return CloudSpec(
        provider="ssh",
        repo=RepoSpec(url="https://github.com/example/app.git"),
        agents={"default": "codex"},
        codex=CodexSpec(),
        mode="idle",
        megaplan=MegaplanSpec(),
        resources=ResourcesSpec(port=8765),
        secrets=[],
        ssh=SshSpec(
            host="testhost",
            remote_dir="/opt/megaplan-cloud/deploy",
            workspace_dir="/opt/megaplan-cloud/workspace",
            cache_dir="/opt/megaplan-cloud/cache",
            container="megaplan-cloud-agent",
        ),
    )


def test_recreate_container_preserves_current_image(monkeypatch) -> None:
    spec = _ssh_spec()
    assert spec.ssh is not None
    remote = Remote(spec.ssh, apply=False)
    commands: list[str] = []

    def fake_run(command: str, **_kwargs):
        commands.append(command)
        return None

    monkeypatch.setattr(remote, "run", fake_run)

    recreate_container(remote, spec)

    assert len(commands) == 1
    command = commands[0]
    assert "docker inspect -f '{{.Config.Image}}' megaplan-cloud-agent" in command
    assert "docker rm -f megaplan-cloud-agent" in command
    assert '"$image"' in command


def test_upload_env_names_accepts_only_credentials(monkeypatch) -> None:
    from scripts import cloud_hot_upload as hot_upload

    spec = _ssh_spec()
    assert spec.ssh is not None
    remote = Remote(spec.ssh, apply=False)
    commands: list[str] = []
    inputs: list[str] = []

    def fake_docker_exec(command: str, *, input_text: str | None = None, **_kwargs):
        commands.append(command)
        inputs.append(input_text or "")

    monkeypatch.setattr(remote, "docker_exec", fake_docker_exec)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test")

    hot_upload.upload_env_names(remote, ["OPENAI_API_KEY", "GITHUB_TOKEN"])

    assert len(commands) == 1
    import base64

    payload = base64.b64decode(inputs[0]).decode("utf-8")
    assert "export OPENAI_API_KEY=" in payload
    assert "export GITHUB_TOKEN=" in payload


def test_upload_env_names_rejects_retired_runtime_selectors(monkeypatch) -> None:
    from scripts import cloud_hot_upload as hot_upload

    spec = _ssh_spec()
    assert spec.ssh is not None
    remote = Remote(spec.ssh, apply=False)
    commands: list[str] = []

    def fake_docker_exec(command: str, **_kwargs):
        commands.append(command)
        return None

    monkeypatch.setattr(remote, "docker_exec", fake_docker_exec)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_SRC", "/workspace/stale")
    monkeypatch.setenv("CLOUD_WATCHDOG_SYNC_BRANCH", "editible-install")

    for name in (
        "MEGAPLAN_RUNTIME_SRC",
        "MEGAPLAN_LAUNCH_RUNTIME_SRC",
        "MEGAPLAN_SUPERVISOR_SOURCE",
        "CLOUD_WATCHDOG_ARNOLD_SRC",
        "MEGAPLAN_META_ARNOLD_SRC",
        "MEGAPLAN_AUDIT_ARNOLD_SRC",
        "CLOUD_WATCHDOG_SYNC_BRANCH",
        "KIMI_GOAL_SYNC_BRANCH",
        "MEGAPLAN_META_SYNC_BRANCH",
    ):
        monkeypatch.setenv(name, "/workspace/stale")
        try:
            hot_upload.upload_env_names(remote, [name])
        except hot_upload.HotUploadError as exc:
            assert "runtime selector" in str(exc)
        else:
            raise AssertionError(f"{name} was not rejected")

    assert commands == []


def test_upload_env_names_rejects_nonsecret_tuning_and_plain_vars(
    monkeypatch,
) -> None:
    from scripts import cloud_hot_upload as hot_upload

    spec = _ssh_spec()
    assert spec.ssh is not None
    remote = Remote(spec.ssh, apply=False)
    commands: list[str] = []

    def fake_docker_exec(command: str, **_kwargs):
        commands.append(command)
        return None

    monkeypatch.setattr(remote, "docker_exec", fake_docker_exec)
    monkeypatch.setenv("ARNOLD_META_REPAIR_ENABLED", "1")
    monkeypatch.setenv("MEGAPLAN_RUNTIME_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("CLOUD_WATCHDOG_SYNC_ENABLED", "1")
    monkeypatch.setenv("MEGAPLAN_RESIDENT_MODE", "production")

    for name in (
        "ARNOLD_META_REPAIR_ENABLED",
        "MEGAPLAN_RUNTIME_MODEL",
        "CLOUD_WATCHDOG_SYNC_ENABLED",
        "MEGAPLAN_RESIDENT_MODE",
    ):
        try:
            hot_upload.upload_env_names(remote, [name])
        except hot_upload.HotUploadError as exc:
            assert "credentials-only" in str(exc)
        else:
            raise AssertionError(f"{name} was not rejected")

    assert commands == []
