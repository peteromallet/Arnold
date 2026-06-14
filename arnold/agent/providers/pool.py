"""Generic API key pooling for provider-backed agent execution.

Provides:
* ``KeyPathSource`` — protocol for injecting the API keys file path.
* ``KeyEntry`` — per-key bookkeeping (last-used, cooldown, failed flag).
* ``KeyPool`` — thread-safe key pool with LRU acquisition, 429 cooldown,
  and failure marking.  Reads keys from environment variables and,
  optionally, from a JSON file supplied via a ``KeyPathSource``.

No imports from arnold.pipelines.megaplan.  Governor integration and
envelope context wiring belong in the megaplan provider layer.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

_RELOAD_TTL_SECONDS = 60.0

_PROVIDER_KEY_VARS = {
    "zhipu": "ZHIPU_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "mimo": "MIMO_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "google": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
}
_ENV_ALIASES = {
    "ZHIPU_API_KEY": ("ZHIPU_API_KEY", "GLM_API_KEY"),
    "ZHIPU_BASE_URL": ("ZHIPU_BASE_URL", "GLM_BASE_URL"),
    "GEMINI_API_KEY": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "FIREWORKS_API_KEY": ("FIREWORKS_API_KEY", "FIREWORKS_AI_API_KEY"),
    "FIREWORKS_BASE_URL": ("FIREWORKS_BASE_URL", "FIREWORKS_AI_BASE_URL"),
}
_PROVIDER_BASE_URL_VARS = {
    "zhipu": "ZHIPU_BASE_URL",
    "minimax": "MINIMAX_BASE_URL",
    "mimo": "MIMO_BASE_URL",
    "deepseek": "DEEPSEEK_BASE_URL",
    "fireworks": "FIREWORKS_BASE_URL",
}
_DEFAULT_BASE_URLS = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "minimax": "https://api.minimax.io/v1",
    "mimo": "https://api.xiaomimimo.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "deepseek": "https://api.deepseek.com",
    "fireworks": "https://api.fireworks.ai/inference/v1",
}

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


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class KeyPathSource(Protocol):
    """Supplies the path to an api_keys.json file for key pool loading."""

    def keys_path(self) -> Path: ...


# ---------------------------------------------------------------------------
# Key entry and pool
# ---------------------------------------------------------------------------


@dataclass
class KeyEntry:
    key: str
    last_used: float = 0.0
    cooldown_until: float = 0.0
    failed: bool = False


class KeyPool:
    """Thread-safe API key pool with LRU acquisition and 429 cooldown.

    Keys are sourced from environment variables (and ~/.hermes/.env) and,
    optionally, from a JSON file at the path returned by ``keys_path_source``.

    Governor integration and envelope context wiring are intentionally absent
    from this generic pool.  Add them via subclassing or a wrapper in the
    plugin layer.
    """

    def __init__(
        self,
        ttl_seconds: float = _RELOAD_TTL_SECONDS,
        keys_path_source: KeyPathSource | None = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._keys_path_source = keys_path_source
        self._lock = threading.Lock()
        self._next_reload = 0.0
        self._hermes_env: dict[str, str] = {}
        self._entries: dict[str, list[KeyEntry]] = {
            provider: [] for provider in _PROVIDER_KEY_VARS
        }

    def _api_keys_path(self) -> Path | None:
        """Return the JSON keys file path via the injected source, or None."""
        if self._keys_path_source is not None:
            return self._keys_path_source.keys_path()
        return None

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
        if path is None or not path.exists():
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
        """Acquire the least-recently-used key for *provider*.

        Returns an empty string when no eligible key is available.
        Governor charging is not performed here — add it in the plugin layer.
        """
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


__all__ = [
    "KeyEntry",
    "KeyPathSource",
    "KeyPool",
    "minimax_openrouter_model",
    "_DEFAULT_BASE_URLS",
    "_ENV_ALIASES",
    "_PROVIDER_BASE_URL_VARS",
    "_PROVIDER_KEY_VARS",
]
