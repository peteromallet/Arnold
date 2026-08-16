"""Closed fail-closed ObservationEnvelope and frozen SD1 evidence precedence.

This module freezes the M2 observation contract consumed by the coherent join
(T9), the shadow comparison API (T14), and every authority-adjacent consumer
(watchdog/status/auditor/dispatch/chain guard).  It builds exclusively on the
T1 foundation (strict identities, locator-only immutable owner references,
validated UTC times, and the one canonical serializer / strict decoder).

Locked decision SD1 — evidence precedence (frozen, do not re-litigate)::

    Run Authority grants/attempts/accepted decisions/fences/quarantine;
    WBC/kernel attempt events;
    maintenance observations/transitions;
    plan events/receipts/artifact digests/accepted gate-finalize results;
    chain and repair-custody events;
    resident/cloud snapshots and heartbeats;
    mutable state/status projections last.

``EVIDENCE_PRECEDENCE`` encodes exactly those seven tiers.  Owner kinds that
are *not* part of SD1 (``custody``, ``conformance``, ``native_manifest``,
``unknown``) are rejected from the envelope's precedence-ordered reference
list: the envelope can never silently mis-rank evidence.  They remain
representable in :class:`SourceVersionVector` (the read log) and in the
Maintenance event contracts (T3).

Fail-closed eligibility rules (the SC2 invariant)::

    terminal / green / dispatchable == True is REJECTED at construction and
    at strict decode unless the envelope is coherent AND complete AND fresh
    AND single-environment.  Incomplete (PARTIAL/UNKNOWN completeness), stale
    (STALE/UNKNOWN freshness), cross-environment, and incoherent
    (INCOHERENT/UNKNOWN coherence) evidence can never serialize as terminal,
    green, or dispatchable.  UNKNOWN states are never promoted.

All models are frozen, forbid unknown fields (except the explicit
``extensions`` map), and round-trip through the single canonical codec
(``canonical_dumps`` / ``strict_loads``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    AttemptId,
    ChainId,
    EnvironmentId,
    Extensions,
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

# ---------------------------------------------------------------------------
# Frozen SD1 evidence precedence
# ---------------------------------------------------------------------------

#: The settled precedence decision identifier (locked in the brief).
EVIDENCE_PRECEDENCE_VERSION: str = "SD1"

#: Exact SD1 evidence precedence as ordered tiers.  Each inner tuple is one
#: precedence tier; kinds inside a tier share the same rank.  This is the
#: single frozen table used by :func:`precedence_rank` and by the envelope's
#: reference ordering — there is deliberately no second or fallback table.
EVIDENCE_PRECEDENCE: tuple[tuple[OwnerKind, ...], ...] = (
    ("run_authority",),  # grants/attempts/accepted decisions/fences/quarantine
    ("wbc",),  # WBC/kernel attempt events
    ("maintenance",),  # maintenance observations/transitions
    ("plan",),  # plan events/receipts/artifact digests/accepted gate-finalize
    ("chain", "repair_custody"),  # chain and repair-custody events
    ("snapshot", "heartbeat"),  # resident/cloud snapshots and heartbeats
    ("status_projection",),  # mutable state/status projections LAST
)

_PRECEDENCE_RANK: dict[OwnerKind, int] = {
    kind: rank
    for rank, tier in enumerate(EVIDENCE_PRECEDENCE, start=1)
    for kind in tier
}


def precedence_rank(owner: OwnerKind) -> int | None:
    """Return the 1-based SD1 precedence rank of *owner*, or ``None``.

    ``None`` means the owner kind is not part of the frozen SD1 table
    (``custody``, ``conformance``, ``native_manifest``, ``unknown``); such
    kinds have no defined precedence and must never appear in the envelope's
    precedence-ordered reference list.
    """
    return _PRECEDENCE_RANK.get(owner)


def _ref_sort_key(ref: Any) -> tuple[Any, ...]:
    """Canonical reference sort key (rank, kind, locator, digest, cursor).

    Accepts both raw dicts (pre-validation input) and validated
    :class:`~arnold_pipelines.megaplan.maintenance.identity.OwnerRef`
    instances so the before-validator can order either form.
    """
    if isinstance(ref, dict):
        owner = ref.get("owner")
        locator = ref.get("locator", "")
        digest = ref.get("digest")
        cursor = ref.get("cursor")
    else:
        owner = getattr(ref, "owner", None)
        locator = getattr(ref, "locator", "")
        digest = getattr(ref, "digest", None)
        cursor = getattr(ref, "cursor", None)
    return (
        precedence_rank(owner),
        owner,
        locator or "",
        digest or "",
        cursor or "",
    )


def _vector_sort_key(vector: Any) -> tuple[Any, ...]:
    """Canonical version-vector sort key (owner, source, env, before, after)."""
    if isinstance(vector, dict):
        owner = vector.get("owner", "")
        source = vector.get("source", "")
        env = vector.get("environment")
        before = vector.get("before")
        after = vector.get("after")
    else:
        owner = getattr(vector, "owner", "")
        source = getattr(vector, "source", "")
        env = getattr(vector, "environment", None)
        before = getattr(vector, "before", None)
        after = getattr(vector, "after", None)
    env_root = env.root if hasattr(env, "root") else (env or "")
    return (owner, source, env_root, before or "", after or "")


# ---------------------------------------------------------------------------
# Envelope states (closed vocabularies)
# ---------------------------------------------------------------------------


class CompletenessState(str, Enum):
    """How much of the selected evidence set was captured."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class FreshnessState(str, Enum):
    """Whether the captured evidence is fresh against the watermark."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class CoherenceState(str, Enum):
    """Whether the captured evidence is one version-coherent truth."""

    COHERENT = "coherent"
    INCOHERENT = "incoherent"
    UNKNOWN = "unknown"


class CoherenceReason(str, Enum):
    """Closed vocabulary of typed reasons for non-coherent envelopes.

    A coherent envelope carries NO reasons; every non-coherent or unknown
    envelope must carry at least one.  The join (T9) maps its failure modes
    onto exactly these reasons.
    """

    MISSING_REQUIRED_SOURCE = "missing_required_source"
    MISSING_OPTIONAL_SOURCE = "missing_optional_source"
    STALE_SOURCE = "stale_source"
    CROSS_ENVIRONMENT = "cross_environment"
    VERSION_TEAR = "version_tear"  # before != after on one source read
    CURSOR_GAP = "cursor_gap"
    RESTORE_MISMATCH = "restore_mismatch"
    INCARNATION_MISMATCH = "incarnation_mismatch"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Before/after source version vectors
# ---------------------------------------------------------------------------


class SourceVersionVector(BaseModel):
    """One source's before/after version coordinates captured around a read.

    The coherent join records, for every selected source, the version(s)
    observed *before* reads and *after* reads.  A vector whose ``before`` and
    ``after`` differ is torn (see :attr:`CoherenceReason.VERSION_TEAR`).
    ``environment`` is carried per source so cross-environment mixing can be
    detected exactly (never inferred).

    Any :data:`~arnold_pipelines.megaplan.maintenance.identity.OwnerKind` may
    appear here — this is the read log, not the SD1-ordered reference list.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: OwnerKind
    source: StrictStr
    environment: EnvironmentId | None = None
    before: StrictStr | None = None
    after: StrictStr | None = None

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        if not value:
            raise ValueError("source identity must be a non-empty string")
        return value

    @field_validator("before", "after")
    @classmethod
    def _validate_version(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("version coordinates must be non-empty strings when present")
        return value


# ---------------------------------------------------------------------------
# Fail-closed eligibility
# ---------------------------------------------------------------------------


def eligibility_supported(
    *,
    coherence: CoherenceState,
    completeness: CompletenessState,
    freshness: FreshnessState,
    cross_environment: bool,
) -> bool:
    """Return whether the states can support terminal/green/dispatchable.

    Fail-closed: every UNKNOWN state, staleness, incompleteness, and any
    cross-environment mixing disqualifies the envelope.  Nothing is inferred
    or promoted.
    """
    return (
        coherence is CoherenceState.COHERENT
        and completeness is CompletenessState.COMPLETE
        and freshness is FreshnessState.FRESH
        and not cross_environment
    )


# ---------------------------------------------------------------------------
# The closed ObservationEnvelope
# ---------------------------------------------------------------------------


class ObservationEnvelope(BaseModel):
    """Closed, fail-closed maintenance observation over authority sources.

    Carries the typed source identities, per-source before/after version
    vectors, SD1-precedence-ordered immutable references, completeness and
    freshness states, coherence reasons, and the derived terminal/green/
    dispatchable eligibility.  The eligibility booleans are part of the
    canonical payload (consumers must be able to serialize
    non-dispatchability), but the SC2 invariant is enforced at both
    construction and strict decode:

    * ``terminal`` / ``green`` / ``dispatchable`` may be ``True`` ONLY when
      the envelope is coherent, complete, fresh, and single-environment;
    * a coherent envelope can never contain cross-environment evidence and
      can never carry coherence reasons;
    * a non-coherent or unknown envelope must carry at least one typed
      :class:`CoherenceReason`.

    ``references`` are always stored in canonical SD1 precedence order
    (rank, then kind, then locator, then digest, then cursor); input order is
    normalized so every instance — constructed or decoded — is
    precedence-ordered.  Only SD1-tier owner kinds are accepted in
    ``references``; other kinds are rejected rather than silently mis-ranked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Closed strict versioning: only the current Maintenance schema version
    #: decodes; unknown versions are rejected instead of being tolerated.
    schema_version: int = Field(
        default=MAINTENANCE_SCHEMA_VERSION, frozen=True
    )

    #: Validated UTC instant at which the observation was captured.
    observed_at: UtcTime

    # Typed source identities (explicit null when unknown — never guessed).
    environment: EnvironmentId | None = None
    tenant: TenantId | None = None
    run: RunId | None = None
    chain: ChainId | None = None
    plan: PlanId | None = None
    stage: StageId | None = None
    model: ModelId | None = None
    profile: ProfileId | None = None
    attempt: AttemptId | None = None

    #: Before/after version vectors for every selected source (read log).
    #: Stored in canonical order by (owner, source, environment, before,
    #: after); input order is normalized.
    version_vectors: tuple[SourceVersionVector, ...] = ()

    #: SD1-precedence-ordered immutable references to owner records.  Only
    #: SD1-tier owner kinds are accepted; the list is always stored in
    #: canonical precedence order.
    references: tuple[OwnerRef, ...] = ()

    completeness: CompletenessState
    freshness: FreshnessState
    coherence: CoherenceState
    coherence_reasons: tuple[CoherenceReason, ...] = ()

    # Derived eligibility — validated, never over-claimable.
    terminal: bool = False
    green: bool = False
    dispatchable: bool = False

    #: The only place unknown keys are allowed.
    extensions: Extensions | None = None

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @property
    def cross_environment(self) -> bool:
        """True when present environment values disagree.

        Compares the envelope's own ``environment`` against every vector
        environment and each vector against the others.  Environments are
        exact-match identities: a mismatch is reported, never aliased.
        Absent (``None``) values cannot disagree and are not inferred.
        """
        present: list[str] = []
        if self.environment is not None:
            present.append(self.environment.root)
        for vector in self.version_vectors:
            if vector.environment is not None:
                present.append(vector.environment.root)
        return len(set(present)) > 1

    @property
    def is_eligible(self) -> bool:
        """Whether the states support terminal/green/dispatchable claims."""
        return eligibility_supported(
            coherence=self.coherence,
            completeness=self.completeness,
            freshness=self.freshness,
            cross_environment=self.cross_environment,
        )

    @field_validator("references", mode="before")
    @classmethod
    def _normalize_references(cls, value: Any) -> Any:
        """Sort raw references into canonical SD1 precedence order.

        Runs before validation so every instance — constructed or decoded —
        stores the references precedence-ordered (rank, kind, locator,
        digest, cursor).  Non-SD1 kinds are rejected by the after validator.
        """
        if isinstance(value, (list, tuple)):
            return sorted(value, key=_ref_sort_key)
        return value

    @field_validator("version_vectors", mode="before")
    @classmethod
    def _normalize_vectors(cls, value: Any) -> Any:
        """Sort raw version vectors into canonical order.

        Canonical order is (owner, source, environment, before, after) so
        digests are byte-stable regardless of capture order.
        """
        if isinstance(value, (list, tuple)):
            return sorted(value, key=_vector_sort_key)
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> ObservationEnvelope:
        # 1. References: only SD1-tier kinds may appear in the
        #    precedence-ordered list (they were already sorted by the before
        #    validator; a kind without an SD1 rank cannot be ranked here).
        for ref in self.references:
            if precedence_rank(ref.owner) is None:
                raise ValueError(
                    f"owner kind {ref.owner!r} has no SD1 precedence rank and "
                    "cannot appear in the precedence-ordered references; "
                    "carry it in version_vectors instead"
                )

        # 2. Coherence/reasons consistency.
        if self.coherence is CoherenceState.COHERENT and self.coherence_reasons:
            raise ValueError(
                "a coherent envelope must not carry coherence reasons; "
                f"got {[r.value for r in self.coherence_reasons]}"
            )
        if self.coherence is not CoherenceState.COHERENT and not self.coherence_reasons:
            raise ValueError(
                f"coherence {self.coherence.value!r} requires at least one "
                "typed coherence reason"
            )
        if self.coherence is CoherenceState.COHERENT and self.cross_environment:
            raise ValueError(
                "a coherent envelope cannot contain cross-environment "
                "evidence; mark it INCOHERENT with CROSS_ENVIRONMENT instead"
            )

        # 3. SC2 fail-closed eligibility: incomplete, stale, cross-environment,
        #    or incoherent evidence can never be terminal/green/dispatchable.
        if not self.is_eligible and (
            self.terminal or self.green or self.dispatchable
        ):
            raise ValueError(
                "fail-closed eligibility violation: an envelope that is "
                f"{self.coherence.value}/{self.completeness.value}/"
                f"{self.freshness.value}"
                f"{' with cross-environment evidence' if self.cross_environment else ''} "
                "cannot be terminal, green, or dispatchable"
            )
        return self

    @classmethod
    def build(
        cls,
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
        version_vectors: Sequence[SourceVersionVector] = (),
        references: Sequence[OwnerRef] = (),
        completeness: CompletenessState,
        freshness: FreshnessState,
        coherence: CoherenceState,
        coherence_reasons: Sequence[CoherenceReason] = (),
        extensions: Extensions | None = None,
    ) -> ObservationEnvelope:
        """Construct an envelope with the eligibility booleans derived.

        ``terminal``, ``green``, and ``dispatchable`` are derived from the
        supplied states (see :func:`eligibility_supported`); callers cannot
        over-claim through this entry point.  Direct construction is still
        possible but every over-claim is rejected by the model validator.
        """
        vectors = tuple(version_vectors)
        probe = cls(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            observed_at=observed_at,
            environment=environment,
            tenant=tenant,
            run=run,
            chain=chain,
            plan=plan,
            stage=stage,
            model=model,
            profile=profile,
            attempt=attempt,
            version_vectors=vectors,
            references=tuple(references),
            completeness=completeness,
            freshness=freshness,
            coherence=coherence,
            coherence_reasons=tuple(coherence_reasons),
            terminal=False,
            green=False,
            dispatchable=False,
            extensions=extensions,
        )
        eligible = probe.is_eligible
        return cls(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            observed_at=observed_at,
            environment=environment,
            tenant=tenant,
            run=run,
            chain=chain,
            plan=plan,
            stage=stage,
            model=model,
            profile=profile,
            attempt=attempt,
            version_vectors=vectors,
            references=tuple(references),
            completeness=completeness,
            freshness=freshness,
            coherence=coherence,
            coherence_reasons=tuple(coherence_reasons),
            terminal=eligible,
            green=eligible,
            dispatchable=eligible,
            extensions=extensions,
        )


__all__ = [
    "CompletenessState",
    "CoherenceReason",
    "CoherenceState",
    "EVIDENCE_PRECEDENCE",
    "EVIDENCE_PRECEDENCE_VERSION",
    "FreshnessState",
    "ObservationEnvelope",
    "SourceVersionVector",
    "eligibility_supported",
    "precedence_rank",
]
