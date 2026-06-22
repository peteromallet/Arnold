"""Kernel event envelope contracts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from enum import StrEnum
from typing import Any, Mapping, TypeVar, get_args, get_origin, get_type_hints


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
    """Journalable event envelope.

    Events carry the full runtime coordinate needed for replay, quarantine,
    and deterministic reconstruction: sequence, manifest hash, run ID,
    reentry ID, scope stack, artifact root, payload schema hash, idempotency
    key, and replay reference.
    """

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
    sequence: int | None = None
    reentry_id: str | None = None
    scope_stack: tuple[str, ...] = ()
    artifact_root: str | None = None


_T = TypeVar("_T")


def _plain_value(value: Any) -> Any:
    """Convert dataclasses, enums, tuples, and mappings to plain JSON values."""

    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain_value(subvalue) for key, subvalue in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _plain_value(subvalue) for key, subvalue in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value


def canonical_event_json(event: EventEnvelope) -> str:
    """Return the canonical NDJSON line for an event envelope."""

    return json.dumps(
        _plain_value(event),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _decode_dataclass(cls: type[_T], payload: Mapping[str, Any]) -> _T:
    kwargs: dict[str, Any] = {}
    type_hints = get_type_hints(cls)
    for item in fields(cls):
        if item.name not in payload:
            continue
        kwargs[item.name] = _decode_value(type_hints[item.name], payload[item.name])
    return cls(**kwargs)


def _decode_value(annotation: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(annotation)
    args = get_args(annotation)
    if is_dataclass(annotation):
        if not isinstance(value, Mapping):
            raise ValueError(f"expected object for {annotation.__name__}")
        return _decode_dataclass(annotation, value)
    if origin is tuple and args:
        inner = args[0]
        return tuple(_decode_value(inner, item) for item in value)
    if origin is dict or origin is Mapping:
        return dict(value)
    if origin is not None and type(None) in args:
        non_none = [arg for arg in args if arg is not type(None)][0]
        return _decode_value(non_none, value)
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation(value)
    return value


def event_from_json(raw: str | bytes) -> EventEnvelope:
    """Parse an :class:`EventEnvelope` from a canonical NDJSON line."""

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("event JSON must decode to an object")
    return _decode_dataclass(EventEnvelope, payload)


def validate_event_envelope(event: EventEnvelope) -> None:
    """Validate the required runtime coordinate fields on an event."""

    if not event.event_id:
        raise ValueError("event_id is required")
    if not event.kind:
        raise ValueError("kind is required")
    if not event.run_id:
        raise ValueError("run_id is required")
    if not event.payload_schema_hash:
        raise ValueError("payload_schema_hash is required")
    if event.sequence is not None and event.sequence < 0:
        raise ValueError("sequence must be non-negative")
    if not event.manifest.alias or not event.manifest.manifest_hash:
        raise ValueError("manifest alias and manifest_hash are required")


__all__ = [
    "EventEnvelope",
    "EventFamily",
    "ManifestReference",
    "ReplayReference",
    "canonical_event_json",
    "event_from_json",
    "validate_event_envelope",
]
