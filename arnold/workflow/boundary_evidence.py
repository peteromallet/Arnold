"""Structured boundary evidence vocabulary for Megaplan checker diagnostics.

This module is intentionally declarative. It defines stable data shapes for
boundary contracts, receipts, authority records, and semantic findings that
downstream S2.5 checker, receipt-emission, and semantic-health work consume.
It does not parse source, resolve imports, mutate state, or drive routing.

Boundary vocabulary types are separate from ``SemanticEvidence`` and
``SemanticFailure`` to prevent conflation between source-topology evidence
and durable-boundary evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from arnold.workflow.diagnostics import DiagnosticCode


# ── Boundary diagnostic codes (AWF246-AWF249) ─────────────────────────────


class BoundaryPhase(StrEnum):
    """Stable boundary phase identifiers for the front-half slice."""

    PREP = "prep"
    PLAN = "plan"
    CRITIQUE = "critique"
    GATE = "gate"
    REVISE = "revise"
    # ── S3 tiebreaker/replan phases ──────────────────────────────────────
    TIEBREAKER_RESEARCHER = "tiebreaker_researcher"
    TIEBREAKER_CHALLENGER = "tiebreaker_challenger"
    TIEBREAKER_SYNTHESIS = "tiebreaker_synthesis"
    TIEBREAKER_DECISION = "tiebreaker_decision"
    REPLAN_AUTHORITY = "replan_authority"
    PARENT_REJOIN = "parent_rejoin"


class BoundaryOutcome(StrEnum):
    """Stable boundary outcome codes."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    PARTIAL = "partial"
    TIER_ACCEPTED = "tier_accepted"
    AWAITING_EXTERNAL_EVIDENCE = "awaiting_external_evidence"
    WAIVED = "waived"
    SUPERSEDED = "superseded"
    VOIDED = "voided"
    ROLLBACK_COMPLETE = "rollback_complete"
    IRREVERSIBLE = "irreversible"
    DEGRADED_CONTINUE = "degraded_continue"


class FindingSeverity(StrEnum):
    """Severity levels for semantic findings."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ── BoundaryContract ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoundaryContract:
    """Declared durable effects expected at a workflow boundary.

    A boundary is complete only when its declared durable effects are
    present, coherent, and authorized.  This contract declares what those
    effects are without executing, observing, or judging them.
    """

    boundary_id: str
    workflow_id: str
    row_id: str | None = None
    phase: BoundaryPhase | None = None
    required_artifacts: tuple[str, ...] = ()
    expected_state_delta: Mapping[str, Any] = field(default_factory=dict)
    expected_history_entry: str | None = None
    phase_result_required: bool = False
    receipt_required: bool = False
    authority_required: bool = False
    contract_version: str = "arnold.workflow.boundary_contract.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.boundary_id:
            raise ValueError("BoundaryContract.boundary_id must be non-empty")
        if not self.workflow_id:
            raise ValueError("BoundaryContract.workflow_id must be non-empty")
        if self.phase is not None:
            object.__setattr__(self, "phase", BoundaryPhase(self.phase))
        object.__setattr__(
            self, "required_artifacts",
            tuple(str(a) for a in self.required_artifacts),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))
        object.__setattr__(
            self, "expected_state_delta",
            _freeze_mapping(self.expected_state_delta),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe payload with primitive values."""
        payload: dict[str, Any] = {
            "boundary_id": self.boundary_id,
            "workflow_id": self.workflow_id,
            "contract_version": self.contract_version,
        }
        if self.row_id is not None:
            payload["row_id"] = self.row_id
        if self.phase is not None:
            payload["phase"] = self.phase.value
        if self.required_artifacts:
            payload["required_artifacts"] = list(self.required_artifacts)
        if self.expected_state_delta:
            payload["expected_state_delta"] = _thaw_value(self.expected_state_delta)
        if self.expected_history_entry is not None:
            payload["expected_history_entry"] = self.expected_history_entry
        payload["phase_result_required"] = self.phase_result_required
        payload["receipt_required"] = self.receipt_required
        payload["authority_required"] = self.authority_required
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload


# ── BoundaryReceipt ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoundaryReceipt:
    """Durable proof that a boundary completed with coherent effects.

    A receipt records what the producer or observer proved actually
    happened at a boundary — artifact refs, state observation, history
    entry, phase result, and authority records.
    """

    boundary_id: str
    workflow_id: str
    row_id: str | None = None
    invocation_id: str | None = None
    artifact_refs: tuple[str, ...] = ()
    state_observation: Mapping[str, Any] = field(default_factory=dict)
    history_ref: str | None = None
    phase_result_ref: str | None = None
    outcome: BoundaryOutcome | None = None
    authority_records: tuple[AuthorityRecord, ...] = ()
    receipt_version: str = "arnold.workflow.boundary_receipt.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.boundary_id:
            raise ValueError("BoundaryReceipt.boundary_id must be non-empty")
        if not self.workflow_id:
            raise ValueError("BoundaryReceipt.workflow_id must be non-empty")
        if self.outcome is not None:
            object.__setattr__(self, "outcome", BoundaryOutcome(self.outcome))
        object.__setattr__(
            self, "artifact_refs",
            tuple(str(a) for a in self.artifact_refs),
        )
        object.__setattr__(
            self, "authority_records",
            tuple(
                AuthorityRecord(
                    actor=a.actor if isinstance(a, AuthorityRecord) else a["actor"],
                    role=a.role if isinstance(a, AuthorityRecord) else a["role"],
                    decision=a.decision if isinstance(a, AuthorityRecord) else a.get("decision"),
                    scope=a.scope if isinstance(a, AuthorityRecord) else a.get("scope"),
                    conditions=(
                        a.conditions
                        if isinstance(a, AuthorityRecord)
                        else a.get("conditions")
                    ),
                    evidence_refs=(
                        a.evidence_refs
                        if isinstance(a, AuthorityRecord)
                        else tuple(a.get("evidence_refs", ()))
                    ),
                    expiry=a.expiry if isinstance(a, AuthorityRecord) else a.get("expiry"),
                    waiver_reason=(
                        a.waiver_reason
                        if isinstance(a, AuthorityRecord)
                        else a.get("waiver_reason")
                    ),
                    details=a.details if isinstance(a, AuthorityRecord) else a.get("details", {}),
                )
                for a in self.authority_records
            ),
        )
        object.__setattr__(
            self, "state_observation",
            _freeze_mapping(self.state_observation),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe receipt payload with primitive values."""
        payload: dict[str, Any] = {
            "boundary_id": self.boundary_id,
            "workflow_id": self.workflow_id,
            "receipt_version": self.receipt_version,
        }
        if self.row_id is not None:
            payload["row_id"] = self.row_id
        if self.invocation_id is not None:
            payload["invocation_id"] = self.invocation_id
        if self.artifact_refs:
            payload["artifact_refs"] = list(self.artifact_refs)
        if self.state_observation:
            payload["state_observation"] = _thaw_value(self.state_observation)
        if self.history_ref is not None:
            payload["history_ref"] = self.history_ref
        if self.phase_result_ref is not None:
            payload["phase_result_ref"] = self.phase_result_ref
        if self.outcome is not None:
            payload["outcome"] = self.outcome.value
        if self.authority_records:
            payload["authority_records"] = [
                ar.to_dict() for ar in self.authority_records
            ]
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload


# ── AuthorityRecord ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuthorityRecord:
    """Proof metadata for an authority-bearing decision at a boundary.

    Covers approvals, denials, waivers, overrides, and force-proceed
    decisions.  Does not decide product routes or replace ``.pypeline``
    topology.
    """

    actor: str
    role: str
    decision: str | None = None
    scope: str | None = None
    conditions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    expiry: str | None = None
    waiver_reason: str | None = None
    authority_version: str = "arnold.workflow.authority_record.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.actor:
            raise ValueError("AuthorityRecord.actor must be non-empty")
        if not self.role:
            raise ValueError("AuthorityRecord.role must be non-empty")
        object.__setattr__(
            self, "conditions",
            tuple(str(c) for c in self.conditions),
        )
        object.__setattr__(
            self, "evidence_refs",
            tuple(str(e) for e in self.evidence_refs),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe authority payload with primitive values."""
        payload: dict[str, Any] = {
            "actor": self.actor,
            "role": self.role,
            "authority_version": self.authority_version,
        }
        if self.decision is not None:
            payload["decision"] = self.decision
        if self.scope is not None:
            payload["scope"] = self.scope
        if self.conditions:
            payload["conditions"] = list(self.conditions)
        if self.evidence_refs:
            payload["evidence_refs"] = list(self.evidence_refs)
        if self.expiry is not None:
            payload["expiry"] = self.expiry
        if self.waiver_reason is not None:
            payload["waiver_reason"] = self.waiver_reason
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload


# ── SemanticFinding ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class SemanticFinding:
    """A mismatch between boundary contract, evidence, authority, and
    current durable reality.

    Semantic findings are produced by semantic-health checks and consumed
    by repair, status, and auditor views.  They are runtime health
    observations, not extensions of ``SemanticFailure``.
    """

    finding_id: str
    boundary_id: str
    description: str
    severity: FindingSeverity = FindingSeverity.ERROR
    diagnostic_code: DiagnosticCode | None = None
    contract_ref: str | None = None
    evidence_ref: str | None = None
    authority_ref: str | None = None
    finding_version: str = "arnold.workflow.semantic_finding.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.finding_id:
            raise ValueError("SemanticFinding.finding_id must be non-empty")
        if not self.boundary_id:
            raise ValueError("SemanticFinding.boundary_id must be non-empty")
        if not self.description:
            raise ValueError("SemanticFinding.description must be non-empty")
        object.__setattr__(self, "severity", FindingSeverity(self.severity))
        if self.diagnostic_code is not None:
            object.__setattr__(
                self, "diagnostic_code",
                DiagnosticCode(self.diagnostic_code),
            )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe finding payload with primitive values."""
        payload: dict[str, Any] = {
            "finding_id": self.finding_id,
            "boundary_id": self.boundary_id,
            "description": self.description,
            "severity": self.severity.value,
            "finding_version": self.finding_version,
        }
        if self.diagnostic_code is not None:
            payload["diagnostic_code"] = self.diagnostic_code.value
        if self.contract_ref is not None:
            payload["contract_ref"] = self.contract_ref
        if self.evidence_ref is not None:
            payload["evidence_ref"] = self.evidence_ref
        if self.authority_ref is not None:
            payload["authority_ref"] = self.authority_ref
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload


# ── internal helpers ──────────────────────────────────────────────────────


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(
        {str(key): _freeze_value(subvalue) for key, subvalue in value.items()}
    )


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_value(subvalue) for key, subvalue in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


__all__ = [
    "AuthorityRecord",
    "BoundaryContract",
    "BoundaryOutcome",
    "BoundaryPhase",
    "BoundaryReceipt",
    "FindingSeverity",
    "SemanticFinding",
]
