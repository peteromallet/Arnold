"""Bounded, store-backed Discord reply ancestry capture and traversal."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any

from agentbox.redaction import redact_text

REPLY_PROVENANCE_SCHEMA = "discord-reply-provenance-v1"
REPLY_CAPTURE_MAX_ANCESTORS = 100
REPLY_CAPTURE_CONTENT_CHARS = 1500
REPLY_PROMPT_ANCESTORS = 3
REPLY_PROMPT_CONTENT_CHARS = 800
REPLY_PROMPT_CURRENT_CONTENT_CHARS = 4000
REPLY_TOOL_MAX_PAGE = 10
REPLY_TOOL_CONTENT_CHARS = 1200
_CURSOR_PREFIX = "rrc1."


def bounded_reply_content(value: object, *, limit: int = REPLY_CAPTURE_CONTENT_CHARS) -> tuple[str, bool]:
    text = redact_text(str(value or ""))
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "…", True


def build_reply_provenance(
    *,
    source_message_id: str,
    source_author_id: str | None,
    conversation_key: str,
    scope: Mapping[str, Any],
    raw_chain: object,
    reference_message_id: str | None,
    reference_author_id: str | None,
    reference_content: str | None,
    stored_parent: Any | None = None,
) -> dict[str, Any]:
    """Normalize an adapter capture, with exact-ID legacy compatibility only."""

    ancestors: list[dict[str, Any]] = []
    termination_reason = "root"
    chain_complete = True
    capture_truncated = False

    if isinstance(raw_chain, Mapping):
        raw_ancestors = raw_chain.get("ancestors")
        if isinstance(raw_ancestors, list):
            for depth, raw in enumerate(raw_ancestors[:REPLY_CAPTURE_MAX_ANCESTORS], start=1):
                if not isinstance(raw, Mapping):
                    continue
                normalized = _normalize_ancestor(raw, depth=depth)
                if normalized is not None:
                    ancestors.append(normalized)
            termination_reason = _safe_reason(raw_chain.get("termination_reason"), "root")
            chain_complete = bool(raw_chain.get("chain_complete", termination_reason == "root"))
            capture_truncated = bool(raw_chain.get("capture_truncated", False))
            if len(raw_ancestors) > REPLY_CAPTURE_MAX_ANCESTORS:
                capture_truncated = True
                chain_complete = False
                termination_reason = "capture_depth_limit"

    if reference_message_id and not ancestors:
        if stored_parent is not None:
            content, truncated = bounded_reply_content(getattr(stored_parent, "content", ""))
            parent_provenance = getattr(stored_parent, "discord_reply_provenance", None)
            parent_author = (
                str(parent_provenance.get("source_author_id"))
                if isinstance(parent_provenance, Mapping)
                and parent_provenance.get("source_author_id") is not None
                else reference_author_id
            )
            ancestors.append(
                {
                    "depth": 1,
                    "message_id": reference_message_id,
                    "author_id": parent_author,
                    "content": content,
                    "content_truncated": truncated,
                    "status": "available",
                    "parent_message_id": _parent_id(parent_provenance),
                }
            )
            if isinstance(parent_provenance, Mapping):
                for raw in list(parent_provenance.get("ancestors") or [])[
                    : REPLY_CAPTURE_MAX_ANCESTORS - 1
                ]:
                    if isinstance(raw, Mapping):
                        normalized = _normalize_ancestor(raw, depth=len(ancestors) + 1)
                        if normalized is not None:
                            ancestors.append(normalized)
                termination_reason = _safe_reason(
                    parent_provenance.get("termination_reason"), "root"
                )
                chain_complete = bool(parent_provenance.get("chain_complete", False))
                capture_truncated = bool(parent_provenance.get("capture_truncated", False))
            else:
                termination_reason = "legacy_parent_provenance_unavailable"
                chain_complete = False
        elif reference_content is not None:
            content, truncated = bounded_reply_content(reference_content)
            ancestors.append(
                {
                    "depth": 1,
                    "message_id": reference_message_id,
                    "author_id": reference_author_id,
                    "content": content,
                    "content_truncated": truncated,
                    "status": "available",
                    "parent_message_id": None,
                }
            )
            termination_reason = "legacy_parent_provenance_unavailable"
            chain_complete = False
        else:
            ancestors.append(
                {
                    "depth": 1,
                    "message_id": reference_message_id,
                    "author_id": reference_author_id,
                    "content": "",
                    "content_truncated": False,
                    "status": "unavailable",
                    "unavailable_reason": "missing_deleted_or_not_captured",
                    "parent_message_id": None,
                }
            )
            termination_reason = "ancestor_unavailable"
            chain_complete = False

    ancestors, forced_termination = _cycle_safe_ancestors(
        ancestors, source_message_id=source_message_id
    )
    if forced_termination is not None:
        termination_reason = forced_termination
        chain_complete = False

    return {
        "schema_version": REPLY_PROVENANCE_SCHEMA,
        "transport": "discord",
        "source_message_id": source_message_id,
        "source_author_id": source_author_id,
        "conversation_key": conversation_key,
        "scope": {key: value for key, value in scope.items() if value is not None},
        "ancestors": ancestors,
        "captured_ancestor_count": len(ancestors),
        "capture_limit": REPLY_CAPTURE_MAX_ANCESTORS,
        "chain_complete": chain_complete,
        "capture_truncated": capture_truncated,
        "termination_reason": termination_reason,
    }


def render_reply_context(message: Any) -> str:
    provenance = getattr(message, "discord_reply_provenance", None)
    source_discord_id = getattr(message, "discord_message_id", None) or "unavailable"
    source_record_id = getattr(message, "id", "unavailable")
    source_author_id = None
    ancestors: list[Mapping[str, Any]] = []
    chain_complete = False
    termination_reason = "legacy_source_provenance_unavailable"
    capture_truncated = False
    if isinstance(provenance, Mapping):
        source_author_id = provenance.get("source_author_id")
        ancestors = [value for value in provenance.get("ancestors", []) if isinstance(value, Mapping)]
        chain_complete = bool(provenance.get("chain_complete", False))
        termination_reason = _safe_reason(provenance.get("termination_reason"), "unknown")
        capture_truncated = bool(provenance.get("capture_truncated", False))

    lines = [
        "[Discord source message — immutable resident provenance]",
        f"Current Discord message id: {source_discord_id}",
        f"Current resident message record id: {source_record_id}",
        f"Current author id: {source_author_id or 'unavailable'}",
        "",
        "[Discord reply ancestry — nearest parent first; current message excluded]",
        "The nearest three ancestors are preloaded here. Do not infer reply ancestry from nearby conversation history.",
    ]
    if not ancestors:
        if chain_complete and termination_reason == "root":
            lines.append("No parent message: this message is not a reply.")
        else:
            lines.append(
                "No ancestor could be loaded. Parent provenance is unavailable "
                f"({termination_reason}); this may be a legacy record."
            )
    for ancestor in ancestors[:REPLY_PROMPT_ANCESTORS]:
        depth = ancestor.get("depth") or "?"
        status = str(ancestor.get("status") or "unavailable")
        lines.extend(
            [
                "",
                f"Ancestor {depth} ({'immediate parent' if depth == 1 else 'older parent'}):",
                f"- Discord message id: {ancestor.get('message_id') or 'unavailable'}",
                f"- Author id: {ancestor.get('author_id') or 'unavailable'}",
                f"- Status: {status}",
            ]
        )
        if status == "available":
            content, prompt_truncated = bounded_reply_content(
                ancestor.get("content"), limit=REPLY_PROMPT_CONTENT_CHARS
            )
            was_truncated = bool(ancestor.get("content_truncated")) or prompt_truncated
            lines.append(f"- Content truncated: {'yes' if was_truncated else 'no'}")
            lines.append("- Content:")
            lines.append(content or "(empty message content)")
        else:
            lines.append(
                f"- Availability detail: {ancestor.get('unavailable_reason') or termination_reason}"
            )

    older_captured = max(0, len(ancestors) - REPLY_PROMPT_ANCESTORS)
    if older_captured or capture_truncated:
        cursor = encode_reply_cursor(str(source_record_id), REPLY_PROMPT_ANCESTORS)
        lines.extend(
            [
                "",
                f"Older captured ancestors not preloaded: {older_captured}",
                f"Capture depth limit reached: {'yes' if capture_truncated else 'no'}",
                "To read older ancestry, call `read_reply_chain` with this cursor: " + cursor,
                "If resident function tools are unavailable, run the constrained command "
                "`python -m arnold_pipelines.megaplan resident read-reply-chain --cursor "
                + cursor
                + "`.",
            ]
        )
    else:
        lines.append("")
        if chain_complete:
            lines.append(f"Older ancestors remain: no (termination: {termination_reason}).")
        else:
            lines.append(
                "Older ancestors remain: unknown; traversal stopped "
                f"({termination_reason})."
            )
    current_content, current_truncated = bounded_reply_content(
        getattr(message, "content", ""), limit=REPLY_PROMPT_CURRENT_CONTENT_CHARS
    )
    lines.extend(
        [
            "",
            "[Current user message]",
            f"Content truncated: {'yes' if current_truncated else 'no'}",
            current_content,
        ]
    )
    return "\n".join(lines)


def encode_reply_cursor(source_record_id: str, offset: int) -> str:
    payload = json.dumps(
        {"source_record_id": source_record_id, "offset": offset},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _CURSOR_PREFIX + base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_reply_cursor(cursor: str) -> tuple[str, int]:
    if not cursor.startswith(_CURSOR_PREFIX):
        raise ValueError("invalid reply-chain cursor")
    encoded = cursor[len(_CURSOR_PREFIX) :]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw)
        source_record_id = str(payload["source_record_id"])
        offset = int(payload["offset"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid reply-chain cursor") from exc
    if not source_record_id or offset < 0 or offset > REPLY_CAPTURE_MAX_ANCESTORS:
        raise ValueError("invalid reply-chain cursor bounds")
    return source_record_id, offset


def reply_chain_page(message: Any, *, offset: int, limit: int) -> dict[str, Any]:
    provenance = getattr(message, "discord_reply_provenance", None)
    if not isinstance(provenance, Mapping):
        return {
            "source_record_id": getattr(message, "id", None),
            "source_message_id": getattr(message, "discord_message_id", None),
            "ancestors": [],
            "count": 0,
            "has_more": False,
            "more_ancestors_remain": None,
            "next_cursor": None,
            "chain_complete": False,
            "capture_truncated": False,
            "termination_reason": "legacy_source_provenance_unavailable",
        }
    ancestors = [value for value in provenance.get("ancestors", []) if isinstance(value, Mapping)]
    bounded_limit = max(1, min(int(limit), REPLY_TOOL_MAX_PAGE))
    page: list[dict[str, Any]] = []
    for raw in ancestors[offset : offset + bounded_limit]:
        item = dict(raw)
        if item.get("status") == "available":
            content, output_truncated = bounded_reply_content(
                item.get("content"), limit=REPLY_TOOL_CONTENT_CHARS
            )
            item["content"] = content
            item["content_truncated"] = bool(item.get("content_truncated")) or output_truncated
        page.append(item)
    next_offset = offset + len(page)
    has_more = next_offset < len(ancestors)
    capture_truncated = bool(provenance.get("capture_truncated", False))
    return {
        "source_record_id": getattr(message, "id", None),
        "source_message_id": provenance.get("source_message_id")
        or getattr(message, "discord_message_id", None),
        "ancestors": page,
        "count": len(page),
        "offset": offset,
        "limit": bounded_limit,
        "has_more": has_more,
        "more_ancestors_remain": (
            True
            if has_more or capture_truncated
            else False if bool(provenance.get("chain_complete", False)) else None
        ),
        "next_cursor": encode_reply_cursor(str(message.id), next_offset) if has_more else None,
        "chain_complete": bool(provenance.get("chain_complete", False)),
        "capture_truncated": capture_truncated,
        "termination_reason": _safe_reason(provenance.get("termination_reason"), "unknown"),
        "capture_limit": int(provenance.get("capture_limit") or REPLY_CAPTURE_MAX_ANCESTORS),
    }


def _normalize_ancestor(raw: Mapping[str, Any], *, depth: int) -> dict[str, Any] | None:
    message_id = str(raw.get("message_id") or "").strip()
    if not message_id:
        return None
    status = str(raw.get("status") or "available")
    if status not in {"available", "unavailable", "cycle_detected", "scope_rejected"}:
        status = "unavailable"
    content, truncated = bounded_reply_content(raw.get("content"))
    return {
        "depth": depth,
        "message_id": message_id,
        "author_id": str(raw.get("author_id")) if raw.get("author_id") is not None else None,
        "content": content if status == "available" else "",
        "content_truncated": bool(raw.get("content_truncated")) or truncated,
        "status": status,
        "unavailable_reason": (
            str(raw.get("unavailable_reason")) if raw.get("unavailable_reason") else None
        ),
        "parent_message_id": (
            str(raw.get("parent_message_id")) if raw.get("parent_message_id") else None
        ),
    }


def _cycle_safe_ancestors(
    ancestors: list[dict[str, Any]], *, source_message_id: str
) -> tuple[list[dict[str, Any]], str | None]:
    result: list[dict[str, Any]] = []
    seen = {source_message_id}
    for ancestor in ancestors:
        item = dict(ancestor)
        message_id = str(item.get("message_id") or "")
        status = str(item.get("status") or "unavailable")
        if message_id in seen:
            item.update(
                status="cycle_detected",
                content="",
                unavailable_reason="reply_pointer_cycle",
            )
            result.append(item)
            return result, "cycle_detected"
        seen.add(message_id)
        result.append(item)
        if status == "cycle_detected":
            return result, "cycle_detected"
        if status == "scope_rejected":
            return result, "scope_rejected"
        if status == "unavailable":
            return result, "ancestor_unavailable"
    return result, None


def _parent_id(provenance: object) -> str | None:
    if not isinstance(provenance, Mapping):
        return None
    ancestors = provenance.get("ancestors")
    if not isinstance(ancestors, list) or not ancestors or not isinstance(ancestors[0], Mapping):
        return None
    value = ancestors[0].get("message_id")
    return str(value) if value else None


def _safe_reason(value: object, default: str) -> str:
    text = str(value or "").strip()
    return text[:80] if text else default
