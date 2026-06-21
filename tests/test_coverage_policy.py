from __future__ import annotations

import tomllib
from pathlib import Path


def test_comfy_nodes_are_counted_by_coverage_policy() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    coverage_run = pyproject["tool"]["coverage"]["run"]
    omitted_paths = coverage_run.get("omit", [])

    assert "vibecomfy" in coverage_run["source"]
    assert "vibecomfy/comfy_nodes/*" not in omitted_paths
