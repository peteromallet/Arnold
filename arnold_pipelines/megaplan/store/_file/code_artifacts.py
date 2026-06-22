from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from arnold_pipelines.megaplan.schemas import CodeArtifact
from arnold_pipelines.megaplan.schemas.base import utc_now

from .common import _new_id, _parse_datetime, _utc_key


class FileCodeArtifactMixin:
    def create_code_artifact(
        self,
        *,
        kind: str,
        source: str,
        content: str,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        line_range: Any = None,
        scope: str | None = None,
        content_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        expires_at: str | None = None,
        artifact_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        artifact = CodeArtifact(
            id=artifact_id or _new_id("artifact"),
            codebase_id=codebase_id,
            epic_id=epic_id,
            kind=kind,
            source=source,
            file_path=file_path,
            line_range=line_range,
            scope=scope,
            content=content,
            content_summary=content_summary,
            metadata=metadata or {},
            created_at=utc_now(),
            expires_at=_parse_datetime(expires_at),
        )
        self._save_model(self._code_artifact_path(artifact.id), artifact, journal_root=self.root)
        return artifact

    def load_code_artifact(self, artifact_id: str) -> CodeArtifact | None:
        return self._load_model(self._code_artifact_path(artifact_id), CodeArtifact)

    def list_code_artifacts(
        self,
        *,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        kind: str | None = None,
        source: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        include_expired: bool = True,
        limit: int | None = 50,
    ) -> list[CodeArtifact]:
        now_dt = datetime.now(UTC)
        artifacts = self._code_artifacts()
        filtered: list[CodeArtifact] = []
        for artifact in artifacts:
            if codebase_id is not None and artifact.codebase_id != codebase_id:
                continue
            if epic_id is not None and artifact.epic_id != epic_id:
                continue
            if kind is not None and artifact.kind != kind:
                continue
            if source is not None and artifact.source != source:
                continue
            if file_path is not None and artifact.file_path != file_path:
                continue
            if scope is not None and artifact.scope != scope:
                continue
            if not include_expired and artifact.expires_at is not None and artifact.expires_at <= now_dt:
                continue
            filtered.append(artifact)
        filtered.sort(key=lambda row: (_utc_key(row.created_at), row.id), reverse=True)
        if limit is not None:
            return filtered[:limit]
        return filtered

    def update_code_artifact(self, artifact_id: str, *, idempotency_key: str | None = None,
        **changes: Any) -> CodeArtifact:
        return self._update_model(self._code_artifact_path(artifact_id), CodeArtifact, journal_root=self.root, **changes)

    def delete_code_artifact(self, artifact_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> None:
        self._delete_file(self._code_artifact_path(artifact_id))

    def touch_code_artifact_used(self, artifact_id: str, *, used_at: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        return self.update_code_artifact(artifact_id, last_used_at=_parse_datetime(used_at) or utc_now())

    def get_api_cache(self, cache_key: str, *, now: str | None = None, touch: bool = True) -> CodeArtifact | None:
        now_dt = _parse_datetime(now) or datetime.now(UTC)
        for artifact in self._code_artifacts():
            if artifact.kind != "api_cache":
                continue
            if artifact.metadata.get("cache_key") != cache_key:
                continue
            if artifact.expires_at is not None and artifact.expires_at <= now_dt:
                return None
            if touch:
                return self.touch_code_artifact_used(artifact.id)
            return artifact
        return None

    def upsert_api_cache(
        self,
        *,
        cache_key: str,
        content: str,
        content_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        codebase_id: str | None = None,
        epic_id: str | None = None,
        file_path: str | None = None,
        scope: str | None = None,
        expires_at: str | None = None,
        ttl_seconds: int = 3600,
        idempotency_key: str | None = None,
    ) -> CodeArtifact:
        existing = self.get_api_cache(cache_key, touch=False)
        expiry = _parse_datetime(expires_at) or (datetime.now(UTC) + timedelta(seconds=ttl_seconds))
        merged_metadata = dict(metadata or {})
        merged_metadata["cache_key"] = cache_key
        if existing is None:
            return self.create_code_artifact(
                kind="api_cache",
                source="conversation",
                content=content,
                codebase_id=codebase_id,
                epic_id=epic_id,
                file_path=file_path,
                scope=scope,
                content_summary=content_summary,
                metadata=merged_metadata,
                expires_at=expiry.isoformat().replace("+00:00", "Z"),
            )
        return self.update_code_artifact(
            existing.id,
            content=content,
            content_summary=content_summary,
            metadata=merged_metadata,
            codebase_id=codebase_id,
            epic_id=epic_id,
            file_path=file_path,
            scope=scope,
            expires_at=expiry,
        )

    def cleanup_expired_api_cache(self, *, now: str | None = None,
        idempotency_key: str | None = None,
    ) -> int:
        now_dt = _parse_datetime(now) or datetime.now(UTC)
        expired = [
            artifact
            for artifact in self._code_artifacts()
            if artifact.kind == "api_cache" and artifact.expires_at is not None and artifact.expires_at <= now_dt
        ]
        for artifact in expired:
            self.delete_code_artifact(artifact.id)
        return len(expired)
