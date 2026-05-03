"""Invocation attachment normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
from typing import TypeAlias


MAX_IMAGE_ATTACHMENT_BYTES = 25 * 1024 * 1024
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
IMAGE_EXTENSION_BY_MIME_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

AttachmentInput: TypeAlias = Path | str | bytes | tuple[bytes, str]


class UnsupportedMediaTypeError(ValueError):
    """Raised when an invocation attachment is not a supported image."""


@dataclass(frozen=True)
class NormalizedImageAttachment:
    content: bytes
    mime_type: str
    filename: str | None = None
    size_bytes: int = 0


def normalize_image_attachment(attachment: AttachmentInput) -> NormalizedImageAttachment:
    """Normalize one invocation image attachment.

    Supported inputs are filesystem paths, raw bytes, and ``(bytes, mime_type)``.
    Raw byte inputs are accepted only when magic bytes identify PNG, JPEG, or
    WEBP. Detectable MIME mismatches are rejected instead of trusting metadata.
    """

    if isinstance(attachment, tuple):
        if len(attachment) != 2:
            raise UnsupportedMediaTypeError("unsupported media type: expected (bytes, mime_type)")
        content, declared_mime_type = attachment
        if not isinstance(content, bytes) or not isinstance(declared_mime_type, str):
            raise UnsupportedMediaTypeError("unsupported media type: expected (bytes, mime_type)")
        return _normalize(content, declared_mime_type=declared_mime_type)
    if isinstance(attachment, bytes):
        return _normalize(attachment)
    if isinstance(attachment, (str, Path)):
        path = Path(attachment)
        return _normalize(
            path.read_bytes(),
            filename=path.name,
            declared_mime_type=_mime_type_from_filename(path.name),
        )
    raise UnsupportedMediaTypeError("unsupported media type: expected path, bytes, or (bytes, mime_type)")


def normalize_image_attachments(
    attachments: list[AttachmentInput] | tuple[AttachmentInput, ...],
) -> list[NormalizedImageAttachment]:
    return [normalize_image_attachment(attachment) for attachment in attachments]


def _normalize(
    content: bytes,
    *,
    filename: str | None = None,
    declared_mime_type: str | None = None,
) -> NormalizedImageAttachment:
    if len(content) > MAX_IMAGE_ATTACHMENT_BYTES:
        raise UnsupportedMediaTypeError("unsupported media type: image attachment exceeds 25MB")
    sniffed_mime_type = _sniff_image_mime_type(content)
    normalized_declared = _normalize_mime_type(declared_mime_type)
    if normalized_declared is not None and normalized_declared not in SUPPORTED_IMAGE_MIME_TYPES:
        raise UnsupportedMediaTypeError(f"unsupported media type: {normalized_declared}")
    if sniffed_mime_type is None:
        raise UnsupportedMediaTypeError("unsupported media type: unknown image bytes")
    if normalized_declared is not None and normalized_declared != sniffed_mime_type:
        raise UnsupportedMediaTypeError(
            f"unsupported media type: declared {normalized_declared} does not match {sniffed_mime_type}"
        )
    return NormalizedImageAttachment(
        content=content,
        mime_type=sniffed_mime_type,
        filename=filename or f"attachment{IMAGE_EXTENSION_BY_MIME_TYPE[sniffed_mime_type]}",
        size_bytes=len(content),
    )


def _mime_type_from_filename(filename: str) -> str | None:
    guessed, _encoding = mimetypes.guess_type(filename)
    return guessed


def _normalize_mime_type(mime_type: str | None) -> str | None:
    if mime_type is None:
        return None
    value = mime_type.split(";", 1)[0].strip().lower()
    if value == "image/jpg":
        return "image/jpeg"
    return value or None


def _sniff_image_mime_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


__all__ = [
    "AttachmentInput",
    "MAX_IMAGE_ATTACHMENT_BYTES",
    "NormalizedImageAttachment",
    "UnsupportedMediaTypeError",
    "normalize_image_attachment",
    "normalize_image_attachments",
]
