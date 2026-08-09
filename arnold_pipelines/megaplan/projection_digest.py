"""Deterministic projection digesting and ordered rebuild helpers.

Projection loss must be recoverable by deterministic replay.  This module
provides the primitives that make every M9 projection byte-stable and
content-addressed: given the same authoritative source records plus immutable
evidence, deleting and rebuilding a projection produces identical ordered
views and identical digests.

Design rules
------------
* Every digest is sha256 over sorted, canonical JSON — no iteration-order
  variance, no timestamp/nonce inclusion, no ambient state.
* Rebuild helpers sort keys, deduplicate, and normalize so the same input
  always yields the same output regardless of code path.
* Delete/rebuild parity is the *only* acceptable behaviour; drift is a bug.
* All digests are explicitly non-authoritative evidence identifiers, not grants.

Covered projections
-------------------
- status (lifecycle display projection)
- resident (resident context/snapshot projection)
- cloud (cloud status/auditor projection)
- introspection (introspect payload projection)
- repair (repair-facing projection)
- work-ledger (work-ledger aggregate projection)
- observer-purity (observer-purity test fixtures)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

# ── Canonical JSON (deterministic serialisation) ───────────────────────────


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, no indentation variance, UTF-8."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def canonical_json_pretty(obj: Any) -> bytes:
    """Deterministic pretty-printed JSON bytes: sorted keys, fixed indent=2."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")


# ── Digest primitives ─────────────────────────────────────────────────────


def projection_digest(*parts: str) -> str:
    """Content-addressed digest for one or more canonical JSON payloads.

    Each *part* is expected to be a canonical JSON string (from
    :func:`canonical_json` decoded back to str, or a pre-normalized string).
    Parts are joined with ``\\x00`` before hashing so ``("a","bc")`` and
    ``("ab","c")`` cannot collide.
    """
    raw = "\x00".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def projection_digest_from_dicts(*dicts: Mapping[str, Any]) -> str:
    """Convenience: digest of one or more dicts serialized deterministically."""
    parts = [canonical_json(d).decode("utf-8") for d in dicts]
    return projection_digest(*parts)


def digest_hex(digest: str) -> str:
    """Normalize a digest to the ``sha256:<hex>`` form."""
    if digest.startswith("sha256:"):
        return digest
    return f"sha256:{digest}"


# ── Ordered rebuild helpers ───────────────────────────────────────────────


def sort_payload_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sort all dict keys in a payload for deterministic output.

    Lists are preserved as-is (order is structural).  This ensures that two
    payloads with the same data but different insertion order produce the
    same canonical JSON and the same digest.
    """
    result: Dict[str, Any] = {}
    for key in sorted(payload):
        value = payload[key]
        if isinstance(value, dict):
            result[key] = sort_payload_keys(value)
        elif isinstance(value, list):
            result[key] = [
                sort_payload_keys(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def normalize_list_of_dicts(items: Sequence[Mapping[str, Any]], sort_by: str = "id") -> List[Dict[str, Any]]:
    """Sort and normalize a list of dicts for deterministic rebuild.

    Each item is key-sorted, and the list is ordered by *sort_by*.
    """
    normalized = [sort_payload_keys(dict(item)) for item in items]
    normalized.sort(key=lambda d: str(d.get(sort_by, "")))
    return normalized


def deduplicate_by_key(items: Sequence[Mapping[str, Any]], key: str) -> List[Dict[str, Any]]:
    """Deduplicate a sequence of dicts by *key*, keeping first occurrence."""
    seen: set[str] = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        val = str(item.get(key, ""))
        if val not in seen:
            seen.add(val)
            result.append(dict(item))
    return result


# ── Projection digest record ──────────────────────────────────────────────


@dataclass(frozen=True)
class ProjectionDigest:
    """A content-addressed digest for a single projection view.

    Carries the projection kind, the digest of the canonical payload,
    the source cursor vector digest that was used to build it, and
    the non-authoritative marker.
    """

    kind: str
    """Projection kind: status, resident, cloud, introspection, repair, work_ledger, observer_purity."""

    payload_digest: str
    """sha256 digest of the canonical JSON payload (sha256:<hex>)."""

    source_cursor_digest: str
    """sha256 digest of the SourceCursorVector used to build this projection."""

    evidence_ids: Tuple[str, ...] = ()
    """Content-addressed evidence IDs that contributed to this projection."""

    _non_authoritative: bool = field(default=True, init=False)
    """Always True — digests are evidence identifiers, never authority."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "payload_digest": self.payload_digest,
            "source_cursor_digest": self.source_cursor_digest,
            "evidence_ids": list(self.evidence_ids),
            "_non_authoritative": self._non_authoritative,
        }

    @property
    def composite_digest(self) -> str:
        """A single digest covering kind + payload + cursor + evidence."""
        parts = [
            self.kind,
            self.payload_digest,
            self.source_cursor_digest,
            *sorted(self.evidence_ids),
        ]
        return digest_hex(projection_digest(*parts))


# ── Rebuild parity fixtures ───────────────────────────────────────────────


@dataclass(frozen=True)
class RebuildParity:
    """Delete/rebuild parity evidence for a set of projections.

    Proves that deleting and rebuilding every projection from authoritative
    source records + immutable evidence produces identical ordered views and
    identical digests.
    """

    projections: Tuple[ProjectionDigest, ...]
    """All projection digests in deterministic order (sorted by kind)."""

    rebuild_digest: str = field(init=False)
    """Aggregate digest of all projection digests (content-addressed)."""

    _non_authoritative: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        sorted_projections = tuple(
            sorted(self.projections, key=lambda p: p.kind)
        )
        object.__setattr__(self, "projections", sorted_projections)
        parts = [p.composite_digest for p in sorted_projections]
        object.__setattr__(
            self,
            "rebuild_digest",
            digest_hex(projection_digest(*parts)),
        )
        object.__setattr__(self, "_non_authoritative", True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "projections": [p.to_dict() for p in self.projections],
            "rebuild_digest": self.rebuild_digest,
            "_non_authoritative": self._non_authoritative,
        }

    @classmethod
    def from_projection_dicts(
        cls,
        *,
        status_payload: Optional[Dict[str, Any]] = None,
        resident_payload: Optional[Dict[str, Any]] = None,
        cloud_payload: Optional[Dict[str, Any]] = None,
        introspection_payload: Optional[Dict[str, Any]] = None,
        repair_payload: Optional[Dict[str, Any]] = None,
        work_ledger_payload: Optional[Dict[str, Any]] = None,
        source_cursor_digest: str = "",
        evidence_ids: Sequence[str] = (),
    ) -> "RebuildParity":
        """Build rebuild parity from projection payloads.

        Each payload is canonically serialized and digested independently.
        Payloads that are None are skipped (they were not rebuilt).
        """
        projections: List[ProjectionDigest] = []
        kind_payloads = [
            ("status", status_payload),
            ("resident", resident_payload),
            ("cloud", cloud_payload),
            ("introspection", introspection_payload),
            ("repair", repair_payload),
            ("work_ledger", work_ledger_payload),
        ]
        for kind, payload in kind_payloads:
            if payload is None:
                continue
            sorted_payload = sort_payload_keys(payload)
            payload_digest = digest_hex(
                projection_digest(canonical_json(sorted_payload).decode("utf-8"))
            )
            projections.append(
                ProjectionDigest(
                    kind=kind,
                    payload_digest=payload_digest,
                    source_cursor_digest=source_cursor_digest,
                    evidence_ids=tuple(sorted(evidence_ids)),
                )
            )
        return cls(projections=tuple(projections))

    def verify_parity(self, other: "RebuildParity") -> bool:
        """True when two rebuilds produce identical digests."""
        return self.rebuild_digest == other.rebuild_digest


# ── Convenience: digest a projection view directly ────────────────────────


def digest_projection(kind: str, payload: Dict[str, Any], *, source_cursor_digest: str = "", evidence_ids: Sequence[str] = ()) -> ProjectionDigest:
    """Create a ProjectionDigest from a projection payload."""
    sorted_payload = sort_payload_keys(payload)
    payload_digest = digest_hex(
        projection_digest(canonical_json(sorted_payload).decode("utf-8"))
    )
    return ProjectionDigest(
        kind=kind,
        payload_digest=payload_digest,
        source_cursor_digest=source_cursor_digest,
        evidence_ids=tuple(sorted(evidence_ids)),
    )


# ── Delete helpers (non-destructive — produce "deleted" markers) ─────────


def deleted_projection_digest(kind: str) -> ProjectionDigest:
    """Return a sentinel ProjectionDigest for a deleted projection.

    This is a content-addressed proof that a projection was explicitly
    deleted, not merely absent.  Consumers can use this to distinguish
    "never built" from "deleted, rebuild expected".
    """
    marker_payload = {
        "kind": kind,
        "status": "deleted",
        "_non_authoritative": True,
    }
    return digest_projection(kind, marker_payload)


__all__ = [
    # ── Canonical serialisation ──
    "canonical_json",
    "canonical_json_pretty",
    # ── Digest primitives ──
    "projection_digest",
    "projection_digest_from_dicts",
    "digest_hex",
    # ── Ordered rebuild helpers ──
    "sort_payload_keys",
    "normalize_list_of_dicts",
    "deduplicate_by_key",
    # ── Projection digest records ──
    "ProjectionDigest",
    "RebuildParity",
    # ── Convenience ──
    "digest_projection",
    "deleted_projection_digest",
]
