from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from megaplan.cloud.spec import RailwaySpec, load_spec
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
    payload["provider"] = "fly"
    with pytest.raises(CliError, match="fly, ssh, local"):
        load_spec(_write_spec(tmp_path, payload))


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
