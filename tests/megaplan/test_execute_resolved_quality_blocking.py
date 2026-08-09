from __future__ import annotations

import json

import pytest

from arnold_pipelines.megaplan.execute.batch import _drop_resolved_quality_blocking_reasons
from arnold_pipelines.megaplan.quality_resolutions import build_quality_resolution_event


def _state_with_resolutions(events: list[dict]) -> dict:
    return {"meta": {"quality_gate_resolutions": events}}


def _debt_resolution(blocker_id: str) -> dict:
    return build_quality_resolution_event(
        blocker_id=blocker_id,
        resolution="accepted_with_debt",
        phase="execute",
        evidence=["test evidence"],
        debt_note="test debt",
    )


def test_unresolved_quality_reason_is_kept() -> None:
    state = _state_with_resolutions([])
    reasons = ["1/17 sense checks have no executor acknowledgment"]
    assert _drop_resolved_quality_blocking_reasons(reasons, state=state) == reasons


def test_resolved_quality_reason_is_dropped() -> None:
    blocker_id = "quality:global:f733f76b3240"
    state = _state_with_resolutions([_debt_resolution(blocker_id)])
    reasons = ["1/17 sense checks have no executor acknowledgment"]
    assert _drop_resolved_quality_blocking_reasons(reasons, state=state) == []


def test_non_quality_reasons_are_always_kept() -> None:
    state = _state_with_resolutions([_debt_resolution("quality:global:f733f76b3240")])
    reasons = [
        "1/17 sense checks have no executor acknowledgment",
        "task(s) reported status=blocked by the worker: T2",
        "unrelated scope drift",
    ]
    dropped = _drop_resolved_quality_blocking_reasons(reasons, state=state)
    assert "1/17 sense checks have no executor acknowledgment" not in dropped
    assert "task(s) reported status=blocked by the worker: T2" in dropped
    assert "unrelated scope drift" in dropped


def test_missing_state_or_resolutions_is_noop() -> None:
    reasons = ["1/17 sense checks have no executor acknowledgment"]
    assert _drop_resolved_quality_blocking_reasons(reasons, state=None) == reasons
    assert _drop_resolved_quality_blocking_reasons(reasons, state={}) == reasons
