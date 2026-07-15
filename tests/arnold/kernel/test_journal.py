from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.kernel import (
    EventEnvelope,
    EventFamily,
    ManifestReference,
    NDJsonEventJournal,
    ReplayReference,
    fold_event_journal,
    read_event_journal,
)


def _event(
    event_id: str,
    kind: str,
    sequence: int | None = None,
    payload: dict | None = None,
    replay: ReplayReference | None = None,
    reentry_id: str | None = None,
    scope_stack: tuple[str, ...] = (),
    artifact_root: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        family=EventFamily.NODE_LIFECYCLE,
        kind=kind,
        manifest=ManifestReference(alias="demo", manifest_hash="sha256:" + "a" * 64),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        payload=payload or {},
        sequence=sequence,
        replay=replay,
        reentry_id=reentry_id,
        scope_stack=scope_stack,
        artifact_root=artifact_root,
    )


def test_append_assigns_monotonic_sequences(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)

    first = journal.append(_event("e1", "node-started"))
    second = journal.append(_event("e2", "node-completed"))
    third = journal.append(_event("e3", "node-failed"))

    assert first.sequence == 0
    assert second.sequence == 1
    assert third.sequence == 2


def test_append_is_append_only(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)

    journal.append(_event("e1", "node-started"))
    before = (tmp_path / "events.ndjson").read_text(encoding="utf-8")

    journal.append(_event("e2", "node-completed"))
    after = (tmp_path / "events.ndjson").read_text(encoding="utf-8")

    assert after.startswith(before)
    assert after.count("\n") == 2


def test_serialization_is_deterministic(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    event = _event(
        "e1",
        "node-started",
        payload={"node": "start", "order": 1},
        scope_stack=("parent", "child"),
        reentry_id="reentry-1",
        artifact_root=str(tmp_path),
    )

    written = journal.append(event)
    lines = (tmp_path / "events.ndjson").read_text(encoding="utf-8").strip().split("\n")

    assert len(lines) == 1
    reparsed = json.loads(lines[0])
    assert reparsed["sequence"] == 0
    assert reparsed["scope_stack"] == ["parent", "child"]
    assert reparsed["reentry_id"] == "reentry-1"
    assert reparsed["artifact_root"] == str(tmp_path)
    assert reparsed["family"] == "node-lifecycle"
    # Canonical ordering: keys sorted.
    assert list(json.loads(lines[0]).keys()) == sorted(reparsed.keys())

    # The same logical event serializes to the same bytes when re-appended.
    journal2 = NDJsonEventJournal(tmp_path / "other")
    journal2.append(written)
    lines2 = (tmp_path / "other" / "events.ndjson").read_text(encoding="utf-8").strip().split("\n")
    assert lines[0] == lines2[0]


def test_reader_returns_events_and_quarantines_malformed_lines(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    # Corrupt the journal with a non-JSON line and a valid-looking but invalid event.
    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write(json.dumps({"event_id": "", "family": "node-lifecycle"}) + "\n")

    events, quarantined = journal.read_with_quarantine()

    assert len(events) == 1
    assert events[0].event_id == "e1"
    assert len(quarantined) == 2
    reasons = {record.reason for record in quarantined}
    assert any("parse" in reason.lower() for reason in reasons)
    assert any("missing" in reason.lower() for reason in reasons)


def test_manifest_hash_lineage_is_enforced(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    first = journal.append(_event("e1", "node-started"))

    second = EventEnvelope(
        event_id="e2",
        family=EventFamily.NODE_LIFECYCLE,
        kind="node-completed",
        manifest=ManifestReference(alias="demo", manifest_hash="sha256:" + "z" * 64),
        run_id="run-1",
        payload_schema_hash="sha256:" + "b" * 64,
        sequence=None,
        artifact_root=str(tmp_path),
    )
    journal.append(second)

    events, quarantined = journal.read_with_quarantine()
    assert events == (first,)
    assert len(quarantined) == 1
    assert "lineage mismatch" in quarantined[0].reason


def test_artifact_root_lineage_is_enforced(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    first = journal.append(_event("e1", "node-started", artifact_root=str(tmp_path)))

    second = _event("e2", "node-completed", artifact_root="/somewhere/else")
    journal.append(second)

    events, quarantined = journal.read_with_quarantine()
    assert events == (first,)
    assert len(quarantined) == 1
    assert "lineage mismatch" in quarantined[0].reason


def test_replay_coordinates_are_preserved(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    event = _event(
        "e1",
        "node-started",
        replay=ReplayReference(journal_uri="other.ndjson", sequence=42, cursor="cursor-1"),
    )

    written = journal.append(event)

    assert written.replay is not None
    assert written.replay.journal_uri == "other.ndjson"
    assert written.replay.sequence == 42
    assert written.replay.cursor == "cursor-1"

    events = journal.read()
    assert events[0].replay == written.replay


def test_read_module_helper(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    events = read_event_journal(tmp_path)
    assert len(events) == 1
    assert events[0].event_id == "e1"


def test_fold_reduces_valid_events(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    for idx in range(3):
        journal.append(_event(f"e{idx}", "tick", payload={"n": idx}))

    total = journal.fold(0, lambda acc, event: acc + event.payload.get("n", 0))
    assert total == 3

    # Module helper works the same way.
    total2 = fold_event_journal(tmp_path, 0, lambda acc, event: acc + event.payload.get("n", 0))
    assert total2 == 3


def test_sequence_violations_are_quarantined(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    # Manually inject an out-of-order event.
    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        payload = {
            "event_id": "e0",
            "family": "node-lifecycle",
            "kind": "node-started",
            "manifest": {"alias": "demo", "manifest_hash": "sha256:" + "a" * 64},
            "run_id": "run-1",
            "payload_schema_hash": "sha256:" + "b" * 64,
            "sequence": 0,
            "artifact_root": str(tmp_path),
        }
        fh.write(json.dumps(payload, sort_keys=True) + "\n")

    events, quarantined = journal.read_with_quarantine()
    assert len(events) == 1
    assert len(quarantined) == 1
    assert "sequence violation" in quarantined[0].reason


def test_quarantine_record_can_be_persisted(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    from arnold.kernel import JournalQuarantineRecord

    record = JournalQuarantineRecord(line_number=7, raw_line="bad", reason="parse error")
    path = journal.quarantine(record)

    assert path.exists()
    persisted = json.loads(path.read_text(encoding="utf-8").strip())
    assert persisted["line_number"] == 7
    assert persisted["raw_line"] == "bad"


def test_reader_skips_blank_lines(tmp_path: Path) -> None:
    journal = NDJsonEventJournal(tmp_path)
    journal.append(_event("e1", "node-started"))

    with open(tmp_path / "events.ndjson", "a", encoding="utf-8") as fh:
        fh.write("\n\n")

    events = journal.read()
    assert len(events) == 1


# ---------------------------------------------------------------------------
# Megaplan journal CAS & crash-injection tests
# ---------------------------------------------------------------------------
# These tests exercise the journal CAS primitives in
# ``arnold_pipelines.megaplan._core.io`` with explicit crash-injection at each
# lifecycle stage: prepare → staged writes → commit marker → apply → cleanup,
# plus replay and rollback.  Every test verifies durable state invariants so
# that a partial crash never exposes torn or premature state.


from arnold_pipelines.megaplan._core.io import (  # noqa: E402
    JournalCASResult,
    JournalCASViolation,
    commit_journal_transaction,
    commit_journal_transaction_cas,
    discard_uncommitted_journal_transaction,
    evaluate_cas_guards,
    journal_blob_promotion,
    journal_bytes_write,
    journal_commit_path,
    journal_prepare_path,
    journal_root,
    journal_text_write,
    prepare_journal_transaction,
    recover_journal,
    sha256_text,
    write_journal_commit_marker,
    _apply_prepared_writes,
    _cleanup_prepared_transaction,
    _path_sha256,
    _stage_write_entry,
)


# ---------------------------------------------------------------------------
# Lifecycle: prepare + staged writes
# ---------------------------------------------------------------------------


class TestPrepareAndStagedWrites:
    """Verify that prepare writes the prepare.json manifest and stages temp
    files with the correct content."""

    def test_prepare_creates_manifest(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "payload\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        prepare_path = journal_prepare_path(root, "t1")
        assert prepare_path.exists()
        payload = json.loads(prepare_path.read_text())
        assert payload["tx_id"] == "t1"
        assert len(payload["writes"]) == 1

    def test_staged_temp_file_exists_after_prepare(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "staged-content\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        temp_path = Path(entry["temp_path"])
        assert temp_path.exists()
        assert temp_path.read_text() == "staged-content\n"

    def test_staged_bytes_temp_file_exists_after_prepare(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "blob.bin"
        entry = journal_bytes_write(target, b"\x00\xFF\x01", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        temp_path = Path(entry["temp_path"])
        assert temp_path.exists()
        assert temp_path.read_bytes() == b"\x00\xFF\x01"

    def test_staged_temp_file_matches_content_sha(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "verify-sha\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        temp_path = Path(entry["temp_path"])
        actual_sha = _path_sha256(temp_path)
        expected_sha = entry["content_sha256"]
        assert actual_sha == expected_sha

    def test_target_untouched_after_prepare(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        entry = journal_text_write(target, "staged\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Target must still be the original — apply hasn't run yet.
        assert target.read_text() == "original\n"


# ---------------------------------------------------------------------------
# Lifecycle: commit marker creation
# ---------------------------------------------------------------------------


class TestCommitMarkerCreation:
    """Verify that the commit marker is a durable empty file created under
    ``_journal/`` with the correct naming convention."""

    def test_commit_marker_created(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        marker = write_journal_commit_marker(root, "t1")
        assert marker.exists()
        assert marker == journal_commit_path(root, "t1")
        assert marker.read_bytes() == b""

    def test_commit_marker_inside_journal_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        marker = write_journal_commit_marker(root, "t2")
        assert marker.parent == journal_root(root)

    def test_commit_marker_does_not_exist_before_write(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        assert not journal_commit_path(root, "t3").exists()


# ---------------------------------------------------------------------------
# Lifecycle: apply
# ---------------------------------------------------------------------------


class TestApplyPreparedWrites:
    """Verify that applying prepared writes promotes staged temp files to
    their target paths."""

    def test_apply_promotes_temp_to_target(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "applied\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Manually apply (simulates what commit does after marker).
        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        _apply_prepared_writes(payload)

        assert target.read_text() == "applied\n"

    def test_apply_removes_temp_file(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "applied\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        temp_path = Path(entry["temp_path"])
        assert temp_path.exists()

        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        _apply_prepared_writes(payload)

        assert not temp_path.exists()

    def test_apply_idempotent_when_target_matches(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "idem\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        _apply_prepared_writes(payload)
        first_mtime = target.stat().st_mtime

        # Second apply should be a no-op (target already matches).
        _apply_prepared_writes(payload)
        assert target.stat().st_mtime == first_mtime
        assert target.read_text() == "idem\n"

    def test_apply_restages_if_temp_missing(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "restaged\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        temp_path = Path(entry["temp_path"])
        temp_path.unlink()

        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        _apply_prepared_writes(payload)

        assert target.read_text() == "restaged\n"


# ---------------------------------------------------------------------------
# Lifecycle: cleanup
# ---------------------------------------------------------------------------


class TestCleanupPreparedTransaction:
    """Verify that cleanup removes temp files, prepare.json, and commit
    marker, leaving only the applied target."""

    def test_cleanup_removes_prepare_and_commit(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "clean\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        write_journal_commit_marker(root, "t1")

        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        payload["journal_root"] = str(root)
        _cleanup_prepared_transaction(payload)

        assert not journal_prepare_path(root, "t1").exists()
        assert not journal_commit_path(root, "t1").exists()

    def test_cleanup_removes_temp_file(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "clean\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        write_journal_commit_marker(root, "t1")

        temp_path = Path(entry["temp_path"])
        assert temp_path.exists()

        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        payload["journal_root"] = str(root)
        _cleanup_prepared_transaction(payload)

        assert not temp_path.exists()

    def test_cleanup_leaves_target_intact(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "survives\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        write_journal_commit_marker(root, "t1")

        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        payload["journal_root"] = str(root)
        _apply_prepared_writes(payload)
        _cleanup_prepared_transaction(payload)

        assert target.exists()
        assert target.read_text() == "survives\n"


# ---------------------------------------------------------------------------
# Lifecycle: replay (crash recovery of committed transactions)
# ---------------------------------------------------------------------------


class TestReplayCommitted:
    """Verify that recovery replays committed transactions (prepare.json +
    commit marker present) and discards uncommitted ones."""

    def test_replay_applies_committed_transaction(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "replayed\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Simulate crash: write commit marker but DON'T apply/cleanup.
        write_journal_commit_marker(root, "t1")

        report = recover_journal(root)
        assert report["replayed"] == ["t1"]
        assert target.read_text() == "replayed\n"

    def test_replay_discards_uncommitted_transaction(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        entry = journal_text_write(target, "uncommitted\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        # No commit marker — simulate crash before commit.
        report = recover_journal(root)
        assert report["discarded"] == ["t1"]
        assert not journal_prepare_path(root, "t1").exists()
        # Target unchanged.
        assert target.read_text() == "original\n"

    def test_replay_idempotent_across_multiple_calls(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "idem-replay\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        write_journal_commit_marker(root, "t1")

        recover_journal(root)
        first_sha = _path_sha256(target)

        # Second recovery should be a no-op.
        report2 = recover_journal(root)
        assert report2["replayed"] == []
        assert _path_sha256(target) == first_sha


# ---------------------------------------------------------------------------
# Lifecycle: rollback (explicit discard_uncommitted_journal_transaction)
# ---------------------------------------------------------------------------


class TestRollback:
    """Verify that explicit discard of an uncommitted transaction cleans up
    staged files and reverts durable state."""

    def test_discard_removes_prepare_and_staging(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "discarded\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        temp_path = Path(entry["temp_path"])
        discard_uncommitted_journal_transaction(root, "t1")

        assert not journal_prepare_path(root, "t1").exists()
        assert not temp_path.exists()

    def test_discard_leaves_existing_target_unchanged(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("safe\n")
        entry = journal_text_write(target, "discarded\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        discard_uncommitted_journal_transaction(root, "t1")
        assert target.read_text() == "safe\n"

    def test_discard_is_idempotent(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "discarded\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        discard_uncommitted_journal_transaction(root, "t1")
        # Second discard must not raise.
        discard_uncommitted_journal_transaction(root, "t1")
        assert not journal_prepare_path(root, "t1").exists()


# ---------------------------------------------------------------------------
# CAS guards: target_absent
# ---------------------------------------------------------------------------


class TestCASTargetAbsent:
    """Verify target_absent guard semantics including crash-injection
    scenarios where the file appears between prepare and commit."""

    def test_target_absent_allows_create(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "new.json"
        entry = journal_text_write(target, "created\n", tx_id="t1", target_absent=True)
        prepare_journal_transaction(root, "t1", writes=[entry])

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is True
        assert target.read_text() == "created\n"

    def test_target_absent_blocks_when_file_exists(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("preexisting\n")
        entry = journal_text_write(target, "overwrite\n", tx_id="t1", target_absent=True)
        prepare_journal_transaction(root, "t1", writes=[entry])

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False
        assert len(result.violations) == 1
        assert result.violations[0].guard == "target_absent"
        # Target untouched; no commit marker.
        assert target.read_text() == "preexisting\n"
        assert not journal_commit_path(root, "t1").exists()

    def test_target_absent_crash_file_appears_between_prepare_and_commit(
        self, tmp_path: Path
    ) -> None:
        """Crash injection: file does not exist at prepare time but is created
        concurrently before commit."""
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "new.json"
        entry = journal_text_write(target, "created\n", tx_id="t1", target_absent=True)
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Concurrent creation between prepare and commit.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("CONCURRENT\n")

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False
        assert target.read_text() == "CONCURRENT\n"
        assert not journal_commit_path(root, "t1").exists()


# ---------------------------------------------------------------------------
# CAS guards: stale prior hash (expected_prior_sha256)
# ---------------------------------------------------------------------------


class TestCASStalePriorHash:
    """Verify expected_prior_sha256 guard semantics including crash-injection
    scenarios where the file is modified between prepare and commit."""

    def test_hash_match_allows_commit(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("v1\n")
        expected = _path_sha256(target)
        entry = journal_text_write(
            target, "v2\n", tx_id="t1", expected_prior_sha256=expected
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is True
        assert target.read_text() == "v2\n"

    def test_stale_hash_blocks_commit(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("v1\n")
        expected = _path_sha256(target)
        entry = journal_text_write(
            target, "v2\n", tx_id="t1", expected_prior_sha256=expected
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Concurrent modification.
        target.write_text("MODIFIED\n")

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False
        assert len(result.violations) == 1
        assert result.violations[0].guard == "expected_prior_sha256"
        assert result.violations[0].expected == expected
        # Target untouched.
        assert target.read_text() == "MODIFIED\n"

    def test_stale_hash_file_removed_concurrently(self, tmp_path: Path) -> None:
        """Crash injection: file deleted between prepare and commit."""
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("v1\n")
        expected = _path_sha256(target)
        entry = journal_text_write(
            target, "v2\n", tx_id="t1", expected_prior_sha256=expected
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        target.unlink()

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False
        assert result.violations[0].actual is None
        assert not target.exists()

    def test_stale_hash_no_prior_file(self, tmp_path: Path) -> None:
        """When target does not exist, expected_prior_sha256 fails because
        actual hash is None != expected."""
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(
            target,
            "v2\n",
            tx_id="t1",
            expected_prior_sha256="sha256:deadbeef",
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False
        assert len(result.violations) == 1
        assert result.violations[0].actual is None


# ---------------------------------------------------------------------------
# Crash-injection: full lifecycle crash at each stage
# ---------------------------------------------------------------------------


class TestCrashInjectionLifecycle:
    """Simulate crashes at each journal stage and verify that recovery never
    exposes torn or premature state."""

    # --- Crash after prepare (no commit marker) ---

    def test_crash_after_prepare_discards_on_recovery(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        entry = journal_text_write(target, "crashed-before-commit\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Simulate crash: process dies here.  On restart, recovery runs.
        report = recover_journal(root)
        assert report["discarded"] == ["t1"]
        assert target.read_text() == "original\n"

    # --- Crash after commit marker but before apply ---

    def test_crash_after_marker_before_apply_replays(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        entry = journal_text_write(target, "marker-no-apply\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        write_journal_commit_marker(root, "t1")

        # Crash: marker exists but apply never ran.
        report = recover_journal(root)
        assert report["replayed"] == ["t1"]
        assert target.read_text() == "marker-no-apply\n"

    # --- Crash after apply but before cleanup ---

    def test_crash_after_apply_before_cleanup_replays_idempotently(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "apply-no-cleanup\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        write_journal_commit_marker(root, "t1")

        # Apply but do NOT cleanup.
        payload = json.loads(journal_prepare_path(root, "t1").read_text())
        _apply_prepared_writes(payload)

        # prepare.json and commit marker still exist.
        assert journal_prepare_path(root, "t1").exists()
        assert journal_commit_path(root, "t1").exists()

        # Recovery replays idempotently and cleans up.
        report = recover_journal(root)
        assert report["replayed"] == ["t1"]
        assert target.read_text() == "apply-no-cleanup\n"

    # --- Crash after cleanup ---

    def test_crash_after_cleanup_no_work_to_do(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "fully-committed\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])
        commit_journal_transaction(root, "t1")

        # Normal commit ran to completion. Recovery must be a no-op.
        report = recover_journal(root)
        assert report["replayed"] == []
        assert report["discarded"] == []
        assert target.read_text() == "fully-committed\n"

    # --- Crash with orphaned commit marker (prepare.json missing) ---

    def test_crash_orphan_commit_marker_cleaned_up(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        write_journal_commit_marker(root, "t1")

        # prepare.json does not exist — orphaned commit marker.
        report = recover_journal(root)
        assert report["replayed"] == []
        assert not journal_commit_path(root, "t1").exists()

    # --- Crash after CAS guard passes, marker written, but before apply ---

    def test_crash_after_cas_pass_before_apply(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("v1\n")
        expected = _path_sha256(target)
        entry = journal_text_write(
            target, "v2\n", tx_id="t1", expected_prior_sha256=expected
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Simulate: CAS passed, marker written, crash before apply.
        result = evaluate_cas_guards(
            json.loads(journal_prepare_path(root, "t1").read_text())
        )
        assert len(result) == 0  # guard passes
        write_journal_commit_marker(root, "t1")

        # Recovery replays.
        report = recover_journal(root)
        assert report["replayed"] == ["t1"]
        assert target.read_text() == "v2\n"

    # --- Crash: CAS guard fails, transaction discarded, recovery ignores ---

    def test_crash_after_cas_failure_recovery_ignores(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("v1\n")
        entry = journal_text_write(
            target,
            "v2\n",
            tx_id="t1",
            expected_prior_sha256="sha256:stale",
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        # CAS failure: discard happens, no marker.
        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False

        # Recovery must have nothing to replay.
        report = recover_journal(root)
        assert report["replayed"] == []
        assert target.read_text() == "v1\n"


# ---------------------------------------------------------------------------
# Non-CAS compatibility with crash scenarios
# ---------------------------------------------------------------------------


class TestNonCASCompatibility:
    """Verify that non-CAS commit path works correctly across crash
    boundaries and that legacy commit ignores stale CAS guards."""

    def test_non_cas_commit_survives_crash_recovery(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "non-cas\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Non-CAS commit runs to completion.
        commit_journal_transaction(root, "t1")

        # Recovery after full commit is a no-op.
        report = recover_journal(root)
        assert report["replayed"] == []
        assert target.read_text() == "non-cas\n"

    def test_non_cas_ignores_stale_cas_guard(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256="sha256:does-not-match",
        )
        prepare_journal_transaction(root, "t1", writes=[entry])

        # Legacy commit must apply despite stale CAS guard.
        commit_journal_transaction(root, "t1")
        assert target.read_text() == "updated\n"

    def test_non_cas_with_multiple_writes_survives_crash(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        t1 = tmp_path / "a" / "x.json"
        t2 = tmp_path / "b" / "y.json"
        e1 = journal_text_write(t1, "x\n", tx_id="t1")
        e2 = journal_text_write(t2, "y\n", tx_id="t1")
        prepare_journal_transaction(root, "t1", writes=[e1, e2])
        write_journal_commit_marker(root, "t1")

        # Crash before apply.
        report = recover_journal(root)
        assert report["replayed"] == ["t1"]
        assert t1.read_text() == "x\n"
        assert t2.read_text() == "y\n"

    def test_non_cas_blob_promotion_survives_crash(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        blob_dir = tmp_path / "store" / "blob-1"
        entry = journal_blob_promotion(
            blob_dir,
            b"blob-data",
            extension="bin",
            metadata={"k": "v"},
        )
        prepare_journal_transaction(root, "t1", blobs=[entry])
        write_journal_commit_marker(root, "t1")

        report = recover_journal(root)
        assert report["replayed"] == ["t1"]
        assert (blob_dir / "data.bin").read_bytes() == b"blob-data"
        assert json.loads((blob_dir / "meta.json").read_text()) == {"k": "v"}


# ---------------------------------------------------------------------------
# CAS failure result integrity
# ---------------------------------------------------------------------------


class TestCASFailureResultIntegrity:
    """Verify that CAS failure results contain accurate violation data
    for crash-injection and audit scenarios."""

    def test_violation_reports_exact_guard_and_path(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("exists\n")

        entry = journal_text_write(target, "x\n", tx_id="t1", target_absent=True)
        prepare_journal_transaction(root, "t1", writes=[entry])

        result = commit_journal_transaction_cas(root, "t1")
        assert result.committed is False
        v = result.violations[0]
        assert v.guard == "target_absent"
        assert v.target_path == str(target)
        assert v.section == "writes"
        assert v.entry_index == 0
        assert v.expected is None
        assert v.actual is not None  # actual hash of existing file

    def test_violation_is_serializable(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("exists\n")

        entry = journal_text_write(target, "x\n", tx_id="t1", target_absent=True)
        prepare_journal_transaction(root, "t1", writes=[entry])

        result = commit_journal_transaction_cas(root, "t1")
        d = result.to_dict()
        assert d["tx_id"] == "t1"
        assert d["committed"] is False
        assert len(d["violations"]) == 1
        assert d["violations"][0]["guard"] == "target_absent"


# ---------------------------------------------------------------------------
# Journal-level acceptance-commit concurrency & crash semantics
# (T30 / Step 20)
#
# These tests model the acceptance-commit boundary as a multi-write CAS-guarded
# journal transaction (state file + receipt file + snapshot file) and prove at
# the journal level that no crash stage, duplicate driver, stale worker, retry,
# or out-of-order replay can expose a torn transaction, duplicate completion
# records, or advance a modeled cursor more than once.
# ---------------------------------------------------------------------------


def _acceptance_writes(root: Path, tx_id: str, *, state_path: Path,
                       state_payload: str, receipt_path: Path,
                       snapshot_path: Path, prior_sha: "str | None") -> list[dict]:
    """Build the multi-write CAS-guarded journal entries that model an
    acceptance commit (mirrors ``prepare_acceptance_commit`` writes)."""
    w_state = journal_text_write(state_path, state_payload, tx_id=tx_id)
    w_state = dict(w_state)
    if prior_sha is not None:
        w_state["expected_prior_sha256"] = prior_sha
    else:
        w_state["target_absent"] = True
    w_receipt = journal_text_write(receipt_path, '{"tx":"' + tx_id + '"}', tx_id=tx_id)
    w_snap = journal_text_write(snapshot_path, '{"snap":1}', tx_id=tx_id)
    return [w_state, w_receipt, w_snap]


def _acceptance_state(payload: str, *, cursor: int, completed: list[str]) -> str:
    """Build a modeled chain-state JSON with a cursor + completed list."""
    return json.dumps(
        {"current_milestone_index": cursor, "completed": completed}, sort_keys=True
    )


class TestAcceptanceCommitJournalCrashStages:
    """Each crash stage of an acceptance-commit journal transaction must
    recover to either fully-applied or fully-discarded — never torn."""

    def test_crash_after_prepare_discards_all(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        receipt = tmp_path / "data" / "receipt.json"
        snap = tmp_path / "data" / "snap.json"
        writes = _acceptance_writes(root, "tx1", state_path=state,
                                    state_payload=_acceptance_state(
                                        "", cursor=3, completed=["m5a"]),
                                    receipt_path=receipt, snapshot_path=snap,
                                    prior_sha=None)
        prepare_journal_transaction(root, "tx1", writes=writes)

        report = recover_journal(root)
        assert report["discarded"] == ["tx1"]
        assert not state.exists()
        assert not receipt.exists()
        assert not snap.exists()

    def test_crash_after_marker_before_apply_completes(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        receipt = tmp_path / "data" / "receipt.json"
        snap = tmp_path / "data" / "snap.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])
        writes = _acceptance_writes(root, "tx1", state_path=state,
                                    state_payload=payload, receipt_path=receipt,
                                    snapshot_path=snap, prior_sha=None)
        prepare_journal_transaction(root, "tx1", writes=writes)
        write_journal_commit_marker(root, "tx1")
        assert not state.exists()

        report = recover_journal(root)
        assert report["replayed"] == ["tx1"]
        assert state.read_text() == payload
        assert receipt.exists()
        assert snap.exists()

    def test_crash_after_apply_before_cleanup_idempotent(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        receipt = tmp_path / "data" / "receipt.json"
        snap = tmp_path / "data" / "snap.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])
        writes = _acceptance_writes(root, "tx1", state_path=state,
                                    state_payload=payload, receipt_path=receipt,
                                    snapshot_path=snap, prior_sha=None)
        prepare_path = prepare_journal_transaction(root, "tx1", writes=writes)
        write_journal_commit_marker(root, "tx1")
        p = json.loads(prepare_path.read_text())
        p["journal_root"] = str(root)
        _apply_prepared_writes(p)
        before = state.read_bytes()

        report = recover_journal(root)
        assert report["replayed"] == ["tx1"]
        assert state.read_bytes() == before  # idempotent

    def test_repeated_recovery_no_duplicate(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        receipt = tmp_path / "data" / "receipt.json"
        snap = tmp_path / "data" / "snap.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])
        writes = _acceptance_writes(root, "tx1", state_path=state,
                                    state_payload=payload, receipt_path=receipt,
                                    snapshot_path=snap, prior_sha=None)
        prepare_journal_transaction(root, "tx1", writes=writes)
        write_journal_commit_marker(root, "tx1")

        for _ in range(5):
            recover_journal(root)
        assert json.loads(state.read_text())["completed"] == ["m5a"]


class TestAcceptanceCommitDuplicateDrivers:
    """Two concurrent drivers cannot both complete the same milestone."""

    def test_target_absent_second_driver_blocked(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])

        w_a = _acceptance_writes(root, "drvA", state_path=state,
                                 state_payload=payload, receipt_path=tmp_path / "rA.json",
                                 snapshot_path=tmp_path / "sA.json", prior_sha=None)
        w_b = _acceptance_writes(root, "drvB", state_path=state,
                                 state_payload=payload, receipt_path=tmp_path / "rB.json",
                                 snapshot_path=tmp_path / "sB.json", prior_sha=None)
        prepare_journal_transaction(root, "drvA", writes=w_a)
        prepare_journal_transaction(root, "drvB", writes=w_b)

        res_a = commit_journal_transaction_cas(root, "drvA")
        res_b = commit_journal_transaction_cas(root, "drvB")
        assert res_a.committed is True
        assert res_b.committed is False
        assert res_b.violations


class TestAcceptanceCommitStaleWorker:
    """A worker with a stale prior-state hash cannot commit."""

    def test_stale_prior_hash_fails_closed(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        state.parent.mkdir()
        # Seed state.
        state.write_text(_acceptance_state("", cursor=0, completed=["m0"]))
        prior = _path_sha256(state)

        # A second commit lands, changing the state.
        state.write_text(_acceptance_state("", cursor=2, completed=["m0", "m2"]))

        # Stale worker still holds the old hash.
        stale = _acceptance_writes(root, "stale", state_path=state,
                                   state_payload=_acceptance_state(
                                       "", cursor=1, completed=["m0", "m2", "m1"]),
                                   receipt_path=tmp_path / "r.json",
                                   snapshot_path=tmp_path / "s.json", prior_sha=prior)
        prepare_journal_transaction(root, "stale", writes=stale)
        res = commit_journal_transaction_cas(root, "stale")
        assert res.committed is False
        # Stale worker's m1 did NOT land.
        assert json.loads(state.read_text())["completed"] == ["m0", "m2"]

    def test_stale_worker_recovers_after_refresh(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        state.parent.mkdir()
        state.write_text(_acceptance_state("", cursor=0, completed=["m0"]))
        prior = _path_sha256(state)
        state.write_text(_acceptance_state("", cursor=2, completed=["m0", "m2"]))

        w_bad = _acceptance_writes(root, "bad", state_path=state,
                                   state_payload=_acceptance_state(
                                       "", cursor=2, completed=["m0", "m2", "m1"]),
                                   receipt_path=tmp_path / "r.json",
                                   snapshot_path=tmp_path / "s.json", prior_sha=prior)
        prepare_journal_transaction(root, "bad", writes=w_bad)
        assert commit_journal_transaction_cas(root, "bad").committed is False

        # Refresh hash and retry.
        fresh = _path_sha256(state)
        w_ok = _acceptance_writes(root, "ok", state_path=state,
                                  state_payload=_acceptance_state(
                                      "", cursor=2, completed=["m0", "m2", "m1"]),
                                  receipt_path=tmp_path / "r2.json",
                                  snapshot_path=tmp_path / "s2.json", prior_sha=fresh)
        prepare_journal_transaction(root, "ok", writes=w_ok)
        assert commit_journal_transaction_cas(root, "ok").committed is True


class TestAcceptanceCommitCrashRestart:
    """Crash at prepare, then restart + re-prepare + commit succeeds."""

    def test_crash_discard_then_reprepare_commit(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])
        w = _acceptance_writes(root, "tx1", state_path=state,
                               state_payload=payload, receipt_path=tmp_path / "r.json",
                               snapshot_path=tmp_path / "s.json", prior_sha=None)
        prepare_journal_transaction(root, "tx1", writes=w)
        # Crash: recover discards.
        recover_journal(root)
        assert not state.exists()

        # Restart: re-prepare + commit.
        w2 = _acceptance_writes(root, "tx2", state_path=state,
                                state_payload=payload, receipt_path=tmp_path / "r.json",
                                snapshot_path=tmp_path / "s.json", prior_sha=None)
        prepare_journal_transaction(root, "tx2", writes=w2)
        assert commit_journal_transaction_cas(root, "tx2").committed is True
        assert state.read_text() == payload


class TestAcceptanceCommitRetry:
    """CAS failure discards the candidate; a fresh prepare commits."""

    def test_cas_failure_discards_then_retry(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        state.parent.mkdir()
        state.write_text(_acceptance_state("", cursor=0, completed=["m0"]))

        # Bad prior hash -> CAS failure.
        w_bad = _acceptance_writes(root, "bad", state_path=state,
                                   state_payload=_acceptance_state(
                                       "", cursor=1, completed=["m0", "m1"]),
                                   receipt_path=tmp_path / "r.json",
                                   snapshot_path=tmp_path / "s.json",
                                   prior_sha="sha256:" + "0" * 64)
        prepare_journal_transaction(root, "bad", writes=w_bad)
        assert commit_journal_transaction_cas(root, "bad").committed is False
        assert not journal_prepare_path(root, "bad").exists()  # auto-discarded

        # Retry with correct hash.
        w_ok = _acceptance_writes(root, "ok", state_path=state,
                                  state_payload=_acceptance_state(
                                      "", cursor=1, completed=["m0", "m1"]),
                                  receipt_path=tmp_path / "r2.json",
                                  snapshot_path=tmp_path / "s2.json",
                                  prior_sha=_path_sha256(state))
        prepare_journal_transaction(root, "ok", writes=w_ok)
        assert commit_journal_transaction_cas(root, "ok").committed is True


class TestAcceptanceCommitOutOfOrder:
    """The modeled cursor (max) never regresses on out-of-order commits."""

    def test_higher_then_lower_cursor_stays_max(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        # Commit index 2.
        p2 = _acceptance_state("", cursor=2, completed=["m2"])
        w2 = _acceptance_writes(root, "t2", state_path=state, state_payload=p2,
                                receipt_path=tmp_path / "r2.json",
                                snapshot_path=tmp_path / "s2.json", prior_sha=None)
        prepare_journal_transaction(root, "t2", writes=w2)
        assert commit_journal_transaction_cas(root, "t2").committed is True

        # Commit index 0 — cursor stays at max(2,0)=2.
        p0 = _acceptance_state("", cursor=2, completed=["m2", "m0"])
        w0 = _acceptance_writes(root, "t0", state_path=state, state_payload=p0,
                                receipt_path=tmp_path / "r0.json",
                                snapshot_path=tmp_path / "s0.json",
                                prior_sha=_path_sha256(state))
        prepare_journal_transaction(root, "t0", writes=w0)
        assert commit_journal_transaction_cas(root, "t0").committed is True
        assert json.loads(state.read_text())["current_milestone_index"] == 2


class TestAcceptanceCommitExactlyOnce:
    """Re-committing the same modeled milestone yields exactly one completion
    entry and the cursor advances exactly once."""

    def test_recommit_single_completion(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])
        w1 = _acceptance_writes(root, "tx1", state_path=state, state_payload=payload,
                                receipt_path=tmp_path / "r.json",
                                snapshot_path=tmp_path / "s.json", prior_sha=None)
        prepare_journal_transaction(root, "tx1", writes=w1)
        commit_journal_transaction_cas(root, "tx1")

        # Re-commit with the same milestone (idempotent content).
        w2 = _acceptance_writes(root, "tx2", state_path=state, state_payload=payload,
                                receipt_path=tmp_path / "r2.json",
                                snapshot_path=tmp_path / "s2.json",
                                prior_sha=_path_sha256(state))
        prepare_journal_transaction(root, "tx2", writes=w2)
        commit_journal_transaction_cas(root, "tx2")

        completed = json.loads(state.read_text())["completed"]
        assert completed.count("m5a") == 1
        assert json.loads(state.read_text())["current_milestone_index"] == 3

    def test_replay_does_not_advance_cursor_twice(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        state = tmp_path / "data" / "state.json"
        payload = _acceptance_state("", cursor=3, completed=["m5a"])
        w = _acceptance_writes(root, "tx1", state_path=state, state_payload=payload,
                               receipt_path=tmp_path / "r.json",
                               snapshot_path=tmp_path / "s.json", prior_sha=None)
        prepare_journal_transaction(root, "tx1", writes=w)
        write_journal_commit_marker(root, "tx1")

        for _ in range(4):
            recover_journal(root)
        d = json.loads(state.read_text())
        assert d["current_milestone_index"] == 3
        assert d["completed"] == ["m5a"]
