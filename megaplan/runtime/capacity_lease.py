"""Per-tenant capacity lease with a monotonic fencing token.

A ``CapacityLease`` serialises acquisitions for a tenant via an
``fcntl.flock`` on ``~/.megaplan/leases/<tenant>.lock``.  Each acquisition
reads + bumps the tenant's persisted ``last_token`` (stored alongside the
lockfile as ``<tenant>.state.json``) and hands the holder an integer
``fencing_token`` strictly greater than any previously issued token for that
tenant.  The lock is held for the lifetime of the lease.

If a second writer *steals* the lease (the holder's flock was lost — e.g. the
process crashed, the file was unlinked, or a forced re-acquire occurred) the
state file's ``last_token`` advances past the original holder's token.  The
next call to :meth:`CapacityLease.write` on the stale holder consults the
persisted ``last_token`` and refuses the write with
:class:`StaleLeaseError` when ``self.fencing_token < state.last_token``.

An in-process fallback path (``flock=False``) replaces the file lock and the
state file with a module-level ``threading.Lock`` + in-memory ``dict`` and is
behaviourally equivalent on a single-process, multi-thread workload.

Tokens are integer monotonic so wall-clock skew between hosts does not affect
ordering.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


class StaleLeaseError(RuntimeError):
    """Raised by ``CapacityLease.write`` when the holder's fencing token
    is older than the tenant's last-issued token (i.e. the lease was
    stolen or the holder is out of date)."""

    def __init__(self, tenant: str, holder_token: int, last_token: int) -> None:
        self.tenant = tenant
        self.holder_token = holder_token
        self.last_token = last_token
        super().__init__(
            f"stale lease for tenant {tenant!r}: holder token "
            f"{holder_token} < last-issued {last_token}"
        )


def default_lease_dir() -> Path:
    return Path(os.path.expanduser("~/.megaplan/leases"))


# ---------------------------------------------------------------------------
# In-process fallback state.
# ---------------------------------------------------------------------------

_inproc_lock = threading.Lock()
_inproc_tokens: Dict[str, int] = {}
_inproc_held: Dict[str, threading.Lock] = {}


def _inproc_tenant_lock(tenant: str) -> threading.Lock:
    with _inproc_lock:
        lock = _inproc_held.get(tenant)
        if lock is None:
            lock = threading.Lock()
            _inproc_held[tenant] = lock
        return lock


def _reset_inproc_state_for_tests() -> None:
    """Test hook — wipes the in-process fallback registry."""

    with _inproc_lock:
        _inproc_tokens.clear()
        _inproc_held.clear()


# ---------------------------------------------------------------------------
# Lease.
# ---------------------------------------------------------------------------


@dataclass
class CapacityLease:
    """An acquired lease.  Construct via :func:`acquire`."""

    tenant: str
    fencing_token: int
    flock: bool
    base_dir: Path
    _fd: Optional[int] = field(default=None, repr=False)
    _inproc_tenant_lock: Optional[threading.Lock] = field(default=None, repr=False)
    _released: bool = field(default=False, repr=False)
    _writes: list = field(default_factory=list, repr=False)

    # -- write -------------------------------------------------------------

    def write(self, payload: Any) -> None:
        """Append ``payload`` to the lease's local write log.

        Raises :class:`StaleLeaseError` when the persisted ``last_token``
        for this tenant is greater than this holder's ``fencing_token``
        (i.e. the lease was stolen)."""

        last = self._read_last_token()
        if self.fencing_token < last:
            raise StaleLeaseError(self.tenant, self.fencing_token, last)
        self._writes.append(payload)

    # -- release / context-manager ----------------------------------------

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            if self.flock and self._fd is not None:
                import fcntl

                try:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                finally:
                    os.close(self._fd)
                    self._fd = None
            elif self._inproc_tenant_lock is not None:
                try:
                    self._inproc_tenant_lock.release()
                except RuntimeError:
                    pass
                self._inproc_tenant_lock = None
        except Exception:
            pass

    def __enter__(self) -> "CapacityLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.release()
        except Exception:
            pass

    # -- internals --------------------------------------------------------

    def _read_last_token(self) -> int:
        if self.flock:
            return _read_state_token(self.base_dir, self.tenant)
        with _inproc_lock:
            return _inproc_tokens.get(self.tenant, 0)


# ---------------------------------------------------------------------------
# Persistence helpers (flock path).
# ---------------------------------------------------------------------------


def _state_path(base_dir: Path, tenant: str) -> Path:
    return base_dir / f"{tenant}.state.json"


def _lock_path(base_dir: Path, tenant: str) -> Path:
    return base_dir / f"{tenant}.lock"


def _read_state_token(base_dir: Path, tenant: str) -> int:
    path = _state_path(base_dir, tenant)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return int(data.get("last_token", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def _write_state_token(base_dir: Path, tenant: str, token: int) -> None:
    path = _state_path(base_dir, tenant)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump({"last_token": int(token)}, fh)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Acquire.
# ---------------------------------------------------------------------------


def acquire(
    tenant: str,
    *,
    flock: bool = True,
    base_dir: Optional[Path] = None,
    blocking: bool = True,
) -> CapacityLease:
    """Acquire the capacity lease for ``tenant``.

    If ``flock=True`` (default) takes a linearizable ``fcntl.flock`` on
    ``<base_dir>/<tenant>.lock`` and persists the monotonic token to
    ``<base_dir>/<tenant>.state.json``.  ``base_dir`` defaults to
    ``~/.megaplan/leases``.

    If ``flock=False`` uses the in-process fallback (single-process,
    multi-thread).

    With ``blocking=False`` raises :class:`BlockingIOError` if the lease is
    currently held by someone else (flock path only)."""

    if not tenant:
        raise ValueError("tenant must be non-empty")
    base = (base_dir or default_lease_dir()).resolve()

    if flock:
        import fcntl

        base.mkdir(parents=True, exist_ok=True)
        fd = os.open(_lock_path(base, tenant), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
            fcntl.flock(fd, flags)
        except BlockingIOError:
            os.close(fd)
            raise
        except Exception:
            os.close(fd)
            raise

        try:
            last = _read_state_token(base, tenant)
            token = last + 1
            _write_state_token(base, tenant, token)
        except Exception:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            raise

        return CapacityLease(
            tenant=tenant,
            fencing_token=token,
            flock=True,
            base_dir=base,
            _fd=fd,
        )

    # in-process fallback
    tenant_lock = _inproc_tenant_lock(tenant)
    acquired = tenant_lock.acquire(blocking=blocking)
    if not acquired:
        raise BlockingIOError(f"in-process lease for {tenant!r} is held")
    with _inproc_lock:
        last = _inproc_tokens.get(tenant, 0)
        token = last + 1
        _inproc_tokens[tenant] = token
    return CapacityLease(
        tenant=tenant,
        fencing_token=token,
        flock=False,
        base_dir=base,
        _inproc_tenant_lock=tenant_lock,
    )


def force_steal(
    tenant: str,
    *,
    flock: bool = True,
    base_dir: Optional[Path] = None,
) -> CapacityLease:
    """Forcibly bump the tenant's ``last_token`` and return a fresh lease,
    invalidating any prior holder's next ``write`` (test-shaped helper that
    mirrors what happens when the original holder's process dies and a new
    actor reacquires)."""

    base = (base_dir or default_lease_dir()).resolve()
    if flock:
        base.mkdir(parents=True, exist_ok=True)
        last = _read_state_token(base, tenant)
        token = last + 1
        _write_state_token(base, tenant, token)
        # No flock — the test scenario explicitly simulates a stolen
        # lease where the original fd is still open elsewhere.
        return CapacityLease(
            tenant=tenant,
            fencing_token=token,
            flock=True,
            base_dir=base,
            _fd=None,
        )

    with _inproc_lock:
        last = _inproc_tokens.get(tenant, 0)
        token = last + 1
        _inproc_tokens[tenant] = token
    return CapacityLease(
        tenant=tenant,
        fencing_token=token,
        flock=False,
        base_dir=base,
        _inproc_tenant_lock=None,
    )
