"""Discord push transport and persist-first DM ingestion."""

from __future__ import annotations

import asyncio
from datetime import datetime
import inspect
import io
import os
from pathlib import Path
from typing import Any, Callable, Sequence

import httpx
from resident_chat_runtime.async_bridge import run_coroutine_sync
from resident_chat_runtime.discord_channel import (
    channel_typing,
    edit_channel_message,
    fetch_channel,
)

from agent_kit.ledger import Ledger, derive_idempotency_key
from agent_kit.ports import Blob, FileUpload, JSONDict, Store


VOICE_MODEL = "whisper-large-v3"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class DiscordTransport:
    def __init__(
        self,
        *,
        store: Store,
        blob: Blob,
        ledger: Ledger,
        groq_client: Any,
        whitelist: set[str] | Sequence[str] | None = None,
        token: str | None = None,
    ) -> None:
        self.store = store
        self.blob = blob
        self.ledger = ledger
        self.groq_client = groq_client
        self.whitelist = set(whitelist or _env_whitelist())
        self.token = token or os.environ.get("DISCORD_BOT_TOKEN")
        self._handler: Callable[[JSONDict], Any] | None = None
        self._client = None
        self._client_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self.quiet_status_updates = True

    def start(self, handler: Callable[[JSONDict], Any]) -> None:
        self._handler = handler
        if self._client is not None:
            return
        try:
            import discord
        except ImportError as exc:
            raise RuntimeError("discord.py is required for DiscordTransport.start") from exc
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        self._client = client

        @client.event
        async def on_connect():  # pragma: no cover - runtime diagnostics
            print("discord gateway connected", flush=True)

        @client.event
        async def on_ready():  # pragma: no cover - runtime diagnostics
            user = getattr(client, "user", None)
            print(
                f"discord ready user={getattr(user, 'name', None)} id={getattr(user, 'id', None)}",
                flush=True,
            )

        @client.event
        async def on_message(message):  # pragma: no cover - exercised via on_message
            print(
                "discord message received "
                f"id={getattr(message, 'id', None)} "
                f"author={getattr(getattr(message, 'author', None), 'id', None)} "
                f"guild={getattr(getattr(message, 'guild', None), 'id', None)} "
                f"channel={getattr(getattr(message, 'channel', None), 'id', None)}",
                flush=True,
            )
            try:
                await self.on_message(message)
            except Exception as exc:
                print(
                    f"discord message handler failed: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                raise

        if not self.token:
            raise RuntimeError("DISCORD_BOT_TOKEN is required")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            client.run(self.token)
            return
        self._loop = loop
        self._client_task = loop.create_task(client.start(self.token))

    def stop(self) -> None:
        if self._client_task is not None:
            self._client_task.cancel()
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        asyncio.run(result)
                    else:
                        loop.create_task(result)

    async def on_message(self, message: Any) -> None:
        if getattr(message, "author", None) is not None and getattr(message.author, "bot", False):
            return
        if getattr(message, "guild", None) is not None:
            return
        author_id = str(getattr(getattr(message, "author", None), "id", ""))
        if self.whitelist and author_id not in self.whitelist:
            self.store.log_system_event(
                level="info",
                category="application",
                event_type="whitelist_rejected",
                message="Discord DM rejected because author is not whitelisted.",
                details={"discord_user_id": author_id},
                epic_id=_message_epic_id(message),
            )
            return

        attachments = list(getattr(message, "attachments", []) or [])
        voice = next((item for item in attachments if _is_voice(item)), None)
        image = next((item for item in attachments if _is_image(item)), None)
        if voice is not None:
            row_id = self._persist_voice(message, voice)
            await self._handle_callback(message, row_id)
            return
        if image is not None:
            row_id = self._persist_image(message, image)
            await self._handle_callback(message, row_id)
            return
        row = self.store.create_message(
            epic_id=self._ensure_message_epic_id(message),
            direction="inbound",
            content=str(getattr(message, "content", "") or ""),
            discord_message_id=str(getattr(message, "id")),
        )
        await self._handle_callback(message, row["id"])

    def post_message(
        self,
        channel_id: str,
        content: str,
        *,
        files: Sequence[FileUpload] | None = None,
    ) -> JSONDict:
        return self._run_coro(self._post_message(channel_id, content, files=files))

    def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> JSONDict:
        return self._run_coro(self._edit_message(channel_id, message_id, content))

    def set_typing(self, channel_id: str, on: bool) -> JSONDict:
        return self._run_coro(self._set_typing(channel_id, on))

    def download_attachment(self, url: str) -> bytes:
        response = httpx.get(url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        return response.content

    def fetch_recent_messages(
        self,
        channel_id: str,
        since: str,
        until: str,
    ) -> list[JSONDict]:
        return self._run_coro(self._fetch_recent_messages(channel_id, since, until))

    def _run_coro(self, coro):
        return run_coroutine_sync(
            coro,
            loop=self._loop if self._loop is not None and self._loop.is_running() else None,
            same_loop_message="DiscordTransport sync method called from Discord event loop",
        )

    def _persist_voice(self, message: Any, attachment: Any) -> str:
        discord_id = str(getattr(message, "id"))
        epic_id = self._ensure_message_epic_id(message)
        path = f"audio/{epic_id}/{discord_id}.ogg"
        storage_endpoint = f"PUT {path}"
        groq_endpoint = "POST /audio/transcriptions"
        # Commit the inbound row and replay ledger before any Storage or Groq call.
        with self.store.transaction():
            row = self.store.create_message(
                epic_id=epic_id,
                direction="inbound",
                content="",
                discord_message_id=discord_id,
                was_voice_message=True,
            )
            storage_request = self._insert_ingest_pending(
                discord_message_id=discord_id,
                provider="supabase_storage",
                endpoint=storage_endpoint,
                request_summary={"deterministic_path": path, "kind": "voice"},
                request_body={
                    "deterministic_path": path,
                    "discord_attachment_url": str(getattr(attachment, "url")),
                },
            )
            groq_request = self._insert_ingest_pending(
                discord_message_id=discord_id,
                provider="groq",
                endpoint=groq_endpoint,
                request_summary={"model": VOICE_MODEL, "audio_storage_url": path},
                request_body={"model": VOICE_MODEL, "audio_storage_url": path},
            )

        try:
            audio = self.download_attachment(str(getattr(attachment, "url")))
            ref = self.blob.put(epic_id, audio, _content_type(attachment, "audio/ogg"))
            self.ledger.mark_confirmed(
                storage_request["id"],
                getattr(ref, "key", path),
                {"storage_url": getattr(ref, "key", path)},
            )
            transcription, summary = self._transcribe(audio, attachment, getattr(ref, "key", path))
            self.ledger.mark_confirmed(groq_request["id"], None, summary)
            self.store.update_message(
                row["id"],
                content=transcription,
                audio_storage_url=getattr(ref, "key", path),
                transcription_metadata=summary,
            )
        except Exception as exc:
            self.ledger.mark_failed(storage_request["id"], _error_details(exc))
            self.ledger.mark_failed(groq_request["id"], _error_details(exc))
            raise
        return row["id"]

    def _persist_image(self, message: Any, attachment: Any) -> str:
        discord_id = str(getattr(message, "id"))
        epic_id = self._ensure_message_epic_id(message)
        ext = Path(str(getattr(attachment, "filename", ""))).suffix.lower() or ".png"
        path = f"images/{epic_id}/{discord_id}{ext}"
        endpoint = f"PUT {path}"
        # Image rows are created only after the persisted message and upload confirm.
        with self.store.transaction():
            row = self.store.create_message(
                epic_id=epic_id,
                direction="inbound",
                content=str(getattr(message, "content", "") or ""),
                discord_message_id=discord_id,
                has_image_attachment=True,
                was_voice_message=False,
            )
            storage_request = self._insert_ingest_pending(
                discord_message_id=discord_id,
                provider="supabase_storage",
                endpoint=endpoint,
                request_summary={"deterministic_path": path, "kind": "image"},
                request_body={
                    "deterministic_path": path,
                    "discord_attachment_url": str(getattr(attachment, "url")),
                },
            )

        try:
            payload = self.download_attachment(str(getattr(attachment, "url")))
            ref = self.blob.put(epic_id, payload, _content_type(attachment, "image/png"))
            storage_url = getattr(ref, "key", path)
            self.ledger.mark_confirmed(
                storage_request["id"],
                storage_url,
                {"storage_url": storage_url},
            )
            self.store.create_image(
                epic_id=epic_id,
                source="user_uploaded",
                storage_url=storage_url,
                discord_attachment_id=str(getattr(attachment, "id", "")),
            )
        except Exception as exc:
            self.ledger.mark_failed(storage_request["id"], _error_details(exc))
            raise
        return row["id"]

    def _insert_ingest_pending(
        self,
        *,
        discord_message_id: str,
        provider: str,
        endpoint: str,
        request_summary: JSONDict,
        request_body: JSONDict,
    ) -> JSONDict:
        idempotency_key = derive_idempotency_key(
            provider=provider,
            endpoint=endpoint,
            request_summary=request_summary,
            turn_id=None,
            ingest_message_id=discord_message_id,
        )
        return self.store.insert_pending(
            idempotency_key=idempotency_key,
            provider=provider,
            endpoint=endpoint,
            request_summary=request_summary,
            request_body=request_body,
            turn_id=None,
            tool_call_id=None,
        )

    def _transcribe(self, audio: bytes, attachment: Any, storage_url: str) -> tuple[str, JSONDict]:
        create = self.groq_client.audio.transcriptions.create
        response = create(
            file=(getattr(attachment, "filename", "voice.ogg"), audio),
            model=VOICE_MODEL,
        )
        text = _response_text(response)
        summary = {
            "model": VOICE_MODEL,
            "audio_storage_url": storage_url,
            "text_length": len(text),
        }
        return text, summary

    async def _handle_callback(self, message: Any, message_id: str) -> None:
        if self._handler is None:
            return
        row = self.store.load_message(message_id) or {}
        payload = {
            "epic_id": row.get("epic_id") or self._ensure_message_epic_id(message),
            "message_id": message_id,
            "message_ids": [message_id],
            "channel_id": str(getattr(getattr(message, "channel", None), "id", "")),
            "discord_message_id": str(getattr(message, "id")),
        }
        result = self._handler(payload)
        if inspect.isawaitable(result):
            await result

    def _ensure_message_epic_id(self, message: Any) -> str:
        author_id = str(getattr(getattr(message, "author", None), "id", ""))
        title = f"Discord DM {author_id}"
        for epic in self.store.list_epics(active_only=True, limit=100):
            if epic.get("title") == title:
                return str(epic["id"])
        created = self.store.create_epic(
            title=title,
            goal=f"Track Discord DM conversation with user {author_id}.",
            body="",
            state="shaping",
        )
        return str(created["id"])

    async def _post_message(
        self,
        channel_id: str,
        content: str,
        *,
        files: Sequence[FileUpload] | None = None,
    ) -> JSONDict:
        channel = await self._resolve_channel(channel_id)
        discord_files = _discord_files(files)
        if discord_files:
            message = await channel.send(content, files=discord_files)
        else:
            message = await channel.send(content)
        return {"id": str(message.id), "channel_id": channel_id}

    async def _edit_message(self, channel_id: str, message_id: str, content: str) -> JSONDict:
        channel = await self._resolve_channel(channel_id)
        message = await channel.fetch_message(int(message_id))
        edited = await edit_channel_message(message, content)
        return {"id": str(edited.id), "channel_id": channel_id}

    async def _set_typing(self, channel_id: str, on: bool) -> JSONDict:
        if on:
            channel = await self._resolve_channel(channel_id)
            trigger_typing = getattr(channel, "trigger_typing", None)
            if callable(trigger_typing):
                await trigger_typing()
            else:
                async with channel_typing(channel):
                    pass
        return {"channel_id": channel_id, "typing": bool(on)}

    async def _fetch_recent_messages(self, channel_id: str, since: str, until: str) -> list[JSONDict]:
        channel = await self._resolve_channel(channel_id)
        after = _parse_dt(since)
        before = _parse_dt(until)
        rows = []
        async for message in channel.history(after=after, before=before):
            rows.append(
                {
                    "discord_message_id": str(message.id),
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
            )
        return rows

    async def _resolve_channel(self, channel_id: str):
        if self._client is None:
            raise RuntimeError("Discord client is not running")
        return await fetch_channel(self._client, channel_id)


def _env_whitelist() -> set[str]:
    raw = os.environ.get("DISCORD_USER_WHITELIST", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _message_epic_id(message: Any) -> str:
    return str(getattr(message, "epic_id", "") or f"discord_user_{getattr(message.author, 'id')}")


def _is_voice(attachment: Any) -> bool:
    checker = getattr(attachment, "is_voice_message", None)
    if checker is not None and checker():
        return True
    return str(getattr(attachment, "content_type", "")).startswith("audio/")


def _is_image(attachment: Any) -> bool:
    content_type = str(getattr(attachment, "content_type", ""))
    if content_type.startswith("image/"):
        return True
    return Path(str(getattr(attachment, "filename", ""))).suffix.lower() in IMAGE_EXTENSIONS


def _content_type(attachment: Any, fallback: str) -> str:
    return str(getattr(attachment, "content_type", "") or fallback)


def _response_text(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("text") or "")
    return str(getattr(response, "text", "") or "")


def _error_details(exc: Exception) -> JSONDict:
    return {"error_type": type(exc).__name__, "message": str(exc)}


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _discord_files(files: Sequence[FileUpload] | None):
    if not files:
        return None
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py is required to send files") from exc
    return [
        discord.File(
            fp=io.BytesIO(file.content),
            filename=file.filename,
        )
        for file in files
    ]


def _run_discord_coro(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("DiscordTransport sync method called from running event loop") from None


__all__ = ["DiscordTransport"]
