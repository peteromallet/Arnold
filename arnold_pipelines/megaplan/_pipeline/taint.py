"""Taint-in-hash (R3) helpers for typed-port value identity.

``port_value_hash`` mixes the port's *taint* set into the value's content
hash so that byte-identical payloads carrying different taints are
non-interchangeable.  ``propagate_taint`` produces *new* :class:`Port`
instances whose taint is the union of the producer's existing taint and
every consumed port's taint.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any, Iterable

from arnold_pipelines.megaplan._pipeline.types import Port, PortRef


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_value(value: Any) -> str:
    """Return a deterministic canonical string for *value*.

    For JSON-serialisable values this is canonical JSON; for anything
    else we fall back to ``repr`` so the helper never raises (but
    callers should pass canonicalisable inputs).
    """
    try:
        return _canonical_json(value)
    except TypeError:
        return repr(value)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def port_value_hash(port: Port, value: Any) -> str:
    """SHA-256 of ``{content_hash, taint}`` — taint is part of identity."""
    payload = {
        "content_hash": _sha256(canonical_value(value)),
        "taint": sorted(port.taint),
    }
    return _sha256(_canonical_json(payload))


def _join_taint(consumes: Iterable[Any]) -> frozenset[str]:
    out: set[str] = set()
    for c in consumes:
        t = getattr(c, "taint", None)
        if t:
            out.update(t)
    return frozenset(out)


def propagate_taint(
    produces: Iterable[Port],
    consumes: Iterable[PortRef],
) -> tuple[Port, ...]:
    """Return NEW Port instances whose taint ∪= union of consumed taints."""
    extra = _join_taint(consumes)
    return tuple(
        dataclasses.replace(p, taint=frozenset(p.taint) | extra) for p in produces
    )
