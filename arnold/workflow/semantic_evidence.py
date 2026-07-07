"""Structured semantic evidence and failure carriers for Megaplan checker diagnostics.

This module is intentionally declarative. It defines stable data shapes for
semantic evidence records and failure carriers that downstream checker,
row-evidence, and compatibility-quarantine work consume. It does not parse
source, resolve imports, or validate AST nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from arnold.manifest.refs import SourceSpan
from arnold.workflow.diagnostics import DiagnosticCode


class ConstructType(StrEnum):
    """Stable construct types for semantic evidence provenance."""

    HANDLER_FUNCTION = "handler_function"
    ROUTE_BRANCH = "route_branch"
    STEP_COMPONENT = "step_component"
    WORKFLOW_SOURCE = "workflow_source"
    CONFORMANCE_ROW = "conformance_row"
    COMPATIBILITY_ADAPTER = "compatibility_adapter"
    # ── S2 front-half construct types ─────────────────────────────────────
    PREP = "prep"
    PLAN = "plan"
    CRITIQUE = "critique"
    GATE = "gate"
    REVISE = "revise"
    # ── S3 tiebreaker/replan construct types ──────────────────────────────
    TIEBREAKER_RESEARCHER = "tiebreaker_researcher"
    TIEBREAKER_CHALLENGER = "tiebreaker_challenger"
    TIEBREAKER_SYNTHESIS = "tiebreaker_synthesis"
    TIEBREAKER_DECISION = "tiebreaker_decision"
    REPLAN_AUTHORITY = "replan_authority"
    PARENT_REJOIN = "parent_rejoin"
    # ── S4 execute construct types ─────────────────────────────────────────
    EXECUTE = "execute"


# ── S2 front-half stable row ID namespace ──────────────────────────────────
# Row IDs are intentionally versioned under 's2.' to allow S3+ to introduce a
# new namespace without collision.  The plan defers mapping these IDs to a
# traceability artifact; S2 introduces the namespace and uses it in tests.

S2_PREP_ROW_ID = "s2.prep.1"
S2_PLAN_ROW_ID = "s2.plan.1"
S2_CRITIQUE_ROW_ID = "s2.critique.1"
S2_GATE_ROW_ID = "s2.gate.1"
S2_REVISE_ROW_ID = "s2.revise.1"

# ── S3 tiebreaker/replan stable row ID namespace ───────────────────────────
# Row IDs are versioned under 's3.' to avoid collision with the S2 namespace.
# The plan defers mapping these IDs to a traceability artifact; S3 introduces
# the namespace and uses it in boundary contracts and tests.

S3_TIEBREAKER_RESEARCHER_ROW_ID = "s3.tiebreaker_researcher.1"
S3_TIEBREAKER_CHALLENGER_ROW_ID = "s3.tiebreaker_challenger.1"
S3_TIEBREAKER_SYNTHESIS_ROW_ID = "s3.tiebreaker_synthesis.1"
S3_TIEBREAKER_DECISION_ROW_ID = "s3.tiebreaker_decision.1"
S3_REPLAN_AUTHORITY_ROW_ID = "s3.replan_authority.1"
S3_PARENT_REJOIN_ROW_ID = "s3.parent_rejoin.1"

# ── S4 execute stable row ID namespace ──────────────────────────────────────
# Row IDs are versioned under 's4.' to avoid collision with the S2/S3 namespaces.
# The plan defers mapping these IDs to a traceability artifact; S4 introduces
# the namespace and uses it in boundary contracts and tests.

S4_EXECUTE_ROW_ID = "s4.execute.1"


class CompatibilityQuarantineCategory(StrEnum):
    """Stable quarantine categories for compatibility inventory entries."""

    MANIFEST_SERIALIZATION = "manifest_serialization"
    CLI_COMPATIBILITY = "cli_compatibility"
    PERSISTED_PAYLOAD = "persisted_payload"
    EXTERNAL_SCHEMA_BOUNDARY = "external_schema_boundary"
    ROUTE_DISPATCH_LEGACY = "route_dispatch_legacy"


@dataclass(frozen=True)
class CompatibilityQuarantineEntry:
    """A single compatibility quarantine entry recording a permitted
    enum-to-string serialization boundary.

    North Star compatibility quarantine: raw strings may only remain at
    explicit enum-to-string serialization adapters for manifests, CLI
    compatibility, persisted payloads, and external schema boundaries —
    never in workflow routing authority.
    """

    category: CompatibilityQuarantineCategory
    adapter_location: str
    enum_type: str
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "category", CompatibilityQuarantineCategory(self.category))


@dataclass(frozen=True)
class SemanticEvidence:
    """Structured semantic evidence for a single checker finding.

    Every proven conformance row must be backed by at least one
    SemanticEvidence record. This is the machine-readable carrier that
    replaces the old false-pass pattern of bare string status fields.
    """

    diagnostic_code: DiagnosticCode
    source_span: SourceSpan | None = None
    construct_type: ConstructType | None = None
    row_id: str | None = None
    checker_version: str = "arnold.workflow.semantic_evidence.v1"
    compatibility_quarantine: tuple[CompatibilityQuarantineEntry, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostic_code", DiagnosticCode(self.diagnostic_code))
        if self.construct_type is not None:
            object.__setattr__(self, "construct_type", ConstructType(self.construct_type))
        object.__setattr__(
            self, "compatibility_quarantine",
            tuple(
                CompatibilityQuarantineEntry(
                    category=e.category if isinstance(e, CompatibilityQuarantineEntry) else e["category"],
                    adapter_location=e.adapter_location if isinstance(e, CompatibilityQuarantineEntry) else e["adapter_location"],
                    enum_type=e.enum_type if isinstance(e, CompatibilityQuarantineEntry) else e["enum_type"],
                    note=e.note if isinstance(e, CompatibilityQuarantineEntry) else e.get("note", ""),
                )
                for e in self.compatibility_quarantine
            ),
        )
        object.__setattr__(self, "details", _freeze_evidence_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a sidecar-safe evidence payload with primitive values."""
        payload: dict[str, Any] = {
            "diagnostic_code": self.diagnostic_code.value,
            "checker_version": self.checker_version,
        }
        if self.source_span is not None:
            payload["source_span"] = {
                "path": self.source_span.path,
                "start_line": self.source_span.start_line,
                "start_column": self.source_span.start_column,
                "end_line": self.source_span.end_line,
                "end_column": self.source_span.end_column,
            }
        if self.construct_type is not None:
            payload["construct_type"] = self.construct_type.value
        if self.row_id is not None:
            payload["row_id"] = self.row_id
        if self.compatibility_quarantine:
            payload["compatibility_quarantine"] = [
                {
                    "category": e.category.value,
                    "adapter_location": e.adapter_location,
                    "enum_type": e.enum_type,
                    "note": e.note,
                }
                for e in self.compatibility_quarantine
            ]
        if self.details:
            payload["details"] = _thaw_evidence_value(self.details)
        return payload


@dataclass(frozen=True)
class SemanticFailure:
    """Aggregated semantic failure report for a single source construct.

    Carries one or more SemanticEvidence records plus an optional
    AuthoringDiagnostic for integration with the existing diagnostic path.
    """

    evidence: tuple[SemanticEvidence, ...]
    authoring_diagnostic_code: DiagnosticCode | None = None
    summary: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("SemanticFailure must carry at least one SemanticEvidence record")
        object.__setattr__(
            self, "evidence",
            tuple(
                SemanticEvidence(
                    diagnostic_code=e.diagnostic_code if isinstance(e, SemanticEvidence) else e["diagnostic_code"],
                    source_span=e.source_span if isinstance(e, SemanticEvidence) else e.get("source_span"),
                    construct_type=e.construct_type if isinstance(e, SemanticEvidence) else e.get("construct_type"),
                    row_id=e.row_id if isinstance(e, SemanticEvidence) else e.get("row_id"),
                    checker_version=e.checker_version if isinstance(e, SemanticEvidence) else e.get("checker_version", "arnold.workflow.semantic_evidence.v1"),
                    compatibility_quarantine=e.compatibility_quarantine if isinstance(e, SemanticEvidence) else e.get("compatibility_quarantine", ()),
                    details=e.details if isinstance(e, SemanticEvidence) else e.get("details", {}),
                )
                for e in self.evidence
            ),
        )
        if self.authoring_diagnostic_code is not None:
            object.__setattr__(self, "authoring_diagnostic_code", DiagnosticCode(self.authoring_diagnostic_code))
        object.__setattr__(self, "details", _freeze_evidence_mapping(self.details))

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable failure report."""
        payload: dict[str, Any] = {
            "evidence": [e.to_dict() for e in self.evidence],
            "summary": self.summary,
        }
        if self.authoring_diagnostic_code is not None:
            payload["authoring_diagnostic_code"] = self.authoring_diagnostic_code.value
        if self.details:
            payload["details"] = _thaw_evidence_value(self.details)
        return payload


# ── internal helpers ──────────────────────────────────────────────────────


def _freeze_evidence_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze_evidence_value(subvalue) for key, subvalue in value.items()})


def _freeze_evidence_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_evidence_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_evidence_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_evidence_value(item) for item in value)
    return value


def _thaw_evidence_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_evidence_value(subvalue) for key, subvalue in value.items()}
    if isinstance(value, tuple):
        return [_thaw_evidence_value(item) for item in value]
    return value


__all__ = [
    "CompatibilityQuarantineCategory",
    "CompatibilityQuarantineEntry",
    "ConstructType",
    "S2_CRITIQUE_ROW_ID",
    "S2_GATE_ROW_ID",
    "S2_PLAN_ROW_ID",
    "S2_PREP_ROW_ID",
    "S2_REVISE_ROW_ID",
    "S3_PARENT_REJOIN_ROW_ID",
    "S3_REPLAN_AUTHORITY_ROW_ID",
    "S3_TIEBREAKER_CHALLENGER_ROW_ID",
    "S3_TIEBREAKER_DECISION_ROW_ID",
    "S3_TIEBREAKER_RESEARCHER_ROW_ID",
    "S3_TIEBREAKER_SYNTHESIS_ROW_ID",
    "S4_EXECUTE_ROW_ID",
    "SemanticEvidence",
    "SemanticFailure",
]
