"""Tests for the fenced durable job state machine (Phase 3A fixer unification).

Covers the design invariants from
``docs/runtime-and-fixer-unification-design-20260807.md`` §3 line 136:

- dedupe key = chain UUID + failure fingerprint
- monotonically increasing fencing epoch (an older epoch cannot act)
- exactly one mutator per dedupe key while a holder is live
- stale holders (past TTL / dead PID / foreign boot) are quarantined and
  re-acquired with ``epoch + 1`` — never blindly re-run
- acknowledge-only-after-redrive
- reconcile quarantines dirty attempts on crash and returns them to the
  caller; a paused holder past TTL cannot resume into the newer epoch
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import repair_lock
from arnold_pipelines.megaplan.cloud.repair_lock import (
    acknowledge_job,
    acquire_job_lock,
    advance_job_state,
    job_is_quarantined,
    reconcile_jobs,
)

CHAIN_UUID = "chain-00000000-0000-0000-0000-000000000001"
OTHER_CHAIN_UUID = "chain-00000000-0000-0000-0000-000000000002"
FINGERPRINT = "repair-blocker-fingerprint/v1:abc123"
BOOT_A = "boot-a"
BOOT_B = "boot-b"
T0 = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)


def _lock_dir(tmp_path: Path) -> Path:
    return tmp_path / "job-locks"


def _record_file(tmp_path: Path) -> Path:
    dedupe_key = f"{CHAIN_UUID}:{FINGERPRINT}"
    digest = hashlib.sha256(dedupe_key.encode("utf-8")).hexdigest()
    return _lock_dir(tmp_path) / f"{digest}.json"


def _acquire(
    tmp_path: Path,
    *,
    chain_uuid: str = CHAIN_UUID,
    fingerprint: str = FINGERPRINT,
    boot_id: str = BOOT_A,
    now: datetime = T0,
    ttl_seconds: int = 3600,
) -> repair_lock.JobLockRecord | None:
    return acquire_job_lock(
        chain_uuid,
        fingerprint,
        lock_dir=_lock_dir(tmp_path),
        holder_pid=os.getpid(),
        boot_id=boot_id,
        ttl_seconds=ttl_seconds,
        now=now,
    )


# ── Acquisition: dedupe key, epoch 1, atomic JSON record ──────────────────


def test_acquire_creates_running_record_with_epoch_one(tmp_path: Path) -> None:
    record = _acquire(tmp_path)
    assert record is not None
    assert record.state == "running"
    assert record.epoch == 1
    assert record.attempt == 1
    assert record.chain_uuid == CHAIN_UUID
    assert record.failure_fingerprint == FINGERPRINT
    assert record.holder_pid == os.getpid()
    assert record.holder_boot_id == BOOT_A
    assert record.ttl_seconds == 3600
    assert record.created_at == T0.isoformat()
    assert record.updated_at == T0.isoformat()
    assert record.acknowledged_at is None
    assert not job_is_quarantined(record)

    # The record is persisted as an atomic JSON file named by the dedupe key.
    path = _record_file(tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "job-lock-record/v1"
    assert payload["state"] == "running"
    assert payload["epoch"] == 1
    assert payload["attempt"] == 1


def test_distinct_dedupe_keys_are_independent(tmp_path: Path) -> None:
    first = _acquire(tmp_path)
    second = _acquire(tmp_path, chain_uuid=OTHER_CHAIN_UUID)
    assert first is not None and first.epoch == 1
    assert second is not None and second.epoch == 1
    assert list(_lock_dir(tmp_path).glob("*.json")) != []


def test_acquire_rejects_invalid_parameters(tmp_path: Path) -> None:
    lock_dir = _lock_dir(tmp_path)
    with pytest.raises(ValueError):
        acquire_job_lock("", FINGERPRINT, lock_dir=lock_dir, holder_pid=1, boot_id=BOOT_A)
    with pytest.raises(ValueError):
        acquire_job_lock(CHAIN_UUID, FINGERPRINT, lock_dir=lock_dir, holder_pid=0, boot_id=BOOT_A)
    with pytest.raises(ValueError):
        acquire_job_lock(CHAIN_UUID, FINGERPRINT, lock_dir=lock_dir, holder_pid=1, boot_id="")
    with pytest.raises(ValueError):
        acquire_job_lock(
            CHAIN_UUID, FINGERPRINT, lock_dir=lock_dir,
            holder_pid=1, boot_id=BOOT_A, ttl_seconds=0,
        )


# ── Exactly one mutator per dedupe key ─────────────────────────────────────


def test_second_acquire_while_holder_live_returns_none(tmp_path: Path) -> None:
    first = _acquire(tmp_path)
    assert first is not None
    before = _record_file(tmp_path).read_bytes()

    # Same dedupe key, same boot generation, live holder → None.
    second = _acquire(tmp_path)
    assert second is None

    # The live holder's record is untouched.
    assert _record_file(tmp_path).read_bytes() == before
    payload = json.loads(before.decode("utf-8"))
    assert payload["epoch"] == 1


def test_live_holder_blocks_reacquisition_even_at_higher_ttl_age(
    tmp_path: Path,
) -> None:
    first = _acquire(tmp_path, now=T0)
    assert first is not None
    # Still inside the TTL window (3600s) → still live → no takeover.
    later = _acquire(tmp_path, now=T0 + timedelta(minutes=30))
    assert later is None


# ── Stale holders are quarantined and re-acquired with epoch + 1 ──────────


def test_stale_holder_past_ttl_is_quarantined_and_reacquired(
    tmp_path: Path,
) -> None:
    first = _acquire(tmp_path, now=T0, ttl_seconds=3600)
    assert first is not None and first.epoch == 1

    # Crash reconciliation observes the durable quarantine evidence.
    reconciled = reconcile_jobs(
        _lock_dir(tmp_path), boot_id=BOOT_A, now=T0 + timedelta(hours=2)
    )
    assert len(reconciled) == 1
    assert job_is_quarantined(reconciled[0])
    assert reconciled[0].quarantine_reason == "ttl_expired"
    assert reconciled[0].state == "running"  # state preserved, not reset

    # Re-acquire succeeds with epoch + 1 (the stale holder was not blind-re-run).
    second = _acquire(tmp_path, now=T0 + timedelta(hours=2), ttl_seconds=3600)
    assert second is not None
    assert second.epoch == 2
    assert second.attempt == 2
    assert second.state == "running"
    assert not job_is_quarantined(second)


def test_dead_pid_holder_is_quarantined(tmp_path: Path, monkeypatch) -> None:
    first = _acquire(tmp_path, now=T0)
    assert first is not None

    # The holder process dies.
    monkeypatch.setattr(repair_lock, "_default_is_pid_live", lambda _pid: False)
    reconciled = reconcile_jobs(_lock_dir(tmp_path), boot_id=BOOT_A, now=T0)
    assert len(reconciled) == 1
    assert job_is_quarantined(reconciled[0])
    assert reconciled[0].quarantine_reason == "holder_pid_not_live"

    # A new contender may acquire into epoch + 1.
    second = _acquire(tmp_path, now=T0)
    assert second is not None
    assert second.epoch == 2


def test_boot_generation_mismatch_holder_is_stale(tmp_path: Path) -> None:
    first = _acquire(tmp_path, boot_id=BOOT_A, now=T0)
    assert first is not None

    # A holder from another boot generation cannot block the new boot.
    second = _acquire(tmp_path, boot_id=BOOT_B, now=T0)
    assert second is not None
    assert second.epoch == 2
    assert second.holder_boot_id == BOOT_B


# ── State machine transitions ──────────────────────────────────────────────


def test_legal_transition_chain_running_committing_redriving_done(
    tmp_path: Path,
) -> None:
    record = _acquire(tmp_path)
    assert record is not None and record.state == "running"

    committing = advance_job_state(record, "committing", lock_dir=_lock_dir(tmp_path), now=T0)
    assert committing is not None and committing.state == "committing"

    redriving = advance_job_state(committing, "redriving", lock_dir=_lock_dir(tmp_path), now=T0)
    assert redriving is not None and redriving.state == "redriving"

    done = acknowledge_job(redriving, lock_dir=_lock_dir(tmp_path), now=T0)
    assert done.state == "done"
    assert done.acknowledged_at == T0.isoformat()
    assert not job_is_quarantined(done)

    # Terminal state: nothing may advance a done job.
    assert advance_job_state(done, "committing", lock_dir=_lock_dir(tmp_path), now=T0) is None


def test_advance_can_complete_redriving_to_done(tmp_path: Path) -> None:
    record = _acquire(tmp_path)
    committing = advance_job_state(record, "committing", lock_dir=_lock_dir(tmp_path), now=T0)
    redriving = advance_job_state(committing, "redriving", lock_dir=_lock_dir(tmp_path), now=T0)
    done = advance_job_state(redriving, "done", lock_dir=_lock_dir(tmp_path), now=T0)
    assert done is not None
    assert done.state == "done"


def test_illegal_transitions_are_rejected(tmp_path: Path) -> None:
    record = _acquire(tmp_path)
    assert record is not None

    # running → done jumps committing + redriving → rejected.
    assert advance_job_state(record, "done", lock_dir=_lock_dir(tmp_path), now=T0) is None
    # running → redriving jumps committing → rejected.
    assert advance_job_state(record, "redriving", lock_dir=_lock_dir(tmp_path), now=T0) is None
    # No self-transitions.
    assert advance_job_state(record, "running", lock_dir=_lock_dir(tmp_path), now=T0) is None


def test_stale_epoch_caller_cannot_advance_fencing(tmp_path: Path) -> None:
    old = _acquire(tmp_path, now=T0)
    assert old is not None and old.epoch == 1

    # TTL passes; a new holder re-acquires into epoch 2.
    newer = _acquire(tmp_path, now=T0 + timedelta(hours=2))
    assert newer is not None and newer.epoch == 2

    # The paused old holder (epoch 1) cannot resume into the newer epoch.
    assert (
        advance_job_state(old, "committing", lock_dir=_lock_dir(tmp_path), now=T0 + timedelta(hours=2))
        is None
    )

    # Acknowledgment is fenced the same way: the current record is returned
    # unchanged, so the stale caller observes the newer epoch and no "done".
    observed = acknowledge_job(old, lock_dir=_lock_dir(tmp_path), now=T0 + timedelta(hours=2))
    assert observed.epoch == 2
    assert observed.state != "done"
    assert observed.acknowledged_at is None


def test_quarantined_record_cannot_advance_or_acknowledge(tmp_path: Path) -> None:
    record = _acquire(tmp_path, boot_id=BOOT_A, now=T0)
    assert record is not None

    # Foreign-boot reconciliation quarantines the holder.
    quarantined = reconcile_jobs(_lock_dir(tmp_path), boot_id=BOOT_B, now=T0)
    assert len(quarantined) == 1
    assert job_is_quarantined(quarantined[0])

    assert (
        advance_job_state(quarantined[0], "committing", lock_dir=_lock_dir(tmp_path), now=T0)
        is None
    )
    observed = acknowledge_job(quarantined[0], lock_dir=_lock_dir(tmp_path), now=T0)
    assert observed.state == "running"
    assert job_is_quarantined(observed)


# ── Acknowledge-after-redrive ──────────────────────────────────────────────


def test_acknowledge_rejected_unless_redriving(tmp_path: Path) -> None:
    running = _acquire(tmp_path)
    assert running is not None

    rejected_running = acknowledge_job(running, lock_dir=_lock_dir(tmp_path), now=T0)
    assert rejected_running.state == "running"
    assert rejected_running.acknowledged_at is None

    committing = advance_job_state(running, "committing", lock_dir=_lock_dir(tmp_path), now=T0)
    assert committing is not None
    rejected_committing = acknowledge_job(committing, lock_dir=_lock_dir(tmp_path), now=T0)
    assert rejected_committing.state == "committing"
    assert rejected_committing.acknowledged_at is None


def test_done_job_reacquired_starts_new_epoch(tmp_path: Path) -> None:
    record = _acquire(tmp_path)
    committing = advance_job_state(record, "committing", lock_dir=_lock_dir(tmp_path), now=T0)
    redriving = advance_job_state(committing, "redriving", lock_dir=_lock_dir(tmp_path), now=T0)
    done = acknowledge_job(redriving, lock_dir=_lock_dir(tmp_path), now=T0)
    assert done.state == "done"

    # A recurring failure of the same fingerprint starts a fresh attempt.
    again = _acquire(tmp_path, now=T0 + timedelta(hours=1))
    assert again is not None
    assert again.epoch == 2
    assert again.attempt == 2
    assert again.state == "running"
    assert not job_is_quarantined(again)


# ── Crash reconciliation ───────────────────────────────────────────────────


def test_reconcile_quarantines_dead_and_boot_mismatched_holders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    same_boot = _acquire(tmp_path, now=T0)
    foreign_boot = _acquire(
        tmp_path, chain_uuid=OTHER_CHAIN_UUID, boot_id=BOOT_B, now=T0
    )
    assert same_boot is not None and foreign_boot is not None

    # Same-boot holder dies; foreign-boot holder comes from another generation.
    monkeypatch.setattr(repair_lock, "_default_is_pid_live", lambda _pid: False)
    records = reconcile_jobs(_lock_dir(tmp_path), boot_id=BOOT_A, now=T0)
    by_key = {r.chain_uuid: r for r in records}
    assert set(by_key) == {CHAIN_UUID, OTHER_CHAIN_UUID}

    assert job_is_quarantined(by_key[CHAIN_UUID])
    assert by_key[CHAIN_UUID].quarantine_reason == "holder_pid_not_live"
    assert job_is_quarantined(by_key[OTHER_CHAIN_UUID])
    assert by_key[OTHER_CHAIN_UUID].quarantine_reason == "boot_id_mismatch"


def test_reconcile_returns_live_records_unmodified(tmp_path: Path) -> None:
    record = _acquire(tmp_path, now=T0)
    assert record is not None

    records = reconcile_jobs(_lock_dir(tmp_path), boot_id=BOOT_A, now=T0)
    assert len(records) == 1
    assert not job_is_quarantined(records[0])
    assert records[0].epoch == 1
    assert records[0].state == "running"

    # A completed (done) job is terminal — reconciliation never quarantines it,
    # even far past TTL.
    committing = advance_job_state(record, "committing", lock_dir=_lock_dir(tmp_path), now=T0)
    redriving = advance_job_state(committing, "redriving", lock_dir=_lock_dir(tmp_path), now=T0)
    done = acknowledge_job(redriving, lock_dir=_lock_dir(tmp_path), now=T0)
    assert done.state == "done"

    after = reconcile_jobs(_lock_dir(tmp_path), boot_id=BOOT_A, now=T0 + timedelta(days=7))
    assert len(after) == 1
    assert after[0].state == "done"
    assert not job_is_quarantined(after[0])


def test_reconcile_marks_ttl_expired_dirty_attempts_quarantined(
    tmp_path: Path,
) -> None:
    record = _acquire(tmp_path, now=T0, ttl_seconds=60)
    assert record is not None
    committing = advance_job_state(record, "committing", lock_dir=_lock_dir(tmp_path), now=T0)
    assert committing is not None

    # A crash leaves the attempt in "committing"; past TTL the reconciler
    # quarantines it instead of re-running it.
    records = reconcile_jobs(
        _lock_dir(tmp_path), boot_id=BOOT_A, now=T0 + timedelta(minutes=5)
    )
    assert len(records) == 1
    assert records[0].state == "committing"
    assert job_is_quarantined(records[0])
    assert records[0].quarantine_reason == "ttl_expired"
