"""Strict schema-parity primitives for structured output (Step 6).

This module hashes and compares the eight structured-output schema phases
that a handler pipeline touches: prompt, materialization, scratch,
parser, capture, handler, receipt, and replay.

Every comparison is *fail-closed*: a missing field, an unknown field,
silent defaulting, type inference, field stripping, schema
reconstruction, or a hash drift raises :class:`SchemaParityError`.  No
parity check ever silently accepts a divergent schema — the whole point
of a content-addressed schema hash is that the *exact* declaration is
the only acceptable match.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, MutableMapping

__all__ = [
    "SCHEMA_PHASES",
    "SchemaParityError",
    "canonicalize_schema",
    "schema_hash",
    "canonical_schema_hash",
    "compare_schema_fields",
    "assert_schema_field_parity",
    "verify_schema_hash",
    "SchemaParityReport",
    "compute_full_parity_report",
]

#: The eight structured-output schema phases tracked end-to-end.
SCHEMA_PHASES = (
    "prompt",
    "materialization",
    "scratch",
    "parser",
    "capture",
    "handler",
    "receipt",
    "replay",
)

#: Sentinel used to detect that a value was never declared.  ``None`` is a
#: legitimate schema value, so we cannot use it as "missing".
_MISSING = object()


class SchemaParityError(ValueError):
    """Raised when a structured-output schema diverges from its declaration.

    The :attr:`phase` and :attr:`reason` attributes let callers record
    durable, machine-readable evidence of *why* the parity check refused.
    """

    def __init__(self, phase: str, reason: str, *, detail: Mapping[str, Any] | None = None):
        self.phase = phase
        self.reason = reason
        self.detail = dict(detail or {})
        super().__init__(f"schema parity failure [{phase}]: {reason}")


# ── canonicalization ──────────────────────────────────────────────────────

def canonicalize_schema(schema: Any) -> bytes:
    """Return deterministic canonical bytes for *schema*.

    Ordering is normalized (``sort_keys=True``) and whitespace is stripped
    so semantically identical schemas hash identically regardless of how
    they were serialized.  ``NaN``/``Infinity`` tokens are rejected
    because they are non-portable and would produce platform-dependent
    hashes.
    """
    if schema is None:
        raise SchemaParityError("?", "schema is None (reconstruction is forbidden)")
    try:
        raw = json.dumps(
            schema,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SchemaParityError("?", f"schema is not JSON-serializable: {exc}") from exc
    return raw.encode("utf-8")


def schema_hash(schema: Any) -> str:
    """SHA-256 hex digest of the canonical form of *schema*."""
    return hashlib.sha256(canonicalize_schema(schema)).hexdigest()


#: Alias matching the plan's wording ("hash and compare").
canonical_schema_hash = schema_hash


# ── field-level comparison ────────────────────────────────────────────────

def compare_schema_fields(
    declared: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> list[str]:
    """Return the list of divergence reasons between two schema field maps.

    An empty list means the two maps are *field-for-field* identical.  No
    defaulting, inference, stripping, or reconstruction is tolerated:

    * a key present in *declared* but absent from *observed* → ``missing``
    * a key present in *observed* but absent from *declared* → ``unknown``
    * a value that differs → ``drift``
    """
    if not isinstance(declared, Mapping):
        raise SchemaParityError("?", "declared schema is not a mapping")
    if not isinstance(observed, Mapping):
        raise SchemaParityError("?", "observed schema is not a mapping")

    reasons: list[str] = []
    for key in declared:
        if key not in observed:
            reasons.append(f"missing:{key}")
    for key in observed:
        if key not in declared:
            reasons.append(f"unknown:{key}")
    for key in declared:
        if key in observed and declared[key] != observed[key]:
            reasons.append(f"drift:{key}")
    return reasons


def assert_schema_field_parity(
    declared: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    phase: str,
) -> None:
    """Raise :class:`SchemaParityError` unless *observed* matches *declared*.

    This rejects missing fields, unknown fields, and value drift.  Because
    the comparison is exact, defaulting and type inference are impossible:
    a producer that omits a field (relying on a default) is flagged as
    ``missing``, and a producer that strips a field before emitting is
    likewise flagged.  Reconstruction is impossible because the caller
    must supply the *exact* declared schema — no inferred defaults are
    synthesized.
    """
    reasons = compare_schema_fields(declared, observed)
    if reasons:
        raise SchemaParityError(
            phase,
            "field divergence: " + ", ".join(reasons),
            detail={"reasons": reasons, "declared_keys": sorted(declared), "observed_keys": sorted(observed)},
        )


# ── hash verification ─────────────────────────────────────────────────────

def verify_schema_hash(
    declared_hash: str,
    observed_schema: Any,
    *,
    phase: str,
) -> str:
    """Verify *observed_schema* hashes exactly to *declared_hash*.

    Returns the computed hash on success (so callers can persist it).
    Raises :class:`SchemaParityError` on any drift, including a missing
    or malformed declared hash (which is treated as reconstruction and
    refused).
    """
    declared = str(declared_hash or "").strip().lower()
    if not declared:
        raise SchemaParityError(phase, "declared schema hash is missing (reconstruction forbidden)")
    observed = schema_hash(observed_schema)
    if observed != declared:
        raise SchemaParityError(
            phase,
            "schema hash drift",
            detail={"declared_hash": declared, "observed_hash": observed},
        )
    return observed


# ── multi-phase report ────────────────────────────────────────────────────

class SchemaParityReport:
    """Aggregated parity verdict across the eight structured-output phases.

    Each phase maps to either a declared hash (matched) or ``None``
    (undeclared / not applicable).  :meth:`is_satisfied` is true only
    when every *declared* phase hash matches its observed schema with no
    drift and no reconstruction.
    """

    __slots__ = ("phase_hashes", "_observations", "_errors")

    def __init__(self) -> None:
        self.phase_hashes: dict[str, str | None] = {p: None for p in SCHEMA_PHASES}
        self._observations: dict[str, str | None] = {p: None for p in SCHEMA_PHASES}
        self._errors: dict[str, SchemaParityError] = {}

    def declare(self, phase: str, schema: Any) -> str:
        """Record the declared hash for *phase* and return it."""
        self._require_known_phase(phase)
        digest = schema_hash(schema)
        self.phase_hashes[phase] = digest
        return digest

    def observe_and_check(self, phase: str, observed_schema: Any) -> str:
        """Observe a schema for *phase* and verify it against the declaration."""
        self._require_known_phase(phase)
        declared = self.phase_hashes.get(phase)
        if declared is None:
            raise SchemaParityError(phase, "observed schema for undeclared phase (no reconstruction)")
        computed = verify_schema_hash(declared, observed_schema, phase=phase)
        self._observations[phase] = computed
        return computed

    def record_error(self, phase: str, error: SchemaParityError) -> None:
        self._errors[phase] = error

    @property
    def errors(self) -> Mapping[str, SchemaParityError]:
        return dict(self._errors)

    def is_satisfied(self) -> bool:
        """True iff every declared phase matched its observed schema exactly."""
        if self._errors:
            return False
        for phase in SCHEMA_PHASES:
            declared = self.phase_hashes.get(phase)
            if declared is None:
                continue
            if self._observations.get(phase) != declared:
                return False
        return True

    @staticmethod
    def _require_known_phase(phase: str) -> None:
        if phase not in SCHEMA_PHASES:
            raise SchemaParityError(str(phase), f"unknown schema phase (expected one of {SCHEMA_PHASES})")


def compute_full_parity_report(
    declared_by_phase: Mapping[str, Any],
    observed_by_phase: Mapping[str, Any],
) -> SchemaParityReport:
    """Build a :class:`SchemaParityReport` from declared/observed schema maps.

    Every phase in *declared_by_phase* is declared, then every phase in
    *observed_by_phase* is checked.  Unknown phases, missing observations
    for declared phases, and drift are all recorded as errors rather than
    raising, so callers can capture a full diagnostic snapshot.
    """
    report = SchemaParityReport()
    for phase, schema in declared_by_phase.items():
        if phase not in SCHEMA_PHASES:
            report.record_error(phase, SchemaParityError(phase, "unknown phase in declared set"))
            continue
        try:
            report.declare(phase, schema)
        except SchemaParityError as exc:
            report.record_error(phase, exc)
    for phase in report.phase_hashes:
        if report.phase_hashes[phase] is None:
            continue
        if phase not in observed_by_phase:
            report.record_error(phase, SchemaParityError(phase, "declared phase has no observation (missing)"))
            continue
        try:
            report.observe_and_check(phase, observed_by_phase[phase])
        except SchemaParityError as exc:
            report.record_error(phase, exc)
    return report
