"""Deterministic fake model adapter for offline tests."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable, Sequence

from agent_kit.ports import (
    JSONDict,
    ModelTurnResult,
    ProviderError,
    ToolRequest,
)


ScriptItem = ModelTurnResult | JSONDict | BaseException


@dataclass(frozen=True)
class FakeModelStep:
    final_text: str | None = None
    tool_requests: tuple[ToolRequest, ...] = ()
    reasoning: str | None = None
    provider_request_id: str | None = None
    response_summary: JSONDict | None = None

    def to_result(self) -> ModelTurnResult:
        return ModelTurnResult(
            final_text=self.final_text,
            tool_requests=list(self.tool_requests),
            reasoning=self.reasoning,
            provider_request_id=self.provider_request_id,
            response_summary=self.response_summary,
        )


class FakeModel:
    def __init__(
        self,
        *,
        seed: int | str = 0,
        script: Iterable[ScriptItem] | None = None,
    ) -> None:
        self.seed = seed
        self._random = random.Random(str(seed))
        self._script = list(script) if script is not None else None
        self.calls: list[JSONDict] = []
        self.call_count = 0

    def complete_turn(
        self,
        *,
        model_id: str,
        messages: Sequence[JSONDict],
        tools: Sequence[JSONDict],
        hot_context: JSONDict,
        idempotency_key: str | None = None,
    ) -> ModelTurnResult:
        self.call_count += 1
        self.calls.append(
            {
                "model_id": model_id,
                "messages": list(messages),
                "tools": list(tools),
                "hot_context": hot_context,
                "idempotency_key": idempotency_key,
            }
        )
        if self._script is None:
            return ModelTurnResult(
                final_text=f"fake reply {self._random.randint(1000, 9999)}",
                reasoning="fake deterministic final response",
                provider_request_id=f"fake_req_{self.call_count}",
                response_summary={"kind": "final"},
            )
        if self.call_count > len(self._script):
            return ModelTurnResult(
                final_text="",
                reasoning="fake script exhausted",
                provider_request_id=f"fake_req_{self.call_count}",
                response_summary={"kind": "exhausted"},
            )
        return _coerce_script_item(
            self._script[self.call_count - 1],
            call_count=self.call_count,
        )


def tool_request(name: str, arguments: JSONDict | None = None) -> ToolRequest:
    return ToolRequest(name=name, arguments=arguments or {})


def provider_error(
    error_details: JSONDict | None = None,
    provider_request_id: str | None = None,
) -> ProviderError:
    return ProviderError(
        error_details=error_details or {"code": "fake_provider_error"},
        provider_request_id=provider_request_id,
    )


def _coerce_script_item(item: ScriptItem, *, call_count: int) -> ModelTurnResult:
    if isinstance(item, BaseException):
        raise item
    if isinstance(item, ModelTurnResult):
        return item
    if isinstance(item, FakeModelStep):
        return item.to_result()
    if isinstance(item, dict):
        if "exception" in item:
            exception = item["exception"]
            if isinstance(exception, BaseException):
                raise exception
            raise RuntimeError(str(exception))
        if item.get("provider_error"):
            raise provider_error(
                item.get("error_details"),
                item.get("provider_request_id"),
            )
        if item.get("runtime_error"):
            raise RuntimeError(str(item.get("runtime_error")))
        return ModelTurnResult(
            final_text=item.get("final_text"),
            tool_requests=[
                _coerce_tool_request(tool)
                for tool in item.get("tool_requests", [])
            ],
            reasoning=item.get("reasoning"),
            provider_request_id=item.get(
                "provider_request_id",
                f"fake_req_{call_count}",
            ),
            response_summary=item.get("response_summary"),
        )
    raise TypeError(f"Unsupported fake model script item: {type(item)!r}")


def _coerce_tool_request(value: Any) -> ToolRequest:
    if isinstance(value, ToolRequest):
        return value
    if isinstance(value, dict):
        return ToolRequest(
            name=value["name"],
            arguments=value.get("arguments", {}),
        )
    raise TypeError(f"Unsupported tool request: {type(value)!r}")


__all__ = [
    "FakeModel",
    "FakeModelStep",
    "provider_error",
    "tool_request",
]
