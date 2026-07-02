"""Smoke tests for :mod:`arnold.pipeline.discovery.manifest` shim.

These tests verify that the M1 compatibility shim correctly delegates
to :mod:`arnold.workflow.discovery.manifest` and exposes the expected
symbols and behaviours.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from arnold.pipeline.discovery.manifest import (
    ARNOLD_IDENTITY_SCHEMA,
    CURRENT_MAJOR,
    REQUIRED_FIELDS,
    Manifest,
    ManifestError,
    derive_runtime_pipeline_id,
    read_manifest,
)
from arnold_pipelines.megaplan.runtime.discovery import _manifest_discovery_enabled


# ---------------------------------------------------------------------------
# Import / shim wiring
# ---------------------------------------------------------------------------


def test_manifest_shim_exposes_expected_symbols() -> None:
    """Every symbol that the pipeline discovery __init__ re-exports must exist."""
    assert isinstance(CURRENT_MAJOR, int) and CURRENT_MAJOR > 0
    assert isinstance(REQUIRED_FIELDS, tuple) and len(REQUIRED_FIELDS) > 0
    assert isinstance(ARNOLD_IDENTITY_SCHEMA, str) and ARNOLD_IDENTITY_SCHEMA
    assert Manifest is not None
    assert ManifestError is not None
    assert callable(read_manifest)
    assert callable(derive_runtime_pipeline_id)


def test_manifest_shim_imports_are_workflow_backed() -> None:
    """The shim delegates to the workflow discovery implementation."""
    from arnold.workflow.discovery import manifest as _wf_manifest

    assert Manifest is _wf_manifest.Manifest
    assert ManifestError is _wf_manifest.ManifestError
    assert read_manifest is _wf_manifest.read_manifest
    assert derive_runtime_pipeline_id is _wf_manifest.derive_runtime_pipeline_id
    assert CURRENT_MAJOR is _wf_manifest.CURRENT_MAJOR
    assert REQUIRED_FIELDS is _wf_manifest.REQUIRED_FIELDS
    assert ARNOLD_IDENTITY_SCHEMA is _wf_manifest.ARNOLD_IDENTITY_SCHEMA


def test_manifest_first_discovery_is_default_compatibility_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", raising=False)
    assert _manifest_discovery_enabled() is True

    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0")
    assert _manifest_discovery_enabled() is True


# ---------------------------------------------------------------------------
# read_manifest smoke
# ---------------------------------------------------------------------------


def test_read_manifest_rejects_missing_file(tmp_path: Path) -> None:
    result = read_manifest(tmp_path / "nonexistent.py")
    assert isinstance(result, ManifestError)
    assert "unable to read module file" in result.reason


def test_read_manifest_rejects_empty_file(tmp_path: Path) -> None:
    module = tmp_path / "empty.py"
    module.write_text("", encoding="utf-8")
    result = read_manifest(module)
    assert isinstance(result, ManifestError)


def test_read_manifest_rejects_non_python(tmp_path: Path) -> None:
    module = tmp_path / "broken.py"
    module.write_text("this is not valid python {{{", encoding="utf-8")
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "malformed Python" in result.reason


def test_read_manifest_rejects_missing_required_fields(tmp_path: Path) -> None:
    module = tmp_path / "partial.py"
    module.write_text("name = 'test'\n", encoding="utf-8")
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "missing required field" in result.reason


def _write_minimal_manifest_module(path: Path) -> None:
    """Write a module containing the minimum required manifest fields."""
    path.write_text(
        textwrap.dedent("""\
            name = "smoke-test"
            description = "A minimal manifest for smoke testing"
            default_profile = None
            supported_modes = ["native"]
            driver = ["native"]
            entrypoint = "build_pipeline"
            arnold_api_version = "1.0"
            capabilities = []

            def build_pipeline():
                pass
        """),
        encoding="utf-8",
    )
    # Also create the required SKILL.md sibling
    (path.parent / "SKILL.md").write_text("# Smoke Test\n", encoding="utf-8")


def test_read_manifest_succeeds_for_valid_module(tmp_path: Path) -> None:
    module = tmp_path / "valid.py"
    _write_minimal_manifest_module(module)
    result = read_manifest(module)
    assert isinstance(result, Manifest)
    assert result.name == "smoke-test"
    assert result.description == "A minimal manifest for smoke testing"
    assert result.default_profile is None
    assert result.manifest_hash.startswith("sha256:")


def test_read_manifest_missing_skill_md(tmp_path: Path) -> None:
    module = tmp_path / "noskill.py"
    _write_minimal_manifest_module(module)
    (module.parent / "SKILL.md").unlink()
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "SKILL.md" in result.reason


# ---------------------------------------------------------------------------
# derive_runtime_pipeline_id smoke
# ---------------------------------------------------------------------------


def test_derive_runtime_pipeline_id_produces_stable_output() -> None:
    a = derive_runtime_pipeline_id("planning", "sha256:" + "a" * 64)
    b = derive_runtime_pipeline_id("planning", "sha256:" + "a" * 64)
    assert a == b
    assert isinstance(a, str) and a


def test_derive_runtime_pipeline_id_differs_on_alias_change() -> None:
    a = derive_runtime_pipeline_id("planning", "sha256:" + "a" * 64)
    b = derive_runtime_pipeline_id("review", "sha256:" + "a" * 64)
    assert a != b


def test_derive_runtime_pipeline_id_differs_on_hash_change() -> None:
    a = derive_runtime_pipeline_id("planning", "sha256:" + "a" * 64)
    b = derive_runtime_pipeline_id("planning", "sha256:" + "b" * 64)
    assert a != b
