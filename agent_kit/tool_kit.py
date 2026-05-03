"""Tool registry and audited invocation wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Callable, Literal

from agent_kit.code_redaction import redact_code_secrets
from agent_kit.envelope import Event
from agent_kit.ledger import Ledger
from agent_kit.ports import Blob, OpenAIOps, ProviderError, PushTransport, Store


EventKind = Literal["tool_call", "activity", "attached_image"]
OperationKind = Literal["read", "write"]
JSONDict = dict[str, Any]
ToolCallable = Callable[..., Any]
ExternalCallable = Callable[[], tuple[str | None, JSONDict | None]]
SyncExternalCallable = Callable[[str], tuple[str | None, JSONDict | None, Any]]


@dataclass(frozen=True)
class ExternalSpec:
    provider: str
    endpoint: str
    request_summary: JSONDict
    request_body: JSONDict | None = None


@dataclass(frozen=True)
class ToolEntry:
    name: str
    func: ToolCallable
    schema: JSONDict
    event_kind: EventKind = "tool_call"
    operation_kind: OperationKind = "write"


@dataclass
class ToolContext:
    store: Store
    turn_id: str
    events: list[Event]
    on_event: Callable[[Event], None] | None = None
    reply_buffer: list[str] = field(default_factory=list)
    metadata: JSONDict = field(default_factory=dict)
    transport: PushTransport | None = None
    blob: Blob | None = None
    openai_ops: OpenAIOps | None = None
    external_queue: list[tuple[ExternalSpec, ExternalCallable]] | None = None


@dataclass(frozen=True)
class SyncExternalResult:
    request_id: str
    idempotency_key: str
    provider_request_id: str | None
    response_summary: JSONDict | None
    result: Any


@dataclass(frozen=True)
class ToolInvocation:
    result: JSONDict
    tool_call: JSONDict
    event: Event


class ToolRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        func: ToolCallable,
        schema: JSONDict,
        *,
        event_kind: EventKind = "tool_call",
        operation_kind: OperationKind = "write",
    ) -> ToolEntry:
        entry = ToolEntry(
            name=name,
            func=func,
            schema=schema,
            event_kind=event_kind,
            operation_kind=operation_kind,
        )
        self._entries[name] = entry
        return entry

    def tool(
        self,
        name: str | None = None,
        *,
        schema: JSONDict | None = None,
        event_kind: EventKind = "tool_call",
        operation_kind: OperationKind = "write",
    ) -> Callable[[ToolCallable], ToolCallable]:
        def decorator(func: ToolCallable) -> ToolCallable:
            self.register(
                name or func.__name__,
                func,
                schema or {},
                event_kind=event_kind,
                operation_kind=operation_kind,
            )
            return func

        return decorator

    def get(self, name: str) -> ToolEntry:
        return self._entries[name]

    def definitions(self) -> list[JSONDict]:
        return [
            {"name": entry.name, "schema": entry.schema}
            for entry in self._entries.values()
        ]

    def invoke(
        self,
        name: str,
        context: ToolContext,
        arguments: JSONDict | None = None,
    ) -> ToolInvocation:
        return audit_wrap(self.get(name))(context, arguments or {})


def audit_wrap(entry: ToolEntry) -> Callable[[ToolContext, JSONDict], ToolInvocation]:
    def invoke(context: ToolContext, arguments: JSONDict) -> ToolInvocation:
        started = perf_counter()
        context.external_queue = []
        queued_requests: list[tuple[ExternalSpec, ExternalCallable, str]] = []
        ledger = Ledger(context.store)
        # Keep tool writes and audit rows atomic; only provider IO runs post-commit.
        try:
            with context.store.transaction():
                raw_result = entry.func(context, **arguments)
                duration_ms = max(0, round((perf_counter() - started) * 1000))
                arguments_for_audit = redact_code_secrets(arguments)
                result = redact_code_secrets(_normalize_result(raw_result))
                tool_call = context.store.record_tool_call(
                    turn_id=context.turn_id,
                    tool_name=entry.name,
                    operation_kind=entry.operation_kind,
                    arguments=arguments_for_audit,
                    result=result,
                    duration_ms=duration_ms,
                )
                event = _event_from_tool_call(
                    entry=entry,
                    arguments=arguments_for_audit,
                    result=result,
                    tool_call=tool_call,
                    duration_ms=duration_ms,
                )
                invocation = ToolInvocation(
                    result=result,
                    tool_call=tool_call,
                    event=event,
                )
                for spec, external_callable in context.external_queue:
                    request_id, _idempotency_key = ledger.record_pending(
                        provider=spec.provider,
                        endpoint=spec.endpoint,
                        request_summary=redact_code_secrets(spec.request_summary),
                        request_body=redact_code_secrets(spec.request_body),
                        turn_id=context.turn_id,
                        tool_call_id=tool_call["id"],
                    )
                    queued_requests.append((spec, external_callable, request_id))
        except Exception:
            _restore_sync_external_settlements(context)
            raise
        context.metadata.pop("_sync_external_settlements", None)
        for _spec, external_callable, request_id in queued_requests:
            try:
                provider_request_id, response_summary = external_callable()
            except Exception as exc:
                ledger.mark_failed(
                    request_id,
                    {
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                raise
            ledger.mark_confirmed(
                request_id,
                provider_request_id,
                response_summary,
            )
        _emit_event(context, invocation.event)
        _emit_pending_attached_image_events(context)
        return invocation

    return invoke


def run_synchronous_external_effect(
    context: ToolContext,
    spec: ExternalSpec,
    effect: SyncExternalCallable,
) -> SyncExternalResult:
    """Record, execute, and settle a result-dependent provider effect."""

    ledger = Ledger(context.store)
    seq = int(context.metadata.get("_sync_external_seq", 0)) + 1
    context.metadata["_sync_external_seq"] = seq
    request_id, idempotency_key = ledger.record_pending(
        provider=spec.provider,
        endpoint=spec.endpoint,
        request_summary=redact_code_secrets(spec.request_summary),
        request_body=redact_code_secrets(spec.request_body),
        turn_id=context.turn_id,
        system_seq=seq,
    )
    try:
        provider_request_id, response_summary, result = effect(idempotency_key)
    except ProviderError as exc:
        ledger.mark_failed(request_id, exc.error_details)
        _remember_sync_external_settlement(
            context,
            spec,
            idempotency_key,
            "failed",
            None,
            None,
            exc.error_details,
        )
        raise
    except Exception as exc:
        error_details = {
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        ledger.mark_failed(request_id, error_details)
        _remember_sync_external_settlement(
            context,
            spec,
            idempotency_key,
            "failed",
            None,
            None,
            error_details,
        )
        raise
    ledger.mark_confirmed(request_id, provider_request_id, response_summary)
    _remember_sync_external_settlement(
        context,
        spec,
        idempotency_key,
        "confirmed",
        provider_request_id,
        response_summary,
        None,
    )
    return SyncExternalResult(
        request_id=request_id,
        idempotency_key=idempotency_key,
        provider_request_id=provider_request_id,
        response_summary=response_summary,
        result=result,
    )


def _remember_sync_external_settlement(
    context: ToolContext,
    spec: ExternalSpec,
    idempotency_key: str,
    status: str,
    provider_request_id: str | None,
    response_summary: JSONDict | None,
    error_details: JSONDict | None,
) -> None:
    settlements = context.metadata.setdefault("_sync_external_settlements", [])
    if isinstance(settlements, list):
        settlements.append(
            {
                "spec": spec,
                "idempotency_key": idempotency_key,
                "status": status,
                "provider_request_id": provider_request_id,
                "response_summary": response_summary,
                "error_details": error_details,
            }
        )


def _restore_sync_external_settlements(context: ToolContext) -> None:
    settlements = context.metadata.pop("_sync_external_settlements", [])
    if not isinstance(settlements, list):
        return
    for settlement in settlements:
        spec = settlement.get("spec")
        idempotency_key = settlement.get("idempotency_key")
        if not isinstance(spec, ExternalSpec) or not isinstance(idempotency_key, str):
            continue
        try:
            row = context.store.insert_pending(
                idempotency_key=idempotency_key,
                provider=spec.provider,
                endpoint=spec.endpoint,
                request_summary=spec.request_summary,
                request_body=spec.request_body,
                turn_id=context.turn_id,
            )
        except Exception:
            continue
        if settlement.get("status") == "confirmed":
            context.store.mark_confirmed(
                row["id"],
                provider_request_id=settlement.get("provider_request_id"),
                provider_response_summary=settlement.get("response_summary"),
            )
        elif settlement.get("status") == "failed":
            context.store.mark_failed(
                row["id"],
                error_details=settlement.get("error_details") or {},
            )


registry = ToolRegistry()


def register_tool(
    name: str | None = None,
    *,
    schema: JSONDict | None = None,
    event_kind: EventKind = "tool_call",
    operation_kind: OperationKind = "write",
) -> Callable[[ToolCallable], ToolCallable]:
    return registry.tool(
        name,
        schema=schema,
        event_kind=event_kind,
        operation_kind=operation_kind,
    )


def _event_from_tool_call(
    *,
    entry: ToolEntry,
    arguments: JSONDict,
    result: JSONDict,
    tool_call: JSONDict,
    duration_ms: int,
) -> Event:
    text = None
    if entry.event_kind == "activity":
        text = _first_string(
            result.get("description"),
            result.get("text"),
            arguments.get("description"),
            arguments.get("text"),
        )
    return Event(
        ts=_now(),
        kind=entry.event_kind,
        name=entry.name,
        text=text,
        ms=duration_ms,
        tool_call_id=tool_call["id"],
    )


def _emit_event(context: ToolContext, event: Event) -> None:
    context.events.append(event)
    if context.on_event is not None:
        context.on_event(event)


def _emit_pending_attached_image_events(context: ToolContext) -> None:
    pending = context.metadata.pop("_pending_attached_image_events", [])
    if not isinstance(pending, list):
        return
    for details in pending:
        if not isinstance(details, dict):
            continue
        _emit_event(
            context,
            Event(
                ts=_now(),
                kind="attached_image",
                name="send_image",
                details=details,
            ),
        )


def _normalize_result(value: Any) -> JSONDict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return {"value": value}


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            return value
    return None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


__all__ = [
    "ToolContext",
    "ToolEntry",
    "ToolInvocation",
    "ToolRegistry",
    "ExternalSpec",
    "SyncExternalResult",
    "audit_wrap",
    "register_tool",
    "run_synchronous_external_effect",
    "registry",
]
