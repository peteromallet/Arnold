"""Routing cache helpers backed by the Store API cache seam."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from arnold_pipelines.megaplan.schemas import CodeArtifact
from arnold_pipelines.megaplan.store import Store
from arnold_pipelines.megaplan.routing.identity import ModelIdentity

CACHE_KEY_PREFIX = "routing.identity"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def identity_cache_key(identity: ModelIdentity) -> str:
    """Return the Store API-cache key for a routing identity."""

    digest = hashlib.sha256(
        _canonical_json(identity.to_json()).encode("utf-8")
    ).hexdigest()
    return f"{CACHE_KEY_PREFIX}:{digest}"


def cache_get(
    store: Store,
    identity: ModelIdentity,
    *,
    now: str | None = None,
    touch: bool = True,
) -> str | None:
    """Read a cached model output through Store.get_api_cache."""

    artifact = store.get_api_cache(
        identity_cache_key(identity),
        now=now,
        touch=touch,
    )
    return None if artifact is None else artifact.content


def cache_set(
    store: Store,
    identity: ModelIdentity,
    content: str,
    *,
    content_summary: str | None = None,
    metadata: dict[str, Any] | None = None,
    codebase_id: str | None = None,
    epic_id: str | None = None,
    file_path: str | None = None,
    scope: str | None = "cross_codebase",
    expires_at: str | None = None,
    ttl_seconds: int = 3600,
    idempotency_key: str | None = None,
) -> CodeArtifact:
    """Write a cached model output through Store.upsert_api_cache."""

    key = identity_cache_key(identity)
    merged_metadata = dict(metadata or {})
    merged_metadata["routing_identity"] = identity.to_json()
    merged_metadata["routing_identity_key"] = key
    return store.upsert_api_cache(
        cache_key=key,
        content=content,
        content_summary=content_summary,
        metadata=merged_metadata,
        codebase_id=codebase_id,
        epic_id=epic_id,
        file_path=file_path,
        scope=scope,
        expires_at=expires_at,
        ttl_seconds=ttl_seconds,
        idempotency_key=idempotency_key,
    )
