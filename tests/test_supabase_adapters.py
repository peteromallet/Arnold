from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import arnold.cli as cli
from agent_kit.blob import LocalBlobStore, SupabaseStorageBlob
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


def test_local_blob_store_put_get_exists_and_rejects_unsafe_keys(tmp_path) -> None:
    blob = LocalBlobStore(tmp_path / "blobs")

    ref = blob.put("folder/epic_1", b"image-bytes", "image/webp", idempotency_key="idem")

    assert ref.key == "images/epic_1/idem.webp"
    assert ref.mime_type == "image/webp"
    assert ref.size_bytes == len(b"image-bytes")
    assert blob.exists(ref) is True
    assert blob.get(ref) == b"image-bytes"

    unsafe = SimpleNamespace(key="../escape", epic_id="epic_1", mime_type="image/png")
    try:
        blob.exists(unsafe)
    except ValueError as exc:
        assert "invalid blob key" in str(exc)
    else:
        raise AssertionError("unsafe blob key was accepted")


def test_cli_blob_selection_uses_local_for_sqlite_and_supabase_only_when_needed(
    tmp_path,
    monkeypatch,
) -> None:
    sqlite_args = SimpleNamespace(store="sqlite", db=str(tmp_path / "arnold.db"))
    sqlite_blob = cli._build_blob(sqlite_args)
    assert isinstance(sqlite_blob, LocalBlobStore)
    assert sqlite_blob.root == tmp_path / "arnold.db.blobs"

    created = object()
    monkeypatch.setattr(
        SupabaseStorageBlob,
        "from_env",
        classmethod(lambda cls: created),
    )
    supabase_args = SimpleNamespace(store="supabase", db=str(tmp_path / "ignored.db"))

    assert cli._build_blob(supabase_args) is None
    assert cli._build_blob(supabase_args, attachments_present=True) is created


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


def test_supabase_sprint_migration_schema_matches_sprint_4_contract() -> None:
    migration = Path("supabase/migrations/202604300006_006_sprints.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS sprints" in migration
    assert "CREATE TABLE IF NOT EXISTS sprint_items" in migration
    assert "epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE" in migration
    assert "sprint_number INTEGER NOT NULL CHECK (sprint_number > 0)" in migration
    assert "status TEXT NOT NULL CHECK (status IN ('proposed', 'queued', 'pending', 'done'))" in migration
    assert "queue_position INTEGER CHECK (queue_position IS NULL OR queue_position > 0)" in migration
    assert "pending_reason TEXT" in migration
    assert "target_weeks INTEGER NOT NULL DEFAULT 2 CHECK (target_weeks > 0)" in migration
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT now()" in migration
    assert "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()" in migration
    assert "queued_at TIMESTAMPTZ" in migration
    assert "CHECK (status != 'queued' OR queue_position IS NOT NULL)" in migration
    assert "CHECK (status != 'pending' OR pending_reason IS NOT NULL)" in migration
    assert "CHECK (status = 'queued' OR queue_position IS NULL)" in migration
    assert "sprint_id TEXT NOT NULL REFERENCES sprints(id) ON DELETE CASCADE" in migration
    assert (
        "estimated_complexity TEXT NOT NULL CHECK (estimated_complexity IN ('small', 'medium', 'large'))"
        in migration
    )
    assert "status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'done'))" in migration
    assert "source_section TEXT" in migration
    assert "position INTEGER NOT NULL CHECK (position > 0)" in migration
    assert "idx_sprints_epic_sprint_number" in migration
    assert "idx_sprints_epic_status" in migration
    assert "idx_sprints_epic_queued_position" in migration
    assert "ON sprints (epic_id, queue_position)" in migration
    assert "WHERE status = 'queued'" in migration
    assert "idx_sprint_items_sprint_position" in migration


def test_supabase_second_opinions_migration_schema_matches_sprint_6_contract() -> None:
    migration = Path("supabase/migrations/202604300008_008_second_opinions.sql").read_text()

    assert "CREATE TABLE IF NOT EXISTS second_opinions" in migration
    assert "epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE" in migration
    assert "requested_at TIMESTAMPTZ NOT NULL DEFAULT now()" in migration
    assert "requested_by TEXT NOT NULL CHECK (requested_by IN ('user', 'auto_state_gate'))" in migration
    assert "focus_areas JSONB NOT NULL DEFAULT '[]'::jsonb" in migration
    assert "raw_response TEXT NOT NULL" in migration
    assert "score INTEGER NOT NULL CHECK (score >= 0 AND score <= 10)" in migration
    assert "summary TEXT NOT NULL" in migration
    assert "verdict TEXT NOT NULL" in migration
    assert "resulting_checklist_item_ids JSONB NOT NULL DEFAULT '[]'::jsonb" in migration
    assert "model_used TEXT NOT NULL" in migration
    assert "idx_second_opinions_epic_requested_at" in migration
    assert "ON second_opinions (epic_id, requested_at DESC)" in migration
    assert "idx_second_opinions_score" in migration


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


def test_supabase_second_opinion_and_active_image_adapter_queries() -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.queries = []

        def execute(self, sql, params=()):
            self.queries.append((sql, params))
            if "SELECT * FROM images WHERE epic_id = %s AND reference_key = %s AND active = true" in sql:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "id": "img_1",
                        "epic_id": params[0],
                        "reference_key": params[1],
                        "active": True,
                        "storage_url": "images/epic_1/flow.png",
                    },
                    fetchall=lambda: [
                        {
                            "id": "img_1",
                            "epic_id": params[0],
                            "reference_key": params[1],
                            "active": True,
                            "storage_url": "images/epic_1/flow.png",
                        }
                    ],
                )
            if "SELECT 1 FROM images WHERE epic_id = %s" in sql:
                return SimpleNamespace(fetchone=lambda: {"?column?": 1})
            if "SELECT * FROM second_opinions WHERE id = %s" in sql:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "id": params[0],
                        "epic_id": "epic_1",
                        "requested_by": "user",
                        "focus_areas": ["handoff"],
                        "raw_response": "Score: 7/10",
                        "score": 7,
                        "summary": "Good shape.",
                        "verdict": "mostly ready",
                        "resulting_checklist_item_ids": ["item_1"],
                        "model_used": "gpt-5.5",
                    }
                )
            if "SELECT * FROM second_opinions WHERE epic_id = %s" in sql:
                return SimpleNamespace(
                    fetchall=lambda: [
                        {
                            "id": "opinion_1",
                            "epic_id": params[0],
                            "requested_by": "user",
                            "focus_areas": ["handoff"],
                            "score": 7,
                            "summary": "Good shape.",
                            "verdict": "mostly ready",
                            "resulting_checklist_item_ids": [],
                            "model_used": "gpt-5.5",
                        }
                    ]
                )
            return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])

    conn = FakeConnection()
    store = supabase_store.SupabaseStore(connection=conn)

    assert store.active_image_reference_exists("epic_1", "img_flow") is True
    assert store.load_active_image_by_reference("epic_1", "img_flow")["id"] == "img_1"
    assert store.deactivate_active_image_reference("epic_1", "img_flow")[0]["id"] == "img_1"
    opinion = store.create_second_opinion(
        epic_id="epic_1",
        requested_by="user",
        focus_areas=["handoff"],
        raw_response="Score: 7/10",
        score=7,
        summary="Good shape.",
        verdict="mostly ready",
        model_used="gpt-5.5",
    )
    linked = store.set_second_opinion_checklist_items(opinion["id"], ["item_1"])

    assert linked["resulting_checklist_item_ids"] == ["item_1"]
    assert store.list_second_opinions("epic_1", limit=2)[0]["id"] == "opinion_1"
    assert any("INSERT INTO second_opinions" in sql for sql, _params in conn.queries)
    assert any("UPDATE images SET active = false" in sql for sql, _params in conn.queries)
    assert any("UPDATE second_opinions SET resulting_checklist_item_ids" in sql for sql, _params in conn.queries)


def test_supabase_sprint_adapter_queries_and_items() -> None:
    class FakeTransaction:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def __init__(self) -> None:
            self.queries = []

        def transaction(self):
            return FakeTransaction()

        def execute(self, sql, params=()):
            self.queries.append((sql, params))
            if "SELECT * FROM sprints WHERE id = %s" in sql:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "id": params[0],
                        "epic_id": "epic_1",
                        "sprint_number": 1,
                        "name": "Sprint 1",
                        "goal": "Goal",
                        "status": "queued",
                        "queue_position": 1,
                    }
                )
            if "SELECT * FROM sprint_items WHERE id = %s" in sql:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "id": params[0],
                        "sprint_id": "sprint_1",
                        "content": "PM-level task",
                        "estimated_complexity": "medium",
                        "status": "open",
                        "position": 1,
                    }
                )
            if "SELECT * FROM sprints WHERE epic_id = %s" in sql:
                return SimpleNamespace(
                    fetchall=lambda: [
                        {
                            "id": "sprint_1",
                            "epic_id": params[0],
                            "sprint_number": 1,
                            "name": "Sprint 1",
                            "goal": "Goal",
                            "status": "queued",
                            "queue_position": 1,
                        }
                    ]
                )
            if "SELECT * FROM sprint_items WHERE sprint_id = %s" in sql:
                return SimpleNamespace(
                    fetchall=lambda: [
                        {
                            "id": "item_1",
                            "sprint_id": params[0],
                            "content": "PM-level task",
                            "estimated_complexity": "medium",
                            "status": "open",
                            "position": 1,
                        }
                    ]
                )
            return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])

    conn = FakeConnection()
    store = supabase_store.SupabaseStore(connection=conn)

    sprint = store.create_sprint(
        epic_id="epic_1",
        sprint_number=1,
        name="Sprint 1",
        goal="Goal",
        status="queued",
        queue_position=1,
    )
    items = store.replace_sprint_items(
        sprint["id"],
        [{"content": "PM-level task", "estimated_complexity": "medium"}],
    )
    loaded = store.list_sprints_with_items("epic_1")

    assert sprint["id"].startswith("sprint_")
    assert items[0]["id"].startswith("sitem_")
    assert loaded[0]["items"][0]["content"] == "PM-level task"
    assert any("INSERT INTO sprints" in sql for sql, _params in conn.queries)
    assert any("INSERT INTO sprint_items" in sql for sql, _params in conn.queries)
    assert any("DELETE FROM sprint_items WHERE sprint_id = %s" in sql for sql, _params in conn.queries)
