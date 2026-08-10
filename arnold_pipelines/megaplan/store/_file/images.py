from __future__ import annotations

import hashlib
import mimetypes
from typing import Any

from arnold_pipelines.megaplan.schemas import Image
from arnold_pipelines.megaplan.schemas.base import utc_now

from .common import _SOURCE_REFERENCE_PREFIX, _new_id


class FileImageMixin:
    def _next_image_reference(self, source: str) -> str:
        prefix = _SOURCE_REFERENCE_PREFIX.get(source, f"img_{source}")
        count = sum(1 for row in self._images() if row.source == source)
        return f"{prefix}_{count + 1}"

    def create_image(
        self,
        *,
        epic_id: str,
        source: str,
        storage_url: str,
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        reference_key: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = False,
        active: bool = True,
        discord_attachment_id: str | None = None,
        blob_backend: str | None = None,
        blob_id: str | None = None,
        blob_sha256: str | None = None,
        blob_size_bytes: int | None = None,
        content_type: str | None = None,
        idempotency_key: str | None = None,
    ) -> Image:
        ref = reference_key or self._next_image_reference(source)
        if active:
            self.deactivate_active_image_reference(epic_id, ref)
        image = Image(
            id=_new_id("img"),
            epic_id=epic_id,
            source=source,
            prompt=prompt,
            storage_url=storage_url,
            quality=quality,
            size=size,
            created_at=utc_now(),
            reference_key=ref,
            description=description,
            caption=caption,
            in_body=in_body,
            active=active,
            discord_attachment_id=discord_attachment_id,
            blob_backend=blob_backend,
            blob_id=blob_id,
            blob_sha256=blob_sha256,
            blob_size_bytes=blob_size_bytes,
            content_type=content_type,
        )
        self._save_model(self._image_path(image.id), image, journal_root=self.root)
        return image

    def attach_image(
        self,
        *,
        epic_id: str,
        content: bytes,
        content_type: str,
        reference_key: str,
        source: str = "user_uploaded",
        prompt: str | None = None,
        quality: str | None = None,
        size: str | None = None,
        description: str | None = None,
        caption: str | None = None,
        in_body: bool = True,
        idempotency_key: str | None = None,
    ) -> Image:
        digest = hashlib.sha256(content).hexdigest()
        blob_id = f"{epic_id}/{reference_key}/{digest}"
        with self.transaction(epic_id):
            extension = (mimetypes.guess_extension(content_type, strict=False) or ".bin").lstrip(".")
            blob_dir = self.blobs._blob_dir(blob_id)
            metadata = {
                "blob_id": blob_id,
                "content_type": content_type,
                "size_bytes": len(content),
                "updated_at": utc_now().isoformat().replace("+00:00", "Z"),
            }
            self._commit_blob(
                blob_dir,
                content,
                extension=extension,
                metadata=metadata,
                journal_root=self._journal_root_for_epic(epic_id),
            )
            return self.create_image(
                epic_id=epic_id,
                source=source,
                storage_url=str(blob_dir / f"data.{extension}"),
                prompt=prompt,
                quality=quality,
                size=size,
                reference_key=reference_key,
                description=description,
                caption=caption,
                in_body=in_body,
                active=True,
                blob_backend="file",
                blob_id=blob_id,
                blob_sha256=digest,
                blob_size_bytes=len(content),
                content_type=content_type,
                idempotency_key=idempotency_key,
            )

    def resolve_image_reference(
        self,
        epic_id: str,
        reference: str,
        *,
        signed: bool = False,
        ttl: int = 3600,
    ) -> str | None:
        key = reference.removeprefix("mp://image/").removeprefix("image:")
        image = self.load_active_image_by_reference(epic_id, key)
        if image is None:
            return None
        if image.blob_id:
            return self.blobs.url(image.blob_id, signed=signed, ttl=ttl)
        return image.storage_url

    def load_image(self, image_id: str) -> Image | None:
        return self._load_model(self._image_path(image_id), Image)

    def list_images(self, *, epic_id: str, source: str | None = None, active: bool | None = True) -> list[Image]:
        images = [row for row in self._images() if row.epic_id == epic_id]
        if source is not None:
            images = [row for row in images if row.source == source]
        if active is not None:
            images = [row for row in images if row.active == active]
        images.sort(key=lambda row: (row.created_at, row.id))
        return images

    def update_image(self, image_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> Image:
        if changes.get("active") and changes.get("reference_key"):
            epic_id = changes.get("epic_id") or (self.load_image(image_id).epic_id if self.load_image(image_id) else None)
            if epic_id:
                self.deactivate_active_image_reference(epic_id, changes["reference_key"])
        return self._update_model(self._image_path(image_id), Image, journal_root=self.root, **changes)

    def list_active_images(self, epic_id: str) -> list[Image]:
        return self.list_images(epic_id=epic_id, active=True)

    def load_active_image_by_reference(self, epic_id: str, reference_key: str) -> Image | None:
        for image in self.list_active_images(epic_id):
            if image.reference_key == reference_key:
                return image
        return None

    def active_image_reference_exists(self, epic_id: str, reference_key: str) -> bool:
        return self.load_active_image_by_reference(epic_id, reference_key) is not None

    def deactivate_active_image_reference(self, epic_id: str, reference_key: str,
        *,
        idempotency_key: str | None = None,
    ) -> list[Image]:
        updated: list[Image] = []
        for image in self.list_active_images(epic_id):
            if image.reference_key != reference_key:
                continue
            updated.append(self.update_image(image.id, active=False))
        return updated
