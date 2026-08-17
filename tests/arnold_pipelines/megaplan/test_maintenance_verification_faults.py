"""Maintenance fault-corpus verification tests (M3 Plan Step 8 / T9).

Parameterizes the independent-verification decision surface
(:func:`evaluate_verification`) from the EXISTING owner fault corpus by
scenario identity and content digest — never by copying owner payloads into
a second Maintenance conformance suite:

* ``evidence/m10-f01-f17-fault-matrix.json`` — F01-F17 scenario identities
  (id, label, custody_precondition, injection_edge, replay_expectation) and
  the live file digest recorded in ``evidence/m10-handoff.json``;
* ``evidence/m10-c01-c20-conformance.json`` — C01-C20 bound-file digests and
  the C18 independent-verifier / negative-control / next-three-hour SLO
  requirements;
* ``evidence/m11-genuine-block-candidate/manifest.json`` — verifier
  separation (the verifier must not be the process that produced the
  failure), kill switch, rollback, and runtime provenance;
* ``evidence/m10-recovery-slo-receipt.json`` — the legitimate long-call
  scenario (``blocker-slow-1``, p95 420.0s > 300.0s target) with typed
  escalation;
* the strict handoff registry's S2R row — accepted S2R references are
  consumed by exact content digest; an unavailable (pending) S2R row is typed
  UNKNOWN and is never treated as accepted evidence (SC9).

Every case asserts the typed fail-closed outcome of the verifier
(open / unknown / incoherent / failed_control / verified); it never
re-implements the owner's fault injectors, providers, or classifiers, and it
never re-asserts the owner suite's prose expectations verbatim (guarded by
:func:`test_evidence_payloads_are_consumed_by_identity_not_copied`).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
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
from arnold_pipelines.megaplan.maintenance.handoffs import (
    ApprovalEvidence,
    ApprovalState,
    HandoffRegistry,
    HandoffResolutionReason,
    HandoffResolutionState,
    HandoffRow,
    build_handoff_view,
    default_handoff_registry,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    OwnerRef,
    UtcTime,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ProducerPrincipal,
    ProducerRole,
)
from arnold_pipelines.megaplan.maintenance.sources import (
    NativeManifestAdapter,
    RuntimeAdapter,
    RUNTIME_SOURCE_PATHS,
)
from arnold_pipelines.megaplan.maintenance.verification import (
    ExpectedAuthority,
    NegativeControlResult,
    VerificationOutcome,
    VerificationRejectReason,
    evaluate_verification,
)

UTC = timezone.utc

IMMEDIATE = CheckpointWindowKind.IMMEDIATE
FIVE_MINUTE = CheckpointWindowKind.FIVE_MINUTE
ONE_HOUR = CheckpointWindowKind.ONE_HOUR
NEXT_THREE_HOUR = CheckpointWindowKind.NEXT_THREE_HOUR

COMPLETE_SET = (IMMEDIATE, FIVE_MINUTE, ONE_HOUR, NEXT_THREE_HOUR)

# ---------------------------------------------------------------------------
# Content-addressed evidence identities (frozen owner artifacts)
# ---------------------------------------------------------------------------
#: sha256 of evidence/m10-f01-f17-fault-matrix.json — recorded verbatim in
#: evidence/m10-handoff.json source_artifacts and re-verified live below.
FAULT_MATRIX_SHA256 = "5d0b6080d75b666dedc3ab63c4cfe54cd6d1a3d293d3649243353b85eeaf3590"
#: sha256 of evidence/m10-c01-c20-conformance.json — recorded verbatim in
#: evidence/m10-handoff.json source_artifacts and re-verified live below.
CONFORMANCE_SHA256 = "f66346dfebccefe461e386aa68f5ff897925a6ac3f7650f9bca88f9c017b605b"
#: sha256 of evidence/m11-genuine-block-candidate/manifest.json (pinned live).
GENUINE_BLOCK_MANIFEST_SHA256 = "f2d4145e000b5a0835ce07d72e8173f814f4d49939452ed36c3dc327fd26c093"
#: sha256 of evidence/m10-recovery-slo-receipt.json (pinned live).
SLO_RECEIPT_SHA256 = "cc5adcd7e54b8bcb60707148fb758e86a0f983fc906d12652f70095de65749cb"

#: Content digests recorded INSIDE evidence/m10-c01-c20-conformance.json
#: (bound_files) — asserted by identity, never recomputed or guessed.
ACTION_VALIDATOR_HASH = "c6a0bb262224ade0237bbaa9018f6afd8284cfa12a00f7735f7973b1996ff5c8"
RECOVERY_VERIFIER_HASH = "267158034df3bca0da8f215ee913ec1f561b24bc281e9ea90f94e578ceb95ae0"
RUNTIME_ATTESTATION_HASH = "4d6680f2c3a007f869e42847f780396cd54446ae58337dc58b64ab376e702ed1"
SIX_HOUR_AUDITOR_HASH = "244d10f6c51396b63035099ec2b4f9381d25e2ff319abaea977a964c1c4c1679"

#: Accepted S2R content digest used by the test-scoped accepted registry.
S2R_ACCEPTED_DIGEST = "a1" * 32  # 64 lowercase hex chars


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=None)
def _load_json(relative: str) -> dict[str, Any]:
    path = _repo_root() / relative
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _live_sha256(relative: str) -> str:
    return hashlib.sha256((_repo_root() / relative).read_bytes()).hexdigest()


def _fault_matrix() -> dict[str, Any]:
    return _load_json("evidence/m10-f01-f17-fault-matrix.json")


def _conformance() -> dict[str, Any]:
    return _load_json("evidence/m10-c01-c20-conformance.json")


def _genuine_block_manifest() -> dict[str, Any]:
    return _load_json("evidence/m11-genuine-block-candidate/manifest.json")


def _slo_receipt() -> dict[str, Any]:
    return _load_json("evidence/m10-recovery-slo-receipt.json")


def _scenario(evidence: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    for scenario in evidence["scenarios"]:
        if scenario["id"] == scenario_id:
            return scenario
    raise AssertionError(f"scenario {scenario_id!r} missing from evidence")


# ---------------------------------------------------------------------------
# Maintenance verifier input builders (construction helpers only — the pure
# verifier API is consumed; no owner store is imported or instantiated).
# ---------------------------------------------------------------------------


def _ts() -> datetime:
    return datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _ref(
    owner: str = "repair_custody",
    record_type: str = "effect",
    locator: str = "effect://occ-1/9",
    digest: str | None = None,
    cursor: str = "journal:9",
    identity: str = "occ-1",
) -> OwnerRef:
    return OwnerRef(
        owner=owner,
        record_type=record_type,
        identity=identity,
        schema_version="1",
        locator=locator,
        digest=digest if digest is not None else "e" * 64,
        cursor=cursor,
    )


def _vector(owner: str, digest: str = "f" * 64) -> SourceVersionVector:
    return SourceVersionVector(
        owner=owner,
        source=owner,
        environment=EnvironmentId("production"),
        before=digest,
        after=digest,
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
    return _ref(
        "repair_custody", "checkpoint", "checkpoint://occ-1/pre",
        digest="d" * 64, cursor="journal:5",
    )


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
) -> Any:
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


def _accepted_row(
    handoff_id: str,
    *,
    source_path: str,
    schema_identity: str,
    digest: str,
) -> HandoffRow:
    return HandoffRow(
        id=handoff_id,
        source_path=source_path,
        schema_identity=schema_identity,
        owner_api_identity=f"owner.api.{handoff_id}",
        schema_version="v1",
        digest=digest,
        approval=ApprovalState.APPROVED,
        requires_wbc_coordinates=False,
        approval_evidence=ApprovalEvidence(
            approver="reviewer-1",
            approved_at=UtcTime(_ts()),
            evidence_ref=f"approval://{handoff_id}/1",
            digest="9" * 64,
        ),
    )


def _registry(accepted: dict[str, HandoffRow] | None = None) -> HandoffRegistry:
    """A full 8-row registry; *accepted* overrides rows that become accepted."""
    overrides = accepted or {}
    rows: list[HandoffRow] = []
    for hid in ("M6A", "M7", "M10", "M11", "C1", "C2", "S1", "S2R"):
        if hid in overrides:
            rows.append(overrides[hid])
        else:
            rows.append(
                HandoffRow(
                    id=hid,
                    source_path=f"pending/{hid}",
                    schema_identity=f"schema-{hid}.v1",
                    owner_api_identity=f"owner.api.{hid}",
                    schema_version="v1",
                    digest=None,
                    approval=ApprovalState.PENDING_HUMAN_APPROVAL,
                    requires_wbc_coordinates=(hid == "M6A"),
                )
            )
    return HandoffRegistry(rows=tuple(rows))


class _Manifest:
    """Minimal owner manifest-shaped record (digest + optional identity)."""

    def __init__(self, digest: str, *, identity: str | None = None) -> None:
        self._digest = digest
        self.identity = identity

    def digest(self) -> str:
        return self._digest


class _Evidence:
    """Minimal owner source-manifest-shaped record."""

    def __init__(self, payload: str) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, str]:
        return {"payload": self.payload}


# ---------------------------------------------------------------------------
# 1. Evidence identities and digests (content-addressed, no payload copies)
# ---------------------------------------------------------------------------


def test_fault_matrix_live_digest_matches_recorded_identity() -> None:
    # The live artifact digest must equal the sha256 recorded in the M10
    # handoff evidence (content-addressed identity, never guessed).
    assert _live_sha256("evidence/m10-f01-f17-fault-matrix.json") == FAULT_MATRIX_SHA256
    assert _fault_matrix()["status"] == "reconciled"
    scenarios = _fault_matrix()["scenarios"]
    assert [scenario["id"] for scenario in scenarios] == [
        f"F{i:02d}" for i in range(1, 18)
    ]


def test_conformance_live_digest_and_bound_file_hashes() -> None:
    assert _live_sha256("evidence/m10-c01-c20-conformance.json") == CONFORMANCE_SHA256
    conformance = _conformance()
    assert conformance["conformance_pass"] is True
    assert conformance["milestone"] == "M10"
    bound = conformance["bound_files"]
    assert bound["custody/action_validator"] == ACTION_VALIDATOR_HASH
    assert bound["recovery/recovery_verifier"] == RECOVERY_VERIFIER_HASH
    assert bound["source/runtime_attestation"] == RUNTIME_ATTESTATION_HASH
    assert bound["recovery/six_hour_auditor"] == SIX_HOUR_AUDITOR_HASH
    # C18: the owner's independent-verifier contract the Maintenance verifier
    # must satisfy (negative control + next-three-hour positive proof cadence).
    c18 = conformance["c18"]
    assert c18["independent_verifier_required"] is True
    assert c18["negative_control_required"] is True
    assert c18["positive_proof_cadence"] == "next_three_hour"
    assert c18["six_hour_backstop_is_compatibility_alias"] is True
    assert c18["next_three_hour_reconciliation_present"] is True


def test_genuine_block_manifest_identity_and_verifier_separation() -> None:
    assert (
        _live_sha256("evidence/m11-genuine-block-candidate/manifest.json")
        == GENUINE_BLOCK_MANIFEST_SHA256
    )
    manifest = _genuine_block_manifest()
    assert manifest["candidate_boundary"]["identity"] == "bc:execute_approval"
    assert manifest["candidate_boundary"]["action_off_in_m10"] is True
    assert manifest["candidate_boundary"]["fault_matrix_coverage"][:2] == ["F01", "F02"]
    assert manifest["candidate_boundary"]["fault_matrix_coverage"][-1] == "F16"
    schedule = manifest["verifier_schedule"]
    assert schedule["independent_verifier_required"] is True
    assert schedule["negative_control_required"] is True
    assert schedule["current_rereads_required"] is True
    assert schedule["verifier_class"] == "RecoveryVerifier"
    assert "must not be the same process that produced the failure" in schedule[
        "verifier_separation"
    ]
    assert manifest["kill_switch"]["fail_closed"] is True
    assert manifest["rollback"]["mechanism"] == "seed_rematerialize._rollback_seed_epoch"
    assert manifest["runtime_provenance"]["content_addressed"] is True
    assert "Acceptance decision" in manifest["left_to_m11"]


def test_long_call_slo_receipt_identity() -> None:
    assert _live_sha256("evidence/m10-recovery-slo-receipt.json") == SLO_RECEIPT_SHA256
    receipt = _slo_receipt()
    assert receipt["p95_seconds"] == 420.0
    assert receipt["slo_target_seconds"] == 300.0
    assert receipt["slo_met"] is False
    assert receipt["next_three_hour_reconciliation"]["requires_attention"] is True
    assert receipt["typed_escalation"]["required"] is True
    assert receipt["slo_exceeded_event_ids"] == ["blocker-slow-1"]
    assert receipt["constraints"]["positive_proof_cadence"] == "next_three_hour"
    assert receipt["constraints"]["six_hour_names_compatibility_only"] is True


# ---------------------------------------------------------------------------
# 2. Fault-corpus parameterization: the nine Maintenance coverages
# ---------------------------------------------------------------------------

#: Scenario ids whose replay_expectation is a typed escalation / fence —
#: the repair target is alive but blocked by authority (M10 F07/F13/F14/F15).
ALIVE_BUT_BLOCKED_SCENARIOS = ("F07", "F13", "F14", "F15")
STALE_FENCING_SCENARIOS = ("F13", "F14")
RETRIGGER_FAILURE_SCENARIOS = ("F03", "F04")
STALE_TERMINAL_SCENARIOS = ("F06", "F16")


def _blocked_verification_inputs(
    scenario: dict[str, Any],
) -> tuple[dict[str, Any], ExpectedAuthority | None]:
    """Derive the failing verifier inputs from the evidence row (no copying).

    The Maintenance case consumes the scenario's OWNED coordinates
    (``custody_precondition`` / ``replay_expectation`` / ``label``) to select
    the typed fail-closed input; the owner's prose assertions are never
    re-asserted.
    """
    precondition = scenario["custody_precondition"]
    if precondition == "lease_expired":
        return {"freshness": FreshnessState.STALE}, None
    if precondition == "stale_epoch":
        return {"run": "run-9"}, ExpectedAuthority(run_id="run-1", attempt_id="att-1")
    if scenario["replay_expectation"] == "fenced" and scenario["injection_edge"] == "dispatch":
        return {"run": "run-9"}, ExpectedAuthority(run_id="run-1", attempt_id="att-1")
    if scenario["label"] == "wbc-evidence-missing-rejection":
        return {"completeness": CompletenessState.PARTIAL}, None
    raise AssertionError(f"unmapped blocked scenario {scenario['id']}")


@pytest.mark.parametrize("scenario_id", ALIVE_BUT_BLOCKED_SCENARIOS)
def test_alive_but_blocked_authority_never_verifies(scenario_id: str) -> None:
    """F07/F13/F14/F15: the process is alive but fenced/blocked by stale
    lease, stale epoch, missing Run Authority grant, or missing WBC evidence —
    Maintenance must never return VERIFIED for such an occurrence."""
    scenario = _scenario(_fault_matrix(), scenario_id)
    assert scenario["provider_behavior"] == "not_called"
    kwargs, expected = _blocked_verification_inputs(scenario)
    result = _evaluate(envelope=_envelope(**kwargs), expected=expected)
    assert result.outcome is not VerificationOutcome.VERIFIED
    assert result.terminal is False
    assert result.outcome in (
        VerificationOutcome.UNKNOWN,
        VerificationOutcome.INCOHERENT,
        VerificationOutcome.FAILED_CONTROL,
    )


@pytest.mark.parametrize("scenario_id", STALE_FENCING_SCENARIOS)
def test_stale_fencing_is_stale_authority(scenario_id: str) -> None:
    """F13/F14: stale custody epoch / Run Authority fence must resolve to the
    typed STALE_AUTHORITY reject reason, never to a fresh grant."""
    scenario = _scenario(_fault_matrix(), scenario_id)
    assert scenario["replay_expectation"] == "fenced"
    result = _evaluate(
        envelope=_envelope(run="run-9"),
        expected=ExpectedAuthority(run_id="run-1", attempt_id="att-1"),
    )
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.STALE_AUTHORITY in result.reasons
    assert result.terminal is False


def test_legitimate_long_call_never_verifies_on_duration_or_liveness() -> None:
    """M10 SLO receipt ``blocker-slow-1``: a genuine long call (p95 420.0s >
    300.0s target) with typed escalation stays open — duration and
    liveness/activity evidence are corroboration only, never closure."""
    receipt = _slo_receipt()
    assert 420.0 in receipt["latencies_seconds"]
    liveness = (
        OwnerRef(owner="snapshot", locator="pid://4321", digest="7" * 64),
        OwnerRef(owner="snapshot", locator="activity://slow-1", digest="8" * 64),
    )
    result = _evaluate(progress_refs=liveness)
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.LIVENESS_ONLY in result.reasons
    assert result.terminal is False
    # The SLO escalation (next_three_hour reconciliation, requires_attention)
    # is reported as data and keeps custody open — never a fabricated close.
    assert receipt["next_three_hour_reconciliation"]["requires_attention"] is True


@pytest.mark.parametrize("scenario_id", STALE_TERMINAL_SCENARIOS)
def test_stale_terminal_state_never_authorizes_terminal_verification(scenario_id: str) -> None:
    """F06/F16: a stale or replayed terminal state (terminal-state-transition
    guard; first-terminal folding) cannot authorize closure — progress must
    advance beyond the pre-repair checkpoint and labels are corroboration
    only."""
    scenario = _scenario(_fault_matrix(), scenario_id)
    assert scenario["replay_expectation"] in ("terminal_state_error", "first_terminal_preserved")
    # A terminal label (label://) without durable progress is liveness-only.
    stale_terminal = (
        OwnerRef(owner="snapshot", locator="label://terminated", digest="7" * 64),
    )
    result = _evaluate(progress_refs=stale_terminal)
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.LIVENESS_ONLY in result.reasons
    # Durable progress that does not advance beyond the pre-repair checkpoint
    # is NO_PROGRESS — a stale terminal state cannot resurrect closure.
    pre_repair = _ref(
        "repair_custody", "checkpoint", "checkpoint://occ-1/pre",
        digest="d" * 64, cursor="journal:9",
    )
    no_advance = (_ref("repair_custody", "effect", "effect://occ-1/5", digest="e" * 64, cursor="journal:5"),)
    result2 = _evaluate(pre_repair_ref=pre_repair, progress_refs=no_advance)
    assert result2.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.NO_PROGRESS in result2.reasons
    assert result2.terminal is False


@pytest.mark.parametrize("scenario_id", RETRIGGER_FAILURE_SCENARIOS)
def test_retrigger_failure_never_fabricates_verification(scenario_id: str) -> None:
    """F03/F04: a retrigger that loses its ACK or cannot query the provider
    must not fabricate closure — the blocker's absence stays unconfirmed
    (FAILED_CONTROL) or progress stays unproven (NO_PROGRESS)."""
    scenario = _scenario(_fault_matrix(), scenario_id)
    if scenario_id == "F04":
        assert scenario["replay_expectation"] == "indeterminate"
        # Query failure means the negative control could not confirm the
        # blocker is absent — typed FAILED_CONTROL, never verified.
        result = _evaluate(controls=_controls(blocker_absent=False))
        assert result.outcome is VerificationOutcome.FAILED_CONTROL
        assert VerificationRejectReason.FAILED_CONTROL in result.reasons
        assert result.terminal is False
    else:
        assert scenario["replay_expectation"] == "fulfilled"
        # Lost ACK must not double-apply: a retry effect at the pre-repair
        # cursor proves no authoritative progress beyond the checkpoint.
        pre_repair = _ref(
            "repair_custody", "checkpoint", "checkpoint://occ-1/pre",
            digest="d" * 64, cursor="journal:9",
        )
        retry = (_ref("repair_custody", "effect", "effect://occ-1/9", digest="e" * 64, cursor="journal:9"),)
        result = _evaluate(pre_repair_ref=pre_repair, progress_refs=retry)
        assert result.outcome is VerificationOutcome.UNKNOWN
        assert VerificationRejectReason.NO_PROGRESS in result.reasons
        assert result.terminal is False


def test_recurrence_requires_fresh_authority_never_reuses_receipts() -> None:
    """F09: same-signature recurrence within the minimum interval is
    suppressed — a recurrence that reuses the prior lease/epoch coordinates or
    the prior closure receipt must fail closed (STALE_AUTHORITY / NO_PROGRESS)
    instead of re-verifying with reused authority."""
    scenario = _scenario(_fault_matrix(), "F09")
    assert scenario["replay_expectation"] == "suppressed"
    # Reusing the prior authority coordinates (same run/attempt) is stale.
    result = _evaluate(
        envelope=_envelope(run="run-1"),
        expected=ExpectedAuthority(run_id="run-9", attempt_id="att-9"),
    )
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.STALE_AUTHORITY in result.reasons
    # Reusing the prior closure receipt (no progress beyond pre-repair) is
    # NO_PROGRESS — a fresh occurrence needs fresh durable progress.
    pre_repair = _ref(
        "repair_custody", "checkpoint", "checkpoint://occ-1/pre",
        digest="d" * 64, cursor="journal:9",
    )
    reused = (_ref("repair_custody", "effect", "effect://occ-1/9", digest="e" * 64, cursor="journal:9"),)
    result2 = _evaluate(pre_repair_ref=pre_repair, progress_refs=reused)
    assert result2.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.NO_PROGRESS in result2.reasons
    assert result2.terminal is False


def test_human_gate_keeps_custody_open() -> None:
    """F17 + M11 manifest: subjective-only criteria are rejected before
    dispatch and the human acceptance decision stays pending — Maintenance
    must keep custody open and never waive the gate."""
    scenario = _scenario(_fault_matrix(), "F17")
    assert scenario["injection_edge"] == "gate"
    assert scenario["replay_expectation"] == "rejected"
    manifest = _genuine_block_manifest()
    assert "Acceptance decision" in manifest["left_to_m11"]
    # While the human gate is pending no accepted negative control can be
    # translated — missing controls are typed UNKNOWN, never verified.
    result = _evaluate(controls=())
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.MISSING_NEGATIVE_CONTROL in result.reasons
    assert result.terminal is False


def test_producer_self_verification_is_rejected() -> None:
    """M11 verifier separation: the verifier that closes recovery must not be
    the same process that produced the failure — repair-producer-authored and
    same-principal verification is typed INCOHERENT."""
    manifest = _genuine_block_manifest()
    assert "must not be the same process that produced the failure" in manifest[
        "verifier_schedule"
    ]["verifier_separation"]
    result = _evaluate(
        provenance=_provenance(principal="producer-1"),
        producer=_producer(principal="producer-1"),
    )
    assert result.outcome is VerificationOutcome.INCOHERENT
    assert VerificationRejectReason.REPAIR_PRODUCER_AUTHORED in result.reasons
    assert VerificationRejectReason.SELF_VERIFICATION in result.reasons
    assert result.terminal is False


# ---------------------------------------------------------------------------
# 3. Wrong installation hash / accepted S2R references (handoff registry)
# ---------------------------------------------------------------------------


def test_wrong_installation_hash_fails_closed() -> None:
    """The installed runtime must match the accepted content digest — a wrong
    installation hash (manifest digest != accepted S2R digest) resolves typed
    DIGEST_MISMATCH, emits no references, and cannot support verification."""
    conformance = _conformance()
    assert conformance["bound_files"]["source/runtime_attestation"] == RUNTIME_ATTESTATION_HASH
    manifest = _genuine_block_manifest()
    assert manifest["runtime_provenance"]["content_addressed"] is True
    registry = _registry({"S2R": _accepted_row("S2R", source_path="native/runtime/s2r", schema_identity="native.runtime.s2r.v1", digest=S2R_ACCEPTED_DIGEST)})
    wrong = NativeManifestAdapter(
        manifest_provider=lambda hid, subject: _Manifest("b" * 64),
        registry=registry,
        environment="production",
    ).read("S2R", "chain:session")
    assert wrong.handoff is not None
    assert wrong.handoff.reason is HandoffResolutionReason.DIGEST_MISMATCH
    assert wrong.manifest_ref is None
    # Without accepted runtime/source references the verifier has no direct
    # owner-source reads for the installed runtime → MISSING_PROVENANCE.
    result = _evaluate(provenance=_provenance(direct_read_refs=()))
    assert result.outcome is VerificationOutcome.UNKNOWN
    assert VerificationRejectReason.MISSING_PROVENANCE in result.reasons
    assert result.terminal is False


def test_s2r_handoff_unavailable_is_never_accepted() -> None:
    """SC9: the default registry's S2R row is pending — unavailable S2R
    evidence must stay typed UNKNOWN and must never be treated as accepted."""
    registry = default_handoff_registry()
    resolution = registry.resolve("S2R")
    assert resolution.state is HandoffResolutionState.UNKNOWN
    assert resolution.approval is ApprovalState.PENDING_HUMAN_APPROVAL
    assert resolution.reason is HandoffResolutionReason.PENDING_HUMAN_APPROVAL
    view = build_handoff_view(registry=registry)
    assert view.enforcement_blocked is True
    assert "S2R" in view.pending_handoff_ids
    adapter = NativeManifestAdapter(
        manifest_provider=lambda hid, subject: _Manifest(S2R_ACCEPTED_DIGEST),
        registry=registry,
        environment="production",
    )
    read = adapter.read("S2R", "chain:session")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.UNKNOWN
    assert read.manifest_ref is None


def test_s2r_accepted_references_are_content_addressed() -> None:
    """With an accepted S2R row the read emits the exact content digest —
    the reference is asserted by identity, never by copying the manifest."""
    registry = _registry({"S2R": _accepted_row("S2R", source_path="native/runtime/s2r", schema_identity="native.runtime.s2r.v1", digest=S2R_ACCEPTED_DIGEST)})
    read = NativeManifestAdapter(
        manifest_provider=lambda hid, subject: _Manifest(S2R_ACCEPTED_DIGEST, identity="chain:session"),
        registry=registry,
        environment="production",
    ).read("S2R", "chain:session")
    assert read.handoff is not None
    assert read.handoff.state is HandoffResolutionState.ACCEPTED
    assert read.manifest_ref is not None
    assert read.manifest_ref.digest == S2R_ACCEPTED_DIGEST
    assert read.manifest_ref.locator == f"{RUNTIME_SOURCE_PATHS['S2R']}//chain:session"
    assert read.version_vector.before == read.version_vector.after == S2R_ACCEPTED_DIGEST
    assert read.torn is False
    # Runtime adapter: runtime/source refs carry the same accepted digest.
    runtime = RuntimeAdapter(
        runtime_provider=lambda hid, subject: _Manifest(S2R_ACCEPTED_DIGEST),
        source_provider=lambda hid, subject: _Evidence("source-manifest"),
        registry=registry,
        environment="production",
    ).read("S2R", "chain:session")
    assert runtime.handoff is not None
    assert runtime.handoff.state is HandoffResolutionState.ACCEPTED
    assert runtime.runtime_ref is not None
    assert runtime.runtime_ref.digest == S2R_ACCEPTED_DIGEST
    assert runtime.source_ref is not None


# ---------------------------------------------------------------------------
# 4. No-payload-copying guard
# ---------------------------------------------------------------------------


def test_evidence_payloads_are_consumed_by_identity_not_copied() -> None:
    """The owner suite's prose payloads (expected assertions and notes) are
    never duplicated verbatim into this Maintenance conformance module —
    scenarios are consumed by id/label/digest only."""
    source = Path(__file__).read_text(encoding="utf-8")
    for scenario in _fault_matrix()["scenarios"]:
        assert scenario["expected_assertion"] not in source, (
            f"copied expected_assertion payload of {scenario['id']}"
        )
        assert scenario["note"] not in source, (
            f"copied note payload of {scenario['id']}"
        )
    conformance = _conformance()
    for group in ("c01_c03", "c04", "c05", "c06_c09", "c10_c14", "c15_c17", "c18", "c19", "c20"):
        entry = conformance.get(group)
        if isinstance(entry, dict):
            criteria = entry.get("criteria")
            if isinstance(criteria, list):
                for criterion in criteria:
                    assert criterion["criterion_text"] not in source, (
                        f"copied criterion payload of {group}"
                    )
