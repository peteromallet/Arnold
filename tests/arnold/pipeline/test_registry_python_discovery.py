from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from arnold_pipelines.megaplan.registry import make_megaplan_registry
from arnold_pipelines.megaplan.runtime.discovery import discover_python_pipelines


def _write_graph_compat_pipeline_module(root: Path) -> Path:
    module = root / "graph_compat.py"
    module.write_text(
        "name = 'graph-compat'\n"
        "description = 'graph compatibility package'\n"
        "default_profile = None\n"
        "supported_modes = ('graph',)\n"
        "driver = ('graph', 'compat')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('execute',)\n"
        "class _Runner:\n"
        "    def run_native_pipeline(self, **kwargs):\n"
        "        return {'ok': True, 'kwargs': kwargs}\n"
        "def build_pipeline():\n"
        "    from arnold.pipeline.types import Pipeline\n"
        "    return Pipeline(stages={}, entry='', resource_bundles=(_Runner(),))\n",
        encoding="utf-8",
    )
    (root / "SKILL.md").write_text("# graph compat\n", encoding="utf-8")
    return module


def test_python_discovery_keeps_graph_only_packages_as_compatibility_entries(
    tmp_path: Path,
) -> None:
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    module = _write_graph_compat_pipeline_module(user_dir)

    with patch(
        "arnold_pipelines.megaplan.runtime.discovery._get_scan_roots",
        lambda: [(user_dir, None)],
    ):
        discovered = discover_python_pipelines()
        registry = make_megaplan_registry()
        assert registry.names() == ("graph-compat",)

    assert len(discovered) == 1
    cli_name, builder, metadata, source_path = discovered[0]
    assert cli_name == "graph-compat"
    assert source_path == module
    assert metadata["supported_modes"] == ("graph",)
    assert registry.registration_kind_for("graph-compat") == "graph_compatibility"
    assert metadata["driver"] == ("graph", "compat")
    pipeline = builder()
    assert callable(pipeline.resource_bundles[0].run_native_pipeline)
    assert (
        registry.metadata_for("graph-compat")["registration_kind"]
        == "graph_compatibility"
    )
