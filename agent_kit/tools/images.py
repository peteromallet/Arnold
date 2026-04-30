"""Image management tools."""

from __future__ import annotations

import base64
import mimetypes
import re
from typing import Any

from agent_kit.ports import BlobRef
from agent_kit.tool_kit import ExternalSpec, ToolContext, register_tool


REFERENCE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

LIST_IMAGES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "source": {
            "type": ["string", "null"],
            "enum": ["agent_generated", "user_uploaded", None],
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
    }
    if not is_resident:
        result["discord_message_id"] = message["discord_message_id"]
        return result

    channel_id = str(context.metadata.get("channel_id") or "")
    endpoint = f"POST /channels/{channel_id}/messages"
    files = [
        {
            "image_id": image_id,
            "storage_url": image["storage_url"],
            "media_type": _media_type(image["storage_url"]),
            "reference_key": image["reference_key"],
        }
    ]

    def _post_and_update():
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
                },
                request_body={"content": content, "files": files},
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


__all__ = [
    "REFERENCE_KEY_RE",
    "list_images",
    "send_image",
    "update_image_metadata",
    "view_image",
]
