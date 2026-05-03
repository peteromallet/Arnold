"""Invocation-mode result envelope for Arnold turns.

The stable JSON helpers in this module are the only supported serialization
path for envelopes and streamed events. ``serialize_for_diff`` is narrower:
it exists only for CLI-vs-Python envelope equivalence tests and must not be
used for stream-vs-envelope comparisons.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import json
from typing import Any, Literal


Outcome = Literal["completed", "blocked_on_caller", "errored", "aborted"]
EventKind = Literal["tool_call", "activity", "attached_image", "turn_start", "turn_end"]


@dataclass(frozen=True)
class EnvelopeError:
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class StateDelta:
    body_diff: str = ""
    checklist_changes: list[dict[str, Any]] = field(default_factory=list)
    sprint_changes: list[dict[str, Any]] = field(default_factory=list)
    state_transition: dict[str, Any] | None = None


@dataclass(frozen=True)
class Event:
    ts: str
    kind: EventKind
    name: str | None = None
    text: str | None = None
    ms: int | None = None
    tool_call_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Envelope:
    turn_id: str
    epic_state_before: str
    epic_state_after: str
    reply: str
    epic_id: str | None = None
    state_delta: StateDelta = field(default_factory=StateDelta)
    questions: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    tool_call_count: int = 0
    outcome: Outcome = "completed"
    error: EnvelopeError | None = None
    envelope_version: str = "1"
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(_to_plain(self))

    def to_json(self) -> str:
        return stable_json_dumps(self.to_dict())


def stable_json_dumps(value: Any) -> str:
    """Serialize JSON with byte-stable ordering and compact separators."""

    return json.dumps(
        _drop_none(_to_plain(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def event_to_json(event: Event) -> str:
    return stable_json_dumps(event)


def serialize_for_diff(envelope: Envelope | dict[str, Any]) -> str:
    """Return a byte-stable comparison form for CLI-vs-Python tests only.

    This strips the non-deterministic fields called out by the Subagent
    Contract: envelope ``reply``, event ``text``, and ``started_at`` /
    ``completed_at`` timestamps wherever they appear. Streaming tests must
    compare real events, not this projection.
    """

    data = _drop_none(_to_plain(envelope))
    return stable_json_dumps(_strip_diff_nondeterminism(data))


def _to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_to_plain(item) for item in value]
    return value


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _drop_none(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


def _strip_diff_nondeterminism(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_diff_nondeterminism(item)
            for key, item in value.items()
            if key not in {"reply", "text", "ms", "started_at", "completed_at"}
        }
    if isinstance(value, list):
        return [_strip_diff_nondeterminism(item) for item in value]
    return value
