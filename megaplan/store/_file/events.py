from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any, Sequence

from megaplan._core.io import read_committed_framed_json_records
from megaplan.schemas import EpicEvent
from megaplan.schemas.base import utc_now
from megaplan.store.base import StoredEvent

from .common import _new_id, _parse_datetime


class FileEventMixin:
    def events_for_plan(self, plan_id: str):
        events: list[StoredEvent] = []
        for event in self.list_epic_events_for_replay(plan_id):
            payload = event.post_state or event.pre_state or event.prior_state or {}
            phase = None
            kind = str(event.event_type or "epic_event")
            if isinstance(payload, dict):
                envelope = payload.get("event")
                if isinstance(envelope, dict):
                    events.append(_stored_from_envelope(envelope, event.occurred_at, event.id, "record_epic_event"))
                    continue
                else:
                    raw_phase = payload.get("phase")
                    phase = str(raw_phase) if raw_phase is not None else None
            events.append(
                StoredEvent(
                    kind=kind,
                    phase=phase,
                    payload=payload if isinstance(payload, dict) else {},
                    occurred_at=event.occurred_at,
                    id=event.id,
                    source="record_epic_event",
                )
            )

        telemetry_path = self.root / "telemetry" / f"{_safe_scope_name(plan_id)}.ndjson"
        if telemetry_path.exists():
            with telemetry_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = raw.get("payload") if isinstance(raw, dict) else {}
                    if isinstance(payload, dict) and isinstance(payload.get("event"), dict):
                        events.append(
                            _stored_from_envelope(
                                payload["event"],
                                raw.get("occurred_at"),
                                raw.get("id") if isinstance(raw.get("id"), str) else None,
                                "append_telemetry_event",
                            )
                        )
                        continue
                    payload = dict(payload) if isinstance(payload, dict) else {}
                    raw_phase = raw.get("phase") if isinstance(raw, dict) else None
                    if raw_phase is None:
                        raw_phase = payload.pop("phase", None)
                    events.append(
                        StoredEvent(
                            kind=str(raw.get("kind") or "telemetry"),
                            phase=raw_phase if isinstance(raw_phase, str) else None,
                            payload=payload,
                            occurred_at=raw.get("occurred_at"),
                            id=raw.get("id") if isinstance(raw.get("id"), str) else None,
                            seq=raw.get("seq") if isinstance(raw.get("seq"), int) else None,
                            run_id=raw.get("run_id") if isinstance(raw.get("run_id"), str) else None,
                            source="append_telemetry_event",
                        )
                    )

        for log in self._system_logs():
            if getattr(log, "epic_id", None) != plan_id:
                continue
            details = getattr(log, "details", None) or {}
            if isinstance(details, dict) and isinstance(details.get("event"), dict):
                events.append(
                    _stored_from_envelope(
                        details["event"],
                        getattr(log, "occurred_at", None),
                        getattr(log, "id", None),
                        "log_system_event",
                    )
                )

        events.sort(key=_stored_event_sort_key)
        return iter(events)

    def append_telemetry_event(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        scope: str | None = None,
    ) -> dict[str, Any]:
        telemetry_dir = self.root / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        safe_scope = scope or "global"
        safe_name = _safe_scope_name(safe_scope)
        seq_path = telemetry_dir / f"{safe_name}.seq"
        ndjson_path = telemetry_dir / f"{safe_name}.ndjson"
        seq_fd = os.open(str(seq_path), os.O_RDWR | os.O_CREAT, 0o644)
        ndjson_fd = os.open(str(ndjson_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            fcntl.flock(seq_fd, fcntl.LOCK_EX)
            raw = os.read(seq_fd, 128)
            try:
                current = int(raw.strip()) if raw.strip() else -1
            except ValueError:
                current = -1
            seq = current + 1
            os.lseek(seq_fd, 0, os.SEEK_SET)
            os.write(seq_fd, str(seq).encode("ascii"))
            os.ftruncate(seq_fd, os.lseek(seq_fd, 0, os.SEEK_CUR))
            event = {
                "seq": seq,
                "kind": kind,
                "payload": dict(payload),
                "scope": scope,
                "occurred_at": utc_now().isoformat(),
            }
            line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            os.write(ndjson_fd, (line + "\n").encode("utf-8"))
            os.fsync(seq_fd)
            os.fsync(ndjson_fd)
            fcntl.flock(seq_fd, fcntl.LOCK_UN)
            return event
        finally:
            try:
                os.close(seq_fd)
            except OSError:
                pass
            try:
                os.close(ndjson_fd)
            except OSError:
                pass

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


def _safe_scope_name(scope: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in scope)


def _stored_from_envelope(
    envelope: dict[str, Any],
    occurred_at: Any,
    event_id: str | None,
    source: str,
) -> StoredEvent:
    raw_phase = envelope.get("phase")
    raw_payload = envelope.get("payload")
    return StoredEvent(
        kind=str(envelope.get("kind") or source),
        phase=raw_phase if isinstance(raw_phase, str) else None,
        payload=raw_payload if isinstance(raw_payload, dict) else {},
        occurred_at=envelope.get("ts_utc") or occurred_at,
        id=event_id,
        seq=envelope.get("seq") if isinstance(envelope.get("seq"), int) else None,
        run_id=envelope.get("run_id") if isinstance(envelope.get("run_id"), str) else None,
        source=str(envelope.get("store_method") or source),
    )


def _stored_event_sort_key(event: StoredEvent) -> tuple[str, int, str, str]:
    occurred = event.occurred_at
    if hasattr(occurred, "isoformat"):
        occurred_key = occurred.isoformat()  # type: ignore[union-attr]
    else:
        occurred_key = str(occurred or "")
    seq = event.seq if event.seq is not None else 10**12
    return (occurred_key, seq, event.source or "", event.id or "")
