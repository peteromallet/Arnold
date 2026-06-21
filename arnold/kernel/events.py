"""Kernel event envelope contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class EventFamily(StrEnum):
    """Neutral event families emitted by later execution."""

    CONTROL_TRANSITION = "control-transition"
    EFFECT = "effect"
    SUSPENSION = "suspension"
    ARTIFACT = "artifact"
    NODE_LIFECYCLE = "node-lifecycle"


@dataclass(frozen=True)
class ManifestReference:
    """Original manifest reference carried on every event."""

    alias: str
    manifest_hash: str
    uri: str | None = None


@dataclass(frozen=True)
class ReplayReference:
    """Replay coordinate for event comparison or quarantine."""

    journal_uri: str | None = None
    sequence: int | None = None
    cursor: str | None = None


@dataclass(frozen=True)
class EventEnvelope:
    """Journalable event envelope."""

    event_id: str
    family: EventFamily
    kind: str
    manifest: ManifestReference
    run_id: str
    payload_schema_hash: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    occurred_at: str | None = None
    replay: ReplayReference | None = None
