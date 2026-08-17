"""Focused Maintenance independent-verification tests (M3 Step 7 / T8).

These tests prove the pure blocker-specific verifier:

* durable distinct-principal provenance (credential/runtime envelope ref +
  direct owner-source read refs) is required;
* the repair producer and any same-principal verifier are rejected
  (self-declared independence);
* only a coherent, complete, fresh direct owner-source envelope verifies —
  torn, contradictory, unknown, stale, or cross-authority evidence fails
  closed;
* accepted M10/C2 negative controls are translated (never re-classified),
  with missing controls typed UNKNOWN and a failed control typed
  FAILED_CONTROL;
* terminal verification requires durable authoritative progress beyond the
  pre-repair checkpoint (liveness-only evidence is corroboration only) and
  the complete required checkpoint set (`six_hour` is a read alias for
  `next_three_hour`);
* outcomes are the closed vocabulary open / unknown / incoherent /
  failed_control / verified, round-trip through the canonical strict codec,
  and the module imports no owner authority store.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
    SourceVersionVector,
)
from arnold_pipelines.megaplan.maintenance.events import (
    CheckpointWindowKind,
    VerifierProvenance,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    OwnerRef,
    UtcTime,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ProducerPrincipal,
    ProducerRole,
)
from arnold_pipelines.megaplan.maintenance.verification import (
    ExpectedAuthority,
    NegativeControlResult,
    VerificationOutcome,
    VerificationRejectReason,
    VerificationResult,
    authoritative_progress_refs,
    checkpoint_set_complete,
    evaluate_verification,
    negative_controls_passed,
    progress_beyond,
    required_checkpoint_set,
)

UTC = timezone.utc

IMMEDIATE = CheckpointWindowKind.IMMEDIATE
FIVE_MINUTE = CheckpointWindowKind.FIVE_MINUTE
ONE_HOUR = CheckpointWindowKind.ONE_HOUR
NEXT_THREE_HOUR = CheckpointWindowKind.NEXT_THREE_HOUR

COMPLETE_SET = (IMMEDIATE, FIVE_MINUTE, ONE_HOUR, NEXT_THREE_HOUR)

#: Owner stores / seams Maintenance domain modules must never import.
_FORBIDDEN_OWNER_IMPORTS = (
    "lease_store",
    "action_validator",
    "attempt_ledger_store",
    "repair_requests",
    "simple_fixer",
    "completion_engine",
    "transition_writer",
    "repair_queue",
    "controlled_writers",
)

_MODULE_DIR = Path(__file__).resolve().parents[3] / "arnold_pipelines" / "megaplan" / "maintenance"


def _ts() -> datetime:
    return datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _ref(
    owner: str = "repair_custody",
    record_type: str = "effect",
    locator: str = "effect://occ-1/9",
    digest: str | None = None,
    cursor: str = "journal:9",
) -> OwnerRef:
    return OwnerRef(
        owner=owner,
        record_type=record_type,
        identity="occ-1",
        schema_version="1",
        locator=locator,
        digest=digest if digest is not None else "e" * 64,
        cursor=cursor,
    )


def _vector(owner: str, before: str = "f" * 64, after: str = "f" * 64) -> SourceVersionVector:
    return SourceVersionVector(
        owner=owner,
        source=owner,
        environment=EnvironmentId("production"),
        before=before,
        after=after,
    )


def _envelope(
    *,
    coherence: CoherenceState = CoherenceState.COHERENT,
    completeness: CompletenessState = CompletenessState.COMPLETE,
    freshness: FreshnessState = FreshnessState.FRESH,
    reasons: tuple[CoherenceReason, ...] = (),
    run: str = "run-1",
    attempt: str = "att-1",
) -> ObservationEnvelope:
    return ObservationEnvelope.build(
        observed_at=UtcTime(_ts()),
        environment="production",
        run=run,
        attempt=attempt,
        version_vectors=(_vector("run_authority"), _vector("wbc")),
        references=(
            OwnerRef(
                owner="run_authority",
                record_type="grant",
                identity=run,
                schema_version="1",
                locator="grant://g-1",
                digest="c" * 64,
                cursor="journal:1",
            ),
            OwnerRef(
                owner="wbc",
                record_type="attempt",
                identity=attempt,
                schema_version="1",
                locator="attempt://att-1",
                digest="b" * 64,
                cursor="journal:1",
            ),
        ),
        completeness=completeness,
        freshness=freshness,
        coherence=coherence,
        coherence_reasons=reasons,
    )


_MISSING = object()


def _provenance(
    principal: str = "verifier-1",
    *,
    credential_envelope_ref: OwnerRef | None | object = _MISSING,
    direct_read_refs: tuple[OwnerRef, ...] | None | object = _MISSING,
) -> VerifierProvenance:
    # ``None`` is an explicit "missing" value; the sentinel selects the
    # durable default so tests can exercise both shapes.
    if credential_envelope_ref is _MISSING:
        credential_envelope_ref = _ref(
            "snapshot", "credential_envelope", "envelope://verifier-1/1", digest="3" * 64
        )
    if direct_read_refs is _MISSING:
        direct_read_refs = (
            _ref("run_authority", "grant", "grant://g-1", digest="4" * 64),
            _ref("wbc", "attempt", "attempt://att-1", digest="5" * 64),
        )
    return VerifierProvenance(
        principal=principal,
        runtime_digest="1" * 64,
        source_digest="2" * 64,
        credential_envelope_ref=credential_envelope_ref,
        observed_at=UtcTime(_ts()),
        direct_read_refs=direct_read_refs,
    )


def _producer(principal: str = "producer-1") -> ProducerPrincipal:
    return ProducerPrincipal(principal=principal, role=ProducerRole.REPAIR_PRODUCER)


def _controls(blocker_absent: bool = True) -> tuple[NegativeControlResult, ...]:
    return (
        NegativeControlResult(
            control_id="c2-f01",
            control_ref=_ref("conformance", "negative_control", "control://c2/f01", digest="6" * 64),
            blocker_absent=blocker_absent,
        ),
    )


def _pre_repair_ref() -> OwnerRef:
    return _ref("repair_custody", "checkpoint", "checkpoint://occ-1/pre", digest="d" * 64, cursor="journal:5")


def _progress_refs() -> tuple[OwnerRef, ...]:
    return (_ref("repair_custody", "effect", "effect://occ-1/9", digest="e" * 64, cursor="journal:9"),)


def _evaluate(
    *,
    terminal: bool = True,
    completed: tuple[Any, ...] = COMPLETE_SET,
    controls: tuple[NegativeControlResult, ...] | None = None,
    progress_refs: tuple[OwnerRef, ...] | None = None,
    pre_repair_ref: OwnerRef | None = None,
    provenance: VerifierProvenance | None = None,
    producer: ProducerPrincipal | None = None,
    envelope: ObservationEnvelope | None = None,
    expected: ExpectedAuthority | None = None,
) -> VerificationResult:
    return evaluate_verification(
        provenance=provenance if provenance is not None else _provenance(),
        producer=producer if producer is not None else _producer(),
        envelope=envelope if envelope is not None else _envelope(),
        negative_controls=controls if controls is not None else _controls(),
        completed_checkpoints=completed,
        pre_repair_ref=pre_repair_ref if pre_repair_ref is not None else _pre_repair_ref(),
        progress_refs=progress_refs if progress_refs is not None else _progress_refs(),
        expected=expected,
        terminal=terminal,
    )


# ---------------------------------------------------------------------------
# Verified paths
# ---------------------------------------------------------------------------


def test_terminal_verification_verified_with_full_evidence() -> None:
    result = _evaluate()
    assert result.outcome is VerificationOutcome.VERIFIED
    assert result.reasons == ()
    assert result.terminal is True
    assert result.verifier_principal == "verifier-1"
    assert result.proof_mode == "negative_control"
    assert result.negative_control_result == "passed"
    assert result.resumed_progress is True
    assert result.verified_windows == COMPLETE_SET


def test_checkpoint_verification_is_verified_but_nonterminal() -> None:
    # Non-terminal checkpoint evidence does not require the complete set.
    result = _evaluate(
        terminal=False,
        completed=(IMMEDIATE, FIVE_MINUTE),
    )
    assert result.outcome is VerificationOutcome.VERIFIED
    assert result.terminal is False
    assert result.verified_windows == (IMMEDIATE, FIVE_MINUTE)


def test_six_hour_alias_completes_the_required_set() -> None:
    # Legacy six_hour naming is a read alias for next_three_hour.
    completed = (IMMEDIATE, FIVE_MINUTE, ONE_HOUR, "six_hour")
    assert checkpoint_set_complete(completed)
    result = _evaluate(completed=completed)
    assert result.outcome is VerificationOutcome.VERIFIED
    assert result.terminal is True
    assert NEXT_THREE_HOUR in result.verified_windows


# ---------------------------------------------------------------------------
# Distinct principal and provenance
# ---------------------------------------------------------------------------


def test_repair_producer_cannot_author_verification() -> None:
    result = _evaluate(
        provenance=_provenance(principal="producer-1"),
        producer=_producer(principal="producer-1"),
    )
    assert result.outcome is VerificationOutcome.INCOHERENT
    assert VerificationRejectReason.REPAIR_PRODUCER_AUTHORED in result.reasons
    assert VerificationRejectReason.SELF_VERIFICATION in result.reasons
    assert result.terminal is False


def test_self_declared_independence_same_principal_rejected() -> None:
    # Even a VERIFIER-role producer cannot be its own independent verifier.
    producer = ProducerPrincipal(principal="dual-1", role=ProducerRole.VERIFIER)
    result = _evaluate(
        provenance=_provenance(principal="dual-1"),
        producer=producer,
    )
    assert result.outcome is VerificationOutcome.INCOHERENT
    assert VerificationRejectReason.SELF_VERIFICATION in result.reasons
    assert result.terminal is False


def test_missing_credential_envelope_ref_is_missing_provenance() -> None:
    result = _evaluate(provenance=_provenance(credential_envelope_ref=None))
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.MISSING_PROVENANCE in result.reasons


def test_missing_direct_read_refs_is_missing_provenance() -> None:
    result = _evaluate(provenance=_provenance(direct_read_refs=()))
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.MISSING_PROVENANCE in result.reasons


# ---------------------------------------------------------------------------
# Direct owner-source envelope (T6 capture)
# ---------------------------------------------------------------------------


def test_torn_envelope_is_incoherent() -> None:
    envelope = _envelope(
        coherence=CoherenceState.INCOHERENT,
        reasons=(CoherenceReason.VERSION_TEAR,),
    )
    result = _evaluate(envelope=envelope)
    assert result.outcome is VerificationOutcome.INCOHERENT
    assert VerificationRejectReason.TORN_ENVELOPE in result.reasons


def test_contradictory_envelope_is_incoherent() -> None:
    envelope = _envelope(
        coherence=CoherenceState.INCOHERENT,
        reasons=(CoherenceReason.CONTRADICTORY_EVIDENCE,),
    )
    result = _evaluate(envelope=envelope)
    assert result.outcome is VerificationOutcome.INCOHERENT
    assert VerificationRejectReason.INCOHERENT_EVIDENCE in result.reasons


def test_unknown_envelope_is_unknown() -> None:
    envelope = _envelope(
        coherence=CoherenceState.UNKNOWN,
        reasons=(CoherenceReason.UNKNOWN,),
    )
    result = _evaluate(envelope=envelope)
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.UNKNOWN_EVIDENCE in result.reasons


def test_stale_envelope_is_stale_authority() -> None:
    result = _evaluate(envelope=_envelope(freshness=FreshnessState.STALE))
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.STALE_AUTHORITY in result.reasons


def test_partial_envelope_is_unknown() -> None:
    result = _evaluate(envelope=_envelope(completeness=CompletenessState.PARTIAL))
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.UNKNOWN_EVIDENCE in result.reasons


def test_run_mismatch_is_stale_authority() -> None:
    envelope = _envelope(run="run-9")
    result = _evaluate(
        envelope=envelope,
        expected=ExpectedAuthority(run_id="run-1", attempt_id="att-1"),
    )
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.STALE_AUTHORITY in result.reasons


def test_attempt_mismatch_is_stale_authority() -> None:
    envelope = _envelope(attempt="att-9")
    result = _evaluate(
        envelope=envelope,
        expected=ExpectedAuthority(run_id="run-1", attempt_id="att-1"),
    )
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.STALE_AUTHORITY in result.reasons


# ---------------------------------------------------------------------------
# Accepted negative controls (M10/C2 translation)
# ---------------------------------------------------------------------------


def test_missing_negative_control_is_unknown() -> None:
    result = _evaluate(controls=())
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.MISSING_NEGATIVE_CONTROL in result.reasons
    assert result.negative_control_result == "unknown"


def test_failed_negative_control_returns_failed_control() -> None:
    result = _evaluate(controls=_controls(blocker_absent=False))
    assert result.outcome is VerificationOutcome.FAILED_CONTROL
    assert VerificationRejectReason.FAILED_CONTROL in result.reasons
    assert result.negative_control_result == "failed"
    assert result.terminal is False


def test_negative_control_requires_durable_content_addressed_ref() -> None:
    with pytest.raises(ValueError):
        NegativeControlResult(
            control_id="c2-f01",
            control_ref=OwnerRef(owner="conformance", locator="control://c2/f01"),
            blocker_absent=True,
        )


# ---------------------------------------------------------------------------
# Authoritative progress beyond the pre-repair checkpoint
# ---------------------------------------------------------------------------


def test_liveness_only_progress_is_corroboration_only() -> None:
    liveness = (
        OwnerRef(owner="snapshot", locator="pid://1234", digest="7" * 64),
        OwnerRef(owner="snapshot", locator="tmux://sess", digest="8" * 64),
    )
    assert authoritative_progress_refs(liveness) == ()
    result = _evaluate(progress_refs=liveness)
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.LIVENESS_ONLY in result.reasons
    assert result.resumed_progress is False


def test_progress_not_beyond_pre_repair_checkpoint_rejected() -> None:
    pre_repair = _ref("repair_custody", "checkpoint", "checkpoint://occ-1/pre", digest="d" * 64, cursor="journal:9")
    progress = (_ref("repair_custody", "effect", "effect://occ-1/5", digest="e" * 64, cursor="journal:5"),)
    assert progress_beyond(pre_repair, progress) is False
    result = _evaluate(pre_repair_ref=pre_repair, progress_refs=progress)
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.NO_PROGRESS in result.reasons


def test_progress_digest_change_counts_when_cursor_is_absent() -> None:
    pre_repair = _ref("repair_custody", "checkpoint", "checkpoint://occ-1/pre", digest="d" * 64, cursor=None)
    progress = (_ref("repair_custody", "effect", "effect://occ-1/9", digest="e" * 64, cursor=None),)
    assert progress_beyond(pre_repair, progress) is True
    result = _evaluate(pre_repair_ref=pre_repair, progress_refs=progress)
    assert result.outcome is VerificationOutcome.VERIFIED


# ---------------------------------------------------------------------------
# Complete required checkpoint set for terminal verification
# ---------------------------------------------------------------------------


def test_incomplete_checkpoint_set_keeps_terminal_open() -> None:
    result = _evaluate(completed=(IMMEDIATE, FIVE_MINUTE, ONE_HOUR))
    assert result.outcome is VerificationOutcome.OPEN
    assert VerificationRejectReason.INCOMPLETE_CHECKPOINTS in result.reasons
    assert result.terminal is False


def test_required_checkpoint_set_is_the_four_canonical_windows() -> None:
    assert required_checkpoint_set() == COMPLETE_SET
    assert checkpoint_set_complete(COMPLETE_SET) is True
    assert checkpoint_set_complete((IMMEDIATE,)) is False


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------


def test_verification_result_round_trips_through_strict_codec() -> None:
    result = _evaluate()
    text = canonical_dumps(result)
    decoded = strict_loads(VerificationResult, text)
    assert decoded.outcome is VerificationOutcome.VERIFIED
    assert decoded.terminal is True
    assert decoded.reasons == ()
    assert decoded.verified_windows == COMPLETE_SET
    assert canonical_digest(decoded) == canonical_digest(result)


def test_verified_result_cannot_carry_reasons() -> None:
    with pytest.raises(ValueError):
        VerificationResult(
            outcome=VerificationOutcome.VERIFIED,
            reasons=(VerificationRejectReason.LIVENESS_ONLY,),
        )


def test_non_verified_result_requires_a_typed_reason() -> None:
    with pytest.raises(ValueError):
        VerificationResult(outcome=VerificationOutcome.UNKNOWN)


def test_only_verified_may_be_terminal() -> None:
    with pytest.raises(ValueError):
        VerificationResult(
            outcome=VerificationOutcome.OPEN,
            reasons=(VerificationRejectReason.INCOMPLETE_CHECKPOINTS,),
            terminal=True,
        )


# ---------------------------------------------------------------------------
# Cohesion: no owner authority store in the Maintenance verifier
# ---------------------------------------------------------------------------


def test_verification_module_never_imports_owner_authority_stores() -> None:
    source = (_MODULE_DIR / "verification.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    for name in imported:
        for forbidden in _FORBIDDEN_OWNER_IMPORTS:
            assert forbidden not in name, (
                f"verification.py must not import owner authority seam {forbidden!r} "
                f"(found in import {name!r})"
            )
