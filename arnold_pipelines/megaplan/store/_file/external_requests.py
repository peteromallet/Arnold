from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from arnold_pipelines.megaplan.schemas import ExternalRequest
from arnold_pipelines.megaplan.schemas.base import utc_now

from .common import _new_id


class FileExternalRequestMixin:
    def insert_pending(
        self,
        *,
        idempotency_key: str,
        provider: str,
        endpoint: str,
        request_summary: dict[str, Any],
        request_body: dict[str, Any] | None = None,
        turn_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> ExternalRequest:
        if any(row.idempotency_key == idempotency_key for row in self._external_requests()):
            raise ValueError(f"duplicate idempotency_key: {idempotency_key}")
        request = ExternalRequest(
            id=_new_id("req"),
            idempotency_key=idempotency_key,
            provider=provider,
            endpoint=endpoint,
            tool_call_id=tool_call_id,
            turn_id=turn_id,
            request_summary=request_summary,
            request_body=request_body,
            status="pending",
            attempt_count=1,
            first_attempted_at=utc_now(),
            last_attempted_at=utc_now(),
        )
        self._save_model(self._external_request_path(request.id), request, journal_root=self.root)
        return request

    def _update_external_request(self, request_id: str, **changes: Any) -> ExternalRequest:
        return self._update_model(self._external_request_path(request_id), ExternalRequest, journal_root=self.root, **changes)

    def mark_confirmed(
        self,
        request_id: str,
        *,
        provider_request_id: str | None = None,
        provider_response_summary: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        return self._update_external_request(
            request_id,
            status="confirmed",
            provider_request_id=provider_request_id,
            provider_response_summary=provider_response_summary,
            completed_at=utc_now(),
            last_attempted_at=utc_now(),
        )

    def mark_failed(self, request_id: str, *, error_details: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        return self._update_external_request(
            request_id,
            status="failed",
            error_details=error_details,
            completed_at=utc_now(),
            last_attempted_at=utc_now(),
        )

    def find_pending_external_requests(self, older_than_seconds: int) -> list[ExternalRequest]:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        return sorted(
            [
                row
                for row in self._external_requests()
                if row.status == "pending" and row.last_attempted_at <= cutoff
            ],
            key=lambda row: (row.last_attempted_at, row.id),
        )

    def mark_orphaned(self, request_id: str, *, error_details: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> ExternalRequest:
        return self._update_external_request(
            request_id,
            status="orphaned",
            error_details=error_details,
            completed_at=utc_now(),
            last_attempted_at=utc_now(),
        )
