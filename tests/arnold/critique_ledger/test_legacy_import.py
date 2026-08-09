"""Tests for the one-time, non-authoritative legacy r5 NDJSON importer.

Verifies the filter-and-tag model:

* both legacy key forms (10-field RepairOccurrenceKey, 6-field
  CustodyTargetKey) normalize;
* every record routes through ``IndependentChildDisposition`` (never migrated);
* the original ``schema_version`` is preserved byte-for-byte (never upgraded);
* records carry ``cl2_kind = legacy_historical`` and
  ``metadata.derived_from_legacy = True``;
* missing-evidence records are labelled ``UNAVAILABLE`` with
  ``unavailable_reason = "legacy_import"`` (a labelling convention; the
  ``cl2_kind`` discriminator is the sole operative defense);
* epoch-prefixed canonical SHA-256 IDs make the same record distinct across
  epochs and make re-import idempotent within an epoch;
* the importer bypasses ``persist_occurrence`` / ``from_dict`` (appends raw
  outcomes directly);
* unsupported ``target_schema`` is rejected before any write (no partial
  publish).
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
    ImportReport,
    OneTimeImporter,
)
from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerPersistenceService,
)
from arnold.critique_ledger.schemas import EvidenceAvailability
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

_TEN_FIELD_RECORD = {
    "environment_id": "env-1",
    "session_id": "sess-1",
    "chain_id": "chain-1",
    "plan_revision": "rev-1",
    "phase": "phase-1",
    "task_id": "task-1",
    "attempt_number": 1,
    "failure_kind": "compile_error",
    "blocker_digest": "bd1",
    "coordinator_fence_token": "7",
    "schema_version": "cl.m6-corpus.v1",
    "finding_id": "finding-10",
    "evidence_ref": "durable://evidence/10",
}

_SIX_FIELD_RECORD = {
    "subject_type": "ticket",
    "subject_id": "t-1",
    "action": "repair",
    "target_kind": "file",
    "target_id": "f.py",
    "contract_id": "c-1",
    "schema_version": "arnold-resident-delegation-provenance-v1",
    "finding_id": "finding-6",
    # No evidence_* keys -> missing evidence.
}

_MISSING_EVIDENCE_RECORD = {
    "environment_id": "env-2",
    "session_id": "sess-2",
    "chain_id": "chain-2",
    "plan_revision": "rev-2",
    "phase": "phase-2",
    "task_id": "task-2",
    "attempt_number": 2,
    "failure_kind": "test_failure",
    "blocker_digest": "bd2",
    "coordinator_fence_token": "8",
    "schema_version": "megaplan-critique-custody-v1",
    "finding_id": "finding-missing",
    # No evidence_* keys -> missing evidence.
}


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-import"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-01T00:00:00+00:00",
        observed_at="2026-08-01T00:00:00+00:00",
    )


@pytest.fixture
def seeded(tmp_path: Path) -> tuple[SqliteAttemptLedgerStore, str, LedgerEventContext, LedgerPersistenceService]:
    store = SqliteAttemptLedgerStore(tmp_path / "legacy.sqlite")
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


def _write_ndjson(tmp_path: Path, name: str, records: list[dict[str, Any]]) -> Path:
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )
    return path


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


# ── normalization: both legacy key forms ────────────────────────────────────


def test_ten_field_repair_occurrence_key_normalizes(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "ten.ndjson", [_TEN_FIELD_RECORD])
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.imported == 1

    env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    key = env["metadata"]["normalized_repair_occurrence_key"]
    assert key["environment_id"] == "env-1"
    assert key["failure_kind"] == "compile_error"
    # CustodyTargetKey is derived from the 10-field repair key.
    custody = env["metadata"]["normalized_custody_target_key"]
    assert custody is not None


def test_six_field_custody_target_key_normalizes(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "six.ndjson", [_SIX_FIELD_RECORD])
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.imported == 1

    env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    custody = env["metadata"]["normalized_custody_target_key"]
    assert custody["subject_type"] == "ticket"
    assert custody["target_id"] == "f.py"


# ── IndependentChildDisposition routing ─────────────────────────────────────


def test_records_route_through_independent_child_disposition(
    seeded: Any, tmp_path: Path
) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "route.ndjson", [_TEN_FIELD_RECORD])
    OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    disp = env["metadata"]["independent_child_disposition"]
    assert disp["action"] == "start_fresh_independent_child"
    assert disp["requires_human_approval"] is True
    assert "independent child" in disp["reason"]
    assert env["metadata"]["authority_migration"] == "not_performed"


# ── schema_version preservation (never upgraded) ────────────────────────────


@pytest.mark.parametrize(
    "schema_version",
    [
        "cl.m6-corpus.v1",
        "arnold-resident-delegation-provenance-v1",
        "megaplan-critique-custody-v1",
        1,
    ],
)
def test_original_schema_version_preserved_byte_for_byte(
    seeded: Any, tmp_path: Path, schema_version: Any
) -> None:
    store, attempt_id, context, _ = seeded
    record = dict(_TEN_FIELD_RECORD)
    record["schema_version"] = schema_version
    record["finding_id"] = f"finding-{schema_version}"
    path = _write_ndjson(tmp_path, "ver.ndjson", [record])
    OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    # Preserved exactly — NOT upgraded to cl.schema.v1.
    assert env["schema_version"] == schema_version
    assert env["schema_version"] != "cl.schema.v1"


# ── non-authority tagging ───────────────────────────────────────────────────


def test_imported_records_carry_legacy_tags(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(
        tmp_path,
        "tags.ndjson",
        [_TEN_FIELD_RECORD, _SIX_FIELD_RECORD],
    )
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.imported == 2
    assert report.derived_from_legacy_count == 2

    for event in _legacy_events(store, attempt_id):
        payload = event.payload
        assert payload["cl2_kind"] == CL2_KIND_LEGACY_HISTORICAL
        env = payload["envelope"]
        assert env["metadata"]["derived_from_legacy"] is True


# ── evidence encoding (labelling convention) ────────────────────────────────


def test_missing_evidence_labelled_unavailable_with_legacy_import(
    seeded: Any, tmp_path: Path
) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "miss.ndjson", [_MISSING_EVIDENCE_RECORD])
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.legacy_unavailable_count == 1

    env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    assert env["evidence_availability"] == EvidenceAvailability.UNAVAILABLE.value
    assert env["unavailable_reason"] == LEGACY_UNAVAILABLE_REASON
    # The UNAVAILABLE encoding is a labelling convention — the importer does
    # NOT set required_for_briefing or reopen_condition on legacy records.
    assert env["metadata"].get("required_for_briefing") is not True
    assert env.get("reopen_condition") is None


def test_present_evidence_retained(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "pres.ndjson", [_TEN_FIELD_RECORD])
    OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    assert env["evidence_availability"] == EvidenceAvailability.RETAINED.value
    assert "unavailable_reason" not in env
    # The original evidence ref is preserved.
    assert env["evidence_ref"] == "durable://evidence/10"


# ── epoch-prefixed canonical IDs ────────────────────────────────────────────


def test_epoch_prefixing_distinct_across_epochs(
    seeded: Any, tmp_path: Path
) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "epoch.ndjson", [_TEN_FIELD_RECORD])
    importer = OneTimeImporter(store)

    report1 = importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    report2 = importer.import_ndjson(
        path, epoch=2, attempt_id=attempt_id, context=context
    )
    assert report1.imported == 1
    assert report2.imported == 1
    assert report1.skipped_duplicates == 0
    assert report2.skipped_duplicates == 0

    events = _legacy_events(store, attempt_id)
    assert len(events) == 2
    ids = {e.payload["envelope"]["occurrence_id"] for e in events}
    assert len(ids) == 2  # distinct across epochs
    epoch_prefixes = {eid.split("-")[1] for eid in ids}
    assert epoch_prefixes == {"1", "2"}


def test_canonical_ids_stable_within_epoch(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "stable.ndjson", [_TEN_FIELD_RECORD])
    importer = OneTimeImporter(store)
    importer.import_ndjson(path, epoch=1, attempt_id=attempt_id, context=context)
    importer.import_ndjson(path, epoch=1, attempt_id=attempt_id, context=context)

    events = _legacy_events(store, attempt_id)
    assert len(events) == 1  # deduped within epoch
    assert events[0].payload["envelope"]["occurrence_id"].startswith("legacy-1-")


# ── bypass persist_occurrence / from_dict ───────────────────────────────────


def test_outcomes_appended_directly_as_legacy_historical(
    seeded: Any, tmp_path: Path
) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "direct.ndjson", [_TEN_FIELD_RECORD])
    OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    events = _legacy_events(store, attempt_id)
    assert len(events) == 1
    event = events[0]
    # The outcome is an EXTERNAL_EFFECT_OUTCOME with the legacy discriminator,
    # appended directly (not via persist_occurrence / from_dict).
    assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
    # The envelope schema_version is non-v1, proving from_dict was bypassed
    # (from_dict would have raised ValueError for non-v1 schema_version).
    assert event.payload["envelope"]["schema_version"] != "cl.schema.v1"


# ── idempotency ─────────────────────────────────────────────────────────────


def test_reimport_is_idempotent(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(
        tmp_path,
        "idem.ndjson",
        [_TEN_FIELD_RECORD, _SIX_FIELD_RECORD, _MISSING_EVIDENCE_RECORD],
    )
    importer = OneTimeImporter(store)
    first = importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    second = importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    assert first.imported == 3
    assert second.imported == 0
    assert second.skipped_duplicates == 3
    assert store.event_count(attempt_id) == 5  # START + INTENT + 3 legacy


# ── reject unsupported target_schema without partial publish ────────────────


def test_unsupported_target_schema_rejected_without_partial_publish(
    seeded: Any, tmp_path: Path
) -> None:
    store, attempt_id, context, _ = seeded
    bad = dict(_TEN_FIELD_RECORD)
    bad["target_schema"] = "cl.schema.v99-future"
    bad["finding_id"] = "finding-future"
    path = _write_ndjson(tmp_path, "bad.ndjson", [bad])
    before = store.event_count(attempt_id)

    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    assert report.imported == 0
    assert len(report.errors) == 1
    assert "cl.schema.v99-future" in report.errors[0]
    # No partial publication: the ledger is unchanged after the rejection.
    assert store.event_count(attempt_id) == before
    assert _legacy_events(store, attempt_id) == []


def test_supported_target_schema_imported(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    rec = dict(_TEN_FIELD_RECORD)
    rec["target_schema"] = "cl.schema.v1"
    rec["finding_id"] = "finding-v1target"
    path = _write_ndjson(tmp_path, "oktarget.ndjson", [rec])
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.imported == 1
    assert report.errors == ()


# ── ImportReport shape ──────────────────────────────────────────────────────


def test_import_report_shape(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(
        tmp_path,
        "shape.ndjson",
        [_TEN_FIELD_RECORD, _MISSING_EVIDENCE_RECORD],
    )
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=3, attempt_id=attempt_id, context=context
    )
    assert isinstance(report, ImportReport)
    assert report.total_records == 2
    assert report.imported == 2
    assert report.skipped_duplicates == 0
    assert report.epoch_prefixes == (3,)
    assert report.epoch_prefixes_set == frozenset({3})
    assert report.legacy_unavailable_count == 1
    assert report.errors == ()
    assert report.derived_from_legacy_count == 2


def test_invalid_json_record_recorded_as_error(seeded: Any, tmp_path: Path) -> None:
    store, attempt_id, context, _ = seeded
    path = tmp_path / "badjson.ndjson"
    path.write_text("{not valid json\n", encoding="utf-8")
    report = OneTimeImporter(store).import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.total_records == 1
    assert report.imported == 0
    assert len(report.errors) == 1
    assert _legacy_events(store, attempt_id) == []


# ── T6: idempotent re-import and stable unavailable-evidence labels ─────────


def test_reimport_appends_nothing_and_counts_duplicates(
    seeded: Any, tmp_path: Path
) -> None:
    """A second import of the same file/epoch appends zero new events.

    Every record is counted as a skipped duplicate; the persisted event set is
    byte-identical to the first import (no new sequences).
    """
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(
        tmp_path,
        "t6-idem.ndjson",
        [_TEN_FIELD_RECORD, _SIX_FIELD_RECORD, _MISSING_EVIDENCE_RECORD],
    )
    importer = OneTimeImporter(store)
    first = importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    events_after_first = store.read_events(attempt_id)
    seqs_after_first = [e.sequence for e in events_after_first]

    second = importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    # Second import appends nothing.
    assert second.imported == 0
    # Every record is counted as a duplicate.
    assert second.skipped_duplicates == 3
    assert second.total_records == 3
    # The persisted stream is unchanged: no new sequences.
    assert [e.sequence for e in store.read_events(attempt_id)] == seqs_after_first
    # START + INTENT + the 3 legacy records from the first import.
    assert store.event_count(attempt_id) == first.imported + 2


def test_unavailable_evidence_labels_stable_across_reimport(
    seeded: Any, tmp_path: Path
) -> None:
    """The UNAVAILABLE label is byte-stable across re-import (dedup wins).

    Re-importing returns the *existing* persisted envelope unchanged, so the
    ``UNAVAILABLE`` evidence class and ``legacy_import`` reason are stable.
    """
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "t6-stable.ndjson", [_MISSING_EVIDENCE_RECORD])
    importer = OneTimeImporter(store)
    importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )

    first_env = _legacy_events(store, attempt_id)[0].payload["envelope"]
    # Re-import the same file/epoch.
    report = importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    assert report.imported == 0
    assert report.skipped_duplicates == 1

    # Still exactly one persisted record; its label is identical.
    events = _legacy_events(store, attempt_id)
    assert len(events) == 1
    stable_env = events[0].payload["envelope"]
    assert stable_env == first_env
    assert stable_env["evidence_availability"] == EvidenceAvailability.UNAVAILABLE.value
    assert stable_env["unavailable_reason"] == LEGACY_UNAVAILABLE_REASON


def test_unavailable_labels_stable_and_distinct_across_epochs(
    seeded: Any, tmp_path: Path
) -> None:
    """The same missing-evidence record imported in two epochs remains
    distinct (different epoch-prefixed IDs) while both carry the stable
    ``UNAVAILABLE`` / ``legacy_import`` label."""
    store, attempt_id, context, _ = seeded
    path = _write_ndjson(tmp_path, "t6-epoch.ndjson", [_MISSING_EVIDENCE_RECORD])
    importer = OneTimeImporter(store)
    importer.import_ndjson(
        path, epoch=1, attempt_id=attempt_id, context=context
    )
    importer.import_ndjson(
        path, epoch=2, attempt_id=attempt_id, context=context
    )

    events = _legacy_events(store, attempt_id)
    assert len(events) == 2  # distinct across epochs (not deduped away)
    ids = {e.payload["envelope"]["occurrence_id"] for e in events}
    assert len(ids) == 2
    # Both carry the stable unavailable label.
    for event in events:
        env = event.payload["envelope"]
        assert env["evidence_availability"] == EvidenceAvailability.UNAVAILABLE.value
        assert env["unavailable_reason"] == LEGACY_UNAVAILABLE_REASON
