"""Focused unit coverage for governed freshness vectors.

Freshness is a staleness/availability signal ONLY.  These tests assert:

* unavailable and tombstoned evidence is surfaced as stale (absence, never
  authority);
* observed age contributes an age-based staleness reason only when an explicit
  freshness window is supplied;
* briefing-required unavailable/tombstoned evidence blocks briefing;
* incidental markers (``derived_from_legacy``, ``producer_id``, ``model_id``,
  ``grant_ref``, ``authority``, ``accepted_for_cl2``) NEVER influence the
  staleness classification — there is no authority field to acquire.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from arnold.critique_ledger.freshness import (
    REASON_INPUT_HASH_DIVERGED,
    REASON_OBSERVATION_EXCEEDED_MAX_AGE,
    REASON_TOMBSTONED,
    REASON_UNAVAILABLE,
    FreshnessTracker,
    FreshnessVector,
    InputStalenessVerdict,
    compare_input_hashes,
    compute_input_hash,
)
from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerPersistenceService,
)
from arnold.critique_ledger.schemas import (
    Authority,
    CritiqueOccurrenceEnvelope,
    EvidenceAvailability,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    ParseStatus,
    Relationship,
)
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptIdentity,
    AttemptProvenance,
    GrantRef,
    RuntimeAdapter,
    VersionSet,
)

# An observation time older than the freshness window used below.
_OBSERVED_AT = "2026-08-01T00:00:00+00:00"


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-fresh"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at=_OBSERVED_AT,
        observed_at=_OBSERVED_AT,
    )


@pytest.fixture
def seeded() -> tuple[SqliteAttemptLedgerStore, str]:
    """Return a store with one attempt stream seeded with a START + INTENT."""
    store = SqliteAttemptLedgerStore(_store_path())
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)
    service.start_attempt(attempt_id, context=context, idempotency_key="start")
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    return store, attempt_id


def _store_path() -> Any:
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp()) / "freshness.sqlite"


def _persist(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    *,
    occurrence_id: str,
    evidence_availability: str = EvidenceAvailability.RETAINED.value,
    parse_status: str = ParseStatus.SELECTED.value,
    metadata: dict[str, Any] | None = None,
) -> None:
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)
    envelope = CritiqueOccurrenceEnvelope(
        occurrence_id=occurrence_id,
        attempt_id=attempt_id,
        evidence_availability=evidence_availability,
        parse_status=parse_status,
        metadata=metadata or {},
    )
    service.persist_occurrence(
        attempt_id,
        envelope,
        idempotency_key=occurrence_id,
        context=context,
    )


# ── compute_freshness: classification ──────────────────────────────────────


def test_retained_evidence_is_fresh_by_default(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(store, attempt_id, occurrence_id="occ-retained")
    vectors = FreshnessTracker(store).compute_freshness(attempt_id)

    assert len(vectors) == 1
    vec = vectors[0]
    assert isinstance(vec, FreshnessVector)
    assert vec.occurrence_id == "occ-retained"
    assert vec.evidence_class == EvidenceAvailability.RETAINED.value
    assert vec.is_stale is False
    assert vec.staleness_reason == ""


def test_unavailable_evidence_is_stale(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-unavailable",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
    )
    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]

    assert vec.is_stale is True
    assert vec.staleness_reason == REASON_UNAVAILABLE
    assert vec.evidence_class == EvidenceAvailability.UNAVAILABLE.value


def test_tombstoned_evidence_is_stale_regardless_of_availability(seeded: Any) -> None:
    """A tombstone marks absence and wins over the availability class."""
    store, attempt_id = seeded
    # Tombstone precedence: even a RETAINED evidence class is stale when the
    # parse status is TOMBSTONED.
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-tomb",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        parse_status=ParseStatus.TOMBSTONED.value,
    )
    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]

    assert vec.is_stale is True
    assert vec.staleness_reason == REASON_TOMBSTONED


def test_tombstone_precedence_over_unavailable(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-tomb-unavail",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        parse_status=ParseStatus.TOMBSTONED.value,
    )
    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]

    assert vec.is_stale is True
    # Tombstone (absence) wins precedence over the unavailable class.
    assert vec.staleness_reason == REASON_TOMBSTONED


def test_governed_reference_is_fresh(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-govref",
        evidence_availability=EvidenceAvailability.GOVERNED_REFERENCE.value,
    )
    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]
    assert vec.is_stale is False


# ── compute_freshness: age-based staleness ─────────────────────────────────


def test_observation_age_flags_stale_only_with_window(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(store, attempt_id, occurrence_id="occ-old")
    tracker = FreshnessTracker(store)

    # No window: never stale by age even though observation is old.
    no_window = tracker.compute_freshness(attempt_id)
    assert no_window[0].is_stale is False

    # With a window shorter than the observation age: stale.
    stale = tracker.compute_freshness(
        attempt_id, now="2026-08-02T00:00:00+00:00", max_age_seconds=1
    )
    assert stale[0].is_stale is True
    assert stale[0].staleness_reason == REASON_OBSERVATION_EXCEEDED_MAX_AGE

    # With a window longer than the observation age: fresh.
    fresh = tracker.compute_freshness(
        attempt_id, now="2026-08-01T00:00:05+00:00", max_age_seconds=60
    )
    assert fresh[0].is_stale is False


def test_unparseable_timestamp_disables_age_staleness(seeded: Any) -> None:
    """Timestamps alone never establish authority; an unparseable timestamp
    simply disables age-based staleness rather than producing an error."""
    store, attempt_id = seeded
    _persist(store, attempt_id, occurrence_id="occ-ts")
    vec = FreshnessTracker(store).compute_freshness(
        attempt_id, now="not-a-timestamp", max_age_seconds=1
    )
    assert vec[0].is_stale is False


# ── required_for_briefing_unavailable ──────────────────────────────────────


def test_briefing_required_unavailable_blocks(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-briefing-unavail",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        metadata={"required_for_briefing": True},
    )
    tracker = FreshnessTracker(store)
    assert tracker.required_for_briefing_unavailable(attempt_id) is True


def test_briefing_required_tombstoned_blocks(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-briefing-tomb",
        parse_status=ParseStatus.TOMBSTONED.value,
        metadata={"required_for_briefing": True},
    )
    tracker = FreshnessTracker(store)
    assert tracker.required_for_briefing_unavailable(attempt_id) is True


def test_briefing_required_retained_does_not_block(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-briefing-retained",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        metadata={"required_for_briefing": True},
    )
    tracker = FreshnessTracker(store)
    assert tracker.required_for_briefing_unavailable(attempt_id) is False


def test_briefing_required_old_evidence_does_not_block(seeded: Any) -> None:
    """Age-based staleness alone does NOT block briefing — the evidence still
    exists, it is merely old.  Only absence (unavailable/tombstoned) blocks."""
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-briefing-old",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        metadata={"required_for_briefing": True},
    )
    tracker = FreshnessTracker(store)
    assert (
        tracker.required_for_briefing_unavailable(
            attempt_id, now="2026-09-01T00:00:00+00:00", max_age_seconds=1
        )
        is False
    )


def test_briefing_filter_by_evidence_class(seeded: Any) -> None:
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-briefing-retained-only",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        metadata={"required_for_briefing": True},
    )
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-briefing-unavail-2",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        metadata={"required_for_briefing": True},
    )
    tracker = FreshnessTracker(store)
    # Filtering to RETAINED finds no unavailable briefing-required evidence.
    assert (
        tracker.required_for_briefing_unavailable(
            attempt_id, evidence_class=EvidenceAvailability.RETAINED.value
        )
        is False
    )
    # Filtering to UNAVAILABLE finds the blocking evidence.
    assert (
        tracker.required_for_briefing_unavailable(
            attempt_id, evidence_class=EvidenceAvailability.UNAVAILABLE.value
        )
        is True
    )


# ── authority neutrality: incidental markers never influence staleness ─────


@pytest.mark.parametrize(
    "marker",
    [
        {"derived_from_legacy": True},
        {"producer_id": "critic-1"},
        {"model_id": "model-1"},
        {"grant_ref": "grant-1"},
        {"authority": "EVALUATOR"},
        {"accepted_for_cl2": True},
    ],
)
def test_incidental_markers_never_confer_freshness(seeded: Any, marker: Any) -> None:
    """Unavailable evidence stays stale even when an incidental marker that
    might look authoritative is present — there is no authority field to read."""
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id=f"occ-marker-{next(iter(marker))}",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        metadata=marker,
    )
    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]
    assert vec.is_stale is True
    assert vec.staleness_reason == REASON_UNAVAILABLE


def test_authority_markers_in_metadata_do_not_promote_retained_to_authoritative(
    seeded: Any,
) -> None:
    """A retained vector with authority-like markers is fresh for staleness
    purposes but carries no authority signal (FreshnessVector has none)."""
    store, attempt_id = seeded
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-retained-marked",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        metadata={
            "derived_from_legacy": True,
            "producer_id": "x",
            "model_id": "y",
            "authority": "EVALUATOR",
            "accepted_for_cl2": True,
        },
    )
    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]
    assert vec.is_stale is False
    # FreshnessVector exposes only staleness fields — no authority attribute.
    assert not hasattr(vec, "authority")
    assert not hasattr(vec, "is_authoritative")


def test_freshness_vector_has_no_authority_field() -> None:
    """Static contract: FreshnessVector is a pure staleness record."""
    fields = {f for f in FreshnessVector.__dataclass_fields__}
    assert "authority" not in fields
    assert "is_authoritative" not in fields
    assert "accepted_for_cl2" not in fields
    assert fields == {
        "occurrence_id",
        "last_observed_at",
        "evidence_class",
        "is_stale",
        "staleness_reason",
    }


# ── input-hash staleness: canonical hashing and advisory comparison ───────


def _occurrence(occurrence_id: str = "occ-1", finding_id: str = "f-1") -> CritiqueOccurrenceEnvelope:
    return CritiqueOccurrenceEnvelope(
        occurrence_id=occurrence_id,
        attempt_id="attempt-1",
        finding_id=finding_id,
        semantic_finding_id=finding_id,
        producer_id="critic-1",
        parse_status=ParseStatus.SELECTED.value,
        evidence_availability=EvidenceAvailability.RETAINED.value,
    )


def _reconciliation(reconciliation_id: str = "rec-1") -> FindingReconciliationEvent:
    return FindingReconciliationEvent(
        reconciliation_id=reconciliation_id,
        canonical_finding_id="f-1",
        semantic_finding_id="f-1",
        occurrence_ids=("occ-1",),
        relationship=Relationship.DUPLICATE.value,
        authority=Authority.EVALUATOR.value,
    )


def _disposition(disposition_id: str = "disp-1") -> FindingDispositionEvent:
    return FindingDispositionEvent(
        disposition_id=disposition_id,
        semantic_finding_id="f-1",
        family="verified",
        authority=Authority.EVALUATOR.value,
    )


def test_compute_input_hash_is_deterministic_for_equivalent_sources() -> None:
    """The same three input sets produce the same hash regardless of order."""
    occ = [_occurrence()]
    rec = [_reconciliation()]
    disp = [_disposition()]
    h1 = compute_input_hash(occ, rec, disp)
    h2 = compute_input_hash(list(reversed(occ)), list(reversed(rec)), list(reversed(disp)))
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64  # SHA-256 hex


def test_compute_input_hash_changes_when_any_source_changes() -> None:
    """Changing any of the three input sources changes the canonical hash."""
    base = compute_input_hash([_occurrence()], [_reconciliation()], [_disposition()])

    # Change occurrences
    occ2 = compute_input_hash(
        [_occurrence(occurrence_id="occ-2")], [_reconciliation()], [_disposition()]
    )
    assert occ2 != base

    # Change reconciliations
    rec2 = compute_input_hash(
        [_occurrence()], [_reconciliation(reconciliation_id="rec-2")], [_disposition()]
    )
    assert rec2 != base

    # Change dispositions
    disp2 = compute_input_hash(
        [_occurrence()], [_reconciliation()], [_disposition(disposition_id="disp-2")]
    )
    assert disp2 != base


def test_compute_input_hash_accepts_dict_envelopes() -> None:
    """Envelope dicts (as read from the ledger payload) hash stably and
    deterministically; the same dict content produces the same hash on every
    call.  Dataclass instances and dicts are intentionally distinct canonical
    representations (``freeze_for_hashing`` records the dataclass type name),
    so callers must hash consistent representations; this test asserts the
    round-trip stability of each representation independently."""
    occ_dc = _occurrence()
    occ_dict = occ_dc.to_dict()
    # Dataclass representation is stable.
    h_dc_1 = compute_input_hash([occ_dc], [], [])
    h_dc_2 = compute_input_hash([occ_dc], [], [])
    assert h_dc_1 == h_dc_2
    # Dict representation is stable and produces a valid SHA-256 hex digest.
    h_dict_1 = compute_input_hash([occ_dict], [], [])
    h_dict_2 = compute_input_hash([occ_dict], [], [])
    assert h_dict_1 == h_dict_2
    assert isinstance(h_dict_1, str) and len(h_dict_1) == 64
    # The two representations differ by type-name wrapping — documented and
    # expected.  Callers choose one representation and hash it consistently.
    assert h_dc_1 != h_dict_1


def test_compare_input_hashes_fresh_when_stored_matches_current() -> None:
    occ, rec, disp = [_occurrence()], [_reconciliation()], [_disposition()]
    stored = compute_input_hash(occ, rec, disp)
    verdict = compare_input_hashes(stored, occ, rec, disp)
    assert verdict.is_stale is False
    assert verdict.stored_hash == stored
    assert verdict.current_hash == stored
    assert verdict.staleness_reason == ""


def test_compare_input_hashes_stale_when_input_changes() -> None:
    """Changing any canonical briefing input sets staleness while leaving the
    advisory authority neutral (sense check SC10)."""
    stored = compute_input_hash([_occurrence()], [_reconciliation()], [_disposition()])
    verdict = compare_input_hashes(
        stored,
        [_occurrence(occurrence_id="occ-changed")],
        [_reconciliation()],
        [_disposition()],
    )
    assert verdict.is_stale is True
    assert verdict.staleness_reason == REASON_INPUT_HASH_DIVERGED
    assert verdict.current_hash != stored
    assert verdict.stored_hash == stored


def test_compare_input_hashes_treats_missing_stored_as_fresh() -> None:
    """No stored hash → cannot assert divergence → fresh (advisory, no
    authority granted either way)."""
    verdict = compare_input_hashes("", [_occurrence()], [_reconciliation()], [_disposition()])
    assert verdict.is_stale is False
    assert verdict.staleness_reason == ""
    verdict_none = compare_input_hashes(
        None,  # type: ignore[arg-type]
        [_occurrence()],
        [_reconciliation()],
        [_disposition()],
    )
    assert verdict_none.is_stale is False


def test_input_staleness_verdict_has_no_authority_field() -> None:
    """Static contract: InputStalenessVerdict is a pure advisory staleness
    record.  It carries hashes and a reason only — never authority."""
    fields = set(InputStalenessVerdict.__dataclass_fields__)
    assert "authority" not in fields
    assert "is_authoritative" not in fields
    assert "accepted_for_cl2" not in fields
    assert fields == {"is_stale", "stored_hash", "current_hash", "staleness_reason"}


def test_input_staleness_never_grants_authority() -> None:
    """SC10: changing any canonical briefing input sets staleness while leaving
    positive authority unchanged.  The verdict has no authority surface at all;
    even inputs carrying authority markers never change the staleness signal."""
    occ_authoritative = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-auth",
        attempt_id="attempt-1",
        finding_id="f-1",
        semantic_finding_id="f-1",
        producer_id="critic-1",
        parse_status=ParseStatus.SELECTED.value,
        evidence_availability=EvidenceAvailability.RETAINED.value,
    )
    occ_authoritative2 = CritiqueOccurrenceEnvelope(
        occurrence_id="occ-auth-2",
        attempt_id="attempt-1",
        finding_id="f-1",
        semantic_finding_id="f-1",
        producer_id="critic-1",
        parse_status=ParseStatus.SELECTED.value,
        evidence_availability=EvidenceAvailability.RETAINED.value,
    )
    disp_authoritative = FindingDispositionEvent(
        disposition_id="disp-1",
        semantic_finding_id="f-1",
        family="verified",
        authority=Authority.EVALUATOR.value,
    )
    stored = compute_input_hash([occ_authoritative], [], [disp_authoritative])
    verdict = compare_input_hashes(stored, [occ_authoritative2], [], [disp_authoritative])
    assert verdict.is_stale is True
    # No authority field to read — staleness does not promote to admission.
    assert not hasattr(verdict, "authority")
    assert not hasattr(verdict, "is_authoritative")
    assert not hasattr(verdict, "accepted_for_cl2")
