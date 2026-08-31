from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from arnold_pipelines.megaplan.cloud.controlled_final_launch import ControlledFinalLaunch
from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerAdmissionReceipt
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome

from tests.cloud.dispatch_test_helpers import request


WORKER = {"host": "host", "pid": 123, "boot_id": "boot"}


def test_native_timeout_teardown_records_and_reaps_sleep(tmp_path: Path) -> None:
    """The native timeout door cannot return with its admitted child alive."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.workers._impl import (
        _LOCAL_SPAWN_CONTROL,
        _native_signal_ladder,
        _spawn_registration_for_process,
    )

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/sleep", "10"])
    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        adapter._persist(
            "accepted",
            worker_identity=registration["worker_identity"],
            started_at=registration["started_at"],
            finished_at=registration["started_at"],
            victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
        )
        token = _LOCAL_SPAWN_CONTROL.set(adapter.spawn_control)
        try:
            assert _native_signal_ladder(process, cause_kind="timeout") is True
        finally:
            _LOCAL_SPAWN_CONTROL.reset(token)
        assert process.poll() is not None
        dispositions = ledger.projection()["dispositions"]
        assert len(dispositions) == 1
        term = next(iter(dispositions.values()))
        assert term["signal"] == "SIGTERM"
        assert term["ladder_step"] == "term"
        assert term["timeout_source"] == "native-timeout"
        assert ledger.projection()["terminals"]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_native_timeout_replays_kill_claim_into_terminal(tmp_path: Path, monkeypatch) -> None:
    """A crash after KILL must recover one terminal without resending KILL."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident import disposition
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/bash", "-c", 'trap "" TERM; sleep 30'])
    original_terminal = disposition._ladder_terminal
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated crash before terminal projection")
        return original_terminal(*args, **kwargs)

    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        adapter._persist(
            "accepted",
            worker_identity=registration["worker_identity"],
            started_at=registration["started_at"],
            finished_at=registration["started_at"],
            victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
        )
        monkeypatch.setattr(disposition, "_ladder_terminal", fail_once)
        first = adapter.immediate_timeout(process)
        assert first["state"] == "unresolved"
        assert process.poll() is not None
        monkeypatch.setattr(disposition, "_ladder_terminal", original_terminal)
        second = adapter.immediate_timeout(process)
        assert second["state"] == "killed"
        assert len(ledger.projection()["dispositions"]) == 2
        assert len(ledger.projection()["terminals"]) == 1
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_native_timeout_identity_mismatch_blocks_term_before_claim(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.watchdog import worker_identity
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/sleep", "30"])
    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        adapter._persist(
            "accepted", worker_identity=registration["worker_identity"],
            started_at=registration["started_at"], finished_at=registration["started_at"],
            victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
        )
        monkeypatch.setattr(worker_identity, "read_process_start_identity", lambda _pid: "reused-incarnation")
        result = adapter.immediate_timeout(process)
        assert result["state"] == "unresolved"
        assert process.poll() is None
        assert ledger.projection()["dispositions"] == {}
        assert ledger.projection()["terminals"] == {}
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_native_timeout_kill_identity_mismatch_does_not_send_kill(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.watchdog import worker_identity
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/bash", "-c", 'trap "" TERM; sleep 30'])
    sent: list[int] = []
    original_send = process.send_signal
    process.send_signal = lambda number: (sent.append(number), original_send(number))[1]
    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        adapter._persist(
            "accepted", worker_identity=registration["worker_identity"],
            started_at=registration["started_at"], finished_at=registration["started_at"],
            victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
        )
        expected = registration["worker_identity"]["process_start_identity"]
        identities = iter((expected, expected, expected, "reused-incarnation"))
        monkeypatch.setattr(worker_identity, "read_process_start_identity", lambda _pid: next(identities))
        result = adapter.immediate_timeout(process)
        assert result["state"] == "unresolved"
        assert sent == [15]
        assert process.poll() is None
        dispositions = ledger.projection()["dispositions"]
        assert any(item.get("ladder_step") == "term" for item in dispositions.values())
        assert not any(item.get("ladder_step") == "kill" for item in dispositions.values())
        assert ledger.projection()["terminals"] == {}
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_signal_ladder_rejects_wrong_process_handle_before_poll_or_signal(tmp_path: Path) -> None:
    ledger, adapter, admitted, _registration = _accepted_sleep_adapter(tmp_path)
    other = subprocess.Popen(["/bin/sleep", "30"])
    sent: list[int] = []
    original_send = other.send_signal
    other.send_signal = lambda number: (sent.append(number), original_send(number))[1]
    try:
        result = adapter.signal_ladder(other, cause_kind="timeout")
        assert result["state"] == "unresolved"
        assert admitted.poll() is None
        assert other.poll() is None
        assert sent == []
        assert ledger.projection()["dispositions"] == {}
        assert ledger.projection()["terminals"] == {}
    finally:
        for process in (admitted, other):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)


def test_immediate_timeout_rejects_wrong_process_handle_before_poll_or_signal(tmp_path: Path) -> None:
    ledger, adapter, admitted, _registration = _accepted_sleep_adapter(tmp_path)
    other = subprocess.Popen(["/bin/sleep", "30"])
    sent: list[int] = []
    original_send = other.send_signal
    other.send_signal = lambda number: (sent.append(number), original_send(number))[1]
    try:
        result = adapter.immediate_timeout(other)
        assert result["state"] == "unresolved"
        assert admitted.poll() is None
        assert other.poll() is None
        assert sent == []
        assert ledger.projection()["dispositions"] == {}
        assert ledger.projection()["terminals"] == {}
    finally:
        for process in (admitted, other):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=2)


def test_production_accepted_outcome_requires_child_process_start_token(tmp_path: Path) -> None:
    from dataclasses import replace
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = replace(
        require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger)),
        production_intent=True,
    )
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    value = DispatchOutcome(
        kind="success", launch_state="accepted", plan_id=receipt.plan_id,
        phase=receipt.phase, dispatch_family_id=receipt.dispatch_family_id,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        selected_spec=receipt.normalized_spec,
        worker_identity={"host": "host", "pid": 123, "boot_id": "boot"},
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    with pytest.raises(TypeError, match="child process-start identity"):
        adapter.run(lambda _context: value)
    assert not any(
        event["payload"].get("launch_state_identity") == "accepted"
        for event in ledger.read_nbf_events()
        if event["payload"].get("event_type") == "controlled_adapter_state"
    )


def test_native_timeout_links_predead_observation_once(tmp_path: Path) -> None:
    """A pre-timeout exit closes through observation, never a signal claim."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/sleep", "0.01"])
    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        adapter._persist(
            "accepted",
            worker_identity=registration["worker_identity"],
            started_at=registration["started_at"],
            finished_at=registration["started_at"],
            victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
        )
        process.wait(timeout=2)
        first = adapter.immediate_timeout(process)
        before_replay = len(ledger.read_nbf_events())
        second = adapter.immediate_timeout(process)
        assert first["state"] == second["state"] == "already_dead"
        assert first["observation"]["payload"]["observation_id"]
        assert second["replayed"] is True
        assert len(ledger.read_nbf_events()) == before_replay
        assert len(ledger.projection()["terminals"]) == 1
        reservation = next(iter(ledger.projection()["reservations"].values()))
        assert reservation["closed"] is True
        assert not ledger.projection()["dispositions"]
        assert not any(
            event["payload"].get("event_type") == "signal_claimed"
            for event in ledger.read_nbf_events()
        )
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
def test_native_timeout_replay_does_not_attribute_unclaimed_disposition(tmp_path: Path, monkeypatch) -> None:
    """A disposition without its pre-signal claim is intent, not a signal."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/sleep", "30"])
    original_locked_door = ledger.record_claim_signal_locked

    def fail_term_claim(disposition, *, signal, signal_fn, preflight=None, actor="signal-authority"):
        if signal == "SIGTERM":
            raise OSError("simulated crash before signal claim")
        return original_locked_door(
            disposition, signal=signal, signal_fn=signal_fn,
            preflight=preflight, actor=actor,
        )

    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        adapter._persist(
            "accepted",
            worker_identity=registration["worker_identity"],
            started_at=registration["started_at"],
            finished_at=registration["started_at"],
            victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
        )
        monkeypatch.setattr(ledger, "record_claim_signal_locked", fail_term_claim)
        first = adapter.immediate_timeout(process)
        assert first["state"] == "unresolved"
        assert ledger.projection()["terminals"] == {}
        process.kill()
        process.wait(timeout=2)
        monkeypatch.setattr(ledger, "record_claim_signal_locked", original_locked_door)
        second = adapter.immediate_timeout(process)
        assert second["state"] == "already_dead"
        assert second["observation"]["payload"]["observation_id"]
        assert len(ledger.projection()["terminals"]) == 1
        assert next(iter(ledger.projection()["terminals"].values()))["outcome_kind"] == "ordinary_terminal_failure"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def _accepted_sleep_adapter(tmp_path: Path, seconds: str = "30"):
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/sleep", seconds])
    registration = _spawn_registration_for_process(process)
    adapter.spawn_control.register(registration)
    adapter._persist(
        "accepted",
        worker_identity=registration["worker_identity"],
        started_at=registration["started_at"],
        finished_at=registration["started_at"],
        victim_process_start_identity=registration["worker_identity"]["process_start_identity"],
    )
    return ledger, adapter, process, registration


def test_spawn_cleanup_handoff_is_identity_bound_and_replay_safe(tmp_path: Path) -> None:
    ledger, adapter, process, registration = _accepted_sleep_adapter(tmp_path)
    registration["spawn_certification_id"] = "certification-1"
    adapter.registered_child["spawn_certification_id"] = "certification-1"
    try:
        first = adapter.spawn_control.handoff_spawn_cleanup(
            process,
            error=RuntimeError("supervisor unwound"),
            reason="dispatch exception escaped",
            route_identity="codex:gpt-5.5",
        )
        event_count = len(ledger.read_nbf_events())
        second = adapter.spawn_control.handoff_spawn_cleanup(
            process,
            error=RuntimeError("same unwind replay"),
            reason="dispatch exception escaped",
            route_identity="codex:gpt-5.5",
        )
        assert first["state"] == second["state"] == "cleanup_hold"
        assert first["handoff"] == second["handoff"]
        assert len(ledger.read_nbf_events()) == event_count
        handoff = first["handoff"]
        assert handoff["admission_receipt_id"] == adapter.receipt.admission_receipt_id
        assert handoff["semantic_dispatch_fingerprint"] == adapter.receipt.semantic_dispatch_fingerprint
        assert handoff["worker_identity"] == registration["worker_identity"]
        assert handoff["victim_pid"] == process.pid
        assert handoff["victim_process_start_identity"] == registration["worker_identity"]["process_start_identity"]
        assert handoff["spawn_certification_id"] == "certification-1"
        assert handoff["route_identity"] == "codex:gpt-5.5"
        assert ledger.projection()["cleanup_handoffs"]
        assert not ledger.projection()["terminals"]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_spawn_cleanup_handoff_reconciles_natural_death_or_permanent_hold(tmp_path: Path) -> None:
    ledger, adapter, process, _registration = _accepted_sleep_adapter(tmp_path)
    try:
        handoff = adapter.handoff_spawn_cleanup(process, reason="cleanup callback lost")
        assert handoff["state"] == "cleanup_hold"
        assert adapter.reconcile_spawn_cleanup(process, resolution="natural_death")["state"] == "cleanup_hold"
        process.kill()
        process.wait(timeout=2)
        resolved = adapter.reconcile_spawn_cleanup(process, resolution="natural_death")
        assert resolved["state"] == "already_dead"
        assert len(ledger.projection()["terminals"]) == 1
        assert ledger.projection()["reservations"]
        assert next(iter(ledger.projection()["reservations"].values()))["closed"] is True
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)

    ledger2, adapter2, process2, _registration2 = _accepted_sleep_adapter(tmp_path / "hold")
    try:
        assert adapter2.handoff_spawn_cleanup(process2)["state"] == "cleanup_hold"
        held = adapter2.reconcile_spawn_cleanup(
            process2,
            resolution="permanent_hold",
            reason="custody cannot revalidate child",
        )
        assert held["state"] == "permanent_hold"
        assert held["reconciliation"]["resolution"] == "permanent_hold_ambiguous"
        replay = adapter2.reconcile_spawn_cleanup(
            process2, resolution="permanent_hold", reason="different retry wording"
        )
        assert replay["state"] == "permanent_hold"
        assert replay["replayed"] is True
        assert replay["reconciliation"] == held["reconciliation"]
        assert not ledger2.projection()["terminals"]
        assert next(iter(ledger2.projection()["reservations"].values()))["closed"] is False
    finally:
        if process2.poll() is None:
            process2.kill()
        process2.wait(timeout=2)


def test_spawn_cleanup_restart_reconciles_dead_child_without_handle(tmp_path: Path) -> None:
    ledger, adapter, process, _registration = _accepted_sleep_adapter(tmp_path)
    try:
        handoff = adapter.handoff_spawn_cleanup(process)
        assert handoff["state"] == "cleanup_hold"
        # Simulate a supervisor restart: only the durable PID/start evidence
        # remains, so reconciliation must not require a Popen handle.
        adapter._custody_process = None
        process.kill()
        process.wait(timeout=2)
        resolved = adapter.reconcile_spawn_cleanup(
            None, resolution="natural_death", handoff_id=handoff["handoff"]["handoff_id"]
        )
        assert resolved["state"] == "already_dead"
        assert len(ledger.projection()["terminals"]) == 1
        assert not ledger.projection()["dispositions"]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_spawn_cleanup_preacceptance_death_is_held_without_terminal(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.workers._impl import _spawn_registration_for_process

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    adapter._persist("entered")
    process = subprocess.Popen(["/bin/sleep", "30"])
    try:
        registration = _spawn_registration_for_process(process)
        adapter.spawn_control.register(registration)
        handoff = adapter.handoff_spawn_cleanup(process)
        process.kill()
        process.wait(timeout=2)
        result = adapter.reconcile_spawn_cleanup(
            None, resolution="natural_death", handoff_id=handoff["handoff"]["handoff_id"]
        )
        assert result["state"] == "permanent_hold"
        assert not ledger.projection()["terminals"]
        assert not ledger.projection()["dispositions"]
        assert next(iter(ledger.projection()["reservations"].values()))["closed"] is False
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_spawn_cleanup_pid_reuse_is_permanent_hold_without_signal(tmp_path: Path, monkeypatch) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.watchdog import worker_identity

    ledger, adapter, process, _registration = _accepted_sleep_adapter(tmp_path)
    try:
        handoff = adapter.handoff_spawn_cleanup(process)
        monkeypatch.setattr(worker_identity, "read_process_start_identity", lambda _pid: "reused-incarnation")
        result = adapter.reconcile_spawn_cleanup(
            process, resolution="natural_death", handoff_id=handoff["handoff"]["handoff_id"]
        )
        assert result["state"] == "permanent_hold"
        assert process.poll() is None
        assert not ledger.projection()["terminals"]
        assert not ledger.projection()["dispositions"]
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_spawn_cleanup_wrapper_unwraps_and_retains_process_handle(tmp_path: Path) -> None:
    from types import SimpleNamespace

    ledger, adapter, process, _registration = _accepted_sleep_adapter(tmp_path)
    hold = SimpleNamespace(
        process=process,
        spawn_event_id="local-spawn-event",
        dispatch_outcome={"kind": "unresolved_launch", "reconciliation_event_id": "local-spawn-event"},
        to_dict=lambda: {"state": "cleanup_hold", "pid": process.pid, "metadata": "retained"},
    )
    try:
        result = adapter.spawn_control.handoff_spawn_cleanup(hold)
        assert result["state"] == "cleanup_hold"
        assert result["handoff_id"] == result["event_id"]
        assert result["handoff_id"] == result["handoff"]["handoff_id"]
        assert result["hold_metadata"]["metadata"] == "retained"
        assert adapter._custody_process is process
        assert hold.spawn_event_id == result["handoff_id"]
        assert hold.dispatch_outcome["reconciliation_event_id"] == result["handoff_id"]
        process.kill()
        process.wait(timeout=2)
        assert adapter._custody_process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_spawn_cleanup_natural_death_replay_returns_exact_event(tmp_path: Path) -> None:
    ledger, adapter, process, _registration = _accepted_sleep_adapter(tmp_path)
    try:
        handoff = adapter.handoff_spawn_cleanup(process)
        process.kill()
        process.wait(timeout=2)
        first = adapter.reconcile_spawn_cleanup(None, resolution="natural_death", handoff_id=handoff["handoff_id"])
        count = len(ledger.read_nbf_events())
        second = adapter.reconcile_spawn_cleanup(None, resolution="natural_death", handoff_id=handoff["handoff_id"])
        assert first["state"] == second["state"] == "already_dead"
        assert second["replayed"] is True
        assert second["terminal_outcome"] == first["terminal_outcome"]
        assert second["observation"] == first["observation"]
        assert len(ledger.read_nbf_events()) == count
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_controlled_launch_returns_typed_unresolved_custody_outcome(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import _unresolved_outcome, require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    unresolved = _unresolved_outcome(receipt)
    result = adapter.run(lambda _context: unresolved)
    assert result is unresolved
    assert result.kind == "unresolved_launch"
    assert adapter.state == "entered"
    assert [event["payload"]["launch_state_identity"] for event in ledger.read_nbf_events() if event["payload"].get("event_type") == "controlled_adapter_state"] == ["not_started", "entered"]


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("plan_id", "other-plan"),
        ("phase", "review"),
        ("dispatch_family_id", "other-family"),
        ("logical_dispatch_id", "other-logical"),
        ("admission_receipt_id", "other-receipt"),
        ("semantic_dispatch_fingerprint", "f" * 64),
        ("selected_spec", "other:gpt"),
    ],
)
def test_unresolved_launch_rejects_cross_reservation_context(
    tmp_path: Path, field: str, bad_value: str,
) -> None:
    from dataclasses import replace
    from arnold_pipelines.megaplan.cloud.worker_dispatch import _unresolved_outcome, require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    unresolved = replace(_unresolved_outcome(receipt), **{field: bad_value})
    with pytest.raises(ValueError, match=rf"dispatch outcome context mismatch: {field}"):
        adapter.run(lambda _context: unresolved)
    assert adapter.state == "entered"
    assert not ledger.projection()["terminals"]
    assert not any(
        event["payload"].get("launch_state_identity") == "accepted"
        for event in ledger.read_nbf_events()
        if event["payload"].get("event_type") == "controlled_adapter_state"
    )


def test_cleanup_wrong_dead_handle_cannot_false_death_live_victim(tmp_path: Path) -> None:
    """A dead handle for another PID cannot replace custody or close the victim."""
    ledger, adapter, victim, _registration = _accepted_sleep_adapter(tmp_path)
    wrong = subprocess.Popen(["/bin/sleep", "0.01"])
    try:
        wrong.wait(timeout=2)
        handoff = adapter.handoff_spawn_cleanup(wrong)
        assert handoff["state"] == "cleanup_hold"
        assert handoff["pid_start_identity_valid"] is False
        assert adapter._custody_process is None
        result = adapter.reconcile_spawn_cleanup(
            wrong, resolution="natural_death", handoff_id=handoff["handoff_id"]
        )
        assert result["state"] == "cleanup_hold"
        assert victim.poll() is None
        assert not ledger.projection()["terminals"]
        assert not ledger.projection()["dispositions"]
    finally:
        if victim.poll() is None:
            victim.kill()
        victim.wait(timeout=2)
        if wrong.poll() is None:
            wrong.kill()
        wrong.wait(timeout=2)


def test_invalid_later_handle_preserves_lawful_retained_custody(tmp_path: Path) -> None:
    """A bad B handle cannot evict already validated A custody."""
    ledger, adapter, victim, _registration = _accepted_sleep_adapter(tmp_path)
    wrong = subprocess.Popen(["/bin/sleep", "0.01"])
    try:
        first = adapter.handoff_spawn_cleanup(victim)
        assert first["state"] == "cleanup_hold"
        assert adapter._custody_process is victim
        wrong.wait(timeout=2)
        second = adapter.handoff_spawn_cleanup(wrong)
        assert second["state"] == "cleanup_hold"
        assert second["pid_start_identity_valid"] is False
        assert adapter._custody_process is victim
        result = adapter.reconcile_spawn_cleanup(
            wrong, resolution="natural_death", handoff_id=first["handoff_id"]
        )
        assert result["state"] == "cleanup_hold"
        assert adapter._custody_process is victim
        assert victim.poll() is None
        assert not ledger.projection()["terminals"]
    finally:
        if victim.poll() is None:
            victim.kill()
        victim.wait(timeout=2)
        if wrong.poll() is None:
            wrong.kill()
        wrong.wait(timeout=2)


@pytest.mark.parametrize("resolution", ["natural_death", "permanent_hold"])
def test_adapter_cannot_reconcile_another_adapters_handoff(
    tmp_path: Path, resolution: str,
) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger, adapter1, process, _registration = _accepted_sleep_adapter(tmp_path)
    try:
        handoff = adapter1.handoff_spawn_cleanup(process)
        receipt2 = require_production_worker_dispatch_runtime(
            request(
                tmp_path, ledger=ledger, logical_dispatch_id="other-logical",
                projection_key="other-projection",
            )
        )
        adapter2 = ControlledFinalLaunch(receipt2, ledger=ledger)
        before = len(ledger.read_nbf_events())
        result = adapter2.reconcile_spawn_cleanup(
            None, resolution=resolution, handoff_id=handoff["handoff_id"]
        )
        assert result["state"] == "unresolved"
        assert "another admission" in result["reason"]
        assert len(ledger.read_nbf_events()) == before
        assert not ledger.projection()["terminals"]
        reservation1 = next(
            value for value in ledger.projection()["reservations"].values()
            if value.get("admission_receipt_id") == adapter1.receipt.admission_receipt_id
        )
        assert not reservation1["closed"]
        assert adapter1._custody_process is process
        assert process.poll() is None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)

def test_controlled_launch_persists_order_and_is_single_use(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    adapter = ControlledFinalLaunch(receipt, ledger=ledger)
    typed = DispatchOutcome(
        kind="success",
        launch_state="accepted",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        dispatch_family_id=receipt.dispatch_family_id,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        selected_spec=receipt.normalized_spec,
        worker_identity=WORKER,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )
    assert adapter.run(lambda _context: typed) == typed
    adapter.close()
    restarted = ControlledFinalLaunch(receipt, ledger=ledger)
    with pytest.raises(RuntimeError):
        restarted.run(lambda _context: typed)
    states = [
        record["payload"]["launch_state_identity"]
        for record in ledger.read_nbf_events()
        if record["payload"].get("event_type") == "controlled_adapter_state"
    ]
    assert states == ["not_started", "entered", "accepted", "closed"]


def test_reopen_rejects_persisted_closed_first_history_before_state(tmp_path: Path) -> None:
    """Reopen validates the complete persisted sequence before selecting state."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        require_production_worker_dispatch_runtime,
    )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    identity = {"host": "host", "pid": 123, "boot_id": "boot"}

    # Write a deliberately malformed persisted history through the mechanism
    # journal: each record is schema-valid, but the ordered lifecycle is not.
    # This simulates legacy/corrupt storage that the normal append API refuses.
    def emit(state: str, suffix: str) -> None:
        payload = {
            "schema_version": 1,
            "event_type": "controlled_adapter_state",
            "event_id": f"reopen-{suffix}",
            "reservation_event_id": receipt.reservation_event_id,
            "admission_receipt_id": receipt.admission_receipt_id,
            "physical_door_id": receipt.physical_door_id,
            "launch_state_identity": state,
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "actor": "test",
        }
        if state == "accepted":
            payload.update(
                {
                    "phase": receipt.phase,
                    "selected_spec": receipt.normalized_spec,
                    "primary_spec": receipt.normalized_spec,
                    "logical_dispatch_id": receipt.logical_dispatch_id,
                    "worker_identity": identity,
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:00:01+00:00",
                }
            )
        ledger._journal.emit("incident.nbf", payload=payload)

    emit("closed", "closed-first")
    emit("not_started", "prefix")
    emit("entered", "entered")
    emit("accepted", "accepted")

    with pytest.raises(ValueError, match="closed before lifecycle start"):
        ledger.projection()
    # ControlledFinalLaunch must call the same full-history validation before
    # it can reopen/select a marker or expose a callable closure.
    with pytest.raises(ValueError, match="closed before lifecycle start"):
        ControlledFinalLaunch(receipt, ledger=ledger)


def test_reopen_holds_legacy_ambiguous_without_new_lifecycle_marker(tmp_path: Path) -> None:
    """Legacy ambiguity is a permanent hold, not a fifth lifecycle state."""
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        require_production_worker_dispatch_runtime,
    )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from arnold_pipelines.megaplan.incident.schema import ReservationReconciled
    from arnold_pipelines.megaplan.types import CliError

    ledger = IncidentLedger(tmp_path)
    receipt = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    # This is the schema-valid legacy marker that the current append door no
    # longer emits.  It must remain replayable for old ledgers.
    ambiguous_id = "legacy-ambiguous"
    ledger._journal.emit(
        "incident.nbf",
        payload={
            "schema_version": 1,
            "event_type": "controlled_adapter_state",
            "event_id": ambiguous_id,
            "reservation_event_id": receipt.reservation_event_id,
            "admission_receipt_id": receipt.admission_receipt_id,
            "physical_door_id": receipt.physical_door_id,
            "launch_state_identity": "ambiguous",
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "actor": "legacy",
        },
    )
    reconciliation = ReservationReconciled(
        reconciliation_id="legacy-reconciliation",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        projection_key=receipt.projection_key,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        reservation_event_id=receipt.reservation_event_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        resolution="permanent_hold_ambiguous",
        evidence_kind="controlled_adapter",
        evidence_event_ids=(ambiguous_id,),
        launch_state_identity="ambiguous",
        observed_at="2026-01-01T00:00:00+00:00",
        recorded_at="2026-01-01T00:00:00+00:00",
        actor="legacy",
    )
    ledger.reconcile_reservation(reconciliation)

    before = ledger.read_nbf_events()
    first = ControlledFinalLaunch(receipt, ledger=ledger)
    after_first = ledger.read_nbf_events()
    second = ControlledFinalLaunch(receipt, ledger=ledger)
    after_second = ledger.read_nbf_events()

    assert first.permanent_hold_ambiguous is True
    assert second.permanent_hold_ambiguous is True
    assert first.state == second.state == "not_started"
    assert after_first == after_second == before
    assert first.permanent_hold_outcome == second.permanent_hold_outcome
    assert first.permanent_hold_outcome.kind == "unresolved_launch"
    assert first.permanent_hold_outcome.launch_state == "ambiguous"
    assert first.permanent_hold_outcome.provider == receipt.provider
    assert first.permanent_hold_outcome.route_liveness_identity == receipt.route_liveness_identity

    provider_calls: list[object] = []
    with pytest.raises(CliError) as raised:
        first.run(lambda context: provider_calls.append(context))
    assert raised.value.extra["reason"] == "permanent_hold_ambiguous"
    assert raised.value.extra["dispatch_outcome"] == first.permanent_hold_outcome.to_dict()
    assert provider_calls == []
    assert ledger.read_nbf_events() == before
    # The reservation remains an open reconciliation hold; it was not silently
    # released or relaunchable after reopening.
    projected = ledger.projection()["reservations"]
    assert next(iter(projected.values()))["reconciliation"] == "permanent_hold_ambiguous"
    assert next(iter(projected.values()))["closed"] is False
