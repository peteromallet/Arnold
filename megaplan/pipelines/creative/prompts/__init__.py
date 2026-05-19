"""Creative-pipeline prompt registry wiring (T8).

Registers the canonical creative-pipeline stage prompts under the
``creative`` pipeline namespace via :func:`register_pipeline_prompt`,
with form-specialised slots for the joke form so
``megaplan run creative --form joke`` resolves joke-specific prompts.

Pipeline-scoped registrations:

    creative/prep                              → generic creative prep
    creative/execute_creative                  → generic creative execute
    creative/critique_creative                 → generic creative critique
    creative/revise_creative                   → generic creative revise

    creative/prep:joke                         → joke-form prep
    creative/execute_creative:joke             → joke-form execute
    creative/critique_creative:joke            → joke-form critique
    creative/revise_creative:joke              → joke-form revise

The ``:joke`` slot uses the ``mode`` parameter of
:func:`register_pipeline_prompt` per the
``<pipeline>/<key>:<mode>`` precedence in :class:`PromptRegistry`. The
creative pipeline's stage shells (``megaplan.pipelines.creative``)
carry ``prompt_key`` values like ``execute_creative:joke`` already
form-baked — those resolve at the pipeline-scoped slot here via the
plain pipeline-only precedence (rule 2 in :meth:`PromptRegistry.resolve`).
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

register_pipeline_prompt("creative", "prep", _adapt(_prep_joke_prompt))
register_pipeline_prompt("creative", "execute_creative", _adapt(_execute_creative_prompt))
register_pipeline_prompt("creative", "critique_creative", _adapt(_critique_creative_prompt))
register_pipeline_prompt("creative", "revise_creative", _adapt(_revise_creative_prompt))


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
    "creative", "execute_creative", _adapt(_execute_joke_prompt), mode="joke"
)
register_pipeline_prompt(
    "creative", "critique_creative", _adapt(_critique_joke_prompt), mode="joke"
)
register_pipeline_prompt(
    "creative", "revise_creative", _adapt(_revise_joke_prompt), mode="joke"
)

# Literal form-baked keys (match the stage's prompt_key directly).
register_pipeline_prompt("creative", "prep:joke", _adapt(_prep_joke_prompt))
register_pipeline_prompt("creative", "execute_creative:joke", _adapt(_execute_joke_prompt))
register_pipeline_prompt(
    "creative", "critique_creative:joke", _adapt(_critique_joke_prompt)
)
register_pipeline_prompt(
    "creative", "revise_creative:joke", _adapt(_revise_joke_prompt)
)


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
    "single_check_critique_joke_prompt",
]
