"""AgentBox host backend for credential list/test/push/guide operations."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from agentbox.config import AgentBoxConfig

from .registry import KNOWN_CREDENTIALS


class CredentialBackendError(ValueError):
    """Raised when a credential backend operation cannot complete safely."""


@dataclass(frozen=True)
class CredentialRecord:
    """Public status for one credential. Never includes the secret value."""

    name: str
    provider: str
    present: bool
    pushed: bool
    last_tested: str | None = None
    test_status: str = "untested"
    test_message: str | None = None
    source: str | None = None
    destination: str | None = None


_Checker = Callable[[str, str], tuple[bool, str]]


def _credentials_root(config: AgentBoxConfig) -> Path:
    return Path(config.credentials_root)


def _value_path(config: AgentBoxConfig, name: str) -> Path:
    return _credentials_root(config) / name


def _meta_path(config: AgentBoxConfig, name: str) -> Path:
    return _credentials_root(config) / f"{name}.meta.json"


def _ensure_credentials_root(config: AgentBoxConfig) -> Path:
    root = _credentials_root(config)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _env_value(name: str, environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    value = env.get(name)
    return value.strip() if value else None


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_meta(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _write_meta(path: Path, meta: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(dict(meta), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _record_for(
    config: AgentBoxConfig,
    name: str,
    environ: Mapping[str, str] | None = None,
) -> CredentialRecord:
    root = _credentials_root(config)
    meta = _read_meta(root / f"{name}.meta.json") or {}
    return CredentialRecord(
        name=name,
        provider=KNOWN_CREDENTIALS[name]["provider"],
        present=_env_value(name, environ) is not None,
        pushed=_value_path(config, name).exists(),
        last_tested=meta.get("last_tested"),
        test_status=meta.get("test_status", "untested"),
        test_message=meta.get("test_message"),
        source=meta.get("source"),
        destination=meta.get("destination"),
    )


def list_credentials(
    config: AgentBoxConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[CredentialRecord]:
    """Return status for every known credential, without secret values."""

    _ensure_credentials_root(config)
    return [_record_for(config, name, environ) for name in sorted(KNOWN_CREDENTIALS)]


def push_credential(
    config: AgentBoxConfig,
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> CredentialRecord:
    """Copy one named credential from the local environment to a strict host path.

    The secret value is written only to the isolated credential file. Metadata
    records source, destination, and status but never the value.
    """

    if name not in KNOWN_CREDENTIALS:
        raise CredentialBackendError(f"Unknown credential: {name!r}")

    value = _env_value(name, environ)
    if value is None:
        raise CredentialBackendError(
            f"Credential {name!r} is not present in the environment; "
            f"set ${name} and retry."
        )

    root = _ensure_credentials_root(config)
    dest = root / name
    dest.write_text(value, encoding="utf-8")
    os.chmod(dest, 0o600)

    meta = {
        "name": name,
        "provider": KNOWN_CREDENTIALS[name]["provider"],
        "source": f"${name}",
        "destination": str(dest),
        "status": "pushed",
        "pushed_at": _now_iso(),
    }
    meta_path = root / f"{name}.meta.json"
    existing = _read_meta(meta_path) or {}
    existing.update(meta)
    existing["audit"] = existing.get("audit", []) + [
        {"event": "pushed", "timestamp": _now_iso()}
    ]
    _write_meta(meta_path, existing)

    return _record_for(config, name, environ)


def push_guide(
    config: AgentBoxConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return concise setup instructions for credentials not present locally."""

    records = list_credentials(config, environ=environ)
    guide: list[dict[str, Any]] = []
    for record in records:
        if record.present:
            continue
        guide.append(
            {
                "name": record.name,
                "provider": record.provider,
                "setup": (
                    f"Export {record.name} in your shell, then run "
                    f"`agentbox creds push {record.name}`."
                ),
            }
        )
    return guide


def run_credential_tests(
    config: AgentBoxConfig,
    *,
    names: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
    checkers: Mapping[str, _Checker] | None = None,
) -> list[dict[str, Any]]:
    """Run health checks for the requested (or all known) credentials.

    Each check is recorded in the credential's metadata audit log. Secret values
    are never written to metadata or returned.
    """

    records = list_credentials(config, environ=environ)
    if names:
        names_set = set(names)
        records = [r for r in records if r.name in names_set]

    checkers = checkers or _default_checkers()
    results: list[dict[str, Any]] = []
    for record in records:
        value = _env_value(record.name, environ)
        if value is None:
            ok = False
            status = "failed"
            message = f"{record.name} is not set"
        else:
            checker = checkers.get(record.provider, _check_generic)
            ok, message = checker(record.name, value)
            status = "passed" if ok else "failed"

        _record_test_audit(config, record.name, ok, message)
        results.append(
            {
                "name": record.name,
                "provider": record.provider,
                "ok": ok,
                "status": status,
                "message": message,
            }
        )
    return results


def _record_test_audit(
    config: AgentBoxConfig,
    name: str,
    ok: bool,
    message: str,
) -> None:
    meta_path = _meta_path(config, name)
    meta = _read_meta(meta_path) or {"name": name}
    meta.update(
        {
            "last_tested": _now_iso(),
            "test_status": "passed" if ok else "failed",
            "test_message": message,
        }
    )
    meta["audit"] = meta.get("audit", []) + [
        {
            "event": "tested",
            "timestamp": _now_iso(),
            "result": "passed" if ok else "failed",
        }
    ]
    _write_meta(meta_path, meta)


def _default_checkers() -> dict[str, _Checker]:
    return {
        "github": _check_github,
        "claude": _check_claude,
        "codex": _check_codex,
        "discord": _check_discord,
        "openai": _check_openai,
    }


def _check_generic(name: str, value: str) -> tuple[bool, str]:
    if len(value) < 4:
        return False, f"{name} is set but looks too short to be a token"
    return True, f"{name} is set"


def _check_github(name: str, value: str) -> tuple[bool, str]:
    if not re.match(r"^gh[pousr]_[A-Za-z0-9]{36,}$", value):
        return False, f"{name} does not look like a GitHub personal access token"
    try:
        import requests

        response = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {value}"},
            timeout=5,
        )
        if response.status_code == 200:
            return True, "GitHub token authenticated"
        if response.status_code == 401:
            return False, "GitHub token rejected (401)"
        return False, f"GitHub token check returned HTTP {response.status_code}"
    except Exception as exc:  # pragma: no cover - network failures are environment-specific
        return False, f"GitHub token check failed: {exc}"


def _check_claude(name: str, value: str) -> tuple[bool, str]:
    # Anthropic API keys begin with "sk-ant"; validate prefix/length only so the
    # check remains deterministic and does not incur API spend during preflight.
    if not value.startswith("sk-ant") or len(value) < 24:
        return False, f"{name} does not look like an Anthropic API key"
    return True, f"{name} looks like a valid Anthropic API key"


def _check_codex(name: str, value: str) -> tuple[bool, str]:
    # Codex routes through OpenAI; accept modern project-style keys.
    if not value.startswith("sk-") or len(value) < 24:
        return False, f"{name} does not look like an OpenAI/Codex API key"
    return True, f"{name} looks like a valid OpenAI/Codex API key"


def _check_discord(name: str, value: str) -> tuple[bool, str]:
    parts = value.split(".")
    if len(parts) != 3 or not all(parts):
        return False, f"{name} does not look like a Discord bot token"
    try:
        import requests

        response = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bot {value}"},
            timeout=5,
        )
        if response.status_code == 200:
            return True, "Discord bot token authenticated"
        if response.status_code == 401:
            return False, "Discord bot token rejected (401)"
        return False, f"Discord bot token check returned HTTP {response.status_code}"
    except Exception as exc:  # pragma: no cover - network failures are environment-specific
        return False, f"Discord bot token check failed: {exc}"


def _check_openai(name: str, value: str) -> tuple[bool, str]:
    if not value.startswith("sk-") or len(value) < 24:
        return False, f"{name} does not look like an OpenAI API key"
    return True, f"{name} looks like a valid OpenAI API key"


__all__ = [
    "CredentialBackendError",
    "CredentialRecord",
    "list_credentials",
    "push_credential",
    "push_guide",
    "test_credentials",
]
