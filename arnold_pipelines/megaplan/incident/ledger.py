"""Incident ledger append wrapper for the canonical M1 event stream."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.runtime.event_journal import NdjsonEventJournal

from arnold_pipelines.megaplan.incident.schema import validate_incident_event

_INCIDENT_LEDGER_DIR = Path(".megaplan") / "incident-ledger"
_EVENTS_FILE = "events.jsonl"


class _IncidentEventJournal(NdjsonEventJournal):
    """Reuse runtime journal locking/seq semantics with the M1 filename."""

    def __init__(self, artifact_root: Path) -> None:
        super().__init__(artifact_root)
        self._ndjson_path = self._root / _EVENTS_FILE


class IncidentLedger:
    """Append-only incident ledger rooted at ``<root>/.megaplan/incident-ledger``."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path.cwd() if root is None else Path(root)
        self._ledger_dir = self._root / _INCIDENT_LEDGER_DIR
        self._journal = _IncidentEventJournal(self._ledger_dir)

    @property
    def ledger_dir(self) -> Path:
        return self._ledger_dir

    @property
    def events_path(self) -> Path:
        return self._ledger_dir / _EVENTS_FILE

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Redact, validate, and append one incident event to the canonical ledger."""
        payload = validate_incident_event(event)
        return self._journal.emit(
            f"incident.{payload['type']}",
            payload=payload,
        )


__all__ = [
    "IncidentLedger",
]
