from __future__ import annotations

import os
from pathlib import Path

import pytest

from megaplan.cloud.spec import (
    AutoSpec,
    ChainSubSpec,
    CloudSpec,
    CodexSpec,
    MegaplanSpec,
    RailwaySpec,
    RepoSpec,
    ResourcesSpec,
)
from megaplan.cloud.template import PLACEHOLDERS, materialize_deploy_dir, render_entrypoint


def _spec(mode: str) -> CloudSpec:
    auto = None
    chain = None
    if mode == "auto":
        auto = AutoSpec(
            plan_name="auto-plan",
            idea_file="/workspace/idea-custom.txt",
            robustness="robust",
        )
    if mode == "chain":
        chain = ChainSubSpec(spec="/workspace/chain-custom.yaml")
    return CloudSpec(
        provider="railway",
        repo=RepoSpec(
            url="https://github.com/example/cloud-app.git",
            branch="release/2026",
            workspace="/workspace/custom-app",
        ),
        agents={"default": "codex", "review": "claude"},
        codex=CodexSpec(model="ops-model", reasoning="medium"),
        mode=mode,
        megaplan=MegaplanSpec(ref="release-branch"),
        resources=ResourcesSpec(volume="agent-volume", port=9090),
        secrets=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
        auto=auto,
        chain=chain,
        railway=RailwaySpec(service="agent", session="agent", project="proj-123"),
    )


@pytest.mark.parametrize("mode", ["auto", "chain", "idle"])
def test_render_entrypoint_replaces_placeholders_and_reigh_hardcodes(mode: str) -> None:
    spec = _spec(mode)
    rendered = render_entrypoint(spec)

    for name in PLACEHOLDERS:
        assert f"${{{name}}}" not in rendered

    assert "banodoco/reigh-app" not in rendered
    assert "gpt-5.4" not in rendered
    assert "codex-agent@reigh.dev" not in rendered
    assert "/workspace/reigh-app" not in rendered
    assert spec.repo.workspace in rendered
    assert rendered.count(spec.repo.workspace) >= 2

    assert '# sandbox_mode = "danger-full-access" stays on because the container is the sandbox.' in rendered
    assert 'sandbox_mode = "danger-full-access"' in rendered
    assert 'if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then' in rendered
    assert "claude setup-token" in rendered
    assert "WARN: Claude token auth failed; continuing without Claude auth" in rendered
    assert "exit 1" not in rendered

    routing_lines = [
        line.strip()
        for line in rendered.splitlines()
        if "megaplan config set agents." in line
    ]
    assert routing_lines
    assert all(line.startswith("megaplan config set agents.") for line in routing_lines)
    assert rendered.count("megaplan config set agents.review claude") == 1
    assert "megaplan config set agents.review codex" not in rendered
    assert "phase_agent." not in rendered

    if mode == "auto":
        assert 'if [ ! -f "$IDEA_FILE" ]; then' in rendered
        assert "megaplan auto --plan auto-plan" in rendered
        assert "megaplan init --project-dir /workspace/custom-app --name auto-plan" in rendered
        assert "mp-chain /workspace/chain-custom.yaml" not in rendered
    elif mode == "chain":
        assert 'if [ ! -f "$CHAIN_SPEC" ]; then' in rendered
        assert "mp-chain /workspace/chain-custom.yaml" in rendered
        assert "megaplan auto --plan auto-plan" not in rendered
    else:
        assert 'tmux new-session -d -s agent -c /workspace/custom-app "bash -l"' in rendered
        assert "megaplan auto --plan" not in rendered
        assert "mp-chain " not in rendered


def test_materialize_deploy_dir_creates_expected_layout(tmp_path: Path) -> None:
    deploy_dir = tmp_path / "deploy"
    materialize_deploy_dir(_spec("auto"), deploy_dir)

    assert (deploy_dir / "Dockerfile").is_file()
    assert (deploy_dir / "entrypoint.sh").is_file()
    assert (deploy_dir / "healthserver.py").is_file()
    assert (deploy_dir / "railway.toml").is_file()

    wrappers = deploy_dir / "wrappers"
    assert wrappers.is_dir()
    for name in ("mp-run", "mp-supervise", "mp-heartbeat", "mp-chain"):
        path = wrappers / name
        assert path.is_file()
        assert os.access(path, os.X_OK)

    dockerfile = (deploy_dir / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY wrappers/ /usr/local/bin/" in dockerfile
    assert "megaplan/cloud/wrappers" not in dockerfile
