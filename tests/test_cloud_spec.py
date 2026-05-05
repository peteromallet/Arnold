from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from megaplan.cloud.spec import LocalSpec, RailwaySpec, SshSpec, ToolchainSpec, load_spec
from megaplan.types import CliError, DEFAULT_AGENT_ROUTING


def _base_spec(*, mode: str = "idle") -> dict[str, object]:
    spec: dict[str, object] = {
        "provider": "railway",
        "repo": {
            "url": "https://github.com/example/app.git",
            "branch": "main",
            "workspace": "/workspace/app",
        },
        "agents": {"default": "codex"},
        "codex": {"model": "gpt-5.4-mini", "reasoning": "medium"},
        "mode": mode,
        "megaplan": {"ref": "main"},
        "resources": {"volume": "agent-volume", "port": 8080},
        "secrets": ["OPENAI_API_KEY"],
    }
    if mode == "auto":
        spec["auto"] = {
            "plan_name": "cloud-plan",
            "idea_file": "/workspace/idea.txt",
            "robustness": "standard",
        }
    if mode == "chain":
        spec["chain"] = {"spec": "/workspace/chain.yaml"}
    return spec


def _write_spec(tmp_path: Path, payload: dict[str, object], *, name: str = "cloud.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize("mode", ["idle", "auto", "chain"])
def test_load_spec_happy_path_for_each_mode(tmp_path: Path, mode: str) -> None:
    spec = load_spec(_write_spec(tmp_path, _base_spec(mode=mode), name=f"{mode}.yaml"))
    assert spec.mode == mode
    assert spec.provider == "railway"
    assert spec.repo.workspace == "/workspace/app"
    if mode == "auto":
        assert spec.auto is not None
        assert spec.auto.plan_name == "cloud-plan"
    else:
        assert spec.auto is None
    if mode == "chain":
        assert spec.chain is not None
        assert spec.chain.spec == "/workspace/chain.yaml"
    else:
        assert spec.chain is None


def test_load_spec_rejects_missing_repo_url(tmp_path: Path) -> None:
    payload = _base_spec()
    del payload["repo"]["url"]  # type: ignore[index]
    with pytest.raises(CliError, match="repo.url"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_non_absolute_workspace(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["repo"]["workspace"] = "workspace/app"  # type: ignore[index]
    with pytest.raises(CliError, match="absolute POSIX path"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_unknown_mode(tmp_path: Path) -> None:
    payload = _base_spec(mode="mystery")
    with pytest.raises(CliError, match="auto, chain, idle"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_auto_without_plan_name(tmp_path: Path) -> None:
    payload = _base_spec(mode="auto")
    del payload["auto"]["plan_name"]  # type: ignore[index]
    with pytest.raises(CliError, match="auto.plan_name"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_auto_without_idea_file(tmp_path: Path) -> None:
    payload = _base_spec(mode="auto")
    del payload["auto"]["idea_file"]  # type: ignore[index]
    with pytest.raises(CliError, match="auto.idea_file"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_auto_with_relative_idea_file(tmp_path: Path) -> None:
    payload = _base_spec(mode="auto")
    payload["auto"]["idea_file"] = "idea.txt"  # type: ignore[index]
    with pytest.raises(CliError, match="absolute POSIX path"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_chain_without_spec(tmp_path: Path) -> None:
    payload = _base_spec(mode="chain")
    del payload["chain"]["spec"]  # type: ignore[index]
    with pytest.raises(CliError, match="chain.spec"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_chain_with_relative_spec(tmp_path: Path) -> None:
    payload = _base_spec(mode="chain")
    payload["chain"]["spec"] = "chain.yaml"  # type: ignore[index]
    with pytest.raises(CliError, match="absolute POSIX path"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_unknown_provider(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["provider"] = "bogus"
    with pytest.raises(CliError, match="railway, local, ssh, fly"):
        load_spec(_write_spec(tmp_path, payload))


@pytest.mark.parametrize("effort", ["minimal", "low", "medium", "high"])
def test_load_spec_accepts_each_codex_reasoning_effort(tmp_path: Path, effort: str) -> None:
    payload = _base_spec()
    payload["codex"] = {"model": "gpt-5.5", "reasoning": effort}
    spec = load_spec(_write_spec(tmp_path, payload))
    assert spec.codex.reasoning == effort


def test_load_spec_rejects_unknown_codex_reasoning(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["codex"] = {"model": "gpt-5.4", "reasoning": "extreme"}
    with pytest.raises(CliError, match="minimal, low, medium, high"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_future_provider_with_distinct_error(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["provider"] = "fly"
    with pytest.raises(CliError) as excinfo:
        load_spec(_write_spec(tmp_path, payload))
    assert excinfo.value.code == "future_provider"
    assert "future release" in excinfo.value.message


def test_load_spec_rejects_unknown_agents_key(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["agents"] = {"default": "codex", "shipit": "claude"}
    valid_keys = ", ".join(("default", *DEFAULT_AGENT_ROUTING.keys()))
    with pytest.raises(CliError, match=valid_keys):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_unknown_agent_value(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["agents"] = {"default": "marvin"}
    with pytest.raises(CliError, match="Unknown agent"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_rejects_malformed_secrets(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["secrets"] = "OPENAI_API_KEY"
    with pytest.raises(CliError, match="list of strings"):
        load_spec(_write_spec(tmp_path, payload))


def test_load_spec_defaults_railway_block_when_omitted(tmp_path: Path) -> None:
    payload = _base_spec()
    spec = load_spec(_write_spec(tmp_path, payload))
    assert spec.railway == RailwaySpec(service="agent", session="agent", project=None)


def test_load_spec_accepts_local_provider(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["provider"] = "local"
    payload["local"] = {"compose_project": "mp-local", "workdir": "workspace-cache"}
    spec = load_spec(_write_spec(tmp_path, payload))
    assert spec.provider == "local"
    assert spec.local == LocalSpec(compose_project="mp-local", workdir="workspace-cache")
    assert spec.ssh is None


def test_load_spec_accepts_ssh_provider(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["provider"] = "ssh"
    payload["ssh"] = {
        "host": "deploy.example.com",
        "user": "root",
        "port": 2222,
        "identity_file": "~/.ssh/id_ed25519",
        "remote_dir": "/srv/megaplan",
        "container": "agent-box",
    }
    spec = load_spec(_write_spec(tmp_path, payload))
    assert spec.provider == "ssh"
    assert spec.ssh == SshSpec(
        host="deploy.example.com",
        user="root",
        port=2222,
        identity_file="~/.ssh/id_ed25519",
        remote_dir="/srv/megaplan",
        container="agent-box",
    )
    assert spec.local is None


def test_load_spec_accepts_toolchain_aliases_and_custom_entries(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["toolchains"] = [
        "rust",
        {"name": "my-tool", "install": "RUN echo install-my-tool"},
    ]
    spec = load_spec(_write_spec(tmp_path, payload))
    assert spec.toolchains == [
        ToolchainSpec(name="rust", install="rust"),
        ToolchainSpec(name="my-tool", install="RUN echo install-my-tool"),
    ]


def test_load_spec_rejects_unknown_toolchain_alias(tmp_path: Path) -> None:
    payload = _base_spec()
    payload["toolchains"] = ["zig"]
    with pytest.raises(CliError, match="Unknown toolchain alias"):
        load_spec(_write_spec(tmp_path, payload))


def test_v0190_specs_still_load_with_same_existing_fields(tmp_path: Path) -> None:
    payload = _base_spec(mode="chain")
    spec = load_spec(_write_spec(tmp_path, payload))
    assert asdict(spec)["provider"] == "railway"
    assert spec.repo.url == "https://github.com/example/app.git"
    assert spec.repo.workspace == "/workspace/app"
    assert spec.mode == "chain"
    assert spec.chain is not None
    assert spec.chain.spec == "/workspace/chain.yaml"
    assert spec.railway == RailwaySpec(service="agent", session="agent", project=None)
    assert spec.local is None
    assert spec.ssh is None
    assert spec.toolchains == []
