"""Contract Ledger, legal-coercion table, and topology-aware port binding.

The :class:`ContractLedger` is a content-hashed registry mapping the
canonical-JSON SHA-256 hash of ``(name, kind, content_type, schema,
cardinality)`` to a :class:`~arnold.pipeline.types.Port`. Taint is
deliberately **excluded** from the contract hash so a tainted variant
of a port resolves to the same contract identity as its clean form.

:data:`legal_coercions` maps a ``(from_content_type, to_content_type)``
pair to a callable performing the coercion. The identity coercion
``(ct, ct) -> lambda x: x`` is registered for every content type seen
by the ledger and is the zero-cost legal move.

Bind infrastructure: :func:`bind` resolves typed-port consumes against
upstream produces.  Accepts an explicit ``typed_ports`` option instead
of consulting megaplan flags — the consuming megaplan shim wires the
flag read before delegating here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from arnold.pipeline.types import Port, _canonical_json_dumps


def _contract_hash(
    name: str,
    kind: str,
    content_type: str,
    schema: Any,
    cardinality: str,
) -> str:
    payload = {
        "name": name,
        "kind": kind,
        "content_type": content_type,
        "schema": schema,
        "cardinality": cardinality,
    }
    raw = _canonical_json_dumps(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class ContractLedger:
    """Content-hashed registry of :class:`Port` contracts.

    ``register(...)`` returns the contract hash. ``lookup(hash)`` returns
    the registered :class:`Port`, or raises ``KeyError``.
    """

    _by_hash: dict[str, Port] = field(default_factory=dict)

    def register(
        self,
        *,
        name: str,
        kind: str,
        content_type: str,
        schema: Any,
        cardinality: str = "one",
    ) -> str:
        digest = _contract_hash(name, kind, content_type, schema, cardinality)
        port = Port(name=name, content_type=content_type)
        self._by_hash.setdefault(digest, port)
        legal_coercions.setdefault(
            (content_type, content_type), _identity_coercion
        )
        return digest

    def lookup(self, digest: str) -> Port:
        if digest not in self._by_hash:
            raise KeyError(f"no contract registered with hash {digest!r}")
        return self._by_hash[digest]

    def __contains__(self, digest: str) -> bool:
        return digest in self._by_hash


def _identity_coercion(value: Any) -> Any:
    return value


# Seeded empty; identity coercions are added lazily by ContractLedger.register
# but identity is treated as the zero-cost legal move whenever from == to.
legal_coercions: dict[tuple[str, str], Callable[[Any], Any]] = {}


def is_legal_coercion(from_ct: str, to_ct: str) -> bool:
    """Return True iff a coercion is registered (identity is always legal)."""
    if from_ct == to_ct:
        return True
    return (from_ct, to_ct) in legal_coercions


def coerce(from_ct: str, to_ct: str, value: Any) -> Any:
    """Apply the registered coercion. Raises ``KeyError`` when illegal."""
    if from_ct == to_ct:
        return value
    if (from_ct, to_ct) not in legal_coercions:
        raise KeyError(f"no legal coercion from {from_ct!r} to {to_ct!r}")
    return legal_coercions[(from_ct, to_ct)](value)


# ── bind() — topology-aware port resolution ────────────────────────────────


class PortBindError(RuntimeError):
    """Raised when typed-port runtime binding cannot resolve a consume.

    Carries ``(step_id, consume_name)`` and an optional ``detail`` string
    for diagnostics. The ``typed_ports=False`` code path never raises this;
    the legacy fallback remains in place there.
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


def _stage_produces(stage: Any) -> tuple:
    """Duck-typed: return produces from stage or its step."""
    produces = getattr(stage, "produces", None)
    if produces:
        return tuple(produces)
    # ParallelStage has no step attribute; bail.
    step = getattr(stage, "step", None)
    if step is None:
        return ()
    step_produces = getattr(step, "produces", None)
    if step_produces:
        return tuple(step_produces)
    return ()


def _stage_consumes(stage: Any) -> tuple:
    """Duck-typed: return consumes from stage or its step."""
    consumes = getattr(stage, "consumes", None)
    if consumes:
        return tuple(consumes)
    step = getattr(stage, "step", None)
    if step is None:
        return ()
    step_consumes = getattr(step, "consumes", None)
    if step_consumes:
        return tuple(step_consumes)
    return ()


def _topo_sort(stages: Mapping[str, Any], edges_by_src: dict[str, list[str]]) -> list[str]:
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


def bind(
    steps: Mapping[str, Any],
    edges: Mapping[str, Iterable[str]] | Iterable[tuple[str, str]],
    *,
    typed_ports: bool = True,
) -> BindResult | RepairGradient:
    """Resolve typed-port consumes against upstream produces.

    ``steps`` is a ``Mapping[str, Stage | ParallelStage]`` (i.e. a
    ``Pipeline.stages``).  ``edges`` is either a ``Mapping[str,
    Iterable[str]]`` of src→targets or any iterable of
    ``(src_id, target_id)`` pairs.

    ``typed_ports`` controls whether the binder enforces full typed-port
    matching. When ``False`` the function short-circuits to an empty
    binding map (the megaplan shim switches this based on the runtime
    flag).

    Returns :class:`BindResult` on success, :class:`RepairGradient` on
    the first unresolved consume.
    """
    if not typed_ports:
        return BindResult(binding_map={})

    edges_by_src: dict[str, list[str]] = {}
    if hasattr(edges, "items"):
        for src, targets in edges.items():  # type: ignore[union-attr]
            edges_by_src.setdefault(src, []).extend(list(targets))
    else:
        for src, target in edges:  # type: ignore[union-attr]
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
                (uid, p) for uid, p in upstream_candidates
                if getattr(p, "name", "") == wanted_name
            ]
            if not name_matches:
                visible_names = tuple(sorted({getattr(p, "name", "") for _, p in upstream_candidates}))
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
                if getattr(p, "content_type", "") == wanted_ct
                or is_legal_coercion(getattr(p, "content_type", ""), wanted_ct)
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
            binding_map[(step_id, wanted_name)] = (chosen_id, getattr(chosen_port, "name", ""))

    return BindResult(binding_map=binding_map)
