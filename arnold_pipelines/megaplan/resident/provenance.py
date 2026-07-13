"""Validated resident-delegation provenance shared across process boundaries.

The environment projection is intentionally routing-only: it never contains
message content, author names, credentials, provider responses, or arbitrary
caller metadata.  Child Megaplan/repair processes may persist this projection
without widening the resident's secret-retention boundary.
"""

from __future__ import annotations

import json
import os
import re
import contextvars
from contextlib import contextmanager
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

DELEGATION_CONTEXT_ENV = "ARNOLD_RESIDENT_DELEGATION_CONTEXT"
DELEGATION_CONTEXT_SCHEMA = "arnold-resident-delegation-provenance-v1"
NOT_APPLICABLE = "not_applicable"

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
# FileStore uses msg_/rconv_ ids while DBStore uses UUIDs.  Both are durable
# opaque record identities, so validation constrains syntax/length rather than
# coupling the transport contract to one backend's prefix.
_SOURCE_ID = _SAFE_ID
_CONVERSATION_ID = _SAFE_ID
_SNOWFLAKE = re.compile(r"^[0-9]{1,20}$")
_ALLOWED_FIELDS = (
    "schema_version",
    "applicability",
    "transport",
    "correlation_id",
    "custody_id",
    "delegation_id",
    "resident_conversation_id",
    "resident_turn_id",
    "source_record_id",
    "conversation_key",
    "discord_message_id",
    "reply_to_message_id",
    "guild_id",
    "channel_id",
    "thread_id",
    "dm_user_id",
    "root_run_id",
    "source_kind",
)
_ACTIVE_PROVENANCE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "arnold_resident_delegation_provenance", default=None
)


class DelegationProvenanceError(ValueError):
    """The supplied provenance cannot identify one safe reply target."""


def stable_identity(prefix: str, *parts: object) -> str:
    material = "\0".join(str(part or "") for part in parts)
    return f"{prefix}-{sha256(material.encode('utf-8')).hexdigest()[:24]}"


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_id(value: object, *, field: str, required: bool = False) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise DelegationProvenanceError(f"{field} is required")
        return None
    if not _SAFE_ID.fullmatch(text):
        raise DelegationProvenanceError(f"{field} is malformed")
    return text


def _snowflake(value: object, *, field: str, required: bool = False) -> str | None:
    text = _text(value)
    if text is None:
        if required:
            raise DelegationProvenanceError(f"{field} is required")
        return None
    if not _SNOWFLAKE.fullmatch(text) or int(text) <= 0:
        raise DelegationProvenanceError(f"{field} must be a Discord snowflake")
    return text


def _validate_conversation_target(payload: Mapping[str, Any]) -> dict[str, str | None]:
    key = _text(payload.get("conversation_key"))
    if key is None:
        raise DelegationProvenanceError("conversation_key is required")
    parts = key.split(":")
    guild_id = _text(payload.get("guild_id"))
    channel_id = _text(payload.get("channel_id"))
    thread_id = _text(payload.get("thread_id"))
    dm_user_id = _text(payload.get("dm_user_id"))
    if len(parts) == 3 and parts[:2] == ["discord", "dm"] and parts[2]:
        if guild_id is not None or thread_id is not None:
            raise DelegationProvenanceError("DM provenance cannot include guild/thread routing")
        if dm_user_id is not None and dm_user_id != parts[2]:
            raise DelegationProvenanceError("DM reply target conflicts with conversation_key")
        dm_user_id = parts[2]
    elif (
        len(parts) in {5, 7}
        and parts[:2] == ["discord", "guild"]
        and parts[2]
        and parts[3] == "channel"
        and parts[4]
        and (len(parts) == 5 or (parts[5] == "thread" and parts[6]))
    ):
        expected_thread = parts[6] if len(parts) == 7 else None
        if guild_id is not None and guild_id != parts[2]:
            raise DelegationProvenanceError("guild_id conflicts with conversation_key")
        if channel_id is not None and channel_id != parts[4]:
            raise DelegationProvenanceError("channel_id conflicts with conversation_key")
        if thread_id is not None and thread_id != expected_thread:
            raise DelegationProvenanceError("thread_id conflicts with conversation_key")
        if dm_user_id is not None:
            raise DelegationProvenanceError("guild provenance cannot include dm_user_id")
        guild_id, channel_id, thread_id = parts[2], parts[4], expected_thread
    else:
        raise DelegationProvenanceError("unsupported Discord conversation_key")
    return {
        "conversation_key": key,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "thread_id": thread_id,
        "dm_user_id": dm_user_id,
    }


def normalize_delegation_provenance(
    value: Mapping[str, Any],
    *,
    require_source_record: bool = True,
) -> dict[str, Any]:
    """Return the allow-listed canonical envelope or fail closed."""

    if not isinstance(value, Mapping):
        raise DelegationProvenanceError("delegation provenance must be an object")
    applicability = _text(value.get("applicability"))
    transport = _text(value.get("transport"))
    if applicability == NOT_APPLICABLE or transport in {"non_discord", NOT_APPLICABLE}:
        return {
            "schema_version": DELEGATION_CONTEXT_SCHEMA,
            "applicability": NOT_APPLICABLE,
            "transport": "non_discord",
            "source_kind": _safe_id(value.get("source_kind") or "explicit_non_discord", field="source_kind", required=True),
        }
    if applicability == "ambiguous":
        raise DelegationProvenanceError("Discord launch provenance is ambiguous")
    if transport != "discord":
        raise DelegationProvenanceError("transport must be discord or explicitly non_discord")

    routing = _validate_conversation_target(value)
    conversation_id = _text(value.get("resident_conversation_id") or value.get("conversation_id"))
    source_record_id = _text(value.get("source_record_id") or value.get("reply_target_source_record_id"))
    if conversation_id is None or not _CONVERSATION_ID.fullmatch(conversation_id):
        raise DelegationProvenanceError("resident_conversation_id is missing or malformed")
    if source_record_id is None:
        if require_source_record:
            raise DelegationProvenanceError("source_record_id is required")
    elif not _SOURCE_ID.fullmatch(source_record_id):
        raise DelegationProvenanceError("source_record_id is malformed")

    discord_message_id = _snowflake(
        value.get("discord_message_id") or value.get("message_id"),
        field="discord_message_id",
        required=True,
    )
    reply_to_message_id = _snowflake(
        value.get("reply_to_message_id"), field="reply_to_message_id", required=True
    )
    if discord_message_id != reply_to_message_id:
        raise DelegationProvenanceError("reply target must equal the original Discord message")
    correlation_id = _safe_id(value.get("correlation_id"), field="correlation_id")
    custody_id = _safe_id(value.get("custody_id"), field="custody_id")
    if correlation_id is None:
        correlation_id = stable_identity(
            "discord-corr", conversation_id, source_record_id, discord_message_id
        )
    if custody_id is None:
        custody_id = stable_identity(
            "discord-custody", conversation_id, source_record_id, discord_message_id
        )
    normalized: dict[str, Any] = {
        "schema_version": DELEGATION_CONTEXT_SCHEMA,
        "applicability": "applicable",
        "transport": "discord",
        "correlation_id": correlation_id,
        "custody_id": custody_id,
        "resident_conversation_id": conversation_id,
        "source_record_id": source_record_id,
        "conversation_key": routing["conversation_key"],
        "discord_message_id": discord_message_id,
        "reply_to_message_id": reply_to_message_id,
        "guild_id": routing["guild_id"],
        "channel_id": routing["channel_id"],
        "thread_id": routing["thread_id"],
        "dm_user_id": routing["dm_user_id"],
    }
    for field in ("delegation_id", "resident_turn_id", "root_run_id", "source_kind"):
        item = _safe_id(value.get(field), field=field)
        if item is not None:
            normalized[field] = item
    return normalized


def provenance_from_environment(*, strict: bool = True) -> dict[str, Any] | None:
    raw = os.environ.get(DELEGATION_CONTEXT_ENV)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return normalize_delegation_provenance(payload)
    except (json.JSONDecodeError, DelegationProvenanceError, TypeError, ValueError):
        if strict:
            raise DelegationProvenanceError(
                f"{DELEGATION_CONTEXT_ENV} contains malformed or ambiguous provenance"
            )
        return None


def encoded_provenance(value: Mapping[str, Any]) -> str:
    return json.dumps(
        normalize_delegation_provenance(value), sort_keys=True, separators=(",", ":")
    )


def environment_with_provenance(
    value: Mapping[str, Any] | None,
    *,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base if base is not None else os.environ)
    if value is None:
        env.pop(DELEGATION_CONTEXT_ENV, None)
    elif value.get("applicability") == "ambiguous":
        # Preserve only the fail-closed sentinel.  This lets a burst turn run
        # conversationally while every child-launch compatibility path still
        # rejects the ambiguous custody envelope.
        env[DELEGATION_CONTEXT_ENV] = json.dumps(
            {
                "schema_version": DELEGATION_CONTEXT_SCHEMA,
                "applicability": "ambiguous",
                "transport": "discord",
                "source_kind": "discord_burst",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        env[DELEGATION_CONTEXT_ENV] = encoded_provenance(value)
    return env


def safe_provenance_projection() -> dict[str, Any] | None:
    """Return validated process provenance for additive state projections."""

    active = _ACTIVE_PROVENANCE.get()
    # If the variable exists, malformed/ambiguous custody is not equivalent to
    # absence.  Every state-changing compatibility path must fail closed.
    return dict(active) if active is not None else provenance_from_environment(strict=True)


@contextmanager
def provenance_scope(value: Mapping[str, Any] | None):
    normalized = normalize_delegation_provenance(value) if value is not None else None
    token = _ACTIVE_PROVENANCE.set(normalized)
    try:
        yield normalized
    finally:
        _ACTIVE_PROVENANCE.reset(token)


def discord_origin_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_delegation_provenance(value)
    if normalized["applicability"] != "applicable":
        raise DelegationProvenanceError("non-Discord provenance has no discord_origin")
    return {
        "transport": "discord",
        "conversation_id": normalized["resident_conversation_id"],
        "conversation_key": normalized["conversation_key"],
        "message_id": normalized["discord_message_id"],
        "reply_to_message_id": normalized["reply_to_message_id"],
        "guild_id": normalized.get("guild_id"),
        "channel_id": normalized.get("channel_id"),
        "thread_id": normalized.get("thread_id"),
        "dm_user_id": normalized.get("dm_user_id"),
        "reply_target_source_record_id": normalized.get("source_record_id"),
        "correlation_id": normalized["correlation_id"],
        "custody_id": normalized["custody_id"],
    }


__all__ = [
    "DELEGATION_CONTEXT_ENV",
    "DELEGATION_CONTEXT_SCHEMA",
    "DelegationProvenanceError",
    "discord_origin_projection",
    "encoded_provenance",
    "environment_with_provenance",
    "normalize_delegation_provenance",
    "provenance_from_environment",
    "provenance_scope",
    "safe_provenance_projection",
    "stable_identity",
]
