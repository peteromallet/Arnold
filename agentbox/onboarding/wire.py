"""Wire accepted credentials into oh-my-pi's own stores (persist-once) and
verify the resulting route. Companion to :mod:`agentbox.onboarding.detect`.

North Star: every accepted credential lands in omp's own stores
(``<agent-dir>/agent.db`` via ``omp auth-broker`` or ``<agent-dir>/models.yml``),
provenance is recorded, and secrets are never printed or logged.

Pinned CLIProxyAPI import schema (read from the oh-my-pi fork
``packages/coding-agent/src/cli/auth-broker-cli.ts`` AND verified empirically
2026-08-25 in an isolated ``PI_CODING_AGENT_DIR`` sandbox):

Input JSON fields (``CliProxyCredentialJson``):
    ``type``            -- maps via CLIPROXY_TYPE_TO_PROVIDER:
                           claude->anthropic, codex->openai-codex,
                           gemini/gemini-cli->google-gemini-cli,
                           antigravity->google-antigravity. Unknown types are
                           SKIPPED (there is NO ``openai`` type);
                           ``--provider=<id>`` overrides.
    ``access_token``    -- REQUIRED
    ``refresh_token``   -- REQUIRED (entry skipped otherwise)
    ``expired``         -- REQUIRED, RFC3339 date string
    ``email``           -- optional identity (becomes identity_key)
    ``account_id``      -- optional identity
    ``id_token``, ``last_refresh`` -- parsed but unused by the importer
    ``disabled``        -- true => skipped unless ``--include-disabled``

Successful stdout with ``--json``::

    {"dryRun": false,
     "imported": [{"provider": ..., "email": ..., "file": ...}],
     "plan": [...],
     "skipped": [{"file": ..., "reason": ...}]}

Skips still exit 0; only broker-upload failures emit ``{"error": ..., "file":
...}`` rows and set exit 1. Local-store landing row (``auth_credentials``):
``(id INTEGER PK, provider TEXT, credential_type TEXT ('oauth'|'api_key'),
data TEXT JSON {access, refresh, expires[, email][, accountId]}, identity_key
TEXT|null ('email:<email>'), disabled_cause TEXT|null, created_at/updated_at
INTEGER epoch seconds)``.

Because the importer REQUIRES a ``refresh_token``, a *static* API key wired
through this route is stored with a synthetic non-secret placeholder refresh
token (``arnold-static-no-refresh``) and a ~10-year expiry, so omp treats it
as a long-lived bearer token and never attempts a refresh with real-looking
but bogus material. Providers without a CLIProxyAPI type mapping (everything
except anthropic/openai-codex) fall back to a static ``apiKey`` in models.yml.

All subprocess traffic goes through :func:`_run` so tests can monkeypatch it.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

# Belt-and-braces scrub, mirroring agentbox.onboarding.detect._SECRET_RE.
# Covers the real key shapes: sk-* (incl. sk-ant-api03-, sk-proj-, sk-or-v1-,
# whose bodies contain hyphens) and xai-* keys.
_SECRET_RE = re.compile(r"(?:sk|xai)-[A-Za-z0-9_-]{8,}")
_REDACTED = "[REDACTED]"
_PROVENANCE_FILE = ".arnold_onboarding_provenance.jsonl"

# Reverse of the fork's CLIPROXY_TYPE_TO_PROVIDER, restricted to providers
# where the resulting omp provider id matches our catalog id exactly. The
# gemini/antigravity types land under "google-gemini-cli"/"google-antigravity",
# which are NOT catalog ids, so they intentionally stay unmapped here.
PROVIDER_TO_CLIPROXY_TYPE: dict[str, str] = {
    "anthropic": "claude",
    "openai-codex": "codex",
}

# Synthetic refresh-token placeholder for static keys (see module docstring).
_STATIC_REFRESH_PLACEHOLDER = "arnold-static-no-refresh"
_STATIC_KEY_EXPIRY_DAYS = 3650


@dataclass(frozen=True)
class WireResult:
    """Outcome of one wiring attempt (never contains secret material)."""

    ok: bool
    provider: str
    mechanism: str  # auth-broker-import | auth-broker-login | models-yml | cli-proxy-models-yml
    detail: str = ""
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of a route smoke-ping; output is always redacted/truncated."""

    ok: bool
    latency_ms: int
    output: str


# ---------------------------------------------------------------------------
# Subprocess seam (single choke point for tests to monkeypatch)
# ---------------------------------------------------------------------------

def _run(
    cmd: list[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run one subprocess. All wire/verify subprocess calls go through here."""
    return subprocess.run(  # noqa: PLW1510 - rc checked by callers
        cmd,
        capture_output=capture,
        text=capture,
        env=dict(env) if env is not None else None,
        timeout=timeout,
        check=False,
    )


def _sandbox_env(agent_dir: Path) -> dict[str, str]:
    """Environment pinning every child omp process to the given agent dir."""
    return {**os.environ, "PI_CODING_AGENT_DIR": str(agent_dir)}


def _redact(text: str, extra_secrets: Iterable[str] = ()) -> str:
    for secret in extra_secrets:
        if secret:
            text = text.replace(secret, _REDACTED)
    return _SECRET_RE.sub(_REDACTED, text)


# ---------------------------------------------------------------------------
# Route 1: static API key -> omp agent.db via `omp auth-broker import`
# ---------------------------------------------------------------------------

def wire_api_key(
    provider_id: str,
    api_key: str,
    *,
    agent_dir: Path,
    origin_kind: str = "manual-entry",
    origin_detail: str = "",
) -> WireResult:
    """Persist a static key into omp's agent.db via ``omp auth-broker import``.

    Builds a CLIProxyAPI-shaped JSON in a 0600 tempfile, imports it against
    the sandboxed agent dir, and deletes the tempfile in a finally block.
    Providers without a CLIProxyAPI type mapping fall back to a static
    models.yml ``apiKey`` (see :func:`_wire_models_yml_static`).
    """
    agent_dir = Path(agent_dir)
    cli_type = PROVIDER_TO_CLIPROXY_TYPE.get(provider_id)
    if cli_type is None:
        return _wire_models_yml_static(provider_id, api_key, agent_dir=agent_dir)

    expires = (
        datetime.now(timezone.utc) + timedelta(days=_STATIC_KEY_EXPIRY_DAYS)
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    payload = {
        "type": cli_type,
        "access_token": api_key,
        "refresh_token": _STATIC_REFRESH_PLACEHOLDER,
        "expired": expires,
    }

    fd, tmp_name = tempfile.mkstemp(prefix="arnold-wire-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        proc = _run(
            ["omp", "auth-broker", "import", str(tmp_path), "--json"],
            env=_sandbox_env(agent_dir),
            timeout=120,
        )
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass

    imported: list = []
    skipped_reasons: list[str] = []
    parse_error = ""
    try:
        report = json.loads(proc.stdout or "{}")
        imported = report.get("imported") or []
        skipped_reasons = [
            f"{entry.get('file', '?')}: {entry.get('reason', '?')}"
            for entry in report.get("skipped") or []
        ]
    except (json.JSONDecodeError, TypeError):
        parse_error = "unparseable import output"

    ok = proc.returncode == 0 and any(e.get("provider") == provider_id for e in imported)
    detail_parts: list[str] = []
    if not ok and proc.returncode != 0:
        detail_parts.append(
            f"exit={proc.returncode} {_redact(proc.stderr or '', (api_key,))}".strip()
        )
    if parse_error:
        detail_parts.append(parse_error)
    detail_parts.extend(_redact(reason, (api_key,)) for reason in skipped_reasons)
    return WireResult(
        ok=ok,
        provider=provider_id,
        mechanism="auth-broker-import",
        detail="; ".join(detail_parts),
        provenance={
            "provider": provider_id,
            "mechanism": "auth-broker-import",
            "origin_kind": origin_kind,
            "origin_detail": origin_detail,
        },
    )


# ---------------------------------------------------------------------------
# Route 2: interactive OAuth -> `omp auth-broker login`
# ---------------------------------------------------------------------------

def wire_oauth(provider_id: str, *, agent_dir: Path) -> WireResult:
    """Run ``omp auth-broker login <provider>`` inheriting stdio (interactive).

    Fails closed on non-TTY stdin (headless paths must behave exactly as
    today per the North Star).
    """
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"oauth login for {provider_id!r} requires an interactive terminal"
        )
    proc = _run(
        ["omp", "auth-broker", "login", provider_id],
        env=_sandbox_env(Path(agent_dir)),
        timeout=None,
        capture=False,
    )
    return WireResult(
        ok=proc.returncode == 0,
        provider=provider_id,
        mechanism="auth-broker-login",
        detail="" if proc.returncode == 0 else f"exit={proc.returncode}",
        provenance={
            "provider": provider_id,
            "mechanism": "auth-broker-login",
            "origin_kind": "interactive-oauth",
            "origin_detail": "",
        },
    )


# ---------------------------------------------------------------------------
# Route 3: foreign-CLI proxy -> command-backed models.yml apiKey (grok-style)
# ---------------------------------------------------------------------------

# Minimal reimplementation of the fork's docs/omp-setup/grok-token.py with the
# hardcoded home path replaced by a runtime expanduser lookup.
_GROK_TOKEN_SCRIPT = '''#!/usr/bin/env python3
"""Print the current x.ai bearer token for the grok CLI proxy, refreshing via
OIDC when near expiry. Used as a command-backed apiKey in models.yml
(apiKey: "!python3 .../grok-token.py"). Writes refreshed tokens back to
~/.grok/auth.json so the grok CLI and omp stay in sync.
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

AUTH_PATH = os.path.join(os.path.expanduser("~"), ".grok", "auth.json")
ISSUER_MARKER = "auth.x.ai"
REFRESH_MARGIN_SECONDS = 300
DEFAULT_EXPIRES_IN = 21600


def load_auth():
    with open(AUTH_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def find_entry(auth):
    for key, entry in auth.items():
        if ISSUER_MARKER in key and isinstance(entry, dict):
            return key, entry
    raise KeyError(f"no {ISSUER_MARKER} entry in {AUTH_PATH}")


def expires_at_ts(entry):
    raw = entry.get("expires_at")
    if not raw:
        return 0
    return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()


def refresh(entry):
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": entry["refresh_token"],
            "client_id": entry["oidc_client_id"],
        }
    ).encode()
    req = urllib.request.Request(
        entry["oidc_issuer"] + "/oauth2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read())
    entry["key"] = result["access_token"]
    if result.get("refresh_token"):
        entry["refresh_token"] = result["refresh_token"]
    entry["expires_at"] = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=result.get("expires_in", DEFAULT_EXPIRES_IN))
    ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return result["access_token"]


def main():
    auth = load_auth()
    _, entry = find_entry(auth)
    key = entry.get("key")
    if key and expires_at_ts(entry) > datetime.datetime.now(datetime.timezone.utc).timestamp() + REFRESH_MARGIN_SECONDS:
        sys.stdout.write(key)
        return
    new_key = refresh(entry)
    with open(AUTH_PATH, "w", encoding="utf-8") as fh:
        json.dump(auth, fh, indent=2)
    sys.stdout.write(new_key)


if __name__ == "__main__":
    main()
'''

_GROK_ENTRY_TEMPLATE: dict = {
    "baseUrl": "https://cli-chat-proxy.grok.com/v1",
    "api": "openai-completions",
    "headers": {
        "X-XAI-Token-Auth": "xai-grok-cli",
        "x-grok-client-version": "1.0.5",
        "x-grok-client-identifier": "grok-shell",
    },
    "models": [
        {
            "id": "grok-4.6",
            "name": "Grok 4.6",
            "contextWindow": 500000,
            "maxTokens": 32768,
            "reasoning": True,
            "thinking": {"mode": "effort", "efforts": ["low", "medium", "high", "xhigh"], "defaultLevel": "high"},
            "compat": {"supportsDeveloperRole": True, "supportsReasoningEffort": True, "reasoningContentField": "reasoning_content"},
        },
        {
            "id": "grok-4.5",
            "name": "Grok 4.5",
            "contextWindow": 500000,
            "maxTokens": 32768,
            "reasoning": True,
            "thinking": {"mode": "effort", "efforts": ["low", "medium", "high", "xhigh"], "defaultLevel": "high"},
            "compat": {"supportsDeveloperRole": True, "supportsReasoningEffort": True, "reasoningContentField": "reasoning_content"},
        },
    ],
}


def _install_grok_token_script(agent_dir: Path) -> Path:
    """Copy the grok-token helper into the agent dir, chmod +x."""
    agent_dir.mkdir(parents=True, exist_ok=True)
    script_path = agent_dir / "grok-token.py"
    script_path.write_text(_GROK_TOKEN_SCRIPT, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script_path


def _render_provider_block(provider_id: str, entry: Mapping) -> str:
    """Render one provider entry as an indented two-space YAML block."""
    dumped = yaml.safe_dump({provider_id: dict(entry)}, sort_keys=False, default_flow_style=False)
    return "\n".join("  " + line for line in dumped.strip("\n").splitlines())


def _rewrite_via_yaml(text: str, provider_id: str, block: str) -> str:
    """Fallback splice for anchor/flow-shaped providers headers (loses comments)."""
    import yaml as _yaml

    data = _yaml.safe_load(text) or {}
    providers = data.get("providers")
    if not isinstance(providers, dict):
        raise ValueError("models.yml has non-mapping providers section; refusing to rewrite")
    entry = _yaml.safe_load(block)
    assert isinstance(entry, dict), "provider block must be a mapping"
    providers[provider_id] = entry[provider_id]
    return _yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def _splice_provider(text: str, provider_id: str, block: str) -> str:
    """Textually insert/replace one provider block, preserving all other bytes.

    Falls back to a full yaml.safe_load/safe_dump rewrite when the top-level
    ``providers:`` header carries YAML anchors or flow tokens (``providers: &a``,
    ``providers: {``) — byte-preserving splicing cannot represent those shapes,
    and appending would create a duplicate key that silently drops user content
    under last-wins mapping resolution.
    """
    import re as _re

    lines = text.splitlines(keepends=True)
    header_re = _re.compile(r"^providers:\s*(#.*)?$")
    exotic_header_re = _re.compile(r"^providers:\s*(?!\s*(?:#.*)?$).+$")
    key_re = _re.compile(rf"^  {_re.escape(provider_id)}:\s*(#.*)?$")
    sibling_re = _re.compile(r"^  \S")

    header_idx = next((i for i, ln in enumerate(lines) if header_re.match(ln.rstrip("\n"))), None)

    if header_idx is None and any(exotic_header_re.match(ln.rstrip("\n")) for ln in lines):
        return _rewrite_via_yaml(text, provider_id, block)

    block_lines = [ln + "\n" for ln in block.splitlines()]

    if header_idx is None:
        sep = "" if not lines or lines[-1].endswith("\n") else "\n"
        return text + sep + "providers:\n" + "".join(block_lines)

    # End of the top-level `providers:` section = next non-empty column-0 line.
    end = len(lines)
    for i in range(header_idx + 1, len(lines)):
        stripped = lines[i].rstrip("\n")
        if stripped and not stripped[0].isspace():
            end = i
            break

    # Existing provider block within the section?
    start = next((i for i in range(header_idx + 1, end) if key_re.match(lines[i].rstrip("\n"))), None)
    if start is not None:
        block_end = end
        for i in range(start + 1, end):
            if sibling_re.match(lines[i].rstrip("\n")):
                block_end = i
                break
        return "".join(lines[:start] + block_lines + lines[block_end:])

    # Insert as first child right after the header.
    return "".join(lines[: header_idx + 1] + block_lines + lines[header_idx + 1 :])


def _atomic_write(path: Path, content: str) -> None:
    """os.replace-based atomic write in the destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".arnold-tmp-", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            mode = 0o600
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise

@contextmanager
def _models_yml_lock(agent_dir: Path):
    """Cross-process lock around the models.yml read-modify-write section.

    Concurrent first-run launches (two terminals, watchdog + interactive)
    would otherwise race the splice and drop each other's provider block.
    The lockfile lives in the agent dir next to models.yml; fcntl.flock is
    advisory but every writer in this module honors it.
    """
    agent_dir.mkdir(parents=True, exist_ok=True)
    lock_path = agent_dir / ".models.yml.lock"
    with open(lock_path, "a", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def wire_cli_proxy(provider_id: str, source: str, *, agent_dir: Path) -> WireResult:
    """Merge a command-backed ``apiKey`` entry into ``<agent-dir>/models.yml``.

    Grok-style: installs the token-refresh helper script into the agent dir
    and references it via ``apiKey: "!python3 <expanded-abs-path>"``. Existing
    user content (comments included) is preserved byte-wise except for the
    targeted provider block; the write is atomic via ``os.replace``.
    ``source`` is recorded in provenance only (e.g. the foreign store path).
    """
    agent_dir = Path(agent_dir)
    if provider_id != "grok":
        raise ValueError(
            f"no cli_proxy wiring template for {provider_id!r}; only 'grok' is supported"
        )

    script_path = _install_grok_token_script(agent_dir)
    entry = dict(_GROK_ENTRY_TEMPLATE)
    # apiKey ordering first, mirroring the fork docs layout.
    ordered = {"baseUrl": entry.pop("baseUrl"), "api": entry.pop("api")}
    ordered["apiKey"] = f"!python3 {script_path.resolve()}"
    ordered.update(entry)

    models_yml = agent_dir / "models.yml"
    with _models_yml_lock(agent_dir):
        existing = ""
        try:
            existing = models_yml.read_text(encoding="utf-8")
        except FileNotFoundError:
            pass
        updated = _splice_provider(existing, provider_id, _render_provider_block(provider_id, ordered))
        _atomic_write(models_yml, updated)

        # Round-trip sanity: the merged file must still parse and keep the cmd key.
        merged = yaml.safe_load(models_yml.read_text(encoding="utf-8"))
        ok = isinstance(merged, dict) and str(
            (merged.get("providers") or {}).get(provider_id, {}).get("apiKey", "")
        ).startswith("!python3 ")

    return WireResult(
        ok=ok,
        provider=provider_id,
        mechanism="cli-proxy-models-yml",
        detail="" if ok else "merged models.yml failed post-write validation",
        provenance={
            "provider": provider_id,
            "mechanism": "cli-proxy-models-yml",
            "origin_kind": "foreign-cli-store",
            "origin_detail": source,
        },
    )


def _wire_models_yml_static(provider_id: str, api_key: str, *, agent_dir: Path) -> WireResult:
    """Fallback route: static ``apiKey`` merged into models.yml for providers
    without a CLIProxyAPI type mapping."""
    models_yml = Path(agent_dir) / "models.yml"
    with _models_yml_lock(Path(agent_dir)):
        existing = ""
        try:
            existing = models_yml.read_text(encoding="utf-8")
        except FileNotFoundError:
            pass
        updated = _splice_provider(
            existing, provider_id, _render_provider_block(provider_id, {"apiKey": api_key})
        )
        _atomic_write(models_yml, updated)
        merged = yaml.safe_load(models_yml.read_text(encoding="utf-8"))
        ok = isinstance(merged, dict) and (
            (merged.get("providers") or {}).get(provider_id, {}).get("apiKey") == api_key
        )
    return WireResult(
        ok=ok,
        provider=provider_id,
        mechanism="models-yml",
        detail="" if ok else "merged models.yml failed post-write validation",
        provenance={
            "provider": provider_id,
            "mechanism": "models-yml",
            "origin_kind": "manual-entry",
            "origin_detail": "",
        },
    )


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def record_provenance(agent_dir: Path, entries: Iterable[Mapping]) -> list[dict]:
    """Append provenance rows to the agent-dir JSONL ledger (secret-free)."""
    agent_dir = Path(agent_dir)
    agent_dir.mkdir(parents=True, exist_ok=True)
    log_path = agent_dir / _PROVENANCE_FILE
    written: list[dict] = []
    with log_path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            row = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "provider": str(entry.get("provider", "")),
                "mechanism": str(entry.get("mechanism", "")),
                "origin_kind": str(entry.get("origin_kind", "")),
                "origin_detail": _redact(str(entry.get("origin_detail", ""))),
            }
            fh.write(json.dumps(row) + "\n")
            written.append(row)
    return written


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

_MAX_VERIFY_OUTPUT = 200


def verify_route(
    route: str,
    *,
    agent_dir: Path,
    timeout: int = 90,
    secrets: Iterable[str] = (),
) -> VerifyResult:
    """Smoke-ping ``omp -p --no-session --model <route> hi`` against agent_dir.

    Never raises on nonzero exit or timeout (ok=False instead); the captured
    output is redacted (sk-* patterns plus any explicitly passed secret
    values) and truncated to 200 characters before leaving this function.
    """
    started = time.monotonic()
    try:
        proc = _run(
            ["omp", "-p", "--no-session", "--model", route, "hi"],
            env=_sandbox_env(Path(agent_dir)),
            timeout=timeout,
        )
        raw = proc.stdout or ""
        if proc.returncode != 0:
            raw = f"{raw}\nexit={proc.returncode} {proc.stderr or ''}".strip()
        latency_ms = int((time.monotonic() - started) * 1000)
        redacted = _redact(raw, secrets)[:_MAX_VERIFY_OUTPUT]
        return VerifyResult(ok=proc.returncode == 0, latency_ms=latency_ms, output=redacted)
    except subprocess.TimeoutExpired:
        latency_ms = int((time.monotonic() - started) * 1000)
        return VerifyResult(ok=False, latency_ms=latency_ms, output=f"[TIMEOUT after {timeout}s]"[:_MAX_VERIFY_OUTPUT])
    except OSError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return VerifyResult(ok=False, latency_ms=latency_ms, output=str(exc)[:_MAX_VERIFY_OUTPUT])


__all__ = [
    "PROVIDER_TO_CLIPROXY_TYPE",
    "VerifyResult",
    "WireResult",
    "record_provenance",
    "verify_route",
    "wire_api_key",
    "wire_cli_proxy",
    "wire_oauth",
]
