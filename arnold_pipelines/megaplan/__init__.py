"""Megaplan planning pipeline — Arnold plugin.

This package is the canonical home for the Megaplan planning pipeline
implementation.  Registry discovery scans ``arnold/pipelines`` before
``megaplan/pipelines``, so this plugin wins deduplication.

Modules:

* ``workflows/planning.py`` — canonical authored workflow source.
* ``pipeline.py`` — thin public facade for ``build_pipeline()`` and the
  native-backed ``build_and_compile_pipeline()`` compatibility shell.
* ``routing.py`` — planning decision literals and routing helpers.
* ``handlers/`` — handler bridge modules (M5a/M5b deferred).

Operation dispatch lives at ``arnold_pipelines.megaplan.planning.operations``
(canonical) — the old ``operations.py`` adapter has been removed.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

name: str = "megaplan"
description: str = (
    "Canonical Megaplan planning pipeline: prep, plan, critique, gate, "
    "revise, finalize, execute, review, and tiebreaker."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("code", "doc", "creative", "joke", "plan", "native")
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "megaplan")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("planning", "execution", "review")


def build_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Return the canonical Megaplan planning pipeline."""

    module = import_module("arnold_pipelines.megaplan.pipeline")
    return module.build_pipeline(*args, **kwargs)


def build_and_compile_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Build the DSL pipeline and project it to a native-backed shell."""

    module = import_module("arnold_pipelines.megaplan.pipeline")
    return module.build_and_compile_pipeline(*args, **kwargs)


# Register megaplan-specific content types with the generic Arnold registry.
# These are opinionated types that belong to the Megaplan plugin, not the
# neutral Arnold substrate.
def _register_megaplan_content_types() -> None:
    from arnold.pipeline.types import CONTENT_TYPES

    _MEGAPLAN_CONTENT_TYPES = (
        "application/x-evaluand-record+json",
        "application/x-routing-key+json",
        "application/x-verdict+json",
    )
    for _ct in _MEGAPLAN_CONTENT_TYPES:
        if _ct not in CONTENT_TYPES:
            CONTENT_TYPES.register(_ct, {"content_type": _ct})


_register_megaplan_content_types()


def _install_model_adapter_once() -> None:
    """Import megaplan model_seam first (registers hooks) then wire the adapter."""
    import arnold_pipelines.megaplan.model_seam as _ms  # noqa: F401 — side-effect: registers hooks
    from arnold.execution.step_invocation import get_default_adapter_registry
    from arnold_pipelines.megaplan.model_seam import (
        ModelStepInvocationAdapter,
        install_model_step_adapter,
    )

    registry = get_default_adapter_registry()
    try:
        install_model_step_adapter(registry)
    except ValueError:
        if isinstance(registry.resolve("model"), ModelStepInvocationAdapter):
            return
        raise


_model_adapter_installed: bool = False

if not _model_adapter_installed:
    _install_model_adapter_once()
    _model_adapter_installed = True


__all__ = [
    "build_and_compile_pipeline",
    "build_pipeline",
]
