from __future__ import annotations

import base64
from types import SimpleNamespace

from agent_kit.openai_ops import IMAGE_MODEL, SECOND_OPINION_MODEL, OpenAIAdapter


class FakeImages:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="img_req_1",
            data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(b"png bytes").decode("ascii"),
                )
            ],
        )


class FakeResponses:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id="resp_req_1", output_text='{"score":7}')


class FakeClient:
    def __init__(self) -> None:
        self.images = FakeImages()
        self.responses = FakeResponses()


def test_openai_adapter_generates_image_with_idempotency_key() -> None:
    client = FakeClient()
    adapter = OpenAIAdapter(client=client)

    result = adapter.generate_image(
        prompt="draw the flow",
        quality="medium",
        size="1024x1024",
        idempotency_key="idem_1",
    )

    assert result.content == b"png bytes"
    assert result.mime_type == "image/png"
    assert result.provider_request_id == "img_req_1"
    assert result.response_summary == {
        "model": IMAGE_MODEL,
        "quality": "medium",
        "size": "1024x1024",
        "byte_count": len(b"png bytes"),
    }
    assert client.images.calls == [
        {
            "model": IMAGE_MODEL,
            "prompt": "draw the flow",
            "quality": "medium",
            "size": "1024x1024",
            "n": 1,
            "extra_headers": {"Idempotency-Key": "idem_1"},
        }
    ]


def test_openai_adapter_requests_second_opinion_with_payload_input() -> None:
    client = FakeClient()
    adapter = OpenAIAdapter(client=client)

    result = adapter.request_second_opinion(
        payload={"input": [{"role": "user", "content": "audit"}]},
        idempotency_key="idem_2",
    )

    assert result.raw_response == '{"score":7}'
    assert result.provider_request_id == "resp_req_1"
    assert result.response_summary == {
        "model": SECOND_OPINION_MODEL,
        "output_length": len('{"score":7}'),
    }
    assert client.responses.calls == [
        {
            "model": SECOND_OPINION_MODEL,
            "input": [{"role": "user", "content": "audit"}],
            "extra_headers": {"Idempotency-Key": "idem_2"},
        }
    ]
