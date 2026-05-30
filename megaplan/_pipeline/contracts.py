"""Contract Ledger and legal-coercion table (M2 / T4a).

The :class:`ContractLedger` is a content-hashed registry mapping the
canonical-JSON SHA-256 hash of ``(name, kind, content_type, schema,
cardinality)`` to a :class:`~megaplan._pipeline.types.Port`. Taint is
deliberately **excluded** from the contract hash so a tainted variant
of a port resolves to the same contract identity as its clean form.

:data:`legal_coercions` maps a ``(from_content_type, to_content_type)``
pair to a callable performing the coercion. The identity coercion
``(ct, ct) -> lambda x: x`` is registered for every content type seen
by the ledger and is the zero-cost legal move.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

from megaplan._pipeline.types import Port, _canonical_json_dumps


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
