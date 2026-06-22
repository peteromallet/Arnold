"""Doc-pipeline prompt bundle wiring.

Owns the five canonical doc-pipeline stage prompts in a bundle-scoped
mapping. The
public Step shells in ``megaplan.pipelines.doc.steps`` carry these as
their ``prompt_key`` values:

    outline       → outline_doc
    section_drafts → execute_doc
    critique      → critique_doc
    revise        → revise_doc
    assembly      → assemble_doc

``prep_doc`` and ``review_doc`` are not bundled here because they are
not stages in the first-class ``doc`` pipeline. The ``doc`` pipeline
reaches users via ``megaplan run doc`` and uses the five keys above.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Mapping, cast

from arnold.pipeline.resources import PipelineResourceBundle, resolve_bundle_prompt
from arnold_pipelines.megaplan.step_types import StepContext
from arnold_pipelines.megaplan.types import PlanState

from .assemble_doc import _assemble_doc_prompt
from .critique_doc import _critique_doc_prompt
from .execute_doc import _execute_doc_prompt
from .outline_doc import _outline_doc_prompt
from .revise_doc import _revise_doc_prompt


def _adapt(builder):
    """Bridge ``(PlanState, plan_dir)`` builders to ``PromptRenderer``."""

    def renderer(ctx: StepContext, params: Mapping[str, Any]) -> str:
        del params
        state = cast(PlanState, dict(ctx.state) if ctx.state else {})
        plan_root = getattr(ctx, "plan_dir", None) or getattr(ctx, "artifact_root")
        return builder(state, Path(plan_root))

    renderer.__name__ = getattr(builder, "__name__", "renderer")
    return renderer


DOC_PROMPT_BUNDLE = PipelineResourceBundle.from_module(
    __file__,
    prompts={
        "doc/outline_doc": _adapt(_outline_doc_prompt),
        "doc/execute_doc": _adapt(_execute_doc_prompt),
        "doc/critique_doc": _adapt(_critique_doc_prompt),
        "doc/revise_doc": _adapt(_revise_doc_prompt),
        "doc/assemble_doc": _adapt(_assemble_doc_prompt),
    },
)


def render_prompt(
    key: str,
    ctx: StepContext,
    params: Mapping[str, Any] | None = None,
) -> str:
    """Render a doc-pipeline prompt from the canonical bundle."""
    inputs = dict(ctx.inputs) if isinstance(ctx.inputs, Mapping) else {}
    inputs.setdefault("_pipeline", "doc")
    scoped_ctx = dataclasses.replace(ctx, inputs=inputs)
    return resolve_bundle_prompt(DOC_PROMPT_BUNDLE, key, scoped_ctx, params=params)


__all__ = [
    "DOC_PROMPT_BUNDLE",
    "_adapt",
    "_assemble_doc_prompt",
    "_critique_doc_prompt",
    "_execute_doc_prompt",
    "_outline_doc_prompt",
    "_revise_doc_prompt",
    "render_prompt",
]
