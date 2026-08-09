"""Incident ledger append wrapper for the canonical M1 event stream."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable

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

    def append_authorized_lifecycle_event(
        self,
        *,
        occurrence_id: str,
        transition: str,
        owner: str,
        grant_id: str,
        custody_epoch: int,
        run_authority_check: Callable[[str, str], bool],
        custody_check: Callable[[str, int, str], bool],
        session_id: str = "",
    ) -> dict[str, Any]:
        """Append an acknowledged/resolved event after live authority rereads.

        The notification store intentionally has no lifecycle writer. This
        method is the canonical incident-owned writer: the current Run
        Authority and Custody sources validate the owner/grant/epoch before
        an append-only event is committed. A card or caller-supplied JSON
        authority blob cannot satisfy either check.
        """
        if transition not in {"acknowledged", "resolved"}:
            raise ValueError("incident lifecycle transition must be acknowledged or resolved")
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must be a non-empty canonical identity")
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise ValueError("grant_id must be a non-empty current grant identity")
        if not isinstance(custody_epoch, int) or isinstance(custody_epoch, bool) or custody_epoch < 1:
            raise ValueError("custody_epoch must be a positive current epoch")
        if not callable(run_authority_check) or not run_authority_check(grant_id, owner):
            raise ValueError("Run Authority grant/owner is not current")
        if not callable(custody_check) or not custody_check(owner, custody_epoch, occurrence_id):
            raise ValueError("Custody owner/epoch is not current")
        occurrence_id = str(occurrence_id).strip()
        if not occurrence_id:
            raise ValueError("occurrence_id must be a non-empty canonical identity")
        event_key = hashlib.sha256(
            json.dumps(
                [occurrence_id, transition, owner, grant_id, custody_epoch],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        return self.append_event(
            {
                "schema_version": 1,
                "event_id": f"incident-lifecycle-{event_key}",
                "ts": now,
                "type": transition,
                "actor": owner,
                "scope": f"incident:{occurrence_id}",
                "outcome": "accepted",
                "summary": f"Incident {transition} through canonical Run Authority and Custody",
                "evidence": [
                    f"run-authority:{grant_id}",
                    f"custody:{owner}:{custody_epoch}",
                ],
                "parent_event_ids": [],
                "next_expected_event": None,
                "deadline_ts": None,
                "trigger_event_id": None,
                "incident_id": occurrence_id,
                "session_id": session_id or None,
                "run_authority_grant_id": grant_id,
                "custody_epoch": custody_epoch,
            }
        )


__all__ = [
    "IncidentLedger",
]
