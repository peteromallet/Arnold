"""Current terminal recovery verification coverage.

The former shell ``TERMINAL_AUDIT_MODE`` path was retired: it retriggered an
already-terminal repair and could not prove a recovery delta.  Terminal
acceptance now belongs to the separated recovery verifier, which rereads
current authority and joins exact request-bound occurrence evidence.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.cloud.recovery_events import (
    RecoveryEvent,
    RecoveryEventKind,
    RecoveryEventStore,
)
from arnold_pipelines.megaplan.cloud.recovery_verifier import (
    OccurrenceOrder,
    RecoveryVerifier,
    RereadSnapshot,
    VerificationTarget,
    VerificationVerdict,
)


def _snapshot(_request_id: str) -> RereadSnapshot:
    return RereadSnapshot(
        ra_grant_id="grant-1",
        ra_fence_token=7,
        ra_decision="SATISFIED",
        custody_lease_id="lease-1",
        custody_epoch=3,
        custody_owner="repair-owner",
    )


def _target(**overrides: object) -> VerificationTarget:
    values = {
        "repair_request_id": "request-1",
        "expected_occurrence_key": "occurrence-1",
        "expected_grant_id": "grant-1",
        "expected_fence_token": 7,
        "expected_epoch": 3,
        "expected_lease_id": "lease-1",
        "expected_basename": "m10-recovery",
    }
    values.update(overrides)
    return VerificationTarget(**values)


def _complete_store() -> RecoveryEventStore:
    store = RecoveryEventStore()
    rows = (
        (RecoveryEventKind.BLOCKER_DETECTED, "2026-07-28T00:00:00+00:00", "", ""),
        (RecoveryEventKind.REPAIR_REQUEST_ENQUEUED, "2026-07-28T00:00:01+00:00", "", ""),
        (
            RecoveryEventKind.REPAIR_CLAIMED,
            "2026-07-28T00:00:02+00:00",
            "2026-07-28T00:00:02+00:00",
            "",
        ),
        (
            RecoveryEventKind.REPAIR_TERMINAL,
            "2026-07-28T00:00:03+00:00",
            "",
            "2026-07-28T00:00:03+00:00",
        ),
    )
    for index, (kind, recorded_at, claim_time, terminal_time) in enumerate(rows):
        store.record(
            RecoveryEvent(
                event_id=f"event-{index}",
                kind=kind,
                occurred_at="2026-07-28T00:00:00+00:00",
                recorded_at=recorded_at,
                request_id="request-1",
                claim_time=claim_time,
                terminal_time=terminal_time,
            )
        )
    return store


def test_current_recovery_verifier_accepts_exact_independent_proof() -> None:
    result = RecoveryVerifier(
        event_store=_complete_store(),
        ra_reread_fn=_snapshot,
    ).verify(_target())

    assert result.verdict == VerificationVerdict.VERIFIED
    assert result.ordering == OccurrenceOrder.IN_ORDER
    assert len(result.events_joined) == 4


def test_current_recovery_verifier_rejects_stale_identity() -> None:
    result = RecoveryVerifier(
        event_store=_complete_store(),
        ra_reread_fn=lambda _request_id: RereadSnapshot(
            ra_grant_id="stale-grant",
            ra_fence_token=7,
            ra_decision="SATISFIED",
            custody_epoch=3,
        ),
    ).verify(_target())

    assert result.verdict == VerificationVerdict.REJECTED_STALE_IDENTITY
    assert result.is_blocked


def test_current_recovery_verifier_rejects_missing_occurrences() -> None:
    result = RecoveryVerifier(
        event_store=RecoveryEventStore(),
        ra_reread_fn=_snapshot,
    ).verify(_target())

    assert result.verdict == VerificationVerdict.REJECTED_LOST
    assert result.ordering == OccurrenceOrder.LOST
