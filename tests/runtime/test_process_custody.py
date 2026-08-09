"""Tests for validation process custody receipts and lifecycle cutovers (Steps 16-17).

Covers:
  * Step 16 — recording coordinator PID/birth identity, process group, command
    hash, receipt path, policies, deterministic logs, and duplicate-launch
    rejection.
  * Step 17 — adopt-or-terminate exact jobs on exit, restart, timeout, signal,
    parent death, and runtime cutover.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest

from arnold_pipelines.megaplan.runtime.process import (
    CUSTODY_ADOPTION_POLICY_ADOPT,
    CUSTODY_ADOPTION_POLICY_TERMINATE,
    CUSTODY_CUTOVER_TRIGGERS,
    DuplicateLaunchError,
    PROCESS_CUSTODY_RECEIPT_SCHEMA,
    PROCESS_CUSTODY_RECEIPT_VERSION,
    ProcessCustodyReceipt,
    ProcessCustodyRegistry,
    apply_cutover_decision,
    command_hash,
    coordinator_birth_identity,
    resolve_cutover,
)


# ---------------------------------------------------------------------------
# Step 16 — identity recording, command hash, duplicate-launch rejection
# ---------------------------------------------------------------------------


def test_process_custody_records_identity():
    """ProcessCustodyReceipt records durable launch provenance and rejects
    duplicate launches while preserving the original validation outcome."""

    # --- command_hash: deterministic, stable, sha256-prefixed ---------------
    argv = ["python3", "-m", "pytest", "-x"]
    h1 = command_hash(argv)
    h2 = command_hash(tuple(argv))
    assert h1 == h2, "command_hash must be stable across list/tuple inputs"
    assert h1.startswith("sha256:"), "command_hash must carry a sha256: prefix"
    assert h1 != command_hash(["python3", "-m", "pytest", "-q"]), \
        "different argv must yield a different hash"

    # --- coordinator birth identity ---------------------------------------
    birth = coordinator_birth_identity()
    assert set(birth.keys()) >= {"host", "pid", "boot_id"}
    assert birth["pid"] == str(os.getpid()), \
        "birth identity must record the acting coordinator PID"

    # --- receipt construction + validation --------------------------------
    receipt = ProcessCustodyReceipt(
        receipt_id="rcpt-001",
        coordinator_pid=int(birth["pid"]),
        coordinator_host=birth["host"],
        coordinator_boot_id=birth["boot_id"],
        process_group_id=4242,
        command=("sleep", "30"),
        command_hash=command_hash(("sleep", "30")),
        receipt_path="process_custody/rcpt-001.json",
        adoption_policy=CUSTODY_ADOPTION_POLICY_ADOPT,
        deterministic_log_path="logs/validation-001.log",
        validation_outcome="passed",
        launched_at="2026-07-29T02:10:00Z",
    )
    assert receipt.schema == PROCESS_CUSTODY_RECEIPT_SCHEMA
    assert receipt.schema_version == PROCESS_CUSTODY_RECEIPT_VERSION
    assert receipt.custody_key == (receipt.command_hash, receipt.receipt_path)
    assert receipt.birth_identity == {
        "host": birth["host"],
        "pid": str(os.getpid()),
        "boot_id": birth["boot_id"],
    }

    # invalid adoption_policy is rejected
    with pytest.raises(ValueError):
        ProcessCustodyReceipt(
            receipt_id="bad",
            coordinator_pid=1,
            coordinator_host="h",
            coordinator_boot_id="b",
            process_group_id=1,
            command=("x",),
            command_hash="sha256:abc",
            receipt_path="p.json",
            adoption_policy="maybe",  # invalid
            deterministic_log_path="l.log",
            validation_outcome="passed",
            launched_at="2026-07-29T02:10:00Z",
        )

    # --- to_dict / from_dict roundtrip ------------------------------------
    restored = ProcessCustodyReceipt.from_dict(receipt.to_dict())
    assert restored == receipt, "roundtrip must be lossless"
    assert restored.command == ("sleep", "30")

    # --- duplicate-launch rejection ---------------------------------------
    registry = ProcessCustodyRegistry()
    registry.register(receipt)
    assert len(registry) == 1
    assert registry.find(receipt.command_hash, receipt.receipt_path) is receipt

    # a twin launch with the same custody key is rejected
    twin = ProcessCustodyReceipt(
        receipt_id="rcpt-002",
        coordinator_pid=int(birth["pid"]),
        coordinator_host=birth["host"],
        coordinator_boot_id=birth["boot_id"],
        process_group_id=9999,
        command=("sleep", "30"),
        command_hash=receipt.command_hash,
        receipt_path=receipt.receipt_path,
        adoption_policy=CUSTODY_ADOPTION_POLICY_ADOPT,
        deterministic_log_path="logs/validation-002.log",
        validation_outcome="passed",
        launched_at="2026-07-29T02:11:00Z",
    )
    with pytest.raises(DuplicateLaunchError):
        registry.register(twin)

    # after release the slot is free for a legitimate relaunch
    registry.release(receipt)
    assert len(registry) == 0
    registry.register(twin)  # now succeeds
    assert len(registry) == 1


# ---------------------------------------------------------------------------
# Step 17 — adopt-or-terminate on lifecycle cutovers
# ---------------------------------------------------------------------------


def _spawn_validation_job(argv: list[str]) -> subprocess.Popen:
    """Spawn *argv* as its own session/group leader (mirrors spawn())."""
    return subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _is_alive(proc: subprocess.Popen) -> bool:
    return proc.poll() is None


def test_exit_restart_timeout_and_cutover_adopt_or_terminate():
    """resolve_cutover + apply_cutover_decision adopt the exact valid job or
    terminate the recorded process group, always preserving the outcome."""

    argv = ["sleep", "300"]
    cmd_hash = command_hash(argv)
    proc = _spawn_validation_job(argv)
    try:
        # Give the kernel a moment to assign the PID / session leader.
        time.sleep(0.15)
        pgid = os.getpgid(proc.pid)
        assert pgid == proc.pid, "child must be its own process-group leader"
        assert _is_alive(proc), "child must be alive after spawn"

        receipt = ProcessCustodyReceipt(
            receipt_id="val-001",
            coordinator_pid=os.getpid(),
            coordinator_host="test-host",
            coordinator_boot_id="boot-abc",
            process_group_id=pgid,
            command=tuple(argv),
            command_hash=cmd_hash,
            receipt_path="process_custody/val-001.json",
            adoption_policy=CUSTODY_ADOPTION_POLICY_ADOPT,
            deterministic_log_path="logs/validation-001.log",
            validation_outcome="passed",
            launched_at="2026-07-29T02:10:00Z",
        )

        # --- exit: job already gone → adopt, outcome preserved -------------
        d_exit = resolve_cutover(receipt, trigger="exit")
        assert d_exit.action == "adopt"
        assert d_exit.preserved_outcome == "passed"
        # applying adopt must NOT kill the live process
        apply_cutover_decision(d_exit, process=proc)
        assert _is_alive(proc), "adopt must not terminate the live process"

        # --- restart with exact match → adopt ------------------------------
        d_restart = resolve_cutover(
            receipt,
            trigger="restart",
            live_command_hash=cmd_hash,
            live_process_group_id=pgid,
        )
        assert d_restart.action == "adopt"
        assert d_restart.preserved_outcome == "passed"
        apply_cutover_decision(d_restart, process=proc)
        assert _is_alive(proc), "adopt (exact match) must not kill"

        # --- signal with policy=terminate → terminate decision -------------
        # (policy on the receipt overrides even an exact match)
        term_receipt = ProcessCustodyReceipt(
            receipt_id="val-002",
            coordinator_pid=os.getpid(),
            coordinator_host="test-host",
            coordinator_boot_id="boot-abc",
            process_group_id=pgid,
            command=tuple(argv),
            command_hash=cmd_hash,
            receipt_path="process_custody/val-002.json",
            adoption_policy=CUSTODY_ADOPTION_POLICY_TERMINATE,
            deterministic_log_path="logs/validation-002.log",
            validation_outcome="failed",
            launched_at="2026-07-29T02:10:00Z",
        )
        d_signal = resolve_cutover(
            term_receipt,
            trigger="signal",
            live_command_hash=cmd_hash,
            live_process_group_id=pgid,
        )
        assert d_signal.action == "terminate"
        assert d_signal.preserved_outcome == "failed"

        # --- timeout with mismatched live job → terminate ------------------
        d_timeout = resolve_cutover(
            receipt,
            trigger="timeout",
            live_command_hash="sha256:deadbeef",
            live_process_group_id=999999,
        )
        assert d_timeout.action == "terminate"
        assert d_timeout.preserved_outcome == "passed", \
            "original outcome must be preserved even on terminate"

        # --- parent_death with no live observation → terminate -------------
        d_parent = resolve_cutover(receipt, trigger="parent_death")
        assert d_parent.action == "terminate"

        # --- runtime cutover with mismatch → terminate ---------------------
        d_cutover = resolve_cutover(
            receipt,
            trigger="cutover",
            live_command_hash=None,
            live_process_group_id=None,
        )
        assert d_cutover.action == "terminate"

        # --- apply terminate: actually kills the recorded process group ----
        apply_cutover_decision(d_cutover, process=proc)
        proc.wait(timeout=10)
        assert not _is_alive(proc), \
            "terminate must reap the recorded process group"

        # --- fail-closed: terminate without a process handle is a no-op ----
        # (cannot signal what you cannot identify)
        ghost_receipt = ProcessCustodyReceipt(
            receipt_id="val-003",
            coordinator_pid=os.getpid(),
            coordinator_host="test-host",
            coordinator_boot_id="boot-abc",
            process_group_id=777777,
            command=("sleep", "1"),
            command_hash=command_hash(("sleep", "1")),
            receipt_path="process_custody/val-003.json",
            adoption_policy=CUSTODY_ADOPTION_POLICY_ADOPT,
            deterministic_log_path="logs/validation-003.log",
            validation_outcome="passed",
            launched_at="2026-07-29T02:10:00Z",
        )
        d_ghost = resolve_cutover(
            ghost_receipt,
            trigger="timeout",
            live_command_hash="sha256:nope",
            live_process_group_id=888888,
        )
        assert d_ghost.action == "terminate"
        # No process handle supplied → must not raise, must not signal
        apply_cutover_decision(d_ghost, process=None)

        # --- unknown trigger is rejected -----------------------------------
        with pytest.raises(ValueError):
            resolve_cutover(receipt, trigger="bogus")

        # --- all declared triggers are exercised ---------------------------
        for trig in CUSTODY_CUTOVER_TRIGGERS:
            resolve_cutover(receipt, trigger=trig)
    finally:
        if _is_alive(proc):
            proc.kill()
            proc.wait(timeout=5)
