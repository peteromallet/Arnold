"""Deterministic cache helpers for code investigation requests."""

from __future__ import annotations

import json
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from agent_kit.code_redaction import redact_code_secrets
from agent_kit.ports import Store


JSONDict = dict[str, Any]
DEFAULT_TTL_SECONDS = 3600


def cache_key(kind: str, payload: JSONDict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = urlsafe_b64encode(sha256(normalized.encode("utf-8")).digest()).decode("ascii").rstrip("=")
    return f"{kind}:{digest}"


def get_cached(store: Store, key: str, *, now: str | None = None) -> JSONDict | None:
    row = store.get_api_cache(key, now=now)
    if row is None:
        return None
    try:
        return json.loads(str(row.get("content") or "{}"))
    except json.JSONDecodeError:
        return {"content": row.get("content")}


def upsert_cached(
    store: Store,
    key: str,
    payload: JSONDict,
    *,
    content_summary: str | None = None,
    metadata: JSONDict | None = None,
    codebase_id: str | None = None,
    epic_id: str | None = None,
    file_path: str | None = None,
    scope: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> JSONDict:
    safe_payload = redact_code_secrets(payload)
    safe_metadata = redact_code_secrets(metadata or {})
    return store.upsert_api_cache(
        cache_key=key,
        content=json.dumps(safe_payload, sort_keys=True),
        content_summary=redact_code_secrets(content_summary),
        metadata=safe_metadata,
        codebase_id=codebase_id,
        epic_id=epic_id,
        file_path=file_path,
        scope=scope,
        expires_at=_format_datetime(datetime.now(UTC) + timedelta(seconds=ttl_seconds)),
        ttl_seconds=ttl_seconds,
    )


def deleted_repo_failure(error: JSONDict, *, cached_artifacts: list[JSONDict] | None = None) -> JSONDict:
    return {
        "ok": False,
        "error": error.get("error", error),
        "cached_artifacts_retained": True,
        "cached_artifact_count": len(cached_artifacts or []),
    }


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


__all__ = ["DEFAULT_TTL_SECONDS", "cache_key", "deleted_repo_failure", "get_cached", "upsert_cached"]
