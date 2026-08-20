"""Occurrence-bound repair-request and effect bridge (M3 Plan Steps 9-12 / T10-T13).

This cloud-side adapter translates an eligible Maintenance operational
decision into exactly one canonical M7 repair request through the owner
seam ``enqueue_occurrence_bound_repair_request``, routes each
allowlisted repair effect (claim, source change, installation, retrigger)
exactly once through the unified fixer seam
``delegate_to_simple_fixer``, admits verified recurrences as FRESH
canonical occurrences (new lease/epoch/keys/budget linked to the
predecessor closure and root-cause cluster, never reusing prior
receipts), and records true human gates / ambiguous blockers with
immutable escalation-owner references while custody stays open.  It is
the ONLY place that calls the canonical owner seams (SD1): the
Maintenance domain modules stay reference-only, and this module never
reimplements a lease store, effect ledger, repair queue, verifier suite,
or lifecycle writer.

Locked decisions (do not re-litigate):

* **Exactly one canonical request.**  The eligible decision is translated
  into the canonical M7 ``occurrence_identity`` envelope (the
  ``RepairOccurrenceKey`` plus run incarnation, grant, lease, and custody
  epoch).  The owner seam is idempotent: a fresh enqueue returns
  ``accepted``, an existing identical request returns ``coalesced``, and
  the adapter joins it.  The adapter never creates another queue or claim
  store.
* **Immutable reference appended once.**  The seam result is reduced to
  one immutable ``OwnerRef`` (``repair_custody``/``request``) and appended
  to the Maintenance ledger as exactly one ``repair_request`` operational
  event.  Exact retries deduplicate at the journal boundary; a divergent
  reuse is rejected without appending.
* **Re-read before authority increase.**  Before any enqueue (an
  authority-increasing side effect) the adapter requires a fresh coherent
  direct owner-source capture and refuses pending handoffs, stale epochs
  or fences, missing WBC attempts, and non-dispatchable observations.
* **Fail-closed outcome vocabulary.**  ``accepted`` / ``joined`` /
  ``rejected``; every rejection carries at least one typed reason and
  never enqueues and never appends.

The module consumes only injected owner read providers and the injected
canonical enqueue seam (defaulting to the real owner API); it constructs
no owner authority records.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.cloud.feature_flags import (
    MUTATION_PATH_L1,
    mutation_authorized,
)
from arnold_pipelines.megaplan.cloud.repair_effect_allowlist import (
    AllowlistCheckResult,
    AllowlistVerdict,
    RepairEffectClass,
    check_effect_class,
)
from arnold_pipelines.megaplan.cloud.repair_effect_ledger import (
    MutationReservation,
    RepairEffectLedger,
)
from arnold_pipelines.megaplan.cloud.repair_requests import (
    enqueue_occurrence_bound_repair_request,
)
from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import (
    RepairDelegationResult,
    build_repair_delegation,
    delegate_to_simple_fixer,
)
from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryResult,
    validate_action_boundary_simple,
)
from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
)
from arnold_pipelines.megaplan.maintenance.events import (
    HumanEscalationPayload,
    InstallationPayload,
    OccurrenceBudget,
    OperationalActionKind,
    OperationalEvent,
    OperationalPayload,
    RecurrencePayload,
    RepairRequestPayload,
    RetriggerPayload,
    SourceChangePayload,
)
from arnold_pipelines.megaplan.maintenance.handoffs import (
    HandoffResolution,
    HandoffResolutionState,
    default_handoff_registry,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    EnvironmentId,
    Extensions,
    OwnerRef,
    UtcTime,
    canonical_digest,
    canonical_json,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.ledger import MaintenanceLedger
from arnold_pipelines.megaplan.maintenance.observation import (
    JoinSource,
    capture_observation,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ActionTarget,
    EscalationReference,
    LeaseCoordinates,
    OccurrenceCoordinates,
    OwnerReceipts,
    PolicyVersionCoordinates,
    ProducerPrincipal,
    ProducerRole,
    RecurrenceReference,
    RunAuthorityCoordinates,
    WbcAttemptCoordinates,
)

#: Handoffs that gate dispatchability of the occurrence-bound request.
#: M7 is the canonical occurrence/lease owner; M6A is the WBC attempt
#: ledger.  A pending or missing handoff is never dispatchable.
REQUEST_HANDOFF_IDS: tuple[str, ...] = ("M7", "M6A")

#: Outcome of one occurrence-bound request submission.
class RequestOutcome(str, Enum):
    """Closed typed outcomes of the request bridge.

    * ``ACCEPTED`` — the canonical seam enqueued a fresh request and the
      Maintenance ledger appended its immutable reference;
    * ``JOINED`` — the seam coalesced onto an existing identical request
      and the reference was appended once;
    * ``REJECTED`` — fail-closed: nothing was enqueued and nothing was
      appended.
    """

    ACCEPTED = "accepted"
    JOINED = "joined"
    REJECTED = "rejected"


class RequestRejectReason(str, Enum):
    """Closed typed reasons for a rejected submission (never guessed)."""

    PENDING_HANDOFF = "pending_handoff"
    TORN_ENVELOPE = "torn_envelope"
    CROSS_ENVIRONMENT = "cross_environment"
    STALE_AUTHORITY = "stale_authority"  # stale epoch / fence / run / attempt
    MISSING_WBC = "missing_wbc"
    MISSING_LEASE = "missing_lease"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    NON_DISPATCHABLE = "non_dispatchable"
    MISSING_OCCURRENCE_IDENTITY = "missing_occurrence_identity"
    IDENTITY_MISMATCH = "identity_mismatch"
    ENQUEUE_REJECTED = "enqueue_rejected"
    DIVERGENT_REUSE = "divergent_reuse"


class ExpectedRequestAuthority(BaseModel):
    """The current authority coordinates the fresh capture must match.

    Every coordinate is optional; a present coordinate is compared exactly
    and a mismatch is typed ``STALE_AUTHORITY`` (stale epoch via
    ``lease_digest``, stale fence via ``fencing_token``, stale run/attempt
    via ``run_id``/``attempt_id``).  Absent coordinates are never inferred.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    occurrence_id: StrictStr | None = None
    lease_id: StrictStr | None = None
    lease_digest: StrictStr | None = None
    fencing_token: StrictStr | None = None
    run_id: StrictStr | None = None
    attempt_id: StrictStr | None = None

    @model_validator(mode="after")
    def _validate_nonempty(self) -> ExpectedRequestAuthority:
        for name in (
            "occurrence_id",
            "lease_id",
            "lease_digest",
            "fencing_token",
            "run_id",
            "attempt_id",
        ):
            value = getattr(self, name)
            if value is not None and not value:
                raise ValueError(
                    f"expected authority coordinate {name!r} must be a "
                    "non-empty string when present"
                )
        return self


class RequestSubmissionResult(BaseModel):
    """The typed fail-closed outcome of one request submission.

    ``outcome`` is ``accepted`` or ``joined`` ONLY when the canonical
    request reference was appended to the Maintenance ledger; every
    rejected outcome carries at least one typed
    :class:`RequestRejectReason` and never enqueues and never appends.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    outcome: RequestOutcome
    reasons: tuple[RequestRejectReason, ...] = ()
    request_id: StrictStr | None = None
    request_ref: OwnerRef | None = None
    request_digest: StrictStr | None = None
    enqueue_status: StrictStr | None = None
    event_id: StrictStr | None = None
    event_digest: StrictStr | None = None
    event_replayed: bool = False
    envelope_digest: StrictStr | None = None
    pending_handoffs: tuple[StrictStr, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> RequestSubmissionResult:
        if self.outcome is RequestOutcome.REJECTED and not self.reasons:
            raise ValueError(
                "a rejected submission requires at least one typed reject reason"
            )
        if self.outcome is not RequestOutcome.REJECTED and self.reasons:
            raise ValueError(
                "an accepted/joined submission must not carry reject reasons; "
                f"got {[reason.value for reason in self.reasons]}"
            )
        if self.outcome is not RequestOutcome.REJECTED and self.request_ref is None:
            raise ValueError(
                "an accepted/joined submission requires the immutable "
                "request reference"
            )
        return self


def _envelope_wbc_present(envelope: ObservationEnvelope) -> bool:
    """Whether the coherent capture carries a WBC attempt reference."""
    return any(ref.owner == "wbc" for ref in envelope.references)


def _lease_digest_matches(
    envelope: ObservationEnvelope,
    expected: ExpectedRequestAuthority | None,
) -> tuple[bool, bool | None]:
    """Return ``(lease_present, lease_digest_matches)`` from the capture.

    The M7 custody lease is not an SD1-tier reference kind, so the
    envelope carries it only in its version vectors (before/after = the
    current lease record digests).  ``lease_present`` is whether the
    custody source was captured at all; ``lease_digest_matches`` is
    ``True``/``False`` when *expected* pins the current lease digest and
    ``None`` when it does not (no expectation is never a match claim).
    """
    custody_vectors = [v for v in envelope.version_vectors if v.owner == "custody"]
    if not custody_vectors:
        return False, None
    if expected is None or expected.lease_digest is None:
        return True, None
    return True, any(v.after == expected.lease_digest for v in custody_vectors)


def _capture_coherent_envelope(
    *,
    sources: Sequence[JoinSource],
    observed_at: UtcTime | datetime,
    environment: EnvironmentId | str | None,
    run: str | None,
    attempt: str | None,
    occurrence_id: str,
    target_id: str,
    lease_id: str,
    fence: str | None,
    expected: ExpectedRequestAuthority | None,
) -> tuple[ObservationEnvelope, tuple[RequestRejectReason, ...]]:
    """Take one fresh coherent owner-source capture and evaluate eligibility.

    The decision's occurrence / target / lease / fence identity dimensions
    are declared on the capture so a cross-occurrence, cross-lease, or
    cross-fence read types INCOHERENT (never dispatched).  Returns the
    envelope plus the deterministic fail-closed rejection reasons (empty
    when the capture is dispatchable).
    """
    envelope = capture_observation(
        sources,
        observed_at=observed_at,
        environment=environment,
        run=run,
        attempt=attempt,
        occurrence_id=occurrence_id,
        target=target_id,
        lease_id=lease_id,
        fence=fence,
    )
    wbc_present = _envelope_wbc_present(envelope)
    lease_present, lease_digest_matches = _lease_digest_matches(envelope, expected)
    reasons = evaluate_request_eligibility(
        envelope=envelope,
        expected=expected,
        wbc_present=wbc_present,
        lease_present=lease_present,
        lease_digest_matches=lease_digest_matches,
    )
    return envelope, reasons


def evaluate_request_eligibility(
    *,
    envelope: ObservationEnvelope,
    expected: ExpectedRequestAuthority | None = None,
    wbc_present: bool,
    lease_present: bool,
    lease_digest_matches: bool | None,
) -> tuple[RequestRejectReason, ...]:
    """Pure fail-closed eligibility of the coherent capture for dispatch.

    Maps the typed capture states onto the closed rejection vocabulary:

    * a torn envelope (``VERSION_TEAR``) is ``TORN_ENVELOPE``;
    * cross-environment evidence is ``CROSS_ENVIRONMENT``;
    * contradictory evidence (stale epoch/fence or cross-occurrence reads)
      is ``STALE_AUTHORITY``;
    * unknown coherence/completeness/freshness is ``UNKNOWN_EVIDENCE``;
    * stale freshness or a pinned lease digest / run / attempt mismatch is
      ``STALE_AUTHORITY``;
    * a missing WBC attempt reference is ``MISSING_WBC``;
    * a missing custody lease capture is ``MISSING_LEASE``.

    Everything else that cannot dispatch is ``NON_DISPATCHABLE``.  Reasons
    are deterministic and de-duplicated.
    """
    reasons: list[RequestRejectReason] = []

    if not envelope.is_eligible or not envelope.dispatchable:
        if envelope.coherence is CoherenceState.INCOHERENT:
            if CoherenceReason.VERSION_TEAR in envelope.coherence_reasons:
                reasons.append(RequestRejectReason.TORN_ENVELOPE)
            elif CoherenceReason.CROSS_ENVIRONMENT in envelope.coherence_reasons:
                reasons.append(RequestRejectReason.CROSS_ENVIRONMENT)
            elif CoherenceReason.CONTRADICTORY_EVIDENCE in envelope.coherence_reasons:
                reasons.append(RequestRejectReason.STALE_AUTHORITY)
            elif CoherenceReason.STALE_SOURCE in envelope.coherence_reasons:
                reasons.append(RequestRejectReason.STALE_AUTHORITY)
            elif any(
                reason in envelope.coherence_reasons
                for reason in (
                    CoherenceReason.MISSING_REQUIRED_SOURCE,
                    CoherenceReason.MISSING_OPTIONAL_SOURCE,
                    CoherenceReason.UNKNOWN,
                )
            ):
                reasons.append(RequestRejectReason.UNKNOWN_EVIDENCE)
            else:
                reasons.append(RequestRejectReason.NON_DISPATCHABLE)
        elif envelope.coherence is CoherenceState.UNKNOWN:
            reasons.append(RequestRejectReason.UNKNOWN_EVIDENCE)
        else:
            if envelope.freshness is FreshnessState.STALE:
                reasons.append(RequestRejectReason.STALE_AUTHORITY)
            elif envelope.freshness is FreshnessState.UNKNOWN:
                reasons.append(RequestRejectReason.UNKNOWN_EVIDENCE)
            if envelope.completeness is not CompletenessState.COMPLETE:
                reasons.append(RequestRejectReason.UNKNOWN_EVIDENCE)
            if not reasons:
                reasons.append(RequestRejectReason.NON_DISPATCHABLE)

    if not wbc_present:
        reasons.append(RequestRejectReason.MISSING_WBC)
    if not lease_present:
        reasons.append(RequestRejectReason.MISSING_LEASE)
    if lease_digest_matches is False:
        reasons.append(RequestRejectReason.STALE_AUTHORITY)

    if expected is not None:
        if (
            expected.run_id is not None
            and envelope.run is not None
            and envelope.run.root != expected.run_id
        ):
            reasons.append(RequestRejectReason.STALE_AUTHORITY)
        if (
            expected.attempt_id is not None
            and envelope.attempt is not None
            and envelope.attempt.root != expected.attempt_id
        ):
            reasons.append(RequestRejectReason.STALE_AUTHORITY)

    return tuple(dict.fromkeys(reasons))


def _identity_occurrence_digest(identity: Mapping[str, Any]) -> str | None:
    """The RepairOccurrenceKey digest recorded in the identity envelope."""
    occurrence = identity.get("occurrence")
    if not isinstance(occurrence, Mapping):
        return None
    digest = occurrence.get("occurrence_digest") or occurrence.get("digest")
    return str(digest) if digest else None


def translate_occurrence_identity(
    *,
    identity: Mapping[str, Any],
    occurrence: OccurrenceCoordinates,
    lease: LeaseCoordinates,
    run_authority: RunAuthorityCoordinates,
) -> tuple[dict[str, Any] | None, tuple[RequestRejectReason, ...]]:
    """Reconcile the canonical M7 identity envelope with the decision.

    The caller supplies the complete canonical M7 ``occurrence_identity``
    envelope (the ``RepairOccurrenceKey`` plus run incarnation, grant,
    lease, and custody epoch — coordinates the reference-only Maintenance
    domain deliberately does not carry).  This adapter translates the
    Maintenance-bound coordinates onto that envelope by requiring every
    comparable coordinate to agree exactly:

    * ``lease_id`` must equal the decision's lease id;
    * ``custody_epoch`` must equal the decision's lease epoch;
    * the ``occurrence`` digest must equal the decision's canonical
      occurrence digest;
    * the ``occurrence.run_id`` must equal the decision's Run Authority
      run id.

    Any mismatch returns ``(None, (IDENTITY_MISMATCH,))`` — the adapter
    never guesses a coordinate and never enqueues under a contradictory
    identity.  A missing/empty envelope returns
    ``MISSING_OCCURRENCE_IDENTITY``.
    """
    if not isinstance(identity, Mapping) or not identity:
        return None, (RequestRejectReason.MISSING_OCCURRENCE_IDENTITY,)

    reasons: list[RequestRejectReason] = []

    identity_lease = str(identity.get("lease_id") or "").strip()
    if identity_lease and identity_lease != lease.lease_id:
        reasons.append(RequestRejectReason.IDENTITY_MISMATCH)

    epoch = identity.get("custody_epoch")
    if epoch is not None:
        try:
            epoch_mismatch = int(epoch) != lease.custody_epoch
        except (TypeError, ValueError):
            epoch_mismatch = True
        if epoch_mismatch:
            reasons.append(RequestRejectReason.IDENTITY_MISMATCH)

    occurrence_raw = identity.get("occurrence")
    if isinstance(occurrence_raw, Mapping):
        occurrence_digest = _identity_occurrence_digest(identity)
        if occurrence_digest and occurrence_digest not in (
            occurrence.occurrence_id,
            occurrence.canonical_digest,
        ):
            reasons.append(RequestRejectReason.IDENTITY_MISMATCH)
        run_id = occurrence_raw.get("run_id")
        if run_id and str(run_id) != run_authority.run_id:
            reasons.append(RequestRejectReason.IDENTITY_MISMATCH)

    if reasons:
        return None, tuple(dict.fromkeys(reasons))
    return dict(identity), ()


def _utc_iso(value: UtcTime | datetime) -> str:
    """Canonical UTC ISO-8601 instant for the seam's ``created_at``."""
    from datetime import timezone

    instant = value.root if isinstance(value, UtcTime) else value
    if instant.tzinfo is None:
        raise ValueError("observed_at must carry an explicit UTC offset")
    return instant.astimezone(timezone.utc).isoformat()


def _request_digest(record: Mapping[str, Any]) -> str:
    """Deterministic content digest of the canonical request record."""
    return hashlib.sha256(
        canonical_json(dict(record)).encode("utf-8")
    ).hexdigest()


def _request_ref(record: Mapping[str, Any]) -> tuple[str, OwnerRef] | None:
    """One immutable reference to the canonical request record.

    Returns ``(request_id, OwnerRef)``; ``None`` when the seam returned no
    request record (fail-closed, never guessed).
    """
    request_id = str(record.get("request_id") or "").strip()
    if not request_id:
        return None
    ref = OwnerRef(
        owner="repair_custody",
        record_type="request",
        identity=request_id,
        schema_version=str(MAINTENANCE_SCHEMA_VERSION),
        locator=f"repair_request://{request_id}",
        digest=_request_digest(record),
    )
    return request_id, ref


def _prior_event_record(ledger: MaintenanceLedger, event_id: str) -> dict[str, Any] | None:
    """Return the first committed Maintenance record carrying *event_id*."""
    path = ledger.events_path
    if not path.exists():
        return None
    import json

    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload") or {}
            if payload.get("event_id") == event_id:
                return record
    return None


def submit_occurrence_bound_repair_request(
    *,
    occurrence: OccurrenceCoordinates,
    lease: LeaseCoordinates,
    run_authority: RunAuthorityCoordinates,
    policy: PolicyVersionCoordinates,
    target: ActionTarget,
    producer: ProducerPrincipal,
    observed_at: UtcTime | datetime,
    occurrence_identity: Mapping[str, Any],
    sources: Sequence[JoinSource],
    environment: EnvironmentId | str | None = None,
    run: str | None = None,
    attempt: str | None = None,
    expected: ExpectedRequestAuthority | None = None,
    handoff_resolver: Callable[[str], HandoffResolution] | None = None,
    enqueue_fn: Callable[..., Mapping[str, Any]] = enqueue_occurrence_bound_repair_request,
    ledger: MaintenanceLedger | None = None,
    wbc_attempt: WbcAttemptCoordinates | None = None,
    queue_root: str | Path,
    session: str,
    problem_signature: Mapping[str, Any],
    source: str,
    root_cause_hint: Any = "",
    marker_dir: str | Path | None = None,
    target_mapping: Mapping[str, Any] | None = None,
    workspace: str | Path | None = None,
    run_kind: str = "",
    evidence_cursor_digest: str = "",
    terminal_receipt_expectations: list[str] | None = None,
) -> RequestSubmissionResult:
    """Submit or join exactly one canonical occurrence-bound repair request.

    Order (fail-closed at every step; nothing enqueues and nothing
    appends before the previous step is satisfied):

    1. **Handoff gate.**  Every :data:`REQUEST_HANDOFF_IDS` handoff must
       resolve ACCEPTED; a pending/missing handoff rejects with
       ``PENDING_HANDOFF`` (the pending ids are preserved on the result).
    2. **Coherent re-read.**  A fresh owner-source capture is taken over
       *sources* with the decision's occurrence / target / lease / fence
       identity dimensions declared, so torn, cross-environment,
       cross-occurrence, stale-epoch, and stale-fence reads fail closed.
    3. **Eligibility.**  The capture must be dispatchable with a WBC
       attempt reference and a current lease capture matching the pinned
       lease digest; otherwise the submission is rejected before any
       authority increase.
    4. **Identity translation.**  The canonical M7 identity envelope is
       reconciled with the Maintenance-bound coordinates.
    5. **Enqueue-or-join.**  The owner seam is called exactly once with
       the translated identity; ``accepted`` becomes ``ACCEPTED`` and
       ``coalesced`` becomes ``JOINED``.  Every other seam status
       (``stale``, ``superseded``, ``zero_authority_rejected``, ...) is
       ``REJECTED``/``ENQUEUE_REJECTED`` with the seam status preserved.
    6. **Append once.**  One ``repair_request`` operational event carrying
       the immutable request reference is appended to the Maintenance
       ledger; exact retries deduplicate (``event_replayed=True``) and a
       divergent reuse is rejected without appending.
    """
    resolver = handoff_resolver or default_handoff_registry().resolve

    # 1. Handoff gate (pending handoffs are never dispatchable).
    pending: list[str] = []
    for handoff_id in REQUEST_HANDOFF_IDS:
        resolution = resolver(handoff_id)
        if resolution.state is not HandoffResolutionState.ACCEPTED:
            pending.append(handoff_id)
    if pending:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=(RequestRejectReason.PENDING_HANDOFF,),
            pending_handoffs=tuple(pending),
        )

    # 2. Coherent direct owner-source re-read before any authority
    #    increase.  The decision's occurrence/target/lease/fence identity
    #    dimensions are declared so a cross-occurrence, cross-lease, or
    #    cross-fence read types INCOHERENT (never dispatched).
    # 3. Eligibility (fail-closed before the enqueue seam is touched).
    envelope, reasons = _capture_coherent_envelope(
        sources=sources,
        observed_at=observed_at,
        environment=environment,
        run=run,
        attempt=attempt,
        occurrence_id=occurrence.occurrence_id,
        target_id=target.target,
        lease_id=lease.lease_id,
        fence=(expected.fencing_token if expected is not None else None),
        expected=expected,
    )
    if reasons:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=reasons,
            envelope_digest=canonical_digest(envelope),
        )

    # 4. Translate the canonical M7 identity onto the decision coordinates.
    translated, identity_reasons = translate_occurrence_identity(
        identity=occurrence_identity,
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
    )
    if translated is None:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=identity_reasons,
            envelope_digest=canonical_digest(envelope),
        )

    # 5. Enqueue-or-join through the canonical owner seam.
    seam_result = enqueue_fn(
        queue_root=queue_root,
        session=session,
        problem_signature=problem_signature,
        root_cause_hint=root_cause_hint,
        source=source,
        marker_dir=marker_dir,
        target=target_mapping,
        workspace=workspace,
        run_kind=run_kind,
        created_at=_utc_iso(observed_at),
        occurrence_identity=translated,
        evidence_cursor_digest=evidence_cursor_digest,
        terminal_receipt_expectations=terminal_receipt_expectations,
    )
    if not isinstance(seam_result, Mapping):
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=(RequestRejectReason.ENQUEUE_REJECTED,),
            envelope_digest=canonical_digest(envelope),
        )
    enqueue_status = str(seam_result.get("status") or "").strip()
    record = seam_result.get("request")
    if not isinstance(record, Mapping):
        record = None

    if enqueue_status in {"queued", "accepted"}:
        outcome = RequestOutcome.ACCEPTED
    elif enqueue_status == "coalesced":
        outcome = RequestOutcome.JOINED
    else:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=(RequestRejectReason.ENQUEUE_REJECTED,),
            enqueue_status=enqueue_status or None,
            envelope_digest=canonical_digest(envelope),
        )
    if record is None:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=(RequestRejectReason.ENQUEUE_REJECTED,),
            enqueue_status=enqueue_status,
            envelope_digest=canonical_digest(envelope),
        )
    request_ref_tuple = _request_ref(record)
    if request_ref_tuple is None:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=(RequestRejectReason.ENQUEUE_REJECTED,),
            enqueue_status=enqueue_status,
            envelope_digest=canonical_digest(envelope),
        )
    request_id, request_ref = request_ref_tuple
    request_digest = request_ref.digest

    # 6. Append the immutable reference once (lifecycle-idempotent).
    event = OperationalEvent.build(
        event_id=f"repair_request:{occurrence.occurrence_id}:{request_id}",
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=producer,
        payload=RepairRequestPayload(request_id=request_id, request_ref=request_ref),
        observed_at=observed_at,
        wbc_attempt=wbc_attempt,
    )

    if ledger is None:
        raise ValueError(
            "submit_occurrence_bound_repair_request requires a MaintenanceLedger "
            "to append the immutable request reference"
        )
    prior = _prior_event_record(ledger, event.event_id)
    from arnold_pipelines.megaplan.maintenance.ledger import (
        MaintenanceEventConflict,
    )

    try:
        ledger.append(event)
    except MaintenanceEventConflict:
        return RequestSubmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RequestOutcome.REJECTED,
            reasons=(RequestRejectReason.DIVERGENT_REUSE,),
            enqueue_status=enqueue_status,
            envelope_digest=canonical_digest(envelope),
        )

    return RequestSubmissionResult(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        outcome=outcome,
        request_id=request_id,
        request_ref=request_ref,
        request_digest=request_digest,
        enqueue_status=enqueue_status,
        event_id=event.event_id,
        event_digest=canonical_digest(event),
        event_replayed=prior is not None,
        envelope_digest=canonical_digest(envelope),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Plan Step 10 / T11 — allowlisted effect routing through the unified fixer
# ═══════════════════════════════════════════════════════════════════════════


class EffectKind(str, Enum):
    """Closed repair-effect kinds routed by the adapter (claim edges)."""

    SOURCE_CHANGE = "source_change"
    INSTALLATION = "installation"
    RETRIGGER = "retrigger"


class EffectOutcome(str, Enum):
    """Closed typed outcomes of one effect-routing attempt.

    * ``DELEGATED`` — a fresh canonical outcome was delegated through
      ``delegate_to_simple_fixer`` and its receipt reference appended;
    * ``ADOPTED`` — a prior canonical outcome (reservation or terminal
      state) was adopted from the canonical effect ledger and its
      reference appended once; the effect is NEVER redriven;
    * ``REJECTED`` — fail-closed: no delegation, no effect, no append.
    """

    DELEGATED = "delegated"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class EffectRejectReason(str, Enum):
    """Closed typed reasons for a rejected effect route (never guessed)."""

    MUTATION_DISABLED = "mutation_disabled"
    EFFECT_NOT_ALLOWLISTED = "effect_not_allowlisted"
    ACTION_BOUNDARY_BLOCKED = "action_boundary_blocked"
    BOUNDARY_INPUTS_MISSING = "boundary_inputs_missing"
    PENDING_HANDOFF = "pending_handoff"
    TORN_ENVELOPE = "torn_envelope"
    CROSS_ENVIRONMENT = "cross_environment"
    STALE_AUTHORITY = "stale_authority"
    MISSING_WBC = "missing_wbc"
    MISSING_LEASE = "missing_lease"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    NON_DISPATCHABLE = "non_dispatchable"
    IDENTITY_MISMATCH = "identity_mismatch"
    MISSING_OCCURRENCE_IDENTITY = "missing_occurrence_identity"
    RECEIPT_UNAVAILABLE = "receipt_unavailable"
    DELEGATION_REJECTED = "delegation_rejected"
    MISSING_EFFECT_RECEIPT = "missing_effect_receipt"
    INVALID_SOURCE_DIGEST = "invalid_source_digest"
    INVALID_INSTALL_DIGEST = "invalid_install_digest"
    INVALID_RETRIGGER_REASON = "invalid_retrigger_reason"
    DIVERGENT_REUSE = "divergent_reuse"


class EffectRoutingResult(BaseModel):
    """Typed fail-closed outcome of one allowlisted effect route.

    ``outcome`` is ``delegated`` or ``adopted`` ONLY when the immutable
    effect-receipt reference was appended to the Maintenance ledger; every
    rejected outcome carries at least one typed
    :class:`EffectRejectReason` and never delegates, never runs an effect,
    and never appends.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    effect_kind: EffectKind
    outcome: EffectOutcome
    reasons: tuple[EffectRejectReason, ...] = ()
    adopted_state: str | None = None
    reservation_id: str | None = None
    effect_ref: OwnerRef | None = None
    delegation_outcome: str | None = None
    simple_fixer_outcome: str | None = None
    gate_result: str | None = None
    allowlist_verdict: str | None = None
    event_id: str | None = None
    event_digest: str | None = None
    event_replayed: bool = False
    envelope_digest: str | None = None

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> EffectRoutingResult:
        if self.outcome is EffectOutcome.REJECTED and not self.reasons:
            raise ValueError(
                "a rejected effect route requires at least one typed reject reason"
            )
        if self.outcome is not EffectOutcome.REJECTED and self.reasons:
            raise ValueError(
                "a delegated/adopted effect route must not carry reject reasons; "
                f"got {[reason.value for reason in self.reasons]}"
            )
        if self.outcome is not EffectOutcome.REJECTED and self.effect_ref is None:
            raise ValueError(
                "a delegated/adopted effect route requires the immutable "
                "effect-receipt reference"
            )
        return self


def boundary_inputs_from_identity(
    identity: Mapping[str, Any],
) -> tuple[str | None, int | None, str]:
    """Extract the fresh M7 boundary inputs from the canonical identity.

    Returns ``(run_authority_grant_id, coordinator_fence_token,
    wbc_attempt_reference)``.  The grant id and fence token are required
    for a fresh ``validate_action_boundary`` result; ``None`` is never
    inferred or guessed.  The WBC attempt reference falls back to the
    coordinator attempt id and may be empty (the validator reports it as
    evidence only).
    """
    grant_id = str(identity.get("run_authority_grant_id") or "").strip() or None
    occurrence = identity.get("occurrence")
    fence_token: int | None = None
    wbc_attempt_reference = ""
    if isinstance(occurrence, Mapping):
        fence_raw = occurrence.get("fence_token")
        try:
            fence_token = int(fence_raw) if fence_raw is not None else None
        except (TypeError, ValueError):
            fence_token = None
        wbc_attempt_reference = str(
            occurrence.get("wbc_attempt_reference")
            or occurrence.get("coordinator_attempt_id")
            or ""
        ).strip()
    return grant_id, fence_token, wbc_attempt_reference


def _boundary_target_mapping(
    *,
    identity: Mapping[str, Any],
    target: ActionTarget,
    environment: str | None,
    session: str,
    attempt: str | None,
    fence_token: int | None,
    request_id: str,
) -> dict[str, Any]:
    """Translate the canonical coordinates onto the M7 boundary target.

    Every field is a real coordinate (identity plan/phase, decision
    target, session, attempt, environment, fence, request id) or an
    explicit typed constant; the adapter never invents an owner identity.
    """
    occurrence = identity.get("occurrence")
    id_target = occurrence.get("target") if isinstance(occurrence, Mapping) else None
    plan = id_target.get("plan") if isinstance(id_target, Mapping) else ""
    phase = id_target.get("phase") if isinstance(id_target, Mapping) else ""
    return {
        "environment": environment or "",
        "session": session,
        "chain": plan or "",
        "plan_revision": plan or "",
        "phase": phase or "repair",
        "task": target.target,
        "attempt": attempt or "",
        "normalized_failure_kind": "maintenance_effect",
        "blocker_or_phase_result_hash": request_id or "",
        "fence": str(fence_token) if fence_token is not None else "",
    }


def _is_sha256_hex(value: str) -> bool:
    """Whether *value* is a well-formed 64-char lowercase sha256 hex digest."""
    return len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _validate_effect_payload_inputs(
    *,
    effect_kind: EffectKind,
    source_digest: str | None,
    install_digest: str | None,
    reason: str,
) -> tuple[EffectRejectReason, ...]:
    """Validate optional effect coordinates BEFORE any delegation.

    A malformed coordinate fails closed before the unified fixer is ever
    consulted (wrong install hash, malformed source digest, or an empty
    retrigger reason never reach an effect).
    """
    if (
        effect_kind is EffectKind.SOURCE_CHANGE
        and source_digest is not None
        and not _is_sha256_hex(source_digest)
    ):
        return (EffectRejectReason.INVALID_SOURCE_DIGEST,)
    if (
        effect_kind is EffectKind.INSTALLATION
        and install_digest is not None
        and not _is_sha256_hex(install_digest)
    ):
        return (EffectRejectReason.INVALID_INSTALL_DIGEST,)
    if effect_kind is EffectKind.RETRIGGER and not str(reason).strip():
        return (EffectRejectReason.INVALID_RETRIGGER_REASON,)
    return ()


def _map_effect_reasons(
    reasons: tuple[RequestRejectReason, ...],
) -> tuple[EffectRejectReason, ...]:
    """Translate shared fail-closed reasons onto the effect vocabulary.

    Every shared reason value (torn, cross-environment, stale authority,
    missing WBC/lease, unknown evidence, non-dispatchable, pending
    handoff, identity mismatch, missing identity) exists verbatim; an
    unmappable value is never guessed and degrades to the typed
    ``NON_DISPATCHABLE`` fail-closed reason.
    """
    mapped: list[EffectRejectReason] = []
    for reason in reasons:
        try:
            mapped.append(EffectRejectReason(reason.value))
        except ValueError:
            mapped.append(EffectRejectReason.NON_DISPATCHABLE)
    return tuple(dict.fromkeys(mapped))


def _effect_ref(reservation: Mapping[str, Any]) -> OwnerRef:
    """One immutable reference to the canonical effect reservation/outcome.

    The reference is locator-only (owner kind, record type, typed
    reservation identity, read-contract schema version, locator into the
    canonical effect ledger, and the canonical content digest of the
    reservation record).  It never embeds an owner payload and never
    authorizes the next lifecycle edge by itself.
    """
    reservation_id = str(reservation.get("reservation_id") or "").strip()
    key = str(reservation.get("repair_identity_key") or "").strip() or "occurrence"
    return OwnerRef(
        owner="repair_custody",
        record_type="effect_receipt",
        identity=reservation_id,
        schema_version=str(MAINTENANCE_SCHEMA_VERSION),
        locator=f"repair_effect://{key}:{reservation_id}",
        digest=_request_digest(reservation),
    )


def _effect_payload(
    effect_kind: EffectKind,
    *,
    effect_ref: OwnerRef,
    source_digest: str | None,
    install_digest: str | None,
    reason: str,
) -> OperationalPayload:
    """Build the discriminated payload for one effect kind."""
    if effect_kind is EffectKind.SOURCE_CHANGE:
        return SourceChangePayload(change_ref=effect_ref, source_digest=source_digest)
    if effect_kind is EffectKind.INSTALLATION:
        return InstallationPayload(install_ref=effect_ref, install_digest=install_digest)
    return RetriggerPayload(retrigger_ref=effect_ref, reason=reason or None)


def _default_receipts_inspect(
    queue_root: str | Path,
) -> Callable[[Mapping[str, Any]], MutationReservation | None]:
    """Canonical M10 effect-ledger receipt query for one queue root.

    The canonical effect ledger is the sole authority for reservations and
    outcomes; the adapter only ever READS it through this seam and never
    reimplements a reservation or outcome store.
    """
    store = RepairEffectLedger(queue_root)

    def _inspect(identity: Mapping[str, Any]) -> MutationReservation | None:
        return store.inspect(identity)

    return _inspect


def _commit_effect_event(
    *,
    ledger: MaintenanceLedger,
    effect_kind: EffectKind,
    occurrence: OccurrenceCoordinates,
    lease: LeaseCoordinates,
    run_authority: RunAuthorityCoordinates,
    policy: PolicyVersionCoordinates,
    target: ActionTarget,
    producer: ProducerPrincipal,
    observed_at: UtcTime | datetime,
    wbc_attempt: WbcAttemptCoordinates | None,
    reservation_id: str,
    effect_ref: OwnerRef,
    source_digest: str | None,
    install_digest: str | None,
    reason: str,
    outcome: EffectOutcome,
    adopted_state: str | None,
    delegation_outcome: str | None,
    simple_fixer_outcome: str | None,
    envelope_digest: str,
) -> EffectRoutingResult:
    """Append one effect event with the separate owner receipt (at most once).

    The event id is derived from the canonical reservation id, so an exact
    retry deduplicates at the journal boundary (``event_replayed=True``)
    while a divergent reuse of the occurrence action is rejected without
    appending.  The immutable effect receipt travels both in the
    discriminated payload reference and in ``owner_receipts``; receipts
    never authorize the next edge.
    """
    event = OperationalEvent.build(
        event_id=f"{effect_kind.value}:{occurrence.occurrence_id}:{reservation_id}",
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=producer,
        payload=_effect_payload(
            effect_kind,
            effect_ref=effect_ref,
            source_digest=source_digest,
            install_digest=install_digest,
            reason=reason,
        ),
        observed_at=observed_at,
        wbc_attempt=wbc_attempt,
        owner_receipts=OwnerReceipts(receipt_refs=(effect_ref,)),
    )
    if ledger is None:
        raise ValueError(
            "route_allowlisted_effect requires a MaintenanceLedger to append "
            "the immutable effect-receipt reference"
        )
    prior = _prior_event_record(ledger, event.event_id)
    from arnold_pipelines.megaplan.maintenance.ledger import (
        MaintenanceEventConflict,
    )

    try:
        ledger.append(event)
    except MaintenanceEventConflict:
        return EffectRoutingResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            effect_kind=effect_kind,
            outcome=EffectOutcome.REJECTED,
            reasons=(EffectRejectReason.DIVERGENT_REUSE,),
            reservation_id=reservation_id,
            delegation_outcome=delegation_outcome,
            simple_fixer_outcome=simple_fixer_outcome,
            envelope_digest=envelope_digest,
        )

    return EffectRoutingResult(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        effect_kind=effect_kind,
        outcome=outcome,
        adopted_state=adopted_state,
        reservation_id=reservation_id,
        effect_ref=effect_ref,
        delegation_outcome=delegation_outcome,
        simple_fixer_outcome=simple_fixer_outcome,
        event_id=event.event_id,
        event_digest=canonical_digest(event),
        event_replayed=prior is not None,
        envelope_digest=envelope_digest,
    )


def route_allowlisted_effect(
    *,
    effect_kind: EffectKind | str,
    occurrence: OccurrenceCoordinates,
    lease: LeaseCoordinates,
    run_authority: RunAuthorityCoordinates,
    policy: PolicyVersionCoordinates,
    target: ActionTarget,
    producer: ProducerPrincipal,
    observed_at: UtcTime | datetime,
    repair_identity: Mapping[str, Any],
    sources: Sequence[JoinSource],
    environment: EnvironmentId | str | None = None,
    run: str | None = None,
    attempt: str | None = None,
    expected: ExpectedRequestAuthority | None = None,
    handoff_resolver: Callable[[str], HandoffResolution] | None = None,
    ledger: MaintenanceLedger | None = None,
    queue_root: str | Path,
    request_id: str,
    session: str,
    effect_class: str | RepairEffectClass,
    mutation_path: str = MUTATION_PATH_L1,
    mutate: Callable[[Any], str] | None = None,
    source_digest: str | None = None,
    install_digest: str | None = None,
    reason: str = "",
    wbc_attempt: WbcAttemptCoordinates | None = None,
    mutation_gate_fn: Callable[[str], bool] | None = None,
    allowlist_fn: Callable[
        [str | RepairEffectClass], AllowlistCheckResult
    ] | None = None,
    boundary_fn: Callable[..., ActionBoundaryResult] | None = None,
    delegation_fn: Callable[..., RepairDelegationResult] | None = None,
    receipts_fn: Callable[
        [Mapping[str, Any]], MutationReservation | None
    ] | None = None,
) -> EffectRoutingResult:
    """Route one allowlisted repair effect exactly once through the unified fixer.

    Applies to the claim, source/install, and retrigger edges.  Fail-closed
    order (nothing delegates and nothing appends before the previous step
    is satisfied):

    1. **Master/path mutation gate.**  The existing default-off
       ``ARNOLD_AUTONOMY`` master gate plus the named path gate
       (:func:`mutation_authorized`) must both pass; ``mutation_path``
       defaults to the L1 repair-trigger path.
    2. **M10 allowlist.**  The effect class must be APPROVED by
       :func:`check_effect_class`; every production effect class is
       action-off in M10.
    3. **Handoff gate.**  Every :data:`REQUEST_HANDOFF_IDS` handoff must
       resolve ACCEPTED (pending handoffs never dispatch an effect).
    4. **Fresh M7 action boundary.**  The canonical identity's grant id /
       fence token / WBC attempt are reread through
       :func:`validate_action_boundary_simple`; only an authorized result
       proceeds.
    5. **Coherent re-read.**  A fresh owner-source capture with the
       decision's occurrence / target / lease / fence dimensions declared;
       torn, cross-environment, cross-occurrence, stale-epoch, stale-fence,
       missing-WBC, and missing-lease reads fail closed.
    6. **Identity reconciliation.**  The canonical M7 identity envelope is
       reconciled exactly with the Maintenance decision coordinates.
    7. **Effect coordinate validation.**  Optional source/install digests
       and the retrigger reason are validated BEFORE any effect.
    8. **Crash reconciliation.**  The canonical M10 effect ledger is
       queried by the exact occurrence: a prior reservation or terminal
       outcome is ADOPTED without re-running the effect (crashes after
       reservation, after effect, and before the Maintenance append); only
       a missing prior outcome delegates freshly.
    9. **Delegate or adopt.**  A fresh outcome goes through
       :func:`delegate_to_simple_fixer` ONLY (no second fixer, no raw
       command, no lifecycle writer); adoption never invokes the fixer.
    10. **Append once.**  One source-change / installation / retrigger
        event carrying the immutable effect-receipt reference and the
        separate owner receipt is appended through the lifecycle-idempotent
        Maintenance ledger; exact retries deduplicate and divergent reuse
        is rejected without appending.
    """
    kind = EffectKind(effect_kind) if not isinstance(effect_kind, EffectKind) else effect_kind

    def _rejected(
        *reasons: EffectRejectReason,
        adopted_state: str | None = None,
        reservation_id: str | None = None,
        effect_ref: OwnerRef | None = None,
        delegation_outcome: str | None = None,
        simple_fixer_outcome: str | None = None,
        gate_result: str | None = None,
        allowlist_verdict: str | None = None,
        envelope_digest: str | None = None,
    ) -> EffectRoutingResult:
        return EffectRoutingResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            effect_kind=kind,
            outcome=EffectOutcome.REJECTED,
            reasons=tuple(dict.fromkeys(reasons)),
            adopted_state=adopted_state,
            reservation_id=reservation_id,
            effect_ref=effect_ref,
            delegation_outcome=delegation_outcome,
            simple_fixer_outcome=simple_fixer_outcome,
            gate_result=gate_result,
            allowlist_verdict=allowlist_verdict,
            envelope_digest=envelope_digest,
        )

    # 1. Default-off master/path mutation gate.
    gate_fn = mutation_gate_fn or mutation_authorized
    if not gate_fn(mutation_path):
        return _rejected(EffectRejectReason.MUTATION_DISABLED)

    # 2. M10 repair-effect allowlist.
    allow_fn = allowlist_fn or check_effect_class
    allowlist_result = allow_fn(effect_class)
    if allowlist_result.verdict is not AllowlistVerdict.APPROVED:
        return _rejected(
            EffectRejectReason.EFFECT_NOT_ALLOWLISTED,
            allowlist_verdict=allowlist_result.verdict.value,
        )

    # 3. Handoff gate (pending handoffs never dispatch an effect).
    resolver = handoff_resolver or default_handoff_registry().resolve
    pending: list[str] = []
    for handoff_id in REQUEST_HANDOFF_IDS:
        resolution = resolver(handoff_id)
        if resolution.state is not HandoffResolutionState.ACCEPTED:
            pending.append(handoff_id)
    if pending:
        return _rejected(EffectRejectReason.PENDING_HANDOFF)

    # 4. Fresh M7 action-boundary validation (never a cached result).
    grant_id, fence_token, wbc_ref = boundary_inputs_from_identity(repair_identity)
    if grant_id is None or fence_token is None:
        return _rejected(EffectRejectReason.BOUNDARY_INPUTS_MISSING)
    boundary_result = (boundary_fn or validate_action_boundary_simple)(
        action_type="repair",
        target=_boundary_target_mapping(
            identity=repair_identity,
            target=target,
            environment=str(environment) if environment is not None else None,
            session=session,
            attempt=attempt,
            fence_token=fence_token,
            request_id=request_id,
        ),
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        wbc_attempt_reference=wbc_ref,
    )
    if not boundary_result.authorized:
        return _rejected(
            EffectRejectReason.ACTION_BOUNDARY_BLOCKED,
            gate_result=boundary_result.gate_result.value,
        )

    # 5. Coherent direct owner-source re-read before any authority increase.
    envelope, reasons = _capture_coherent_envelope(
        sources=sources,
        observed_at=observed_at,
        environment=environment,
        run=run,
        attempt=attempt,
        occurrence_id=occurrence.occurrence_id,
        target_id=target.target,
        lease_id=lease.lease_id,
        fence=(expected.fencing_token if expected is not None else None),
        expected=expected,
    )
    if reasons:
        return _rejected(
            *_map_effect_reasons(reasons),
            envelope_digest=canonical_digest(envelope),
        )

    # 6. Reconcile the canonical identity with the decision coordinates.
    translated, identity_reasons = translate_occurrence_identity(
        identity=repair_identity,
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
    )
    if translated is None:
        return _rejected(
            *_map_effect_reasons(identity_reasons),
            envelope_digest=canonical_digest(envelope),
        )

    # 7. Validate optional effect coordinates before any effect.
    invalid_payload = _validate_effect_payload_inputs(
        effect_kind=kind,
        source_digest=source_digest,
        install_digest=install_digest,
        reason=reason,
    )
    if invalid_payload:
        return _rejected(*invalid_payload, envelope_digest=canonical_digest(envelope))

    # 8. Crash reconciliation through the canonical effect-ledger receipts.
    receipts = receipts_fn or _default_receipts_inspect(queue_root)
    try:
        prior = receipts(repair_identity)
    except Exception:
        return _rejected(
            EffectRejectReason.RECEIPT_UNAVAILABLE,
            envelope_digest=canonical_digest(envelope),
        )

    envelope_digest = canonical_digest(envelope)

    if prior is not None:
        # A prior canonical outcome exists: the effect is NEVER redriven.
        # Crash after reservation (RESERVED) and crash after effect (still
        # RESERVED or terminal) both adopt the durable canonical state; a
        # terminal row means the crash happened before the Maintenance
        # append and only the reference is missing.
        reservation = asdict(prior)
        effect_ref = _effect_ref(reservation)
        return _commit_effect_event(
            ledger=ledger,
            effect_kind=kind,
            occurrence=occurrence,
            lease=lease,
            run_authority=run_authority,
            policy=policy,
            target=target,
            producer=producer,
            observed_at=observed_at,
            wbc_attempt=wbc_attempt,
            reservation_id=prior.reservation_id,
            effect_ref=effect_ref,
            source_digest=source_digest,
            install_digest=install_digest,
            reason=reason,
            outcome=EffectOutcome.ADOPTED,
            adopted_state=prior.state,
            delegation_outcome=None,
            simple_fixer_outcome=None,
            envelope_digest=envelope_digest,
        )

    # 9. No prior outcome: delegate the exact occurrence through the
    #    unified fixer — the ONLY effect path (no second fixer, no raw
    #    command, no lifecycle writer).
    if mutate is None:
        return _rejected(
            EffectRejectReason.DELEGATION_REJECTED,
            delegation_outcome="missing_effect_mutation",
            envelope_digest=envelope_digest,
        )
    delegation = build_repair_delegation(
        "controller",
        request_id or f"{kind.value}:{occurrence.occurrence_id}",
        translated,
    )
    if delegation is None:
        return _rejected(
            EffectRejectReason.DELEGATION_REJECTED,
            delegation_outcome="invalid_delegation",
            envelope_digest=envelope_digest,
        )
    delegation_result = (delegation_fn or delegate_to_simple_fixer)(
        delegation,
        queue_dir=str(queue_root),
        mutate=mutate,
        actor="maintenance_recovery",
        request_id=request_id,
        session_id=session,
        kind="immediate_trigger",
        verifier_slot="",
    )
    if not delegation_result.delegated:
        return _rejected(
            EffectRejectReason.DELEGATION_REJECTED,
            delegation_outcome=delegation_result.outcome,
            simple_fixer_outcome=delegation_result.simple_fixer_outcome,
            envelope_digest=envelope_digest,
        )

    # 10. Append the immutable effect receipt once.
    evidence = (
        delegation_result.evidence
        if isinstance(delegation_result.evidence, Mapping)
        else {}
    )
    effect_ledger = evidence.get("effect_ledger")
    if not isinstance(effect_ledger, Mapping) or not str(
        effect_ledger.get("reservation_id") or ""
    ).strip():
        return _rejected(
            EffectRejectReason.MISSING_EFFECT_RECEIPT,
            delegation_outcome=delegation_result.outcome,
            simple_fixer_outcome=delegation_result.simple_fixer_outcome,
            envelope_digest=envelope_digest,
        )
    reservation_id = str(effect_ledger["reservation_id"]).strip()
    effect_ref = _effect_ref(effect_ledger)
    return _commit_effect_event(
        ledger=ledger,
        effect_kind=kind,
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=producer,
        observed_at=observed_at,
        wbc_attempt=wbc_attempt,
        reservation_id=reservation_id,
        effect_ref=effect_ref,
        source_digest=source_digest,
        install_digest=install_digest,
        reason=reason,
        outcome=EffectOutcome.DELEGATED,
        adopted_state=None,
        delegation_outcome=delegation_result.outcome,
        simple_fixer_outcome=delegation_result.simple_fixer_outcome,
        envelope_digest=envelope_digest,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Plan Step 12 / T13 — verified recurrence admission and human escalation
# ═══════════════════════════════════════════════════════════════════════════
#
# A verified recurrence ALWAYS creates or joins one FRESH canonical M7
# occurrence with a new lease, epoch, keys, and occurrence-scoped budget,
# causally linked to the predecessor's closure and root-cause cluster.  It
# never reuses a prior receipt, never reuses the predecessor occurrence, and
# is only admitted after the predecessor's terminal-verification closure is
# present in the Maintenance ledger.  A true human gate or ambiguous blocker
# is recorded with an immutable escalation-owner reference while canonical
# custody stays OPEN: escalation never waives, never force-proceeds, and
# never closes custody.


class RecurrenceAdmissionOutcome(str, Enum):
    """Closed outcomes of one verified-recurrence admission.

    * ``ADMITTED`` — a fresh canonical M7 occurrence was created through the
      canonical enqueue-or-join seam and its recurrence event appended with
      a fresh immutable request reference;
    * ``JOINED`` — the seam coalesced onto the identical request for the
      fresh occurrence (e.g. a concurrent admission) and the recurrence
      event was appended (deduplicated on exact replay);
    * ``REJECTED`` — fail-closed: no fresh occurrence was admitted and no
      recurrence event was appended.
    """

    ADMITTED = "admitted"
    JOINED = "joined"
    REJECTED = "rejected"


class RecurrenceRejectReason(str, Enum):
    """Closed typed reasons for a rejected recurrence admission (never guessed)."""

    PENDING_HANDOFF = "pending_handoff"
    TORN_ENVELOPE = "torn_envelope"
    CROSS_ENVIRONMENT = "cross_environment"
    STALE_AUTHORITY = "stale_authority"
    MISSING_WBC = "missing_wbc"
    MISSING_LEASE = "missing_lease"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    NON_DISPATCHABLE = "non_dispatchable"
    MISSING_OCCURRENCE_IDENTITY = "missing_occurrence_identity"
    IDENTITY_MISMATCH = "identity_mismatch"
    ENQUEUE_REJECTED = "enqueue_rejected"
    DIVERGENT_REUSE = "divergent_reuse"
    SAME_OCCURRENCE_REUSE = "same_occurrence_reuse"
    MISSING_PREDECESSOR = "missing_predecessor"
    PREDECESSOR_NOT_CLOSED = "predecessor_not_closed"
    REUSED_RECEIPT = "reused_receipt"
    INVALID_BUDGET = "invalid_budget"


class RecurrenceAdmissionResult(BaseModel):
    """Typed fail-closed outcome of one verified-recurrence admission.

    ``outcome`` is ``admitted`` or ``joined`` ONLY when the fresh
    occurrence's immutable request reference AND its recurrence event were
    committed (or replayed exactly once); every rejected outcome carries at
    least one typed :class:`RecurrenceRejectReason` and never appends a
    recurrence event.  ``budget`` is the fresh occurrence-scoped budget when
    one was supplied (never the predecessor's consumed budget).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    outcome: RecurrenceAdmissionOutcome
    reasons: tuple[RecurrenceRejectReason, ...] = ()
    predecessor_occurrence_id: StrictStr
    predecessor_event_id: StrictStr
    new_occurrence_id: StrictStr
    request_id: StrictStr | None = None
    request_ref: OwnerRef | None = None
    request_event_id: StrictStr | None = None
    request_event_replayed: bool = False
    event_id: StrictStr | None = None
    event_digest: StrictStr | None = None
    event_replayed: bool = False
    envelope_digest: StrictStr | None = None
    budget: dict[str, Any] | None = None

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> RecurrenceAdmissionResult:
        if self.outcome is RecurrenceAdmissionOutcome.REJECTED and not self.reasons:
            raise ValueError(
                "a rejected recurrence admission requires at least one typed "
                "reject reason"
            )
        if self.outcome is not RecurrenceAdmissionOutcome.REJECTED and self.reasons:
            raise ValueError(
                "an admitted/joined recurrence must not carry reject reasons; "
                f"got {[reason.value for reason in self.reasons]}"
            )
        if (
            self.outcome is not RecurrenceAdmissionOutcome.REJECTED
            and self.request_ref is None
        ):
            raise ValueError(
                "an admitted/joined recurrence requires the fresh immutable "
                "request reference"
            )
        if self.outcome is not RecurrenceAdmissionOutcome.REJECTED and self.event_id is None:
            raise ValueError(
                "an admitted/joined recurrence requires the recurrence event id"
            )
        return self


class EscalationOutcome(str, Enum):
    """Closed outcomes of one human-escalation record.

    * ``RECORDED`` — the immutable escalation-owner reference was appended
      as a ``human_escalation`` operational event and canonical custody
      stays OPEN (escalation never waives a gate, never force-proceeds, and
      never closes custody);
    * ``REJECTED`` — fail-closed: nothing was appended.
    """

    RECORDED = "recorded"
    REJECTED = "rejected"


class EscalationRejectReason(str, Enum):
    """Closed typed reasons for a rejected human-escalation record."""

    MISSING_ESCALATION_OWNER = "missing_escalation_owner"
    EMPTY_REASON = "empty_reason"
    INVALID_ESCALATION_REF = "invalid_escalation_ref"
    DIVERGENT_REUSE = "divergent_reuse"


class HumanEscalationResult(BaseModel):
    """Typed fail-closed outcome of one human-escalation record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    outcome: EscalationOutcome
    reasons: tuple[EscalationRejectReason, ...] = ()
    escalation_owner: StrictStr | None = None
    escalation_ref: OwnerRef | None = None
    event_id: StrictStr | None = None
    event_digest: StrictStr | None = None
    event_replayed: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> HumanEscalationResult:
        if self.outcome is EscalationOutcome.REJECTED and not self.reasons:
            raise ValueError(
                "a rejected human-escalation record requires at least one "
                "typed reject reason"
            )
        if self.outcome is not EscalationOutcome.REJECTED and self.reasons:
            raise ValueError(
                "a recorded human escalation must not carry reject reasons; "
                f"got {[reason.value for reason in self.reasons]}"
            )
        if self.outcome is not EscalationOutcome.REJECTED and self.escalation_ref is None:
            raise ValueError(
                "a recorded human escalation requires the immutable "
                "escalation-owner reference"
            )
        return self


def _map_recurrence_reasons(
    reasons: tuple[RequestRejectReason, ...],
) -> tuple[RecurrenceRejectReason, ...]:
    """Translate shared fail-closed reasons onto the recurrence vocabulary.

    Every shared reason value exists verbatim; an unmappable value is never
    guessed and degrades to the typed ``NON_DISPATCHABLE`` fail-closed
    reason.  ``STALE_AUTHORITY`` is mapped by enum identity so the typed
    reason survives even when the shared enum's serialized value is
    unavailable.
    """
    mapped: list[RecurrenceRejectReason] = []
    for reason in reasons:
        if reason is RequestRejectReason.STALE_AUTHORITY:
            mapped.append(RecurrenceRejectReason.STALE_AUTHORITY)
            continue
        try:
            mapped.append(RecurrenceRejectReason(reason.value))
        except ValueError:
            mapped.append(RecurrenceRejectReason.NON_DISPATCHABLE)
    return tuple(dict.fromkeys(mapped))


def _predecessor_closure_record(
    ledger: MaintenanceLedger,
    predecessor_occurrence_id: str,
    predecessor_event_id: str,
) -> dict[str, Any] | None:
    """Return the committed terminal-verification record closing the predecessor.

    The recurrence link must point at the predecessor's CLOSURE: the found
    record must strict-decode as an operational event whose action is
    ``terminal_verification`` for exactly the predecessor occurrence.
    Anything else — a missing record, a different action, a different
    occurrence, or a malformed payload — is NOT a closure and returns
    ``None`` (the recurrence is not admitted).
    """
    path = ledger.events_path
    if not path.exists():
        return None
    import json

    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload") or {}
            if payload.get("event_id") != predecessor_event_id:
                continue
            try:
                event = strict_loads(OperationalEvent, payload)
            except Exception:
                return None
            if (
                event.action_kind is OperationalActionKind.TERMINAL_VERIFICATION
                and event.occurrence.occurrence_id == predecessor_occurrence_id
            ):
                return record
            return None
    return None


def _predecessor_request_id(
    ledger: MaintenanceLedger,
    occurrence_id: str,
) -> str | None:
    """The canonical request id recorded for *occurrence_id*, if any.

    Scans the committed Maintenance ledger for the occurrence's
    ``repair_request`` operational event.  Used by the receipt-freshness
    gate: a fresh occurrence's request receipt must NEVER equal a prior
    occurrence's receipt (prior receipts are never reused).
    """
    path = ledger.events_path
    if not path.exists():
        return None
    import json

    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload") or {}
            if payload.get("action_kind") != "repair_request":
                continue
            try:
                event = strict_loads(OperationalEvent, payload)
            except Exception:
                continue
            if event.occurrence.occurrence_id == occurrence_id:
                return event.payload.request_id
    return None


def admit_verified_recurrence(
    *,
    occurrence: OccurrenceCoordinates,
    lease: LeaseCoordinates,
    run_authority: RunAuthorityCoordinates,
    policy: PolicyVersionCoordinates,
    target: ActionTarget,
    producer: ProducerPrincipal,
    observed_at: UtcTime | datetime,
    occurrence_identity: Mapping[str, Any],
    sources: Sequence[JoinSource],
    predecessor_occurrence_id: str,
    predecessor_event_id: str,
    root_cause_cluster: str | None = None,
    budget: OccurrenceBudget | None = None,
    environment: EnvironmentId | str | None = None,
    run: str | None = None,
    attempt: str | None = None,
    expected: ExpectedRequestAuthority | None = None,
    handoff_resolver: Callable[[str], HandoffResolution] | None = None,
    enqueue_fn: Callable[..., Mapping[str, Any]] = enqueue_occurrence_bound_repair_request,
    ledger: MaintenanceLedger | None = None,
    wbc_attempt: WbcAttemptCoordinates | None = None,
    queue_root: str | Path,
    session: str,
    problem_signature: Mapping[str, Any],
    source: str,
    root_cause_hint: Any = "",
    marker_dir: str | Path | None = None,
    target_mapping: Mapping[str, Any] | None = None,
    workspace: str | Path | None = None,
    run_kind: str = "",
    evidence_cursor_digest: str = "",
    terminal_receipt_expectations: list[str] | None = None,
) -> RecurrenceAdmissionResult:
    """Admit one verified recurrence as a FRESH canonical M7 occurrence.

    The fresh occurrence receives a new lease, epoch, keys (the recurrence
    event derives its own operational action key from the new occurrence
    digest), and an occurrence-scoped budget, all causally linked to the
    predecessor's closure and root-cause cluster.  Fail-closed order
    (nothing enqueues and nothing appends before the previous step is
    satisfied):

    1. **Predecessor linkage.**  The predecessor occurrence/event identities
       must be present and the fresh occurrence must DIFFER from the
       predecessor occurrence (a recurrence is never the same occurrence).
    2. **Predecessor closure.**  The Maintenance ledger must hold the
       predecessor's terminal-verification closure event; a missing or
       non-terminal predecessor is ``PREDECESSOR_NOT_CLOSED``.
    3. **Fresh budget.**  When supplied, the occurrence-scoped budget must
       be fresh (``attempts_used == 0``); a recurrence never inherits the
       predecessor's consumed budget (``INVALID_BUDGET`` otherwise).
    4. **Enqueue-or-join.**  The fresh occurrence is submitted through the
       SAME canonical seam (:func:`submit_occurrence_bound_repair_request`)
       with the new lease/epoch/keys identity; a rejected submission is
       mapped onto the recurrence rejection vocabulary.
    5. **Receipt freshness.**  The fresh request receipt must NOT equal the
       predecessor's recorded request receipt — prior receipts are never
       reused for a different occurrence (``REUSED_RECEIPT``).
    6. **Append once.**  One ``recurrence`` operational event links the
       fresh occurrence to the predecessor closure and root-cause cluster;
       exact retries deduplicate (``event_replayed=True``) and a divergent
       reuse is rejected without appending (``DIVERGENT_REUSE``).
    """
    if ledger is None:
        raise ValueError(
            "admit_verified_recurrence requires a MaintenanceLedger to verify "
            "the predecessor closure and append the recurrence event"
        )

    new_occurrence_id = occurrence.occurrence_id
    predecessor_occurrence_id = str(predecessor_occurrence_id or "").strip()
    predecessor_event_id = str(predecessor_event_id or "").strip()

    def _rejected(
        *reasons: RecurrenceRejectReason,
        envelope_digest: str | None = None,
    ) -> RecurrenceAdmissionResult:
        return RecurrenceAdmissionResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=RecurrenceAdmissionOutcome.REJECTED,
            reasons=tuple(dict.fromkeys(reasons)),
            predecessor_occurrence_id=predecessor_occurrence_id,
            predecessor_event_id=predecessor_event_id,
            new_occurrence_id=new_occurrence_id,
            envelope_digest=envelope_digest,
        )

    # 1. Predecessor linkage: identities present and occurrence is fresh.
    if not predecessor_occurrence_id or not predecessor_event_id:
        return _rejected(RecurrenceRejectReason.MISSING_PREDECESSOR)
    if predecessor_occurrence_id == new_occurrence_id:
        return _rejected(RecurrenceRejectReason.SAME_OCCURRENCE_REUSE)

    # 2. Predecessor closure: only a terminal-verification closure admits.
    if (
        _predecessor_closure_record(
            ledger, predecessor_occurrence_id, predecessor_event_id
        )
        is None
    ):
        return _rejected(RecurrenceRejectReason.PREDECESSOR_NOT_CLOSED)

    # 3. Fresh occurrence-scoped budget (never the predecessor's consumed one).
    if budget is not None and budget.attempts_used != 0:
        return _rejected(RecurrenceRejectReason.INVALID_BUDGET)

    # 4. Enqueue-or-join the fresh occurrence through the SAME canonical seam.
    request_result = submit_occurrence_bound_repair_request(
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=producer,
        observed_at=observed_at,
        occurrence_identity=occurrence_identity,
        sources=sources,
        environment=environment,
        run=run,
        attempt=attempt,
        expected=expected,
        handoff_resolver=handoff_resolver,
        enqueue_fn=enqueue_fn,
        ledger=ledger,
        wbc_attempt=wbc_attempt,
        queue_root=queue_root,
        session=session,
        problem_signature=problem_signature,
        source=source,
        root_cause_hint=root_cause_hint,
        marker_dir=marker_dir,
        target_mapping=target_mapping,
        workspace=workspace,
        run_kind=run_kind,
        evidence_cursor_digest=evidence_cursor_digest,
        terminal_receipt_expectations=terminal_receipt_expectations,
    )
    if request_result.outcome is RequestOutcome.REJECTED:
        return _rejected(
            *_map_recurrence_reasons(request_result.reasons),
            envelope_digest=request_result.envelope_digest,
        )

    # 5. Receipt freshness: the fresh request receipt is never a prior receipt.
    request_ref = request_result.request_ref
    assert request_ref is not None  # guaranteed by RequestSubmissionResult
    prior_request_id = _predecessor_request_id(ledger, predecessor_occurrence_id)
    if prior_request_id is not None and request_result.request_id == prior_request_id:
        return _rejected(
            RecurrenceRejectReason.REUSED_RECEIPT,
            envelope_digest=request_result.envelope_digest,
        )

    # 6. Append the recurrence event once, linked to closure + cluster.
    event = OperationalEvent.build(
        event_id=f"recurrence:{new_occurrence_id}:{predecessor_event_id}",
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=producer,
        payload=RecurrencePayload(
            recurrence=RecurrenceReference(
                predecessor_occurrence_id=predecessor_occurrence_id,
                predecessor_event_id=predecessor_event_id,
                root_cause_cluster=root_cause_cluster,
            )
        ),
        observed_at=observed_at,
        wbc_attempt=wbc_attempt,
        owner_receipts=OwnerReceipts(receipt_refs=(request_ref,)),
        extensions=(
            Extensions(
                {"occurrence_budget": budget.model_dump(mode="json")}
            )
            if budget is not None
            else None
        ),
    )
    prior = _prior_event_record(ledger, event.event_id)
    from arnold_pipelines.megaplan.maintenance.ledger import (
        MaintenanceEventConflict,
    )

    try:
        ledger.append(event)
    except MaintenanceEventConflict:
        return _rejected(
            RecurrenceRejectReason.DIVERGENT_REUSE,
            envelope_digest=request_result.envelope_digest,
        )

    return RecurrenceAdmissionResult(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        outcome=(
            RecurrenceAdmissionOutcome.JOINED
            if request_result.outcome is RequestOutcome.JOINED
            else RecurrenceAdmissionOutcome.ADMITTED
        ),
        predecessor_occurrence_id=predecessor_occurrence_id,
        predecessor_event_id=predecessor_event_id,
        new_occurrence_id=new_occurrence_id,
        request_id=request_result.request_id,
        request_ref=request_ref,
        request_event_id=request_result.event_id,
        request_event_replayed=request_result.event_replayed,
        event_id=event.event_id,
        event_digest=canonical_digest(event),
        event_replayed=prior is not None,
        envelope_digest=request_result.envelope_digest,
        budget=budget.model_dump(mode="json") if budget is not None else None,
    )


def record_human_escalation(
    *,
    occurrence: OccurrenceCoordinates,
    lease: LeaseCoordinates,
    run_authority: RunAuthorityCoordinates,
    policy: PolicyVersionCoordinates,
    target: ActionTarget,
    producer: ProducerPrincipal,
    observed_at: UtcTime | datetime,
    escalation_owner: str,
    reason: str,
    escalation_ref: OwnerRef,
    ledger: MaintenanceLedger | None = None,
    wbc_attempt: WbcAttemptCoordinates | None = None,
) -> HumanEscalationResult:
    """Record a true human gate / ambiguous blocker with an immutable owner ref.

    A true human gate or ambiguous blocker is recorded with an immutable
    escalation-owner reference while canonical custody stays OPEN: the
    ``human_escalation`` action is nonterminal by contract (it never waives,
    never force-proceeds, and never closes custody).  Fail-closed order
    (nothing appends before the previous step is satisfied):

    1. **Owner.**  The escalation owner must be a non-empty identity — a
       missing owner is typed ``MISSING_ESCALATION_OWNER``.
    2. **Reason.**  The gate reason must be non-empty — ``EMPTY_REASON``.
    3. **Reference.**  The immutable escalation-owner reference must be
       present — ``INVALID_ESCALATION_REF``.
    4. **Append once.**  One ``human_escalation`` operational event carries
       the reference; exact retries deduplicate (``event_replayed=True``)
       and a divergent reuse of the occurrence action is rejected without
       appending (``DIVERGENT_REUSE``).
    """
    if ledger is None:
        raise ValueError(
            "record_human_escalation requires a MaintenanceLedger to append "
            "the immutable escalation-owner reference"
        )

    owner = str(escalation_owner or "").strip()
    gate_reason = str(reason or "").strip()

    def _rejected(*reasons: EscalationRejectReason) -> HumanEscalationResult:
        return HumanEscalationResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=EscalationOutcome.REJECTED,
            reasons=tuple(dict.fromkeys(reasons)),
            escalation_owner=owner or None,
            escalation_ref=escalation_ref if escalation_ref is not None else None,
        )

    if not owner:
        return _rejected(EscalationRejectReason.MISSING_ESCALATION_OWNER)
    if not gate_reason:
        return _rejected(EscalationRejectReason.EMPTY_REASON)
    if escalation_ref is None:
        return _rejected(EscalationRejectReason.INVALID_ESCALATION_REF)

    event = OperationalEvent.build(
        event_id=(
            f"human_escalation:{occurrence.occurrence_id}:"
            f"{escalation_ref.identity or escalation_ref.locator}"
        ),
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=producer,
        payload=HumanEscalationPayload(
            escalation=EscalationReference(
                reason=gate_reason,
                escalation_owner=owner,
                human_gate=True,
                escalation_ref=escalation_ref,
            )
        ),
        observed_at=observed_at,
        wbc_attempt=wbc_attempt,
    )
    prior = _prior_event_record(ledger, event.event_id)
    from arnold_pipelines.megaplan.maintenance.ledger import (
        MaintenanceEventConflict,
    )

    try:
        ledger.append(event)
    except MaintenanceEventConflict:
        return HumanEscalationResult(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            outcome=EscalationOutcome.REJECTED,
            reasons=(EscalationRejectReason.DIVERGENT_REUSE,),
            escalation_owner=owner,
            escalation_ref=escalation_ref,
        )

    return HumanEscalationResult(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        outcome=EscalationOutcome.RECORDED,
        escalation_owner=owner,
        escalation_ref=escalation_ref,
        event_id=event.event_id,
        event_digest=canonical_digest(event),
        event_replayed=prior is not None,
    )


class TerminalOutcome(str, Enum):
    SUBMITTED = "submitted"
    REJECTED = "rejected"


class TerminalRejectReason(str, Enum):
    FINAL_BOUNDARY_REQUIRED = "final_boundary_required"
    FINAL_BOUNDARY_BLOCKED = "final_boundary_blocked"
    PENDING_HANDOFF = "pending_handoff"
    STALE_AUTHORITY = "stale_authority"
    MISSING_WBC = "missing_wbc"
    MISSING_LEASE = "missing_lease"
    TORN_ENVELOPE = "torn_envelope"
    CROSS_ENVIRONMENT = "cross_environment"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    NON_DISPATCHABLE = "non_dispatchable"
    IDENTITY_MISMATCH = "identity_mismatch"
    ENQUEUE_REJECTED = "enqueue_rejected"
    DIVERGENT_REUSE = "divergent_reuse"


class TerminalSubmissionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    outcome: TerminalOutcome
    reasons: tuple[TerminalRejectReason, ...] = ()
    event_id: StrictStr | None = None
    event_digest: StrictStr | None = None
    event_replayed: bool = False
    envelope_digest: StrictStr | None = None
    enqueue_status: StrictStr | None = None
    request_id: StrictStr | None = None
    request_ref: OwnerRef | None = None
    boundary_result: dict[str, Any] | None = None
    custody_closed: bool = False


#: Deterministic mapping from the canonical request seam's typed rejections
#: to the terminal custody vocabulary.  Every rejection reason is preserved
#: (never collapsed onto a generic enqueue failure); unknown reasons fail
#: closed to ``ENQUEUE_REJECTED``.
_REQUEST_REJECT_TO_TERMINAL: dict[RequestRejectReason, TerminalRejectReason] = {
    RequestRejectReason.PENDING_HANDOFF: TerminalRejectReason.PENDING_HANDOFF,
    RequestRejectReason.STALE_AUTHORITY: TerminalRejectReason.STALE_AUTHORITY,
    RequestRejectReason.MISSING_WBC: TerminalRejectReason.MISSING_WBC,
    RequestRejectReason.MISSING_LEASE: TerminalRejectReason.MISSING_LEASE,
    RequestRejectReason.TORN_ENVELOPE: TerminalRejectReason.TORN_ENVELOPE,
    RequestRejectReason.CROSS_ENVIRONMENT: TerminalRejectReason.CROSS_ENVIRONMENT,
    RequestRejectReason.UNKNOWN_EVIDENCE: TerminalRejectReason.UNKNOWN_EVIDENCE,
    RequestRejectReason.NON_DISPATCHABLE: TerminalRejectReason.NON_DISPATCHABLE,
    RequestRejectReason.MISSING_OCCURRENCE_IDENTITY: (
        TerminalRejectReason.IDENTITY_MISMATCH
    ),
    RequestRejectReason.IDENTITY_MISMATCH: TerminalRejectReason.IDENTITY_MISMATCH,
    RequestRejectReason.ENQUEUE_REJECTED: TerminalRejectReason.ENQUEUE_REJECTED,
    RequestRejectReason.DIVERGENT_REUSE: TerminalRejectReason.DIVERGENT_REUSE,
}


def _serialize_boundary_result(boundary: Any) -> dict[str, Any] | None:
    """Serialize one typed boundary result for the terminal receipt.

    Prefers a dataclass field dump; falls back to the authoritative
    ``authorized`` flag plus the stable scalar fields so the receipt never
    loses the boundary verdict even if the result shape changes.
    """
    if boundary is None:
        return None
    try:
        import dataclasses

        if dataclasses.is_dataclass(boundary):
            return dataclasses.asdict(boundary)
    except Exception:
        pass
    return {
        "authorized": bool(getattr(boundary, "authorized", False)),
        "action_type": str(getattr(boundary, "action_type", "")),
        "target_digest": str(getattr(boundary, "target_digest", "")),
        "enforcement_enabled": bool(
            getattr(boundary, "enforcement_enabled", False)
        ),
    }


def submit_terminal_verification(
    *,
    occurrence: Any,
    lease: Any,
    run_authority: Any,
    policy: Any,
    target: Any,
    producer: Any,
    observed_at: Any,
    verifier: Any,
    terminal_reason: str,
    negative_control_refs: Sequence[Any],
    verification_ref: OwnerRef,
    sources: Sequence[Any],
    environment: Any = None,
    run: str | None = None,
    attempt: str | None = None,
    expected: Any = None,
    boundary_fn: Callable[..., Any] | None = None,
    ledger: Any = None,
    wbc_attempt: Any = None,
    request_kwargs: Mapping[str, Any] | None = None,
) -> TerminalSubmissionResult:
    """Submit terminal verification exactly once through canonical M7 custody.

    Fail-closed order: the final M7 action-validator reread is MANDATORY
    (``boundary_fn`` is required and must authorize), then the canonical
    occurrence-bound request seam is re-driven (handoff gate, fresh
    custody/WBC capture, identity translation, enqueue-or-join), and only
    after that succeeds is the ``terminal_verification`` evidence event
    appended once.  The Maintenance ledger append is evidence, never custody
    authority; custody is closed only by the canonical request seam.
    """
    from arnold_pipelines.megaplan.maintenance.events import (
        OperationalEvent,
        OwnerReceipts,
        TerminalVerificationPayload,
        canonical_digest,
    )
    from arnold_pipelines.megaplan.maintenance.ledger import (
        MaintenanceEventConflict,
    )

    def _reject(reason: TerminalRejectReason) -> TerminalSubmissionResult:
        return TerminalSubmissionResult(
            outcome=TerminalOutcome.REJECTED,
            reasons=(reason,),
            custody_closed=False,
        )

    if boundary_fn is None:
        return _reject(TerminalRejectReason.FINAL_BOUNDARY_REQUIRED)
    request_kwargs = dict(request_kwargs or {})
    request_kwargs["ledger"] = ledger
    if expected is not None:
        request_kwargs["expected"] = expected
    repair_identity = request_kwargs.get("occurrence_identity")
    if not isinstance(repair_identity, Mapping):
        return _reject(TerminalRejectReason.IDENTITY_MISMATCH)
    grant_id, fence_token, wbc_ref = boundary_inputs_from_identity(repair_identity)
    identity_occurrence = repair_identity.get("occurrence")
    target_mapping = (
        dict(identity_occurrence.get("target"))
        if isinstance(identity_occurrence, Mapping)
        else None
    )
    if grant_id is None or fence_token is None or not target_mapping:
        return _reject(TerminalRejectReason.FINAL_BOUNDARY_BLOCKED)
    boundary = boundary_fn(
        action_type="completion",
        target=target_mapping,
        run_authority_grant_id=grant_id,
        coordinator_fence_token=fence_token,
        wbc_attempt_reference=wbc_ref,
    )
    if not isinstance(boundary, ActionBoundaryResult) or not boundary.authorized:
        return _reject(TerminalRejectReason.FINAL_BOUNDARY_BLOCKED)

    request_result = submit_occurrence_bound_repair_request(**request_kwargs)
    if request_result.outcome is RequestOutcome.REJECTED:
        reason = _REQUEST_REJECT_TO_TERMINAL.get(
            request_result.reasons[0] if request_result.reasons else None,
            TerminalRejectReason.ENQUEUE_REJECTED,
        )
        return _reject(reason)

    envelope_digest = canonical_digest(
        capture_observation(
            sources,
            observed_at=observed_at,
            environment=environment,
            run=run,
            attempt=attempt,
            occurrence_id=occurrence.occurrence_id,
            target=target.target,
            lease_id=lease.lease_id,
            fence=expected.fencing_token if expected is not None else None,
        )
    )
    terminal_event = OperationalEvent.build(
        event_id=f"terminal_verification:{occurrence.occurrence_id}",
        occurrence=occurrence,
        lease=lease,
        run_authority=run_authority,
        policy=policy,
        target=target,
        producer=ProducerPrincipal(
            principal=verifier.principal, role=ProducerRole.VERIFIER
        ),
        payload=TerminalVerificationPayload(
            verifier=verifier,
            terminal_reason=terminal_reason,
            negative_control_refs=tuple(negative_control_refs),
            verification_ref=verification_ref,
        ),
        observed_at=observed_at,
        wbc_attempt=wbc_attempt,
        owner_receipts=OwnerReceipts(receipt_refs=(verification_ref,)),
    )
    prior = _prior_event_record(ledger, terminal_event.event_id)
    try:
        ledger.append(terminal_event)
    except MaintenanceEventConflict:
        return _reject(TerminalRejectReason.DIVERGENT_REUSE)
    return TerminalSubmissionResult(
        outcome=TerminalOutcome.SUBMITTED,
        event_id=terminal_event.event_id,
        event_digest=canonical_digest(terminal_event),
        event_replayed=prior is not None,
        envelope_digest=envelope_digest,
        enqueue_status=getattr(request_result, "enqueue_status", None)
        or getattr(request_result, "outcome", None),
        request_id=getattr(request_result, "request_id", None),
        request_ref=getattr(request_result, "request_ref", None),
        boundary_result=_serialize_boundary_result(boundary),
        custody_closed=True,
    )


__all__ = [
    "EffectKind",
    "EffectOutcome",
    "EffectRejectReason",
    "EffectRoutingResult",
    "EscalationOutcome",
    "EscalationRejectReason",
    "ExpectedRequestAuthority",
    "HumanEscalationResult",
    "REQUEST_HANDOFF_IDS",
    "RecurrenceAdmissionOutcome",
    "RecurrenceAdmissionResult",
    "RecurrenceRejectReason",
    "RequestOutcome",
    "RequestRejectReason",
    "RequestSubmissionResult",
    "TerminalOutcome",
    "TerminalRejectReason",
    "TerminalSubmissionResult",
    "admit_verified_recurrence",
    "boundary_inputs_from_identity",
    "evaluate_request_eligibility",
    "record_human_escalation",
    "route_allowlisted_effect",
    "submit_occurrence_bound_repair_request",
    "submit_terminal_verification",
    "translate_occurrence_identity",
]
