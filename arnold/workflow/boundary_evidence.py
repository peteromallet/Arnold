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
    # ── S4 execute phase ──────────────────────────────────────────────────
    EXECUTE = "execute"


class AuthorityState(StrEnum):
    """Stable authority state classification for transition provenance.

    These states describe the authority posture of a transition decision
    so operators and auditors can quickly classify it without inspecting
    the full evidence chain.  They are intentionally narrow: every state
    can be derived from the decision's own payload fields.
    """

    MISSING = "missing"
    """No authority records or evidence refs found — nothing was checked."""

    DENIED = "denied"
    """Transition was denied by policy or explicit authority decision."""

    STALE = "stale"
    """Authority evidence exists but is past its freshness window."""

    WAIVED = "waived"
    """Authority was explicitly waived by a recognized waiver grant."""

    PARTIAL = "partial"
    """Some authority refs exist but coverage is incomplete."""

    DEGRADED = "degraded"
    """Authority evidence is present but provider errors or incomplete
    checks reduce its reliability."""

    IRREVERSIBLE = "irreversible"
    """Allowed transition with a complete, fresh authority chain; the
    decision cannot be rolled back by automated means."""


class BoundaryOutcome(StrEnum):
    """Stable boundary outcome codes."""

    COMPLETE = "complete"
    SUCCEEDED = "succeeded"
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


# ── Template / profile compatibility ──────────────────────────────────────


class TemplateCompatibility(StrEnum):
    """Classifies the relationship between two template versions."""

    EXACT_MATCH = "exact_match"
    COMPATIBLE_EXTENSION = "compatible_extension"
    BREAKING_CHANGE = "breaking_change"
    INCOMPATIBLE_RANGE = "incompatible_range"
    DELIBERATE_UPGRADE = "deliberate_upgrade"


@dataclass(frozen=True)
class TemplateCompatibilityResult:
    """Result of comparing two template/profile versions.

    Produced by :func:`check_template_compatibility` and consumed by
    registry pin/upgrade flows.  This is a declarative record, not a
    routing decision.
    """

    compatibility: TemplateCompatibility
    added_optional_fields: tuple[str, ...] = ()
    removed_required_fields: tuple[str, ...] = ()
    changed_required_fields: tuple[str, ...] = ()
    template_id: str | None = None
    from_version: str | None = None
    to_version: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "added_optional_fields",
            tuple(str(f) for f in self.added_optional_fields),
        )
        object.__setattr__(
            self, "removed_required_fields",
            tuple(str(f) for f in self.removed_required_fields),
        )
        object.__setattr__(
            self, "changed_required_fields",
            tuple(str(f) for f in self.changed_required_fields),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "compatibility": self.compatibility.value,
        }
        if self.added_optional_fields:
            payload["added_optional_fields"] = list(self.added_optional_fields)
        if self.removed_required_fields:
            payload["removed_required_fields"] = list(self.removed_required_fields)
        if self.changed_required_fields:
            payload["changed_required_fields"] = list(self.changed_required_fields)
        if self.template_id is not None:
            payload["template_id"] = self.template_id
        if self.from_version is not None:
            payload["from_version"] = self.from_version
        if self.to_version is not None:
            payload["to_version"] = self.to_version
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload


def check_template_compatibility(
    template_id: str,
    from_required_fields: frozenset[str],
    from_optional_fields: frozenset[str],
    to_required_fields: frozenset[str],
    to_optional_fields: frozenset[str],
    from_version: str | None = None,
    to_version: str | None = None,
) -> TemplateCompatibilityResult:
    """Compare two template/profile field sets and classify compatibility.

    A *breaking change* is any removal of a required field or a change that
    moves a field from optional to required (which existing producers cannot
    satisfy).  A *compatible extension* adds optional fields without removing
    or tightening existing requirements.
    """
    if from_required_fields == to_required_fields and from_optional_fields == to_optional_fields:
        return TemplateCompatibilityResult(
            compatibility=TemplateCompatibility.EXACT_MATCH,
            template_id=template_id,
            from_version=from_version,
            to_version=to_version,
        )

    removed_required = tuple(
        sorted(f for f in from_required_fields if f not in to_required_fields)
    )
    changed_to_required = tuple(
        sorted(f for f in from_optional_fields if f in to_required_fields)
    )
    added_optional = tuple(
        sorted(f for f in to_optional_fields if f not in from_optional_fields and f not in from_required_fields)
    )

    if removed_required or changed_to_required:
        return TemplateCompatibilityResult(
            compatibility=TemplateCompatibility.BREAKING_CHANGE,
            removed_required_fields=tuple(
                sorted(set(removed_required) | set(changed_to_required))
            ),
            added_optional_fields=added_optional,
            template_id=template_id,
            from_version=from_version,
            to_version=to_version,
        )

    if added_optional:
        return TemplateCompatibilityResult(
            compatibility=TemplateCompatibility.COMPATIBLE_EXTENSION,
            added_optional_fields=added_optional,
            template_id=template_id,
            from_version=from_version,
            to_version=to_version,
        )

    # Fields reorganized but not strictly additive or subtractive
    changed_required = tuple(
        sorted(
            (from_required_fields | from_optional_fields)
            ^ (to_required_fields | to_optional_fields)
        )
    )
    return TemplateCompatibilityResult(
        compatibility=TemplateCompatibility.INCOMPATIBLE_RANGE,
        changed_required_fields=changed_required,
        template_id=template_id,
        from_version=from_version,
        to_version=to_version,
    )


_TOPOLOGY_DETAIL_KEYS_BY_ROW_ID = MappingProxyType(
    {
        "s5.review_child_outputs.1": ("fan_in_ref", "evidence_surface_ref"),
        "s5.review_reducer_promotion.1": ("reducer_ref",),
        "s5.review_rework_effects.1": ("evidence_surface_ref",),
        "s5.review_cap_authority.1": ("authority_scope", "authority_outcomes", "policy_ref"),
        "s5.review_human_verification.1": (
            "suspension_route_id",
            "resume_policy_ref",
            "resume_cursor_ref",
        ),
        "s5.finalize_artifacts.1": ("effect_id", "artifact_policy_ref"),
        "s5.finalize_fallback.1": ("evidence_surface_ref", "projection_ref"),
        "s5.final_projection.1": ("evidence_surface_ref", "projection_cases"),
    }
)


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


# ── BoundaryEvidence ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoundaryEvidence:
    """Raw evidence record for an individual piece of boundary proof.

    Distinct from :class:`BoundaryReceipt`, which composites multiple
    evidence items into a single completion proof.  ``BoundaryEvidence``
    captures individual artifacts, journal entries, envelopes, warrants,
    and their fingerprints before they are assembled into a receipt.

    This is the canonical shape for producer-emitted evidence that
    semantic-health, status, repair, and auditor consumers evaluate.
    """

    evidence_id: str
    boundary_id: str
    workflow_id: str
    producer_id: str | None = None
    invocation_id: str | None = None
    artifact_refs: tuple[str, ...] = ()
    artifact_fingerprints: Mapping[str, str] = field(default_factory=dict)
    event_journal_refs: tuple[str, ...] = ()
    step_io_envelope_refs: tuple[str, ...] = ()
    warrant_capsule_refs: tuple[str, ...] = ()
    authority_level: str | None = None
    evidence_profile_ref: str | None = None
    freshness: str | None = None
    observation_time: str | None = None
    evidence_version: str = "arnold.workflow.boundary_evidence.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("BoundaryEvidence.evidence_id must be non-empty")
        if not self.boundary_id:
            raise ValueError("BoundaryEvidence.boundary_id must be non-empty")
        if not self.workflow_id:
            raise ValueError("BoundaryEvidence.workflow_id must be non-empty")
        object.__setattr__(
            self, "artifact_refs",
            tuple(str(a) for a in self.artifact_refs),
        )
        object.__setattr__(
            self, "event_journal_refs",
            tuple(str(e) for e in self.event_journal_refs),
        )
        object.__setattr__(
            self, "step_io_envelope_refs",
            tuple(str(s) for s in self.step_io_envelope_refs),
        )
        object.__setattr__(
            self, "warrant_capsule_refs",
            tuple(str(w) for w in self.warrant_capsule_refs),
        )
        object.__setattr__(
            self, "artifact_fingerprints",
            _freeze_mapping(self.artifact_fingerprints),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe evidence payload with primitive values."""
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "boundary_id": self.boundary_id,
            "workflow_id": self.workflow_id,
            "evidence_version": self.evidence_version,
        }
        if self.producer_id is not None:
            payload["producer_id"] = self.producer_id
        if self.invocation_id is not None:
            payload["invocation_id"] = self.invocation_id
        if self.artifact_refs:
            payload["artifact_refs"] = list(self.artifact_refs)
        if self.artifact_fingerprints:
            payload["artifact_fingerprints"] = _thaw_value(self.artifact_fingerprints)
        if self.event_journal_refs:
            payload["event_journal_refs"] = list(self.event_journal_refs)
        if self.step_io_envelope_refs:
            payload["step_io_envelope_refs"] = list(self.step_io_envelope_refs)
        if self.warrant_capsule_refs:
            payload["warrant_capsule_refs"] = list(self.warrant_capsule_refs)
        if self.authority_level is not None:
            payload["authority_level"] = self.authority_level
        if self.evidence_profile_ref is not None:
            payload["evidence_profile_ref"] = self.evidence_profile_ref
        if self.freshness is not None:
            payload["freshness"] = self.freshness
        if self.observation_time is not None:
            payload["observation_time"] = self.observation_time
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BoundaryEvidence:
        """Reconstruct from a serialized dict (e.g. sidecar JSON)."""
        return cls(
            evidence_id=data["evidence_id"],
            boundary_id=data["boundary_id"],
            workflow_id=data["workflow_id"],
            producer_id=data.get("producer_id"),
            invocation_id=data.get("invocation_id"),
            artifact_refs=tuple(data.get("artifact_refs", ())),
            artifact_fingerprints=data.get("artifact_fingerprints", {}),
            event_journal_refs=tuple(data.get("event_journal_refs", ())),
            step_io_envelope_refs=tuple(data.get("step_io_envelope_refs", ())),
            warrant_capsule_refs=tuple(data.get("warrant_capsule_refs", ())),
            authority_level=data.get("authority_level"),
            evidence_profile_ref=data.get("evidence_profile_ref"),
            freshness=data.get("freshness"),
            observation_time=data.get("observation_time"),
            evidence_version=data.get("evidence_version", "arnold.workflow.boundary_evidence.v1"),
            details=data.get("details", {}),
        )


# ── EvidenceProfile ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class EvidenceProfile:
    """Provenance and trust metadata for boundary evidence.

    Describes *who* produced the evidence, *how* it was produced, and
    what *trust level* it carries.  This is referenced by
    :class:`BoundaryEvidence` and :class:`BoundaryReceipt` but is not
    itself evidence — it is the profile that qualifies evidence.
    """

    profile_id: str
    provenance: str | None = None
    trust_level: str | None = None
    source_type: str | None = None
    source_kind: str | None = None
    actor_identity: str | None = None
    tool_version_vector: tuple[str, ...] = ()
    confidence: str | None = None
    privacy_class: str | None = None
    observation_window: str | None = None
    profile_version: str = "arnold.workflow.evidence_profile.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("EvidenceProfile.profile_id must be non-empty")
        object.__setattr__(
            self, "tool_version_vector",
            tuple(str(t) for t in self.tool_version_vector),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe profile payload with primitive values."""
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
        }
        if self.provenance is not None:
            payload["provenance"] = self.provenance
        if self.trust_level is not None:
            payload["trust_level"] = self.trust_level
        if self.source_type is not None:
            payload["source_type"] = self.source_type
        if self.source_kind is not None:
            payload["source_kind"] = self.source_kind
        if self.actor_identity is not None:
            payload["actor_identity"] = self.actor_identity
        if self.tool_version_vector:
            payload["tool_version_vector"] = list(self.tool_version_vector)
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.privacy_class is not None:
            payload["privacy_class"] = self.privacy_class
        if self.observation_window is not None:
            payload["observation_window"] = self.observation_window
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvidenceProfile:
        """Reconstruct from a serialized dict."""
        return cls(
            profile_id=data["profile_id"],
            provenance=data.get("provenance"),
            trust_level=data.get("trust_level"),
            source_type=data.get("source_type"),
            source_kind=data.get("source_kind"),
            actor_identity=data.get("actor_identity"),
            tool_version_vector=tuple(data.get("tool_version_vector", ())),
            confidence=data.get("confidence"),
            privacy_class=data.get("privacy_class"),
            observation_window=data.get("observation_window"),
            profile_version=data.get("profile_version", "arnold.workflow.evidence_profile.v1"),
            details=data.get("details", {}),
        )


# ── BoundaryGraph ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoundaryGraph:
    """Declared dependency, join, and fan-out structure at a boundary.

    Describes what other boundaries this boundary depends on, joins with,
    fans out to, or fans in from — including cross-workflow refs and
    entity lineage.  This is declarative graph metadata, not a runtime
    route topology.
    """

    graph_id: str
    boundary_id: str
    dependencies: tuple[str, ...] = ()
    joins: tuple[str, ...] = ()
    fan_out_refs: tuple[str, ...] = ()
    fan_in_ref: str | None = None
    cross_workflow_refs: tuple[str, ...] = ()
    entity_lineage: tuple[str, ...] = ()
    peer_join_requirements: tuple[str, ...] = ()
    graph_version: str = "arnold.workflow.boundary_graph.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.graph_id:
            raise ValueError("BoundaryGraph.graph_id must be non-empty")
        if not self.boundary_id:
            raise ValueError("BoundaryGraph.boundary_id must be non-empty")
        object.__setattr__(
            self, "dependencies",
            tuple(str(d) for d in self.dependencies),
        )
        object.__setattr__(
            self, "joins",
            tuple(str(j) for j in self.joins),
        )
        object.__setattr__(
            self, "fan_out_refs",
            tuple(str(f) for f in self.fan_out_refs),
        )
        object.__setattr__(
            self, "cross_workflow_refs",
            tuple(str(c) for c in self.cross_workflow_refs),
        )
        object.__setattr__(
            self, "entity_lineage",
            tuple(str(e) for e in self.entity_lineage),
        )
        object.__setattr__(
            self, "peer_join_requirements",
            tuple(str(p) for p in self.peer_join_requirements),
        )
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe graph payload with primitive values."""
        payload: dict[str, Any] = {
            "graph_id": self.graph_id,
            "boundary_id": self.boundary_id,
            "graph_version": self.graph_version,
        }
        if self.dependencies:
            payload["dependencies"] = list(self.dependencies)
        if self.joins:
            payload["joins"] = list(self.joins)
        if self.fan_out_refs:
            payload["fan_out_refs"] = list(self.fan_out_refs)
        if self.fan_in_ref is not None:
            payload["fan_in_ref"] = self.fan_in_ref
        if self.cross_workflow_refs:
            payload["cross_workflow_refs"] = list(self.cross_workflow_refs)
        if self.entity_lineage:
            payload["entity_lineage"] = list(self.entity_lineage)
        if self.peer_join_requirements:
            payload["peer_join_requirements"] = list(self.peer_join_requirements)
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BoundaryGraph:
        """Reconstruct from a serialized dict."""
        return cls(
            graph_id=data["graph_id"],
            boundary_id=data["boundary_id"],
            dependencies=tuple(data.get("dependencies", ())),
            joins=tuple(data.get("joins", ())),
            fan_out_refs=tuple(data.get("fan_out_refs", ())),
            fan_in_ref=data.get("fan_in_ref"),
            cross_workflow_refs=tuple(data.get("cross_workflow_refs", ())),
            entity_lineage=tuple(data.get("entity_lineage", ())),
            peer_join_requirements=tuple(data.get("peer_join_requirements", ())),
            graph_version=data.get("graph_version", "arnold.workflow.boundary_graph.v1"),
            details=data.get("details", {}),
        )


# ── TemporalPolicy ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TemporalPolicy:
    """Time-based validity policy for boundary evidence and authority.

    Separates staleness, deadline, verification timeout, minimum
    observation duration, expiry, and sunset/renewal as distinct fields
    rather than collapsing them into a single timestamp.

    Referenced by contracts, receipts, evidence profiles, and authority
    records to communicate how long each piece of proof remains valid.
    """

    policy_id: str
    staleness_duration: str | None = None
    deadline: str | None = None
    verification_timeout: str | None = None
    minimum_observation_duration: str | None = None
    expiry: str | None = None
    sunset_renewal: str | None = None
    policy_version: str = "arnold.workflow.temporal_policy.v1"
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise ValueError("TemporalPolicy.policy_id must be non-empty")
        object.__setattr__(self, "details", _freeze_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe temporal policy payload."""
        payload: dict[str, Any] = {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }
        if self.staleness_duration is not None:
            payload["staleness_duration"] = self.staleness_duration
        if self.deadline is not None:
            payload["deadline"] = self.deadline
        if self.verification_timeout is not None:
            payload["verification_timeout"] = self.verification_timeout
        if self.minimum_observation_duration is not None:
            payload["minimum_observation_duration"] = self.minimum_observation_duration
        if self.expiry is not None:
            payload["expiry"] = self.expiry
        if self.sunset_renewal is not None:
            payload["sunset_renewal"] = self.sunset_renewal
        if self.details:
            payload["details"] = _thaw_value(self.details)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TemporalPolicy:
        """Reconstruct from a serialized dict."""
        return cls(
            policy_id=data["policy_id"],
            staleness_duration=data.get("staleness_duration"),
            deadline=data.get("deadline"),
            verification_timeout=data.get("verification_timeout"),
            minimum_observation_duration=data.get("minimum_observation_duration"),
            expiry=data.get("expiry"),
            sunset_renewal=data.get("sunset_renewal"),
            policy_version=data.get("policy_version", "arnold.workflow.temporal_policy.v1"),
            details=data.get("details", {}),
        )


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


def boundary_contract_missing_topology_detail_keys(contract: BoundaryContract) -> tuple[str, ...]:
    """Return missing source/policy topology markers required for S5 evidence rows."""

    required_keys = _TOPOLOGY_DETAIL_KEYS_BY_ROW_ID.get(contract.row_id or "", ())
    if not required_keys:
        return ()
    missing: list[str] = []
    for key in required_keys:
        value = contract.details.get(key)
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(key)
            continue
        if isinstance(value, tuple) and not value:
            missing.append(key)
    return tuple(missing)


# ── Transition authority state classification ─────────────────────────────


def classify_authority_state(
    *,
    allowed: bool,
    authority_record_refs: tuple[str, ...],
    checked_evidence_refs: tuple[str, ...],
    advisory: tuple[str, ...] = (),
    has_waiver: bool = False,
    provider_errors: bool = False,
    denial_reasons: tuple[str, ...] = (),
) -> AuthorityState:
    """Classify the authority posture of a review-to-done transition decision.

    Derives one of seven stable :class:`AuthorityState` values from the
    decision's own payload fields.  The classification is deterministic
    and does not inspect external state.

    Priority order (first match wins):

    1. *denied* — transition was denied by policy.
    2. *missing* — no authority refs and no evidence refs.
    3. *waived* — explicit waiver grant detected.
    4. *stale* — evidence is stale (advisory freshness warning present).
    5. *degraded* — evidence present but provider errors degrade it.
    6. *partial* — some authority refs exist but coverage incomplete.
    7. *irreversible* — allowed with complete fresh authority chain.
    """
    if not allowed:
        return AuthorityState.DENIED

    has_any_authority = bool(authority_record_refs)
    has_any_evidence = bool(checked_evidence_refs)

    if not has_any_authority and not has_any_evidence:
        return AuthorityState.MISSING

    if has_waiver:
        return AuthorityState.WAIVED

    advisory_text = " ".join(str(a).lower() for a in advisory)
    if "stale" in advisory_text or "could not prove" in advisory_text:
        return AuthorityState.STALE

    if provider_errors:
        return AuthorityState.DEGRADED

    if has_any_authority and not has_any_evidence:
        return AuthorityState.PARTIAL

    # Evidence present, no staleness, no degradation, no denial.
    return AuthorityState.IRREVERSIBLE


def compile_authority_view(
    *,
    boundary_id: str | None = None,
    authority_state: AuthorityState | str,
    authority_record_refs: tuple[str, ...] = (),
    checked_evidence_refs: tuple[str, ...] = (),
    status: str = "",
    would_block_reasons: tuple[str, ...] = (),
    operator_summary: str | None = None,
) -> dict[str, Any]:
    """Build a compact operator/auditor-friendly authority view dict.

    The returned dict is suitable for embedding in ``routing_provenance``
    as ``authority_view`` so operators and auditors can classify a
    transition decision at a glance without inspecting the full evidence
    chain.
    """
    state = authority_state.value if isinstance(authority_state, AuthorityState) else str(authority_state)
    view: dict[str, Any] = {
        "authority_state": state,
        "status": status,
    }
    if boundary_id is not None:
        view["boundary_id"] = boundary_id
    if authority_record_refs:
        view["authority_record_refs"] = list(authority_record_refs)
    if checked_evidence_refs:
        view["checked_evidence_refs"] = list(checked_evidence_refs)
    if would_block_reasons:
        view["would_block_reasons"] = list(would_block_reasons)
    if operator_summary is not None:
        view["operator_summary"] = operator_summary
    return view


__all__ = [
    "AuthorityRecord",
    "AuthorityState",
    "BoundaryContract",
    "BoundaryEvidence",
    "BoundaryGraph",
    "BoundaryOutcome",
    "BoundaryPhase",
    "BoundaryReceipt",
    "EvidenceProfile",
    "FindingSeverity",
    "SemanticFinding",
    "TemplateCompatibility",
    "TemplateCompatibilityResult",
    "TemporalPolicy",
    "boundary_contract_missing_topology_detail_keys",
    "check_template_compatibility",
    "classify_authority_state",
    "compile_authority_view",
]
