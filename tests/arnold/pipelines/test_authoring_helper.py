"""Tests for ``arnold.pipelines._authoring`` native-first contract validation.

These tests live under ``tests/arnold/pipelines/`` without a package
``__init__.py``, verifying that pytest can collect them via
``--import-mode=importlib`` (PEP 420 namespace package).  Do **not** add an
``__init__.py`` to this directory.
"""

from __future__ import annotations

import importlib
import types

import pytest

from arnold.pipeline import Pipeline
from arnold.pipelines._authoring import (
    CONTRACT_TEXT,
    NATIVE_DRIVER_PREFIX,
    NATIVE_MODE_LITERAL,
    REQUIRED_METADATA_KEYS,
    _AuthoringError,
    _BuildPipelineError,
    _InvalidDriverError,
    _MissingMetadataError,
    _MissingNativeModeError,
    validate_package_module,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_module(**attrs: object) -> types.ModuleType:
    """Return a lightweight stand-in module with the given attributes."""
    mod = types.ModuleType("_test_fake_pkg")
    for name, value in attrs.items():
        setattr(mod, name, value)
    return mod


def _native_first_module(**overrides: object) -> types.ModuleType:
    """Return a module that satisfies the native-first contract.

    Override any kwarg to introduce a deliberate violation.
    """
    defaults: dict[str, object] = {
        "name": "test-pkg",
        "description": "A test native-first package.",
        "driver": ("native", "project+validate"),
        "supported_modes": ("native", "dry-run"),
        "entrypoint": "build_pipeline",
        "arnold_api_version": "1.0",
        "build_pipeline": lambda: Pipeline(
            stages={}, entry="start", native_program=object()
        ),
    }
    defaults.update(overrides)
    return _make_module(**defaults)


# ---------------------------------------------------------------------------
# Positive cases — real shipped packages
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pkg_name",
    [
        "arnold_pipelines.megaplan.pipelines.jokes",
        "arnold_pipelines.megaplan.pipelines.doc",
    ],
)
def test_validate_accepts_shipped_native_packages(pkg_name: str) -> None:
    """Shipped native-first packages must pass the authoring validator."""
    pkg = importlib.import_module(pkg_name)
    pipeline = validate_package_module(pkg)
    assert isinstance(pipeline, Pipeline)
    assert pipeline.native_program is not None


# ---------------------------------------------------------------------------
# Negative cases — graph / shim / fallback
# ---------------------------------------------------------------------------


def test_validate_rejects_graph_driver() -> None:
    """A ``driver`` that does not start with ``'native'`` is rejected."""
    pkg = _native_first_module(driver=("graph", "linear"))
    with pytest.raises(_InvalidDriverError, match="must be 'native'"):
        validate_package_module(pkg)


def test_validate_rejects_missing_native_in_supported_modes() -> None:
    """``'native'`` must appear in ``supported_modes``."""
    pkg = _native_first_module(supported_modes=("graph", "dry-run"))
    with pytest.raises(_MissingNativeModeError, match="must include 'native'"):
        validate_package_module(pkg)


def test_validate_rejects_null_native_program() -> None:
    """A Pipeline with ``native_program=None`` is rejected."""

    def _build_null() -> Pipeline:
        return Pipeline(stages={}, entry="start", native_program=None)

    pkg = _native_first_module(build_pipeline=_build_null)
    with pytest.raises(_BuildPipelineError, match="null `native_program`"):
        validate_package_module(pkg)


def test_validate_rejects_missing_build_pipeline() -> None:
    """A module without ``build_pipeline`` is rejected."""
    pkg = _make_module(
        name="test-pkg",
        description="No build_pipeline.",
        driver=("native", "project+validate"),
        supported_modes=("native",),
        entrypoint="build_pipeline",
        arnold_api_version="1.0",
    )
    with pytest.raises(_BuildPipelineError, match="build_pipeline"):
        validate_package_module(pkg)


@pytest.mark.parametrize(
    "missing_key",
    list(REQUIRED_METADATA_KEYS),
)
def test_validate_rejects_missing_required_metadata_key(missing_key: str) -> None:
    """Each ``REQUIRED_METADATA_KEYS`` entry is individually checked."""
    overrides = {missing_key: None}
    pkg = _native_first_module(**overrides)
    # After the override we must delete the attr so hasattr fails.
    delattr(pkg, missing_key)
    with pytest.raises(_MissingMetadataError, match=missing_key):
        validate_package_module(pkg)


def test_validate_rejects_non_callable_build_pipeline() -> None:
    """``build_pipeline`` that is not callable is rejected."""
    pkg = _native_first_module(build_pipeline="not-a-function")
    with pytest.raises(_BuildPipelineError, match="must be callable"):
        validate_package_module(pkg)


def test_validate_accepts_fully_valid_fake_module() -> None:
    """A synthetic module meeting all contract requirements passes."""
    pipeline = validate_package_module(_native_first_module())
    assert isinstance(pipeline, Pipeline)
    assert pipeline.native_program is not None


# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------


def test_contract_constants_are_stable() -> None:
    """The public contract constants are present and of expected types."""
    assert isinstance(CONTRACT_TEXT, str)
    assert len(CONTRACT_TEXT) > 50
    assert NATIVE_DRIVER_PREFIX == "native"
    assert NATIVE_MODE_LITERAL == "native"
    assert isinstance(REQUIRED_METADATA_KEYS, tuple)
    assert "driver" in REQUIRED_METADATA_KEYS
    assert "supported_modes" in REQUIRED_METADATA_KEYS
    assert "build_pipeline" not in REQUIRED_METADATA_KEYS  # checked separately


# ---------------------------------------------------------------------------
# Template rejection — graph-era scaffold
# ---------------------------------------------------------------------------


def test_validate_rejects_graph_template() -> None:
    """The current _template uses ``driver=('graph',...)`` and must be rejected."""
    pkg = importlib.import_module("arnold_pipelines._template")
    with pytest.raises(_AuthoringError):
        validate_package_module(pkg)
