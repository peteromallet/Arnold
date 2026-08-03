from __future__ import annotations

import json
import multiprocessing
import sqlite3
import threading
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import human_review_diagnostic as diagnostic
from arnold_pipelines.megaplan.cloud.incident_notification import IncidentNotificationStore


def _payload() -> dict[str, object]:
    return {
        "event": "cloud_watchdog_needs_human",
        "notification_kind": "stable_human_gate",
        "timestamp_utc": "2026-08-02T10:00:00+00:00",
        "session": "same-session",
        "summary": "manual_review halt",
        "plan": {"name": "same-plan", "current_state": "awaiting_human_verify"},
        "human_gate": {
            "state_token": "awaiting_human_verify",
            "reason": "same reason",
            "required_action": "answer the question",
        },
    }


def _marker() -> dict[str, object]:
    return {
        "session": "same-session",
        # Intentionally no resident_delegation: this is the deterministic
        # provenance-failure path and must never reach a provider.
    }


def _admit_process(root: str, result_path: str) -> None:
    with IncidentNotificationStore(root) as store:
        admission = store.admit(
            occurrence_id="gate-0123456789abcdef",
            session="same-session",
            state="awaiting_human_verify",
            payload=_payload(),
            marker=_marker(),
        )
        Path(result_path).write_text(
            json.dumps({"occurrence_id": admission.occurrence_id, "outbox_id": admission.outbox_id}),
            encoding="utf-8",
        )


def test_two_process_observers_and_200_scans_admit_one_intent(tmp_path: Path) -> None:
    root = tmp_path / "repair-data"
    root.mkdir()
    result_paths = [tmp_path / "p1.json", tmp_path / "p2.json"]
    ctx = multiprocessing.get_context("fork")
    processes = [ctx.Process(target=_admit_process, args=(str(root), str(path))) for path in result_paths]
    for process in processes:
        process.start()
    for process in processes:
        process.join(15)
        assert process.exitcode == 0

    with IncidentNotificationStore(root) as store:
        for _ in range(200):
            admission = store.admit(
                occurrence_id="gate-0123456789abcdef",
                session="same-session",
                state="awaiting_human_verify",
                payload=_payload(),
                marker=_marker(),
            )
            assert admission.duplicate is True
        rows = store.conn.execute("SELECT COUNT(*) FROM incident_occurrences").fetchone()
        assert rows == (1,)
        admission_projection = json.loads(result_paths[0].read_text())
        outbox = store.conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT outbox_id) FROM outbox_records"
        ).fetchone()
        assert outbox == (1, 1)
        assert admission_projection["outbox_id"] == store.conn.execute("SELECT outbox_id FROM outbox_records").fetchone()[0]


def test_missing_provenance_is_terminal_and_never_calls_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "workspace"
    project.mkdir()
    markers = tmp_path / "markers"
    repair_data = markers / "repair-data"
    repair_data.mkdir(parents=True)
    (markers / "same-session.json").write_text(json.dumps(_marker()), encoding="utf-8")
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({**_payload(), "workspace": str(project)}), encoding="utf-8")

    calls = 0

    async def provider_must_not_run(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("provider path reached before provenance terminal result")

    monkeypatch.setattr(diagnostic, "launch_subagent_task", provider_must_not_run)
    results = [
        diagnostic.launch_human_review_diagnostic(
            payload_path=payload_path,
            marker_dir=markers,
            repair_data_dir=repair_data,
            project_dir=project,
        )
        for _ in range(200)
    ]
    assert calls == 0
    assert {result.status for result in results} == {"provenance_failed"}
    assert {result.escalation_id for result in results} == {"gate-" + results[0].escalation_id[5:]}
    state = json.loads(Path(results[0].state_path).read_text(encoding="utf-8"))
    assert state["diagnostic_attempt_id"]
    assert state["notification_intent_id"]
    assert state["fallback_delivery"]["status"] == "not_permitted"
    with IncidentNotificationStore(repair_data) as custody:
        events = custody.conn.execute(
            "SELECT event_type FROM attempt_events WHERE attempt_id = ? ORDER BY sequence",
            (state["diagnostic_attempt_id"],),
        ).fetchall()
        assert events == [("started",), ("failed",)]
        assert custody.conn.execute("SELECT COUNT(*) FROM outbox_records").fetchone() == (1,)
    card = json.loads((Path(results[0].state_path).parent / "incident-card.json").read_text(encoding="utf-8"))
    assert card["state"] == "awaiting_human_verify"
    assert card["diagnostic_fixer_result"]["status"] == "provenance_failed"
    assert card["acknowledgement_resolution_projection"] == {
        "source": "canonical-incident-ledger",
        "status": "not_recorded",
    }


def test_thread_race_has_one_stable_occurrence(tmp_path: Path) -> None:
    root = tmp_path / "repair-data"
    root.mkdir()
    results: list[object] = []
    barrier = threading.Barrier(2)

    def run() -> None:
        barrier.wait()
        with IncidentNotificationStore(root) as store:
            results.append(
                store.admit(
                    occurrence_id="gate-0123456789abcdef",
                    session="same-session",
                    state="awaiting_human_verify",
                    payload=_payload(),
                    marker=_marker(),
                )
            )

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert len(results) == 2
    assert sum(not result.duplicate for result in results) == 1


def test_persistence_refusal_fails_closed_before_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "workspace"
    project.mkdir()
    markers = tmp_path / "markers"
    repair_data = markers / "repair-data"
    repair_data.mkdir(parents=True)
    (markers / "same-session.json").write_text(json.dumps(_marker()), encoding="utf-8")
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({**_payload(), "workspace": str(project)}), encoding="utf-8")
    provider_calls = 0

    async def provider_must_not_run(*args: object, **kwargs: object) -> None:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider path reached before durable intent")

    monkeypatch.setattr(diagnostic, "launch_subagent_task", provider_must_not_run)

    def refuse(*args: object, **kwargs: object) -> object:
        raise OSError("ENOSPC")

    monkeypatch.setattr(IncidentNotificationStore, "admit", refuse)
    result = diagnostic.launch_human_review_diagnostic(
        payload_path=payload_path,
        marker_dir=markers,
        repair_data_dir=repair_data,
        project_dir=project,
    )
    assert result.status == "persistence_failed"
    assert result.state_path
    assert result.fallback_delivery_required is False
    assert provider_calls == 0


def test_crash_after_atomic_intent_before_projection_replays_without_duplicate(tmp_path: Path) -> None:
    with IncidentNotificationStore(tmp_path) as first_store:
        first = first_store.admit(
            occurrence_id="gate-0123456789abcdef",
            session="same-session",
            state="awaiting_human_verify",
            payload=_payload(),
            marker=_marker(),
        )
        # Simulate a process dying before its JSON projection is written.
        assert first.duplicate is False
    with IncidentNotificationStore(tmp_path) as restarted_store:
        replay = restarted_store.admit(
            occurrence_id="gate-0123456789abcdef",
            session="same-session",
            state="awaiting_human_verify",
            payload=_payload(),
            marker=_marker(),
        )
        assert replay.duplicate is True
        assert restarted_store.conn.execute("SELECT COUNT(*) FROM outbox_records").fetchone() == (1,)


def test_restart_rebuilds_occurrence_projection_from_committed_event(tmp_path: Path) -> None:
    with IncidentNotificationStore(tmp_path) as store:
        admission = store.admit(
            occurrence_id="gate-0123456789abcdef",
            session="same-session",
            state="awaiting_human_verify",
            payload=_payload(),
            marker=_marker(),
        )
        store.conn.execute("DELETE FROM incident_occurrences")
        assert store.conn.execute("SELECT COUNT(*) FROM incident_occurrences").fetchone() == (0,)

    with IncidentNotificationStore(tmp_path) as restarted:
        replay = restarted.admit(
            occurrence_id="gate-0123456789abcdef",
            session="same-session",
            state="awaiting_human_verify",
            payload=_payload(),
            marker=_marker(),
        )
        assert replay.duplicate is True
        assert restarted.conn.execute(
            "SELECT occurrence_id, notification_intent_id FROM incident_occurrences"
        ).fetchone() == (admission.occurrence_id, admission.notification_intent_id)


def test_caller_owner_and_authority_inputs_are_not_admission_api(tmp_path: Path) -> None:
    with IncidentNotificationStore(tmp_path) as store:
        with pytest.raises(TypeError):
            store.admit(  # type: ignore[call-arg]
                occurrence_id="gate-0123456789abcdef",
                session="same-session",
                state="awaiting_human_verify",
                owner="forged-owner",
                payload=_payload(),
                marker=_marker(),
            )


def test_legacy_local_authority_and_provider_tables_are_migrated_away(tmp_path: Path) -> None:
    db_path = tmp_path / ".incident-notifications.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE incident_occurrences (occurrence_id TEXT PRIMARY KEY, diagnostic_attempt_id TEXT NOT NULL, notification_intent_id TEXT NOT NULL UNIQUE, state_version INTEGER NOT NULL, fingerprint TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, authority_state_json TEXT NOT NULL)"
    )
    conn.execute("CREATE TABLE notification_provider_attempts (provider_attempt_id TEXT)")
    conn.execute("CREATE TABLE incident_authority_transitions (transition_id TEXT)")
    conn.execute(
        "INSERT INTO incident_occurrences VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("occ-1", "attempt-1", "intent-1", 1, "fingerprint-1", "now", "forged"),
    )
    conn.commit()
    conn.close()

    with IncidentNotificationStore(tmp_path) as store:
        columns = {
            str(row[1])
            for row in store.conn.execute("PRAGMA table_info(incident_occurrences)").fetchall()
        }
        assert "authority_state_json" not in columns
        tables = {
            str(row[0])
            for row in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "notification_provider_attempts" not in tables
        assert "incident_authority_transitions" not in tables


def test_retired_cloud_intent_cannot_be_used_as_a_provider_authority(tmp_path: Path) -> None:
    with IncidentNotificationStore(tmp_path) as store:
        admission = store.admit(
            occurrence_id="gate-0123456789abcdef",
            session="same-session",
            state="awaiting_human_verify",
            payload=_payload(),
            marker=_marker(),
        )
        intent = store.canonical_intent(admission.notification_intent_id)
        assert intent["destination"] == "notification:discord.retired"
        assert intent["payload"]["dispatchable"] is False
        assert store.conn.execute("SELECT status FROM outbox_records").fetchone() == ("tombstoned",)
        with pytest.raises(ValueError, match="canonical outbox"):
            store.canonical_intent("forged-intent")


def test_authority_and_provider_mutators_are_retired() -> None:
    assert not hasattr(IncidentNotificationStore, "authority_transition")
    assert not hasattr(IncidentNotificationStore, "record_provider_attempt")
    assert not hasattr(IncidentNotificationStore, "record_provider_receipt")
    assert not hasattr(IncidentNotificationStore, "dispatch_eligible")


def test_production_notification_python_has_no_unbound_provider_api() -> None:
    production = (
        Path("arnold_pipelines/megaplan/cloud/incident_notification.py").read_text(encoding="utf-8")
        + Path("arnold_pipelines/megaplan/cloud/human_review_diagnostic.py").read_text(encoding="utf-8")
    )
    assert "def authority_transition" not in production
    assert "def record_provider_attempt" not in production
    assert "def record_provider_receipt" not in production
    assert "DISCORD_DM_BIN" not in production


def test_watchdog_source_has_no_provider_fallback() -> None:
    source = Path("arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog").read_text(encoding="utf-8")
    assert "arnold-discord-dm" not in source
    assert 'curl -fsS' not in source
    assert "write_opened(" not in source


def test_repair_loop_direct_notification_writer_is_retired() -> None:
    source = Path("arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop").read_text(
        encoding="utf-8"
    )
    assert "DISCORD_DM_BIN" not in source
    function = source.split("send_discord_escalation() {", 1)[1].split(
        'log "starting session=', 1
    )[0]
    assert "canonical_notification_outbox" in function
    assert "EscalationLedgerWriter" not in function
    assert "discord-payload" not in function
