"""T7 — flag-gated manifest-first discovery in scan_python_pipelines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan._pipeline.behavioral_manifest import (
    StaticBehavioralManifest,
    static_behavioral_manifest_for_pipeline,
)
from arnold.pipelines.megaplan._pipeline import registry
from arnold.pipeline.discovery.manifest import Manifest


WELL_FORMED = '''\
"""Example pipeline."""
name = "demo-on"
description = "demo"
default_profile = None
supported_modes = ("plan",)
driver = ("subprocess_isolated", "graph+loop-node")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("plan",)


def build_pipeline():
    return None
'''


def _make_pkg(tmp_path: Path, name: str, body: str = WELL_FORMED, skill: bool = True) -> Path:
    pkg = tmp_path / name
    pkg.mkdir(parents=True, exist_ok=True)
    body = body.replace('name = "demo-on"', f'name = "{name.replace("_", "-")}"')
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
    assert d.manifest.manifest_hash.startswith("sha256:")


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


BEHAVIORAL_SOURCE = '''\
"""Static behavioral manifest fixture."""
from pathlib import Path

from .helpers import HELPER_VALUE

_PIPELINE_DIR = Path(__file__).parent
_PROMPTS = _PIPELINE_DIR / "prompts"

name = "behavioral-demo"
description = "demo"
default_profile = None
supported_modes = ("plan",)
driver = ("subprocess_isolated", "graph+loop-node")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("plan",)


def build_pipeline():
    from arnold.pipelines.megaplan._pipeline.types import Pipeline

    return (
        Pipeline.builder("behavioral-demo", pipeline_dir=_PIPELINE_DIR)
        .input("draft", file=True)
        .agent("write", prompt=str(_PROMPTS / "write.md"), inputs=["draft"])
        .build()
    )
'''


def _make_behavioral_pkg(tmp_path: Path, *, source: str = BEHAVIORAL_SOURCE) -> Path:
    pkg = tmp_path / "behavioral_demo"
    (pkg / "prompts").mkdir(parents=True)
    (pkg / "__init__.py").write_text(source)
    (pkg / "SKILL.md").write_text("# Behavioral demo\n")
    (pkg / "helpers.py").write_text("HELPER_VALUE = 'stable'\n")
    (pkg / "prompts" / "write.md").write_text("Write from {draft}\n")
    return pkg / "__init__.py"


def _file_hashes(manifest: StaticBehavioralManifest) -> dict[tuple[str, str], str]:
    return {(item.role, item.logical_path): item.sha256 for item in manifest.files}


def test_static_behavioral_manifest_is_stable_and_canonical(tmp_path: Path) -> None:
    module = _make_behavioral_pkg(tmp_path)

    first = static_behavioral_manifest_for_pipeline("behavioral-demo", source_path=module)
    second = static_behavioral_manifest_for_pipeline("behavioral-demo", source_path=module)

    assert first.static_behavioral_hash == second.static_behavioral_hash
    assert first.canonical_bytes == second.canonical_bytes
    assert first.static_behavioral_hash.startswith("sha256:")
    assert first.canonical_bytes == first.canonical_bytes.strip()
    assert b'"projection":"megaplan.static-behavioral-manifest"' in first.canonical_bytes
    assert first.manifest_hash.startswith("sha256:")
    assert {"file": True, "name": "draft"} in first.declared_inputs
    assert any(
        item.get("name", "").startswith("agent_inputs@__init__.py:")
        and item.get("refs") == ["draft"]
        for item in first.declared_inputs
    )
    assert _file_hashes(first).keys() >= {
        ("pipeline_source", "__init__.py"),
        ("skill", "SKILL.md"),
        ("helper", "helpers.py"),
        ("resource", "prompts/write.md"),
    }


@pytest.mark.parametrize(
    ("relative_path", "expected_role"),
    [
        ("__init__.py", "pipeline_source"),
        ("SKILL.md", "skill"),
        ("helpers.py", "helper"),
        ("prompts/write.md", "resource"),
    ],
)
def test_static_behavioral_manifest_changes_for_source_skill_helper_or_resource(
    tmp_path: Path,
    relative_path: str,
    expected_role: str,
) -> None:
    module = _make_behavioral_pkg(tmp_path)
    before = static_behavioral_manifest_for_pipeline("behavioral-demo", source_path=module)

    changed = module.parent / relative_path
    changed.write_text(changed.read_text() + "\nchanged\n")
    after = static_behavioral_manifest_for_pipeline("behavioral-demo", source_path=module)

    assert after.static_behavioral_hash != before.static_behavioral_hash
    before_hashes = _file_hashes(before)
    after_hashes = _file_hashes(after)
    assert after_hashes[(expected_role, relative_path)] != before_hashes[
        (expected_role, relative_path)
    ]


def test_static_behavioral_manifest_reports_unresolved_dynamic_inputs(
    tmp_path: Path,
) -> None:
    module = _make_behavioral_pkg(
        tmp_path,
        source=BEHAVIORAL_SOURCE.replace(
            '.agent("write", prompt=str(_PROMPTS / "write.md"), inputs=["draft"])',
            '.agent("write", prompt=dynamic_prompt(), inputs=dynamic_inputs())',
        ),
    )

    manifest = static_behavioral_manifest_for_pipeline("behavioral-demo", source_path=module)

    unresolved = {(item.role, item.detail) for item in manifest.unresolved_dynamic_inputs}
    assert ("resource", "prompt path is dynamic") in unresolved
    assert ("agent_inputs", "inputs argument is dynamic") in unresolved


def test_static_behavioral_manifest_by_name_does_not_import_pipeline_module(
    tmp_path: Path,
) -> None:
    module = _make_behavioral_pkg(
        tmp_path,
        source=BEHAVIORAL_SOURCE + '\nraise RuntimeError("must not import")\n',
    )

    with _patch_scan_roots(tmp_path), patch.object(
        registry,
        "_load_module_from_path",
        side_effect=AssertionError("static behavioral discovery imported module"),
    ):
        manifest = static_behavioral_manifest_for_pipeline("behavioral-demo")

    assert manifest.pipeline_name == "behavioral-demo"
    assert manifest.source_path == module
