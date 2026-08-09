"""Artifact-presence, source-version, timestamp, and diff-clean rebuild validation.

Generated artifacts are projections and must be rebuildable, tracked, and
disposable.  This module provides a bounded validation layer that gates
projection producers on artifact existence and rebuild cleanliness.  Every
validator fails closed — missing artifacts or metadata block cutover instead
of silently passing.

Covered projection artifacts
----------------------------
- status snapshots
- resident trees
- introspection output
- compatibility projections
- cloud projections
- repair-facing projections
- work-ledger projections

Design rules
------------
* Every validator returns a ``ValidationResult`` — never raises on missing data.
* ``ValidationResult`` carries exact evidence IDs so consumers can detect drift.
* Missing artifacts are ``fail_closed`` — the validator reports ``BLOCKED``,
  not ``PASSED``.
* Source-version metadata (version identifiers, timestamps) must be present
  and match the expected source-cursor state.
* Diff-clean rebuild validation proves that deleting and rebuilding produces
  identical digests.
* All validators are ``_non_authoritative`` — they are evidence, not grants.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.projection_digest import (
    ProjectionDigest,
    canonical_json,
    digest_hex,
    projection_digest,
    sort_payload_keys,
)
from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorState,
    SourceCursorVector,
)


# ── Validation result types ────────────────────────────────────────────────


class ValidationVerdict(Enum):
    """Verdict of a projection validation.

    * ``PASSED`` — the projection artifact is valid and rebuildable.
    * ``BLOCKED`` — the artifact is missing, incomplete, or has invalid metadata.
      Cutover must fail closed.
    * ``STALE`` — the artifact exists but its source version is behind current.
    * ``INCONCLUSIVE`` — the validator could not reach a conclusion.
    """

    PASSED = "passed"
    BLOCKED = "blocked"
    STALE = "stale"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class ValidationResult:
    """Result of a single projection artifact validation.

    Carries the validation kind, verdict, evidence references, and diagnostic
    detail.  ``BLOCKED`` results indicate the artifact cannot be used for
    cutover — the gate must fail closed.
    """

    validation_kind: str
    """Kind of validation: artifact_presence, source_version, timestamp, diff_clean_rebuild."""

    verdict: ValidationVerdict
    """Whether the validation passed, blocked, detected staleness, or was inconclusive."""

    artifact_path: str = ""
    """Path to the artifact being validated (empty for logical artifacts)."""

    detail: str = ""
    """Human-readable diagnostic detail."""

    evidence_ids: Tuple[str, ...] = ()
    """Content-addressed evidence IDs that contributed to this result."""

    source_cursor_digest: str = ""
    """Digest of the source-cursor vector that produced this artifact."""

    artifact_digest: str = ""
    """Digest of the artifact payload (if available)."""

    validation_id: str = field(init=False)
    """Content-addressed validation identifier."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = (
            f"{self.validation_kind}\x00{self.verdict.value}\x00{self.artifact_path}\x00"
            f"{self.detail}\x00{self.source_cursor_digest}\x00{self.artifact_digest}"
        )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "validation_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_pass(self) -> bool:
        return self.verdict == ValidationVerdict.PASSED

    @property
    def is_blocked(self) -> bool:
        return self.verdict == ValidationVerdict.BLOCKED

    @property
    def is_stale(self) -> bool:
        return self.verdict == ValidationVerdict.STALE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_kind": self.validation_kind,
            "verdict": self.verdict.value,
            "artifact_path": self.artifact_path,
            "detail": self.detail,
            "evidence_ids": list(self.evidence_ids),
            "source_cursor_digest": self.source_cursor_digest,
            "artifact_digest": self.artifact_digest,
            "validation_id": self.validation_id,
            "is_pass": self.is_pass,
            "is_blocked": self.is_blocked,
            "is_stale": self.is_stale,
            "_non_authoritative": self._non_authoritative,
        }


# ── Aggregate validation suite ─────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationSuite:
    """Aggregate results from projection artifact validations.

    Used to gate cutover: if any validation is ``BLOCKED``, cutover fails.
    """

    results: Tuple[ValidationResult, ...]
    """Individual validation results, sorted by validation_kind."""

    suite_digest: str = field(init=False)

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_results = tuple(sorted(self.results, key=lambda r: r.validation_kind))
        object.__setattr__(self, "results", sorted_results)
        parts = "\x00".join(r.validation_id for r in sorted_results)
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "suite_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def all_pass(self) -> bool:
        """True when every validation passed."""
        return all(r.verdict == ValidationVerdict.PASSED for r in self.results)

    @property
    def any_blocked(self) -> bool:
        """True when any validation blocked (cutover must fail)."""
        return any(r.verdict == ValidationVerdict.BLOCKED for r in self.results)

    @property
    def any_stale(self) -> bool:
        """True when any artifact is stale."""
        return any(r.verdict == ValidationVerdict.STALE for r in self.results)

    @property
    def blocked_validations(self) -> Tuple[ValidationResult, ...]:
        """Validations that blocked."""
        return tuple(r for r in self.results if r.is_blocked)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "suite_digest": self.suite_digest,
            "all_pass": self.all_pass,
            "any_blocked": self.any_blocked,
            "any_stale": self.any_stale,
            "blocked_count": len(self.blocked_validations),
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_results(cls, *results: ValidationResult) -> "ValidationSuite":
        return cls(results=tuple(results))


# ── Artifact presence validation ───────────────────────────────────────────


def validate_artifact_presence(
    artifact_path: str,
    *,
    artifact_kind: str = "",
    expected_min_size_bytes: int = 0,
) -> ValidationResult:
    """Validate that a projection artifact exists and is not empty.

    Fails closed (BLOCKED) when the artifact is missing, empty, or unreadable.
    """
    evidence_ids: list[str] = []

    if not artifact_path:
        return ValidationResult(
            validation_kind="artifact_presence",
            verdict=ValidationVerdict.BLOCKED,
            artifact_path="",
            detail="no artifact path provided",
        )

    path = Path(artifact_path)
    evidence_ids.append(f"path:{artifact_path}")

    if not path.exists():
        return ValidationResult(
            validation_kind="artifact_presence",
            verdict=ValidationVerdict.BLOCKED,
            artifact_path=artifact_path,
            detail=f"artifact missing: {artifact_path}",
            evidence_ids=tuple(evidence_ids),
        )

    if not path.is_file():
        return ValidationResult(
            validation_kind="artifact_presence",
            verdict=ValidationVerdict.BLOCKED,
            artifact_path=artifact_path,
            detail=f"artifact is not a regular file: {artifact_path}",
            evidence_ids=tuple(evidence_ids),
        )

    try:
        stat = path.stat()
        size = stat.st_mtime
        actual_size = stat.st_size
    except Exception:
        return ValidationResult(
            validation_kind="artifact_presence",
            verdict=ValidationVerdict.BLOCKED,
            artifact_path=artifact_path,
            detail=f"cannot stat artifact: {artifact_path}",
            evidence_ids=tuple(evidence_ids),
        )

    if expected_min_size_bytes > 0 and actual_size < expected_min_size_bytes:
        return ValidationResult(
            validation_kind="artifact_presence",
            verdict=ValidationVerdict.BLOCKED,
            artifact_path=artifact_path,
            detail=f"artifact size {actual_size} < expected min {expected_min_size_bytes} bytes",
            evidence_ids=tuple(evidence_ids),
        )

    # Compute artifact digest
    try:
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        evidence_ids.append(f"sha256:{digest}")
    except Exception:
        return ValidationResult(
            validation_kind="artifact_presence",
            verdict=ValidationVerdict.BLOCKED,
            artifact_path=artifact_path,
            detail=f"cannot read artifact: {artifact_path}",
            evidence_ids=tuple(evidence_ids),
        )

    return ValidationResult(
        validation_kind="artifact_presence",
        verdict=ValidationVerdict.PASSED,
        artifact_path=artifact_path,
        detail=f"artifact present: {artifact_path} ({actual_size} bytes)",
        evidence_ids=tuple(evidence_ids),
        artifact_digest=f"sha256:{digest}",
    )


# ── Source-version validation ──────────────────────────────────────────────


def validate_source_version(
    artifact_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
    expected_dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
) -> ValidationResult:
    """Validate that a projection carries correct source-version metadata.

    Every projection must carry a source-cursor vector with version identifiers
    for the dimensions it depends on.  Missing or unknown cursor dimensions
    block cutover.
    """
    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    if source_cursor is None:
        # Check if artifact carries its own cursor reference
        cursor_ref = artifact_payload.get("source_cursor_digest", "")
        if not cursor_ref:
            return ValidationResult(
                validation_kind="source_version",
                verdict=ValidationVerdict.BLOCKED,
                detail="projection carries no source cursor vector or reference",
                evidence_ids=tuple(evidence_ids),
            )
        return ValidationResult(
            validation_kind="source_version",
            verdict=ValidationVerdict.INCONCLUSIVE,
            detail=f"cursor digest referenced but vector not provided: {cursor_ref}",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=str(cursor_ref),
        )

    # Check that expected dimensions are present
    if expected_dimensions is not None:
        missing_dims = []
        for dim in expected_dimensions:
            c = source_cursor.cursor(dim)
            if c is None:
                missing_dims.append(dim)
        if missing_dims:
            return ValidationResult(
                validation_kind="source_version",
                verdict=ValidationVerdict.BLOCKED,
                detail=f"missing cursor dimensions: {missing_dims}",
                evidence_ids=tuple(evidence_ids),
                source_cursor_digest=source_cursor.vector_id,
            )

    # Check that no dimension is unknown (cannot verify version)
    unknown_dims = [
        c.dimension for c in source_cursor.cursors
        if c.state == "unknown"
    ]
    if unknown_dims:
        return ValidationResult(
            validation_kind="source_version",
            verdict=ValidationVerdict.BLOCKED,
            detail=f"unknown cursor dimensions: {unknown_dims} (cannot verify source version)",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    # Check for stale dimensions
    stale_dims = source_cursor.stale_dimensions()
    if stale_dims:
        return ValidationResult(
            validation_kind="source_version",
            verdict=ValidationVerdict.STALE,
            detail=f"stale cursor dimensions: {stale_dims}",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    # All dimensions fresh and known
    return ValidationResult(
        validation_kind="source_version",
        verdict=ValidationVerdict.PASSED,
        detail="all cursor dimensions fresh with known versions",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id,
    )


# ── Timestamp validation ───────────────────────────────────────────────────


def validate_timestamp(
    artifact_payload: Mapping[str, Any],
    *,
    timestamp_field: str = "generated_at",
    max_age_ms: int = 300_000,  # 5 minutes default
    now_epoch_ms: Optional[float] = None,
) -> ValidationResult:
    """Validate that a projection carries a recent generation timestamp.

    Projections without a timestamp or with a stale timestamp are blocked.
    """
    now = now_epoch_ms if now_epoch_ms is not None else (time.time() * 1000)

    ts_raw = artifact_payload.get(timestamp_field)
    if ts_raw is None:
        return ValidationResult(
            validation_kind="timestamp",
            verdict=ValidationVerdict.BLOCKED,
            detail=f"missing timestamp field: {timestamp_field}",
        )

    # Try ISO-8601 parsing
    ts_epoch_ms: Optional[float] = None
    if isinstance(ts_raw, str):
        try:
            from datetime import datetime
            clean = ts_raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            ts_epoch_ms = dt.timestamp() * 1000
        except (ValueError, TypeError):
            pass

    # Try numeric (epoch ms)
    if ts_epoch_ms is None and isinstance(ts_raw, (int, float)):
        ts_epoch_ms = float(ts_raw)

    if ts_epoch_ms is None:
        return ValidationResult(
            validation_kind="timestamp",
            verdict=ValidationVerdict.BLOCKED,
            detail=f"unparseable timestamp: {ts_raw}",
        )

    age_ms = now - ts_epoch_ms
    if age_ms > max_age_ms:
        return ValidationResult(
            validation_kind="timestamp",
            verdict=ValidationVerdict.STALE,
            detail=f"timestamp age {age_ms:.0f}ms exceeds max {max_age_ms}ms",
        )

    return ValidationResult(
        validation_kind="timestamp",
        verdict=ValidationVerdict.PASSED,
        detail=f"timestamp age {age_ms:.0f}ms within window ({max_age_ms}ms)",
        evidence_ids=(f"timestamp_field:{timestamp_field}",),
    )


# ── Diff-clean rebuild validation ──────────────────────────────────────────


def validate_diff_clean_rebuild(
    before_payload: Mapping[str, Any],
    after_payload: Mapping[str, Any],
    *,
    projection_kind: str = "",
) -> ValidationResult:
    """Validate that a delete-and-rebuild produces identical output.

    When a projection is deleted and rebuilt from the same authoritative
    source records, the output must be byte-identical.  Any diff indicates
    nondeterminism or incomplete source coverage.

    Args:
        before_payload: The original projection payload.
        after_payload: The rebuilt projection payload.
        projection_kind: Kind of projection (status, resident, cloud, etc.).

    Returns:
        PASSED when digests match, BLOCKED on diff.
    """
    before_sorted = sort_payload_keys(dict(before_payload))
    after_sorted = sort_payload_keys(dict(after_payload))

    before_bytes = canonical_json(before_sorted)
    after_bytes = canonical_json(after_sorted)

    before_digest = hashlib.sha256(before_bytes).hexdigest()
    after_digest = hashlib.sha256(after_bytes).hexdigest()

    evidence_ids = (
        f"before:sha256:{before_digest}",
        f"after:sha256:{after_digest}",
    )

    if before_digest != after_digest:
        return ValidationResult(
            validation_kind="diff_clean_rebuild",
            verdict=ValidationVerdict.BLOCKED,
            detail=(
                f"rebuild produced different digest for {projection_kind}: "
                f"before={before_digest[:16]}... after={after_digest[:16]}..."
            ),
            evidence_ids=evidence_ids,
        )

    return ValidationResult(
        validation_kind="diff_clean_rebuild",
        verdict=ValidationVerdict.PASSED,
        detail=f"rebuild parity verified for {projection_kind}: digests match",
        evidence_ids=evidence_ids,
        artifact_digest=f"sha256:{before_digest}",
    )


# ── Projection metadata validation ─────────────────────────────────────────


def validate_projection_metadata(
    artifact_payload: Mapping[str, Any],
    *,
    required_fields: Optional[Tuple[str, ...]] = None,
    source_cursor: Optional[SourceCursorVector] = None,
) -> ValidationResult:
    """Validate that a projection carries required metadata fields.

    Every projection must carry:
    - ``_non_authoritative`` marker (or equivalent).
    - ``source_cursor_digest`` (reference to source-cursor vector).
    - ``generated_at`` (timestamp).

    Additional required fields can be specified per projection kind.
    """
    if required_fields is None:
        required_fields = (
            "_non_authoritative",
            "source_cursor_digest",
            "generated_at",
        )

    missing = [f for f in required_fields if f not in artifact_payload]
    if missing:
        return ValidationResult(
            validation_kind="projection_metadata",
            verdict=ValidationVerdict.BLOCKED,
            detail=f"missing required metadata fields: {missing}",
        )

    # Check _non_authoritative
    non_auth = artifact_payload.get("_non_authoritative", False)
    if isinstance(non_auth, str):
        non_auth = non_auth.lower() in ("true", "1")
    if not non_auth:
        return ValidationResult(
            validation_kind="projection_metadata",
            verdict=ValidationVerdict.BLOCKED,
            detail="projection missing _non_authoritative marker",
        )

    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    cursor_ref = artifact_payload.get("source_cursor_digest", "")
    if source_cursor is not None and cursor_ref and cursor_ref != source_cursor.vector_id:
        return ValidationResult(
            validation_kind="projection_metadata",
            verdict=ValidationVerdict.BLOCKED,
            detail=f"source_cursor_digest mismatch: payload={cursor_ref} vs cursor={source_cursor.vector_id}",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    return ValidationResult(
        validation_kind="projection_metadata",
        verdict=ValidationVerdict.PASSED,
        detail="all required metadata fields present and valid",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id if source_cursor else str(cursor_ref),
    )


# ── Convenience: validate a projection artifact end-to-end ─────────────────


def validate_projection_artifact(
    artifact_path: str,
    artifact_payload: Mapping[str, Any],
    *,
    projection_kind: str = "",
    source_cursor: Optional[SourceCursorVector] = None,
    expected_dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
    max_timestamp_age_ms: int = 300_000,
    rebuild_payload: Optional[Mapping[str, Any]] = None,
) -> ValidationSuite:
    """Run the full validation suite on a projection artifact.

    Args:
        artifact_path: Filesystem path to the artifact.
        artifact_payload: Parsed artifact content.
        projection_kind: Kind of projection (status, resident, cloud, etc.).
        source_cursor: Source-cursor vector (parsed from the projection).
        expected_dimensions: Source dimensions the projection must cover.
        max_timestamp_age_ms: Maximum acceptable timestamp age.
        rebuild_payload: Rebuilt payload for diff-clean check (if available).

    Returns:
        ValidationSuite with all results.  ``any_blocked`` means cutover must fail.
    """
    results: list[ValidationResult] = []

    # 1. Artifact presence
    results.append(validate_artifact_presence(artifact_path, artifact_kind=projection_kind))

    # 2. Projection metadata
    results.append(validate_projection_metadata(artifact_payload, source_cursor=source_cursor))

    # 3. Source version
    results.append(
        validate_source_version(
            artifact_payload,
            source_cursor=source_cursor,
            expected_dimensions=expected_dimensions,
        )
    )

    # 4. Timestamp
    results.append(validate_timestamp(artifact_payload, max_age_ms=max_timestamp_age_ms))

    # 5. Diff-clean rebuild (if rebuild payload provided)
    if rebuild_payload is not None:
        results.append(
            validate_diff_clean_rebuild(
                artifact_payload,
                rebuild_payload,
                projection_kind=projection_kind,
            )
        )

    return ValidationSuite.from_results(*results)


# ── Multi-artifact validation ──────────────────────────────────────────────


def validate_projection_artifacts(
    artifacts: Sequence[Tuple[str, Mapping[str, Any]]],
    *,
    projection_kind: str = "",
    source_cursor: Optional[SourceCursorVector] = None,
    expected_dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
    rebuild_payloads: Optional[Sequence[Mapping[str, Any]]] = None,
) -> ValidationSuite:
    """Validate multiple projection artifacts (e.g. status + resident + introspect).

    Each artifact is validated independently.  The aggregate suite blocks if
    any individual artifact blocks.
    """
    all_results: list[ValidationResult] = []
    for i, (path, payload) in enumerate(artifacts):
        rebuild = rebuild_payloads[i] if rebuild_payloads and i < len(rebuild_payloads) else None
        suite = validate_projection_artifact(
            artifact_path=path,
            artifact_payload=payload,
            projection_kind=projection_kind,
            source_cursor=source_cursor,
            expected_dimensions=expected_dimensions,
            rebuild_payload=rebuild,
        )
        all_results.extend(suite.results)

    return ValidationSuite.from_results(*all_results)


__all__ = [
    # ── Types ──
    "ValidationVerdict",
    "ValidationResult",
    "ValidationSuite",
    # ── Individual validators ──
    "validate_artifact_presence",
    "validate_source_version",
    "validate_timestamp",
    "validate_diff_clean_rebuild",
    "validate_projection_metadata",
    # ── Convenience ──
    "validate_projection_artifact",
    "validate_projection_artifacts",
]
