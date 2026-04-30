"""Anthropic model adapter."""

from __future__ import annotations

from typing import Any, Sequence

from agent_kit.ports import (
    JSONDict,
    ModelTurnResult,
    ProviderError,
    ToolRequest,
)


class AnthropicModel:
    def __init__(self, model_id: str = "claude-opus-4-7", client: Any = None):
        self.model_id = model_id
        self._client = client

    def complete_turn(
        self,
        *,
        model_id: str,
        messages: Sequence[JSONDict],
        tools: Sequence[JSONDict],
        hot_context: JSONDict,
        idempotency_key: str | None = None,
    ) -> ModelTurnResult:
        selected_model_id = model_id or self.model_id
        client = self._client or _make_client()
        request_summary = {
            "model": selected_model_id,
            "message_count": len(messages),
            "tool_names": [tool.get("name") for tool in tools],
            "hot_context_keys": sorted(hot_context.keys()),
        }
        try:
            create_kwargs = {
                "model": selected_model_id,
                "max_tokens": 4096,
                "messages": list(messages),
                "tools": _anthropic_tools(tools),
            }
            if idempotency_key is not None:
                create_kwargs["extra_headers"] = {
                    "Idempotency-Key": idempotency_key,
                }
            response = client.messages.create(**create_kwargs)
        except Exception as exc:
            provider_error = _extract_provider_error(exc)
            if provider_error is not None:
                raise ProviderError(
                    error_details=provider_error["error_details"],
                    provider_request_id=provider_error.get("provider_request_id"),
                ) from exc
            raise

        text_parts: list[str] = []
        tool_requests: list[ToolRequest] = []
        for block in getattr(response, "content", []) or []:
            block_type = _get(block, "type")
            if block_type == "text":
                text_parts.append(_get(block, "text") or "")
            elif block_type == "tool_use":
                tool_requests.append(
                    ToolRequest(
                        name=_get(block, "name"),
                        arguments=_get(block, "input") or {},
                    )
                )
        final_text = "\n".join(part for part in text_parts if part).strip() or None
        response_summary = {
            "id": getattr(response, "id", None),
            "model": getattr(response, "model", selected_model_id),
            "stop_reason": getattr(response, "stop_reason", None),
            "tool_request_count": len(tool_requests),
            "text_present": final_text is not None,
        }
        return ModelTurnResult(
            final_text=final_text,
            tool_requests=tool_requests,
            reasoning=_summarize_reasoning(final_text, tool_requests),
            provider_request_id=getattr(response, "id", None),
            response_summary={
                "request": request_summary,
                "response": response_summary,
            },
        )


def _make_client() -> Any:
    import anthropic

    return anthropic.Anthropic()


def _anthropic_tools(tools: Sequence[JSONDict]) -> list[JSONDict]:
    definitions = []
    for tool in tools:
        schema = tool.get("input_schema") or tool.get("schema") or {}
        definitions.append(
            {
                "name": tool["name"],
                "input_schema": schema,
            }
        )
    return definitions


def _extract_provider_error(exc: Exception) -> JSONDict | None:
    provider_request_id = getattr(exc, "request_id", None)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return {
            "error_details": body,
            "provider_request_id": provider_request_id,
        }
    response = getattr(exc, "response", None)
    if response is not None:
        provider_request_id = provider_request_id or getattr(
            response,
            "headers",
            {},
        ).get("request-id")
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            return {
                "error_details": payload,
                "provider_request_id": provider_request_id,
            }
    return None


def _summarize_reasoning(
    final_text: str | None,
    tool_requests: Sequence[ToolRequest],
) -> str:
    if tool_requests:
        names = ", ".join(request.name for request in tool_requests)
        return f"requested tools: {names}"
    if final_text:
        return "returned final text"
    return "empty model response"


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


__all__ = ["AnthropicModel"]
