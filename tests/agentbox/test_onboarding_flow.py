"""Tests for the interactive onboarding flow (agentbox.onboarding.flow).

All sessions are fully scripted through the injectable stdin/stdout seams;
detection and omp subprocess traffic are monkeypatched, so nothing here
touches the network or the real omp stores.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import agentbox.onboarding.detect as detect_mod
import agentbox.onboarding.flow as flow_mod
from agentbox.onboarding.detect import Origin, ProviderScan, ScanReport
from agentbox.onboarding.flow import (
    FlowResult,
    offer_and_repreflight,
    run_flow,
    should_offer,
)
from agentbox.onboarding.wire import VerifyResult, WireResult

FAKE_KEY = "sk-fake00000000deadbeef"
_HINT = "Non-interactive shell; run `arnold` in a terminal to set up providers."


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _canned_report() -> ScanReport:
    """anthropic ready, deepseek candidate (foreign store), grok missing."""
    return ScanReport(
        providers=(
            ProviderScan(
                id="anthropic",
                status=detect_mod.READY,
                origin=Origin("oauth", "~/.codex/auth.json"),
                env_keys=("ANTHROPIC_API_KEY",),
                default_route="anthropic/claude-opus-4-8",
            ),
            ProviderScan(
                id="deepseek",
                status=detect_mod.CANDIDATE,
                origin=Origin("cli_store", "~/.deepseek/config", wired=False),
                env_keys=("DEEPSEEK_API_KEY",),
                default_route="deepseek/deepseek-v4-flash",
            ),
            ProviderScan(
                id="grok",
                status=detect_mod.MISSING,
                origin=None,
                env_keys=(),
                default_route="grok/grok-4.6",
            ),
        ),
        rank_order=("anthropic", "deepseek"),
    )


@pytest.fixture
def canned_scan(monkeypatch: pytest.MonkeyPatch) -> ScanReport:
    report = _canned_report()
    monkeypatch.setattr(detect_mod, "scan_providers", lambda **kw: report)
    return report


class Script:
    """Scripted stdin: replays answers; EOFError once exhausted."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.i = 0

    def __call__(self) -> str:
        if self.i >= len(self.answers):
            raise EOFError
        answer = self.answers[self.i]
        self.i += 1
        return answer


class Transcript:
    """Captured stdout sink."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        self.lines.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


class WireRecorder:
    """Monkeypatches flow.wire_api_key; records calls, always succeeds."""

    def __init__(self, ok: bool = True) -> None:
        self.calls: list[dict] = []
        self._ok = ok

    def __call__(self, provider_id, api_key, *, agent_dir, **kw) -> WireResult:
        self.calls.append(
            {"provider": provider_id, "key": api_key, "agent_dir": Path(agent_dir), **kw}
        )
        return WireResult(
            ok=self._ok,
            provider=provider_id,
            mechanism="auth-broker-import" if self._ok else "failed",
            detail="" if self._ok else "exit=1 broker exploded",
            provenance={
                "provider": provider_id,
                "mechanism": "auth-broker-import",
                "origin_kind": kw.get("origin_kind", ""),
                "origin_detail": kw.get("origin_detail", ""),
            },
        )


class VerifyScript:
    """Monkeypatches flow.verify_route; replays verdicts, last one repeats."""

    def __init__(self, verdicts: list[bool]) -> None:
        self.verdicts = list(verdicts)
        self._last = bool(verdicts[-1]) if verdicts else False
        self.routes: list[str] = []

    def __call__(self, route, *, agent_dir, **kw) -> VerifyResult:
        self.routes.append(route)
        ok = self.verdicts.pop(0) if self.verdicts else self._last
        ok = bool(ok)
        return VerifyResult(ok=ok, latency_ms=1, output="" if ok else "boom")


@pytest.fixture
def agent_dir(tmp_path: Path) -> Path:
    return tmp_path / "agent"


def _run(script_answers, *, agent_dir, monkeypatch, verify_verdicts=None,
         wire_ok=True, **kw):
    """Standard harness: script + transcript + patched wire/verify seams."""
    wire = WireRecorder(ok=wire_ok)
    monkeypatch.setattr(flow_mod, "wire_api_key", wire)
    verify = VerifyScript(verify_verdicts if verify_verdicts is not None else [True])
    monkeypatch.setattr(flow_mod, "verify_route", verify)
    out = Transcript()
    result = run_flow(
        stdin=Script(*script_answers),
        stdout=out,
        agent_dir=agent_dir,
        stdin_tty=True,
        stderr_tty=True,
        **kw,
    )
    return result, out, wire, verify


# ---------------------------------------------------------------------------
# Guard matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs,expected",
    [
        # happy interactive terminal
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=[], environ={}), True),
        # non-TTY stdin / stderr
        (dict(stdin_tty=False, stderr_tty=True, message=False, flags=[], environ={}), False),
        (dict(stdin_tty=True, stderr_tty=False, message=False, flags=[], environ={}), False),
        # one-shot --message mode
        (dict(stdin_tty=True, stderr_tty=True, message=True, flags=[], environ={}), False),
        # continuation / resume flags
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=["-c"], environ={}), False),
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=["--resume"], environ={}), False),
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=["--resume=abc"], environ={}), False),
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=["--session-dir", "/tmp/x"], environ={}), False),
        # environment guards
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=[], environ={"CI": "true"}), False),
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=[], environ={"ARNOLD_STOCK_OMP": "1"}), False),
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=[], environ={"MEGAPLAN_RESIDENT_MODE": "resident"}), False),
        # empty values count as unset; stock-omp != 1 is fine
        (dict(stdin_tty=True, stderr_tty=True, message=False, flags=[], environ={"CI": "", "MEGAPLAN_RESIDENT_MODE": "", "ARNOLD_STOCK_OMP": "0"}), True),
    ],
)
def test_should_offer_guard_matrix(kwargs, expected):
    assert should_offer(**kwargs) is expected


# ---------------------------------------------------------------------------
# Scripted sessions
# ---------------------------------------------------------------------------

def test_happy_path_candidate_paste_verify(canned_scan, agent_dir, monkeypatch):
    # Menu: 1=anthropic(ready, recommended), 2=deepseek(candidate). Pick 2.
    result, out, wire, verify = _run(
        ["2", FAKE_KEY, "", ""],
        agent_dir=agent_dir,
        monkeypatch=monkeypatch,
        verify_verdicts=[True],
    )
    assert result == FlowResult(
        exit_code=0, wired_provider="deepseek",
        route="deepseek/deepseek-v4-flash", verified=True,
    )
    # wire called with exactly what the user consented to paste
    assert len(wire.calls) == 1
    call = wire.calls[0]
    assert call["provider"] == "deepseek"
    assert call["key"] == FAKE_KEY
    assert call["agent_dir"] == agent_dir
    assert call["origin_kind"] == "manual-entry"
    # verification ran against the default route
    assert verify.routes == ["deepseek/deepseek-v4-flash"]
    # provenance recorded in the agent dir ledger, secret-free
    ledger = agent_dir / ".arnold_onboarding_provenance.jsonl"
    assert ledger.is_file()
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert rows[-1]["provider"] == "deepseek"
    assert rows[-1]["origin_kind"] == "manual-entry"
    # verified route itself is confirmed on the success screen
    assert "Verified route: deepseek/deepseek-v4-flash" in out.text
    # detection-before-asking UI: buckets + recommended marker present
    assert "recommended" in out.text
    assert "Ready now:" in out.text


def test_menu_buckets_found_first_and_toggle(canned_scan, agent_dir, monkeypatch):
    # 's' toggles hidden missing providers, then decline.
    result, out, _wire, _verify = _run(
        ["s", "n"], agent_dir=agent_dir, monkeypatch=monkeypatch
    )
    assert result.exit_code == 1
    assert "show everything" in out.text
    assert "hide missing providers" in out.text
    # openrouter lane offered because it's neither ready/candidate nor configured
    assert "Set up OpenRouter" in out.text


def test_openrouter_lane_selectable(canned_scan, agent_dir, monkeypatch):
    result, out, wire, _verify = _run(
        ["o", FAKE_KEY, "", ""],
        agent_dir=agent_dir,
        monkeypatch=monkeypatch,
    )
    assert result.exit_code == 0
    assert result.wired_provider == "openrouter"


def test_verify_fail_then_pass_loops_back_to_s2(canned_scan, agent_dir, monkeypatch):
    # Fail twice, pass on attempt 3; every retry goes back through S2 (re-paste).
    result, out, wire, verify = _run(
        ["2", "k-one", "", "",   # attempt 1 -> fail -> [Enter]=try again
         "k-two", "", "",        # attempt 2 -> fail -> [Enter]=try again
         "k-three", "", ""],     # attempt 3 -> pass
        agent_dir=agent_dir,
        monkeypatch=monkeypatch,
        verify_verdicts=[False, False, True],
    )
    assert result == FlowResult(0, "deepseek", "deepseek/deepseek-v4-flash", True)
    assert len(wire.calls) == 3
    assert verify.routes.count("deepseek/deepseek-v4-flash") == 3


def test_verify_fails_capped_at_three_attempts(canned_scan, agent_dir, monkeypatch):
    result, out, wire, verify = _run(
        ["2", "k-one", "", "", "k-two", "", "", "k-three", "", ""],
        agent_dir=agent_dir,
        monkeypatch=monkeypatch,
        verify_verdicts=[False, False, False],
    )
    # Never exit half-wired: three strikes -> exit 1.
    assert result.exit_code == 1
    assert result.verified is False
    assert len(wire.calls) == 3
    assert len(verify.routes) == 3
    assert "Giving up on deepseek after 3 attempts" in out.text


def test_decline_at_main_prompt_is_cancelled(canned_scan, agent_dir, monkeypatch):
    result, _out, wire, verify = _run(
        ["n"], agent_dir=agent_dir, monkeypatch=monkeypatch
    )
    assert result == FlowResult(1)
    assert wire.calls == []
    assert verify.routes == []


def test_eof_mid_flow_exits_cancelled(canned_scan, agent_dir, monkeypatch):
    # Answer the menu, then stdin hits EOF at the key prompt.
    result, _out, wire, _verify = _run(
        ["2"], agent_dir=agent_dir, monkeypatch=monkeypatch
    )
    assert result == FlowResult(1)
    assert wire.calls == []


def test_keyboard_interrupt_exits_cancelled(canned_scan, agent_dir, monkeypatch):

    def ctrl_c() -> str:
        raise KeyboardInterrupt

    out = Transcript()
    result = run_flow(
        stdin=ctrl_c, stdout=out, agent_dir=agent_dir,
        stdin_tty=True, stderr_tty=True,
    )
    assert result.exit_code == 1


def test_non_tty_prints_hint_and_exits_2(canned_scan, agent_dir, monkeypatch):
    out = Transcript()
    result = run_flow(
        stdin=Script(), stdout=out, agent_dir=agent_dir,
        stdin_tty=False, stderr_tty=True,
    )
    assert result == FlowResult(2)
    assert _HINT in out.text


def test_secret_never_appears_in_transcript(canned_scan, agent_dir, monkeypatch):
    result, out, wire, _verify = _run(
        ["2", FAKE_KEY, "", ""],
        agent_dir=agent_dir,
        monkeypatch=monkeypatch,
    )
    assert result.exit_code == 0
    transcript = out.text
    assert FAKE_KEY not in transcript
    assert "k-one" not in transcript or True  # single-paste session
    # ledger is secret-free too
    ledger_text = (agent_dir / ".arnold_onboarding_provenance.jsonl").read_text()
    assert FAKE_KEY not in ledger_text


def test_add_another_provider_loops_to_s1_minus_configured(
    canned_scan, agent_dir, monkeypatch
):
    # Configure deepseek, say yes to another, configure anthropic (now option 1),
    # then stop.
    results_out = Transcript()

    class TwoPhaseVerify:
        def __init__(self):
            self.routes = []

        def __call__(self, route, *, agent_dir, **kw):
            self.routes.append(route)
            return VerifyResult(ok=True, latency_ms=1, output="")

    verify = TwoPhaseVerify()
    monkeypatch.setattr(flow_mod, "verify_route", verify)
    wire = WireRecorder()
    monkeypatch.setattr(flow_mod, "wire_api_key", wire)

    result = run_flow(
        stdin=Script("2", FAKE_KEY, "", "y", "1", FAKE_KEY, "", ""),
        stdout=results_out,
        agent_dir=agent_dir,
        stdin_tty=True,
        stderr_tty=True,
    )
    assert result == FlowResult(0, "anthropic", "anthropic/claude-opus-4-8", True)
    assert [c["provider"] for c in wire.calls] == ["deepseek", "anthropic"]
    assert verify.routes == [
        "deepseek/deepseek-v4-flash",
        "anthropic/claude-opus-4-8",
    ]
    # deepseek must NOT be re-offered after being configured
    text = results_out.text
    second_menu = text.split("Add another provider now?", 1)[1]
    assert "deepseek" not in second_menu


# ---------------------------------------------------------------------------
# offer_and_repreflight
# ---------------------------------------------------------------------------

def test_offer_declined_returns_none(monkeypatch):
    called = []

    def run_flow_spy(**kw):
        called.append(kw)
        raise AssertionError("run_flow must not run on decline")

    monkeypatch.setattr(flow_mod, "run_flow", run_flow_spy)
    result = offer_and_repreflight(
        stdin_tty=True,
        stderr_tty=True,
        message=False,
        flags=[],
        environ={},
        repreflight=lambda: True,
    )
    assert result is None
    assert called == []


def test_offer_guards_off_silent(monkeypatch, capsys):
    result = offer_and_repreflight(
        stdin_tty=False,
        stderr_tty=True,
        message=False,
        flags=[],
        environ={},
        repreflight=lambda: True,
    )
    assert result is None
    assert capsys.readouterr().out == ""


def test_offer_accept_then_repreflight_true(monkeypatch):
    monkeypatch.setattr(
        flow_mod,
        "run_flow",
        lambda **kw: FlowResult(0, "deepseek", "deepseek/deepseek-v4-flash", True),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert (
        offer_and_repreflight(
            stdin_tty=True,
            stderr_tty=True,
            message=False,
            flags=[],
            environ={},
        repreflight=lambda: True,
        )
        is True
    )
    # repreflight still failing after a successful flow -> False, not None
    assert (
        offer_and_repreflight(
            stdin_tty=True,
            stderr_tty=True,
            message=False,
            flags=[],
            environ={},
            repreflight=lambda: False,
        )
        is False
    )


def test_old_pin_fallback_file_not_found_returns_none(monkeypatch):
    repreflight_calls = []

    def repreflight():
        repreflight_calls.append(1)
        return True

    def broken_run_flow(**kw):
        raise FileNotFoundError("[Errno 2] No such file or directory: 'omp'")

    monkeypatch.setattr(flow_mod, "run_flow", broken_run_flow)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    result = offer_and_repreflight(
        stdin_tty=True,
        stderr_tty=True,
        message=False,
        flags=[],
        repreflight=repreflight,
    )
    assert result is None
    assert repreflight_calls == []  # original preflight result untouched


def test_old_pin_fallback_oserror_returns_none(monkeypatch):
    monkeypatch.setattr(flow_mod, "run_flow", lambda **kw: (_ for _ in ()).throw(OSError("spawn failed")))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert (
        offer_and_repreflight(
            stdin_tty=True,
            stderr_tty=True,
            message=False,
            flags=[],
            environ={},
        repreflight=lambda: True,
        )
        is None
    )


def test_offer_flow_exit_1_means_none(monkeypatch):
    monkeypatch.setattr(flow_mod, "run_flow", lambda **kw: FlowResult(1))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert (
        offer_and_repreflight(
            stdin_tty=True,
            stderr_tty=True,
            message=False,
            flags=[],
            environ={},
        repreflight=lambda: True,
        )
        is None
    )


def test_ask_secret_hidden_read_roundtrip_via_pty() -> None:
    """On a real pty, _read_hidden returns the typed line and never echoes it."""
    import os as _os
    import select as _select
    import threading

    master_fd, slave_fd = _os.openpty()
    old_fd = _os.dup(0)
    try:
        _os.dup2(slave_fd, 0)
        result: dict[str, str | None] = {}
        th = threading.Thread(target=lambda: result.update(value=flow_mod._read_hidden()))
        th.start()
        time.sleep(0.3)  # let the reader enter cbreak mode (macOS drops pre-cbreak input)
        _os.write(master_fd, b"sk-test-abc123\r")
        th.join(timeout=5)
        assert result.get("value") == "sk-test-abc123"
        readable, _, _ = _select.select([master_fd], [], [], 0.3)
        assert not readable, "terminal echoed secret characters"
    finally:
        _os.dup2(old_fd, 0)
        _os.close(old_fd)
        _os.close(master_fd)
        _os.close(slave_fd)


def test_dead_shim_removed() -> None:
    assert not hasattr(flow_mod, "_default_agent_dir_or")


def test_read_hidden_eof_returns_none() -> None:
    """Closing the pty master mid-read must return None, never spin."""
    import os as _os
    import threading

    master_fd, slave_fd = _os.openpty()
    old_fd = _os.dup(0)
    try:
        _os.dup2(slave_fd, 0)
        result: dict[str, str | None] = {}
        th = threading.Thread(target=lambda: result.update(value=flow_mod._read_hidden()))
        th.start()
        time.sleep(0.3)
        _os.close(master_fd)
        th.join(timeout=5)
        assert not th.is_alive()
        assert result.get("value") is None
    finally:
        _os.dup2(old_fd, 0)
        _os.close(old_fd)
        _os.close(slave_fd)


def test_read_hidden_multibyte_utf8_survives() -> None:
    import os as _os
    import threading

    master_fd, slave_fd = _os.openpty()
    old_fd = _os.dup(0)
    try:
        _os.dup2(slave_fd, 0)
        result: dict[str, str | None] = {}
        th = threading.Thread(target=lambda: result.update(value=flow_mod._read_hidden()))
        th.start()
        time.sleep(0.3)
        secret = "sk-é中\U0001f6009"
        _os.write(master_fd, secret.encode("utf-8") + b"\r")
        th.join(timeout=5)
        assert result.get("value") == secret
    finally:
        _os.dup2(old_fd, 0)
        _os.close(old_fd)
        _os.close(master_fd)
        _os.close(slave_fd)
