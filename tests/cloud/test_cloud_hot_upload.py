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
