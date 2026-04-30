from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agent_kit.ledger import Reconciler
from agent_kit.model import FakeModel
from tests.helpers import create_store, insert_epic


def test_anthropic_replay_uses_stored_request_body_and_idempotency_key(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    model = FakeModel(script=[{"final_text": "ok", "provider_request_id": "anthropic_req_1"}])
    row = store.insert_pending(
        idempotency_key="idem_anthropic_1",
        provider="anthropic",
        endpoint="POST /v1/messages",
        request_summary={"system_seq": 7},
        request_body={
            "model": "fake-replay",
            "system": "stored system prompt",
            "messages": [{"role": "user", "content": "stored prompt"}],
            "tools": [{"name": "send_message", "schema": {"type": "object"}}],
            "max_tokens": 1024,
        },
    )
    conn.execute(
        "UPDATE external_requests SET last_attempted_at = ? WHERE id = ?",
        (_old_timestamp(120), row["id"]),
    )
    conn.commit()

    Reconciler(store, model=model).run_once()

    assert model.calls[0]["model_id"] == "fake-replay"
    assert model.calls[0]["system"] == "stored system prompt"
    assert model.calls[0]["idempotency_key"] == "idem_anthropic_1"
    assert model.calls[0]["messages"] == [{"role": "user", "content": "stored prompt"}]
    assert model.calls[0]["tools"] == [
        {"name": "send_message", "schema": {"type": "object"}}
    ]
    request = conn.execute("SELECT * FROM external_requests").fetchone()
    assert request["status"] == "confirmed"
    assert request["provider_request_id"] == "anthropic_req_1"


def _old_timestamp(seconds: int) -> str:
    value = datetime.now(UTC) - timedelta(seconds=seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
