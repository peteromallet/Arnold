"""Joke-mode execute prompt compatibility shims."""

from __future__ import annotations

from functools import partial

from arnold.pipelines.megaplan.forms import get_form

from .execute_creative import _execute_creative_batch_prompt, _execute_creative_prompt

_execute_joke_prompt = partial(_execute_creative_prompt, form=get_form("joke"))
_execute_joke_batch_prompt = partial(_execute_creative_batch_prompt, form=get_form("joke"))

__all__ = ["_execute_joke_prompt", "_execute_joke_batch_prompt"]
