"""Task identity boundary for task-native execute custody."""

from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

TASK_KEY_SCHEMA_VERSION = 1
TASK_ID_TRAILER_ENCODING = "base64url-utf8-v1"

_SAFE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_SAFE_CHUNK_RE = re.compile(r"[a-z0-9]+")


class TaskIdentityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TaskIdentity:
    """Stable mapping from user-facing task id to custody-safe task key."""

    original_task_id: str
    task_key: str
    original_task_id_encoded: str
    key_schema_version: int = TASK_KEY_SCHEMA_VERSION
    trailer_encoding: str = TASK_ID_TRAILER_ENCODING

    def registry_identity(self) -> dict[str, Any]:
        return {
            "key_schema_version": self.key_schema_version,
            "task_key": self.task_key,
            "original_task_id_encoded": self.original_task_id_encoded,
            "original_task_id_encoding": self.trailer_encoding,
        }

    def trailer_fields(self) -> dict[str, str]:
        return {
            "Task-Key": self.task_key,
            "Task-Id-Encoding": self.trailer_encoding,
            "Task-Id-B64": self.original_task_id_encoded,
        }


def validate_task_key(task_key: str) -> str:
    if not isinstance(task_key, str):
        raise TypeError("task_key must be a string")
    if not _SAFE_KEY_RE.fullmatch(task_key):
        raise ValueError("task_key must match [a-z0-9][a-z0-9-]{0,79}")
    return task_key


def make_task_identity(original_task_id: str) -> TaskIdentity:
    if not isinstance(original_task_id, str):
        raise TypeError("original_task_id must be a string")
    if original_task_id == "":
        raise TaskIdentityError("empty_task_id", "task id must not be empty")
    digest = hashlib.sha256(original_task_id.encode("utf-8")).hexdigest()[:16]
    normalized = unicodedata.normalize("NFKD", original_task_id)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    chunks = _SAFE_CHUNK_RE.findall(ascii_text)
    prefix = "-".join(chunks).strip("-") or "task"
    prefix = prefix[: max(1, 79 - len(digest) - 1)].strip("-") or "task"
    task_key = validate_task_key(f"{prefix}-{digest}")
    return TaskIdentity(
        original_task_id=original_task_id,
        task_key=task_key,
        original_task_id_encoded=encode_original_task_id(original_task_id),
    )


def build_task_identity_map(tasks: Iterable[dict[str, Any]]) -> dict[str, TaskIdentity]:
    identities: dict[str, TaskIdentity] = {}
    normalized_originals: dict[str, str] = {}
    normalized_keys: dict[str, str] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        original = task.get("id")
        if not isinstance(original, str):
            raise TaskIdentityError("missing_task_id", "every task must have a string id")
        normalized_original = unicodedata.normalize("NFC", original)
        previous_original = normalized_originals.get(normalized_original)
        if previous_original is not None:
            raise TaskIdentityError(
                "duplicate_normalized_task_id",
                f"task ids {previous_original!r} and {original!r} collide after Unicode normalization",
            )
        identity = make_task_identity(original)
        normalized_key = unicodedata.normalize("NFC", identity.task_key).casefold()
        previous_key = normalized_keys.get(normalized_key)
        if previous_key is not None:
            raise TaskIdentityError(
                "task_key_collision",
                f"task ids {previous_key!r} and {original!r} map to the same filesystem task key",
            )
        normalized_originals[normalized_original] = original
        normalized_keys[normalized_key] = original
        identities[original] = identity
    return identities


def identity_map_payload(identity_map: dict[str, TaskIdentity]) -> dict[str, dict[str, Any]]:
    return {
        original_task_id: identity.registry_identity()
        for original_task_id, identity in identity_map.items()
    }


def encode_original_task_id(original_task_id: str) -> str:
    encoded = base64.urlsafe_b64encode(original_task_id.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_original_task_id(encoded: str) -> str:
    if not isinstance(encoded, str) or not encoded:
        raise TaskIdentityError("invalid_encoded_task_id", "encoded task id must be a non-empty string")
    padding = "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise TaskIdentityError("invalid_encoded_task_id", "encoded task id is not base64url UTF-8") from exc


def validate_trailer_identity(
    trailers: dict[str, str],
    identity_map: dict[str, TaskIdentity],
) -> TaskIdentity:
    task_key = trailers.get("Task-Key")
    encoding = trailers.get("Task-Id-Encoding")
    encoded = trailers.get("Task-Id-B64")
    if not task_key or not encoding or not encoded:
        raise TaskIdentityError("missing_identity_trailer", "commit trailers must include task key and encoded original id")
    if encoding != TASK_ID_TRAILER_ENCODING:
        raise TaskIdentityError("unsupported_trailer_encoding", f"unsupported task id trailer encoding: {encoding}")
    original = decode_original_task_id(encoded)
    identity = identity_map.get(original)
    if identity is None:
        raise TaskIdentityError("unknown_task_identity", f"trailer original task id {original!r} is not in finalize identity map")
    if identity.task_key != task_key:
        raise TaskIdentityError("task_key_mismatch", "trailer task key does not match finalize identity map")
    return identity
