"""Default-on claude-binary pinning for the Shannon worker.

Regression coverage for the headless wedge where the Claude CLI auto-updater
repoints ~/.local/bin/claude to a newer build that crashes in the tmux path.
Shannon pins the resolved claude binary (by absolute path) on the child PATH so
a mid-run symlink flip can't switch the version under a running step.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from megaplan.types import CliError
from megaplan.workers.shannon import (
    ShannonConfig,
    _assert_runnable_claude_binary,
    _install_claude_pin,
    _resolve_pinned_claude,
)


def _cfg(env: dict[str, str]) -> ShannonConfig:
    base = {"MEGAPLAN_SHANNON_CLAUDE_CONFIG_MODE": "native"}
    base.update(env)
    return ShannonConfig.load({}, env=base)


def test_pin_claude_defaults_on() -> None:
    cfg = _cfg({})
    assert cfg.pin_claude is True
    assert cfg.claude_bin == ""


def test_pin_claude_can_be_disabled() -> None:
    cfg = _cfg({"MEGAPLAN_SHANNON_PIN_CLAUDE": "0"})
    assert cfg.pin_claude is False
    assert _resolve_pinned_claude(cfg) is None


def test_explicit_claude_bin_override(tmp_path: Path) -> None:
    fake = tmp_path / "claude-2.1.165"
    fake.write_text("#!/bin/bash\necho fake\n")
    fake.chmod(0o755)
    cfg = _cfg({"MEGAPLAN_SHANNON_CLAUDE_BIN": str(fake)})
    assert cfg.claude_bin == str(fake)
    assert _resolve_pinned_claude(cfg) == os.path.realpath(str(fake))


def test_invalid_claude_bin_fails_loudly(tmp_path: Path) -> None:
    cfg = _cfg({"MEGAPLAN_SHANNON_CLAUDE_BIN": str(tmp_path / "does-not-exist")})
    with pytest.raises(CliError):
        _resolve_pinned_claude(cfg)


def test_pin_resolves_symlink_target_for_drift_immunity(tmp_path: Path) -> None:
    # symlink -> real versioned binary; the pin must capture the REAL path so a
    # later repoint of the symlink cannot change what runs.
    real = tmp_path / "versions" / "2.1.165"
    real.parent.mkdir(parents=True)
    real.write_text("x")
    real.chmod(0o755)
    link = tmp_path / "claude"
    os.symlink(real, link)
    cfg = _cfg({"MEGAPLAN_SHANNON_CLAUDE_BIN": str(link)})
    assert _resolve_pinned_claude(cfg) == os.path.realpath(str(real))


def test_self_referential_stub_rejected_loudly(tmp_path: Path) -> None:
    # The crashed-auto-update residue: a tiny script that execs ITSELF in an
    # infinite loop. Pinning it yields a blind readiness timeout + empty pane.
    # The resolver must reject it with an actionable CliError, not pin it.
    stub = tmp_path / "versions" / "2.1.165"
    stub.parent.mkdir(parents=True)
    stub.write_text(f'#!/bin/bash\nexec {stub} "$@"\n')
    stub.chmod(0o755)
    cfg = _cfg({"MEGAPLAN_SHANNON_CLAUDE_BIN": str(stub)})
    with pytest.raises(CliError) as ei:
        _resolve_pinned_claude(cfg)
    assert "self-referential stub" in str(ei.value)


def test_self_referential_stub_via_symlink_rejected(tmp_path: Path) -> None:
    # Same stub, reached through the ~/.local/bin/claude symlink that points
    # back at it — the validator resolves both sides to the same realpath.
    stub = tmp_path / "versions" / "2.1.165"
    stub.parent.mkdir(parents=True)
    link = tmp_path / "claude"
    os.symlink(stub, link)
    stub.write_text(f'#!/bin/bash\nexec {link} "$@"\n')
    stub.chmod(0o755)
    with pytest.raises(CliError):
        _assert_runnable_claude_binary(os.path.realpath(str(link)), origin="test")


def test_legitimate_wrapper_shim_passes(tmp_path: Path) -> None:
    # A real exec-wrapper shim points at a DIFFERENT target — must not trip.
    target = tmp_path / "versions" / "2.1.173"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    target.chmod(0o755)
    shim = tmp_path / "claude"
    shim.write_text(f'#!/bin/bash\nexec {target} "$@"\n')
    shim.chmod(0o755)
    _assert_runnable_claude_binary(str(shim), origin="test")  # no raise


def test_large_binary_not_sniffed(tmp_path: Path) -> None:
    # Native builds are huge; the validator skips them without reading them in.
    big = tmp_path / "versions" / "2.1.173"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"\x00" * (70 * 1024))
    _assert_runnable_claude_binary(str(big), origin="test")  # no raise


def test_install_pin_shims_path_first(tmp_path: Path) -> None:
    pinned = tmp_path / "versions" / "2.1.165"
    pinned.parent.mkdir(parents=True)
    pinned.write_text("#!/bin/bash\necho 2.1.165\n")
    pinned.chmod(0o755)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    env = {"PATH": "/usr/bin:/bin"}

    new_env = _install_claude_pin(env, run_dir, str(pinned))

    shim = run_dir / "claude_pin" / "claude"
    assert shim.is_symlink() or shim.is_file()
    assert os.path.realpath(str(shim)) == os.path.realpath(str(pinned))
    # shim dir is FIRST on PATH so the launcher's `which claude` finds it.
    assert new_env["PATH"].split(os.pathsep)[0] == str(run_dir / "claude_pin")
    # input env is not mutated.
    assert env["PATH"] == "/usr/bin:/bin"
