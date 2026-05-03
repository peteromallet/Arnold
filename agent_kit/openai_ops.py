"""OpenAI adapter for generated images and second opinions."""

from __future__ import annotations

import base64
import json
from typing import Any

from agent_kit.ports import JSONDict, OpenAIImageResult, OpenAISecondOpinionResult


IMAGE_MODEL = "gpt-image-2"
SECOND_OPINION_MODEL = "gpt-5.5"


class OpenAIAdapter:
    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI()
        self._client = client

    def generate_image(
        self,
        *,
        prompt: str,
        quality: str,
        size: str,
        idempotency_key: str,
    ) -> OpenAIImageResult:
        response = self._client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            quality=quality,
            size=size,
            n=1,
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        first = (_get(response, "data") or [None])[0]
        b64_json = _get(first, "b64_json")
        if not isinstance(b64_json, str) or not b64_json:
            raise RuntimeError("OpenAI image response did not include b64_json")
        content = base64.b64decode(b64_json)
        return OpenAIImageResult(
            content=content,
            mime_type="image/png",
            provider_request_id=_as_optional_string(_get(response, "id")),
            response_summary={
                "model": IMAGE_MODEL,
                "quality": quality,
                "size": size,
                "byte_count": len(content),
            },
        )

    def request_second_opinion(
        self,
        *,
        payload: JSONDict,
        idempotency_key: str,
    ) -> OpenAISecondOpinionResult:
        response = self._client.responses.create(
            model=SECOND_OPINION_MODEL,
            input=_second_opinion_input(payload),
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        raw_response = _response_output_text(response)
        if not raw_response:
            raise RuntimeError("OpenAI second-opinion response did not include text")
        return OpenAISecondOpinionResult(
            raw_response=raw_response,
            provider_request_id=_as_optional_string(_get(response, "id")),
            response_summary={
                "model": SECOND_OPINION_MODEL,
                "output_length": len(raw_response),
            },
        )


def _second_opinion_input(payload: JSONDict) -> Any:
    if "input" in payload:
        return payload["input"]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _response_output_text(response: Any) -> str:
    output_text = _get(response, "output_text")
    if isinstance(output_text, str):
        return output_text
    texts: list[str] = []
    for item in _get(response, "output") or []:
        for content in _get(item, "content") or []:
            text = _get(content, "text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts)


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _as_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = ["IMAGE_MODEL", "SECOND_OPINION_MODEL", "OpenAIAdapter"]
