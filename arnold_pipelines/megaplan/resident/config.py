"""Configuration boundary for resident orchestration."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ResidentMode = Literal["dev", "production"]
ResidentProfileName = Literal["megaplan", "agentbox_operator"]
DiscordBotRole = Literal["test", "production"]


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in value.split(",") if part.strip())


class ResidentConfig(BaseModel):
    """Runtime configuration shared by Discord, scheduling, and tools."""

    mode: ResidentMode = "dev"
    profile: ResidentProfileName = "megaplan"
    discord_bot_token_env: str = "DISCORD_BOT_TOKEN"
    discord_bot_role: DiscordBotRole = "test"
    allowed_guild_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_channel_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_user_ids: tuple[str, ...] = Field(default_factory=tuple)
    admin_user_ids: tuple[str, ...] = Field(default_factory=tuple)
    model_provider: str = "hermes"
    model_name: str = "zhipu:glm-5.2"
    model_api_key_env: str | None = None
    model_base_url: str | None = None
    codex_reasoning_effort: str = "low"
    codex_sandbox: str = "workspace-write"
    model_timeout_s: float = Field(default=120.0, gt=0)
    model_max_tokens: int = Field(default=65_536, gt=0)
    model_toolsets: str = "file,web,terminal"
    max_prompt_chars: int = Field(default=700_000, gt=0)
    voice_transcription_enabled: bool = True
    voice_transcription_provider: Literal["groq", "openai", "resident"] = "groq"
    voice_transcription_model: str = "whisper-large-v3-turbo"
    voice_transcription_api_key_env: str | None = None
    voice_transcription_base_url: str | None = None
    voice_max_attachment_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    voice_download_timeout_s: float = Field(default=20.0, gt=0)
    voice_transcription_timeout_s: float = Field(default=90.0, gt=0)
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
    # Canonical broad-status snapshot (written by the watchdog, read by every
    # status consumer). Defaults to the cloud-box path; overridable for tests.
    status_snapshot_path: Path = Path("/workspace/.megaplan/status/cloud-status.json")
    resident_export_root: Path = Path(".megaplan/resident_exports")
    escalation_repair_data_dir: Path | None = None
    escalation_repair_lock_dir: Path | None = None
    history_window: int = Field(default=10, ge=0)
    subagent_model_name: str = "deepseek:deepseek-v4-pro"
    subagent_models: tuple[str, ...] = Field(default_factory=tuple)
    subagent_max_tool_calls: int = Field(default=4, gt=0)
    special_requests_enabled: bool = True
    special_requests_interval_s: int = Field(default=21600, gt=0)
    special_requests_todo_path: Path = Path(".megaplan/resident/vp_todo_list.json")
    special_requests_conversation_key: str | None = None
    special_requests_subject_user_id: str | None = None
    special_requests_subagent_toolsets: str = "file,web,terminal"
    special_requests_subagent_timeout_s: float = Field(default=600.0, gt=0)
    special_requests_subagent_max_tokens: int = Field(default=65536, gt=0)
    default_timezone: str = "UTC"
    guild_timezone_defaults: dict[str, str] = Field(default_factory=dict)

    @field_validator(
        "allowed_guild_ids",
        "allowed_channel_ids",
        "allowed_user_ids",
        "admin_user_ids",
        "subagent_models",
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
        env = os.environ if environ is None else environ
        arnold_user_whitelist = env.get("DISCORD_USER_WHITELIST")
        return cls(
            mode=env.get("MEGAPLAN_RESIDENT_MODE", "dev"),
            profile=env.get("MEGAPLAN_RESIDENT_PROFILE", "megaplan"),
            discord_bot_role=env.get("MEGAPLAN_RESIDENT_DISCORD_BOT_ROLE", "test"),
            allowed_guild_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_GUILDS")),
            allowed_channel_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_CHANNELS")),
            allowed_user_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ALLOWED_USERS") or arnold_user_whitelist),
            admin_user_ids=_split_csv(env.get("MEGAPLAN_RESIDENT_ADMIN_USERS") or arnold_user_whitelist),
            model_provider=env.get("MEGAPLAN_RESIDENT_MODEL_PROVIDER", "hermes"),
            model_name=env.get("MEGAPLAN_RESIDENT_MODEL", "zhipu:glm-5.2"),
            model_api_key_env=env.get("MEGAPLAN_RESIDENT_MODEL_API_KEY_ENV"),
            model_base_url=env.get("MEGAPLAN_RESIDENT_MODEL_BASE_URL") or env.get("OPENAI_BASE_URL"),
            codex_reasoning_effort=env.get("MEGAPLAN_RESIDENT_CODEX_REASONING_EFFORT", "low"),
            codex_sandbox=env.get("MEGAPLAN_RESIDENT_CODEX_SANDBOX", "workspace-write"),
            model_timeout_s=_env_float(env, "MEGAPLAN_RESIDENT_MODEL_TIMEOUT_S", 120.0),
            model_max_tokens=_env_int(env, "MEGAPLAN_RESIDENT_MODEL_MAX_TOKENS", 65_536),
            model_toolsets=env.get(
                "MEGAPLAN_RESIDENT_MODEL_TOOLSETS", "file,web,terminal"
            ),
            max_prompt_chars=_env_int(env, "MEGAPLAN_RESIDENT_MAX_PROMPT_CHARS", 700_000),
            voice_transcription_enabled=_env_bool(
                env,
                "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_ENABLED",
                True,
            ),
            voice_transcription_provider=env.get(
                "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_PROVIDER",
                "groq",
            ),
            voice_transcription_model=env.get(
                "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_MODEL",
                "whisper-large-v3-turbo",
            ),
            voice_transcription_api_key_env=(
                env.get("MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_API_KEY_ENV") or None
            ),
            voice_transcription_base_url=(
                env.get("MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_BASE_URL") or None
            ),
            voice_max_attachment_bytes=_env_int(
                env,
                "MEGAPLAN_RESIDENT_VOICE_MAX_BYTES",
                20 * 1024 * 1024,
            ),
            voice_download_timeout_s=_env_float(
                env,
                "MEGAPLAN_RESIDENT_VOICE_DOWNLOAD_TIMEOUT_S",
                20.0,
            ),
            voice_transcription_timeout_s=_env_float(
                env,
                "MEGAPLAN_RESIDENT_VOICE_TRANSCRIPTION_TIMEOUT_S",
                90.0,
            ),
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
            status_snapshot_path=Path(
                env.get("MEGAPLAN_STATUS_SNAPSHOT", "/workspace/.megaplan/status/cloud-status.json")
            ),
            resident_export_root=Path(env.get("MEGAPLAN_RESIDENT_EXPORT_ROOT", ".megaplan/resident_exports")),
            escalation_repair_data_dir=(
                Path(env["MEGAPLAN_RESIDENT_REPAIR_DATA_DIR"])
                if env.get("MEGAPLAN_RESIDENT_REPAIR_DATA_DIR")
                else (Path(env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"]) if env.get("CLOUD_WATCHDOG_REPAIR_DATA_DIR") else None)
            ),
            escalation_repair_lock_dir=(
                Path(env["MEGAPLAN_RESIDENT_REPAIR_LOCK_DIR"])
                if env.get("MEGAPLAN_RESIDENT_REPAIR_LOCK_DIR")
                else (Path(env["CLOUD_WATCHDOG_REPAIR_LOCK_DIR"]) if env.get("CLOUD_WATCHDOG_REPAIR_LOCK_DIR") else None)
            ),
            history_window=_env_int(env, "MEGAPLAN_RESIDENT_HISTORY_WINDOW", 10),
            subagent_model_name=env.get("MEGAPLAN_RESIDENT_SUBAGENT_MODEL", "deepseek:deepseek-v4-pro"),
            subagent_models=_split_csv(env.get("MEGAPLAN_RESIDENT_SUBAGENT_MODELS")),
            subagent_max_tool_calls=_env_int(env, "MEGAPLAN_RESIDENT_SUBAGENT_MAX_TOOL_CALLS", 4),
            special_requests_enabled=_env_bool(env, "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_ENABLED", True),
            special_requests_interval_s=_env_int(env, "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_INTERVAL_S", 21600),
            special_requests_todo_path=Path(
                env.get("MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_TODO_PATH", ".megaplan/resident/vp_todo_list.json")
            ),
            special_requests_conversation_key=env.get("MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_CONVERSATION_KEY") or None,
            special_requests_subject_user_id=env.get("MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBJECT_USER_ID") or None,
            special_requests_subagent_toolsets=env.get(
                "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_TOOLSETS", "file,web,terminal"
            ),
            special_requests_subagent_timeout_s=_env_float(
                env, "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_TIMEOUT_S", 600.0
            ),
            special_requests_subagent_max_tokens=_env_int(
                env, "MEGAPLAN_RESIDENT_SPECIAL_REQUESTS_SUBAGENT_MAX_TOKENS", 65536
            ),
            default_timezone=env.get("MEGAPLAN_RESIDENT_DEFAULT_TIMEZONE", "UTC"),
            guild_timezone_defaults=_env_json_mapping(
                env, "MEGAPLAN_RESIDENT_GUILD_TIMEZONES"
            ),
        )

    @property
    def is_production(self) -> bool:
        return self.mode == "production"

    @property
    def allows_operational_discord_delivery(self) -> bool:
        """Require independent runtime and bot-role proof for outbox traffic."""

        return self.is_production and self.discord_bot_role == "production"


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


def _env_json_mapping(env: dict[str, str], key: str) -> dict[str, str]:
    raw = env.get(key)
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return {str(item_key): str(item_value) for item_key, item_value in value.items()}
