"""Image management tools."""

from __future__ import annotations

import base64
import mimetypes
import re
from uuid import uuid4
from typing import Any

from agent_kit.ports import BlobRef, FileUpload
from agent_kit.openai_ops import IMAGE_MODEL
from agent_kit.tool_kit import (
    ExternalSpec,
    ToolContext,
    register_tool,
    run_synchronous_external_effect,
)


REFERENCE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

LIST_IMAGES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "source": {
            "type": ["string", "null"],
            "enum": ["agent_generated", "user_uploaded", "caller_uploaded", None],
        },
    },
}

VIEW_IMAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["image_id"],
    "properties": {
        "image_id": {"type": "string"},
        "mode": {
            "type": "string",
            "enum": ["visual", "description"],
            "default": "visual",
        },
    },
}

SEND_IMAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["image_id"],
    "properties": {
        "image_id": {"type": "string"},
        "caption": {"type": ["string", "null"]},
    },
}

UPDATE_IMAGE_METADATA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["image_id"],
    "properties": {
        "image_id": {"type": "string"},
        "caption": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "reference_key": {"type": ["string", "null"]},
    },
}

GENERATE_IMAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id", "prompt"],
    "properties": {
        "epic_id": {"type": "string"},
        "prompt": {"type": "string"},
        "quality": {
            "type": ["string", "null"],
            "enum": ["low", "medium", "high", None],
        },
        "size": {"type": ["string", "null"]},
        "reference_key": {"type": ["string", "null"]},
        "caption": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
    },
}


@register_tool(
    "list_images",
    schema=LIST_IMAGES_SCHEMA,
    event_kind="tool_call",
    operation_kind="read",
)
def list_images(
    context: ToolContext,
    epic_id: str,
    source: str | None = None,
) -> dict[str, Any]:
    images = context.store.list_images(epic_id=epic_id, source=source)
    return {"images": [_metadata(image) for image in images]}


@register_tool(
    "view_image",
    schema=VIEW_IMAGE_SCHEMA,
    event_kind="tool_call",
    operation_kind="read",
)
def view_image(
    context: ToolContext,
    image_id: str,
    mode: str = "visual",
) -> dict[str, Any]:
    image = _require_image(context, image_id)
    if mode == "description":
        return {"image": _metadata(image)}
    if mode != "visual":
        raise ValueError("mode must be 'visual' or 'description'")
    if context.blob is None:
        raise ValueError("view_image visual mode requires a blob adapter")

    media_type = _media_type(image["storage_url"])
    ref = BlobRef(
        epic_id=image["epic_id"],
        key=image["storage_url"],
        mime_type=media_type,
    )
    payload = context.blob.get(ref)
    return {
        "image": _metadata(image),
        "media_type": media_type,
        "image_bytes_b64": base64.b64encode(payload).decode("ascii"),
    }


@register_tool(
    "send_image",
    schema=SEND_IMAGE_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def send_image(
    context: ToolContext,
    image_id: str,
    caption: str | None = None,
) -> dict[str, Any]:
    image = _require_image(context, image_id)
    content = caption if caption is not None else image.get("caption") or ""
    is_resident = context.transport is not None
    if is_resident and context.blob is None:
        raise ValueError("send_image resident mode requires a blob adapter")
    message = context.store.create_message(
        epic_id=image["epic_id"],
        direction="outbound",
        content=content,
        bot_turn_id=context.turn_id,
        has_image_attachment=True,
        synthesize_outbound_id=not is_resident,
    )
    result = {
        "image_id": image_id,
        "message_row_id": message["id"],
        "caption": content,
        "storage_url": image["storage_url"],
        "reference_key": image["reference_key"],
        "media_type": _media_type(image["storage_url"]),
    }
    if not is_resident:
        result["discord_message_id"] = message["discord_message_id"]
        pending = context.metadata.setdefault("_pending_attached_image_events", [])
        if isinstance(pending, list):
            pending.append(
                {
                    "image_id": image_id,
                    "caption": content,
                    "storage_url": image["storage_url"],
                    "reference_key": image["reference_key"],
                    "media_type": result["media_type"],
                }
            )
        return result

    channel_id = str(context.metadata.get("channel_id") or "")
    endpoint = f"POST /channels/{channel_id}/messages"
    media_type = result["media_type"]
    file_metadata = [
        {
            "image_id": image_id,
            "storage_url": image["storage_url"],
            "media_type": media_type,
            "reference_key": image["reference_key"],
            "filename": _filename_for_image(image["storage_url"], media_type),
        }
    ]
    ref = BlobRef(
        epic_id=image["epic_id"],
        key=image["storage_url"],
        mime_type=media_type,
    )

    def _post_and_update():
        payload = context.blob.get(ref)  # type: ignore[union-attr]
        files = [
            FileUpload(
                filename=file_metadata[0]["filename"],
                content=payload,
                mime_type=media_type,
                metadata=file_metadata[0],
            )
        ]
        response = context.transport.post_message(  # type: ignore[union-attr]
            channel_id,
            content,
            files=files,
        )
        discord_message_id = (
            response.get("discord_message_id")
            or response.get("id")
            or response.get("message_id")
        )
        if discord_message_id is not None:
            context.store.update_message(
                message["id"],
                discord_message_id=str(discord_message_id),
            )
        return (
            str(discord_message_id) if discord_message_id is not None else None,
            response,
        )

    if context.external_queue is None:
        context.external_queue = []
    context.external_queue.append(
        (
            ExternalSpec(
                provider="discord",
                endpoint=endpoint,
                request_summary={
                    "content_preview": content[:100],
                    "channel_id": channel_id,
                    "message_row_id": message["id"],
                    "image_id": image_id,
                    "reference_key": image["reference_key"],
                    "files": file_metadata,
                },
                request_body={"content": content, "files": file_metadata},
            ),
            _post_and_update,
        )
    )
    return result


@register_tool(
    "update_image_metadata",
    schema=UPDATE_IMAGE_METADATA_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def update_image_metadata(
    context: ToolContext,
    image_id: str,
    caption: str | None = None,
    description: str | None = None,
    reference_key: str | None = None,
) -> dict[str, Any]:
    changes = {}
    if caption is not None:
        changes["caption"] = caption
    if description is not None:
        changes["description"] = description
    if reference_key is not None:
        if not REFERENCE_KEY_RE.fullmatch(reference_key):
            raise ValueError("reference_key must match ^[a-z][a-z0-9_]{0,63}$")
        changes["reference_key"] = reference_key
    image = context.store.update_image(image_id, **changes)
    return {"image": _metadata(image)}


@register_tool(
    "generate_image",
    schema=GENERATE_IMAGE_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def generate_image(
    context: ToolContext,
    epic_id: str,
    prompt: str,
    quality: str | None = None,
    size: str | None = None,
    reference_key: str | None = None,
    caption: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    if context.openai_ops is None:
        raise ValueError("generate_image requires openai_ops")
    if context.blob is None:
        raise ValueError("generate_image requires a blob adapter")

    epic = context.store.load_epic(epic_id)
    if not epic:
        raise ValueError(f"epic not found: {epic_id}")

    normalized_prompt = _compact_text(prompt, 1600)
    if not normalized_prompt:
        raise ValueError("prompt is required")
    selected_quality = _select_quality(normalized_prompt, quality)
    selected_size = size or _select_size(normalized_prompt)
    selected_reference_key = reference_key or _generate_reference_key(context, epic_id)
    if not REFERENCE_KEY_RE.fullmatch(selected_reference_key):
        raise ValueError("reference_key must match ^[a-z][a-z0-9_]{0,63}$")

    full_prompt = _build_generation_prompt(
        epic=epic,
        user_prompt=normalized_prompt,
        active_images=context.store.list_active_images(epic_id),
    )
    image_result = run_synchronous_external_effect(
        context,
        ExternalSpec(
            provider="openai",
            endpoint=f"images.generate:{IMAGE_MODEL}",
            request_summary={
                "epic_id": epic_id,
                "reference_key": selected_reference_key,
                "quality": selected_quality,
                "size": selected_size,
                "prompt_preview": normalized_prompt[:200],
            },
            request_body={
                "model": IMAGE_MODEL,
                "prompt": full_prompt,
                "quality": selected_quality,
                "size": selected_size,
            },
        ),
        lambda idempotency_key: _call_openai_image(
            context,
            full_prompt,
            selected_quality,
            selected_size,
            idempotency_key,
        ),
    )
    openai_image = image_result.result

    blob_result = run_synchronous_external_effect(
        context,
        ExternalSpec(
            provider="supabase_storage",
            endpoint="blob.put",
            request_summary={
                "epic_id": epic_id,
                "reference_key": selected_reference_key,
                "mime_type": openai_image.mime_type,
                "byte_count": len(openai_image.content),
            },
            request_body={
                "epic_id": epic_id,
                "mime_type": openai_image.mime_type,
                "byte_count": len(openai_image.content),
                "source": "agent_generated_openai",
            },
        ),
        lambda idempotency_key: _put_generated_blob(
            context,
            epic_id,
            openai_image.content,
            openai_image.mime_type,
            idempotency_key,
        ),
    )
    blob_ref = blob_result.result

    deactivated = context.store.deactivate_active_image_reference(
        epic_id,
        selected_reference_key,
    )
    image = context.store.create_image(
        epic_id=epic_id,
        source="agent_generated",
        storage_url=blob_ref.key,
        prompt=full_prompt,
        quality=selected_quality,
        size=selected_size,
        reference_key=selected_reference_key,
        description=description or _derive_description(normalized_prompt),
        caption=caption,
        active=True,
    )
    return {
        "image": _metadata(image),
        "reference_key": image["reference_key"],
        "image_id": image["id"],
        "storage_url": image["storage_url"],
        "openai_external_request_id": image_result.request_id,
        "openai_provider_request_id": image_result.provider_request_id,
        "storage_external_request_id": blob_result.request_id,
        "storage_provider_request_id": blob_result.provider_request_id,
        "deactivated_image_ids": [row["id"] for row in deactivated],
    }


def _require_image(context: ToolContext, image_id: str) -> dict[str, Any]:
    image = context.store.load_image(image_id)
    if image is None:
        raise ValueError(f"image not found: {image_id}")
    return image


def _metadata(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": image["id"],
        "epic_id": image["epic_id"],
        "source": image["source"],
        "storage_url": image["storage_url"],
        "reference_key": image["reference_key"],
        "prompt": image.get("prompt"),
        "quality": image.get("quality"),
        "size": image.get("size"),
        "description": image.get("description"),
        "caption": image.get("caption"),
        "in_body": bool(image.get("in_body")),
        "active": bool(image.get("active")),
        "discord_attachment_id": image.get("discord_attachment_id"),
    }


def _media_type(storage_url: str) -> str:
    guessed, _encoding = mimetypes.guess_type(storage_url)
    return guessed or "image/png"


def _filename_for_image(storage_url: str, media_type: str) -> str:
    filename = storage_url.rsplit("/", 1)[-1]
    if "." in filename:
        return filename
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(media_type, ".png")
    return f"{filename or 'image'}{suffix}"


def _select_quality(prompt: str, explicit: str | None) -> str:
    if explicit is not None:
        if explicit not in {"low", "medium", "high"}:
            raise ValueError("quality must be low, medium, or high")
        return explicit
    lowered = prompt.lower()
    if any(word in lowered for word in ("rough", "sketch", "draft", "quick", "iteration")):
        return "low"
    if any(word in lowered for word in ("final", "deliverable", "production", "text-heavy", "text heavy")):
        return "high"
    return "medium"


def _select_size(prompt: str) -> str:
    lowered = prompt.lower()
    if any(word in lowered for word in ("wide", "landscape", "flow", "timeline", "diagram")):
        return "1536x1024"
    return "1024x1024"


def _generate_reference_key(context: ToolContext, epic_id: str) -> str:
    for _attempt in range(32):
        key = f"img_{uuid4().hex[:8]}"
        if not context.store.active_image_reference_exists(epic_id, key):
            return key
    raise RuntimeError("could not generate a unique image reference_key")


def _build_generation_prompt(
    *,
    epic: dict[str, Any],
    user_prompt: str,
    active_images: list[dict[str, Any]],
) -> str:
    lines = [
        "Create a reference image for this product-planning epic.",
        "",
        f"Requested image: {user_prompt}",
        "",
        f"Epic title: {_compact_text(str(epic.get('title') or ''), 160)}",
        f"Epic goal: {_compact_text(str(epic.get('goal') or ''), 320)}",
    ]
    body_text = _compact_text(str(epic.get("body") or ""), 1200)
    if body_text:
        lines.extend(["", "Epic body excerpt:", body_text])
    image_lines = [
        f"- {image.get('reference_key')}: {image.get('description') or image.get('caption') or 'no description'}"
        for image in active_images
        if image.get("description") or image.get("caption")
    ][:8]
    if image_lines:
        lines.extend(["", "Existing active image references:", *image_lines])
    lines.extend(
        [
            "",
            "Keep it useful as a planning reference. Avoid tiny unreadable labels unless the request explicitly needs text.",
        ]
    )
    return "\n".join(lines)


def _derive_description(prompt: str) -> str:
    description = _compact_text(prompt, 180)
    if not description.endswith("."):
        description += "."
    return f"Agent-generated image: {description}"


def _compact_text(value: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def _call_openai_image(
    context: ToolContext,
    prompt: str,
    quality: str,
    size: str,
    idempotency_key: str,
):
    result = context.openai_ops.generate_image(  # type: ignore[union-attr]
        prompt=prompt,
        quality=quality,
        size=size,
        idempotency_key=idempotency_key,
    )
    return (
        result.provider_request_id,
        result.response_summary,
        result,
    )


def _put_generated_blob(
    context: ToolContext,
    epic_id: str,
    content: bytes,
    mime_type: str,
    idempotency_key: str,
):
    try:
        ref = context.blob.put(  # type: ignore[union-attr,call-arg]
            epic_id,
            content,
            mime_type,
            idempotency_key=idempotency_key,
        )
    except TypeError:
        ref = context.blob.put(epic_id, content, mime_type)  # type: ignore[union-attr]
    return (
        ref.key,
        {"storage_url": ref.key, "mime_type": ref.mime_type, "size_bytes": ref.size_bytes},
        ref,
    )


__all__ = [
    "REFERENCE_KEY_RE",
    "generate_image",
    "list_images",
    "send_image",
    "update_image_metadata",
    "view_image",
]
