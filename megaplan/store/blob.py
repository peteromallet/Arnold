"""Blob storage protocol and file-mode seam."""

from __future__ import annotations

from datetime import UTC, datetime
import mimetypes
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import Field

from megaplan._core.io import commit_journal_transaction, journal_blob_promotion, prepare_journal_transaction
from megaplan.schemas import StorageModel, utc_now


class BlobMissingError(FileNotFoundError):
    """Raised when a blob cannot be loaded from the backing store."""


class BlobRef(StorageModel):
    blob_id: str
    content_type: str
    size_bytes: int | None = None
    storage_url: str | None = None


class BlobStat(StorageModel):
    blob_id: str
    content_type: str
    size_bytes: int
    updated_at: datetime = Field(default_factory=utc_now)


@runtime_checkable
class BlobStore(Protocol):
    """Backend-agnostic blob storage contract."""

    def put(self, blob_id: str, content: bytes, *, content_type: str) -> BlobRef:
        ...

    def get(self, blob_id: str) -> bytes:
        ...

    def url(self, blob_id: str, *, signed: bool = False, ttl: int = 3600) -> str:
        ...

    def delete(self, blob_id: str) -> None:
        ...

    def stat(self, blob_id: str) -> BlobStat | None:
        ...


class LocalDirBlobStore:
    """Filesystem blob store seam.

    Blob contents live at ``<root>/<blob-id>/data.<ext>`` with metadata in
    ``meta.json``. Writes use the shared journal blob-promotion helpers so the
    file mode semantics match FileStore's staging rules.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _blob_dir(self, blob_id: str) -> Path:
        return self.root / blob_id

    def _find_data_path(self, blob_id: str) -> Path | None:
        blob_dir = self._blob_dir(blob_id)
        if not blob_dir.exists():
            return None
        candidates = [
            path
            for path in sorted(blob_dir.glob("data.*"))
            if path.is_file() and not path.name.endswith(".staging")
        ]
        return candidates[0] if candidates else None

    def _meta_path(self, blob_id: str) -> Path:
        return self._blob_dir(blob_id) / "meta.json"

    def _extension_for_content_type(self, content_type: str) -> str:
        guessed = mimetypes.guess_extension(content_type, strict=False) or ".bin"
        return guessed.lstrip(".")

    def put(self, blob_id: str, content: bytes, *, content_type: str) -> BlobRef:
        extension = self._extension_for_content_type(content_type)
        blob_dir = self._blob_dir(blob_id)
        metadata = {
            "blob_id": blob_id,
            "content_type": content_type,
            "size_bytes": len(content),
            "updated_at": utc_now().isoformat().replace("+00:00", "Z"),
        }
        tx_id = f"blob-{blob_id}"
        prepare_journal_transaction(
            self.root,
            tx_id,
            blobs=[journal_blob_promotion(blob_dir, content, extension=extension, metadata=metadata)],
        )
        commit_journal_transaction(self.root, tx_id)
        return BlobRef(
            blob_id=blob_id,
            content_type=content_type,
            size_bytes=len(content),
            storage_url=str(self._find_data_path(blob_id)),
        )

    def get(self, blob_id: str) -> bytes:
        data_path = self._find_data_path(blob_id)
        if data_path is None:
            raise BlobMissingError(blob_id)
        return data_path.read_bytes()

    def url(self, blob_id: str, *, signed: bool = False, ttl: int = 3600) -> str:
        del signed, ttl
        data_path = self._find_data_path(blob_id)
        if data_path is None:
            raise BlobMissingError(blob_id)
        return str(data_path)

    def delete(self, blob_id: str) -> None:
        blob_dir = self._blob_dir(blob_id)
        if not blob_dir.exists():
            return
        import shutil

        shutil.rmtree(blob_dir)

    def stat(self, blob_id: str) -> BlobStat | None:
        meta_path = self._meta_path(blob_id)
        data_path = self._find_data_path(blob_id)
        if data_path is None:
            return None
        if meta_path.exists():
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            updated_at = datetime.fromisoformat(meta["updated_at"].replace("Z", "+00:00"))
            return BlobStat(
                blob_id=blob_id,
                content_type=meta["content_type"],
                size_bytes=meta.get("size_bytes", data_path.stat().st_size),
                updated_at=updated_at,
            )
        guessed_type = mimetypes.guess_type(str(data_path))[0] or "application/octet-stream"
        return BlobStat(
            blob_id=blob_id,
            content_type=guessed_type,
            size_bytes=data_path.stat().st_size,
            updated_at=datetime.fromtimestamp(data_path.stat().st_mtime, tz=UTC),
        )


__all__ = [
    "BlobMissingError",
    "BlobRef",
    "BlobStat",
    "BlobStore",
    "LocalDirBlobStore",
]
