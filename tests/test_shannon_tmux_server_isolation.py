"""Every Shannon tmux operation must address a PRIVATE per-session server.

Root cause of the finalize "no server running" hang (2026-06-11): all Shannon
sessions + any operator/agent tmux landed on the single shared default server
(``$TMUX_TMPDIR/default``). tmux's default ``exit-empty on`` destroys the server
the instant its LAST session is killed, so when ANY concurrent chain tore down
what happened to be the last session — or anything ran ``tmux kill-server`` — a
victim chain's live Claude pane died with it ("tmux capture-pane ... failed:
no server running"), and the worker hung holding the plan lock with no result.

Fix: each session runs on its own ``tmux -L mp-<session>`` server, and the
Python-side reap/exists/pane_pids helpers target that SAME socket. These
tests assert the ``-L <socket>`` selector is present on every tmux argv and that
the socket derivation matches the vendored launcher's ``megaplanTmuxSocket``.
"""
from __future__ import annotations

import subprocess

import pytest

from arnold.pipelines.megaplan.runtime.process import TmuxSession, pane_pids, tmux_socket_for


def _capture_args(monkeypatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(args, *a, **k):
        calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_socket_is_deterministic_and_matches_launcher_derivation():
    # MUST mirror megaplanTmuxSocket() in vendor/shannon/index.ts.
    assert tmux_socket_for("abc123") == "mp-abc123"
    assert tmux_socket_for("abc123") == tmux_socket_for("abc123")
    assert tmux_socket_for("other") != tmux_socket_for("abc123")


def test_socket_env_override(monkeypatch):
    monkeypatch.setenv("SHANNON_TMUX_SOCKET", "override-sock")
    assert tmux_socket_for("ignored") == "override-sock"
    assert TmuxSession("ignored").socket == "override-sock"


def test_teardown_and_exists_pin_private_socket(monkeypatch):
    calls = _capture_args(monkeypatch)
    sess = TmuxSession("6745e6b5a884")
    sess.teardown()
    sess.exists()
    assert len(calls) == 3
    for argv in calls:
        assert argv[0] == "tmux"
        assert argv[1] == "-L"
        assert argv[2] == "mp-6745e6b5a884"
    # subcommands are preserved after the socket selector
    assert calls[0][3:6] == ["kill-session", "-t", "6745e6b5a884"]
    assert calls[1][3:4] == ["kill-server"]
    assert calls[2][3:6] == ["has-session", "-t", "6745e6b5a884"]


def test_pane_pids_pins_private_socket(monkeypatch):
    calls = _capture_args(monkeypatch)
    pane_pids("deadbeef0000")
    assert calls[0][:3] == ["tmux", "-L", "mp-deadbeef0000"]
    assert "list-panes" in calls[0]


def test_distinct_sessions_never_share_a_socket(monkeypatch):
    calls = _capture_args(monkeypatch)
    TmuxSession("AAAA").teardown()
    TmuxSession("BBBB").teardown()
    assert calls[0][2] == "mp-AAAA"
    assert calls[2][2] == "mp-BBBB"
    assert calls[0][2] != calls[2][2]
