"""Canonical run-state model types for the pure resolver.

Defines the frozen :class:`CanonicalRunState` dataclass, the
:class:`CanonicalState` and :class:`TypedHumanGate` enums, and stable
serialization helpers.  This module also carries the canonical failure-token
normalization contract (:class:`NormalizedFailureToken`,
:class:`FailureTokenKind`), WBC evidence references
(:class:`WbcEvidenceRef`), Run Authority grant/fence references
(:class:`RunAuthorityRef`), Custody lease/epoch references
(:class:`CustodyRef`), and freshness/lag/uncertainty dimensions
(:class:`UncertaintyLevel`).

This module MUST NOT import from watchdog, status, repair-loop, or any other
consumer — it is the shared contract layer consumed by the resolver and all
downstream observers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Mapping, Sequence


class CanonicalState(Enum):
    """Canonical run-state classifications determined by the resolver.

    These replace the legacy terminal-label projection (``blocked``, ``failed``,
    ``manual_review``, etc.) that multiple layers independently derived from
    overlapping artifacts.  Every consumer should use this enum instead of
    classifying raw evidence on its own.
    """

    RUNNING = auto()
    PAUSED = auto()
    REPAIRING = auto()
    RETRYABLE_EXECUTION_BLOCK = auto()
    REAL_IMPLEMENTATION_BLOCK = auto()
    HUMAN_ACTION_REQUIRED = auto()
    COMPLETED = auto()
    STALE_DERIVED_STATE = auto()
    BROKEN_STATE_MACHINE = auto()
    UNKNOWN = auto()


class TypedHumanGate(Enum):
    """Specific categories of human-action-required gates.

    Only these explicit gate categories cause the resolver to classify a run
    as :attr:`CanonicalState.HUMAN_ACTION_REQUIRED`.  Machine-actionable
    implementation blockers (route-binding gaps, fixture refreshes, stale
    assertions, budget exhaustion) are *never* human gates.
    """

    EXPLICIT_APPROVAL = auto()       # User explicitly approved or rejected a gate.
    CREDENTIAL_ACCOUNT = auto()      # Missing external credential or account.
    QUOTA = auto()                   # Rate-limit or resource quota exhausted.
    VERIFICATION = auto()            # Human verification required (policy).
    POLICY = auto()                  # Policy decision pending human input.
    USER_ACTION = auto()             # Explicit user-action record pending.
    DESTRUCTIVE_ACTION = auto()      # Explicit consent for a destructive action.
    PRODUCT_DECISION = auto()        # Genuine product/requirements choice.


# ── Failure token normalization ────────────────────────────────────────────


class FailureTokenKind(Enum):
    """Canonical failure token kind after normalization.

    The kind drives evidence routing — it determines whether a token is a
    bare ``fail``, a ``failed`` outcome, or an ``error`` signal.
    """

    FAIL = auto()    # "fail" — bare / unqualified
    FAILED = auto()  # "failed" — completion with failure
    ERROR = auto()   # "error" — runtime/system error signal


@dataclass(frozen=True)
class NormalizedFailureToken:
    """Canonical failure token with preserved identity.

    Failure tokens entering the resolver can take lossy forms — ``fail``,
    ``failed``, ``failed: <detail>``, ``error: <detail>``.  This dataclass
    normalizes the token to its canonical form while preserving every piece
    of occurrence identity the source provided.

    Fields
    ------
    canonical:
        The normalized token string (e.g. ``"fail"``, ``"failed:budget"``,
        ``"error:timeout"``).  Whitespace around the colon is collapsed to
        a single ``:`` separator.
    raw:
        The original un-normalized string exactly as provided by the source.
    kind:
        The canonical :class:`FailureTokenKind` derived from the token prefix.
    detail:
        The substring after the first ``:``, stripped of leading/trailing
        whitespace.  Empty string when no colon is present.
    command:
        A preserved command or action label associated with the failure
        occurrence (may be empty).
    criterion_ids:
        Preserved criterion / evaluation-rule identifiers (may be empty).
    content_hash:
        Preserved content digest (sha256:<hex> or empty).
    occurrence_id:
        Preserved occurrence identity (event id, ledger sequence, or empty).
    """

    canonical: str
    raw: str
    kind: FailureTokenKind
    detail: str = ""
    command: str = ""
    criterion_ids: tuple[str, ...] = ()
    content_hash: str = ""
    occurrence_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "criterion_ids", tuple(self.criterion_ids))

    @classmethod
    def normalize(
        cls,
        raw: str,
        *,
        command: str = "",
        criterion_ids: tuple[str, ...] = (),
        content_hash: str = "",
        occurrence_id: str = "",
    ) -> NormalizedFailureToken:
        """Normalize a raw failure token string to canonical form.

        The normalization rules are:

        * Trim leading/trailing whitespace.
        * If the trimmed string starts with ``"fail"`` (case-insensitive)
          followed by optional ``":" detail``, normalize to ``"fail"`` or
          ``"fail:<detail>"``.
        * If it starts with ``"failed"``, normalize to ``"failed"`` or
          ``"failed:<detail>"``.
        * If it starts with ``"error"``, normalize to ``"error"`` or
          ``"error:<detail>"``.
        * Detail after the colon is stripped of leading/trailing whitespace.
        * All other strings are left as-is with kind determined by prefix.

        Returns:
            A frozen :class:`NormalizedFailureToken` with canonical form
            and preserved identity fields.
        """
        trimmed = raw.strip()
        if not trimmed:
            return cls(
                canonical="",
                raw=raw,
                kind=FailureTokenKind.FAIL,
                command=command,
                criterion_ids=criterion_ids,
                content_hash=content_hash,
                occurrence_id=occurrence_id,
            )

        low = trimmed.lower()
        colon_idx = trimmed.find(":")

        if colon_idx != -1:
            prefix = low[:colon_idx].strip()
            detail = trimmed[colon_idx + 1:].strip()
        else:
            prefix = low
            detail = ""

        if prefix == "fail":
            kind = FailureTokenKind.FAIL
            canonical = "fail" + (f":{detail}" if detail else "")
        elif prefix == "failed":
            kind = FailureTokenKind.FAILED
            canonical = "failed" + (f":{detail}" if detail else "")
        elif prefix == "error":
            kind = FailureTokenKind.ERROR
            canonical = "error" + (f":{detail}" if detail else "")
        else:
            # Non-standard prefix — classify by best-effort match.
            if "fail" in prefix:
                kind = FailureTokenKind.FAILED
            elif "error" in prefix:
                kind = FailureTokenKind.ERROR
            else:
                kind = FailureTokenKind.FAILED
            canonical = trimmed

        return cls(
            canonical=canonical,
            raw=raw,
            kind=kind,
            detail=detail,
            command=command,
            criterion_ids=criterion_ids,
            content_hash=content_hash,
            occurrence_id=occurrence_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a stable dict for JSON persistence."""
        return {
            "canonical": self.canonical,
            "raw": self.raw,
            "kind": self.kind.name,
            "detail": self.detail,
            "command": self.command,
            "criterion_ids": list(self.criterion_ids),
            "content_hash": self.content_hash,
            "occurrence_id": self.occurrence_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NormalizedFailureToken:
        """Deserialize from a dict produced by :meth:`to_dict`."""
        return cls(
            canonical=data.get("canonical", ""),
            raw=data.get("raw", ""),
            kind=FailureTokenKind[data.get("kind", "FAIL")],
            detail=data.get("detail", ""),
            command=data.get("command", ""),
            criterion_ids=tuple(data.get("criterion_ids", ())),
            content_hash=data.get("content_hash", ""),
            occurrence_id=data.get("occurrence_id", ""),
        )


# ── WBC / Run Authority / Custody reference types ──────────────────────────


@dataclass(frozen=True)
class WbcEvidenceRef:
    """Non-authoritative reference to a WBC query envelope.

    Carries the envelope type, gate status, attempt identity, content
    digest, and any evidence ids.  This is a lightweight pointer — the
    resolver does not store the full envelope.
    """

    envelope_type: str  # "start", "terminal", "ledger", "gap", "source_cursor"
    status: str  # GateStatus name string
    attempt_id: str = ""
    content_digest: str = ""
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_type": self.envelope_type,
            "status": self.status,
            "attempt_id": self.attempt_id,
            "content_digest": self.content_digest,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WbcEvidenceRef:
        return cls(
            envelope_type=data.get("envelope_type", ""),
            status=data.get("status", ""),
            attempt_id=data.get("attempt_id", ""),
            content_digest=data.get("content_digest", ""),
            evidence_ids=tuple(data.get("evidence_ids", ())),
        )


@dataclass(frozen=True)
class RunAuthorityRef:
    """Reference to a Run Authority grant and optional fence.

    An attempt is dispatched under a capability grant.  A fence may
    restrict when that grant can be exercised.  This ref carries the
    grant identity, an optional decision id, and an optional fence id so
    that every resolver classification can trace back to the authority
    decision under which it runs.
    """

    grant_id: str = ""
    decision_id: str = ""
    fence_id: str = ""
    authority_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"grant_id": self.grant_id}
        if self.decision_id:
            payload["decision_id"] = self.decision_id
        if self.fence_id:
            payload["fence_id"] = self.fence_id
        if self.authority_version:
            payload["authority_version"] = self.authority_version
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunAuthorityRef:
        return cls(
            grant_id=data.get("grant_id", ""),
            decision_id=data.get("decision_id", ""),
            fence_id=data.get("fence_id", ""),
            authority_version=data.get("authority_version", ""),
        )


@dataclass(frozen=True)
class CustodyRef:
    """Reference to a Custody lease and/or epoch.

    Projection rebuilds and lease-based custody checks are tracked by
    lease_id and epoch_id.  This lightweight ref lets every resolver
    classification carry the projection identity consulted during
    evidence gathering.
    """

    lease_id: str = ""
    epoch_id: str = ""
    projection_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.lease_id:
            payload["lease_id"] = self.lease_id
        if self.epoch_id:
            payload["epoch_id"] = self.epoch_id
        if self.projection_id:
            payload["projection_id"] = self.projection_id
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CustodyRef:
        return cls(
            lease_id=data.get("lease_id", ""),
            epoch_id=data.get("epoch_id", ""),
            projection_id=data.get("projection_id", ""),
        )


# ── Freshness / lag / uncertainty dimensions ───────────────────────────────


class UncertaintyLevel(Enum):
    """Degree of uncertainty in the resolver's classification.

    The resolver always produces a canonical state, but the evidence
    backing that state can be fresh or stale, recent or lagging, and
    may have gaps.  This enum captures the resolver's own uncertainty
    about its output so consumers can decide whether to act immediately
    or wait for fresher evidence.
    """

    LOW = auto()     # Evidence is recent, complete, and unambiguous.
    MEDIUM = auto()  # Evidence has minor staleness or a single gap.
    HIGH = auto()    # Evidence is stale, has multiple gaps, or is contradictory.


@dataclass(frozen=True)
class CanonicalRunState:
    """Frozen canonical run-state result produced by the resolver.

    This is the authoritative output that all consumers (watchdog, status,
    repair-loop, chain, auto, progress-auditor) should use instead of
    independently classifying raw artifacts.

    Fields
    ------
    canonical_state:
        The resolver's single classification for this run.
    confidence:
        ``"high"``, ``"medium"``, or ``"low"``.
    source_of_truth:
        Ordered list of evidence sources the resolver considered authoritative.
    stale_sources:
        Evidence sources the resolver found stale or contradictory.
    human_required:
        ``True`` only when *canonical_state* is ``HUMAN_ACTION_REQUIRED``.
    human_gate:
        The specific typed gate when *human_required* is ``True``, else ``None``.
    repairable:
        ``True`` when the repair loop should attempt automated repair.
    running:
        ``True`` when the run is actively executing (live worker).
    next_action:
        Suggested next action for the repair loop or operator.
    reason:
        Human-readable rationale for the classification.
    evidence:
        Supporting evidence items (each a dict with at least ``kind``,
        ``path``, and ``summary``).
    """

    canonical_state: CanonicalState
    confidence: str = "medium"
    source_of_truth: Sequence[str] = field(default_factory=tuple)
    stale_sources: Sequence[str] = field(default_factory=tuple)
    human_required: bool = False
    human_gate: TypedHumanGate | None = None
    repairable: bool = False
    running: bool = False
    next_action: str = ""
    reason: str = ""
    evidence: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    # ── M9 dimensions ──────────────────────────────────────────────────
    failure_token: NormalizedFailureToken | None = None
    wbc_refs: Sequence[WbcEvidenceRef] = field(default_factory=tuple)
    run_authority_ref: RunAuthorityRef | None = None
    custody_ref: CustodyRef | None = None
    freshness_seconds: float | None = None
    lag_seconds: float | None = None
    uncertainty: UncertaintyLevel = UncertaintyLevel.MEDIUM

    def __post_init__(self) -> None:
        """Normalize mutable sequences to immutable tuples.

        The dataclass is frozen so we must use ``object.__setattr__``.
        """
        object.__setattr__(self, "source_of_truth", tuple(self.source_of_truth))
        object.__setattr__(self, "stale_sources", tuple(self.stale_sources))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "wbc_refs", tuple(self.wbc_refs))

    # ------------------------------------------------------------------
    # stable serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a stable dict suitable for JSON persistence.

        Enum members are stored by name so the output survives re-ordering
        of enum definitions.  All sequences are materialized as lists.
        """
        result: dict[str, Any] = {
            "canonical_state": self.canonical_state.name,
            "confidence": self.confidence,
            "source_of_truth": list(self.source_of_truth),
            "stale_sources": list(self.stale_sources),
            "human_required": self.human_required,
            "human_gate": self.human_gate.name if self.human_gate is not None else None,
            "repairable": self.repairable,
            "running": self.running,
            "next_action": self.next_action,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "uncertainty": self.uncertainty.name,
        }
        if self.failure_token is not None:
            result["failure_token"] = self.failure_token.to_dict()
        if self.wbc_refs:
            result["wbc_refs"] = [r.to_dict() for r in self.wbc_refs]
        if self.run_authority_ref is not None:
            result["run_authority_ref"] = self.run_authority_ref.to_dict()
        if self.custody_ref is not None:
            result["custody_ref"] = self.custody_ref.to_dict()
        if self.freshness_seconds is not None:
            result["freshness_seconds"] = self.freshness_seconds
        if self.lag_seconds is not None:
            result["lag_seconds"] = self.lag_seconds
        return result

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to a stable JSON string.

        Keys are sorted so identical payloads produce identical strings.
        """
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CanonicalRunState:
        """Deserialize from a dict previously produced by :meth:`to_dict`."""
        human_gate_raw = data.get("human_gate")
        failure_token_raw = data.get("failure_token")
        wbc_refs_raw = data.get("wbc_refs")
        run_auth_raw = data.get("run_authority_ref")
        custody_raw = data.get("custody_ref")
        uncertainty_raw = data.get("uncertainty", "MEDIUM")
        return cls(
            canonical_state=CanonicalState[data["canonical_state"]],
            confidence=data.get("confidence", "medium"),
            source_of_truth=tuple(data.get("source_of_truth", ())),
            stale_sources=tuple(data.get("stale_sources", ())),
            human_required=data.get("human_required", False),
            human_gate=TypedHumanGate[human_gate_raw] if human_gate_raw is not None else None,
            repairable=data.get("repairable", False),
            running=data.get("running", False),
            next_action=data.get("next_action", ""),
            reason=data.get("reason", ""),
            evidence=tuple(data.get("evidence", ())),
            failure_token=NormalizedFailureToken.from_dict(failure_token_raw)
            if isinstance(failure_token_raw, Mapping) else None,
            wbc_refs=tuple(
                WbcEvidenceRef.from_dict(r) for r in wbc_refs_raw
            ) if isinstance(wbc_refs_raw, list) else (),
            run_authority_ref=RunAuthorityRef.from_dict(run_auth_raw)
            if isinstance(run_auth_raw, Mapping) else None,
            custody_ref=CustodyRef.from_dict(custody_raw)
            if isinstance(custody_raw, Mapping) else None,
            freshness_seconds=data.get("freshness_seconds"),
            lag_seconds=data.get("lag_seconds"),
            uncertainty=UncertaintyLevel[uncertainty_raw]
            if uncertainty_raw in UncertaintyLevel.__members__ else UncertaintyLevel.MEDIUM,
        )

    @classmethod
    def from_json(cls, text: str) -> CanonicalRunState:
        """Deserialize from a JSON string produced by :meth:`to_json`."""
        return cls.from_dict(json.loads(text))
