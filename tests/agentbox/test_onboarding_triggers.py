"""Trigger wiring tests (Batch 4).

Covers:
- T1: first-run onboarding hook in ``agentbox.arnold_agent.main``
- T2: ``preflight_or_raise`` TTY menu option [4] wired to the onboarding flow
- T3: ``megaplan doctor --onboard`` / ``agentbox doctor --onboard``
- Golden regression [W1/R1]: headless/non-TTY behavior byte-for-byte
- Old-pin propagation [W1/R2]: offer returning None falls through to the
  original failure paths unchanged
"""

from __future__ import annotations

import argparse
import builtins
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from agentbox import arnold_agent
from agentbox.cli import build_parser as agentbox_build_parser
from agentbox.cli import main as agentbox_cli_main
from agentbox.onboarding import detect as detect_mod
from agentbox.onboarding import flow as flow_mod
from agentbox.onboarding.flow import FlowResult
from agentbox.onboarding.flow import should_offer
from arnold_pipelines.megaplan.preflight import preflight_or_raise


class _ExecSentinel(Exception):
    """Raised by the fake execvp to stop main() without replacing the process."""


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_trigger_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards read these; make every test start from a neutral machine."""
    for var in ("CI", "MEGAPLAN_RESIDENT_MODE", "ARNOLD_STOCK_OMP"):
        monkeypatch.delenv(var, raising=False)


class _FakeTTY:
    """stdin/stderr stand-in whose isatty() says yes."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def isatty(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self.parts.append(text)
        return len(text)

    def flush(self) -> None:
        pass


def _fake_ttys(monkeypatch: pytest.MonkeyPatch) -> tuple[_FakeTTY, _FakeTTY]:
    stdin_tty, stderr_tty = _FakeTTY(), _FakeTTY()
    monkeypatch.setattr(sys, "stdin", stdin_tty)
    monkeypatch.setattr(sys, "stderr", stderr_tty)
    return stdin_tty, stderr_tty


def _scan_report(*statuses: str):
    providers = tuple(
        detect_mod.ProviderScan(
            id=f"p{i}",
            status=status,
            origin=None,
            env_keys=(),
            default_route="vendor/model",
        )
        for i, status in enumerate(statuses)
    )
    return detect_mod.ScanReport(providers=providers, rank_order=())


def _patch_scan(monkeypatch: pytest.MonkeyPatch, *statuses: str) -> None:
    report = _scan_report(*statuses)
    monkeypatch.setattr(detect_mod, "scan_providers", lambda **kw: report)


def _patch_offer(monkeypatch: pytest.MonkeyPatch, result=None) -> list[dict]:
    calls: list[dict] = []

    def fake_offer(**kw):
        calls.append(kw)
        return result

    monkeypatch.setattr(flow_mod, "offer_and_repreflight", fake_offer)
    return calls


def _record_execvp(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    recorded: list[list[str]] = []

    def fake_execvp(_file: str, argv: list[str]) -> None:
        recorded.append(list(argv))
        raise _ExecSentinel

    monkeypatch.setattr(arnold_agent.os, "execvp", fake_execvp)
    return recorded


def _launchable(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    monkeypatch.setattr(
        arnold_agent, "_find_launcher", lambda: Path("/fake/bin/agent")
    )
    return _record_execvp(monkeypatch)


@contextmanager
def _onboarding_unimportable():
    """Evict cached onboarding modules and make them impossible to re-import."""
    saved = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "agentbox.onboarding"
        or name.startswith("agentbox.onboarding.")
    }
    for name in saved:
        del sys.modules[name]

    class _Blocker:
        def find_spec(self, fullname, path=None, target=None):
            parts = fullname.split(".")
            if parts[:2] == ["agentbox", "onboarding"]:
                raise ImportError(f"blocked for test: {fullname}")
            return None

    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        for name, mod in saved.items():
            sys.modules[name] = mod


# ---------------------------------------------------------------------------
# T1 guard matrix — integration through arnold_agent.main
# ---------------------------------------------------------------------------


def test_non_tty_launch_never_offers(monkeypatch, capsys) -> None:
    """pytest's captured stdio is not a TTY: the headless path never offers."""
    _launchable(monkeypatch)
    calls = _patch_offer(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    assert calls == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize("argv", [["--resume", "abc"], ["-c"], ["--session-dir", "d"]])
def test_resume_style_flags_never_offers(monkeypatch, argv) -> None:
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)  # zero routes ready, would otherwise offer
    _launchable(monkeypatch)
    calls = _patch_offer(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main(argv)

    assert calls == []


def test_one_shot_message_never_offers(monkeypatch) -> None:
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)
    _launchable(monkeypatch)
    calls = _patch_offer(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main(["fix the bug"])

    assert calls == []


def test_ci_env_never_offers(monkeypatch) -> None:
    monkeypatch.setenv("CI", "1")
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)
    _launchable(monkeypatch)
    calls = _patch_offer(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    assert calls == []


def test_interactive_fresh_machine_offers_once(monkeypatch) -> None:
    """Interactive TTY session, no ready route anywhere: exactly one offer."""
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch, "missing", "candidate")
    recorded = _launchable(monkeypatch)
    calls = _patch_offer(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["message"] is False
    assert kwargs["flags"] == []
    assert kwargs["stdin_tty"] is True
    assert kwargs["stderr_tty"] is True
    # The repreflight closure is the live zero-route check.
    assert kwargs["repreflight"]() is False
    # Launch proceeds regardless of the offer outcome.
    assert recorded and recorded[0][1] == "run"


def test_machine_with_ready_route_is_never_nagged(monkeypatch) -> None:
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch, "ready", "candidate")
    _launchable(monkeypatch)
    calls = _patch_offer(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    assert calls == []


def test_onboarding_exception_is_swallowed_and_launch_proceeds(
    monkeypatch, capsys
) -> None:
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)
    recorded = _launchable(monkeypatch)

    def boom(**kw):
        raise RuntimeError("onboarding exploded")

    monkeypatch.setattr(flow_mod, "offer_and_repreflight", boom)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert recorded  # reached exec


def test_scan_exploding_is_also_swallowed(monkeypatch, capsys) -> None:
    _fake_ttys(monkeypatch)
    monkeypatch.setattr(
        detect_mod,
        "scan_providers",
        lambda **kw: (_ for _ in ()).throw(RuntimeError("fs exploded")),
    )
    recorded = _launchable(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert recorded


# ---------------------------------------------------------------------------
# Golden regression [W1/R1] — headless stays byte-for-byte
# ---------------------------------------------------------------------------


def test_golden_headless_stderr_identical_with_and_without_onboarding(
    monkeypatch, capsys
) -> None:
    """With guards failing, main() output is byte-identical whether or not the
    onboarding package exists. The launcher-missing error fires AFTER the
    onboarding block, giving a non-trivial byte stream to compare."""
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: None)

    arnold_agent.main([])
    baseline = capsys.readouterr()

    with _onboarding_unimportable():
        arnold_agent.main([])
        blocked = capsys.readouterr()

    assert baseline.out == blocked.out
    assert baseline.err == blocked.err
    # Sanity: the original failure text is present in BOTH runs.
    assert "could not locate the omp agent launcher" in baseline.err


def test_golden_guards_fail_despite_tty_writes_zero_bytes(monkeypatch, capsys) -> None:
    """Unit proof complement: a full-TTY session with a failing guard (CI)
    emits nothing from the onboarding block."""
    monkeypatch.setenv("CI", "1")
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)
    _launchable(monkeypatch)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_guard_helper_agrees_with_block(monkeypatch) -> None:
    """should_offer is the single source of truth for the block's gate."""
    assert should_offer(
        stdin_tty=False, stderr_tty=True, message=False, flags=[]
    ) is False
    assert should_offer(
        stdin_tty=True, stderr_tty=True, message=False, flags=["--resume", "x"]
    ) is False


# ---------------------------------------------------------------------------
# Old-pin propagation [W1/R2] — offer None falls through to original failure
# ---------------------------------------------------------------------------


def test_t1_old_pin_none_propagates_to_original_failure_missing_launcher(
    monkeypatch,
) -> None:
    """PATH without omp: offer returns None (B3-tested) and main() lands on
    the exact pre-existing launcher-missing failure."""
    _stdin_tty, stderr_tty = _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)
    monkeypatch.setattr(arnold_agent, "_find_launcher", lambda: None)
    calls = _patch_offer(monkeypatch, result=None)

    rc = arnold_agent.main([])

    assert rc == 1
    assert len(calls) == 1
    assert "could not locate the omp agent launcher" in "".join(stderr_tty.parts)


def test_t1_old_pin_none_still_execs_original_argv(monkeypatch) -> None:
    _fake_ttys(monkeypatch)
    _patch_scan(monkeypatch)
    recorded = _launchable(monkeypatch)
    _patch_offer(monkeypatch, result=None)

    with pytest.raises(_ExecSentinel):
        arnold_agent.main([])

    assert recorded == [["/fake/bin/agent", "run", "arnold"]]


# ---------------------------------------------------------------------------
# T2 — preflight_or_raise TTY menu
# ---------------------------------------------------------------------------

_PROFILE = {"synth": "claude", "revise": "codex"}


def _tty_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)


def test_t2_non_tty_exit_7_untouched_and_silent_flow(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fail_input(prompt=""):
        raise AssertionError("non-TTY branch must never prompt")

    def fail_flow(**kw):
        raise AssertionError("non-TTY branch must never invoke the flow")

    monkeypatch.setattr(builtins, "input", fail_input)
    monkeypatch.setattr(flow_mod, "run_flow", fail_flow)

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(_PROFILE, pipeline_name="p", profile_name="prof")

    assert exc_info.value.code == 7
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ANTHROPIC_API_KEY" in captured.err


def test_t2_tty_option_4_invokes_flow_then_exits_7_while_still_missing(
    monkeypatch,
) -> None:
    _tty_stdout(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "4")

    flow_calls: list[dict] = []

    def fake_run_flow(**kw):
        flow_calls.append(kw)
        return FlowResult(0, wired_provider="anthropic", verified=True)

    monkeypatch.setattr(flow_mod, "run_flow", fake_run_flow)

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(_PROFILE, pipeline_name="p", profile_name="prof")

    assert exc_info.value.code == 7
    assert len(flow_calls) == 1


def test_t2_tty_option_4_continues_when_credentials_now_present(
    monkeypatch,
) -> None:
    _tty_stdout(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "4")

    def fake_run_flow(**kw):
        # Wiring made the key visible to this process.
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-onboarded")
        return FlowResult(0, wired_provider="anthropic", verified=True)

    monkeypatch.setattr(flow_mod, "run_flow", fake_run_flow)

    assert (
        preflight_or_raise(
            {"synth": "claude"}, pipeline_name="p", profile_name="prof"
        )
        is None
    )


@pytest.mark.parametrize("answer", ["1", "2", "3", "", "n"])
def test_t2_tty_other_answers_keep_original_exit_7(monkeypatch, answer) -> None:
    _tty_stdout(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(builtins, "input", lambda prompt="": answer)

    def fail_flow(**kw):
        raise AssertionError("flow must only run for option 4")

    monkeypatch.setattr(flow_mod, "run_flow", fail_flow)

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(_PROFILE, pipeline_name="p", profile_name="prof")

    assert exc_info.value.code == 7


def test_t2_tty_eof_at_menu_keeps_exit_7(monkeypatch) -> None:
    _tty_stdout(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def eof_input(prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", eof_input)

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(_PROFILE, pipeline_name="p", profile_name="prof")

    assert exc_info.value.code == 7


def test_t2_old_pin_file_not_found_during_flow_keeps_exit_7(monkeypatch) -> None:
    """W1/R2 at the T2 call site: omp binary gone mid-offer -> exit 7."""
    _tty_stdout(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "4")

    def old_pin_flow(**kw):
        raise FileNotFoundError("omp binary vanished")

    monkeypatch.setattr(flow_mod, "run_flow", old_pin_flow)

    with pytest.raises(SystemExit) as exc_info:
        preflight_or_raise(_PROFILE, pipeline_name="p", profile_name="prof")

    assert exc_info.value.code == 7


# ---------------------------------------------------------------------------
# T3 — doctor --onboard
# ---------------------------------------------------------------------------


def test_megaplan_doctor_parser_accepts_onboard_flag() -> None:
    from arnold_pipelines.megaplan.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["doctor", "--onboard"]).onboard is True
    assert parser.parse_args(["doctor"]).onboard is False


def test_megaplan_doctor_onboard_reports_flow_exit_code(monkeypatch) -> None:
    from arnold_pipelines.megaplan.observability.doctor import handle_doctor

    calls: list[dict] = []
    monkeypatch.setattr(
        flow_mod,
        "run_flow",
        lambda **kw: calls.append(kw) or FlowResult(2),
    )

    rc = handle_doctor(Path("."), argparse.Namespace(onboard=True))

    assert rc == 2
    assert len(calls) == 1


def test_megaplan_doctor_without_flag_never_touches_flow(monkeypatch) -> None:
    from arnold_pipelines.megaplan.observability.doctor import handle_doctor

    def fail_flow(**kw):
        raise AssertionError("doctor without --onboard must not run the flow")

    monkeypatch.setattr(flow_mod, "run_flow", fail_flow)

    # Falls through to the usage error, exactly as before Batch 4.
    assert handle_doctor(Path("."), argparse.Namespace()) == 1


def test_agentbox_doctor_parser_accepts_onboard_flag() -> None:
    parser = agentbox_build_parser()
    assert parser.parse_args(["doctor", "--onboard"]).onboard is True
    assert parser.parse_args(["doctor"]).onboard is False


def test_agentbox_doctor_onboard_reports_flow_exit_code(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'ws'}\n", encoding="utf-8"
    )

    calls: list[dict] = []
    monkeypatch.setattr(
        flow_mod,
        "run_flow",
        lambda **kw: calls.append(kw) or FlowResult(0),
    )

    assert agentbox_cli_main(["doctor", "--onboard"]) == 0
    assert len(calls) == 1


def test_agentbox_doctor_without_flag_never_touches_flow(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTBOX_CONFIG", str(tmp_path / "agentbox.yaml"))
    (tmp_path / "agentbox.yaml").write_text(
        f"workspace_root: {tmp_path / 'ws'}\n", encoding="utf-8"
    )

    def fail_flow(**kw):
        raise AssertionError("doctor without --onboard must not run the flow")

    monkeypatch.setattr(flow_mod, "run_flow", fail_flow)

    # Pre-existing behavior: plain doctor runs its health checks (exit free).
    agentbox_cli_main(["doctor"])
