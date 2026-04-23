"""Dynamic API key pooling for Hermes-backed providers."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_RELOAD_TTL_SECONDS = 60.0
_PROVIDER_KEY_VARS = {
    "zhipu": "ZHIPU_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "google": "GEMINI_API_KEY",
}
_ENV_ALIASES = {
    "ZHIPU_API_KEY": ("ZHIPU_API_KEY", "GLM_API_KEY"),
    "ZHIPU_BASE_URL": ("ZHIPU_BASE_URL", "GLM_BASE_URL"),
    "GEMINI_API_KEY": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}
_PROVIDER_BASE_URL_VARS = {"zhipu": "ZHIPU_BASE_URL", "minimax": "MINIMAX_BASE_URL"}

# Direct API model name → OpenRouter model ID
_MINIMAX_OR_MODEL_MAP = {
    "MiniMax-M2.7-highspeed": "minimax/minimax-m2.7",
    "MiniMax-M2.7": "minimax/minimax-m2.7",
    "MiniMax-M2.5-highspeed": "minimax/minimax-m2.5",
    "MiniMax-M2.5": "minimax/minimax-m2.5",
    "MiniMax-M2.1-highspeed": "minimax/minimax-m2.1",
    "MiniMax-M2.1": "minimax/minimax-m2.1",
    "MiniMax-M2": "minimax/minimax-m2",
}


def minimax_openrouter_model(direct_model: str) -> str:
    """Map a MiniMax direct API model name to its OpenRouter equivalent."""
    return _MINIMAX_OR_MODEL_MAP.get(direct_model, "minimax/" + direct_model)
_DEFAULT_BASE_URLS = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "minimax": "https://api.minimax.io/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
}
@dataclass
class KeyEntry:
    key: str
    last_used: float = 0.0
    cooldown_until: float = 0.0
    failed: bool = False
class KeyPool:
    def __init__(self, ttl_seconds: float = _RELOAD_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._next_reload = 0.0
        self._hermes_env: dict[str, str] = {}
        self._entries: dict[str, list[KeyEntry]] = {provider: [] for provider in _PROVIDER_KEY_VARS}
    def _api_keys_path(self) -> Path:
        override = os.environ.get("MEGAPLAN_API_KEYS_PATH")
        if override:
            return Path(override).expanduser()
        repo_root = Path(__file__).resolve().parents[1]
        candidates = (
            repo_root / "auto_improve" / "api_keys.json",
        )
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]
    def _load_hermes_env_unlocked(self) -> dict[str, str]:
        result: dict[str, str] = {}
        env_path = Path.home() / ".hermes" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    result[key.strip()] = value.strip().strip("'\"")
        return result
    def _collect_key_values(self, env_var: str, hermes_env: dict[str, str]) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        names = _ENV_ALIASES.get(env_var, (env_var,))
        combined_names = set(hermes_env) | set(os.environ)
        for name in names:
            pattern = re.compile(rf"^{re.escape(name)}(?:_(\d+))?$")
            matches: list[tuple[int, str]] = []
            for candidate in combined_names:
                match = pattern.match(candidate)
                if match:
                    matches.append((int(match.group(1) or "1"), candidate))
            for _, candidate in sorted(matches):
                value = (os.environ.get(candidate) or hermes_env.get(candidate) or "").strip().strip("'\"")
                if value and value not in seen:
                    seen.add(value)
                    values.append(value)
        return values
    def _load_api_keys_json(self) -> list[str]:
        path = self._api_keys_path()
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        keys: list[str] = []
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    key = str(item.get("key", "")).strip()
                    if key and key not in keys:
                        keys.append(key)
        return keys
    def _load_keys_unlocked(self, now: float) -> None:
        if now < self._next_reload:
            return
        hermes_env = self._load_hermes_env_unlocked()
        self._hermes_env = hermes_env
        for provider, env_var in _PROVIDER_KEY_VARS.items():
            keys = self._collect_key_values(env_var, hermes_env)
            if provider == "zhipu":
                for key in self._load_api_keys_json():
                    if key not in keys:
                        keys.append(key)
            existing = {entry.key: entry for entry in self._entries.get(provider, [])}
            self._entries[provider] = [existing.get(key, KeyEntry(key=key)) for key in keys]
        self._next_reload = now + self._ttl_seconds
    def _get_api_credential_unlocked(self, env_var: str, hermes_env: dict[str, str] | None = None) -> str:
        source = hermes_env if hermes_env is not None else self._hermes_env
        for candidate in _ENV_ALIASES.get(env_var, (env_var,)):
            value = (os.environ.get(candidate) or source.get(candidate) or "").strip().strip("'\"")
            if value:
                return value
        return ""
    def load_hermes_env(self) -> dict[str, str]:
        with self._lock:
            self._load_keys_unlocked(time.monotonic())
            return dict(self._hermes_env)
    def get_api_credential(self, env_var: str, hermes_env: dict[str, str] | None = None) -> str:
        with self._lock:
            self._load_keys_unlocked(time.monotonic())
            return self._get_api_credential_unlocked(env_var, hermes_env)
    def acquire(self, provider: str) -> str:
        with self._lock:
            now = time.monotonic()
            self._load_keys_unlocked(now)
            eligible = [
                entry for entry in self._entries.get(provider, [])
                if not entry.failed and entry.cooldown_until <= now
            ]
            if not eligible:
                return ""
            entry = min(eligible, key=lambda item: item.last_used)
            entry.last_used = now
            return entry.key
    def report_429(self, provider: str, key: str, cooldown_secs: float = 60) -> None:
        if not key:
            return
        with self._lock:
            now = time.monotonic()
            self._load_keys_unlocked(now)
            for entry in self._entries.get(provider, []):
                if entry.key == key:
                    entry.cooldown_until = max(entry.cooldown_until, now + cooldown_secs)
                    entry.last_used = now
                    print(f"[key-pool] Cooling down {provider} key for {int(cooldown_secs)}s", file=sys.stderr)
                    return
    def report_failure(self, provider: str, key: str) -> None:
        if not key:
            return
        with self._lock:
            self._load_keys_unlocked(time.monotonic())
            for entry in self._entries.get(provider, []):
                if entry.key == key:
                    entry.failed = True
                    print(f"[key-pool] Marked {provider} key as failed", file=sys.stderr)
                    return
    def has_keys(self, provider: str) -> bool:
        with self._lock:
            self._load_keys_unlocked(time.monotonic())
            return bool(self._entries.get(provider))
_pool = KeyPool()
def _load_hermes_env() -> dict[str, str]:
    return _pool.load_hermes_env()
def _get_api_credential(env_var: str, hermes_env: dict[str, str] | None = None) -> str:
    return _pool.get_api_credential(env_var, hermes_env)
def acquire_key(provider: str) -> str:
    return _pool.acquire(provider)
def report_429(provider: str, key: str, cooldown_secs: float = 60) -> None:
    _pool.report_429(provider, key, cooldown_secs)
def report_failure(provider: str, key: str) -> None:
    _pool.report_failure(provider, key)
def has_keys(provider: str) -> bool:
    return _pool.has_keys(provider)
def resolve_model(model: str | None) -> tuple[str, dict[str, str]]:
    agent_kwargs: dict[str, str] = {}
    resolved_model = model or "anthropic/claude-opus-4.6"
    if resolved_model.startswith("zhipu:"):
        resolved_model = resolved_model[len("zhipu:"):]
        agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["zhipu"]) or _DEFAULT_BASE_URLS["zhipu"]
        agent_kwargs["api_key"] = acquire_key("zhipu")
    elif resolved_model.startswith("google:"):
        resolved_model = resolved_model[len("google:"):]
        agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["google"]
        agent_kwargs["api_key"] = acquire_key("google")
    elif resolved_model.startswith("minimax:"):
        resolved_model = resolved_model[len("minimax:"):]
        minimax_key = acquire_key("minimax")
        if minimax_key:
            agent_kwargs["base_url"] = _get_api_credential(_PROVIDER_BASE_URL_VARS["minimax"]) or _DEFAULT_BASE_URLS["minimax"]
            agent_kwargs["api_key"] = minimax_key
        else:
            resolved_model = "minimax/" + resolved_model
            agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["openrouter"]
            agent_kwargs["api_key"] = acquire_key("openrouter")
    else:
        # Non-prefixed models (e.g. "qwen/qwen3.5-27b") → route through OpenRouter
        or_key = acquire_key("openrouter")
        if or_key:
            agent_kwargs["base_url"] = _DEFAULT_BASE_URLS["openrouter"]
            agent_kwargs["api_key"] = or_key
    return resolved_model, agent_kwargs
