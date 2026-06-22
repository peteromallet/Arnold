"""Joke-mode critique prompt compatibility shims."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.forms import get_form
from arnold_pipelines.megaplan.types import PlanState

from .critique_creative import _critique_creative_prompt
from arnold_pipelines.megaplan.prompts.critique import _build_critique_prompt, _critique_context

_critique_joke_prompt = partial(_critique_creative_prompt, form=get_form("joke"))


def single_check_critique_joke_prompt(
    state: PlanState,
    plan_dir: Path,
    root: Path | None,
    check: dict[str, Any],
    template_path: Path,
) -> str:
    context = _critique_context(state, plan_dir, root)
    critique_review_block = (
        f"Your output template is at: {template_path}\n"
        f"Investigate only this creative provocation and write one committed `FLAG-{check['id']}` proposal.\n\n"
        f"Question: {check.get('question', '')}\n"
        f"Guidance: {check.get('guidance', '')}"
    )
    return _build_critique_prompt(state, context, critique_review_block)


__all__ = ["_critique_joke_prompt", "single_check_critique_joke_prompt"]
