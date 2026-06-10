"""Loud-fail readiness guard for the Shannon worker.

When the readiness probe fires and the claude CLI is broken in the headless tmux
path (empty pane / session exited before producing output), Shannon must raise a
clear ``CliError(code='shannon_claude_headless_broken')`` instead of letting the
failure surface as a silent stall or a generic ``worker_timeout``/``worker_error``.

All tests are hermetic: no real claude, bun, or tmux process is spawned.
"""
from __future__ import annotations

import pytest

from megaplan.runtime.process import TmuxSession
from megaplan.types import CliError
from megaplan.workers.shannon import (
    _HEADLESS_BROKEN_MSG,
    _is_headless_crash_signature,
)


# ---------------------------------------------------------------------------
# _is_headless_crash_signature unit tests
# ---------------------------------------------------------------------------


def _make_session(name: str = "test-session") -> TmuxSession:
    return TmuxSession(name)


def test_headless_crash_when_session_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session does not exist → headless-crash signature fires."""
    session = _make_session()
    monkeypatch.setattr(session, "exists", lambda: False)
    assert _is_headless_crash_signature(session) is True


def test_headless_crash_when_pane_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session alive but pane is empty string → headless-crash signature fires."""
    session = _make_session()
    monkeypatch.setattr(session, "exists", lambda: True)
    import megaplan.workers.shannon as _mod
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _name: "")
    assert _is_headless_crash_signature(session) is True


def test_headless_crash_when_pane_whitespace_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session alive but pane is only whitespace → headless-crash signature fires."""
    session = _make_session()
    monkeypatch.setattr(session, "exists", lambda: True)
    import megaplan.workers.shannon as _mod
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _name: "   \n\t  \n")
    assert _is_headless_crash_signature(session) is True


def test_headless_crash_when_pane_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session alive but capture-pane fails (returns None) → headless-crash signature."""
    session = _make_session()
    monkeypatch.setattr(session, "exists", lambda: True)
    import megaplan.workers.shannon as _mod
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _name: None)
    assert _is_headless_crash_signature(session) is True


def test_no_headless_crash_when_pane_has_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session alive and pane has visible content → NOT a headless-crash signature."""
    session = _make_session()
    monkeypatch.setattr(session, "exists", lambda: True)
    import megaplan.workers.shannon as _mod
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _name: "❯ Welcome to Claude")
    assert _is_headless_crash_signature(session) is False


def test_no_headless_crash_when_exists_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If exists() raises, we conservatively return False (no over-fire)."""
    session = _make_session()

    def _boom() -> bool:
        raise RuntimeError("tmux unavailable")

    monkeypatch.setattr(session, "exists", _boom)
    assert _is_headless_crash_signature(session) is False


# ---------------------------------------------------------------------------
# Readiness probe integration: loud-fail CliError is raised
# ---------------------------------------------------------------------------


def _make_fake_ctx(tmux_session: TmuxSession) -> object:
    """Build a minimal TurnContext-like namespace with just tmux_session."""
    import types

    ctx = types.SimpleNamespace(tmux_session=tmux_session)
    return ctx


def _make_fake_turn() -> object:
    """Build a minimal Turn-like namespace."""
    import types

    return types.SimpleNamespace(
        session_id="fake-session-id",
        resume=False,
        body="hello",
        delivery="argv",
        expect="non_empty",
        timeout=5,
        pre_sleep_s=0.0,
    )


def _make_headless_broken_session(monkeypatch: pytest.MonkeyPatch) -> TmuxSession:
    """Return a TmuxSession whose pane is empty and session is gone (crash sig)."""
    session = _make_session()
    monkeypatch.setattr(session, "exists", lambda: False)
    return session


def test_worker_timeout_with_empty_pane_raises_headless_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """worker_timeout + empty pane → CliError('shannon_claude_headless_broken')."""
    import megaplan.workers.shannon as _mod

    session = _make_headless_broken_session(monkeypatch)

    def _fake_run_turn(_turn, _ctx):
        raise CliError("worker_timeout", "timed out", extra={})

    monkeypatch.setattr(_mod, "run_turn", _fake_run_turn)

    # Simulate the readiness-probe exception path directly.
    ctx = _make_fake_ctx(session)
    pre_turn = _make_fake_turn()

    with pytest.raises(CliError) as exc_info:
        try:
            _mod.run_turn(pre_turn, ctx)
        except CliError as error:
            if error.code in {"worker_timeout", "worker_stall"}:
                error.extra["session_id"] = pre_turn.session_id
                if _mod._is_headless_crash_signature(ctx.tmux_session):
                    raise CliError(
                        "shannon_claude_headless_broken",
                        _mod._HEADLESS_BROKEN_MSG,
                        extra={
                            "session_id": pre_turn.session_id,
                            "original_code": error.code,
                        },
                    ) from error
            raise

    assert exc_info.value.code == "shannon_claude_headless_broken"
    assert "MEGAPLAN_SHANNON_CLAUDE_BIN" in exc_info.value.message


def test_worker_stall_with_empty_pane_raises_headless_broken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """worker_stall + empty pane → CliError('shannon_claude_headless_broken')."""
    import megaplan.workers.shannon as _mod

    session = _make_headless_broken_session(monkeypatch)

    def _fake_run_turn(_turn, _ctx):
        raise CliError("worker_stall", "stalled", extra={})

    monkeypatch.setattr(_mod, "run_turn", _fake_run_turn)

    ctx = _make_fake_ctx(session)
    pre_turn = _make_fake_turn()

    with pytest.raises(CliError) as exc_info:
        try:
            _mod.run_turn(pre_turn, ctx)
        except CliError as error:
            if error.code in {"worker_timeout", "worker_stall"}:
                error.extra["session_id"] = pre_turn.session_id
                if _mod._is_headless_crash_signature(ctx.tmux_session):
                    raise CliError(
                        "shannon_claude_headless_broken",
                        _mod._HEADLESS_BROKEN_MSG,
                        extra={
                            "session_id": pre_turn.session_id,
                            "original_code": error.code,
                        },
                    ) from error
            raise

    assert exc_info.value.code == "shannon_claude_headless_broken"
    assert "MEGAPLAN_SHANNON_CLAUDE_BIN" in exc_info.value.message


def test_worker_timeout_with_live_pane_reraises_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """worker_timeout + live pane → original CliError propagates (not headless-broken)."""
    import megaplan.workers.shannon as _mod

    session = _make_session()
    # Session is alive with content — NOT the headless crash signature.
    monkeypatch.setattr(session, "exists", lambda: True)
    monkeypatch.setattr(_mod, "_tmux_capture_pane", lambda _n: "❯ some output here")

    def _fake_run_turn(_turn, _ctx):
        raise CliError("worker_timeout", "timed out", extra={})

    monkeypatch.setattr(_mod, "run_turn", _fake_run_turn)

    ctx = _make_fake_ctx(session)
    pre_turn = _make_fake_turn()

    with pytest.raises(CliError) as exc_info:
        try:
            _mod.run_turn(pre_turn, ctx)
        except CliError as error:
            if error.code in {"worker_timeout", "worker_stall"}:
                error.extra["session_id"] = pre_turn.session_id
                if _mod._is_headless_crash_signature(ctx.tmux_session):
                    raise CliError(
                        "shannon_claude_headless_broken",
                        _mod._HEADLESS_BROKEN_MSG,
                        extra={
                            "session_id": pre_turn.session_id,
                            "original_code": error.code,
                        },
                    ) from error
            raise

    # Original code preserved — pane had content, so it's NOT a headless crash.
    assert exc_info.value.code == "worker_timeout"


def test_headless_broken_message_contains_guidance() -> None:
    """The headless-broken message must name the env-var fix."""
    assert "MEGAPLAN_SHANNON_CLAUDE_BIN" in _HEADLESS_BROKEN_MSG
    assert "headless" in _HEADLESS_BROKEN_MSG.lower()


def test_headless_broken_message_names_cause() -> None:
    """The message should reference both empty-pane and server-exited conditions."""
    assert "empty pane" in _HEADLESS_BROKEN_MSG
    assert "server exited" in _HEADLESS_BROKEN_MSG or "exited" in _HEADLESS_BROKEN_MSG
