from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from arnold_pipelines.megaplan.source_cursor_contract import SourceCursorVector
from arnold_pipelines.run_authority import (
    EvidenceEnvelope,
    GLEKConflictError,
    IdempotencyConflictError,
    InvalidAuthorityRecordError,
    InvalidCursorError,
    JournalCommitIndeterminateError,
    JournalCorruptionError,
    JournalStorageError,
    RunAuthorityJournal,
    StaleCursorError,
)


RUN = "run-journal"
REVISION = "revision-1"


def _evidence(
    evidence_id: str,
    *,
    payload: object = None,
    run_id: str = RUN,
    revision: str = REVISION,
) -> EvidenceEnvelope:
    if payload is None:
        payload = {"ok": True, "evidence_id": evidence_id}
    return EvidenceEnvelope(
        evidence_id=evidence_id,
        run_id=run_id,
        run_revision=revision,
        evidence_type="test",
        source="test://journal",
        payload=payload,
    )


def test_read_view_and_append_return_contracts_and_integer_cursor(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")

    records, cursor = journal.read_view(RUN, REVISION)
    assert records == ()
    assert cursor == 0
    assert type(cursor) is int

    first = journal.compare_and_append(RUN, REVISION, 0, _evidence("ev-1"))
    assert first.cursor == 1
    assert first.is_duplicate is False
    assert type(first.cursor) is int
    assert first.glek.startswith("glek:")

    view = journal.read_view(RUN, REVISION)
    assert view.records == (_evidence("ev-1"),)
    assert view.cursor == 1
    unpacked_records, unpacked_cursor = view
    assert unpacked_records == view.records
    assert unpacked_cursor == view.cursor


def test_stale_cursor_is_a_real_compare_against_durable_head(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    journal.compare_and_append(RUN, REVISION, 0, _evidence("ev-1"))

    with pytest.raises(StaleCursorError):
        journal.compare_and_append(RUN, REVISION, 0, _evidence("ev-2"))

    view = journal.read_view(RUN, REVISION)
    assert view.cursor == 1
    assert [record.evidence_id for record in view.records] == ["ev-1"]


def test_same_key_same_payload_is_a_content_safe_noop_even_with_stale_cursor(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    original = _evidence("ev-1")
    written = journal.compare_and_append(
        RUN, REVISION, 0, original, idempotency_key="operation-1"
    )

    retry = journal.compare_and_append(
        RUN, REVISION, 0, _evidence("ev-1"), idempotency_key="operation-1", glek=written.glek
    )
    assert retry.is_duplicate is True
    assert retry.cursor == written.cursor == 1
    assert retry.record == written.record == original
    assert retry.glek == written.glek
    assert journal.read_view(RUN, REVISION).cursor == 1


def test_retrying_any_existing_record_does_not_decode_it_as_new_genesis(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    first = _evidence("ev-1")
    second = _evidence("ev-2")
    journal.compare_and_append(RUN, REVISION, 0, first)
    journal.compare_and_append(RUN, REVISION, 1, second)

    retry = journal.compare_and_append(RUN, REVISION, 0, second)
    assert retry.is_duplicate is True
    assert retry.cursor == 2
    assert journal.read_view(RUN, REVISION).cursor == 2


def test_same_key_divergent_payload_is_rejected_without_a_synthetic_record(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    journal.compare_and_append(
        RUN, REVISION, 0, _evidence("ev-1", payload={"value": 1}), idempotency_key="operation-1"
    )

    with pytest.raises(IdempotencyConflictError):
        journal.compare_and_append(
            RUN,
            REVISION,
            0,
            _evidence("ev-2", payload={"value": 2}),
            idempotency_key="operation-1",
        )

    view = journal.read_view(RUN, REVISION)
    assert view.cursor == 1
    assert [record.evidence_id for record in view.records] == ["ev-1"]


def test_glek_is_unique_across_views_and_stable_on_retry(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    first = journal.compare_and_append(
        RUN, REVISION, 0, _evidence("ev-1"), glek="glek:one"
    )
    retry = journal.compare_and_append(
        RUN, REVISION, 0, _evidence("ev-1"), glek="glek:one"
    )
    assert retry.is_duplicate is True
    assert retry.glek == first.glek == "glek:one"

    with pytest.raises(GLEKConflictError):
        journal.compare_and_append(
            RUN, REVISION, 0, _evidence("ev-1"), glek="glek:other"
        )

    with pytest.raises(GLEKConflictError):
        journal.compare_and_append(
            "other-run",
            "revision-2",
            0,
            _evidence("ev-other", run_id="other-run", revision="revision-2"),
            glek="glek:one",
        )

    with pytest.raises(GLEKConflictError):
        journal.compare_and_append(
            RUN, REVISION, 1, _evidence("ev-2"), glek="glek:one"
        )
    assert journal.read_view(RUN, REVISION).cursor == 1


@pytest.mark.parametrize("bad_cursor", [True, False, "0", 0.0, -1])
def test_cursor_is_strictly_an_integer_and_never_coerced(tmp_path: Path, bad_cursor: object) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    with pytest.raises(InvalidCursorError):
        journal.compare_and_append(RUN, REVISION, bad_cursor, _evidence("ev-1"))  # type: ignore[arg-type]


def test_source_cursor_vector_and_mapping_cannot_become_authority_or_cursor(tmp_path: Path) -> None:
    journal = RunAuthorityJournal(tmp_path / "authority.db")
    vector = SourceCursorVector.all_unknown(observed_at="now")

    with pytest.raises(InvalidCursorError):
        journal.compare_and_append(RUN, REVISION, vector, _evidence("ev-1"))  # type: ignore[arg-type]
    with pytest.raises(InvalidCursorError):
        journal.compare_and_append(RUN, REVISION, vector.vector_id, _evidence("ev-1"))  # type: ignore[arg-type]
    with pytest.raises(InvalidAuthorityRecordError):
        journal.compare_and_append(RUN, REVISION, 0, {"record": _evidence("ev-1")})  # type: ignore[arg-type]
    assert journal.read_view(RUN, REVISION).records == ()


def test_concurrent_writers_use_one_durable_cursor_winner(tmp_path: Path) -> None:
    database = tmp_path / "authority.db"
    journals = (RunAuthorityJournal(database), RunAuthorityJournal(database))
    barrier = Barrier(2)

    def append(index: int):
        barrier.wait()
        try:
            return journals[index].compare_and_append(RUN, REVISION, 0, _evidence(f"ev-{index}"))
        except Exception as exc:  # return for deterministic assertions below
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(append, (0, 1)))

    winners = [outcome for outcome in outcomes if not isinstance(outcome, Exception)]
    losers = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
    assert len(winners) == 1
    assert len(losers) == 1
    assert isinstance(losers[0], StaleCursorError)
    view = RunAuthorityJournal(database).read_view(RUN, REVISION)
    assert view.cursor == 1
    assert len(view.records) == 1


def test_crash_before_commit_rolls_back_without_synthetic_authority(tmp_path: Path) -> None:
    def fail(stage: str) -> None:
        if stage == "before_commit":
            raise RuntimeError("simulated crash")

    database = tmp_path / "authority.db"
    journal = RunAuthorityJournal(database, fault_hook=fail)
    with pytest.raises(JournalStorageError):
        journal.compare_and_append(RUN, REVISION, 0, _evidence("ev-1"))
    assert RunAuthorityJournal(database).read_view(RUN, REVISION).records == ()


def test_crash_after_commit_is_reconciled_by_reread_and_idempotent_retry(tmp_path: Path) -> None:
    def fail(stage: str) -> None:
        if stage == "after_commit":
            raise RuntimeError("ack lost")

    database = tmp_path / "authority.db"
    journal = RunAuthorityJournal(database, fault_hook=fail)
    with pytest.raises(JournalCommitIndeterminateError):
        journal.compare_and_append(RUN, REVISION, 0, _evidence("ev-1"))

    restarted = RunAuthorityJournal(database)
    view = restarted.read_view(RUN, REVISION)
    assert view.cursor == 1
    assert view.records == (_evidence("ev-1"),)
    retry = restarted.compare_and_append(RUN, REVISION, 0, _evidence("ev-1"))
    assert retry.is_duplicate is True
    assert retry.cursor == 1


def test_hash_chain_corruption_is_detected_without_repairing_or_inventing_rows(tmp_path: Path) -> None:
    database = tmp_path / "authority.db"
    journal = RunAuthorityJournal(database)
    journal.compare_and_append(RUN, REVISION, 0, _evidence("ev-1"))

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE authority_journal_records SET record_hash = ? WHERE run_id = ?",
            ("corrupted", RUN),
        )

    with pytest.raises(JournalCorruptionError):
        journal.read_view(RUN, REVISION)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM authority_journal_records").fetchone()[0] == 1
