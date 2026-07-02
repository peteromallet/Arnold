"""Template package for Arnold pipeline authors (native-first).

Copy this directory, rename it (without a leading underscore), fill in the
contract fields, and replace the skeleton phases with real logic. The
``build_pipeline()`` entrypoint returns a native-first projected
:class:`arnold.pipeline.Pipeline` shell with a non-null ``native_program``
that the runtime executes directly.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from arnold.pipeline.native import project_graph
from arnold.pipeline.types import Pipeline

from arnold_pipelines._template.pipelines import build_native_program


# ── Required contract fields ─────────────────────────────────────────────

name: str = "my-pipeline"
"""Public CLI-visible pipeline name. Keep stable for discovery."""

description: str = (
    "A new Arnold native-first pipeline (replace with a meaningful one-liner)."
)
"""Human-readable one-liner describing what the pipeline does."""

driver: tuple[str, str] = ("native", "project+validate")
"""Execution driver tuple. Must start with ``'native'``."""

supported_modes: tuple[str, ...] = ("native",)
"""Modes the pipeline package supports. Must include ``'native'``."""

entrypoint: str = "build_pipeline"
"""Pipeline factory callable. Resolved via ``getattr(module, entrypoint)``."""

arnold_api_version: str = "1.0"
"""Semver ``major.minor`` string declaring the Arnold SDK version."""

# ── Recommended contract fields ──────────────────────────────────────────

default_profile: str | None = None
"""Default profile name when the caller does not specify one."""

recommended_profiles: tuple[str, ...] = ()
"""Recommended profiles for this pipeline."""

capabilities: tuple[str, ...] = ("skeleton",)
"""Labels used by the CLI and registry to classify this pipeline."""


def _native_program() -> Any:
    """Compile and return the native program for the template pipeline."""
    return build_native_program()


def build_pipeline() -> Pipeline:
    """Return the canonical native-backed ``my-pipeline`` :class:`Pipeline`.

    The returned shell projects the native-program topology into a
    :class:`Pipeline` with a non-null ``native_program``, satisfying
    the native-first authoring contract.
    """
    native = _native_program()
    projected = project_graph(native, key_mode="phase")
    return replace(
        projected,
        resource_bundles=(),
        native_program=native,
    )


__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
