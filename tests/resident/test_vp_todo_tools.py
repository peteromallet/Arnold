from __future__ import annotations

import asyncio

from arnold_pipelines.megaplan.resident import profile as profile_module
from arnold_pipelines.megaplan.resident.auth import ResidentAuthorizer
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import (
    AddTodoItemInput,
    CompleteTodoItemInput,
    FailTodoItemInput,
    LaunchSubagentInput,
    MegaplanResidentProfile,
    ReadTodoListInput,
)
from arnold_pipelines.megaplan.resident.subagent import SubagentResult
from arnold_pipelines.megaplan.store import FileStore


def _profile(tmp_path):
    config = ResidentConfig(special_requests_todo_path=tmp_path / "todo.json")
    return MegaplanResidentProfile(
        store=FileStore(tmp_path / "store"),
        authorizer=ResidentAuthorizer(config),
        config=config,
    )


def test_read_todo_list_empty(tmp_path) -> None:
    profile = _profile(tmp_path)
    result = profile._read_todo_list(ReadTodoListInput())
    assert result.ok is True
    assert result.data["items"] == []
    assert result.data["pending"] == 0


def test_complete_clears_via_tool(tmp_path) -> None:
    profile = _profile(tmp_path)
    added = profile._add_todo_item(AddTodoItemInput(task="ship it")).data["item"]
    completed = profile._complete_todo_item(
        CompleteTodoItemInput(id=added["id"], result="shipped")
    )
    assert completed.ok is True
    assert completed.data["item"]["status"] == "done"
    # list now empty
    after = profile._read_todo_list(ReadTodoListInput())
    assert after.data["items"] == []


def test_complete_unknown_id(tmp_path) -> None:
    profile = _profile(tmp_path)
    result = profile._complete_todo_item(CompleteTodoItemInput(id="ghost", result="r"))
    assert result.ok is False
    assert "not found" in (result.message or "")


def test_fail_retained_via_tool(tmp_path) -> None:
    profile = _profile(tmp_path)
    added = profile._add_todo_item(AddTodoItemInput(task="ship it")).data["item"]
    failed = profile._fail_todo_item(FailTodoItemInput(id=added["id"], reason="nope"))
    assert failed.ok is True
    items = profile._read_todo_list(ReadTodoListInput()).data["items"]
    assert len(items) == 1
    assert items[0]["status"] == "failed"


def test_add_rejects_empty_task(tmp_path) -> None:
    profile = _profile(tmp_path)
    result = profile._add_todo_item(AddTodoItemInput(task="   "))
    assert result.ok is False


def test_add_todo_item_records_when_condition(tmp_path) -> None:
    profile = _profile(tmp_path)
    result = profile._add_todo_item(
        AddTodoItemInput(task="ship it", when="once epic ABC is done")
    )
    assert result.ok is True
    assert result.data["item"]["when"] == "once epic ABC is done"


def test_launch_subagent_tool_wraps_dispatcher(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path)

    captured: dict = {}

    async def fake_launch(config, *, task, toolsets=None, project_dir=None):
        captured["task"] = task
        captured["toolsets"] = toolsets
        captured["project_dir"] = project_dir
        return SubagentResult(ok=True, final_text="did it", stderr="", returncode=0)

    monkeypatch.setattr(profile_module, "launch_subagent_task", fake_launch)

    result = asyncio.run(
        profile._launch_subagent(
            LaunchSubagentInput(task="summarize readme", toolsets="file,web", project_dir="/repo")
        )
    )
    assert result.ok is True
    assert result.data["final_text"] == "did it"
    assert captured["task"] == "summarize readme"
    assert captured["toolsets"] == "file,web"
    assert captured["project_dir"] == "/repo"


def test_launch_subagent_tool_propagates_failure(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path)

    async def fake_launch(config, *, task, toolsets=None, project_dir=None):
        return SubagentResult(ok=False, final_text="", stderr="boom", returncode=6, error="exit 6")

    monkeypatch.setattr(profile_module, "launch_subagent_task", fake_launch)

    result = asyncio.run(profile._launch_subagent(LaunchSubagentInput(task="x")))
    assert result.ok is False
    assert result.data["returncode"] == 6


def test_launch_subagent_tool_rejects_empty_task(tmp_path) -> None:
    profile = _profile(tmp_path)
    result = asyncio.run(profile._launch_subagent(LaunchSubagentInput(task="")))
    assert result.ok is False
