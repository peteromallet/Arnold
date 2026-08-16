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

import pytest
from pydantic import ValidationError

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
    ClassifierInfo,
    DetectionEvent,
    EfficiencyAnalysis,
    EventKind,
    MaintenanceEvent,
    OccurrenceBudget,
    ProjectionCoordinates,
    RecurrenceLink,
    RootCauseCluster,
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
