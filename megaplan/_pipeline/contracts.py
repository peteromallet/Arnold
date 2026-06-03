"""Contract Ledger, legal-coercion table, and topology-aware port binding.

The contract-ledger half (ContractLedger, legal_coercions, is_legal_coercion,
coerce) has been relocated to :mod:`arnold.pipeline.contracts` in M3a.
This module re-exports those symbols as a compatibility bridge and retains
the Megaplan-specific :func:`bind` topology-resolution machinery.

M3a compatibility bridge; delete re-exports in M7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

from megaplan._pipeline.types import ParallelStage, Port, PortRef, Stage


# ── bind() — topology-aware port resolution (M2 / T4b) ────────────────


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(
                min(
                    cur[-1] + 1,
                    prev[j] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            )
        prev = cur
    return prev[-1]


class PortBindError(RuntimeError):
    """Raised when typed-port runtime binding cannot resolve a consume.

    Carries ``(step_id, consume_name)`` and an optional ``detail`` string
    for diagnostics. The flag-OFF code path (``typed_ports_on() is
    False``) never raises this; the legacy ``v1.md`` fallback remains in
    place there.
    """

    def __init__(
        self,
        step_id: str,
        consume_name: str,
        detail: str = "",
    ) -> None:
        self.step_id = step_id
        self.consume_name = consume_name
        self.detail = detail
        msg = f"PortBindError: step {step_id!r} consume {consume_name!r}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


@dataclass(frozen=True)
class BindResult:
    """Successful binding output of :func:`bind`."""

    binding_map: dict


@dataclass(frozen=True)
class RepairGradient:
    """Structured failure output of :func:`bind`.

    ``error_kind`` is one of ``no_match`` / ``typo_name`` /
    ``content_type_mismatch`` / ``schema_mismatch`` /
    ``cardinality_mismatch``. ``wanted`` is the unresolved consume; the
    ``candidates`` are the visible upstream produces, and
    ``suggested_moves`` are Levenshtein-2 typo suggestions when
    ``error_kind == "typo_name"``.
    """

    error_kind: str
    wanted: Any
    candidates: tuple
    suggested_moves: tuple = ()


def _stage_produces(stage):
    if stage.produces:
        return stage.produces
    if isinstance(stage, ParallelStage):
        return ()
    step = getattr(stage, "step", None)
    if step is None:
        return ()
    return tuple(getattr(step, "produces", ()) or ())


def _stage_consumes(stage):
    if stage.consumes:
        return stage.consumes
    if isinstance(stage, ParallelStage):
        return ()
    step = getattr(stage, "step", None)
    if step is None:
        return ()
    return tuple(getattr(step, "consumes", ()) or ())


def _topo_sort(stages, edges_by_src):
    """Kahn's algorithm. Returns order; falls back to insertion order on cycles."""
    indeg: dict[str, int] = {n: 0 for n in stages}
    for src, targets in edges_by_src.items():
        for t in targets:
            if t in indeg:
                indeg[t] += 1
    queue = [n for n, d in indeg.items() if d == 0]
    order: list[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for t in edges_by_src.get(n, ()):
            if t in indeg:
                indeg[t] -= 1
                if indeg[t] == 0:
                    queue.append(t)
    if len(order) != len(stages):
        # Cycle: append remaining in declaration order.
        for n in stages:
            if n not in order:
                order.append(n)
    return order


def bind(steps, edges):
    """Resolve typed-port consumes against upstream produces.

    ``steps`` is a ``Mapping[str, Stage | ParallelStage]`` (i.e. a
    ``Pipeline.stages``).  ``edges`` is either a ``Mapping[str,
    Iterable[str]]`` of src→targets or any iterable of
    ``(src_id, target_id)`` pairs.

    Returns :class:`BindResult` on success, :class:`RepairGradient` on
    the first unresolved consume.
    """
    edges_by_src: dict[str, list[str]] = {}
    if hasattr(edges, "items"):
        for src, targets in edges.items():
            edges_by_src.setdefault(src, []).extend(list(targets))
    else:
        for src, target in edges:
            edges_by_src.setdefault(src, []).append(target)

    order = _topo_sort(steps, edges_by_src)
    rank = {name: i for i, name in enumerate(order)}

    binding_map: dict = {}
    for step_id in order:
        stage = steps[step_id]
        consumes = _stage_consumes(stage)
        if not consumes:
            continue
        for consume in consumes:
            wanted_name = getattr(consume, "port_name", getattr(consume, "name", ""))
            wanted_ct = getattr(consume, "content_type", "")
            upstream_candidates: list[tuple[str, Any]] = []
            for upstream_id, upstream_stage in steps.items():
                if upstream_id == step_id:
                    continue
                if rank.get(upstream_id, -1) >= rank.get(step_id, 0):
                    continue
                for port in _stage_produces(upstream_stage):
                    upstream_candidates.append((upstream_id, port))

            name_matches = [
                (uid, p) for uid, p in upstream_candidates if p.name == wanted_name
            ]
            if not name_matches:
                visible_names = tuple(sorted({p.name for _, p in upstream_candidates}))
                close = tuple(
                    n for n in visible_names if _levenshtein(n, wanted_name) <= 2
                )
                if close:
                    return RepairGradient(
                        error_kind="typo_name",
                        wanted=consume,
                        candidates=tuple(upstream_candidates),
                        suggested_moves=close,
                    )
                return RepairGradient(
                    error_kind="no_match",
                    wanted=consume,
                    candidates=tuple(upstream_candidates),
                )

            ct_matches = [
                (uid, p)
                for uid, p in name_matches
                if p.content_type == wanted_ct
                or is_legal_coercion(p.content_type, wanted_ct)
            ]
            if not ct_matches:
                return RepairGradient(
                    error_kind="content_type_mismatch",
                    wanted=consume,
                    candidates=tuple(name_matches),
                )

            # Prefer the nearest upstream (highest rank < current).
            ct_matches.sort(key=lambda pair: rank.get(pair[0], -1), reverse=True)
            chosen_id, chosen_port = ct_matches[0]
            binding_map[(step_id, wanted_name)] = (chosen_id, chosen_port.name)

    return BindResult(binding_map=binding_map)
