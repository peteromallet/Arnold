"""Agent runner protocols for resident turns."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Mapping, Protocol

from pydantic import BaseModel, ValidationError

from .config import ResidentConfig
from .tool_schemas import ToolCallAuditRecord, ToolResult
from .tool_registry import ToolRegistry


@dataclass(frozen=True)
class AgentRequest:
    conversation_id: str
    messages: tuple[dict[str, Any], ...]
    system_prompt: str
    hot_context: dict[str, Any] = field(default_factory=dict)
    model_seam_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResponse:
    final_text: str
    tool_calls: tuple[ToolCallAuditRecord, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class DispatchProtocol(Protocol):
    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        """Dispatch one resident bot turn through the resident model/tool loop."""


class AgentRunner(DispatchProtocol, Protocol):
    """Resident runner alias for the shared dispatch-shaped Protocol."""


@dataclass(frozen=True)
class FakeToolCall:
    """Scripted fake-model tool request used by tests and local dry runs."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FakeAgentStep:
    """One fake-model step: either call a tool or return final text."""

    tool_call: FakeToolCall | None = None
    final_text: str | None = None

    @classmethod
    def call(cls, tool_name: str, arguments: dict[str, Any] | None = None) -> "FakeAgentStep":
        return cls(tool_call=FakeToolCall(tool_name=tool_name, arguments=dict(arguments or {})))

    @classmethod
    def final(cls, text: str) -> "FakeAgentStep":
        return cls(final_text=text)


class AgentLoopError(RuntimeError):
    """Deterministic resident agent-loop failure."""


class FakeAgentRunner:
    """Deterministic runner that exercises the resident tool-call loop."""

    def __init__(
        self,
        steps: list[FakeAgentStep] | tuple[FakeAgentStep, ...],
        *,
        max_tool_calls: int = 8,
        tool_timeout_s: float = 30.0,
    ) -> None:
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if tool_timeout_s <= 0:
            raise ValueError("tool_timeout_s must be positive")
        self.steps = tuple(steps)
        self.max_tool_calls = max_tool_calls
        self.tool_timeout_s = tool_timeout_s

    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        del request
        audit_records: list[ToolCallAuditRecord] = []
        tool_call_count = 0

        for step_index, step in enumerate(self.steps, start=1):
            if step.final_text is not None:
                return AgentResponse(
                    final_text=step.final_text,
                    tool_calls=tuple(audit_records),
                    metadata={"steps_executed": step_index, "tool_calls_executed": tool_call_count},
                )
            if step.tool_call is None:
                raise AgentLoopError(f"fake agent step {step_index} has neither final_text nor tool_call")

            if tool_call_count >= self.max_tool_calls:
                raise AgentLoopError(f"resident tool-call limit exceeded: {self.max_tool_calls}")
            tool_call_count += 1
            audit_records.append(await self._execute_tool_call(step.tool_call, tools, tool_call_count))

        raise AgentLoopError("fake agent script ended without final_text")

    async def _execute_tool_call(
        self,
        call: FakeToolCall,
        tools: ToolRegistry,
        sequence: int,
    ) -> ToolCallAuditRecord:
        start = perf_counter()
        arguments = dict(call.arguments)
        tool_name = call.tool_name
        operation_kind = "read"
        try:
            registration = tools.get(call.tool_name)
            tool_name = registration.name
            operation_kind = registration.operation_kind
            tool_input = registration.input_model.model_validate(arguments)
            raw_result = await asyncio.wait_for(
                _await_maybe(registration.handler(tool_input)),
                timeout=self.tool_timeout_s,
            )
            result_model = _coerce_tool_result(registration.output_model, raw_result)
            result_payload = result_model.model_dump(mode="json")
        except asyncio.TimeoutError:
            result_payload = {
                "ok": False,
                "message": f"tool timed out after {self.tool_timeout_s:g}s",
                "data": {"error": "timeout"},
            }
        except (ValidationError, Exception) as exc:
            result_payload = {
                "ok": False,
                "message": str(exc),
                "data": {"error": exc.__class__.__name__},
            }
        duration_ms = max(0, int((perf_counter() - start) * 1000))
        return ToolCallAuditRecord(
            id=f"fake_tool_{sequence:04d}",
            tool_name=tool_name,
            operation_kind=operation_kind,
            arguments=arguments,
            result=result_payload,
            duration_ms=duration_ms,
        )


class OpenAICompatibleAgentRunner(DispatchProtocol):
    """OpenAI-compatible chat/tool-call runner for live resident operation."""

    def __init__(
        self,
        config: ResidentConfig,
        *,
        max_tool_calls: int | None = None,
        tool_timeout_s: float | None = None,
    ) -> None:
        self.config = config
        self.max_tool_calls = max_tool_calls or config.max_tool_calls_per_turn
        self.tool_timeout_s = tool_timeout_s or config.model_timeout_s
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if self.tool_timeout_s <= 0:
            raise ValueError("tool_timeout_s must be positive")

    async def run(self, request: AgentRequest, tools: ToolRegistry) -> AgentResponse:
        client = _openai_client(self.config)
        messages = self._messages(request)
        openai_tools = [_openai_tool_schema(tool) for tool in tools.list()]
        audit_records: list[ToolCallAuditRecord] = []

        for step_index in range(1, self.max_tool_calls + 2):
            model_name = _request_model_name(request, self.config.model_name)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=openai_tools or None,
                    tool_choice="auto" if openai_tools else None,
                    timeout=self.config.model_timeout_s,
                ),
                timeout=self.config.model_timeout_s,
            )
            message = response.choices[0].message
            tool_calls = tuple(message.tool_calls or ())
            if not tool_calls:
                final_text = _message_content_text(message.content)
                return AgentResponse(
                    final_text=final_text,
                    tool_calls=tuple(audit_records),
                    metadata={"steps_executed": step_index, "tool_calls_executed": len(audit_records), "model": model_name},
                )
            if len(audit_records) + len(tool_calls) > self.max_tool_calls:
                raise AgentLoopError(f"resident tool-call limit exceeded: {self.max_tool_calls}")
            messages.append(_assistant_tool_call_message(message))
            for tool_call in tool_calls:
                arguments = _tool_call_arguments(tool_call)
                audit = await _execute_registered_tool(
                    tools=tools,
                    tool_name=tool_call.function.name,
                    arguments=arguments,
                    audit_id=tool_call.id,
                    timeout_s=self.tool_timeout_s,
                )
                audit_records.append(audit)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(audit.result, sort_keys=True),
                    }
                )
        raise AgentLoopError("resident model loop ended without final_text")

    def _messages(self, request: AgentRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system_prompt}]
        if request.hot_context:
            messages.append(
                {
                    "role": "system",
                    "content": "Hot context JSON:\n" + json.dumps(request.hot_context, sort_keys=True, default=str),
                }
            )
        for message in request.messages:
            role = message.get("role")
            content = message.get("content")
            if role in {"user", "assistant", "system"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        return messages


async def _await_maybe(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


def _coerce_tool_result(output_model: type[BaseModel], value: Any) -> BaseModel:
    if isinstance(value, output_model):
        return value
    if isinstance(value, ToolResult) and output_model is not ToolResult:
        return output_model.model_validate(value.model_dump(mode="python"))
    if isinstance(value, BaseModel):
        return output_model.model_validate(value.model_dump(mode="python"))
    return output_model.model_validate(value)


def _request_model_name(request: AgentRequest, default: str) -> str:
    model_name = request.model_seam_metadata.get("normalized_model")
    return str(model_name) if model_name else default


async def _execute_registered_tool(
    *,
    tools: ToolRegistry,
    tool_name: str,
    arguments: dict[str, Any],
    audit_id: str,
    timeout_s: float,
) -> ToolCallAuditRecord:
    start = perf_counter()
    operation_kind = "read"
    try:
        registration = tools.get(tool_name)
        tool_name = registration.name
        operation_kind = registration.operation_kind
        tool_input = registration.input_model.model_validate(arguments)
        raw_result = await asyncio.wait_for(
            _await_maybe(registration.handler(tool_input)),
            timeout=timeout_s,
        )
        result_model = _coerce_tool_result(registration.output_model, raw_result)
        result_payload = result_model.model_dump(mode="json")
    except asyncio.TimeoutError:
        result_payload = {
            "ok": False,
            "message": f"tool timed out after {timeout_s:g}s",
            "data": {"error": "timeout"},
        }
    except (ValidationError, Exception) as exc:
        result_payload = {
            "ok": False,
            "message": str(exc),
            "data": {"error": exc.__class__.__name__},
        }
    duration_ms = max(0, int((perf_counter() - start) * 1000))
    return ToolCallAuditRecord(
        id=audit_id,
        tool_name=tool_name,
        operation_kind=operation_kind,
        arguments=arguments,
        result=result_payload,
        duration_ms=duration_ms,
    )


def _openai_client(config: ResidentConfig) -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise AgentLoopError("The openai package is required for live resident model turns") from exc
    kwargs: dict[str, Any] = {"api_key": _api_key(config)}
    base_url = _base_url(config)
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncOpenAI(**kwargs)


def _api_key(config: ResidentConfig) -> str:
    env_name = config.model_api_key_env or _default_api_key_env(config.model_provider)
    value = os.getenv(env_name)
    if not value:
        raise AgentLoopError(f"{env_name} is required for live resident model turns")
    return value


def _default_api_key_env(provider: str) -> str:
    return "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"


def _base_url(config: ResidentConfig) -> str | None:
    if config.model_base_url:
        return config.model_base_url
    if config.model_provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    return None


def _openai_tool_schema(registration: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": registration.name,
            "description": registration.description,
            "parameters": registration.input_model.model_json_schema(),
        },
    }


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, list):
        return "\n".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _assistant_tool_call_message(message: Any) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": _message_content_text(message.content) or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in (message.tool_calls or ())
        ],
    }


def _tool_call_arguments(tool_call: Any) -> dict[str, Any]:
    raw = tool_call.function.arguments or "{}"
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise AgentLoopError(f"tool call {tool_call.id} arguments must be a JSON object")
    return parsed
