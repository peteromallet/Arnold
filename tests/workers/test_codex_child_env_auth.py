"""Regression tests for the Codex child-env auth self-heal (occurrence fc98376b2f10).

The normal dispatch path inherits ``CODEX_HOME`` unchanged; a stale ``auth.json``
there makes every Codex child fail with 401 on the realtime backend. These tests
cover the best-effort repair in ``_seed_codex_auth_into_env``.
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.workers._impl import (
    _CODEX_AUTH_SEED_PATHS,
    _codex_child_env,
)


def jwt_token(exp: int | None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    claims = {} if exp is None else {"exp": exp}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


def chatgpt_auth(*, exp: int | None = None, last_refresh: str | None = None) -> dict:
    data: dict = {
        "auth_mode": "chatgpt",
        "last_refresh": last_refresh or "2026-08-09T10:50:27.121757Z",
        "tokens": {
            "access_token": jwt_token(exp),
            "id_token": jwt_token(exp),
            "refresh_token": "rt.1.test",
            "account_id": "test-account",
        },
    }
    return data


def apikey_auth(*, key: str | None = "sk-test") -> dict:
    return {"auth_mode": "apikey", "OPENAI_API_KEY": key, "tokens": {}}


def write_auth(path: Path, data: dict, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(json.dumps(data).encode())
    path.chmod(mode)


@pytest.fixture
def auth_seed_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point the canonical seed list at two tmp files (persistent first, then root)."""
    persistent = tmp_path / "persistent" / "codex-auth.json"
    root = tmp_path / "root" / "codex-auth.json"
    write_auth(persistent, chatgpt_auth(exp=int(time.time()) + 3600))
    write_auth(root, chatgpt_auth(exp=int(time.time()) + 3600))
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl._CODEX_AUTH_SEED_PATHS",
        (persistent, root),
    )
    return persistent, root


def _codex_home_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point CODEX_HOME (and HOME) at a fresh tmp dir; returns the codex home."""
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(mode=0o700)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("HOME", str(tmp_path))
    return codex_home


def test_codex_child_env_replaces_expired_auth_atomically_and_private(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    persistent, _ = auth_seed_paths
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    write_auth(target, chatgpt_auth(exp=int(time.time()) - 3600))

    replaced: list[tuple] = []
    real_replace = os.replace
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl.os.replace",
        lambda src, dst: (replaced.append((src, dst)), real_replace(src, dst))[1],
    )

    result = _codex_child_env(turn_id="plan_worker_x")

    assert result["CODEX_HOME"] == str(codex_home)
    assert result["MEGAPLAN_TURN_ID"] == "plan_worker_x"
    assert "CODEX_THREAD_ID" not in result
    assert target.read_bytes() == persistent.read_bytes()
    assert (target.stat().st_mode & 0o777) == 0o600
    assert len(replaced) == 1
    assert not list(codex_home.glob(".auth.json.tmp.*"))


def test_codex_child_env_leaves_valid_auth_content_and_mtime_untouched(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    data = chatgpt_auth(exp=int(time.time()) + 3600)
    write_auth(target, data)
    before = (target.read_bytes(), target.stat().st_mtime_ns)

    _codex_child_env()

    after = (target.read_bytes(), target.stat().st_mtime_ns)
    assert after == before


def test_codex_child_env_seeds_missing_auth(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    persistent, _ = auth_seed_paths
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    assert not target.exists()

    _codex_child_env()

    assert target.exists()
    assert target.read_bytes() == persistent.read_bytes()
    assert (target.stat().st_mode & 0o777) == 0o600


def test_codex_child_env_leaves_nonempty_apikey_auth_untouched(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    write_auth(target, apikey_auth(key="sk-keep"))
    before = (target.read_bytes(), target.stat().st_mtime_ns)

    _codex_child_env()

    assert (target.read_bytes(), target.stat().st_mtime_ns) == before


def test_codex_child_env_without_valid_seed_does_not_raise_or_change_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    write_auth(target, chatgpt_auth(exp=int(time.time()) - 3600))
    before = target.read_bytes()
    stale = tmp_path / "stale" / "codex-auth.json"
    write_auth(stale, chatgpt_auth(exp=int(time.time()) - 7200))
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl._CODEX_AUTH_SEED_PATHS",
        (stale,),
    )

    result = _codex_child_env()

    assert result["CODEX_HOME"] == str(codex_home)
    assert target.read_bytes() == before


def test_codex_child_env_uses_recent_last_refresh_only_without_jwt_exp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    # Opaque access token (no decodable exp) with a RECENT last_refresh -> valid.
    data = chatgpt_auth()
    data["tokens"]["access_token"] = "opaque-token-no-dots"
    write_auth(target, data)
    before = target.read_bytes()

    _codex_child_env()

    assert target.read_bytes() == before

    # Same shape but last_refresh OLDER than the fallback bound -> stale -> seeded.
    seed = tmp_path / "seed" / "codex-auth.json"
    write_auth(seed, chatgpt_auth(exp=int(time.time()) + 3600))
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl._CODEX_AUTH_SEED_PATHS",
        (seed,),
    )
    old = chatgpt_auth()
    old["tokens"]["access_token"] = "opaque-token-no-dots"
    old["last_refresh"] = "2026-01-01T00:00:00Z"
    write_auth(target, old)

    _codex_child_env()

    assert target.read_bytes() == seed.read_bytes()


def test_codex_child_env_prefers_persistent_seed_then_root_fallback(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    persistent, root = auth_seed_paths
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    target = codex_home / "auth.json"
    write_auth(target, chatgpt_auth(exp=int(time.time()) - 3600))

    _codex_child_env()
    assert target.read_bytes() == persistent.read_bytes()

    # Invalidate the persistent seed; the root fallback must be used.
    write_auth(persistent, chatgpt_auth(exp=int(time.time()) - 7200))
    write_auth(target, chatgpt_auth(exp=int(time.time()) - 3600))
    _codex_child_env()
    assert target.read_bytes() == root.read_bytes()


def test_codex_child_env_refuses_symlink_target(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = _codex_home_env(monkeypatch, tmp_path)
    referent = tmp_path / "outside" / "auth.json"
    write_auth(referent, chatgpt_auth(exp=int(time.time()) - 3600))
    target = codex_home / "auth.json"
    target.symlink_to(referent)
    before = referent.read_bytes()

    _codex_child_env()

    assert target.is_symlink()
    assert referent.read_bytes() == before


def test_codex_child_env_seeds_isolated_final_codex_home(
    tmp_path: Path, auth_seed_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    persistent, _ = auth_seed_paths
    isolated = tmp_path / "isolated-codex"
    isolated.mkdir(mode=0o700)

    def fake_isolation(env: dict) -> dict:
        env["CODEX_HOME"] = str(isolated)
        return env

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl._apply_worker_state_isolation",
        fake_isolation,
    )
    # The pre-isolation CODEX_HOME is a bogus path that must never be touched.
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "bogus"))
    monkeypatch.setenv("HOME", str(tmp_path))

    _codex_child_env()

    assert (isolated / "auth.json").read_bytes() == persistent.read_bytes()
    assert not (tmp_path / "bogus").exists()
