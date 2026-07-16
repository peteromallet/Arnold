from __future__ import annotations

import argparse
import asyncio
import json
import shlex

import pytest

from arnold_pipelines.megaplan.resident import profile as profile_module
from arnold_pipelines.megaplan.resident import vp_todo
from arnold_pipelines.megaplan.resident import agent_loop as agent_loop_module
from arnold_pipelines.megaplan.resident.agent_loop import ToolRuntimeContext
from arnold_pipelines.megaplan.resident.auth import ResidentAuthorizer
from arnold_pipelines.megaplan.resident.cli import _register_resident_subcommands
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.profile import (
    AddTodoItemInput,
    CompleteTodoItemInput,
    FailTodoItemInput,
    LaunchSubagentInput,
    MegaplanResidentProfile,
    ReadTodoListInput,
    ReconcileTodoItemInput,
    SupersedeTodoItemInput,
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


def test_reconcile_existing_canonical_run_is_terminal_and_idempotent(tmp_path) -> None:
    profile = _profile(tmp_path)
    added = profile._add_todo_item(AddTodoItemInput(task="launch chain")).data["item"]
    payload = ReconcileTodoItemInput(
        id=added["id"],
        canonical_run_id="canonical-chain-7",
        evidence="/evidence/canonical-chain-7.json",
        resolution="the exact requested chain is already canonical and running",
    )

    first = profile._reconcile_todo_item(payload)
    second = profile._reconcile_todo_item(payload)

    assert first.ok is True and second.ok is True
    item = profile._read_todo_list(ReadTodoListInput()).data["items"][0]
    assert item["status"] == vp_todo.SUPERSEDED
    assert item["canonical_run_id"] == "canonical-chain-7"
    assert item["canonical_run_evidence"] == "/evidence/canonical-chain-7.json"
    assert profile._read_todo_list(ReadTodoListInput()).data["pending"] == 0


def test_supersede_tool_uses_canonical_record_without_claiming_completion(tmp_path) -> None:
    profile = _profile(tmp_path)
    added = profile._add_todo_item(AddTodoItemInput(task="launch retired chain")).data["item"]
    payload = SupersedeTodoItemInput(
        id=added["id"],
        canonical_record_id="initiative:custody-control-plane",
        evidence="refs/heads/main:.megaplan/initiatives/wbc/.retired@deadbeef",
        resolution="standalone chain was canonically retired and replaced",
    )

    first = profile._supersede_todo_item(payload)
    second = profile._supersede_todo_item(payload)

    assert first.ok is True and second.ok is True
    item = profile._read_todo_list(ReadTodoListInput()).data["items"][0]
    assert item["status"] == vp_todo.SUPERSEDED
    assert item["canonical_record_id"] == "initiative:custody-control-plane"
    assert "completion" in first.message
    assert profile._read_todo_list(ReadTodoListInput()).data["pending"] == 0


def test_reconcile_rejects_missing_evidence_and_conflicting_run(tmp_path) -> None:
    profile = _profile(tmp_path)
    added = profile._add_todo_item(AddTodoItemInput(task="launch chain")).data["item"]
    missing = profile._reconcile_todo_item(
        ReconcileTodoItemInput(
            id=added["id"], canonical_run_id="run-1", evidence="", resolution="overlap"
        )
    )
    assert missing.ok is False
    assert profile._read_todo_list(ReadTodoListInput()).data["pending"] == 1

    assert profile._reconcile_todo_item(
        ReconcileTodoItemInput(
            id=added["id"],
            canonical_run_id="run-1",
            evidence="/evidence/run-1.json",
            resolution="exact canonical identity",
        )
    ).ok
    conflict = profile._reconcile_todo_item(
        ReconcileTodoItemInput(
            id=added["id"],
            canonical_run_id="run-2",
            evidence="/evidence/run-2.json",
            resolution="different run",
        )
    )
    assert conflict.ok is False


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
                work_intent="review",
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
    assert captured["backend"] == "codex"
    assert captured["background"] is True
    assert captured["work_intent"] == "review"


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


def test_scheduled_todo_launch_without_authoritative_inbound_fails_with_diagnostic(
    tmp_path, monkeypatch
) -> None:
    profile = _profile(tmp_path)
    item = vp_todo.add_item(
        profile.config.special_requests_todo_path,
        "launch legacy scheduled work",
    )

    async def must_not_launch(*args, **kwargs):
        raise AssertionError("missing inbound custody must block process launch")

    monkeypatch.setattr(profile_module, "launch_subagent_task", must_not_launch)

    result = asyncio.run(
        profile._launch_subagent(
            LaunchSubagentInput(
                task=item["task"],
                description="Launch the scheduled work",
                request_id=item["id"],
            )
        )
    )

    assert result.ok is False
    assert result.data["diagnostic_code"] == "missing_launch_provenance"
    assert result.data["escalation_required"] is True
    logs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "store" / "system_logs").glob("*.json")
    ]
    diagnostic = next(
        row
        for row in logs
        if row["event_type"] == "resident_vp_todo_launch_custody_failure"
    )
    assert diagnostic["details"]["todo_item_id"] == item["id"]
    assert diagnostic["details"]["delegation_allowed"] is False


def test_scheduled_turn_cannot_launch_outside_retained_todo(tmp_path, monkeypatch) -> None:
    profile = _profile(tmp_path)

    async def must_not_launch(*args, **kwargs):
        raise AssertionError("scheduled authority must remain bounded to a retained todo")

    monkeypatch.setattr(profile_module, "launch_subagent_task", must_not_launch)
    token = agent_loop_module._TOOL_RUNTIME_CONTEXT.set(
        ToolRuntimeContext(
            conversation_id="scheduled-audit",
            launch_origin={
                "transport": "non_discord",
                "applicability": "not_applicable",
                "source_kind": "scheduled_turn",
            },
        )
    )
    try:
        result = asyncio.run(
            profile._launch_subagent(
                LaunchSubagentInput(
                    task="unretained work",
                    description="Attempt work outside the retained todo",
                    request_id="unknown-todo",
                )
            )
        )
    finally:
        agent_loop_module._TOOL_RUNTIME_CONTEXT.reset(token)

    assert result.ok is False
    assert result.data["delegation_allowed"] is False
    assert result.data["escalation_required"] is True
    assert "exact retained todo" in result.message


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
    assert policy["schema_version"] == "megaplan-resident-delegation-policy-v3"
    assert "independent actionable sub-problems" in policy["preference"]
    assert "one clear owner per sub-problem" in policy["ownership"]
    assert "action-oriented task prompt" in policy["task_prompt_contract"]
    assert "explanation, review, status" in policy["exceptions"]["non_execution"]
    assert "trivial or non-independent fragments" in policy["exceptions"][
        "trivial_or_non_independent"
    ]
    assert "never expands" in policy["exceptions"]["authorization"]
    assert "returned durable run ID" in policy["launch_evidence"]
    assert "implements, verifies, and delivers" in policy["execution_default"]
    assert "isolated worktree and feature branch" in policy["workspace_default"]
    assert "Never infer literal `main`" in policy["integration_default"]
    assert "explicit approval" in policy["external_actions"]
    assert "label it unintegrated" in policy["tentative_work"]
    assert "durable ancestry evidence" in policy["completion_evidence"]


def test_hot_context_fan_in_example_matches_tool_and_cli_contract(tmp_path) -> None:
    context = asyncio.run(_profile(tmp_path).load_hot_context("missing-conversation"))
    queued = context["resident_runtime"]["subagent_launch"]["queued_successors"]
    owner = queued["fan_in_example"]["synthesis_delivery_owner"]

    assert owner["resident_tool"] == "launch_subagent"
    tool_payload = LaunchSubagentInput(**owner["arguments"])
    assert tool_payload.aggregation_role == "synthesis_delivery_owner"
    assert tool_payload.depends_on_run_id is None
    assert tool_payload.depends_on_run_ids == [
        "subagent-20260716-120000-a1b2c3d4",
        "subagent-20260716-120100-b2c3d4e5",
    ]

    parser = argparse.ArgumentParser()
    _register_resident_subcommands(parser)
    cli_tokens = shlex.split(queued["cli_create"])
    cli_args = parser.parse_args(
        cli_tokens[cli_tokens.index("queue-subagent-successor") :]
    )
    assert cli_args.after_run_id is None
    assert cli_args.after_run_ids == tool_payload.depends_on_run_ids

    singular_tokens = shlex.split(queued["singular_compatibility"]["cli_create"])
    singular_args = parser.parse_args(
        singular_tokens[singular_tokens.index("queue-subagent-successor") :]
    )
    assert singular_args.after_run_id == tool_payload.depends_on_run_ids[0]
    assert singular_args.after_run_ids is None


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


def test_supersede_todo_cli_requires_canonical_record_evidence() -> None:
    parser = argparse.ArgumentParser()
    _register_resident_subcommands(parser)

    args = parser.parse_args(
        [
            "supersede-todo",
            "--id",
            "todo-7",
            "--canonical-record-id",
            "initiative:replacement",
            "--evidence",
            "refs/heads/main:.megaplan/initiatives/old/.retired@abc",
            "--resolution",
            "canonical retirement replaced the old launch intent",
            "--todo-path",
            "/tmp/todo.json",
        ]
    )

    assert args.resident_action == "supersede-todo"
    assert args.canonical_record_id == "initiative:replacement"
    assert args.evidence.endswith("@abc")


def test_report_only_tool_boundary_denies_non_reconciliation_mutation(tmp_path) -> None:
    profile = _profile(tmp_path)

    audit = asyncio.run(
        agent_loop_module._execute_registered_tool(
            tools=profile.tools(),
            tool_name="add_todo_item",
            arguments={"task": "must not be added"},
            audit_id="audit-denied",
            timeout_s=5,
            runtime_context=ToolRuntimeContext(
                conversation_id="scheduled-audit",
                launch_origin={
                    "source_kind": "scheduled_turn",
                    "report_only": True,
                },
            ),
        )
    )

    assert audit.result["ok"] is False
    assert audit.result["data"]["error"] == "report_only_execution_denied"
    assert vp_todo.load_items(profile.config.special_requests_todo_path) == []
