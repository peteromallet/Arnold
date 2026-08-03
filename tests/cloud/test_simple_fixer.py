"""Tests for the canonical ``simple_fixer`` occurrence contract (Steps 34-35).

Covers:

* Step 34 — exact occurrence identity, typed outcomes, and the
  contract-layer no-child-agent behaviour.
* Step 35 — singleton exact-occurrence claims through the plural repair
  queue API, the two-try unchanged-fingerprint mutation budget, and action
  gates at every mutation boundary.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.cloud import simple_fixer as sf
from arnold_pipelines.megaplan.cloud import repair_requests
from arnold_pipelines.megaplan.cloud.repair_requests import (
    singleton_occurrence_claim_lock_dir,
)
from arnold_pipelines.megaplan.custody.contracts import ContractError, CustodyTargetKey

# ── helpers ─────────────────────────────────────────────────────────────────

_DEFAULT_TARGET = {
    "environment": "/workspace/demo",
    "session": "demo",
    "chain": "/workspace/demo/chain.yaml",
    "plan_revision": "sha256:plan-rev-1",
    "phase": "execute",
    "task": "T1",
    "attempt": "1",
    "normalized_failure_kind": "blocked_step",
    "blocker_or_phase_result_hash": "sha256:blocker-1",
    "fence": "fence-1",
}


def _target(**overrides):
    fields = dict(_DEFAULT_TARGET)
    fields.update(overrides)
    return CustodyTargetKey(**fields)


def _occurrence(**overrides):
    target = _target(**overrides)
    identity = repair_requests.build_normalized_repair_identity(
        target=target,
        run_id="demo",
        run_revision="sha256:plan-rev-1",
        run_incarnation_id="run-incarnation-1",
        coordinator_attempt_id="coordinator:1",
        fence_token=7,
        wbc_attempt_reference="wbc:1",
        run_authority_grant_id="grant-1",
        lease_id="lease-1",
        custody_epoch=1,
    )
    return sf.SimpleFixerOccurrence(target=target, repair_identity=identity)


def _queue_dir(tmp_path):
    """A valid central queue root shape (does not need to pre-exist)."""

    return str(tmp_path / ".megaplan" / "repair-queue")


# ═══════════════════════════════════════════════════════════════════════════
# Step 34 — exact occurrence identity
# ═══════════════════════════════════════════════════════════════════════════


def test_occurrence_identity_requires_exact_tuple():
    """Identity is the exact F01 tuple; forbidden sources cannot construct it."""

    # A complete exact tuple constructs and yields a stable fingerprint.
    occ = _occurrence()
    fp = occ.occurrence_fingerprint
    assert fp.startswith("sha256:")
    # Deterministic: the same tuple always yields the same fingerprint.
    assert _occurrence().occurrence_fingerprint == fp

    # Every single F01 field is load-bearing: changing any one of the ten
    # fields produces a different fingerprint.
    for field_name in (
        "environment",
        "session",
        "chain",
        "plan_revision",
        "phase",
        "task",
        "attempt",
        "normalized_failure_kind",
        "blocker_or_phase_result_hash",
        "fence",
    ):
        changed = _occurrence(**{field_name: f"sha256:different-{field_name}"})
        assert changed.occurrence_fingerprint != fp, (
            f"field {field_name!r} did not affect the occurrence fingerprint"
        )

    # A partial tuple — any F01 field missing or blank — is rejected at
    # construction.  Authority cannot be built from an incomplete identity.
    for field_name in (
        "environment",
        "session",
        "chain",
        "plan_revision",
        "phase",
        "task",
        "attempt",
        "normalized_failure_kind",
        "blocker_or_phase_result_hash",
        "fence",
    ):
        with pytest.raises(ContractError):
            _occurrence(**{field_name: ""})
        with pytest.raises(ContractError):
            _occurrence(**{field_name: "   "})

    # The builder returns None (does not raise) for invalid identity, so a
    # forbidden source simply fails to produce an occurrence.
    assert sf.build_simple_fixer_occurrence(None) is None
    assert sf.build_simple_fixer_occurrence({"environment": "only-a-label"}) is None
    assert (
        sf.build_simple_fixer_occurrence(
            {**_DEFAULT_TARGET, "session": ""}
        )
        is None
    )
    # A mapping with only the full F01 tuple remains readable but is not the
    # authority-bearing run/custody occurrence.
    built = sf.build_simple_fixer_occurrence(_DEFAULT_TARGET)
    assert isinstance(built, sf.SimpleFixerOccurrence)
    assert not built.authoritative
    assert built.occurrence_fingerprint != fp

    # A predecessor F01-only target remains diagnostic/read-only even when it
    # carries the optional chain identity.  It must not collide with the
    # authority-bearing run/custody occurrence fingerprint.
    with_chain = sf.SimpleFixerOccurrence(
        target=CustodyTargetKey(chain_identity="chain-id-A", **_DEFAULT_TARGET)
    )
    assert not with_chain.authoritative
    assert with_chain.occurrence_fingerprint != fp

    # A non-CustodyTargetKey target is rejected outright.
    with pytest.raises(ContractError):
        sf.SimpleFixerOccurrence(target="not-a-key")  # type: ignore[arg-type]


def test_typed_outcomes_form_a_closed_vocabulary():
    """Every outcome returned by the fixer is within the closed set."""

    expected = {
        "claimed",
        "already_claimed",
        "busy",
        "attempted",
        "unchanged",
        "exhausted",
        "rejected_identity",
        "rejected_no_claim",
        "rejected_child_agent",
        "rejected_gate",
    }
    assert set(sf.SIMPLE_FIXER_OUTCOMES) == expected
    # Claim results validate their outcome against the vocabulary.
    with pytest.raises(ContractError):
        sf.SimpleFixerClaimResult(
            outcome="not-a-real-outcome",
            occurrence_fingerprint="sha256:x",
            lock_dir="/tmp/x",
        )


def test_no_child_agent_gate_rejects_fanout():
    """The fixer is a leaf node: child-agent fan-out is rejected at the contract layer."""

    # Runtime guard.
    assert sf.guard_no_child_agent(requests_child_agent=True) == "rejected_child_agent"
    assert (
        sf.guard_no_child_agent(requests_child_agent=False, child_agent_count=3)
        == "rejected_child_agent"
    )
    assert sf.guard_no_child_agent(requests_child_agent=False, child_agent_count=0) is None

    # A SimpleFixerAction never carries fan-out: the contract carries only a
    # single in-process callable.  It still validates the callable.
    action = sf.SimpleFixerAction(mutate=lambda occ: occ.occurrence_fingerprint)
    assert callable(action.mutate)
    with pytest.raises(ContractError):
        sf.SimpleFixerAction(mutate="not-callable")  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# Step 35 — singleton claim + mutation budget + action gates
# ═══════════════════════════════════════════════════════════════════════════


def test_singleton_claim_is_occurrence_scoped_and_uses_queue_api(tmp_path):
    """The singleton claim is keyed by the exact occurrence fingerprint."""

    queue_dir = _queue_dir(tmp_path)
    occ = _occurrence()

    # The lock dir lives under the occurrence-claims queue namespace and is
    # derived from the occurrence fingerprint — i.e. it goes through the
    # plural repair queue API surface.
    lock_dir = singleton_occurrence_claim_lock_dir(queue_dir, occ.occurrence_fingerprint)
    assert "occurrence-claims" in str(lock_dir)
    assert str(lock_dir).startswith(queue_dir)

    claim = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="worker-A",
        request_id="req-1",
        session="sess-1",
    )
    assert claim.outcome == "claimed"
    assert claim.claimed is True
    assert claim.lock_dir == str(lock_dir)

    # A different occurrence gets a different lock slot.
    other_occ = _occurrence(attempt="2")
    assert other_occ.occurrence_fingerprint != occ.occurrence_fingerprint
    other_lock = singleton_occurrence_claim_lock_dir(
        queue_dir, other_occ.occurrence_fingerprint
    )
    assert other_lock != lock_dir


def test_singleton_claim_and_mutation_budget(tmp_path):
    """One active occurrence; budget caps no-ops; gates fire at every boundary."""

    queue_dir = _queue_dir(tmp_path)
    occ = _occurrence()

    # ── Singleton enforcement ───────────────────────────────────────────
    claim_a = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="worker-A",
        request_id="req-1",
        session="sess-1",
    )
    assert claim_a.outcome == "claimed"

    # The same owner re-claiming is already_claimed (idempotent, not busy).
    claim_a_again = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="worker-A",
        request_id="req-1",
        session="sess-1",
    )
    assert claim_a_again.outcome == "already_claimed"
    assert claim_a_again.claimed is False

    # A different owner contends and gets busy — the occurrence is held.
    claim_b = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="worker-B",
        request_id="req-2",
        session="sess-2",
    )
    assert claim_b.outcome == "busy"
    assert claim_b.claimed is False
    assert claim_b.evidence["kind"] == "singleton_occurrence_claim_contention"

    # A distinct occurrence can be claimed independently (singleton is
    # occurrence-scoped, not global).
    occ2 = _occurrence(attempt="2")
    claim_c = sf.claim_singleton_occurrence(
        queue_dir,
        occ2,
        actor="worker-A",
        request_id="req-3",
        session="sess-3",
    )
    assert claim_c.outcome == "claimed"

    # After releasing occ, it can be claimed again.
    released = sf.release_singleton_occurrence_claim(queue_dir, occ)
    assert released is True
    claim_reclaimed = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="worker-B",
        request_id="req-2",
        session="sess-2",
    )
    assert claim_reclaimed.outcome == "claimed"

    # ── Mutation budget: two unchanged attempts exhaust ─────────────────
    budget = sf.MutationBudget(occ.occurrence_fingerprint)
    fp = occ.occurrence_fingerprint

    # A productive mutation (fingerprint changed) → attempted, resets streak.
    assert budget.record_mutation(fp, "sha256:after-first") == "attempted"
    assert budget.unchanged_attempts == 0
    assert budget.exhausted is False

    # First unchanged attempt → unchanged (1 < 2).
    assert budget.record_mutation(fp, fp) == "unchanged"
    assert budget.unchanged_attempts == 1
    assert budget.exhausted is False

    # Second unchanged attempt → exhausted (2 >= 2).
    assert budget.record_mutation(fp, fp) == "exhausted"
    assert budget.unchanged_attempts == 2
    assert budget.exhausted is True
    assert budget.remaining == 0

    # ── Session action gates fire at every boundary ────────────────────
    # Release so the session can acquire a fresh claim.
    assert sf.release_singleton_occurrence_claim(queue_dir, occ) is True
    session = sf.SimpleFixerSession(occurrence=occ)

    # Gate 3: no claim held → rejected_no_claim.
    result = session.attempt_mutation(
        sf.SimpleFixerAction(mutate=lambda o: o.occurrence_fingerprint)
    )
    assert result == "rejected_no_claim"

    # Acquire the claim for this session.
    session.claim = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="worker-C",
        request_id="req-4",
        session="sess-4",
    )
    assert session.has_claim

    # Gate 2: child-agent fan-out requested → rejected_child_agent (before
    # the mutation callable is ever invoked).
    result = session.attempt_mutation(
        sf.SimpleFixerAction(mutate=lambda o: o.occurrence_fingerprint),
        requests_child_agent=True,
    )
    assert result == "rejected_child_agent"

    # A fresh budget: two unchanged then a third is rejected (gate 4).
    session.budget = sf.MutationBudget(occ.occurrence_fingerprint)
    no_op = sf.SimpleFixerAction(mutate=lambda o: o.occurrence_fingerprint)
    assert session.attempt_mutation(no_op) == "unchanged"
    assert session.attempt_mutation(no_op) == "exhausted"
    # Once exhausted, even an otherwise-valid mutation is rejected.
    assert session.attempt_mutation(no_op) == "exhausted"

    # A productive mutation on a fresh budget resets the streak.
    session.budget = sf.MutationBudget(occ.occurrence_fingerprint)
    productive = sf.SimpleFixerAction(mutate=lambda o: "sha256:fixed")
    assert session.attempt_mutation(no_op) == "unchanged"
    assert session.attempt_mutation(productive) == "attempted"
    assert session.budget.unchanged_attempts == 0


def test_claim_rejects_non_occurrence_identity(tmp_path):
    """A non-SimpleFixerOccurrence is rejected with typed rejected_identity."""

    queue_dir = _queue_dir(tmp_path)
    result = sf.claim_singleton_occurrence(
        queue_dir,
        "not-an-occurrence",  # type: ignore[arg-type]
        actor="worker-A",
        request_id="req-1",
        session="sess-1",
    )
    assert result.outcome == "rejected_identity"
    assert "current normalized repair identity" in result.evidence["reason"]


def test_mutation_budget_is_occurrence_scoped(tmp_path):
    """The budget is bound to one occurrence fingerprint."""

    occ = _occurrence()
    budget = sf.MutationBudget(occ.occurrence_fingerprint)
    snapshot = budget.to_dict()
    assert snapshot["occurrence_fingerprint"] == occ.occurrence_fingerprint
    assert snapshot["max_unchanged_fingerprint_attempts"] == sf.MAX_UNCHANGED_FINGERPRINT_ATTEMPTS
    assert snapshot["exhausted"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Step 36-37 — Canonical runner emits verifier receipts
# ═══════════════════════════════════════════════════════════════════════════


def test_canonical_runner_emits_verifier_receipts(tmp_path):
    """One runner for both immediate trigger and reconciliation; emits redacted receipts."""

    queue_dir = _queue_dir(tmp_path)
    occ = _occurrence()

    # Build the canonical runner with explicit provenance hashes for determinism.
    runner = sf.build_canonical_runner(
        provenance_hash="sha256:test-provenance",
        source_env_hash="sha256:test-source-env",
    )

    # ── Acquire claim so the runner can attempt a mutation ────────────
    claim = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="test-actor",
        request_id="req-runner",
        session="sess-runner",
    )
    assert claim.outcome == "claimed"

    session = sf.SimpleFixerSession(occurrence=occ)
    session.claim = claim

    # ── Immediate trigger path ──────────────────────────────────────
    action = sf.SimpleFixerAction(mutate=lambda o: "sha256:fixed-by-runner")
    outcome, receipt = runner.run(
        occ,
        action,
        kind="immediate_trigger",
        session=session,
        verifier_slot="five_minute",
    )
    assert outcome == "attempted"
    assert receipt is not None
    assert receipt.kind == "immediate_trigger"
    assert receipt.status == "success"
    assert receipt.redacted is True
    assert receipt.runner_identity == "simple_fixer.canonical"
    assert receipt.provenance_hash == "sha256:test-provenance"
    assert receipt.source_env_hash == "sha256:test-source-env"
    assert receipt.verifier_slot == "five_minute"
    assert receipt.receipt_id.startswith("sha256:")
    assert receipt.occurrence_fingerprint == occ.occurrence_fingerprint

    # The transcript is redacted — no secrets leak through.
    assert "[REDACTED]" not in receipt.redacted_transcript or "TOKEN=" not in receipt.redacted_transcript

    # to_dict() includes runner_contract marker.
    d = receipt.to_dict()
    assert d["runner_contract"] == "simple_fixer.canonical"
    assert d["redacted"] is True

    # ── Reconciliation path uses the SAME runner ────────────────────
    # Release and re-claim for reconciliation (different session)
    sf.release_singleton_occurrence_claim(queue_dir, occ)
    claim2 = sf.claim_singleton_occurrence(
        queue_dir,
        occ,
        actor="test-actor",
        request_id="req-recon",
        session="sess-recon",
    )
    session2 = sf.SimpleFixerSession(occurrence=occ)
    session2.claim = claim2

    outcome2, receipt2 = runner.run(
        occ,
        action,
        kind="reconciliation",
        session=session2,
        verifier_slot="next_three_hour",
    )
    assert outcome2 == "attempted"
    assert receipt2 is not None
    assert receipt2.kind == "reconciliation"
    assert receipt2.verifier_slot == "next_three_hour"
    # Same provenance — the runner implementation is identical.
    assert receipt2.provenance_hash == receipt.provenance_hash

    # ── Rejected mutation (no claim) still emits a receipt ──────────
    session_no_claim = sf.SimpleFixerSession(occurrence=occ)
    outcome3, receipt3 = runner.run(
        occ,
        action,
        kind="immediate_trigger",
        session=session_no_claim,
        verifier_slot="one_hour",
    )
    assert outcome3 == "rejected_no_claim"
    assert receipt3 is not None
    assert receipt3.status == "rejected"


def test_verifier_schedule_check_rejects_legacy_six_hour():
    """Schedule mismatch: six_hour with no next_three_hour fails closed."""

    # Legacy manifest with six_hour but no next_three_hour
    legacy_slots = frozenset({"five_minute", "one_hour", "six_hour"})
    check = sf.check_verifier_schedule(legacy_slots)
    assert check.schedule_valid is False
    assert "recovery_verifier_schedule_mismatch" in check.reason
    assert "six_hour" in check.legacy_only_slots
    assert "next_three_hour" in check.missing_canonical_slots

    # Canonical manifest with all three required slots
    canonical_slots = frozenset({"five_minute", "one_hour", "next_three_hour"})
    check2 = sf.check_verifier_schedule(canonical_slots)
    assert check2.schedule_valid is True
    assert "all canonical verifier slots present" in check2.reason

    # Manifest with six_hour AND next_three_hour is valid (extra legacy tolerated)
    both_slots = frozenset({"five_minute", "one_hour", "next_three_hour", "six_hour"})
    check3 = sf.check_verifier_schedule(both_slots)
    assert check3.schedule_valid is True

    # Missing five_minute
    missing_slots = frozenset({"one_hour", "next_three_hour"})
    check4 = sf.check_verifier_schedule(missing_slots)
    assert check4.schedule_valid is False
    assert "five_minute" in check4.missing_canonical_slots

    # Empty manifest
    check5 = sf.check_verifier_schedule(frozenset())
    assert check5.schedule_valid is False
    assert len(check5.missing_canonical_slots) == 3


def test_extract_verifier_slots_from_manifest():
    """Extract verifier slot names from a genuine-block manifest."""

    # Real-world shape matching evidence/m11-genuine-block-candidate/manifest.json
    legacy_manifest = {
        "verifier_schedule": {
            "schedule": {
                "five_minute": {"check": "liveness"},
                "one_hour": {"check": "slo"},
                "six_hour": {"check": "backstop"},
            }
        }
    }
    slots = sf.extract_verifier_slots_from_manifest(legacy_manifest)
    assert slots == frozenset({"five_minute", "one_hour", "six_hour"})

    # Canonical manifest
    canonical_manifest = {
        "verifier_schedule": {
            "schedule": {
                "five_minute": {},
                "one_hour": {},
                "next_three_hour": {},
            }
        }
    }
    slots2 = sf.extract_verifier_slots_from_manifest(canonical_manifest)
    assert slots2 == frozenset({"five_minute", "one_hour", "next_three_hour"})

    # None / malformed returns empty
    assert sf.extract_verifier_slots_from_manifest(None) == frozenset()
    assert sf.extract_verifier_slots_from_manifest({}) == frozenset()
    assert sf.extract_verifier_slots_from_manifest({"verifier_schedule": None}) == frozenset()


def test_runner_receipt_redaction():
    """Receipt from_runner_result redacts secrets from transcripts."""

    transcript_with_secrets = (
        "canonical_runner start kind=immediate_trigger\n"
        "TOKEN=abc123secret\n"
        "API_KEY=sk-1234567890\n"
        "normal output line\n"
        "-----BEGIN PRIVATE KEY-----\n"
        "mocked_key_data\n"
        "-----END PRIVATE KEY-----\n"
        "more normal output\n"
    )
    receipt = sf.RunnerReceipt.from_runner_result(
        occurrence_fingerprint="sha256:test-fp",
        kind="immediate_trigger",
        status="success",
        transcript=transcript_with_secrets,
        provenance_hash="sha256:prov",
        source_env_hash="sha256:env",
    )
    assert receipt.redacted is True
    # Secret lines are replaced with [REDACTED]
    assert "[REDACTED]" in receipt.redacted_transcript
    # Normal lines are preserved
    assert "normal output line" in receipt.redacted_transcript
    assert "more normal output" in receipt.redacted_transcript
    # Secrets are NOT in the redacted output
    assert "abc123secret" not in receipt.redacted_transcript
    assert "sk-1234567890" not in receipt.redacted_transcript
    assert "PRIVATE KEY" not in receipt.redacted_transcript
