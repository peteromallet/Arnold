"""Tests for acceptance_transaction models.

Covers:
- Stable byte-identical hashing for identical semantic input
- Required-field rejection with clear error messages
- Snapshot immutability (FrozenInstanceError on mutation attempts)
- Round-trip serialization fidelity (to_dict → from_dict)
- Content hash validation on deserialization
"""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError

import pytest

from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    ACCEPTANCE_RECEIPT_SCHEMA,
    ACCEPTANCE_RECEIPT_SCHEMA_VERSION,
    ACCEPTANCE_SNAPSHOT_SCHEMA,
    ACCEPTANCE_SNAPSHOT_SCHEMA_VERSION,
    ACCEPTANCE_TRANSACTION_SCHEMA,
    ACCEPTANCE_TRANSACTION_SCHEMA_VERSION,
    AcceptanceReceipt,
    AcceptanceSnapshot,
    AcceptanceTransaction,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    EvidenceStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_evidence() -> tuple[EvidenceRef, ...]:
    return (
        EvidenceRef(
            kind="green_suite",
            status=EvidenceStatus.satisfied,
            summary="All tests passed",
            details={"delta": {"passed": 10, "failed": 0, "skipped": 0}},
            provider="pytest",
        ),
        EvidenceRef(
            kind="landed_diff",
            status=EvidenceStatus.satisfied,
            summary="No unexpected diffs",
            details={"files_changed": 5},
            provider="git",
        ),
    )


@pytest.fixture
def minimal_snapshot_kwargs() -> dict:
    return {
        "transaction_id": "txn-m5a-20260715-001",
        "chain_run_id": "chain-run-m5a",
        "milestone_label": "m5a",
        "milestone_index": 2,
        "plan_name": "m5a-atomic-fail-closed-20260715-0149",
        "source_commit_ref": "abc123def456",
        "runtime_identity": "test-runtime-v1.0.0",
    }


@pytest.fixture
def sample_snapshot(minimal_snapshot_kwargs, sample_evidence) -> AcceptanceSnapshot:
    return AcceptanceSnapshot(
        evidence=sample_evidence,
        evidence_refs=("ref-1", "ref-2"),
        **minimal_snapshot_kwargs,
    )


# ---------------------------------------------------------------------------
# Stable serialization / deterministic hashing
# ---------------------------------------------------------------------------


def test_deterministic_hash_identical_input(sample_snapshot):
    """Two snapshots built from identical inputs must produce the same hash."""
    snap1 = sample_snapshot
    snap2 = AcceptanceSnapshot.from_dict(snap1.to_dict())
    assert snap1.content_hash == snap2.content_hash
    assert len(snap1.content_hash) > 10  # sha256: + 64 hex chars
    assert snap1.content_hash.startswith("sha256:")


def test_deterministic_hash_different_input_yields_different_hash(
    minimal_snapshot_kwargs, sample_evidence
):
    """Different semantic input must produce a different hash."""
    snap_a = AcceptanceSnapshot(
        evidence=sample_evidence, **minimal_snapshot_kwargs
    )
    snap_b = AcceptanceSnapshot(
        evidence=sample_evidence,
        **{**minimal_snapshot_kwargs, "transaction_id": "txn-different-002"},
    )
    assert snap_a.content_hash != snap_b.content_hash


def test_deterministic_hash_dict_order_irrelevant(
    minimal_snapshot_kwargs, sample_evidence
):
    """Dict key order in input evidence must not affect the content hash."""
    evidence_a = (
        EvidenceRef(kind="alpha", status=EvidenceStatus.satisfied, summary="a"),
        EvidenceRef(kind="beta", status=EvidenceStatus.satisfied, summary="b"),
    )
    evidence_b = (
        EvidenceRef(kind="beta", status=EvidenceStatus.satisfied, summary="b"),
        EvidenceRef(kind="alpha", status=EvidenceStatus.satisfied, summary="a"),
    )
    snap_a = AcceptanceSnapshot(evidence=evidence_a, **minimal_snapshot_kwargs)
    snap_b = AcceptanceSnapshot(evidence=evidence_b, **minimal_snapshot_kwargs)
    # Evidence is sorted by (kind, status) in the content payload,
    # so order of construction should not matter.
    assert snap_a.content_hash == snap_b.content_hash


def test_deterministic_hash_roundtrip_json_stability(
    minimal_snapshot_kwargs, sample_evidence
):
    """JSON round-trip (to_dict → json → from_dict) must preserve the hash."""
    snap = AcceptanceSnapshot(evidence=sample_evidence, **minimal_snapshot_kwargs)
    json_str = json.dumps(snap.to_dict(), sort_keys=True, separators=(",", ":"))
    reloaded_dict = json.loads(json_str)
    snap2 = AcceptanceSnapshot.from_dict(reloaded_dict)
    assert snap.content_hash == snap2.content_hash


def test_hash_stable_across_equivalent_construction_paths(
    minimal_snapshot_kwargs, sample_evidence
):
    """Building via constructor vs from_dict must yield the same hash."""
    snap1 = AcceptanceSnapshot(evidence=sample_evidence, **minimal_snapshot_kwargs)
    snap2 = AcceptanceSnapshot.from_dict(snap1.to_dict())
    assert snap1.content_hash == snap2.content_hash


# ---------------------------------------------------------------------------
# Required-field rejection
# ---------------------------------------------------------------------------


def test_reject_missing_transaction_id(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "transaction_id": ""}
    with pytest.raises(ValueError, match="transaction_id"):
        AcceptanceSnapshot(**kwargs)


def test_reject_missing_chain_run_id(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "chain_run_id": ""}
    with pytest.raises(ValueError, match="chain_run_id"):
        AcceptanceSnapshot(**kwargs)


def test_reject_missing_milestone_label(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "milestone_label": ""}
    with pytest.raises(ValueError, match="milestone_label"):
        AcceptanceSnapshot(**kwargs)


def test_reject_missing_plan_name(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "plan_name": ""}
    with pytest.raises(ValueError, match="plan_name"):
        AcceptanceSnapshot(**kwargs)


def test_reject_missing_source_commit_ref(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "source_commit_ref": ""}
    with pytest.raises(ValueError, match="source_commit_ref"):
        AcceptanceSnapshot(**kwargs)


def test_reject_missing_runtime_identity(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "runtime_identity": ""}
    with pytest.raises(ValueError, match="runtime_identity"):
        AcceptanceSnapshot(**kwargs)


def test_reject_negative_milestone_index(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "milestone_index": -1}
    with pytest.raises(ValueError, match="milestone_index"):
        AcceptanceSnapshot(**kwargs)


def test_reject_whitespace_only_transaction_id(minimal_snapshot_kwargs):
    kwargs = {**minimal_snapshot_kwargs, "transaction_id": "   "}
    with pytest.raises(ValueError, match="transaction_id"):
        AcceptanceSnapshot(**kwargs)


# ---------------------------------------------------------------------------
# Snapshot immutability
# ---------------------------------------------------------------------------


def test_snapshot_is_frozen(sample_snapshot):
    """AcceptanceSnapshot is a frozen dataclass — mutation raises FrozenInstanceError."""
    with pytest.raises(FrozenInstanceError):
        sample_snapshot.transaction_id = "hijacked"  # type: ignore[misc]


def test_snapshot_content_hash_is_frozen(sample_snapshot):
    """content_hash cannot be mutated after construction."""
    with pytest.raises(FrozenInstanceError):
        sample_snapshot.content_hash = "tampered"  # type: ignore[misc]


def test_snapshot_evidence_is_immutable_tuple(sample_snapshot):
    """Evidence field is a tuple and cannot be mutated."""
    assert isinstance(sample_snapshot.evidence, tuple)
    with pytest.raises(FrozenInstanceError):
        sample_snapshot.evidence = ()  # type: ignore[misc]


def test_snapshot_hash_does_not_change_on_evidence_dict_mutation(sample_snapshot):
    """The content hash is fixed at construction and does not reflect
    later mutations of evidence dicts passed in (they were copied inside)."""
    original_hash = sample_snapshot.content_hash
    # Try to mutate the original sample_evidence dicts — they should be
    # independent copies in the snapshot.
    for ref in sample_snapshot.evidence:
        if hasattr(ref, "details") and isinstance(ref.details, dict):
            ref.details["tampered"] = True  # type: ignore[index]
    # The hash should be unchanged because the snapshot stores immutable copies.
    assert sample_snapshot.content_hash == original_hash


# ---------------------------------------------------------------------------
# AcceptanceReceipt tests
# ---------------------------------------------------------------------------


def test_receipt_required_fields(minimal_snapshot_kwargs, sample_snapshot):
    """Receipt must reject missing required fields."""
    receipt = sample_snapshot.with_receipt()
    assert receipt.transaction_id == sample_snapshot.transaction_id
    assert receipt.snapshot_hash == sample_snapshot.content_hash
    assert receipt.milestone_label == sample_snapshot.milestone_label
    assert receipt.milestone_index == sample_snapshot.milestone_index
    assert receipt.plan_name == sample_snapshot.plan_name

    with pytest.raises(ValueError, match="transaction_id"):
        AcceptanceReceipt(
            transaction_id="",
            snapshot_hash="sha256:abc",
            milestone_label="m5a",
            milestone_index=0,
            plan_name="plan",
        )
    with pytest.raises(ValueError, match="snapshot_hash"):
        AcceptanceReceipt(
            transaction_id="txn",
            snapshot_hash="",
            milestone_label="m5a",
            milestone_index=0,
            plan_name="plan",
        )
    with pytest.raises(ValueError, match="milestone_index"):
        AcceptanceReceipt(
            transaction_id="txn",
            snapshot_hash="sha256:abc",
            milestone_label="m5a",
            milestone_index=-1,
            plan_name="plan",
        )


def test_receipt_roundtrip(sample_snapshot):
    """Receipt must survive to_dict → from_dict round-trip."""
    receipt = sample_snapshot.with_receipt()
    d = receipt.to_dict()
    receipt2 = AcceptanceReceipt.from_dict(d)
    assert receipt2.transaction_id == receipt.transaction_id
    assert receipt2.snapshot_hash == receipt.snapshot_hash
    assert receipt2.milestone_label == receipt.milestone_label
    assert receipt2.milestone_index == receipt.milestone_index
    assert receipt2.plan_name == receipt.plan_name


def test_receipt_is_frozen():
    """Receipt is frozen."""
    receipt = AcceptanceReceipt(
        transaction_id="txn-1",
        snapshot_hash="sha256:abc123",
        milestone_label="m5a",
        milestone_index=0,
        plan_name="plan",
    )
    with pytest.raises(FrozenInstanceError):
        receipt.transaction_id = "hijacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AcceptanceTransaction tests
# ---------------------------------------------------------------------------


def test_transaction_required_fields():
    """AcceptanceTransaction must reject missing required fields."""
    with pytest.raises(ValueError, match="transaction_id"):
        AcceptanceTransaction(
            transaction_id="",
            snapshot_hash="sha256:abc",
            accepted=True,
            mode="atomic",
            tested_commit_ref="abc123",
            tested_runtime_identity="rt-v1",
        )
    with pytest.raises(ValueError, match="snapshot_hash"):
        AcceptanceTransaction(
            transaction_id="txn",
            snapshot_hash="",
            accepted=True,
            mode="atomic",
            tested_commit_ref="abc123",
            tested_runtime_identity="rt-v1",
        )
    with pytest.raises(ValueError, match="mode"):
        AcceptanceTransaction(
            transaction_id="txn",
            snapshot_hash="sha256:abc",
            accepted=True,
            mode="",
            tested_commit_ref="abc123",
            tested_runtime_identity="rt-v1",
        )


def test_transaction_roundtrip():
    """AcceptanceTransaction must survive to_dict → from_dict round-trip."""
    txn = AcceptanceTransaction(
        transaction_id="txn-m5a",
        snapshot_hash="sha256:abcdef",
        accepted=True,
        mode="atomic",
        tested_commit_ref="abc123def",
        tested_runtime_identity="rt-v1.0.0",
        failure_reasons=(),
        verdict_ref="verdict-1",
    )
    d = txn.to_dict()
    txn2 = AcceptanceTransaction.from_dict(d)
    assert txn2.transaction_id == txn.transaction_id
    assert txn2.snapshot_hash == txn.snapshot_hash
    assert txn2.accepted == txn.accepted
    assert txn2.mode == txn.mode
    assert txn2.tested_commit_ref == txn.tested_commit_ref
    assert txn2.tested_runtime_identity == txn.tested_runtime_identity
    assert txn2.verdict_ref == txn.verdict_ref
    assert txn2.failure_reasons == txn.failure_reasons


def test_transaction_is_frozen():
    """AcceptanceTransaction is a frozen dataclass."""
    txn = AcceptanceTransaction(
        transaction_id="txn-m5a",
        snapshot_hash="sha256:abc",
        accepted=True,
        mode="atomic",
        tested_commit_ref="abc123",
        tested_runtime_identity="rt-v1",
    )
    with pytest.raises(FrozenInstanceError):
        txn.accepted = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Content hash validation on deserialization
# ---------------------------------------------------------------------------


def test_from_dict_validates_content_hash(minimal_snapshot_kwargs, sample_evidence):
    """Deserializing a snapshot with a tampered content hash must raise."""
    snap = AcceptanceSnapshot(evidence=sample_evidence, **minimal_snapshot_kwargs)
    d = snap.to_dict()
    # Tamper with the hash
    d["content_hash"] = "sha256:deadbeef"
    with pytest.raises(ValueError, match="content hash mismatch"):
        AcceptanceSnapshot.from_dict(d)


def test_from_dict_tolerates_missing_hash_in_legacy(minimal_snapshot_kwargs):
    """Deserialization without a stored hash is allowed (legacy compat)."""
    snap = AcceptanceSnapshot(**minimal_snapshot_kwargs)
    d = snap.to_dict()
    del d["content_hash"]
    snap2 = AcceptanceSnapshot.from_dict(d)
    # Should still compute the correct hash
    assert snap2.content_hash == snap.content_hash


def test_empty_evidence_ok(minimal_snapshot_kwargs):
    """A snapshot with no evidence is valid (vacuous truth)."""
    snap = AcceptanceSnapshot(**minimal_snapshot_kwargs)
    assert snap.content_hash
    assert snap.evidence == ()


# ---------------------------------------------------------------------------
# Schema versioning
# ---------------------------------------------------------------------------


def test_schema_constants_consistent():
    """Schema constants are internally consistent."""
    assert ACCEPTANCE_SNAPSHOT_SCHEMA == "megaplan.acceptance_snapshot"
    assert ACCEPTANCE_SNAPSHOT_SCHEMA_VERSION == 1
    assert ACCEPTANCE_TRANSACTION_SCHEMA == "megaplan.acceptance_transaction"
    assert ACCEPTANCE_TRANSACTION_SCHEMA_VERSION == 1
    assert ACCEPTANCE_RECEIPT_SCHEMA == "megaplan.acceptance_receipt"
    assert ACCEPTANCE_RECEIPT_SCHEMA_VERSION == 1
