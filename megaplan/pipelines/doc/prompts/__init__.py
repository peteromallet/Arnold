"""Doc-pipeline prompt registry wiring.

Registers the five canonical doc-pipeline stage prompts under the
``doc`` pipeline namespace via :func:`register_pipeline_prompt`. The
public Step shells in ``megaplan.pipelines.doc.steps`` carry these as
their ``prompt_key`` values:

    outline       → outline_doc
    section_drafts → execute_doc
    critique      → critique_doc
    revise        → revise_doc
    assembly      → assemble_doc

``prep_doc`` and ``review_doc`` are not registered here because they are
not stages in the first-class ``doc`` pipeline. The ``doc`` pipeline
reaches users via ``megaplan run doc`` and uses the five keys above.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast

from megaplan._pipeline.prompts import register_pipeline_prompt
from megaplan._pipeline.types import StepContext
from megaplan.types import PlanState

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
        return builder(state, Path(ctx.plan_dir))

    renderer.__name__ = getattr(builder, "__name__", "renderer")
    return renderer


# ── Pipeline-scoped registration ─────────────────────────────────────

register_pipeline_prompt("doc", "outline_doc", _adapt(_outline_doc_prompt))
register_pipeline_prompt("doc", "execute_doc", _adapt(_execute_doc_prompt))
register_pipeline_prompt("doc", "critique_doc", _adapt(_critique_doc_prompt))
register_pipeline_prompt("doc", "revise_doc", _adapt(_revise_doc_prompt))
register_pipeline_prompt("doc", "assemble_doc", _adapt(_assemble_doc_prompt))


__all__ = [
    "_adapt",
    "_assemble_doc_prompt",
    "_critique_doc_prompt",
    "_execute_doc_prompt",
    "_outline_doc_prompt",
    "_revise_doc_prompt",
]
