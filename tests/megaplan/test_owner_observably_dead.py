"""Regression tests for dead-owner custody lease reclaim.

The astrid dispatch-lease wedge (grok consult): a resume worker that dies
mid-batch leaves an ACTIVE custody lease with a dead PID, and the acquire path
denied it as ``active foreign`` until the 1h ``expires_at`` lapsed — wedging
every subsequent resume.  `owner_observably_dead` makes the acquire (and the
occurrence-join foreign-lease scan) reclaim dead-owner active leases.
"""

from __future__ import annotations

import os

from arnold_pipelines.megaplan.custody.contracts import (
    owner_observably_dead,
    process_birth_identity,
)


def _dead_pid() -> int:
    """A PID that is guaranteed gone on this host."""
    # Spawn a short-lived process and wait for it to exit.
    import subprocess
    import sys

    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def _alive_pid() -> int:
    return os.getpid()


def test_owner_observably_dead_rejects_empty_and_foreign_host() -> None:
    """Dead-owner checks fail closed for empty identity and foreign hosts."""
    birth = process_birth_identity()
    host = str(birth.get("host") or "")
    boot = str(birth.get("boot_id") or "")

    # Empty host / pid -> not dead (fail closed).
    assert not owner_observably_dead(host="", pid="", boot_id="")
    assert not owner_observably_dead(host=host, pid="", boot_id=boot)
    # Foreign host -> never dead (leases are never stolen cross-host).
    assert not owner_observably_dead(
        host="some-other-host.example", pid=str(_dead_pid()), boot_id=boot
    )


def test_owner_observably_dead_detects_dead_same_host_pid() -> None:
    """A same-host PID that is gone is observably dead (even unexpired)."""
    birth = process_birth_identity()
    host = str(birth.get("host") or "")
    boot = str(birth.get("boot_id") or "")
    dead = _dead_pid()
    assert not os.path.exists(f"/proc/{dead}")
    assert owner_observably_dead(host=host, pid=str(dead), boot_id=boot)


def test_owner_observably_dead_keeps_live_same_host_pid() -> None:
    """A live same-host PID is NOT dead — the lease must not be stolen."""
    birth = process_birth_identity()
    host = str(birth.get("host") or "")
    boot = str(birth.get("boot_id") or "")
    assert not owner_observably_dead(
        host=host, pid=str(_alive_pid()), boot_id=boot
    )


def test_owner_observably_dead_non_numeric_pid_fails_closed() -> None:
    """Unparseable pids never fabricate death."""
    birth = process_birth_identity()
    host = str(birth.get("host") or "")
    assert not owner_observably_dead(host=host, pid="not-a-pid", boot_id="")
