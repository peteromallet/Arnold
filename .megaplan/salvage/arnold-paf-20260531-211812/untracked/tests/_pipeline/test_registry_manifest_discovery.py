"""T7 — flag-gated manifest-first discovery in scan_python_pipelines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from megaplan._pipeline import registry
from megaplan._pipeline.discovery.manifest import Manifest


WELL_FORMED = '''\
"""Example pipeline."""
description = "demo"
default_profile = None
supported_modes = ("plan",)
driver = ("subprocess_isolated", "graph+loop-node")
arnold_api_version = "1.0"
capabilities = ("plan",)


def build_pipeline():
    return None
'''


def _make_pkg(tmp_path: Path, name: str, body: str = WELL_FORMED, skill: bool = True) -> Path:
    pkg = tmp_path / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(body)
    if skill:
        (pkg / "SKILL.md").write_text("# skill\n")
    return pkg / "__init__.py"


def _patch_scan_roots(tmp_path: Path):
    return patch.object(
        registry,
        "_get_scan_roots",
        return_value=[(tmp_path, "megaplan.pipelines")],
    )


def test_flag_off_uses_exec_module(tmp_path):
    _make_pkg(tmp_path, "demo_off")

    with _patch_scan_roots(tmp_path), patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "0"}, clear=False
    ), patch.object(
        registry, "_load_module_from_path", wraps=registry._load_module_from_path
    ) as load_spy:
        dispositions = registry.scan_python_pipelines()

    assert load_spy.called, "flag-OFF must use the exec_module path"
    cli_names = [d.cli_name for d in dispositions]
    assert "demo-off" in cli_names
    for d in dispositions:
        assert d.manifest is None


def test_flag_on_skips_exec_module_and_populates_manifest(tmp_path):
    _make_pkg(tmp_path, "demo_on")

    with _patch_scan_roots(tmp_path), patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(registry, "_load_module_from_path") as load_spy:
        dispositions = registry.scan_python_pipelines()

    assert load_spy.call_count == 0, "flag-ON must NOT invoke exec_module"
    by_name = {d.cli_name: d for d in dispositions}
    assert "demo-on" in by_name
    d = by_name["demo-on"]
    assert d.status == "discovered"
    assert isinstance(d.manifest, Manifest)
    assert d.manifest.capabilities == ("plan",)


def test_flag_on_rejects_when_manifest_invalid(tmp_path):
    _make_pkg(tmp_path, "demo_bad", body='description = "x"\n')  # missing fields, no build_pipeline

    with _patch_scan_roots(tmp_path), patch.dict(
        "os.environ", {"MEGAPLAN_M6_MANIFEST_DISCOVERY": "1"}, clear=False
    ), patch.object(registry, "_load_module_from_path") as load_spy:
        dispositions = registry.scan_python_pipelines()

    assert load_spy.call_count == 0
    by_name = {d.cli_name: d for d in dispositions}
    assert by_name["demo-bad"].status == "rejected"
    assert by_name["demo-bad"].manifest is None
    assert "manifest rejected" in by_name["demo-bad"].reason
