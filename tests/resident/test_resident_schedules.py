from __future__ import annotations

import asyncio
import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.resident.schedules import (
    ScheduleDefinition,
    ScheduleService,
    parse_cron,
)
from arnold_pipelines.megaplan.resident.cli import (
    _register_resident_subcommands,
    run_resident_cli,
)
from arnold_pipelines.megaplan.store import FileStore


NOW = datetime(2026, 7, 16, 18, 0, tzinfo=UTC)


def definition(
    *,
    schedule_id: str = "sched_test_foundation",
    timing: dict | None = None,
    state: str = "active",
    operation: str = "probe",
    kind: str = "resident_orchestrator_turn",
    policies: dict | None = None,
    quota: dict | None = None,
    bounds: dict | None = None,
    grant_id: str = "grant_test_v1",
) -> ScheduleDefinition:
    prompt = "Inspect the pinned evidence and report only."
    return ScheduleDefinition.model_validate(
        {
            "schema": "arnold-resident-schedule-v1",
            "schedule_id": schedule_id,
            "revision": 1,
            "generation": 1,
            "state": state,
            "owner": {"principal_id": "resident_role:test", "custody_scope": "tests"},
            "authorization": {
                "grant_id": grant_id,
                "source_envelope_digest": "sha256:" + "a" * 64,
                "approved_at": "2026-07-16T17:00:00Z",
                "expires_at": "2027-07-16T17:00:00Z",
                "maximum_work_intent": "review",
                "launch_origin": {"applicability": "not_applicable"},
                "route_ref": "inherited-source-route",
            },
            "schedule": timing
            or {"kind": "at", "at": NOW.isoformat(), "timezone": "UTC"},
            "bounds": bounds or {"max_occurrences": 1},
            "policies": {
                "misfire": "latest_once",
                "catch_up_limit": 1,
                "grace": "PT5M",
                "overlap": "forbid",
                "max_active": 1,
                **(policies or {}),
            },
            "target": {
                "kind": kind,
                "prompt_ref": "resident-prompt://test/v1",
                "prompt": prompt,
                "prompt_digest": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
                "model": "gpt-5.6-terra",
                "profile": "resident-subagent-standard",
                "toolsets": ["repo_read"],
                "work_intent": "review",
                "task_kind": "audit",
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
            "quota": quota or {"max_runs_per_day": 10, "max_concurrent_runs": 1},
            "created_at": "2026-07-16T17:00:00Z",
            "updated_at": "2026-07-16T17:00:00Z",
            "audit_reason": "test fixture",
        }
    )


def test_create_is_idempotent_and_conflicting_body_is_rejected(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row = definition()
    created, changed = service.create(row, idempotency_key="same")
    replay, replay_changed = service.create(row, idempotency_key="same")
    assert changed is True
    assert replay_changed is False
    assert replay == created

    changed_body = row.model_copy(update={"audit_reason": "different"})
    with pytest.raises(ValueError, match="different definition"):
        service.create(changed_body, idempotency_key="same")


def test_probe_occurrence_survives_restart_and_never_duplicate_fires(tmp_path: Path) -> None:
    first = ScheduleService(tmp_path)
    first.create(definition(), idempotency_key="probe")
    receipt = asyncio.run(first.run_due_once(now=NOW, worker_id="worker-a"))
    assert receipt.materialized == 1
    assert receipt.terminal == 1

    restarted = ScheduleService(tmp_path)
    replay = asyncio.run(restarted.run_due_once(now=NOW + timedelta(minutes=1), worker_id="worker-b"))
    assert replay.materialized == 0
    rows = restarted.repo.occurrences("sched_test_foundation")
    assert len(rows) == 1
    assert rows[0].state == "terminal"
    assert rows[0].decision == "probe_no_external_effect"


def test_interval_misfire_latest_once_is_fixed_rate_and_suppresses_older(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row = definition(
        timing={
            "kind": "interval",
            "every": "PT1H",
            "anchor_at": "2026-07-16T12:00:00Z",
            "cadence": "fixed_rate",
            "timezone": "UTC",
        },
        bounds={"max_occurrences": 20},
    ).model_copy(update={"created_at": datetime(2026, 7, 16, 11, 0, tzinfo=UTC)})
    service.create(row, idempotency_key="interval")
    receipt = service.materialize(now=NOW)
    projections = service.repo.occurrences(row.schedule_id)
    assert receipt.materialized == 7
    assert [item.occurrence.nominal_at.hour for item in projections] == list(range(12, 19))
    assert [item.occurrence.nominal_at.hour for item in projections if item.state == "scheduled"] == [17, 18]
    assert projections[-1].occurrence.nominal_at == NOW


def test_delay_is_normalized_once_to_an_at_instant(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row = definition(
        schedule_id="sched_delay_once",
        timing={
            "kind": "delay", "after": "PT45M",
            "accepted_at": "2026-07-16T17:00:00Z", "timezone": "UTC",
        },
    )
    created, _ = service.create(row, idempotency_key="delay")
    assert created.schedule.kind == "at"
    assert created.schedule.at == datetime(2026, 7, 16, 17, 45, tzinfo=UTC)
    assert created.schedule.after == "PT45M"


def test_stale_claim_is_recovered_with_a_higher_fence(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    service.create(definition(bounds={"max_occurrences": 2}), idempotency_key="lease")
    service.materialize(now=NOW)
    first = service.claim(worker_id="one", now=NOW, lease_seconds=10)[0]
    second = service.claim(worker_id="two", now=NOW + timedelta(seconds=11), lease_seconds=10)[0]
    assert second.fence == first.fence + 1
    assert second.claim_token != first.claim_token
    with pytest.raises(RuntimeError, match="stale occurrence fence"):
        service.repo.transition(
            first.occurrence.occurrence_id,
            event="stale_commit",
            actor="one",
            expected_fence=first.fence,
            expected_token=first.claim_token,
            changes={"state": "terminal"},
        )


def test_timing_update_increments_generation_and_cancels_unclaimed_old_occurrence(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    current, _ = service.create(definition(bounds={"max_occurrences": 5}), idempotency_key="revise")
    service.materialize(now=NOW)
    replacement = current.model_copy(
        update={
            "schedule": current.schedule.model_copy(
                update={"kind": "at", "at": NOW + timedelta(hours=2)}
            ),
            "audit_reason": "move future timing",
        }
    )
    revised = service.revise(current.schedule_id, replacement, if_revision=1)
    assert revised.revision == 2
    assert revised.generation == 2
    assert service.repo.occurrences(current.schedule_id)[0].state == "cancelled"
    with pytest.raises(ValueError, match="revision conflict"):
        service.revise(current.schedule_id, replacement, if_revision=1)


def test_pause_resume_and_cancel_are_optimistic_and_terminal(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row, _ = service.create(definition(state="draft"), idempotency_key="lifecycle")
    active = service.set_state(row.schedule_id, "active", if_revision=1, audit_reason="approved")
    paused = service.set_state(row.schedule_id, "paused", if_revision=2, audit_reason="operator pause")
    resumed = service.set_state(row.schedule_id, "active", if_revision=3, audit_reason="operator resume")
    cancelled = service.set_state(row.schedule_id, "cancelled", if_revision=4, audit_reason="finished")
    assert (active.state, paused.state, resumed.state, cancelled.state) == (
        "active", "paused", "active", "cancelled"
    )
    with pytest.raises(ValueError, match="terminal schedule"):
        service.set_state(row.schedule_id, "active", if_revision=5, audit_reason="invalid")


def test_cron_and_calendar_preview_use_iana_timezone_and_fold_policy(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    cron = definition(
        timing={
            "kind": "cron",
            "expression": "30 1 * * *",
            "grammar": "cron-5field-v1",
            "timezone": "America/New_York",
            "gap_policy": "skip",
            "fold_policy": "both",
        },
        bounds={"max_occurrences": 10},
    )
    start = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)
    preview = service.preview(cron, count=3, start=start)
    assert preview[:2] == [
        datetime(2026, 11, 1, 5, 30, tzinfo=UTC),
        datetime(2026, 11, 1, 6, 30, tzinfo=UTC),
    ]

    dublin = definition(
        schedule_id="sched_dublin_calendar",
        timing={
            "kind": "calendar",
            "local_time": "09:00:00",
            "days": ["monday"],
            "timezone": "Europe/Dublin",
            "gap_policy": "next_valid",
            "fold_policy": "first",
        },
        bounds={"max_occurrences": 2},
    )
    assert service.preview(
        dublin, count=1, start=datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    ) == [datetime(2026, 7, 20, 8, 0, tzinfo=UTC)]
    assert parse_cron("0 9 * * 1")
    posix_or = definition(
        schedule_id="sched_posix_cron_or",
        timing={
            "kind": "cron", "expression": "0 9 1 * 1",
            "timezone": "UTC", "gap_policy": "reject", "fold_policy": "first",
        },
        bounds={"max_occurrences": 3},
    )
    # Monday July 6 matches weekday even though it is not the first of month.
    assert service.preview(
        posix_or, count=1, start=datetime(2026, 7, 5, tzinfo=UTC)
    ) == [datetime(2026, 7, 6, 9, 0, tzinfo=UTC)]
    with pytest.raises(ValueError, match="five fields"):
        parse_cron("0 9 * *")


def test_event_selector_is_typed_predicated_and_deduplicated(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row = definition(
        timing={
            "kind": "event",
            "event_type": "megaplan.chain.terminal",
            "predicate": {"status": "failed"},
            "cooldown": "PT1M",
            "dedupe_key": "event_id",
            "timezone": "UTC",
        },
        bounds={"max_occurrences": 3},
    )
    service.create(row, idempotency_key="event")
    event = {"event_id": "evt_1", "event_type": "megaplan.chain.terminal", "status": "failed"}
    created = service.ingest_event(event, now=NOW)
    assert len(created) == 1
    assert service.ingest_event(event, now=NOW) == []
    assert service.ingest_event(
        {"event_id": "evt_2", "event_type": "megaplan.chain.terminal", "status": "complete"},
        now=NOW,
    ) == []


def test_managed_launch_copies_occurrence_context_and_reconciles_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ScheduleService(tmp_path, project_root=tmp_path)
    row = definition(
        operation="managed_launch", kind="resident_managed_agent",
        bounds={"max_occurrences": 1},
    )
    service.create(row, idempotency_key="launch")
    captured: dict = {}
    manifest = tmp_path / "managed-manifest.json"

    async def fake_launch(*args, **kwargs):
        captured.update(kwargs)
        manifest.write_text(json.dumps({"status": "launching", "delivery": {"status": "pending"}}))
        return SimpleNamespace(run_id="subagent-test", manifest_path=str(manifest), status="launching")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.subagent.launch_subagent_task", fake_launch
    )
    receipt = asyncio.run(service.run_due_once(now=NOW, worker_id="launcher"))
    assert receipt.launched == 1
    assert captured["schedule_context"]["occurrence_id"].startswith("occ_")
    assert captured["launch_origin"] == {"applicability": "not_applicable"}
    projection = service.repo.occurrences(row.schedule_id)[0]
    assert projection.run_id == "subagent-test"
    manifest.write_text(json.dumps({"status": "completed", "delivery": {"status": "delivered"}}))
    assert service.reconcile_terminal_runs() == 1
    projection = service.repo.occurrences(row.schedule_id)[0]
    assert projection.state == "terminal"
    assert projection.delivery_state == "delivered"


def test_orchestrator_occurrence_commits_one_schedule_owned_legacy_job(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row = definition(operation="vp_todo_sweep", kind="resident_orchestrator_turn")
    service.create(row, idempotency_key="vp-turn")
    receipt = asyncio.run(service.run_due_once(now=NOW, worker_id="vp-schedule"))
    assert receipt.launched == 1
    projection = service.repo.occurrences(row.schedule_id)[0]
    assert projection.run_id is not None
    job_id = projection.run_id.removeprefix("scheduled-job:")
    store = FileStore(tmp_path)
    job = store.load_scheduled_job(job_id)
    assert job is not None
    assert job.payload["schedule_owned"] is True
    assert job.payload["schedule_occurrence"]["occurrence_id"] == projection.occurrence.occurrence_id
    store.update_scheduled_job(job_id, status="fired", fired_at=NOW)
    assert service.reconcile_terminal_runs() == 1
    assert service.repo.occurrences(row.schedule_id)[0].state == "terminal"


def test_transient_launch_failure_retries_then_recovers_without_new_occurrence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ScheduleService(tmp_path, project_root=tmp_path)
    row = definition(operation="managed_launch", kind="resident_managed_agent")
    service.create(row, idempotency_key="retry")
    attempts = 0
    manifest = tmp_path / "retry-manifest.json"

    async def flaky(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary launch failure")
        manifest.write_text(json.dumps({"status": "launching"}))
        return SimpleNamespace(run_id="subagent-recovered", manifest_path=str(manifest), status="launching")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.subagent.launch_subagent_task", flaky
    )
    first = asyncio.run(service.run_due_once(now=NOW, worker_id="retry-worker"))
    assert first.retried == 1
    second = asyncio.run(
        service.run_due_once(now=NOW + timedelta(seconds=2), worker_id="retry-worker")
    )
    assert second.launched == 1
    rows = service.repo.occurrences(row.schedule_id)
    assert len(rows) == 1
    assert rows[0].attempt == 2
    assert rows[0].run_id == "subagent-recovered"


def test_unavailable_cost_accounting_fails_closed_into_dead_letter(tmp_path: Path) -> None:
    service = ScheduleService(tmp_path)
    row = definition(quota={"max_concurrent_runs": 1, "maximum_cost_usd_per_day": 1.0})
    service.create(row, idempotency_key="quota")
    receipt = asyncio.run(service.run_due_once(now=NOW, worker_id="quota-worker"))
    assert receipt.dead_lettered == 1
    dead = service.repo.occurrences(row.schedule_id)[0]
    assert dead.state == "dead_letter"
    assert dead.last_error == "accounting_unavailable_fail_closed"


def test_authorization_and_prompt_tampering_fail_validation() -> None:
    payload = definition().model_dump(mode="json", by_alias=True)
    payload["target"]["prompt_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="prompt_digest"):
        ScheduleDefinition.model_validate(payload)
    payload = definition().model_dump(mode="json", by_alias=True)
    payload["target"]["work_intent"] = "execution"
    with pytest.raises(ValueError, match="exceeds"):
        ScheduleDefinition.model_validate(payload)


def test_cli_create_list_run_and_occurrence_projection(tmp_path: Path) -> None:
    schedule_file = tmp_path / "schedule.json"
    schedule_file.write_text(
        json.dumps(definition().model_dump(mode="json", by_alias=True)), encoding="utf-8"
    )
    parser = argparse.ArgumentParser()
    _register_resident_subcommands(parser)
    store_root = tmp_path / "resident-store"

    create_args = parser.parse_args(
        ["schedule", "--store-root", str(store_root), "create", "--file", str(schedule_file),
         "--idempotency-key", "cli-create"]
    )
    created = run_resident_cli(tmp_path, create_args)
    assert created["success"] is True
    assert created["created"] is True

    run_args = parser.parse_args(
        ["schedule", "--store-root", str(store_root), "run-once", "--worker-id", "cli-test"]
    )
    receipt = run_resident_cli(tmp_path, run_args)
    assert receipt["receipt"]["terminal"] == 1

    occurrences_args = parser.parse_args(
        ["schedule", "--store-root", str(store_root), "occurrences", "sched_test_foundation"]
    )
    occurrences = run_resident_cli(tmp_path, occurrences_args)
    assert occurrences["count"] == 1
    assert occurrences["items"][0]["state"] == "terminal"
