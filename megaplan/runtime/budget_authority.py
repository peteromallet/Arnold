"""M4 T20 — BudgetAuthority: cross-process budget ledger over CapacityLease.

A ``BudgetAuthority`` accumulates external-act spend keyed by
``(lease_id, fencing_token)`` so that duplicate charges (replay,
retry-after-crash, double-acknowledged dispatch) cannot double-count.
The persistent backend is an ``fcntl.flock``'d JSON ledger living in the
same directory as the M3 :mod:`megaplan.runtime.capacity_lease` lockfiles
so the two substrates share locking discipline.

Schema (per-tenant ledger file ``<base>/<tenant>.budget.json``):

    {
      "total_usd": float,                       # running total
      "seen": {"<lease_id>:<fencing_token>": float},  # idempotency
      "sub_budget_usd": float | null            # M4 schema-only reservation
    }

The ``sub_budget_usd`` field is reserved for a per-tenant cap at M5; this
milestone writes ``null`` and never reads it.

Single-process fallback
-----------------------
When constructed with ``flock=False`` the authority keeps its state in
memory.  ``install`` accepts a ``state_total`` seed which is loaded as the
initial ``total_usd`` so that reads via :meth:`current_total` are
byte-identical to the legacy ``state['meta']['total_cost_usd']`` path
when no new charges have arrived.

CostTracker reconciliation
--------------------------
:class:`megaplan._pipeline.runtime.CostTracker` keeps its public
``should_abort(state)`` signature.  Under ``UNIFIED_BUDGET=1`` it consults
the installed authority's :meth:`current_total` and ignores
``state['meta']['total_cost_usd']``.  In the single-process fallback the
two readings are equal at install time, so the legacy byte-identical
behaviour is preserved.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


def default_authority_dir() -> Path:
    return Path(os.path.expanduser("~/.megaplan/leases"))


def _budget_path(base_dir: Path, tenant: str) -> Path:
    return base_dir / f"{tenant}.budget.json"


def _ledger_key(lease_id: str, fencing_token: int) -> str:
    return f"{lease_id}:{int(fencing_token)}"


# ---------------------------------------------------------------------------
# Authority
# ---------------------------------------------------------------------------


@dataclass
class BudgetAuthority:
    """Process-shared budget ledger.

    Construct via :func:`install`; consumers should never instantiate
    directly because the install path is also where the single-process
    fallback is seeded from ``state['meta']['total_cost_usd']``.
    """

    tenant: str
    flock: bool
    base_dir: Path
    _total: float = 0.0
    _seen: Dict[str, float] = field(default_factory=dict)
    _sub_budget: Optional[float] = None
    _inproc_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # -- public reads --------------------------------------------------------

    def current_total(self) -> float:
        if self.flock:
            data = self._read_ledger()
            return float(data.get("total_usd", 0.0))
        with self._inproc_lock:
            return float(self._total)

    # -- charge --------------------------------------------------------------

    def charge(self, *, lease_id: str, fencing_token: int, amount_usd: float) -> float:
        """Apply a charge keyed by ``(lease_id, fencing_token)``.

        Returns the new running total.  Duplicate calls with the same key
        are no-ops — this is the seam where double-counting is prevented.
        """

        if not lease_id:
            raise ValueError("lease_id is required")
        amount = float(amount_usd)
        key = _ledger_key(lease_id, fencing_token)

        if self.flock:
            return self._charge_flock(key, amount)
        with self._inproc_lock:
            if key in self._seen:
                return self._total
            self._seen[key] = amount
            self._total += amount
            return self._total

    # -- flock backend -------------------------------------------------------

    def _charge_flock(self, key: str, amount: float) -> float:
        import fcntl

        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.base_dir / f"{self.tenant}.budget.lock"
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            data = self._read_ledger()
            seen = data.setdefault("seen", {})
            if key in seen:
                return float(data.get("total_usd", 0.0))
            seen[key] = amount
            new_total = float(data.get("total_usd", 0.0)) + amount
            data["total_usd"] = new_total
            data.setdefault("sub_budget_usd", self._sub_budget)
            self._write_ledger(data)
            return new_total
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def _read_ledger(self) -> dict:
        path = _budget_path(self.base_dir, self.tenant)
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {"total_usd": float(self._total), "seen": {}, "sub_budget_usd": self._sub_budget}

    def _write_ledger(self, data: dict) -> None:
        path = _budget_path(self.base_dir, self.tenant)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Install / accessor
# ---------------------------------------------------------------------------


_installed: Optional[BudgetAuthority] = None
_installed_lock = threading.Lock()


def install(
    tenant: str = "default",
    *,
    state_total: float = 0.0,
    flock: bool = False,
    base_dir: Optional[Path] = None,
) -> BudgetAuthority:
    """Install the process-wide BudgetAuthority and seed its total.

    ``state_total`` is the legacy ``state['meta']['total_cost_usd']``
    value at install time.  In the single-process fallback it becomes
    the authority's initial total so that ``current_total()`` reads are
    byte-identical to the legacy state read.
    """

    base = (base_dir or default_authority_dir()).resolve()
    auth = BudgetAuthority(
        tenant=tenant,
        flock=flock,
        base_dir=base,
        _total=float(state_total or 0.0),
    )
    global _installed
    with _installed_lock:
        _installed = auth
    return auth


def current_authority() -> Optional[BudgetAuthority]:
    with _installed_lock:
        return _installed


def uninstall() -> None:
    """Test hook — clear the installed authority."""

    global _installed
    with _installed_lock:
        _installed = None
