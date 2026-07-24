"""Frozen side-effect-free v1 dataclasses for the Critique Ledger domain.

Defines the complete type system for critique occurrence, reconciliation,
disposition, briefing, and manifest records. All dataclasses are frozen
and provide canonical to_dict/from_dict with strict/preserve modes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# ══════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════


class ContextMode(str, Enum):
    """Whether a critique was produced blind or with history awareness."""

    BLIND = "BLIND"
    HISTORY_AWARE = "HISTORY_AWARE"


class ParseStatus(str, Enum):
    """Outcome of parsing a critique producer output."""

    SELECTED = "SELECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DROPPED = "DROPPED"
    MALFORMED = "MALFORMED"
    TOMBSTONED = "TOMBSTONED"
    NO_ADDITIONAL_FINDINGS = "NO_ADDITIONAL_FINDINGS"


class EvidenceAvailability(str, Enum):
    """Availability classification for critique evidence artifacts."""

    RETAINED = "RETAINED"
    GOVERNED_REFERENCE = "GOVERNED_REFERENCE"
    UNAVAILABLE = "UNAVAILABLE"


class Relationship(str, Enum):
    """Semantic relationship between two findings, supplied by evaluator
    reconciliation events. Never inferred by deterministic code."""

    DUPLICATE = "DUPLICATE"
    SUPERSEDED = "SUPERSEDED"
    REGRESSION = "REGRESSION"
    REFINEMENT = "REFINEMENT"
    SPLIT = "SPLIT"
    REOPEN = "REOPEN"
    BLOCKS = "BLOCKS"
    BLOCKED_BY = "BLOCKED_BY"


class Authority(str, Enum):
    """Authority class for a disposition or reconciliation decision."""

    EVALUATOR = "EVALUATOR"
    CURATOR_PROPOSAL = "CURATOR_PROPOSAL"
    MANUAL = "MANUAL"


class CompatibilityProfile(str, Enum):
    """Schema compatibility profile for version-aware validation."""

    V1_STRICT = "v1_strict"
    V1_PRESERVE = "v1_preserve"


class DispositionFamily(str, Enum):
    """Eight canonical disposition families with orthogonal severity,
    reason subcodes, action/non-action, accountable scope, and reopen
    predicates."""

    ACTED_ON = "acted-on"
    IGNORED = "ignored"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    ACCEPTED_RISK = "accepted-risk"
    UNKNOWN = "unknown"
    RESOLVED = "resolved"


# ══════════════════════════════════════════════════════════════════════
# Schema version constants
# ══════════════════════════════════════════════════════════════════════

SCHEMA_VERSION = "cl.schema.v1"
SUPPORTED_VERSIONS = {SCHEMA_VERSION}

# ══════════════════════════════════════════════════════════════════════
# Hashing helpers
# ══════════════════════════════════════════════════════════════════════


def _freeze_value(value: Any) -> Any:
    """Recursively freeze a value for deterministic hashing.

    Lists/tuples become tuples of frozen elements.
    Dicts become sorted tuples of (key, frozen_value) pairs.
    Enums become their string values.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return tuple(
            sorted((str(k), _freeze_value(v)) for k, v in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_value(v) for v in value))
    return value


def freeze_for_hashing(obj: Any) -> tuple:
    """Produce a deterministic, hashable tuple representation.

    Dataclass instances are converted to (class_name, sorted_fields).
    """
    if hasattr(obj, "__dataclass_fields__"):
        fields_dict = {}
        for f_name in obj.__dataclass_fields__:
            val = getattr(obj, f_name)
            fields_dict[f_name] = val
        return (
            type(obj).__name__,
            _freeze_value(fields_dict),
        )
    return _freeze_value(obj)


def canonical_hash(obj: Any) -> str:
    """SHA-256 hex digest of the frozen representation."""
    frozen = freeze_for_hashing(obj)
    serialized = json.dumps(frozen, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


# ══════════════════════════════════════════════════════════════════════
# Serialization helpers
# ══════════════════════════════════════════════════════════════════════


def _serialize_value(value: Any) -> Any:
    """Convert a value to a JSON-serializable form."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(v) for v in value]
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _deserialize_value(cls: type, value: Any) -> Any:
    """Deserialize a JSON value back into the expected type."""
    if cls is Any or value is None:
        return value
    if isinstance(cls, type) and issubclass(cls, Enum):
        return cls(value)
    if hasattr(cls, "from_dict"):
        return cls.from_dict(value)
    return value


# ══════════════════════════════════════════════════════════════════════
# Dataclasses
# ══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CritiqueOccurrenceEnvelope:
    """A single critique occurrence produced by a model/producer during
    one critique round.

    Identity fields:
      - occurrence_id: producer-local identity within the execution attempt
      - finding_id: producer-local canonical finding identity
      - semantic_finding_id: evaluator-assigned semantic finding identity
        (may differ from finding_id when evaluator reconciliation maps
        multiple occurrences to one finding)

    All three identity fields are separately named and never conflated.
    """

    schema_version: str = SCHEMA_VERSION
    occurrence_id: str = ""
    attempt_id: str = ""
    round_label: str = ""
    finding_id: str = ""
    semantic_finding_id: str = ""
    producer_id: str = ""
    model_id: str = ""
    context_mode: str = ContextMode.BLIND.value
    parse_status: str = ParseStatus.SELECTED.value
    evidence_availability: str = EvidenceAvailability.RETAINED.value
    evidence_ref: Optional[str] = None
    redacted_prompt_hash: Optional[str] = None
    raw_prompt_hash: Optional[str] = None
    raw_completion_hash: Optional[str] = None
    unavailable_reason: Optional[str] = None
    reopen_condition: Optional[str] = None
    custody_receipt_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mode: str = "strict") -> dict[str, Any]:
        """Serialize to a plain dict.

        Args:
            mode: 'strict' rejects unknown extra fields.
                  'preserve' includes _extra fields.
        """
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "occurrence_id": self.occurrence_id,
            "attempt_id": self.attempt_id,
            "round_label": self.round_label,
            "finding_id": self.finding_id,
            "semantic_finding_id": self.semantic_finding_id,
            "producer_id": self.producer_id,
            "model_id": self.model_id,
            "context_mode": self.context_mode,
            "parse_status": self.parse_status,
            "evidence_availability": self.evidence_availability,
            "evidence_ref": self.evidence_ref,
            "redacted_prompt_hash": self.redacted_prompt_hash,
            "raw_prompt_hash": self.raw_prompt_hash,
            "raw_completion_hash": self.raw_completion_hash,
            "unavailable_reason": self.unavailable_reason,
            "reopen_condition": self.reopen_condition,
            "custody_receipt_refs": list(self.custody_receipt_refs),
            "metadata": dict(self.metadata),
        }
        if mode == "preserve" and self._extra:
            result.update(self._extra)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any], mode: str = "strict") -> "CritiqueOccurrenceEnvelope":
        """Deserialize from a plain dict.

        Args:
            data: The dict to deserialize.
            mode: 'strict' rejects unknown fields.
                  'preserve' stores unknown fields in _extra.

        Raises:
            ValueError: if mode is 'strict' and unknown fields are present,
                        or if schema_version is unsupported.
        """
        version = data.get("schema_version", SCHEMA_VERSION)
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version: {version!r}. "
                f"Supported: {SUPPORTED_VERSIONS}"
            )

        known_fields = {
            "schema_version", "occurrence_id", "attempt_id", "round_label",
            "finding_id", "semantic_finding_id", "producer_id", "model_id",
            "context_mode", "parse_status", "evidence_availability",
            "evidence_ref", "redacted_prompt_hash", "raw_prompt_hash",
            "raw_completion_hash", "unavailable_reason", "reopen_condition",
            "custody_receipt_refs", "metadata",
        }
        extra = {}
        for key in data:
            if key not in known_fields and key != "_extra":
                if mode == "strict":
                    raise ValueError(
                        f"Unknown field {key!r} in strict mode. "
                        f"Use mode='preserve' to retain unknown fields."
                    )
                extra[key] = data[key]

        custody = tuple(data.get("custody_receipt_refs", ()))
        return cls(
            schema_version=version,
            occurrence_id=data.get("occurrence_id", ""),
            attempt_id=data.get("attempt_id", ""),
            round_label=data.get("round_label", ""),
            finding_id=data.get("finding_id", ""),
            semantic_finding_id=data.get("semantic_finding_id", ""),
            producer_id=data.get("producer_id", ""),
            model_id=data.get("model_id", ""),
            context_mode=data.get("context_mode", ContextMode.BLIND.value),
            parse_status=data.get("parse_status", ParseStatus.SELECTED.value),
            evidence_availability=data.get(
                "evidence_availability", EvidenceAvailability.RETAINED.value
            ),
            evidence_ref=data.get("evidence_ref"),
            redacted_prompt_hash=data.get("redacted_prompt_hash"),
            raw_prompt_hash=data.get("raw_prompt_hash"),
            raw_completion_hash=data.get("raw_completion_hash"),
            unavailable_reason=data.get("unavailable_reason"),
            reopen_condition=data.get("reopen_condition"),
            custody_receipt_refs=custody,
            metadata=dict(data.get("metadata", {})),
            _extra=extra,
        )


@dataclass(frozen=True)
class FindingReconciliationEvent:
    """An evaluator-supplied reconciliation event that maps one or more
    occurrences to a single semantic finding.

    The reconciliation identity (reconciliation_id) is separate from the
    canonical finding identity (canonical_finding_id) and the semantic
    finding identity (semantic_finding_id). All three are distinct.
    """

    schema_version: str = SCHEMA_VERSION
    reconciliation_id: str = ""
    canonical_finding_id: str = ""
    semantic_finding_id: str = ""
    occurrence_ids: tuple[str, ...] = ()
    relationship: str = Relationship.DUPLICATE.value
    authority: str = Authority.EVALUATOR.value
    reason: str = ""
    evidence_refs: tuple[str, ...] = ()
    is_reopen: bool = False
    reopen_condition: Optional[str] = None
    timestamp_utc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mode: str = "strict") -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "reconciliation_id": self.reconciliation_id,
            "canonical_finding_id": self.canonical_finding_id,
            "semantic_finding_id": self.semantic_finding_id,
            "occurrence_ids": list(self.occurrence_ids),
            "relationship": self.relationship,
            "authority": self.authority,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "is_reopen": self.is_reopen,
            "reopen_condition": self.reopen_condition,
            "timestamp_utc": self.timestamp_utc,
            "metadata": dict(self.metadata),
        }
        if mode == "preserve" and self._extra:
            result.update(self._extra)
        return result

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], mode: str = "strict"
    ) -> "FindingReconciliationEvent":
        version = data.get("schema_version", SCHEMA_VERSION)
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported schema_version: {version!r}"
            )

        known_fields = {
            "schema_version", "reconciliation_id", "canonical_finding_id",
            "semantic_finding_id", "occurrence_ids", "relationship",
            "authority", "reason", "evidence_refs", "is_reopen",
            "reopen_condition", "timestamp_utc", "metadata",
        }
        extra = {}
        for key in data:
            if key not in known_fields and key != "_extra":
                if mode == "strict":
                    raise ValueError(f"Unknown field {key!r} in strict mode.")
                extra[key] = data[key]

        return cls(
            schema_version=version,
            reconciliation_id=data.get("reconciliation_id", ""),
            canonical_finding_id=data.get("canonical_finding_id", ""),
            semantic_finding_id=data.get("semantic_finding_id", ""),
            occurrence_ids=tuple(data.get("occurrence_ids", ())),
            relationship=data.get("relationship", Relationship.DUPLICATE.value),
            authority=data.get("authority", Authority.EVALUATOR.value),
            reason=data.get("reason", ""),
            evidence_refs=tuple(data.get("evidence_refs", ())),
            is_reopen=data.get("is_reopen", False),
            reopen_condition=data.get("reopen_condition"),
            timestamp_utc=data.get("timestamp_utc", ""),
            metadata=dict(data.get("metadata", {})),
            _extra=extra,
        )


@dataclass(frozen=True)
class FindingDispositionEvent:
    """An evaluator-assigned disposition for a semantic finding.

    Eight canonical families with reason subcodes, orthogonal severity,
    evidence limits, action/non-action, accountable scope, and reopen
    predicates.
    """

    schema_version: str = SCHEMA_VERSION
    disposition_id: str = ""
    semantic_finding_id: str = ""
    family: str = DispositionFamily.UNKNOWN.value
    reason_subcode: str = ""
    severity: str = ""
    action_taken: bool = False
    action_description: Optional[str] = None
    accountable_scope: str = ""
    is_reopen: bool = False
    reopen_predicate: Optional[str] = None
    evidence_refs: tuple[str, ...] = ()
    authority: str = Authority.EVALUATOR.value
    timestamp_utc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mode: str = "strict") -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "disposition_id": self.disposition_id,
            "semantic_finding_id": self.semantic_finding_id,
            "family": self.family,
            "reason_subcode": self.reason_subcode,
            "severity": self.severity,
            "action_taken": self.action_taken,
            "action_description": self.action_description,
            "accountable_scope": self.accountable_scope,
            "is_reopen": self.is_reopen,
            "reopen_predicate": self.reopen_predicate,
            "evidence_refs": list(self.evidence_refs),
            "authority": self.authority,
            "timestamp_utc": self.timestamp_utc,
            "metadata": dict(self.metadata),
        }
        if mode == "preserve" and self._extra:
            result.update(self._extra)
        return result

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], mode: str = "strict"
    ) -> "FindingDispositionEvent":
        version = data.get("schema_version", SCHEMA_VERSION)
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported schema_version: {version!r}")

        known_fields = {
            "schema_version", "disposition_id", "semantic_finding_id",
            "family", "reason_subcode", "severity", "action_taken",
            "action_description", "accountable_scope", "is_reopen",
            "reopen_predicate", "evidence_refs", "authority",
            "timestamp_utc", "metadata",
        }
        extra = {}
        for key in data:
            if key not in known_fields and key != "_extra":
                if mode == "strict":
                    raise ValueError(f"Unknown field {key!r} in strict mode.")
                extra[key] = data[key]

        return cls(
            schema_version=version,
            disposition_id=data.get("disposition_id", ""),
            semantic_finding_id=data.get("semantic_finding_id", ""),
            family=data.get("family", DispositionFamily.UNKNOWN.value),
            reason_subcode=data.get("reason_subcode", ""),
            severity=data.get("severity", ""),
            action_taken=data.get("action_taken", False),
            action_description=data.get("action_description"),
            accountable_scope=data.get("accountable_scope", ""),
            is_reopen=data.get("is_reopen", False),
            reopen_predicate=data.get("reopen_predicate"),
            evidence_refs=tuple(data.get("evidence_refs", ())),
            authority=data.get("authority", Authority.EVALUATOR.value),
            timestamp_utc=data.get("timestamp_utc", ""),
            metadata=dict(data.get("metadata", {})),
            _extra=extra,
        )


# ══════════════════════════════════════════════════════════════════════
# Provisional CL1 briefing budgets
# ══════════════════════════════════════════════════════════════════════

BRIEFING_BUDGETS = {
    "standard": {"max_domains": 2, "max_findings": 10},
    "high": {"max_domains": 4, "max_findings": 25},
    "exhaustive": {"max_domains": None, "max_findings": None},  # all / unbounded
}


@dataclass(frozen=True)
class DomainBriefingEnvelope:
    """A domain-scoped briefing built from an accepted LedgerRevisionManifest.

    Provisional CL1 budgets:
      - standard: 2 domains / 10 findings
      - high: 4 domains / 25 findings
      - exhaustive: all catalog domains / unbounded

    All budgets enforce mandatory domain floors. Overflow findings are
    linked via spillover references — never silently truncated.
    Silent truncation must raise an error.
    """

    schema_version: str = SCHEMA_VERSION
    briefing_id: str = ""
    revision_manifest_hash: str = ""
    budget_level: str = "standard"
    domains: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    open_findings: tuple[str, ...] = ()
    blocked_findings: tuple[str, ...] = ()
    accepted_risk_findings: tuple[str, ...] = ()
    unknown_findings: tuple[str, ...] = ()
    cross_domain_refs: tuple[str, ...] = ()
    spillover_findings: tuple[str, ...] = ()
    no_additional_findings: bool = False
    no_open_blocking_findings: bool = False
    no_known_findings: bool = False
    no_adjacent_text_match: bool = False
    is_truncated: bool = False
    truncation_warning: Optional[str] = None
    timestamp_utc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def validate_budget(
        cls, budget_level: str, domain_count: int, finding_count: int
    ) -> None:
        """Validate that domain/finding counts fit within the budget.

        Raises:
            ValueError: if budget_level is unknown or counts exceed budget
                        without explicit spillover handling.
        """
        if budget_level not in BRIEFING_BUDGETS:
            raise ValueError(
                f"Unknown budget_level: {budget_level!r}. "
                f"Valid: {list(BRIEFING_BUDGETS)}"
            )
        budget = BRIEFING_BUDGETS[budget_level]
        max_d = budget["max_domains"]
        max_f = budget["max_findings"]
        if max_d is not None and domain_count > max_d:
            raise ValueError(
                f"Domain count {domain_count} exceeds {budget_level} "
                f"budget max {max_d}. Use spillover, not silent truncation."
            )
        if max_f is not None and finding_count > max_f:
            raise ValueError(
                f"Finding count {finding_count} exceeds {budget_level} "
                f"budget max {max_f}. Use spillover, not silent truncation."
            )

    def to_dict(self, mode: str = "strict") -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "briefing_id": self.briefing_id,
            "revision_manifest_hash": self.revision_manifest_hash,
            "budget_level": self.budget_level,
            "domains": list(self.domains),
            "findings": list(self.findings),
            "open_findings": list(self.open_findings),
            "blocked_findings": list(self.blocked_findings),
            "accepted_risk_findings": list(self.accepted_risk_findings),
            "unknown_findings": list(self.unknown_findings),
            "cross_domain_refs": list(self.cross_domain_refs),
            "spillover_findings": list(self.spillover_findings),
            "no_additional_findings": self.no_additional_findings,
            "no_open_blocking_findings": self.no_open_blocking_findings,
            "no_known_findings": self.no_known_findings,
            "no_adjacent_text_match": self.no_adjacent_text_match,
            "is_truncated": self.is_truncated,
            "truncation_warning": self.truncation_warning,
            "timestamp_utc": self.timestamp_utc,
            "metadata": dict(self.metadata),
        }
        if mode == "preserve" and self._extra:
            result.update(self._extra)
        return result

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], mode: str = "strict"
    ) -> "DomainBriefingEnvelope":
        version = data.get("schema_version", SCHEMA_VERSION)
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported schema_version: {version!r}")

        known_fields = {
            "schema_version", "briefing_id", "revision_manifest_hash",
            "budget_level", "domains", "findings", "open_findings",
            "blocked_findings", "accepted_risk_findings", "unknown_findings",
            "cross_domain_refs", "spillover_findings",
            "no_additional_findings", "no_open_blocking_findings",
            "no_known_findings", "no_adjacent_text_match",
            "is_truncated", "truncation_warning", "timestamp_utc", "metadata",
        }
        extra = {}
        for key in data:
            if key not in known_fields and key != "_extra":
                if mode == "strict":
                    raise ValueError(f"Unknown field {key!r} in strict mode.")
                extra[key] = data[key]

        return cls(
            schema_version=version,
            briefing_id=data.get("briefing_id", ""),
            revision_manifest_hash=data.get("revision_manifest_hash", ""),
            budget_level=data.get("budget_level", "standard"),
            domains=tuple(data.get("domains", ())),
            findings=tuple(data.get("findings", ())),
            open_findings=tuple(data.get("open_findings", ())),
            blocked_findings=tuple(data.get("blocked_findings", ())),
            accepted_risk_findings=tuple(data.get("accepted_risk_findings", ())),
            unknown_findings=tuple(data.get("unknown_findings", ())),
            cross_domain_refs=tuple(data.get("cross_domain_refs", ())),
            spillover_findings=tuple(data.get("spillover_findings", ())),
            no_additional_findings=data.get("no_additional_findings", False),
            no_open_blocking_findings=data.get("no_open_blocking_findings", False),
            no_known_findings=data.get("no_known_findings", False),
            no_adjacent_text_match=data.get("no_adjacent_text_match", False),
            is_truncated=data.get("is_truncated", False),
            truncation_warning=data.get("truncation_warning"),
            timestamp_utc=data.get("timestamp_utc", ""),
            metadata=dict(data.get("metadata", {})),
            _extra=extra,
        )


@dataclass(frozen=True)
class LedgerRevisionManifest:
    """Exact freshness vectors and completeness maps for a critique
    ledger revision.

    Ties together:
      - input-set hashes (all sources consumed)
      - prior-revision hash chain
      - completeness maps per domain/schema
      - WBC receipt references
      - deterministic event ordering
    """

    schema_version: str = SCHEMA_VERSION
    manifest_id: str = ""
    revision_number: int = 1
    prior_revision_hash: Optional[str] = None
    input_set_hash: str = ""
    source_revisions: tuple[str, ...] = ()
    domain_completeness: dict[str, bool] = field(default_factory=dict)
    wbc_receipt_refs: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    included_reasons: dict[str, str] = field(default_factory=dict)
    excluded_reasons: dict[str, str] = field(default_factory=dict)
    cross_domain_refs: tuple[str, ...] = ()
    timestamp_utc: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, mode: str = "strict") -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "revision_number": self.revision_number,
            "prior_revision_hash": self.prior_revision_hash,
            "input_set_hash": self.input_set_hash,
            "source_revisions": list(self.source_revisions),
            "domain_completeness": dict(self.domain_completeness),
            "wbc_receipt_refs": list(self.wbc_receipt_refs),
            "event_ids": list(self.event_ids),
            "included_reasons": dict(self.included_reasons),
            "excluded_reasons": dict(self.excluded_reasons),
            "cross_domain_refs": list(self.cross_domain_refs),
            "timestamp_utc": self.timestamp_utc,
            "metadata": dict(self.metadata),
        }
        if mode == "preserve" and self._extra:
            result.update(self._extra)
        return result

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], mode: str = "strict"
    ) -> "LedgerRevisionManifest":
        version = data.get("schema_version", SCHEMA_VERSION)
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported schema_version: {version!r}")

        known_fields = {
            "schema_version", "manifest_id", "revision_number",
            "prior_revision_hash", "input_set_hash", "source_revisions",
            "domain_completeness", "wbc_receipt_refs", "event_ids",
            "included_reasons", "excluded_reasons", "cross_domain_refs",
            "timestamp_utc", "metadata",
        }
        extra = {}
        for key in data:
            if key not in known_fields and key != "_extra":
                if mode == "strict":
                    raise ValueError(f"Unknown field {key!r} in strict mode.")
                extra[key] = data[key]

        return cls(
            schema_version=version,
            manifest_id=data.get("manifest_id", ""),
            revision_number=data.get("revision_number", 1),
            prior_revision_hash=data.get("prior_revision_hash"),
            input_set_hash=data.get("input_set_hash", ""),
            source_revisions=tuple(data.get("source_revisions", ())),
            domain_completeness=dict(data.get("domain_completeness", {})),
            wbc_receipt_refs=tuple(data.get("wbc_receipt_refs", ())),
            event_ids=tuple(data.get("event_ids", ())),
            included_reasons=dict(data.get("included_reasons", {})),
            excluded_reasons=dict(data.get("excluded_reasons", {})),
            cross_domain_refs=tuple(data.get("cross_domain_refs", ())),
            timestamp_utc=data.get("timestamp_utc", ""),
            metadata=dict(data.get("metadata", {})),
            _extra=extra,
        )
