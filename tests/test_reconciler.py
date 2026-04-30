from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agent_kit.ledger import Reconciler
from agent_kit.model import FakeModel
from agent_kit.ports import BlobRef
from tests.helpers import create_store, insert_epic


class FakeTransport:
    def __init__(self, messages):
        self.messages = messages

    def fetch_recent_messages(self, channel_id, since, until):
        return self.messages


class FakeBlob:
    def __init__(self, existing: set[str] | None = None):
        self.existing = existing or set()
        self.puts = []

    def put(self, epic_id, content, mime_type):
        ref = BlobRef(epic_id=epic_id, key=f"uploaded/{len(self.puts) + 1}", mime_type=mime_type)
        self.puts.append((epic_id, content, mime_type))
        self.existing.add(ref.key)
        return ref

    def get(self, ref):
        return b""

    def exists(self, ref):
        return ref.key in self.existing


class FakeGroq:
    def __init__(self):
        self.audio = self
        self.transcriptions = self
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        class Result:
            text = "transcribed"

        return Result()


def test_reconciler_marks_abandoned_turns_and_returns_trigger_ids(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    message = store.create_message(
        epic_id="epic_1",
        direction="inbound",
        content="hello",
        discord_message_id="discord_1",
    )
    turn = store.create_turn(epic_id="epic_1", triggered_by_message_ids=[message["id"]])
    conn.execute(
        "UPDATE bot_turns SET started_at = ? WHERE id = ?",
        (_old_timestamp(600), turn["id"]),
    )
    conn.commit()

    result = Reconciler(store).run_once()

    assert result["requeued_message_ids"] == [message["id"]]
    assert conn.execute("SELECT status FROM bot_turns").fetchone()["status"] == "abandoned"
    log = conn.execute("SELECT * FROM system_logs").fetchone()
    assert log["level"] == "warn"
    assert log["category"] == "recovery"
    assert log["event_type"] == "turn_abandoned"


def test_reconciler_replays_model_from_request_body_and_stored_key(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    model = FakeModel(script=[{"final_text": "ok", "provider_request_id": "req_1"}])
    row = store.insert_pending(
        idempotency_key="idem_model",
        provider="anthropic",
        endpoint="POST /v1/messages",
        request_summary={},
        request_body={
            "model": "fake",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [],
        },
        turn_id=None,
    )
    _age_request(conn, row["id"])

    Reconciler(store, model=model).run_once()

    assert model.calls[0]["idempotency_key"] == "idem_model"
    assert model.calls[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert conn.execute("SELECT status FROM external_requests").fetchone()["status"] == "confirmed"


def test_reconciler_matches_or_orphans_discord_requests(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    confirmed = store.insert_pending(
        idempotency_key="discord_confirmed",
        provider="discord",
        endpoint="POST /channels/c/messages",
        request_summary={"channel_id": "c", "content_preview": "hello"},
        request_body={"content": "hello"},
    )
    orphaned = store.insert_pending(
        idempotency_key="discord_orphaned",
        provider="discord",
        endpoint="POST /channels/c/messages",
        request_summary={"channel_id": "c", "content_preview": "missing"},
        request_body={"content": "missing"},
    )
    _age_request(conn, confirmed["id"])
    _age_request(conn, orphaned["id"])

    Reconciler(
        store,
        transport=FakeTransport(
            [{"discord_message_id": "discord_2", "content": "hello world"}]
        ),
    ).run_once()

    rows = {
        row["idempotency_key"]: row["status"]
        for row in conn.execute("SELECT idempotency_key, status FROM external_requests")
    }
    assert rows == {"discord_confirmed": "confirmed", "discord_orphaned": "orphaned"}


def test_reconciler_confirms_existing_storage_and_refetches_missing(monkeypatch, tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    existing = store.insert_pending(
        idempotency_key="storage_existing",
        provider="supabase_storage",
        endpoint="PUT images/x",
        request_summary={"epic_id": "epic_1"},
        request_body={"deterministic_path": "images/epic_1/existing.png"},
    )
    missing = store.insert_pending(
        idempotency_key="storage_missing",
        provider="supabase_storage",
        endpoint="PUT images/y",
        request_summary={"epic_id": "epic_1"},
        request_body={
            "deterministic_path": "images/epic_1/missing.png",
            "discord_attachment_url": "https://discord.example/file.png",
            "mime_type": "image/png",
        },
    )
    _age_request(conn, existing["id"])
    _age_request(conn, missing["id"])
    blob = FakeBlob(existing={"images/epic_1/existing.png"})

    class Response:
        content = b"image-bytes"

        def raise_for_status(self):
            pass

    monkeypatch.setattr("agent_kit.ledger.httpx.get", lambda *args, **kwargs: Response())

    Reconciler(store, blob=blob).run_once()

    statuses = [
        row["status"]
        for row in conn.execute("SELECT status FROM external_requests ORDER BY idempotency_key")
    ]
    assert statuses == ["confirmed", "confirmed"]
    assert blob.puts == [("epic_1", b"image-bytes", "image/png")]


def test_reconciler_orphans_storage_when_discord_url_expired(monkeypatch, tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    row = store.insert_pending(
        idempotency_key="storage_expired",
        provider="supabase_storage",
        endpoint="PUT audio/x",
        request_summary={"epic_id": "epic_1"},
        request_body={
            "deterministic_path": "audio/epic_1/a.ogg",
            "discord_attachment_url": "https://discord.example/expired.ogg",
        },
    )
    _age_request(conn, row["id"])

    def fail(*args, **kwargs):
        raise RuntimeError("expired")

    monkeypatch.setattr("agent_kit.ledger.httpx.get", fail)

    Reconciler(store, blob=FakeBlob()).run_once()

    external = conn.execute("SELECT status, error_details FROM external_requests").fetchone()
    assert external["status"] == "orphaned"
    log = conn.execute("SELECT category, event_type FROM system_logs").fetchone()
    assert (log["category"], log["event_type"]) == (
        "recovery",
        "storage_reconcile_orphaned",
    )


def test_reconciler_reissues_groq_from_stored_audio_url(tmp_path) -> None:
    store, conn = create_store(tmp_path / "arnold.db")
    insert_epic(conn)
    row = store.insert_pending(
        idempotency_key="groq_1",
        provider="groq",
        endpoint="POST /audio/transcriptions",
        request_summary={},
        request_body={"model": "whisper-large-v3", "audio_storage_url": "audio/path.ogg"},
    )
    _age_request(conn, row["id"])
    groq = FakeGroq()

    Reconciler(store, groq_client=groq).run_once()

    assert groq.calls == [{"model": "whisper-large-v3", "file": "audio/path.ogg"}]
    assert conn.execute("SELECT status FROM external_requests").fetchone()["status"] == "confirmed"


def _age_request(conn, request_id: str) -> None:
    conn.execute(
        "UPDATE external_requests SET last_attempted_at = ? WHERE id = ?",
        (_old_timestamp(120), request_id),
    )
    conn.commit()


def _old_timestamp(seconds: int) -> str:
    value = datetime.now(UTC) - timedelta(seconds=seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
