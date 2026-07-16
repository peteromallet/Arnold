"""Durable resident-managed schedule definitions and immutable occurrences.

The scheduler in this module owns only timing, admission, and the durable link
to the existing managed-agent boundary.  Managed-agent execution, synthesis,
and delivery continue to be owned by :mod:`resident.subagent`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, time, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import TZPATH, ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ScheduleState = Literal["draft", "active", "paused", "cancelled", "exhausted"]
OccurrenceState = Literal[
    "scheduled", "claimed", "launch_committed", "launched", "terminal",
    "suppressed", "cancelled", "dead_letter",
]
TERMINAL_OCCURRENCE_STATES = frozenset({"terminal", "suppressed", "cancelled", "dead_letter"})
ACTIVE_OCCURRENCE_STATES = frozenset({"claimed", "launch_committed", "launched"})
_DAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
         "friday": 4, "saturday": 5, "sunday": 6}
_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps require an explicit UTC offset")
    return value.astimezone(UTC)


def parse_duration(value: str) -> timedelta:
    match = _DURATION.fullmatch(value)
    if not match or not any(match.groupdict().values()):
        raise ValueError(f"unsupported ISO 8601 duration: {value!r}")
    result = timedelta(
        days=int(match.group("days") or 0),
        hours=int(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
        seconds=float(match.group("seconds") or 0),
    )
    if result <= timedelta(0):
        raise ValueError("duration must be positive")
    return result


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _tzdb_version() -> str:
    for root in TZPATH:
        version = Path(root) / "tzdata.zi"
        try:
            first = version.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, IndexError):
            continue
        if first.startswith("# version "):
            return first.removeprefix("# version ").strip()
    return "system-unknown"


class Owner(BaseModel):
    principal_id: str
    custody_scope: str


class AuthorizationGrant(BaseModel):
    grant_id: str
    source_envelope_digest: str
    approved_at: datetime
    expires_at: datetime | None = None
    maximum_work_intent: Literal["speculative", "review", "execution"]
    launch_origin: dict[str, Any] = Field(default_factory=dict)
    route_ref: str = "inherited-source-route"

    @field_validator("approved_at", "expires_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def expiry_is_ordered(self) -> "AuthorizationGrant":
        if self.expires_at is not None and self.expires_at <= self.approved_at:
            raise ValueError("authorization expiry must be after approval")
        if not self.source_envelope_digest.startswith("sha256:"):
            raise ValueError("source_envelope_digest must be content addressed")
        return self


class Timing(BaseModel):
    kind: Literal["at", "delay", "interval", "cron", "calendar", "event"]
    at: datetime | None = None
    after: str | None = None
    accepted_at: datetime | None = None
    every: str | None = None
    anchor_at: datetime | None = None
    cadence: Literal["fixed_rate", "fixed_delay"] = "fixed_rate"
    expression: str | None = None
    grammar: str = "cron-5field-v1"
    local_time: str | None = None
    days: list[str] = Field(default_factory=list)
    timezone: str = "UTC"
    gap_policy: Literal["reject", "skip", "next_valid"] = "reject"
    fold_policy: Literal["first", "second", "both"] = "first"
    event_type: str | None = None
    predicate: dict[str, Any] = Field(default_factory=dict)
    debounce: str | None = None
    cooldown: str | None = None
    dedupe_key: str = "event_id"

    @model_validator(mode="after")
    def validate_shape(self) -> "Timing":
        ZoneInfo(self.timezone)
        if self.kind == "at" and self.at is None:
            raise ValueError("at schedules require schedule.at")
        if self.kind == "delay" and (not self.after or self.accepted_at is None):
            raise ValueError("delay schedules require after and accepted_at")
        if self.kind == "interval" and (not self.every or self.anchor_at is None):
            raise ValueError("interval schedules require every and anchor_at")
        if self.kind == "cron":
            if not self.expression:
                raise ValueError("cron schedules require expression")
            parse_cron(self.expression)
            if self.grammar != "cron-5field-v1":
                raise ValueError("only versioned cron-5field-v1 is supported")
        if self.kind == "calendar":
            if not self.local_time or not self.days:
                raise ValueError("calendar schedules require local_time and days")
            time.fromisoformat(self.local_time)
            if any(day.lower() not in _DAYS for day in self.days):
                raise ValueError("calendar days must be weekday names")
        if self.kind == "event" and not self.event_type:
            raise ValueError("event schedules require event_type")
        for value in (self.after, self.every, self.debounce, self.cooldown):
            if value:
                parse_duration(value)
        for name in ("at", "accepted_at", "anchor_at"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, _utc(value))
        return self


class Bounds(BaseModel):
    max_occurrences: int | None = Field(default=None, ge=1)
    end_at: datetime | None = None

    @field_validator("end_at")
    @classmethod
    def end_is_aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)


class Policies(BaseModel):
    misfire: Literal["skip", "latest_once", "catch_up"] = "latest_once"
    catch_up_limit: int = Field(default=1, ge=1, le=100)
    grace: str = "PT5M"
    overlap: Literal["allow", "forbid", "queue", "replace"] = "forbid"
    concurrency_key: str | None = None
    max_active: int = Field(default=1, ge=1, le=100)
    maximum_queue_age: str = "PT24H"
    quota_breach: Literal["suppress", "pause"] = "suppress"

    @model_validator(mode="after")
    def durations_are_valid(self) -> "Policies":
        parse_duration(self.grace)
        parse_duration(self.maximum_queue_age)
        if self.overlap == "replace":
            raise ValueError("replace overlap requires a separate cancellation grant and is disabled")
        return self


class Target(BaseModel):
    kind: Literal["resident_managed_agent", "resident_orchestrator_turn"]
    prompt_ref: str
    prompt: str
    prompt_digest: str
    model: str = "gpt-5.6-terra"
    profile: str = "resident-subagent-standard"
    toolsets: list[str] = Field(default_factory=list)
    work_intent: Literal["speculative", "review", "execution"]
    task_kind: str = "other"
    description: str = "Scheduled resident-managed work"
    project_dir: str | None = None
    operation: Literal["managed_launch", "vp_todo_sweep", "probe"] = "managed_launch"
    dependencies: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def prompt_is_immutable(self) -> "Target":
        actual = "sha256:" + hashlib.sha256(self.prompt.encode()).hexdigest()
        if self.prompt_digest != actual:
            raise ValueError("target prompt_digest does not match prompt bytes")
        if not self.prompt_ref or not self.prompt_ref.rsplit("/", 1)[-1]:
            raise ValueError("prompt_ref must identify an immutable version")
        if self.kind == "resident_managed_agent" and self.operation != "managed_launch":
            raise ValueError("resident_managed_agent targets require managed_launch")
        if self.kind == "resident_orchestrator_turn" and self.operation not in {"vp_todo_sweep", "probe"}:
            raise ValueError("resident_orchestrator_turn targets require vp_todo_sweep or probe")
        return self


class Delivery(BaseModel):
    synthesis_owner: Literal["schedule_root"] = "schedule_root"
    route_ref: str = "inherited-source-route"
    mode: Literal["exact_authorized_route"] = "exact_authorized_route"


class RetryPolicy(BaseModel):
    launch_max_attempts: int = Field(default=3, ge=1, le=10)
    initial_backoff: str = "PT30S"
    maximum_backoff: str = "PT1H"

    @model_validator(mode="after")
    def validate_backoff(self) -> "RetryPolicy":
        if parse_duration(self.maximum_backoff) < parse_duration(self.initial_backoff):
            raise ValueError("maximum_backoff must not be less than initial_backoff")
        return self


class Quota(BaseModel):
    max_runs_per_hour: int | None = Field(default=None, ge=1)
    max_runs_per_day: int | None = Field(default=None, ge=1)
    max_concurrent_runs: int = Field(default=1, ge=1)
    maximum_tokens_per_occurrence: int | None = Field(default=None, ge=1)
    maximum_tokens_per_day: int | None = Field(default=None, ge=1)
    maximum_cost_usd_per_day: float | None = Field(default=None, gt=0)
    maximum_schedule_lifetime: str | None = None


class ScheduleDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    schema_version: Literal["arnold-resident-schedule-v1"] = Field(
        default="arnold-resident-schedule-v1", alias="schema"
    )
    schedule_id: str = Field(pattern=r"^sched_[a-z0-9][a-z0-9_-]{2,95}$")
    revision: int = Field(default=1, ge=1)
    generation: int = Field(default=1, ge=1)
    state: ScheduleState = "draft"
    owner: Owner
    authorization: AuthorizationGrant
    schedule: Timing
    bounds: Bounds = Field(default_factory=Bounds)
    policies: Policies = Field(default_factory=Policies)
    target: Target
    delivery: Delivery = Field(default_factory=Delivery)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    quota: Quota = Field(default_factory=Quota)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    audit_reason: str

    @model_validator(mode="after")
    def authorization_is_narrow(self) -> "ScheduleDefinition":
        rank = {"speculative": 0, "review": 1, "execution": 2}
        if rank[self.target.work_intent] > rank[self.authorization.maximum_work_intent]:
            raise ValueError("target work_intent exceeds the immutable authorization grant")
        if self.delivery.route_ref != self.authorization.route_ref:
            raise ValueError("delivery route must exactly match the authorized route")
        self.created_at = _utc(self.created_at)
        self.updated_at = _utc(self.updated_at)
        if self.quota.maximum_schedule_lifetime:
            parse_duration(self.quota.maximum_schedule_lifetime)
        return self


class ScheduleOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["arnold-resident-schedule-occurrence-v1"] = "arnold-resident-schedule-occurrence-v1"
    occurrence_id: str
    occurrence_key: str
    schedule_id: str
    schedule_revision: int
    generation: int
    nominal_at: datetime
    eligible_at: datetime
    initial_state: Literal["scheduled", "suppressed"] = "scheduled"
    authorization_digest: str
    pinned_definition_digest: str
    pinned_launch_spec: dict[str, Any]
    event_id: str | None = None
    replay_of_occurrence_id: str | None = None
    tzdb_version: str
    created_at: datetime


class OccurrenceProjection(BaseModel):
    occurrence: ScheduleOccurrence
    state: OccurrenceState
    attempt: int = 0
    claim_owner: str | None = None
    claim_token: str | None = None
    fence: int = 0
    claim_expires_at: datetime | None = None
    retry_at: datetime | None = None
    run_id: str | None = None
    manifest_path: str | None = None
    manifest_digest: str | None = None
    delivery_state: str | None = None
    decision: str | None = None
    last_error: str | None = None
    updated_at: datetime


class ScheduleRunReceipt(BaseModel):
    materialized: int = 0
    suppressed: int = 0
    claimed: int = 0
    launched: int = 0
    terminal: int = 0
    retried: int = 0
    dead_lettered: int = 0
    duplicate_conflicts: int = 0


def _cron_field(token: str, minimum: int, maximum: int, *, sunday: bool = False) -> frozenset[int]:
    values: set[int] = set()
    for part in token.split(","):
        base, slash, step_text = part.partition("/")
        step = int(step_text) if slash else 1
        if step < 1:
            raise ValueError("cron step must be positive")
        if base == "*":
            lo, hi = minimum, maximum
        elif "-" in base:
            lo_text, hi_text = base.split("-", 1)
            lo, hi = int(lo_text), int(hi_text)
        else:
            lo = hi = int(base)
        if lo < minimum or hi > maximum or lo > hi:
            raise ValueError(f"cron field {token!r} outside {minimum}..{maximum}")
        values.update(range(lo, hi + 1, step))
    if sunday and 7 in values:
        values.remove(7)
        values.add(0)
    return frozenset(values)


def parse_cron(expression: str) -> tuple[frozenset[int], ...]:
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError("cron-5field-v1 requires exactly five fields")
    return (
        _cron_field(parts[0], 0, 59), _cron_field(parts[1], 0, 23),
        _cron_field(parts[2], 1, 31), _cron_field(parts[3], 1, 12),
        _cron_field(parts[4], 0, 7, sunday=True),
    )


def _valid_local_candidates(local: datetime, timing: Timing) -> list[datetime]:
    zone = ZoneInfo(timing.timezone)
    candidates: list[datetime] = []
    for fold in (0, 1):
        aware = local.replace(tzinfo=zone, fold=fold)
        back = aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
        if back == local and aware.utcoffset() not in [item.utcoffset() for item in candidates]:
            candidates.append(aware)
    candidates.sort(key=lambda value: value.astimezone(UTC))
    if not candidates:
        if timing.gap_policy == "reject":
            raise ValueError(f"local time {local.isoformat()} is in a DST gap")
        if timing.gap_policy == "skip":
            return []
        probe = local
        for _ in range(180):
            probe += timedelta(minutes=1)
            found = _valid_local_candidates(probe, timing.model_copy(update={"gap_policy": "skip"}))
            if found:
                return found[:1]
        raise ValueError("could not find a valid local time within three hours of DST gap")
    if len(candidates) == 1:
        return candidates
    if timing.fold_policy == "both":
        return candidates
    return [candidates[0 if timing.fold_policy == "first" else 1]]


def _local_nominals(timing: Timing, start: datetime, end: datetime) -> Iterable[datetime]:
    zone = ZoneInfo(timing.timezone)
    local_start = start.astimezone(zone).replace(tzinfo=None, second=0, microsecond=0)
    local_end = end.astimezone(zone).replace(tzinfo=None, second=0, microsecond=0)
    if timing.kind == "cron":
        expression = str(timing.expression)
        minute, hour, monthday, month, weekday = parse_cron(expression)
        cron_parts = expression.split()
        cursor = local_start
        while cursor <= local_end:
            cron_weekday = (cursor.weekday() + 1) % 7
            day_of_month_matches = cursor.day in monthday
            day_of_week_matches = cron_weekday in weekday
            if cron_parts[2] == "*":
                day_matches = day_of_week_matches
            elif cron_parts[4] == "*":
                day_matches = day_of_month_matches
            else:
                # POSIX cron treats restricted day-of-month and day-of-week as OR.
                day_matches = day_of_month_matches or day_of_week_matches
            if (cursor.minute in minute and cursor.hour in hour
                    and cursor.month in month and day_matches):
                for aware in _valid_local_candidates(cursor, timing):
                    nominal = aware.astimezone(UTC)
                    if start <= nominal <= end:
                        yield nominal
            cursor += timedelta(minutes=1)
        return
    local_clock = time.fromisoformat(str(timing.local_time))
    weekdays = {_DAYS[item.lower()] for item in timing.days}
    cursor_date = local_start.date()
    while cursor_date <= local_end.date():
        if cursor_date.weekday() in weekdays:
            local = datetime.combine(cursor_date, local_clock)
            for aware in _valid_local_candidates(local, timing):
                nominal = aware.astimezone(UTC)
                if start <= nominal <= end:
                    yield nominal
        cursor_date += timedelta(days=1)


class ScheduleRepository:
    """Append-only file repository protected by a process-wide OS lock."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve() / "schedules"

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / ".writer.lock").open("a+b")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _atomic(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, indent=2, default=str)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _append(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def definition_path(self, schedule_id: str, revision: int) -> Path:
        return self.root / "definitions" / schedule_id / f"{revision:08d}.json"

    def head_path(self, schedule_id: str) -> Path:
        return self.root / "heads" / f"{schedule_id}.json"

    def occurrence_path(self, occurrence_id: str) -> Path:
        return self.root / "occurrences" / f"{occurrence_id}.json"

    def transition_path(self, occurrence_id: str) -> Path:
        return self.root / "occurrence-events" / f"{occurrence_id}.jsonl"

    def read_definition(self, schedule_id: str, revision: int | None = None) -> ScheduleDefinition:
        if revision is None:
            head = json.loads(self.head_path(schedule_id).read_text(encoding="utf-8"))
            revision = int(head["revision"])
        return ScheduleDefinition.model_validate_json(self.definition_path(schedule_id, revision).read_text(encoding="utf-8"))

    def definitions(self, *, state: str | None = None) -> list[ScheduleDefinition]:
        rows = []
        for path in sorted((self.root / "heads").glob("*.json")):
            try:
                head = json.loads(path.read_text(encoding="utf-8"))
                row = self.read_definition(str(head["schedule_id"]), int(head["revision"]))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            if state is None or row.state == state:
                rows.append(row)
        return rows

    def occurrences(self, schedule_id: str | None = None) -> list[OccurrenceProjection]:
        rows: list[OccurrenceProjection] = []
        for path in sorted((self.root / "occurrences").glob("*.json")):
            occurrence = ScheduleOccurrence.model_validate_json(path.read_text(encoding="utf-8"))
            if schedule_id is None or occurrence.schedule_id == schedule_id:
                rows.append(self.project(occurrence))
        rows.sort(key=lambda item: (item.occurrence.nominal_at, item.occurrence.occurrence_id))
        return rows

    def project(self, occurrence: ScheduleOccurrence) -> OccurrenceProjection:
        projection = OccurrenceProjection(
            occurrence=occurrence, state=occurrence.initial_state,
            decision="misfire_suppressed" if occurrence.initial_state == "suppressed" else "admitted",
            updated_at=occurrence.created_at,
        )
        path = self.transition_path(occurrence.occurrence_id)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                changes = {key: value for key, value in event.get("changes", {}).items()
                           if key in OccurrenceProjection.model_fields}
                changes["updated_at"] = event["at"]
                payload = projection.model_dump(mode="python")
                payload.update(changes)
                projection = OccurrenceProjection.model_validate(payload)
        return projection

    def transition(self, occurrence_id: str, *, event: str, actor: str,
                   changes: Mapping[str, Any], expected_fence: int | None = None,
                   expected_token: str | None = None) -> OccurrenceProjection:
        with self.locked():
            return self._transition_unlocked(
                occurrence_id, event=event, actor=actor, changes=changes,
                expected_fence=expected_fence, expected_token=expected_token,
            )

    def _transition_unlocked(self, occurrence_id: str, *, event: str, actor: str,
                             changes: Mapping[str, Any], expected_fence: int | None = None,
                             expected_token: str | None = None) -> OccurrenceProjection:
        occurrence = ScheduleOccurrence.model_validate_json(self.occurrence_path(occurrence_id).read_text(encoding="utf-8"))
        current = self.project(occurrence)
        if expected_fence is not None and current.fence != expected_fence:
            raise RuntimeError("stale occurrence fence")
        if expected_token is not None and current.claim_token != expected_token:
            raise RuntimeError("stale occurrence claim token")
        now = utc_now()
        receipt = {
            "schema_version": "arnold-resident-schedule-receipt-v1", "event": event,
            "schedule_id": occurrence.schedule_id, "schedule_revision": occurrence.schedule_revision,
            "generation": occurrence.generation, "occurrence_id": occurrence_id,
            "occurrence_key": occurrence.occurrence_key, "nominal_at": occurrence.nominal_at,
            "at": now, "actor": actor, "source_digest": occurrence.authorization_digest,
            "previous_event_hash": self._last_event_hash(self.transition_path(occurrence_id)),
            "changes": dict(changes),
        }
        receipt["event_hash"] = _digest(receipt)
        self._append(self.transition_path(occurrence_id), receipt)
        return self.project(occurrence)

    @staticmethod
    def _last_event_hash(path: Path) -> str | None:
        if not path.exists():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1]).get("event_hash") if lines else None


class ScheduleService:
    def __init__(self, store_root: Path, *, project_root: Path | None = None) -> None:
        self.repo = ScheduleRepository(store_root)
        self.project_root = Path(project_root or Path.cwd()).resolve()

    def create(self, definition: ScheduleDefinition, *, idempotency_key: str,
               actor: str = "resident-cli") -> tuple[ScheduleDefinition, bool]:
        if definition.schedule.kind == "delay":
            normalized_timing = definition.schedule.model_copy(update={
                "kind": "at",
                "at": definition.schedule.accepted_at + parse_duration(str(definition.schedule.after)),
            })
            payload = definition.model_dump(mode="python", by_alias=True)
            payload["schedule"] = normalized_timing.model_dump(mode="python")
            definition = ScheduleDefinition.model_validate(payload)
        if (definition.state == "active" and definition.authorization.expires_at is not None
                and definition.authorization.expires_at <= utc_now()):
            raise ValueError("cannot create an active schedule with an expired authorization grant")
        body = definition.model_dump(mode="json", by_alias=True)
        body_digest = _digest(body)
        idem = self.repo.root / "idempotency" / f"{hashlib.sha256(idempotency_key.encode()).hexdigest()}.json"
        with self.repo.locked():
            if idem.exists():
                prior = json.loads(idem.read_text(encoding="utf-8"))
                if prior["body_digest"] != body_digest:
                    raise ValueError("idempotency key already used with a different definition")
                return self.repo.read_definition(str(prior["schedule_id"]), int(prior["revision"])), False
            if self.repo.head_path(definition.schedule_id).exists():
                existing = self.repo.read_definition(definition.schedule_id)
                if _digest(existing.model_dump(mode="json", by_alias=True)) != body_digest:
                    raise ValueError("schedule_id already exists; use update with optimistic revision")
                self.repo._atomic(idem, {
                    "schedule_id": existing.schedule_id,
                    "revision": existing.revision,
                    "body_digest": body_digest,
                })
                return existing, False
            if definition.revision != 1 or definition.generation != 1:
                raise ValueError("new definitions must start at revision 1 and generation 1")
            self.repo._atomic(self.repo.definition_path(definition.schedule_id, 1), body)
            self.repo._atomic(self.repo.head_path(definition.schedule_id), {
                "schedule_id": definition.schedule_id, "revision": 1, "state": definition.state,
                "updated_at": definition.updated_at,
            })
            self.repo._atomic(idem, {"schedule_id": definition.schedule_id, "revision": 1, "body_digest": body_digest})
            self._definition_receipt(definition, "definition_created", actor)
            return definition, True

    def revise(self, schedule_id: str, replacement: ScheduleDefinition, *, if_revision: int,
               actor: str = "resident-cli") -> ScheduleDefinition:
        with self.repo.locked():
            current = self.repo.read_definition(schedule_id)
            if current.revision != if_revision:
                raise ValueError(f"revision conflict: expected {if_revision}, found {current.revision}")
            if replacement.schedule_id != schedule_id:
                raise ValueError("schedule_id is immutable")
            if replacement.owner != current.owner:
                raise ValueError("owner/custody changes require a new schedule")
            grant_changed = replacement.authorization != current.authorization
            if grant_changed and replacement.authorization.grant_id == current.authorization.grant_id:
                raise ValueError("authorization changes require a new immutable grant_id")
            timing_changed = replacement.schedule != current.schedule
            now = utc_now()
            revised_payload = replacement.model_dump(mode="python", by_alias=True)
            revised_payload.update({
                "revision": current.revision + 1,
                "generation": current.generation + int(timing_changed),
                "created_at": current.created_at, "updated_at": now,
            })
            revised = ScheduleDefinition.model_validate(revised_payload)
            path = self.repo.definition_path(schedule_id, revised.revision)
            self.repo._atomic(path, revised.model_dump(mode="json", by_alias=True))
            self.repo._atomic(self.repo.head_path(schedule_id), {
                "schedule_id": schedule_id, "revision": revised.revision,
                "state": revised.state, "updated_at": now,
            })
            if timing_changed:
                for projection in self.repo.occurrences(schedule_id):
                    if projection.occurrence.generation == current.generation and projection.state == "scheduled":
                        self.repo._transition_unlocked(
                            projection.occurrence.occurrence_id, event="old_generation_cancelled",
                            actor=actor, changes={"state": "cancelled", "decision": "definition_revised"}
                        )
            self._definition_receipt(revised, "definition_revised", actor)
            return revised

    def set_state(self, schedule_id: str, state: Literal["active", "paused", "cancelled"], *,
                  if_revision: int, actor: str = "resident-cli", audit_reason: str) -> ScheduleDefinition:
        current = self.repo.read_definition(schedule_id)
        if current.state in {"cancelled", "exhausted"}:
            raise ValueError(f"terminal schedule cannot transition from {current.state}")
        if state == "active" and current.state not in {"draft", "paused", "active"}:
            raise ValueError("schedule cannot be activated from current state")
        if (state == "active" and current.authorization.expires_at is not None
                and current.authorization.expires_at <= utc_now()):
            raise ValueError("cannot activate an expired authorization grant")
        replacement = current.model_copy(update={"state": state, "audit_reason": audit_reason})
        return self.revise(schedule_id, replacement, if_revision=if_revision, actor=actor)

    def _definition_receipt(self, definition: ScheduleDefinition, event: str, actor: str) -> None:
        path = self.repo.root / "definition-events" / f"{definition.schedule_id}.jsonl"
        receipt = {
            "schema_version": "arnold-resident-schedule-receipt-v1", "event": event,
            "schedule_id": definition.schedule_id, "schedule_revision": definition.revision,
            "generation": definition.generation, "at": utc_now(), "actor": actor,
            "source_digest": definition.authorization.source_envelope_digest,
            "previous_event_hash": self.repo._last_event_hash(path),
            "definition_digest": _digest(definition.model_dump(mode="json", by_alias=True)),
        }
        receipt["event_hash"] = _digest(receipt)
        self.repo._append(path, receipt)

    def preview(self, definition: ScheduleDefinition, *, count: int = 10,
                start: datetime | None = None) -> list[datetime]:
        start = _utc(start or utc_now())
        timing = definition.schedule
        if timing.kind == "event":
            return []
        if timing.kind == "at":
            values = [_utc(timing.at)]  # type: ignore[arg-type]
        elif timing.kind == "delay":
            values = [_utc(timing.accepted_at) + parse_duration(str(timing.after))]  # type: ignore[arg-type]
        elif timing.kind == "interval":
            anchor = _utc(timing.anchor_at)  # type: ignore[arg-type]
            every = parse_duration(str(timing.every))
            if start <= anchor:
                cursor = anchor
            else:
                elapsed = (start - anchor).total_seconds()
                cursor = anchor + every * int(elapsed // every.total_seconds())
                if cursor < start:
                    cursor += every
            values = [cursor + every * offset for offset in range(count)]
        else:
            horizon = start + timedelta(days=370)
            values = list(_local_nominals(timing, start, horizon))
        if definition.bounds.end_at:
            values = [item for item in values if item <= definition.bounds.end_at]
        return values[:count]

    def _due_nominals(self, definition: ScheduleDefinition, now: datetime) -> list[tuple[datetime, str | None]]:
        existing = self.repo.occurrences(definition.schedule_id)
        seen = {(item.occurrence.generation, item.occurrence.nominal_at) for item in existing}
        timing = definition.schedule
        start = definition.created_at
        if existing:
            same_generation = [item.occurrence.nominal_at for item in existing
                               if item.occurrence.generation == definition.generation]
            if same_generation:
                start = max(same_generation) + timedelta(microseconds=1)
        values: list[datetime]
        if timing.kind == "at":
            values = [_utc(timing.at)]  # type: ignore[arg-type]
        elif timing.kind == "delay":
            values = [_utc(timing.accepted_at) + parse_duration(str(timing.after))]  # type: ignore[arg-type]
        elif timing.kind == "interval":
            anchor = _utc(timing.anchor_at)  # type: ignore[arg-type]
            every = parse_duration(str(timing.every))
            if timing.cadence == "fixed_delay" and existing:
                latest = max(existing, key=lambda item: item.occurrence.nominal_at)
                if latest.state not in TERMINAL_OCCURRENCE_STATES:
                    return []
                nominal = latest.updated_at + every
                values = [nominal] if nominal <= now else []
                return [(item, None) for item in values
                        if (definition.generation, item) not in seen]
            cursor = anchor
            if start > cursor:
                cursor = anchor + every * int((start - anchor).total_seconds() // every.total_seconds())
                if cursor < start:
                    cursor += every
            values = []
            while cursor <= now and len(values) < 10000:
                values.append(cursor)
                cursor += every
        elif timing.kind in {"cron", "calendar"}:
            values = list(_local_nominals(timing, start, now))
        else:
            return []
        return [(item, None) for item in values if item <= now and (definition.generation, item) not in seen]

    def materialize(self, *, now: datetime | None = None) -> ScheduleRunReceipt:
        now = _utc(now or utc_now())
        result = ScheduleRunReceipt()
        with self.repo.locked():
            for definition in self.repo.definitions(state="active"):
                lifetime = definition.quota.maximum_schedule_lifetime
                if lifetime and definition.created_at + parse_duration(lifetime) < now:
                    self._exhaust(definition)
                    continue
                due = self._due_nominals(definition, now)
                if definition.bounds.end_at is not None:
                    due = [item for item in due if item[0] <= definition.bounds.end_at]
                if not due:
                    continue
                existing_count = len(self.repo.occurrences(definition.schedule_id))
                remaining = ((definition.bounds.max_occurrences - existing_count)
                             if definition.bounds.max_occurrences is not None else len(due))
                if remaining <= 0:
                    self._exhaust(definition)
                    continue
                due = due[:remaining]
                grace = parse_duration(definition.policies.grace)
                on_time = {item[0] for item in due if now - item[0] <= grace}
                missed = [item for item in due if item[0] not in on_time]
                admitted: set[datetime] = set(on_time)
                if definition.policies.misfire == "skip":
                    pass
                elif definition.policies.misfire == "latest_once" and missed:
                    admitted.add(missed[-1][0])
                else:
                    admitted.update(item[0] for item in missed[:definition.policies.catch_up_limit])
                for nominal, event_id in due:
                    initial = "scheduled" if nominal in admitted else "suppressed"
                    created = self._insert_occurrence(definition, nominal, now, initial, event_id)
                    if created:
                        result.materialized += 1
                        result.suppressed += int(initial == "suppressed")
                    else:
                        result.duplicate_conflicts += 1
                if definition.bounds.max_occurrences is not None:
                    if len(self.repo.occurrences(definition.schedule_id)) >= definition.bounds.max_occurrences:
                        self._exhaust(definition)
        return result

    def _exhaust(self, definition: ScheduleDefinition) -> None:
        if definition.state != "active":
            return
        exhausted = definition.model_copy(update={
            "revision": definition.revision + 1, "state": "exhausted",
            "updated_at": utc_now(), "audit_reason": "maximum occurrences reached",
        })
        self.repo._atomic(self.repo.definition_path(exhausted.schedule_id, exhausted.revision),
                          exhausted.model_dump(mode="json", by_alias=True))
        self.repo._atomic(self.repo.head_path(exhausted.schedule_id), {
            "schedule_id": exhausted.schedule_id, "revision": exhausted.revision,
            "state": exhausted.state, "updated_at": exhausted.updated_at,
        })
        self._definition_receipt(exhausted, "definition_exhausted", "resident-scheduler")

    def _insert_occurrence(self, definition: ScheduleDefinition, nominal: datetime, now: datetime,
                           initial: Literal["scheduled", "suppressed"], event_id: str | None,
                           replay_of_occurrence_id: str | None = None) -> bool:
        identity = (
            [definition.schedule_id, definition.generation, "event", event_id]
            if event_id is not None
            else [definition.schedule_id, definition.generation, "time", nominal.isoformat()]
        )
        key = _digest(identity)
        occurrence_id = f"occ_{definition.schedule_id.removeprefix('sched_')}_{key[7:31]}"
        path = self.repo.occurrence_path(occurrence_id)
        if path.exists():
            return False
        pinned = {
            "target": definition.target.model_dump(mode="json"),
            "authorization": definition.authorization.model_dump(mode="json"),
            "delivery": definition.delivery.model_dump(mode="json"),
            "retry": definition.retry.model_dump(mode="json"),
            "quota": definition.quota.model_dump(mode="json"),
            "owner": definition.owner.model_dump(mode="json"),
            "policies": definition.policies.model_dump(mode="json"),
        }
        occurrence = ScheduleOccurrence(
            occurrence_id=occurrence_id, occurrence_key=key,
            schedule_id=definition.schedule_id, schedule_revision=definition.revision,
            generation=definition.generation, nominal_at=nominal, eligible_at=nominal,
            initial_state=initial,
            authorization_digest=_digest(definition.authorization.model_dump(mode="json")),
            pinned_definition_digest=_digest(definition.model_dump(mode="json", by_alias=True)),
            pinned_launch_spec=pinned, event_id=event_id,
            replay_of_occurrence_id=replay_of_occurrence_id,
            tzdb_version=_tzdb_version(),
            created_at=now,
        )
        self.repo._atomic(path, occurrence.model_dump(mode="json"))
        self.repo._transition_unlocked(
            occurrence_id, event="occurrence_materialized", actor="resident-scheduler",
            changes={"state": initial,
                     "decision": "admitted" if initial == "scheduled" else "misfire_suppressed"},
        )
        return True

    def ingest_event(self, event: Mapping[str, Any], *, actor: str = "resident-event-adapter",
                     now: datetime | None = None) -> list[str]:
        now = _utc(now or utc_now())
        event_id = str(event.get("event_id") or "")
        event_type = str(event.get("event_type") or "")
        if not event_id or not event_type:
            raise ValueError("typed events require stable event_id and event_type")
        created: list[str] = []
        with self.repo.locked():
            dedupe = self.repo.root / "event-dedupe" / f"{hashlib.sha256(event_id.encode()).hexdigest()}.json"
            if dedupe.exists():
                return []
            for definition in self.repo.definitions(state="active"):
                timing = definition.schedule
                if timing.kind != "event" or timing.event_type != event_type:
                    continue
                if definition.bounds.end_at is not None and now > definition.bounds.end_at:
                    continue
                if (definition.bounds.max_occurrences is not None
                        and len(self.repo.occurrences(definition.schedule_id)) >= definition.bounds.max_occurrences):
                    self._exhaust(definition)
                    continue
                if any(event.get(key) != value for key, value in timing.predicate.items()):
                    continue
                recent = [item for item in self.repo.occurrences(definition.schedule_id)
                          if item.occurrence.event_id is not None]
                quiet_periods = [parse_duration(value) for value in (timing.debounce, timing.cooldown) if value]
                if quiet_periods and recent:
                    if now - max(item.occurrence.nominal_at for item in recent) < max(quiet_periods):
                        continue
                before = {item.occurrence.occurrence_id for item in recent}
                if self._insert_occurrence(definition, now, now, "scheduled", event_id):
                    after = {item.occurrence.occurrence_id for item in self.repo.occurrences(definition.schedule_id)}
                    created.extend(sorted(after - before))
            self.repo._atomic(dedupe, {"event_id": event_id, "event_type": event_type,
                                       "at": now, "created_occurrence_ids": created, "actor": actor})
        return created

    def replay(self, occurrence_id: str, *, grant: AuthorizationGrant,
               actor: str = "resident-cli", now: datetime | None = None) -> str:
        now = _utc(now or utc_now())
        with self.repo.locked():
            original = ScheduleOccurrence.model_validate_json(
                self.repo.occurrence_path(occurrence_id).read_text(encoding="utf-8")
            )
            projection = self.repo.project(original)
            if projection.state != "dead_letter":
                raise ValueError("only dead-letter occurrences may be replayed")
            definition = self.repo.read_definition(original.schedule_id)
            if grant.grant_id == definition.authorization.grant_id:
                raise ValueError("replay requires a new immutable authorization grant")
            replacement = definition.model_copy(update={"authorization": grant})
            # Full validation re-applies work-intent and route non-expansion.
            replacement = ScheduleDefinition.model_validate(
                replacement.model_dump(mode="json", by_alias=True)
            )
            event_id = f"replay:{occurrence_id}:{grant.grant_id}"
            if not self._insert_occurrence(
                replacement, now, now, "scheduled", event_id,
                replay_of_occurrence_id=occurrence_id,
            ):
                raise ValueError("replay already exists for this occurrence and grant")
            created = [item for item in self.repo.occurrences(original.schedule_id)
                       if item.occurrence.replay_of_occurrence_id == occurrence_id
                       and item.occurrence.event_id == event_id]
            return created[-1].occurrence.occurrence_id

    def claim(self, *, worker_id: str, now: datetime | None = None, limit: int = 10,
              lease_seconds: int = 600) -> list[OccurrenceProjection]:
        now = _utc(now or utc_now())
        claimed: list[OccurrenceProjection] = []
        with self.repo.locked():
            for projection in self.repo.occurrences():
                if len(claimed) >= limit:
                    break
                definition = self.repo.read_definition(projection.occurrence.schedule_id)
                if definition.state not in {"active", "exhausted"}:
                    continue
                stale = (projection.state == "claimed" and projection.claim_expires_at is not None
                         and projection.claim_expires_at <= now)
                retry_due = projection.retry_at is None or projection.retry_at <= now
                if not ((projection.state == "scheduled" and retry_due) or stale):
                    continue
                token = uuid4().hex
                next_fence = projection.fence + 1
                claimed.append(self.repo._transition_unlocked(
                    projection.occurrence.occurrence_id,
                    event="occurrence_reclaimed" if stale else "occurrence_claimed",
                    actor=worker_id,
                    changes={"state": "claimed", "attempt": projection.attempt + 1,
                             "claim_owner": worker_id, "claim_token": token, "fence": next_fence,
                             "claim_expires_at": now + timedelta(seconds=lease_seconds), "retry_at": None},
                ))
        return claimed

    async def run_due_once(self, *, worker_id: str = "resident-schedule-worker",
                           now: datetime | None = None, limit: int = 10) -> ScheduleRunReceipt:
        now = _utc(now or utc_now())
        result = self.materialize(now=now)
        self.reconcile_terminal_runs()
        claims = self.claim(worker_id=worker_id, now=now, limit=limit)
        result.claimed += len(claims)
        for claim in claims:
            outcome = await self._execute_claim(claim, now=now, worker_id=worker_id)
            setattr(result, outcome, getattr(result, outcome) + 1)
        return result

    async def _execute_claim(self, claim: OccurrenceProjection, *, now: datetime,
                             worker_id: str) -> str:
        occurrence = claim.occurrence
        pinned = occurrence.pinned_launch_spec
        authorization = AuthorizationGrant.model_validate(pinned["authorization"])
        target = Target.model_validate(pinned["target"])
        quota = Quota.model_validate(pinned["quota"])
        policies = Policies.model_validate(pinned["policies"])
        token, fence = claim.claim_token, claim.fence
        try:
            if authorization.expires_at is not None and authorization.expires_at <= now:
                raise PermissionError("authorization grant expired before launch")
            if _digest(authorization.model_dump(mode="json")) != occurrence.authorization_digest:
                raise PermissionError("authorization digest mismatch")
            if target.prompt_digest != "sha256:" + hashlib.sha256(target.prompt.encode()).hexdigest():
                raise PermissionError("prompt digest mismatch")
            active = [item for item in self.repo.occurrences(occurrence.schedule_id)
                      if item.occurrence.occurrence_id != occurrence.occurrence_id
                      and item.state in ACTIVE_OCCURRENCE_STATES]
            all_active = [item for item in self.repo.occurrences()
                          if item.occurrence.occurrence_id != occurrence.occurrence_id
                          and item.state in ACTIVE_OCCURRENCE_STATES]
            owner = Owner.model_validate(pinned["owner"])
            def _same(item: OccurrenceProjection, field: str, value: str) -> bool:
                data = item.occurrence.pinned_launch_spec
                if field in {"principal_id", "custody_scope"}:
                    return str((data.get("owner") or {}).get(field)) == value
                return str((data.get("target") or {}).get(field)) == value
            hierarchical = (
                (len(all_active), int(os.environ.get("ARNOLD_RESIDENT_SCHEDULE_GLOBAL_MAX_ACTIVE", "32")), "global_concurrency_quota"),
                (sum(_same(item, "principal_id", owner.principal_id) for item in all_active),
                 int(os.environ.get("ARNOLD_RESIDENT_SCHEDULE_PRINCIPAL_MAX_ACTIVE", "4")), "principal_concurrency_quota"),
                (sum(_same(item, "custody_scope", owner.custody_scope) for item in all_active),
                 int(os.environ.get("ARNOLD_RESIDENT_SCHEDULE_CUSTODY_MAX_ACTIVE", "8")), "custody_concurrency_quota"),
                (sum(_same(item, "model", target.model) for item in all_active),
                 int(os.environ.get("ARNOLD_RESIDENT_SCHEDULE_MODEL_MAX_ACTIVE", "8")), "model_concurrency_quota"),
            )
            for used, cap, reason in hierarchical:
                if used >= cap:
                    return self._quota_breach(claim, policies, reason, worker_id)
            if len(active) >= min(policies.max_active, quota.max_concurrent_runs):
                return self._quota_breach(claim, policies, "schedule_concurrency_quota", worker_id)
            group = policies.concurrency_key
            if group:
                group_active = [
                    item for item in all_active
                    if str((item.occurrence.pinned_launch_spec.get("policies") or {}).get("concurrency_key")) == group
                ]
                if len(group_active) >= policies.max_active:
                    return self._quota_breach(claim, policies, "concurrency_group_quota", worker_id)
            if active and policies.overlap == "forbid":
                return self._finish_claim(claim, "suppressed", "overlap_forbidden", worker_id)
            if active and policies.overlap == "queue":
                age = now - occurrence.eligible_at
                if age > parse_duration(policies.maximum_queue_age):
                    return self._finish_claim(claim, "dead_letter", "overlap_queue_expired", worker_id)
                self.repo.transition(occurrence.occurrence_id, event="occurrence_requeued", actor=worker_id,
                                     expected_fence=fence, expected_token=token,
                                     changes={"state": "scheduled", "retry_at": now + timedelta(seconds=30),
                                              "claim_owner": None, "claim_token": None,
                                              "claim_expires_at": None, "decision": "overlap_queued"})
                return "retried"
            admitted = [item for item in self.repo.occurrences(occurrence.schedule_id)
                        if item.state in {"launch_committed", "launched", "terminal"}]
            day = [item for item in admitted if item.updated_at.date() == now.date()]
            hour = [item for item in admitted if now - item.updated_at <= timedelta(hours=1)]
            if quota.max_runs_per_day is not None and len(day) >= quota.max_runs_per_day:
                return self._quota_breach(claim, policies, "daily_run_quota", worker_id)
            if quota.max_runs_per_hour is not None and len(hour) >= quota.max_runs_per_hour:
                return self._quota_breach(claim, policies, "hourly_run_quota", worker_id)
            if (quota.maximum_cost_usd_per_day is not None
                    or quota.maximum_tokens_per_day is not None
                    or quota.maximum_tokens_per_occurrence is not None):
                return self._finish_claim(claim, "dead_letter", "accounting_unavailable_fail_closed", worker_id)
            schedule_context = {
                "schema_version": occurrence.schema_version,
                "schedule_id": occurrence.schedule_id,
                "schedule_revision": occurrence.schedule_revision,
                "generation": occurrence.generation,
                "occurrence_id": occurrence.occurrence_id,
                "occurrence_key": occurrence.occurrence_key,
                "nominal_at": occurrence.nominal_at.isoformat(),
                "authorization_digest": occurrence.authorization_digest,
                "pinned_definition_digest": occurrence.pinned_definition_digest,
            }
            if target.kind == "resident_orchestrator_turn" and target.operation == "probe":
                self.repo.transition(occurrence.occurrence_id, event="probe_committed", actor=worker_id,
                                     expected_fence=fence, expected_token=token,
                                     changes={"state": "terminal", "decision": "probe_no_external_effect",
                                              "claim_owner": None, "claim_token": None,
                                              "claim_expires_at": None})
                return "terminal"
            if target.kind == "resident_orchestrator_turn" and target.operation == "vp_todo_sweep":
                from arnold_pipelines.megaplan.store import (
                    FileStore, ScheduledJobInput, deterministic_idempotency_key,
                )
                store = FileStore(self.repo.root.parent)
                job = store.create_scheduled_job(
                    ScheduledJobInput(
                        job_type="vp_todo_sweep", scheduled_for=now,
                        payload={
                            "schedule_owned": True,
                            "schedule_occurrence": schedule_context,
                        },
                        max_attempts=RetryPolicy.model_validate(pinned["retry"]).launch_max_attempts,
                    ),
                    idempotency_key=deterministic_idempotency_key(
                        "resident-schedule-vp-turn", occurrence.occurrence_key
                    ),
                )
                self.repo.transition(
                    occurrence.occurrence_id, event="orchestrator_turn_committed", actor=worker_id,
                    expected_fence=fence, expected_token=token,
                    changes={"state": "launched", "run_id": f"scheduled-job:{job.id}",
                             "decision": "vp_todo_sweep_committed", "claim_owner": None,
                             "claim_token": None, "claim_expires_at": None},
                )
                return "launched"
            from .config import ResidentConfig
            from .subagent import launch_subagent_task
            task = target.prompt
            result = await launch_subagent_task(
                ResidentConfig.from_env(), task=task, description=target.description,
                project_dir=target.project_dir or str(self.project_root), model=target.model,
                task_kind=target.task_kind, work_intent=target.work_intent,
                request_id=occurrence.occurrence_id, launch_origin=authorization.launch_origin,
                depends_on_run_ids=target.dependencies or None,
                queue_max_launch_attempts=RetryPolicy.model_validate(pinned["retry"]).launch_max_attempts,
                schedule_context=schedule_context,
            )
            manifest_path = Path(result.manifest_path)
            manifest_digest = "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            self.repo.transition(occurrence.occurrence_id, event="launch_manifest_committed", actor=worker_id,
                                 expected_fence=fence, expected_token=token,
                                 changes={"state": "launch_committed", "run_id": result.run_id,
                                          "manifest_path": str(manifest_path),
                                          "manifest_digest": manifest_digest,
                                          "decision": "managed_launch_committed"})
            self.repo.transition(occurrence.occurrence_id, event="managed_run_linked", actor=worker_id,
                                 expected_fence=fence, expected_token=token,
                                 changes={"state": "launched", "claim_owner": None,
                                          "claim_token": None, "claim_expires_at": None})
            return "launched"
        except (PermissionError, ValueError) as exc:
            return self._finish_claim(claim, "dead_letter", str(exc), worker_id)
        except RuntimeError as exc:
            if "stale occurrence" in str(exc):
                return "retried"
            retry = RetryPolicy.model_validate(pinned["retry"])
            if claim.attempt >= retry.launch_max_attempts:
                return self._finish_claim(claim, "dead_letter", str(exc), worker_id)
            delay = min(parse_duration(retry.maximum_backoff),
                        parse_duration(retry.initial_backoff) * (2 ** max(0, claim.attempt - 1)))
            self.repo.transition(occurrence.occurrence_id, event="prelaunch_retry_scheduled", actor=worker_id,
                                 expected_fence=fence, expected_token=token,
                                 changes={"state": "scheduled", "retry_at": now + delay,
                                          "last_error": str(exc), "claim_owner": None,
                                          "claim_token": None, "claim_expires_at": None})
            return "retried"
        except Exception as exc:
            retry = RetryPolicy.model_validate(pinned["retry"])
            if claim.attempt >= retry.launch_max_attempts:
                return self._finish_claim(claim, "dead_letter", str(exc), worker_id)
            delay = min(parse_duration(retry.maximum_backoff),
                        parse_duration(retry.initial_backoff) * (2 ** max(0, claim.attempt - 1)))
            self.repo.transition(occurrence.occurrence_id, event="prelaunch_retry_scheduled", actor=worker_id,
                                 expected_fence=fence, expected_token=token,
                                 changes={"state": "scheduled", "retry_at": now + delay,
                                          "last_error": str(exc), "claim_owner": None,
                                          "claim_token": None, "claim_expires_at": None})
            return "retried"

    def _finish_claim(self, claim: OccurrenceProjection, state: OccurrenceState,
                      decision: str, actor: str) -> str:
        self.repo.transition(claim.occurrence.occurrence_id, event=f"occurrence_{state}", actor=actor,
                             expected_fence=claim.fence, expected_token=claim.claim_token,
                             changes={"state": state, "decision": decision,
                                      "last_error": decision if state == "dead_letter" else None,
                                      "claim_owner": None, "claim_token": None,
                                      "claim_expires_at": None})
        return "dead_lettered" if state == "dead_letter" else "suppressed"

    def _quota_breach(self, claim: OccurrenceProjection, policies: Policies,
                      decision: str, actor: str) -> str:
        if policies.quota_breach == "pause":
            definition = self.repo.read_definition(claim.occurrence.schedule_id)
            self.set_state(definition.schedule_id, "paused", if_revision=definition.revision,
                           actor=actor, audit_reason=decision)
        return self._finish_claim(claim, "suppressed", decision, actor)

    def reconcile_terminal_runs(self) -> int:
        reconciled = 0
        terminal = {"completed", "failed", "cancelled", "blocked", "interrupted"}
        with self.repo.locked():
            for projection in self.repo.occurrences():
                if projection.state not in {"launch_committed", "launched"}:
                    continue
                if projection.run_id and projection.run_id.startswith("scheduled-job:"):
                    from arnold_pipelines.megaplan.store import FileStore
                    job = FileStore(self.repo.root.parent).load_scheduled_job(
                        projection.run_id.removeprefix("scheduled-job:")
                    )
                    if job is None or job.status not in {"fired", "cancelled", "failed"}:
                        continue
                    state = "terminal" if job.status == "fired" else "dead_letter"
                    self.repo._transition_unlocked(
                        projection.occurrence.occurrence_id,
                        event="orchestrator_turn_terminal",
                        actor="resident-schedule-reconciler",
                        changes={"state": state, "decision": f"scheduled_job_{job.status}",
                                 "last_error": job.last_error},
                    )
                    reconciled += 1
                    continue
                if not projection.manifest_path:
                    continue
                try:
                    manifest = json.loads(Path(projection.manifest_path).read_text(encoding="utf-8"))
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
                if str(manifest.get("status")) not in terminal:
                    continue
                delivery = manifest.get("delivery") if isinstance(manifest.get("delivery"), Mapping) else {}
                self.repo._transition_unlocked(
                    projection.occurrence.occurrence_id, event="managed_run_terminal",
                    actor="resident-schedule-reconciler",
                    changes={"state": "terminal", "delivery_state": delivery.get("status"),
                             "decision": f"managed_run_{manifest.get('status')}"},
                )
                reconciled += 1
        return reconciled


def definition_from_file(path: Path) -> ScheduleDefinition:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return ScheduleDefinition.model_validate_json(text)
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise ValueError("YAML schedule files require PyYAML") from exc
    return ScheduleDefinition.model_validate(yaml.safe_load(text))


def schedule_store_root(store: object) -> Path | None:
    root = getattr(store, "root", None)
    return Path(root).resolve() if root is not None else None
