from __future__ import annotations

import tomllib
from pathlib import Path


def test_top_level_public_api_exports_promised_names() -> None:
    import vibecomfy
    from vibecomfy.ingest.loader import load_template, load_workflow_json
    from vibecomfy.registry.library import workflow_from_template
    from vibecomfy.runtime.run import run_embedded, run_embedded_sync

    expected = {
        "load_workflow_json": load_workflow_json,
        "load_template": load_template,
        "workflow_from_template": workflow_from_template,
        "run_embedded": run_embedded,
        "run_embedded_sync": run_embedded_sync,
    }

    for name, value in expected.items():
        assert getattr(vibecomfy, name) is value
        assert name in vibecomfy.__all__


def test_nodes_package_layout_stays_collapsed() -> None:
    nodes_dir = Path("vibecomfy/nodes")

    assert not (nodes_dir / "_generated").exists()
    assert sorted(path.relative_to(nodes_dir).as_posix() for path in nodes_dir.rglob("*.pyi")) == []


def test_runpod_dependencies_stay_out_of_core_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    core_dependencies = project["dependencies"]
    runpod_dependencies = project["optional-dependencies"]["runpod-local"]

    assert "python-dotenv>=1.0" not in core_dependencies
    assert "python-dotenv>=1.0" in runpod_dependencies
    assert not any("file://" in dependency or "/Users/" in dependency for dependency in runpod_dependencies)
    assert any(
        dependency == "runpod-lifecycle @ git+https://github.com/banodoco/runpod-lifecycle.git@v0.1.1"
        for dependency in runpod_dependencies
    )


def test_unused_schema_dependencies_stay_out_of_core_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert "pydantic>=2" not in project["dependencies"]
