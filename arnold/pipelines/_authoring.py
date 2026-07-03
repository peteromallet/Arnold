"""Native-first pipeline authoring helpers (import-only).

This module lives at ``arnold.pipelines._authoring`` and is discoverable
via PEP 420 namespace packages — the ``arnold/pipelines/`` directory
**must not** have an ``__init__.py``.

Usage::

    from arnold.pipelines._authoring import (
        validate_package_module,
        REQUIRED_METADATA_KEYS,
        NATIVE_DRIVER_PREFIX,
        NATIVE_MODE_LITERAL,
    )

``validate_package_module(pkg)`` inspects a pipeline package module and
raises structured :exc:`_AuthoringError` (or subclasses) when the
native-first contract is violated.  It is the authoritative guard for
scaffolds, generators, and doc examples.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Mapping, Sequence

from arnold.pipeline import Pipeline
from arnold.pipeline.native import validate_pipeline_purity
from arnold.pipeline.native.ir import NativeProgram

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

#: Module-level keys every native-first pipeline package **must** export.
REQUIRED_METADATA_KEYS: tuple[str, ...] = (
    "name",
    "description",
    "driver",
    "supported_modes",
    "entrypoint",
    "arnold_api_version",
)

#: Optional but recommended metadata keys.
RECOMMENDED_METADATA_KEYS: tuple[str, ...] = (
    "default_profile",
    "recommended_profiles",
    "capabilities",
)

#: The ``driver`` tuple **must** start with this literal.
NATIVE_DRIVER_PREFIX: str = "native"

#: The literal that **must** appear in ``supported_modes``.
NATIVE_MODE_LITERAL: str = "native"

#: Contract docstring (stable prose, used by docs and error messages).
CONTRACT_TEXT: str = (
    "A native-first pipeline package exports module-level metadata "
    "(`name`, `description`, `driver`, `supported_modes`, `entrypoint`, "
    "`arnold_api_version`) and a `build_pipeline()` callable that returns "
    "an `arnold.pipeline.Pipeline` with a non-null `native_program`. "
    "The `driver` tuple must start with `'native'` and `supported_modes` "
    "must include `'native'`."
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class _AuthoringError(ValueError):
    """Base error for authoring-contract violations."""


class _MissingMetadataError(_AuthoringError):
    """Raised when a required module-level metadata key is absent."""


class _InvalidDriverError(_AuthoringError):
    """Raised when ``driver`` does not start with ``'native'``."""


class _MissingNativeModeError(_AuthoringError):
    """Raised when ``'native'`` is not in ``supported_modes``."""


class _BuildPipelineError(_AuthoringError):
    """Raised when ``build_pipeline()`` is missing, not callable, or returns
    a pipeline with a null ``native_program``."""


class _RoutingPurityError(_AuthoringError):
    """Raised when a native program's routing decisions contain impure code."""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _check_required_metadata(pkg: object) -> None:
    """Verify every key in *REQUIRED_METADATA_KEYS* is present on *pkg*."""
    missing = [k for k in REQUIRED_METADATA_KEYS if not hasattr(pkg, k)]
    if missing:
        raise _MissingMetadataError(
            f"Missing required module-level metadata: {', '.join(sorted(missing))}"
        )


def _check_driver(driver: object) -> None:
    """*driver* must be a sequence whose first element is ``'native'``."""
    if not isinstance(driver, Sequence) or isinstance(driver, (str, bytes)):
        raise _InvalidDriverError(
            f"`driver` must be a non-string sequence; got {type(driver).__name__}"
        )
    if len(driver) == 0:
        raise _InvalidDriverError("`driver` must be non-empty")
    if driver[0] != NATIVE_DRIVER_PREFIX:
        raise _InvalidDriverError(
            f"`driver[0]` must be {NATIVE_DRIVER_PREFIX!r}; got {driver[0]!r}"
        )


def _check_supported_modes(supported_modes: object) -> None:
    """*supported_modes* must be a sequence containing ``'native'``."""
    if not isinstance(supported_modes, Sequence) or isinstance(supported_modes, (str, bytes)):
        raise _MissingNativeModeError(
            f"`supported_modes` must be a non-string sequence; "
            f"got {type(supported_modes).__name__}"
        )
    if NATIVE_MODE_LITERAL not in supported_modes:
        raise _MissingNativeModeError(
            f"`supported_modes` must include {NATIVE_MODE_LITERAL!r}; "
            f"got {supported_modes!r}"
        )


def _check_build_pipeline(pkg: object) -> Pipeline:
    """Call ``build_pipeline()`` and ensure the result has a non-null
    *native_program*.

    Returns the pipeline for further inspection / downstream use.
    """
    build = getattr(pkg, "build_pipeline", None)
    if build is None:
        raise _BuildPipelineError(
            "Module must export a `build_pipeline` callable"
        )
    if not callable(build):
        raise _BuildPipelineError(
            f"`build_pipeline` must be callable; got {type(build).__name__}"
        )

    try:
        result = build()
    except Exception as exc:
        raise _BuildPipelineError(
            f"`build_pipeline()` raised {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(result, Pipeline):
        raise _BuildPipelineError(
            f"`build_pipeline()` must return an `arnold.pipeline.Pipeline`; "
            f"got {type(result).__name__}"
        )

    if result.native_program is None:
        raise _BuildPipelineError(
            "`build_pipeline()` returned a Pipeline with null `native_program`. "
            "Native-first packages must attach a compiled native program."
        )

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_package_module(pkg: object) -> Pipeline:
    """Validate *pkg* against the native-first contract and return its pipeline.

    *pkg* can be a module object (e.g. ``importlib.import_module(...)``)
    or any object that exposes the required module-level attributes.

    Checks performed (in order):

    1. All ``REQUIRED_METADATA_KEYS`` are present.
    2. ``driver`` is a sequence whose first element is ``'native'``.
    3. ``supported_modes`` is a sequence containing ``'native'``.
    4. ``build_pipeline()`` exists, is callable, returns a
       :class:`arnold.pipeline.Pipeline`, and that pipeline has a
       non-null ``native_program``.
    5. When ``native_program`` is a :class:`~arnold.pipeline.native.ir.NativeProgram`
       instance, routing-purity validation is performed on its decision bodies
       and static topology.

    Returns the :class:`~arnold.pipeline.Pipeline` produced by
    ``build_pipeline()`` (already validated).

    Raises:
        _MissingMetadataError: missing required metadata keys.
        _InvalidDriverError: ``driver`` does not start with ``'native'``.
        _MissingNativeModeError: ``'native'`` not in ``supported_modes``.
        _BuildPipelineError: ``build_pipeline`` contract violation.
        _RoutingPurityError: native program routing decisions contain impure
            code or invalid static topology.
    """
    _check_required_metadata(pkg)
    _check_driver(getattr(pkg, "driver"))
    _check_supported_modes(getattr(pkg, "supported_modes"))
    pipeline = _check_build_pipeline(pkg)

    # Routing-purity validation for real NativeProgram instances only.
    # Non-NativeProgram sentinels (e.g. object() used in test fakes) are
    # silently skipped to preserve sentinel compatibility.
    if isinstance(pipeline.native_program, NativeProgram):
        report = validate_pipeline_purity(pipeline.native_program)
        if not report.ok:
            raise _RoutingPurityError(
                f"Native program '{pipeline.native_program.name}' has "
                f"{len(report.diagnostics)} routing-purity violation(s): "
                + "; ".join(
                    f"[{d.code}] {d.message}"
                    for d in report.diagnostics[:5]
                )
                + (
                    f" (+{len(report.diagnostics) - 5} more)"
                    if len(report.diagnostics) > 5
                    else ""
                )
            )

    return pipeline


__all__ = [
    "_AuthoringError",
    "_BuildPipelineError",
    "_InvalidDriverError",
    "_MissingMetadataError",
    "_MissingNativeModeError",
    "_RoutingPurityError",
    "CONTRACT_TEXT",
    "NATIVE_DRIVER_PREFIX",
    "NATIVE_MODE_LITERAL",
    "RECOMMENDED_METADATA_KEYS",
    "REQUIRED_METADATA_KEYS",
    "validate_package_module",
]
