from __future__ import annotations

from arnold.pipelines.megaplan._pipeline.schema_registry_adapter import (
    create_contract_schema_registry,
    derive_project_root_from_plan_dir,
    resolve_contract_schema_project_root,
)


def test_schema_registry_root_resolution_prefers_explicit_context_root(tmp_path, monkeypatch) -> None:
    explicit_root = tmp_path / "project"
    explicit_root.mkdir()
    env_root = tmp_path / "env-project"
    env_root.mkdir()
    monkeypatch.setenv("MEGAPLAN_CONTRACT_SCHEMA_ROOT", str(env_root))

    resolved = resolve_contract_schema_project_root(explicit_root)
    registry = create_contract_schema_registry(explicit_root)

    assert resolved == explicit_root.resolve()
    assert registry is not None
    assert registry.root == explicit_root.resolve() / ".contract_schemas"


def test_schema_registry_root_resolution_uses_env_override_when_context_missing(tmp_path, monkeypatch) -> None:
    env_root = tmp_path / "env-project"
    env_root.mkdir()
    monkeypatch.setenv("MEGAPLAN_CONTRACT_SCHEMA_ROOT", str(env_root))

    resolved = resolve_contract_schema_project_root()
    registry = create_contract_schema_registry()

    assert resolved == env_root.resolve()
    assert registry is not None
    assert registry.root == env_root.resolve() / ".contract_schemas"


def test_schema_registry_root_resolution_derives_project_root_from_plan_directory(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("MEGAPLAN_CONTRACT_SCHEMA_ROOT", raising=False)
    project_root = tmp_path / "project"
    plan_dir = project_root / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)

    derived = derive_project_root_from_plan_dir(plan_dir)
    registry = create_contract_schema_registry(plan_dir)

    assert derived == project_root.resolve()
    assert registry is not None
    assert registry.root == project_root.resolve() / ".contract_schemas"
