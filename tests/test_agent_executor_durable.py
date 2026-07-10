from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent.executor_durable import maybe_write_executor_only_durable_turn


def test_executor_durable_module_import_does_not_load_routes_edit_or_executor_core() -> None:
    code = """
import sys
import vibecomfy.comfy_nodes.agent.executor_durable
assert "vibecomfy.comfy_nodes.agent.routes" not in sys.modules
assert "vibecomfy.comfy_nodes.agent.edit" not in sys.modules
assert "vibecomfy.executor.core" not in sys.modules
"""

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_applyable_executor_response_keeps_handle_agent_edit_durable_artifacts_delegated(tmp_path) -> None:
    calls: list[dict] = []
    response = {
        "ok": True,
        "route": "revise",
        "session_id": "sess-edit",
        "turn_id": "0001",
        "artifacts": {"response": "response.json", "chat": "chat.json"},
    }

    def fail_allocate_turn(**kwargs):
        calls.append(kwargs)
        raise AssertionError("applyable routes must not allocate executor-only durable turns")

    stamped = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={"query": "make it brighter", "session_id": "sess-edit"},
        request=SimpleNamespace(query="make it brighter", graph={"nodes": []}),
        session_root=tmp_path,
        allocate_turn_func=fail_allocate_turn,
    )

    assert stamped is response
    assert calls == []
    assert not any(tmp_path.rglob("request.json"))
    assert not any(tmp_path.rglob("response.json"))
    assert not any(tmp_path.rglob("chat.json"))


def test_non_applyable_executor_response_writes_request_response_and_chat(tmp_path) -> None:
    request = SimpleNamespace(
        query="what does this workflow do?",
        graph={"nodes": [{"id": 1, "type": "LoadImage"}], "links": []},
    )
    response = {
        "ok": True,
        "route": "inspect",
        "reply": "It loads an image and previews it.",
        "message": "It loads an image and previews it.",
        "outcome": {"kind": "noop"},
    }

    stamped = maybe_write_executor_only_durable_turn(
        response=response,
        result=None,
        payload={"query": request.query, "graph": request.graph, "session_id": "durable-test"},
        request=request,
        session_root=tmp_path,
    )

    session_id = stamped["session_id"]
    turn_id = stamped["turn_id"]
    turn_dir = tmp_path / session_id / "turns" / turn_id
    request_payload = json.loads((turn_dir / "request.json").read_text(encoding="utf-8"))
    response_payload = json.loads((turn_dir / "response.json").read_text(encoding="utf-8"))
    chat_payload = json.loads((turn_dir / "chat.json").read_text(encoding="utf-8"))

    assert request_payload == {
        "query": request.query,
        "task": request.query,
        "session_id": session_id,
        "graph": request.graph,
    }
    assert response_payload["session_id"] == session_id
    assert response_payload["turn_id"] == turn_id
    assert response_payload["route"] == "inspect"
    assert response_payload["reply"] == response["reply"]
    assert response_payload["apply_eligible"] is False
    assert response_payload["graph_unchanged"] is True
    assert response_payload["no_candidate_reason"] == "route_not_applyable"
    assert chat_payload["session_id"] == session_id
    assert chat_payload["turn_id"] == turn_id
    assert chat_payload["route"] == "inspect"
    assert chat_payload["messages"][0]["text"] == request.query
    assert chat_payload["messages"][1]["text"] == response["reply"]
