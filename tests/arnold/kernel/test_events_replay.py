from __future__ import annotations

from arnold.kernel import (
    EventEnvelope,
    EventFamily,
    ManifestReference,
    QuarantineRecord,
    ReplayDecision,
    ReplayReference,
    ReplayResolution,
)


def test_event_envelope_carries_manifest_lineage_and_replay_refs() -> None:
    event = EventEnvelope(
        event_id="event-1",
        family=EventFamily.NODE_LIFECYCLE,
        kind="node-started",
        manifest=ManifestReference("planning", "sha256:" + "a" * 64, uri="manifest.json"),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        payload={"node": "plan"},
        idempotency_key="sha256:" + "c" * 64,
        occurred_at="2026-06-22T00:00:00Z",
        replay=ReplayReference(journal_uri="events.ndjson", sequence=1),
    )

    assert event.manifest.manifest_hash == "sha256:" + "a" * 64
    assert event.replay is not None
    assert event.replay.sequence == 1


def test_replay_resolution_and_quarantine_are_explicit() -> None:
    resolution = ReplayResolution(ReplayDecision.QUARANTINE, reason="manifest mismatch")
    record = QuarantineRecord(
        run_id="run-1",
        original_manifest_hash="sha256:" + "a" * 64,
        observed_manifest_hash="sha256:" + "b" * 64,
        reason=resolution.reason,
    )

    assert resolution.decision is ReplayDecision.QUARANTINE
    assert record.reason == "manifest mismatch"
