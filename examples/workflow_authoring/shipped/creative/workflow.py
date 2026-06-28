"""Authoring-only scaffold for the shipped creative pipeline."""

from __future__ import annotations

from arnold.workflow.authoring import workflow

from .components import (
    critique_creative,
    execute_creative,
    finalize,
    prep,
    revise_creative,
)


@workflow(id="shipped-creative", version="1.0")
def creative(brief: str) -> None:
    prepared = prep(id="prep", brief=brief)
    draft = execute_creative(id="execute_creative", brief=prepared)
    critique = critique_creative(id="critique_creative", draft=draft)
    revised = revise_creative(id="revise_creative", draft=draft, critique=critique)
    finalize(id="finalize", artifact=revised)
