"""Curated r5 evidence-preservation import fixture (T11).

Loads ``tests/fixtures/critique_ledger/r5_sample_events.ndjson`` (50 records
covering both epoch prefixes, both legacy key formats, missing evidence,
admissible and inadmissible ``target_schema`` markers) and asserts:

* complete import with a correct :class:`ImportReport`;
* stable epoch-prefixed canonical event IDs;
* both legacy key formats normalize (10-field RepairOccurrenceKey, 6-field
  CustodyTargetKey);
* every record routes through ``IndependentChildDisposition`` (never migrated);
* nested provenance (producer/model/round/semantic finding/evidence) survives;
* exact ``UNAVAILABLE`` / ``legacy_import`` labelling for missing evidence;
* no-op re-import within an epoch (idempotency);
* full legacy-context queries via ``ProjectionBuilder.read_legacy_context``;
* replay exclusion — legacy records never enter the v1 replay partition.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from arnold.critique_ledger.legacy_import import (
    CL2_KIND_LEGACY_HISTORICAL,
    LEGACY_UNAVAILABLE_REASON,
    OneTimeImporter,
)
from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerPersistenceService,
)
from arnold.critique_ledger.projections import (
    EXCLUSION_REASON_LEGACY_DERIVED,
    ProjectionBuilder,
)
from arnold.critique_ledger.schemas import (
    Authority,
    CritiqueOccurrenceEnvelope,
    DispositionFamily,
    EvidenceAvailability,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    ParseStatus,
    Relationship,
)
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptProvenance,
    GrantRef,
    RuntimeAdapter,
    VersionSet,
)

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "critique_ledger"
    / "r5_sample_events.ndjson"
)

#: Records in the fixture file (50), of which 4 carry an inadmissible
#: ``target_schema`` (cl.schema.v99-future-*) and are rejected without publish.
FIXTURE_TOTAL = 50
REJECTED_TARGET_SCHEMA = 4
EXPECTED_IMPORTED = FIXTURE_TOTAL - REJECTED_TARGET_SCHEMA  # 46

#: Missing-evidence counts: 12 of 24 ten-field (odd idx) + 7 of 20 six-field
#: (idx % 3 == 0).  The 2 admissible-target and 4 rejected records all carry
#: evidence, so they contribute 0.
EXPECTED_UNAVAILABLE = 12 + 7  # 19


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-t11-fixture"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-06T00:00:00+00:00",
        observed_at="2026-08-06T00:00:01+00:00",
    )


def _legacy_events(
    store: SqliteAttemptLedgerStore, attempt_id: str
) -> list[Any]:
    return [
        e
        for e in store.read_events(attempt_id)
        if e.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
        and isinstance(e.payload, dict)
        and e.payload.get("cl2_kind") == CL2_KIND_LEGACY_HISTORICAL
    ]


@pytest.fixture
def seeded(tmp_path: Path) -> tuple[
    SqliteAttemptLedgerStore,
    str,
    LedgerEventContext,
    LedgerPersistenceService,
    ProjectionBuilder,
]:
    store = SqliteAttemptLedgerStore(tmp_path / "r5-fixture.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)
    service.start_attempt(attempt_id, context=context, idempotency_key="start")
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    return store, attempt_id, context, service, ProjectionBuilder(store)


# ── complete import + report shape ──────────────────────────────────────────


def test_complete_import_report(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    report = OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.total_records == FIXTURE_TOTAL
    assert report.imported == EXPECTED_IMPORTED
    assert report.skipped_duplicates == 0
    assert report.legacy_unavailable_count == EXPECTED_UNAVAILABLE
    assert report.derived_from_legacy_count == EXPECTED_IMPORTED
    assert report.epoch_prefixes == (1,)
    assert len(report.errors) == REJECTED_TARGET_SCHEMA
    for err in report.errors:
        assert "cl.schema.v99-future" in err
        assert "without publication" in err
    # The ledger holds START + INTENT + EXPECTED_IMPORTED legacy outcomes.
    assert store.event_count(attempt_id) == 2 + EXPECTED_IMPORTED


# ── stable epoch-prefixed IDs ───────────────────────────────────────────────


def test_stable_epoch_prefixed_ids(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    ids = [e.payload["envelope"]["occurrence_id"] for e in _legacy_events(store, attempt_id)]
    assert len(ids) == EXPECTED_IMPORTED
    # Every ID is epoch-prefixed.
    assert all(i.startswith("legacy-1-") for i in ids)
    # IDs are unique and stable (canonical digest of the source line).
    assert len(set(ids)) == EXPECTED_IMPORTED


def test_distinct_ids_across_two_epochs(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    importer = OneTimeImporter(store)
    importer.import_ndjson(FIXTURE, epoch=1, attempt_id=attempt_id, context=context)
    importer.import_ndjson(FIXTURE, epoch=2, attempt_id=attempt_id, context=context)

    events = _legacy_events(store, attempt_id)
    assert len(events) == 2 * EXPECTED_IMPORTED
    ids = [e.payload["envelope"]["occurrence_id"] for e in events]
    # Both epoch prefixes are present and the same source record yields
    # distinct IDs across epochs (not deduped away).
    prefixes = {i.split("-")[1] for i in ids}
    assert prefixes == {"1", "2"}
    assert len(set(ids)) == 2 * EXPECTED_IMPORTED


# ── both legacy key formats normalize ───────────────────────────────────────


def test_ten_field_repair_key_normalizes(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    ten = [
        e for e in _legacy_events(store, attempt_id)
        if "FINDING-10-" in e.payload["envelope"]["finding_id"]
    ]
    assert ten  # 24 imported ten-field records
    for event in ten:
        meta = event.payload["envelope"]["metadata"]
        rk = meta["normalized_repair_occurrence_key"]
        # The 10-field legacy form is preserved in the normalized key.
        assert rk["failure_kind"]
        assert rk["blocker_digest"]
        # CustodyTargetKey is derived from the repair key's target.
        assert meta["normalized_custody_target_key"] is not None


def test_six_field_custody_key_normalizes(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    six = [
        e for e in _legacy_events(store, attempt_id)
        if "FINDING-6-" in e.payload["envelope"]["finding_id"]
    ]
    assert len(six) == 20
    for event in six:
        meta = event.payload["envelope"]["metadata"]
        ck = meta["normalized_custody_target_key"]
        assert ck["target_id"].endswith(".py")
        assert ck["contract_id"]


# ── IndependentChildDisposition routing ─────────────────────────────────────


def test_records_route_through_independent_child_disposition(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    for event in _legacy_events(store, attempt_id):
        disp = event.payload["envelope"]["metadata"]["independent_child_disposition"]
        assert disp["action"] == "start_fresh_independent_child"
        assert disp["requires_human_approval"] is True
        assert event.payload["envelope"]["metadata"]["authority_migration"] == "not_performed"


# ── nested provenance survival ──────────────────────────────────────────────


def test_nested_provenance_survives(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    # Pick a ten-field record that carried evidence.
    ten_with_ev = next(
        e for e in _legacy_events(store, attempt_id)
        if "FINDING-10-000" in e.payload["envelope"]["finding_id"]
    )
    env = ten_with_ev.payload["envelope"]
    assert env["producer_id"] == "critic-r5-0"
    assert env["model_id"] == "model-r5-0"
    assert env["round_label"] == "round-0"
    assert env["semantic_finding_id"] == "sf-10-0"
    assert env["evidence_ref"] == "durable://evidence/r5/ten/0"
    assert env["redacted_prompt_hash"].startswith("sha256:ten-redacted-")
    assert env["raw_completion_hash"].startswith("sha256:ten-completion-")


# ── exact UNAVAILABLE labeling ──────────────────────────────────────────────


def test_exact_unavailable_labeling(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    unavailable = [
        e for e in _legacy_events(store, attempt_id)
        if e.payload["envelope"]["evidence_availability"]
        == EvidenceAvailability.UNAVAILABLE.value
    ]
    assert len(unavailable) == EXPECTED_UNAVAILABLE
    for event in unavailable:
        env = event.payload["envelope"]
        assert env["unavailable_reason"] == LEGACY_UNAVAILABLE_REASON
        # No evidence keys leak onto unavailable records.
        for key in ("evidence_ref", "raw_completion_hash"):
            assert key not in env


def test_present_evidence_retained(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    retained = [
        e for e in _legacy_events(store, attempt_id)
        if e.payload["envelope"]["evidence_availability"]
        == EvidenceAvailability.RETAINED.value
    ]
    expected_retained = EXPECTED_IMPORTED - EXPECTED_UNAVAILABLE
    assert len(retained) == expected_retained
    for event in retained:
        assert "unavailable_reason" not in event.payload["envelope"]


# ── no-op re-import (idempotency) ───────────────────────────────────────────


def test_reimport_is_noop(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    importer = OneTimeImporter(store)
    first = importer.import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    events_after_first = [e.sequence for e in store.read_events(attempt_id)]

    second = importer.import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    assert second.imported == 0
    assert second.skipped_duplicates == EXPECTED_IMPORTED
    # The persisted stream is byte-identical: no new sequences.
    assert [e.sequence for e in store.read_events(attempt_id)] == events_after_first


# ── full legacy-context queries ─────────────────────────────────────────────


def test_full_legacy_context_queryable(seeded: Any) -> None:
    store, attempt_id, context, _, builder = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    legacy = builder.read_legacy_context(attempt_id)
    assert len(legacy) == EXPECTED_IMPORTED
    for event in legacy:
        assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
        assert event.payload["cl2_kind"] == CL2_KIND_LEGACY_HISTORICAL
        assert event.payload["envelope"]["metadata"]["derived_from_legacy"] is True
    # Every imported source finding_id is queryable through legacy context.
    queried = {
        e.payload["envelope"]["finding_id"] for e in legacy
    }
    # 24 ten-field + 20 six-field + 2 admissible-target = 46.
    assert len(queried) == EXPECTED_IMPORTED


# ── replay exclusion ────────────────────────────────────────────────────────


def test_legacy_records_excluded_from_replay(seeded: Any) -> None:
    """Legacy records are queryable but never enter the v1 replay partition."""
    store, attempt_id, context, service, builder = seeded
    # Seed exactly ONE complete v1 replay partition (occurrence +
    # reconciliation + disposition) so the admitted replay partition is
    # non-empty and well-formed (replay_full rejects empty occurrence sets
    # and unmapped parseable occurrences); every legacy record must still be
    # excluded before reconstruction.
    service.persist_occurrence(
        attempt_id,
        CritiqueOccurrenceEnvelope(
            occurrence_id="occ-v1-anchor",
            attempt_id=attempt_id,
            round_label="round-anchor",
            finding_id="F-ANCHOR",
            producer_id="critic-anchor",
            model_id="model-anchor",
            custody_receipt_refs=("wbc-001",),
            parse_status=ParseStatus.SELECTED.value,
            evidence_availability=EvidenceAvailability.RETAINED.value,
        ),
        idempotency_key="occ-anchor",
        context=context,
    )
    service.persist_reconciliation(
        attempt_id,
        FindingReconciliationEvent(
            reconciliation_id="rec-anchor",
            canonical_finding_id="F-ANCHOR",
            semantic_finding_id="sf-anchor",
            occurrence_ids=("occ-v1-anchor",),
            relationship=Relationship.DUPLICATE.value,
            authority=Authority.EVALUATOR.value,
            reason="anchor for replay-exclusion proof",
        ),
        idempotency_key="rec-anchor",
        context=context,
    )
    service.persist_disposition(
        attempt_id,
        FindingDispositionEvent(
            disposition_id="disp-anchor",
            semantic_finding_id="sf-anchor",
            family=DispositionFamily.ACCEPTED_RISK.value,
            authority=Authority.EVALUATOR.value,
        ),
        idempotency_key="disp-anchor",
        context=context,
    )
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    # read_legacy_context returns all 46 legacy records (queryable)...
    assert len(builder.read_legacy_context(attempt_id)) == EXPECTED_IMPORTED
    # ...but replay_full receives ZERO of them: the single v1 occurrence is
    # admitted and every legacy OUTCOME is excluded with reason legacy_derived.
    result = builder.replay(attempt_id, wbc_receipt_chain={"wbc-001": {"valid": True}})
    assert len(result.occurrences) == 1
    assert result.occurrences[0].occurrence_id == "occ-v1-anchor"
    assert len(result.reconciliations) == 1
    assert len(result.dispositions) == 1
    # Every legacy OUTCOME is excluded with reason legacy_derived.
    assert len(result.replay_excluded) == EXPECTED_IMPORTED
    for excl in result.replay_excluded:
        assert excl.cl2_kind == CL2_KIND_LEGACY_HISTORICAL
        assert excl.reason == EXCLUSION_REASON_LEGACY_DERIVED


# ── schema_version preservation (never upgraded) ────────────────────────────


def test_original_schema_versions_preserved(seeded: Any) -> None:
    store, attempt_id, context, _, _ = seeded
    OneTimeImporter(store).import_ndjson(
        FIXTURE, epoch=1, attempt_id=attempt_id, context=context
    )
    versions = {
        e.payload["envelope"]["schema_version"] for e in _legacy_events(store, attempt_id)
    }
    # All three legacy schema versions are preserved; NONE upgraded to v1.
    assert "cl.m6-corpus.v1" in versions
    assert "arnold-resident-delegation-provenance-v1" in versions
    assert "megaplan-critique-custody-v1" in versions
    assert "cl.schema.v1" not in versions
