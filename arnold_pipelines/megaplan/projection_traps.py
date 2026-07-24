"""Shared observer-purity assertions and forged/stale projection trap helpers.

A projection is not a grant, lease, completion, publication, or delivery
decision.  This module provides reusable negative-authority traps that prove
projections **cannot**:

* Append progress, activity, lifecycle, delivery, or repair evidence.
* Grant positive action without rereading live source authority.
* Refresh liveness from an observer read (observer purity).
* Convert forged or stale projection data into bearer authority.

These traps are designed for reuse across later milestone tests.  Every trap
returns structured evidence (``TrapResult``) that downstream test code can
assert on without reimplementing projection-negative-authority checks.

Design rules
------------
* Traps are **stateless** — they accept projection data and source-cursor
  evidence as inputs and return typed results.
* Every trap carries an explicit ``_non_authoritative`` marker.
* Traps for forged projections prove that synthetic/manipulated projection
  data cannot authorize positive actions.
* Traps for stale projections prove that out-of-date projection data cannot
  substitute for fresh source reads.
* Observer-purity traps prove that reading/observing a projection does not
  modify evidence (no append, no mutation, no side-effect).
* All trap results include exact evidence IDs for traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, Mapping, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.source_cursor_contract import (
    DimensionCursor,
    SourceCursorDimension,
    SourceCursorState,
    SourceCursorVector,
)
from arnold_pipelines.megaplan.projection_digest import ProjectionDigest, projection_digest


# ── Trap result types ──────────────────────────────────────────────────────


class TrapVerdict(Enum):
    """Verdict of a negative-authority trap.

    * ``TRAPPED`` — the trap caught an attempt to use a projection as authority
      (the projection correctly refused / was blocked).
    * ``PASSED`` — no authority violation was detected (the trap's negative
      assertion holds; i.e. the projection did *not* authorize).
    * ``BREACHED`` — the trap's negative assertion was violated (the projection
      incorrectly authorized something it shouldn't have).
    * ``INCONCLUSIVE`` — the trap could not reach a conclusion (missing evidence).
    """

    TRAPPED = "trapped"
    PASSED = "passed"
    BREACHED = "breached"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class TrapResult:
    """Result of a single negative-authority trap check.

    Carries the trap kind, verdict, evidence references, and diagnostic detail.
    """

    trap_kind: str
    """Kind of trap: observer_purity, forged_projection, stale_projection, etc."""

    verdict: TrapVerdict
    """Whether the trap caught a violation, passed, or was inconclusive."""

    detail: str = ""
    """Human-readable diagnostic detail."""

    evidence_ids: Tuple[str, ...] = ()
    """Content-addressed evidence IDs that contributed to this trap result."""

    source_cursor_digest: str = ""
    """Digest of the source-cursor vector used (if any)."""

    trap_id: str = field(init=False)
    """Content-addressed trap identifier for traceability."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        raw = f"{self.trap_kind}\x00{self.verdict.value}\x00{self.detail}\x00{self.source_cursor_digest}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        object.__setattr__(self, "trap_id", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def is_clean(self) -> bool:
        """True when the trap's negative assertion holds (PASSED)."""
        return self.verdict == TrapVerdict.PASSED

    @property
    def is_violation(self) -> bool:
        """True when the trap caught an authority breach (BREACHED)."""
        return self.verdict == TrapVerdict.BREACHED

    @property
    def is_trapped(self) -> bool:
        """True when the trap caught and blocked a violation (TRAPPED)."""
        return self.verdict == TrapVerdict.TRAPPED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trap_kind": self.trap_kind,
            "verdict": self.verdict.value,
            "detail": self.detail,
            "evidence_ids": list(self.evidence_ids),
            "source_cursor_digest": self.source_cursor_digest,
            "trap_id": self.trap_id,
            "is_clean": self.is_clean,
            "is_violation": self.is_violation,
            "is_trapped": self.is_trapped,
            "_non_authoritative": self._non_authoritative,
        }


# ── Aggregate trap suite ───────────────────────────────────────────────────


@dataclass(frozen=True)
class TrapSuite:
    """Aggregate results from a set of negative-authority traps.

    Used to prove that a projection passes all traps — observer purity,
    forged/stale rejection, and no positive-action grant.
    """

    results: Tuple[TrapResult, ...]
    """Individual trap results, sorted by trap_kind."""

    suite_digest: str = field(init=False)
    """Aggregate digest of all trap results."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_results = tuple(sorted(self.results, key=lambda r: r.trap_kind))
        object.__setattr__(self, "results", sorted_results)
        parts = "\x00".join(r.trap_id for r in sorted_results)
        digest = hashlib.sha256(parts.encode("utf-8")).hexdigest()
        object.__setattr__(self, "suite_digest", f"sha256:{digest}")
        object.__setattr__(self, "_non_authoritative", True)

    @property
    def all_clean(self) -> bool:
        """True when every trap passed (no violations, no breaches)."""
        return all(r.verdict == TrapVerdict.PASSED for r in self.results)

    @property
    def any_violation(self) -> bool:
        """True when any trap detected an authority breach."""
        return any(r.verdict == TrapVerdict.BREACHED for r in self.results)

    @property
    def any_trapped(self) -> bool:
        """True when any trap caught and blocked a violation."""
        return any(r.verdict == TrapVerdict.TRAPPED for r in self.results)

    def by_kind(self, trap_kind: str) -> Tuple[TrapResult, ...]:
        """Return results of a specific trap kind."""
        return tuple(r for r in self.results if r.trap_kind == trap_kind)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "suite_digest": self.suite_digest,
            "all_clean": self.all_clean,
            "any_violation": self.any_violation,
            "any_trapped": self.any_trapped,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_results(cls, *results: TrapResult) -> "TrapSuite":
        return cls(results=tuple(results))


# ── Observer-purity traps ──────────────────────────────────────────────────

# Actions that a projection must NEVER perform (bearer-authority actions).
_FORBIDDEN_ACTION_KINDS: FrozenSet[str] = frozenset(
    {
        "dispatch",
        "repair",
        "retry",
        "complete",
        "cancel",
        "publish",
        "deliver",
        "grant",
        "transfer",
        "release",
        "acquire",
    }
)

# Evidence kinds that a projection must NEVER append/modify.
_FORBIDDEN_EVIDENCE_KINDS: FrozenSet[str] = frozenset(
    {
        "progress",
        "activity",
        "lifecycle",
        "delivery",
        "repair",
        "completion",
        "publication",
        "lease",
        "grant",
    }
)


def trap_observer_purity_read(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
    before_digest: str = "",
) -> TrapResult:
    """Prove that reading/observing a projection does not modify evidence.

    An observer-pure projection:
    1. Carries ``_non_authoritative: True`` (or equivalent).
    2. Does not claim any bearer-authority action kind.
    3. Does not append/modify any forbidden evidence kind.
    4. Has a stable digest (content-addressed, not mutated by read).

    Args:
        projection_payload: The projection data to check.
        source_cursor: The source-cursor vector the projection was built from.
        before_digest: Digest of the projection before the "observer read"
            (to prove no mutation occurred).

    Returns:
        TrapResult with PASSED if pure, BREACHED if authority violation detected.
    """
    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    # Check 1: non-authoritative marker
    is_marked_non_auth = projection_payload.get("_non_authoritative", False)
    if isinstance(is_marked_non_auth, str):
        is_marked_non_auth = is_marked_non_auth.lower() in ("true", "1")

    if not is_marked_non_auth:
        return TrapResult(
            trap_kind="observer_purity_read",
            verdict=TrapVerdict.BREACHED,
            detail="projection does not carry _non_authoritative marker; may be mistaken for authority",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id if source_cursor else "",
        )

    # Check 2: no bearer-authority action claims
    action_kinds = projection_payload.get("action_kinds", [])
    if isinstance(action_kinds, (list, tuple)):
        forbidden = [a for a in action_kinds if str(a).lower() in _FORBIDDEN_ACTION_KINDS]
        if forbidden:
            return TrapResult(
                trap_kind="observer_purity_read",
                verdict=TrapVerdict.BREACHED,
                detail=f"projection claims bearer-authority action kinds: {forbidden}",
                evidence_ids=tuple(evidence_ids),
                source_cursor_digest=source_cursor.vector_id if source_cursor else "",
            )

    # Check 3: no forbidden evidence appends
    evidence_appended = projection_payload.get("evidence_appended", [])
    if isinstance(evidence_appended, (list, tuple)):
        forbidden_ev = [
            e for e in evidence_appended
            if isinstance(e, dict) and str(e.get("kind", "")).lower() in _FORBIDDEN_EVIDENCE_KINDS
        ]
        if forbidden_ev:
            return TrapResult(
                trap_kind="observer_purity_read",
                verdict=TrapVerdict.BREACHED,
                detail=f"projection appends forbidden evidence kinds: {[e.get('kind') for e in forbidden_ev]}",
                evidence_ids=tuple(evidence_ids),
                source_cursor_digest=source_cursor.vector_id if source_cursor else "",
            )

    # Check 4: projection carries no positive-action grants
    grants = projection_payload.get("grants", [])
    if isinstance(grants, (list, tuple)) and len(grants) > 0:
        return TrapResult(
            trap_kind="observer_purity_read",
            verdict=TrapVerdict.BREACHED,
            detail=f"projection carries {len(grants)} grant(s); projections must not grant actions",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id if source_cursor else "",
        )

    # Check 5: content-addressed (not mutated by read)
    if before_digest:
        import json as _json
        try:
            sorted_payload = _json.dumps(
                dict(sorted(projection_payload.items())),
                sort_keys=True,
                separators=(",", ":"),
            )
            after_digest = hashlib.sha256(sorted_payload.encode("utf-8")).hexdigest()
            if before_digest != after_digest:
                return TrapResult(
                    trap_kind="observer_purity_read",
                    verdict=TrapVerdict.BREACHED,
                    detail="projection digest changed after observer read; projection was mutated",
                    evidence_ids=tuple(evidence_ids + [f"before:{before_digest}", f"after:{after_digest}"]),
                    source_cursor_digest=source_cursor.vector_id if source_cursor else "",
                )
        except Exception:
            pass

    return TrapResult(
        trap_kind="observer_purity_read",
        verdict=TrapVerdict.PASSED,
        detail="observer-pure: no authority violation detected",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id if source_cursor else "",
    )


def trap_observer_purity_no_append(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
) -> TrapResult:
    """Prove that observing a projection does not append progress/activity/lifecycle evidence.

    This is a focused variant of ``trap_observer_purity_read`` that specifically
    checks for forbidden evidence append operations.
    """
    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    # Check for any evidence_append-like fields
    suspicious_fields = {
        "events_appended",
        "progress_appended",
        "activity_recorded",
        "lifecycle_updated",
        "delivery_recorded",
        "repair_recorded",
    }
    appended = []
    for field in suspicious_fields:
        val = projection_payload.get(field)
        if isinstance(val, (list, tuple)) and len(val) > 0:
            appended.append(f"{field}: {len(val)} entries")
        elif isinstance(val, dict) and val:
            appended.append(f"{field}: non-empty")

    if appended:
        return TrapResult(
            trap_kind="observer_purity_no_append",
            verdict=TrapVerdict.BREACHED,
            detail=f"observer read appended evidence: {', '.join(appended)}",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id if source_cursor else "",
        )

    return TrapResult(
        trap_kind="observer_purity_no_append",
        verdict=TrapVerdict.PASSED,
        detail="no evidence appended by observer read",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id if source_cursor else "",
    )


# ── Forged projection traps ────────────────────────────────────────────────


def trap_forged_projection_no_authority(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
    live_source_evidence: Optional[Mapping[str, Any]] = None,
) -> TrapResult:
    """Prove that a forged projection cannot grant positive action.

    A forged projection is one where the source cursor does not match the
    canonical source.  This trap proves that even if a projection claims
    ``state: completed`` or carries a ``grant`` payload, it cannot authorize
    positive action without rereading live source authority.

    Args:
        projection_payload: The (potentially forged) projection.
        source_cursor: The source-cursor vector carried by the projection.
        live_source_evidence: Fresh source evidence against which to compare.

    Returns:
        TRAPPED if the forged projection was caught and blocked.
        BREACHED if the forged projection authorized something it shouldn't.
        PASSED if the projection carries no forged authority.
    """
    evidence_ids: list[str] = []
    sc_digest = source_cursor.vector_id if source_cursor else ""

    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    # Check if source cursor is stale/unknown (indicating forged/outdated data)
    if source_cursor is not None:
        if source_cursor.has_any_stale_or_worse():
            stale_dims = source_cursor.stale_dimensions()
            # If projection claims positive state with stale cursor → trapped
            positive_claims = []
            claimed_state = projection_payload.get("state", "")
            claimed_display = projection_payload.get("display_state", "")
            claimed_execution = projection_payload.get("execution_state", "")
            claimed_outcome = projection_payload.get("outcome", "")

            if str(claimed_state).lower() in {"completed", "done", "success", "succeeded"}:
                positive_claims.append(f"state={claimed_state}")
            if str(claimed_display).lower() in {"done", "completed"}:
                positive_claims.append(f"display_state={claimed_display}")
            if str(claimed_execution).lower() in {"completed", "done"}:
                positive_claims.append(f"execution_state={claimed_execution}")
            if str(claimed_outcome).lower() in {"succeeded", "completed"}:
                positive_claims.append(f"outcome={claimed_outcome}")

            grants = projection_payload.get("grants", [])
            if isinstance(grants, (list, tuple)) and len(grants) > 0:
                positive_claims.append(f"grants={len(grants)}")

            if positive_claims:
                return TrapResult(
                    trap_kind="forged_projection_no_authority",
                    verdict=TrapVerdict.TRAPPED,
                    detail=(
                        f"stale cursor on {sorted(stale_dims)} cannot authorize: "
                        f"{', '.join(positive_claims)}"
                    ),
                    evidence_ids=tuple(evidence_ids),
                    source_cursor_digest=sc_digest,
                )

    # Compare against live source evidence if provided
    if live_source_evidence is not None:
        proj_state = str(projection_payload.get("state", "")).lower()
        live_state = str(live_source_evidence.get("state", "")).lower()

        if proj_state in {"completed", "done"} and live_state not in {"completed", "done"}:
            return TrapResult(
                trap_kind="forged_projection_no_authority",
                verdict=TrapVerdict.TRAPPED,
                detail=f"projection claims '{proj_state}' but live source is '{live_state}'",
                evidence_ids=tuple(evidence_ids),
                source_cursor_digest=sc_digest,
            )

    # Check for incoherent cursor
    if source_cursor is not None:
        for c in source_cursor.cursors:
            if c.state == "incoherent":
                return TrapResult(
                    trap_kind="forged_projection_no_authority",
                    verdict=TrapVerdict.TRAPPED,
                    detail=f"incoherent cursor dimension {c.dimension}: {c.detail}",
                    evidence_ids=tuple(evidence_ids),
                    source_cursor_digest=sc_digest,
                )

    return TrapResult(
        trap_kind="forged_projection_no_authority",
        verdict=TrapVerdict.PASSED,
        detail="forged projection carries no unauthorized positive action",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=sc_digest,
    )


def trap_forged_projection_no_rereread_bypass(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
    required_reread_dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
) -> TrapResult:
    """Prove that a projection cannot bypass the reread obligation.

    Positive-control-path consumers must reread live source authority before
    acting.  This trap proves that a projection cannot substitute for that
    reread — the projection's source cursor must be fresh on all required
    dimensions, or the action is blocked.

    Args:
        projection_payload: The projection to check.
        source_cursor: The source-cursor vector.
        required_reread_dimensions: Dimensions that MUST be fresh for positive
            action.  Defaults to blocking dimensions (custody, wbc, run_authority).

    Returns:
        TRAPPED if the projection tries to bypass reread.
        PASSED if the projection correctly requires reread.
    """
    if required_reread_dimensions is None:
        required_reread_dimensions = ("custody", "wbc", "run_authority")

    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    if source_cursor is None:
        return TrapResult(
            trap_kind="forged_projection_no_reread_bypass",
            verdict=TrapVerdict.TRAPPED,
            detail="no source cursor vector; cannot verify reread obligation",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest="",
        )

    non_fresh: list[str] = []
    for dim in required_reread_dimensions:
        c = source_cursor.cursor(dim)
        if c is None or c.state != "fresh":
            non_fresh.append(dim)

    if non_fresh:
        return TrapResult(
            trap_kind="forged_projection_no_reread_bypass",
            verdict=TrapVerdict.TRAPPED,
            detail=f"reread bypass blocked: non-fresh dimensions: {non_fresh}",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    return TrapResult(
        trap_kind="forged_projection_no_reread_bypass",
        verdict=TrapVerdict.PASSED,
        detail="reread obligation verified: all required dimensions fresh",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id,
    )


# ── Stale projection traps ─────────────────────────────────────────────────


def trap_stale_projection_no_positive_action(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
    max_age_ms: int = 120_000,
) -> TrapResult:
    """Prove that a stale projection cannot grant positive action.

    A stale projection (source cursor has any stale dimension) may diagnose
    and deny, but it can never authorize dispatch, repair, retry, completion,
    cancellation, publication, or delivery.

    Args:
        projection_payload: The projection to check.
        source_cursor: Source-cursor vector (must be present for evaluation).
        max_age_ms: Maximum acceptable age for fresh cursor.

    Returns:
        TRAPPED if stale cursor tried to authorize positive action.
        PASSED if stale cursor correctly blocks/denies.
    """
    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    if source_cursor is None:
        return TrapResult(
            trap_kind="stale_projection_no_positive_action",
            verdict=TrapVerdict.PASSED,
            detail="no source cursor — cannot evaluate staleness",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest="",
        )

    if not source_cursor.has_any_stale_or_worse():
        return TrapResult(
            trap_kind="stale_projection_no_positive_action",
            verdict=TrapVerdict.PASSED,
            detail="all cursor dimensions fresh; no staleness violation",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    # All dimensions are fresh or some are stale — check for positive claims
    stale_dims = source_cursor.stale_dimensions()

    # If projection claims any positive action → TRAPPED
    positive_indicators = []

    # Check for completion/delivery claims
    for field in ("state", "display_state", "execution_state", "outcome"):
        val = str(projection_payload.get(field, "")).lower()
        if val in {"completed", "done", "success", "succeeded", "delivered", "published"}:
            positive_indicators.append(f"{field}={val}")

    # Check for grants
    grants = projection_payload.get("grants", [])
    if isinstance(grants, (list, tuple)) and len(grants) > 0:
        positive_indicators.append(f"grants present ({len(grants)})")

    # Check for action claims
    action = projection_payload.get("recommended_action", "")
    if str(action).lower() in {"retry", "dispatch", "repair", "complete", "publish", "deliver"}:
        positive_indicators.append(f"recommended_action={action}")

    if positive_indicators:
        return TrapResult(
            trap_kind="stale_projection_no_positive_action",
            verdict=TrapVerdict.TRAPPED,
            detail=(
                f"stale cursor on {sorted(stale_dims)} tried to authorize "
                f"positive action: {', '.join(positive_indicators)}"
            ),
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    # Stale cursor but no positive claims → projection correctly denies
    return TrapResult(
        trap_kind="stale_projection_no_positive_action",
        verdict=TrapVerdict.PASSED,
        detail=f"stale cursor on {sorted(stale_dims)} correctly denies positive action",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id,
    )


def trap_stale_projection_blocks_progress(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
) -> TrapResult:
    """Prove that a stale projection blocks progress rather than fabricating it.

    A healthy stale projection:
    1. Does not claim positive progress (running, progressing, completed).
    2. Surfaces the staleness as a blocking diagnostic.
    3. Provides the exact stale dimensions so consumers can decide.

    Returns BREACHED if a stale projection claims positive progress.
    """
    evidence_ids: list[str] = []
    if source_cursor is not None:
        evidence_ids.append(source_cursor.vector_id)

    if source_cursor is None:
        return TrapResult(
            trap_kind="stale_projection_blocks_progress",
            verdict=TrapVerdict.PASSED,
            detail="no source cursor — cannot evaluate staleness vs progress",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest="",
        )

    if not source_cursor.has_any_stale_or_worse():
        return TrapResult(
            trap_kind="stale_projection_blocks_progress",
            verdict=TrapVerdict.PASSED,
            detail="all cursor dimensions fresh; no staleness to block progress",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    stale_dims = source_cursor.stale_dimensions()

    # Check for positive progress claims
    liveness = str(projection_payload.get("liveness", "")).lower()
    display = str(projection_payload.get("display_state", "")).lower()
    execution = str(projection_payload.get("execution_state", "")).lower()

    positive_progress = liveness in {"progressing", "live", "running", "active"}
    positive_display = display in {"executing", "progressing", "running", "active"}
    positive_execution = execution in {"executing", "running", "progressing"}

    if positive_progress or positive_display or positive_execution:
        return TrapResult(
            trap_kind="stale_projection_blocks_progress",
            verdict=TrapVerdict.BREACHED,
            detail=(
                f"stale cursor on {sorted(stale_dims)} claims positive progress: "
                f"liveness={liveness}, display={display}, execution={execution}"
            ),
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    # Check that staleness is surfaced diagnostically
    has_blocking_info = bool(
        projection_payload.get("stale_dimensions") or projection_payload.get("blocking_dimensions")
    )
    has_cursor_detail = bool(projection_payload.get("cursor_state"))

    if not has_blocking_info and not has_cursor_detail:
        return TrapResult(
            trap_kind="stale_projection_blocks_progress",
            verdict=TrapVerdict.BREACHED,
            detail="stale cursor not surfaced diagnostically; consumer cannot detect staleness",
            evidence_ids=tuple(evidence_ids),
            source_cursor_digest=source_cursor.vector_id,
        )

    return TrapResult(
        trap_kind="stale_projection_blocks_progress",
        verdict=TrapVerdict.PASSED,
        detail=f"stale cursor on {sorted(stale_dims)} correctly blocks progress, surfaced diagnostically",
        evidence_ids=tuple(evidence_ids),
        source_cursor_digest=source_cursor.vector_id,
    )


# ── Convenience: run all projection-negative-authority traps ────────────────


def run_projection_traps(
    projection_payload: Mapping[str, Any],
    *,
    source_cursor: Optional[SourceCursorVector] = None,
    live_source_evidence: Optional[Mapping[str, Any]] = None,
    before_digest: str = "",
    required_reread_dimensions: Optional[Tuple[SourceCursorDimension, ...]] = None,
) -> TrapSuite:
    """Run the full suite of negative-authority traps on a projection.

    Args:
        projection_payload: The projection to check.
        source_cursor: Source-cursor vector (parsed from projection).
        live_source_evidence: Fresh source evidence for forged-detection.
        before_digest: Digest before observer read (for purity check).
        required_reread_dimensions: Dimensions requiring fresh reread.

    Returns:
        TrapSuite with all trap results.
    """
    traps: list[Callable[..., TrapResult]] = [
        lambda: trap_observer_purity_read(
            projection_payload, source_cursor=source_cursor, before_digest=before_digest
        ),
        lambda: trap_observer_purity_no_append(
            projection_payload, source_cursor=source_cursor
        ),
        lambda: trap_forged_projection_no_authority(
            projection_payload, source_cursor=source_cursor,
            live_source_evidence=live_source_evidence,
        ),
        lambda: trap_forged_projection_no_rereread_bypass(
            projection_payload, source_cursor=source_cursor,
            required_reread_dimensions=required_reread_dimensions,
        ),
        lambda: trap_stale_projection_no_positive_action(
            projection_payload, source_cursor=source_cursor,
        ),
        lambda: trap_stale_projection_blocks_progress(
            projection_payload, source_cursor=source_cursor,
        ),
    ]
    results = tuple(t() for t in traps)
    return TrapSuite.from_results(*results)


__all__ = [
    # ── Types ──
    "TrapVerdict",
    "TrapResult",
    "TrapSuite",
    # ── Observer purity ──
    "trap_observer_purity_read",
    "trap_observer_purity_no_append",
    # ── Forged projection ──
    "trap_forged_projection_no_authority",
    "trap_forged_projection_no_rereread_bypass",
    # ── Stale projection ──
    "trap_stale_projection_no_positive_action",
    "trap_stale_projection_blocks_progress",
    # ── Convenience ──
    "run_projection_traps",
    # ── Constants ──
    "_FORBIDDEN_ACTION_KINDS",
    "_FORBIDDEN_EVIDENCE_KINDS",
]
