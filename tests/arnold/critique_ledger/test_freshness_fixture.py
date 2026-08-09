"""End-to-end freshness and tombstone-governance fixture (T12).

Builds a single attempt ledger carrying available, unavailable, and
tombstoned evidence -- some of it decorated with incidental authority-like
markers -- and proves the governed freshness contract:

* freshness reasons are correct (retained=fresh; unavailable/tombstoned=stale);
* tombstone precedence wins over the availability class;
* stale / unavailable / tombstoned evidence surfaces as *stale* (unknown for
  use) -- never as authoritative or "known";
* tombstones NEVER confer authority: ``FreshnessVector`` has no authority
  field, and incidental markers (``authority``, ``accepted_for_cl2``,
  ``producer_id``, ``model_id``, ``grant_ref``, ``derived_from_legacy``) never
  change the staleness classification;
* briefing-required unavailable/tombstoned evidence blocks briefing.
"""

from __future__ import annotations

import uuid
from pathlib import Path
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

# Every incidental marker that might *look* authoritative.  Each must be
# ignored by freshness classification -- there is no authority field to read.
_AUTHORITY_LIKE_MARKERS: dict[str, Any] = {
    "authority": "EVALUATOR",
    "accepted_for_cl2": True,
    "producer_id": "critic-authoritative-looking",
    "model_id": "model-authoritative-looking",
    "grant_ref": "grant-looks-real",
    "derived_from_legacy": True,
}


def _context(
    attempt_id: str,
    *,
    observed_at: str = "2026-08-01T00:00:00+00:00",
) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-freshness-fixture"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at=observed_at,
        observed_at=observed_at,
    )


def _persist(
    store: SqliteAttemptLedgerStore,
    attempt_id: str,
    *,
    occurrence_id: str,
    evidence_availability: str = EvidenceAvailability.RETAINED.value,
    parse_status: str = ParseStatus.SELECTED.value,
    metadata: dict[str, Any] | None = None,
    observed_at: str = "2026-08-01T00:00:00+00:00",
) -> None:
    context = _context(attempt_id, observed_at=observed_at)
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


@pytest.fixture
def ledger(
    tmp_path: Path,
) -> tuple[SqliteAttemptLedgerStore, str]:
    """A store + attempt seeded with STARTED + INTENT for outcome appends."""
    store = SqliteAttemptLedgerStore(tmp_path / "freshness-fixture.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)
    service.start_attempt(attempt_id, context=context, idempotency_key="start")
    service.record_intent(
        attempt_id,
        {"briefing_ref": "ref"},
        idempotency_key="intent",
        context=context,
    )
    return store, attempt_id


def _seed_three_classes(
    store: SqliteAttemptLedgerStore, attempt_id: str
) -> None:
    """Seed available, unavailable, and tombstoned evidence.

    The unavailable and tombstoned records deliberately carry every
    authority-like incidental marker so the fixture positively exercises the
    "markers never authorize" invariant.
    """
    # 1. Available (RETAINED) evidence -- fresh.
    _persist(store, attempt_id, occurrence_id="occ-available")

    # 2. Unavailable evidence carrying authority-like markers -- stale.
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-unavailable-marked",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        metadata=dict(_AUTHORITY_LIKE_MARKERS, required_for_briefing=True),
    )

    # 3. Tombstoned evidence (RETAINED class) carrying authority-like markers
    #    -- stale by tombstone precedence.
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-tomb-marked",
        parse_status=ParseStatus.TOMBSTONED.value,
        metadata=dict(_AUTHORITY_LIKE_MARKERS, required_for_briefing=True),
    )

    # 4. Tombstoned AND unavailable -- tombstone precedence wins.
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-tomb-unavailable",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        parse_status=ParseStatus.TOMBSTONED.value,
    )


def test_freshness_reasons_across_availability_and_tombstone_classes(
    ledger: Any,
) -> None:
    """Correct staleness reasons for available, unavailable, and tombstoned."""
    store, attempt_id = ledger
    _seed_three_classes(store, attempt_id)

    vectors = FreshnessTracker(store).compute_freshness(attempt_id)
    by_id = {vec.occurrence_id: vec for vec in vectors}

    # Available (RETAINED) -> fresh, no reason.
    available = by_id["occ-available"]
    assert available.evidence_class == EvidenceAvailability.RETAINED.value
    assert available.is_stale is False
    assert available.staleness_reason == ""

    # Unavailable -> stale, reason "unavailable" (markers do not change this).
    unavailable = by_id["occ-unavailable-marked"]
    assert unavailable.evidence_class == EvidenceAvailability.UNAVAILABLE.value
    assert unavailable.is_stale is True
    assert unavailable.staleness_reason == REASON_UNAVAILABLE

    # Tombstoned (RETAINED class) -> stale, reason "tombstoned" (precedence).
    tomb = by_id["occ-tomb-marked"]
    assert tomb.is_stale is True
    assert tomb.staleness_reason == REASON_TOMBSTONED

    # Tombstoned + unavailable -> tombstone precedence over the class.
    tomb_unavail = by_id["occ-tomb-unavailable"]
    assert tomb_unavail.is_stale is True
    assert tomb_unavail.staleness_reason == REASON_TOMBSTONED


def test_stale_evidence_surfaces_as_unknown_for_use_never_authoritative(
    ledger: Any,
) -> None:
    """Unavailable/tombstoned evidence projects as stale (unknown for use).

    No stale vector can be read as authoritative or "known": each carries only
    a staleness signal, and the only stale reasons are absence reasons
    (``unavailable`` / ``tombstoned``) or age.  There is no authority channel.
    """
    store, attempt_id = ledger
    _seed_three_classes(store, attempt_id)

    vectors = FreshnessTracker(store).compute_freshness(attempt_id)

    stale = [vec for vec in vectors if vec.is_stale]
    fresh = [vec for vec in vectors if not vec.is_stale]
    assert len(stale) == 3  # unavailable + 2 tombstoned
    assert len(fresh) == 1  # the single RETAINED occurrence

    for vec in stale:
        # Stale evidence surfaces ONLY as an absence/age reason -- never as a
        # positive "known/authoritative" signal.
        assert vec.staleness_reason in (
            REASON_UNAVAILABLE,
            REASON_TOMBSTONED,
            REASON_OBSERVATION_EXCEEDED_MAX_AGE,
        )
        # No vector exposes any authority channel.
        assert not hasattr(vec, "authority")
        assert not hasattr(vec, "is_authoritative")
        assert not hasattr(vec, "accepted_for_cl2")


def test_tombstones_never_confer_authority_from_incidental_markers(
    ledger: Any,
) -> None:
    """Positively prove tombstones mean absence only, never authorization.

    A tombstoned record decorated with the full set of authority-like markers
    (``authority``, ``accepted_for_cl2``, ``producer_id``, ``model_id``,
    ``grant_ref``, ``derived_from_legacy``) is STILL stale, and no marker
    promotes it to fresh or authoritative.  FreshnessVector is structurally
    incapable of carrying authority.
    """
    store, attempt_id = ledger
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-tomb-fully-marked",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        parse_status=ParseStatus.TOMBSTONED.value,
        metadata=_AUTHORITY_LIKE_MARKERS,
    )

    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]

    # The tombstone marks absence regardless of every authority-like marker.
    assert vec.is_stale is True
    assert vec.staleness_reason == REASON_TOMBSTONED

    # Static contract: FreshnessVector has no authority field whatsoever, so a
    # tombstone (or any incidental marker) cannot confer authority.
    fields = set(FreshnessVector.__dataclass_fields__)
    assert fields.isdisjoint(
        {"authority", "is_authoritative", "accepted_for_cl2", "grant_ref"}
    )
    assert fields == {
        "occurrence_id",
        "last_observed_at",
        "evidence_class",
        "is_stale",
        "staleness_reason",
    }


def test_unavailable_with_markers_stays_unavailable(ledger: Any) -> None:
    """Unavailable evidence carrying authority-like markers stays stale.

    The marker set that might *look* like an admission/authority grant does
    not change the unavailable classification -- absence is absence.
    """
    store, attempt_id = ledger
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-unavail-fully-marked",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
        metadata=_AUTHORITY_LIKE_MARKERS,
    )

    vec = FreshnessTracker(store).compute_freshness(attempt_id)[0]
    assert vec.is_stale is True
    assert vec.staleness_reason == REASON_UNAVAILABLE
    assert vec.evidence_class == EvidenceAvailability.UNAVAILABLE.value


def test_briefing_blocked_by_unavailable_and_tombstoned_required_evidence(
    ledger: Any,
) -> None:
    """Briefing-required unavailable AND tombstoned evidence block briefing.

    Age-based staleness alone would not block (the evidence still exists), but
    absence (unavailable / tombstoned) blocks.  Markers do not un-block.
    """
    store, attempt_id = ledger
    _seed_three_classes(store, attempt_id)
    tracker = FreshnessTracker(store)

    # The seeded unavailable and tombstoned records are briefing-required;
    # their absence blocks briefing.
    assert tracker.required_for_briefing_unavailable(attempt_id) is True

    # A fresh RETAINED record that is briefing-required does NOT block: build
    # a second clean attempt on the SAME store and confirm.
    fresh_attempt = str(uuid.uuid4())
    context = _context(fresh_attempt)
    service = LedgerPersistenceService(store)
    service.start_attempt(
        fresh_attempt, context=context, idempotency_key="start-fresh"
    )
    service.record_intent(
        fresh_attempt,
        {"briefing_ref": "ref"},
        idempotency_key="intent-fresh",
        context=context,
    )
    _persist(
        store,
        fresh_attempt,
        occurrence_id="occ-fresh-required",
        evidence_availability=EvidenceAvailability.RETAINED.value,
        metadata={"required_for_briefing": True},
    )
    assert (
        tracker.required_for_briefing_unavailable(fresh_attempt) is False
    )


def test_freshness_is_read_only_and_idempotent(ledger: Any) -> None:
    """Computing freshness twice yields identical vectors and mutates nothing.

    The tracker is side-effect-free: it reads the persisted stream and never
    appends or reserves.  This reinforces that freshness confers no authority
    and cannot alter the ledger.
    """
    store, attempt_id = ledger
    _seed_three_classes(store, attempt_id)
    tracker = FreshnessTracker(store)

    before_count = store.event_count(attempt_id)
    first = tracker.compute_freshness(attempt_id)
    second = tracker.compute_freshness(attempt_id)

    assert store.event_count(attempt_id) == before_count  # no mutation
    assert len(first) == len(second) == 4
    for a, b in zip(first, second):
        assert a == b


def test_all_four_freshness_categories_in_one_ledger(ledger: Any) -> None:
    """Seed available, age-stale, unavailable, and tombstoned evidence end-to-end.

    The fixture task names four categories -- available, *stale* (age-based),
    unavailable, and tombstoned -- and this builds all four in ONE ledger, then
    computes freshness with an explicit window and asserts each carries its
    explicit reason.  Age-staleness is distinct from absence: an available
    record older than the window surfaces with
    ``observation_exceeded_max_age``, while unavailable/tombstoned keep their
    absence reasons by precedence (the age detector is never reached for them).
    No category confers authority.
    """
    store, attempt_id = ledger

    # Window: 1 hour.  ``now`` is 2 hours after the baseline observation time.
    now = "2026-08-01T02:00:00+00:00"
    max_age_seconds = 3600

    # 1. Available evidence observed recently -- inside the window -> fresh.
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-available-recent",
        observed_at="2026-08-01T01:30:00+00:00",
    )

    # 2. Available evidence observed at the baseline time -- outside the window
    #    -> age-stale (distinct reason, NOT an absence reason).
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-available-age-stale",
        observed_at="2026-08-01T00:00:00+00:00",
    )

    # 3. Unavailable evidence (also at the baseline time, but precedence beats
    #    age so the reason is "unavailable", not the age reason).
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-unavailable",
        evidence_availability=EvidenceAvailability.UNAVAILABLE.value,
    )

    # 4. Tombstoned evidence (precedence beats both unavailable and age).
    _persist(
        store,
        attempt_id,
        occurrence_id="occ-tombstoned",
        parse_status=ParseStatus.TOMBSTONED.value,
    )

    vectors = FreshnessTracker(store).compute_freshness(
        attempt_id, now=now, max_age_seconds=max_age_seconds
    )
    by_id = {vec.occurrence_id: vec for vec in vectors}

    # (1) Recent available -> fresh.
    recent = by_id["occ-available-recent"]
    assert recent.is_stale is False
    assert recent.staleness_reason == ""

    # (2) Available but old -> age-stale with the explicit age reason.
    age_stale = by_id["occ-available-age-stale"]
    assert age_stale.is_stale is True
    assert age_stale.staleness_reason == REASON_OBSERVATION_EXCEEDED_MAX_AGE

    # (3) Unavailable -> stale, reason "unavailable".
    unavail = by_id["occ-unavailable"]
    assert unavail.is_stale is True
    assert unavail.staleness_reason == REASON_UNAVAILABLE

    # (4) Tombstoned -> stale, reason "tombstoned".
    tomb = by_id["occ-tombstoned"]
    assert tomb.is_stale is True
    assert tomb.staleness_reason == REASON_TOMBSTONED

    # All four categories are represented by exactly these distinct reasons;
    # none of them exposes an authority channel.
    observed_reasons = {vec.staleness_reason for vec in vectors}
    assert "" in observed_reasons  # one fresh
    assert REASON_OBSERVATION_EXCEEDED_MAX_AGE in observed_reasons
    assert REASON_UNAVAILABLE in observed_reasons
    assert REASON_TOMBSTONED in observed_reasons
    for vec in vectors:
        assert not hasattr(vec, "authority")
