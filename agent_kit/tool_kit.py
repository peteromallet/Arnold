"""Tool registry and audited invocation wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Callable, Literal

from agent_kit.envelope import Event
from agent_kit.ledger import Ledger
from agent_kit.ports import Blob, PushTransport, Store


EventKind = Literal["tool_call", "activity"]
OperationKind = Literal["read", "write"]
JSONDict = dict[str, Any]
ToolCallable = Callable[..., Any]
ExternalCallable = Callable[[], tuple[str | None, JSONDict | None]]


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
    external_queue: list[tuple[ExternalSpec, ExternalCallable]] | None = None


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
        with context.store.transaction():
            raw_result = entry.func(context, **arguments)
            duration_ms = max(0, round((perf_counter() - started) * 1000))
            result = _normalize_result(raw_result)
            tool_call = context.store.record_tool_call(
                turn_id=context.turn_id,
                tool_name=entry.name,
                operation_kind=entry.operation_kind,
                arguments=arguments,
                result=result,
                duration_ms=duration_ms,
            )
            event = _event_from_tool_call(
                entry=entry,
                arguments=arguments,
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
                    request_summary=spec.request_summary,
                    request_body=spec.request_body,
                    turn_id=context.turn_id,
                    tool_call_id=tool_call["id"],
                )
                queued_requests.append((spec, external_callable, request_id))
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
        context.events.append(invocation.event)
        if context.on_event is not None:
            context.on_event(invocation.event)
        return invocation

    return invoke


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
    "audit_wrap",
    "register_tool",
    "registry",
]
