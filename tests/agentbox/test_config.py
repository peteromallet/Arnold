from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentbox.config import (
    AGENTBOX_CONFIG_ENV,
    AgentBoxConfig,
    AgentBoxConfigError,
    load_agentbox_config,
)


def test_constructor_derives_missing_roots_from_absolute_workspace_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    config = AgentBoxConfig(workspace_root=workspace)

    assert config.workspace_root == workspace
    assert config.repos_root == workspace / "repos"
    assert config.runs_root == workspace / "runs"
    assert config.locks_root == workspace / "locks"
    assert config.ops_store_root == workspace / "ops"
    assert config.operation_runs_path == workspace / "ops" / "operation_runs.json"


def test_explicit_absolute_roots_are_honored(tmp_path: Path) -> None:
    config = AgentBoxConfig(
        workspace_root=tmp_path / "workspace",
        repos_root=tmp_path / "canonical-repos",
        runs_root=tmp_path / "agent-runs",
        locks_root=tmp_path / "repo-locks",
        ops_store_root=tmp_path / "durable-ops",
    )

    assert config.repos_root == tmp_path / "canonical-repos"
    assert config.runs_root == tmp_path / "agent-runs"
    assert config.locks_root == tmp_path / "repo-locks"
    assert config.ops_store_root == tmp_path / "durable-ops"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspace_root", "workspace"),
        ("repos_root", "repos"),
        ("runs_root", "runs"),
        ("locks_root", "locks"),
        ("ops_store_root", "ops"),
    ],
)
def test_relative_roots_are_rejected(field: str, value: str, tmp_path: Path) -> None:
    kwargs: dict[str, object] = {"workspace_root": tmp_path / "workspace", field: value}

    with pytest.raises(AgentBoxConfigError, match=f"{field} must be an absolute path"):
        AgentBoxConfig(**kwargs)


def test_agentbox_config_environment_path_takes_precedence(tmp_path: Path) -> None:
    env_workspace = tmp_path / "env-workspace"
    default_workspace = tmp_path / "default-workspace"
    env_config = tmp_path / "env.yaml"
    default_config = tmp_path / "default.yaml"
    env_config.write_text(yaml.safe_dump({"workspace_root": str(env_workspace)}), encoding="utf-8")
    default_config.write_text(yaml.safe_dump({"workspace_root": str(default_workspace)}), encoding="utf-8")

    config = load_agentbox_config(
        environ={AGENTBOX_CONFIG_ENV: str(env_config)},
        default_config_path=default_config,
    )

    assert config.workspace_root == env_workspace
    assert config.repos_root == env_workspace / "repos"


def test_default_config_path_is_loaded_when_environment_is_unset(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    default_config = tmp_path / "agentbox.yaml"
    default_config.write_text(
        yaml.safe_dump(
            {
                "workspace_root": str(workspace),
                "repos_root": str(tmp_path / "repos-override"),
            }
        ),
        encoding="utf-8",
    )

    config = load_agentbox_config(environ={}, default_config_path=default_config)

    assert config.workspace_root == workspace
    assert config.repos_root == tmp_path / "repos-override"
    assert config.runs_root == workspace / "runs"


def test_missing_default_config_uses_workspace_defaults(tmp_path: Path) -> None:
    config = load_agentbox_config(environ={}, default_config_path=tmp_path / "missing.yaml")

    assert config.workspace_root == Path("/workspace")
    assert config.operation_runs_path == Path("/workspace/ops/operation_runs.json")


def test_missing_environment_config_is_an_error(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing.yaml"

    with pytest.raises(AgentBoxConfigError, match="does not exist"):
        load_agentbox_config(environ={AGENTBOX_CONFIG_ENV: str(missing_config)})


def test_yaml_must_be_a_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "agentbox.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(AgentBoxConfigError, match="must be a YAML mapping"):
        load_agentbox_config(environ={AGENTBOX_CONFIG_ENV: str(config_path)})
