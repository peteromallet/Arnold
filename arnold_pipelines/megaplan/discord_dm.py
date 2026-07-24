"""Best-effort Discord bot DM helpers for Megaplan notifications."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Mapping, Sequence
from urllib import error, request

from arnold_pipelines.megaplan.cloud.redact import redact_payload
from arnold_pipelines.megaplan.notification_safety import classify_user_notification

LOGGER = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_MESSAGE_LIMIT = 2000


def render_discord_dm(payload: Mapping[str, Any]) -> list[str]:
    """Render a structured DM payload into Discord-sized markdown chunks."""

    payload = redact_payload(payload)
    lines: list[str] = []

    title = _clean_text(payload.get("title"))
    if title:
        lines.append(title)

    summary = _clean_text(payload.get("summary"))
    if summary:
        if lines:
            lines.append("")
        lines.extend(_wrap_plain_text(summary, DISCORD_MESSAGE_LIMIT))

    fields = payload.get("fields")
    if isinstance(fields, Sequence) and not isinstance(fields, (str, bytes)):
        for field in fields:
            rendered = _render_field(field)
            if rendered:
                if lines and lines[-1] == "":
                    pass
                lines.extend(_wrap_plain_text(rendered, DISCORD_MESSAGE_LIMIT))

    links = _render_links(payload.get("links"))
    if links:
        lines.extend(_wrap_plain_text(links, DISCORD_MESSAGE_LIMIT))

    next_action = _clean_text(payload.get("next_action"))
    if next_action:
        lines.extend(_wrap_plain_text(f"**Next action:** {next_action}", DISCORD_MESSAGE_LIMIT))

    footer = _clean_text(payload.get("footer"))
    if footer:
        lines.extend(_wrap_plain_text(footer, DISCORD_MESSAGE_LIMIT))

    compact_lines = _trim_blank_lines(lines)
    if not compact_lines:
        return []
    return _chunk_lines(compact_lines, DISCORD_MESSAGE_LIMIT)


def send_discord_dm(
    payload: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    opener: Any | None = None,
) -> dict[str, Any]:
    """Send a structured payload as one or more Discord bot DMs."""

    environment = env if env is not None else os.environ
    payload = redact_payload(payload, env=environment)
    safety = classify_user_notification(payload=payload, env=environment)
    if not safety.allowed:
        LOGGER.warning("Discord DM suppressed by notification safety policy: %s", safety.reason)
        return {
            "ok": False,
            "reason": "test_execution_suppressed",
            "suppression_reason": safety.reason,
            "message_count": 0,
        }
    token = (environment.get("DISCORD_BOT_TOKEN") or "").strip()
    user_id = (environment.get("DISCORD_DM_USER_ID") or "").strip()
    messages = render_discord_dm(payload)
    if not messages:
        return {
            "ok": False,
            "reason": "empty_payload",
            "message_count": 0,
        }

    missing: list[str] = []
    if not token:
        missing.append("DISCORD_BOT_TOKEN")
    if not user_id:
        missing.append("DISCORD_DM_USER_ID")
    if missing:
        LOGGER.warning("Discord DM skipped; missing %s", ", ".join(missing))
        return {
            "ok": False,
            "reason": "missing_config",
            "missing": missing,
            "message_count": 0,
        }

    urlopen = opener or request.urlopen
    try:
        channel = _discord_api_request(
            "/users/@me/channels",
            {"recipient_id": user_id},
            token=token,
            opener=urlopen,
        )
        channel_id = str(channel["id"])
        message_ids: list[str] = []
        for content in messages:
            delivered = _discord_api_request(
                f"/channels/{channel_id}/messages",
                {"content": content},
                token=token,
                opener=urlopen,
            )
            message_id = delivered.get("id")
            if message_id is not None:
                message_ids.append(str(message_id))
    except Exception as exc:
        LOGGER.warning("Discord DM delivery failed for user %s: %s", user_id, exc)
        return {
            "ok": False,
            "reason": "send_failed",
            "error": str(exc),
            "message_count": 0,
        }

    return {
        "ok": True,
        "channel_id": channel_id,
        "message_ids": message_ids,
        "message_count": len(messages),
    }


def _discord_api_request(
    path: str,
    payload: Mapping[str, Any],
    *,
    token: str,
    opener: Any,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{DISCORD_API_BASE}{path}",
        data=body,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "arnold-megaplan-discord-dm/1.0",
        },
        method="POST",
    )
    try:
        with opener(req, timeout=10) as response:
            data = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord API {path} failed with {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Discord API {path} failed: {exc.reason}") from exc
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Discord API {path} returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Discord API {path} returned an unexpected payload")
    return parsed


def _render_field(field: object) -> str:
    if not isinstance(field, Mapping):
        return ""
    label = _clean_text(field.get("label"))
    value = field.get("value")
    if not label:
        return ""
    raw_joiner = field.get("joiner")
    joiner = raw_joiner if isinstance(raw_joiner, str) and raw_joiner else " | "
    rendered_value = _format_value(value, style=_clean_text(field.get("style")), joiner=joiner)
    if not rendered_value:
        return ""
    return f"**{label}:** {rendered_value}"


def _format_value(value: object, *, style: str | None, joiner: str) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        cleaned_items = [_clean_text(item) for item in value]
        filtered = [item for item in cleaned_items if item]
        if not filtered:
            return ""
        if style == "code_list":
            return joiner.join(f"`{item}`" for item in filtered)
        return joiner.join(filtered)

    text = _clean_text(value)
    if not text:
        return ""
    if style == "code":
        return f"`{text}`"
    return text


def _render_links(raw_links: object) -> str:
    if not isinstance(raw_links, Sequence) or isinstance(raw_links, (str, bytes)):
        return ""
    parts: list[str] = []
    for item in raw_links:
        if not isinstance(item, Mapping):
            continue
        label = _clean_text(item.get("label"))
        url = _clean_text(item.get("url"))
        if label and url:
            parts.append(f"{label}: <{url}>")
    if not parts:
        return ""
    return f"**Links:** {' | '.join(parts)}"


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return " ".join(text.split()) if text else ""


def _trim_blank_lines(lines: Sequence[str]) -> list[str]:
    trimmed: list[str] = []
    for line in lines:
        text = line.rstrip()
        if text:
            trimmed.append(text)
        elif trimmed and trimmed[-1] != "":
            trimmed.append("")
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return trimmed


def _chunk_lines(lines: Sequence[str], limit: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for line in lines:
        for piece in _split_line(line, limit):
            addition = len(piece) if not current else len(piece) + 1
            if current and current_length + addition > limit:
                chunks.append("\n".join(current))
                current = [piece]
                current_length = len(piece)
            else:
                current.append(piece)
                current_length += addition
    if current:
        chunks.append("\n".join(current))
    return chunks


def _split_line(line: str, limit: int) -> list[str]:
    if len(line) <= limit:
        return [line]
    parts: list[str] = []
    remaining = line
    while len(remaining) > limit:
        split_at = remaining.rfind(" ", 0, limit)
        if split_at <= 0:
            split_at = limit
        parts.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts


def _wrap_plain_text(text: str, limit: int) -> list[str]:
    return _split_line(text, limit)


__all__ = [
    "DISCORD_MESSAGE_LIMIT",
    "render_discord_dm",
    "send_discord_dm",
]
