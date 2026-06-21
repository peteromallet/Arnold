"""Replay resolution and quarantine contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReplayDecision(StrEnum):
    """Possible replay resolver outcomes."""

    REUSE = "reuse"
    RECOMPUTE = "recompute"
    ALIAS = "alias"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class ReplayResolution:
    """Decision returned by a replay resolver."""

    decision: ReplayDecision
    reason: str
    alias_manifest_hash: str | None = None


@dataclass(frozen=True)
class QuarantineRecord:
    """Operator-visible replay quarantine record."""

    run_id: str
    original_manifest_hash: str
    observed_manifest_hash: str
    reason: str
