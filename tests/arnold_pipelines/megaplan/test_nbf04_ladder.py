from pathlib import Path
import signal

import pytest

from arnold_pipelines.megaplan.incident.disposition import (
    SignalDispositionError,
    WorkerSignalContext,
    confirmation_id,
    consume_confirmation,
    observe_confirmation,
    signal_worker,
    signal_worker_ladder,
)
from arnold_pipelines.megaplan.incident.schema import WorkerDisposition
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger


WORKER = {"host": "test", "pid": 1234, "boot_id": "boot"}
FINGERPRINT = "a" * 64


def _ready(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    reservation = ledger.reserve(
        plan_id="p", phase="phase", projection_key="key",
        semantic_dispatch_fingerprint=FINGERPRINT,
        logical_dispatch_id="logical", dispatch_family_id="family",
        selected_spec="spec",
    )
    event_id = reservation["payload"]["event_id"]
    receipt = reservation["payload"]["admission_receipt_id"]
    for state in ("not_started", "entered", "accepted"):
        values = dict(
            reservation_event_id=event_id, admission_receipt_id=receipt,
            physical_door_id="default-door", launch_state_identity=state,
        )
        if state == "accepted":
            values.update(
                phase="phase", selected_spec="spec", primary_spec="spec",
                logical_dispatch_id="logical", worker_identity=WORKER,
                victim_process_start_identity="incarnation",
                started_at="2026-01-01T00:00:00Z",
                finished_at="2026-01-01T00:00:01Z",
            )
        ledger.append_controlled_adapter_state(**values)
    context = WorkerSignalContext(
        "p", "phase", "family", "logical", receipt, FINGERPRINT, "spec",
        WORKER, WORKER["pid"], "incarnation",
    )
    return ledger, context


def test_confirmation_pending_never_signals(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []
    result = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="wedge",
        term_signal_fn=lambda: calls.append("term"),
        kill_signal_fn=lambda: calls.append("kill"),
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: "incarnation",
    )
    assert result.state == "confirmation_pending"
    assert calls == []


def test_term_dead_links_one_terminal_and_replays_without_signal(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []
    kwargs = dict(
        killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term"),
        liveness_fn=lambda _pid: False,
        process_start_identity_fn=lambda _pid: "incarnation",
    )
    first = signal_worker_ladder(ledger, context, **kwargs)
    second = signal_worker_ladder(ledger, context, **kwargs)
    assert first.state == second.state == "already_dead"
    assert calls == ["term"]
    assert len(ledger.projection()["terminals"]) == 1


def test_alive_worker_escalates_once_to_kill(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []
    kwargs = dict(
        killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term"),
        kill_signal_fn=lambda: calls.append("kill"),
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: "incarnation",
    )
    first = signal_worker_ladder(ledger, context, **kwargs)
    second = signal_worker_ladder(ledger, context, **kwargs)
    assert first.state == second.state == "killed"
    assert calls == ["term", "kill"]
    assert len(ledger.projection()["terminals"]) == 1


def test_kill_terminal_append_failure_blocks_kill(tmp_path, monkeypatch):
    ledger, context = _ready(tmp_path)
    calls = []
    monkeypatch.setattr(
        ledger, "append_terminal_outcome",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("terminal unavailable")),
    )
    result = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term"),
        kill_signal_fn=lambda: calls.append("kill"),
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: "incarnation",
    )
    assert result.state == "unresolved"
    assert calls == ["term", "kill"]
    projection = ledger.projection()
    assert projection["terminals"] == {}
    assert next(iter(projection["reservations"].values()))["closed"] is False


def test_term_signal_failure_leaves_reservation_open_without_terminal(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []

    def fail_term():
        calls.append("term")
        raise OSError("synthetic TERM failure")

    with pytest.raises(SignalDispositionError, match="TERM failure"):
        signal_worker_ladder(
            ledger, context, killer_identity="watchdog", cause_kind="terminate",
            term_signal_fn=fail_term,
            kill_signal_fn=lambda: calls.append("kill"),
            liveness_fn=lambda _pid: True,
            process_start_identity_fn=lambda _pid: "incarnation",
        )

    projection = ledger.projection()
    assert calls == ["term"]
    assert projection["terminals"] == {}
    assert next(iter(projection["reservations"].values()))["closed"] is False


def test_term_identity_mismatch_is_fenced_before_physical_signal(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []

    with pytest.raises(SignalDispositionError, match="TERM failure"):
        signal_worker_ladder(
            ledger, context, killer_identity="watchdog", cause_kind="terminate",
            term_signal_fn=lambda: calls.append("term"),
            kill_signal_fn=lambda: calls.append("kill"),
            liveness_fn=lambda _pid: True,
            process_start_identity_fn=lambda _pid: "reused-incarnation",
        )

    assert calls == []
    assert ledger.projection()["dispositions"] == {}
    assert ledger.projection()["terminals"] == {}
    assert next(iter(ledger.projection()["reservations"].values()))["closed"] is False


def test_kill_identity_mismatch_is_fenced_inside_locked_signal_door(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []
    identities = iter(("incarnation", "incarnation", "reused-incarnation"))

    result = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term"),
        kill_signal_fn=lambda: calls.append("kill"),
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: next(identities),
    )

    assert result.state == "unresolved"
    assert calls == ["term"]
    assert any(
        payload.get("ladder_step") == "kill"
        for payload in ledger.projection()["dispositions"].values()
    )
    assert not any(
        item.get("payload", {}).get("event_type") == "signal_claimed"
        and item.get("payload", {}).get("signal") == "SIGKILL"
        for item in ledger.read_nbf_events()
    )
    assert ledger.projection()["terminals"] == {}
    assert next(iter(ledger.projection()["reservations"].values()))["closed"] is False


def test_kill_signal_failure_leaves_claim_unresolved_and_replay_never_resends(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []

    def fail_kill():
        calls.append("kill")
        raise OSError("synthetic KILL failure")

    first = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term"), kill_signal_fn=fail_kill,
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: "incarnation",
    )
    second = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term-replay"),
        kill_signal_fn=lambda: calls.append("kill-replay"),
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: "incarnation",
    )

    projection = ledger.projection()
    reservation = next(iter(projection["reservations"].values()))
    assert first.state == second.state == "unresolved"
    assert calls == ["term", "kill"]
    assert projection["terminals"] == {}
    assert reservation["closed"] is False


def test_kill_claim_replay_reconciles_after_death_without_resignal(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []
    liveness = iter((True, True, False))

    def fail_kill():
        calls.append("kill")
        raise OSError("synthetic KILL failure")

    first = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term"), kill_signal_fn=fail_kill,
        liveness_fn=lambda _pid: next(liveness),
        process_start_identity_fn=lambda _pid: "incarnation",
    )
    second = signal_worker_ladder(
        ledger, context, killer_identity="watchdog", cause_kind="terminate",
        term_signal_fn=lambda: calls.append("term-replay"),
        kill_signal_fn=lambda: calls.append("kill-replay"),
        liveness_fn=lambda _pid: next(liveness),
        process_start_identity_fn=lambda _pid: "incarnation",
    )

    projection = ledger.projection()
    reservation = next(iter(projection["reservations"].values()))
    assert first.state == "unresolved"
    assert second.state == "already_dead"
    assert calls == ["term", "kill"]
    assert len(projection["terminals"]) == 1
    assert reservation["closed"] is True


def test_single_stage_signal_failure_does_not_project_terminal(tmp_path):
    ledger, context = _ready(tmp_path)
    calls = []

    def fail_signal():
        calls.append("physical")
        raise OSError("synthetic signal failure")

    with pytest.raises(SignalDispositionError, match="signal failed"):
        signal_worker(
            ledger, context, signal_name=signal.SIGKILL,
            killer_kind="watchdog", killer_identity="watchdog",
            cause_kind="terminate", signal_fn=fail_signal, final_signal=True,
            process_alive_fn=lambda _pid: True,
            process_start_identity_fn=lambda _pid: "incarnation",
        )

    projection = ledger.projection()
    assert calls == ["physical"]
    assert projection["terminals"] == {}
    assert next(iter(projection["reservations"].values()))["closed"] is False


def _proof(ledger, context, *, cause, at, ladder_step):
    first = observe_confirmation(
        ledger, site_id=f"site-{ladder_step}", subject_class="worker",
        plan_id=context.plan_id, admission_receipt_id=context.admission_receipt_id,
        victim_pid=context.victim_pid,
        victim_process_start_identity=context.victim_process_start_identity,
        relevant_progress_identity="progress",
        supervisor_incarnation_identity="supervisor",
        cause_kind=cause, scan_interval_s=1, observed_at=at, evidence={},
        semantic_dispatch_fingerprint=context.semantic_dispatch_fingerprint,
        ladder_stage=ladder_step, signal_identity=("SIGTERM" if ladder_step == "term" else "SIGKILL"),
    )
    cid = first["payload"]["confirmation_id"]
    signal = "SIGTERM" if ladder_step == "term" else "SIGKILL"
    disposition_id = WorkerDisposition.deterministic_id(
        receipt=context.admission_receipt_id, signal=signal, ladder_step=ladder_step,
    )
    consume_confirmation(
        ledger, confirmation_id_value=cid,
        second_observed_at=("2026-01-01T00:00:04Z" if at.endswith("03Z") else "2026-01-01T00:00:01Z"), second_evidence={},
        victim_pid=context.victim_pid,
        victim_process_start_identity=context.victim_process_start_identity,
        relevant_progress_identity="progress",
        supervisor_incarnation_identity="supervisor", cause_kind=cause,
        scan_interval_s=1, expires_at=first["payload"]["expires_at"],
        confirmation_policy_identity="default-v1", schema_version=1,
        semantic_dispatch_fingerprint=context.semantic_dispatch_fingerprint,
        disposition_id=disposition_id,
        ladder_stage=ladder_step,
        signal_identity=signal,
    )
    return cid


def test_sustained_ladder_requires_distinct_later_kill_proof(tmp_path):
    ledger, context = _ready(tmp_path)
    term_id = _proof(ledger, context, cause="wedge", at="2026-01-01T00:00:00Z", ladder_step="term")
    calls = []
    args = dict(
        killer_identity="watchdog", cause_kind="wedge",
        term_confirmation_event_id=term_id,
        term_signal_fn=lambda: calls.append("term"),
        kill_signal_fn=lambda: calls.append("kill"),
        liveness_fn=lambda _pid: True,
        process_start_identity_fn=lambda _pid: "incarnation",
        relevant_progress_identity="progress",
        supervisor_incarnation_identity="supervisor",
    )
    pending = signal_worker_ladder(ledger, context, **args)
    assert pending.state == "confirmation_pending"
    assert calls == ["term"]
    # Reusing TERM proof remains pending and cannot authorize KILL.
    reused = signal_worker_ladder(ledger, context, kill_confirmation_event_id=term_id, **args)
    assert reused.state == "confirmation_pending"
    assert calls == ["term"]
    kill_id = _proof(ledger, context, cause="wedge", at="2026-01-01T00:00:03Z", ladder_step="kill")
    done = signal_worker_ladder(ledger, context, kill_confirmation_event_id=kill_id, **args)
    assert done.state == "killed"
    assert calls == ["term", "kill"]
