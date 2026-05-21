from __future__ import annotations

import pytest

from megaplan.quality_resolutions import (
    ACCEPTED_WITH_DEBT,
    ADVANCE_WITH_DEBT,
    FIXED,
    HARD_BLOCK,
    MANUAL_REQUIRED,
    REJECTED,
    RERUN_REQUIRED,
    RESOLVED,
    build_quality_resolution_event,
    classify_quality_resolution_behavior,
    is_non_terminal_quality_resolution,
    latest_quality_resolutions,
)
from megaplan.types import CliError


def test_build_quality_resolution_event_requires_debt_context() -> None:
    with pytest.raises(CliError, match="requires phase"):
        build_quality_resolution_event(
            blocker_id="quality:T1:evidence",
            resolution=ACCEPTED_WITH_DEBT,
            evidence=["reviewed"],
            debt_note="accepted temporarily",
            timestamp="2026-05-20T10:00:00Z",
        )

    with pytest.raises(CliError, match="requires evidence"):
        build_quality_resolution_event(
            blocker_id="quality:T1:evidence",
            resolution=ACCEPTED_WITH_DEBT,
            phase="execute",
            debt_note="accepted temporarily",
            timestamp="2026-05-20T10:00:00Z",
        )

    with pytest.raises(CliError, match="requires debt_note"):
        build_quality_resolution_event(
            blocker_id="quality:T1:evidence",
            resolution=ACCEPTED_WITH_DEBT,
            phase="execute",
            evidence=["reviewed"],
            timestamp="2026-05-20T10:00:00Z",
        )


def test_build_quality_resolution_event_stores_timestamp_aliases() -> None:
    event = build_quality_resolution_event(
        blocker_id="quality:T1:evidence",
        resolution=ACCEPTED_WITH_DEBT,
        phase="execute",
        evidence=["reviewed audit finding"],
        debt_note="accepted temporarily",
        fallback_mode="degraded-validation",
        created_by="tester",
        timestamp="2026-05-20T10:00:00Z",
    )

    assert event["timestamp"] == "2026-05-20T10:00:00Z"
    assert event["created_at"] == "2026-05-20T10:00:00Z"
    assert event["created_by"] == "tester"
    assert event["phase"] == "execute"
    assert event["evidence"] == ["reviewed audit finding"]
    assert event["debt_note"] == "accepted temporarily"
    assert event["fallback_mode"] == "degraded-validation"


def test_latest_quality_resolutions_uses_timestamp_or_created_at() -> None:
    latest = latest_quality_resolutions(
        [
            {
                "blocker_id": "quality:T1:evidence",
                "created_at": "2026-05-20T10:00:00Z",
                "resolution": REJECTED,
            },
            {
                "blocker_id": "quality:T1:evidence",
                "timestamp": "2026-05-20T11:00:00Z",
                "resolution": ACCEPTED_WITH_DEBT,
            },
        ]
    )

    assert latest["quality:T1:evidence"]["resolution"] == ACCEPTED_WITH_DEBT


def test_quality_resolution_behavior_keeps_active_fixed_non_advancing() -> None:
    assert classify_quality_resolution_behavior(ACCEPTED_WITH_DEBT) == ADVANCE_WITH_DEBT
    assert classify_quality_resolution_behavior(FIXED) == RERUN_REQUIRED
    assert (
        classify_quality_resolution_behavior(FIXED, deviation_active=False) == RESOLVED
    )
    assert classify_quality_resolution_behavior(MANUAL_REQUIRED) == HARD_BLOCK
    assert classify_quality_resolution_behavior(REJECTED) == HARD_BLOCK
    assert is_non_terminal_quality_resolution(ACCEPTED_WITH_DEBT)
    assert not is_non_terminal_quality_resolution(FIXED)
    assert is_non_terminal_quality_resolution(FIXED, deviation_active=False)
