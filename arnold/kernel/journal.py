"""Journal contracts for kernel events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from arnold.kernel.events import EventEnvelope


class EventJournal(Protocol):
    """Minimal append/read journal protocol for later runners."""

    def append(self, event: EventEnvelope) -> None: ...

    def read(self) -> tuple[EventEnvelope, ...]: ...


@dataclass(frozen=True)
class JournalPosition:
    """Stable journal position."""

    journal_uri: str
    sequence: int
