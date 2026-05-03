from __future__ import annotations

import json

import agent_kit.tools.code as code_tools
from agent_kit.model import FakeModel, tool_request
from agent_kit.loop import run_turn
from agent_kit.tool_kit import ToolContext, registry
from tests.helpers import create_store, insert_epic


SECRET = "sk-proj-" + "A" * 48


class FakeGitHubClient:
    def __init__(self) -> None:
        self.tree_calls = 0
        self.search_calls = 0
        self.file_calls = 0

    def repo_metadata(self, owner: str, name: str):
        return {"ok": True, "repo": {"owner": owner.lower(), "name": name.lower(), "default_branch": "main"}}

    def tree(self, owner: str, name: str, ref: str, *, path: str | None = None):
        self.tree_calls += 1
        return {"ok": True, "tree": [{"path": "src/app.py", "type": "blob", "sha": "1"}], "truncated": False}

    def file_content(self, owner: str, name: str, file_path: str, *, ref: str):
        self.file_calls += 1
        return {"ok": True, "file": {"path": file_path, "sha": "1", "size": 20, "content": f"a\n{SECRET}\nc"}}

    def search_code(self, owner: str, name: str, query: str):
        self.search_calls += 1
        return {"ok": True, "items": [{"path": "src/app.py", "name": "app.py", "sha": "1", "url": "u"}]}


def _context(tmp_path):
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    client = FakeGitHubClient()
    context = ToolContext(
        store=store,
        turn_id=turn["id"],
        events=[],
        metadata={"epic_id": "epic_1", "github_client": client},
    )
    return store, conn, context, client


def test_codebase_management_and_full_investigation_chain(tmp_path) -> None:
    store, conn, context, client = _context(tmp_path)

    added = registry.invoke("add_codebase", context, {"owner": "Owner", "name": "Repo", "group_name": "backend"}).result
    codebase = added["codebase"]
    assert codebase["owner"] == "owner"
    assert codebase["name"] == "repo"
    assert codebase["verified_accessible_at"]

    assert registry.invoke("list_codebases", context, {"group": "backend"}).result["codebases"][0]["id"] == codebase["id"]
    assert registry.invoke("get_codebase_tree", context, {"codebase_id": codebase["id"]}).result["tree"][0]["path"] == "src/app.py"
    assert registry.invoke("search_code", context, {"codebase_id": codebase["id"], "query": "app"}).result["items"][0]["path"] == "src/app.py"
    read = registry.invoke("read_codebase_file", context, {"codebase_id": codebase["id"], "file_path": "src/app.py", "line_range": "2-2"}).result
    assert SECRET not in read["content"]

    excerpt = registry.invoke(
        "save_code_excerpt",
        context,
        {"codebase_id": codebase["id"], "file_path": "src/app.py", "content": read["content"], "summary": "important"},
    ).result["artifact"]
    mark = registry.invoke("mark_code_in_body", context, {"artifact_id": excerpt["id"], "epic_id": "epic_1", "reason": "API contract"}).result
    assert mark["body_edited"] is False

    event = conn.execute("SELECT event_type FROM epic_events WHERE event_type = 'code_referenced'").fetchone()
    assert event is not None
    raw_payloads = conn.execute("SELECT result FROM tool_calls UNION ALL SELECT content FROM code_artifacts").fetchall()
    assert SECRET not in json.dumps([row[0] for row in raw_payloads])


def test_analyze_code_cross_codebase_cache_reuses_without_github_call(tmp_path) -> None:
    _store, _conn, context, client = _context(tmp_path)
    one = registry.invoke("add_codebase", context, {"owner": "o", "name": "one"}).result["codebase"]
    two = registry.invoke("add_codebase", context, {"owner": "o", "name": "two"}).result["codebase"]

    first = registry.invoke(
        "analyze_code",
        context,
        {"codebase_ids": [one["id"], two["id"]], "scope": "cross_codebase", "question": "how are they shaped?"},
    ).result
    calls_after_first = client.tree_calls
    second = registry.invoke(
        "analyze_code",
        context,
        {"codebase_ids": [two["id"], one["id"]], "scope": "cross_codebase", "question": "how are they shaped?"},
    ).result

    assert {row["codebase_id"] for row in first["analysis"]} == {one["id"], two["id"]}
    assert second["cache_hit"] is True
    assert client.tree_calls == calls_after_first


def test_deleted_repo_reports_failure_and_retains_cached_artifacts(tmp_path) -> None:
    _store, _conn, context, client = _context(tmp_path)
    codebase = registry.invoke("add_codebase", context, {"owner": "o", "name": "repo"}).result["codebase"]
    artifact = registry.invoke(
        "save_code_excerpt",
        context,
        {"codebase_id": codebase["id"], "content": "cached", "summary": "cached"},
    ).result["artifact"]

    client.tree = lambda owner, name, ref, path=None: {"ok": False, "error": {"type": "not_found", "message": "gone"}}
    result = registry.invoke("get_codebase_tree", context, {"codebase_id": codebase["id"]}).result

    assert result["ok"] is False
    assert result["cached_artifacts_retained"] is True
    assert context.store.load_code_artifact(artifact["id"]) is not None


def test_natural_language_loop_can_add_repo_with_fake_model(tmp_path, monkeypatch) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    fake_client = FakeGitHubClient()
    monkeypatch.setattr(code_tools, "GitHubClient", lambda store=None: fake_client)
    model = FakeModel(
        script=[
            {
                "tool_requests": [
                    tool_request("add_codebase", {"owner": "Owner", "name": "Repo"}),
                ],
                "provider_request_id": "req_1",
            },
            {"final_text": "added", "provider_request_id": "req_2"},
        ]
    )

    run_turn(epic_id="epic_1", input="add Owner/Repo", store=store, model=model, model_id="fake")
    names = [tool["name"] for tool in model.calls[0]["tools"]]
    assert "add_codebase" in names
    assert "analyze_code" in names
    assert store.find_codebase("owner", "repo") is not None
