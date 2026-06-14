"""Template package for Arnold pipeline authors.

Copy this directory, rename it (without a leading underscore), fill in
the contract fields, and replace the skeleton pipeline with real logic.

IMPORTANT: This directory is named ``_template`` (leading underscore)
so that the pipeline discovery scanner in
``arnold/pipelines/megaplan/_pipeline/registry.py:904`` skips it.
The underscore skip rule hides any file or directory whose name begins
with ``_`` or ``.``, keeping internal helpers and templates out of the
public pipeline registry.
"""

from __future__ import annotations

from typing import Any

from arnold.pipelines._authoring import build_skeleton_pipeline
from arnold.pipeline.types import Pipeline

# ── Required contract fields ──────────────────────────────────────────────

name: str = "my-pipeline"
"""Public CLI-visible pipeline name.  Must be a non-empty ``str``, kept
stable so discovery and deduplication work predictably."""

description: str = (
    "A new Arnold pipeline (replace this description with a meaningful one-liner)."
)
"""Human-readable one-liner describing what the pipeline does."""

driver: str | tuple[str, ...] = "in_process"
"""Execution driver identity.  Accepts a plain string or a tuple of strings.
Evidence-pack uses ``\"in_process\"``; Megaplan uses ``(\"megaplan\", \"planning\")``."""

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

capabilities: tuple[str, ...] = ("skeleton",)
"""Labels used by the CLI, Capsule contracts, and registry filtering to
classify what the pipeline can do.  Must be a non-empty ``tuple[str, ...]``."""

# ── Recommended contract fields ───────────────────────────────────────────

default_profile: str | None = None
"""Default profile name when the caller does not specify one.
Recommended; may be ``None``."""

supported_modes: tuple[str, ...] = ()
"""Modes explicitly supported by this pipeline package.
Recommended; may be an empty tuple."""

# ── Entrypoint ────────────────────────────────────────────────────────────


def build_pipeline(name: str = "my-pipeline", description: str = "") -> Pipeline:
    """Build the pipeline (delegates to :func:`build_skeleton_pipeline`).

    Replace this function body with real pipeline construction logic
    (using :class:`arnold.pipeline.builder.PipelineBuilder`) once you
    are ready to move beyond the skeleton.
    """
    return build_skeleton_pipeline(
        name=name or "my-pipeline",
        description=description or "Skeleton pipeline — replace with real logic.",
    )


# ── Recommended extension surface (optional — fill in as needed) ──────────

# hooks: type[ExecutorHooks] | None = None
# """Optional module-level hooks class or instance."""

# resume: Callable[..., Any] | None = None
# """Optional module-level resume driver."""

# build_continuation_pipeline: Callable[[], Pipeline] | None = None
# """Optional nullary callable returning a continuation ``Pipeline``."""
