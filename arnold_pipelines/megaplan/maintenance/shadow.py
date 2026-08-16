"""Deterministic read-only shadow comparison API (M2, T14).

This module compares a *legacy consumer result* (the pre-M2 verdict of a
watchdog / status / auditor / dispatch / chain-guard consumer) to a coherent
Maintenance :class:`~arnold_pipelines.megaplan.maintenance.contracts.ObservationEnvelope`
without authorizing either one.  Every comparison produces exactly **one**
:class:`ShadowComparison` row whose :attr:`~ShadowComparison.bucket` is exactly
one of the six closed buckets:

* ``match`` — the legacy verdict agrees with the envelope verdict and the
  envelope is eligible (coherent, complete, fresh, single-environment, with a
  digest-stable projection when one is supplied);
* ``explained_difference`` — a difference with a typed explanation: the
  envelope is non-eligible while the legacy verdict is also non-promoting (the
  envelope's coherence reasons explain its non-green state), or the envelope
  is eligible and promoting while the legacy verdict is a known conservative
  non-promotion (typed ``legacy_conservative_non_promotion``);
* ``unexplained_difference`` — the verdicts disagree with no typed explanation
  (e.g. a legacy verdict that promotes against an eligible, explicitly
  non-promoting envelope, or a projection source-digest mismatch);
* ``missing_denominator`` — the comparison requires a coverage denominator but
  none is available;
* ``stale_projection`` — the supplied projection reports ``stale``/``unknown``
  freshness, so no comparison on top of it may ever be green;
* ``would_block`` — the legacy verdict would promote (green/dispatchable) while
  the envelope is non-eligible; the shadow comparison would block it.

Fail-closed interpretation (the SC14 invariant):::

    UNKNOWN/PARTIAL/INCOHERENT completeness or coherence, STALE/UNKNOWN
    freshness, cross-environment evidence, a stale projection, a projection
    source-digest mismatch, or a missing required denominator can NEVER yield
    ``green`` / ``dispatchable`` / ``terminal`` on a comparison row.  Only a
    ``match`` row whose envelope is eligible may carry green/dispatchable/
    terminal, and only when the legacy verdict agrees.

Every row carries the envelope (source) digest, the projection source/output
digests, the coverage denominator, the derived coverage, the legacy hash, and
the typed reasons.  The module exposes **no mutation and no dispatch method**:
it never writes, never applies, never enqueues, and never authorizes either
side of the comparison.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from arnold_pipelines.megaplan.maintenance.contracts import ObservationEnvelope
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    canonical_digest,
    canonical_dumps,
)

#: The six closed shadow buckets, in canonical order.  A comparison row is
#: assigned exactly one of these.
SHADOW_BUCKETS: tuple[str, ...] = (
    "match",
    "explained_difference",
    "unexplained_difference",
    "missing_denominator",
    "stale_projection",
    "would_block",
)

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

#: Projection freshness values that are never promotable (fail-closed: unknown
#: freshness is treated exactly like stale freshness — never promoted).
_NON_FRESH_PROJECTION: frozenset[str] = frozenset({"stale", "unknown"})


class ShadowBucket(str, Enum):
    """Closed bucket assigned to one shadow comparison row."""

    MATCH = "match"
    EXPLAINED_DIFFERENCE = "explained_difference"
    UNEXPLAINED_DIFFERENCE = "unexplained_difference"
    MISSING_DENOMINATOR = "missing_denominator"
    STALE_PROJECTION = "stale_projection"
    WOULD_BLOCK = "would_block"


class LegacyResult(BaseModel):
    """The normalized, read-only legacy consumer verdict being compared.

    Strict and frozen: ``green`` / ``dispatchable`` / ``terminal`` must be
    real booleans (no coercion, no inference) and no unknown field is
    accepted.  The comparator never authorizes this result — it only classifies
    the row and hashes the normalized verdict.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    green: bool = False
    dispatchable: bool = False
    terminal: bool = False


# ---------------------------------------------------------------------------
# Internal projection metadata extraction (duck-typed, read-only)
# ---------------------------------------------------------------------------


def _enum_value(value: Any) -> Any:
    """Return the scalar value of a str-Enum projection field, unchanged otherwise."""
    if hasattr(value, "value") and not isinstance(value, str):
        return value.value
    return value


def _projection_metadata(projection: Any) -> dict[str, Any]:
    """Extract the comparison-relevant metadata from a projection snapshot.

    Accepts any object exposing the T13 projection surface (``freshness``,
    ``source_digest``, ``output_digest``, ``coverage_denominator``,
    ``covered_count``, ``projection``) — typically an
    :class:`~arnold_pipelines.megaplan.maintenance.projections.EfficiencyProjection`
    or a test double.  Absent values stay explicit ``None`` (never guessed).
    """
    if projection is None:
        return {
            "name": None,
            "freshness": None,
            "source_digest": None,
            "output_digest": None,
            "denominator": None,
            "covered_count": None,
        }
    return {
        "name": _enum_value(getattr(projection, "projection", None)),
        "freshness": _enum_value(getattr(projection, "freshness", None)),
        "source_digest": getattr(projection, "source_digest", None),
        "output_digest": getattr(projection, "output_digest", None),
        "denominator": getattr(projection, "coverage_denominator", None),
        "covered_count": getattr(projection, "covered_count", None),
    }


def _coerce_legacy(legacy: LegacyResult | Mapping[str, Any]) -> LegacyResult:
    """Normalize a legacy verdict to a strict :class:`LegacyResult`.

    Mappings are accepted for consumer compatibility; only the three known
    verdict fields are read (extra consumer fields do not change the verdict)
    and the normalized model is what the legacy hash covers.
    """
    if isinstance(legacy, LegacyResult):
        return legacy
    if isinstance(legacy, Mapping):
        known = {
            key: legacy[key]
            for key in ("green", "dispatchable", "terminal")
            if key in legacy
        }
        return LegacyResult(**known)
    raise ValueError(
        "legacy must be a LegacyResult or a mapping with green/dispatchable/terminal"
    )


def _derived_coverage(denominator: Any, covered_count: Any) -> float | None:
    """Coverage = covered / denominator; ``None`` for every unknown case.

    A missing numerator, a missing denominator, or a zero denominator yields
    ``None`` — never a division by zero and never a promoted zero.
    """
    if denominator is None or covered_count is None:
        return None
    try:
        denominator_value = float(denominator)
        covered_value = float(covered_count)
    except (TypeError, ValueError):
        return None
    if denominator_value == 0:
        return None
    return covered_value / denominator_value


# ---------------------------------------------------------------------------
# The comparison row
# ---------------------------------------------------------------------------


class ShadowComparison(BaseModel):
    """One deterministic, read-only shadow comparison row.

    ``bucket`` is exactly one of the six :class:`ShadowBucket` values; the
    fail-closed ``green`` / ``dispatchable`` / ``terminal`` flags are derived
    and validated (a non-``match`` row can never carry a True promotion flag).
    The row carries the envelope (source) digest, projection source/output
    digests, coverage denominator, derived coverage, legacy hash, and the
    typed reasons.  It exposes no mutation or dispatch method.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    bucket: ShadowBucket
    reasons: tuple[str, ...] = ()

    # Legacy verdict (reported as data, never authorized).
    legacy_green: bool
    legacy_dispatchable: bool
    legacy_terminal: bool

    # Envelope verdict (fail-closed: eligibility is never inferred).
    envelope_eligible: bool
    envelope_green: bool
    envelope_dispatchable: bool
    envelope_terminal: bool
    cross_environment: bool

    # Derived shadow verdict — True only for a match on an eligible envelope
    # with a legacy verdict that agrees.
    green: bool
    dispatchable: bool
    terminal: bool

    # Digests / denominator / coverage / legacy hash (explicit, never guessed).
    envelope_digest: str
    legacy_hash: str
    projection_name: str | None = None
    projection_source_digest: str | None = None
    projection_output_digest: str | None = None
    denominator: int | None = None
    covered_count: int | None = None
    coverage: float | None = None

    # Fail-closed condition flags (data; the bucket encodes the decision).
    stale_projection: bool = False
    digest_mismatch: bool = False
    missing_denominator: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported shadow comparison schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator(
        "envelope_digest",
        "legacy_hash",
        "projection_source_digest",
        "projection_output_digest",
    )
    @classmethod
    def _validate_digests(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _SHA256_HEX_RE.fullmatch(value):
            raise ValueError(
                "shadow comparison digests must be 64-character lowercase "
                "sha256 hex digests"
            )
        return value

    @field_validator("denominator", "covered_count")
    @classmethod
    def _validate_counts(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int):
            raise ValueError("denominator/covered_count must be integers when present")
        if value < 0:
            raise ValueError("denominator/covered_count must be >= 0")
        return value

    @field_validator("coverage")
    @classmethod
    def _validate_coverage(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"coverage must be within [0, 1], got {value}")
        return value

    @model_validator(mode="after")
    def _enforce_fail_closed(self) -> ShadowComparison:
        # 1. Reasons consistency: a match carries no reasons; every other
        #    bucket carries at least one typed reason.
        if self.bucket is ShadowBucket.MATCH and self.reasons:
            raise ValueError("a match comparison row must not carry reasons")
        if self.bucket is not ShadowBucket.MATCH and not self.reasons:
            raise ValueError(
                f"bucket {self.bucket.value!r} requires at least one typed reason"
            )

        # 2. Bucket <-> condition-flag consistency.
        if self.bucket is ShadowBucket.STALE_PROJECTION and not self.stale_projection:
            raise ValueError(
                "stale_projection bucket requires stale_projection=True"
            )
        if self.stale_projection and self.bucket is not ShadowBucket.STALE_PROJECTION:
            raise ValueError(
                "a stale projection must land in the stale_projection bucket"
            )
        if self.bucket is ShadowBucket.MISSING_DENOMINATOR and not self.missing_denominator:
            raise ValueError(
                "missing_denominator bucket requires missing_denominator=True"
            )
        if self.missing_denominator and self.bucket is not ShadowBucket.MISSING_DENOMINATOR:
            raise ValueError(
                "a missing required denominator must land in the "
                "missing_denominator bucket"
            )
        if self.digest_mismatch and self.bucket is not ShadowBucket.UNEXPLAINED_DIFFERENCE:
            raise ValueError(
                "a projection digest mismatch must land in the "
                "unexplained_difference bucket"
            )

        # 3. Fail-closed promotion: green/dispatchable/terminal require a match
        #    on an eligible envelope with a legacy verdict that agrees.
        if self.green and not (
            self.bucket is ShadowBucket.MATCH
            and self.envelope_eligible
            and self.envelope_green
            and self.legacy_green
        ):
            raise ValueError("green requires a match on an eligible, agreeing envelope")
        if self.dispatchable and not (
            self.bucket is ShadowBucket.MATCH
            and self.envelope_eligible
            and self.envelope_dispatchable
            and self.legacy_dispatchable
        ):
            raise ValueError(
                "dispatchable requires a match on an eligible, agreeing envelope"
            )
        if self.terminal and not (
            self.bucket is ShadowBucket.MATCH
            and self.envelope_eligible
            and self.envelope_terminal
            and self.legacy_terminal
        ):
            raise ValueError("terminal requires a match on an eligible, agreeing envelope")

        # 4. Coverage consistency: a present denominator+count with a non-zero
        #    denominator must equal the reported coverage.
        if (
            self.denominator is not None
            and self.covered_count is not None
            and self.denominator != 0
            and self.coverage is not None
        ):
            expected = self.covered_count / self.denominator
            if abs(self.coverage - expected) > 1e-12:
                raise ValueError(
                    "coverage must equal covered_count / denominator when both "
                    "are present with a non-zero denominator"
                )
        return self

    @property
    def digest(self) -> str:
        """Canonical digest of the whole comparison row (replayable)."""
        return canonical_digest(self)


# ---------------------------------------------------------------------------
# The comparator (pure, read-only, deterministic)
# ---------------------------------------------------------------------------


def compare_shadow(
    legacy: LegacyResult | Mapping[str, Any],
    envelope: ObservationEnvelope,
    *,
    projection: Any | None = None,
    expected_source_digest: str | None = None,
    require_denominator: bool = False,
) -> ShadowComparison:
    """Compare a legacy consumer result to a coherent Maintenance envelope.

    Every call returns exactly one :class:`ShadowComparison` row assigned to
    exactly one of the six :class:`ShadowBucket` values, with explicit
    envelope/projection digests, coverage denominator, derived coverage, and
    legacy hash.  The interpretation is fail-closed: UNKNOWN/PARTIAL/INCOHERENT
    completeness or coherence, STALE/UNKNOWN freshness, cross-environment
    evidence, a stale projection, a projection source-digest mismatch, or a
    missing required denominator can never yield green/dispatchable/terminal.

    * ``legacy`` — the normalized legacy verdict (``LegacyResult`` or a mapping
      with ``green`` / ``dispatchable`` / ``terminal``).
    * ``envelope`` — the :class:`ObservationEnvelope` produced by the coherent
      join (T9); the comparator never authorizes either side.
    * ``projection`` — optional T13 projection snapshot (duck-typed:
      ``freshness``, ``source_digest``, ``output_digest``,
      ``coverage_denominator``, ``covered_count``, ``projection``).
    * ``expected_source_digest`` — when supplied, the projection source digest
      must equal it; any mismatch (or an absent projection/digest) is a
      non-green digest mismatch.
    * ``require_denominator`` — when ``True``, an absent coverage denominator
      lands the row in the ``missing_denominator`` bucket.

    The function performs no mutation and no dispatch; it is a pure function of
    its inputs (same inputs -> same row digest).
    """
    legacy_model = _coerce_legacy(legacy)
    meta = _projection_metadata(projection)

    envelope_eligible = envelope.is_eligible
    envelope_green = bool(envelope.green) and envelope_eligible
    envelope_dispatchable = bool(envelope.dispatchable) and envelope_eligible
    envelope_terminal = bool(envelope.terminal) and envelope_eligible
    envelope_reasons = tuple(reason.value for reason in envelope.coherence_reasons)

    # Projection gates, computed in dominance order so exactly one gate can
    # fire: a stale projection dominates (the projection is unusable), then a
    # missing required denominator (the comparison cannot be formed), then a
    # projection source-digest mismatch (the projection is not the expected
    # one).  A gate subsumed by a stronger one stays False — the row's bucket
    # names the single gate that decided it.
    stale_projection = (
        projection is not None and meta["freshness"] in _NON_FRESH_PROJECTION
    )
    missing_denominator = bool(
        require_denominator
        and meta["denominator"] is None
        and not stale_projection
    )
    digest_mismatch = (
        expected_source_digest is not None
        and not stale_projection
        and not missing_denominator
        and (
            projection is None
            or meta["source_digest"] is None
            or meta["source_digest"] != expected_source_digest
        )
    )

    # Deterministic bucketing: exactly one bucket per row.  Projection gates
    # dominate (a missing required denominator means the comparison cannot be
    # formed at all; a digest mismatch means the projection is not the expected
    # one), then the envelope-eligibility gate, then verdict agreement.
    if stale_projection:
        bucket = ShadowBucket.STALE_PROJECTION
        reasons = ("stale_projection",) + envelope_reasons
    elif missing_denominator:
        bucket = ShadowBucket.MISSING_DENOMINATOR
        reasons = ("missing_denominator",) + envelope_reasons
    elif digest_mismatch:
        bucket = ShadowBucket.UNEXPLAINED_DIFFERENCE
        reasons = ("digest_mismatch",) + envelope_reasons
    elif not envelope_eligible:
        if legacy_model.green or legacy_model.dispatchable:
            bucket = ShadowBucket.WOULD_BLOCK
            reasons = ("would_block",) + envelope_reasons
        else:
            bucket = ShadowBucket.EXPLAINED_DIFFERENCE
            reasons = tuple(envelope_reasons) or ("envelope_not_eligible",)
    elif (
        legacy_model.green == envelope_green
        and legacy_model.dispatchable == envelope_dispatchable
    ):
        bucket = ShadowBucket.MATCH
        reasons = ()
    elif not (
        legacy_model.green or legacy_model.dispatchable or legacy_model.terminal
    ) and (envelope_green or envelope_dispatchable or envelope_terminal):
        # Known conservative legacy non-promotion (REVIEW-CHECK_SHADOW_BUCKET-
        # 001): the legacy verdict declines to promote in every dimension while
        # the eligible envelope would promote.  The difference is deterministic
        # and typed, so the row is explained — never green/dispatchable, and
        # never labeled unexplained.
        bucket = ShadowBucket.EXPLAINED_DIFFERENCE
        reasons = ("legacy_conservative_non_promotion",)
    else:
        bucket = ShadowBucket.UNEXPLAINED_DIFFERENCE
        reasons = ("verdict_disagreement",)

    green = (
        bucket is ShadowBucket.MATCH
        and envelope_eligible
        and envelope_green
        and legacy_model.green
    )
    dispatchable = (
        bucket is ShadowBucket.MATCH
        and envelope_eligible
        and envelope_dispatchable
        and legacy_model.dispatchable
    )
    terminal = (
        bucket is ShadowBucket.MATCH
        and envelope_eligible
        and envelope_terminal
        and legacy_model.terminal
    )

    legacy_hash = hashlib.sha256(
        canonical_dumps(legacy_model).encode("utf-8")
    ).hexdigest()

    return ShadowComparison(
        schema_version=MAINTENANCE_SCHEMA_VERSION,
        bucket=bucket,
        reasons=reasons,
        legacy_green=legacy_model.green,
        legacy_dispatchable=legacy_model.dispatchable,
        legacy_terminal=legacy_model.terminal,
        envelope_eligible=envelope_eligible,
        envelope_green=envelope_green,
        envelope_dispatchable=envelope_dispatchable,
        envelope_terminal=envelope_terminal,
        cross_environment=envelope.cross_environment,
        green=green,
        dispatchable=dispatchable,
        terminal=terminal,
        envelope_digest=canonical_digest(envelope),
        legacy_hash=legacy_hash,
        projection_name=meta["name"],
        projection_source_digest=meta["source_digest"],
        projection_output_digest=meta["output_digest"],
        denominator=meta["denominator"],
        covered_count=meta["covered_count"],
        coverage=_derived_coverage(meta["denominator"], meta["covered_count"]),
        stale_projection=stale_projection,
        digest_mismatch=digest_mismatch,
        missing_denominator=missing_denominator,
    )


__all__ = [
    "LegacyResult",
    "SHADOW_BUCKETS",
    "ShadowBucket",
    "ShadowComparison",
    "compare_shadow",
]
