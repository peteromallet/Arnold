from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from arnold.workflow.discovery.manifest import Manifest, read_manifest
from arnold_pipelines.megaplan.registry import make_megaplan_registry
from arnold_pipelines.megaplan.runtime.discovery import discover_python_pipelines


def _write_native_pipeline_module(root: Path, *, package_name: str = "native-project") -> Path:
    module = root / "native_project.py"
    module.write_text(
        "name = 'native-project'\n"
        "description = 'native projected shell'\n"
        "default_profile = 'default'\n"
        "supported_modes = ('native', 'graph')\n"
        "driver = ('native', 'test')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('execute',)\n"
        "def build_pipeline():\n"
        "    from arnold.pipeline.native.ir import NativeProgram\n"
        "    from arnold.pipeline.types import Pipeline\n"
        "    return Pipeline(stages={}, entry='', native_program=NativeProgram(name='native-project'))\n",
        encoding="utf-8",
    )
    (root / "SKILL.md").write_text(f"# {package_name}\n", encoding="utf-8")
    return module


def test_discover_python_pipelines_prefers_manifest_metadata_by_default(
    tmp_path: Path,
) -> None:
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    module = _write_native_pipeline_module(user_dir)

    with patch(
        "arnold_pipelines.megaplan.runtime.discovery._get_scan_roots",
        lambda: [(user_dir, None)],
    ):
        discovered = discover_python_pipelines()

    assert len(discovered) == 1
    cli_name, builder, metadata, source_path = discovered[0]
    manifest = read_manifest(module)
    assert isinstance(manifest, Manifest)
    assert cli_name == "native-project"
    assert source_path == module
    assert metadata["name"] == manifest.name
    assert metadata["manifest_hash"] == manifest.manifest_hash
    assert metadata["supported_modes"] == manifest.supported_modes
    assert builder().native_program is not None


def test_megaplan_registry_metadata_stays_aligned_with_manifest(
    tmp_path: Path,
) -> None:
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    module = _write_native_pipeline_module(user_dir, package_name="registry-alignment")

    with patch(
        "arnold_pipelines.megaplan.runtime.discovery._get_scan_roots",
        lambda: [(user_dir, None)],
    ):
        registry = make_megaplan_registry()
        assert registry.names() == ("native-project",)
        manifest = read_manifest(module)

    assert isinstance(manifest, Manifest)
    metadata = registry.metadata_for("native-project")
    assert metadata["name"] == manifest.name
    assert metadata["default_profile"] == manifest.default_profile
    assert metadata["manifest_hash"] == manifest.manifest_hash
    assert metadata["registration_kind"] == "native"
    assert registry.registration_kind_for("native-project") == "native"
    assert registry.get("native-project").native_program is not None
