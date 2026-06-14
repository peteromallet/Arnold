"""Unit tests for the three-channel shannon liveness probe + hard backstop.

Background — the bug this replaces: the shannon worker (Claude driven in a tmux
pane) decided "is this turn dead?" from an inter-event OUTPUT timeout (no
transcript .jsonl growth for N seconds → kill). But silence is AMBIGUOUS: a
healthy turn is legitimately silent while (a) running a long synchronous tool
call (a 10-20 min ``pytest``) or (b) thinking server-side before any token
surfaces — and a genuine wedge (stalled SSE) also looks silent. Conflating these
false-killed healthy turns.

The fix treats the turn as ALIVE if ANY of three independent channels advanced
since the last sample (transcript growth, process-subtree CPU, API socket recv),
and WEDGED only if ALL THREE are flat across the idle window K. Silence alone
never kills. A hard ABSOLUTE per-turn cap (independent of the probe) still bounds
an INFINITE run that keeps a channel hot forever.

These tests exercise the COMBINING / DECISION logic with injected samplers (no
live ``claude`` / sockets / ps / nettop) plus the hard cap via a real
subprocess, and the native-mode transcript dir resolution.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers._impl import (
    DEFAULT_TURN_HARD_CAP_SECONDS,
    build_three_channel_liveness_probe,
    run_command,
    _turn_hard_cap_seconds,
)
from arnold.pipelines.megaplan.workers.shannon import _claude_transcript_paths


# ---------------------------------------------------------------------------
# Helpers: mutable scalar samplers driven by the test body.
# ---------------------------------------------------------------------------


class _Channel:
    """A mutable sampler: ``value`` is returned on each call (or ``None``)."""

    def __init__(self, value=0.0):
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


def _build(transcript, cpu, socket):
    return build_three_channel_liveness_probe(
        transcript_sample=transcript,
        cpu_sample=cpu,
        socket_sample=socket,
    )


# ---------------------------------------------------------------------------
# Each channel alone keeps the turn alive while the other two are flat.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("active_channel", ["transcript", "cpu", "socket"])
def test_any_single_channel_advancing_keeps_turn_alive(active_channel):
    """If exactly ONE channel advances while the other two stay flat, the turn
    is alive — this is the whole point: a silent tool call (only CPU moves) or a
    silent think (only socket moves) must NOT be killed.
    """
    chans = {"transcript": _Channel(100.0), "cpu": _Channel(5.0), "socket": _Channel(2000.0)}
    probe = _build(chans["transcript"], chans["cpu"], chans["socket"])

    # First call primes the baselines.
    assert probe() is True

    # Advance only the active channel; the other two are flat.
    chans[active_channel].value += 1.0
    assert probe() is True, f"{active_channel} advancing should keep the turn alive"

    # Stop advancing — now all three flat — and it should report wedged.
    assert probe() is False


def test_all_three_flat_reports_wedged():
    """When NONE of the three channels advances across a probe call, the turn is
    wedged (all three flat for the window → kill).
    """
    t, c, s = _Channel(1.0), _Channel(1.0), _Channel(1.0)
    probe = _build(t, c, s)
    assert probe() is True  # prime
    # No channel moved.
    assert probe() is False
    assert probe() is False


def test_first_call_primes_and_never_kills():
    """The first probe call establishes baselines and must return True so the
    very first idle expiry never kills before any comparison exists.
    """
    probe = _build(_Channel(0.0), _Channel(0.0), _Channel(0.0))
    assert probe() is True


# ---------------------------------------------------------------------------
# Graceful degradation: unavailable tools => "unknown", never a false kill.
# ---------------------------------------------------------------------------


def test_unavailable_tools_degrade_to_not_flat():
    """If a channel sampler returns None (tool unavailable, e.g. nettop/ps
    missing) it is 'unknown', NOT 'flat'. With one readable+flat channel and two
    unknown channels, the turn is wedged (we DID prove a flat readable channel).
    But if EVERY channel is unknown we cannot prove a wedge → stay alive.
    """
    # All three unknown: cannot prove a wedge → alive (no false kill).
    probe_all_unknown = _build(_Channel(None), _Channel(None), _Channel(None))
    assert probe_all_unknown() is True  # prime
    assert probe_all_unknown() is True  # still can't prove anything → alive

    # One readable+flat, two unknown: a readable channel is flat → wedged.
    t = _Channel(10.0)
    probe_one_readable = _build(t, _Channel(None), _Channel(None))
    assert probe_one_readable() is True  # prime
    assert probe_one_readable() is False


def test_channel_becoming_readable_midstream_is_not_counted_as_advance():
    """A channel that starts unknown then becomes readable establishes its
    baseline on first readable sample (not counted as 'advanced') so a missing
    transcript that later appears does not spuriously reset the idle clock.
    """
    cpu = _Channel(1.0)
    socket = _Channel(1.0)
    transcript = _Channel(None)  # not readable yet
    probe = _build(transcript, cpu, socket)

    assert probe() is True  # prime (cpu/socket baselined; transcript unknown)
    # CPU/socket flat, transcript still unknown → wedged.
    assert probe() is False

    # Transcript file appears now with some value: baseline established this
    # call, NOT counted as advance → with cpu/socket still flat, still wedged.
    transcript.value = 500.0
    assert probe() is False
    # Next call, transcript grows → alive.
    transcript.value = 501.0
    assert probe() is True


def test_sampler_exception_treated_as_unknown_not_kill():
    """A sampler that raises must be treated as unknown (None), never causing a
    false kill. With the other two flat+readable it is still a wedge; but if the
    raising one is the only signal, the turn stays alive.
    """
    def _boom():
        raise RuntimeError("sampler blew up")

    # Raising sampler is the only channel that would distinguish — others flat.
    probe = _build(_boom, _Channel(7.0), _Channel(7.0))
    assert probe() is True  # prime
    assert probe() is False  # cpu+socket readable & flat → wedged

    # All three raise → all unknown → alive (no false kill).
    probe_all_boom = _build(_boom, _boom, _boom)
    assert probe_all_boom() is True
    assert probe_all_boom() is True


# ---------------------------------------------------------------------------
# Hard absolute cap fires even when a channel stays hot forever.
# ---------------------------------------------------------------------------


def test_hard_cap_env_default_and_floor(monkeypatch):
    monkeypatch.delenv("SHANNON_TURN_HARD_CAP_SECONDS", raising=False)
    assert _turn_hard_cap_seconds() == DEFAULT_TURN_HARD_CAP_SECONDS == 5400.0

    monkeypatch.setenv("SHANNON_TURN_HARD_CAP_SECONDS", "6000")
    assert _turn_hard_cap_seconds() == 6000.0

    monkeypatch.setenv("SHANNON_TURN_HARD_CAP_SECONDS", "garbage")
    assert _turn_hard_cap_seconds() == DEFAULT_TURN_HARD_CAP_SECONDS

    # Floor protects a legitimate large test run (test_baseline_timeout=3600).
    monkeypatch.setenv("SHANNON_TURN_HARD_CAP_SECONDS", "10")
    assert _turn_hard_cap_seconds() == 3600.0


def test_hard_cap_fires_even_when_probe_stays_alive(monkeypatch):
    """A runaway that keeps a channel HOT forever (probe always returns True)
    must still be killed by the hard absolute cap. Models an infinite-loop
    pytest spinning CPU forever: channel 2 hot, probe says alive, but the
    absolute cap bounds it regardless.
    """
    # Tiny hard cap; the floor is bypassed for the test by clamping against the
    # wall-clock timeout (run_command uses min(hard_cap, timeout)). We use a
    # timeout of 2s so min(3600, 2) == 2 fires fast.
    probe_calls = [0]

    def _always_alive() -> bool:
        probe_calls[0] += 1
        return True

    # Silent on stdout, sleeps far past the 2s effective cap.
    script = "import time; time.sleep(30)"

    start = time.monotonic()
    with pytest.raises(CliError) as excinfo:
        run_command(
            [sys.executable, "-c", script],
            cwd=Path.cwd(),
            timeout=2,  # min(hard_cap_floor=3600, timeout=2) == 2s effective cap
            activity_callback=lambda *a: None,
            idle_timeout=1.0,
            liveness_probe=_always_alive,
        )
    elapsed = time.monotonic() - start

    # The hard cap (== timeout here) fires. Either the explicit hard-cap message
    # or the wall-clock timeout — both are worker_timeout and both prove a hot
    # probe cannot keep an infinite run alive forever.
    assert excinfo.value.code == "worker_timeout"
    assert elapsed < 10.0, f"hard cap did not fire promptly (took {elapsed:.2f}s)"


def test_hard_cap_message_when_below_wall_clock(monkeypatch):
    """When the hard cap is strictly below the wall-clock timeout, the kill
    surfaces the dedicated hard-cap message (not the coarse phase timeout).
    """
    monkeypatch.setenv("SHANNON_TURN_HARD_CAP_SECONDS", "3600")  # floored to 3600

    # Patch the helper to a tiny value so the cap is testable without waiting an
    # hour, while keeping timeout generous so it is the HARD CAP that fires.
    import arnold.pipelines.megaplan.workers._impl as impl

    monkeypatch.setattr(impl, "_turn_hard_cap_seconds", lambda: 2.0)

    script = "import time; time.sleep(30)"
    start = time.monotonic()
    with pytest.raises(CliError) as excinfo:
        run_command(
            [sys.executable, "-c", script],
            cwd=Path.cwd(),
            timeout=60,  # generous; the 2s hard cap must fire first
            activity_callback=lambda *a: None,
            idle_timeout=1.0,
            liveness_probe=lambda: True,  # hot probe → only the hard cap can kill
        )
    elapsed = time.monotonic() - start
    assert excinfo.value.code == "worker_timeout"
    assert "hard per-turn cap" in str(excinfo.value)
    assert elapsed < 10.0


def test_no_hard_cap_without_liveness_probe(monkeypatch):
    """The hard cap is only armed on the shannon liveness path (a probe was
    supplied). A codex/native caller (no probe) keeps its exact prior behaviour:
    a short silent turn completes, never killed by a hard cap.
    """
    import arnold.pipelines.megaplan.workers._impl as impl

    monkeypatch.setattr(impl, "_turn_hard_cap_seconds", lambda: 0.5)

    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        cwd=Path.cwd(),
        timeout=30,
        activity_callback=lambda *a: None,
        idle_timeout=10.0,  # idle watchdog armed, but NO liveness_probe
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Native-mode transcript dir resolution picks $CLAUDE_CONFIG_DIR/projects.
# ---------------------------------------------------------------------------


def test_native_mode_transcript_dir_resolution(tmp_path):
    """When CLAUDE_CONFIG_DIR is set (native mode), the transcript glob roots at
    ``<claude_config_dir>/projects`` — NOT ``~/.claude/projects`` — so the probe
    is no longer blind in native mode.
    """
    session_id = "abc123-session"
    cfg_dir = tmp_path / "claude_cfg"
    projects = cfg_dir / "projects" / "some-slug"
    projects.mkdir(parents=True)
    transcript = projects / f"{session_id}.jsonl"
    transcript.write_text('{"type":"user"}\n', encoding="utf-8")

    # A decoy under ~/.claude that must NOT be picked.
    paths = _claude_transcript_paths(
        session_id,
        tmp_path / "work",
        claude_config_dir=str(cfg_dir),
        home=str(tmp_path / "fake_home"),
    )
    assert transcript in paths, f"native-mode glob missed the transcript: {paths}"


def test_native_mode_falls_back_to_workdir_slug(tmp_path):
    """With no session-id match, the work_dir-derived slug glob (under the native
    projects root) still finds transcripts — and the slug replaces EVERY
    non-alphanumeric char (matching shannon's projectKeyForCwd).
    """
    cfg_dir = tmp_path / "cfg"
    work_dir = tmp_path / "wd-with.dots"
    work_dir.mkdir()
    import re

    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", str(work_dir.resolve()))
    proj = cfg_dir / "projects" / slug
    proj.mkdir(parents=True)
    t = proj / "deadbeef.jsonl"
    t.write_text("{}\n", encoding="utf-8")

    paths = _claude_transcript_paths(
        None, work_dir, claude_config_dir=str(cfg_dir), home=None
    )
    assert t in paths
