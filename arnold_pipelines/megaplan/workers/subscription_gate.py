"""Machine-wide concurrency guard for the shared ``claude`` CLI subscription.

Every Shannon turn drives the local ``claude`` CLI, which is backed by ONE
subscription on the host. When several megaplan chains run on the same box they
all fire Shannon turns concurrently against that single subscription. Once the
subscription is over-subscribed, individual turns get no slot: ``claude`` emits
no tokens and writes nothing to its transcript, so the Shannon liveness probe
(:func:`megaplan.workers.shannon._make_shannon_liveness_probe`) correctly reads
the turn as "not progressing". Starvation is therefore indistinguishable from a
genuine hang, and the phase burns its wall/idle timeout. For non-``execute``
phases (``finalize`` et al.) the driver treats that timeout as a TERMINAL
``phase_timeout`` → ``failed`` (there is no execute-style retry/remediation), so
a transient subscription squeeze hard-fails an entire chain.

This module adds a host-wide counting semaphore so concurrent chains QUEUE for
the shared subscription instead of all starving at once. It is implemented with
``fcntl.flock`` over a fixed pool of slot files under ``~/.megaplan`` — the same
advisory-lock primitive :mod:`megaplan._core.state` already relies on. The
kernel releases an ``flock`` automatically when the holding process exits (even
on crash), so a dead holder never wedges a slot.

Crucially, the wait-to-acquire happens BEFORE a turn starts its ``run_command``
timeout clock, so time spent queueing for the subscription never counts against
the phase wall/idle timeout.

Configuration (env, read fresh on every acquire):

  MEGAPLAN_SHANNON_MAX_CONCURRENT   max concurrent claude turns on this host.
                                    <= 0 (default) DISABLES the gate entirely —
                                    behaviour is then identical to before this
                                    module existed. Set it to the number of
                                    chains the subscription can sustain in
                                    parallel (commonly 1-2).
  MEGAPLAN_SHANNON_SLOT_WAIT_SECONDS  max seconds to wait for a free slot before
                                    giving up (default 3600). On timeout the gate
                                    raises so the turn surfaces as a retryable
                                    external_error rather than silently starving.
  MEGAPLAN_SHANNON_SLOT_DIR         override the slot directory (tests).
"""

from __future__ import annotations

import errno
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

__all__ = [
    "SubscriptionSlotTimeout",
    "max_concurrent",
    "slot_wait_seconds",
    "subscription_slot",
]


class SubscriptionSlotTimeout(RuntimeError):
    """Raised when no subscription slot frees up within the bounded wait."""


def _slot_dir() -> Path:
    override = os.getenv("MEGAPLAN_SHANNON_SLOT_DIR", "").strip()
    if override:
        base = Path(override)
    else:
        base = Path(os.path.expanduser("~")) / ".megaplan" / "shannon-slots"
    return base


def max_concurrent() -> int:
    """Resolve the configured host-wide max concurrent claude turns.

    Returns 0 (gate disabled) for an unset/invalid/non-positive value.
    """
    raw = os.getenv("MEGAPLAN_SHANNON_MAX_CONCURRENT", "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return 0
    return value if value > 0 else 0


def slot_wait_seconds() -> float:
    raw = os.getenv("MEGAPLAN_SHANNON_SLOT_WAIT_SECONDS", "").strip()
    if not raw:
        return 3600.0
    try:
        value = float(raw)
    except ValueError:
        return 3600.0
    return value if value > 0 else 3600.0


def _try_acquire_any_slot(slot_dir: Path, n: int) -> "tuple[int, object] | None":
    """Try each of the *n* slot files once; return (index, open handle) or None.

    The returned handle holds an exclusive ``flock``; closing it (or the owning
    process dying) releases the slot. The caller owns the handle's lifetime.
    """
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
        # Acquired. Stamp the holder pid for operator observability (best-effort).
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
def subscription_slot(
    *,
    poll_interval: float = 1.0,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> Iterator[bool]:
    """Hold one host-wide claude-subscription slot for the duration of the block.

    Yields ``True`` when a real slot is held, ``False`` when the gate is disabled
    (``max_concurrent() <= 0``) and the block runs unguarded.

    Raises :class:`SubscriptionSlotTimeout` if no slot frees up within
    :func:`slot_wait_seconds`. The caller should map that to a retryable
    external_error (NOT a terminal phase failure), since it means the host is
    saturated, not that the work is broken.

    ``sleep``/``monotonic`` are injectable for deterministic tests.
    """
    n = max_concurrent()
    if n <= 0:
        # Gate disabled — preserve pre-gate behaviour exactly.
        yield False
        return

    slot_dir = _slot_dir()
    try:
        slot_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If we cannot even create the slot dir, fail open rather than wedge a
        # turn that would otherwise have run fine.
        yield False
        return

    deadline = monotonic() + slot_wait_seconds()
    acquired: object | None = None
    while True:
        got = _try_acquire_any_slot(slot_dir, n)
        if got is not None:
            _, acquired = got
            break
        if monotonic() >= deadline:
            raise SubscriptionSlotTimeout(
                f"no claude subscription slot freed within "
                f"{slot_wait_seconds():.0f}s (max_concurrent={n}); host is "
                f"saturated by concurrent megaplan chains"
            )
        sleep(poll_interval)

    try:
        yield True
    finally:
        try:
            # Releasing the flock + closing the handle frees the slot.
            fcntl.flock(acquired.fileno(), fcntl.LOCK_UN)  # type: ignore[union-attr]
        except OSError:
            pass
        try:
            acquired.close()  # type: ignore[union-attr]
        except OSError:
            pass
