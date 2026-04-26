from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.commands.session as session_cmd
import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import SessionConfig, find_active_session


class FakePopen:
    started: list[list[str]] = []

    def __init__(self, cmd, *, stdout, stderr, start_new_session: bool) -> None:
        self.cmd = list(cmd)
        self.returncode = None
        FakePopen.started.append(self.cmd)
        assert start_new_session is True
        id_ = self.cmd[self.cmd.index("--id") + 1]
        config = json.loads(self.cmd[self.cmd.index("--config") + 1])
        session_dir = Path("out/sessions") / id_
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "pid").write_text("4242", encoding="utf-8")
        (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
        (session_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def poll(self):
        return self.returncode


def test_session_cli_start_list_flush_stop_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    FakePopen.started = []
    alive = {4242}
    free_calls: list[tuple[str, bool, bool]] = []

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0:
            if pid not in alive:
                raise ProcessLookupError(pid)
            return
        if sig == signal.SIGTERM and pid in alive:
            alive.remove(pid)
            session_module._cleanup_session_files(Path("out/sessions/default"))
            return
        raise ProcessLookupError(pid)

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def free(self, *, unload_models: bool, free_memory: bool) -> dict[str, Any]:
            free_calls.append((self.url, unload_models, free_memory))
            return {}

    monkeypatch.setattr(session_cmd.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_cmd, "ComfyClient", FakeClient)

    start_args = argparse.Namespace(
        id="default",
        port=8200,
        vram_policy="high",
        reserve_vram_gb=2.0,
        cache_policy="lru:3",
        warm_policy="always",
        disable_smart_memory=True,
    )
    assert session_cmd._cmd_session_start(start_args) == 0
    assert (tmp_path / "out/sessions/default/pid").exists()
    assert (tmp_path / "out/sessions/default/url").read_text(encoding="utf-8") == "http://127.0.0.1:8200"
    config = json.loads((tmp_path / "out/sessions/default/config.json").read_text(encoding="utf-8"))
    assert config == {
        "port": 8200,
        "vram_policy": "high",
        "reserve_vram_gb": 2.0,
        "cache_policy": "lru:3",
        "warm_policy": "always",
        "disable_smart_memory": True,
    }

    assert session_cmd._cmd_session_list(argparse.Namespace()) == 0
    assert "default\thttp://127.0.0.1:8200" in capsys.readouterr().out

    assert session_cmd._cmd_session_flush(
        argparse.Namespace(id="default", unload_models=True, free_memory=True)
    ) == 0
    assert free_calls == [("http://127.0.0.1:8200", True, True)]

    assert session_cmd._cmd_session_stop(argparse.Namespace(id="default")) == 0
    assert not (tmp_path / "out/sessions/default/pid").exists()
    assert not (tmp_path / "out/sessions/default/url").exists()
    assert not (tmp_path / "out/sessions/default/config.json").exists()


def test_find_active_session_returns_url_or_cleans_stale_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text("{}", encoding="utf-8")
    alive = True

    def fake_kill(pid: int, sig: int) -> None:
        assert pid == 4242
        assert sig == 0
        if not alive:
            raise ProcessLookupError(pid)

    monkeypatch.setattr(session_module.os, "kill", fake_kill)

    assert find_active_session("default") == "http://127.0.0.1:8200"
    alive = False
    assert find_active_session("default") is None
    assert not (session_dir / "pid").exists()
    assert not (session_dir / "url").exists()
    assert not (session_dir / "config.json").exists()


def test_daemon_config_carry_through_typed_and_raw_hiddenswitch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: list[SessionConfig] = []

    class FakeEvent:
        def set(self) -> None:
            pass

        async def wait(self) -> None:
            return None

    class FakeServerSession:
        def __init__(self, config: SessionConfig) -> None:
            self.config = config
            self.url = "http://127.0.0.1:8200"
            captured.append(config)

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(session_cmd.asyncio, "Event", FakeEvent)
    monkeypatch.setattr(session_cmd, "ServerSession", FakeServerSession)

    typed = {
        "port": 8200,
        "vram_policy": "high",
        "reserve_vram_gb": 2.0,
        "cache_policy": "lru:3",
        "warm_policy": "always",
    }
    raw = {
        "reserve_vram": 12,
        "cache_none": True,
        "fp8_e4m3fn_text_enc": True,
        "port": 8200,
    }

    assert asyncio.run(session_cmd._daemon_main(argparse.Namespace(id="typed", config=json.dumps(typed)))) == 0
    assert asyncio.run(session_cmd._daemon_main(argparse.Namespace(id="raw", config=json.dumps(raw)))) == 0

    assert captured[0] == SessionConfig(
        port=8200,
        vram_policy="high",
        reserve_vram_gb=2.0,
        cache_policy="lru:3",
        warm_policy="always",
        extra={},
    )
    assert captured[1] == SessionConfig(
        port=8200,
        reserve_vram_gb=12,
        cache_policy="none",
        extra={"fp8_e4m3fn_text_enc": True},
    )
