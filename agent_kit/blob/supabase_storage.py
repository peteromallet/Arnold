"""Supabase Storage Blob adapter."""

from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath
from uuid import uuid4

import httpx

from agent_kit.ports import BlobRef


class SupabaseStorageBlob:
    def __init__(
        self,
        *,
        url: str | None = None,
        service_key: str | None = None,
        bucket: str | None = None,
        client=None,
    ) -> None:
        self.url = (url or os.environ["SUPABASE_URL"]).rstrip("/")
        self.service_key = service_key or os.environ["SUPABASE_SERVICE_KEY"]
        self.bucket = bucket or os.environ.get("SUPABASE_STORAGE_BUCKET", "arnold")
        self._client = client

    @classmethod
    def from_env(cls) -> "SupabaseStorageBlob":
        return cls()

    def put(
        self,
        epic_id: str,
        content: bytes,
        mime_type: str,
        *,
        idempotency_key: str | None = None,
    ) -> BlobRef:
        key = _storage_key(epic_id, content, mime_type, idempotency_key)
        self._bucket().upload(
            key,
            content,
            file_options={"content-type": mime_type, "upsert": "true"},
        )
        return BlobRef(
            epic_id=epic_id,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
        )

    def get(self, ref: BlobRef) -> bytes:
        return self._bucket().download(ref.key)

    def exists(self, ref: BlobRef) -> bool:
        response = httpx.head(
            f"{self.url}/storage/v1/object/{self.bucket}/{ref.key}",
            headers={
                "apikey": self.service_key,
                "authorization": f"Bearer {self.service_key}",
            },
            timeout=30,
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def _bucket(self):
        return self._supabase().storage.from_(self.bucket)

    def _supabase(self):
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise RuntimeError("supabase-py is required for SupabaseStorageBlob") from exc
            self._client = create_client(self.url, self.service_key)
        return self._client


def _storage_key(
    epic_id: str,
    content: bytes,
    mime_type: str,
    idempotency_key: str | None,
) -> str:
    stable = idempotency_key or hashlib.sha256(content).hexdigest()[:16] or uuid4().hex
    safe_epic = PurePosixPath(epic_id).name
    if mime_type.startswith("audio/"):
        return f"audio/{safe_epic}/{stable}.ogg"
    return f"images/{safe_epic}/{stable}{_image_ext(mime_type)}"


def _image_ext(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(mime_type, ".bin")


__all__ = ["SupabaseStorageBlob"]
