from __future__ import annotations

import asyncio
import json

from arnold_pipelines.megaplan.resident.agent_loop import AgentResponse
from arnold_pipelines.megaplan.resident.auth import (
    AuthorizationSubject,
    ResidentAuthorizer,
)
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.runtime import (
    InboundEvent,
    OutboundMessage,
    ResidentRuntime,
)
from arnold_pipelines.megaplan.store import FileStore


class CapturingRunner:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.requests = []

    async def run(self, request, _tools):
        self.requests.append(request)
        return AgentResponse(final_text=self.responses.pop(0))


class CapturingOutbound:
    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> None:
        self.sent.append(message)


def _runtime(tmp_path, responses: list[str], *, idle_delay_s: float = 0):
    store = FileStore(tmp_path / "store")
    config = ResidentConfig(
        allowed_user_ids=("42",),
        burst_idle_delay_s=idle_delay_s,
        burst_max_delay_s=max(1, idle_delay_s),
    )
    authorizer = ResidentAuthorizer(config)
    runner = CapturingRunner(responses)
    outbound = CapturingOutbound()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=MegaplanResidentProfile(
            store=store, authorizer=authorizer, config=config
        ),
        runner=runner,
        outbound=outbound,
    )
    return runtime, runner, outbound


def _event(key: str, content: str, **raw) -> InboundEvent:
    return InboundEvent(
        idempotency_key=f"discord:message:{key}",
        conversation_key="discord:dm:42",
        subject=AuthorizationSubject(user_id="42", channel_id="42"),
        content=content,
        raw={"discord_message_id": key, "dm_user_id": "42", **raw},
    )


def _authoritative_records(system_prompt: str) -> list[dict[str, str]]:
    start = "<authoritative_current_request_json>\n"
    end = "\n</authoritative_current_request_json>"
    payload = system_prompt.split(start, 1)[1].split(end, 1)[0]
    return json.loads(payload)


def test_direct_message_is_injected_and_response_is_not_normalized(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, outbound = _runtime(
            tmp_path, ["A natural response with no required summary header."]
        )
        event = _event("1001", "Fix the direct resident request binding.")

        await runtime.receive(event)
        await runtime.coalescer.flush_all()

        request = runner.requests[0]
        records = _authoritative_records(request.system_prompt)
        assert [record["content"] for record in records] == [event.content]
        assert "sole current request" in request.system_prompt
        assert "do not infer or substitute a different current request" in request.system_prompt
        assert outbound.sent[0].content == "A natural response with no required summary header."
        assert outbound.sent[0].metadata["discord_reply_to_message_id"] == "1001"
        current = request.hot_context["current_request"]
        assert current["source_record_ids"] == [records[0]["source_record_id"]]
        assert "summary_line" not in current

    asyncio.run(run_case())


def test_reply_uses_current_reply_not_bounded_history_as_prompt_authority(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, outbound = _runtime(tmp_path, ["First answer.", "Reply answer."])
        earlier = _event("2001", "Earlier request that must remain history only.")
        await runtime.receive(earlier)
        await runtime.coalescer.flush_all()

        reply = _event(
            "2002",
            "This reply is the authoritative current request.",
            discord_reference_message_id="2001",
            discord_reference_author_id="42",
            discord_reference_content=earlier.content,
            discord_reply_chain={
                "ancestors": [
                    {
                        "message_id": "2001",
                        "author_id": "42",
                        "content": earlier.content,
                        "status": "available",
                    }
                ],
                "chain_complete": True,
            },
        )
        await runtime.receive(reply)
        await runtime.coalescer.flush_all()

        request = runner.requests[-1]
        records = _authoritative_records(request.system_prompt)
        assert [record["content"] for record in records] == [reply.content]
        assert earlier.content not in request.system_prompt
        assert any(earlier.content in message["content"] for message in request.messages)
        assert outbound.sent[-1].metadata["discord_reply_to_message_id"] == "2002"

    asyncio.run(run_case())


def test_rapid_messages_are_bound_together_in_arrival_order(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, outbound = _runtime(
            tmp_path, ["Combined answer."], idle_delay_s=3600
        )
        first = _event("3001", "First rapid request.")
        second = _event("3002", "Second rapid request.")

        await runtime.receive(first)
        await runtime.receive(second)
        await runtime.coalescer.flush_all()

        request = runner.requests[0]
        records = _authoritative_records(request.system_prompt)
        assert [record["content"] for record in records] == [first.content, second.content]
        assert len(request.hot_context["current_request"]["source_record_ids"]) == 2
        assert outbound.sent[0].metadata["discord_reply_to_message_id"] == "3002"

    asyncio.run(run_case())


def test_empty_authoritative_content_is_represented_without_fallback_request(tmp_path) -> None:
    async def run_case() -> None:
        runtime, runner, outbound = _runtime(tmp_path, ["No request content was provided."])
        await runtime.receive(_event("4001", ""))
        await runtime.coalescer.flush_all()

        request = runner.requests[0]
        assert _authoritative_records(request.system_prompt)[0]["content"] == ""
        assert "There is no substantive current request" in request.system_prompt
        assert "unavailable from the authoritative inbound request" not in request.system_prompt
        assert outbound.sent[0].content == "No request content was provided."

    asyncio.run(run_case())
