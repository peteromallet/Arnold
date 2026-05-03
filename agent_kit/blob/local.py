"""Local filesystem Blob adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from uuid import uuid4

from agent_kit.ports import BlobRef


class LocalBlobStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @classmethod
    def for_sqlite_db(cls, database: str | Path) -> "LocalBlobStore":
        path = Path(database)
        if str(database) == ":memory:":
            return cls(Path.cwd() / ".arnold-blobs")
        return cls(path.parent / f"{path.name}.blobs")

    def put(
        self,
        epic_id: str,
        content: bytes,
        mime_type: str,
        *,
        idempotency_key: str | None = None,
    ) -> BlobRef:
        key = _storage_key(epic_id, content, mime_type, idempotency_key)
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return BlobRef(
            epic_id=epic_id,
            key=key,
            mime_type=mime_type,
            size_bytes=len(content),
        )

    def get(self, ref: BlobRef) -> bytes:
        return self._path_for_key(ref.key).read_bytes()

    def exists(self, ref: BlobRef) -> bool:
        return self._path_for_key(ref.key).is_file()

    def _path_for_key(self, key: str) -> Path:
        normalized = PurePosixPath(key)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"invalid blob key: {key}")
        return self.root.joinpath(*normalized.parts)


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


__all__ = ["LocalBlobStore"]
