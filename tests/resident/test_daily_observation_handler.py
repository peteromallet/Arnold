"""Focused T6.3 handler tests: the canonical daily-observer handoff.

Proves ``ResidentJobHandlers.handle_daily_observation`` is a pure CONSUMER
of the T2.1 authoritative claim/lease API
(``ScheduleService.claim`` / ``claim_superfixer_occurrence`` over the
``ScheduleRepository`` fence/claim-token CAS):

* schedule ownership: only an occurrence committed by T2.1 for THIS job and
  pinned to the ``daily_observation`` operation is ever consumed;
* foreign schedule IDs, cross-window leases, missing coordinates, and
  tampered bindings fail closed before custody is taken;
* concurrent/replayed wakeups join or no-op; terminal remains terminal;
* a runner failure retains a retryable claim (no release, no terminal
  write); a stale lease is reclaimed ONLY through T2.1's newer-fence CAS;
* terminalization stays with ``ScheduleService.reconcile_terminal_runs``;
  the handler's only write is the CAS-guarded custody release.

Every state-writing test uses an explicit disposable root proven not a
project/candidate/live runtime root.  Companion static negative-authority
evidence: ``tests/resident/test_daily_observation_negative_authority.py``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from uuid import uuid4
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident import scheduler as scheduler_module
from arnold_pipelines.megaplan.resident import schedules as schedules_module
from arnold_pipelines.megaplan.resident.cloud import CloudToolRequest, CloudToolResult
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.scheduler import (
    DAILY_OBSERVATION_LEASE_SECONDS,
    ResidentJobHandlers,
    ScheduledJobWorker,
    StoreScheduledJobBackend,
)
from arnold_pipelines.megaplan.store import FileStore

UTC = UTC
DAILY_NOW = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Disposable-root proof + fixtures
# ---------------------------------------------------------------------------


def _disposable_root(tmp_path: Path) -> Path:
    """Return and PROVE a test-only runtime root.

    The root must live inside pytest's per-test temp directory and must never
    be (or contain) this project checkout, the live ``.megaplan`` runtime
    state, a runtime-candidate root, or any megaplan worktree root.
    """
    root = tmp_path / "runtime"
    resolved = root.resolve()
    assert resolved.is_relative_to(tmp_path.resolve()), f"escaped pytest tmp: {resolved}"
    assert resolved != _PROJECT_ROOT
    assert not resolved.is_relative_to(_PROJECT_ROOT), (
        f"root is inside the project checkout: {resolved}"
    )
    assert ".megaplan-worktrees" not in resolved.parts
    assert "runtime-candidates" not in resolved.parts
    assert not (resolved / "arnold_pipelines" / "megaplan").exists()
    return root


class FakeCloudBackend:
    async def run(self, request: CloudToolRequest) -> CloudToolResult:  # pragma: no cover
        return CloudToolResult(classification="running", summary="unused", details={})


class RecordingRunner:
    """Injectable T6.2 daily-runner stand-in capturing the handoff."""

    def __init__(self, *, delay: float = 0.0, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.probe_results: list[bool] = []
        self._lock = threading.Lock()
        self._delay = delay
        self._error = error

    def __call__(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs)
        # The runner probes custody liveness under the handoff, exactly as
        # the T6.2 contract requires before any write boundary.
        if callable(kwargs.get("fence_check")):
            with self._lock:
                self.probe_results.append(bool(kwargs["fence_check"]()))
        if self._delay:
            import time

            time.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(status="appended")  # typed closure receipt stand-in


def _schedule_definition(
    *,
    schedule_id: str = "sched_daily_observation_test",
    operation: str = "daily_observation",
) -> schedules_module.ScheduleDefinition:
    prompt = "Read-only daily efficiency observation over provably closed windows."
    return schedules_module.ScheduleDefinition.model_validate(
        {
            "schema": "arnold-resident-schedule-v1",
            "schedule_id": schedule_id,
            "revision": 1,
            "generation": 1,
            "state": "active",
            "owner": {"principal_id": "resident_role:test", "custody_scope": "tests"},
            "authorization": {
                "grant_id": f"grant_{schedule_id}",
                "source_envelope_digest": "sha256:" + "a" * 64,
                "approved_at": "2026-08-20T00:00:00Z",
                "expires_at": "2027-08-20T00:00:00Z",
                "maximum_work_intent": "review",
                "launch_origin": {"applicability": "not_applicable"},
                "route_ref": "inherited-source-route",
            },
            "schedule": {"kind": "at", "at": DAILY_NOW.isoformat(), "timezone": "UTC"},
            "bounds": {"max_occurrences": 4},
            "policies": {
                "misfire": "latest_once",
                "catch_up_limit": 1,
                "grace": "PT5M",
                "overlap": "forbid",
                "max_active": 1,
            },
            "target": {
                "kind": "resident_orchestrator_turn",
                "prompt_ref": "resident-prompt://daily-observation/v1",
                "prompt": prompt,
                "prompt_digest": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
                "model": "hermes:deepseek:deepseek-v4-flash",
                "profile": "resident-subagent-standard",
                "toolsets": ["repo_read"],
                "work_intent": "review",
                "task_kind": "observation",
                "operation": operation,
            },
            "delivery": {
                "synthesis_owner": "schedule_root",
                "route_ref": "inherited-source-route",
                "mode": "exact_authorized_route",
            },
            "retry": {
                "launch_max_attempts": 3,
                "initial_backoff": "PT1S",
                "maximum_backoff": "PT1M",
            },
            "quota": {"max_runs_per_day": 10, "max_concurrent_runs": 1},
            "created_at": "2026-08-20T00:00:00Z",
            "updated_at": "2026-08-20T00:00:00Z",
            "audit_reason": "daily observer handoff test fixture",
        }
    )


class Fixture:
    """One committed schedule-owned daily-observation occurrence."""

    def __init__(self, tmp_path: Path, *, schedule_id: str) -> None:
        self.root = _disposable_root(tmp_path)
        self.store = FileStore(self.root / "store")
        self.service = schedules_module.ScheduleService(self.root / "store")
        self.definition = _schedule_definition(schedule_id=schedule_id)
        self.service.create(self.definition, idempotency_key=schedule_id)
        receipt = asyncio.run(
            self.service.run_due_once(now=DAILY_NOW, worker_id="daily-schedule")
        )
        assert receipt.launched == 1
        self.projection = self.service.repo.occurrences(schedule_id)[0]
        self.occurrence_id = self.projection.occurrence.occurrence_id
        self.occurrence_key = self.projection.occurrence.occurrence_key
        loaded_job = self.store.load_scheduled_job(
            str(self.projection.run_id).removeprefix("scheduled-job:")
        )
        assert loaded_job is not None
        self.job = loaded_job
        self.event_path = self.service.repo.transition_path(self.occurrence_id)
        self.events = self._events()
        self.event_count = len(self.events)

    def _events(self) -> list[dict]:
        return [json.loads(line) for line in self.event_path.read_text().splitlines()]

    @property
    def payload(self) -> dict:
        return self.job.model_dump(mode="json")

    def projection_now(self):
        claim = self.service.load_occurrence(self.occurrence_id)
        assert claim is not None
        return claim

    def persist_payload(self, payload: dict) -> None:
        """Corrupt/replace the PERSISTED job payload (the store is authoritative)."""
        self.store.update_scheduled_job(
            self.job.id,
            payload=payload,
            idempotency_key=f"t63-persist-{uuid4().hex}",
        )
        reloaded = self.store.load_scheduled_job(self.job.id)
        assert reloaded is not None
        self.job = reloaded

    def settle(self) -> int:
        """Mark the delivery fired and let T2.1 terminalize the occurrence."""
        self.store.update_scheduled_job(
            self.job.id,
            status="fired",
            fired_at=DAILY_NOW,
            idempotency_key=f"t63-settle-{uuid4().hex}",
        )
        return self.service.reconcile_terminal_runs()

    def handlers(self, runner, *, worker_id: str = "daily-consumer") -> ResidentJobHandlers:
        return ResidentJobHandlers(
            store=self.store,
            config=ResidentConfig(),
            cloud_backend=FakeCloudBackend(),
            worker_id=worker_id,
            daily_runner=runner,
        )

    def worker(self, runner, *, worker_id: str = "daily-consumer") -> ScheduledJobWorker:
        backend = StoreScheduledJobBackend(
            self.store, stale_after_seconds=900, batch_size=8
        )
        return ScheduledJobWorker(
            backend, handlers=self.handlers(runner, worker_id=worker_id).handlers(), worker_id=worker_id
        )


def _fixture(tmp_path: Path, *, schedule_id: str = "sched_daily_observation_test") -> Fixture:
    return Fixture(tmp_path, schedule_id=schedule_id)


def _patch_clock(monkeypatch: pytest.MonkeyPatch, value: datetime) -> dict:
    """Pin both modules' utc_now so backdated lease liveness is deterministic."""
    clock = {"value": value}
    monkeypatch.setattr(scheduler_module, "utc_now", lambda: clock["value"])
    monkeypatch.setattr(schedules_module, "utc_now", lambda: clock["value"])
    return clock


# ---------------------------------------------------------------------------
# Schedule ownership + T2.1 terminalization
# ---------------------------------------------------------------------------


def test_committed_occurrence_runs_runner_once_and_t21_terminalizes(tmp_path) -> None:
    fixture = _fixture(tmp_path)
    runner = RecordingRunner()
    worker = fixture.worker(runner)

    result = asyncio.run(worker.run_due_once(now=DAILY_NOW))
    assert result.fired == 1
    assert len(runner.calls) == 1

    call = runner.calls[0]
    custody = call["custody"]
    assert custody["schedule_id"] == fixture.definition.schedule_id
    assert custody["occurrence_id"] == fixture.occurrence_id
    assert custody["occurrence_key"] == fixture.occurrence_key
    assert custody["observation_only"] is True
    assert custody["claim"]["fence"] > fixture.projection.fence
    assert callable(call["fence_check"])
    # Probed DURING custody: the T2.1 re-read answered True under the claim.
    assert runner.probe_results == [True]

    released = fixture.projection_now()
    assert released.state == "launched"  # custody RELEASED via the T2.1 CAS
    assert released.decision == "daily_observation_completed"
    assert released.claim_owner is None
    assert released.attempt == fixture.projection.attempt + 1
    # Exactly TWO new events since the commit, both through the T2.1 CAS:
    # the one-shot claim and the single custody release.
    events = fixture._events()
    assert len(events) == fixture.event_count + 2
    assert events[-2]["event"] == "superfixer_occurrence_claimed"  # T2.1 CAS
    assert events[-1]["event"] == "daily_observation_completed"  # CAS release

    # Terminalization is T2.1's job, after the store marks the job fired.
    assert fixture.settle() == 1
    terminal = fixture.projection_now()
    assert terminal.state == "terminal"
    assert terminal.decision == "scheduled_job_fired"
    # The probe now honestly reports the lost custody.
    assert call["fence_check"]() is False


# ---------------------------------------------------------------------------
# Missing coordinates / foreign bindings fail closed
# ---------------------------------------------------------------------------


def _persisted_mutation(fixture: Fixture, mutate) -> dict:
    """Corrupt the PERSISTED job record; the handler trusts only the store."""
    payload = json.loads(json.dumps(fixture.payload))
    mutate(payload["payload"])
    fixture.persist_payload(payload["payload"])
    return fixture.payload


def test_missing_coordinates_fail_closed_before_any_custody(tmp_path) -> None:
    fixture = _fixture(tmp_path)
    runner = RecordingRunner()
    handlers = fixture.handlers(runner)

    def drop_owned(payload):
        payload.pop("schedule_owned")

    def drop_context(payload):
        payload.pop("schedule_occurrence")

    def drop_occurrence_id(payload):
        payload["schedule_occurrence"].pop("occurrence_id")

    def empty_key(payload):
        payload["schedule_occurrence"]["occurrence_key"] = ""

    original = json.loads(json.dumps(fixture.payload))
    for mutate in (drop_owned, drop_context, drop_occurrence_id, empty_key):
        corrupted = _persisted_mutation(fixture, mutate)
        with pytest.raises(ValueError, match="daily_observation"):
            asyncio.run(handlers.handle_daily_observation(corrupted))
        fixture.persist_payload(original["payload"])  # restore for next sub-case

    assert runner.calls == []
    claim = fixture.projection_now()
    assert claim.state == "launched"  # commit state; custody never taken
    assert claim.attempt == fixture.projection.attempt
    assert len(fixture._events()) == fixture.event_count


def test_foreign_schedule_and_tampered_bindings_fail_closed(tmp_path) -> None:
    fixture = _fixture(tmp_path)
    runner = RecordingRunner()
    handlers = fixture.handlers(runner)
    pristine = json.loads(json.dumps(fixture.payload))

    def expect_closed(exc_type, match, mutate):
        with pytest.raises(exc_type, match=match):
            asyncio.run(
                handlers.handle_daily_observation(_persisted_mutation(fixture, mutate))
            )
        fixture.persist_payload(pristine["payload"])  # clean base per sub-case

    # Tampered occurrence key: the PERSISTED record no longer matches the
    # occurrence in the schedule store.
    def tamper_key(payload):
        payload["schedule_occurrence"]["occurrence_key"] = "sha256:" + "f" * 64

    expect_closed(ValueError, "binding mismatch", tamper_key)

    # Unknown occurrence id in the persisted binding.
    def unknown_occurrence(payload):
        payload["schedule_occurrence"]["occurrence_id"] = "occ_missing"

    expect_closed(ValueError, "does not exist", unknown_occurrence)

    # Recurrence owner drifts from the bound schedule.
    def drift_owner(payload):
        payload["recurrence_owner"] = "sched_some_other_schedule"

    expect_closed(ValueError, "recurrence owner", drift_owner)

    # A corrupted record whose coordinates consistently point at a FOREIGN
    # schedule's occurrence still fails closed at the T2.1 job-binding CAS
    # (that occurrence's run_id belongs to a different job).
    other = Fixture(tmp_path, schedule_id="sched_daily_observation_foreign")

    def point_at_foreign(payload):
        context = other.payload["payload"]["schedule_occurrence"]
        payload["schedule_occurrence"] = dict(context)
        payload["recurrence_owner"] = other.definition.schedule_id

    expect_closed(RuntimeError, "not bound to job", point_at_foreign)

    assert runner.calls == []
    for f in (fixture, other):
        claim = f.projection_now()
        assert claim.state == "launched"
        assert claim.claim_owner is None
        assert len(f._events()) == f.event_count


def test_non_daily_pinned_operation_fails_closed(tmp_path) -> None:
    """A superfixer-owned occurrence can never be consumed by the observer."""
    root = _disposable_root(tmp_path)
    store = FileStore(root / "store")
    service = schedules_module.ScheduleService(root / "store")
    row = _schedule_definition(
        schedule_id="sched_superfixer_not_daily", operation="superfixer_proactive"
    )
    service.create(row, idempotency_key="sfx-not-daily")
    receipt = asyncio.run(service.run_due_once(now=DAILY_NOW, worker_id="daily-schedule"))
    assert receipt.launched == 1
    projection = service.repo.occurrences(row.schedule_id)[0]
    job = store.load_scheduled_job(str(projection.run_id).removeprefix("scheduled-job:"))
    assert job is not None

    runner = RecordingRunner()
    handlers = ResidentJobHandlers(
        store=store,
        config=ResidentConfig(),
        cloud_backend=FakeCloudBackend(),
        worker_id="daily-consumer",
        daily_runner=runner,
    )
    with pytest.raises(ValueError, match="not pinned to the daily_observation"):
        asyncio.run(handlers.handle_daily_observation(job.model_dump(mode="json")))
    assert runner.calls == []
    assert service.load_occurrence(projection.occurrence.occurrence_id).state == "launched"


# ---------------------------------------------------------------------------
# Concurrency / replay / terminal
# ---------------------------------------------------------------------------


def test_concurrent_wakeups_join_exactly_one_runner_run(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    _patch_clock(monkeypatch, DAILY_NOW)
    runner = RecordingRunner(delay=0.05)
    handlers = fixture.handlers(runner)
    payload = fixture.payload
    barrier = threading.Barrier(2)
    outcomes: list[tuple[str, str]] = []
    lock = threading.Lock()

    def deliver() -> None:
        barrier.wait()
        try:
            asyncio.run(handlers.handle_daily_observation(payload))
            outcome = ("ok", "")
        except Exception as exc:  # noqa: BLE001 - the loser must fail closed
            outcome = ("error", str(exc))
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=deliver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(kind for kind, _ in outcomes) == ["error", "ok"]
    loser_reason = next(reason for kind, reason in outcomes if kind == "error")
    assert "not claimable" in loser_reason
    assert len(runner.calls) == 1  # exactly one observation run, ever

    released = fixture.projection_now()
    assert released.state == "launched"  # winner released custody via the CAS
    assert released.decision == "daily_observation_completed"

    assert fixture.settle() == 1
    # Replayed wakeup after success: terminal remains terminal, no runner run.
    asyncio.run(handlers.handle_daily_observation(payload))
    assert len(runner.calls) == 1
    assert fixture.projection_now().state == "terminal"


def test_replayed_wakeup_after_success_is_noop_and_terminal_stays_terminal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    _patch_clock(monkeypatch, DAILY_NOW)
    runner = RecordingRunner()
    handlers = fixture.handlers(runner)

    asyncio.run(handlers.handle_daily_observation(fixture.payload))
    assert len(runner.calls) == 1
    assert fixture.settle() == 1
    events_after_success = fixture._events()

    for _ in range(2):
        asyncio.run(handlers.handle_daily_observation(fixture.payload))
    assert len(runner.calls) == 1
    assert fixture._events() == events_after_success
    assert fixture.projection_now().state == "terminal"


# ---------------------------------------------------------------------------
# Failure / retry: the claim is retained, never released
# ---------------------------------------------------------------------------


def test_runner_failure_retains_retryable_claim_and_store_job_retries(tmp_path) -> None:
    fixture = _fixture(tmp_path)
    runner = RecordingRunner(error=RuntimeError("runner boom"))
    worker = fixture.worker(runner)

    result = asyncio.run(worker.run_due_once(now=DAILY_NOW))
    assert result.fired == 0
    assert result.retried == 1

    # The claim is RETAINED: still held by this consumer, no release, no
    # dead-letter, no terminal write — the occurrence stays retryable.
    claim = fixture.projection_now()
    assert claim.state == "claimed"
    assert claim.claim_owner == "daily-consumer"
    assert claim.attempt == fixture.projection.attempt + 1
    events = fixture._events()
    assert len(events) == fixture.event_count + 1
    assert events[-1]["event"] == "superfixer_occurrence_claimed"
    assert events[-1]["changes"]["state"] == "claimed"

    job = fixture.store.load_scheduled_job(fixture.job.id)
    assert job.status == "pending"  # store-level retry machinery owns redelivery
    assert "runner boom" in (job.last_error or "")

    # A duplicate delivery while the lease is still live joins (fails closed
    # at the T2.1 CAS) instead of double-running.
    with pytest.raises(RuntimeError, match="not claimable"):
        asyncio.run(
            fixture.handlers(RecordingRunner()).handle_daily_observation(fixture.payload)
        )
    assert len(runner.calls) == 1


def test_stale_lease_reclaimed_only_through_t21_newer_fence(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    # A crashed consumer's claim, created with a backdated clock so its lease
    # has already expired relative to the handler's (patched) now.
    clock = _patch_clock(monkeypatch, DAILY_NOW)

    crashed = fixture.service.claim_superfixer_occurrence(
        fixture.occurrence_id,
        job_id=fixture.job.id,
        worker_id="crashed-consumer",
        now=DAILY_NOW,
        lease_seconds=1,
    )
    assert crashed.claim_owner == "crashed-consumer"

    clock["value"] = DAILY_NOW + timedelta(seconds=DAILY_OBSERVATION_LEASE_SECONDS + 5)
    runner = RecordingRunner()
    asyncio.run(fixture.handlers(runner).handle_daily_observation(fixture.payload))

    assert len(runner.calls) == 1
    reclaimed = fixture.projection_now()
    assert reclaimed.state == "launched"  # handler released after the run
    assert reclaimed.decision == "daily_observation_completed"
    assert reclaimed.attempt == crashed.attempt + 1
    assert reclaimed.fence > crashed.fence  # newer fence: T2.1 reclaim CAS
    events = fixture._events()
    # T2.1's STALE-reclaim event name proves the reclaim went through the
    # T2.1 CAS (newer fence), never through handler-local lease logic.
    assert events[-2]["event"] == "occurrence_reclaimed"
    assert events[-1]["event"] == "daily_observation_completed"
    reclaim_events = [e for e in events if e["event"] == "occurrence_reclaimed"]
    assert len(reclaim_events) == 1


# ---------------------------------------------------------------------------
# Cross-window leases fail closed without leaking
# ---------------------------------------------------------------------------


def test_cross_window_lease_holds_fail_closed_without_leaking(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window_a = _fixture(tmp_path, schedule_id="sched_daily_window_a")
    window_b = _fixture(tmp_path, schedule_id="sched_daily_window_b")

    # A foreign holder owns window B with a LIVE lease (patched clock).
    _patch_clock(monkeypatch, DAILY_NOW)

    live = window_b.service.claim_superfixer_occurrence(
        window_b.occurrence_id,
        job_id=window_b.job.id,
        worker_id="cross-window-holder",
        now=DAILY_NOW,
        lease_seconds=600,
    )
    assert live.claim_owner == "cross-window-holder"

    runner = RecordingRunner()
    handlers_a = window_a.handlers(runner, worker_id="daily-consumer")
    handlers_b = window_b.handlers(runner, worker_id="daily-consumer")

    # Delivering window B while the foreign lease is live fails closed.
    with pytest.raises(RuntimeError, match="not claimable"):
        asyncio.run(handlers_b.handle_daily_observation(window_b.payload))

    # Window A is independent: it claims and runs under its own fence.
    asyncio.run(handlers_a.handle_daily_observation(window_a.payload))
    assert len(runner.calls) == 1
    assert runner.calls[0]["custody"]["schedule_id"] == "sched_daily_window_a"

    # The foreign lease was never disturbed by window A's run.
    held = window_b.projection_now()
    assert held.state == "claimed"
    assert held.claim_owner == "cross-window-holder"
    assert held.fence == live.fence
    assert held.attempt == live.attempt
    assert len(window_b._events()) == window_b.event_count + 1


# ---------------------------------------------------------------------------
# Withdrawn schedule custody: no-op without any write
# ---------------------------------------------------------------------------


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_cancelled_schedule_delivery_noops_with_byte_identical_store(tmp_path) -> None:
    fixture = _fixture(tmp_path)
    fixture.service.set_state(
        fixture.definition.schedule_id,
        "cancelled",
        if_revision=fixture.definition.revision,
        actor="operator",
        audit_reason="withdrawn",
    )
    before = _tree_digest(fixture.root)

    runner = RecordingRunner()
    asyncio.run(fixture.handlers(runner).handle_daily_observation(fixture.payload))

    assert runner.calls == []
    assert _tree_digest(fixture.root) == before  # byte-for-byte: no write at all
