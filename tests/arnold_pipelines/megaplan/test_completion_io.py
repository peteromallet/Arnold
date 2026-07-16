"""Tests for acceptance snapshot IO and recovery helpers in completion_io.

Covers:
- Snapshot store/load with content-addressed paths
- Snapshot immutability (idempotent store, hash verification on load)
- Transaction lifecycle: prepare → commit → discard
- Recovery replay: committed transactions survive, uncommitted discarded
- Empty/missing directory and edge-case handling
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    AcceptanceSnapshot,
    AcceptanceTransaction,
)
from arnold_pipelines.megaplan.orchestration.completion_io import (
    AcceptanceReplayResult,
    commit_acceptance_transaction,
    discard_uncommitted_acceptance_transaction,
    list_committed_acceptance_transactions,
    load_acceptance_snapshot,
    load_acceptance_transaction_by_id,
    prepare_acceptance_transaction,
    replay_acceptance_transactions,
    snapshot_exists,
    store_acceptance_snapshot,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    EvidenceStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    """A clean temporary plan directory."""
    pd = tmp_path / "plan"
    pd.mkdir()
    return pd


@pytest.fixture
def sample_snapshot() -> AcceptanceSnapshot:
    """A minimal valid snapshot for IO testing."""
    return AcceptanceSnapshot(
        transaction_id="txn-io-test-001",
        chain_run_id="chain-run-io-test",
        milestone_label="m5a",
        milestone_index=2,
        plan_name="test-plan",
        source_commit_ref="abc123",
        runtime_identity="test-runtime",
        evidence=(
            EvidenceRef(
                kind="green_suite",
                status=EvidenceStatus.satisfied,
                summary="All tests passed",
                details={"delta": {"passed": 5, "failed": 0}},
            ),
        ),
        evidence_refs=("ref-a", "ref-b"),
    )


@pytest.fixture
def sample_transaction(sample_snapshot: AcceptanceSnapshot) -> AcceptanceTransaction:
    """A minimal valid acceptance transaction."""
    return AcceptanceTransaction(
        transaction_id="txn-io-test-001",
        snapshot_hash=sample_snapshot.content_hash,
        accepted=True,
        mode="shadow",
        tested_commit_ref="abc123",
        tested_runtime_identity="test-runtime",
    )


def _make_snapshot(tx_id: str, **kwargs: object) -> AcceptanceSnapshot:
    """Create a snapshot with a specific transaction_id."""
    defaults = {
        "transaction_id": tx_id,
        "chain_run_id": "chain-run-io-test",
        "milestone_label": "m5a",
        "milestone_index": 2,
        "plan_name": "test-plan",
        "source_commit_ref": "abc123",
        "runtime_identity": "test-runtime",
    }
    defaults.update(kwargs)
    return AcceptanceSnapshot(**defaults)


def _make_transaction(
    tx_id: str,
    snapshot_hash: str,
    **kwargs: object,
) -> AcceptanceTransaction:
    """Create a transaction with a specific id and snapshot hash."""
    defaults = {
        "transaction_id": tx_id,
        "snapshot_hash": snapshot_hash,
        "accepted": True,
        "mode": "shadow",
        "tested_commit_ref": "abc123",
        "tested_runtime_identity": "test-runtime",
    }
    defaults.update(kwargs)
    return AcceptanceTransaction(**defaults)


# ---------------------------------------------------------------------------
# Snapshot store / load
# ---------------------------------------------------------------------------


def test_store_and_load_snapshot_round_trip(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Snapshot round-trip: store → load should produce identical snapshot."""
    stored_path = store_acceptance_snapshot(plan_dir, sample_snapshot)
    assert stored_path.is_file()
    # Path should be content-addressed
    assert "_acceptance/snapshots/" in str(stored_path)

    loaded = load_acceptance_snapshot(plan_dir, sample_snapshot.content_hash)
    assert loaded is not None
    assert loaded.transaction_id == sample_snapshot.transaction_id
    assert loaded.content_hash == sample_snapshot.content_hash
    assert loaded.evidence_refs == sample_snapshot.evidence_refs


def test_store_snapshot_idempotent(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Storing the same snapshot twice should not fail or duplicate."""
    path1 = store_acceptance_snapshot(plan_dir, sample_snapshot)
    path2 = store_acceptance_snapshot(plan_dir, sample_snapshot)
    assert path1 == path2
    # Still only one file
    snapshots = list((plan_dir / "_acceptance" / "snapshots").rglob("*.json"))
    assert len(snapshots) == 1


def test_load_nonexistent_snapshot(plan_dir: Path) -> None:
    """Loading a snapshot that was never stored returns None."""
    result = load_acceptance_snapshot(plan_dir, "sha256:deadbeef" * 4)
    assert result is None


def test_snapshot_exists(plan_dir: Path, sample_snapshot: AcceptanceSnapshot) -> None:
    """snapshot_exists should reflect storage state."""
    assert not snapshot_exists(plan_dir, sample_snapshot.content_hash)
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    assert snapshot_exists(plan_dir, sample_snapshot.content_hash)
    assert not snapshot_exists(plan_dir, "sha256:0000000000000000000000000000000000000000000000000000000000000000")


def test_load_snapshot_hash_mismatch(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Loading with a hash different from stored content-hash returns None."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    wrong_hash = "sha256:" + "ff" * 32
    result = load_acceptance_snapshot(plan_dir, wrong_hash)
    assert result is None


def test_store_multiple_different_snapshots(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Storing different snapshots should create distinct files."""
    snap2 = _make_snapshot("txn-io-test-002")
    path1 = store_acceptance_snapshot(plan_dir, sample_snapshot)
    path2 = store_acceptance_snapshot(plan_dir, snap2)
    assert path1 != path2
    assert path1.is_file()
    assert path2.is_file()

    loaded1 = load_acceptance_snapshot(plan_dir, sample_snapshot.content_hash)
    loaded2 = load_acceptance_snapshot(plan_dir, snap2.content_hash)
    assert loaded1 is not None
    assert loaded2 is not None
    assert loaded1.transaction_id != loaded2.transaction_id


# ---------------------------------------------------------------------------
# Transaction lifecycle: prepare → commit → discard
# ---------------------------------------------------------------------------


def test_prepare_and_commit_transaction(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """A prepared transaction should be committable."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-001", sample_snapshot.content_hash)

    prepare_path = prepare_acceptance_transaction(plan_dir, tx)
    assert prepare_path.is_file()
    assert prepare_path.name.endswith(".prepare.json")

    committed_path = commit_acceptance_transaction(plan_dir, "tx-001")
    assert committed_path is not None
    assert committed_path.is_file()
    assert not committed_path.name.endswith(".prepare.json")

    # Prepare file should be removed after commit
    assert not prepare_path.exists()

    # Commit marker should exist
    marker = plan_dir / "_acceptance" / "transactions" / "tx-001.commit"
    assert marker.is_file()


def test_commit_nonexistent_transaction(plan_dir: Path) -> None:
    """Committing a transaction that was never prepared returns None."""
    result = commit_acceptance_transaction(plan_dir, "no-such-tx")
    assert result is None


def test_discard_uncommitted_transaction(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Discarding a prepared (but not committed) transaction removes its files."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-discard", sample_snapshot.content_hash)

    prepare_path = prepare_acceptance_transaction(plan_dir, tx)
    assert prepare_path.is_file()

    discard_uncommitted_acceptance_transaction(plan_dir, "tx-discard")
    assert not prepare_path.exists()


def test_discard_nonexistent_transaction_noop(plan_dir: Path) -> None:
    """Discarding a transaction that doesn't exist should be a no-op."""
    # Should not raise
    discard_uncommitted_acceptance_transaction(plan_dir, "no-such-tx")


def test_prepare_commit_load_round_trip(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Full lifecycle: prepare → commit → load."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-lifecycle", sample_snapshot.content_hash)

    prepare_acceptance_transaction(plan_dir, tx)
    commit_acceptance_transaction(plan_dir, "tx-lifecycle")

    loaded = load_acceptance_transaction_by_id(plan_dir, "tx-lifecycle")
    assert loaded is not None
    assert loaded.transaction_id == "tx-lifecycle"
    assert loaded.snapshot_hash == sample_snapshot.content_hash
    assert loaded.accepted is True
    assert loaded.mode == "shadow"


def test_load_transaction_by_id_nonexistent(plan_dir: Path) -> None:
    """Loading a non-existent transaction returns None."""
    result = load_acceptance_transaction_by_id(plan_dir, "no-such-tx")
    assert result is None


def test_list_committed_transactions(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """List committed transactions should return all committed ones."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)

    # Commit two transactions
    for tx_id in ("tx-a", "tx-b"):
        tx = _make_transaction(tx_id, sample_snapshot.content_hash)
        prepare_acceptance_transaction(plan_dir, tx)
        commit_acceptance_transaction(plan_dir, tx_id)

    committed = list_committed_acceptance_transactions(plan_dir)
    assert len(committed) == 2
    assert "tx-a" in committed
    assert "tx-b" in committed


def test_list_committed_transactions_empty_dir(plan_dir: Path) -> None:
    """Listing committed transactions in an empty dir returns empty dict."""
    committed = list_committed_acceptance_transactions(plan_dir)
    assert committed == {}


# ---------------------------------------------------------------------------
# Recovery replay — committed survive, uncommitted discarded
# ---------------------------------------------------------------------------


def test_replay_promotes_committed_transactions(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Replay should promote transactions that have commit markers."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-replay-commit", sample_snapshot.content_hash)

    # Simulate: prepare exists, commit marker exists (crashed after marker before cleanup)
    prepare_acceptance_transaction(plan_dir, tx)
    # Write commit marker manually to simulate crash state
    marker_path = plan_dir / "_acceptance" / "transactions" / "tx-replay-commit.commit"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_bytes(b"")

    result = replay_acceptance_transactions(plan_dir)
    assert isinstance(result, AcceptanceReplayResult)
    assert "tx-replay-commit" in result.committed
    assert len(result.discarded) == 0

    # Prepare file should be cleaned up
    prepare_path = plan_dir / "_acceptance" / "transactions" / "tx-replay-commit.prepare.json"
    assert not prepare_path.exists()

    # Committed file should exist
    committed_path = plan_dir / "_acceptance" / "transactions" / "tx-replay-commit.json"
    assert committed_path.is_file()


def test_replay_discards_uncommitted_candidates(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Replay should discard transactions that have no commit marker."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-replay-discard", sample_snapshot.content_hash)

    # Simulate: prepare exists, but NO commit marker (crashed before commit)
    prepare_acceptance_transaction(plan_dir, tx)

    result = replay_acceptance_transactions(plan_dir)
    assert "tx-replay-discard" in result.discarded
    assert "tx-replay-discard" not in result.committed

    # Prepare file should be removed
    prepare_path = plan_dir / "_acceptance" / "transactions" / "tx-replay-discard.prepare.json"
    assert not prepare_path.exists()


def test_replay_mixed_committed_and_candidates(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Replay with a mix of committed and candidate transactions."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)

    # Transaction 1: committed (prepare + marker)
    tx1 = _make_transaction("tx-mixed-1", sample_snapshot.content_hash)
    prepare_acceptance_transaction(plan_dir, tx1)
    marker1 = plan_dir / "_acceptance" / "transactions" / "tx-mixed-1.commit"
    marker1.parent.mkdir(parents=True, exist_ok=True)
    marker1.write_bytes(b"")

    # Transaction 2: candidate only (prepare, no marker)
    tx2 = _make_transaction("tx-mixed-2", sample_snapshot.content_hash)
    prepare_acceptance_transaction(plan_dir, tx2)

    # Transaction 3: already fully committed
    tx3 = _make_transaction("tx-mixed-3", sample_snapshot.content_hash)
    prepare_acceptance_transaction(plan_dir, tx3)
    commit_acceptance_transaction(plan_dir, "tx-mixed-3")

    result = replay_acceptance_transactions(plan_dir)
    assert "tx-mixed-1" in result.committed
    assert "tx-mixed-2" in result.discarded
    assert "tx-mixed-3" in result.committed
    assert len(result.committed) == 2
    assert len(result.discarded) == 1


def test_replay_empty_acceptance_dir(plan_dir: Path) -> None:
    """Replay on a plan_dir with no _acceptance directory returns empty result."""
    result = replay_acceptance_transactions(plan_dir)
    assert result.committed == {}
    assert result.discarded == ()


def test_replay_cleans_up_orphaned_commit_markers(
    plan_dir: Path,
) -> None:
    """Orphaned commit markers (no prepare, no committed) should be removed on replay."""
    marker_path = plan_dir / "_acceptance" / "transactions" / "orphan.commit"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_bytes(b"")

    result = replay_acceptance_transactions(plan_dir)
    assert result.committed == {}
    assert result.discarded == ()
    assert not marker_path.exists()


def test_replay_idempotent(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Replaying twice should produce the same result."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-idem", sample_snapshot.content_hash)
    prepare_acceptance_transaction(plan_dir, tx)
    marker = plan_dir / "_acceptance" / "transactions" / "tx-idem.commit"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(b"")

    result1 = replay_acceptance_transactions(plan_dir)
    result2 = replay_acceptance_transactions(plan_dir)

    assert set(result1.committed.keys()) == set(result2.committed.keys())
    assert result1.discarded == result2.discarded


def test_replay_does_not_load_malformed_transactions(
    plan_dir: Path, sample_snapshot: AcceptanceSnapshot
) -> None:
    """Malformed committed transaction files should be silently skipped."""
    store_acceptance_snapshot(plan_dir, sample_snapshot)
    tx = _make_transaction("tx-valid", sample_snapshot.content_hash)
    prepare_acceptance_transaction(plan_dir, tx)
    commit_acceptance_transaction(plan_dir, "tx-valid")

    # Write a malformed file directly
    bad_path = plan_dir / "_acceptance" / "transactions" / "tx-bad.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{not valid json", encoding="utf-8")

    result = replay_acceptance_transactions(plan_dir)
    assert "tx-valid" in result.committed
    assert "tx-bad" not in result.committed


# ---------------------------------------------------------------------------
# Snapshot path independence from observed_at
# ---------------------------------------------------------------------------


def test_snapshot_content_hash_excludes_observed_at(
    plan_dir: Path,
) -> None:
    """Two snapshots differing only in observed_at should share the same content hash
    and therefore the same storage path."""
    import time

    snap1 = _make_snapshot("txn-path-test")
    time.sleep(0.01)  # Ensure different observed_at
    snap2 = _make_snapshot("txn-path-test")

    # Content hashes should match (observed_at excluded from hash)
    assert snap1.content_hash == snap2.content_hash

    path1 = store_acceptance_snapshot(plan_dir, snap1)
    path2 = store_acceptance_snapshot(plan_dir, snap2)
    assert path1 == path2


# ---------------------------------------------------------------------------
# Multiple snapshots in the same prefix bucket
# ---------------------------------------------------------------------------


def test_multiple_snapshots_same_hash_prefix(
    plan_dir: Path,
) -> None:
    """Multiple snapshots with the same 2-char hash prefix coexist in the same dir."""
    # Create many snapshots; some will share hash prefixes
    snapshots = [_make_snapshot(f"txn-bucket-{i:03d}") for i in range(10)]
    paths = [store_acceptance_snapshot(plan_dir, snap) for snap in snapshots]

    # All should exist and be loadable
    for i, snap in enumerate(snapshots):
        assert paths[i].is_file()
        loaded = load_acceptance_snapshot(plan_dir, snap.content_hash)
        assert loaded is not None
        assert loaded.transaction_id == snap.transaction_id
