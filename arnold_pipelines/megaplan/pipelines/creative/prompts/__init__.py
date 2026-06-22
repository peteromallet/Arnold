"""Creative-pipeline prompt bundle wiring.

Owns the canonical creative-pipeline stage prompts in a bundle-scoped mapping,
with generic slots for non-joke forms and joke-specific slots so
``megaplan run creative --form joke`` resolves joke-specific prompts.

Pipeline-scoped registrations:

    creative/prep                              → generic fresh creative prep
    creative/execute_creative                  → generic fresh creative execute
    creative/critique_creative                 → generic fresh creative critique
    creative/revise_creative                   → generic fresh creative revise
    creative/prep:joke                         → joke-form prep
    creative/execute_creative:joke             → joke-form execute
    creative/critique_creative:joke            → joke-form critique
    creative/revise_creative:joke              → joke-form revise

The ``:joke`` slot uses the bundle's
``<pipeline>/<key>:<mode>`` precedence. The
creative pipeline's stage shells (``megaplan.pipelines.creative``)
carry generic prompt keys for non-joke forms and ``:joke`` prompt keys
for the default joke form. Non-joke forms pass form metadata through
state/params while resolving the generic slots.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Mapping, cast

from arnold.pipeline.resources import PipelineResourceBundle, resolve_bundle_prompt
from arnold_pipelines.megaplan._pipeline.types import StepContext
from arnold_pipelines.megaplan.forms import get_form
from arnold_pipelines.megaplan.types import PlanState

from .critique_creative import _critique_creative_prompt
from .critique_joke import _critique_joke_prompt, single_check_critique_joke_prompt
from .execute_creative import _execute_creative_batch_prompt, _execute_creative_prompt
from .execute_joke import _execute_joke_batch_prompt, _execute_joke_prompt
from .generic import (
    creative_critique_prompt,
    creative_execute_prompt,
    creative_joke_critique_prompt,
    creative_joke_execute_prompt,
    creative_joke_revise_prompt,
    creative_prep_prompt,
    creative_revise_prompt,
)
from .prep_joke import _prep_joke_prompt
from .revise_creative import _revise_creative_prompt
from .revise_joke import _revise_joke_prompt


def _adapt(builder):
    """Bridge ``(PlanState, plan_dir, ...)`` builders to ``PromptRenderer``."""

    def renderer(ctx: StepContext, params: Mapping[str, Any]) -> str:
        del params
        state = cast(PlanState, dict(ctx.state) if ctx.state else {})
        plan_root = getattr(ctx, "plan_dir", None) or getattr(ctx, "artifact_root")
        return builder(state, Path(plan_root))

    renderer.__name__ = getattr(builder, "__name__", "renderer")
    return renderer


# ── Bundle-owned creative-form prompt mappings ───────────────────────

_GENERIC_RENDERERS: dict[str, Any] = {
    "prep": creative_prep_prompt,
    "execute_creative": creative_execute_prompt,
    "critique_creative": creative_critique_prompt,
    "revise_creative": creative_revise_prompt,
}

_BUNDLE_PROMPTS: dict[str, Any] = {
    f"creative/{key}": renderer for key, renderer in _GENERIC_RENDERERS.items()
}


# ── Joke-form specialised slots (``:joke``) ───────────────────────────
#
# These land at ``creative/<key>:joke`` so
# the creative pipeline's stage ``prompt_key`` values
# (``prep:joke`` / ``execute_creative:joke`` / etc.) resolve correctly.
_BUNDLE_PROMPTS.update(
    {
        "creative/prep:joke": _adapt(_prep_joke_prompt),
        "creative/execute_creative:joke": creative_joke_execute_prompt,
        "creative/critique_creative:joke": creative_joke_critique_prompt,
        "creative/revise_creative:joke": creative_joke_revise_prompt,
    }
)

CREATIVE_PROMPT_BUNDLE = PipelineResourceBundle.from_module(
    __file__,
    prompts=_BUNDLE_PROMPTS,
)


def render_prompt(
    key: str,
    ctx: StepContext,
    params: Mapping[str, Any] | None = None,
) -> str:
    """Render a creative-pipeline prompt from the canonical bundle."""
    inputs = dict(ctx.inputs) if isinstance(ctx.inputs, Mapping) else {}
    inputs.setdefault("_pipeline", "creative")
    scoped_ctx = dataclasses.replace(ctx, inputs=inputs)
    return resolve_bundle_prompt(CREATIVE_PROMPT_BUNDLE, key, scoped_ctx, params=params)


__all__ = [
    "CREATIVE_PROMPT_BUNDLE",
    "_adapt",
    "_critique_creative_prompt",
    "_critique_joke_prompt",
    "_execute_creative_batch_prompt",
    "_execute_creative_prompt",
    "_execute_joke_batch_prompt",
    "_execute_joke_prompt",
    "_prep_joke_prompt",
    "_revise_creative_prompt",
    "_revise_joke_prompt",
    "creative_critique_prompt",
    "creative_execute_prompt",
    "creative_joke_critique_prompt",
    "creative_joke_execute_prompt",
    "creative_joke_revise_prompt",
    "creative_prep_prompt",
    "creative_revise_prompt",
    "render_prompt",
    "single_check_critique_joke_prompt",
]
