from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from megaplan._core.io import read_committed_framed_json_records
from megaplan.schemas import EpicEvent
from megaplan.schemas.base import utc_now

from .common import _new_id, _parse_datetime


class FileEventMixin:
    def record_epic_event(
        self,
        *,
        epic_id: str,
        transaction_id: str,
        event_type: str,
        summary: str,
        prior_state: dict[str, Any] | None,
        pre_state: dict[str, Any] | None = None,
        post_state: dict[str, Any] | None = None,
        pre_state_canonical_json: str | None = None,
        post_state_canonical_json: str | None = None,
        pre_state_sha256: str | None = None,
        post_state_sha256: str | None = None,
        turn_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> EpicEvent:
        event = EpicEvent(
            id=_new_id("evt"),
            epic_id=epic_id,
            transaction_id=transaction_id,
            event_type=event_type,
            summary=summary,
            prior_state=prior_state,
            pre_state=pre_state,
            post_state=post_state,
            pre_state_canonical_json=pre_state_canonical_json,
            post_state_canonical_json=post_state_canonical_json,
            pre_state_sha256=pre_state_sha256,
            post_state_sha256=post_state_sha256,
            turn_id=turn_id,
            occurred_at=utc_now(),
        )
        self._commit_event(epic_id, event.model_dump(mode="json"))

        # Auto-address hook: flip tickets linked with resolves_on_complete=true
        # FileStore.root is the Arnold/epic backend directory, which may
        # differ from the git working tree where .megaplan/tickets/ lives.
        # Try self.root first, fall back to os.getcwd(); skip file walk if
        # neither contains a tickets directory (address_resolved_by_epic
        # handles None/absent-dir cleanly).
        if (
            event_type == "state_change"
            and post_state
            and post_state.get("state") == "done"
        ):
            from megaplan.tickets import address_resolved_by_epic

            import os as _os

            repo_root = self.root
            if not (repo_root / ".megaplan" / "tickets").is_dir():
                cwd = Path(_os.getcwd())
                if (cwd / ".megaplan" / "tickets").is_dir():
                    repo_root = cwd
                else:
                    repo_root = None
            address_resolved_by_epic(epic_id, store=self, repo_root=repo_root)

        return event

    def list_epic_events(
        self,
        epic_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        kinds: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[EpicEvent]:
        events_path = self._events_path(epic_id)
        events = [
            EpicEvent.model_validate({key: value for key, value in record.items() if key != "tx_id"})
            for record in read_committed_framed_json_records(events_path)
        ]
        if self._active_transaction is not None:
            events.extend(
                EpicEvent.model_validate(record)
                for record in self._active_transaction.staged_records(events_path)
            )
        since_dt = _parse_datetime(since)
        until_dt = _parse_datetime(until)
        filtered: list[EpicEvent] = []
        for event in events:
            if kinds and event.event_type not in kinds:
                continue
            if since_dt and event.occurred_at < since_dt:
                continue
            if until_dt and event.occurred_at > until_dt:
                continue
            filtered.append(event)
        filtered.sort(key=lambda event: (event.occurred_at, event.id), reverse=True)
        if limit is not None:
            return filtered[:limit]
        return filtered

    def list_epic_events_for_replay(self, epic_id: str) -> list[EpicEvent]:
        events = self.list_epic_events(epic_id, limit=None)
        return sorted(events, key=lambda event: (event.occurred_at, event.id))

    def latest_transaction_id(self, epic_id: str) -> str | None:
        events = self.list_epic_events(epic_id)
        if not events:
            return None
        return events[0].transaction_id

    def events_by_transaction(self, transaction_id: str) -> list[EpicEvent]:
        results: list[EpicEvent] = []
        for epic in self._epics():
            results.extend(
                event
                for event in self.list_epic_events_for_replay(epic.id)
                if event.transaction_id == transaction_id
            )
        results.sort(key=lambda event: (event.occurred_at, event.id))
        return results
