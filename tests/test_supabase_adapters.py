from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import arnold.cli as cli
from agent_kit.blob.supabase_storage import SupabaseStorageBlob
from agent_kit.store import supabase as supabase_store


def test_supabase_store_from_env_uses_db_url(monkeypatch) -> None:
    captured = {}

    class FakeConnection:
        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://example/db")
    monkeypatch.setattr(
        supabase_store,
        "_connect",
        lambda dsn: captured.setdefault("dsn", dsn) and FakeConnection(),
    )

    store = supabase_store.SupabaseStore.from_env()
    assert captured["dsn"] == "postgresql://example/db"
    store.close()
    assert captured["closed"] is True


def test_supabase_storage_blob_paths_and_exists(monkeypatch) -> None:
    uploaded = {}

    class FakeBucket:
        def upload(self, key, content, *, file_options):
            uploaded.update(key=key, content=content, options=file_options)

        def download(self, key):
            return b"stored:" + key.encode()

    class FakeStorage:
        def from_(self, bucket):
            uploaded["bucket"] = bucket
            return FakeBucket()

    blob = SupabaseStorageBlob(
        url="https://project.supabase.co",
        service_key="service-key",
        bucket="attachments",
        client=SimpleNamespace(storage=FakeStorage()),
    )

    ref = blob.put("folder/epic_1", b"image-bytes", "image/png", idempotency_key="idem")
    assert ref.key == "images/epic_1/idem.png"
    assert uploaded == {
        "bucket": "attachments",
        "key": "images/epic_1/idem.png",
        "content": b"image-bytes",
        "options": {"content-type": "image/png", "upsert": "true"},
    }
    assert blob.get(ref) == b"stored:images/epic_1/idem.png"

    monkeypatch.setattr(
        "agent_kit.blob.supabase_storage.httpx.head",
        lambda url, headers, timeout: SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            url=url,
            headers=headers,
            timeout=timeout,
        ),
    )
    assert blob.exists(ref) is True


def test_cli_has_resident_subcommand_and_supabase_store_builder() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["resident", "--model-id", "fake"])
    assert args.command == "resident"
    assert args.model_id == "fake"
    assert not hasattr(cli, "_unsupported_store_envelope")


def test_supabase_feedback_migration_schema_matches_sprint_2b_contract() -> None:
    migration = Path("supabase/migrations/202604300005_005_feedback.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS feedback" in migration
    assert "context_snapshot JSONB" in migration
    assert "active BOOLEAN NOT NULL DEFAULT true" in migration
    assert "resolved BOOLEAN NOT NULL DEFAULT false" in migration
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT now()" in migration
    assert "last_referenced_at TIMESTAMPTZ" in migration
    assert "last_applied_at TIMESTAMPTZ" in migration
    assert "source_message_id TEXT REFERENCES messages(id) ON DELETE SET NULL" in migration
    assert "epic_id TEXT REFERENCES epics(id) ON DELETE CASCADE" in migration
    assert "turn_id TEXT REFERENCES bot_turns(id) ON DELETE SET NULL" in migration
    assert "kind IN ('style', 'process', 'epic_specific')" in migration
    assert "source = 'agent_observation'" in migration
    assert "idx_feedback_active_global_kind_created" in migration
    assert "idx_feedback_epic_active_kind_created" in migration
    assert "idx_feedback_unresolved_observations_created" in migration


def test_supabase_feedback_adapter_queries_and_hot_context() -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.queries = []

        def execute(self, sql, params=()):
            self.queries.append((sql, params))
            if "SELECT * FROM feedback WHERE id = %s" in sql:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "id": params[0],
                        "kind": "style",
                        "content": "Keep it short.",
                        "source": "explicit_save_request",
                        "context_snapshot": {"ok": True},
                        "active": True,
                        "resolved": False,
                    }
                )
            if "SELECT * FROM epics WHERE id = %s" in sql:
                return SimpleNamespace(fetchone=lambda: {"id": params[0], "title": "T"})
            return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])

    conn = FakeConnection()
    store = supabase_store.SupabaseStore(connection=conn)

    created = store.create_feedback(
        kind="style",
        content="Keep it short.",
        source="explicit_save_request",
        context_snapshot={"ok": True},
    )
    assert created["id"].startswith("fb_")
    store.update_feedback(created["id"], last_applied_at="2026-04-30T12:00:00Z")
    no_epic_context = store.load_hot_context(None)
    epic_context = store.load_hot_context("epic_1")

    assert no_epic_context["epic"] is None
    assert no_epic_context["recent_messages"] == []
    assert no_epic_context["recent_tool_calls"] == []
    assert epic_context["epic"]["id"] == "epic_1"
    assert any("INSERT INTO feedback" in sql for sql, _params in conn.queries)
    assert any("UPDATE feedback SET last_applied_at = %s" in sql for sql, _params in conn.queries)
    assert any("SELECT * FROM feedback WHERE" in sql and "ORDER BY created_at DESC" in sql for sql, _params in conn.queries)
