from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import PipelineIdRegistryError, load_pipeline_id_registry
from scripts.check_pipeline_id_registry import find_pipeline_id_renames, main as check_pipeline_id_registry_main


def _write_registry(path: Path, pipelines: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"version": 1, "pipelines": pipelines}), encoding="utf-8")


def test_source_controlled_pipeline_id_registry_loads() -> None:
    registry = load_pipeline_id_registry(
        Path("arnold/pipelines/megaplan/_pipeline/pipeline_ids.json")
    )

    assert "planning" in registry.by_name
    assert registry.by_name["planning"]["stable_id"] == "megaplan.planning"


def test_pipeline_id_registry_rejects_duplicate_stable_ids(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_ids.json"
    _write_registry(
        path,
        [
            {"name": "a", "stable_id": "same", "typed_contract_capable": True},
            {"name": "b", "stable_id": "same", "typed_contract_capable": True},
        ],
    )

    with pytest.raises(PipelineIdRegistryError, match="duplicate stable_id"):
        load_pipeline_id_registry(path)


def test_pipeline_id_registry_rejects_missing_stable_id_for_typed_contract_capable_pipeline(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pipeline_ids.json"
    _write_registry(path, [{"name": "a", "typed_contract_capable": True}])

    with pytest.raises(PipelineIdRegistryError, match="missing stable_id"):
        load_pipeline_id_registry(path)


def test_pipeline_id_registry_rejects_duplicate_seam_ids_across_pipelines(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_ids.json"
    _write_registry(
        path,
        [
            {
                "name": "a",
                "stable_id": "a",
                "typed_contract_capable": True,
                "seam_ids": ["pipe::b.in<=a.out"],
            },
            {
                "name": "b",
                "stable_id": "b",
                "typed_contract_capable": True,
                "seam_ids": ["pipe::b.in<=a.out"],
            },
        ],
    )

    with pytest.raises(PipelineIdRegistryError, match="duplicate seam_id"):
        load_pipeline_id_registry(path)


def test_pipeline_id_registry_rejects_duplicate_previous_stable_ids(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_ids.json"
    _write_registry(
        path,
        [
            {"name": "a", "stable_id": "a", "previous_stable_ids": ["legacy.id"]},
            {"name": "b", "stable_id": "b", "previous_stable_ids": ["legacy.id"]},
        ],
    )

    with pytest.raises(PipelineIdRegistryError, match="duplicate previous_stable_id"):
        load_pipeline_id_registry(path)


def test_pipeline_id_rename_guard_fails_without_migration_alias_metadata(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    _write_registry(
        base,
        [{"name": "planning", "stable_id": "megaplan.planning", "typed_contract_capable": True}],
    )
    _write_registry(
        current,
        [{"name": "planning", "stable_id": "megaplan.planning.v2", "typed_contract_capable": True}],
    )

    errors = find_pipeline_id_renames(base, current)

    assert errors == [
        "pipeline 'planning' changed stable_id from 'megaplan.planning' to 'megaplan.planning.v2' without previous_stable_ids metadata"
    ]


def test_pipeline_id_rename_guard_passes_with_previous_stable_id_alias(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    _write_registry(
        base,
        [{"name": "planning", "stable_id": "megaplan.planning", "typed_contract_capable": True}],
    )
    _write_registry(
        current,
        [
            {
                "name": "planning",
                "stable_id": "megaplan.planning.v2",
                "typed_contract_capable": True,
                "previous_stable_ids": ["megaplan.planning"],
            }
        ],
    )

    assert find_pipeline_id_renames(base, current) == []
    assert check_pipeline_id_registry_main(
        ["--base-registry", str(base), "--registry", str(current)]
    ) == 0
