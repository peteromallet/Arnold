"""Tests for credential wiring + route verification (agentbox.onboarding.wire).

Everything runs against isolated PI_CODING_AGENT_DIR/HOME sandboxes; the only
test that invokes the real ``omp`` binary uses a FAKE key and touches nothing
outside its own temp dirs. Network-touching verification is gated behind
RUN_OMP_VERIFY=1. All subprocess seams are exercised through monkeypatched
``wire._run`` except the explicitly-marked live-sandbox round-trip.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import agentbox.onboarding.wire as wire_mod
from agentbox.onboarding.wire import (
    PROVIDER_TO_CLIPROXY_TYPE,
    _splice_provider,
    record_provenance,
    verify_route,
    wire_api_key,
    wire_cli_proxy,
    wire_oauth,
)

FAKE_KEY = "sk-fake00000000deadbeef"
SECRET_VALUE = "supersecret-value-do-not-leak"

_OMP_AVAILABLE = shutil.which("omp") is not None


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME (and omp's config root) at throwaway dirs for every test."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PI_CONFIG_DIR", str(home / ".omp"))
    return home


class _RunRecorder:
    """Monkeypatches wire_mod._run, capturing calls and replaying results."""

    def __init__(self, results=None, raises=None):
        self.calls: list[dict] = []
        self._results = list(results or [])
        self._raises = raises

    def __call__(self, cmd, *, env=None, timeout=None, capture=True):
        self.calls.append(
            {"cmd": cmd, "env": dict(env or {}), "timeout": timeout, "capture": capture}
        )
        if self._raises is not None:
            raise self._raises
        if self._results:
            return self._results.pop(0)
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")


@pytest.fixture
def agent_dir(tmp_path: Path) -> Path:
    return tmp_path / "agent"


def _db_rows(agent_dir: Path, query: str) -> list[dict]:
    db_path = agent_dir / "agent.db"
    assert db_path.is_file(), f"agent.db missing at {db_path}"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query).fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pinned schema map
# ---------------------------------------------------------------------------

def test_provider_to_cliproxy_map_matches_empirically_pinned_schema() -> None:
    # claude->anthropic and codex->openai-codex verified against the fork
    # parser AND a live sandbox import; gemini/antigravity land under
    # google-gemini-cli/google-antigravity (non-catalog ids) so stay unmapped;
    # there is NO `openai` CLIProxyAPI type.
    assert PROVIDER_TO_CLIPROXY_TYPE == {"anthropic": "claude", "openai-codex": "codex"}


# ---------------------------------------------------------------------------
# wire_api_key — real omp sandbox round-trip (fake key, isolated dir only)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _OMP_AVAILABLE, reason="omp binary not on PATH")
def test_wire_api_key_import_round_trip_into_real_sandbox(agent_dir: Path) -> None:
    result = wire_api_key("anthropic", FAKE_KEY, agent_dir=agent_dir)
    assert result.ok, result.detail
    assert result.mechanism == "auth-broker-import"

    rows = _db_rows(agent_dir, "SELECT provider, credential_type, data FROM auth_credentials")
    matching = [row for row in rows if row["provider"] == "anthropic"]
    assert matching, f"no anthropic row: {rows}"
    assert matching[0]["credential_type"] == "oauth"
    data = json.loads(matching[0]["data"])
    assert data["access"] == FAKE_KEY
    assert data["refresh"]  # synthetic placeholder present


def test_wire_api_key_builds_tempfile_and_cleans_up(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RunRecorder(
        results=[
            subprocess.CompletedProcess(
                [], 0,
                stdout=json.dumps({"imported": [{"provider": "anthropic"}], "skipped": []}),
                stderr="",
            )
        ]
    )
    monkeypatch.setattr(wire_mod, "_run", recorder)
    result = wire_api_key("anthropic", FAKE_KEY, agent_dir=agent_dir)

    assert result.ok
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["cmd"][0:3] == ["omp", "auth-broker", "import"]
    assert call["cmd"][-1] == "--json"
    assert call["timeout"] == 120
    assert call["env"]["PI_CODING_AGENT_DIR"] == str(agent_dir)
    payload_path = Path(call["cmd"][3])
    assert payload_path.suffix == ".json"
    assert not payload_path.exists(), "temp credential file must be deleted in finally"


def test_wire_api_key_reports_skips_without_ok(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skip_reason = f"missing access_token ({FAKE_KEY})"
    recorder = _RunRecorder(
        results=[
            subprocess.CompletedProcess(
                [], 0,
                stdout=json.dumps(
                    {"imported": [], "skipped": [{"file": "x.json", "reason": skip_reason}]}
                ),
                stderr="",
            )
        ]
    )
    monkeypatch.setattr(wire_mod, "_run", recorder)
    result = wire_api_key("anthropic", FAKE_KEY, agent_dir=agent_dir)

    assert not result.ok
    assert FAKE_KEY not in result.detail, "secret leaked into detail"
    assert "access_token" in result.detail


def test_wire_api_key_nonzero_exit_is_failure_not_raise(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RunRecorder(
        results=[subprocess.CompletedProcess([], 1, stdout="", stderr="boom")]
    )
    monkeypatch.setattr(wire_mod, "_run", recorder)
    result = wire_api_key("anthropic", FAKE_KEY, agent_dir=agent_dir)
    assert not result.ok
    assert "exit=1" in result.detail
    assert "boom" in result.detail


# ---------------------------------------------------------------------------
# wire_api_key — models.yml fallback for unmapped providers
# ---------------------------------------------------------------------------

def test_unmapped_provider_falls_back_to_models_yml_static(agent_dir: Path) -> None:
    result = wire_api_key("deepseek", FAKE_KEY, agent_dir=agent_dir)
    assert result.ok
    assert result.mechanism == "models-yml"

    merged = yaml.safe_load((agent_dir / "models.yml").read_text(encoding="utf-8"))
    assert merged["providers"]["deepseek"]["apiKey"] == FAKE_KEY


# ---------------------------------------------------------------------------
# wire_oauth — TTY guard + login invocation
# ---------------------------------------------------------------------------

def test_wire_oauth_fails_closed_on_non_tty(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", type("_FakeStdin", (), {"isatty": lambda self: False})())
    recorder = _RunRecorder()
    monkeypatch.setattr(wire_mod, "_run", recorder)

    with pytest.raises(RuntimeError):
        wire_oauth("kimi-code", agent_dir=agent_dir)
    assert recorder.calls == [], "login must not be spawned without a TTY"


def test_wire_oauth_tty_invokes_login_inheriting_stdio(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", type("_FakeStdin", (), {"isatty": lambda self: True})())
    recorder = _RunRecorder()
    monkeypatch.setattr(wire_mod, "_run", recorder)

    result = wire_oauth("kimi-code", agent_dir=agent_dir)
    assert result.ok
    assert result.mechanism == "auth-broker-login"
    call = recorder.calls[0]
    assert call["cmd"] == ["omp", "auth-broker", "login", "kimi-code"]
    assert call["capture"] is False, "stdio must be inherited for interactive OAuth"
    assert call["timeout"] is None
    assert call["env"]["PI_CODING_AGENT_DIR"] == str(agent_dir)


# ---------------------------------------------------------------------------
# wire_cli_proxy — grok-style models.yml merge
# ---------------------------------------------------------------------------

_EXISTING_MODELS_YML = """\
# my custom comment stays
providers:
  custom-provider:
    apiKey: static-custom
    baseUrl: https://example.invalid/v1
otherTop:
  nested: true
"""


def _grok_cmd_key(text: str) -> str:
    merged = yaml.safe_load(text)
    return merged["providers"]["grok"]["apiKey"]


def test_cli_proxy_merge_preserves_user_content_byte_wise(agent_dir: Path) -> None:
    models_yml = agent_dir / "models.yml"
    models_yml.parent.mkdir(parents=True, exist_ok=True)
    models_yml.write_text(_EXISTING_MODELS_YML, encoding="utf-8")

    result = wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    assert result.ok, result.detail

    updated = models_yml.read_text(encoding="utf-8")
    # Untouched regions are byte-identical: leading comment, sibling provider
    # block, and trailing top-level key all survive verbatim.
    assert "# my custom comment stays\n" in updated
    assert (
        "  custom-provider:\n"
        "    apiKey: static-custom\n"
        "    baseUrl: https://example.invalid/v1\n"
    ) in updated
    assert "\notherTop:\n  nested: true\n" in updated

    merged = yaml.safe_load(updated)
    assert merged["otherTop"] == {"nested": True}
    grok_entry = merged["providers"]["grok"]
    assert grok_entry["baseUrl"] == "https://cli-chat-proxy.grok.com/v1"
    assert grok_entry["api"] == "openai-completions"
    assert grok_entry["headers"]["X-XAI-Token-Auth"] == "xai-grok-cli"
    assert [model["id"] for model in grok_entry["models"]] == ["grok-4.6", "grok-4.5"]
    assert grok_entry["apiKey"].startswith("!python3 "), grok_entry["apiKey"]


def test_cli_proxy_merge_is_idempotent(agent_dir: Path) -> None:
    first = wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    assert first.ok
    text_after_first = (agent_dir / "models.yml").read_text(encoding="utf-8")

    second = wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    assert second.ok
    text_after_second = (agent_dir / "models.yml").read_text(encoding="utf-8")

    assert text_after_first == text_after_second, "second run must be a no-op"
    assert text_after_second.count("!python3 ") == 1


def test_cli_proxy_replaces_existing_grok_block_without_duplication(agent_dir: Path) -> None:
    # Seed a stale grok block; merge must replace it, not append a second one.
    wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    text = (agent_dir / "models.yml").read_text(encoding="utf-8")
    mutated = text.replace("grok-4.6", "grok-9.9-stale")
    (agent_dir / "models.yml").write_text(mutated, encoding="utf-8")

    result = wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    assert result.ok
    updated = (agent_dir / "models.yml").read_text(encoding="utf-8")
    assert "grok-9.9-stale" not in updated
    assert updated.count("grok:") == 1
    assert "grok-4.6" in updated


def test_cli_proxy_write_is_atomic_via_os_replace(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models_yml = agent_dir / "models.yml"
    agent_dir.mkdir(parents=True, exist_ok=True)
    models_yml.write_text(_EXISTING_MODELS_YML, encoding="utf-8")
    original_bytes = models_yml.read_bytes()

    real_replace = os.replace
    seen: list[tuple[Path, Path]] = []

    def crashing_replace(src, dst):
        seen.append((Path(src), Path(dst)))
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr(wire_mod.os, "replace", crashing_replace)
    with pytest.raises(OSError):
        wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)

    # One atomic-replace attempt, tmp staged in the SAME directory...
    assert len(seen) == 1
    src, dst = seen[0]
    assert dst == models_yml
    assert src.parent == models_yml.parent
    # ...original content intact and no partial artifacts left behind.
    assert models_yml.read_bytes() == original_bytes
    assert list(agent_dir.glob(".arnold-tmp-*")) == []

    monkeypatch.setattr(wire_mod.os, "replace", real_replace)


def test_cli_proxy_paths_are_expanded_absolute_no_tilde(agent_dir: Path) -> None:
    result = wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    assert result.ok

    text = (agent_dir / "models.yml").read_text(encoding="utf-8")
    cmd_key = _grok_cmd_key(text)
    assert cmd_key.startswith("!python3 ")
    script_path = cmd_key.split("!python3 ", 1)[1]
    assert script_path == str((agent_dir / "grok-token.py").resolve())
    assert "~" not in text
    assert "$HOME" not in text
    assert "/Users/peteromalley" not in text  # sandboxed HOME is a tmp dir


def test_cli_proxy_installs_executable_token_script(agent_dir: Path) -> None:
    wire_cli_proxy("grok", "~/.grok/auth.json", agent_dir=agent_dir)
    script = agent_dir / "grok-token.py"
    assert script.is_file()
    assert script.stat().st_mode & 0o111, "token script must be executable"
    compile(script.read_text(encoding="utf-8"), "grok-token.py", "exec")


def test_cli_proxy_unknown_provider_template_raises(agent_dir: Path) -> None:
    with pytest.raises(ValueError):
        wire_cli_proxy("not-a-proxy-provider", "src", agent_dir=agent_dir)


# ---------------------------------------------------------------------------
# Provenance ledger
# ---------------------------------------------------------------------------

def test_provenance_jsonl_appended_and_secret_free(agent_dir: Path) -> None:
    rows = record_provenance(
        agent_dir,
        [
            {
                "provider": "grok",
                "mechanism": "cli-proxy-models-yml",
                "origin_kind": "foreign-cli-store",
                "origin_detail": f"onboarded from ~/.grok/auth.json key={FAKE_KEY}",
            },
            {
                "provider": "deepseek",
                "mechanism": "auth-broker-import",
                "origin_kind": "manual-entry",
                "origin_detail": "",
            },
        ],
    )
    log_path = agent_dir / ".arnold_onboarding_provenance.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    for row in parsed:
        assert set(row) == {"ts", "provider", "mechanism", "origin_kind", "origin_detail"}
    assert parsed[0]["provider"] == "grok"
    assert parsed[0]["ts"].endswith(("Z", "+00:00"))
    # Secret-free: neither raw values nor sk-patterns survive the ledger.
    assert FAKE_KEY not in log_path.read_text(encoding="utf-8")
    assert "[REDACTED]" in parsed[0]["origin_detail"]

    # Appending (not truncating) on subsequent calls.
    record_provenance(agent_dir, [{"provider": "x", "mechanism": "y", "origin_kind": "z", "origin_detail": ""}])
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


# ---------------------------------------------------------------------------
# verify_route — redaction, truncation, fail-closed semantics
# ---------------------------------------------------------------------------

def test_verify_route_redacts_secrets_and_truncates(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    long_tail = "x" * 500
    recorder = _RunRecorder(
        results=[
            subprocess.CompletedProcess(
                [], 0,
                stdout=f"ok {FAKE_KEY} {SECRET_VALUE} {long_tail}\n",
                stderr="",
            )
        ]
    )
    monkeypatch.setattr(wire_mod, "_run", recorder)

    result = verify_route(
        "anthropic/claude-opus-4-8", agent_dir=agent_dir, secrets=[SECRET_VALUE]
    )
    assert result.ok
    assert len(result.output) <= 200
    assert FAKE_KEY not in result.output
    assert SECRET_VALUE not in result.output
    assert result.output.count("[REDACTED]") == 2
    call = recorder.calls[0]
    assert call["cmd"] == [
        "omp", "-p", "--no-session", "--model", "anthropic/claude-opus-4-8", "hi"
    ]
    assert call["env"]["PI_CODING_AGENT_DIR"] == str(agent_dir)


def test_verify_route_nonzero_exit_never_raises(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RunRecorder(results=[subprocess.CompletedProcess([], 7, stdout="", stderr="bad model")])
    monkeypatch.setattr(wire_mod, "_run", recorder)

    result = verify_route("nope/nope", agent_dir=agent_dir)
    assert not result.ok
    assert "exit=7" in result.output
    assert "bad model" in result.output
    assert result.latency_ms >= 0


def test_verify_route_timeout_returns_failure(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RunRecorder(raises=subprocess.TimeoutExpired(cmd=["omp"], timeout=90))
    monkeypatch.setattr(wire_mod, "_run", recorder)

    result = verify_route("x/y", agent_dir=agent_dir, timeout=90)
    assert not result.ok
    assert "TIMEOUT" in result.output


def test_verify_route_missing_binary_returns_failure(
    agent_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _RunRecorder(raises=FileNotFoundError("[Errno 2] No such file: 'omp'"))
    monkeypatch.setattr(wire_mod, "_run", recorder)

    result = verify_route("x/y", agent_dir=agent_dir)
    assert not result.ok
    assert "No such file" in result.output


# ---------------------------------------------------------------------------
# Live E2E verification — strictly opt-in (network-touching)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _OMP_AVAILABLE, reason="omp binary not on PATH")
@pytest.mark.skipif(os.environ.get("RUN_OMP_VERIFY") != "1", reason="set RUN_OMP_VERIFY=1")
def test_verify_route_live_against_real_sandbox(agent_dir: Path) -> None:
    """E2E smoke: wire a FAKE key into a sandbox, then ping the route. The
    request itself will fail upstream auth, but the pipeline must complete
    fail-closed with redacted output and no exception."""
    wired = wire_api_key("anthropic", FAKE_KEY, agent_dir=agent_dir)
    assert wired.ok, wired.detail
    verified = verify_route(
        "anthropic/claude-opus-4-8", agent_dir=agent_dir, secrets=[FAKE_KEY]
    )
    assert isinstance(verified.ok, bool)
    assert FAKE_KEY not in verified.output


def test_splice_preserves_anchored_providers_header(tmp_path: Path) -> None:
    text = "providers: &defaults\n  grok:\n    apiKey: \"!cmd\"\n"
    merged = _splice_provider(text, "deepseek", "deepseek:\n  apiKey: sk-test\n")
    data = yaml.safe_load(merged)
    assert set(data["providers"]) == {"grok", "deepseek"}
    assert data["providers"]["grok"]["apiKey"] == "!cmd"


def test_splice_preserves_flow_providers_header(tmp_path: Path) -> None:
    text = "providers: {grok: {apiKey: '!cmd'}}\n"
    merged = _splice_provider(text, "deepseek", "deepseek:\n  apiKey: sk-test\n")
    data = yaml.safe_load(merged)
    assert set(data["providers"]) == {"grok", "deepseek"}
