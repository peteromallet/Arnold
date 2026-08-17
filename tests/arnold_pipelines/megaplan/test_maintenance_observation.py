"""Focused Maintenance coherent-join tests (M2, T9).

These tests prove the bounded multi-source coherent observation join:

* the deterministic coherent / torn fixtures round-trip through the shared
  codec and pin the envelope states exactly;
* a version-stable capture returns one coherent, eligible envelope;
* a transient mid-read version tear is retried to one stable vector within the
  two-attempt default, while a permanent tear returns a typed ``INCOHERENT``
  envelope carrying **both** before/after vectors — never a mixture of source
  truth;
* every fail-closed mapping (required/optional missing, stale, contradictory,
  cursor-gap, restore/incarnation, cross-environment, unapproved handoff)
  yields a non-coherent envelope that can never be terminal, green, or
  dispatchable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arnold_pipelines.megaplan.maintenance.contracts import (
    CoherenceReason,
    CoherenceState,
    CompletenessState,
    FreshnessState,
    ObservationEnvelope,
    SourceVersionVector,
    precedence_rank,
)
from arnold_pipelines.megaplan.maintenance.handoffs import HandoffResolutionState
from arnold_pipelines.megaplan.maintenance.identity import (
    EnvironmentId,
    OwnerRef,
    canonical_digest,
    canonical_dumps,
    strict_loads,
)
from arnold_pipelines.megaplan.maintenance.observation import (
    DEFAULT_MAX_ATTEMPTS,
    JoinSource,
    capture_observation,
    conformance_source,
    custody_source,
    native_manifest_source,
    proof_source,
    run_authority_source,
    runtime_source,
    wbc_source,
)

UTC = timezone.utc
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "maintenance"


def _ts(hour: int = 12) -> datetime:
    return datetime(2026, 8, 15, hour, 0, tzinfo=UTC)


def _vector(owner: str, before: str, after: str) -> SourceVersionVector:
    return SourceVersionVector(
        owner=owner,
        source=owner,
        environment=EnvironmentId("production"),
        before=before,
        after=after,
    )


def _raise(exc: Exception) -> Any:
    def _read() -> Any:
        raise exc

    return _read


def _fake_read(
    owner: str = "run_authority",
    *,
    env: str = "production",
    torn: bool = False,
    handoff_state: HandoffResolutionState | None = None,
    run_id: str = "run-1",
    attempt_id: str = "att-1",
    gap_refs: tuple[OwnerRef, ...] = (),
    incarnation: str | None = None,
    restore_generation: str | None = None,
) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "environment": EnvironmentId(env),
        "torn": torn,
        "version_vector": _vector(owner, "a" * 64, "a" * 64),
    }
    if owner == "run_authority":
        fields["run_id"] = run_id
        fields["grants"] = (
            OwnerRef(owner="run_authority", locator="grant://g-1", digest="c" * 64, cursor="journal:1"),
        )
        fields["decisions"] = ()
        fields["fences"] = ()
        fields["attempts"] = ()
        fields["quarantines"] = ()
        fields["diagnostics"] = ()
    if owner == "wbc":
        fields["attempt_id"] = attempt_id
        fields["gap_refs"] = tuple(gap_refs)
        fields["incarnation"] = incarnation
        fields["restore_generation"] = restore_generation
    if handoff_state is not None:
        fields["handoff"] = SimpleNamespace(state=handoff_state)
    return SimpleNamespace(**fields)


def _stable_source(
    key: str,
    owner: str,
    *,
    required: bool = True,
    probe_value: str | None = "f" * 64,
    read: Any | None = None,
    stale: bool = False,
) -> JoinSource:
    return JoinSource(
        key=key,
        owner=owner,  # type: ignore[arg-type]
        required=required,
        probe=lambda: probe_value,
        read=read if read is not None else (lambda: _fake_read(owner)),
        stale_probe=(lambda _read: stale),
    )


# ---------------------------------------------------------------------------
# Deterministic fixtures
# ---------------------------------------------------------------------------


def _load_fixture(name: str) -> ObservationEnvelope:
    text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    return strict_loads(ObservationEnvelope, text)


def test_coherent_fixture_round_trips_and_is_eligible() -> None:
    envelope = _load_fixture("coherent_join.json")
    assert envelope.coherence is CoherenceState.COHERENT
    assert envelope.completeness is CompletenessState.COMPLETE
    assert envelope.freshness is FreshnessState.FRESH
    assert envelope.coherence_reasons == ()
    assert envelope.terminal is True
    assert envelope.green is True
    assert envelope.dispatchable is True
    # Deterministic canonical digest (pinned).
    assert canonical_digest(envelope) == (
        "b59006674d55fdb4d17ecb0054bd52b943166b29defb790715856ce5033f31d9"
    )


def test_torn_fixture_round_trips_with_both_vectors() -> None:
    envelope = _load_fixture("torn_join.json")
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert envelope.coherence_reasons == (CoherenceReason.VERSION_TEAR,)
    assert envelope.terminal is False
    assert envelope.green is False
    assert envelope.dispatchable is False
    torn = [v for v in envelope.version_vectors if v.owner == "wbc"]
    assert torn and any(v.before != v.after for v in torn)
    assert canonical_digest(envelope) == (
        "a4821a596420fc651e389bf1b48d7f478534b8fbc77a285ba32b6b9aa31d711a"
    )


# ---------------------------------------------------------------------------
# Coherent capture and identity validation
# ---------------------------------------------------------------------------


def test_stable_capture_returns_one_coherent_eligible_envelope() -> None:
    sources = [
        _stable_source("run_authority", "run_authority"),
        _stable_source("wbc", "wbc"),
    ]
    envelope = capture_observation(
        sources,
        observed_at=_ts(),
        environment="production",
        run="run-1",
        attempt="att-1",
    )
    assert envelope.coherence is CoherenceState.COHERENT
    assert envelope.completeness is CompletenessState.COMPLETE
    assert envelope.freshness is FreshnessState.FRESH
    assert envelope.terminal and envelope.green and envelope.dispatchable
    # References are SD1-ordered and contain no non-SD1 owner kind.
    ranks = [precedence_rank(ref.owner) for ref in envelope.references]
    assert all(rank is not None for rank in ranks)
    assert ranks == sorted(rank for rank in ranks if rank is not None)


# ---------------------------------------------------------------------------
# T6_impl: occurrence-bound owner-source join (M3 Step 5)
# ---------------------------------------------------------------------------


def _occurrence_read(
    owner: str = "custody",
    *,
    occurrence_id: str = "occ-1",
    target: str = "chain:session",
    lease_id: str = "lease-1",
    fence: str = "tok-1",
    env: str = "production",
) -> SimpleNamespace:
    """A read exposing the M7 occurrence/lease/fence/target coordinates."""
    return SimpleNamespace(
        environment=EnvironmentId(env),
        occurrence_id=occurrence_id,
        target=target,
        lease_id=lease_id,
        fencing_token=fence,
        version_vector=_vector(owner, "a" * 64, "a" * 64),
        torn=False,
    )


def _occurrence_source(
    key: str,
    owner: str,
    read: Any,
) -> JoinSource:
    return JoinSource(
        key=key,
        owner=owner,  # type: ignore[arg-type]
        required=True,
        probe=lambda: "f" * 64,
        read=lambda: read,
        stale_probe=lambda _read: False,
    )


def test_occurrence_bound_join_requires_matching_coordinates() -> None:
    sources = [
        _occurrence_source("run_authority", "run_authority", _fake_read("run_authority")),
        _occurrence_source("custody", "custody", _occurrence_read()),
    ]
    envelope = capture_observation(
        sources,
        observed_at=_ts(),
        environment="production",
        run="run-1",
        occurrence_id="occ-1",
        target="chain:session",
        lease_id="lease-1",
        fence="tok-1",
    )
    assert envelope.coherence is CoherenceState.COHERENT
    assert envelope.dispatchable is True
    assert envelope.terminal is True


def test_cross_occurrence_read_fails_closed() -> None:
    sources = [
        _occurrence_source("run_authority", "run_authority", _fake_read("run_authority")),
        _occurrence_source(
            "custody", "custody", _occurrence_read(occurrence_id="occ-OTHER")
        ),
    ]
    envelope = capture_observation(
        sources,
        observed_at=_ts(),
        environment="production",
        run="run-1",
        occurrence_id="occ-1",
        target="chain:session",
        lease_id="lease-1",
        fence="tok-1",
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.CONTRADICTORY_EVIDENCE in envelope.coherence_reasons
    assert envelope.dispatchable is False
    assert envelope.terminal is False


@pytest.mark.parametrize(
    "overrides",
    [
        dict(target="chain:other"),
        dict(lease_id="lease-OTHER"),
        dict(fence="tok-OTHER"),
        dict(env="staging"),
    ],
)
def test_occurrence_bound_dimension_mismatch_fails_closed(overrides: dict) -> None:
    sources = [
        _occurrence_source("run_authority", "run_authority", _fake_read("run_authority")),
        _occurrence_source("custody", "custody", _occurrence_read(**overrides)),
    ]
    envelope = capture_observation(
        sources,
        observed_at=_ts(),
        environment="production",
        run="run-1",
        occurrence_id="occ-1",
        target="chain:session",
        lease_id="lease-1",
        fence="tok-1",
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert envelope.dispatchable is False
    assert envelope.terminal is False


def test_missing_occurrence_coordinate_source_fails_closed() -> None:
    # A required source that carries NO occurrence coordinates (a torn or
    # missing read) keeps the envelope non-dispatchable: coordinates are
    # never inferred from the other sources.
    sources = [
        _occurrence_source("run_authority", "run_authority", _fake_read("run_authority")),
        _occurrence_source("custody", "custody", None),
    ]
    envelope = capture_observation(
        sources,
        observed_at=_ts(),
        environment="production",
        run="run-1",
        occurrence_id="occ-1",
        target="chain:session",
        lease_id="lease-1",
        fence="tok-1",
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.MISSING_REQUIRED_SOURCE in envelope.coherence_reasons


def test_proof_and_runtime_source_factories_build_join_sources() -> None:
    proof = proof_source(
        "proof-1",
        "chain:session",
        proof_provider=lambda proof_id: SimpleNamespace(digest=lambda: "d" * 64),
        registry=None,
        environment="production",
    )
    assert proof.key == "proof"
    assert proof.owner == "native_manifest"
    runtime = runtime_source(
        "S2R",
        "chain:session",
        runtime_provider=lambda hid, subject: SimpleNamespace(digest=lambda: "d" * 64),
        environment="production",
    )
    assert runtime.key == "runtime:S2R"
    assert runtime.owner == "native_manifest"


def test_unapproved_proof_source_is_unknown_and_fails_closed() -> None:
    # The default registry marks every handoff pending: the C2 proof read is
    # typed UNKNOWN and the envelope is non-dispatchable.
    source = proof_source(
        "proof-1",
        "chain:session",
        proof_provider=lambda proof_id: SimpleNamespace(digest=lambda: "d" * 64),
        environment="production",
    )
    envelope = capture_observation(
        [
            _occurrence_source("run_authority", "run_authority", _fake_read("run_authority")),
            _occurrence_source("custody", "custody", _occurrence_read()),
            source,
        ],
        observed_at=_ts(),
        environment="production",
        run="run-1",
        occurrence_id="occ-1",
        target="chain:session",
        lease_id="lease-1",
        fence="tok-1",
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.UNKNOWN in envelope.coherence_reasons
    assert envelope.dispatchable is False
    assert envelope.terminal is False


def test_join_validates_run_and_attempt_identity_dimensions() -> None:
    sources = [_stable_source("run_authority", "run_authority")]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", run="run-1"
    )
    assert envelope.coherence is CoherenceState.COHERENT
    # A contradictory declared run identity fails closed.
    contradictory = capture_observation(
        [_stable_source("run_authority", "run_authority", read=lambda: _fake_read("run_authority", run_id="run-OTHER"))],
        observed_at=_ts(),
        environment="production",
        run="run-1",
    )
    assert contradictory.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.CONTRADICTORY_EVIDENCE in contradictory.coherence_reasons
    assert not contradictory.terminal


def test_unknown_freshness_is_never_promoted_to_green() -> None:
    # No staleness signal: the capture is coherent but freshness is UNKNOWN,
    # so terminal/green/dispatchable stay False (fail-closed, never guessed).
    source = JoinSource(
        key="run_authority",
        owner="run_authority",
        required=True,
        probe=lambda: "f" * 64,
        read=lambda: _fake_read("run_authority"),
        stale_probe=None,
    )
    envelope = capture_observation(
        [source], observed_at=_ts(), environment="production", run="run-1"
    )
    assert envelope.coherence is CoherenceState.COHERENT
    assert envelope.freshness is FreshnessState.UNKNOWN
    assert not (envelope.terminal or envelope.green or envelope.dispatchable)


# ---------------------------------------------------------------------------
# Fault injection: tearing retry and permanent tear
# ---------------------------------------------------------------------------


def test_transient_tear_retries_to_one_stable_vector() -> None:
    values = ["v1" * 32, "v2" * 32, "v3" * 32, "v3" * 32]

    def probe() -> str:
        return values.pop(0)

    sources = [
        JoinSource(
            key="wbc",
            owner="wbc",
            required=True,
            probe=probe,
            read=lambda: _fake_read("wbc"),
            stale_probe=lambda _read: False,
        )
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", attempt="att-1"
    )
    assert values == []  # exactly two attempts consumed the four probes
    assert envelope.coherence is CoherenceState.COHERENT
    assert envelope.terminal is True
    wbc_vectors = [v for v in envelope.version_vectors if v.owner == "wbc"]
    assert wbc_vectors and all(v.before == v.after for v in wbc_vectors)


def test_permanent_tear_returns_incoherent_with_both_vectors() -> None:
    state = {"n": 0}

    def probe() -> str:
        state["n"] += 1
        return "x" * 64 if state["n"] % 2 else "y" * 64

    sources = [
        JoinSource(
            key="wbc",
            owner="wbc",
            required=True,
            probe=probe,
            read=lambda: _fake_read("wbc"),
            stale_probe=lambda _read: False,
        )
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", attempt="att-1"
    )
    assert state["n"] == DEFAULT_MAX_ATTEMPTS * 2  # two attempts, two probes each
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.VERSION_TEAR in envelope.coherence_reasons
    wbc_vectors = [v for v in envelope.version_vectors if v.owner == "wbc"]
    assert wbc_vectors and any(v.before != v.after for v in wbc_vectors)
    assert not (envelope.terminal or envelope.green or envelope.dispatchable)


def test_adapter_level_torn_flag_also_fails_closed() -> None:
    sources = [
        _stable_source("run_authority", "run_authority"),
        _stable_source(
            "wbc", "wbc", read=lambda: _fake_read("wbc", torn=True)
        ),
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", attempt="att-1"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.VERSION_TEAR in envelope.coherence_reasons
    assert not envelope.terminal


# ---------------------------------------------------------------------------
# Fail-closed mappings
# ---------------------------------------------------------------------------


def test_missing_required_source_fails_closed() -> None:
    sources = [
        _stable_source(
            "run_authority",
            "run_authority",
            read=_raise(RuntimeError("view unavailable")),
        )
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", run="run-1"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.MISSING_REQUIRED_SOURCE in envelope.coherence_reasons
    assert envelope.completeness is CompletenessState.PARTIAL
    assert not (envelope.terminal or envelope.green or envelope.dispatchable)


def test_missing_optional_source_fails_closed() -> None:
    sources = [
        _stable_source("run_authority", "run_authority"),
        JoinSource(
            key="custody",
            owner="custody",
            required=False,
            probe=lambda: None,
            read=lambda: None,
            stale_probe=lambda _read: False,
        ),
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", run="run-1"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.MISSING_OPTIONAL_SOURCE in envelope.coherence_reasons
    assert envelope.completeness is CompletenessState.PARTIAL
    assert not envelope.terminal


def test_cross_environment_fails_closed() -> None:
    sources = [
        _stable_source("run_authority", "run_authority", read=lambda: _fake_read("run_authority", env="production")),
        _stable_source("wbc", "wbc", read=lambda: _fake_read("wbc", env="staging")),
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.CROSS_ENVIRONMENT in envelope.coherence_reasons
    assert envelope.cross_environment is True
    assert not envelope.terminal


def test_cursor_gap_fails_closed() -> None:
    gap = OwnerRef(owner="wbc", locator="gap://att-1/1:2", digest="f" * 64, cursor="sequence:2")
    sources = [
        _stable_source("wbc", "wbc", read=lambda: _fake_read("wbc", gap_refs=(gap,)))
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", attempt="att-1"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.CURSOR_GAP in envelope.coherence_reasons
    assert not envelope.terminal


def test_incarnation_and_restore_mismatch_fail_closed() -> None:
    incarnation_source = [
        _stable_source("wbc", "wbc", read=lambda: _fake_read("wbc", incarnation="inc-A"))
    ]
    env_inc = capture_observation(
        incarnation_source,
        observed_at=_ts(),
        environment="production",
        attempt="att-1",
        expected_incarnation="inc-B",
    )
    assert CoherenceReason.INCARNATION_MISMATCH in env_inc.coherence_reasons

    restore_source = [
        _stable_source("wbc", "wbc", read=lambda: _fake_read("wbc", restore_generation="gen-A"))
    ]
    env_restore = capture_observation(
        restore_source,
        observed_at=_ts(),
        environment="production",
        attempt="att-1",
        expected_restore_generation="gen-B",
    )
    assert CoherenceReason.RESTORE_MISMATCH in env_restore.coherence_reasons


def test_unapproved_handoff_is_unknown_and_fails_closed() -> None:
    sources = [
        _stable_source(
            "wbc",
            "wbc",
            read=lambda: _fake_read("wbc", handoff_state=HandoffResolutionState.UNKNOWN),
        )
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", attempt="att-1"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.UNKNOWN in envelope.coherence_reasons
    assert envelope.completeness is CompletenessState.UNKNOWN
    assert not (envelope.terminal or envelope.green or envelope.dispatchable)


def test_stale_source_fails_closed() -> None:
    sources = [
        _stable_source("run_authority", "run_authority", stale=True),
        _stable_source("wbc", "wbc"),
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production"
    )
    assert envelope.coherence is CoherenceState.INCOHERENT
    assert CoherenceReason.STALE_SOURCE in envelope.coherence_reasons
    assert envelope.freshness is FreshnessState.STALE
    assert not envelope.terminal


def test_max_attempts_must_be_positive_and_sources_required() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        capture_observation([], observed_at=_ts())
    with pytest.raises(ValueError, match="max_attempts"):
        capture_observation(
            [_stable_source("run_authority", "run_authority")],
            observed_at=_ts(),
            max_attempts=0,
        )


# ---------------------------------------------------------------------------
# Adapter-backed source factories
# ---------------------------------------------------------------------------


def test_adapter_source_factories_build_join_sources() -> None:
    view = SimpleNamespace(view_hash="v" * 64)
    ra = run_authority_source(lambda: view, environment="production")
    assert ra.key == "run_authority" and ra.required is True
    assert ra.probe() == "v" * 64

    store = SimpleNamespace(
        get_contract_version=lambda: "c1",
        get_store_version=lambda: "s1",
    )
    wbc = wbc_source(store, "att-1", environment="production")
    assert wbc.key == "wbc" and wbc.required is True
    assert wbc.probe() == "contract:c1|store:s1"

    custody = custody_source(
        "lease-1",
        current_lease_provider=lambda _lease_id: None,
        history_provider=lambda _lease_id: [],
    )
    assert custody.key == "custody" and custody.required is False

    conformance = conformance_source(
        "subject-1", validation_evidence_provider=lambda _subject: []
    )
    assert conformance.key == "conformance" and conformance.required is False

    native = native_manifest_source(
        "C1", "subject-1", manifest_provider=lambda _hid, _sub: None
    )
    assert native.key == "native_manifest:C1" and native.required is False


def test_canonical_round_trip_of_join_output() -> None:
    sources = [
        _stable_source("run_authority", "run_authority"),
        _stable_source("wbc", "wbc"),
    ]
    envelope = capture_observation(
        sources, observed_at=_ts(), environment="production", attempt="att-1"
    )
    decoded = strict_loads(ObservationEnvelope, canonical_dumps(envelope))
    assert decoded == envelope
    assert canonical_digest(decoded) == canonical_digest(envelope)
