"""Shared WBC runtime producer facade for M8 producer adoption."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol

from arnold.workflow.attempt_ledger_store import (
    AppendResult,
    AttemptLedgerStore,
    AttemptReservation,
    GateStatus,
    SourceCursor,
    StartGateResult,
    TerminalGateResult,
)
from arnold.workflow.execution_attempt_ledger import ExecutionAttemptLedger, LedgerEvent

from .action_validator import ActionBoundaryContext, ActionBoundaryResult, GateResult, validate_action_boundary
from .compatibility import RollbackValidation
from .controlled_writer_registry import WriteGuardDecision, WriteGuardResult, writer_guard
from .lease_store import CustodyLeaseStore
from .outbox import CustodyOutbox


class PromotionMode(StrEnum):
    OBSERVE = "observe"
    ACTION_OFF = "action_off"
    PROMOTE = "promote"


class RuntimeOperation(StrEnum):
    RESERVE = "reserve"
    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"
    SUSPEND = "suspend"
    RESUME = "resume"
    RETRY = "retry"
    EFFECT_INTENT = "effect_intent"
    EFFECT_OUTCOME = "effect_outcome"
    AUTHORITATIVE_REREAD = "authoritative_reread"


class RuntimeFacadeError(RuntimeError):
    """Base class for fail-closed runtime facade errors."""


class WriterGuardError(RuntimeFacadeError):
    """Raised when a writer is not currently allowed to emit WBC events."""


class ExactSourceLookupError(RuntimeFacadeError):
    """Raised when the exact source version cannot be re-read and matched."""


class ActionBoundaryDeniedError(RuntimeFacadeError):
    """Raised when run authority, fence, custody, or WBC evidence is stale."""


class AuthoritativeRereadError(RuntimeFacadeError):
    """Raised when a post-write reread cannot prove the just-written state."""


class ExactSourceLookup(Protocol):
    def __call__(self, lookup_key: str) -> "ExactSourceRecord | None":
        ...


class ExternalEffectExecutor(Protocol):
    def __call__(
        self,
        *,
        source_record: "ExactSourceRecord",
        artifacts: "ImmutableAttemptArtifacts",
        intent_event: LedgerEvent | None,
        outcome_event: LedgerEvent,
    ) -> Any:
        ...


class RollbackValidator(Protocol):
    def __call__(self) -> RollbackValidation:
        ...


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(value[key]) for key in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not value:
        return MappingProxyType({})
    return MappingProxyType({str(key): _freeze_json(item) for key, item in sorted(value.items())})


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class AttemptArtifact:
    artifact_id: str
    artifact_kind: str
    version: str
    locator: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _required(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "artifact_kind", _required(self.artifact_kind, "artifact_kind"))
        object.__setattr__(self, "version", _required(self.version, "version"))
        object.__setattr__(self, "locator", str(self.locator))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "version": self.version,
            "locator": self.locator,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ImmutableAttemptArtifacts:
    attempt_id: str
    artifacts: tuple[AttemptArtifact, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attempt_id", _required(self.attempt_id, "attempt_id"))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExactSourceRecord:
    lookup_key: str
    version: str
    source_uri: str = ""
    observed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lookup_key", _required(self.lookup_key, "lookup_key"))
        object.__setattr__(self, "version", _required(self.version, "version"))
        object.__setattr__(self, "source_uri", str(self.source_uri))
        object.__setattr__(self, "observed_at", str(self.observed_at))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "lookup_key": self.lookup_key,
            "version": self.version,
            "source_uri": self.source_uri,
            "observed_at": self.observed_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AuthoritativeRereadResult:
    attempt_id: str
    ledger: ExecutionAttemptLedger
    events: tuple[LedgerEvent, ...]
    verified_event: LedgerEvent | None = None
    started_gate: StartGateResult | None = None
    terminal_gate: TerminalGateResult | None = None
    source_cursor: SourceCursor | None = None


@dataclass(frozen=True)
class RuntimeProducerResult:
    operation: RuntimeOperation
    attempt_id: str
    writer_guard: WriteGuardResult
    source_record: ExactSourceRecord
    action_boundary: ActionBoundaryResult | None = None
    reservation: AttemptReservation | None = None
    append_result: AppendResult | None = None
    authoritative_reread: AuthoritativeRereadResult | None = None
    artifacts: ImmutableAttemptArtifacts | None = None
    promotion_mode: PromotionMode = PromotionMode.ACTION_OFF
    external_effect_executed: bool = False
    rollback_validation: RollbackValidation | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


class WbcRuntimeProducerFacade:
    """Shared runtime producer entrypoint for WBC-backed boundary mutations."""

    def __init__(
        self,
        ledger_store: AttemptLedgerStore,
        *,
        source_lookup: ExactSourceLookup,
        lease_store: CustodyLeaseStore | None = None,
        outbox: CustodyOutbox | None = None,
        promotion_mode: PromotionMode = PromotionMode.ACTION_OFF,
        enforcement_enabled: bool = True,
        writer_guard_fn: Callable[..., WriteGuardResult] = writer_guard,
        rollback_validator: RollbackValidator | None = None,
    ) -> None:
        self._ledger_store = ledger_store
        self._source_lookup = source_lookup
        self._lease_store = lease_store
        self._outbox = outbox
        self._promotion_mode = PromotionMode(promotion_mode)
        self._enforcement_enabled = bool(enforcement_enabled)
        self._writer_guard_fn = writer_guard_fn
        self._rollback_validator = rollback_validator

    @property
    def promotion_mode(self) -> PromotionMode:
        return self._promotion_mode

    def reserve_attempt(
        self,
        *,
        attempt_id: str,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        guard, source_record, boundary, rollback_validation = self._preflight(
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
        )
        reservation = self._ledger_store.reserve_attempt(attempt_id)
        reread = self._build_authoritative_reread(attempt_id=attempt_id, cursor_key=cursor_key)
        effective_mode, _ = self._effective_promotion_mode(
            rollback_validation=rollback_validation
        )
        return RuntimeProducerResult(
            operation=RuntimeOperation.RESERVE,
            attempt_id=attempt_id,
            writer_guard=guard,
            source_record=source_record,
            action_boundary=boundary,
            reservation=reservation,
            authoritative_reread=reread,
            artifacts=artifacts,
            promotion_mode=effective_mode,
            rollback_validation=rollback_validation,
            diagnostics=_freeze_mapping(
                {
                    "reservation_count": reservation.reservation_count,
                    "has_terminal": reservation.has_terminal,
                    "requested_promotion_mode": self._promotion_mode.value,
                    "promotion_mode": effective_mode.value,
                }
            ),
        )

    def start_attempt(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.START,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def complete_attempt(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.COMPLETE,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def fail_attempt(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.FAIL,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def cancel_attempt(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.CANCEL,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def suspend_attempt(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.SUSPEND,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def resume_attempt(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.RESUME,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def schedule_retry(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.RETRY,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def record_effect_intent(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        return self._append_operation(
            operation=RuntimeOperation.EFFECT_INTENT,
            attempt_id=attempt_id,
            event=event,
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
            artifacts=artifacts,
            cursor_key=cursor_key,
        )

    def record_effect_outcome(
        self,
        *,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        artifacts: ImmutableAttemptArtifacts | None = None,
        effect_executor: ExternalEffectExecutor | None = None,
        intent_event: LedgerEvent | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        guard, source_record, boundary, rollback_validation = self._preflight(
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
        )
        intent_reread_verified = False
        if self._promotion_mode == PromotionMode.PROMOTE and intent_event is not None:
            try:
                intent_reread = self._build_authoritative_reread(
                    attempt_id=attempt_id,
                    verify_event=intent_event,
                    cursor_key=cursor_key,
                )
            except AuthoritativeRereadError:
                intent_reread = None
            intent_reread_verified = bool(
                intent_reread is not None and intent_reread.verified_event is not None
            )
        effective_mode, effect_note = self._effective_promotion_mode(
            rollback_validation=rollback_validation,
            require_verified_reread=self._promotion_mode == PromotionMode.PROMOTE,
            reread_verified=intent_reread_verified,
        )
        prepared_event = self._prepare_event(
            event=event,
            operation=RuntimeOperation.EFFECT_OUTCOME,
            source_record=source_record,
            artifacts=artifacts,
            writer_id=writer_id,
            surface_name=surface_name,
            promotion_mode=effective_mode,
        )
        effect_executed = False
        if effect_executor is not None and effective_mode == PromotionMode.PROMOTE:
            effect_executor(
                source_record=source_record,
                artifacts=artifacts or ImmutableAttemptArtifacts(attempt_id=attempt_id),
                intent_event=intent_event,
                outcome_event=prepared_event,
            )
            effect_executed = True
            effect_note = "executed"
        append_result = self._append_event(attempt_id=attempt_id, event=prepared_event)
        reread = self._build_authoritative_reread(
            attempt_id=attempt_id,
            verify_event=append_result.event,
            cursor_key=cursor_key,
        )
        return RuntimeProducerResult(
            operation=RuntimeOperation.EFFECT_OUTCOME,
            attempt_id=attempt_id,
            writer_guard=guard,
            source_record=source_record,
            action_boundary=boundary,
            append_result=append_result,
            authoritative_reread=reread,
            artifacts=artifacts,
            promotion_mode=effective_mode,
            external_effect_executed=effect_executed,
            rollback_validation=rollback_validation,
            diagnostics=_freeze_mapping(
                {
                    "effect_execution": effect_note,
                    "requested_promotion_mode": self._promotion_mode.value,
                    "promotion_mode": effective_mode.value,
                    "intent_reread_verified": intent_reread_verified,
                }
            ),
        )

    def authoritative_reread(
        self,
        *,
        attempt_id: str,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None = None,
        verify_event: LedgerEvent | None = None,
        cursor_key: str = "default",
    ) -> RuntimeProducerResult:
        guard, source_record, boundary, rollback_validation = self._preflight(
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
        )
        reread = self._build_authoritative_reread(
            attempt_id=attempt_id,
            verify_event=verify_event,
            cursor_key=cursor_key,
        )
        effective_mode, _ = self._effective_promotion_mode(
            rollback_validation=rollback_validation
        )
        return RuntimeProducerResult(
            operation=RuntimeOperation.AUTHORITATIVE_REREAD,
            attempt_id=attempt_id,
            writer_guard=guard,
            source_record=source_record,
            action_boundary=boundary,
            authoritative_reread=reread,
            promotion_mode=effective_mode,
            rollback_validation=rollback_validation,
            diagnostics=_freeze_mapping(
                {
                    "event_count": len(reread.events),
                    "requested_promotion_mode": self._promotion_mode.value,
                    "promotion_mode": effective_mode.value,
                }
            ),
        )

    def _append_operation(
        self,
        *,
        operation: RuntimeOperation,
        attempt_id: str,
        event: LedgerEvent,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None,
        artifacts: ImmutableAttemptArtifacts | None,
        cursor_key: str,
    ) -> RuntimeProducerResult:
        guard, source_record, boundary, rollback_validation = self._preflight(
            writer_id=writer_id,
            surface_name=surface_name,
            source_lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
            action_context=action_context,
        )
        effective_mode, _ = self._effective_promotion_mode(
            rollback_validation=rollback_validation
        )
        prepared_event = self._prepare_event(
            event=event,
            operation=operation,
            source_record=source_record,
            artifacts=artifacts,
            writer_id=writer_id,
            surface_name=surface_name,
            promotion_mode=effective_mode,
        )
        append_result = self._append_event(attempt_id=attempt_id, event=prepared_event)
        reread = self._build_authoritative_reread(
            attempt_id=attempt_id,
            verify_event=append_result.event,
            cursor_key=cursor_key,
        )
        return RuntimeProducerResult(
            operation=operation,
            attempt_id=attempt_id,
            writer_guard=guard,
            source_record=source_record,
            action_boundary=boundary,
            append_result=append_result,
            authoritative_reread=reread,
            artifacts=artifacts,
            promotion_mode=effective_mode,
            rollback_validation=rollback_validation,
            diagnostics=_freeze_mapping(
                {
                    "sequence": append_result.sequence,
                    "is_duplicate": append_result.is_duplicate,
                    "requested_promotion_mode": self._promotion_mode.value,
                    "promotion_mode": effective_mode.value,
                }
            ),
        )

    def _preflight(
        self,
        *,
        writer_id: str,
        surface_name: str,
        source_lookup_key: str,
        expected_source_version: str,
        action_context: ActionBoundaryContext | None,
    ) -> tuple[WriteGuardResult, ExactSourceRecord, ActionBoundaryResult | None, RollbackValidation | None]:
        guard = self._writer_guard_fn(writer_id=writer_id, surface_name=surface_name)
        if guard.decision in {WriteGuardDecision.DENIED, WriteGuardDecision.UNREGISTERED}:
            raise WriterGuardError(
                f"writer {writer_id!r} on {surface_name!r} is not authorized: {guard.decision.value}"
            )

        source_record = self._lookup_exact_source(
            lookup_key=source_lookup_key,
            expected_source_version=expected_source_version,
        )
        boundary = None
        if action_context is not None:
            boundary = validate_action_boundary(
                action_context,
                lease_store=self._lease_store,
                outbox=self._outbox,
                enforcement_enabled=self._enforcement_enabled,
            )
            if boundary.gate_result not in {GateResult.AUTHORIZED, GateResult.SHADOW_PASS}:
                raise ActionBoundaryDeniedError(
                    f"{action_context.action_type} blocked by {boundary.gate_result.value}"
                )
        rollback_validation = self._rollback_validator() if self._rollback_validator is not None else None
        return guard, source_record, boundary, rollback_validation

    def _lookup_exact_source(self, *, lookup_key: str, expected_source_version: str) -> ExactSourceRecord:
        record = self._source_lookup(lookup_key)
        if record is None:
            raise ExactSourceLookupError(f"missing exact source record for {lookup_key!r}")
        if record.version != expected_source_version:
            raise ExactSourceLookupError(
                f"exact source lookup mismatch for {lookup_key!r}: expected {expected_source_version!r}, "
                f"observed {record.version!r}"
            )
        return record

    def _prepare_event(
        self,
        *,
        event: LedgerEvent,
        operation: RuntimeOperation,
        source_record: ExactSourceRecord,
        artifacts: ImmutableAttemptArtifacts | None,
        writer_id: str,
        surface_name: str,
        promotion_mode: PromotionMode | None = None,
    ) -> LedgerEvent:
        effective_mode = promotion_mode or self._promotion_mode
        runtime_metadata = {
            "operation": operation.value,
            "writer_id": writer_id,
            "surface_name": surface_name,
            "source_record": source_record.to_dict(),
            "promotion_mode": effective_mode.value,
        }
        if artifacts is not None:
            if artifacts.attempt_id != event.identity.attempt_id:
                raise ValueError(
                    f"artifact attempt {artifacts.attempt_id!r} does not match event attempt "
                    f"{event.identity.attempt_id!r}"
                )
            runtime_metadata["artifacts"] = artifacts.to_dict()
        payload = event.payload
        if payload is None:
            payload = {"__wbc_runtime__": runtime_metadata}
        elif isinstance(payload, Mapping):
            merged = dict(payload)
            merged["__wbc_runtime__"] = runtime_metadata
            payload = merged
        return replace(event, payload=payload)

    def _append_event(self, *, attempt_id: str, event: LedgerEvent) -> AppendResult:
        if event.identity.attempt_id != attempt_id:
            raise ValueError(
                f"event.identity.attempt_id {event.identity.attempt_id!r} does not match attempt_id {attempt_id!r}"
            )
        if event.event_type.value == "started":
            return self._ledger_store.append_started(attempt_id, event)
        if event.event_type.value == "completed":
            return self._ledger_store.append_completed(attempt_id, event)
        if event.event_type.value == "failed":
            return self._ledger_store.append_failed(attempt_id, event)
        if event.event_type.value == "cancelled":
            return self._ledger_store.append_cancelled(attempt_id, event)
        return self._ledger_store.append_event(attempt_id, event)

    def _build_authoritative_reread(
        self,
        *,
        attempt_id: str,
        verify_event: LedgerEvent | None = None,
        cursor_key: str = "default",
    ) -> AuthoritativeRereadResult:
        ledger = self._ledger_store.read_ledger(attempt_id)
        events = tuple(self._ledger_store.read_events(attempt_id))
        verified_event = None
        started_gate = None
        terminal_gate = None
        if verify_event is not None:
            verified_event = next(
                (
                    event
                    for event in events
                    if event.sequence == verify_event.sequence and event.idempotency_key == verify_event.idempotency_key
                ),
                None,
            )
            if verified_event is None:
                raise AuthoritativeRereadError(
                    f"authoritative reread did not return sequence {verify_event.sequence} for {attempt_id!r}"
                )
            if verify_event.event_type.value == "started":
                started_gate = self._ledger_store.start_verified(attempt_id)
                if started_gate.status != GateStatus.VERIFIED:
                    raise AuthoritativeRereadError(
                        f"start verification for {attempt_id!r} returned {started_gate.status.value}"
                    )
            if verify_event.is_terminal:
                terminal_gate = self._ledger_store.terminal_or_indeterminate_verified(attempt_id)
                if terminal_gate.status != GateStatus.VERIFIED:
                    raise AuthoritativeRereadError(
                        f"terminal verification for {attempt_id!r} returned {terminal_gate.status.value}"
                    )
        source_cursor = self._ledger_store.query_source_cursor(attempt_id, cursor_key=cursor_key)
        return AuthoritativeRereadResult(
            attempt_id=attempt_id,
            ledger=ledger,
            events=events,
            verified_event=verified_event,
            started_gate=started_gate,
            terminal_gate=terminal_gate,
            source_cursor=source_cursor,
        )

    def _effective_promotion_mode(
        self,
        *,
        rollback_validation: RollbackValidation | None,
        require_verified_reread: bool = False,
        reread_verified: bool = False,
    ) -> tuple[PromotionMode, str]:
        if self._promotion_mode != PromotionMode.PROMOTE:
            return self._promotion_mode, "suppressed by action-off/observe mode"
        if rollback_validation is not None and (
            not rollback_validation.adopter_promotion_enabled
            or not rollback_validation.real_effects_enabled
        ):
            return PromotionMode.ACTION_OFF, rollback_validation.reason
        if require_verified_reread and not reread_verified:
            return (
                PromotionMode.ACTION_OFF,
                "suppressed by rollback enforcement: missing authoritative reread",
            )
        return PromotionMode.PROMOTE, "executed"


__all__ = [
    "ActionBoundaryDeniedError",
    "AttemptArtifact",
    "AuthoritativeRereadError",
    "AuthoritativeRereadResult",
    "ExactSourceLookup",
    "ExactSourceLookupError",
    "ExactSourceRecord",
    "ExternalEffectExecutor",
    "ImmutableAttemptArtifacts",
    "PromotionMode",
    "RuntimeFacadeError",
    "RuntimeOperation",
    "RuntimeProducerResult",
    "WbcRuntimeProducerFacade",
    "WriterGuardError",
]
