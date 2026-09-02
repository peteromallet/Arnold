"""Pure, non-authoritative completion evaluation for the C2 shadow kernel.

The records in this module deliberately live beside the neutral completion
schemas.  They do not import the product acceptance path and they never write
authority.  A verdict says what the shadow evaluator could prove for one
exact ``(spec, obligation, binding)`` identity; it is not an acceptance
receipt.

The evaluator admits evidence only when its binding and evidence coordinates
match the pinned binding.  It then content-deduplicates the admitted records
before evaluating the four initial proof modes.  Complete-capture proofs are
unknown until a named producer has supplied a complete capture marker.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Any

from arnold.workflow.completion.binding import CompletionBinding
from arnold.workflow.completion.evidence import (
    EvidenceScope,
    EvidenceScopeMismatch,
    scope_mismatches,
)
from arnold.workflow.completion.hashing import hash_canonical
from arnold.workflow.completion.spec import CompletionSpec, Obligation, ProofMode


EVIDENCE_SCHEMA_VERSION = "arnold.workflow.completion_evidence.v1"
OBLIGATION_RESULT_SCHEMA_VERSION = "arnold.workflow.completion_obligation_result.v1"
DIAGNOSTIC_SCHEMA_VERSION = "arnold.workflow.completion_diagnostic.v1"
VERDICT_SCHEMA_VERSION = "arnold.workflow.completion_verdict.v1"


class EvaluationStatus(StrEnum):
    """Status of one proof obligation or of the complete shadow verdict."""

    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    UNKNOWN = "unknown"
    WAIVED = "waived"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"
    SUSPENDED = "suspended"
    QUARANTINED = "quarantined"
    FAILED = "failed"


ObligationStatus = EvaluationStatus
VerdictStatus = EvaluationStatus


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def _freeze(value: Any) -> Any:
    """Return a recursively immutable JSON-like value."""

    if isinstance(value, Mapping):
        return _FrozenMapping(
            (str(key), _freeze(item)) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (str, int, bool, float)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("evidence values must contain finite numbers")
        return value
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(f"value must be JSON-like, got {type(value).__name__}")


class _FrozenMapping(tuple):
    """Tagged tuple used so immutable maps can be thawed without ambiguity."""


def _thaw(value: Any) -> Any:
    if isinstance(value, _FrozenMapping):
        return {key: _thaw(item) for key, item in value}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _text(value: Any, field: str, *, allow_empty: bool = True) -> str:
    text = "" if value is None else str(value).strip()
    if not allow_empty and not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def _as_tuple(value: Any, field: str = "value") -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        value = value.keys()
    if not isinstance(value, Iterable):
        return (str(value),)
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError(f"{field} cannot contain empty values")
    return result


def _choose_alias(primary: Any, aliases: Sequence[Any], field: str) -> Any:
    values = [
        value
        for value in (primary, *aliases)
        if value is not None and value != "" and value != () and value != []
    ]
    if not values:
        return None
    first = values[0]
    if any(repr(value) != repr(first) for value in values[1:]):
        raise ValueError(f"{field} received conflicting aliases")
    return first


def _enum_value(value: Any, enum_type: type[StrEnum], field: str) -> StrEnum:
    try:
        return value if isinstance(value, enum_type) else enum_type(str(value))
    except ValueError as exc:
        raise ValueError(f"unsupported {field}: {value!r}") from exc


@dataclass(frozen=True, init=False)
class EvidenceRecord:
    """A self-hashing evidence item associated with one binding and scope.

    ``evidence_id`` is a reference/display identity.  ``content_hash`` and
    ``evidence_hash`` are content identities and intentionally exclude the
    display identity and obligation links.  Thus the same receipt can be
    linked to more than one obligation, while repeating it cannot manufacture
    multiplicity.
    """

    kind: str
    content: Any
    binding_hash: str
    scope_hash: str
    evidence_id: str
    producer: str
    producer_version: str
    obligation_ids: tuple[str, ...]
    member_id: str
    capture_id: str
    capture_complete: bool | None
    admitted: bool
    stale: bool
    cursor: Any
    details: Any
    multiplicity: int
    scope: EvidenceScope | None
    content_hash: str
    evidence_hash: str

    def __init__(
        self,
        kind: str,
        content: Any = None,
        binding_hash: str = "",
        scope_hash: str = "",
        evidence_id: str = "",
        producer: str = "",
        producer_version: str = "",
        obligation_ids: Iterable[str] = (),
        member_id: Any = None,
        capture_id: str = "",
        capture_complete: bool | None = None,
        admitted: bool = True,
        stale: bool = False,
        cursor: Any = None,
        details: Any = None,
        multiplicity: int = 1,
        scope: EvidenceScope | Mapping[str, Any] | None = None,
        evidence_hash: str = "",
        *,
        payload: Any = None,
        value: Any = None,
        body: Any = None,
        content_hash: str = "",
        hash: str = "",
        record_hash: str = "",
        evidence_scope: EvidenceScope | Mapping[str, Any] | None = None,
        links: Iterable[str] = (),
        supports: Iterable[str] = (),
        obligation_id: str | None = None,
        provider: str = "",
        provider_version: str = "",
        capture_producer: str = "",
        complete_capture: bool | None = None,
        capture: Mapping[str, Any] | None = None,
        event_id: Any = None,
        item_id: Any = None,
        reference_id: Any = None,
        status: Any = None,
        is_admitted: bool | None = None,
        stale_evidence: bool | None = None,
    ) -> None:
        actual_content = _choose_alias(content, (payload, value, body), "content")
        actual_scope = _choose_alias(scope, (evidence_scope,), "scope")
        if isinstance(actual_scope, Mapping):
            actual_scope = EvidenceScope.from_dict(actual_scope)
        if actual_scope is not None and not isinstance(actual_scope, EvidenceScope):
            raise TypeError("scope must be an EvidenceScope or mapping")

        actual_binding = _text(binding_hash, "binding_hash")
        if actual_scope is not None and actual_scope.binding_hash:
            if actual_binding and actual_binding != actual_scope.binding_hash:
                raise ValueError("EvidenceRecord binding_hash conflicts with scope")
            actual_binding = actual_scope.binding_hash
        actual_scope_hash = _text(scope_hash, "scope_hash")
        if actual_scope is not None:
            if actual_scope_hash and actual_scope_hash != actual_scope.scope_hash:
                raise ValueError("EvidenceRecord scope_hash conflicts with scope")
            actual_scope_hash = actual_scope.scope_hash

        actual_producer = _text(_choose_alias(producer, (provider, capture_producer), "producer"), "producer")
        actual_producer_version = _text(_choose_alias(producer_version, (provider_version,), "producer_version"), "producer_version")
        complete_values = [item for item in (capture_complete, complete_capture) if item is not None]
        if complete_values and any(item != complete_values[0] for item in complete_values[1:]):
            raise ValueError("capture_complete received conflicting aliases")
        actual_complete = complete_values[0] if complete_values else None
        if actual_complete is not None and not isinstance(actual_complete, bool):
            raise TypeError("capture_complete must be bool or None")
        if capture and actual_complete is None:
            for key in ("capture_complete", "complete_capture", "complete"):
                if key in capture:
                    actual_complete = bool(capture[key])
                    break
        if isinstance(actual_content, Mapping) and actual_complete is None:
            for key in ("capture_complete", "complete_capture", "complete"):
                if key in actual_content:
                    actual_complete = bool(actual_content[key])
                    break
        if capture and not actual_producer:
            actual_producer = _text(capture.get("producer", capture.get("capture_producer", "")), "producer")
        if isinstance(actual_content, Mapping) and not actual_producer:
            actual_producer = _text(actual_content.get("producer", actual_content.get("capture_producer", "")), "producer")
        actual_capture_id = _text(capture_id or (capture or {}).get("capture_id", ""), "capture_id")

        link_values: list[str] = []
        for source in (obligation_ids, links, supports):
            link_values.extend(_as_tuple(source, "obligation_ids"))
        if obligation_id:
            link_values.append(str(obligation_id))
        actual_links = tuple(dict.fromkeys(link_values))

        actual_member = _choose_alias(member_id, (event_id, item_id), "member_id")
        if actual_member is None and isinstance(actual_content, Mapping):
            actual_member = next(
                (actual_content[key] for key in ("member_id", "event_id", "item_id") if key in actual_content),
                None,
            )
        actual_member_text = "" if actual_member is None else str(actual_member)
        actual_reference = _text(_choose_alias(evidence_id, (reference_id,), "evidence_id"), "evidence_id")
        actual_admitted = admitted if is_admitted is None else is_admitted
        actual_stale = stale if stale_evidence is None else stale_evidence
        if status is not None and str(status).lower() in {"stale", "stale_evidence"}:
            actual_stale = True
        if not isinstance(actual_admitted, bool) or not isinstance(actual_stale, bool):
            raise TypeError("admitted and stale must be bool")
        if isinstance(multiplicity, bool) or not isinstance(multiplicity, int) or multiplicity < 1:
            raise ValueError("multiplicity must be a positive integer")

        frozen_content = _freeze(actual_content)
        frozen_cursor = _freeze(cursor) if cursor is not None else None
        frozen_details = _freeze(details) if details is not None else None
        content_payload = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "kind": _text(kind, "kind", allow_empty=False),
            "content": _thaw(frozen_content),
            "binding_hash": actual_binding,
            "scope_hash": actual_scope_hash,
            "producer": actual_producer,
            "producer_version": actual_producer_version,
            "member_id": actual_member_text,
            "capture_id": actual_capture_id,
            "capture_complete": actual_complete,
            "cursor": _thaw(frozen_cursor),
            "details": _thaw(frozen_details),
            "multiplicity": multiplicity,
        }
        expected_hash = hash_canonical(content_payload)
        supplied_hashes = [item for item in (evidence_hash, content_hash, hash, record_hash) if item]
        if supplied_hashes and any(item != expected_hash for item in supplied_hashes):
            raise ValueError("EvidenceRecord content/evidence hash mismatch")
        if not actual_reference:
            actual_reference = expected_hash

        object.__setattr__(self, "kind", _text(kind, "kind", allow_empty=False))
        object.__setattr__(self, "content", frozen_content)
        object.__setattr__(self, "binding_hash", actual_binding)
        object.__setattr__(self, "scope_hash", actual_scope_hash)
        object.__setattr__(self, "evidence_id", actual_reference)
        object.__setattr__(self, "producer", actual_producer)
        object.__setattr__(self, "producer_version", actual_producer_version)
        object.__setattr__(self, "obligation_ids", actual_links)
        object.__setattr__(self, "member_id", actual_member_text)
        object.__setattr__(self, "capture_id", actual_capture_id)
        object.__setattr__(self, "capture_complete", actual_complete)
        object.__setattr__(self, "admitted", actual_admitted)
        object.__setattr__(self, "stale", actual_stale)
        object.__setattr__(self, "cursor", frozen_cursor)
        object.__setattr__(self, "details", frozen_details)
        object.__setattr__(self, "multiplicity", multiplicity)
        object.__setattr__(self, "scope", actual_scope)
        object.__setattr__(self, "content_hash", expected_hash)
        object.__setattr__(self, "evidence_hash", expected_hash)

    @property
    def hash(self) -> str:
        return self.content_hash

    @property
    def reference_id(self) -> str:
        return self.evidence_id

    @property
    def obligation_links(self) -> tuple[str, ...]:
        return self.obligation_ids

    @property
    def evidence_scope(self) -> EvidenceScope | None:
        return self.scope

    @property
    def is_capture_marker(self) -> bool:
        kind = self.kind.lower().replace("-", "_")
        return self.capture_complete is not None or kind in {
            "capture",
            "capture_marker",
            "capture_receipt",
            "complete_capture",
            "complete_capture_receipt",
        }

    @property
    def is_complete_capture(self) -> bool:
        return self.is_capture_marker and self.capture_complete is True

    @property
    def capture_producer(self) -> str:
        return self.producer

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "kind": self.kind,
            "content": _thaw(self.content),
            "binding_hash": self.binding_hash,
            "scope_hash": self.scope_hash,
            "evidence_id": self.evidence_id,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "obligation_ids": list(self.obligation_ids),
            "member_id": self.member_id,
            "capture_id": self.capture_id,
            "capture_complete": self.capture_complete,
            "admitted": self.admitted,
            "stale": self.stale,
            "cursor": _thaw(self.cursor),
            "details": _thaw(self.details),
            "multiplicity": self.multiplicity,
            "content_hash": self.content_hash,
            "evidence_hash": self.evidence_hash,
        }
        if self.scope is not None:
            result["scope"] = self.scope.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceRecord":
        return cls(
            kind=data["kind"],
            content=data.get("content", data.get("payload")),
            binding_hash=str(data.get("binding_hash", "")),
            scope_hash=str(data.get("scope_hash", "")),
            evidence_id=str(data.get("evidence_id", data.get("reference_id", ""))),
            producer=str(data.get("producer", data.get("provider", ""))),
            producer_version=str(data.get("producer_version", data.get("provider_version", ""))),
            obligation_ids=data.get("obligation_ids", data.get("links", ())),
            member_id=data.get("member_id", data.get("event_id", data.get("item_id"))),
            capture_id=str(data.get("capture_id", "")),
            capture_complete=data.get("capture_complete", data.get("complete_capture")),
            admitted=bool(data.get("admitted", True)),
            stale=bool(data.get("stale", False)),
            cursor=data.get("cursor"),
            details=data.get("details"),
            multiplicity=int(data.get("multiplicity", 1)),
            scope=data.get("scope", data.get("evidence_scope")),
            evidence_hash=str(data.get("evidence_hash", data.get("content_hash", ""))),
        )


HashedEvidence = EvidenceRecord
Evidence = EvidenceRecord
EvidenceItem = EvidenceRecord
EvidenceRef = EvidenceRecord


@dataclass(frozen=True, init=False)
class Diagnostic:
    """Stable, machine-readable causal diagnostic and repair frontier."""

    code: str
    message: str
    severity: DiagnosticSeverity
    obligation_id: str
    evidence_ids: tuple[str, ...]
    cause: str
    repair_frontier: tuple[str, ...]
    details: Any
    diagnostic_hash: str

    def __init__(
        self,
        code: str,
        message: str = "",
        severity: DiagnosticSeverity | str = DiagnosticSeverity.ERROR,
        obligation_id: str = "",
        evidence_ids: Iterable[str] = (),
        cause: str = "",
        repair_frontier: Iterable[str] = (),
        details: Any = None,
        diagnostic_hash: str = "",
        *,
        causal_occurrence: str = "",
        frontier: Iterable[str] = (),
    ) -> None:
        actual_cause = _choose_alias(cause, (causal_occurrence,), "cause") or str(code)
        actual_frontier = _choose_alias(repair_frontier, (frontier,), "repair_frontier")
        actual_severity = _enum_value(severity, DiagnosticSeverity, "severity")
        frozen_details = _freeze(details) if details is not None else None
        payload = {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "code": _text(code, "code", allow_empty=False),
            "message": _text(message or code, "message", allow_empty=False),
            "severity": actual_severity.value,
            "obligation_id": _text(obligation_id, "obligation_id"),
            "evidence_ids": list(_as_tuple(evidence_ids, "evidence_ids")),
            "cause": _text(actual_cause, "cause", allow_empty=False),
            "repair_frontier": list(_as_tuple(actual_frontier, "repair_frontier")),
            "details": _thaw(frozen_details),
        }
        expected_hash = hash_canonical(payload)
        if diagnostic_hash and diagnostic_hash != expected_hash:
            raise ValueError("Diagnostic diagnostic_hash mismatch")
        object.__setattr__(self, "code", payload["code"])
        object.__setattr__(self, "message", payload["message"])
        object.__setattr__(self, "severity", actual_severity)
        object.__setattr__(self, "obligation_id", payload["obligation_id"])
        object.__setattr__(self, "evidence_ids", tuple(payload["evidence_ids"]))
        object.__setattr__(self, "cause", payload["cause"])
        object.__setattr__(self, "repair_frontier", tuple(payload["repair_frontier"]))
        object.__setattr__(self, "details", frozen_details)
        object.__setattr__(self, "diagnostic_hash", expected_hash)

    @property
    def causal_occurrence(self) -> str:
        return self.cause

    @property
    def frontier(self) -> tuple[str, ...]:
        return self.repair_frontier

    @property
    def hash(self) -> str:
        return self.diagnostic_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "obligation_id": self.obligation_id,
            "evidence_ids": list(self.evidence_ids),
            "cause": self.cause,
            "causal_occurrence": self.cause,
            "repair_frontier": list(self.repair_frontier),
            "details": _thaw(self.details),
            "diagnostic_hash": self.diagnostic_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Diagnostic":
        return cls(
            code=str(data["code"]),
            message=str(data.get("message", data["code"])),
            severity=str(data.get("severity", "error")),
            obligation_id=str(data.get("obligation_id", "")),
            evidence_ids=data.get("evidence_ids", ()),
            cause=str(data.get("cause", data.get("causal_occurrence", data["code"]))),
            repair_frontier=data.get("repair_frontier", data.get("frontier", ())),
            details=data.get("details"),
            diagnostic_hash=str(data.get("diagnostic_hash", "")),
        )


EvaluationDiagnostic = Diagnostic
DiagnosticRecord = Diagnostic


@dataclass(frozen=True, init=False)
class ObligationResult:
    """The complete result for one obligation and exact binding identity."""

    obligation_id: str
    status: EvaluationStatus
    kind: ProofMode
    spec_hash: str
    binding_hash: str
    required: bool
    evidence_ids: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]
    observed_count: int
    expected_count: int | None
    observed_ids: tuple[str, ...]
    expected_ids: tuple[str, ...]
    aggregate_value: Any
    result_hash: str

    def __init__(
        self,
        obligation_id: str,
        status: EvaluationStatus | str,
        kind: ProofMode | str = ProofMode.PRESENCE,
        spec_hash: str = "",
        binding_hash: str = "",
        required: bool = True,
        evidence_ids: Iterable[str] = (),
        diagnostics: Iterable[Diagnostic | Mapping[str, Any]] = (),
        observed_count: int = 0,
        expected_count: int | None = None,
        observed_ids: Iterable[str] = (),
        expected_ids: Iterable[str] = (),
        aggregate_value: Any = None,
        result_hash: str = "",
        *,
        proof_mode: ProofMode | str | None = None,
        result: EvaluationStatus | str | None = None,
    ) -> None:
        actual_kind = _enum_value(proof_mode if proof_mode is not None else kind, ProofMode, "proof mode")
        actual_status = _enum_value(result if result is not None else status, EvaluationStatus, "evaluation status")
        actual_diagnostics = tuple(
            item if isinstance(item, Diagnostic) else Diagnostic.from_dict(item) for item in diagnostics
        )
        if isinstance(observed_count, bool) or observed_count < 0:
            raise ValueError("observed_count must be non-negative")
        if expected_count is not None and (isinstance(expected_count, bool) or expected_count < 0):
            raise ValueError("expected_count must be non-negative or None")
        frozen_aggregate = _freeze(aggregate_value) if aggregate_value is not None else None
        payload = {
            "schema_version": OBLIGATION_RESULT_SCHEMA_VERSION,
            "obligation_id": _text(obligation_id, "obligation_id", allow_empty=False),
            "status": actual_status.value,
            "kind": actual_kind.value,
            "spec_hash": _text(spec_hash, "spec_hash"),
            "binding_hash": _text(binding_hash, "binding_hash"),
            "required": bool(required),
            "evidence_ids": list(_as_tuple(evidence_ids, "evidence_ids")),
            "diagnostics": [item.to_dict() for item in actual_diagnostics],
            "observed_count": observed_count,
            "expected_count": expected_count,
            "observed_ids": list(_as_tuple(observed_ids, "observed_ids")),
            "expected_ids": list(_as_tuple(expected_ids, "expected_ids")),
            "aggregate_value": _thaw(frozen_aggregate),
        }
        expected_hash = hash_canonical(payload)
        if result_hash and result_hash != expected_hash:
            raise ValueError("ObligationResult result_hash mismatch")
        for name, value in {
            "obligation_id": payload["obligation_id"],
            "status": actual_status,
            "kind": actual_kind,
            "spec_hash": payload["spec_hash"],
            "binding_hash": payload["binding_hash"],
            "required": payload["required"],
            "evidence_ids": tuple(payload["evidence_ids"]),
            "diagnostics": actual_diagnostics,
            "observed_count": observed_count,
            "expected_count": expected_count,
            "observed_ids": tuple(payload["observed_ids"]),
            "expected_ids": tuple(payload["expected_ids"]),
            "aggregate_value": frozen_aggregate,
            "result_hash": expected_hash,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def proof_mode(self) -> ProofMode:
        return self.kind

    @property
    def satisfied(self) -> bool:
        return self.status in {EvaluationStatus.SATISFIED, EvaluationStatus.WAIVED}

    @property
    def accepted(self) -> bool:
        return self.satisfied

    @property
    def unknown(self) -> bool:
        return self.status is EvaluationStatus.UNKNOWN

    @property
    def failed(self) -> bool:
        return self.status is EvaluationStatus.UNSATISFIED

    @property
    def reuse_identity(self) -> tuple[str, str, str]:
        return (self.spec_hash, self.obligation_id, self.binding_hash)

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.reuse_identity

    @property
    def hash(self) -> str:
        return self.result_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OBLIGATION_RESULT_SCHEMA_VERSION,
            "obligation_id": self.obligation_id,
            "status": self.status.value,
            "kind": self.kind.value,
            "proof_mode": self.kind.value,
            "spec_hash": self.spec_hash,
            "binding_hash": self.binding_hash,
            "required": self.required,
            "evidence_ids": list(self.evidence_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "observed_count": self.observed_count,
            "expected_count": self.expected_count,
            "observed_ids": list(self.observed_ids),
            "expected_ids": list(self.expected_ids),
            "aggregate_value": _thaw(self.aggregate_value),
            "result_hash": self.result_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObligationResult":
        return cls(
            obligation_id=str(data["obligation_id"]),
            status=str(data["status"]),
            kind=str(data.get("kind", data.get("proof_mode", "presence"))),
            spec_hash=str(data.get("spec_hash", "")),
            binding_hash=str(data.get("binding_hash", "")),
            required=bool(data.get("required", True)),
            evidence_ids=data.get("evidence_ids", ()),
            diagnostics=data.get("diagnostics", ()),
            observed_count=int(data.get("observed_count", 0)),
            expected_count=data.get("expected_count"),
            observed_ids=data.get("observed_ids", ()),
            expected_ids=data.get("expected_ids", ()),
            aggregate_value=data.get("aggregate_value"),
            result_hash=str(data.get("result_hash", "")),
        )


ObligationEvaluation = ObligationResult
ObligationResultRecord = ObligationResult


def _hashed_record(schema_version: str, payload: Mapping[str, Any], supplied: str = "") -> str:
    expected = hash_canonical({"schema_version": schema_version, **dict(payload)})
    if supplied and supplied != expected:
        raise ValueError(f"{schema_version} hash mismatch")
    return expected


@dataclass(frozen=True, init=False)
class CandidateSelection:
    """The single candidate chosen before any obligation is applicable."""

    declared_candidates: tuple[str, ...]
    selected_candidate: str
    applicability: Any
    selection_hash: str

    def __init__(
        self,
        declared_candidates: Iterable[str] = (),
        selected_candidate: str = "",
        applicability: Any = None,
        selection_hash: str = "",
        *,
        candidates: Iterable[str] | None = None,
        selected: str | None = None,
    ) -> None:
        declared = tuple(dict.fromkeys(_as_tuple(
            declared_candidates if candidates is None else candidates,
            "declared_candidates",
        )))
        chosen = _text(selected_candidate if selected is None else selected, "selected_candidate")
        if len(declared) != 1:
            raise ValueError("candidate selection requires exactly one declared candidate")
        if chosen != declared[0]:
            raise ValueError("selected candidate is not the sole declared candidate")
        frozen_applicability = _freeze(applicability) if applicability is not None else None
        payload = {
            "declared_candidates": list(declared),
            "selected_candidate": chosen,
            "applicability": _thaw(frozen_applicability),
        }
        expected = _hashed_record("arnold.workflow.completion_candidate_selection.v1", payload, selection_hash)
        object.__setattr__(self, "declared_candidates", declared)
        object.__setattr__(self, "selected_candidate", chosen)
        object.__setattr__(self, "applicability", frozen_applicability)
        object.__setattr__(self, "selection_hash", expected)

    @property
    def selected(self) -> str:
        return self.selected_candidate

    @property
    def hash(self) -> str:
        return self.selection_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "arnold.workflow.completion_candidate_selection.v1",
            "declared_candidates": list(self.declared_candidates),
            "selected_candidate": self.selected_candidate,
            "applicability": _thaw(self.applicability),
            "selection_hash": self.selection_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateSelection":
        return cls(
            declared_candidates=data.get("declared_candidates", data.get("candidates", ())),
            selected_candidate=str(data.get("selected_candidate", data.get("selected", ""))),
            applicability=data.get("applicability"),
            selection_hash=str(data.get("selection_hash", data.get("hash", ""))),
        )


@dataclass(frozen=True, init=False)
class BlockedProof:
    """Typed proof that a candidate is blocked and how it can recover."""

    blocker_id: str
    causal_evidence_ids: tuple[str, ...]
    authority_coordinates: Any
    custody_coordinates: Any
    next_admission: str
    recovery_disposition: str
    binding_hash: str
    proof_hash: str

    def __init__(
        self,
        blocker_id: str = "",
        causal_evidence_ids: Iterable[str] = (),
        authority_coordinates: Any = None,
        custody_coordinates: Any = None,
        next_admission: str = "",
        recovery_disposition: str = "",
        binding_hash: str = "",
        proof_hash: str = "",
        *,
        evidence_ids: Iterable[str] | None = None,
        authority: Any = None,
        custody: Any = None,
        disposition: str | None = None,
        recovery: str | None = None,
    ) -> None:
        ids = tuple(dict.fromkeys(_as_tuple(
            causal_evidence_ids if evidence_ids is None else evidence_ids,
            "causal_evidence_ids",
        )))
        blocker = _text(blocker_id, "blocker_id", allow_empty=False)
        next_step = _text(next_admission, "next_admission", allow_empty=False)
        recovery_step = _text(
            recovery_disposition if recovery is None else recovery,
            "recovery_disposition",
            allow_empty=False,
        )
        authority_value = authority_coordinates if authority is None else authority
        custody_value = custody_coordinates if custody is None else custody
        if not ids or authority_value is None or custody_value is None:
            raise ValueError("blocked proof requires causal evidence, authority, and custody coordinates")
        payload = {
            "blocker_id": blocker,
            "causal_evidence_ids": list(ids),
            "authority_coordinates": authority_value,
            "custody_coordinates": custody_value,
            "next_admission": next_step,
            "recovery_disposition": recovery_step,
            "binding_hash": binding_hash,
        }
        expected = _hashed_record("arnold.workflow.completion_blocked_proof.v1", payload, proof_hash)
        for name, value in {
            "blocker_id": blocker,
            "causal_evidence_ids": ids,
            "authority_coordinates": _freeze(authority_value),
            "custody_coordinates": _freeze(custody_value),
            "next_admission": next_step,
            "recovery_disposition": recovery_step,
            "binding_hash": str(binding_hash),
            "proof_hash": expected,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return self.causal_evidence_ids

    @property
    def hash(self) -> str:
        return self.proof_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "arnold.workflow.completion_blocked_proof.v1",
            "blocker_id": self.blocker_id,
            "causal_evidence_ids": list(self.causal_evidence_ids),
            "evidence_ids": list(self.causal_evidence_ids),
            "authority_coordinates": _thaw(self.authority_coordinates),
            "custody_coordinates": _thaw(self.custody_coordinates),
            "next_admission": self.next_admission,
            "recovery_disposition": self.recovery_disposition,
            "binding_hash": self.binding_hash,
            "proof_hash": self.proof_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlockedProof":
        return cls(
            blocker_id=str(data.get("blocker_id", data.get("id", ""))),
            causal_evidence_ids=data.get("causal_evidence_ids", data.get("evidence_ids", ())),
            authority_coordinates=data.get("authority_coordinates", data.get("authority")),
            custody_coordinates=data.get("custody_coordinates", data.get("custody")),
            next_admission=str(data.get("next_admission", data.get("next_admission_disposition", ""))),
            recovery_disposition=str(data.get("recovery_disposition", data.get("recovery", data.get("disposition", "")))),
            binding_hash=str(data.get("binding_hash", "")),
            proof_hash=str(data.get("proof_hash", data.get("hash", ""))),
        )


@dataclass(frozen=True, init=False)
class WaiverProof:
    """Typed, scoped waiver proof carrying immutable taint."""

    authority_provenance: Any
    scope: Any
    reason: str
    evidence_ids: tuple[str, ...]
    expiry: Any
    taint: frozenset[str]
    binding_hash: str
    proof_hash: str

    def __init__(
        self,
        authority_provenance: Any = None,
        scope: Any = None,
        reason: str = "",
        evidence_ids: Iterable[str] = (),
        expiry: Any = None,
        taint: Iterable[str] = (),
        binding_hash: str = "",
        proof_hash: str = "",
        *,
        authority: Any = None,
        waiver_scope: Any = None,
        expires: Any = None,
    ) -> None:
        authority_value = authority_provenance if authority is None else authority
        scope_value = scope if waiver_scope is None else waiver_scope
        actual_expiry = expiry if expires is None else expires
        ids = tuple(dict.fromkeys(_as_tuple(evidence_ids, "evidence_ids")))
        actual_taint = frozenset(str(item) for item in taint) | frozenset({"waived"})
        if authority_value is None or scope_value is None or not _text(reason, "reason", allow_empty=False):
            raise ValueError("waiver proof requires authority provenance, scope, and reason")
        if actual_expiry is None:
            raise ValueError("waiver proof requires an expiry")
        if not ids:
            raise ValueError("waiver proof requires evidence")
        payload = {
            "authority_provenance": authority_value,
            "scope": scope_value,
            "reason": str(reason).strip(),
            "evidence_ids": list(ids),
            "expiry": actual_expiry,
            "taint": sorted(actual_taint),
            "binding_hash": binding_hash,
        }
        expected = _hashed_record("arnold.workflow.completion_waiver_proof.v1", payload, proof_hash)
        for name, value in {
            "authority_provenance": _freeze(authority_value),
            "scope": _freeze(scope_value),
            "reason": payload["reason"],
            "evidence_ids": ids,
            "expiry": _freeze(actual_expiry),
            "taint": actual_taint,
            "binding_hash": str(binding_hash),
            "proof_hash": expected,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def hash(self) -> str:
        return self.proof_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "arnold.workflow.completion_waiver_proof.v1",
            "authority_provenance": _thaw(self.authority_provenance),
            "scope": _thaw(self.scope),
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "expiry": _thaw(self.expiry),
            "taint": sorted(self.taint),
            "binding_hash": self.binding_hash,
            "proof_hash": self.proof_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WaiverProof":
        return cls(
            authority_provenance=data.get("authority_provenance", data.get("authority")),
            scope=data.get("scope", data.get("waiver_scope")),
            reason=str(data.get("reason", "")),
            evidence_ids=data.get("evidence_ids", ()),
            expiry=data.get("expiry", data.get("expires")),
            taint=data.get("taint", ()),
            binding_hash=str(data.get("binding_hash", "")),
            proof_hash=str(data.get("proof_hash", data.get("hash", ""))),
        )


@dataclass(frozen=True, init=False)
class TerminalPolicy:
    """An independently admitted policy allowing a non-success terminal."""

    permitted_outcomes: frozenset[str]
    evidence_ids: tuple[str, ...]
    admitted: bool
    independent: bool
    producer: str
    trust_domain: str
    policy_hash: str

    def __init__(
        self,
        permitted_outcomes: Iterable[str] = (),
        evidence_ids: Iterable[str] = (),
        admitted: bool = False,
        independent: bool = False,
        producer: str = "",
        trust_domain: str = "",
        policy_hash: str = "",
        *,
        outcomes: Iterable[str] | None = None,
        allowed_outcomes: Iterable[str] | None = None,
        independently_admitted: bool | None = None,
    ) -> None:
        raw_outcomes = permitted_outcomes
        if outcomes is not None:
            raw_outcomes = outcomes
        if allowed_outcomes is not None:
            raw_outcomes = allowed_outcomes
        actual_outcomes = frozenset(_as_tuple(raw_outcomes, "permitted_outcomes"))
        actual_independent = independent if independently_admitted is None else independently_admitted
        actual_producer = _text(producer, "producer")
        actual_trust = _text(trust_domain, "trust_domain")
        ids = tuple(dict.fromkeys(_as_tuple(evidence_ids, "evidence_ids")))
        payload = {
            "permitted_outcomes": sorted(actual_outcomes),
            "evidence_ids": list(ids),
            "admitted": bool(admitted),
            "independent": bool(actual_independent),
            "producer": actual_producer,
            "trust_domain": actual_trust,
        }
        expected = _hashed_record("arnold.workflow.completion_terminal_policy.v1", payload, policy_hash)
        for name, value in {
            "permitted_outcomes": actual_outcomes,
            "evidence_ids": ids,
            "admitted": bool(admitted),
            "independent": bool(actual_independent),
            "producer": actual_producer,
            "trust_domain": actual_trust,
            "policy_hash": expected,
        }.items():
            object.__setattr__(self, name, value)

    def permits(self, outcome: str) -> bool:
        return self.admitted and self.independent and bool(self.evidence_ids) and outcome in self.permitted_outcomes

    @property
    def hash(self) -> str:
        return self.policy_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "arnold.workflow.completion_terminal_policy.v1",
            "permitted_outcomes": sorted(self.permitted_outcomes),
            "evidence_ids": list(self.evidence_ids),
            "admitted": self.admitted,
            "independent": self.independent,
            "producer": self.producer,
            "trust_domain": self.trust_domain,
            "policy_hash": self.policy_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerminalPolicy":
        return cls(
            permitted_outcomes=data.get("permitted_outcomes", data.get("allowed_outcomes", data.get("outcomes", ()))),
            evidence_ids=data.get("evidence_ids", ()),
            admitted=bool(data.get("admitted", False)),
            independent=bool(data.get("independent", data.get("independently_admitted", False))),
            producer=str(data.get("producer", "")),
            trust_domain=str(data.get("trust_domain", "")),
            policy_hash=str(data.get("policy_hash", data.get("hash", ""))),
        )


@dataclass(frozen=True, init=False)
class VerifierIndependence:
    """Machine-checkable provenance result for the shadow verifier."""

    implementation_provenance: str
    producer_identity: str
    trust_domain: str
    primary_evidence_access: bool
    independent: bool
    reasons: tuple[str, ...]
    independence_hash: str

    def __init__(
        self,
        implementation_provenance: str = "",
        producer_identity: str = "",
        trust_domain: str = "",
        primary_evidence_access: bool = False,
        independent: bool | None = None,
        reasons: Iterable[str] = (),
        independence_hash: str = "",
        *,
        implementation: str | None = None,
        producer: str | None = None,
        direct_primary_evidence_access: bool | None = None,
    ) -> None:
        actual_implementation = implementation_provenance if implementation is None else implementation
        actual_producer = producer_identity if producer is None else producer
        actual_access = primary_evidence_access if direct_primary_evidence_access is None else direct_primary_evidence_access
        reason_values = tuple(dict.fromkeys(str(item) for item in reasons))
        actual_independent = bool(independent) if independent is not None else bool(
            actual_implementation and actual_producer and trust_domain and actual_access and not reason_values
        )
        payload = {
            "implementation_provenance": str(actual_implementation),
            "producer_identity": str(actual_producer),
            "trust_domain": str(trust_domain),
            "primary_evidence_access": bool(actual_access),
            "independent": actual_independent,
            "reasons": list(reason_values),
        }
        expected = _hashed_record("arnold.workflow.completion_verifier_independence.v1", payload, independence_hash)
        for name, value in {
            "implementation_provenance": payload["implementation_provenance"],
            "producer_identity": payload["producer_identity"],
            "trust_domain": payload["trust_domain"],
            "primary_evidence_access": payload["primary_evidence_access"],
            "independent": actual_independent,
            "reasons": reason_values,
            "independence_hash": expected,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def valid(self) -> bool:
        return self.independent

    @property
    def hash(self) -> str:
        return self.independence_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "arnold.workflow.completion_verifier_independence.v1",
            "implementation_provenance": self.implementation_provenance,
            "producer_identity": self.producer_identity,
            "trust_domain": self.trust_domain,
            "primary_evidence_access": self.primary_evidence_access,
            "independent": self.independent,
            "reasons": list(self.reasons),
            "independence_hash": self.independence_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VerifierIndependence":
        return cls(
            implementation_provenance=str(data.get("implementation_provenance", data.get("implementation", ""))),
            producer_identity=str(data.get("producer_identity", data.get("producer", ""))),
            trust_domain=str(data.get("trust_domain", "")),
            primary_evidence_access=bool(data.get("primary_evidence_access", data.get("direct_primary_evidence_access", False))),
            independent=bool(data.get("independent", False)),
            reasons=data.get("reasons", ()),
            independence_hash=str(data.get("independence_hash", data.get("hash", ""))),
        )


# Friendly aliases used by callers that name the proof by its outcome.
BlockedOutcomeProof = BlockedProof
WaiverOutcomeProof = WaiverProof
TerminalDispositionPolicy = TerminalPolicy
VerifierIndependenceProof = VerifierIndependence


@dataclass(frozen=True, init=False)
class CompletionVerdict:
    """Immutable shadow verdict for one candidate and one exact binding."""

    spec_hash: str
    binding_hash: str
    outcome: str
    status: EvaluationStatus
    accepted: bool
    obligation_results: tuple[ObligationResult, ...]
    evidence: tuple[EvidenceRecord, ...]
    diagnostics: tuple[Diagnostic, ...]
    candidate_selection: CandidateSelection | None
    exceptional_proof: BlockedProof | WaiverProof | None
    terminal_policy: TerminalPolicy | None
    terminal: bool
    taint: frozenset[str]
    verifier_independence: VerifierIndependence | None
    verifier: str
    verifier_version: str
    verdict_hash: str

    def __init__(
        self,
        spec_hash: str = "",
        binding_hash: str = "",
        outcome: Any = "success",
        obligation_results: Iterable[ObligationResult | Mapping[str, Any]] = (),
        evidence: Iterable[EvidenceRecord | Mapping[str, Any]] = (),
        diagnostics: Iterable[Diagnostic | Mapping[str, Any]] = (),
        accepted: bool | None = None,
        status: EvaluationStatus | str | None = None,
        verifier: str = "completion-shadow",
        verifier_version: str = EVIDENCE_SCHEMA_VERSION,
        verdict_hash: str = "",
        *,
        results: Iterable[ObligationResult | Mapping[str, Any]] | None = None,
        evidence_refs: Iterable[EvidenceRecord | Mapping[str, Any]] | None = None,
        candidate_outcome: Any = None,
        overall_status: EvaluationStatus | str | None = None,
        candidate_selection: CandidateSelection | Mapping[str, Any] | None = None,
        exceptional_proof: BlockedProof | WaiverProof | Mapping[str, Any] | None = None,
        terminal_policy: TerminalPolicy | Mapping[str, Any] | None = None,
        terminal: bool = False,
        taint: Iterable[str] = (),
        verifier_independence: VerifierIndependence | Mapping[str, Any] | None = None,
    ) -> None:
        raw_results = results if results is not None else obligation_results
        actual_results = tuple(
            item if isinstance(item, ObligationResult) else ObligationResult.from_dict(item) for item in raw_results
        )
        raw_evidence = evidence_refs if evidence_refs is not None else evidence
        actual_evidence = tuple(
            item if isinstance(item, EvidenceRecord) else EvidenceRecord.from_dict(item) for item in raw_evidence
        )
        actual_diagnostics = tuple(
            item if isinstance(item, Diagnostic) else Diagnostic.from_dict(item) for item in diagnostics
        )
        actual_candidate = (
            candidate_selection
            if isinstance(candidate_selection, CandidateSelection) or candidate_selection is None
            else CandidateSelection.from_dict(candidate_selection)
        )
        if isinstance(exceptional_proof, Mapping):
            proof_kind = str(exceptional_proof.get("outcome", "")).lower()
            exceptional_proof = (
                WaiverProof.from_dict(exceptional_proof)
                if proof_kind == "waived" or "authority_provenance" in exceptional_proof
                else BlockedProof.from_dict(exceptional_proof)
            )
        actual_independence = (
            verifier_independence
            if isinstance(verifier_independence, VerifierIndependence) or verifier_independence is None
            else VerifierIndependence.from_dict(verifier_independence)
        )
        actual_policy = (
            terminal_policy
            if isinstance(terminal_policy, TerminalPolicy) or terminal_policy is None
            else TerminalPolicy.from_dict(terminal_policy)
        )
        actual_taint = frozenset(str(item) for item in taint)
        if isinstance(exceptional_proof, WaiverProof):
            actual_taint = actual_taint | exceptional_proof.taint
        actual_outcome = _text(candidate_outcome if candidate_outcome is not None else outcome, "outcome") or "success"
        required_results = tuple(item for item in actual_results if item.required)
        logical_accepted = bool(required_results) and all(item.satisfied for item in required_results)
        actual_accepted = logical_accepted if accepted is None else bool(accepted)
        if actual_accepted and not logical_accepted:
            raise ValueError("CompletionVerdict cannot be accepted with an unsatisfied required obligation")
        if overall_status is not None:
            actual_status = _enum_value(overall_status, EvaluationStatus, "verdict status")
        elif status is not None:
            actual_status = _enum_value(status, EvaluationStatus, "verdict status")
        elif actual_accepted:
            actual_status = EvaluationStatus.SATISFIED
        elif any(item.unknown for item in required_results):
            actual_status = EvaluationStatus.UNKNOWN
        elif any(item.failed for item in required_results):
            actual_status = EvaluationStatus.UNSATISFIED
        else:
            actual_status = EvaluationStatus.UNKNOWN
        payload = {
            "schema_version": VERDICT_SCHEMA_VERSION,
            "spec_hash": _text(spec_hash, "spec_hash"),
            "binding_hash": _text(binding_hash, "binding_hash"),
            "outcome": actual_outcome,
            "status": actual_status.value,
            "accepted": actual_accepted,
            "obligation_results": [item.to_dict() for item in actual_results],
            "evidence": [item.to_dict() for item in actual_evidence],
            "diagnostics": [item.to_dict() for item in actual_diagnostics],
            "candidate_selection": actual_candidate.to_dict() if actual_candidate else None,
            "exceptional_proof": exceptional_proof.to_dict() if exceptional_proof else None,
            "terminal_policy": actual_policy.to_dict() if actual_policy else None,
            "terminal": bool(terminal),
            "taint": sorted(actual_taint),
            "verifier_independence": actual_independence.to_dict() if actual_independence else None,
            "verifier": _text(verifier, "verifier"),
            "verifier_version": _text(verifier_version, "verifier_version"),
        }
        expected_hash = hash_canonical(payload)
        if verdict_hash and verdict_hash != expected_hash:
            raise ValueError("CompletionVerdict verdict_hash mismatch")
        for name, value in {
            "spec_hash": payload["spec_hash"],
            "binding_hash": payload["binding_hash"],
            "outcome": actual_outcome,
            "status": actual_status,
            "accepted": actual_accepted,
            "obligation_results": actual_results,
            "evidence": actual_evidence,
            "diagnostics": actual_diagnostics,
            "candidate_selection": actual_candidate,
            "exceptional_proof": exceptional_proof,
            "terminal_policy": actual_policy,
            "terminal": bool(terminal),
            "taint": actual_taint,
            "verifier_independence": actual_independence,
            "verifier": payload["verifier"],
            "verifier_version": payload["verifier_version"],
            "verdict_hash": expected_hash,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def candidate_outcome(self) -> str:
        return self.outcome

    @property
    def results(self) -> tuple[ObligationResult, ...]:
        return self.obligation_results

    @property
    def evidence_refs(self) -> tuple[EvidenceRecord, ...]:
        return self.evidence

    @property
    def selected_candidate(self) -> str | None:
        return self.candidate_selection.selected_candidate if self.candidate_selection else None

    @property
    def waiver_taint(self) -> frozenset[str]:
        return self.taint

    @property
    def independent(self) -> bool | None:
        return self.verifier_independence.independent if self.verifier_independence else None

    @property
    def unknown(self) -> bool:
        return self.status is EvaluationStatus.UNKNOWN

    @property
    def satisfied(self) -> bool:
        return self.accepted

    @property
    def reuse_identities(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(item.reuse_identity for item in self.obligation_results)

    @property
    def hash(self) -> str:
        return self.verdict_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": VERDICT_SCHEMA_VERSION,
            "spec_hash": self.spec_hash,
            "binding_hash": self.binding_hash,
            "outcome": self.outcome,
            "candidate_outcome": self.outcome,
            "status": self.status.value,
            "accepted": self.accepted,
            "obligation_results": [item.to_dict() for item in self.obligation_results],
            "results": [item.to_dict() for item in self.obligation_results],
            "evidence": [item.to_dict() for item in self.evidence],
            "evidence_refs": [item.to_dict() for item in self.evidence],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "candidate_selection": self.candidate_selection.to_dict() if self.candidate_selection else None,
            "exceptional_proof": self.exceptional_proof.to_dict() if self.exceptional_proof else None,
            "terminal_policy": self.terminal_policy.to_dict() if self.terminal_policy else None,
            "terminal": self.terminal,
            "taint": sorted(self.taint),
            "verifier_independence": self.verifier_independence.to_dict() if self.verifier_independence else None,
            "verifier": self.verifier,
            "verifier_version": self.verifier_version,
            "verdict_hash": self.verdict_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompletionVerdict":
        return cls(
            spec_hash=str(data.get("spec_hash", "")),
            binding_hash=str(data.get("binding_hash", "")),
            outcome=data.get("outcome", data.get("candidate_outcome", "success")),
            obligation_results=data.get("obligation_results", data.get("results", ())),
            evidence=data.get("evidence", data.get("evidence_refs", ())),
            diagnostics=data.get("diagnostics", ()),
            candidate_selection=data.get("candidate_selection"),
            exceptional_proof=data.get("exceptional_proof"),
            terminal_policy=data.get("terminal_policy"),
            terminal=bool(data.get("terminal", False)),
            taint=data.get("taint", ()),
            verifier_independence=data.get("verifier_independence"),
            accepted=bool(data.get("accepted", False)),
            status=data.get("status"),
            verifier=str(data.get("verifier", "completion-shadow")),
            verifier_version=str(data.get("verifier_version", EVIDENCE_SCHEMA_VERSION)),
            verdict_hash=str(data.get("verdict_hash", "")),
        )


ShadowCompletionVerdict = CompletionVerdict
CompletionVerdictRecord = CompletionVerdict


def _coerce_spec(value: CompletionSpec | Mapping[str, Any]) -> CompletionSpec:
    return value if isinstance(value, CompletionSpec) else CompletionSpec.from_dict(value)


def _coerce_binding(value: CompletionBinding | Mapping[str, Any]) -> CompletionBinding:
    return value if isinstance(value, CompletionBinding) else CompletionBinding.from_dict(value)


def _coerce_evidence(value: EvidenceRecord | Mapping[str, Any]) -> EvidenceRecord:
    return value if isinstance(value, EvidenceRecord) else EvidenceRecord.from_dict(value)


def _candidate_name(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("candidate", "outcome", "name", "id", "candidate_id"):
            if key in value:
                return _text(value[key], "candidate", allow_empty=False)
    return _text(value, "candidate", allow_empty=False)


def select_candidate(
    candidate_outcome: Any = "success",
    *,
    declared_candidates: Any = None,
    candidates: Any = None,
    selected_candidate: str | None = None,
) -> CandidateSelection:
    """Select exactly one declared candidate, before applicability is read."""

    declared_value = candidates if candidates is not None else declared_candidates
    selected_value = selected_candidate
    if isinstance(candidate_outcome, Mapping):
        if selected_value is None:
            selected_value = candidate_outcome.get(
                "selected_candidate",
                candidate_outcome.get("selected", candidate_outcome.get("outcome")),
            )
        if declared_value is None:
            declared_value = candidate_outcome.get(
                "declared_candidates",
                candidate_outcome.get("candidates"),
            )
    if declared_value is None:
        if isinstance(candidate_outcome, (list, tuple, set, frozenset)):
            declared_value = candidate_outcome
        else:
            declared_value = (candidate_outcome,)
    if isinstance(declared_value, Mapping):
        declared_value = declared_value.get(
            "declared_candidates",
            declared_value.get("candidates", tuple(declared_value)),
        )
    declared = tuple(dict.fromkeys(_candidate_name(item) for item in declared_value))
    chosen = _candidate_name(selected_value if selected_value is not None else candidate_outcome)
    return CandidateSelection(declared, chosen)


def _applicable_obligations(
    selection: CandidateSelection,
    applicability: Any,
    obligations: Sequence[Obligation],
) -> tuple[tuple[Obligation, ...], Diagnostic | None]:
    """Resolve applicability only after candidate selection.

    Applicability is declarative.  Callables and references to evidence,
    results, or the selected candidate are rejected because they make the
    candidate/obligation decision circular or observer-dependent.
    """

    if applicability is None:
        return tuple(obligations), None
    if callable(applicability):
        return (), _diagnostic(
            "CIRCULAR_APPLICABILITY",
            "callable applicability could observe evaluation results",
            cause="circular-applicability",
            repair_frontier=(f"candidate:{selection.selected_candidate}:applicability",),
        )
    source = applicability
    if isinstance(source, Mapping) and selection.selected_candidate in source:
        source = source[selection.selected_candidate]
    if isinstance(source, Mapping):
        depends = source.get("depends_on", source.get("based_on", ()))
        dependency_names = {str(item).lower() for item in _as_tuple(depends, "depends_on")}
        if dependency_names & {
            "candidate",
            "selected_candidate",
            "outcome",
            "verdict",
            "evidence",
            "results",
            "obligation_results",
        }:
            return (), _diagnostic(
                "CIRCULAR_APPLICABILITY",
                "obligation applicability depends on candidate or evaluation results",
                cause="circular-applicability",
                repair_frontier=(f"candidate:{selection.selected_candidate}:applicability",),
            )
        source = source.get("obligations", source.get("applicable_obligations", source))
    if isinstance(source, bool):
        source = [item.obligation_id for item in obligations] if source else []
    if isinstance(source, str):
        source = (source,)
    if not isinstance(source, Iterable):
        return (), _diagnostic(
            "APPLICABILITY_INVALID",
            "applicability must be a static obligation-id collection",
            cause="invalid-applicability",
            repair_frontier=(f"candidate:{selection.selected_candidate}:applicability",),
        )
    names = {str(item) for item in source}
    applicable = tuple(item for item in obligations if item.obligation_id in names)
    unknown = names - {item.obligation_id for item in obligations}
    if unknown:
        return (), _diagnostic(
            "APPLICABILITY_UNKNOWN_OBLIGATION",
            "applicability names an obligation outside the declared spec",
            cause="unknown-applicability-obligation",
            repair_frontier=(f"candidate:{selection.selected_candidate}:applicability",),
            details={"unknown_obligations": sorted(unknown)},
        )
    return applicable, None


def verify_verifier_independence(
    provenance: VerifierIndependence | Mapping[str, Any] | None,
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]] = (),
    *,
    verifier: str = "completion-shadow",
) -> VerifierIndependence:
    """Check all four independence dimensions and reject relabelled wrappers."""

    if isinstance(provenance, VerifierIndependence):
        return provenance
    data = dict(provenance or {})
    implementation = str(data.get(
        "implementation_provenance",
        data.get("implementation", data.get("code_provenance", data.get("code", ""))),
    ))
    producer = str(data.get(
        "producer_identity",
        data.get("producer", data.get("verifier_identity", verifier)),
    ))
    trust_domain = str(data.get("trust_domain", data.get("domain", "")))
    direct_access = bool(data.get(
        "primary_evidence_access",
        data.get("direct_primary_evidence_access", data.get("direct_access", False)),
    ))
    primary_implementation = str(data.get(
        "primary_implementation_provenance",
        data.get("producer_implementation", data.get("primary_code_provenance", "")),
    ))
    primary_producer = str(data.get("primary_producer_identity", data.get("primary_producer", "")))
    primary_domain = str(data.get("primary_trust_domain", data.get("primary_domain", "")))
    records = tuple(_coerce_evidence(item) for item in evidence)
    evidence_producers = {item.producer for item in records if item.producer}
    if not primary_producer and len(evidence_producers) == 1:
        primary_producer = next(iter(evidence_producers))
    reasons: list[str] = []
    if not implementation:
        reasons.append("missing implementation provenance")
    if not producer:
        reasons.append("missing producer identity")
    if not trust_domain:
        reasons.append("missing trust domain")
    if not direct_access:
        reasons.append("verifier lacks direct primary-evidence access")
    if primary_implementation and implementation == primary_implementation:
        reasons.append("verifier reuses primary implementation provenance")
    if primary_producer and producer == primary_producer:
        reasons.append("verifier producer identity equals primary producer")
    if primary_domain and trust_domain == primary_domain:
        reasons.append("verifier trust domain equals primary trust domain")
    return VerifierIndependence(
        implementation_provenance=implementation,
        producer_identity=producer,
        trust_domain=trust_domain,
        primary_evidence_access=direct_access,
        independent=not reasons,
        reasons=reasons,
    )


def propagate_waiver_taint(*values: Any) -> frozenset[str]:
    """Join waiver labels through an arbitrary child/result graph immutably."""

    labels: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, WaiverProof):
            labels.update(value.taint)
            return
        if isinstance(value, CompletionVerdict):
            labels.update(value.taint)
            return
        if isinstance(value, Mapping):
            if "taint" in value:
                visit(value["taint"])
            for key in ("children", "results", "obligations", "proof", "waiver_proof"):
                if key in value:
                    visit(value[key])
            return
        if isinstance(value, (str, bytes)):
            labels.add(value.decode() if isinstance(value, bytes) else value)
            return
        if isinstance(value, Iterable):
            for item in value:
                visit(item)

    for value in values:
        visit(value)
    return frozenset(labels)


combine_waiver_taint = propagate_waiver_taint
transitive_waiver_taint = propagate_waiver_taint


def _diagnostic(
    code: str,
    message: str,
    *,
    obligation_id: str = "",
    evidence_ids: Iterable[str] = (),
    cause: str | None = None,
    repair_frontier: Iterable[str] = (),
    details: Any = None,
    severity: DiagnosticSeverity | str = DiagnosticSeverity.ERROR,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        message=message,
        severity=severity,
        obligation_id=obligation_id,
        evidence_ids=evidence_ids,
        cause=cause or code,
        repair_frontier=repair_frontier,
        details=details,
    )


def _deduplicate(records: Iterable[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
    """Deduplicate by content identity while retaining first-seen order.

    Obligation links are relationship metadata and are therefore unioned when
    duplicate references carry different explicit links.  No other content is
    merged, so duplicate receipts still contribute only one proof item.
    """

    selected: dict[str, EvidenceRecord] = {}
    for record in records:
        previous = selected.get(record.content_hash)
        if previous is None:
            selected[record.content_hash] = record
            continue
        links = tuple(dict.fromkeys(previous.obligation_ids + record.obligation_ids))
        if links != previous.obligation_ids:
            payload = previous.to_dict()
            payload["obligation_ids"] = list(links)
            selected[record.content_hash] = EvidenceRecord.from_dict(payload)
    return tuple(selected.values())


def deduplicate_evidence(records: Iterable[EvidenceRecord | Mapping[str, Any]]) -> tuple[EvidenceRecord, ...]:
    """Public content-deduplication helper used by the shadow evaluator."""

    return _deduplicate(_coerce_evidence(item) for item in records)


def _admit_records(
    binding: CompletionBinding,
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]],
) -> tuple[tuple[EvidenceRecord, ...], tuple[Diagnostic, ...]]:
    admitted: list[EvidenceRecord] = []
    diagnostics: list[Diagnostic] = []
    expected_scope = binding.evidence_scope
    for index, raw in enumerate(evidence):
        try:
            record = _coerce_evidence(raw)
        except (TypeError, ValueError, KeyError) as exc:
            diagnostics.append(
                _diagnostic(
                    "INVALID_EVIDENCE",
                    f"evidence item {index} is invalid: {exc}",
                    cause="invalid-evidence",
                    repair_frontier=(f"evidence:{index}",),
                )
            )
            continue
        if not record.admitted:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_NOT_ADMITTED",
                    f"evidence {record.evidence_id} is not admitted",
                    evidence_ids=(record.evidence_id,),
                    cause="evidence-not-admitted",
                    repair_frontier=(f"evidence:{record.evidence_id}",),
                )
            )
            continue
        if record.stale:
            diagnostics.append(
                _diagnostic(
                    "STALE_EVIDENCE",
                    f"evidence {record.evidence_id} is stale",
                    evidence_ids=(record.evidence_id,),
                    cause="stale-evidence",
                    repair_frontier=(f"evidence:{record.evidence_id}",),
                )
            )
            continue
        if record.binding_hash != binding.binding_hash:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_BINDING_MISMATCH",
                    f"evidence {record.evidence_id} is bound to a different binding",
                    evidence_ids=(record.evidence_id,),
                    cause="binding-mismatch",
                    repair_frontier=(f"binding:{binding.binding_hash}",),
                )
            )
            continue
        if expected_scope is None:
            diagnostics.append(
                _diagnostic(
                    "LEGACY_BINDING_UNKNOWN",
                    "legacy C1 binding has no admissible C2 evidence scope",
                    evidence_ids=(record.evidence_id,),
                    cause="legacy-binding-unknown",
                    repair_frontier=("binding:migrate",),
                )
            )
            continue
        if not record.scope_hash:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_SCOPE_MISSING",
                    f"evidence {record.evidence_id} has no bound evidence scope",
                    evidence_ids=(record.evidence_id,),
                    cause="scope-missing",
                    repair_frontier=(f"evidence:{record.evidence_id}",),
                )
            )
            continue
        if record.scope is not None:
            try:
                mismatches = scope_mismatches(expected_scope, record.scope)
            except (TypeError, ValueError, EvidenceScopeMismatch) as exc:
                mismatches = (f"scope-invalid:{exc}",)
        else:
            mismatches = () if record.scope_hash == expected_scope.scope_hash else ("scope_hash",)
        if record.scope_hash != expected_scope.scope_hash:
            mismatches = tuple(dict.fromkeys((*mismatches, "scope_hash")))
        if mismatches:
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_OUT_OF_SCOPE",
                    f"evidence {record.evidence_id} is outside the pinned evidence scope",
                    evidence_ids=(record.evidence_id,),
                    cause="out-of-scope-evidence",
                    repair_frontier=(f"scope:{expected_scope.scope_hash}",),
                    details={"mismatches": list(mismatches)},
                )
            )
            continue
        if record.cursor is not None and not expected_scope.evidence_window.contains(record.cursor):
            diagnostics.append(
                _diagnostic(
                    "EVIDENCE_CURSOR_OUT_OF_SCOPE",
                    f"evidence {record.evidence_id} has a cursor outside the pinned window",
                    evidence_ids=(record.evidence_id,),
                    cause="cursor-out-of-scope",
                    repair_frontier=(f"scope:{expected_scope.scope_hash}",),
                )
            )
            continue
        admitted.append(record)
    return _deduplicate(admitted), tuple(diagnostics)


def admit_evidence_for_binding(
    binding: CompletionBinding | Mapping[str, Any],
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]],
) -> tuple[tuple[EvidenceRecord, ...], tuple[Diagnostic, ...]]:
    """Return only scope/binding-admitted, content-deduplicated evidence."""

    return _admit_records(_coerce_binding(binding), evidence)


def _capture_state(
    records: Sequence[EvidenceRecord],
    *,
    complete_capture: bool | None,
    capture_producer: str | None,
) -> tuple[bool | None, str, tuple[Diagnostic, ...]]:
    markers = tuple(record for record in records if record.is_capture_marker)
    explicit_producer = _text(capture_producer, "capture_producer")
    if complete_capture is not None and not isinstance(complete_capture, bool):
        raise TypeError("complete_capture must be bool or None")
    values = [record.capture_complete for record in markers if record.capture_complete is not None]
    values = list(dict.fromkeys(values))
    if complete_capture is not None:
        values.append(complete_capture)
        values = list(dict.fromkeys(values))
    if len(values) > 1:
        return (
            None,
            "",
            (
                _diagnostic(
                    "CAPTURE_COMPLETENESS_CONFLICT",
                    "capture evidence contains conflicting completeness declarations",
                    cause="capture-completeness-conflict",
                    repair_frontier=("capture:complete",),
                ),
            ),
        )
    if not values:
        # Presence and aggregate proofs do not need a capture marker.  The
        # absence/set evaluators issue their mode-specific unknown diagnostic
        # when they observe this ``None`` state.
        return None, "", ()
    actual_complete = values[0]
    producers = tuple(dict.fromkeys(record.capture_producer for record in markers if record.capture_producer))
    if explicit_producer:
        producers = tuple(dict.fromkeys((*producers, explicit_producer)))
    if actual_complete and not producers:
        return True, "", ()
    if len(producers) > 1:
        return (
            None,
            "",
            (
                _diagnostic(
                    "CAPTURE_PRODUCER_CONFLICT",
                    "capture evidence names more than one producer",
                    cause="capture-producer-conflict",
                    repair_frontier=("capture:producer",),
                    details={"producers": list(producers)},
                ),
            ),
        )
    if not actual_complete:
        return False, producers[0] if producers else "", ()
    return True, producers[0], ()


def _relevant(
    records: Sequence[EvidenceRecord],
    obligation: Obligation,
) -> tuple[EvidenceRecord, ...]:
    targets = set(obligation.target_evidence_kinds)
    result: list[EvidenceRecord] = []
    for record in records:
        if record.is_capture_marker:
            continue
        if targets and record.kind not in targets:
            continue
        if record.obligation_ids and obligation.obligation_id not in record.obligation_ids:
            continue
        result.append(record)
    return tuple(result)


def _member_id(record: EvidenceRecord) -> str:
    if record.member_id:
        return record.member_id
    content = _thaw(record.content)
    if isinstance(content, Mapping):
        for key in ("member_id", "event_id", "item_id", "id", "key", "name"):
            if key in content:
                return str(content[key])
    return record.evidence_id


def _expected_for(
    obligation: Obligation,
    expected_ids: Any,
    capture_records: Sequence[EvidenceRecord],
) -> tuple[str, ...] | None:
    candidate = expected_ids
    if isinstance(expected_ids, Mapping):
        if obligation.obligation_id in expected_ids:
            candidate = expected_ids[obligation.obligation_id]
        elif "expected_ids" in expected_ids:
            candidate = expected_ids["expected_ids"]
        elif "declared_ids" in expected_ids:
            candidate = expected_ids["declared_ids"]
        else:
            candidate = None
    if candidate is not None:
        return tuple(dict.fromkeys(_as_tuple(candidate, "expected_ids")))
    for marker in capture_records:
        content = _thaw(marker.content)
        if not isinstance(content, Mapping):
            continue
        raw = content.get("expected_ids", content.get("declared_ids", content.get("members")))
        if isinstance(raw, Mapping):
            raw = raw.get(obligation.obligation_id)
        if raw is not None:
            return tuple(dict.fromkeys(_as_tuple(raw, "expected_ids")))
    return None


def _aggregate_rule(aggregate: Any, obligation: Obligation) -> Any:
    if isinstance(aggregate, Mapping):
        if obligation.obligation_id in aggregate:
            return aggregate[obligation.obligation_id]
        if any(key in aggregate for key in ("operator", "op", "function", "expected", "threshold", "minimum", "maximum")):
            return aggregate
        return None
    return aggregate


def _numeric_value(record: EvidenceRecord) -> Any:
    content = _thaw(record.content)
    if isinstance(content, Mapping):
        for key in ("value", "amount", "contribution", "total"):
            if key in content:
                return content[key]
    return content


def _evaluate_aggregate(
    obligation: Obligation,
    records: Sequence[EvidenceRecord],
    rule: Any,
) -> tuple[EvaluationStatus, tuple[Diagnostic, ...], Any, int | None]:
    if rule is None:
        return (
            EvaluationStatus.UNKNOWN,
            (
                _diagnostic(
                    "AGGREGATE_RULE_MISSING",
                    "aggregate proof has no deterministic aggregate rule",
                    obligation_id=obligation.obligation_id,
                    cause="aggregate-rule-missing",
                    repair_frontier=(f"obligation:{obligation.obligation_id}:aggregate",),
                ),
            ),
            None,
            None,
        )
    values = tuple(_numeric_value(record) for record in records for _ in range(record.multiplicity))
    unique_values = tuple(_numeric_value(record) for record in records)
    if callable(rule):
        try:
            actual = rule(records)
        except Exception as exc:  # pragma: no cover - defensive boundary
            return (
                EvaluationStatus.UNKNOWN,
                (
                    _diagnostic(
                        "AGGREGATE_EVALUATION_ERROR",
                        f"aggregate rule raised {exc!r}",
                        obligation_id=obligation.obligation_id,
                        cause="aggregate-evaluation-error",
                        repair_frontier=(f"obligation:{obligation.obligation_id}:aggregate",),
                    ),
                ),
                None,
                None,
            )
        expected = None
        operator = "callable"
    else:
        rule_map = rule if isinstance(rule, Mapping) else {"expected": rule}
        operator = str(rule_map.get("operator", rule_map.get("op", rule_map.get("function", "sum")))).lower()
        expected = rule_map.get("expected", rule_map.get("value"))
        if operator in {"threshold", "at_least", "minimum"}:
            expected = rule_map.get("threshold", rule_map.get("minimum", expected))
        if operator in {"at_most", "maximum"}:
            expected = rule_map.get("threshold", rule_map.get("maximum", expected))
        try:
            if operator == "sum":
                actual = sum(unique_values)
            elif operator == "count":
                actual = len(records)
            elif operator == "min":
                actual = min(unique_values) if unique_values else None
            elif operator == "max":
                actual = max(unique_values) if unique_values else None
            elif operator in {"threshold", "at_least", "minimum"}:
                actual = sum(unique_values)
                expected = (">=", expected)
            elif operator in {"at_most", "maximum"}:
                actual = sum(unique_values)
                expected = ("<=", expected)
            elif operator in {"any", "all"}:
                actual = any(values) if operator == "any" else all(values)
            else:
                return (
                    EvaluationStatus.UNKNOWN,
                    (
                        _diagnostic(
                            "AGGREGATE_OPERATOR_UNKNOWN",
                            f"unsupported aggregate operator {operator!r}",
                            obligation_id=obligation.obligation_id,
                            cause="aggregate-operator-unknown",
                            repair_frontier=(f"obligation:{obligation.obligation_id}:aggregate",),
                        ),
                    ),
                    None,
                    None,
                )
        except (TypeError, ValueError) as exc:
            return (
                EvaluationStatus.UNKNOWN,
                (
                    _diagnostic(
                        "AGGREGATE_VALUE_INVALID",
                        f"aggregate values are not reducible: {exc}",
                        obligation_id=obligation.obligation_id,
                        cause="aggregate-value-invalid",
                        repair_frontier=(f"obligation:{obligation.obligation_id}:aggregate",),
                    ),
                ),
                None,
                None,
            )
    matches = (actual == expected) if operator == "callable" or not isinstance(expected, tuple) else (
        actual >= expected[1] if expected[0] == ">=" else actual <= expected[1]
    )
    if matches:
        return EvaluationStatus.SATISFIED, (), actual, len(records)
    return (
        EvaluationStatus.UNSATISFIED,
        (
            _diagnostic(
                "AGGREGATE_MISMATCH",
                f"aggregate result {actual!r} does not satisfy {expected!r}",
                obligation_id=obligation.obligation_id,
                cause="aggregate-mismatch",
                repair_frontier=(f"obligation:{obligation.obligation_id}:aggregate",),
                details={"actual": actual, "expected": expected, "operator": operator},
            ),
        ),
        actual,
        len(records),
    )


def _evaluate_one(
    obligation: Obligation,
    *,
    spec_hash: str,
    binding_hash: str,
    records: Sequence[EvidenceRecord],
    capture_records: Sequence[EvidenceRecord],
    capture_complete: bool | None,
    capture_producer: str,
    expected_ids: Any,
    aggregate: Any,
    required_multiplicity: Any,
    base_diagnostics: Sequence[Diagnostic] = (),
) -> ObligationResult:
    relevant = _relevant(records, obligation)
    evidence_ids = tuple(record.evidence_id for record in relevant)
    diagnostics: list[Diagnostic] = list(base_diagnostics)
    expected_count: int | None = None
    observed_ids: tuple[str, ...] = ()
    declared_ids: tuple[str, ...] = ()
    aggregate_value = None
    if isinstance(required_multiplicity, Mapping):
        required_count_value = required_multiplicity.get(obligation.obligation_id, 1)
    elif required_multiplicity is None:
        required_count_value = 1
    else:
        required_count_value = required_multiplicity
    if isinstance(required_count_value, bool) or not isinstance(required_count_value, int) or required_count_value < 1:
        diagnostics.append(
            _diagnostic(
                "MULTIPLICITY_RULE_INVALID",
                "required multiplicity must be a positive integer",
                obligation_id=obligation.obligation_id,
                cause="multiplicity-rule-invalid",
                repair_frontier=(f"obligation:{obligation.obligation_id}:multiplicity",),
            )
        )
        required_count_value = 1

    if obligation.kind in {ProofMode.PRESENCE, ProofMode.AGGREGATE} and len(relevant) < required_count_value:
        diagnostics.append(
            _diagnostic(
                "MULTIPLICITY_UNSATISFIED",
                f"only {len(relevant)} distinct admitted evidence item(s) support a required multiplicity of {required_count_value}",
                obligation_id=obligation.obligation_id,
                evidence_ids=evidence_ids,
                cause="multiplicity-unsatisfied",
                repair_frontier=(f"obligation:{obligation.obligation_id}:multiplicity",),
                details={"required_count": required_count_value, "observed_count": len(relevant)},
            )
        )

    if obligation.kind is ProofMode.PRESENCE:
        if len(relevant) >= required_count_value:
            status = EvaluationStatus.SATISFIED
        else:
            status = EvaluationStatus.UNSATISFIED
            diagnostics.append(
                _diagnostic(
                    "MISSING_EVIDENCE",
                    f"presence obligation requires {required_count_value} admitted evidence item(s)",
                    obligation_id=obligation.obligation_id,
                    evidence_ids=evidence_ids,
                    cause="missing-evidence",
                    repair_frontier=(f"obligation:{obligation.obligation_id}:evidence",),
                    details={"required_count": required_count_value, "observed_count": len(relevant)},
                )
            )
    elif obligation.kind is ProofMode.COMPLETE_CAPTURE_ABSENCE:
        if capture_complete is not True:
            status = EvaluationStatus.UNKNOWN
            diagnostics.append(
                _diagnostic(
                    "INCOMPLETE_CAPTURE",
                    "absence cannot be proved from an incomplete evidence capture",
                    obligation_id=obligation.obligation_id,
                    cause="incomplete-capture",
                    repair_frontier=("capture:complete",),
                )
            )
        elif not capture_producer:
            status = EvaluationStatus.UNKNOWN
            diagnostics.append(
                _diagnostic(
                    "CAPTURE_PRODUCER_MISSING",
                    "absence requires a named complete-capture producer",
                    obligation_id=obligation.obligation_id,
                    cause="capture-producer-missing",
                    repair_frontier=("capture:producer",),
                )
            )
        elif relevant:
            status = EvaluationStatus.UNSATISFIED
            diagnostics.append(
                _diagnostic(
                    "UNEXPECTED_EVIDENCE",
                    "complete capture contains evidence matching an absence obligation",
                    obligation_id=obligation.obligation_id,
                    evidence_ids=evidence_ids,
                    cause="unexpected-evidence",
                    repair_frontier=(f"obligation:{obligation.obligation_id}:evidence",),
                )
            )
        else:
            status = EvaluationStatus.SATISFIED
    elif obligation.kind is ProofMode.SET_EQUALITY:
        if capture_complete is not True:
            status = EvaluationStatus.UNKNOWN
            diagnostics.append(
                _diagnostic(
                    "INCOMPLETE_CAPTURE",
                    "set equality cannot be proved from an incomplete evidence capture",
                    obligation_id=obligation.obligation_id,
                    cause="incomplete-capture",
                    repair_frontier=("capture:complete",),
                )
            )
        elif not capture_producer:
            status = EvaluationStatus.UNKNOWN
            diagnostics.append(
                _diagnostic(
                    "CAPTURE_PRODUCER_MISSING",
                    "set equality requires a named complete-capture producer",
                    obligation_id=obligation.obligation_id,
                    cause="capture-producer-missing",
                    repair_frontier=("capture:producer",),
                )
            )
        else:
            declared = _expected_for(obligation, expected_ids, capture_records)
            if declared is None:
                status = EvaluationStatus.UNKNOWN
                diagnostics.append(
                    _diagnostic(
                        "EXPECTED_SET_MISSING",
                        "set equality has no declared expected member set",
                        obligation_id=obligation.obligation_id,
                        cause="expected-set-missing",
                        repair_frontier=(f"obligation:{obligation.obligation_id}:expected-set",),
                    )
                )
            else:
                declared_ids = tuple(dict.fromkeys(declared))
                raw_observed = tuple(_member_id(record) for record in relevant)
                observed_ids = raw_observed
                expected_count = len(declared_ids)
                duplicates = tuple(dict.fromkeys(item for item in raw_observed if raw_observed.count(item) > 1))
                missing = tuple(item for item in declared_ids if item not in set(raw_observed))
                extra = tuple(item for item in raw_observed if item not in set(declared_ids))
                if duplicates:
                    status = EvaluationStatus.UNSATISFIED
                    diagnostics.append(
                        _diagnostic(
                            "DUPLICATE_EVIDENCE",
                            "set equality cannot use repeated member evidence as multiplicity",
                            obligation_id=obligation.obligation_id,
                            evidence_ids=evidence_ids,
                            cause="duplicate-evidence",
                            repair_frontier=(f"obligation:{obligation.obligation_id}:members",),
                            details={"duplicate_ids": list(duplicates)},
                        )
                    )
                elif missing or extra or len(raw_observed) != len(declared_ids):
                    status = EvaluationStatus.UNSATISFIED
                    diagnostics.append(
                        _diagnostic(
                            "SET_MISMATCH",
                            "observed evidence membership does not equal the declared set",
                            obligation_id=obligation.obligation_id,
                            evidence_ids=evidence_ids,
                            cause="set-mismatch",
                            repair_frontier=(f"obligation:{obligation.obligation_id}:members",),
                            details={"missing": list(missing), "extra": list(extra)},
                        )
                    )
                else:
                    status = EvaluationStatus.SATISFIED
    else:
        status, aggregate_diagnostics, aggregate_value, expected_count = _evaluate_aggregate(
            obligation,
            relevant,
            _aggregate_rule(aggregate, obligation),
        )
        diagnostics.extend(aggregate_diagnostics)

    return ObligationResult(
        obligation_id=obligation.obligation_id,
        status=status,
        kind=obligation.kind,
        spec_hash=spec_hash,
        binding_hash=binding_hash,
        required=obligation.required,
        evidence_ids=evidence_ids,
        diagnostics=diagnostics,
        observed_count=len(relevant),
        expected_count=expected_count,
        observed_ids=observed_ids,
        expected_ids=declared_ids,
        aggregate_value=aggregate_value,
    )


def evaluate_obligation(
    obligation: Obligation,
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]],
    *,
    spec_hash: str = "",
    binding_hash: str = "",
    complete_capture: bool | None = None,
    capture_producer: str | None = None,
    expected_ids: Any = None,
    aggregate: Any = None,
    required_multiplicity: Any = None,
) -> ObligationResult:
    """Evaluate one obligation over already prepared evidence.

    This lower-level helper does not invent a binding or scope.  The full
    :func:`evaluate_completion` path should be used when admission matters.
    """

    records = tuple(_coerce_evidence(item) for item in evidence)
    unique = _deduplicate(records)
    capture_records = tuple(item for item in unique if item.is_capture_marker)
    state, producer, capture_diagnostics = _capture_state(
        unique,
        complete_capture=complete_capture,
        capture_producer=capture_producer,
    )
    return _evaluate_one(
        obligation,
        spec_hash=spec_hash,
        binding_hash=binding_hash,
        records=unique,
        capture_records=capture_records,
        capture_complete=state,
        capture_producer=producer,
        expected_ids=expected_ids,
        aggregate=aggregate,
        required_multiplicity=required_multiplicity,
        base_diagnostics=capture_diagnostics,
    )


def evaluate_completion(
    spec: CompletionSpec | Mapping[str, Any],
    binding: CompletionBinding | Mapping[str, Any],
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]] = (),
    *,
    candidate_outcome: Any = "success",
    outcome: Any = None,
    complete_capture: bool | None = None,
    capture_producer: str | None = None,
    expected_ids: Any = None,
    expected_sets: Any = None,
    aggregate: Any = None,
    aggregate_rules: Any = None,
    required_multiplicity: Any = None,
    multiplicity: Any = None,
    verifier: str = "completion-shadow",
    verifier_version: str = EVIDENCE_SCHEMA_VERSION,
    declared_candidates: Any = None,
    candidates: Any = None,
    selected_candidate: str | None = None,
    applicability: Any = None,
    blocked_proof: BlockedProof | Mapping[str, Any] | None = None,
    waiver_proof: WaiverProof | Mapping[str, Any] | None = None,
    terminal_policy: TerminalPolicy | Mapping[str, Any] | None = None,
    verifier_provenance: VerifierIndependence | Mapping[str, Any] | None = None,
    require_verifier_independence: bool = False,
    independence: VerifierIndependence | Mapping[str, Any] | None = None,
    inherited_taint: Iterable[str] = (),
    waiver_taint: Iterable[str] = (),
    exceptional_proof: BlockedProof | WaiverProof | Mapping[str, Any] | None = None,
) -> CompletionVerdict:
    """Evaluate all obligations for one exact, immutable binding.

    Scope and binding failures are represented as unknown/failed diagnostics;
    no inadmissible evidence is passed to a proof-mode evaluator.  The
    function is intentionally pure and returns a shadow verdict only.
    """

    actual_spec = _coerce_spec(spec)
    actual_binding = _coerce_binding(binding)
    all_raw_evidence = tuple(evidence)
    raw_expected = expected_sets if expected_sets is not None else expected_ids
    raw_aggregate = aggregate_rules if aggregate_rules is not None else aggregate
    raw_multiplicity = multiplicity if multiplicity is not None else required_multiplicity
    selected_outcome = outcome if outcome is not None else candidate_outcome
    actual_taint = propagate_waiver_taint(inherited_taint, waiver_taint)
    if exceptional_proof is not None:
        if isinstance(exceptional_proof, WaiverProof):
            waiver_proof = exceptional_proof
        elif isinstance(exceptional_proof, BlockedProof):
            blocked_proof = exceptional_proof
        elif isinstance(exceptional_proof, Mapping):
            if "authority_provenance" in exceptional_proof or str(exceptional_proof.get("outcome", "")).lower() == "waived":
                waiver_proof = exceptional_proof
            else:
                blocked_proof = exceptional_proof

    selection: CandidateSelection | None = None
    selection_diagnostic: Diagnostic | None = None
    try:
        selection = select_candidate(
            selected_outcome,
            declared_candidates=declared_candidates,
            candidates=candidates,
            selected_candidate=selected_candidate,
        )
        selected_outcome = selection.selected_candidate
    except (TypeError, ValueError) as exc:
        selection_diagnostic = _diagnostic(
            "CANDIDATE_SELECTION_INVALID",
            str(exc),
            cause="candidate-selection-invalid",
            repair_frontier=("candidate:selection",),
        )

    identity_diagnostics: list[Diagnostic] = []
    if selection_diagnostic is not None:
        identity_diagnostics.append(selection_diagnostic)
    if actual_binding.spec_hash != actual_spec.spec_hash:
        identity_diagnostics.append(
            _diagnostic(
                "REUSE_IDENTITY_MISMATCH",
                "binding spec_hash does not match the completion spec",
                cause="spec-binding-mismatch",
                repair_frontier=(f"spec:{actual_spec.spec_hash}",),
                details={"spec_hash": actual_spec.spec_hash, "binding_spec_hash": actual_binding.spec_hash},
            )
        )
    if not actual_binding.is_canonical:
        identity_diagnostics.append(
            _diagnostic(
                "LEGACY_BINDING_UNKNOWN",
                "C1 legacy coordinates cannot establish a C2 evidence scope",
                cause="legacy-binding-unknown",
                repair_frontier=("binding:migrate",),
            )
        )

    admitted, admission_diagnostics = _admit_records(actual_binding, all_raw_evidence)
    all_diagnostics = list(identity_diagnostics) + list(admission_diagnostics)
    raw_obligations = actual_spec.obligations or (
        Obligation(actual_spec.obligation_id, ProofMode.PRESENCE, "primary completion evidence"),
    )
    applicable_obligations: tuple[Obligation, ...] = raw_obligations
    if selection is not None:
        applicable_obligations, applicability_diagnostic = _applicable_obligations(
            selection,
            applicability,
            raw_obligations,
        )
        if applicability_diagnostic is not None:
            all_diagnostics.append(applicability_diagnostic)
    if identity_diagnostics or selection_diagnostic is not None or not actual_binding.is_canonical:
        results = tuple(
            ObligationResult(
                obligation_id=obligation.obligation_id,
                status=EvaluationStatus.UNKNOWN,
                kind=obligation.kind,
                spec_hash=actual_spec.spec_hash,
                binding_hash=actual_binding.binding_hash,
                required=obligation.required,
                diagnostics=identity_diagnostics,
            )
            for obligation in raw_obligations
        )
        return CompletionVerdict(
            spec_hash=actual_spec.spec_hash,
            binding_hash=actual_binding.binding_hash,
            outcome=selected_outcome,
            obligation_results=results,
            evidence=admitted,
            diagnostics=all_diagnostics,
            candidate_selection=selection,
            taint=actual_taint,
            accepted=False,
            status=EvaluationStatus.UNKNOWN,
            verifier=verifier,
            verifier_version=verifier_version,
        )

    if any(item.code.startswith("CIRCULAR_APPLICABILITY") or item.code.startswith("APPLICABILITY_") for item in all_diagnostics):
        results = tuple(
            ObligationResult(
                obligation_id=obligation.obligation_id,
                status=EvaluationStatus.UNKNOWN,
                kind=obligation.kind,
                spec_hash=actual_spec.spec_hash,
                binding_hash=actual_binding.binding_hash,
                required=obligation.required,
                diagnostics=tuple(item for item in all_diagnostics if item.obligation_id in {"", obligation.obligation_id}),
            )
            for obligation in raw_obligations
        )
        return CompletionVerdict(
            spec_hash=actual_spec.spec_hash,
            binding_hash=actual_binding.binding_hash,
            outcome=selected_outcome,
            obligation_results=results,
            evidence=admitted,
            diagnostics=all_diagnostics,
            candidate_selection=selection,
            taint=actual_taint,
            accepted=False,
            status=EvaluationStatus.UNKNOWN,
            verifier=verifier,
            verifier_version=verifier_version,
        )

    actual_independence: VerifierIndependence | None = None
    if independence is not None:
        verifier_provenance = independence
    if require_verifier_independence or verifier_provenance is not None:
        actual_independence = verify_verifier_independence(
            verifier_provenance,
            admitted,
            verifier=verifier,
        )
        if not actual_independence.independent:
            all_diagnostics.append(
                _diagnostic(
                    "VERIFIER_NOT_INDEPENDENT",
                    "shadow verifier does not have independent implementation, producer, trust, and evidence provenance",
                    cause="verifier-not-independent",
                    repair_frontier=("verifier:independence",),
                    details={"reasons": list(actual_independence.reasons)},
                )
            )

    normalized_outcome = str(selected_outcome).strip().lower().replace("-", "_")
    proof: BlockedProof | WaiverProof | None = None
    proof_diagnostic: Diagnostic | None = None
    actual_policy: TerminalPolicy | None = None
    if normalized_outcome == "blocked":
        try:
            proof = blocked_proof if isinstance(blocked_proof, BlockedProof) else (
                BlockedProof.from_dict(blocked_proof) if blocked_proof is not None else None
            )
        except (TypeError, ValueError, KeyError) as exc:
            proof_diagnostic = _diagnostic("BLOCKED_PROOF_INVALID", str(exc), cause="blocked-proof-invalid", repair_frontier=("proof:blocked",))
        if proof is None and proof_diagnostic is None:
            proof_diagnostic = _diagnostic("BLOCKED_PROOF_MISSING", "blocked candidate requires a typed blocked proof", cause="blocked-proof-missing", repair_frontier=("proof:blocked",))
    elif normalized_outcome == "waived":
        try:
            proof = waiver_proof if isinstance(waiver_proof, WaiverProof) else (
                WaiverProof.from_dict(waiver_proof) if waiver_proof is not None else None
            )
        except (TypeError, ValueError, KeyError) as exc:
            proof_diagnostic = _diagnostic("WAIVER_PROOF_INVALID", str(exc), cause="waiver-proof-invalid", repair_frontier=("proof:waiver",))
        if proof is None and proof_diagnostic is None:
            proof_diagnostic = _diagnostic("WAIVER_PROOF_MISSING", "waived candidate requires a typed waiver proof", cause="waiver-proof-missing", repair_frontier=("proof:waiver",))
    elif normalized_outcome in {"suspended", "quarantined"}:
        try:
            policy = terminal_policy if isinstance(terminal_policy, TerminalPolicy) else (
                TerminalPolicy.from_dict(terminal_policy) if terminal_policy is not None else None
            )
            actual_policy = policy
        except (TypeError, ValueError, KeyError) as exc:
            policy = None
            proof_diagnostic = _diagnostic("TERMINAL_POLICY_INVALID", str(exc), cause="terminal-policy-invalid", repair_frontier=("policy:terminal",))
        if proof_diagnostic is None and (policy is None or not policy.permits(normalized_outcome)):
            proof_diagnostic = _diagnostic(
                "NONTERMINAL_OUTCOME",
                f"{normalized_outcome} is nonterminal without an independently admitted terminal policy",
                cause="terminal-policy-missing",
                repair_frontier=("policy:terminal",),
            )
        terminal = proof_diagnostic is None
    elif normalized_outcome not in {"success", "completed", "complete"}:
        if proof is None:
            proof_diagnostic = _diagnostic(
                "EXCEPTIONAL_PROOF_MISSING",
                "non-success candidate requires nontrivial typed proof",
                cause="exceptional-proof-missing",
                repair_frontier=(f"candidate:{selected_outcome}:proof",),
            )
    if proof is not None:
        proof_ids = set(proof.evidence_ids)
        admitted_ids = {item.evidence_id for item in admitted}
        proof_binding = getattr(proof, "binding_hash", "")
        if proof_binding and proof_binding != actual_binding.binding_hash:
            proof_diagnostic = _diagnostic(
                "PROOF_BINDING_MISMATCH",
                "exceptional proof is bound to a different completion binding",
                cause="proof-binding-mismatch",
                repair_frontier=(f"binding:{actual_binding.binding_hash}",),
            )
        elif not proof_ids or not proof_ids.issubset(admitted_ids):
            proof_diagnostic = _diagnostic(
                "PROOF_EVIDENCE_NOT_ADMITTED",
                "exceptional proof must cite admitted evidence in the exact scope",
                cause="proof-evidence-not-admitted",
                repair_frontier=(f"scope:{actual_binding.evidence_scope.scope_hash}",),
                details={"missing_evidence_ids": sorted(proof_ids - admitted_ids)},
            )
    if actual_policy is not None and not set(actual_policy.evidence_ids).issubset({item.evidence_id for item in admitted}):
        proof_diagnostic = _diagnostic(
            "TERMINAL_POLICY_EVIDENCE_NOT_ADMITTED",
            "terminal policy must cite admitted evidence in the exact scope",
            cause="terminal-policy-evidence-not-admitted",
            repair_frontier=(f"scope:{actual_binding.evidence_scope.scope_hash}",),
            details={"missing_evidence_ids": sorted(set(actual_policy.evidence_ids) - {item.evidence_id for item in admitted})},
        )
    if proof_diagnostic is not None:
        all_diagnostics.append(proof_diagnostic)
    if actual_independence is not None and not actual_independence.independent:
        # Independence is required for a shadow verdict whenever requested;
        # retain the typed proof in the verdict even when it failed.
        exceptional_failure = True
    else:
        exceptional_failure = False

    if normalized_outcome != "success" and normalized_outcome not in {"completed", "complete"}:
        status_by_outcome = {
            "blocked": EvaluationStatus.BLOCKED,
            "waived": EvaluationStatus.WAIVED,
            "suspended": EvaluationStatus.SUSPENDED,
            "quarantined": EvaluationStatus.QUARANTINED,
        }
        exceptional_status = status_by_outcome.get(normalized_outcome, EvaluationStatus.FAILED)
        valid_exception = proof_diagnostic is None and not exceptional_failure
        return CompletionVerdict(
            spec_hash=actual_spec.spec_hash,
            binding_hash=actual_binding.binding_hash,
            outcome=selected_outcome,
            obligation_results=tuple(
                ObligationResult(
                    obligation_id=item.obligation_id,
                    status=exceptional_status if valid_exception else EvaluationStatus.UNKNOWN,
                    kind=item.kind,
                    spec_hash=actual_spec.spec_hash,
                    binding_hash=actual_binding.binding_hash,
                    required=item.required,
                    diagnostics=(proof_diagnostic,) if proof_diagnostic else (),
                )
                for item in applicable_obligations
            ),
            evidence=admitted,
            diagnostics=all_diagnostics,
            candidate_selection=selection,
            exceptional_proof=proof,
            terminal_policy=actual_policy,
            terminal=terminal if normalized_outcome in {"suspended", "quarantined"} else valid_exception,
            taint=actual_taint | (proof.taint if isinstance(proof, WaiverProof) else frozenset()),
            verifier_independence=actual_independence,
            accepted=normalized_outcome == "waived" and valid_exception,
            status=exceptional_status if valid_exception else EvaluationStatus.UNKNOWN,
            verifier=verifier,
            verifier_version=verifier_version,
        )

    capture_state, producer, capture_diagnostics = _capture_state(
        admitted,
        complete_capture=complete_capture,
        capture_producer=capture_producer,
    )
    all_diagnostics.extend(capture_diagnostics)
    capture_records = tuple(record for record in admitted if record.is_capture_marker)
    results = tuple(
        _evaluate_one(
            obligation,
            spec_hash=actual_spec.spec_hash,
            binding_hash=actual_binding.binding_hash,
            records=admitted,
            capture_records=capture_records,
            capture_complete=capture_state,
            capture_producer=producer,
            expected_ids=raw_expected,
            aggregate=raw_aggregate,
            required_multiplicity=raw_multiplicity,
        )
        for obligation in applicable_obligations
    )
    for result in results:
        all_diagnostics.extend(result.diagnostics)
    # Keep one stable top-level occurrence for each causal diagnostic.  The
    # per-obligation records retain the exact diagnostic as well.
    unique_diagnostics: dict[str, Diagnostic] = {}
    for diagnostic in all_diagnostics:
        unique_diagnostics.setdefault(diagnostic.diagnostic_hash, diagnostic)
    return CompletionVerdict(
        spec_hash=actual_spec.spec_hash,
        binding_hash=actual_binding.binding_hash,
        outcome=selected_outcome,
        obligation_results=results,
        evidence=admitted,
        diagnostics=tuple(unique_diagnostics.values()),
        candidate_selection=selection,
        taint=actual_taint,
        verifier_independence=actual_independence,
        verifier=verifier,
        verifier_version=verifier_version,
    )


def evaluate(
    spec: CompletionSpec | Mapping[str, Any],
    binding: CompletionBinding | Mapping[str, Any],
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]] = (),
    **kwargs: Any,
) -> CompletionVerdict:
    """Short alias for :func:`evaluate_completion`."""

    return evaluate_completion(spec, binding, evidence, **kwargs)


evaluate_spec = evaluate_completion
evaluate_binding = evaluate_completion
evaluate_completion_binding = evaluate_completion


def hash_evidence(record: EvidenceRecord | Mapping[str, Any]) -> str:
    """Return the content identity of an evidence record."""

    return _coerce_evidence(record).content_hash


compute_evidence_hash = hash_evidence


class CompletionEvaluator:
    """Small object façade for callers that prefer an evaluator instance."""

    def __init__(self, *, verifier: str = "completion-shadow", verifier_version: str = EVIDENCE_SCHEMA_VERSION) -> None:
        self.verifier = verifier
        self.verifier_version = verifier_version

    def evaluate(self, spec: CompletionSpec | Mapping[str, Any], binding: CompletionBinding | Mapping[str, Any], evidence: Iterable[EvidenceRecord | Mapping[str, Any]] = (), **kwargs: Any) -> CompletionVerdict:
        kwargs.setdefault("verifier", self.verifier)
        kwargs.setdefault("verifier_version", self.verifier_version)
        return evaluate_completion(spec, binding, evidence, **kwargs)


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "OBLIGATION_RESULT_SCHEMA_VERSION",
    "DIAGNOSTIC_SCHEMA_VERSION",
    "VERDICT_SCHEMA_VERSION",
    "EvaluationStatus",
    "ObligationStatus",
    "VerdictStatus",
    "DiagnosticSeverity",
    "EvidenceRecord",
    "HashedEvidence",
    "Evidence",
    "EvidenceItem",
    "EvidenceRef",
    "Diagnostic",
    "EvaluationDiagnostic",
    "DiagnosticRecord",
    "ObligationResult",
    "ObligationEvaluation",
    "ObligationResultRecord",
    "CandidateSelection",
    "select_candidate",
    "BlockedProof",
    "BlockedOutcomeProof",
    "WaiverProof",
    "WaiverOutcomeProof",
    "TerminalPolicy",
    "TerminalDispositionPolicy",
    "VerifierIndependence",
    "VerifierIndependenceProof",
    "verify_verifier_independence",
    "propagate_waiver_taint",
    "combine_waiver_taint",
    "transitive_waiver_taint",
    "CompletionVerdict",
    "ShadowCompletionVerdict",
    "CompletionVerdictRecord",
    "deduplicate_evidence",
    "admit_evidence_for_binding",
    "evaluate_obligation",
    "evaluate_completion",
    "evaluate",
    "evaluate_spec",
    "evaluate_binding",
    "evaluate_completion_binding",
    "hash_evidence",
    "compute_evidence_hash",
    "CompletionEvaluator",
]
