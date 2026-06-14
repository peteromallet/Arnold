"""Tests for megaplan.runtime.capacity_lease.

Covers the five oracles called out in the plan:

* two-tenant — independent leases, no cross-tenant interference
* fork-bomb  — many concurrent acquires serialise + tokens are monotonic
               and never double-issued
* clock-skew — tokens are integer monotonic, indifferent to wall-clock
* stolen lease — a forced re-acquire bumps the persisted last_token; the
                 original holder's next write raises StaleLeaseError
* in-process fallback parity — the flock=False path matches the flock=True
                               path on a deterministic workload
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.runtime import capacity_lease as cl
from arnold.pipelines.megaplan.runtime.capacity_lease import (
    CapacityLease,
    StaleLeaseError,
    acquire,
    force_steal,
)


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    d = tmp_path / "leases"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _reset_inproc():
    cl._reset_inproc_state_for_tests()
    yield
    cl._reset_inproc_state_for_tests()


# ---------------------------------------------------------------------------
# Two-tenant.
# ---------------------------------------------------------------------------


def test_two_tenants_independent_no_double_issue(base_dir: Path) -> None:
    a1 = acquire("tenant-A", base_dir=base_dir)
    b1 = acquire("tenant-B", base_dir=base_dir)
    assert a1.fencing_token == 1
    assert b1.fencing_token == 1
    a1.release()
    b1.release()

    a2 = acquire("tenant-A", base_dir=base_dir)
    b2 = acquire("tenant-B", base_dir=base_dir)
    assert a2.fencing_token == 2
    assert b2.fencing_token == 2
    a2.release()
    b2.release()


def test_two_tenant_lock_files_distinct(base_dir: Path) -> None:
    with acquire("tenant-A", base_dir=base_dir):
        with acquire("tenant-B", base_dir=base_dir):
            assert (base_dir / "tenant-A.lock").exists()
            assert (base_dir / "tenant-B.lock").exists()


# ---------------------------------------------------------------------------
# Fork-bomb — many concurrent acquires.
# ---------------------------------------------------------------------------


def _child_acquire(args):
    base_dir, tenant = args
    lease = acquire(tenant, base_dir=Path(base_dir))
    token = lease.fencing_token
    lease.release()
    return token


def test_fork_bomb_no_double_issue_no_skip(base_dir: Path) -> None:
    """N concurrent processes each acquire+release.  Tokens must be a
    contiguous 1..N permutation — no duplicates, no skips."""

    n = 16
    ctx = mp.get_context("spawn")  # macOS: fork-after-threads deadlocks the green suite
    with ctx.Pool(processes=4) as pool:
        tokens = pool.map(_child_acquire, [(str(base_dir), "fork-bomb")] * n)

    assert sorted(tokens) == list(range(1, n + 1))


def test_concurrent_threads_serialise_via_flock(base_dir: Path) -> None:
    tokens: list = []
    lock = threading.Lock()

    def worker():
        lease = acquire("threads", base_dir=base_dir)
        with lock:
            tokens.append(lease.fencing_token)
        lease.release()

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(tokens) == list(range(1, 21))


# ---------------------------------------------------------------------------
# Clock skew.
# ---------------------------------------------------------------------------


def test_clock_skew_does_not_affect_tokens(base_dir: Path, monkeypatch) -> None:
    """Tokens are integer monotonic — they don't read the wall clock, so a
    skewed/non-monotonic clock cannot reorder them or collide them."""

    fake_times = iter([1_000_000.0, 0.0, 500_000.0, -1.0, 999.0])
    monkeypatch.setattr(time, "time", lambda: next(fake_times))

    seen = []
    for _ in range(5):
        with acquire("skew", base_dir=base_dir) as lease:
            seen.append(lease.fencing_token)
    assert seen == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Stolen lease.
# ---------------------------------------------------------------------------


def test_stolen_lease_fails_next_write_with_stale_error(base_dir: Path) -> None:
    original = acquire("steal", base_dir=base_dir)
    assert original.fencing_token == 1

    # First write is fine — last_token == self.fencing_token.
    original.write({"ok": True})

    # Simulate a stolen lease: another actor forcibly re-acquires.
    stolen = force_steal("steal", base_dir=base_dir)
    assert stolen.fencing_token == 2

    # The original holder's NEXT write must now fail loudly.
    with pytest.raises(StaleLeaseError) as exc_info:
        original.write({"too": "late"})
    assert exc_info.value.tenant == "steal"
    assert exc_info.value.holder_token == 1
    assert exc_info.value.last_token == 2

    # The new (fresh) lease can write.
    stolen.write({"ok": True})

    original.release()
    stolen.release()


def test_stolen_lease_persists_in_state_file(base_dir: Path) -> None:
    lease = acquire("persist", base_dir=base_dir)
    lease.release()
    force_steal("persist", base_dir=base_dir).release()

    data = json.loads((base_dir / "persist.state.json").read_text())
    assert data == {"last_token": 2}


def test_stolen_lease_inproc_fallback_also_raises(base_dir: Path) -> None:
    original = acquire("steal-inp", flock=False, base_dir=base_dir)
    original.write("ok")
    # Bump the in-proc registry without going through the held lock so we
    # can simulate the steal end-to-end.
    with cl._inproc_lock:
        cl._inproc_tokens["steal-inp"] = original.fencing_token + 5

    with pytest.raises(StaleLeaseError):
        original.write("nope")
    original.release()


# ---------------------------------------------------------------------------
# In-process fallback parity.
# ---------------------------------------------------------------------------


def _run_workload(*, flock: bool, base_dir: Path, tenant: str, n: int) -> list:
    tokens = []
    for _ in range(n):
        with acquire(tenant, flock=flock, base_dir=base_dir) as lease:
            tokens.append(lease.fencing_token)
            lease.write({"iter": lease.fencing_token})
    return tokens


def test_inproc_fallback_parity_with_flock(base_dir: Path) -> None:
    flock_tokens = _run_workload(
        flock=True, base_dir=base_dir, tenant="parity-flock", n=8
    )
    inproc_tokens = _run_workload(
        flock=False, base_dir=base_dir, tenant="parity-inproc", n=8
    )
    assert flock_tokens == inproc_tokens == list(range(1, 9))


def test_inproc_fallback_write_succeeds_when_token_current(base_dir: Path) -> None:
    with acquire("ok-inp", flock=False, base_dir=base_dir) as lease:
        lease.write("a")
        lease.write("b")
        assert lease._writes == ["a", "b"]


def test_inproc_fallback_blocks_second_acquire_nonblocking(base_dir: Path) -> None:
    held = acquire("busy", flock=False, base_dir=base_dir)
    with pytest.raises(BlockingIOError):
        acquire("busy", flock=False, base_dir=base_dir, blocking=False)
    held.release()
    # Now reacquirable.
    with acquire("busy", flock=False, base_dir=base_dir) as relock:
        assert relock.fencing_token == 2


def test_flock_blocks_second_acquire_nonblocking(base_dir: Path) -> None:
    held = acquire("flock-busy", base_dir=base_dir)
    with pytest.raises(BlockingIOError):
        acquire("flock-busy", base_dir=base_dir, blocking=False)
    held.release()
    with acquire("flock-busy", base_dir=base_dir, blocking=False) as relock:
        assert relock.fencing_token == 2


# ---------------------------------------------------------------------------
# Misc invariants.
# ---------------------------------------------------------------------------


def test_empty_tenant_rejected(base_dir: Path) -> None:
    with pytest.raises(ValueError):
        acquire("", base_dir=base_dir)


def test_release_idempotent(base_dir: Path) -> None:
    lease = acquire("rel", base_dir=base_dir)
    lease.release()
    lease.release()  # second call must not raise


def test_context_manager_releases(base_dir: Path) -> None:
    with acquire("ctx", base_dir=base_dir) as lease:
        token = lease.fencing_token
    # Re-acquire should work and bump.
    with acquire("ctx", base_dir=base_dir) as lease2:
        assert lease2.fencing_token == token + 1
