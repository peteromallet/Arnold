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
    REASON_OBSERVATION_EXCEEDED_MAX_AGE,
    REASON_TOMBSTONED,
    REASON_UNAVAILABLE,
    FreshnessTracker,
    FreshnessVector,
)
from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerPersistenceService,
)
from arnold.critique_ledger.schemas import (
    CritiqueOccurrenceEnvelope,
    EvidenceAvailability,
    ParseStatus,
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
