"""Focused Maintenance contract tests (M2, T4).

These tests exercise the SHARED codec behavior of the T1 foundation and the
T2/T3 contracts through the single canonical serializer / strict decoder
(``canonical_dumps`` / ``canonical_digest`` / ``strict_loads``).  They are
deliberately centered on the shared codec so that a second, divergent
serialization implementation is detected: every round trip must use the
exported codec and produce byte-stable canonical JSON and digests.

Coverage matrix (per the T4 task):

* canonical round trips for identities, owner references, time/window
  primitives, the ObservationEnvelope, and every Maintenance event payload;
* missing and unknown fields fail strict decode (except inside ``Extensions``);
* invalid and cross-environment identities are rejected or reported exactly;
* UTC ordering, half-open ``[start, end)`` window boundaries, and the closed
  lateness boundary ``event_time <= watermark``;
* frozen SD1 evidence precedence and precedence-ordered references;
* occurrence-scoped recurrence (SD2) with fresh occurrence/event identity;
* fail-closed rejection of terminal / green / dispatchable claims from
  incomplete, stale, cross-environment, or incoherent envelopes — at
  construction AND at strict decode.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from arnold_pipelines.megaplan.incident.schema import (
    LEGACY_OCCURRENCE_ONLY_KINDS,
    OPERATIONAL_KEY_COORDINATES,
    is_operational_lifecycle_row,
    legacy_occurrence_idempotency_key,
    lifecycle_idempotency_key,
    operational_action_key,
    operational_event_action_key,
)
from arnold_pipelines.megaplan.maintenance.contracts import (
    CompletenessState,
    CoherenceReason,
    CoherenceState,
    EVIDENCE_PRECEDENCE,
    EVIDENCE_PRECEDENCE_VERSION,
    FreshnessState,
    ObservationEnvelope,
    SourceVersionVector,
    eligibility_supported,
    precedence_rank,
)
from arnold_pipelines.megaplan.maintenance.events import (
    AuditFinding,
    AuditReport,
    CheckpointVerificationPayload,
    CheckpointWindowKind,
    ClassifierInfo,
    DetectionEvent,
    EfficiencyAnalysis,
    EscalationReference,
    EventKind,
    HumanEscalationPayload,
    InstallationPayload,
    MaintenanceEvent,
    OccurrenceBudget,
    OperationalActionKind,
    OperationalEvent,
    OperationalPayload,
    ProgressObservationPayload,
    ProjectionCoordinates,
    RecurrenceLink,
    RecurrencePayload,
    RepairRequestPayload,
    RetriggerPayload,
    RootCauseCluster,
    SourceChangePayload,
    TerminalVerificationPayload,
    VerifierProvenance,
    event_digest,
    occurrence_idempotency_key,
    verified_recurrence,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_ENVIRONMENTS,
    MAINTENANCE_SCHEMA_VERSION,
    AttemptId,
    ChainId,
    CorrectionLink,
    EnvironmentId,
    EventWindow,
    Extensions,
    IdentityComparison,
    IdentityMismatchError,
    InvalidTimeError,
    Lateness,
    MaintenanceCodecError,
    ModelId,
    OwnerRef,
    PlanId,
    ProfileId,
    RunId,
    StageId,
    TenantId,
    UtcTime,
    Watermark,
    canonical_digest,
    canonical_dumps,
    canonical_json,
    classify_lateness,
    compare_identities,
    require_identical,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.operations import (
    ActionTarget,
    LeaseCoordinates,
    OccurrenceCoordinates,
    PolicyVersionCoordinates,
    ProducerPrincipal,
    ProducerRole,
    RecurrenceReference,
    RunAuthorityCoordinates,
    WbcAttemptCoordinates,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc


def _ts(
    year: int = 2026,
    month: int = 8,
    day: int = 1,
    hour: int = 12,
    minute: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _env(value: str = "production") -> EnvironmentId:
    return EnvironmentId(value)


def _ref(owner: str = "run_authority", locator: str = "grant://g-1") -> OwnerRef:
    digest = "a" * 64
    return OwnerRef(owner=owner, locator=locator, digest=digest, cursor="journal:7")


def _vector(
    owner: str = "run_authority",
    source: str = "run_authority.view",
    before: str = "b" * 64,
    after: str = "b" * 64,
    environment: EnvironmentId | None = None,
) -> SourceVersionVector:
    return SourceVersionVector(
        owner=owner,
        source=source,
        environment=environment,
        before=before,
        after=after,
    )


def _classifier() -> ClassifierInfo:
    return ClassifierInfo(classifier_version="v1.0", confidence=0.95, impact="high")


def _cluster() -> RootCauseCluster:
    return RootCauseCluster(signature="sig-1", cluster_id="cluster-1")


def _budget() -> OccurrenceBudget:
    return OccurrenceBudget(max_attempts=3, attempts_used=1)


def _detection(**overrides: object) -> DetectionEvent:
    fields: dict[str, object] = {
        "detection_kind": "watchdog",
        "subject": "chain:session",
        "severity": "critical",
        "description": "stall",
    }
    fields.update(overrides)
    return DetectionEvent(**fields)  # type: ignore[arg-type]


def _efficiency() -> EfficiencyAnalysis:
    return EfficiencyAnalysis(
        product="operational_custody",
        coverage_denominator=10,
        covered_count=7,
        censored_duration_seconds=120.0,
        bucket_counts={"recovered": 5, "stale": 2},
    )


def _audit() -> AuditReport:
    return AuditReport(
        report_type="six_hour",
        verdict="attention",
        summary="findings below",
        findings=(
            AuditFinding(finding_id="f-1", severity="high", message="parser loss"),
        ),
    )


def _window() -> EventWindow:
    return EventWindow(start=UtcTime(_ts(hour=10)), end=UtcTime(_ts(hour=11)))


def _watermark() -> Watermark:
    return Watermark(_ts(hour=10, minute=30))


def _event(
    payload: object | None = None,
    *,
    event_id: str = "evt-1",
    occurrence_id: str = "occ-1",
    event_time: datetime | None = None,
    window: EventWindow | None = None,
    watermark: Watermark | None = None,
    environment: EnvironmentId | str | None = "production",
    **overrides: object,
) -> MaintenanceEvent:
    return MaintenanceEvent.build(
        event_id=event_id,
        occurrence_id=occurrence_id,
        observed_at=_ts(hour=12),
        event_time=event_time or _ts(hour=10, minute=15),
        window=window or _window(),
        watermark=watermark or _watermark(),
        classifier=_classifier(),
        cluster=_cluster(),
        budget=_budget(),
        payload=payload if payload is not None else _detection(),
        environment=environment,
        run=RunId("run-1"),
        chain=ChainId("chain-1"),
        **overrides,  # type: ignore[arg-type]
    )


def _coherent_envelope() -> ObservationEnvelope:
    return ObservationEnvelope.build(
        observed_at=_ts(hour=12),
        environment="production",
        run="run-1",
        chain="chain-1",
        version_vectors=[_vector()],
        references=[_ref()],
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.COHERENT,
    )


# ---------------------------------------------------------------------------
# Canonical round trips through the shared codec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "identity",
    [
        EnvironmentId("production"),
        EnvironmentId("staging"),
        TenantId("tenant-1"),
        RunId("run-1"),
        ChainId("chain-1"),
        PlanId("plan-1"),
        StageId("stage-1"),
        ModelId("model-1"),
        ProfileId("profile-1"),
        AttemptId("attempt-1"),
    ],
)
def test_identity_round_trip(identity: object) -> None:
    dumped = canonical_dumps(identity)  # type: ignore[arg-type]
    assert dumped == json.dumps(identity.root, separators=(",", ":"))  # type: ignore[attr-defined]
    # Identities are RootModels rooted at a JSON scalar, so strict decode
    # round-trips through the same canonical JSON value.
    decoded = type(identity).model_validate(json.loads(dumped))  # type: ignore[arg-type]
    assert decoded == identity


def test_owner_ref_round_trip_preserves_explicit_null_fields() -> None:
    ref = OwnerRef(owner="wbc", locator="ledger://a", digest=None, cursor=None)
    dumped = canonical_dumps(ref)
    assert '"digest":null' in dumped
    assert '"cursor":null' in dumped
    decoded = strict_loads(OwnerRef, dumped)
    assert decoded == ref
    assert decoded.digest is None and decoded.cursor is None


def test_envelope_canonical_round_trip_and_stable_digest() -> None:
    envelope = _coherent_envelope()
    dumped = canonical_dumps(envelope)
    decoded = strict_loads(ObservationEnvelope, dumped)
    assert decoded == envelope
    assert canonical_digest(decoded) == canonical_digest(envelope)


def test_envelope_round_trip_normalizes_references_to_sd1_order() -> None:
    low = _ref(owner="status_projection", locator="status://s")
    high = _ref(owner="run_authority", locator="grant://g")
    envelope = ObservationEnvelope.build(
        observed_at=_ts(hour=12),
        references=[low, high],
        version_vectors=[_vector()],
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.COHERENT,
    )
    assert [ref.locator for ref in envelope.references] == ["grant://g", "status://s"]


@pytest.mark.parametrize(
    "payload,kind",
    [
        (_detection(), EventKind.DETECTION),
        (_efficiency(), EventKind.EFFICIENCY_ANALYSIS),
        (_audit(), EventKind.AUDIT_REPORT),
    ],
)
def test_maintenance_event_round_trip_for_every_payload(
    payload: object, kind: EventKind
) -> None:
    event = _event(payload)  # type: ignore[arg-type]
    dumped = canonical_dumps(event)
    decoded = strict_loads(MaintenanceEvent, dumped)
    assert decoded == event
    assert decoded.event_kind is kind
    assert decoded.payload.kind == kind.value


def test_codec_detects_duplicate_serialization_implementations() -> None:
    """A non-canonical encoder must produce a different digest.

    This pins the shared codec contract: any second serializer that does not
    sort keys, uses different separators, or omits null fields would produce
    a different canonical payload and a different digest.
    """
    envelope = _coherent_envelope()
    canonical = canonical_json(
        envelope.model_dump(mode="json", by_alias=True, exclude_none=False)
    )
    # A naive encoder that drops nulls and keeps insertion order must differ.
    naive = json.dumps(
        envelope.model_dump(mode="json", exclude_none=True),
        separators=(",", ":"),
        sort_keys=False,
    )
    assert naive != canonical
    assert canonical_dumps(envelope) == canonical


def test_canonical_json_is_deterministic_and_rejects_nan() -> None:
    assert canonical_json({"b": 1, "a": [2, 1]}) == '{"a":[2,1],"b":1}'
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


# ---------------------------------------------------------------------------
# Missing and unknown fields
# ---------------------------------------------------------------------------


def test_strict_decode_rejects_missing_required_fields() -> None:
    with pytest.raises(MaintenanceCodecError) as excinfo:
        strict_loads(ObservationEnvelope, {"observed_at": _ts(hour=12).isoformat()})
    types = {error["type"] for error in excinfo.value.errors}
    assert "missing" in types
    assert any("completeness" in tuple(error["loc"]) for error in excinfo.value.errors)


def test_strict_decode_rejects_unknown_fields() -> None:
    envelope = _coherent_envelope()
    data = json.loads(canonical_dumps(envelope))
    data["bogus_field"] = True
    with pytest.raises(MaintenanceCodecError) as excinfo:
        strict_loads(ObservationEnvelope, json.dumps(data))
    assert any(error["type"] == "extra_forbidden" for error in excinfo.value.errors)


def test_strict_decode_rejects_unknown_fields_on_events() -> None:
    event = _event()
    data = json.loads(canonical_dumps(event))
    data["surprise"] = 1
    with pytest.raises(MaintenanceCodecError):
        strict_loads(MaintenanceEvent, json.dumps(data))


def test_unknown_fields_allowed_inside_extensions_only() -> None:
    event = _event(extensions=Extensions({"custom": {"anything": [1, 2, None]}}))
    dumped = canonical_dumps(event)
    assert '"extensions"' in dumped
    decoded = strict_loads(MaintenanceEvent, dumped)
    assert decoded.extensions is not None
    assert decoded.extensions.root == {"custom": {"anything": [1, 2, None]}}
    # Unknown fields OUTSIDE the extension map still fail.
    data = json.loads(dumped)
    data["another"] = "x"
    with pytest.raises(MaintenanceCodecError):
        strict_loads(MaintenanceEvent, json.dumps(data))


def test_strict_decode_rejects_non_object_input() -> None:
    with pytest.raises(MaintenanceCodecError, match="JSON object"):
        strict_loads(EnvironmentId, "[1, 2]")
    with pytest.raises(MaintenanceCodecError, match="invalid JSON"):
        strict_loads(EnvironmentId, "{not json")


def test_strict_decode_rejects_unsupported_schema_version() -> None:
    event = _event()
    data = json.loads(canonical_dumps(event))
    data["schema_version"] = MAINTENANCE_SCHEMA_VERSION + 1
    with pytest.raises(MaintenanceCodecError, match="schema version"):
        strict_loads(MaintenanceEvent, json.dumps(data))


# ---------------------------------------------------------------------------
# Invalid and cross-environment identities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["", "prod", "Production", "production\n", "x" * 257, "bad\u0000env"],
)
def test_invalid_environment_identities_rejected(value: str) -> None:
    with pytest.raises((ValueError, ValidationError)):
        EnvironmentId(value)


@pytest.mark.parametrize("cls", [TenantId, RunId, ChainId, PlanId, StageId, ModelId, ProfileId, AttemptId])
def test_invalid_generic_identities_rejected(cls: type) -> None:
    with pytest.raises(ValueError):
        cls("")  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        cls("has\u0007control")  # type: ignore[call-arg]


def test_identities_are_exact_match_never_normalized() -> None:
    assert EnvironmentId("production") == EnvironmentId("production")
    assert EnvironmentId("production") != EnvironmentId("staging")
    assert compare_identities(RunId("r"), RunId("r")) is IdentityComparison.MATCH
    assert compare_identities(RunId("r"), RunId("s")) is IdentityComparison.VALUE_MISMATCH
    assert compare_identities(RunId("r"), ChainId("r")) is IdentityComparison.KIND_MISMATCH


def test_require_identical_raises_typed_mismatch() -> None:
    with pytest.raises(IdentityMismatchError, match="value_mismatch"):
        require_identical(RunId("a"), RunId("b"), context="run")
    with pytest.raises(IdentityMismatchError, match="kind_mismatch"):
        require_identical(RunId("a"), PlanId("a"), context="identity")
    require_identical(RunId("a"), RunId("a"), context="run")


def test_cross_environment_detection_is_explicit() -> None:
    vector_prod = _vector(environment=EnvironmentId("production"))
    vector_stage = _vector(environment=EnvironmentId("staging"))
    envelope = ObservationEnvelope.build(
        observed_at=_ts(hour=12),
        environment="production",
        version_vectors=[vector_prod, vector_stage],
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.INCOHERENT,
        coherence_reasons=[CoherenceReason.CROSS_ENVIRONMENT],
    )
    assert envelope.cross_environment is True
    # A coherent envelope cannot mix environments.
    with pytest.raises(ValidationError, match="cross-environment"):
        ObservationEnvelope.build(
            observed_at=_ts(hour=12),
            environment="production",
            version_vectors=[vector_prod, vector_stage],
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.COHERENT,
        )


# ---------------------------------------------------------------------------
# UTC ordering and half-open boundaries
# ---------------------------------------------------------------------------


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises((ValueError, ValidationError, InvalidTimeError)):
        UtcTime(datetime(2026, 8, 1, 12))
    with pytest.raises((ValueError, ValidationError)):
        ObservationEnvelope.build(
            observed_at=datetime(2026, 8, 1, 12),
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.COHERENT,
        )


def test_utc_normalization_and_ordering() -> None:
    utc_value = UtcTime(datetime(2026, 8, 1, 12, tzinfo=timezone.utc))
    offset_value = UtcTime(datetime(2026, 8, 1, 7, tzinfo=timezone(timedelta(hours=-5))))
    assert utc_value.root == offset_value.root
    assert offset_value.root.tzinfo == timezone.utc


def test_half_open_window_boundaries() -> None:
    start = _ts(hour=10)
    end = _ts(hour=11)
    window = EventWindow(start=UtcTime(start), end=UtcTime(end))
    assert window.contains(_ts(hour=10))  # start inclusive
    assert window.contains(_ts(hour=10, minute=59))
    assert not window.contains(_ts(hour=11))  # end exclusive
    assert not window.contains(_ts(hour=9, minute=59))


def test_degenerate_window_is_rejected() -> None:
    with pytest.raises(ValidationError, match="half-open"):
        EventWindow(start=UtcTime(_ts(hour=11)), end=UtcTime(_ts(hour=10)))
    with pytest.raises(ValidationError, match="half-open"):
        EventWindow(start=UtcTime(_ts(hour=10)), end=UtcTime(_ts(hour=10)))


def test_lateness_closed_boundary_at_watermark() -> None:
    watermark = _watermark()  # 10:30
    assert classify_lateness(_ts(hour=10, minute=30), watermark) is Lateness.LATE
    assert classify_lateness(_ts(hour=10, minute=29), watermark) is Lateness.LATE
    assert classify_lateness(_ts(hour=10, minute=31), watermark) is Lateness.ON_TIME
    # A derived event carries the exact classification.
    event = _event(event_time=_ts(hour=10, minute=31))
    assert event.lateness is Lateness.ON_TIME
    late_event = _event(event_time=_ts(hour=10, minute=15))
    assert late_event.lateness is Lateness.LATE


def test_correction_link_is_append_only_reference() -> None:
    link = CorrectionLink(corrected_event_id="occ-original", reason="late evidence")
    assert link.corrected_event_id == "occ-original"
    with pytest.raises(ValidationError):
        CorrectionLink(corrected_event_id="", reason="x")


# ---------------------------------------------------------------------------
# SD1 evidence precedence
# ---------------------------------------------------------------------------


def test_precedence_table_is_frozen_sd1() -> None:
    assert EVIDENCE_PRECEDENCE_VERSION == "SD1"
    ranks = [precedence_rank(owner) for owner, *_ in []]  # type: ignore[arg-type]
    # Exact tier order from the frozen decision.
    expected = [
        ("run_authority", 1),
        ("wbc", 2),
        ("maintenance", 3),
        ("plan", 4),
        ("chain", 5),
        ("repair_custody", 5),
        ("snapshot", 6),
        ("heartbeat", 6),
        ("status_projection", 7),
    ]
    for owner, rank in expected:
        assert precedence_rank(owner) == rank, owner
    # Non-SD1 owner kinds are never ranked.
    for owner in ("custody", "conformance", "native_manifest", "unknown"):
        assert precedence_rank(owner) is None


def test_envelope_rejects_non_sd1_reference_kinds() -> None:
    with pytest.raises(ValidationError, match="precedence"):
        ObservationEnvelope.build(
            observed_at=_ts(hour=12),
            references=[_ref(owner="custody", locator="lease://l-1")],
            version_vectors=[_vector()],
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.COHERENT,
        )


# ---------------------------------------------------------------------------
# Occurrence recurrence (SD2)
# ---------------------------------------------------------------------------


def test_idempotency_key_is_occurrence_identity() -> None:
    event = _event(occurrence_id="occ-7")
    assert occurrence_idempotency_key(event) == "occ-7"
    assert event.idempotency_key == "occ-7"


def test_verified_recurrence_creates_fresh_linked_occurrence() -> None:
    predecessor = _event(
        event_id="evt-1",
        occurrence_id="occ-1",
        payload=_detection(detection_kind="watchdog"),
    )
    recurrence = verified_recurrence(
        predecessor=predecessor,
        new_event_id="evt-2",
        new_occurrence_id="occ-2",
        observed_at=_ts(hour=13),
        event_time=_ts(hour=12, minute=45),
        window=EventWindow(start=UtcTime(_ts(hour=12)), end=UtcTime(_ts(hour=13))),
        watermark=Watermark(_ts(hour=12, minute=30)),
        budget=OccurrenceBudget(max_attempts=3, attempts_used=0),
        payload=_detection(detection_kind="watchdog"),
    )
    assert recurrence.occurrence_id == "occ-2"
    assert recurrence.event_id == "evt-2"
    assert recurrence.recurrence is not None
    assert recurrence.recurrence.verified is True
    assert recurrence.recurrence.predecessor_occurrence_id == "occ-1"
    assert recurrence.recurrence.predecessor_event_id == "evt-1"
    # Signature/cluster grouping is preserved (analytical grouping only).
    assert recurrence.cluster == predecessor.cluster
    # Fresh occurrence scope carries its own budget.
    assert recurrence.budget.max_attempts == 3 and recurrence.budget.attempts_used == 0
    # Round trip through the shared codec preserves the causal link.
    decoded = strict_loads(MaintenanceEvent, canonical_dumps(recurrence))
    assert decoded.recurrence == recurrence.recurrence


def test_recurrence_requires_fresh_occurrence_and_event() -> None:
    predecessor = _event(event_id="evt-1", occurrence_id="occ-1")
    with pytest.raises(ValueError, match="fresh occurrence"):
        verified_recurrence(
            predecessor=predecessor,
            new_event_id="evt-2",
            new_occurrence_id="occ-1",  # same occurrence -> rejected
            observed_at=_ts(hour=13),
            event_time=_ts(hour=12, minute=45),
            window=_window(),
            watermark=_watermark(),
            budget=_budget(),
            payload=_detection(),
        )
    with pytest.raises(ValueError, match="fresh event"):
        verified_recurrence(
            predecessor=predecessor,
            new_event_id="evt-1",  # same event -> rejected
            new_occurrence_id="occ-2",
            observed_at=_ts(hour=13),
            event_time=_ts(hour=12, minute=45),
            window=_window(),
            watermark=_watermark(),
            budget=_budget(),
            payload=_detection(),
        )


def test_recurrence_link_must_be_verified_and_distinct() -> None:
    with pytest.raises(ValidationError, match="unverified recurrence"):
        _event(
            recurrence=RecurrenceLink(
                verified=False,
                predecessor_event_id="evt-0",
                predecessor_occurrence_id="occ-0",
            )
        )
    with pytest.raises(ValidationError, match="fresh occurrence"):
        _event(
            recurrence=RecurrenceLink(
                verified=True,
                predecessor_event_id="evt-0",
                predecessor_occurrence_id="occ-1",  # equals enclosing occurrence
            )
        )


def test_payload_kind_must_match_envelope_kind() -> None:
    with pytest.raises(ValidationError, match="does not match payload"):
        MaintenanceEvent(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            event_id="evt-1",
            occurrence_id="occ-1",
            event_kind=EventKind.DETECTION,
            observed_at=UtcTime(_ts(hour=12)),
            event_time=UtcTime(_ts(hour=10, minute=15)),
            window=_window(),
            watermark=_watermark(),
            lateness=Lateness.LATE,
            classifier=_classifier(),
            cluster=_cluster(),
            budget=_budget(),
            payload=_efficiency(),
        )


def test_occurrence_budget_is_bounded() -> None:
    with pytest.raises(ValidationError):
        OccurrenceBudget(max_attempts=0)
    with pytest.raises(ValidationError, match="exhausted"):
        OccurrenceBudget(max_attempts=2, attempts_used=3)
    assert OccurrenceBudget(max_attempts=2, attempts_used=2).attempts_used == 2


def test_event_digest_is_canonical_and_stable() -> None:
    event = _event()
    assert event_digest(event) == canonical_digest(event)
    assert event_digest(strict_loads(MaintenanceEvent, canonical_dumps(event))) == event_digest(event)


# ---------------------------------------------------------------------------
# Fail-closed eligibility: terminal/green/dispatchable
# ---------------------------------------------------------------------------


def test_eligibility_supported_requires_every_positive_state() -> None:
    assert eligibility_supported(
        coherence=CoherenceState.COHERENT,
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        cross_environment=False,
    ) is True
    for coherence in (CoherenceState.INCOHERENT, CoherenceState.UNKNOWN):
        assert (
            eligibility_supported(
                coherence=coherence,
                completeness=CompletenessState.COMPLETE,
                freshness=FreshnessState.FRESH,
                cross_environment=False,
            )
            is False
        )
    for completeness in (CompletenessState.PARTIAL, CompletenessState.UNKNOWN):
        assert (
            eligibility_supported(
                coherence=CoherenceState.COHERENT,
                completeness=completeness,
                freshness=FreshnessState.FRESH,
                cross_environment=False,
            )
            is False
        )
    for freshness in (FreshnessState.STALE, FreshnessState.UNKNOWN):
        assert (
            eligibility_supported(
                coherence=CoherenceState.COHERENT,
                completeness=CompletenessState.COMPLETE,
                freshness=freshness,
                cross_environment=False,
            )
            is False
        )
    assert (
        eligibility_supported(
            coherence=CoherenceState.COHERENT,
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            cross_environment=True,
        )
        is False
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(coherence=CoherenceState.INCOHERENT, coherence_reasons=[CoherenceReason.VERSION_TEAR]),
        dict(coherence=CoherenceState.UNKNOWN, coherence_reasons=[CoherenceReason.UNKNOWN]),
        dict(completeness=CompletenessState.PARTIAL),
        dict(freshness=FreshnessState.STALE),
    ],
)
def test_build_never_derives_eligibility_from_non_coherent_states(kwargs: dict) -> None:
    base = dict(
        observed_at=_ts(hour=12),
        environment="production",
        version_vectors=[_vector()],
        completeness=CompletenessState.COMPLETE,
        freshness=FreshnessState.FRESH,
        coherence=CoherenceState.COHERENT,
    )
    base.update(kwargs)
    envelope = ObservationEnvelope.build(**base)  # type: ignore[arg-type]
    assert envelope.terminal is False
    assert envelope.green is False
    assert envelope.dispatchable is False


def test_build_derives_eligibility_only_for_coherent_complete_fresh() -> None:
    envelope = _coherent_envelope()
    assert envelope.terminal is True
    assert envelope.green is True
    assert envelope.dispatchable is True


def test_direct_construction_rejects_overclaimed_eligibility() -> None:
    with pytest.raises(ValidationError, match="fail-closed eligibility"):
        ObservationEnvelope(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            observed_at=UtcTime(_ts(hour=12)),
            environment=EnvironmentId("production"),
            version_vectors=(_vector(),),
            references=(_ref(),),
            completeness=CompletenessState.PARTIAL,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.COHERENT,
            terminal=True,
            green=True,
            dispatchable=True,
        )


def test_strict_decode_rejects_overclaimed_eligibility() -> None:
    envelope = _coherent_envelope()
    data = json.loads(canonical_dumps(envelope))
    data["completeness"] = CompletenessState.PARTIAL.value
    data["terminal"] = True
    data["green"] = True
    data["dispatchable"] = True
    with pytest.raises(MaintenanceCodecError, match="fail-closed"):
        strict_loads(ObservationEnvelope, json.dumps(data))


def test_incoherent_envelope_requires_reasons_and_coherent_forbids_them() -> None:
    with pytest.raises(ValidationError, match="requires at least one"):
        ObservationEnvelope.build(
            observed_at=_ts(hour=12),
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.INCOHERENT,
        )
    with pytest.raises(ValidationError, match="must not carry coherence reasons"):
        ObservationEnvelope.build(
            observed_at=_ts(hour=12),
            completeness=CompletenessState.COMPLETE,
            freshness=FreshnessState.FRESH,
            coherence=CoherenceState.COHERENT,
            coherence_reasons=[CoherenceReason.VERSION_TEAR],
        )


def test_unknown_states_never_promoted() -> None:
    envelope = ObservationEnvelope.build(
        observed_at=_ts(hour=12),
        environment=None,
        completeness=CompletenessState.UNKNOWN,
        freshness=FreshnessState.UNKNOWN,
        coherence=CoherenceState.UNKNOWN,
        coherence_reasons=[CoherenceReason.UNKNOWN],
    )
    assert envelope.terminal is False
    assert envelope.green is False
    assert envelope.dispatchable is False
    # Explicit null environment is preserved on the wire (never guessed).
    assert '"environment":null' in canonical_dumps(envelope)


# ---------------------------------------------------------------------------
# T3: lifecycle action idempotency keys (incident schema boundary)
# ---------------------------------------------------------------------------


def _operational_payload(
    action: OperationalActionKind,
    *,
    event_id: str,
) -> OperationalPayload:
    """Build the closed discriminated payload for *action*."""
    if action is OperationalActionKind.REPAIR_REQUEST:
        return RepairRequestPayload(request_id=f"req-{event_id}")
    if action is OperationalActionKind.SOURCE_CHANGE:
        return SourceChangePayload()
    if action is OperationalActionKind.INSTALLATION:
        return InstallationPayload()
    if action is OperationalActionKind.RETRIGGER:
        return RetriggerPayload()
    if action is OperationalActionKind.PROGRESS_OBSERVATION:
        return ProgressObservationPayload()
    if action is OperationalActionKind.CHECKPOINT_VERIFICATION:
        return CheckpointVerificationPayload(checkpoint=CheckpointWindowKind.IMMEDIATE)
    if action is OperationalActionKind.TERMINAL_VERIFICATION:
        return TerminalVerificationPayload(
            verifier=VerifierProvenance(
                principal="verifier-1",
                runtime_digest="a" * 64,
                source_digest="b" * 64,
                observed_at=UtcTime(_ts(hour=12)),
            ),
            terminal_reason="original blocker absent",
        )
    if action is OperationalActionKind.RECURRENCE:
        return RecurrencePayload(
            recurrence=RecurrenceReference(
                predecessor_occurrence_id="occ-0",
                predecessor_event_id="evt-0",
            )
        )
    if action is OperationalActionKind.HUMAN_ESCALATION:
        return HumanEscalationPayload(
            escalation=EscalationReference(
                reason="ambiguous blocker",
                escalation_owner="human-owner-1",
            )
        )
    raise AssertionError(f"unhandled operational action {action}")


def _operational_event(
    *,
    event_id: str = "op-evt-1",
    action: OperationalActionKind = OperationalActionKind.REPAIR_REQUEST,
    occurrence_id: str = "occ-1",
    occurrence_digest: str = "d" * 64,
    policy_version: str = "policy-1",
    target: str = "chain:session",
    lease_id: str = "lease-1",
    custody_epoch: int = 1,
    run_id: str = "run-1",
    attempt_id: str | None = "att-1",
    payload: OperationalPayload | None = None,
) -> OperationalEvent:
    """Build one closed occurrence-bound operational lifecycle event."""
    role = (
        ProducerRole.VERIFIER
        if action is OperationalActionKind.TERMINAL_VERIFICATION
        else ProducerRole.REPAIR_PRODUCER
    )
    return OperationalEvent.build(
        event_id=event_id,
        occurrence=OccurrenceCoordinates(
            occurrence_id=occurrence_id,
            canonical_digest=occurrence_digest,
        ),
        lease=LeaseCoordinates(lease_id=lease_id, custody_epoch=custody_epoch),
        run_authority=RunAuthorityCoordinates(run_id=run_id, satisfied=True),
        policy=PolicyVersionCoordinates(policy_version=policy_version),
        target=ActionTarget(target=target),
        producer=ProducerPrincipal(principal=f"principal-{role.value}", role=role),
        payload=payload if payload is not None else _operational_payload(action, event_id=event_id),
        observed_at=_ts(hour=12),
        wbc_attempt=(
            WbcAttemptCoordinates(attempt_id=attempt_id) if attempt_id is not None else None
        ),
    )


def test_operational_action_key_distinct_for_every_lifecycle_action() -> None:
    keys = {
        action: operational_event_action_key(
            _operational_event(
                event_id=f"op-evt-{index}",
                action=action,
            )
        )
        for index, action in enumerate(OperationalActionKind)
    }
    # The closed lifecycle vocabulary never collapses into a generic success
    # receipt: all nine distinct actions for ONE occurrence derive distinct
    # keys, so request/source-change/installation/retrigger/progress/
    # verification records coexist while exact retries deduplicate.
    assert len(keys) == len(OperationalActionKind)
    assert len(set(keys.values())) == len(OperationalActionKind)


def test_operational_action_key_exact_retry_reproduces_same_key() -> None:
    first = _operational_event()
    second = _operational_event()  # exact retry: identical coordinates
    assert operational_event_action_key(first) == operational_event_action_key(second)
    assert (
        lifecycle_idempotency_key(first.model_dump(mode="json"))
        == lifecycle_idempotency_key(second.model_dump(mode="json"))
    )


def test_operational_action_key_changes_with_every_coordinate() -> None:
    base = operational_action_key(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        occurrence_digest="d" * 64,
        action_kind="repair_request",
        policy_version="policy-1",
        target="chain:session",
    )
    variants = [
        dict(action_kind="source_change"),
        dict(policy_version="policy-2"),
        dict(target="chain:other"),
        dict(occurrence_digest="e" * 64),
    ]
    base_kwargs: dict[str, object] = dict(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        occurrence_digest="d" * 64,
        action_kind="repair_request",
        policy_version="policy-1",
        target="chain:session",
    )
    for variant in variants:
        kwargs = dict(base_kwargs)
        kwargs.update(variant)
        changed = operational_action_key(**kwargs)  # type: ignore[arg-type]
        assert changed != base
    # The exact retry reproduces the base key; coordinate ORDER is frozen by
    # the OPERATIONAL_KEY_COORDINATES contract.
    assert operational_action_key(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        occurrence_digest="d" * 64,
        action_kind="repair_request",
        policy_version="policy-1",
        target="chain:session",
    ) == base
    assert OPERATIONAL_KEY_COORDINATES == (
        "schema_version",
        "occurrence_digest",
        "action_kind",
        "policy_version",
        "target",
    )


def test_operational_action_key_fails_closed_on_malformed_coordinates() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        operational_action_key(
            schema_version=2,
            occurrence_digest="d" * 64,
            action_kind="repair_request",
            policy_version="policy-1",
            target="chain:session",
        )
    with pytest.raises(ValueError, match="sha256"):
        operational_action_key(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            occurrence_digest="not-a-digest",
            action_kind="repair_request",
            policy_version="policy-1",
            target="chain:session",
        )
    with pytest.raises(ValueError, match="action kind"):
        operational_action_key(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            occurrence_digest="d" * 64,
            action_kind="",
            policy_version="policy-1",
            target="chain:session",
        )
    with pytest.raises(ValueError, match="policy version"):
        operational_action_key(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            occurrence_digest="d" * 64,
            action_kind="repair_request",
            policy_version="",
            target="chain:session",
        )
    with pytest.raises(ValueError, match="target identity"):
        operational_action_key(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            occurrence_digest="d" * 64,
            action_kind="repair_request",
            policy_version="policy-1",
            target="",
        )


def test_strict_codec_keeps_separate_lifecycle_records_distinct() -> None:
    # Distinct lifecycle actions for ONE occurrence survive the strict codec
    # as distinct records with distinct canonical dumps, digests, and keys.
    records = [
        _operational_event(event_id=f"op-evt-{index}", action=action)
        for index, action in enumerate(OperationalActionKind)
    ]
    decoded = [
        strict_loads(OperationalEvent, canonical_dumps(record)) for record in records
    ]
    assert len({canonical_dumps(record) for record in decoded}) == len(records)
    assert len({canonical_digest(record) for record in decoded}) == len(records)
    assert (
        len({operational_event_action_key(record) for record in decoded}) == len(records)
    )
    # Every record round-trips byte-stably through the single canonical codec.
    for record in decoded:
        assert (
            canonical_dumps(strict_loads(OperationalEvent, canonical_dumps(record)))
            == canonical_dumps(record)
        )


def test_lifecycle_idempotency_key_discriminates_legacy_and_operational() -> None:
    # Legacy detection rows keep the occurrence-only key (M2 compatibility).
    legacy = _event(occurrence_id="occ-legacy").model_dump(mode="json")
    assert is_operational_lifecycle_row(legacy) is False
    assert legacy_occurrence_idempotency_key(legacy) == "occ-legacy"
    assert lifecycle_idempotency_key(legacy) == "occ-legacy"

    # Operational rows derive the strict action key from the five coordinates.
    operational = _operational_event().model_dump(mode="json")
    assert is_operational_lifecycle_row(operational) is True
    assert lifecycle_idempotency_key(operational) == operational_event_action_key(
        _operational_event()
    )
    # The legacy occurrence-only kinds are exactly the closed M2 vocabulary.
    assert LEGACY_OCCURRENCE_ONLY_KINDS == frozenset(
        {"detection", "efficiency_analysis", "audit_report"}
    )


def test_operational_action_key_rejects_truncated_operational_rows() -> None:
    operational = _operational_event().model_dump(mode="json")
    del operational["target"]
    with pytest.raises(ValueError, match="target"):
        lifecycle_idempotency_key(operational)
    bad_digest = _operational_event().model_dump(mode="json")
    bad_digest["occurrence"]["canonical_digest"] = "short"
    with pytest.raises(ValueError, match="sha256"):
        lifecycle_idempotency_key(bad_digest)


# ---------------------------------------------------------------------------
# T16 (Plan Step 15): the frozen M4-facing API surface
# ---------------------------------------------------------------------------
# The package exports the stable owner-source join, occurrence-bound request
# reference, checkpoint scheduler, recurrence, and verification APIs M4 will
# consume, plus the M3 handoff view.  These assertions pin that surface: the
# exported names resolve, are the SAME objects as their source-module
# definitions (no shadowing/duplication), never include an owner authority
# substrate, and round-trip through the single canonical strict codec.


def test_m4_api_surface_is_frozen_and_resolvable() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    api = maintenance_pkg.M4_API
    assert isinstance(api, tuple) and api
    missing = [name for name in api if not hasattr(maintenance_pkg, name)]
    assert missing == [], f"M4_API names missing from the package: {missing}"
    # Every required category of the M4 handoff is present.
    names = set(api)
    for required in (
        # owner-source join (T6)
        "ObservationEnvelope",
        "capture_observation",
        "JoinSource",
        "read_custody",
        # occurrence-bound request reference (T2/T3/T10)
        "OperationalEvent",
        "RepairRequestPayload",
        "OccurrenceCoordinates",
        "LeaseCoordinates",
        # checkpoint scheduler (T7)
        "due_checkpoints",
        "CheckpointDueItem",
        "CANONICAL_CHECKPOINT_ORDER",
        # recurrence / escalation (T13)
        "verified_recurrence",
        "RecurrenceLink",
        "RecurrenceReference",
        "EscalationReference",
        # independent verification (T8)
        "evaluate_verification",
        "VerificationResult",
        "NegativeControlResult",
        # M4 handoff view (T1): accepted vector + drift, never guessed
        "MaintenanceHandoffView",
        "build_handoff_view",
        "verify_frozen_digests",
        "verify_handoff_drift",
    ):
        assert required in names, required


def test_m4_api_exports_are_the_same_objects_as_their_source_modules() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg
    import arnold_pipelines.megaplan.maintenance.checkpoints as _checkpoints
    import arnold_pipelines.megaplan.maintenance.contracts as _contracts
    import arnold_pipelines.megaplan.maintenance.events as _events
    import arnold_pipelines.megaplan.maintenance.handoffs as _handoffs
    import arnold_pipelines.megaplan.maintenance.observation as _observation
    import arnold_pipelines.megaplan.maintenance.operations as _operations
    import arnold_pipelines.megaplan.maintenance.sources as _sources
    import arnold_pipelines.megaplan.maintenance.verification as _verification

    expected: dict[str, tuple[Any, str]] = {
        "ObservationEnvelope": (_contracts, "ObservationEnvelope"),
        "SourceVersionVector": (_contracts, "SourceVersionVector"),
        "OperationalEvent": (_events, "OperationalEvent"),
        "OperationalActionKind": (_events, "OperationalActionKind"),
        "RepairRequestPayload": (_events, "RepairRequestPayload"),
        "CheckpointWindowKind": (_events, "CheckpointWindowKind"),
        "SIX_HOUR_ALIAS": (_events, "SIX_HOUR_ALIAS"),
        "canonical_checkpoint_window": (_events, "canonical_checkpoint_window"),
        "verified_recurrence": (_events, "verified_recurrence"),
        "RecurrenceLink": (_events, "RecurrenceLink"),
        "OccurrenceCoordinates": (_operations, "OccurrenceCoordinates"),
        "LeaseCoordinates": (_operations, "LeaseCoordinates"),
        "RunAuthorityCoordinates": (_operations, "RunAuthorityCoordinates"),
        "WbcAttemptCoordinates": (_operations, "WbcAttemptCoordinates"),
        "PolicyVersionCoordinates": (_operations, "PolicyVersionCoordinates"),
        "ActionTarget": (_operations, "ActionTarget"),
        "ProducerPrincipal": (_operations, "ProducerPrincipal"),
        "OwnerReceipts": (_operations, "OwnerReceipts"),
        "RecurrenceReference": (_operations, "RecurrenceReference"),
        "EscalationReference": (_operations, "EscalationReference"),
        "CheckpointDueItem": (_checkpoints, "CheckpointDueItem"),
        "due_checkpoints": (_checkpoints, "due_checkpoints"),
        "checkpoint_window_bounds": (_checkpoints, "checkpoint_window_bounds"),
        "completed_checkpoint_windows": (_checkpoints, "completed_checkpoint_windows"),
        "CANONICAL_CHECKPOINT_ORDER": (_checkpoints, "CANONICAL_CHECKPOINT_ORDER"),
        "CHECKPOINT_WINDOW_DELTAS": (_checkpoints, "CHECKPOINT_WINDOW_DELTAS"),
        "VerificationResult": (_verification, "VerificationResult"),
        "VerificationOutcome": (_verification, "VerificationOutcome"),
        "VerificationRejectReason": (_verification, "VerificationRejectReason"),
        "NegativeControlResult": (_verification, "NegativeControlResult"),
        "ExpectedAuthority": (_verification, "ExpectedAuthority"),
        "evaluate_verification": (_verification, "evaluate_verification"),
        "required_checkpoint_set": (_verification, "required_checkpoint_set"),
        "checkpoint_set_complete": (_verification, "checkpoint_set_complete"),
        "MaintenanceHandoffView": (_handoffs, "MaintenanceHandoffView"),
        "build_handoff_view": (_handoffs, "build_handoff_view"),
        "default_handoff_registry": (_handoffs, "default_handoff_registry"),
        "verify_frozen_digests": (_handoffs, "verify_frozen_digests"),
        "verify_handoff_drift": (_handoffs, "verify_handoff_drift"),
        "HandoffRegistry": (_handoffs, "HandoffRegistry"),
        "HandoffResolution": (_handoffs, "HandoffResolution"),
        "HandoffResolutionState": (_handoffs, "HandoffResolutionState"),
        "capture_observation": (_observation, "capture_observation"),
        "JoinSource": (_observation, "JoinSource"),
        "read_custody": (_sources, "read_custody"),
        "read_run_authority": (_sources, "read_run_authority"),
        "read_wbc_attempt": (_sources, "read_wbc_attempt"),
        "CustodyRead": (_sources, "CustodyRead"),
        "RunAuthorityRead": (_sources, "RunAuthorityRead"),
        "WbcRead": (_sources, "WbcRead"),
    }
    for name, (module, attr) in expected.items():
        assert getattr(maintenance_pkg, name) is getattr(module, attr), name


def test_m4_api_never_exports_owner_authority_substrate() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    forbidden = (
        # lease stores
        "CustodyLeaseStore",
        "CapacityLease",
        "ExecutionLease",
        "LivenessLeasePublisher",
        # attempt stores
        "AttemptLedgerStore",
        "SqliteAttemptLedgerStore",
        # validators
        "ActionBoundaryResult",
        "RollbackValidator",
        "validate_action_boundary_simple",
        # effect ledger / repair queue / simple_fixer
        "RepairEffectLedger",
        "MutationReservation",
        "enqueue_occurrence_bound_repair_request",
        "delegate_to_simple_fixer",
        # completion engines
        "CompletionSubject",
        "ManagedCompletionTurnResult",
        # queues
        "ManagedAgentQueueSweepResult",
        "QueueSprintsInput",
        # lifecycle writers
        "TransitionWriter",
        "RuntimeTransitionWriter",
        "write_plan_state",
        "save_chain_state",
    )
    exported = set(maintenance_pkg.__all__) | set(dir(maintenance_pkg))
    hits = sorted(name for name in forbidden if name in exported)
    assert hits == [], f"M4 API exports owner authority substrate: {hits}"
    assert not (set(maintenance_pkg.M4_API) & set(forbidden))


def test_m4_request_reference_api_is_occurrence_bound_and_reference_only() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    m = maintenance_pkg
    event = m.OperationalEvent.build(
        event_id="m4-req-1",
        occurrence=m.OccurrenceCoordinates(
            occurrence_id="occ-1", canonical_digest="d" * 64
        ),
        lease=m.LeaseCoordinates(lease_id="lease-1", custody_epoch=1),
        run_authority=m.RunAuthorityCoordinates(run_id="run-1", satisfied=True),
        policy=m.PolicyVersionCoordinates(policy_version="policy-1"),
        target=m.ActionTarget(target="chain:session"),
        producer=m.ProducerPrincipal(
            principal="producer-1", role=m.ProducerRole.REPAIR_PRODUCER
        ),
        payload=m.RepairRequestPayload(request_id="req-1"),
        observed_at=_ts(hour=12),
        wbc_attempt=m.WbcAttemptCoordinates(attempt_id="att-1"),
    )
    decoded = strict_loads(m.OperationalEvent, canonical_dumps(event))
    assert decoded == event
    # M4 consumes the FIXED lifecycle encoding: the exported event derives the
    # same idempotency key as the frozen incident-schema codec.
    assert lifecycle_idempotency_key(decoded.model_dump(mode="json")) == (
        operational_event_action_key(event)
    )
    # Reference-only: the exported request reference never constructs an owner
    # authority record or a second queue/store.
    assert not hasattr(m, "CustodyLeaseStore")
    assert not hasattr(m, "enqueue_occurrence_bound_repair_request")


def test_m4_checkpoint_api_round_trips_through_strict_codec() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    m = maintenance_pkg
    due = m.due_checkpoints(
        anchor_at=_ts(hour=12),
        now=_ts(hour=12, minute=10),
        completed=[m.CheckpointWindowKind.IMMEDIATE],
        occurrence_id="occ-1",
        lease_id="lease-1",
        custody_epoch=1,
        fencing_token="fence-1",
    )
    # Half-open windows anchored to the durable effect receipt: with the
    # immediate window completed and ten minutes elapsed, five_minute is the
    # only due window (one_hour opens at 13:00).
    assert [item.window for item in due] == [m.CheckpointWindowKind.FIVE_MINUTE]
    decoded = [
        strict_loads(m.CheckpointDueItem, canonical_dumps(item)) for item in due
    ]
    assert decoded == list(due)
    # The schedule is canonical: next_three_hour is the unbounded horizon and
    # six_hour is only a read alias — never a separate window.
    assert tuple(m.CANONICAL_CHECKPOINT_ORDER) == (
        m.CheckpointWindowKind.IMMEDIATE,
        m.CheckpointWindowKind.FIVE_MINUTE,
        m.CheckpointWindowKind.ONE_HOUR,
        m.CheckpointWindowKind.NEXT_THREE_HOUR,
    )
    assert m.canonical_checkpoint_window("six_hour") is m.CheckpointWindowKind.NEXT_THREE_HOUR
    # The due item carries the inherited M7 lease/epoch/fence so the executor
    # must reacquire current authority before acting.
    for item in decoded:
        assert item.lease_id == "lease-1"
        assert item.custody_epoch == 1
        assert item.fencing_token == "fence-1"
    # Delayed catch-up returns every overdue window once, in event-time order,
    # with next_three_hour the unbounded horizon.
    late = m.due_checkpoints(
        anchor_at=_ts(hour=12),
        now=_ts(hour=16),
        completed=[m.CheckpointWindowKind.IMMEDIATE],
    )
    assert [item.window for item in late] == [
        m.CheckpointWindowKind.FIVE_MINUTE,
        m.CheckpointWindowKind.ONE_HOUR,
        m.CheckpointWindowKind.NEXT_THREE_HOUR,
    ]
    assert all(item.delayed for item in late[:-1])
    assert late[-1].close_at is None


def test_m4_verification_api_round_trips_and_fails_closed() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    m = maintenance_pkg
    unknown = m.VerificationResult(
        schema_version=m.MAINTENANCE_SCHEMA_VERSION,
        outcome=m.VerificationOutcome.UNKNOWN,
        reasons=(m.VerificationRejectReason.UNKNOWN_EVIDENCE,),
        terminal=False,
    )
    decoded = strict_loads(m.VerificationResult, canonical_dumps(unknown))
    assert decoded == unknown
    assert decoded.terminal is False
    # Only a VERIFIED outcome may be terminal; the strict codec round-trips it.
    verified = m.VerificationResult(
        schema_version=m.MAINTENANCE_SCHEMA_VERSION,
        outcome=m.VerificationOutcome.VERIFIED,
        reasons=(),
        terminal=True,
        verified_windows=tuple(m.required_checkpoint_set()),
    )
    assert strict_loads(m.VerificationResult, canonical_dumps(verified)) == verified
    # The required set is exactly the canonical schedule through the exported
    # API, and an incomplete set can never close custody.
    assert tuple(m.required_checkpoint_set()) == tuple(m.CANONICAL_CHECKPOINT_ORDER)
    assert m.checkpoint_set_complete(m.required_checkpoint_set()) is True
    assert m.checkpoint_set_complete([m.CheckpointWindowKind.IMMEDIATE]) is False


def test_m4_recurrence_api_requires_fresh_linked_occurrence() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    m = maintenance_pkg
    predecessor = _event(
        event_id="evt-1", occurrence_id="occ-1", payload=_detection()
    )
    with pytest.raises(ValueError, match="fresh occurrence"):
        m.verified_recurrence(
            predecessor=predecessor,
            new_event_id="evt-2",
            new_occurrence_id="occ-1",  # same occurrence -> rejected
            observed_at=_ts(hour=13),
            event_time=_ts(hour=12, minute=45),
            window=_window(),
            watermark=_watermark(),
            budget=_budget(),
            payload=_detection(),
        )
    recurrence = m.verified_recurrence(
        predecessor=predecessor,
        new_event_id="evt-2",
        new_occurrence_id="occ-2",
        observed_at=_ts(hour=13),
        event_time=_ts(hour=12, minute=45),
        window=_window(),
        watermark=_watermark(),
        budget=_budget(),
        payload=_detection(),
    )
    assert recurrence.recurrence is not None
    assert recurrence.recurrence.verified is True
    assert recurrence.recurrence.predecessor_occurrence_id == "occ-1"
    decoded = strict_loads(m.MaintenanceEvent, canonical_dumps(recurrence))
    assert decoded.recurrence == recurrence.recurrence
    # A fresh recurrence never reuses the prior occurrence/event identity.
    assert decoded.occurrence_id == "occ-2"
    assert decoded.event_id == "evt-2"


def test_m4_handoff_view_reports_frozen_digests_without_guessing() -> None:
    import arnold_pipelines.megaplan.maintenance as maintenance_pkg

    m = maintenance_pkg
    # The frozen schema/fixture digests match their live artifacts exactly
    # after the T16 refresh (real drift only; never guessed).
    report = m.verify_frozen_digests()
    assert set(report) == {"schema", "fixtures"}
    drifting = {
        f"{group}.{key}"
        for group, entries in report.items()
        for key, entry in entries.items()
        if not entry["matches"]
    }
    assert drifting == set(), f"frozen digests drifted: {sorted(drifting)}"
    # The view is canonical, read-only, and round-trips through the strict
    # codec; all handoffs stay pending (report-only mode), so the accepted
    # vector is empty and drift is reported as data, never promoted.
    view = m.build_handoff_view()
    assert view.accepted_handoff_count == 0
    assert view.enforcement_enabled is False
    assert view.shadow_operation_enabled is True
    assert view.enforcement_blocked is True
    decoded = strict_loads(m.MaintenanceHandoffView, canonical_dumps(view))
    assert decoded == view


def test_checkpoint_window_fold_distinguishes_all_four_windows_and_matches_dict_model() -> None:
    """Four checkpoint windows yield four distinct lifecycle keys; an exact
    retry of the same window reproduces the same key; dict and model
    derivations are mirror-identical."""
    from arnold_pipelines.megaplan.maintenance.events import (
        CheckpointWindowKind,
        OperationalEvent,
    )

    base = {
        "schema_version": 1,
        "event_id": "checkpoint_verification:occ-1:immediate",
        "occurrence": {"occurrence_id": "occ-1", "canonical_digest": "1" * 64},
        "lease": {"lease_id": "lease-1", "custody_epoch": 3},
        "run_authority": {"run_id": "run-1", "satisfied": True},
        "policy": {"policy_version": "p1", "policy_digest": "2" * 64},
        "target": {"target": "target-1", "target_type": "path"},
        "producer": {
            "principal": "verifier-1",
            "role": "verifier",
        },
        "action_kind": "checkpoint_verification",
        "payload": {
            "kind": "checkpoint_verification",
            "checkpoint": "immediate",
            "checkpoint_ref": None,
            "evidence_refs": [],
        },
        "observed_at": "2026-08-17T00:00:00Z",
    }
    keys: set[str] = set()
    for window in CheckpointWindowKind:
        event = dict(base)
        event["event_id"] = f"checkpoint_verification:occ-1:{window.value}"
        event["payload"] = dict(base["payload"])
        event["payload"]["checkpoint"] = window.value
        model = OperationalEvent.model_validate(event)
        dict_key = lifecycle_idempotency_key(event)
        model_key = operational_event_action_key(model)
        assert dict_key == model_key
        keys.add(dict_key)
        # Exact retry reproduces the same key.
        retry = dict(event)
        retry["event_id"] = f"checkpoint_verification:occ-1:{window.value}-retry"
        assert lifecycle_idempotency_key(retry) == dict_key
    assert len(keys) == len(CheckpointWindowKind)
