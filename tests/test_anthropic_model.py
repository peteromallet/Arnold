from __future__ import annotations

from agent_kit.model.anthropic import AnthropicModel


class _Messages:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type(
            "Response",
            (),
            {
                "id": "req_1",
                "model": kwargs["model"],
                "stop_reason": "end_turn",
                "content": [
                    type("Block", (), {"type": "text", "text": "done"})(),
                ],
            },
        )()


class _Client:
    def __init__(self) -> None:
        self.messages = _Messages()


def test_anthropic_model_forwards_idempotency_key_header() -> None:
    client = _Client()
    model = AnthropicModel(client=client)

    result = model.complete_turn(
        model_id="claude-test",
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        hot_context={},
        idempotency_key="idem_123",
    )

    assert result.final_text == "done"
    assert client.messages.kwargs["extra_headers"] == {
        "Idempotency-Key": "idem_123",
    }


def test_anthropic_model_omits_idempotency_header_when_absent() -> None:
    client = _Client()
    model = AnthropicModel(client=client)

    model.complete_turn(
        model_id="claude-test",
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        hot_context={},
    )

    assert "extra_headers" not in client.messages.kwargs
