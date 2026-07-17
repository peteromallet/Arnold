from __future__ import annotations

import asyncio

import pytest

from arnold_pipelines.megaplan.resident import profile as profile_module
from arnold_pipelines.megaplan.resident import vp_todo
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

    async def fake_launch(config, *, task, toolsets=None, project_dir=None, **kwargs):
        captured["task"] = task
        captured["toolsets"] = toolsets
        captured["project_dir"] = project_dir
        captured.update(kwargs)
        return SubagentResult(ok=True, final_text="did it", stderr="", returncode=0)

    monkeypatch.setattr(profile_module, "launch_subagent_task", fake_launch)

    result = asyncio.run(
        profile._launch_subagent(
            LaunchSubagentInput(
                task="summarize readme",
                description="Summarize the repository README",
                toolsets="file,web",
                project_dir="/repo",
            )
        )
    )
    assert result.ok is True
    assert result.data["final_text"] == "did it"
    assert captured["task"] == "summarize readme"
    assert captured["toolsets"] == "file,web"
    assert captured["project_dir"] == "/repo"
    assert captured["backend"] == "auto"
    assert captured["background"] is True


def test_launch_subagent_tool_propagates_failure(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path)

    async def fake_launch(config, *, task, toolsets=None, project_dir=None, **kwargs):
        return SubagentResult(ok=False, final_text="", stderr="boom", returncode=6, error="exit 6")

    monkeypatch.setattr(profile_module, "launch_subagent_task", fake_launch)

    result = asyncio.run(
        profile._launch_subagent(
            LaunchSubagentInput(task="x", description="Run the delegated task")
        )
    )
    assert result.ok is False
    assert result.data["returncode"] == 6


def test_hot_context_exposes_managed_resident_agents(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path)
    expected = {
        "schema_version": "arnold-resident-agent-run-v1",
        "running": [{"run_id": "resident-1", "manifest_path": "/runs/manifest.json"}],
        "recent": [],
    }
    monkeypatch.setattr(profile_module, "list_managed_resident_agents", lambda **kwargs: expected)

    context = asyncio.run(profile.load_hot_context("missing-conversation"))

    agents = context["resident_agents"]
    assert agents["schema_version"] == expected["schema_version"]
    assert agents["running_count"] == 1
    assert agents["running"] == [
        {"run_id": "resident-1", "completion_delivery": None}
    ]
    assert agents["recent"] == []
    assert "manifest_path" not in agents["running"][0]
    assert context["resident_runtime"]["subagent_launch"]["standard"] == (
        "arnold-managed-agent-run-v2"
    )
    policy = context["resident_runtime"]["subagent_launch"]["delegation_policy"]
    assert "independent actionable sub-problems" in policy["preference"]
    assert "one clear owner per sub-problem" in policy["ownership"]
    assert "action-oriented task prompt" in policy["task_prompt_contract"]
    assert "explanation, review, status" in policy["exceptions"]["non_execution"]
    assert "trivial or non-independent fragments" in policy["exceptions"][
        "trivial_or_non_independent"
    ]
    assert "never expands" in policy["exceptions"]["authorization"]
    assert "returned durable run ID" in policy["launch_evidence"]


def test_hot_context_vp_todos_is_empty_when_no_pending_items(tmp_path) -> None:
    context = asyncio.run(_profile(tmp_path).load_hot_context("missing-conversation"))

    todos = context["vp_special_requests_todos"]
    assert todos["schema_version"] == "vp-special-requests-todo-hot-context-v1"
    assert todos["pending_count"] == 0
    assert todos["pending_preview"] == []
    assert todos["preview_omitted_count"] == 0


@pytest.mark.parametrize("count", [1, 2, 3])
def test_hot_context_vp_todos_previews_up_to_three_pending_items(tmp_path, count) -> None:
    profile = _profile(tmp_path)
    vp_todo.save_items(
        profile.config.special_requests_todo_path,
        [
            {
                "id": f"task-{number}",
                "task": f"special request {number}",
                "status": "pending",
                "result": "",
                "reason": "",
                "updated_at": "2026-01-01T00:00:00Z",
                "when": "",
            }
            for number in range(1, count + 1)
        ],
    )

    todos = asyncio.run(profile.load_hot_context("missing-conversation"))["vp_special_requests_todos"]

    assert todos["pending_count"] == count
    assert [item["id"] for item in todos["pending_preview"]] == [
        f"task-{number}" for number in range(1, count + 1)
    ]
    assert [item["task"] for item in todos["pending_preview"]] == [
        f"special request {number}" for number in range(1, count + 1)
    ]
    assert all(item["status"] == "pending" for item in todos["pending_preview"])
    assert all(item["when"] is None for item in todos["pending_preview"])


def test_hot_context_vp_todos_bounds_preview_and_keeps_stable_ids(tmp_path) -> None:
    profile = _profile(tmp_path)
    vp_todo.save_items(
        profile.config.special_requests_todo_path,
        [
            {
                "id": f"stable-{number}",
                "task": f"request {number}",
                "status": "pending",
                "result": "",
                "reason": "",
                "updated_at": "2026-01-01T00:00:00Z",
                "when": "",
            }
            for number in range(1, 5)
        ],
    )

    todos = asyncio.run(profile.load_hot_context("missing-conversation"))["vp_special_requests_todos"]

    assert todos["pending_count"] == 4
    assert [item["id"] for item in todos["pending_preview"]] == [
        "stable-1",
        "stable-2",
        "stable-3",
    ]
    assert todos["preview_omitted_count"] == 1


def test_hot_context_vp_todos_labels_conditional_work_and_full_list_retrieval(tmp_path) -> None:
    profile = _profile(tmp_path)
    vp_todo.save_items(
        profile.config.special_requests_todo_path,
        [
            {
                "id": "conditional-7",
                "task": "publish the report using sk-abcdefghijklmnopqrstuvwxyz1234567890",
                "status": "pending",
                "result": "",
                "reason": "",
                "updated_at": "2026-01-01T00:00:00Z",
                "when": "once epic ABC is done",
                "launch_provenance": {"token": "sk-abcdefghijklmnopqrstuvwxyz1234567890"},
            }
        ],
    )

    todos = asyncio.run(profile.load_hot_context("missing-conversation"))["vp_special_requests_todos"]

    assert todos["pending_count"] == 1
    assert todos["pending_preview"] == [
        {
            "id": "conditional-7",
            "task": "publish the report using <REDACTED_API_KEY>",
            "status": "pending",
            "when": "once epic ABC is done",
        }
    ]
    assert "not thereby known to be due" in todos["pending_semantics"]
    assert todos["full_list_retrieval"]["tool"] == "read_todo_list"
    assert todos["full_list_retrieval"]["arguments"] == {}
    assert "full VP special-requests" in todos["full_list_retrieval"]["instruction"]
    assert "vp_special_requests_todos" in profile.system_prompt()
    assert "call `read_todo_list` with no arguments" in profile.system_prompt()
    assert "sk-" not in repr(todos)


def test_launch_subagent_tool_rejects_empty_task(tmp_path) -> None:
    profile = _profile(tmp_path)
    result = asyncio.run(
        profile._launch_subagent(
            LaunchSubagentInput(task="", description="Reject the empty task")
        )
    )
    assert result.ok is False
