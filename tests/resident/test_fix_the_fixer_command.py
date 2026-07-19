from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from arnold_pipelines.megaplan.resident import profile as profile_module
from arnold_pipelines.megaplan.resident.agent_loop import (
    ToolRuntimeContext,
    execute_registered_tool,
)
from arnold_pipelines.megaplan.resident.auth import ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.discord import ResidentDiscordService
from arnold_pipelines.megaplan.resident.fix_the_fixer import (
    FIX_THE_FIXER_COMMAND,
    FIX_THE_FIXER_TOOL,
)
from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV
from arnold_pipelines.megaplan.resident.runtime import ResidentRuntime
from arnold_pipelines.megaplan.resident.subagent import (
    SubagentResult,
    route_delegated_task,
)
from arnold_pipelines.megaplan.store import FileStore


class _Profile(MegaplanResidentProfile):
    async def load_hot_context(self, conversation_id: str) -> dict[str, Any]:
        return {"prompt_version": "test", "user_timezone": {"name": "UTC"}}


class _NeverRunner:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, request: Any, tools: Any) -> Any:
        self.calls += 1
        raise AssertionError("direct resident commands must not use model routing")


class _Outbound:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, message: Any) -> None:
        self.sent.append(message)


class _Channel:
    id = "301463647895683072"
    parent = None

    def get_partial_message(self, message_id: int) -> str:
        return f"partial:{message_id}"


def _message(content: str, *, message_id: str, author_id: str = "301463647895683072") -> Any:
    return SimpleNamespace(
        id=message_id,
        content=content,
        guild=None,
        channel=_Channel(),
        author=SimpleNamespace(id=author_id, bot=False),
        reference=None,
        flags=SimpleNamespace(voice=False),
        attachments=[],
    )


def _resident(tmp_path, *, allowed_users: tuple[str, ...] = ("301463647895683072",)):
    config = ResidentConfig(
        allowed_user_ids=allowed_users,
        special_requests_todo_path=tmp_path / "todo.json",
        burst_idle_delay_s=0,
        burst_max_delay_s=1,
    )
    store = FileStore(tmp_path / "store")
    authorizer = ResidentAuthorizer(config)
    profile = _Profile(store=store, authorizer=authorizer, config=config)
    runner = _NeverRunner()
    outbound = _Outbound()
    runtime = ResidentRuntime(
        config=config,
        authorizer=authorizer,
        store=store,
        profile=profile,
        runner=runner,
        outbound=outbound,
        project_root=tmp_path,
    )
    return (
        ResidentDiscordService(runtime=runtime, token="test-token"),
        profile,
        runner,
        outbound,
    )


def test_fix_the_fixer_is_discoverable_as_command_and_tool(tmp_path) -> None:
    service, profile, _, _ = _resident(tmp_path)
    command = service.command_catalog()[0]
    registration = profile.tools().get(FIX_THE_FIXER_TOOL)

    assert command["usage"] == '/fix-the-fixer --target "EPIC_OR_SESSION_TEXT"'
    assert registration.operation_kind == "write"
    assert registration.input_model.model_json_schema()["required"] == ["target"]
    assert any(
        item.get("name") == FIX_THE_FIXER_TOOL
        for item in profile.tools().as_compact_catalog()
    )
    with pytest.raises(KeyError):
        profile.tools().get("superfixer_debug")


def test_discord_dispatch_preserves_target_provenance_and_launches_once(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run_case() -> None:
        monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
        calls: list[dict[str, Any]] = []

        async def fake_launch(config: ResidentConfig, *, task: str, **kwargs: Any) -> SubagentResult:
            calls.append({"task": task, **kwargs})
            return SubagentResult(
                ok=True,
                final_text="",
                stderr="",
                returncode=0,
                run_id="subagent-safe-dry-run",
                status="running",
                description=kwargs.get("description"),
            )

        monkeypatch.setattr(profile_module, "launch_subagent_task", fake_launch)
        service, _, runner, outbound = _resident(tmp_path)
        target = "  custody-control-plane / session:alpha  beta  "
        message = _message(
            f'{FIX_THE_FIXER_COMMAND} --target "{target}"',
            message_id="1527630039552888943",
        )

        await service.handle_message(message)
        await service.handle_message(message)

        assert runner.calls == 0
        assert len(calls) == 1
        launch = calls[0]
        assert f'target "{target}"' in launch["task"]
        assert launch["task"].startswith("/goal\n")
        assert "$superfixer-debug" in launch["task"]
        assert "TRACKED, FIXED, INTENT, and CONTEXT" in launch["task"]
        assert "Launch no agents or subagents" in launch["task"]
        assert launch["task_kind"] == "root_cause"
        assert launch["difficulty"] == 10
        assert launch["model"] is None
        assert launch["reasoning_effort"] is None
        assert launch["aggregation_role"] == "synthesis_delivery_owner"
        origin = launch["launch_origin"]
        assert origin["source_kind"] == "discord_inbound_message"
        assert origin["discord_message_id"] == "1527630039552888943"
        assert origin["reply_to_message_id"] == "1527630039552888943"
        assert origin["source_record_id"].startswith("msg_")
        assert origin["delegation_id"].startswith("resident_command_")
        route = route_delegated_task(
            task_kind=launch["task_kind"], difficulty=launch["difficulty"]
        )
        assert (route.model, route.reasoning_effort) == ("gpt-5.6-sol", "high")
        assert len(outbound.sent) == 1
        assert "subagent-safe-dry-run" in outbound.sent[0].content
        assert target in outbound.sent[0].content

    asyncio.run(run_case())


@pytest.mark.parametrize(
    "content",
    [
        FIX_THE_FIXER_COMMAND,
        f'{FIX_THE_FIXER_COMMAND} --target "   "',
        f'{FIX_THE_FIXER_COMMAND} --target one --target two',
    ],
)
def test_discord_dispatch_rejects_missing_blank_or_duplicate_target(
    tmp_path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    async def run_case() -> None:
        launches = 0

        async def must_not_launch(*args: Any, **kwargs: Any) -> SubagentResult:
            nonlocal launches
            launches += 1
            raise AssertionError("invalid command reached launcher")

        monkeypatch.setattr(profile_module, "launch_subagent_task", must_not_launch)
        service, _, runner, outbound = _resident(tmp_path)
        await service.handle_message(
            _message(content, message_id="1527630039552888944")
        )

        assert launches == 0
        assert runner.calls == 0
        assert len(outbound.sent) == 1
        assert "--target" in outbound.sent[0].content

    asyncio.run(run_case())


def test_unauthorized_or_internal_context_cannot_launch(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def run_case() -> None:
        launches = 0

        async def must_not_launch(*args: Any, **kwargs: Any) -> SubagentResult:
            nonlocal launches
            launches += 1
            raise AssertionError("guarded context reached launcher")

        monkeypatch.setattr(profile_module, "launch_subagent_task", must_not_launch)
        service, profile, runner, outbound = _resident(
            tmp_path, allowed_users=("999999999999999999",)
        )
        await service.handle_message(
            _message(
                f'{FIX_THE_FIXER_COMMAND} --target "session-alpha"',
                message_id="1527630039552888945",
            )
        )
        audit = await execute_registered_tool(
            tools=profile.tools(),
            tool_name=FIX_THE_FIXER_TOOL,
            arguments={"target": "session-alpha"},
            audit_id="internal-goal-call",
            timeout_s=5,
            runtime_context=ToolRuntimeContext(
                conversation_id="rconv_internalgoal",
                subject=None,
                launch_origin={
                    "transport": "discord",
                    "applicability": "applicable",
                    "source_kind": "discord_inbound_message",
                },
            ),
        )

        assert launches == 0
        assert runner.calls == 0
        assert outbound.sent == []
        assert audit.result["data"]["recursion_guard"] is True

    asyncio.run(run_case())
