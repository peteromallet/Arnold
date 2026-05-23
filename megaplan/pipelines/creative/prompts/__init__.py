"""Creative-pipeline prompt registry wiring.

Registers the canonical creative-pipeline stage prompts under the
``creative`` pipeline namespace via :func:`register_pipeline_prompt`,
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

The ``:joke`` slot uses the ``mode`` parameter of
:func:`register_pipeline_prompt` per the
``<pipeline>/<key>:<mode>`` precedence in :class:`PromptRegistry`. The
creative pipeline's stage shells (``megaplan.pipelines.creative``)
carry generic prompt keys for non-joke forms and ``:joke`` prompt keys
for the default joke form. Non-joke forms pass form metadata through
state/params while resolving the generic slots.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast

from megaplan._pipeline.prompts import register_pipeline_prompt
from megaplan._pipeline.types import StepContext
from megaplan.forms import get_form
from megaplan.types import PlanState

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
        return builder(state, Path(ctx.plan_dir))

    renderer.__name__ = getattr(builder, "__name__", "renderer")
    return renderer


# ── Generic creative-form registrations ──────────────────────────────

_GENERIC_RENDERERS = {
    "prep": creative_prep_prompt,
    "execute_creative": creative_execute_prompt,
    "critique_creative": creative_critique_prompt,
    "revise_creative": creative_revise_prompt,
}

for _key, _renderer in _GENERIC_RENDERERS.items():
    register_pipeline_prompt("creative", _key, _renderer)


# ── Joke-form specialised slots (``:joke``) ───────────────────────────
#
# The ``mode='joke'`` kwarg lands these at ``creative/<key>:joke`` so
# the creative pipeline's stage ``prompt_key`` values
# (``prep:joke`` / ``execute_creative:joke`` / etc.) resolve correctly.
# Belt-and-braces: also register the literal form-baked keys so a
# resolve against the raw stage prompt_key (no separate mode/pipeline
# kwargs) still hits a renderer.

register_pipeline_prompt("creative", "prep", _adapt(_prep_joke_prompt), mode="joke")
register_pipeline_prompt(
    "creative", "execute_creative", creative_joke_execute_prompt, mode="joke"
)
register_pipeline_prompt(
    "creative", "critique_creative", creative_joke_critique_prompt, mode="joke"
)
register_pipeline_prompt(
    "creative", "revise_creative", creative_joke_revise_prompt, mode="joke"
)

# Literal form-baked keys (match the stage's prompt_key directly).
register_pipeline_prompt("creative", "prep:joke", _adapt(_prep_joke_prompt))
register_pipeline_prompt(
    "creative", "execute_creative:joke", creative_joke_execute_prompt
)
register_pipeline_prompt(
    "creative", "critique_creative:joke", creative_joke_critique_prompt
)
register_pipeline_prompt("creative", "revise_creative:joke", creative_joke_revise_prompt)


__all__ = [
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
    "single_check_critique_joke_prompt",
]
