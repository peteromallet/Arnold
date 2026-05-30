"""M4 T23 — EvaluandRecord: versioned verify/judge record.

The verify/judge surface writes a versioned :class:`EvaluandRecord`
into the one Ledger, using the Step 7b R5 join key (``run_id``) — never
a bare float — so a downstream reader can answer "what did we score?"
without recomputation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class EvaluandRecord:
    """A versioned verify/judge result.

    Fields
    ------
    judge_version:
        Opaque version string of the judge that produced ``score``.
    rubric_version:
        Opaque version string of the rubric being applied.
    input_set_hash:
        Content hash of the input set scored.  Lets the no-recompute read
        confirm a stored record applies to the asked-about input set.
    score:
        The numeric score itself (never written naked — always inside a
        full record).
    recorded_at:
        Wall-clock epoch seconds at write time.
    """

    judge_version: str
    rubric_version: str
    input_set_hash: str
    score: float
    recorded_at: float = field(default_factory=time.time)


# In-process Ledger for the verify/judge surface.  Keyed by the R5 join
# key (``run_id``) so the read surface can no-recompute lookup by run.
_LEDGER: Dict[str, EvaluandRecord] = {}


def write_evaluand(run_id: str, record: EvaluandRecord) -> None:
    """Write the versioned record into the one Ledger.

    Raises ``TypeError`` if ``record`` is a bare float — the schema
    invariant the M4 brief locks.
    """
    if not isinstance(record, EvaluandRecord):
        raise TypeError(
            "evaluand write requires a versioned EvaluandRecord, "
            f"not a bare {type(record).__name__}"
        )
    if not run_id:
        raise ValueError("run_id is required for the R5 join key")
    _LEDGER[run_id] = record


def read_evaluand(run_id: str) -> Optional[EvaluandRecord]:
    """No-recompute read: return the stored record for ``run_id`` if any."""
    return _LEDGER.get(run_id)


def _reset_for_tests() -> None:
    _LEDGER.clear()


# ---------------------------------------------------------------------------
# T24 — Evaluand transaction boundary
# ---------------------------------------------------------------------------

import contextlib
from typing import Iterator, Optional

# Receipts written within an active boundary; cleared on commit, discarded
# on rollback so the {state, receipt, ledger} triple flips atomically.
_PENDING_RECEIPTS: list[tuple[str, EvaluandRecord]] = []


def stage_receipt(run_id: str, record: EvaluandRecord) -> None:
    """Stage a receipt to be committed at the end of the active
    evaluand transaction boundary. Outside a boundary, writes through
    immediately to preserve legacy single-call semantics."""
    if not _IN_BOUNDARY:
        write_evaluand(run_id, record)
        return
    _PENDING_RECEIPTS.append((run_id, record))


_IN_BOUNDARY: bool = False


@contextlib.contextmanager
def _evaluand_transaction_boundary(
    envelope: object | None = None,
    *,
    store: object | None = None,
) -> Iterator[None]:
    """T24 — open a transactional boundary around state-merge + receipt
    write. On clean exit, staged receipts commit and the optional
    Store.transaction commits. On exception, staged receipts are
    discarded and the Store rolls back.
    """
    global _IN_BOUNDARY
    epic_id: Optional[str] = None
    if envelope is not None:
        epic_id = getattr(envelope, "epic_id", None)

    prev = _IN_BOUNDARY
    _IN_BOUNDARY = True
    staged_before = len(_PENDING_RECEIPTS)
    if store is not None:
        cm = store.transaction(epic_id=epic_id)
    else:
        cm = contextlib.nullcontext()
    try:
        with cm:
            yield
            # Commit: flush staged receipts into the ledger.
            for run_id, record in _PENDING_RECEIPTS[staged_before:]:
                _LEDGER[run_id] = record
            del _PENDING_RECEIPTS[staged_before:]
    except BaseException:
        # Rollback: discard staged receipts; Store transaction rolls back
        # via its own __exit__.
        del _PENDING_RECEIPTS[staged_before:]
        raise
    finally:
        _IN_BOUNDARY = prev


__all__ = [
    "EvaluandRecord",
    "write_evaluand",
    "read_evaluand",
    "stage_receipt",
]
