from __future__ import annotations

import asyncio

from pydantic import Field

import arnold.pipelines.megaplan.resident.agent_loop as agent_loop
from arnold.pipelines.megaplan.resident import (
    AgentLoopError,
    AgentRequest,
    AgentRunner,
    DispatchProtocol,
    FakeAgentRunner,
    FakeAgentStep,
    OpenAICompatibleAgentRunner,
    ResidentConfig,
    ToolRegistration,
    ToolRegistry,
)
from arnold.pipelines.megaplan.resident.tool_schemas import ToolInput, ToolResult


class EchoInput(ToolInput):
    text: str


class CountInput(ToolInput):
    amount: int = Field(gt=0)


def _request() -> AgentRequest:
    return AgentRequest(
        conversation_id="conversation-1",
        messages=({"role": "user", "content": "hello"},),
        system_prompt="system",
        hot_context={"ok": True},
    )


def test_resident_agent_runner_is_bound_to_dispatch_protocol() -> None:
    assert DispatchProtocol in AgentRunner.__mro__
    assert DispatchProtocol in OpenAICompatibleAgentRunner.__mro__


def test_fake_agent_runner_executes_bounded_tool_loop_and_returns_audit_records() -> None:
    registry = ToolRegistry()

    def echo_tool(payload: EchoInput) -> ToolResult:
        return ToolResult(ok=True, message="echoed", data={"text": payload.text})

    async def count_tool(payload: CountInput) -> ToolResult:
        await asyncio.sleep(0)
        return ToolResult(ok=True, data={"amount": payload.amount})

    registry.register(
        ToolRegistration(
            name="echo",
            description="Echo text",
            operation_kind="read",
            input_model=EchoInput,
            output_model=ToolResult,
            handler=echo_tool,
        )
    )
    registry.register(
        ToolRegistration(
            name="count",
            description="Count",
            operation_kind="write",
            input_model=CountInput,
            output_model=ToolResult,
            handler=count_tool,
        )
    )

    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("echo", {"text": "hi"}),
            FakeAgentStep.call("count", {"amount": 3}),
            FakeAgentStep.final("done"),
        ],
        max_tool_calls=4,
    )

    response = asyncio.run(runner.run(_request(), registry))

    assert response.final_text == "done"
    assert response.metadata == {"steps_executed": 3, "tool_calls_executed": 2}
    assert [record.id for record in response.tool_calls] == ["fake_tool_0001", "fake_tool_0002"]
    assert [record.tool_name for record in response.tool_calls] == ["echo", "count"]
    assert response.tool_calls[0].arguments == {"text": "hi"}
    assert response.tool_calls[0].result == {"ok": True, "message": "echoed", "data": {"text": "hi"}}
    assert response.tool_calls[1].operation_kind == "write"


def test_fake_agent_runner_records_validation_and_timeout_errors_deterministically() -> None:
    registry = ToolRegistry()

    async def slow_tool(payload: EchoInput) -> ToolResult:
        del payload
        await asyncio.sleep(0.05)
        return ToolResult(ok=True)

    registry.register(
        ToolRegistration(
            name="needs_count",
            description="Needs a positive count",
            operation_kind="read",
            input_model=CountInput,
            output_model=ToolResult,
            handler=lambda payload: ToolResult(ok=True, data={"amount": payload.amount}),
        )
    )
    registry.register(
        ToolRegistration(
            name="slow",
            description="Slow",
            operation_kind="cloud_read",
            input_model=EchoInput,
            output_model=ToolResult,
            handler=slow_tool,
        )
    )
    runner = FakeAgentRunner(
        [
            FakeAgentStep.call("needs_count", {"amount": 0}),
            FakeAgentStep.call("slow", {"text": "wait"}),
            FakeAgentStep.final("done"),
        ],
        tool_timeout_s=0.001,
    )

    response = asyncio.run(runner.run(_request(), registry))

    assert response.final_text == "done"
    assert response.tool_calls[0].result["ok"] is False
    assert response.tool_calls[0].result["data"] == {"error": "ValidationError"}
    assert response.tool_calls[1].result == {
        "ok": False,
        "message": "tool timed out after 0.001s",
        "data": {"error": "timeout"},
    }


def test_fake_agent_runner_audits_unknown_tool_without_model_access() -> None:
    runner = FakeAgentRunner([FakeAgentStep.call("missing", {"value": "x"}), FakeAgentStep.final("done")])

    response = asyncio.run(runner.run(_request(), ToolRegistry()))

    assert response.final_text == "done"
    assert response.tool_calls[0].tool_name == "missing"
    assert response.tool_calls[0].result["ok"] is False
    assert response.tool_calls[0].result["data"] == {"error": "KeyError"}


def test_fake_agent_runner_enforces_tool_call_limit_and_requires_final_text() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolRegistration(
            name="echo",
            description="Echo",
            operation_kind="read",
            input_model=EchoInput,
            output_model=ToolResult,
            handler=lambda payload: ToolResult(ok=True, data={"text": payload.text}),
        )
    )

    too_many = FakeAgentRunner(
        [FakeAgentStep.call("echo", {"text": "a"}), FakeAgentStep.call("echo", {"text": "b"})],
        max_tool_calls=1,
    )
    try:
        asyncio.run(too_many.run(_request(), registry))
    except AgentLoopError as exc:
        assert str(exc) == "resident tool-call limit exceeded: 1"
    else:
        raise AssertionError("expected tool-call limit failure")

    no_final = FakeAgentRunner([FakeAgentStep.call("echo", {"text": "a"})])
    try:
        asyncio.run(no_final.run(_request(), registry))
    except AgentLoopError as exc:
        assert str(exc) == "fake agent script ended without final_text"
    else:
        raise AssertionError("expected missing final_text failure")


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content: str | None = None, tool_calls: list[_FakeToolCall] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs: object) -> _FakeResponse:
        self.calls += 1
        if self.calls == 1:
            assert kwargs["model"] == "gpt-test"
            assert kwargs["tool_choice"] == "auto"
            return _FakeResponse(_FakeMessage(tool_calls=[_FakeToolCall("call-1", "echo", '{"text": "live"}')]))
        return _FakeResponse(_FakeMessage(content="live final"))


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.chat = _FakeChat()


def test_openai_compatible_agent_runner_executes_live_tool_loop(monkeypatch) -> None:
    registry = ToolRegistry()
    registry.register(
        ToolRegistration(
            name="echo",
            description="Echo",
            operation_kind="read",
            input_model=EchoInput,
            output_model=ToolResult,
            handler=lambda payload: ToolResult(ok=True, message="echoed", data={"text": payload.text}),
        )
    )
    client = _FakeOpenAIClient()
    monkeypatch.setattr(agent_loop, "_openai_client", lambda config: client)

    runner = OpenAICompatibleAgentRunner(ResidentConfig(model_name="gpt-test"), max_tool_calls=2)
    response = asyncio.run(runner.run(_request(), registry))

    assert response.final_text == "live final"
    assert response.metadata["model"] == "gpt-test"
    assert response.tool_calls[0].id == "call-1"
    assert response.tool_calls[0].tool_name == "echo"
    assert response.tool_calls[0].result == {"ok": True, "message": "echoed", "data": {"text": "live"}}
