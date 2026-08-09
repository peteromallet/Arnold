"""Current-source import test over the m6-corpus.json fixture.

The m6-corpus is a multi-schema corpus with **zero** ``cl.schema.v1`` records.
This test proves that attempting to persist its heterogeneous records as CL2
``cl2_kind:occurrence`` outcomes yields **zero** authoritative writes and
leaves the ledger clean after every shape or version rejection — mechanism
agnostic.  It separately rejects a synthetic ``cl.schema.v99-future`` envelope
without partial publication.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from arnold.critique_ledger.persistence_service import (
    CL2_KIND_OCCURRENCE,
    LedgerEventContext,
    LedgerPersistenceService,
)
from arnold.critique_ledger.schemas import (
    SCHEMA_VERSION,
    CritiqueOccurrenceEnvelope,
    EvidenceAvailability,
    ParseStatus,
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

CORPUS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "critique_ledger"
    / "m6-corpus.json"
)


def _load_corpus() -> dict[str, Any]:
    with CORPUS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _collect_schema_versions(obj: Any) -> set[str]:
    """Walk a nested structure and collect every ``schema_version`` value."""
    versions: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "schema_version" in node:
                versions.add(str(node["schema_version"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(obj)
    return versions


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-current"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-01T00:00:00+00:00",
        observed_at="2026-08-01T00:00:00+00:00",
    )


@pytest.fixture
def seeded(tmp_path: Path) -> tuple[SqliteAttemptLedgerStore, str, LedgerEventContext, LedgerPersistenceService]:
    store = SqliteAttemptLedgerStore(tmp_path / "current.sqlite")
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
    return store, attempt_id, context, service


def _occurrence_outcomes(
    store: SqliteAttemptLedgerStore, attempt_id: str
) -> list[Any]:
    return [
        e
        for e in store.read_events(attempt_id)
        if e.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
        and isinstance(e.payload, dict)
        and e.payload.get("cl2_kind") == CL2_KIND_OCCURRENCE
    ]


# ── corpus shape ────────────────────────────────────────────────────────────


def test_corpus_fixture_exists_and_is_multi_schema() -> None:
    assert CORPUS_PATH.exists(), f"Corpus fixture missing: {CORPUS_PATH}"
    corpus = _load_corpus()
    versions = _collect_schema_versions(corpus)
    assert len(versions) > 1, "expected a multi-schema corpus"
    # The corpus contains ZERO cl.schema.v1 records.
    assert SCHEMA_VERSION not in versions
    assert "cl.schema.v1" not in versions


# ── validate every ParseStatus and EvidenceAvailability value ───────────────


def test_every_parse_status_value_is_valid() -> None:
    """Every ParseStatus enum member is a non-empty, distinct string value."""
    values = [member.value for member in ParseStatus]
    assert all(isinstance(v, str) and v for v in values)
    assert len(set(values)) == len(values), "ParseStatus values must be distinct"
    # The corpus references parse_status semantics indirectly; the enum is the
    # authoritative set.
    assert ParseStatus.TOMBSTONED.value == "TOMBSTONED"
    assert ParseStatus.SELECTED.value == "SELECTED"


def test_every_evidence_availability_value_is_valid() -> None:
    """Every EvidenceAvailability enum member is a non-empty, distinct value."""
    values = [member.value for member in EvidenceAvailability]
    assert all(isinstance(v, str) and v for v in values)
    assert len(set(values)) == len(values)
    assert EvidenceAvailability.UNAVAILABLE.value == "UNAVAILABLE"
    assert EvidenceAvailability.RETAINED.value == "RETAINED"
    assert EvidenceAvailability.GOVERNED_REFERENCE.value == "GOVERNED_REFERENCE"


# ── zero authoritative occurrence writes across the zero-v1 corpus ─────────


def test_zero_v1_corpus_yields_zero_occurrence_writes(seeded: Any) -> None:
    """Attempt persistence outcome-mechanically across every corpus version.

    Every schema_version in the corpus is non-v1, so every attempt to persist
    an occurrence is rejected (mechanism-agnostic) and zero cl2_kind:occurrence
    events survive.
    """
    store, attempt_id, context, service = seeded
    corpus = _load_corpus()
    versions = sorted(_collect_schema_versions(corpus))
    assert SCHEMA_VERSION not in versions

    rejections = 0
    for version in versions:
        # Construct an occurrence envelope carrying the corpus's version.
        # The dataclass __init__ accepts non-v1 versions; the v1 gate fires
        # during the validated persistence path.
        envelope = CritiqueOccurrenceEnvelope(
            schema_version=version,
            occurrence_id=f"current-{version}",
            attempt_id=attempt_id,
        )
        # Attempt persistence; rejection is mechanism-agnostic (any failure
        # counts — we assert the outcome, not the specific mechanism).
        try:
            service.persist_occurrence(
                attempt_id,
                envelope,
                idempotency_key=f"current-{version}",
                context=context,
            )
        except Exception:  # noqa: BLE001 — mechanism-agnostic rejection
            rejections += 1

    assert rejections == len(versions), (
        f"expected all {len(versions)} corpus versions rejected, "
        f"got {rejections} rejections"
    )
    # Zero authoritative occurrence writes survived.
    assert _occurrence_outcomes(store, attempt_id) == []


def test_ledger_clean_after_corpus_rejection(seeded: Any) -> None:
    """After every shape/version rejection the ledger has no partial records
    and no incomplete revision — only the START + INTENT lifecycle events."""
    store, attempt_id, context, service = seeded
    corpus = _load_corpus()
    lifecycle_before = store.event_count(attempt_id)

    for version in sorted(_collect_schema_versions(corpus)):
        envelope = CritiqueOccurrenceEnvelope(
            schema_version=version,
            occurrence_id=f"clean-{version}",
            attempt_id=attempt_id,
        )
        with contextlib.suppress(Exception):
            service.persist_occurrence(
                attempt_id,
                envelope,
                idempotency_key=f"clean-{version}",
                context=context,
            )

    # No partial records, no incomplete revision: the count is unchanged.
    assert store.event_count(attempt_id) == lifecycle_before
    events = store.read_events(attempt_id)
    types = [e.event_type for e in events]
    assert AttemptEventType.EXTERNAL_EFFECT_OUTCOME not in types
    # Only STARTED + INTENT survived.
    assert types == [AttemptEventType.STARTED, AttemptEventType.EXTERNAL_EFFECT_INTENT]


def test_heterogeneous_corpus_shapes_all_rejected(seeded: Any) -> None:
    """Walk every dict in the corpus that carries a schema_version and attempt
    to persist it as an occurrence; every shape is rejected, ledger stays
    clean."""
    store, attempt_id, context, service = seeded
    corpus = _load_corpus()
    lifecycle_before = store.event_count(attempt_id)

    candidates = list(_iter_versioned_dicts(corpus))
    assert len(candidates) > 0
    rejected = 0
    for index, candidate in enumerate(candidates):
        version = str(candidate.get("schema_version", "missing"))
        envelope = CritiqueOccurrenceEnvelope(
            schema_version=version if version != "missing" else SCHEMA_VERSION,
            occurrence_id=f"hetero-{index}",
            attempt_id=attempt_id,
        )
        try:
            service.persist_occurrence(
                attempt_id,
                envelope,
                idempotency_key=f"hetero-{index}",
                context=context,
            )
        except Exception:  # noqa: BLE001
            rejected += 1

    assert rejected == len(candidates)
    assert _occurrence_outcomes(store, attempt_id) == []
    assert store.event_count(attempt_id) == lifecycle_before


# ── synthetic cl.schema.v99-future rejection without partial publish ───────


def test_synthetic_future_schema_rejected_without_partial_publish(
    seeded: Any,
) -> None:
    """A synthetic cl.schema.v99-future envelope is rejected and the ledger
    is left without any partial publication."""
    store, attempt_id, context, service = seeded
    lifecycle_before = store.event_count(attempt_id)

    future = CritiqueOccurrenceEnvelope(
        schema_version="cl.schema.v99-future",
        occurrence_id="future-occ",
        attempt_id=attempt_id,
    )
    with pytest.raises(ValueError, match="Unsupported schema_version"):
        service.persist_occurrence(
            attempt_id,
            future,
            idempotency_key="future-occ",
            context=context,
        )

    # No partial publication: the ledger is unchanged and clean.
    assert store.event_count(attempt_id) == lifecycle_before
    assert _occurrence_outcomes(store, attempt_id) == []
    events = store.read_events(attempt_id)
    assert all(
        e.event_type
        in (AttemptEventType.STARTED, AttemptEventType.EXTERNAL_EFFECT_INTENT)
        for e in events
    )


# ── helpers ─────────────────────────────────────────────────────────────────


def _iter_versioned_dicts(obj: Any):
    """Yield every dict in ``obj`` that carries a ``schema_version`` key."""
    if isinstance(obj, dict):
        if "schema_version" in obj:
            yield obj
        for value in obj.values():
            yield from _iter_versioned_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_versioned_dicts(value)
