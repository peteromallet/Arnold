"""Authoring-only scaffold for the shipped live-supervisor pipeline."""

from __future__ import annotations

from arnold.workflow.authoring import workflow

from .components import classify, diagnose, recheck_emit, repair_decision


@workflow(id="shipped-live-supervisor", version="1.0")
def live_supervisor(event: str) -> None:
    classification = classify(id="classify", event=event)
    diagnosis = diagnose(id="diagnose", classification=classification)
    decision = repair_decision(id="repair_decision", diagnosis=diagnosis)
    recheck_emit(id="recheck_emit", decision=decision)
