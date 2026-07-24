"""Deliberation example package for Arnold pipeline authors.

Demonstrates a four-stage pipeline (draft → critique → human_review → revise)
using :class:`~arnold.pipeline.steps.agent.AgentStep`,
:class:`~arnold.pipelines.evidence_pack.steps.HumanReviewStep`, and
:class:`~arnold.pipeline.types.Edge`.

IMPORTANT: This directory is named ``_deliberation_example`` (leading underscore)
so that the pipeline discovery scanner in
``arnold/pipelines/megaplan/_pipeline/registry.py:904`` skips it.
The underscore skip rule hides any file or directory whose name begins
with ``_`` or ``.``, keeping internal helpers and examples out of the
public pipeline registry.
"""

from __future__ import annotations

from typing import Any

from arnold.pipelines._deliberation_example._hooks import DeliberationHooks
from arnold.pipelines._deliberation_example.pipelines import build_pipeline as _build_pipeline
from arnold.pipeline.types import Pipeline

# ── Required contract fields ──────────────────────────────────────────────

name: str = "deliberation-example"
"""Public CLI-visible pipeline name.  Must be a non-empty ``str``, kept
stable so discovery and deduplication work predictably."""

description: str = (
    "Example deliberation pipeline: draft → critique → human_review → revise."
)
"""Human-readable one-liner describing what the pipeline does."""

driver: str = "in_process"
"""Execution driver identity.  Accepts a plain string or a tuple of strings.
Uses ``\"in_process\"`` matching evidence_pack convention."""

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

supported_modes: tuple[str, ...] = ()
"""Modes explicitly supported by this pipeline package.
Recommended; may be an empty tuple."""

# ── Entrypoint ────────────────────────────────────────────────────────────


def build_pipeline(
    name: str = "deliberation-example", description: str = ""
) -> Pipeline:
    """Build the deliberation example pipeline (delegates to the builder in :mod:`.pipelines`)."""
    return _build_pipeline(name=name, description=description)


# ── Recommended extension surface ─────────────────────────────────────────

hooks = DeliberationHooks
"""Module-level hooks class for human-review suspension.

:class:`DeliberationHooks` overrides
:meth:`~arnold.pipeline.hooks.NullExecutorHooks.should_suspend`
to inspect ``result.contract_result`` after each step and return
``(True, 'human_review_requested')`` when the status is
:attr:`~arnold.pipeline.types.ContractStatus.SUSPENDED`.

Callers instantiate this class (``hooks=DeliberationHooks()``) and pass it
to :func:`~arnold.pipeline.executor.run_pipeline`.
"""

# resume: Callable[..., Any] | None = None
# """Optional module-level resume driver."""

# build_continuation_pipeline: Callable[[], Pipeline] | None = None
# """Optional nullary callable returning a continuation ``Pipeline``."""
