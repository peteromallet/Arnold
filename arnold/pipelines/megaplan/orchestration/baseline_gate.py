"""Machine-wide concurrency guard for the finalize test-baseline suite run.

Every ``finalize`` phase captures a regression baseline by running the project's
full pytest suite. When several megaplan chains hit ``finalize`` on the same box
at once they fire that full suite concurrently, saturating host CPU. Every
chain's other work is then starved, finalize phases burn their timeout and retry,
re-running baselines, and the box spirals into a contention loop.

This module uses a host-wide counting semaphore implemented with ``fcntl.flock``
over a fixed pool of slot files under ``~/.megaplan`` so concurrent chains QUEUE
for a baseline slot instead of all running the suite at once. The kernel releases
an ``flock`` automatically when the holding process exits (even on crash), so a
dead holder never wedges a slot.

Configuration (env, read fresh on every acquire):

  MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT  max concurrent baseline suite runs on
                                    this host. Unset/invalid -> 1 (serialize).
                                    <= 0 DISABLES the gate.
  MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS  max seconds to wait for a free slot
                                    before degrading gracefully. Default 1800.
  MEGAPLAN_TEST_BASELINE_SLOT_DIR   override the slot directory (tests).
"""

from __future__ import annotations

import errno
import fcntl
import os
import time
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Iterator

__all__ = [
    "BaselineSlot",
    "baseline_max_concurrent",
    "baseline_slot_wait_seconds",
    "baseline_slot",
]


class BaselineSlot(Enum):
    """What the caller should do, yielded by :func:`baseline_slot`."""

    #: The gate is disabled (max_concurrent <= 0); run the suite unguarded.
    DISABLED = "disabled"
    #: A real host-wide slot is held; run the suite, release on block exit.
    HELD = "held"
    #: No slot freed within the bounded wait — DEGRADE: skip the baseline and
    #: proceed "baseline unavailable" (do NOT run the suite, do NOT hang).
    DEGRADED = "degraded"

    @property
    def should_run(self) -> bool:
        """True when the caller should actually run the baseline suite."""
        return self is not BaselineSlot.DEGRADED


def _slot_dir() -> Path:
    override = os.getenv("MEGAPLAN_TEST_BASELINE_SLOT_DIR", "").strip()
    if override:
        return Path(override)
    return Path(os.path.expanduser("~")) / ".megaplan" / "baseline-slots"


def baseline_max_concurrent() -> int:
    """Resolve the host-wide max concurrent baseline suite runs.

    An unset or invalid value resolves to 1 (serialize). A value <= 0
    explicitly DISABLES the gate (run unguarded).
    """
    raw = os.getenv("MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT", "").strip()
    if not raw:
        return 1
    try:
        value = int(raw)
    except ValueError:
        return 1
    return value


def baseline_slot_wait_seconds() -> float:
    raw = os.getenv("MEGAPLAN_TEST_BASELINE_SLOT_WAIT_SECONDS", "").strip()
    if not raw:
        return 1800.0
    try:
        value = float(raw)
    except ValueError:
        return 1800.0
    return value if value > 0 else 1800.0


def _try_acquire_any_slot(slot_dir: Path, n: int) -> "tuple[int, object] | None":
    """Try each of the *n* slot files once; return (index, open handle) or None."""
    for index in range(n):
        slot_path = slot_dir / f"slot-{index}.lock"
        try:
            handle = slot_path.open("a+", encoding="utf-8")
        except OSError:
            continue
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                continue
            continue
        # Stamp the holder pid for operator observability (best-effort).
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(f"{os.getpid()}\n")
            handle.flush()
        except OSError:
            pass
        return index, handle
    return None


@contextmanager
def baseline_slot(
    *,
    poll_interval: float = 1.0,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> Iterator[BaselineSlot]:
    """Hold one host-wide baseline-suite slot for the duration of the block.

    Yields a :class:`BaselineSlot`:

      * ``DISABLED`` — gate off; run unguarded.
      * ``HELD`` — a real slot is held; run the suite. Released on block exit.
      * ``DEGRADED`` — no slot freed within the wait; the caller must SKIP
        the baseline and proceed "baseline unavailable" without running the suite.

    A wait-timeout here NEVER raises — re-queuing a full-suite run is the
    contention we're avoiding.
    """
    n = baseline_max_concurrent()
    if n <= 0:
        yield BaselineSlot.DISABLED
        return

    slot_dir = _slot_dir()
    try:
        slot_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Can't create slot dir — fail open rather than wedge a baseline.
        yield BaselineSlot.DISABLED
        return

    deadline = monotonic() + baseline_slot_wait_seconds()
    acquired: object | None = None
    while True:
        got = _try_acquire_any_slot(slot_dir, n)
        if got is not None:
            _, acquired = got
            break
        if monotonic() >= deadline:
            yield BaselineSlot.DEGRADED
            return
        sleep(poll_interval)

    try:
        yield BaselineSlot.HELD
    finally:
        try:
            fcntl.flock(acquired.fileno(), fcntl.LOCK_UN)  # type: ignore[union-attr]
        except OSError:
            pass
        try:
            acquired.close()  # type: ignore[union-attr]
        except OSError:
            pass
