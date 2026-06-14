from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipeline import (
    PipelineIdRegistryError,
    load_pipeline_id_registries,
    load_pipeline_id_registry,
)
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


def test_pipeline_id_registry_rejects_active_previous_collision_even_when_active_appears_later(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pipeline_ids.json"
    _write_registry(
        path,
        [
            {"name": "a", "stable_id": "a", "previous_stable_ids": ["legacy.id"]},
            {"name": "b", "stable_id": "legacy.id", "typed_contract_capable": True},
        ],
    )

    with pytest.raises(PipelineIdRegistryError, match="collides with previous_stable_id"):
        load_pipeline_id_registry(path)


def test_load_pipeline_id_registries_preserves_single_file_behavior(tmp_path: Path) -> None:
    path = tmp_path / "pipeline_ids.json"
    _write_registry(
        path,
        [{"name": "planning", "stable_id": "megaplan.planning", "typed_contract_capable": True}],
    )

    single = load_pipeline_id_registry(path)
    aggregate = load_pipeline_id_registries([path])

    assert aggregate == single


def test_load_pipeline_id_registries_rejects_duplicate_active_stable_ids_across_files(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    _write_registry(left, [{"name": "a", "stable_id": "shared", "typed_contract_capable": True}])
    _write_registry(right, [{"name": "b", "stable_id": "shared", "typed_contract_capable": True}])

    with pytest.raises(PipelineIdRegistryError, match="duplicate stable_id"):
        load_pipeline_id_registries([left, right])


def test_load_pipeline_id_registries_rejects_duplicate_previous_ids_across_files(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    _write_registry(left, [{"name": "a", "stable_id": "a", "previous_stable_ids": ["legacy.id"]}])
    _write_registry(right, [{"name": "b", "stable_id": "b", "previous_stable_ids": ["legacy.id"]}])

    with pytest.raises(PipelineIdRegistryError, match="duplicate previous_stable_id"):
        load_pipeline_id_registries([left, right])


def test_load_pipeline_id_registries_rejects_duplicate_seam_ids_across_files(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    _write_registry(
        left,
        [{"name": "a", "stable_id": "a", "seam_ids": ["pipe::shared"], "typed_contract_capable": True}],
    )
    _write_registry(
        right,
        [{"name": "b", "stable_id": "b", "seam_ids": ["pipe::shared"], "typed_contract_capable": True}],
    )

    with pytest.raises(PipelineIdRegistryError, match="duplicate seam_id"):
        load_pipeline_id_registries([left, right])


def test_load_pipeline_id_registries_rejects_active_previous_collisions_across_files(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    _write_registry(left, [{"name": "a", "stable_id": "a", "previous_stable_ids": ["legacy.id"]}])
    _write_registry(right, [{"name": "b", "stable_id": "legacy.id", "typed_contract_capable": True}])

    with pytest.raises(PipelineIdRegistryError, match="collides with previous_stable_id"):
        load_pipeline_id_registries([left, right])


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


# ---------------------------------------------------------------------------
# Default discovery coverage
# ---------------------------------------------------------------------------


def test_discover_registry_files_finds_source_controlled_registries() -> None:
    """Default discovery finds at least the canonical megaplan registry file."""
    from scripts.check_pipeline_id_registry import discover_registry_files

    paths = discover_registry_files()
    assert len(paths) >= 1
    found = [p.as_posix() for p in paths]
    assert any("pipeline_ids.json" in p for p in found)


def test_discover_registry_files_returns_paths_within_repo() -> None:
    """Discovered registry files are absolute and exist."""
    from scripts.check_pipeline_id_registry import discover_registry_files

    paths = discover_registry_files()
    for path in paths:
        assert path.is_absolute()
        assert path.exists()
        assert path.name == "pipeline_ids.json"


def test_main_no_args_runs_default_discovery() -> None:
    """Running main() with no arguments discovers registries and passes."""
    from scripts.check_pipeline_id_registry import main

    exit_code = main([])
    # Should succeed since the source-controlled registry is valid
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Per-file drift behavior with multiple registry files
# ---------------------------------------------------------------------------


def test_find_pipeline_id_renames_per_file_multiple_registries(tmp_path: Path) -> None:
    """Per-file drift is computed independently for each registry file pair."""
    base_a = tmp_path / "base_a.json"
    curr_a = tmp_path / "curr_a.json"
    base_b = tmp_path / "base_b.json"
    curr_b = tmp_path / "curr_b.json"

    _write_registry(
        base_a,
        [{"name": "alpha", "stable_id": "alpha.v1", "typed_contract_capable": True}],
    )
    _write_registry(
        curr_a,
        [{"name": "alpha", "stable_id": "alpha.v2", "typed_contract_capable": True}],
    )
    _write_registry(
        base_b,
        [{"name": "beta", "stable_id": "beta.v1", "typed_contract_capable": True}],
    )
    _write_registry(
        curr_b,
        [{"name": "beta", "stable_id": "beta.v1", "typed_contract_capable": True}],
    )

    errors_a = find_pipeline_id_renames(base_a, curr_a)
    errors_b = find_pipeline_id_renames(base_b, curr_b)

    assert len(errors_a) == 1
    assert "alpha" in errors_a[0]
    assert errors_b == []


def test_main_with_explicit_registry_and_no_drift_flag(tmp_path: Path) -> None:
    """Running main with --no-drift skips per-file comparison."""
    curr = tmp_path / "current.json"
    _write_registry(
        curr,
        [{"name": "x", "stable_id": "x.v1", "typed_contract_capable": True}],
    )

    from scripts.check_pipeline_id_registry import main

    exit_code = main(["--no-drift", "--registry", str(curr)])
    assert exit_code == 0


def test_main_with_multiple_explicit_registries(tmp_path: Path) -> None:
    """Running main with two explicit --registry paths validates both."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_registry(
        a,
        [{"name": "alpha", "stable_id": "alpha.id", "typed_contract_capable": True}],
    )
    _write_registry(
        b,
        [{"name": "beta", "stable_id": "beta.id", "typed_contract_capable": True}],
    )

    from scripts.check_pipeline_id_registry import main

    exit_code = main(["--registry", str(a), "--registry", str(b), "--no-drift"])
    assert exit_code == 0


def test_main_detects_aggregate_duplicate_across_explicit_files(tmp_path: Path) -> None:
    """Running main with two explicit files that share a stable_id fails."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_registry(
        a,
        [{"name": "alpha", "stable_id": "shared", "typed_contract_capable": True}],
    )
    _write_registry(
        b,
        [{"name": "beta", "stable_id": "shared", "typed_contract_capable": True}],
    )

    from scripts.check_pipeline_id_registry import main

    exit_code = main(["--registry", str(a), "--registry", str(b), "--no-drift"])
    assert exit_code == 1


# ---------------------------------------------------------------------------
# Three-file aggregate validation
# ---------------------------------------------------------------------------


def test_load_pipeline_id_registries_three_files_all_valid(tmp_path: Path) -> None:
    """Three distinct registry files load successfully."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    c = tmp_path / "c.json"
    _write_registry(
        a,
        [{"name": "alpha", "stable_id": "alpha", "typed_contract_capable": True}],
    )
    _write_registry(
        b,
        [{"name": "beta", "stable_id": "beta", "typed_contract_capable": True}],
    )
    _write_registry(
        c,
        [{"name": "gamma", "stable_id": "gamma", "typed_contract_capable": True}],
    )

    registry = load_pipeline_id_registries([a, b, c])
    assert len(registry.pipelines) == 3
    names = {item["name"] for item in registry.pipelines}
    assert names == {"alpha", "beta", "gamma"}


def test_load_pipeline_id_registries_three_files_duplicate_seam(tmp_path: Path) -> None:
    """Three files with duplicate seam_id across the first and third file fails."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    c = tmp_path / "c.json"
    _write_registry(
        a,
        [{"name": "alpha", "stable_id": "alpha", "seam_ids": ["pipe::dup"], "typed_contract_capable": True}],
    )
    _write_registry(
        b,
        [{"name": "beta", "stable_id": "beta", "typed_contract_capable": True}],
    )
    _write_registry(
        c,
        [{"name": "gamma", "stable_id": "gamma", "seam_ids": ["pipe::dup"], "typed_contract_capable": True}],
    )

    with pytest.raises(PipelineIdRegistryError, match="duplicate seam_id"):
        load_pipeline_id_registries([a, b, c])


def test_load_pipeline_id_registries_three_files_active_previous_collision(tmp_path: Path) -> None:
    """Three files: second file's previous_stable_id collides with third file's active stable_id."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    c = tmp_path / "c.json"
    _write_registry(
        a,
        [{"name": "alpha", "stable_id": "alpha", "typed_contract_capable": True}],
    )
    _write_registry(
        b,
        [{"name": "beta", "stable_id": "beta", "previous_stable_ids": ["legacy.shared"]}],
    )
    _write_registry(
        c,
        [{"name": "gamma", "stable_id": "legacy.shared", "typed_contract_capable": True}],
    )

    with pytest.raises(PipelineIdRegistryError, match="collides"):
        load_pipeline_id_registries([a, b, c])


# ---------------------------------------------------------------------------
# Edge cases: empty registry, missing file, non-object pipeline entry
# ---------------------------------------------------------------------------


def test_load_pipeline_id_registry_empty_pipelines(tmp_path: Path) -> None:
    """A registry with an empty pipelines list loads without error."""
    path = tmp_path / "pipeline_ids.json"
    _write_registry(path, [])

    registry = load_pipeline_id_registry(path)
    assert len(registry.pipelines) == 0


def test_load_pipeline_id_registry_missing_file_raises(tmp_path: Path) -> None:
    """Loading a nonexistent file raises FileNotFoundError."""
    path = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        load_pipeline_id_registry(path)


def test_load_pipeline_id_registries_non_dict_pipeline_entry_raises(tmp_path: Path) -> None:
    """A registry with a non-object pipeline entry raises PipelineIdRegistryError."""
    path = tmp_path / "pipeline_ids.json"
    path.write_text(
        json.dumps({"version": 1, "pipelines": ["not-an-object"]}),
        encoding="utf-8",
    )

    with pytest.raises(PipelineIdRegistryError):
        load_pipeline_id_registry(path)
