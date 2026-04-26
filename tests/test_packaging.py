from __future__ import annotations

import tomllib
from pathlib import Path


def test_runpod_dependencies_stay_out_of_core_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    core_dependencies = project["dependencies"]
    runpod_dependencies = project["optional-dependencies"]["runpod-local"]

    assert "python-dotenv>=1.0" not in core_dependencies
    assert "python-dotenv>=1.0" in runpod_dependencies
    assert not any("file://" in dependency or "/Users/" in dependency for dependency in runpod_dependencies)


def test_unused_schema_dependencies_stay_out_of_core_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert "pydantic>=2" not in project["dependencies"]
