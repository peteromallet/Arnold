"""Deliberation example package for Arnold pipeline authors.

Demonstrates a four-stage native pipeline (draft → critique → human_review → revise)
using native :func:`~arnold.pipeline.native.decorators.phase` wrappers and the
evidence-pack :class:`~arnold.pipelines.evidence_pack.steps.HumanReviewStep` for the
human-review gate.

IMPORTANT: This directory is named ``_deliberation_example`` (leading underscore)
so that the pipeline discovery scanner in
``arnold/pipelines/megaplan/registry.py:904`` skips it.
The underscore skip rule hides any file or directory whose name begins
with ``_`` or ``.``, keeping internal helpers and examples out of the
public pipeline registry.
"""

from __future__ import annotations

from typing import Any

from arnold.pipelines._deliberation_example._hooks import DeliberationHooks
from arnold.pipelines._deliberation_example.pipelines import (
    build_native_program,
    build_pipeline as _build_pipeline,
)
from arnold.pipeline.types import Pipeline

# ── Required contract fields ──────────────────────────────────────────────

name: str = "deliberation-example"
"""Public CLI-visible pipeline name.  Must be a non-empty ``str``, kept
stable so discovery and deduplication work predictably."""

description: str = (
    "Example deliberation pipeline: draft → critique → human_review → revise."
)
"""Human-readable one-liner describing what the pipeline does."""

driver: str = "native"
"""Execution driver identity.  Uses ``\"native\"`` for the native runtime."""

entrypoint: str = "build_pipeline"
"""Pipeline factory callable reference.

Two formats are accepted:

* **bare name** — resolved via ``getattr(module, entrypoint)``.
* **module:name** — the part after the colon is the bare name;
  the part before is the fully-qualified module to import.
"""

arnold_api_version: str = "1.0"
"""Semver ``major.minor`` string declaring the Arnold SDK version this
package targets."""

capabilities: tuple[str, ...] = ("deliberation", "example")
"""Labels used by the CLI, Capsule contracts, and registry filtering to
classify what the pipeline can do.  Must be a non-empty ``tuple[str, ...]``."""

# ── Recommended contract fields ───────────────────────────────────────────

default_profile: str | None = None
"""Default profile name when the caller does not specify one.
Recommended; may be ``None``."""

supported_modes: tuple[str, ...] = ("native",)
"""Modes explicitly supported by this pipeline package.
Native-only: this pipeline does not support legacy graph execution."""

# ── Entrypoint ────────────────────────────────────────────────────────────


def build_pipeline(
    name: str = "deliberation-example", description: str = ""
) -> Pipeline:
    """Build the deliberation example pipeline (delegates to the builder in :mod:`.pipelines`)."""
    return _build_pipeline(name=name, description=description)


# ── Recommended extension surface ─────────────────────────────────────────

hooks = DeliberationHooks
"""Module-level hooks class for native human-review suspension.

:class:`DeliberationHooks` extends
:class:`~arnold.pipeline.native.hooks.NullNativeRuntimeHooks`
and overrides
:meth:`~arnold.pipeline.native.hooks.NativeRuntimeHooks.should_suspend`
to inspect the phase result after the *human_review* phase completes,
signalling suspension when the step produces a SUSPENDED contract result.

Callers instantiate this class (``hooks=DeliberationHooks()``) and pass it
to :func:`~arnold.pipeline.native.runtime.run_native_pipeline`.
"""
