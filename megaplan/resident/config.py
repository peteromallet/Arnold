"""Configuration boundary for resident orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ResidentMode = Literal["dev", "production"]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


class ResidentConfig(BaseModel):
    """Runtime configuration shared by Discord, scheduling, and tools."""

    mode: ResidentMode = "dev"
    discord_bot_token_env: str = "DISCORD_BOT_TOKEN"
    allowed_guild_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_channel_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_user_ids: tuple[str, ...] = Field(default_factory=tuple)
    admin_user_ids: tuple[str, ...] = Field(default_factory=tuple)
    model_provider: str = "openai"
    model_name: str = "gpt-5.4"
    model_api_key_env: str | None = None
    model_base_url: str | None = None
    model_timeout_s: float = Field(default=120.0, gt=0)
    max_tool_calls_per_turn: int = Field(default=8, gt=0)
    scheduler_poll_interval_s: float = Field(default=10.0, gt=0)
    scheduler_batch_size: int = Field(default=10, gt=0)
    stale_claim_timeout_s: float = Field(default=600.0, gt=0)
    stale_turn_timeout_s: float = Field(default=1800.0, gt=0)
    stale_control_claim_timeout_s: float = Field(default=600.0, gt=0)
    burst_idle_delay_s: float = Field(default=1.5, ge=0)
    burst_max_delay_s: float = Field(default=10.0, gt=0)
    confirmation_expiry_s: float = Field(default=900.0, gt=0)
    require_cloud_start_confirmation: bool = True
    cloud_yaml_path: Path = Path("cloud.yaml")

    @field_validator(
        "allowed_guild_ids",
        "allowed_channel_ids",
        "allowed_user_ids",
        "admin_user_ids",
        mode="before",
    )
    @classmethod
    def _coerce_id_tuple(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return _split_csv(value)
        if isinstance(value, (list, tuple, set)):
            return tuple(str(part).strip() for part in value if str(part).strip())
        raise TypeError("allowlist values must be strings or sequences")

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "ResidentConfig":
        env = environ or os.environ
        arnold_user_whitelist = env.get("DISCORD_USER_WHITELIST")
        return cls(
            mode=env.get("MEGAPLAN_RESIDENT_MODE", "dev"),
            allowed_guild_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_GUILDS")),
            allowed_channel_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_CHANNELS")),
            allowed_user_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_USERS") or arnold_user_whitelist),
            admin_user_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ADMIN_USERS") or arnold_user_whitelist),
            model_provider=env.get("MEGAPLAN_RESIDENT_MODEL_PROVIDER", "openai"),
            model_name=env.get("MEGAPLAN_RESIDENT_MODEL", "gpt-5.4"),
            model_api_key_env=env.get("MEGAPLAN_RESIDENT_MODEL_API_KEY_ENV"),
            model_base_url=env.get("MEGAPLAN_RESIDENT_MODEL_BASE_URL") or env.get("OPENAI_BASE_URL"),
            model_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_MODEL_TIMEOUT_S", 120.0),
            max_tool_calls_per_turn=_env_int(env, "MEGAPLAN_RESIDENT_MAX_TOOL_CALLS", 8),
            scheduler_poll_interval_s=_env_float(env, "MEGAPLAN_RESIDENT_SCHEDULER_POLL_S", 10.0),
            scheduler_batch_size=_env_int(env, "MEGAPLAN_RESIDENT_SCHEDULER_BATCH_SIZE", 10),
            stale_claim_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_STALE_CLAIM_TIMEOUT_S", 600.0),
            stale_turn_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_STALE_TURN_TIMEOUT_S", 1800.0),
            stale_control_claim_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_STALE_CONTROL_CLAIM_TIMEOUT_S", 600.0),
            burst_idle_delay_s=_env_float(env, "MEGAPLAN_RESIDENT_BURST_IDLE_S", 1.5),
            burst_max_delay_s=_env_float(env, "MEGAPLAN_RESIDENT_BURST_MAX_S", 10.0),
            confirmation_expiry_s=_env_float(env, "MEGAPLAN_RESIDENT_CONFIRMATION_EXPIRY_S", 900.0),
            require_cloud_start_confirmation=_env_bool(
                env,
                "MEGAPLAN_RESIDENT_REQUIRE_CLOUD_CONFIRMATION",
                True,
            ),
            cloud_yaml_path=Path(env.get("MEGAPLAN_RESIDENT_CLOUD_YAML", "cloud.yaml")),
        )

    @property
    def is_production(self) -> bool:
        return self.mode == "production"


def _env_int(env: dict[str, str], key: str, default: int) -> int:
    value = env.get(key)
    return default if value is None or value == "" else int(value)


def _env_float(env: dict[str, str], key: str, default: float) -> float:
    value = env.get(key)
    return default if value is None or value == "" else float(value)


def _env_bool(env: dict[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean token")
