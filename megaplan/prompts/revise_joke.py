"""Joke-mode revise prompt compatibility shim."""

from __future__ import annotations

from functools import partial

from megaplan.forms import get_form

from .revise_creative import _revise_creative_prompt

_revise_joke_prompt = partial(_revise_creative_prompt, form=get_form("joke"))

__all__ = ["_revise_joke_prompt"]
