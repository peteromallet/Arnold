"""Megaplan completion adapter — bridges megaplan artifacts to the completion kernel.

This package provides the adapter layer that translates megaplan-specific
artifact types (plans, milestones, phases, steps) into completion-kernel
:class:`~arnold.workflow.completion.spec.SubjectKind` values and generates
shadow specs and bindings for them.

.. caution::
   This package is **experimental and non-authoritative**.  Shadow verdicts
   have **zero authority** and **cannot satisfy completion**.  See S2R GO-0
   for the future live-enablement gate.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.completion.adapter import (
    CompletionSubject,
    S2FShadowRunner,
    SubjectInventory,
    megaplan_subject_inventory,
    shadow_runner,
)

__all__ = [
    "CompletionSubject",
    "S2FShadowRunner",
    "SubjectInventory",
    "megaplan_subject_inventory",
    "shadow_runner",
]