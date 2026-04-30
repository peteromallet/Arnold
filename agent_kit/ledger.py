"""External request ledger helpers.

Sprint 1a intentionally extends the spec's system-request idempotency formula
with a caller-supplied ``system_seq`` ordinal:

``sha256(turn_id + ':system:' + provider + ':' + endpoint + ':' + str(system_seq))[:16]``

This prevents collisions when one turn performs multiple model calls during
tool-use chaining. ``Ledger`` does not assign the ordinal; ``run_turn`` must
pass it explicitly, and Sprint 1b reconciliation must use the same formula.
Tool-call-driven requests keep the spec formula verbatim.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from agent_kit.logging import log
from agent_kit.ports import Blob, BlobRef, Model, PushTransport, Store


JSONDict = dict[str, Any]


class Ledger:
    def __init__(self, store: Store):
        self.store = store

    def record_pending(
        self,
        provider: str,
        endpoint: str,
        request_summary: JSONDict,
        *,
        turn_id: str | None,
        tool_call_id: str | None = None,
        system_seq: int | None = None,
        ingest_message_id: str | None = None,
        request_body: JSONDict | None = None,
    ) -> tuple[str, str]:
        idempotency_key = derive_idempotency_key(
            provider=provider,
            endpoint=endpoint,
            request_summary=request_summary,
            turn_id=turn_id,
            tool_call_id=tool_call_id,
            system_seq=system_seq,
            ingest_message_id=ingest_message_id,
        )
        row = self.store.insert_pending(
            idempotency_key=idempotency_key,
            provider=provider,
            endpoint=endpoint,
            request_summary=request_summary,
            request_body=request_body,
            turn_id=turn_id,
            tool_call_id=tool_call_id,
        )
        return row["id"], idempotency_key

    def mark_confirmed(
        self,
        request_id: str,
        provider_request_id: str | None,
        provider_response_summary: JSONDict | None,
    ) -> JSONDict:
        return self.store.mark_confirmed(
            request_id,
            provider_request_id=provider_request_id,
            provider_response_summary=provider_response_summary,
        )

    def mark_failed(self, request_id: str, error_details: JSONDict) -> JSONDict:
        return self.store.mark_failed(request_id, error_details=error_details)


def derive_idempotency_key(
    *,
    provider: str,
    endpoint: str,
    request_summary: JSONDict,
    turn_id: str | None,
    tool_call_id: str | None = None,
    system_seq: int | None = None,
    ingest_message_id: str | None = None,
) -> str:
    if ingest_message_id is not None:
        material = f"ingest:{ingest_message_id}:{provider}:{endpoint}"
    elif tool_call_id is not None:
        if turn_id is None:
            raise ValueError("turn_id is required for tool-call ledger requests")
        canonical_args = _canonical_json(request_summary)
        material = (
            f"{turn_id}:{tool_call_id}:{provider}:{endpoint}:{canonical_args}"
        )
    else:
        if turn_id is None:
            raise ValueError("turn_id is required for system ledger requests")
        if system_seq is None:
            raise ValueError("system_seq is required for system ledger requests")
        material = f"{turn_id}:system:{provider}:{endpoint}:{system_seq}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


class Reconciler:
    def __init__(
        self,
        store: Store,
        *,
        model: Model | None = None,
        transport: PushTransport | None = None,
        blob: Blob | None = None,
        groq_client: Any | None = None,
    ) -> None:
        self.store = store
        self.model = model
        self.transport = transport
        self.blob = blob
        self.groq_client = groq_client
        self.ledger = Ledger(store)

    def run_once(self) -> JSONDict:
        requeued_message_ids = self._mark_abandoned_turns()
        results = [
            self._reconcile_external_request(row)
            for row in self.store.find_pending_external_requests(60)
        ]
        return {
            "requeued_message_ids": requeued_message_ids,
            "external_requests": results,
        }

    def _mark_abandoned_turns(self) -> list[str]:
        message_ids: list[str] = []
        for turn in self.store.find_abandoned_turns(300):
            updated = self.store.update_turn(turn["id"], status="abandoned")
            triggered = list(updated.get("triggered_by_message_ids") or [])
            message_ids.extend(str(message_id) for message_id in triggered)
            log(
                self.store,
                "warn",
                "recovery",
                "turn_abandoned",
                "Marked stale in-progress turn abandoned for recovery.",
                turn_id=turn["id"],
                epic_id=turn.get("epic_id"),
                triggered_by_message_ids=triggered,
            )
        return message_ids

    def _reconcile_external_request(self, row: JSONDict) -> JSONDict:
        provider = row.get("provider")
        try:
            if provider in {"anthropic", "openai"}:
                return self._reconcile_model(row)
            if provider == "discord":
                return self._reconcile_discord(row)
            if provider == "groq":
                return self._reconcile_groq(row)
            if provider == "supabase_storage":
                return self._reconcile_storage(row)
            if provider == "github":
                log(
                    self.store,
                    "info",
                    "recovery",
                    "github_reconcile_skipped",
                    "GitHub request reconciliation is informational only.",
                    turn_id=row.get("turn_id"),
                    details={"request_id": row.get("id")},
                )
                return {"id": row.get("id"), "status": "skipped"}
        except Exception as exc:
            self.ledger.mark_failed(
                row["id"],
                {"error_type": type(exc).__name__, "message": str(exc)},
            )
            raise
        return {"id": row.get("id"), "status": "unsupported_provider"}

    def _reconcile_model(self, row: JSONDict) -> JSONDict:
        if self.model is None:
            return {"id": row["id"], "status": "missing_model"}
        body = row.get("request_body") or {}
        result = self.model.complete_turn(
            model_id=body["model"],
            messages=body["messages"],
            tools=body["tools"],
            hot_context={},
            idempotency_key=row["idempotency_key"],
        )
        return self.ledger.mark_confirmed(
            row["id"],
            result.provider_request_id,
            result.response_summary,
        )

    def _reconcile_discord(self, row: JSONDict) -> JSONDict:
        if self.transport is None:
            return {"id": row["id"], "status": "missing_transport"}
        summary = row.get("request_summary") or {}
        channel_id = str(summary.get("channel_id") or "")
        content_preview = str(summary.get("content_preview") or "")
        messages = self.transport.fetch_recent_messages(
            channel_id,
            str(row.get("first_attempted_at") or ""),
            str(row.get("last_attempted_at") or ""),
        )
        for message in messages:
            if content_preview and str(message.get("content") or "").startswith(content_preview):
                return self.ledger.mark_confirmed(
                    row["id"],
                    str(message.get("discord_message_id") or ""),
                    {"matched": "content_preview"},
                )
        return self.store.mark_orphaned(
            row["id"],
            error_details={"reason": "discord_message_not_found"},
        )

    def _reconcile_groq(self, row: JSONDict) -> JSONDict:
        if self.groq_client is None:
            return {"id": row["id"], "status": "missing_groq_client"}
        body = row.get("request_body") or {}
        transcription = self.groq_client.audio.transcriptions.create(
            model=body.get("model", "whisper-large-v3"),
            file=body["audio_storage_url"],
        )
        text = getattr(transcription, "text", None)
        response_summary = {"text": text} if text is not None else {"result": str(transcription)}
        return self.ledger.mark_confirmed(row["id"], None, response_summary)

    def _reconcile_storage(self, row: JSONDict) -> JSONDict:
        if self.blob is None:
            return {"id": row["id"], "status": "missing_blob"}
        body = row.get("request_body") or {}
        path = body["deterministic_path"]
        ref = BlobRef(
            epic_id=str(body.get("epic_id") or (row.get("request_summary") or {}).get("epic_id") or ""),
            key=path,
            mime_type=str(body.get("mime_type") or "application/octet-stream"),
        )
        if self.blob.exists(ref):
            return self.ledger.mark_confirmed(
                row["id"],
                path,
                {"exists": True, "storage_url": path},
            )

        attachment_url = body.get("discord_attachment_url")
        if not attachment_url:
            return self._orphan_storage(row, "missing_discord_attachment_url")
        try:
            response = httpx.get(str(attachment_url), timeout=30)
            response.raise_for_status()
        except Exception as exc:
            return self._orphan_storage(row, f"{type(exc).__name__}: {exc}")

        uploaded = self.blob.put(
            ref.epic_id,
            response.content,
            ref.mime_type,
        )
        return self.ledger.mark_confirmed(
            row["id"],
            uploaded.key,
            {"storage_url": uploaded.key, "refetched": True},
        )

    def _orphan_storage(self, row: JSONDict, reason: str) -> JSONDict:
        log(
            self.store,
            "warn",
            "recovery",
            "storage_reconcile_orphaned",
            "Storage request could not be replayed from Discord attachment URL.",
            turn_id=row.get("turn_id"),
            details={"request_id": row.get("id"), "reason": reason},
        )
        return self.store.mark_orphaned(
            row["id"],
            error_details={"reason": reason},
        )


def reconcile_on_boot(store: Store) -> JSONDict:
    return Reconciler(store).run_once()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
