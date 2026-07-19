"""Tests for optional Compare-And-Swap (CAS) guards on the journal primitives.

Covers:
- CAS builder fields (``expected_prior_sha256``, ``target_absent``) are only
  emitted when set, so non-CAS entries stay byte-identical to the pre-CAS
  journal format.
- Mutual-exclusivity validation for contradictory guards.
- ``commit_journal_transaction_cas`` commits when guards pass (or are absent)
  and produces an explicit failure ``JournalCASResult`` when a guard fails.
- CAS failures occur **before** the commit marker is created: no marker, target
  unchanged, prepare.json removed, and recovery treats the transaction as
  discarded (sense check SC2).
- Non-CAS prepare/commit/recover/cleanup behaviour is preserved.
- Result/violation serialization (``to_dict``).
"""

from __future__ import annotations

import json

import pytest

from arnold_pipelines.megaplan._core.io import (
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
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prior_hash(path) -> str:
    """Return the current on-disk SHA-256 of *path* in the journal format."""
    from arnold_pipelines.megaplan._core.io import _path_sha256

    return _path_sha256(path)


def _prepare_one_write(root, tx_id, entry) -> None:
    prepare_journal_transaction(root, tx_id, writes=[entry])


# ---------------------------------------------------------------------------
# Builder: non-CAS entries are byte-identical to the pre-CAS format
# ---------------------------------------------------------------------------


class TestNonCASBuildersUnchanged:
    def test_text_write_omits_cas_keys_by_default(self, tmp_path):
        target = tmp_path / "state.json"
        entry = journal_text_write(target, "payload\n", tx_id="t1")
        assert "expected_prior_sha256" not in entry
        assert "target_absent" not in entry
        # Core fields unchanged.
        assert entry["target_path"] == str(target)
        assert entry["content"] == "payload\n"
        assert entry["content_storage"] == "text"

    def test_bytes_write_omits_cas_keys_by_default(self, tmp_path):
        target = tmp_path / "blob.bin"
        entry = journal_bytes_write(target, b"\x00\x01", tx_id="t1")
        assert "expected_prior_sha256" not in entry
        assert "target_absent" not in entry
        assert entry["content_storage"] == "base64"

    def test_blob_promotion_omits_cas_keys_by_default(self, tmp_path):
        entry = journal_blob_promotion(
            tmp_path / "blob",
            b"data",
            extension="json",
            metadata={"k": "v"},
        )
        assert "expected_prior_sha256" not in entry
        assert "target_absent" not in entry


# ---------------------------------------------------------------------------
# Builder: CAS fields are emitted when set
# ---------------------------------------------------------------------------


class TestCABuilderFields:
    def test_text_write_emits_expected_prior_sha256(self, tmp_path):
        target = tmp_path / "state.json"
        entry = journal_text_write(
            target,
            "payload\n",
            tx_id="t1",
            expected_prior_sha256="sha256:abc",
        )
        assert entry["expected_prior_sha256"] == "sha256:abc"
        assert "target_absent" not in entry

    def test_text_write_emits_target_absent(self, tmp_path):
        target = tmp_path / "state.json"
        entry = journal_text_write(target, "payload\n", tx_id="t1", target_absent=True)
        assert entry["target_absent"] is True
        assert "expected_prior_sha256" not in entry

    def test_bytes_write_emits_cas_fields(self, tmp_path):
        target = tmp_path / "blob.bin"
        entry = journal_bytes_write(
            target,
            b"\x00",
            tx_id="t1",
            target_absent=True,
        )
        assert entry["target_absent"] is True

    def test_blob_promotion_emits_cas_fields(self, tmp_path):
        entry = journal_blob_promotion(
            tmp_path / "blob",
            b"data",
            extension="json",
            metadata={},
            expected_prior_sha256="sha256:def",
        )
        assert entry["expected_prior_sha256"] == "sha256:def"

    @pytest.mark.parametrize("builder", ["text", "bytes", "blob"])
    def test_contradictory_guards_rejected(self, tmp_path, builder):
        with pytest.raises(ValueError, match="mutually exclusive"):
            if builder == "text":
                journal_text_write(
                    tmp_path / "a",
                    "x",
                    expected_prior_sha256="sha256:1",
                    target_absent=True,
                )
            elif builder == "bytes":
                journal_bytes_write(
                    tmp_path / "a",
                    b"x",
                    expected_prior_sha256="sha256:1",
                    target_absent=True,
                )
            else:
                journal_blob_promotion(
                    tmp_path / "b",
                    b"x",
                    extension="json",
                    metadata={},
                    expected_prior_sha256="sha256:1",
                    target_absent=True,
                )


# ---------------------------------------------------------------------------
# CAS commit: success paths
# ---------------------------------------------------------------------------


class TestCASCommitSuccess:
    def test_no_guards_commits_normally(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        entry = journal_text_write(target, "fresh\n", tx_id="t1")
        _prepare_one_write(root, "t1", entry)

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is True
        assert result.violations == ()
        assert target.read_text() == "fresh\n"
        # Commit marker and prepare file cleaned up after success.
        assert not journal_commit_path(root, "t1").exists()
        assert not journal_prepare_path(root, "t1").exists()

    def test_expected_prior_sha256_match_commits(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        expected = _prior_hash(target)
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256=expected,
        )
        _prepare_one_write(root, "t1", entry)

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is True
        assert result.violations == ()
        assert target.read_text() == "updated\n"

    def test_target_absent_when_file_missing_commits(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "new.json"
        entry = journal_text_write(target, "created\n", tx_id="t1", target_absent=True)
        _prepare_one_write(root, "t1", entry)

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is True
        assert target.read_text() == "created\n"


# ---------------------------------------------------------------------------
# CAS commit: failure paths (must fail BEFORE commit marker creation — SC2)
# ---------------------------------------------------------------------------


class TestCASCommitFailure:
    def test_expected_prior_sha256_mismatch_fails_before_marker(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        expected = _prior_hash(target)
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256=expected,
        )
        _prepare_one_write(root, "t1", entry)

        # Concurrent modification between prepare and commit.
        target.write_text("CONCURRENT-CHANGE\n")
        actual_hash = _prior_hash(target)

        result = commit_journal_transaction_cas(root, "t1")

        # Explicit failure result.
        assert result.committed is False
        assert len(result.violations) == 1
        violation = result.violations[0]
        assert violation.guard == "expected_prior_sha256"
        assert violation.section == "writes"
        assert violation.entry_index == 0
        assert violation.target_path == str(target)
        assert violation.expected == expected
        assert violation.actual == actual_hash

        # SC2: no commit marker was ever created.
        assert not journal_commit_path(root, "t1").exists()
        # SC2: the target is untouched (still the concurrent change, not our write).
        assert target.read_text() == "CONCURRENT-CHANGE\n"
        # SC2: prepare.json was cleaned up (transaction fully discarded).
        assert not journal_prepare_path(root, "t1").exists()

    def test_expected_prior_sha256_file_now_absent(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        expected = _prior_hash(target)
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256=expected,
        )
        _prepare_one_write(root, "t1", entry)

        # File removed concurrently — expected hash cannot match None.
        target.unlink()

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is False
        assert len(result.violations) == 1
        assert result.violations[0].actual is None
        assert not journal_commit_path(root, "t1").exists()

    def test_target_absent_but_file_exists_fails(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("exists\n")
        entry = journal_text_write(target, "overwrite\n", tx_id="t1", target_absent=True)
        _prepare_one_write(root, "t1", entry)

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is False
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.guard == "target_absent"
        assert v.expected is None
        assert v.actual == _prior_hash(target)
        # Target untouched.
        assert target.read_text() == "exists\n"
        assert not journal_commit_path(root, "t1").exists()

    def test_multiple_violations_all_reported(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        t1 = tmp_path / "a" / "x.json"
        t1.parent.mkdir(parents=True)
        t1.write_text("one\n")
        t2 = tmp_path / "b" / "y.json"
        t2.parent.mkdir(parents=True)
        t2.write_text("two\n")

        e1 = journal_text_write(t1, "x\n", tx_id="t1", expected_prior_sha256="sha256:stale1")
        e2 = journal_text_write(t2, "y\n", tx_id="t1", expected_prior_sha256="sha256:stale2")
        prepare_journal_transaction(root, "t1", writes=[e1, e2])

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is False
        assert len(result.violations) == 2
        indices = [v.entry_index for v in result.violations]
        assert indices == [0, 1]


# ---------------------------------------------------------------------------
# CAS failure + recovery interaction (transaction is never-committed)
# ---------------------------------------------------------------------------


class TestCASFailureRecovery:
    def test_failed_cas_transaction_is_discarded_by_recovery(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        expected = _prior_hash(target)
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256=expected,
        )
        _prepare_one_write(root, "t1", entry)
        target.write_text("CONCURRENT\n")  # break the guard

        commit_journal_transaction_cas(root, "t1")

        # The CAS failure already cleaned up prepare.json; recovery must not
        # replay anything and the target stays as the concurrent value.
        report = recover_journal(root)
        assert report["replayed"] == []
        assert target.read_text() == "CONCURRENT\n"

    def test_passed_cas_transaction_with_marker_is_replayed_by_recovery(self, tmp_path):
        # A CAS-guarded transaction that committed (marker exists) must be
        # idempotently replayable by the non-CAS recovery path.
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        expected = _prior_hash(target)
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256=expected,
        )
        _prepare_one_write(root, "t1", entry)

        # Manually write the commit marker WITHOUT applying, then recover —
        # simulates a crash after CAS passed + marker was durably written.
        from arnold_pipelines.megaplan._core.io import write_journal_commit_marker

        write_journal_commit_marker(root, "t1")
        assert target.read_text() == "original\n"

        report = recover_journal(root)

        assert report["replayed"] == ["t1"]
        assert target.read_text() == "updated\n"


# ---------------------------------------------------------------------------
# evaluate_cas_guards is a pure read
# ---------------------------------------------------------------------------


class TestEvaluateCASGuardsPure:
    def test_evaluate_makes_no_changes(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        expected = _prior_hash(target)
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256=expected,
        )
        _prepare_one_write(root, "t1", entry)
        prepare_payload = json.loads(journal_prepare_path(root, "t1").read_text())

        # Break the guard after prepare.
        target.write_text("CHANGED\n")

        violations = evaluate_cas_guards(prepare_payload)

        assert len(violations) == 1
        # evaluate must not have touched the target or written a marker.
        assert target.read_text() == "CHANGED\n"
        assert not journal_commit_path(root, "t1").exists()

    def test_evaluate_empty_when_no_guards(self, tmp_path):
        payload = {"writes": [{"target_path": str(tmp_path / "x")}], "blob_promotions": []}
        assert evaluate_cas_guards(payload) == ()


# ---------------------------------------------------------------------------
# Non-CAS behaviour preserved: commit_journal_transaction unchanged
# ---------------------------------------------------------------------------


class TestNonCASBehaviorPreserved:
    def test_legacy_commit_ignores_cas_keys(self, tmp_path):
        # An entry carrying CAS keys committed via the legacy (non-CAS) path
        # must still apply the write without evaluating guards.
        root = tmp_path / "root"
        root.mkdir()
        target = tmp_path / "data" / "state.json"
        target.parent.mkdir(parents=True)
        target.write_text("original\n")
        # Stale guard that would normally block — legacy path ignores it.
        entry = journal_text_write(
            target,
            "updated\n",
            tx_id="t1",
            expected_prior_sha256="sha256:does-not-match",
        )
        _prepare_one_write(root, "t1", entry)

        commit_journal_transaction(root, "t1")

        assert target.read_text() == "updated\n"
        assert not journal_commit_path(root, "t1").exists()

    def test_cas_commit_with_blob_guard(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        blob_dir = tmp_path / "store" / "blob-1"
        entry = journal_blob_promotion(
            blob_dir,
            b"blobby",
            extension="json",
            metadata={"id": "1"},
            target_absent=True,
        )
        prepare_journal_transaction(root, "t1", blobs=[entry])

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is True
        assert (blob_dir / "data.json").read_bytes() == b"blobby"

    def test_cas_commit_blob_guard_fails_when_present(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        blob_dir = tmp_path / "store" / "blob-1"
        blob_dir.mkdir(parents=True)
        (blob_dir / "data.json").write_bytes(b"preexisting")
        entry = journal_blob_promotion(
            blob_dir,
            b"blobby",
            extension="json",
            metadata={"id": "1"},
            target_absent=True,
        )
        prepare_journal_transaction(root, "t1", blobs=[entry])

        result = commit_journal_transaction_cas(root, "t1")

        assert result.committed is False
        assert len(result.violations) == 1
        assert result.violations[0].section == "blob_promotions"
        assert result.violations[0].guard == "target_absent"
        assert (blob_dir / "data.json").read_bytes() == b"preexisting"


# ---------------------------------------------------------------------------
# Result serialization
# ---------------------------------------------------------------------------


class TestResultSerialization:
    def test_violation_to_dict(self):
        v = JournalCASViolation(
            section="writes",
            entry_index=2,
            target_path="/a/b.json",
            guard="expected_prior_sha256",
            expected="sha256:e",
            actual="sha256:a",
        )
        d = v.to_dict()
        assert d == {
            "section": "writes",
            "entry_index": 2,
            "target_path": "/a/b.json",
            "guard": "expected_prior_sha256",
            "expected": "sha256:e",
            "actual": "sha256:a",
        }

    def test_result_to_dict_success(self):
        r = JournalCASResult(tx_id="t1", committed=True)
        assert r.to_dict() == {"tx_id": "t1", "committed": True, "violations": []}

    def test_result_to_dict_failure(self):
        v = JournalCASViolation(
            section="writes",
            entry_index=0,
            target_path="/x",
            guard="target_absent",
            expected=None,
            actual="sha256:1",
        )
        r = JournalCASResult(tx_id="t1", committed=False, violations=(v,))
        d = r.to_dict()
        assert d["committed"] is False
        assert d["violations"] == [v.to_dict()]

    def test_result_is_frozen(self):
        r = JournalCASResult(tx_id="t1", committed=True)
        with pytest.raises(Exception):
            r.committed = False  # type: ignore[misc]
