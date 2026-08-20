"""Bounded multi-source coherent observation join (M2, T9).

This module is the core M2 consistency algorithm.  It captures a coherent
observation over the selected authority sources by running a *two-phase*
version capture around every read:

1. **Before phase** — capture every selected source's identity/version
   (``probe``) *before* reading anything.
2. **Read phase** — read the immutable adapter snapshots produced by the T6/T7
   adapters (``RunAuthorityRead``, ``WbcRead``, ``CustodyRead``,
   ``ConformanceRead``, ``NativeManifestRead``).
3. **After phase** — recapture every selected source's version *before* any
   classification.

Classification never happens between the initial and final version reads.  If
any source tears (its before and after versions disagree, or its own adapter
snapshot reports ``torn``), the join retries the whole capture, bounded to
``max_attempts`` (default ``2``).  A permanent tear returns a typed
``INCOHERENT`` envelope that carries **both** the before and after version
vectors plus a :class:`~contracts.CoherenceReason.VERSION_TEAR` reason — never
a mixture of before/after source truth.

The join validates every identity dimension it can observe (environment across
all sources and the declared observation environment; run identity against the
Run Authority read; attempt identity against the WBC read) and maps its
failure modes onto the frozen :class:`~contracts.CoherenceReason` vocabulary
fail-closed:

* required source missing            -> ``MISSING_REQUIRED_SOURCE``
* optional source missing            -> ``MISSING_OPTIONAL_SOURCE``
* stale source                       -> ``STALE_SOURCE``
* cross-environment evidence         -> ``CROSS_ENVIRONMENT``
* before/after version tear          -> ``VERSION_TEAR``
* WBC cursor gap                     -> ``CURSOR_GAP``
* WBC incarnation mismatch           -> ``INCARNATION_MISMATCH``
* WBC restore-generation mismatch    -> ``RESTORE_MISMATCH``
* identity disagreement              -> ``CONTRADICTORY_EVIDENCE``
* unapproved / unknown handoff       -> ``UNKNOWN``

Only SD1-tier references are placed in the envelope's precedence-ordered
``references`` (Run Authority and WBC references); custody / conformance /
native references stay in the per-source read results and in the
``version_vectors`` read log (never mis-ranked).  Every failure path resolves
to a non-coherent envelope, so terminal / green / dispatchable state can never
be derived from missing, stale, contradictory, gapped, or cross-environment
evidence.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
    AttemptId,
    ChainId,
    EnvironmentId,
    ModelId,
    OwnerKind,
    OwnerRef,
    PlanId,
    ProfileId,
    RunId,
    StageId,
    TenantId,
    UtcTime,
)
from arnold_pipelines.megaplan.maintenance.sources import (
    ConformanceAdapter,
    ConformanceRead,
    CustodyAdapter,
    CustodyRead,
    NativeManifestAdapter,
    NativeManifestRead,
    ProofAdapter,
    ProofRead,
    RunAuthorityAdapter,
    RunAuthorityRead,
    RuntimeAdapter,
    RuntimeRead,
    WbcAdapter,
    WbcRead,
)

#: The default (bounded) number of capture attempts before a tear is declared
#: permanent and the join returns a typed ``INCOHERENT`` envelope.  The
#: approved configuration may override this; never exceed it silently.
DEFAULT_MAX_ATTEMPTS: int = 2


# ---------------------------------------------------------------------------
# Source bindings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JoinSource:
    """One selected source bound to its version probe and snapshot read.

    ``probe`` returns the source's current version coordinate (or ``None`` when
    the source has no separate version API); it is called before and after the
    read phase so the join can detect a tear that spans the whole read set.
    ``read`` returns the immutable adapter snapshot (a ``RunAuthorityRead``,
    ``WbcRead``, ``CustodyRead``, ``ConformanceRead``, or
    ``NativeManifestRead``).  ``stale_probe``, when supplied, reports whether
    the just-read snapshot is stale; a source without it has *unknown*
    freshness (fail-closed: never promoted to fresh).
    """

    key: str
    owner: OwnerKind
    required: bool
    probe: Callable[[], str | None]
    read: Callable[[], Any]
    stale_probe: Callable[[Any], bool] | None = None


# ---------------------------------------------------------------------------
# Adapter-backed source factories
# ---------------------------------------------------------------------------


def run_authority_source(
    view_provider: Callable[[], Any],
    *,
    request: Any | None = None,
    environment: EnvironmentId | str | None = None,
    required: bool = True,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build a required Run Authority source over ``RunAuthorityView``."""
    adapter = RunAuthorityAdapter(view_provider, environment=environment)

    def probe() -> str | None:
        return getattr(view_provider(), "view_hash", None)

    def read() -> Any:
        return adapter.read(request=request)

    return JoinSource(
        key="run_authority",
        owner="run_authority",
        required=required,
        probe=probe,
        read=read,
        stale_probe=stale_probe,
    )


def wbc_source(
    store: Any,
    attempt_id: str,
    *,
    registry: Any | None = None,
    environment: EnvironmentId | str | None = None,
    cursor_key: str = "default",
    required: bool = True,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build a required WBC source over the ``AttemptLedgerStore`` read APIs."""
    adapter = WbcAdapter(store, registry=registry, environment=environment)

    def probe() -> str | None:
        return (
            f"contract:{store.get_contract_version()}|"
            f"store:{store.get_store_version()}"
        )

    def read() -> Any:
        return adapter.read_attempt(attempt_id, cursor_key=cursor_key)

    return JoinSource(
        key="wbc",
        owner="wbc",
        required=required,
        probe=probe,
        read=read,
        stale_probe=stale_probe,
    )


def custody_source(
    lease_id: str,
    *,
    current_lease_provider: Callable[[str], Any],
    history_provider: Callable[[str], Sequence[Any]],
    validator_evidence_provider: Callable[[str], Sequence[Any]] | None = None,
    registry: Any | None = None,
    environment: EnvironmentId | str | None = None,
    required: bool = False,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build an optional M7 Custody source with an owner-backed version probe."""
    adapter = CustodyAdapter(
        current_lease_provider=current_lease_provider,
        history_provider=history_provider,
        validator_evidence_provider=validator_evidence_provider,
        registry=registry,
        environment=environment,
    )

    return JoinSource(
        key="custody",
        owner="custody",
        required=required,
        probe=lambda: adapter.probe(lease_id),
        read=lambda: adapter.read(lease_id),
        stale_probe=stale_probe,
    )


def conformance_source(
    subject: str,
    *,
    validation_evidence_provider: Callable[[str], Sequence[Any]],
    predecessor_wrapper_provider: Callable[[str], Sequence[Any]] | None = None,
    registry: Any | None = None,
    environment: EnvironmentId | str | None = None,
    required: bool = False,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build an optional M10/M11 conformance source with a version probe."""
    adapter = ConformanceAdapter(
        validation_evidence_provider=validation_evidence_provider,
        predecessor_wrapper_provider=predecessor_wrapper_provider,
        registry=registry,
        environment=environment,
    )

    return JoinSource(
        key="conformance",
        owner="conformance",
        required=required,
        probe=lambda: adapter.probe(subject),
        read=lambda: adapter.read(subject),
        stale_probe=stale_probe,
    )


def native_manifest_source(
    handoff_id: str,
    subject: str,
    *,
    manifest_provider: Callable[[str, str], Any],
    registry: Any | None = None,
    environment: EnvironmentId | str | None = None,
    required: bool = False,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build an optional Native Parity manifest source with a version probe."""
    adapter = NativeManifestAdapter(
        manifest_provider=manifest_provider,
        registry=registry,
        environment=environment,
    )

    return JoinSource(
        key=f"native_manifest:{handoff_id}",
        owner="native_manifest",
        required=required,
        probe=lambda: adapter.probe(handoff_id, subject),
        read=lambda: adapter.read(handoff_id, subject),
        stale_probe=stale_probe,
    )


def proof_source(
    proof_id: str,
    subject: str,
    *,
    proof_provider: Callable[[str], Any],
    control_provider: Callable[[str], Sequence[Any]] | None = None,
    registry: Any | None = None,
    environment: EnvironmentId | str | None = None,
    required: bool = False,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build an optional C2 negative-control proof source with a version probe."""
    adapter = ProofAdapter(
        proof_provider=proof_provider,
        control_provider=control_provider,
        registry=registry,
        environment=environment,
    )

    return JoinSource(
        key="proof",
        owner="native_manifest",
        required=required,
        probe=lambda: adapter.probe(proof_id),
        read=lambda: adapter.read(proof_id, subject),
        stale_probe=stale_probe,
    )


def runtime_source(
    handoff_id: str,
    subject: str,
    *,
    runtime_provider: Callable[[str, str], Any],
    source_provider: Callable[[str, str], Any] | None = None,
    registry: Any | None = None,
    environment: EnvironmentId | str | None = None,
    required: bool = False,
    stale_probe: Callable[[Any], bool] | None = None,
) -> JoinSource:
    """Build an optional S1/S2R runtime/source source with a version probe.

    ``handoff_id`` must be ``S1`` or ``S2R``; any other id is rejected by the
    underlying :class:`RuntimeAdapter` — a runtime source is never guessed.
    """
    adapter = RuntimeAdapter(
        runtime_provider=runtime_provider,
        source_provider=source_provider,
        registry=registry,
        environment=environment,
    )

    return JoinSource(
        key=f"runtime:{handoff_id}",
        owner="native_manifest",
        required=required,
        probe=lambda: adapter.probe(handoff_id, subject),
        read=lambda: adapter.read(handoff_id, subject),
        stale_probe=stale_probe,
    )


# ---------------------------------------------------------------------------
# Internal read-result inspection
# ---------------------------------------------------------------------------


def _identity_str(value: Any) -> str | None:
    if value is None:
        return None
    root = getattr(value, "root", None)
    if isinstance(root, str):
        return root
    return str(value)


#: Read-result attribute names that expose each declared identity dimension,
#: in precedence order (the ``_id`` form first, then the bare form).  The join
#: compares every present dimension across all sources plus the declared
#: observation identities; any disagreement is CONTRADICTORY_EVIDENCE.
#: Occurrence-bound dimensions (M3 Step 5): ``occurrence`` (the M7
#: RepairOccurrenceKey), ``target`` (the action target identity), ``lease``
#: (the current M7 lease id), and ``fence`` (the current fencing token) are
#: required to match exactly across every source that exposes them — a
#: cross-occurrence, cross-target, cross-lease, or cross-fence read is never
#: coherent.
_IDENTITY_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("tenant_id", "tenant"),
    ("tenant", "tenant"),
    ("run_id", "run"),
    ("run", "run"),
    ("chain_id", "chain"),
    ("chain", "chain"),
    ("plan_id", "plan"),
    ("plan", "plan"),
    ("stage_id", "stage"),
    ("stage", "stage"),
    ("model_id", "model"),
    ("model", "model"),
    ("profile_id", "profile"),
    ("profile", "profile"),
    ("attempt_id", "attempt"),
    ("attempt", "attempt"),
    ("occurrence_id", "occurrence"),
    ("occurrence", "occurrence"),
    ("target", "target"),
    ("lease_id", "lease"),
    ("lease", "lease"),
    ("fencing_token", "fence"),
    ("fence_token", "fence"),
    ("fence", "fence"),
)


def _read_environment(read: Any) -> EnvironmentId | None:
    return getattr(read, "environment", None)


def _read_torn(read: Any) -> bool:
    return bool(getattr(read, "torn", False))


def _read_version_vector(read: Any) -> SourceVersionVector | None:
    vector = getattr(read, "version_vector", None)
    return vector if isinstance(vector, SourceVersionVector) else None


def _read_handoff_unknown(read: Any) -> bool:
    """Return ``True`` when a read carries an unaccepted handoff resolution.

    An unaccepted (pending / missing) handoff means the source's evidence is
    typed UNKNOWN — never accepted and never guessed green.
    """
    handoff = getattr(read, "handoff", None)
    if handoff is not None:
        return getattr(handoff, "state", None) is not HandoffResolutionState.ACCEPTED
    handoffs = getattr(read, "handoffs", None)
    if handoffs:
        return any(
            getattr(item, "state", None) is not HandoffResolutionState.ACCEPTED
            for item in handoffs
        )
    return False


def _read_identity(read: Any) -> dict[str, str]:
    """Read every declared identity dimension exposed on a read result.

    A read result (``RunAuthorityRead``, ``WbcRead``, ...) exposes a subset of
    the declared identity dimensions as attributes (``run_id``, ``attempt_id``,
    ``chain_id``, ``occurrence_id``, ``fencing_token``, ...).  This returns
    the non-null, non-empty values keyed by dimension so the join can detect
    disagreement exactly — never inferring a missing dimension.  Ref lists /
    record payloads (e.g. the Run Authority ``fences`` reference list) are
    never misread as identity values.
    """
    values: dict[str, str] = {}
    for attr, key in _IDENTITY_DIMENSIONS:
        value = getattr(read, attr, None)
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, dict)):
            continue
        normalized = _identity_str(value)
        if normalized:
            values[key] = normalized
    return values


def _read_refs(read: Any) -> tuple[OwnerRef, ...]:
    """Collect every ``OwnerRef`` on a read result (unsorted, unfiltered)."""
    refs: list[OwnerRef] = []
    for attr in (
        "grants",
        "decisions",
        "fences",
        "attempts",
        "quarantines",
        "diagnostics",
        "ledger_ref",
        "gap_refs",
        "persistence_diagnostics",
        "reconciliation",
        "current_lease_ref",
        "history_refs",
        "validator_evidence_refs",
        "validation_refs",
        "predecessor_wrapper_refs",
        "manifest_ref",
        "proof_ref",
        "control_refs",
        "runtime_ref",
        "source_ref",
    ):
        value = getattr(read, attr, None)
        if isinstance(value, OwnerRef):
            refs.append(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, OwnerRef):
                    refs.append(item)
    return tuple(refs)


def _read_reasons(read: Any) -> list[CoherenceReason]:
    """Per-source diagnostics (e.g. a WBC cursor gap)."""
    reasons: list[CoherenceReason] = []
    if getattr(read, "gap_refs", ()):
        reasons.append(CoherenceReason.CURSOR_GAP)
    return reasons


def _safe_probe(probe: Callable[[], str | None]) -> str | None:
    try:
        return probe()
    except Exception:
        return None


def _dedupe(reasons: Sequence[CoherenceReason]) -> tuple[CoherenceReason, ...]:
    seen: set[CoherenceReason] = set()
    ordered: list[CoherenceReason] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered.append(reason)
    return tuple(ordered)


def _dedupe_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    seen: set[tuple[Any, ...]] = set()
    ordered: list[OwnerRef] = []
    for ref in refs:
        key = (ref.owner, ref.locator, ref.digest, ref.cursor)
        if key not in seen:
            seen.add(key)
            ordered.append(ref)
    return tuple(ordered)


# ---------------------------------------------------------------------------
# The join
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Assessment:
    """Normalized result of one capture attempt (used to build the envelope)."""

    coherent: bool
    completeness: CompletenessState
    freshness: FreshnessState
    coherence: CoherenceState
    reasons: tuple[CoherenceReason, ...]
    version_vectors: tuple[SourceVersionVector, ...]
    references: tuple[OwnerRef, ...]
    environment: EnvironmentId | None


def _assess_attempt(
    sources: Sequence[JoinSource],
    reads: dict[str, Any],
    before: dict[str, str | None],
    after: dict[str, str | None],
    *,
    declared_environment: EnvironmentId | None,
    declared_identities: dict[str, str],
    expected_incarnation: str | None,
    expected_restore_generation: str | None,
) -> _Assessment:
    reasons: list[CoherenceReason] = []
    missing_required = False
    missing_optional = False
    any_required_unknown = False
    stale = False
    fresh_unknown = False
    environments: set[EnvironmentId] = set()
    version_vectors: list[SourceVersionVector] = []
    all_refs: list[OwnerRef] = []
    identity_values: dict[str, set[str]] = {}
    read_environments: list[EnvironmentId] = []

    if declared_environment is not None:
        environments.add(declared_environment)

    for source in sources:
        read = reads.get(source.key)
        probe_before = before.get(source.key)
        probe_after = after.get(source.key)
        probe_torn = probe_before != probe_after  # None == None is not a tear

        if read is None:
            # Read failed: a missing selected source.
            if source.required:
                missing_required = True
                reasons.append(CoherenceReason.MISSING_REQUIRED_SOURCE)
            else:
                missing_optional = True
                reasons.append(CoherenceReason.MISSING_OPTIONAL_SOURCE)
            version_vectors.append(
                SourceVersionVector(
                    owner=source.owner,
                    source=source.key,
                    environment=declared_environment,
                    before=probe_before,
                    after=probe_after,
                )
            )
            continue

        read_torn = _read_torn(read)
        read_unknown = _read_handoff_unknown(read)
        env = _read_environment(read)
        if env is not None:
            environments.add(env)
            read_environments.append(env)

        if read_torn or probe_torn:
            reasons.append(CoherenceReason.VERSION_TEAR)

        if read_unknown:
            if source.required:
                any_required_unknown = True
            reasons.append(CoherenceReason.UNKNOWN)

        if source.stale_probe is not None:
            try:
                if bool(source.stale_probe(read)):
                    stale = True
                    reasons.append(CoherenceReason.STALE_SOURCE)
            except Exception:
                pass
        else:
            fresh_unknown = True

        reasons.extend(_read_reasons(read))

        if expected_incarnation is not None:
            actual = getattr(read, "incarnation", None)
            if actual is not None and str(actual) != expected_incarnation:
                reasons.append(CoherenceReason.INCARNATION_MISMATCH)
        if expected_restore_generation is not None:
            actual = getattr(read, "restore_generation", None)
            if actual is not None and str(actual) != expected_restore_generation:
                reasons.append(CoherenceReason.RESTORE_MISMATCH)

        vector = _read_version_vector(read)
        if probe_before is not None or probe_after is not None:
            version_vectors.append(
                SourceVersionVector(
                    owner=source.owner,
                    source=source.key,
                    environment=env if env is not None else declared_environment,
                    before=probe_before,
                    after=probe_after,
                )
            )
        elif vector is not None:
            version_vectors.append(vector)
        else:
            version_vectors.append(
                SourceVersionVector(
                    owner=source.owner,
                    source=source.key,
                    environment=env if env is not None else declared_environment,
                    before=None,
                    after=None,
                )
            )

        all_refs.extend(_read_refs(read))

        for key, value in _read_identity(read).items():
            identity_values.setdefault(key, set()).add(value)

    # Identity-dimension validation (fail-closed, never inferred): every
    # declared dimension and every read-exposed dimension must agree exactly.
    # A disagreement on any dimension (tenant/run/chain/plan/stage/model/
    # profile/attempt) is CONTRADICTORY_EVIDENCE and never coherent/green.
    for key, value in declared_identities.items():
        identity_values.setdefault(key, set()).add(value)
    for values in identity_values.values():
        if len(values) > 1:
            reasons.append(CoherenceReason.CONTRADICTORY_EVIDENCE)
            break

    cross_environment = len(environments) > 1
    if cross_environment:
        reasons.append(CoherenceReason.CROSS_ENVIRONMENT)

    reasons = _dedupe(reasons)

    if missing_required or missing_optional:
        completeness = CompletenessState.PARTIAL
    elif any_required_unknown:
        completeness = CompletenessState.UNKNOWN
    else:
        completeness = CompletenessState.COMPLETE

    if stale:
        freshness = FreshnessState.STALE
    elif fresh_unknown:
        freshness = FreshnessState.UNKNOWN
    else:
        freshness = FreshnessState.FRESH

    coherent = (
        not reasons
        and completeness is CompletenessState.COMPLETE
        and not cross_environment
    )
    if not coherent and not reasons:
        # Fail closed: a non-coherent outcome must always carry a typed
        # reason (the envelope contract requires it).
        reasons = (CoherenceReason.UNKNOWN,)
    coherence = CoherenceState.COHERENT if coherent else CoherenceState.INCOHERENT

    references = _dedupe_refs(all_refs)
    sd1_references = tuple(
        ref for ref in references if precedence_rank(ref.owner) is not None
    )

    if declared_environment is not None:
        envelope_environment = declared_environment
    elif len(read_environments) == 1:
        envelope_environment = read_environments[0]
    else:
        envelope_environment = None

    return _Assessment(
        coherent=coherent,
        completeness=completeness,
        freshness=freshness,
        coherence=coherence,
        reasons=reasons,
        version_vectors=tuple(version_vectors),
        references=sd1_references,
        environment=envelope_environment,
    )


def capture_observation(
    sources: Sequence[JoinSource],
    *,
    observed_at: UtcTime | datetime,
    environment: EnvironmentId | str | None = None,
    tenant: TenantId | str | None = None,
    run: RunId | str | None = None,
    chain: ChainId | str | None = None,
    plan: PlanId | str | None = None,
    stage: StageId | str | None = None,
    model: ModelId | str | None = None,
    profile: ProfileId | str | None = None,
    attempt: AttemptId | str | None = None,
    occurrence_id: str | None = None,
    target: str | None = None,
    lease_id: str | None = None,
    fence: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    expected_incarnation: str | None = None,
    expected_restore_generation: str | None = None,
) -> ObservationEnvelope:
    """Capture one coherent observation over the selected sources.

    Runs the bounded two-phase capture (before -> read -> after) and returns
    either a coherent :class:`~contracts.ObservationEnvelope` or a typed
    ``INCOHERENT`` envelope carrying both version vectors and the mapped
    :class:`~contracts.CoherenceReason` values.  A transient version tear is
    retried up to ``max_attempts``; every other failure mode (missing, stale,
    contradictory, cursor-gap, restore/incarnation, cross-environment,
    unapproved handoff) is permanent and fails closed immediately.

    Occurrence-bound coordinates (M3 Step 5): ``occurrence_id`` (the M7
    RepairOccurrenceKey), ``target`` (the action target identity),
    ``lease_id`` (the current M7 lease id), and ``fence`` (the current
    fencing token) are validated as identity dimensions like environment /
    run / attempt: every source that exposes them must agree exactly, and a
    cross-occurrence / cross-target / cross-lease / cross-fence read is typed
    ``INCOHERENT`` with ``CONTRADICTORY_EVIDENCE``.
    """
    if not sources:
        raise ValueError("capture_observation requires at least one source")
    if max_attempts < 1:
        raise ValueError(
            f"max_attempts must be >= 1, got {max_attempts}"
        )

    env_value = (
        EnvironmentId(environment) if isinstance(environment, str) else environment
    )
    declared_identities: dict[str, str] = {}
    for key, value in (
        ("tenant", _identity_str(tenant)),
        ("run", _identity_str(run)),
        ("chain", _identity_str(chain)),
        ("plan", _identity_str(plan)),
        ("stage", _identity_str(stage)),
        ("model", _identity_str(model)),
        ("profile", _identity_str(profile)),
        ("attempt", _identity_str(attempt)),
        ("occurrence", _identity_str(occurrence_id)),
        ("target", _identity_str(target)),
        ("lease", _identity_str(lease_id)),
        ("fence", _identity_str(fence)),
    ):
        if value:
            declared_identities[key] = value

    source_list = list(sources)
    last_envelope: ObservationEnvelope | None = None

    for attempt_no in range(1, max_attempts + 1):
        before: dict[str, str | None] = {
            source.key: _safe_probe(source.probe) for source in source_list
        }
        reads: dict[str, Any] = {}
        for source in source_list:
            try:
                reads[source.key] = source.read()
            except Exception:
                reads[source.key] = None
        after: dict[str, str | None] = {
            source.key: _safe_probe(source.probe) for source in source_list
        }

        assessment = _assess_attempt(
            source_list,
            reads,
            before,
            after,
            declared_environment=env_value,
            declared_identities=declared_identities,
            expected_incarnation=expected_incarnation,
            expected_restore_generation=expected_restore_generation,
        )
        envelope = ObservationEnvelope.build(
            observed_at=observed_at,
            environment=assessment.environment,
            tenant=tenant,
            run=run,
            chain=chain,
            plan=plan,
            stage=stage,
            model=model,
            profile=profile,
            attempt=attempt,
            version_vectors=assessment.version_vectors,
            references=assessment.references,
            completeness=assessment.completeness,
            freshness=assessment.freshness,
            coherence=assessment.coherence,
            coherence_reasons=assessment.reasons,
        )
        last_envelope = envelope

        if assessment.coherent:
            return envelope

        # Retry only a transient version tear within the bounded budget.
        if CoherenceReason.VERSION_TEAR in assessment.reasons and attempt_no < max_attempts:
            continue

        return envelope

    assert last_envelope is not None
    return last_envelope


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "JoinSource",
    "capture_observation",
    "conformance_source",
    "custody_source",
    "native_manifest_source",
    "proof_source",
    "run_authority_source",
    "runtime_source",
    "wbc_source",
]
