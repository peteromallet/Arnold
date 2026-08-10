from __future__ import annotations

from arnold.kernel import (
    derive_pipeline_identity,
    EventEnvelope,
    EventFamily,
    ManifestReference,
    QuarantineRecord,
    ReplayDecision,
    ReplayReference,
    ReplayResolution,
)
from arnold.kernel.events import canonical_event_json


def test_manifest_reference_pipeline_identity_is_computed_not_serialized() -> None:
    manifest_hash = "sha256:" + "a" * 64
    reference = ManifestReference("planning", manifest_hash, uri="manifest.json")
    event = EventEnvelope(
        event_id="event-1",
        family=EventFamily.NODE_LIFECYCLE,
        kind="node-started",
        manifest=reference,
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
    )

    assert reference.pipeline_identity == derive_pipeline_identity("planning", manifest_hash)
    serialized = canonical_event_json(event)
    assert '"manifest":{"alias":"planning","manifest_hash":"' in serialized
    assert "pipeline_identity" not in serialized


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
