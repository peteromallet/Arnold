"""Read-only Run Authority and WBC source adapters (M2).

These adapters bridge the two canonical authority stores consumed by the
coherent maintenance join (T9):

* :class:`RunAuthorityAdapter` reads the reduced
  :class:`~arnold_pipelines.run_authority.reducer.RunAuthorityView` and
  evaluates the current source via ``evaluate_current_source``;
* :class:`WbcAdapter` reads the exact ``AttemptLedgerStore`` read/query/
  version APIs (``read_events``, ``read_ledger``, terminal/gap/diagnostic
  queries, ``query_source_cursor``, ``get_contract_version``, and
  ``get_store_version``).

Both adapters are strictly read-only and immutable-result:

* they call ONLY the named read/query/version APIs — never an append,
  reservation, cursor-update, lease, or store-creation method;
* they emit only immutable references / digests / cursors
  (:class:`~arnold_pipelines.megaplan.maintenance.identity.OwnerRef` and
  the typed ref models below) — owner payloads are never embedded;
* they create no store, migration, outbox, or payload policy;
* they capture source versions before and after every read as a
  :class:`~arnold_pipelines.megaplan.maintenance.contracts.SourceVersionVector`
  so the join can detect version tears exactly.

The WBC adapter resolves the M6A handoff through the strict registry (T5):
until human approval, incarnation/restore/high-water coordinates stay
explicit ``None`` (typed UNKNOWN) and the resolution reason is preserved.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import fields, is_dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from arnold_pipelines.megaplan.maintenance.contracts import SourceVersionVector
from arnold_pipelines.megaplan.maintenance.handoffs import (
    HandoffRegistry,
    HandoffResolution,
    HandoffResolutionReason,
    HandoffResolutionState,
    default_handoff_registry,
)
from arnold_pipelines.megaplan.maintenance.identity import (
    MAINTENANCE_SCHEMA_VERSION,
    EnvironmentId,
    OwnerRef,
    canonical_digest,
    canonical_json,
)

_SHA256_HEX = frozenset("0123456789abcdef")


def _require_sha256(value: str, *, what: str) -> str:
    if len(value) != 64 or any(char not in _SHA256_HEX for char in value):
        raise ValueError(f"{what} must be a 64-character lowercase sha256 hex digest")
    return value


def _to_plain(value: Any) -> Any:
    """Recursively convert owner dataclasses/enums to canonical JSON values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_plain(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_plain(item) for key, item in sorted(value.items())}
    if hasattr(value, "value") and not isinstance(value, str):
        return _to_plain(value.value)
    return value


def _record_digest(record: Any) -> str:
    """Deterministic sha256 digest of an owner record without embedding it."""
    if hasattr(record, "digest") and callable(getattr(record, "digest")):
        return _require_sha256(record.digest(), what="owner record digest")
    if hasattr(record, "to_dict") and callable(getattr(record, "to_dict")):
        material = canonical_json(_to_plain(record.to_dict()))
    else:
        material = canonical_json(_to_plain(record))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _sort_refs(refs: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
    """Deterministic (owner, locator, digest, cursor) reference order."""
    return tuple(
        sorted(
            refs,
            key=lambda ref: (ref.owner, ref.locator, ref.digest or "", ref.cursor or ""),
        )
    )


# ---------------------------------------------------------------------------
# Run Authority adapter
# ---------------------------------------------------------------------------


class CurrentSourceRead(BaseModel):
    """Immutable read-only outcome of ``evaluate_current_source``.

    Carries only the status, reason, canonical request/detail digests, and
    locator references to the matched grant/fence/attempt/decision records —
    never the records themselves.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    satisfied: bool
    reason: StrictStr
    request_digest: StrictStr
    detail_digest: StrictStr | None = None
    references: tuple[OwnerRef, ...] = ()

    @field_validator("request_digest", "detail_digest")
    @classmethod
    def _validate_digests(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_sha256(value, what="current-source digest")


class RunAuthorityRead(BaseModel):
    """Immutable result of one read-only Run Authority capture.

    ``before_view_hash``/``after_view_hash`` are the source versions captured
    around the read; ``torn`` is ``True`` when they differ (a version tear the
    join must never mix).  ``version_vector`` carries the same coordinates in
    the shared envelope vocabulary.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    run_id: StrictStr
    run_revision: StrictStr
    environment: EnvironmentId | None = None
    journal_cursor: int
    before_view_hash: StrictStr
    after_view_hash: StrictStr
    view_hash: StrictStr
    evidence_set_digest: StrictStr
    version_vector: SourceVersionVector
    grants: tuple[OwnerRef, ...] = ()
    decisions: tuple[OwnerRef, ...] = ()
    fences: tuple[OwnerRef, ...] = ()
    attempts: tuple[OwnerRef, ...] = ()
    quarantines: tuple[OwnerRef, ...] = ()
    diagnostics: tuple[OwnerRef, ...] = ()
    current_source: CurrentSourceRead | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("before_view_hash", "after_view_hash", "view_hash")
    @classmethod
    def _validate_hashes(cls, value: str) -> str:
        return _require_sha256(value, what="run authority view hash")

    @field_validator("evidence_set_digest")
    @classmethod
    def _validate_evidence_digest(cls, value: str) -> str:
        return _require_sha256(value, what="evidence set digest")

    @field_validator(
        "grants", "decisions", "fences", "attempts", "quarantines", "diagnostics"
    )
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class RunAuthorityAdapter:
    """Read-only adapter over ``RunAuthorityView`` and ``evaluate_current_source``.

    The adapter holds only a read provider and an optional environment
    identity; it exposes no mutation method and never constructs an owner
    store.
    """

    def __init__(
        self,
        view_provider: Callable[[], Any],
        *,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._view_provider = view_provider
        self._environment = environment

    def read(
        self, request: Any | None = None
    ) -> RunAuthorityRead:
        """Capture one version-coherent Run Authority read.

        Reads the view before and after the evaluation, records both view
        hashes, and emits immutable references/digests/cursors.  When
        *request* (a ``CurrentSourceRequest``) is supplied, the current
        source is evaluated against the BEFORE snapshot and the matched
        records are referenced (never embedded).
        """
        before = self._view_provider()
        before_hash = before.view_hash
        current_source: CurrentSourceRead | None = None
        if request is not None:
            current_source = _evaluate_current_source_read(before, request)
        after = self._view_provider()
        after_hash = after.view_hash
        return RunAuthorityRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            run_id=after.run_id,
            run_revision=after.run_revision,
            environment=self._environment,
            journal_cursor=after.journal_cursor,
            before_view_hash=before_hash,
            after_view_hash=after_hash,
            view_hash=after_hash,
            evidence_set_digest=after.evidence_set_digest,
            version_vector=SourceVersionVector(
                owner="run_authority",
                source="run_authority.view",
                environment=self._environment,
                before=before_hash,
                after=after_hash,
            ),
            grants=_sort_refs(
                OwnerRef(
                    owner="run_authority",
                    record_type="grant",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"grant://{grant.grant_id}",
                    digest=_record_digest(grant),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for grant in after.grants
            ),
            decisions=_sort_refs(
                OwnerRef(
                    owner="run_authority",
                    record_type="decision",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"decision://{decision.decision_id}",
                    digest=_record_digest(decision),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for decision in after.decisions
            ),
            fences=_sort_refs(
                OwnerRef(
                    owner="run_authority",
                    record_type="fence",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"fence://{fence.coordinator_attempt_id}/{fence.token}",
                    digest=_record_digest(fence),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for fence in after.fences
            ),
            attempts=_sort_refs(
                OwnerRef(
                    owner="run_authority",
                    record_type="attempt",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"attempt://{attempt.attempt_id}",
                    digest=_record_digest(attempt),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for attempt in after.attempts
            ),
            quarantines=_sort_refs(
                OwnerRef(
                    owner="run_authority",
                    record_type="quarantine",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"quarantine://{quarantine.quarantine_id}",
                    digest=_record_digest(quarantine),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for quarantine in after.quarantines
            ),
            diagnostics=_sort_refs(
                OwnerRef(
                    owner="run_authority",
                    record_type="diagnostic",
                    identity=after.run_id,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"diagnostic://{diagnostic.record_type}/{diagnostic.record_id}",
                    digest=_record_digest(diagnostic),
                    cursor=f"journal:{after.journal_cursor}",
                )
                for diagnostic in after.diagnostics
            ),
            current_source=current_source,
            torn=(before_hash != after_hash),
        )


def _evaluate_current_source_read(view: Any, request: Any) -> CurrentSourceRead:
    """Evaluate *request* against *view* and emit a read-only result."""
    from arnold_pipelines.run_authority.current_source import evaluate_current_source

    result = evaluate_current_source(view, request)
    request_digest = hashlib.sha256(
        canonical_json(_to_plain(request)).encode("utf-8")
    ).hexdigest()
    detail = _to_plain(result.detail)
    references: list[OwnerRef] = []
    if result.status.is_satisfied:
        references = _matched_authority_refs(view, detail)
    return CurrentSourceRead(
        satisfied=result.status.is_satisfied,
        reason=result.reason,
        request_digest=request_digest,
        detail_digest=(
            hashlib.sha256(canonical_json(detail).encode("utf-8")).hexdigest()
            if detail
            else None
        ),
        references=_sort_refs(references),
    )


def _matched_authority_refs(view: Any, detail: dict[str, Any]) -> list[OwnerRef]:
    """Locator references to the records matched by a satisfied evaluation."""
    refs: list[OwnerRef] = []
    grant_id = detail.get("grant_id")
    fence_token = detail.get("fence_token")
    subject_attempt_id = detail.get("subject_attempt_id")
    decision_id = detail.get("decision_id")
    cursor = f"journal:{view.journal_cursor}"
    for grant in view.grants:
        if grant.grant_id == grant_id:
            refs.append(
                OwnerRef(
                    owner="run_authority",
                    record_type="grant",
                    identity=getattr(view, "run_id", None),
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"grant://{grant.grant_id}",
                    digest=_record_digest(grant),
                    cursor=cursor,
                )
            )
    for fence in view.fences:
        if fence.token == fence_token:
            refs.append(
                OwnerRef(
                    owner="run_authority",
                    record_type="fence",
                    identity=getattr(view, "run_id", None),
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"fence://{fence.coordinator_attempt_id}/{fence.token}",
                    digest=_record_digest(fence),
                    cursor=cursor,
                )
            )
    for attempt in view.attempts:
        if attempt.attempt_id == subject_attempt_id:
            refs.append(
                OwnerRef(
                    owner="run_authority",
                    record_type="attempt",
                    identity=getattr(view, "run_id", None),
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"attempt://{attempt.attempt_id}",
                    digest=_record_digest(attempt),
                    cursor=cursor,
                )
            )
    for decision in view.decisions:
        if decision.decision_id == decision_id:
            refs.append(
                OwnerRef(
                    owner="run_authority",
                    record_type="decision",
                    identity=getattr(view, "run_id", None),
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"decision://{decision.decision_id}",
                    digest=_record_digest(decision),
                    cursor=cursor,
                )
            )
    return refs


# ---------------------------------------------------------------------------
# WBC adapter
# ---------------------------------------------------------------------------


class WbcEventRef(BaseModel):
    """Immutable reference to one WBC ledger event (digest + locator only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: StrictStr
    sequence: int
    event_type: StrictStr
    idempotency_key: StrictStr
    digest: StrictStr
    locator: StrictStr

    @field_validator("sequence")
    @classmethod
    def _validate_sequence(cls, value: int) -> int:
        if value < 1:
            raise ValueError(f"WBC event sequence must be >= 1, got {value}")
        return value

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _require_sha256(value, what="WBC event digest")


class SourceCursorRef(BaseModel):
    """Immutable reference to a WBC source-cursor position."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt_id: StrictStr
    cursor_key: StrictStr
    last_sequence: int
    last_position: StrictStr | None = None
    digest: StrictStr

    @field_validator("last_sequence")
    @classmethod
    def _validate_sequence(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"source cursor last_sequence must be >= 0, got {value}")
        return value

    @field_validator("digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return _require_sha256(value, what="source cursor digest")


class WbcRead(BaseModel):
    """Immutable result of one read-only WBC attempt capture.

    Emits only event/ledger/gap/diagnostic/cursor references and digests,
    never owner payloads.  ``contract_version_before/after`` and
    ``store_version_before/after`` are captured around the read;
    ``version_vector`` carries the combined coordinates.  ``handoff`` is the
    M6A resolution from the strict registry; until approved, incarnation/
    restore/high-water stay explicit ``None`` (typed UNKNOWN).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    attempt_id: StrictStr
    environment: EnvironmentId | None = None
    contract_version_before: StrictStr
    contract_version_after: StrictStr
    store_version_before: StrictStr
    store_version_after: StrictStr
    version_vector: SourceVersionVector
    handoff: HandoffResolution | None = None
    incarnation: StrictStr | None = None
    restore_generation: StrictStr | None = None
    high_water: StrictStr | None = None
    event_refs: tuple[WbcEventRef, ...] = ()
    ledger_ref: OwnerRef | None = None
    terminal_ref: WbcEventRef | None = None
    gap_refs: tuple[OwnerRef, ...] = ()
    persistence_diagnostics: tuple[OwnerRef, ...] = ()
    reconciliation: tuple[OwnerRef, ...] = ()
    source_cursor: SourceCursorRef | None = None
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("gap_refs", "persistence_diagnostics", "reconciliation")
    @classmethod
    def _sort_ref_lists(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class WbcAdapter:
    """Read-only adapter over the exact ``AttemptLedgerStore`` read/query APIs.

    The adapter calls ONLY read/query/version methods
    (``read_events``, ``read_ledger``, ``get_terminal_event``,
    ``query_gaps``, ``query_persistence_diagnostics``,
    ``query_reconciliation_state``, ``query_source_cursor``,
    ``get_contract_version``, ``get_store_version``).  It never appends,
    reserves, updates cursors, or creates a store.
    """

    def __init__(
        self,
        store: Any,
        *,
        registry: HandoffRegistry | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._store = store
        self._registry = registry if registry is not None else default_handoff_registry()
        self._environment = environment

    def read_attempt(
        self, attempt_id: str, *, cursor_key: str = "default"
    ) -> WbcRead:
        """Capture one read-only WBC attempt snapshot with before/after versions."""
        before_contract = self._store.get_contract_version()
        before_store = self._store.get_store_version()

        events = tuple(self._store.read_events(attempt_id))
        ledger = self._store.read_ledger(attempt_id)
        terminal = self._store.get_terminal_event(attempt_id)
        gaps = tuple(self._store.query_gaps(attempt_id))
        persistence = tuple(self._store.query_persistence_diagnostics(attempt_id))
        reconciliation = tuple(self._store.query_reconciliation_state(attempt_id))
        cursor = self._store.query_source_cursor(attempt_id, cursor_key)

        after_contract = self._store.get_contract_version()
        after_store = self._store.get_store_version()

        m6a = self._registry.resolve("M6A")
        incarnation: str | None = None
        restore_generation: str | None = None
        high_water: str | None = None
        if m6a.state is HandoffResolutionState.ACCEPTED and m6a.row is not None:
            coordinates = m6a.row.wbc_coordinates
            if coordinates is not None:
                incarnation = coordinates.incarnation
                restore_generation = coordinates.restore_generation
                high_water = coordinates.high_water

        event_refs = tuple(
            WbcEventRef(
                attempt_id=attempt_id,
                sequence=event.sequence,
                event_type=event.event_type.value,
                idempotency_key=event.idempotency_key,
                digest=_wbc_event_digest(event),
                locator=f"wbc://{attempt_id}/{event.sequence}",
            )
            for event in events
        )
        ledger_ref = (
            OwnerRef(
                owner="wbc",
                record_type="ledger",
                identity=attempt_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"ledger://{attempt_id}",
                digest=_record_digest(ledger),
                cursor=f"sequence:{ledger.last_event.sequence if ledger.last_event else 0}",
            )
            if ledger is not None
            else None
        )
        terminal_ref = None
        if terminal is not None:
            terminal_ref = WbcEventRef(
                attempt_id=attempt_id,
                sequence=terminal.sequence,
                event_type=terminal.event_type.value,
                idempotency_key=terminal.idempotency_key,
                digest=_wbc_event_digest(terminal),
                locator=f"wbc://{attempt_id}/{terminal.sequence}",
            )
        gap_refs = _sort_refs(
            OwnerRef(
                owner="wbc",
                record_type="gap",
                identity=attempt_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"gap://{attempt_id}/{gap.gap_start}:{gap.gap_end}",
                digest=_record_digest(gap),
                cursor=f"sequence:{gap.gap_end}",
            )
            for gap in gaps
        )
        persistence_refs = _sort_refs(
            OwnerRef(
                owner="wbc",
                record_type="persistence_diagnostic",
                identity=attempt_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"persistence-diagnostic://{attempt_id}/{_diag_index(index)}",
                digest=_record_digest(diagnostic),
                cursor=f"sequence:{getattr(diagnostic, 'target_event_sequence', None) or 0}",
            )
            for index, diagnostic in enumerate(persistence)
        )
        reconciliation_refs = _sort_refs(
            OwnerRef(
                owner="wbc",
                record_type="reconciliation",
                identity=attempt_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"reconciliation-diagnostic://{attempt_id}/{_diag_index(index)}",
                digest=_record_digest(diagnostic),
                cursor=f"sequence:{getattr(diagnostic, 'reconciled_event_sequence', None) or 0}",
            )
            for index, diagnostic in enumerate(reconciliation)
        )
        source_cursor_ref = None
        if cursor is not None:
            source_cursor_ref = SourceCursorRef(
                attempt_id=attempt_id,
                cursor_key=cursor.cursor_key,
                last_sequence=cursor.last_sequence,
                last_position=cursor.last_position,
                digest=_record_digest(cursor),
            )

        return WbcRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            attempt_id=attempt_id,
            environment=self._environment,
            contract_version_before=before_contract,
            contract_version_after=after_contract,
            store_version_before=before_store,
            store_version_after=after_store,
            version_vector=SourceVersionVector(
                owner="wbc",
                source="wbc.attempt_ledger_store",
                environment=self._environment,
                before=f"contract:{before_contract}|store:{before_store}",
                after=f"contract:{after_contract}|store:{after_store}",
            ),
            handoff=m6a,
            incarnation=incarnation,
            restore_generation=restore_generation,
            high_water=high_water,
            event_refs=event_refs,
            ledger_ref=ledger_ref,
            terminal_ref=terminal_ref,
            gap_refs=gap_refs,
            persistence_diagnostics=persistence_refs,
            reconciliation=reconciliation_refs,
            source_cursor=source_cursor_ref,
            torn=(
                before_contract != after_contract or before_store != after_store
            ),
        )


def _wbc_event_digest(event: Any) -> str:
    """Digest of a WBC event using the store's canonical event serialization."""
    from arnold.workflow.attempt_ledger_store import canonical_event_json

    return hashlib.sha256(canonical_event_json(event).encode("utf-8")).hexdigest()


def _diag_index(index: int) -> str:
    return f"{index:04d}"


def read_run_authority(
    view_provider: Callable[[], Any],
    *,
    environment: EnvironmentId | str | None = None,
    request: Any | None = None,
) -> RunAuthorityRead:
    """Convenience read-only Run Authority capture (see :class:`RunAuthorityAdapter`)."""
    return RunAuthorityAdapter(
        view_provider, environment=environment
    ).read(request=request)


def read_wbc_attempt(
    store: Any,
    attempt_id: str,
    *,
    registry: HandoffRegistry | None = None,
    environment: EnvironmentId | str | None = None,
    cursor_key: str = "default",
) -> WbcRead:
    """Convenience read-only WBC capture (see :class:`WbcAdapter`)."""
    return WbcAdapter(
        store, registry=registry, environment=environment
    ).read_attempt(attempt_id, cursor_key=cursor_key)


# ---------------------------------------------------------------------------
# M7 Custody adapter (lease history / current lease / validator evidence)
# ---------------------------------------------------------------------------


class CustodyRead(BaseModel):
    """Immutable read-only M7 Custody capture.

    Emits only locator references to the current lease, its append-only
    history, and validator evidence — never copies of the records.  Until
    the M7 handoff is accepted, the result is typed UNKNOWN with the
    resolution reason preserved and no references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    lease_id: StrictStr
    environment: EnvironmentId | None = None
    handoff: HandoffResolution | None = None
    #: Exact accepted owner coordinates from the approved M7 row; typed
    #: UNKNOWN reads carry ``None`` (never inferred, never guessed).
    owner_api_identity: StrictStr | None = None
    owner_schema_version: StrictStr | None = None
    #: M7 RepairOccurrenceKey bound to this lease (explicit ``None`` when the
    #: lease record does not expose it).  The coherent join requires the
    #: occurrence identity to match the declared occurrence across every
    #: source; a cross-occurrence read is typed INCOHERENT.
    occurrence_id: StrictStr | None = None
    #: Current lease fencing token (explicit ``None`` when unavailable).  A
    #: fence is an identity dimension of the occurrence-bound join: matching
    #: lease/fence coordinates are required for a coherent envelope.
    fencing_token: StrictStr | None = None
    current_lease_ref: OwnerRef | None = None
    history_refs: tuple[OwnerRef, ...] = ()
    validator_evidence_refs: tuple[OwnerRef, ...] = ()
    version_vector: SourceVersionVector
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("owner_api_identity", "owner_schema_version")
    @classmethod
    def _validate_owner_coordinates(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "owner api identity/schema version must be non-empty strings "
                "when present"
            )
        return value

    @field_validator("occurrence_id", "fencing_token")
    @classmethod
    def _validate_occurrence_coordinates(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "occurrence_id/fencing_token must be non-empty strings when present"
            )
        return value

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class CustodyAdapter:
    """Read-only adapter over the M7 Custody lease/validator surfaces.

    Consumes the exact read APIs (``current_lease``, ``replay_history`` /
    ``load_history``, validator evidence reads) through injected providers;
    it NEVER acquires, renews, transfers, releases, expires, or fences a
    lease, never validates actions anew, and never instantiates a competing
    owner service.  Every read is gated by the M7 handoff registry row:
    until the row is complete AND approved, the result stays typed UNKNOWN.
    """

    def __init__(
        self,
        *,
        current_lease_provider: Callable[[str], Any],
        history_provider: Callable[[str], Sequence[Any]],
        validator_evidence_provider: Callable[[str], Sequence[Any]] | None = None,
        registry: HandoffRegistry | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._current_lease_provider = current_lease_provider
        self._history_provider = history_provider
        self._validator_evidence_provider = validator_evidence_provider
        self._registry = registry if registry is not None else default_handoff_registry()
        self._environment = environment

    def _version(self, lease_id: str) -> str | None:
        """Lightweight owner version coordinate: the current lease digest."""
        current = self._current_lease_provider(lease_id)
        return _record_digest(current) if current is not None else None

    def probe(self, lease_id: str) -> str | None:
        """Owner-backed version probe consumed by the coherent join (T9).

        Returns ``None`` while the M7 handoff is unaccepted (typed UNKNOWN);
        otherwise the current lease digest, so a mid-read lease change tears.
        """
        if self._registry.resolve("M7").state is not HandoffResolutionState.ACCEPTED:
            return None
        return self._version(lease_id)

    def read(self, lease_id: str) -> CustodyRead:
        m7 = self._registry.resolve("M7")
        if m7.state is not HandoffResolutionState.ACCEPTED or m7.row is None:
            return CustodyRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                lease_id=lease_id,
                environment=self._environment,
                handoff=m7,
                version_vector=SourceVersionVector(
                    owner="custody",
                    source="custody.lease_store",
                    environment=self._environment,
                    before=None,
                    after=None,
                ),
            )
        # Validate the accepted handoff identity before consuming evidence:
        # source path and schema identity must match the approved row exactly.
        row = m7.row
        if row.source_path != "megaplan/controlled_writers":
            return CustodyRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                lease_id=lease_id,
                environment=self._environment,
                handoff=HandoffResolution(
                    handoff_id="M7",
                    state=HandoffResolutionState.UNKNOWN,
                    approval=m7.approval,
                    reason=HandoffResolutionReason.PATH_MISMATCH,
                ),
                version_vector=SourceVersionVector(
                    owner="custody",
                    source="custody.lease_store",
                    environment=self._environment,
                    before=None,
                    after=None,
                ),
            )
        before_digest = self._version(lease_id)
        current = self._current_lease_provider(lease_id)
        history = tuple(self._history_provider(lease_id))
        evidence = (
            tuple(self._validator_evidence_provider(lease_id))
            if self._validator_evidence_provider is not None
            else ()
        )
        after_digest = self._version(lease_id)
        current_ref = (
            OwnerRef(
                owner="custody",
                record_type="current_lease",
                identity=lease_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"lease://{lease_id}",
                digest=_record_digest(current),
                cursor=f"epoch:{getattr(current, 'custody_epoch', 0)}",
            )
            if current is not None
            else None
        )
        history_refs = _sort_refs(
            OwnerRef(
                owner="custody",
                record_type="lease_event",
                identity=lease_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"lease-event://{lease_id}/{getattr(event, 'sequence', index)}",
                digest=_record_digest(event),
            )
            for index, event in enumerate(history)
        )
        evidence_refs = _sort_refs(
            OwnerRef(
                owner="custody",
                record_type="validator_evidence",
                identity=lease_id,
                schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                locator=f"validator-evidence://{lease_id}/{index}",
                digest=_record_digest(evidence_record),
            )
            for index, evidence_record in enumerate(evidence)
        )
        return CustodyRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            lease_id=lease_id,
            environment=self._environment,
            handoff=m7,
            owner_api_identity=row.owner_api_identity,
            owner_schema_version=row.schema_version,
            occurrence_id=getattr(current, "occurrence_id", None),
            fencing_token=getattr(current, "fencing_token", None),
            current_lease_ref=current_ref,
            history_refs=history_refs,
            validator_evidence_refs=evidence_refs,
            version_vector=SourceVersionVector(
                owner="custody",
                source="custody.lease_store",
                environment=self._environment,
                before=before_digest,
                after=after_digest,
            ),
            torn=(before_digest != after_digest),
        )


def read_custody(
    lease_id: str,
    *,
    current_lease_provider: Callable[[str], Any],
    history_provider: Callable[[str], Sequence[Any]],
    validator_evidence_provider: Callable[[str], Sequence[Any]] | None = None,
    registry: HandoffRegistry | None = None,
    environment: EnvironmentId | str | None = None,
) -> CustodyRead:
    """Convenience read-only M7 capture (see :class:`CustodyAdapter`)."""
    return CustodyAdapter(
        current_lease_provider=current_lease_provider,
        history_provider=history_provider,
        validator_evidence_provider=validator_evidence_provider,
        registry=registry,
        environment=environment,
    ).read(lease_id)


# ---------------------------------------------------------------------------
# M10/M11 conformance adapter (validation + predecessor-wrapper evidence)
# ---------------------------------------------------------------------------


class ConformanceRead(BaseModel):
    """Immutable read-only M10/M11 conformance capture.

    Emits only references to accepted validation evidence and the
    predecessor-wrapper evidence chain.  Until the M10/M11 handoffs are
    accepted, the result is typed UNKNOWN with reasons preserved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    subject: StrictStr
    environment: EnvironmentId | None = None
    handoffs: tuple[HandoffResolution, ...] = ()
    #: Exact accepted owner coordinates from the approved M10/M11 rows
    #: (canonical handoff-id order); typed UNKNOWN reads carry ``()``.
    owner_api_identities: tuple[str, ...] = ()
    owner_schema_versions: tuple[str, ...] = ()
    validation_refs: tuple[OwnerRef, ...] = ()
    predecessor_wrapper_refs: tuple[OwnerRef, ...] = ()
    version_vector: SourceVersionVector
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class ConformanceAdapter:
    """Read-only adapter over accepted M10/M11 validation evidence.

    Consumes the validation outcome and predecessor-wrapper evidence through
    injected read providers; it never validates actions anew and never
    instantiates a competing validator.  Both M10 and M11 handoffs must be
    accepted before any evidence reference is emitted; otherwise the result
    stays typed UNKNOWN with the pending/missing reasons preserved.
    """

    def __init__(
        self,
        *,
        validation_evidence_provider: Callable[[str], Sequence[Any]],
        predecessor_wrapper_provider: Callable[[str], Sequence[Any]] | None = None,
        registry: HandoffRegistry | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._validation_evidence_provider = validation_evidence_provider
        self._predecessor_wrapper_provider = predecessor_wrapper_provider
        self._registry = registry if registry is not None else default_handoff_registry()
        self._environment = environment

    def _version(self, subject: str) -> str | None:
        """Lightweight owner version coordinate over validation + wrappers."""
        validation = tuple(self._validation_evidence_provider(subject))
        wrappers = (
            tuple(self._predecessor_wrapper_provider(subject))
            if self._predecessor_wrapper_provider is not None
            else ()
        )
        if not validation and not wrappers:
            return None
        material = {
            "validation": [_record_digest(record) for record in validation],
            "predecessor_wrappers": [_record_digest(record) for record in wrappers],
        }
        return _record_digest(material)

    def probe(self, subject: str) -> str | None:
        """Owner-backed version probe consumed by the coherent join (T9)."""
        m10 = self._registry.resolve("M10")
        m11 = self._registry.resolve("M11")
        if (
            m10.state is not HandoffResolutionState.ACCEPTED
            or m11.state is not HandoffResolutionState.ACCEPTED
        ):
            return None
        return self._version(subject)

    def read(self, subject: str) -> ConformanceRead:
        m10 = self._registry.resolve("M10")
        m11 = self._registry.resolve("M11")
        handoffs = (m10, m11)
        if (
            m10.state is not HandoffResolutionState.ACCEPTED
            or m11.state is not HandoffResolutionState.ACCEPTED
        ):
            return ConformanceRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                subject=subject,
                environment=self._environment,
                handoffs=handoffs,
                version_vector=SourceVersionVector(
                    owner="conformance",
                    source="megaplan.conformance",
                    environment=self._environment,
                    before=None,
                    after=None,
                ),
            )
        before = self._version(subject)
        validation = tuple(self._validation_evidence_provider(subject))
        wrappers = (
            tuple(self._predecessor_wrapper_provider(subject))
            if self._predecessor_wrapper_provider is not None
            else ()
        )
        after = self._version(subject)
        accepted_rows = {
            resolution.handoff_id: resolution.row
            for resolution in (m10, m11)
            if resolution.state is HandoffResolutionState.ACCEPTED
            and resolution.row is not None
        }
        return ConformanceRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            subject=subject,
            environment=self._environment,
            handoffs=handoffs,
            owner_api_identities=tuple(
                accepted_rows[hid].owner_api_identity for hid in ("M10", "M11")
            ),
            owner_schema_versions=tuple(
                accepted_rows[hid].schema_version for hid in ("M10", "M11")
            ),
            validation_refs=_sort_refs(
                OwnerRef(
                    owner="conformance",
                    record_type="validation",
                    identity=subject,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"validation://{subject}/{index}",
                    digest=_record_digest(record),
                )
                for index, record in enumerate(validation)
            ),
            predecessor_wrapper_refs=_sort_refs(
                OwnerRef(
                    owner="conformance",
                    record_type="predecessor_wrapper",
                    identity=subject,
                    schema_version=str(MAINTENANCE_SCHEMA_VERSION),
                    locator=f"predecessor-wrapper://{subject}/{index}",
                    digest=_record_digest(record),
                )
                for index, record in enumerate(wrappers)
            ),
            version_vector=SourceVersionVector(
                owner="conformance",
                source="megaplan.conformance",
                environment=self._environment,
                before=before,
                after=after,
            ),
            torn=(before != after),
        )


def read_conformance(
    subject: str,
    *,
    validation_evidence_provider: Callable[[str], Sequence[Any]],
    predecessor_wrapper_provider: Callable[[str], Sequence[Any]] | None = None,
    registry: HandoffRegistry | None = None,
    environment: EnvironmentId | str | None = None,
) -> ConformanceRead:
    """Convenience read-only M10/M11 capture (see :class:`ConformanceAdapter`)."""
    return ConformanceAdapter(
        validation_evidence_provider=validation_evidence_provider,
        predecessor_wrapper_provider=predecessor_wrapper_provider,
        registry=registry,
        environment=environment,
    ).read(subject)


# ---------------------------------------------------------------------------
# Native Parity adapter (C1/C2/S1/S2R neutral manifest/conformance APIs)
# ---------------------------------------------------------------------------


class NativeManifestRead(BaseModel):
    """Immutable read-only Native Parity capture for one handoff id.

    ``handoff_id`` is one of C1/C2/S1/S2R.  Emits only the neutral manifest
    reference (locator + canonical digest) and the schema identity after
    validating source path, schema, digest, approval, and shared identity.
    Until the handoff is accepted the result is typed UNKNOWN.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    handoff_id: StrictStr
    subject: StrictStr
    environment: EnvironmentId | None = None
    handoff: HandoffResolution | None = None
    #: Exact accepted owner coordinates from the approved row; typed
    #: UNKNOWN reads carry ``None`` (never inferred, never guessed).
    owner_api_identity: StrictStr | None = None
    owner_schema_version: StrictStr | None = None
    manifest_ref: OwnerRef | None = None
    schema_identity: StrictStr | None = None
    version_vector: SourceVersionVector
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class NativeManifestAdapter:
    """Read-only adapter over neutral Native Parity manifest/conformance APIs.

    The adapter consumes ONE neutral read surface (the injected
    ``manifest_provider``) for the C1/C2/S1/S2R handoff ids; it never
    implements C1/C2 completion semantics or S1/S2R runtime primitives and
    never instantiates a competing owner service.  Source path, schema
    identity, digest, approval, and shared identity are validated against
    the accepted handoff row; mismatches and missing/unapproved handoffs
    stay typed UNKNOWN.
    """

    #: Neutral Native manifest source-path prefix for the four handoff ids.
    _SOURCE_PATHS: dict[str, str] = {
        "C1": "native/completion/c1",
        "C2": "native/completion/c2",
        "S1": "native/runtime/s1",
        "S2R": "native/runtime/s2r",
    }

    def __init__(
        self,
        *,
        manifest_provider: Callable[[str, str], Any],
        registry: HandoffRegistry | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._manifest_provider = manifest_provider
        self._registry = registry if registry is not None else default_handoff_registry()
        self._environment = environment

    def _version(self, handoff_id: str, subject: str) -> str | None:
        """Lightweight owner version coordinate: the neutral manifest digest."""
        resolution = self._registry.resolve(handoff_id)
        if resolution.state is not HandoffResolutionState.ACCEPTED or resolution.row is None:
            return None
        try:
            manifest = self._manifest_provider(handoff_id, subject)
        except Exception:
            return None
        if manifest is None:
            return None
        return _record_digest(manifest)

    def probe(self, handoff_id: str, subject: str) -> str | None:
        """Owner-backed version probe consumed by the coherent join (T9)."""
        return self._version(handoff_id, subject)

    def _unknown(
        self,
        handoff_id: str,
        subject: str,
        source: str,
        resolution: HandoffResolution,
        reason: HandoffResolutionReason,
    ) -> NativeManifestRead:
        """A typed UNKNOWN read carrying no references (never acceptance)."""
        return NativeManifestRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            handoff_id=handoff_id,
            subject=subject,
            environment=self._environment,
            handoff=HandoffResolution(
                handoff_id=handoff_id,
                state=HandoffResolutionState.UNKNOWN,
                approval=resolution.approval,
                reason=reason,
            ),
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source=source,
                environment=self._environment,
                before=None,
                after=None,
            ),
        )

    def read(self, handoff_id: str, subject: str) -> NativeManifestRead:
        if handoff_id not in self._SOURCE_PATHS:
            raise ValueError(
                f"unknown Native handoff id {handoff_id!r}; expected one of "
                f"{sorted(self._SOURCE_PATHS)}"
            )
        expected_path = self._SOURCE_PATHS[handoff_id]
        resolution = self._registry.resolve(handoff_id)
        if resolution.state is not HandoffResolutionState.ACCEPTED or resolution.row is None:
            return NativeManifestRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                handoff_id=handoff_id,
                subject=subject,
                environment=self._environment,
                handoff=resolution,
                version_vector=SourceVersionVector(
                    owner="native_manifest",
                    source=expected_path,
                    environment=self._environment,
                    before=None,
                    after=None,
                ),
            )
        row = resolution.row
        # Validate source path, schema identity, digest, approval, and shared
        # identity against the approved row; a mismatch is typed UNKNOWN, never
        # acceptance, and never emits a manifest reference.
        if row.source_path != expected_path:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.PATH_MISMATCH,
            )
        before = self._version(handoff_id, subject)
        manifest = self._manifest_provider(handoff_id, subject)
        after = self._version(handoff_id, subject)
        if manifest is None:
            return NativeManifestRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                handoff_id=handoff_id,
                subject=subject,
                environment=self._environment,
                handoff=resolution,
                version_vector=SourceVersionVector(
                    owner="native_manifest",
                    source=expected_path,
                    environment=self._environment,
                    before=before,
                    after=after,
                ),
                torn=(before != after),
            )
        manifest_schema = getattr(manifest, "schema_identity", None)
        if manifest_schema is not None and manifest_schema != row.schema_identity:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.SCHEMA_MISMATCH,
            )
        manifest_identity = getattr(manifest, "identity", None)
        if manifest_identity is not None and manifest_identity != subject:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.IDENTITY_MISMATCH,
            )
        digest = _record_digest(manifest)
        if row.digest is not None and digest != row.digest:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.DIGEST_MISMATCH,
            )
        return NativeManifestRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            handoff_id=handoff_id,
            subject=subject,
            environment=self._environment,
            handoff=resolution,
            owner_api_identity=row.owner_api_identity,
            owner_schema_version=row.schema_version,
            manifest_ref=OwnerRef(
                owner="native_manifest",
                record_type="manifest",
                identity=subject,
                schema_version=row.schema_identity,
                locator=f"{expected_path}//{subject}",
                digest=digest,
            ),
            schema_identity=row.schema_identity,
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source=expected_path,
                environment=self._environment,
                before=before,
                after=after,
            ),
            torn=(before != after),
        )


def read_native_manifest(
    handoff_id: str,
    subject: str,
    *,
    manifest_provider: Callable[[str, str], Any],
    registry: HandoffRegistry | None = None,
    environment: EnvironmentId | str | None = None,
) -> NativeManifestRead:
    """Convenience read-only Native capture (see :class:`NativeManifestAdapter`)."""
    return NativeManifestAdapter(
        manifest_provider=manifest_provider,
        registry=registry,
        environment=environment,
    ).read(handoff_id, subject)


# ---------------------------------------------------------------------------
# C2 negative-control proof and S1/S2R runtime/source adapters (M3 Step 5)
# ---------------------------------------------------------------------------


class ProofRead(BaseModel):
    """Immutable read-only C2 negative-control proof capture.

    Emits only a locator reference to the accepted proof record plus its
    negative-control references — never a copy of the proof.  Until the C2
    handoff is accepted, the result is typed UNKNOWN with the resolution
    reason preserved and no references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    proof_id: StrictStr
    subject: StrictStr
    environment: EnvironmentId | None = None
    handoff: HandoffResolution | None = None
    owner_api_identity: StrictStr | None = None
    owner_schema_version: StrictStr | None = None
    proof_ref: OwnerRef | None = None
    control_refs: tuple[OwnerRef, ...] = ()
    version_vector: SourceVersionVector
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("proof_id", "subject")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("proof_id/subject must be non-empty strings")
        return value

    @field_validator("owner_api_identity", "owner_schema_version")
    @classmethod
    def _validate_owner_coordinates(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "owner api identity/schema version must be non-empty strings "
                "when present"
            )
        return value

    @field_validator("control_refs")
    @classmethod
    def _sort_refs(cls, value: Sequence[OwnerRef]) -> tuple[OwnerRef, ...]:
        return _sort_refs(value)

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


class ProofAdapter:
    """Read-only adapter over the C2 negative-control proof surface.

    Consumes the exact read APIs (proof record read, optional negative
    control reads) through injected providers; it NEVER submits, approves,
    or writes a proof, and never instantiates a competing completion engine.
    Every read is gated by the C2 handoff registry row: until the row is
    complete AND approved, the result stays typed UNKNOWN.
    """

    def __init__(
        self,
        *,
        proof_provider: Callable[[str], Any],
        control_provider: Callable[[str], Sequence[Any]] | None = None,
        registry: HandoffRegistry | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._proof_provider = proof_provider
        self._control_provider = control_provider
        self._registry = registry if registry is not None else default_handoff_registry()
        self._environment = environment

    def _version(self, proof_id: str) -> str | None:
        """Owner version coordinate: the proof record digest."""
        proof = self._proof_provider(proof_id)
        return _record_digest(proof) if proof is not None else None

    def probe(self, proof_id: str) -> str | None:
        """Owner-backed version probe consumed by the coherent join.

        Returns ``None`` while the C2 handoff is unaccepted (typed UNKNOWN);
        otherwise the proof digest, so a mid-read proof change tears.
        """
        if self._registry.resolve("C2").state is not HandoffResolutionState.ACCEPTED:
            return None
        return self._version(proof_id)

    def read(self, proof_id: str, subject: str) -> ProofRead:
        c2 = self._registry.resolve("C2")
        if c2.state is not HandoffResolutionState.ACCEPTED or c2.row is None:
            return ProofRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                proof_id=proof_id,
                subject=subject,
                environment=self._environment,
                handoff=c2,
                version_vector=SourceVersionVector(
                    owner="native_manifest",
                    source="native/completion/c2",
                    environment=self._environment,
                    before=None,
                    after=None,
                ),
            )
        row = c2.row
        if row.source_path != "native/completion/c2":
            return self._unknown(
                proof_id, subject, c2, HandoffResolutionReason.PATH_MISMATCH
            )
        before = self._version(proof_id)
        proof = self._proof_provider(proof_id)
        controls = (
            tuple(self._control_provider(proof_id))
            if self._control_provider is not None
            else ()
        )
        after = self._version(proof_id)
        if proof is None:
            return ProofRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                proof_id=proof_id,
                subject=subject,
                environment=self._environment,
                handoff=c2,
                version_vector=SourceVersionVector(
                    owner="native_manifest",
                    source="native/completion/c2",
                    environment=self._environment,
                    before=before,
                    after=after,
                ),
                torn=(before != after),
            )
        proof_schema = getattr(proof, "schema_identity", None)
        if proof_schema is not None and proof_schema != row.schema_identity:
            return self._unknown(
                proof_id, subject, c2, HandoffResolutionReason.SCHEMA_MISMATCH
            )
        proof_identity = getattr(proof, "identity", None)
        if proof_identity is not None and proof_identity != subject:
            return self._unknown(
                proof_id, subject, c2, HandoffResolutionReason.IDENTITY_MISMATCH
            )
        digest = _record_digest(proof)
        if row.digest is not None and digest != row.digest:
            return self._unknown(
                proof_id, subject, c2, HandoffResolutionReason.DIGEST_MISMATCH
            )
        return ProofRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            proof_id=proof_id,
            subject=subject,
            environment=self._environment,
            handoff=c2,
            owner_api_identity=row.owner_api_identity,
            owner_schema_version=row.schema_version,
            proof_ref=OwnerRef(
                owner="native_manifest",
                record_type="negative_control_proof",
                identity=subject,
                schema_version=row.schema_identity,
                locator=f"native/completion/c2//{subject}",
                digest=digest,
            ),
            control_refs=_sort_refs(
                OwnerRef(
                    owner="native_manifest",
                    record_type="negative_control",
                    identity=subject,
                    schema_version=row.schema_identity,
                    locator=f"native/completion/c2//{subject}/control/{index}",
                    digest=_record_digest(control),
                )
                for index, control in enumerate(controls)
            ),
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source="native/completion/c2",
                environment=self._environment,
                before=before,
                after=after,
            ),
            torn=(before != after),
        )

    def _unknown(
        self,
        proof_id: str,
        subject: str,
        resolution: HandoffResolution,
        reason: HandoffResolutionReason,
    ) -> ProofRead:
        return ProofRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            proof_id=proof_id,
            subject=subject,
            environment=self._environment,
            handoff=HandoffResolution(
                handoff_id="C2",
                state=HandoffResolutionState.UNKNOWN,
                approval=resolution.approval,
                reason=reason,
            ),
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source="native/completion/c2",
                environment=self._environment,
                before=None,
                after=None,
            ),
        )


def read_proof(
    proof_id: str,
    subject: str,
    *,
    proof_provider: Callable[[str], Any],
    control_provider: Callable[[str], Sequence[Any]] | None = None,
    registry: HandoffRegistry | None = None,
    environment: EnvironmentId | str | None = None,
) -> ProofRead:
    """Convenience read-only C2 capture (see :class:`ProofAdapter`)."""
    return ProofAdapter(
        proof_provider=proof_provider,
        control_provider=control_provider,
        registry=registry,
        environment=environment,
    ).read(proof_id, subject)


class RuntimeRead(BaseModel):
    """Immutable read-only S1/S2R runtime/source capture.

    Emits only locator references to the accepted runtime and source
    manifests — never copies of them.  Until the S1/S2R handoff is accepted,
    the result is typed UNKNOWN with the resolution reason preserved and no
    references.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=MAINTENANCE_SCHEMA_VERSION, frozen=True)
    runtime_id: StrictStr
    subject: StrictStr
    environment: EnvironmentId | None = None
    handoff: HandoffResolution | None = None
    owner_api_identity: StrictStr | None = None
    owner_schema_version: StrictStr | None = None
    runtime_ref: OwnerRef | None = None
    source_ref: OwnerRef | None = None
    version_vector: SourceVersionVector
    torn: bool = False

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != MAINTENANCE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported Maintenance schema version {value}; expected "
                f"{MAINTENANCE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("runtime_id", "subject")
    @classmethod
    def _validate_nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("runtime_id/subject must be non-empty strings")
        return value

    @field_validator("owner_api_identity", "owner_schema_version")
    @classmethod
    def _validate_owner_coordinates(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError(
                "owner api identity/schema version must be non-empty strings "
                "when present"
            )
        return value

    @property
    def digest(self) -> str:
        """Canonical digest of the whole read result (replayable)."""
        return canonical_digest(self)


#: Exact owner source path per S1/S2R handoff id (the Native Parity runtime
#: schema surface).  Unknown ids are rejected — a runtime source is never
#: guessed.
RUNTIME_SOURCE_PATHS: dict[str, str] = {
    "S1": "native/runtime/s1",
    "S2R": "native/runtime/s2r",
}


class RuntimeAdapter:
    """Read-only adapter over the S1/S2R runtime/source manifest surface.

    Consumes the exact read APIs (runtime manifest read, optional source
    manifest read) through injected providers; it NEVER installs, restarts,
    or writes a runtime, and never instantiates a competing runtime engine.
    Every read is gated by the S1/S2R handoff registry row: until the row is
    complete AND approved, the result stays typed UNKNOWN.
    """

    def __init__(
        self,
        *,
        runtime_provider: Callable[[str, str], Any],
        source_provider: Callable[[str, str], Any] | None = None,
        registry: HandoffRegistry | None = None,
        environment: EnvironmentId | str | None = None,
    ) -> None:
        self._runtime_provider = runtime_provider
        self._source_provider = source_provider
        self._registry = registry if registry is not None else default_handoff_registry()
        self._environment = environment

    def _version(self, handoff_id: str, subject: str) -> str | None:
        """Owner version coordinate: the runtime manifest digest."""
        runtime = self._runtime_provider(handoff_id, subject)
        return _record_digest(runtime) if runtime is not None else None

    def probe(self, handoff_id: str, subject: str) -> str | None:
        """Owner-backed version probe consumed by the coherent join.

        Returns ``None`` while the S1/S2R handoff is unaccepted (typed
        UNKNOWN); otherwise the runtime digest, so a mid-read runtime change
        tears.
        """
        if handoff_id not in RUNTIME_SOURCE_PATHS:
            return None
        if self._registry.resolve(handoff_id).state is not HandoffResolutionState.ACCEPTED:
            return None
        return self._version(handoff_id, subject)

    def read(self, handoff_id: str, subject: str) -> RuntimeRead:
        expected_path = RUNTIME_SOURCE_PATHS.get(handoff_id)
        if expected_path is None:
            raise ValueError(
                f"unknown runtime handoff id {handoff_id!r}; expected one of "
                f"{sorted(RUNTIME_SOURCE_PATHS)}"
            )
        resolution = self._registry.resolve(handoff_id)
        if resolution.state is not HandoffResolutionState.ACCEPTED or resolution.row is None:
            return RuntimeRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                runtime_id=handoff_id,
                subject=subject,
                environment=self._environment,
                handoff=resolution,
                version_vector=SourceVersionVector(
                    owner="native_manifest",
                    source=expected_path,
                    environment=self._environment,
                    before=None,
                    after=None,
                ),
            )
        row = resolution.row
        if row.source_path != expected_path:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.PATH_MISMATCH,
            )
        before = self._version(handoff_id, subject)
        runtime = self._runtime_provider(handoff_id, subject)
        source = (
            self._source_provider(handoff_id, subject)
            if self._source_provider is not None
            else None
        )
        after = self._version(handoff_id, subject)
        if runtime is None:
            return RuntimeRead(
                schema_version=MAINTENANCE_SCHEMA_VERSION,
                runtime_id=handoff_id,
                subject=subject,
                environment=self._environment,
                handoff=resolution,
                version_vector=SourceVersionVector(
                    owner="native_manifest",
                    source=expected_path,
                    environment=self._environment,
                    before=before,
                    after=after,
                ),
                torn=(before != after),
            )
        runtime_schema = getattr(runtime, "schema_identity", None)
        if runtime_schema is not None and runtime_schema != row.schema_identity:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.SCHEMA_MISMATCH,
            )
        runtime_identity = getattr(runtime, "identity", None)
        if runtime_identity is not None and runtime_identity != subject:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.IDENTITY_MISMATCH,
            )
        digest = _record_digest(runtime)
        if row.digest is not None and digest != row.digest:
            return self._unknown(
                handoff_id, subject, expected_path, resolution,
                HandoffResolutionReason.DIGEST_MISMATCH,
            )
        source_ref = None
        if source is not None:
            source_ref = OwnerRef(
                owner="native_manifest",
                record_type="runtime_source",
                identity=subject,
                schema_version=row.schema_identity,
                locator=f"{expected_path}//{subject}/source",
                digest=_record_digest(source),
            )
        return RuntimeRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            runtime_id=handoff_id,
            subject=subject,
            environment=self._environment,
            handoff=resolution,
            owner_api_identity=row.owner_api_identity,
            owner_schema_version=row.schema_version,
            runtime_ref=OwnerRef(
                owner="native_manifest",
                record_type="runtime_manifest",
                identity=subject,
                schema_version=row.schema_identity,
                locator=f"{expected_path}//{subject}",
                digest=digest,
            ),
            source_ref=source_ref,
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source=expected_path,
                environment=self._environment,
                before=before,
                after=after,
            ),
            torn=(before != after),
        )

    def _unknown(
        self,
        handoff_id: str,
        subject: str,
        expected_path: str,
        resolution: HandoffResolution,
        reason: HandoffResolutionReason,
    ) -> RuntimeRead:
        return RuntimeRead(
            schema_version=MAINTENANCE_SCHEMA_VERSION,
            runtime_id=handoff_id,
            subject=subject,
            environment=self._environment,
            handoff=HandoffResolution(
                handoff_id=handoff_id,
                state=HandoffResolutionState.UNKNOWN,
                approval=resolution.approval,
                reason=reason,
            ),
            version_vector=SourceVersionVector(
                owner="native_manifest",
                source=expected_path,
                environment=self._environment,
                before=None,
                after=None,
            ),
        )


def read_runtime(
    handoff_id: str,
    subject: str,
    *,
    runtime_provider: Callable[[str, str], Any],
    source_provider: Callable[[str, str], Any] | None = None,
    registry: HandoffRegistry | None = None,
    environment: EnvironmentId | str | None = None,
) -> RuntimeRead:
    """Convenience read-only S1/S2R capture (see :class:`RuntimeAdapter`)."""
    return RuntimeAdapter(
        runtime_provider=runtime_provider,
        source_provider=source_provider,
        registry=registry,
        environment=environment,
    ).read(handoff_id, subject)


__all__ = [
    "ConformanceAdapter",
    "ConformanceRead",
    "CurrentSourceRead",
    "CustodyAdapter",
    "CustodyRead",
    "NativeManifestAdapter",
    "NativeManifestRead",
    "ProofAdapter",
    "ProofRead",
    "RUNTIME_SOURCE_PATHS",
    "RunAuthorityAdapter",
    "RunAuthorityRead",
    "RuntimeAdapter",
    "RuntimeRead",
    "SourceCursorRef",
    "WbcAdapter",
    "WbcEventRef",
    "WbcRead",
    "read_conformance",
    "read_custody",
    "read_native_manifest",
    "read_proof",
    "read_run_authority",
    "read_runtime",
    "read_wbc_attempt",
]
