"""Contract tests for the CL2 ProjectionBuilder replay and authority model.

Covers:
- byte-equivalence (deterministic manifest/briefing hashes across replays)
- legacy-exclusion filter (three conjunctive conditions, exclude-then-reconstruct)
- replay_excluded reason discriminators (legacy_derived / schema_version_mismatch)
- read_legacy_context returns queryable legacy events
- per-contribution authority_scope and the four-valued attempt_authority_summary
- mixed-attempt coverage (v1 + legacy_historical under one attempt_id)
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerEventMapper,
    LedgerPersistenceService,
)
from arnold.critique_ledger.projections import (
    AUTHORITY_SCOPE_AUTHORITATIVE,
    AUTHORITY_SCOPE_NON_AUTHORITATIVE,
    ATTEMPT_AUTHORITY_AUTHORITATIVE,
    ATTEMPT_AUTHORITY_EMPTY,
    ATTEMPT_AUTHORITY_MIXED,
    ATTEMPT_AUTHORITY_NON_AUTHORITATIVE,
    CL2_KIND_LEGACY_HISTORICAL,
    EXCLUSION_REASON_LEGACY_DERIVED,
    EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH,
    ProjectionBuilder,
    ProjectionResult,
)
from arnold.critique_ledger.schemas import (
    Authority,
    DispositionFamily,
    EvidenceAvailability,
    ParseStatus,
    Relationship,
    CritiqueOccurrenceEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
)
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    RuntimeAdapter,
    VersionSet,
)

WBC_CHAIN = {"wbc-001": {"valid": True}}


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-proj-test"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-06T00:00:00+00:00",
        observed_at="2026-08-06T00:00:01+00:00",
    )


def _lifecycle_event(
    context: LedgerEventContext,
    event_type: AttemptEventType,
    sequence: int,
    idempotency_key: str,
) -> LedgerEvent:
    outcome = None
    if event_type == AttemptEventType.COMPLETED:
        outcome = AttemptOutcome.SUCCEEDED
    elif event_type == AttemptEventType.FAILED:
        outcome = AttemptOutcome.FAILED
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=context.identity,
        provenance=context.provenance,
        adapter=context.adapter,
        versions=context.versions,
        grant_ref=context.grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=sequence - 1,
        append_position=sequence - 1,
        occurred_at=context.occurred_at,
        observed_at=context.observed_at,
        outcome=outcome,
    )


def _valid_occurrence(attempt_id: str, occurrence_id: str = "occ-1") -> CritiqueOccurrenceEnvelope:
    return CritiqueOccurrenceEnvelope(
        occurrence_id=occurrence_id,
        attempt_id=attempt_id,
        round_label="round-1",
        finding_id="F01",
        producer_id="critic-1",
        model_id="model-1",
        custody_receipt_refs=("wbc-001",),
        parse_status=ParseStatus.SELECTED.value,
        evidence_availability=EvidenceAvailability.RETAINED.value,
    )


def _valid_reconciliation(occurrence_id: str = "occ-1") -> FindingReconciliationEvent:
    return FindingReconciliationEvent(
        reconciliation_id="rec-1",
        canonical_finding_id="F01",
        semantic_finding_id="sf-1",
        occurrence_ids=(occurrence_id,),
        relationship=Relationship.DUPLICATE.value,
        authority=Authority.EVALUATOR.value,
        reason="evaluator supplied",
    )


def _valid_disposition() -> FindingDispositionEvent:
    return FindingDispositionEvent(
        disposition_id="disp-1",
        semantic_finding_id="sf-1",
        family=DispositionFamily.ACCEPTED_RISK.value,
        authority=Authority.EVALUATOR.value,
        reopen_predicate="revisit when reproducer available",
    )


def _legacy_outcome_event(
    context: LedgerEventContext,
    sequence: int,
    *,
    occurrence_id: str = "legacy-occ",
) -> LedgerEvent:
    """Build a legacy_historical OUTCOME event (bypasses from_dict).

    Mirrors OneTimeImporter: original (non-v1) schema_version preserved,
    cl2_kind=legacy_historical, metadata.derived_from_legacy=True.
    """
    return LedgerEventMapper._event(
        event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
        idempotency_key=f"legacy-{occurrence_id}",
        context=context,
        sequence=sequence,
        payload={
            "cl2_kind": CL2_KIND_LEGACY_HISTORICAL,
            "envelope": {
                "schema_version": "cl.m6-corpus.v1",
                "occurrence_id": occurrence_id,
                "attempt_id": context.identity.attempt_id,
                "metadata": {"derived_from_legacy": True},
            },
        },
    )


@pytest.fixture
def env(tmp_path: Any) -> tuple[
    SqliteAttemptLedgerStore,
    ProjectionBuilder,
    LedgerPersistenceService,
    str,
    LedgerEventContext,
]:
    store = SqliteAttemptLedgerStore(tmp_path / "cl2-proj.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    return store, ProjectionBuilder(store), LedgerPersistenceService(store), attempt_id, context


def _seed_valid_v1(
    service: LedgerPersistenceService,
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    context: LedgerEventContext,
) -> int:
    """Persist a minimal valid v1 replay partition; return next free sequence."""
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.persist_occurrence(
        attempt_id,
        _valid_occurrence(attempt_id),
        idempotency_key="occ-1",
        context=context,
    )
    service.persist_reconciliation(
        attempt_id,
        _valid_reconciliation(),
        idempotency_key="rec-1",
        context=context,
    )
    service.persist_disposition(
        attempt_id,
        _valid_disposition(),
        idempotency_key="disp-1",
        context=context,
    )
    return store.last_sequence(attempt_id) + 1


# ── byte-equivalence ────────────────────────────────────────────────────────


def test_replay_produces_deterministic_hashes(env: Any) -> None:
    """Replaying the same attempt twice yields identical manifest/briefing hashes."""
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)

    first = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    second = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)

    assert isinstance(first, ProjectionResult)
    assert first.manifest_hash == second.manifest_hash
    assert first.briefing_hash == second.briefing_hash
    assert first.manifest_hash  # non-empty
    assert first.briefing_hash
    # Determinism is byte-level: same content round-trips.
    assert json.dumps(first.replay_result["manifest"].to_dict(), sort_keys=True) == json.dumps(
        second.replay_result["manifest"].to_dict(), sort_keys=True
    )


def test_verify_byte_equivalence_returns_true_for_match(env: Any) -> None:
    """verify_byte_equivalence replays and compares against expected hashes."""
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)

    baseline = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    assert builder.verify_byte_equivalence(
        attempt_id,
        baseline.manifest_hash,
        baseline.briefing_hash,
        wbc_receipt_chain=WBC_CHAIN,
    ) is True


def test_verify_byte_equivalence_false_for_mismatch(env: Any) -> None:
    """A wrong expected hash makes verify_byte_equivalence False."""
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)

    assert builder.verify_byte_equivalence(
        attempt_id,
        "0" * 64,
        "1" * 64,
        wbc_receipt_chain=WBC_CHAIN,
    ) is False


# ── legacy-exclusion filter ─────────────────────────────────────────────────


def test_legacy_event_excluded_from_replay_with_legacy_derived_reason(
    env: Any,
) -> None:
    """A legacy_historical OUTCOME is excluded with reason legacy_derived.

    The filter runs BEFORE from_dict (exclude-then-reconstruct), so the
    non-v1 schema_version never reaches the hard-raise path.  The legacy event
    is queryable via read_legacy_context but never routed through replay_full.
    """
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)
    # Append a legacy_historical OUTCOME directly (bypasses from_dict).
    store.append_event(
        attempt_id,
        _legacy_outcome_event(
            context, store.last_sequence(attempt_id) + 1
        ),
    )

    result = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)

    # The v1 partition is admitted and replay succeeds.
    assert len(result.occurrences) == 1
    assert len(result.reconciliations) == 1
    assert len(result.dispositions) == 1
    # The legacy event is excluded with reason legacy_derived.
    assert len(result.replay_excluded) == 1
    excl = result.replay_excluded[0]
    assert excl.cl2_kind == CL2_KIND_LEGACY_HISTORICAL
    assert excl.reason == EXCLUSION_REASON_LEGACY_DERIVED


def test_non_v1_non_legacy_event_excluded_with_schema_version_mismatch(
    env: Any,
) -> None:
    """A non-v1 OUTCOME that is NOT legacy-derived gets schema_version_mismatch.

    A valid v1 occurrence is seeded first so the admitted replay partition is
    non-empty (replay_full rejects empty occurrence sets); the future-schema
    event is excluded with reason schema_version_mismatch.
    """
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)
    # An occurrence-kind payload with a non-v1 schema and NO legacy marker.
    future_event = LedgerEventMapper._event(
        event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
        idempotency_key="future-occ",
        context=context,
        sequence=store.last_sequence(attempt_id) + 1,
        payload={
            "cl2_kind": "occurrence",
            "envelope": {
                "schema_version": "cl.schema.v99",
                "occurrence_id": "future",
                "attempt_id": attempt_id,
                "metadata": {},
            },
        },
    )
    store.append_event(attempt_id, future_event)

    result = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    # The future-schema event is excluded with reason schema_version_mismatch.
    assert len(result.replay_excluded) == 1
    assert result.replay_excluded[0].reason == EXCLUSION_REASON_SCHEMA_VERSION_MISMATCH
    # The v1 occurrence is still admitted (non-empty partition).
    assert len(result.occurrences) == 1


def test_read_legacy_context_returns_legacy_events(env: Any) -> None:
    """read_legacy_context returns full queryable legacy_historical records."""
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)
    legacy_seq = store.last_sequence(attempt_id) + 1
    store.append_event(attempt_id, _legacy_outcome_event(context, legacy_seq))

    legacy = builder.read_legacy_context(attempt_id)

    assert len(legacy) == 1
    event = legacy[0]
    assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
    assert event.payload["cl2_kind"] == CL2_KIND_LEGACY_HISTORICAL
    assert event.payload["envelope"]["metadata"]["derived_from_legacy"] is True
    assert event.sequence == legacy_seq


def test_read_legacy_context_empty_when_no_legacy(env: Any) -> None:
    """No legacy events -> read_legacy_context returns []."""
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)
    assert builder.read_legacy_context(attempt_id) == []


# ── per-contribution authority_scope + rollup ──────────────────────────────


def test_build_cumulative_authoritative_only(env: Any) -> None:
    """An attempt with only v1 contributions rolls up to authoritative."""
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)

    cumulative = builder.build_cumulative([attempt_id])

    scopes = {c.authority_scope for c in cumulative.contributions}
    assert scopes == {AUTHORITY_SCOPE_AUTHORITATIVE}
    assert cumulative.attempt_authority_summary[attempt_id] == ATTEMPT_AUTHORITY_AUTHORITATIVE


def test_build_cumulative_mixed_attempt_authority_scope(env: Any) -> None:
    """A mixed attempt (v1 + legacy) tags each contribution with its own scope.

    Settles CF-F716F109: per-contribution authority_scope (NOT per-attempt).
    The v1 contribution is authoritative, the legacy contribution is
    non_authoritative, and the per-attempt rollup is mixed_authoritative.
    """
    store, builder, service, attempt_id, context = env
    _seed_valid_v1(service, store, attempt_id, context)
    # Append a legacy contribution under the SAME attempt_id.
    legacy_seq = store.last_sequence(attempt_id) + 1
    store.append_event(attempt_id, _legacy_outcome_event(context, legacy_seq))

    cumulative = builder.build_cumulative([attempt_id])

    by_seq = {c.sequence: c for c in cumulative.contributions}
    # The v1 occurrence/reconciliation/disposition OUTCOMEs are authoritative.
    v1_seqs = {s for s, e in zip(
        [e.sequence for e in store.read_events(attempt_id)],
        store.read_events(attempt_id),
    ) if e.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
      and isinstance(e.payload, dict)
      and e.payload.get("cl2_kind") != CL2_KIND_LEGACY_HISTORICAL}
    for seq in v1_seqs:
        assert by_seq[seq].authority_scope == AUTHORITY_SCOPE_AUTHORITATIVE
    # The legacy contribution is non_authoritative.
    assert by_seq[legacy_seq].authority_scope == AUTHORITY_SCOPE_NON_AUTHORITATIVE
    # Per-attempt rollup: mixed.
    assert cumulative.attempt_authority_summary[attempt_id] == ATTEMPT_AUTHORITY_MIXED


def test_build_cumulative_non_authoritative_only(env: Any) -> None:
    """An attempt with only legacy contributions rolls up to non_authoritative."""
    store, builder, _, attempt_id, context = env
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    from arnold.critique_ledger.persistence_service import LedgerPersistenceService as _Svc
    # Need an INTENT before the legacy OUTCOME (lifecycle precedence).
    LedgerPersistenceService(store).record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    store.append_event(
        attempt_id,
        _legacy_outcome_event(context, store.last_sequence(attempt_id) + 1),
    )

    cumulative = builder.build_cumulative([attempt_id])

    assert all(
        c.authority_scope == AUTHORITY_SCOPE_NON_AUTHORITATIVE
        for c in cumulative.contributions
    )
    assert cumulative.attempt_authority_summary[attempt_id] == ATTEMPT_AUTHORITY_NON_AUTHORITATIVE


def test_build_cumulative_empty_for_attempt_with_no_outcomes(env: Any) -> None:
    """An attempt with no OUTCOME contributions rolls up to empty."""
    store, builder, _, attempt_id, context = env
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )

    cumulative = builder.build_cumulative([attempt_id])

    assert cumulative.contributions == []
    assert cumulative.attempt_authority_summary[attempt_id] == ATTEMPT_AUTHORITY_EMPTY


def test_build_cumulative_across_multiple_attempts(env: Any) -> None:
    """Cumulative aggregates across attempts with distinct rollups."""
    store, builder, service, attempt_id_a, context_a = env
    # Attempt A: authoritative only.
    _seed_valid_v1(service, store, attempt_id_a, context_a)

    # Attempt B: legacy only.
    attempt_id_b = str(uuid.uuid4())
    context_b = _context(attempt_id_b)
    store.append_started(
        attempt_id_b,
        _lifecycle_event(context_b, AttemptEventType.STARTED, 1, "started"),
    )
    service.record_intent(
        attempt_id_b, {"briefing_ref": "ref"}, idempotency_key="intent", context=context_b
    )
    store.append_event(
        attempt_id_b,
        _legacy_outcome_event(context_b, store.last_sequence(attempt_id_b) + 1),
    )

    cumulative = builder.build_cumulative([attempt_id_a, attempt_id_b])

    assert cumulative.attempt_authority_summary[attempt_id_a] == ATTEMPT_AUTHORITY_AUTHORITATIVE
    assert cumulative.attempt_authority_summary[attempt_id_b] == ATTEMPT_AUTHORITY_NON_AUTHORITATIVE


# ── reconstruction integrity ────────────────────────────────────────────────


def test_replay_reconstruction_byte_equivalence_to_persisted(env: Any) -> None:
    """Reconstructed CL1 objects are byte-equivalent to the persisted originals."""
    store, builder, service, attempt_id, context = env
    occ = _valid_occurrence(attempt_id)
    rec = _valid_reconciliation()
    disp = _valid_disposition()
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.persist_occurrence(attempt_id, occ, idempotency_key="occ-1", context=context)
    service.persist_reconciliation(attempt_id, rec, idempotency_key="rec-1", context=context)
    service.persist_disposition(attempt_id, disp, idempotency_key="disp-1", context=context)

    result = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)

    def _canonical(value: dict[str, Any]) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    assert _canonical(result.occurrences[0].to_dict()) == _canonical(occ.to_dict())
    assert _canonical(result.reconciliations[0].to_dict()) == _canonical(rec.to_dict())
    assert _canonical(result.dispositions[0].to_dict()) == _canonical(disp.to_dict())
