"""Authoring-only scaffold for the shipped jokes pipeline."""

from __future__ import annotations

from arnold.workflow.authoring import workflow

from .components import draft, emit, tighten


@workflow(id="shipped-jokes", version="1.0")
def jokes(prompt: str) -> None:
    draft_text = draft(id="draft", prompt=prompt)
    tightened = tighten(id="tighten", draft=draft_text)
    emit(id="emit", joke=tightened)
