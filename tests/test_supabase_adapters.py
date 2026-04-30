from __future__ import annotations

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
