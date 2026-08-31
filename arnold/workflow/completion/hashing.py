"""Canonical content hashing for the completion kernel.

This module implements deterministic canonical JSON serialization and
content-addressed SHA-256 hashing.  The algorithm is a deliberate
reimplementation of ``acceptance_transaction.py``'s internal helpers:

* ``_canonical_json_kwargs`` → :func:`canonical_json`
* ``_sha256_hex`` → :func:`hash_canonical`

The duplication is required by the neutral-package import boundary
(:mod:`arnold.workflow` and its descendants must not import from
``arnold_pipelines.megaplan``).  Extraction into a shared library is
tracked as a C2 / S2R candidate.

Output format
-------------
All hashes use the ``sha256:`` prefix convention:

    sha256:<64-hex-digits>

This matches the format produced by ``acceptance_transaction._sha256_hex``,
which is consumed by acceptance receipts in ``ChainState.completed`` records.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Canonical JSON serialization
# ---------------------------------------------------------------------------

#: Keyword arguments for deterministic, compact JSON serialization.
#: ``sort_keys=True`` guarantees stable key ordering across Python versions
#: and platforms; the no-whitespace separators produce the same byte stream
#: for equivalent semantic content.
_CANONICAL_JSON_KWARGS: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
}


def canonical_json(obj: Any) -> bytes:
    """Serialize *obj* to canonical (sorted-key, compact) JSON bytes.

    Parameters
    ----------
    obj:
        Any JSON-serializable Python object.

    Returns
    -------
    bytes
        UTF-8 encoded canonical JSON.

    Notes
    -----
    This is a deliberate reimplementation of
    ``acceptance_transaction._canonical_json_bytes`` with identical kwargs.
    """
    return json.dumps(obj, **_CANONICAL_JSON_KWARGS).encode("utf-8")


# ---------------------------------------------------------------------------
# Content hashing
# ---------------------------------------------------------------------------


def hash_canonical(obj: Any) -> str:
    """Return the ``sha256:``-prefixed SHA-256 digest of *obj*'s canonical JSON.

    Parameters
    ----------
    obj:
        Any JSON-serializable Python object.

    Returns
    -------
    str
        ``sha256:`` followed by the 64-character hex digest (e.g.
        ``sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855``).

    Notes
    -----
    This is a deliberate reimplementation of
    ``acceptance_transaction._sha256_hex(canonical_json_bytes(obj))`` and
    produces identical output for the same input.
    """
    return "sha256:" + hashlib.sha256(canonical_json(obj)).hexdigest()


# ---------------------------------------------------------------------------
# Content-addressed store path helper
# ---------------------------------------------------------------------------


def content_addressed_store_path(base_dir: str | Path, digest: str) -> Path:
    """Return a content-addressed file path for *digest* under *base_dir*.

    The path follows a two-level sharding scheme: the first two characters
    of the hex digest form the first directory level, the ``sha256:`` prefix
    is stripped, and the remaining hex digest forms the filename.

    For ``sha256:e3b0c44298fc…`` the result is ``base_dir / "e3" / "e3b0c44298fc…"``.

    Parameters
    ----------
    base_dir:
        Root directory for the content-addressed store.
    digest:
        ``sha256:``-prefixed digest string as returned by :func:`hash_canonical`.

    Returns
    -------
    Path
        A ``Path`` under *base_dir* suitable for writing or reading the
        content-addressed blob.
    """
    base = Path(base_dir)
    if not digest.startswith("sha256:"):
        raise ValueError(f"Digest must start with 'sha256:', got {digest!r}")
    hex_part = digest[len("sha256:"):]
    shard = hex_part[:2]
    return base / shard / hex_part