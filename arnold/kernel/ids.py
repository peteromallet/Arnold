"""Neutral kernel identity contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class RunId:
    """Stable run identifier supplied by execution."""

    value: str


@dataclass(frozen=True, order=True)
class ReentryId:
    """Stable identifier for resuming from a suspension point."""

    value: str


def derive_pipeline_identity(alias: str, manifest_hash: str) -> str:
    """Derive the canonical runtime pipeline identity."""

    return _sha256_text(f"workflow:{alias}@{manifest_hash}")


def derive_idempotency_key(*parts: str) -> str:
    """Derive a deterministic idempotency key from ordered string parts."""

    if not parts or any(part == "" for part in parts):
        raise ValueError("idempotency key parts must be non-empty")
    return _sha256_text("\x1f".join(parts))
