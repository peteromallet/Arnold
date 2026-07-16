"""Canonical resident timezone resolution and presentation formatting.

All inputs remain authoritative UTC values.  This module only creates display
projections or user-facing text and never writes localized wall times back to
control-plane records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import re
from typing import Any, Mapping
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from arnold_pipelines.megaplan.store import deterministic_idempotency_key

UTC_NAME = "UTC"
_ISO_TIMESTAMP_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<value>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2}))"
)
_ABSOLUTE_TIMESTAMP_KEYS = frozenset(
    {
        "timestamp",
        "generated_at",
        "watchdog_generated_at",
        "scheduled_for",
        "due_at",
        "occurred_at",
        "sent_at",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
        "completed_at",
        "checked_at",
        "last_checked_at",
        "last_active_at",
        "expires_at",
        "claimed_at",
        "fired_at",
        "cancelled_at",
        "delivered_at",
        "attempted_at",
        "next_attempt_at",
        "next_trigger_at",
        "materialized_at",
    }
)


class InvalidTimezone(ValueError):
    pass


class InvalidWallTime(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedTimezone:
    name: str
    source: str
    requested_name: str | None = None
    fallback_reason: str | None = None

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.name)

    def hot_context(self) -> dict[str, Any]:
        return {
            "timezone_name": self.name,
            "source": self.source,
            "requested_name": self.requested_name,
            "fallback_reason": self.fallback_reason,
            "format": "YYYY-MM-DD HH:MM:SS TZ (UTC±HH:MM)",
            "instruction": (
                f"Render absolute user-visible times in {self.name}; retain UTC in stored and "
                "structured control-plane records. Keep relative durations relative."
            ),
        }


def validate_timezone_name(value: object) -> str:
    name = str(value or "").strip()
    if not name:
        raise InvalidTimezone("timezone must be a non-empty IANA identifier")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidTimezone(f"unknown IANA timezone: {name}") from exc
    return name


def parse_utc_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("timestamp is empty")
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_timestamp(value: datetime | str, timezone_name: str) -> str:
    zone = ZoneInfo(validate_timezone_name(timezone_name))
    local = parse_utc_timestamp(value).astimezone(zone)
    offset = local.strftime("%z")
    numeric = f"{offset[:3]}:{offset[3:]}" if offset else "+00:00"
    return f"{local:%Y-%m-%d %H:%M:%S} {local.tzname() or timezone_name} (UTC{numeric})"


def localize_wall_time(
    wall_time: datetime,
    timezone_name: str,
    *,
    fold: int | None = None,
) -> datetime:
    """Resolve a naive local wall time, rejecting gaps and unchosen folds."""

    if wall_time.tzinfo is not None:
        raise InvalidWallTime("wall_time must be naive")
    zone = ZoneInfo(validate_timezone_name(timezone_name))
    candidates: list[datetime] = []
    for candidate_fold in (0, 1):
        candidate = wall_time.replace(tzinfo=zone, fold=candidate_fold)
        round_trip = candidate.astimezone(UTC).astimezone(zone)
        if round_trip.replace(tzinfo=None) == wall_time and round_trip.fold == candidate_fold:
            candidates.append(candidate)
    if not candidates:
        raise InvalidWallTime(
            f"{wall_time.isoformat()} does not exist in {timezone_name} because of a clock change"
        )
    distinct_offsets = {candidate.utcoffset() for candidate in candidates}
    if len(distinct_offsets) > 1:
        if fold not in {0, 1}:
            raise InvalidWallTime(
                f"{wall_time.isoformat()} is ambiguous in {timezone_name}; specify fold=0 or fold=1"
            )
        return next(candidate for candidate in candidates if candidate.fold == fold)
    return candidates[0]


def add_localized_timestamp_fields(value: Any, timezone_name: str) -> Any:
    """Copy a structured projection and add ``*_local`` display siblings."""

    validate_timezone_name(timezone_name)
    if isinstance(value, Mapping):
        rendered: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            rendered[key] = add_localized_timestamp_fields(item, timezone_name)
            if (
                key in _ABSOLUTE_TIMESTAMP_KEYS or key.endswith("_timestamp")
            ) and item is not None and not key.endswith("_local"):
                try:
                    rendered[f"{key}_local"] = format_timestamp(item, timezone_name)
                except (TypeError, ValueError):
                    pass
        return rendered
    if isinstance(value, list):
        return [add_localized_timestamp_fields(item, timezone_name) for item in value]
    if isinstance(value, tuple):
        return tuple(add_localized_timestamp_fields(item, timezone_name) for item in value)
    return value


def localize_text_timestamps(text: str, timezone_name: str) -> str:
    """Deterministically localize ISO timestamps in final user-facing prose."""

    validate_timezone_name(timezone_name)

    def replace(match: re.Match[str]) -> str:
        try:
            return format_timestamp(match.group("value"), timezone_name)
        except (TypeError, ValueError):
            return match.group("value")

    return _ISO_TIMESTAMP_RE.sub(replace, text)


class TimezoneService:
    """Resolve and update the canonical preference through the resident Store."""

    def __init__(self, store: Any, config: Any) -> None:
        self.store = store
        self.config = config

    def get_user_preference(self, user_id: str) -> Any | None:
        return self.store.load_resident_user_preference(
            transport="discord", user_id=str(user_id)
        )

    def set_user_timezone(
        self,
        user_id: str,
        timezone_name: str,
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        name = validate_timezone_name(timezone_name)
        return self.store.upsert_resident_user_preference(
            transport="discord",
            user_id=str(user_id),
            timezone_name=name,
            metadata={"schema_version": "resident-user-preferences-v1"},
            idempotency_key=idempotency_key
            or deterministic_idempotency_key(
                "resident-user-timezone", "discord", user_id, name, uuid4().hex
            ),
        )

    def resolve(
        self,
        *,
        user_id: str | None,
        conversation: Any | None = None,
        guild_id: str | None = None,
    ) -> ResolvedTimezone:
        if user_id:
            try:
                preference = self.get_user_preference(user_id)
            except Exception as exc:
                return ResolvedTimezone(
                    name=UTC_NAME,
                    source="utc_fallback",
                    fallback_reason=(
                        "user_preference_store_unavailable: "
                        f"{exc.__class__.__name__}"
                    ),
                )
            if preference is not None and preference.timezone_name:
                return _resolve_candidate(preference.timezone_name, "user")

        metadata = (
            dict(getattr(conversation, "metadata", {}) or {})
            if conversation is not None
            else {}
        )
        conversation_name = metadata.get("timezone_name") or metadata.get("timezone")
        if conversation_name:
            return _resolve_candidate(conversation_name, "conversation")

        effective_guild_id = guild_id or getattr(conversation, "guild_id", None)
        guild_defaults = dict(getattr(self.config, "guild_timezone_defaults", {}) or {})
        if effective_guild_id and guild_defaults.get(str(effective_guild_id)):
            return _resolve_candidate(guild_defaults[str(effective_guild_id)], "guild")

        system_name = getattr(self.config, "default_timezone", UTC_NAME) or UTC_NAME
        return _resolve_candidate(system_name, "system")


def _resolve_candidate(value: object, source: str) -> ResolvedTimezone:
    requested = str(value or "").strip() or None
    try:
        name = validate_timezone_name(requested)
    except InvalidTimezone as exc:
        return ResolvedTimezone(
            name=UTC_NAME,
            source="utc_fallback",
            requested_name=requested,
            fallback_reason=f"invalid_{source}_timezone: {exc}",
        )
    return ResolvedTimezone(name=name, source=source, requested_name=requested)


def timezone_prompt_instruction(resolved: ResolvedTimezone) -> str:
    return (
        "User-time presentation rule: render every absolute user-visible time in "
        f"{resolved.name} using local date/time plus timezone abbreviation and numeric UTC offset. "
        "Keep authoritative timestamps and structured control-plane/evidence records in UTC; never "
        "convert stored fields. Preserve relative durations (for example, '3 hours ago') as relative. "
        "When a structured object has both a UTC field and a *_local display field, quote the local "
        "display field to the user."
    )


__all__ = [
    "InvalidTimezone",
    "InvalidWallTime",
    "ResolvedTimezone",
    "TimezoneService",
    "add_localized_timestamp_fields",
    "format_timestamp",
    "localize_text_timestamps",
    "localize_wall_time",
    "timezone_prompt_instruction",
    "validate_timezone_name",
]
