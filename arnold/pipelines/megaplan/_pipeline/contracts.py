"""Contract Ledger, legal-coercion table, and topology-aware port binding.

The contract-ledger half (ContractLedger, legal_coercions, is_legal_coercion,
coerce) has been relocated to :mod:`arnold.pipeline.contracts` in M3a.
This module re-exports those symbols as a compatibility bridge and retains
the Megaplan-specific :func:`bind` topology-resolution machinery.

The bind logic itself now lives in :mod:`arnold.pipeline.contracts` (M3c T2);
this module provides a shim that delegates to the Arnold bind.

M3a compatibility bridge; delete re-exports in M7.
"""

from __future__ import annotations

# ── M3a bridge re-exports from Arnold ──────────────────────────────────
# M3a compatibility bridge; delete in M7
from arnold.pipeline.contracts import (  # noqa: F401  # re-export
    ContractLedger,
    _contract_hash,
    _identity_coercion,
    coerce,
    is_legal_coercion,
    legal_coercions,
)

# ── M3c T2 bridge — bind delegates to Arnold ───────────────────────────

from arnold.pipeline.contracts import (  # noqa: F401  # re-export
    BindResult,
    PortBindError,
    RepairGradient,
    bind as _arnold_bind,
)


def bind(steps, edges):
    """Resolve typed-port consumes against upstream produces.

    Shim that delegates to :func:`arnold.pipeline.contracts.bind`
    with ``typed_ports=True`` (always — the original megaplan bind
    never gated on the typed-ports flag).

    ``steps`` is a ``Mapping[str, Stage | ParallelStage]`` (i.e. a
    ``Pipeline.stages``).  ``edges`` is either a ``Mapping[str,
    Iterable[str]]`` of src→targets or any iterable of
    ``(src_id, target_id)`` pairs.

    Returns :class:`BindResult` on success, :class:`RepairGradient` on
    the first unresolved consume.
    """
    return _arnold_bind(steps, edges, typed_ports=True)
