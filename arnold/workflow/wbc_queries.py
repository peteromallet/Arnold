"""Exact-version result contracts for Workflow Boundary Contract queries.

The types in this module are immutable, non-authoritative views of durable
attempt-ledger evidence.  They deliberately have no dispatch, completion, or
grant API: a verified query result can be used as evidence by a caller, but it
is never a bearer token for an authority-increasing action.

This module defines the result boundary only.  The store-backed query facade
that proves where the evidence came from is layered on top of these contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, ClassVar, TypeAlias

from arnold.workflow.attempt_ledger_store import SourceCursor
from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
    AttemptEventType,
    LedgerEvent,
    PersistenceStatus,
)


WBC_QUERY_CONTRACT_VERSION = "arnold.workflow.wbc_query_result.v1"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TERMINAL_EVENT_TYPES = frozenset(
    {
        AttemptEventType.COMPLETED.value,
        AttemptEventType.FAILED.value,
        AttemptEventType.CANCELLED.value,
    }
)


class WbcQueryStatus(StrEnum):
    """Closed result states for exact-version WBC reads."""

    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    INDETERMINATE = "indeterminate"
    INCOHERENT = "incoherent"


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_digest(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise ValueError(
            f"{field_name} must be 'sha256:' followed by 64 lowercase hex characters"
        )


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class WbcQueryDiagnostic:
    """A stable diagnostic attached to a non-verified result."""

    code: str
    message: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.code, "diagnostic.code")
        _require_nonempty(self.message, "diagnostic.message")
        _validate_evidence_ids(self.evidence_ids, "diagnostic.evidence_ids")


@dataclass(frozen=True)
class WbcEventRef:
    """Digest-bound reference to one stored attempt-ledger event."""

    attempt_id: str
    event_id: str
    sequence: int
    event_type: str
    content_digest: str
    stored_schema_version: str

    def __post_init__(self) -> None:
        _require_nonempty(self.attempt_id, "event_ref.attempt_id")
        _require_nonempty(self.event_id, "event_ref.event_id")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise TypeError("event_ref.sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("event_ref.sequence must be positive")
        _require_nonempty(self.event_type, "event_ref.event_type")
        _require_digest(self.content_digest, "event_ref.content_digest")
        _require_nonempty(
            self.stored_schema_version, "event_ref.stored_schema_version"
        )

    @classmethod
    def from_event(cls, event: LedgerEvent) -> WbcEventRef:
        """Create a reference from one exact, durable ledger event."""

        if not isinstance(event, LedgerEvent):
            raise TypeError(
                "event must be a LedgerEvent, not a raw receipt or projection"
            )
        if event.persistence_status is not PersistenceStatus.DURABLE:
            raise ValueError(
                "event must be durably persisted before it can be referenced"
            )
        return cls(
            attempt_id=event.identity.attempt_id,
            event_id=event.idempotency_key,
            sequence=event.sequence,
            event_type=event.event_type.value,
            content_digest=_canonical_digest(event.to_dict()),
            stored_schema_version=event.event_schema_version,
        )


@dataclass(frozen=True)
class WbcSourceCursor:
    """Exact observed cursor for the durable source read."""

    attempt_id: str
    cursor_key: str
    last_sequence: int
    last_position: str | None
    source_version: str

    def __post_init__(self) -> None:
        _require_nonempty(self.attempt_id, "source_cursor.attempt_id")
        _require_nonempty(self.cursor_key, "source_cursor.cursor_key")
        if not isinstance(self.last_sequence, int) or isinstance(
            self.last_sequence, bool
        ):
            raise TypeError("source_cursor.last_sequence must be an integer")
        if self.last_sequence < 0:
            raise ValueError("source_cursor.last_sequence must be non-negative")
        if self.last_position is not None and not isinstance(
            self.last_position, str
        ):
            raise TypeError("source_cursor.last_position must be a string or None")
        _require_nonempty(self.source_version, "source_cursor.source_version")

    @classmethod
    def from_store_cursor(
        cls,
        cursor: SourceCursor,
        *,
        source_version: str,
    ) -> WbcSourceCursor:
        if not isinstance(cursor, SourceCursor):
            raise TypeError("cursor must be a SourceCursor, not raw mutable data")
        return cls(
            attempt_id=cursor.attempt_id,
            cursor_key=cursor.cursor_key,
            last_sequence=cursor.last_sequence,
            last_position=cursor.last_position,
            source_version=source_version,
        )


def _validate_evidence_ids(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be an immutable tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field_name} entries must be non-empty strings")
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{field_name} must be sorted and duplicate-free")


def _verified_digest_payload(
    *,
    attempt_id: str,
    contract_version: str,
    start_event_ref: WbcEventRef,
    terminal_event_ref: WbcEventRef,
    source_cursor: WbcSourceCursor,
    evidence_ids: tuple[str, ...],
    stored_schema_version: str,
) -> dict[str, Any]:
    return {
        "attempt_id": attempt_id,
        "contract_version": contract_version,
        "start_event_ref": asdict(start_event_ref),
        "terminal_event_ref": asdict(terminal_event_ref),
        "source_cursor": asdict(source_cursor),
        "evidence_ids": evidence_ids,
        "stored_schema_version": stored_schema_version,
    }


@dataclass(frozen=True)
class _WbcQueryResultBase:
    """Fields common to every WBC query result state."""

    attempt_id: str
    contract_version: str = WBC_QUERY_CONTRACT_VERSION
    start_event_ref: WbcEventRef | None = None
    terminal_event_ref: WbcEventRef | None = None
    source_cursor: WbcSourceCursor | None = None
    evidence_ids: tuple[str, ...] = ()
    digest: str | None = None
    stored_schema_version: str | None = None
    diagnostics: tuple[WbcQueryDiagnostic, ...] = ()

    status: ClassVar[WbcQueryStatus]

    def __post_init__(self) -> None:
        _require_nonempty(self.attempt_id, "attempt_id")
        if self.contract_version != WBC_QUERY_CONTRACT_VERSION:
            raise ValueError(
                "contract_version must name the exact supported WBC query contract"
            )
        for field_name, ref in (
            ("start_event_ref", self.start_event_ref),
            ("terminal_event_ref", self.terminal_event_ref),
        ):
            if ref is not None and not isinstance(ref, WbcEventRef):
                raise TypeError(f"{field_name} must be a WbcEventRef or None")
            if ref is not None and ref.attempt_id != self.attempt_id:
                raise ValueError(f"{field_name} belongs to a different attempt")
        if self.source_cursor is not None and not isinstance(
            self.source_cursor, WbcSourceCursor
        ):
            raise TypeError("source_cursor must be a WbcSourceCursor or None")
        if (
            self.source_cursor is not None
            and self.source_cursor.attempt_id != self.attempt_id
        ):
            raise ValueError("source_cursor belongs to a different attempt")
        _validate_evidence_ids(self.evidence_ids, "evidence_ids")
        if self.digest is not None:
            _require_digest(self.digest, "digest")
        if self.stored_schema_version is not None:
            _require_nonempty(self.stored_schema_version, "stored_schema_version")
        if not isinstance(self.diagnostics, tuple):
            raise TypeError("diagnostics must be an immutable tuple")
        if any(
            not isinstance(diagnostic, WbcQueryDiagnostic)
            for diagnostic in self.diagnostics
        ):
            raise TypeError("diagnostics entries must be WbcQueryDiagnostic values")

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, JSON-compatible view of the result."""

        value = asdict(self)
        value["status"] = self.status.value
        return value


@dataclass(frozen=True)
class WbcVerifiedResult(_WbcQueryResultBase):
    """A complete, exact-version result over durable source evidence."""

    status: ClassVar[WbcQueryStatus] = WbcQueryStatus.VERIFIED

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.start_event_ref is None or self.terminal_event_ref is None:
            raise ValueError("verified results require start and terminal event refs")
        if self.source_cursor is None:
            raise ValueError("verified results require an exact source cursor")
        if not self.evidence_ids:
            raise ValueError("verified results require exact evidence IDs")
        if self.digest is None:
            raise ValueError("verified results require a canonical digest")
        if self.stored_schema_version != LEDGER_SCHEMA_VERSION:
            raise ValueError(
                "verified results require the exact supported stored schema version"
            )
        if self.diagnostics:
            raise ValueError("verified results cannot suppress diagnostics")
        if self.start_event_ref.event_type != AttemptEventType.STARTED.value:
            raise ValueError("start_event_ref must reference a started event")
        if self.terminal_event_ref.event_type not in _TERMINAL_EVENT_TYPES:
            raise ValueError("terminal_event_ref must reference a terminal event")
        if self.start_event_ref.sequence >= self.terminal_event_ref.sequence:
            raise ValueError("terminal event must follow the started event")
        for ref in (self.start_event_ref, self.terminal_event_ref):
            if ref.stored_schema_version != self.stored_schema_version:
                raise ValueError("event ref stored schema versions must agree")
        if self.source_cursor.source_version != self.stored_schema_version:
            raise ValueError("source cursor version must match stored schema version")
        if self.source_cursor.last_sequence != self.terminal_event_ref.sequence:
            raise ValueError("source cursor must bind the exact terminal sequence")
        expected_digest = _canonical_digest(
            _verified_digest_payload(
                attempt_id=self.attempt_id,
                contract_version=self.contract_version,
                start_event_ref=self.start_event_ref,
                terminal_event_ref=self.terminal_event_ref,
                source_cursor=self.source_cursor,
                evidence_ids=self.evidence_ids,
                stored_schema_version=self.stored_schema_version,
            )
        )
        if self.digest != expected_digest:
            raise ValueError("digest does not match the exact verified evidence")

    @classmethod
    def from_events(
        cls,
        *,
        started_event: LedgerEvent,
        terminal_event: LedgerEvent,
        source_cursor: SourceCursor,
        evidence_ids: tuple[str, ...],
    ) -> WbcVerifiedResult:
        """Build a verified result from typed durable evidence only."""

        if not isinstance(evidence_ids, tuple):
            raise TypeError("evidence_ids must be an immutable tuple")
        start_ref = WbcEventRef.from_event(started_event)
        terminal_ref = WbcEventRef.from_event(terminal_event)
        cursor_ref = WbcSourceCursor.from_store_cursor(
            source_cursor,
            source_version=start_ref.stored_schema_version,
        )
        canonical_evidence_ids = tuple(sorted(set(evidence_ids)))
        payload = _verified_digest_payload(
            attempt_id=start_ref.attempt_id,
            contract_version=WBC_QUERY_CONTRACT_VERSION,
            start_event_ref=start_ref,
            terminal_event_ref=terminal_ref,
            source_cursor=cursor_ref,
            evidence_ids=canonical_evidence_ids,
            stored_schema_version=start_ref.stored_schema_version,
        )
        return cls(
            attempt_id=start_ref.attempt_id,
            start_event_ref=start_ref,
            terminal_event_ref=terminal_ref,
            source_cursor=cursor_ref,
            evidence_ids=canonical_evidence_ids,
            digest=_canonical_digest(payload),
            stored_schema_version=start_ref.stored_schema_version,
        )


@dataclass(frozen=True)
class WbcIncompleteResult(_WbcQueryResultBase):
    """The durable source is coherent but required evidence is absent."""

    status: ClassVar[WbcQueryStatus] = WbcQueryStatus.INCOMPLETE

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_non_verified(self)
        if self.terminal_event_ref is not None:
            raise ValueError("incomplete results cannot claim a terminal event")


@dataclass(frozen=True)
class WbcIndeterminateResult(_WbcQueryResultBase):
    """The source cannot be read or version-bound strongly enough to decide."""

    status: ClassVar[WbcQueryStatus] = WbcQueryStatus.INDETERMINATE

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_non_verified(self)


@dataclass(frozen=True)
class WbcIncoherentResult(_WbcQueryResultBase):
    """Durable evidence exists but contradicts the WBC contract."""

    status: ClassVar[WbcQueryStatus] = WbcQueryStatus.INCOHERENT

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_non_verified(self)


def _validate_non_verified(result: _WbcQueryResultBase) -> None:
    if not result.diagnostics:
        raise ValueError(f"{result.status.value} results require diagnostics")
    if result.digest is not None:
        raise ValueError(
            f"{result.status.value} results cannot carry a verified digest"
        )


WbcQueryResult: TypeAlias = (
    WbcVerifiedResult
    | WbcIncompleteResult
    | WbcIndeterminateResult
    | WbcIncoherentResult
)


__all__ = [
    "WBC_QUERY_CONTRACT_VERSION",
    "WbcEventRef",
    "WbcIncompleteResult",
    "WbcIncoherentResult",
    "WbcIndeterminateResult",
    "WbcQueryDiagnostic",
    "WbcQueryResult",
    "WbcQueryStatus",
    "WbcSourceCursor",
    "WbcVerifiedResult",
]
