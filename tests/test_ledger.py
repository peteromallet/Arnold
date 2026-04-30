from __future__ import annotations

import hashlib
import json

from agent_kit.ledger import derive_idempotency_key
from agent_kit.loop import (
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MESSAGES_ENDPOINT,
    run_turn,
)
from agent_kit.model import FakeModel
from agent_kit.ports import ProviderError
from tests.helpers import create_store, insert_epic


def test_idempotency_key_formulas(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[])
    tool_call = store.record_tool_call(
        turn_id=turn["id"],
        tool_name="send_message",
        operation_kind="write",
        arguments={"content": "hi"},
        result={"value": "inv_1"},
        duration_ms=1,
    )
    request_summary = {"b": 2, "a": 1}
    canonical = json.dumps(request_summary, sort_keys=True, separators=(",", ":"))
    expected_tool = hashlib.sha256(
        f"{turn['id']}:{tool_call['id']}:discord:POST /x:{canonical}".encode()
    ).hexdigest()[:16]
    assert (
        derive_idempotency_key(
            provider="discord",
            endpoint="POST /x",
            request_summary=request_summary,
            turn_id=turn["id"],
            tool_call_id=tool_call["id"],
        )
        == expected_tool
    )

    key_1 = derive_idempotency_key(
        provider="anthropic",
        endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
        request_summary={},
        turn_id=turn["id"],
        system_seq=1,
    )
    key_2 = derive_idempotency_key(
        provider="anthropic",
        endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
        request_summary={},
        turn_id=turn["id"],
        system_seq=2,
    )
    expected_system = hashlib.sha256(
        f"{turn['id']}:system:anthropic:{ANTHROPIC_MESSAGES_ENDPOINT}:1".encode()
    ).hexdigest()[:16]
    assert key_1 == expected_system
    assert key_1 != key_2


def test_ledger_lifecycle_success_single_call(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    model = FakeModel(
        script=[
            {
                "final_text": "done",
                "provider_request_id": "req_1",
                "response_summary": {"kind": "final"},
            }
        ]
    )
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=model,
        model_id="fake",
    )
    assert envelope.outcome == "completed"
    turn_id = envelope.turn_id
    row = conn.execute("SELECT * FROM external_requests").fetchone()
    assert row["tool_call_id"] is None
    assert row["provider"] == "anthropic"
    assert row["endpoint"] == ANTHROPIC_MESSAGES_ENDPOINT
    assert row["turn_id"] == turn_id
    assert row["status"] == "confirmed"
    assert row["provider_request_id"] == "req_1"
    assert row["idempotency_key"] == derive_idempotency_key(
        provider="anthropic",
        endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
        request_summary={},
        turn_id=turn_id,
        system_seq=1,
    )
    request_summary = json.loads(row["request_summary"])
    request_body = json.loads(row["request_body"])
    assert request_summary["system_seq"] == 1
    assert request_body["model"] == "fake"
    assert request_body["messages"] == [{"role": "user", "content": "hello"}]
    assert request_body["max_tokens"] == ANTHROPIC_MAX_TOKENS
    assert [tool["name"] for tool in request_body["tools"]]
    assert model_idempotency_keys(model) == [row["idempotency_key"]]


def model_idempotency_keys(model: FakeModel) -> list[str | None]:
    return [call["idempotency_key"] for call in model.calls]


def test_ledger_lifecycle_tool_use_chaining(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(
            script=[
                {
                    "tool_requests": [
                        {
                            "name": "set_activity",
                            "arguments": {"description": "drafting"},
                        }
                    ],
                    "provider_request_id": "req_1",
                    "response_summary": {"step": 1},
                },
                {
                    "final_text": "done",
                    "provider_request_id": "req_2",
                    "response_summary": {"step": 2},
                },
            ]
        ),
        model_id="fake",
    )
    assert envelope.outcome == "completed"
    rows = conn.execute(
        "SELECT * FROM external_requests ORDER BY first_attempted_at, id"
    ).fetchall()
    assert [row["status"] for row in rows] == ["confirmed", "confirmed"]
    assert [row["provider_request_id"] for row in rows] == ["req_1", "req_2"]
    assert rows[0]["idempotency_key"] != rows[1]["idempotency_key"]
    assert {
        row["idempotency_key"] for row in rows
    } == {
        derive_idempotency_key(
            provider="anthropic",
            endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
            request_summary={},
            turn_id=envelope.turn_id,
            system_seq=1,
        ),
        derive_idempotency_key(
            provider="anthropic",
            endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
            request_summary={},
            turn_id=envelope.turn_id,
            system_seq=2,
        ),
    }


def test_ledger_provider_error_marks_failed(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(
            script=[
                ProviderError(
                    error_details={"code": "bad_request"},
                    provider_request_id="req_bad",
                )
            ]
        ),
        model_id="fake",
    )
    assert envelope.outcome == "errored"
    row = conn.execute("SELECT * FROM external_requests").fetchone()
    assert row["status"] == "failed"
    assert json.loads(row["error_details"])["code"] == "bad_request"
    assert row["completed_at"] is not None


def test_ledger_runtime_error_leaves_pending(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    envelope = run_turn(
        epic_id="epic_1",
        input="hello",
        store=store,
        model=FakeModel(script=[RuntimeError("network down")]),
        model_id="fake",
    )
    assert envelope.outcome == "errored"
    row = conn.execute("SELECT * FROM external_requests").fetchone()
    assert row["status"] == "pending"
    assert row["error_details"] is None
    assert row["completed_at"] is None
