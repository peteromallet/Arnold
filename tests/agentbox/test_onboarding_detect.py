"""Tests for first-run provider detection (agentbox.onboarding).

Isolation: every scan test passes explicit ``home``/``cwd``/``environ`` rooted
at ``tmp_path`` so neither ``HOME`` nor ``os.environ`` is touched; one test
additionally monkeypatches ``HOME`` to prove default resolution follows it.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

from agentbox.onboarding.catalog import AUTH_KINDS, PROVIDERS, RANK_ORDER
from agentbox.onboarding.detect import (
    CANDIDATE,
    MISSING,
    READY,
    ScanReport,
    parse_env_file,
    scan_providers,
)

# ---------------------------------------------------------------------------
# Catalog invariants + worker-table parity
# ---------------------------------------------------------------------------

def test_rank_order_matches_found_first_spec() -> None:
    assert RANK_ORDER == (
        "deepseek",
        "openrouter",
        "xai",
        "anthropic",
        "kimi-code",
        "zai",
        "moonshot",
        "fireworks",
        "openai-codex",
        "grok",
        "google",
        "openai",
        "minimax",
        "perplexity",
    )
    # Every ranked provider is catalogued, and nothing else is.
    assert set(RANK_ORDER) == set(PROVIDERS)


def test_catalog_parity_with_worker_credential_env() -> None:
    """env_keys cannot drift from workers.omp / cloud.preflight tables."""
    from arnold_pipelines.megaplan.cloud import preflight
    from arnold_pipelines.megaplan.workers import omp

    worker_env = omp._OMP_CREDENTIAL_ENV
    for provider_id, env_keys in worker_env.items():
        assert provider_id in PROVIDERS, f"worker provider {provider_id} missing from catalog"
        assert PROVIDERS[provider_id].env_keys == env_keys

    # Reverse direction: catalog env-key providers outside the worker table
    # must be exactly the documented long tail.
    tail = {"google", "openai", "minimax", "perplexity"}
    catalog_env_providers = {pid for pid, spec in PROVIDERS.items() if spec.env_keys}
    assert catalog_env_providers - set(worker_env) == tail

    # Cloud preflight hints stay in lock-step with the worker table.
    assert preflight._ENV_HINTS_BY_OMP_PROVIDER == {
        **worker_env,
        "openai-codex": (),
        "grok": (),
    }


def test_native_routes_use_expected_auth_kinds() -> None:
    assert PROVIDERS["grok"].auth_kinds == frozenset({"cli_proxy"})
    assert PROVIDERS["openai-codex"].auth_kinds == frozenset({"oauth"})
    assert "oauth" in PROVIDERS["kimi-code"].auth_kinds
    assert "api_key" in PROVIDERS["kimi-code"].auth_kinds
    for spec in PROVIDERS.values():
        assert spec.auth_kinds <= AUTH_KINDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _isolated(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    cwd = tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    return home, cwd


def _status(report: ScanReport, provider_id: str) -> object:
    return next(scan for scan in report.providers if scan.id == provider_id)


# ---------------------------------------------------------------------------
# Environment sweep
# ---------------------------------------------------------------------------

def test_process_env_key_marks_provider_ready(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    report = scan_providers(
        home=home,
        cwd=cwd,
        environ={"DEEPSEEK_API_KEY": "sk-test-deepseek-value"},
    )

    scan = _status(report, "deepseek")
    assert scan.status == READY
    assert scan.origin is not None
    assert scan.origin.kind == "env"
    # Presence descriptor only — never the value itself.
    assert "sk-test-deepseek-value" not in json.dumps(report.to_json())


def test_env_file_precedence_mirrors_omp_load_order(tmp_path: Path) -> None:
    """omp apply order: process env > cwd/.env > <agent>/.env > <config>/.env."""
    home, cwd = _isolated(tmp_path)
    agent_dir = home / ".omp" / "agent"
    agent_dir.mkdir(parents=True)

    (home / ".omp" / ".env").write_text(
        'FIREWORKS_API_KEY="from-config-root"\n', encoding="utf-8"
    )
    (agent_dir / ".env").write_text(
        "export FIREWORKS_API_KEY=from-agent\n", encoding="utf-8"
    )
    (cwd / ".env").write_text(
        "# comment line\nFIREWORKS_API_KEY = from-cwd  # trailing comment\n",
        encoding="utf-8",
    )

    report = scan_providers(home=home, cwd=cwd, environ={})
    scan = _status(report, "fireworks")
    assert scan.status == READY
    assert scan.origin is not None
    assert scan.origin.kind == "env_file"
    assert str(cwd / ".env") in scan.origin.detail

    # Agent-dir file wins over config-root when cwd does not define the key.
    report = scan_providers(home=home, cwd=tmp_path / "no-such-cwd", environ={})
    scan = _status(report, "fireworks")
    assert scan.status == READY
    assert scan.origin is not None
    assert str(agent_dir / ".env") in (scan.origin.detail or "")


def test_default_resolution_follows_home_monkeypatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, cwd = _isolated(tmp_path)
    monkeypatch.setattr(os, "environ", {"HOME": str(home), "ZAI_API_KEY": "sk-zai"})
    report = scan_providers(cwd=cwd)
    scan = _status(report, "zai")
    assert scan.status == READY
    assert scan.origin is not None
    assert scan.origin.kind == "env"


# ---------------------------------------------------------------------------
# Foreign CLI stores
# ---------------------------------------------------------------------------

def test_codex_and_grok_stores_are_ready_origins(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    codex = home / ".codex"
    codex.mkdir()
    (codex / "auth.json").write_text(json.dumps({"tokens": "REDACTED"}), encoding="utf-8")
    grok = home / ".grok"
    grok.mkdir()
    (grok / "auth.json").write_text("{}", encoding="utf-8")

    report = scan_providers(home=home, cwd=cwd, environ={})

    codex_scan = _status(report, "openai-codex")
    assert codex_scan.status == READY
    assert codex_scan.origin is not None
    assert codex_scan.origin.kind == "cli_store"

    grok_scan = _status(report, "grok")
    assert grok_scan.status == READY
    assert grok_scan.origin is not None
    assert grok_scan.origin.kind == "cli_proxy"


def test_kimi_dir_is_candidate_not_ready(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    (home / ".kimi").mkdir()

    report = scan_providers(home=home, cwd=cwd, environ={})
    scan = _status(report, "kimi-code")
    assert scan.status == CANDIDATE
    assert scan.origin is not None
    assert scan.origin.kind == "cli_store"


def test_claude_credentials_are_candidate_even_when_unreadable(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    claude = home / ".claude"
    claude.mkdir()
    creds = claude / ".credentials.json"
    creds.write_text('{"anthropic": "REDACTED"}', encoding="utf-8")
    if os.geteuid() != 0:
        creds.chmod(0o000)

    report = scan_providers(home=home, cwd=cwd, environ={})
    scan = _status(report, "anthropic")
    assert scan.status == CANDIDATE
    assert scan.origin is not None
    assert scan.origin.kind == "cli_store"


def test_unreadable_codex_auth_is_skipped_silently(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    codex = home / ".codex"
    codex.mkdir()
    auth = codex / "auth.json"
    auth.write_text("{}", encoding="utf-8")
    if os.geteuid() != 0:
        auth.chmod(0o000)

    report = scan_providers(home=home, cwd=cwd, environ={})  # must not raise
    scan = _status(report, "openai-codex")
    assert scan.status == MISSING
    assert scan.origin is None


# ---------------------------------------------------------------------------
# agent.db sweep
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE auth_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    data TEXT NOT NULL,
    disabled_cause TEXT DEFAULT NULL
);
"""


def _seed_db(agent_dir: Path, rows: list[tuple[str, str, str | None]]) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(agent_dir / "agent.db")
    try:
        connection.executescript(_SCHEMA)
        for provider, credential_type, disabled_cause in rows:
            connection.execute(
                "INSERT INTO auth_credentials (provider, credential_type, data,"
                " disabled_cause) VALUES (?, ?, ?, ?)",
                (provider, credential_type, "REDACTED", disabled_cause),
            )
        connection.commit()
    finally:
        connection.close()


def test_agent_db_rows_mark_ready_with_credential_type_origin(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    agent_dir = home / ".omp" / "agent"
    _seed_db(
        agent_dir,
        [
            ("deepseek", "api_key", None),
            ("openai-codex", "oauth", None),
            ("legacy-provider", "api_key", None),  # not in catalog -> skipped
            ("moonshot", "api_key", "revoked"),  # disabled -> skipped
        ],
    )

    report = scan_providers(home=home, cwd=cwd, environ={})

    deepseek = _status(report, "deepseek")
    assert deepseek.status == READY
    assert deepseek.origin is not None
    assert deepseek.origin.kind == "api_key"

    codex = _status(report, "openai-codex")
    assert codex.origin is not None
    assert codex.origin.kind == "oauth"

    assert _status(report, "moonshot").status == MISSING


def test_agent_db_kimi_alias_maps_to_kimi_code(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    _seed_db(home / ".omp" / "agent", [("kimi", "api_key", None)])

    report = scan_providers(home=home, cwd=cwd, environ={})
    scan = _status(report, "kimi-code")
    assert scan.status == READY
    assert scan.origin is not None
    assert scan.origin.kind == "api_key"


def test_pi_coding_agent_dir_overrides_db_location(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    custom = tmp_path / "custom-agent"
    _seed_db(custom, [("xai", "api_key", None)])

    report = scan_providers(
        home=home,
        cwd=cwd,
        environ={"PI_CODING_AGENT_DIR": str(custom)},
    )
    assert _status(report, "xai").status == READY


# ---------------------------------------------------------------------------
# models.yml sweep
# ---------------------------------------------------------------------------

def test_models_yml_command_backed_key_is_cli_proxy(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    agent_dir = home / ".omp" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "models.yml").write_text(
        "providers:\n"
        "  grok:\n"
        "    baseUrl: https://example.invalid/v1\n"
        '    apiKey: "!python3 /path/to/token.py"\n'
        "  some-custom:\n"
        "    apiKey: static-not-in-catalog\n",
        encoding="utf-8",
    )

    report = scan_providers(home=home, cwd=cwd, environ={})
    grok = _status(report, "grok")
    assert grok.status == READY
    assert grok.origin is not None
    assert grok.origin.kind == "cli_proxy"


def test_models_yml_static_key_is_config_origin(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    agent_dir = home / ".omp" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "models.yml").write_text(
        "providers:\n"
        "  deepseek:\n"
        "    apiKey: sk-static-in-yml-12345678\n",
        encoding="utf-8",
    )

    report = scan_providers(home=home, cwd=cwd, environ={})
    deepseek = _status(report, "deepseek")
    assert deepseek.status == READY
    assert deepseek.origin is not None
    assert deepseek.origin.kind == "config"
    # Secret value must not survive into the JSON dump even via details.
    assert "sk-static-in-yml-12345678" not in json.dumps(report.to_json())


def test_malformed_models_yml_is_skipped_silently(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    agent_dir = home / ".omp" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "models.yml").write_text("providers: [unclosed\n", encoding="utf-8")

    report = scan_providers(home=home, cwd=cwd, environ={})  # must not raise
    assert all(scan.status == MISSING for scan in report.providers)


# ---------------------------------------------------------------------------
# Report shape + secret-redaction audit
# ---------------------------------------------------------------------------

def test_to_json_shape(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    report = scan_providers(home=home, cwd=cwd, environ={})
    payload = report.to_json()

    assert set(payload) == {"providers", "rank_order"}
    assert payload["rank_order"] == list(RANK_ORDER)
    for entry in payload["providers"]:
        assert set(entry) == {"id", "status", "origin", "env_keys", "default_route"}
        assert entry["status"] in {READY, CANDIDATE, MISSING}
        assert entry["origin"] is None or set(entry["origin"]) == {"kind", "detail"}
        assert entry["env_keys"] == list(PROVIDERS[entry["id"]].env_keys)


def test_no_secret_values_anywhere_in_dump(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    agent_dir = home / ".omp" / "agent"
    _seed_db(agent_dir, [("deepseek", "api_key", None)])
    (cwd / ".env").write_text(
        "DEEPSEEK_API_KEY=sk-aabbccdd11223344\n"
        "OPENROUTER_API_KEY='sk-quote-escaped-99887766'\n",
        encoding="utf-8",
    )
    (home / ".codex").mkdir()
    (home / ".codex" / "auth.json").write_text(
        '{"ACCESS_TOKEN": "sk-codex-secret-55443322"}', encoding="utf-8"
    )

    report = scan_providers(home=home, cwd=cwd, environ={})
    dump = json.dumps(report.to_json())
    assert re.search(r"sk-[A-Za-z0-9]{8,}", dump) is None


def test_missing_everything_reports_missing(tmp_path: Path) -> None:
    home, cwd = _isolated(tmp_path)
    report = scan_providers(home=home, cwd=cwd, environ={})
    assert {scan.status for scan in report.providers} == {MISSING}


# ---------------------------------------------------------------------------
# .env parser semantics (Bun-compatible, mirrored from omp env.ts)
# ---------------------------------------------------------------------------

def parse_env_line(line: str) -> tuple[str, str] | None:
    from agentbox.onboarding.detect import _parse_env_line

    return _parse_env_line(line)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("KEY=value", ("KEY", "value")),
        ("export KEY=value", ("KEY", "value")),
        ("export\tKEY=value", ("KEY", "value")),
        ('KEY="quoted value"', ("KEY", "quoted value")),
        ("KEY='single'", ("KEY", "single")),
        ("KEY=`backtick`", ("KEY", "backtick")),
        ("KEY=va #ue # second hash", ("KEY", "va")),
        ("KEY=", ("KEY", "")),
        ("# full comment", None),
        ("   ", None),
        ("NO_EQUALS", None),
        ("1BAD=x", None),
        ("KEY WITH SPACE=x", None),
    ],
)
def test_parse_env_line_semantics(line: str, expected: tuple[str, str] | None) -> None:
    assert parse_env_line(line) == expected


def test_parse_env_file_unreadable_returns_empty(tmp_path: Path) -> None:
    assert parse_env_file(tmp_path / "does-not-exist.env") == {}


def test_parse_env_file_non_utf8_returns_empty(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_bytes(b"GOOD=1\n\xff\xfe\nBAD_KEY=\xff")
    assert parse_env_file(env_file) == {}


def test_scan_survives_non_utf8_env_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_bytes(b"\xff\xfe\x00")
    report = scan_providers(home=tmp_path, cwd=tmp_path, environ={})
    assert report is not None


def test_kimi_code_supports_env_auth_kind() -> None:
    assert "env" in PROVIDERS["kimi-code"].auth_kinds
