"""Unit tests for arnold.pipeline.discovery.manifest.read_manifest.

Covers the failure modes listed in M6/T5:
- well-formed manifest
- missing required field
- malformed Python
- arnold_api_version out-of-range
- no top-level build_pipeline AST symbol
- missing SKILL.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipeline.discovery.manifest import (
    CURRENT_MAJOR,
    Manifest,
    ManifestError,
    read_manifest,
)


WELL_FORMED_SOURCE = '''\
"""A test pipeline package."""

name: str = "demo-pipeline"
description: str = "A toy pipeline used in discovery tests."
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("plan",)
driver: tuple[str, str] = ("subprocess_isolated", "graph+loop-node")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("plan",)


def build_pipeline(**kwargs):
    raise NotImplementedError
'''


def _write_package(
    root: Path,
    *,
    source: str = WELL_FORMED_SOURCE,
    with_skill_md: bool = True,
    package: bool = True,
) -> Path:
    if package:
        pkg = root / "demo_pipeline"
        pkg.mkdir(parents=True)
        module = pkg / "__init__.py"
    else:
        pkg = root
        pkg.mkdir(parents=True, exist_ok=True)
        module = root / "demo_pipeline.py"
    module.write_text(source)
    if with_skill_md:
        (module.parent / "SKILL.md").write_text("# demo\n")
    return module


def test_well_formed_manifest(tmp_path: Path) -> None:
    module = _write_package(tmp_path)
    result = read_manifest(module)
    assert isinstance(result, Manifest), result
    assert result.name == "demo-pipeline"
    assert result.description.startswith("A toy")
    assert result.default_profile is None
    assert result.supported_modes == ("plan",)
    assert result.driver == ("subprocess_isolated", "graph+loop-node")
    assert result.arnold_api_version == "1.0"
    assert result.capabilities == ("plan",)
    assert result.manifest_hash.startswith("sha256:")


def test_well_formed_module_file_uses_static_name(tmp_path: Path) -> None:
    module = _write_package(tmp_path, package=False)
    result = read_manifest(module)
    assert isinstance(result, Manifest)
    assert result.name == "demo-pipeline"
    assert result.entrypoint == "build_pipeline"


def test_manifest_hash_is_location_independent(tmp_path: Path) -> None:
    left = _write_package(tmp_path / "left")
    right = _write_package(tmp_path / "right")
    left_result = read_manifest(left)
    right_result = read_manifest(right)
    assert isinstance(left_result, Manifest)
    assert isinstance(right_result, Manifest)
    assert left_result.manifest_hash == right_result.manifest_hash


def test_manifest_hash_changes_with_source_or_skill_md(tmp_path: Path) -> None:
    original = _write_package(tmp_path / "original")
    source_changed = _write_package(
        tmp_path / "source_changed",
        source=WELL_FORMED_SOURCE.replace("A toy pipeline", "A changed pipeline"),
    )
    skill_changed = _write_package(tmp_path / "skill_changed")
    (skill_changed.parent / "SKILL.md").write_text("# changed\n")

    original_result = read_manifest(original)
    source_result = read_manifest(source_changed)
    skill_result = read_manifest(skill_changed)
    assert isinstance(original_result, Manifest)
    assert isinstance(source_result, Manifest)
    assert isinstance(skill_result, Manifest)
    assert source_result.manifest_hash != original_result.manifest_hash
    assert skill_result.manifest_hash != original_result.manifest_hash


def test_missing_required_field(tmp_path: Path) -> None:
    source = WELL_FORMED_SOURCE.replace(
        'capabilities: tuple[str, ...] = ("plan",)\n', ""
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "capabilities" in result.reason
    assert "missing required field" in result.reason


def test_malformed_python(tmp_path: Path) -> None:
    module = _write_package(tmp_path, source="def build_pipeline(:\n    pass\n")
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "malformed Python" in result.reason


@pytest.mark.parametrize("version", ["1.0", "1.5", "1.99"])
def test_arnold_api_version_in_range(tmp_path: Path, version: str) -> None:
    """Valid arnold_api_version values in [1.0, CURRENT_MAJOR) produce a Manifest."""
    source = WELL_FORMED_SOURCE.replace(
        'arnold_api_version: str = "1.0"',
        f'arnold_api_version: str = "{version}"',
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, Manifest), f"expected Manifest for version {version}, got {result}"
    assert result.arnold_api_version == version


def test_api_version_out_of_range_too_new(tmp_path: Path) -> None:
    """Version at or above CURRENT_MAJOR.0 must be rejected with the version in the reason."""
    offending = f"{CURRENT_MAJOR}.0"
    source = WELL_FORMED_SOURCE.replace(
        'arnold_api_version: str = "1.0"',
        f'arnold_api_version: str = "{offending}"',
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "outside supported range" in result.reason
    assert offending in result.reason, f"reason must contain offending version {offending!r}: {result.reason}"


def test_api_version_out_of_range_too_new_minor(tmp_path: Path) -> None:
    """Version above CURRENT_MAJOR.0 (e.g. 2.1) must be rejected with the version in the reason."""
    offending = f"{CURRENT_MAJOR}.1"
    source = WELL_FORMED_SOURCE.replace(
        'arnold_api_version: str = "1.0"',
        f'arnold_api_version: str = "{offending}"',
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "outside supported range" in result.reason
    assert offending in result.reason, f"reason must contain offending version {offending!r}: {result.reason}"


def test_api_version_out_of_range_too_old(tmp_path: Path) -> None:
    """Version below 1.0 must be rejected with the offending version in the reason."""
    offending = "0.9"
    source = WELL_FORMED_SOURCE.replace(
        'arnold_api_version: str = "1.0"',
        f'arnold_api_version: str = "{offending}"',
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "outside supported range" in result.reason
    assert offending in result.reason, f"reason must contain offending version {offending!r}: {result.reason}"


def test_api_version_malformed(tmp_path: Path) -> None:
    source = WELL_FORMED_SOURCE.replace(
        'arnold_api_version: str = "1.0"',
        'arnold_api_version: str = "v1"',
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "not a valid semver" in result.reason


def test_no_build_pipeline_symbol(tmp_path: Path) -> None:
    source = WELL_FORMED_SOURCE.replace(
        "def build_pipeline(**kwargs):\n    raise NotImplementedError\n", ""
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "build_pipeline" in result.reason


def test_missing_skill_md(tmp_path: Path) -> None:
    module = _write_package(tmp_path, with_skill_md=False)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert result.reason == "SKILL.md missing"


def test_does_not_import_module(tmp_path: Path) -> None:
    """If the module raised at import time, read_manifest must still succeed."""

    source = (
        WELL_FORMED_SOURCE
        + '\n\nraise RuntimeError("manifest reader must not execute this")\n'
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, Manifest), result


def test_non_literal_required_field_rejected(tmp_path: Path) -> None:
    """A required field bound to a non-literal expression must reject loudly."""

    source = WELL_FORMED_SOURCE.replace(
        'capabilities: tuple[str, ...] = ("plan",)',
        "capabilities = tuple(['plan'])",
    )
    module = _write_package(tmp_path, source=source)
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert "capabilities" in result.reason
    assert "non-literal" in result.reason


@pytest.mark.parametrize("missing_field", ["name", "description", "supported_modes", "driver", "entrypoint"])
def test_missing_other_required_fields(tmp_path: Path, missing_field: str) -> None:
    lines = [
        line
        for line in WELL_FORMED_SOURCE.splitlines(keepends=True)
        if not line.startswith(f"{missing_field}")
    ]
    module = _write_package(tmp_path, source="".join(lines))
    result = read_manifest(module)
    assert isinstance(result, ManifestError)
    assert missing_field in result.reason
