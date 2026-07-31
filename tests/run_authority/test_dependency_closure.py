"""Run Authority dependency-closure regressions (M11 Step 11).

These tests prove that five named classes of *apparent* progress can never be
counted as accepted authority without the full accepted kernel-evidence chain
reduced by :func:`reduce_run_authority`:

1. legacy ``done`` / terminal labels,
2. unresolved prerequisites (a claim whose kernel records are missing or stale),
3. cursor movement (advancing the journal cursor),
4. projection rebuild (re-reducing the same or augmented record set), and
5. repeated divergence (conflicting payloads for one identity, replayed).

The only path to accepted progress is a fully linked kernel chain:
``EvidenceEnvelope`` + ``CoordinatorFence`` + ``CapabilityGrant`` +
``SubjectAttempt`` + ``IdempotencyKey`` + ``Claim`` (and optionally a matching
``Decision``).  Labels, liveness, WBC-style receipts, and rebuildable
projections never mint authority on their own.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from arnold_pipelines.run_authority import (
    CapabilityGrant,
    Claim,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    IdempotencyKey,
    ObservationEnvelope,
    SubjectAttempt,
    reduce_run_authority,
)

RUN_ID = "run-A"
REVISION = "rev-A"


def _accepted_kernel_chain() -> tuple:
    """A fully linked kernel-evidence chain that the reducer *does* accept.

    Returned in dependency order: evidence, fence, grant, attempt, the claim's
    idempotency key, the claim, the decision's idempotency key, and the
    decision.  Every identity (run, revision, coordinator, fence token,
    subject, grant, attempt) agrees.
    """

    evidence = EvidenceEnvelope(
        "ev-1", RUN_ID, REVISION, "result", "worker://one", {"ok": True}
    )
    fence = CoordinatorFence(RUN_ID, REVISION, "coord-1", 7)
    grant = CapabilityGrant(
        "grant-1", RUN_ID, REVISION, "coord-1", 7,
        ("subject-1",), ("submit",), ("ev-1",),
    )
    attempt = SubjectAttempt(
        "attempt-1", RUN_ID, REVISION, "subject-1", "grant-1", "coord-1", 7, 1,
    )
    claim = Claim(
        "claim-1", RUN_ID, REVISION, "subject-1", "attempt-1", "grant-1", "coord-1", 7,
        "result", ("ev-1",), "claim-key", {"state": "complete"},
    )
    decision = Decision(
        "decision-1", RUN_ID, REVISION, "subject-1", "attempt-1", "grant-1", "coord-1", 7,
        "claim-1", "accepted", ("ev-1",), "decision-key", {"reason": "verified"},
    )
    return (
        evidence, fence, grant, attempt,
        IdempotencyKey("claim-key", claim.payload_hash), claim,
        IdempotencyKey("decision-key", decision.payload_hash), decision,
    )


def _legacy_done_label(legacy_id: str = "legacy-done") -> ObservationEnvelope:
    """A legacy terminal ``done`` label carried as a passive observation."""

    return ObservationEnvelope(
        legacy_id, RUN_ID, "old-rev", "terminal_status_label",
        "legacy://run-status", (), {"status": "done", "milestone": "complete"},
    )


def _accepted_ids(view) -> tuple[list[str], list[str]]:
    return (
        [item.claim_id for item in view.claims],
        [item.decision_id for item in view.decisions],
    )


# ---------------------------------------------------------------------------
# Positive baseline: the regression suite is not vacuously passing.
# ---------------------------------------------------------------------------

def test_positive_full_kernel_evidence_chain_is_accepted_progress() -> None:
    """A fully linked kernel chain is the one path that yields accepted progress."""

    view = reduce_run_authority(
        _accepted_kernel_chain(), run_id=RUN_ID, run_revision=REVISION, journal_cursor=8,
    )

    assert _accepted_ids(view) == (["claim-1"], ["decision-1"])
    assert view.quarantines == ()


def test_only_the_complete_kernel_chain_closes_dependencies() -> None:
    """Removing *any* single kernel record quarantines claim and decision.

    This is the dependency-closure invariant: every prerequisite record is
    load-bearing, so no subset of the chain can unlock accepted progress.
    """

    chain = _accepted_kernel_chain()
    full = reduce_run_authority(chain, run_id=RUN_ID, run_revision=REVISION)
    assert full.claims and full.decisions

    prerequisite_types = (
        EvidenceEnvelope, CoordinatorFence, CapabilityGrant,
        SubjectAttempt, IdempotencyKey,
    )
    for record_type in prerequisite_types:
        stripped = tuple(record for record in chain if not isinstance(record, record_type))
        view = reduce_run_authority(stripped, run_id=RUN_ID, run_revision=REVISION)

        assert view.claims == (), f"{record_type.__name__} removal must quarantine the claim"
        assert view.decisions == (), f"{record_type.__name__} removal must quarantine the decision"
        # The unresolved prerequisite is recorded as an explicit quarantine,
        # never silently dropped.
        assert any(q.reason.startswith("missing_matching") for q in view.quarantines), (
            f"{record_type.__name__} removal must emit a missing_matching_* quarantine"
        )


# ---------------------------------------------------------------------------
# Bug class 1 — legacy ``done`` labels.
# ---------------------------------------------------------------------------

def test_legacy_done_label_cannot_create_accepted_progress() -> None:
    legacy = _legacy_done_label()

    view = reduce_run_authority((legacy,), run_id=RUN_ID, run_revision=REVISION)

    # The label is preserved as a passive observation for auditability...
    assert [item.observation_id for item in view.observations] == ["legacy-done"]
    # ...but it mints no authority of any kind.
    assert view.claims == ()
    assert view.decisions == ()
    assert view.grants == () and view.attempts == () and view.fences == ()
    assert view.quarantines == ()


def test_legacy_done_label_does_not_rescue_unresolved_claim() -> None:
    chain = _accepted_kernel_chain()
    claim = next(record for record in chain if isinstance(record, Claim))
    legacy = _legacy_done_label("legacy-rescue")

    # A claim with NO kernel evidence plus a legacy ``done`` label: the label
    # still cannot stand in for the missing grant/fence/attempt/evidence.
    view = reduce_run_authority(
        (claim, legacy), run_id=RUN_ID, run_revision=REVISION,
    )

    assert view.claims == ()
    assert view.decisions == ()
    assert any(q.reason.startswith("missing_matching") for q in view.quarantines)
    # The legacy label survives only as an observation.
    assert [item.observation_id for item in view.observations] == ["legacy-rescue"]


# ---------------------------------------------------------------------------
# Bug class 2 — unresolved prerequisites.
# ---------------------------------------------------------------------------

def test_unresolved_prerequisite_cascades_to_decision_quarantine() -> None:
    chain = _accepted_kernel_chain()
    # Drop the grant: the claim's grant prerequisite is unresolved.
    records = tuple(record for record in chain if not isinstance(record, CapabilityGrant))

    view = reduce_run_authority(records, run_id=RUN_ID, run_revision=REVISION)

    assert view.claims == ()
    assert view.decisions == ()
    reasons = {q.reason for q in view.quarantines}
    # The claim is quarantined for its missing prerequisite grant...
    assert "missing_matching_grant" in reasons
    # ...and the decision cascades because it has no authoritative claim.
    assert "missing_authoritative_claim" in reasons


def test_stale_revision_prerequisite_is_not_accepted_progress() -> None:
    chain = _accepted_kernel_chain()
    # Rewrite the claim to a stale revision: its prerequisite linkage breaks
    # even though every record id is still present.
    claim = next(record for record in chain if isinstance(record, Claim))
    stale_claim = replace(claim, run_revision="stale-rev")

    records = tuple(stale_claim if record is claim else record for record in chain)
    view = reduce_run_authority(records, run_id=RUN_ID, run_revision=REVISION)

    assert view.claims == ()
    assert view.decisions == ()
    assert "missing_matching_revision" in {q.reason for q in view.quarantines}


# ---------------------------------------------------------------------------
# Bug class 3 — cursor movement.
# ---------------------------------------------------------------------------

def test_cursor_movement_alone_does_not_create_accepted_progress() -> None:
    legacy = _legacy_done_label("legacy-cursor")

    low = reduce_run_authority((legacy,), run_id=RUN_ID, run_revision=REVISION, journal_cursor=0)
    high = reduce_run_authority(
        (legacy,), run_id=RUN_ID, run_revision=REVISION, journal_cursor=999,
    )

    # Advancing the cursor never turns a legacy label into authority.
    assert low.claims == () and low.decisions == ()
    assert high.claims == () and high.decisions == ()
    # The cursor is faithfully recorded but confers no authority.
    assert low.journal_cursor == 0
    assert high.journal_cursor == 999


def test_cursor_movement_does_not_inflate_accepted_progress() -> None:
    chain = _accepted_kernel_chain()

    low = reduce_run_authority(chain, run_id=RUN_ID, run_revision=REVISION, journal_cursor=1)
    high = reduce_run_authority(
        chain, run_id=RUN_ID, run_revision=REVISION, journal_cursor=10_000,
    )

    # Accepted progress is identical regardless of how far the cursor advanced.
    assert _accepted_ids(low) == _accepted_ids(high) == (["claim-1"], ["decision-1"])
    assert low.evidence_set_digest == high.evidence_set_digest
    # Only the cursor and the derived view hash differ.
    assert low.journal_cursor != high.journal_cursor
    assert low.view_hash != high.view_hash


# ---------------------------------------------------------------------------
# Bug class 4 — projection rebuild.
# ---------------------------------------------------------------------------

def test_projection_rebuild_is_idempotent() -> None:
    chain = _accepted_kernel_chain()

    first = reduce_run_authority(chain, run_id=RUN_ID, run_revision=REVISION, journal_cursor=8)
    # Re-reduce the same records three times over (a full replay rebuild).
    rebuilt = reduce_run_authority(
        chain * 3, run_id=RUN_ID, run_revision=REVISION, journal_cursor=8,
    )

    assert first.to_dict() == rebuilt.to_dict()


def test_projection_rebuild_does_not_mint_authority_from_labels() -> None:
    chain = _accepted_kernel_chain()
    claim = next(record for record in chain if isinstance(record, Claim))
    legacy = _legacy_done_label("legacy-rebuild")

    # Rebuild an unresolved record set with legacy labels tacked on: rebuilding
    # the projection cannot conjure accepted progress that the kernel never had.
    view = reduce_run_authority(
        (claim, legacy, legacy, legacy), run_id=RUN_ID, run_revision=REVISION, journal_cursor=8,
    )

    assert view.claims == ()
    assert view.decisions == ()
    assert any(q.reason.startswith("missing_matching") for q in view.quarantines)


# ---------------------------------------------------------------------------
# Bug class 5 — repeated divergence.
# ---------------------------------------------------------------------------

def test_repeated_divergence_never_becomes_accepted_progress() -> None:
    chain = _accepted_kernel_chain()
    claim = next(record for record in chain if isinstance(record, Claim))
    claim_key = next(
        record for record in chain
        if isinstance(record, IdempotencyKey) and record.value == "claim-key"
    )

    # Two divergent payloads for the SAME claim identity (and idempotency key),
    # replayed many times to simulate repeated legacy divergence.
    divergent_claim = replace(claim, payload={"state": "failed"})
    divergent_key = IdempotencyKey("claim-key", divergent_claim.payload_hash)

    divergence_block = (claim, claim_key, divergent_claim, divergent_key)
    repeated = tuple(record for _ in range(5) for record in divergence_block)
    view = reduce_run_authority(
        repeated, run_id=RUN_ID, run_revision=REVISION, journal_cursor=20,
    )

    # No amount of repeated divergence is accepted as progress.
    assert view.claims == ()
    assert view.decisions == ()

    # Divergence is recorded as diagnostics, never resolved into authority.
    conflicts = [d for d in view.diagnostics if d.code == "conflicting_duplicate_key"]
    assert conflicts
    conflicted_ids = {c.record_id for c in conflicts}
    assert "claim-1" in conflicted_ids and "claim-key" in conflicted_ids


def test_repeated_legacy_done_labels_remain_observations_only() -> None:
    # The same legacy ``done`` label repeated many times collapses to one
    # observation and produces zero accepted progress.
    legacy = _legacy_done_label("legacy-repeat")
    view = reduce_run_authority(
        tuple(legacy for _ in range(10)),
        run_id=RUN_ID, run_revision=REVISION, journal_cursor=5,
    )

    assert [item.observation_id for item in view.observations] == ["legacy-repeat"]
    assert view.claims == ()
    assert view.decisions == ()
    assert view.quarantines == ()
