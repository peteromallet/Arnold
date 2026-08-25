"""Read-only detection of provider credentials already present on this machine.

Detect-before-asking (North Star): the scan reports what exists — process env,
omp-loaded ``.env`` files, omp's agent.db, ``models.yml``, foreign CLI stores —
and never emits a secret value, only presence plus an origin descriptor.

Every accessor is read-only and every file/dir access is guarded: an unreadable
path is skipped silently (record nothing), so a scan can never crash on
permissions, malformed JSON/YAML, or a missing database.

``.env`` precedence mirrors oh-my-pi ``packages/utils/src/env.ts``: the real
process environment wins; among files, omp applies them in order
[cwd/.env, <agent-dir>/.env, <config-root>/.env] filling only names not yet
set — so the FIRST file in that order to define a name wins.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

from agentbox.onboarding.catalog import PROVIDERS, RANK_ORDER

# Belt-and-braces scrub for origin detail strings; origins are built from
# paths and enum-ish values only, but the North Star forbids secret leakage
# outright, so to_json() scrubs defensively anyway.
_SECRET_RE = re.compile(r"sk-[A-Za-z0-9]{8,}")

READY = "ready"
CANDIDATE = "candidate"
MISSING = "missing"

# agent.db stores some providers under historical aliases.
_DB_PROVIDER_ALIASES: Mapping[str, str] = {"kimi": "kimi-code"}


@dataclass(frozen=True)
class Origin:
    """Where a detected credential comes from (descriptor only — no secrets).

    ``wired`` marks origins that resolve a working route *today* (env var set,
    omp store row, models.yml entry, omp-native CLI route). Foreign stores
    that merely exist on the machine are ``wired=False`` -> candidate.
    """

    kind: str  # env | env_file | oauth | api_key | cli_store | cli_proxy | config
    detail: str
    wired: bool = True


@dataclass(frozen=True)
class ProviderScan:
    """Per-provider scan outcome."""

    id: str
    status: str  # ready | candidate | missing
    origin: Origin | None
    env_keys: tuple[str, ...]
    default_route: str


@dataclass(frozen=True)
class ScanReport:
    """Full machine scan; serializes via :meth:`to_json`."""

    providers: tuple[ProviderScan, ...]
    rank_order: tuple[str, ...]

    def to_json(self) -> dict:
        return {
            "providers": [
                {
                    "id": p.id,
                    "status": p.status,
                    "origin": None if p.origin is None else {
                        "kind": _SECRET_RE.sub("[redacted]", p.origin.kind),
                        "detail": _SECRET_RE.sub("[redacted]", p.origin.detail),
                    },
                    "env_keys": list(p.env_keys),
                    "default_route": p.default_route,
                }
                for p in self.providers
            ],
            "rank_order": list(self.rank_order),
        }


# ---------------------------------------------------------------------------
# .env parsing — Bun-compatible line semantics mirrored from omp's env.ts:
# optional `export` prefix, full-line comments, inline ` #` comments on
# unquoted values, single/double/backtick quoting. Parsed VALUES are used
# internally for presence only and never leave this module.
# ---------------------------------------------------------------------------

_ENV_NAME_CHARS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_env_line(line: str) -> tuple[str, str] | None:
    trimmed = line.strip()
    if not trimmed or trimmed.startswith("#"):
        return None
    eq_index = trimmed.find("=")
    if eq_index == -1:
        return None
    key = trimmed[:eq_index].strip()
    exported = re.match(r"^export[ \t]+(.*)$", key)
    if exported:
        key = exported.group(1).strip()
    if not _ENV_NAME_CHARS.match(key):
        return None
    raw = trimmed[eq_index + 1 :].lstrip(" \t")
    quote = raw[:1]
    if quote in ('"', "'", "`"):
        close = raw.find(quote, 1)
        while close != -1 and raw[close - 1] == "\\":
            close = raw.find(quote, close + 1)
        value = raw[1:] if close == -1 else raw[1:close]
        return key, value
    comment_index = re.search(r"[ \t]#", raw)
    if comment_index:
        raw = raw[: comment_index.start()]
    return key, raw.rstrip()


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into key/value pairs; unreadable/missing -> {}."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    result: dict[str, str] = {}
    for line in content.split("\n"):
        parsed = _parse_env_line(line)
        if parsed is not None:
            result[parsed[0]] = parsed[1]
    return result


# ---------------------------------------------------------------------------
# Adapter 1: foreign CLI credential stores (presence + parse only)
# ---------------------------------------------------------------------------

def _foreign_store_origins(
    home: Path,
    environ: Mapping[str, str],
) -> dict[str, list[Origin]]:
    """Probe foreign CLIs' own credential stores.

    openai-codex/grok map to omp-native routes, so a usable store means the
    route resolves today -> ready. The rest are found-but-not-wired ->
    candidate. ~/.hermes is probed for parity with the store table but has no
    catalog provider yet, so it contributes nothing to the report.
    """
    origins: dict[str, list[Origin]] = {}

    codex_auth = home / ".codex" / "auth.json"
    try:
        if codex_auth.is_file():
            json.loads(codex_auth.read_text(encoding="utf-8"))
            origins.setdefault("openai-codex", []).append(
                Origin(kind="cli_store", detail=str(codex_auth), wired=True)
            )
    except (OSError, ValueError):
        pass

    grok_auth = home / ".grok" / "auth.json"
    try:
        if grok_auth.is_file():
            origins.setdefault("grok", []).append(
                Origin(kind="cli_proxy", detail=str(grok_auth), wired=True)
            )
    except OSError:
        pass

    kimi_dir = home / ".kimi"
    try:
        if kimi_dir.is_dir():
            origins.setdefault("kimi-code", []).append(
                Origin(kind="cli_store", detail=str(kimi_dir), wired=False)
            )
    except OSError:
        pass

    claude_creds = home / ".claude" / ".credentials.json"
    try:
        # Never marked ready: Claude's OAuth belongs to another product until
        # explicitly onboarded; an unreadable (e.g. keychain-gated) file still
        # proves existence, hence candidate either way.
        if claude_creds.exists():
            origins.setdefault("anthropic", []).append(
                Origin(kind="cli_store", detail=str(claude_creds), wired=False)
            )
    except OSError:
        pass

    # Presence-only probe: no catalog provider maps to hermes yet.
    try:
        (home / ".hermes").exists()
    except OSError:
        pass

    return origins


# ---------------------------------------------------------------------------
# Adapter 2: environment sweep (process env + omp-loaded .env files)
# ---------------------------------------------------------------------------

def _omp_env_files(home: Path, cwd: Path, environ: Mapping[str, str]) -> list[Path]:
    """Files omp loads .env from, in omp's apply (highest-priority-first) order.

    Mirrors oh-my-pi packages/utils/src/env.ts: the process environment wins,
    then cwd/.env, then <agent-dir>/.env, then <config-root>/.env (each file
    only fills names no earlier source set).
    """
    config_root = home / ".omp"
    agent_dir_env = environ.get("PI_CODING_AGENT_DIR")
    agent_dir = Path(agent_dir_env) if agent_dir_env else config_root / "agent"
    return [
        cwd / ".env",
        agent_dir / ".env",
        config_root / ".env",
    ]


def _env_origins(
    spec_env_keys: Mapping[str, tuple[str, ...]],
    environ: Mapping[str, str],
    env_files: list[tuple[Path, dict[str, str]]],
) -> dict[str, list[Origin]]:
    origins: dict[str, list[Origin]] = {}
    for provider_id, keys in spec_env_keys.items():
        for key in keys:
            if environ.get(key):
                origins.setdefault(provider_id, []).append(
                    Origin(kind="env", detail=f"{key} in process environment")
                )
                break
        else:
            for path, parsed in env_files:
                matched = next((key for key in keys if parsed.get(key)), None)
                if matched is not None:
                    origins.setdefault(provider_id, []).append(
                        Origin(kind="env_file", detail=f"{path} ({matched})")
                    )
                    break
    return origins


# ---------------------------------------------------------------------------
# Adapter 3: omp agent.db auth_credentials (read-only URI mode)
# ---------------------------------------------------------------------------

def _agent_db_path(home: Path, environ: Mapping[str, str]) -> Path | None:
    override = environ.get("PI_CODING_AGENT_DIR")
    base = Path(override) if override else home / ".omp" / "agent"
    candidate = base / "agent.db"
    return candidate if candidate.is_file() else None


def _db_origins(agent_db: Path | None) -> dict[str, list[Origin]]:
    if agent_db is None:
        return {}
    origins: dict[str, list[Origin]] = {}
    connection = sqlite3.connect(f"file:{agent_db}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT provider, credential_type FROM auth_credentials "
            "WHERE disabled_cause IS NULL"
        ).fetchall()
    finally:
        connection.close()
    for provider, credential_type in rows:
        provider_id = _DB_PROVIDER_ALIASES.get(provider, provider)
        if provider_id not in PROVIDERS or credential_type is None:
            continue
        origins.setdefault(provider_id, []).append(
            Origin(kind=credential_type, detail=f"{agent_db} ({provider})")
        )
    return origins


# ---------------------------------------------------------------------------
# Adapter 4: ~/.omp/agent/models.yml command-backed / static keys
# ---------------------------------------------------------------------------

def _models_yml_path(home: Path, environ: Mapping[str, str]) -> Path | None:
    override = environ.get("PI_CODING_AGENT_DIR")
    base = Path(override) if override else home / ".omp" / "agent"
    candidate = base / "models.yml"
    return candidate if candidate.is_file() else None


def _models_yml_origins(models_yml: Path | None) -> dict[str, list[Origin]]:
    if models_yml is None:
        return {}
    data = yaml.safe_load(models_yml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    providers = data.get("providers")
    if not isinstance(providers, dict):
        return {}
    origins: dict[str, list[Origin]] = {}
    for name, entry in providers.items():
        provider_id = _DB_PROVIDER_ALIASES.get(name, name)
        if provider_id not in PROVIDERS or not isinstance(entry, dict):
            continue
        api_key = entry.get("apiKey")
        if not api_key:
            continue
        kind = "cli_proxy" if str(api_key).startswith("!") else "config"
        origins.setdefault(provider_id, []).append(
            Origin(kind=kind, detail=f"{models_yml} ({name})")
        )
    return origins


# ---------------------------------------------------------------------------
# Scan orchestration
# ---------------------------------------------------------------------------

def scan_providers(
    *,
    home: Path | None = None,
    cwd: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ScanReport:
    """Scan every adapter read-only and rank results by ``RANK_ORDER``.

    All parameters default to the live machine (``HOME`` / cwd /
    ``os.environ``); tests pass isolated paths instead of touching global
    state. Any adapter failure is swallowed: it contributes nothing rather
    than crashing the scan.
    """
    home = home if home is not None else Path(os.environ.get("HOME") or Path.home())
    cwd = cwd if cwd is not None else Path.cwd()
    environ = os.environ if environ is None else environ

    origins: dict[str, list[Origin]] = {}
    for adapter_result in (
        _foreign_store_origins(home, environ),
        _env_origins(
            {pid: spec.env_keys for pid, spec in PROVIDERS.items()},
            environ,
            [(p, parse_env_file(p)) for p in _omp_env_files(home, cwd, environ)],
        ),
        _safe(_db_origins, _agent_db_path(home, environ)),
        _safe(_models_yml_origins, _models_yml_path(home, environ)),
    ):
        for provider_id, found in adapter_result.items():
            origins.setdefault(provider_id, []).extend(found)

    scans = []
    for provider_id in PROVIDERS:
        found = origins.get(provider_id, ())
        wired = [o for o in found if o.wired]
        chosen = wired[0] if wired else (found[0] if found else None)
        status = READY if wired else (CANDIDATE if found else MISSING)
        spec = PROVIDERS[provider_id]
        scans.append(
            ProviderScan(
                id=provider_id,
                status=status,
                origin=chosen,
                env_keys=spec.env_keys,
                default_route=spec.default_route,
            )
        )

    return ScanReport(
        providers=tuple(scans),
        rank_order=tuple(pid for pid in PROVIDERS if pid in RANK_ORDER),
    )


def _safe(adapter, *args) -> dict[str, list[Origin]]:
    """Run one adapter; any failure records nothing (never crash the scan)."""
    try:
        return adapter(*args)
    except Exception:
        return {}


__all__ = [
    "CANDIDATE",
    "MISSING",
    "READY",
    "Origin",
    "ProviderScan",
    "ScanReport",
    "parse_env_file",
    "scan_providers",
]
