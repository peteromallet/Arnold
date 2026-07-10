"""Megaplan-specific authority contracts and shadow projections."""

from .batch_scope import (
    BATCH_SCOPE_KEY,
    BATCH_SCOPE_SCHEMA_VERSION,
    BatchScope,
    BatchScopeQuarantine,
    BatchScopeResolution,
    resolve_batch_scope,
)

__all__ = [
    "BATCH_SCOPE_KEY",
    "BATCH_SCOPE_SCHEMA_VERSION",
    "BatchScope",
    "BatchScopeQuarantine",
    "BatchScopeResolution",
    "resolve_batch_scope",
]
