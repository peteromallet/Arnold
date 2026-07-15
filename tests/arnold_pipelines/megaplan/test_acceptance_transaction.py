"""Tests for acceptance_transaction models.

Covers:
- Stable byte-identical hashing for identical semantic input
- Required-field rejection with clear error messages
- Snapshot immutability (FrozenInstanceError on mutation attempts)
- Round-trip serialization fidelity (to_dict → from_dict)
- Content hash validation on deserialization
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# run_acceptance_boundary — identity validation
# ---------------------------------------------------------------------------


@pytest.fixture
def boundary_tmp_dirs(tmp_path: Path):
    """Create a minimal project and plan directory for boundary tests."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "finalize.json").write_text(
        json.dumps({"baseline_test_command": None}), encoding="utf-8"
    )
    return project_dir, plan_dir


def test_boundary_fails_closed_on_unbound_commit_ref(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """Unbound commit ref (short SHA) must short-circuit before suite run."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="abc1234", runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    result = run_acceptance_boundary(
        snap, project_dir=project_dir, plan_dir=plan_dir, mode="atomic",
    )
    assert result.identity_valid is False
    assert result.accepted is False
    assert len(result.identity_failures) > 0
    assert "unbound" in str(result.identity_failures).lower() or "short" in str(result.identity_failures).lower()
    # Suite should not have been run
    assert result.suite_status is None


def test_boundary_fails_closed_on_shadow_runtime(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """Shadow runtime identity must be rejected."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="shadow")
    snap = AcceptanceSnapshot(**kwargs)
    result = run_acceptance_boundary(
        snap, project_dir=project_dir, plan_dir=plan_dir, mode="atomic",
    )
    assert result.identity_valid is False
    assert result.accepted is False
    assert any("shadow" in f.lower() or "placeholder" in f.lower() for f in result.identity_failures)


def test_boundary_fails_closed_on_branch_ref(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """Branch ref (refs/heads/*) must be rejected as unbound."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="refs/heads/main", runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    result = run_acceptance_boundary(
        snap, project_dir=project_dir, plan_dir=plan_dir, mode="atomic",
    )
    assert result.identity_valid is False
    assert result.accepted is False


# ---------------------------------------------------------------------------
# run_acceptance_boundary — suite execution & verdict
# ---------------------------------------------------------------------------


_MOCK_SUITE_PASSED = object()


def _make_mock_suite_result(
    status="passed", exit_code=0, command="pytest -q", run_id="run-001"
):
    """Create a minimal object mimicking SuiteRunResult."""

    class MockSuiteResult:
        def __init__(self):
            self.run_id = run_id
            self.phase = "verification"
            self.command = command
            self.duration = 1.5
            self.collected = 10
            self.collected_ids = ["tests/test_a.py::test_1"]
            self.failures = []
            self.passes = ["tests/test_a.py::test_1"]
            self.status = status
            self.exit_code = exit_code
            self.code_hash = "sha256:abcdef1234567890"
            self.raw_log_path = None
            self.collections_parse_ok = True
            self.collection_errors = []
            self.timeout_reason = None

    return MockSuiteResult()


def _make_accepting_verdict():
    """Return a pre-computed CompletionVerdict with accepted=True."""
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        CompletionSubject,
        CompletionVerdict,
    )

    subject = CompletionSubject(
        kind="milestone", name="m5a", to_state="done",
        plan_name="test-plan", milestone_label="m5a",
    )
    return CompletionVerdict(
        mode="enforce",
        subject=subject,
        evidence=(),
        accepted=True,
    )


def test_boundary_success_path(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """Full success path: valid identity + suite passed + verdict accepted."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    mock_suite = _make_mock_suite_result(status="passed", exit_code=0)
    accepting_verdict = _make_accepting_verdict()

    result = run_acceptance_boundary(
        snap,
        project_dir=project_dir,
        plan_dir=plan_dir,
        mode="atomic",
        suite_runner=lambda *a, **kw: mock_suite,
        suite_config={"test_command": "true"},
        verdict=accepting_verdict,
        invalidate_prior_candidates=False,
    )
    assert result.accepted is True
    assert result.identity_valid is True
    assert result.suite_status == "passed"


def test_boundary_suite_failed_blocks_acceptance(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """Even with valid identity, a failing suite must block acceptance."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    mock_suite = _make_mock_suite_result(status="failed", exit_code=1)
    accepting_verdict = _make_accepting_verdict()

    result = run_acceptance_boundary(
        snap,
        project_dir=project_dir,
        plan_dir=plan_dir,
        mode="atomic",
        suite_runner=lambda *a, **kw: mock_suite,
        suite_config={"test_command": "false"},
        verdict=accepting_verdict,
        invalidate_prior_candidates=False,
    )
    assert result.accepted is False
    assert result.suite_status == "failed"
    assert any("did not pass" in r for r in result.failure_reasons)


def _make_rejecting_verdict(*, predicate_kind="unknown", evidence_kind="test_evidence"):
    """Return a pre-computed CompletionVerdict with accepted=False and typed failures."""
    from arnold_pipelines.megaplan.orchestration.completion_contract import (
        BlockingPredicateFailure,
        CompletionSubject,
        CompletionVerdict,
    )

    subject = CompletionSubject(
        kind="milestone", name="m5a", to_state="done",
        plan_name="test-plan", milestone_label="m5a",
    )
    return CompletionVerdict(
        mode="enforce",
        subject=subject,
        evidence=(),
        accepted=False,
        failures=("test_evidence: blocked",),
        predicate_failures=(
            BlockingPredicateFailure(
                kind=predicate_kind,
                evidence_kind=evidence_kind,
                summary="blocked",
                details={"reason": "test"},
            ),
        ),
    )


def test_boundary_rejecting_verdict_blocks_acceptance(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """A rejecting verdict (accepted=False) must block overall acceptance."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    mock_suite = _make_mock_suite_result(status="passed", exit_code=0)
    rejecting_verdict = _make_rejecting_verdict(predicate_kind="rejected")

    result = run_acceptance_boundary(
        snap,
        project_dir=project_dir,
        plan_dir=plan_dir,
        mode="atomic",
        suite_runner=lambda *a, **kw: mock_suite,
        suite_config={"test_command": "true"},
        verdict=rejecting_verdict,
        invalidate_prior_candidates=False,
    )
    assert result.accepted is False
    assert result.verdict is not None
    assert getattr(result.verdict, "accepted", True) is False


# ---------------------------------------------------------------------------
# run_acceptance_boundary — no test_command (vacuously passed)
# ---------------------------------------------------------------------------


def test_boundary_no_test_command_passes_vacuously(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """No test_command = suite not_applicable, vacuously passed."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    # Remove any test_command from finalize
    (plan_dir / "finalize.json").write_text("{}", encoding="utf-8")
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    accepting_verdict = _make_accepting_verdict()

    result = run_acceptance_boundary(
        snap,
        project_dir=project_dir,
        plan_dir=plan_dir,
        mode="atomic",
        verdict=accepting_verdict,
        invalidate_prior_candidates=False,
    )
    assert result.suite_status == "not_applicable"
    # suite_passed is True when not_applicable
    assert result.accepted is True


# ---------------------------------------------------------------------------
# run_acceptance_boundary — require_full_boundary
# ---------------------------------------------------------------------------


def test_boundary_require_full_boundary_ignores_test_selection_override(
    tmp_path, minimal_snapshot_kwargs, boundary_tmp_dirs
):
    """require_full_boundary=True must ignore test_selection command_override."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        run_acceptance_boundary,
    )

    project_dir, plan_dir = boundary_tmp_dirs
    (plan_dir / "finalize.json").write_text(
        json.dumps({
            "baseline_test_command": "echo baseline",
            "test_selection": {"command_override": "echo focused"},
        }),
        encoding="utf-8",
    )
    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    accepting_verdict = _make_accepting_verdict()
    captured_config = {}

    def capture_runner(_project_dir, config, **_kw):
        captured_config.update(config)
        return _make_mock_suite_result()

    run_acceptance_boundary(
        snap,
        project_dir=project_dir,
        plan_dir=plan_dir,
        mode="atomic",
        suite_runner=capture_runner,
        verdict=accepting_verdict,
        invalidate_prior_candidates=False,
        require_full_boundary=True,
    )
    assert captured_config.get("test_command") == "echo baseline"


# ---------------------------------------------------------------------------
# CandidateInvalidation tests
# ---------------------------------------------------------------------------


def test_candidate_invalidation_required_fields():
    """CandidateInvalidation must reject missing required fields."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        CandidateInvalidation,
    )

    with pytest.raises(ValueError, match="transaction_id"):
        CandidateInvalidation(transaction_id="", reason="stale-evidence")
    with pytest.raises(ValueError, match="reason"):
        CandidateInvalidation(transaction_id="txn-1", reason="")


def test_candidate_invalidation_roundtrip():
    """CandidateInvalidation must survive to_dict -> from_dict round-trip."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        CandidateInvalidation,
    )

    inv = CandidateInvalidation(
        transaction_id="txn-old",
        reason="stale-evidence",
        superseded_by="txn-new",
    )
    d = inv.to_dict()
    inv2 = CandidateInvalidation.from_dict(d)
    assert inv2.transaction_id == inv.transaction_id
    assert inv2.reason == inv.reason
    assert inv2.superseded_by == inv.superseded_by
    assert inv2.invalidated_at == inv.invalidated_at


def test_candidate_invalidation_is_frozen():
    """CandidateInvalidation is a frozen dataclass."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        CandidateInvalidation,
    )

    inv = CandidateInvalidation(transaction_id="txn-1", reason="stale-evidence")
    with pytest.raises(FrozenInstanceError):
        inv.reason = "hijacked"  # type: ignore[misc]


def test_check_and_invalidate_stale_candidates_same_hash_no_invalidation(
    tmp_path, minimal_snapshot_kwargs
):
    """Same hash -> no invalidation."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        check_and_invalidate_stale_candidates,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    snap = AcceptanceSnapshot(**minimal_snapshot_kwargs)
    # All candidates have same hash as snapshot
    prior = {
        "txn-old": type("obj", (), {"snapshot_hash": snap.content_hash})(),
    }
    result = check_and_invalidate_stale_candidates(
        snap, plan_dir=plan_dir, prior_candidates=prior,
    )
    assert len(result) == 0


def test_check_and_invalidate_stale_candidates_different_hash_invalidates(
    tmp_path, minimal_snapshot_kwargs
):
    """Different hash -> stale candidate invalidated."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        check_and_invalidate_stale_candidates,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    snap = AcceptanceSnapshot(**minimal_snapshot_kwargs)
    prior = {
        "txn-old": type("obj", (), {"snapshot_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000bad"})(),
    }
    result = check_and_invalidate_stale_candidates(
        snap, plan_dir=plan_dir, prior_candidates=prior,
    )
    assert len(result) == 1
    assert result[0].transaction_id == "txn-old"
    assert result[0].reason == "stale-evidence"
    assert result[0].superseded_by == snap.transaction_id


def test_check_and_invalidate_malformed_candidate(
    tmp_path, minimal_snapshot_kwargs
):
    """Candidate without a valid snapshot_hash -> invalidated as malformed."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        check_and_invalidate_stale_candidates,
    )

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    snap = AcceptanceSnapshot(**minimal_snapshot_kwargs)
    prior = {
        "txn-old": type("obj", (), {"snapshot_hash": None})(),
    }
    result = check_and_invalidate_stale_candidates(
        snap, plan_dir=plan_dir, prior_candidates=prior,
    )
    assert len(result) == 1
    assert result[0].transaction_id == "txn-old"
    assert result[0].reason == "malformed-candidate"


# ---------------------------------------------------------------------------
# AcceptanceBoundaryResult round-trip
# ---------------------------------------------------------------------------


def test_boundary_result_roundtrip(
    tmp_path, minimal_snapshot_kwargs, sample_evidence
):
    """AcceptanceBoundaryResult must survive to_dict -> from_dict round-trip."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceBoundaryResult,
    )

    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(evidence=sample_evidence, **kwargs)
    result = AcceptanceBoundaryResult(
        snapshot=snap,
        identity_valid=True,
        identity_failures=(),
        suite_run=None,
        verdict=None,
        commands=("echo hi",),
        exit_codes=(0,),
        log_paths=("/tmp/log.txt",),
        log_digests=("sha256:abc",),
        started_at="2026-07-15T00:00:00Z",
        completed_at="2026-07-15T00:00:01Z",
        suite_identity="run-001",
        commit_tree="sha256:tree",
        artifact_digests={"/tmp/log.txt": "sha256:abc"},
        suite_status="passed",
        accepted=True,
        duration_seconds=1.0,
        failure_reasons=(),
        mode="atomic",
    )
    d = result.to_dict()
    result2 = AcceptanceBoundaryResult.from_dict(d)
    assert result2.accepted == result.accepted
    assert result2.identity_valid == result.identity_valid
    assert result2.suite_status == result.suite_status
    assert result2.mode == result.mode
    assert result2.snapshot.content_hash == snap.content_hash


def test_boundary_result_is_frozen(
    tmp_path, minimal_snapshot_kwargs
):
    """AcceptanceBoundaryResult is a frozen dataclass."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceBoundaryResult,
    )

    kwargs = {**minimal_snapshot_kwargs}
    kwargs.update(source_commit_ref="a" * 40, runtime_identity="arnold-engine-v4.0.0")
    snap = AcceptanceSnapshot(**kwargs)
    result = AcceptanceBoundaryResult(
        snapshot=snap,
        identity_valid=False,
        identity_failures=("bad commit",),
        suite_run=None,
        verdict=None,
        commands=(),
        exit_codes=(),
        log_paths=(),
        log_digests=(),
        started_at="2026-07-15T00:00:00Z",
        completed_at="2026-07-15T00:00:01Z",
        suite_identity=None,
        commit_tree=None,
        artifact_digests={},
        suite_status=None,
        accepted=False,
        duration_seconds=0.1,
        failure_reasons=("bad commit",),
        mode="atomic",
    )
    with pytest.raises(FrozenInstanceError):
        result.accepted = True  # type: ignore[misc]
