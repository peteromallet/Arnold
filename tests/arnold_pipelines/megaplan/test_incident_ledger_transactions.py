from pathlib import Path
import pytest
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
from arnold_pipelines.megaplan.incident.schema import ChangedPrecondition, ReservationReconciled, ProviderFailureKey, SourceRevisionSource, ProviderRecoverySource, produce_provider_recovery_verified

WORKER = {"host": "test-host", "pid": 1234, "boot_id": "boot-1"}


def _reserve_process(root, logical, result):
    try:
        IncidentLedger(root).reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id=logical, dispatch_family_id="fam")
        result.put("won")
    except Exception as exc:
        result.put(type(exc).__name__)


def test_reservation_and_replay_are_single_authority(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    rec = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f"*64, logical_dispatch_id="l", dispatch_family_id="fam")
    assert ledger.projection()["reservations"]
    assert ledger.projection()["projection_version"] == 1
    assert rec["payload"]["reservation_key"]


def test_same_fingerprint_different_logical_ids_contend(tmp_path):
    ledger=IncidentLedger(tmp_path); args=dict(plan_id="p",phase="ph",projection_key="pk",semantic_dispatch_fingerprint="f"*64,dispatch_family_id="fam")
    ledger.reserve(logical_dispatch_id="one",**args)
    import pytest
    with pytest.raises(ValueError): ledger.reserve(logical_dispatch_id="two",**args)


def test_torn_line_is_not_projected(tmp_path):
    ledger=IncidentLedger(tmp_path); ledger.events_path.parent.mkdir(parents=True,exist_ok=True)
    ledger.events_path.write_text('{"seq":99,"payload":\n',encoding="utf-8")
    assert ledger.projection()["projection_version"] == 0


def test_torn_composite_write_exposes_neither_transition_nor_receipt(tmp_path, monkeypatch):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    parent = ledger.reserve(plan_id="p", phase="ph", projection_key="parent", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="parent", dispatch_family_id="fam", selected_spec="spec")
    ledger.append_controlled_adapter_state(reservation_event_id=parent["payload"]["event_id"], admission_receipt_id=parent["payload"]["admission_receipt_id"], physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="parent", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    outcome = DispatchOutcome("provider_exhausted", "accepted", "p", "ph", "fam", "parent", parent["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", provider_evidence={"observation_id":"o","retryability_class":"availability","exhausted_attempt_count":1,"terminal_provider_evidence_id":"ev","precondition_identity":"pre","provider_epoch_identity":"epoch","provider_failure_key":key,"observed_at":"2026-01-01T00:00:00Z"})
    terminal = ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=parent["payload"]["event_id"], projection_key="parent")
    lease = ledger.create_probe_lease(provider_failure_key=key, expires_at=9999999999, parent_reservation_event_id=parent["payload"]["event_id"], phase="ph", route_identity="spec->backup")
    probe = ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key=key, passed=True, evidence_digest="e" * 64, parent_reservation_event_id=parent["payload"]["event_id"], phase="ph", route_identity="spec->backup")
    before = ProviderRecoverySource("v1", "provider", "probe-receipt", {"state":"down"}, key)
    after = ProviderRecoverySource("v2", "provider", "probe-receipt", {"state":"up"}, key)
    change = produce_provider_recovery_verified(plan_id="p", phase="ph", authoritative_subject="provider", before=before, after=after, evidence_event_id=probe["payload"]["event_id"], evidence=probe["payload"], actor="test")
    ledger.append_changed_precondition(change)
    kwargs = dict(plan_id="p", phase="ph", projection_key="parent", expected_projection_version=ledger.projection()["projection_version"], transition_kind="fallback", from_spec="spec", to_spec="backup", parent_logical_dispatch_id="parent", parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"], authorizing_event_id=change.event_id, configured_fallback_chain_identity="chain", precondition_identity="pre", child_dispatch_family_id="fam", child_logical_dispatch_id="child", child_physical_door_id="door", child_semantic_dispatch_fingerprint="a" * 64, child_route_liveness_identity="live")
    def fail(*args, **kwargs):
        raise OSError("injected composite write failure")
    monkeypatch.setattr(ledger._journal, "_emit_locked", fail)
    import pytest
    with pytest.raises(OSError):
        ledger.reserve_provider_route_child(**kwargs)
    reopened = IncidentLedger(tmp_path)
    assert not any(record["payload"].get("event_type") == "provider_route_child_reserved" for record in reopened.read_nbf_events())
    assert not any(value.get("logical_dispatch_id") == "child" for value in reopened.projection()["reservations"].values())


def test_two_process_reservation_contention_one_winner(tmp_path):
    import multiprocessing
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_reserve_process, args=(tmp_path, name, queue)) for name in ("one", "two")]
    for process in processes: process.start()
    for process in processes: process.join(10)
    results = [queue.get(timeout=2) for _ in processes]
    assert results.count("won") == 1
    assert len(IncidentLedger(tmp_path).projection()["reservations"]) == 1


def test_crash_after_read_before_append_exposes_no_partial_reservation(tmp_path):
    import subprocess
    import sys
    script = """
from pathlib import Path
import os
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
ledger = IncidentLedger(Path(__import__('sys').argv[1]))
with ledger._locked() as (fd, records):
    ledger._project_records(records)
    os._exit(0)
"""
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd="/Users/peteromalley/Documents/Arnold-oracle-nbf", capture_output=True, text=True)
    assert result.returncode == 0
    assert IncidentLedger(tmp_path).projection()["reservations"] == {}


def _terminal(ledger, *, logical="log", projection="pk", kind="success"):
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key=projection, semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id=logical, dispatch_family_id="fam", selected_spec="spec")
    kwargs = {"success_payload": {"ok": True}} if kind == "success" else {"terminal_failure": {"error": "x"}}
    ledger.append_controlled_adapter_state(reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id=logical, worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    outcome = DispatchOutcome(kind, "accepted", "p", "ph", "fam", logical, reservation["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", **kwargs)
    return reservation, outcome


def test_same_id_terminal_linkage_is_idempotent(tmp_path):
    import multiprocessing
    reservation, outcome = _terminal(IncidentLedger(tmp_path))
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()

    def append_one(root, receipt_event, result):
        try:
            ledger = IncidentLedger(root)
            rec = ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=receipt_event, projection_key="pk")
            result.put(("ok", rec["payload"]["terminal_outcome_id"]))
        except Exception as exc:
            result.put((type(exc).__name__, str(exc)))

    processes = [ctx.Process(target=append_one, args=(tmp_path, reservation["payload"]["event_id"], queue)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
    results = [queue.get(timeout=2) for _ in processes]
    assert all(result[0] == "ok" for result in results)
    assert len(IncidentLedger(tmp_path).projection()["terminals"]) == 1


def test_post_append_receipt_boundary_failure_reopens_with_byte_identical_receipt(tmp_path, monkeypatch):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    parent = ledger.reserve(plan_id="p", phase="ph", projection_key="parent", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="parent", dispatch_family_id="fam", selected_spec="spec")
    ledger.append_controlled_adapter_state(reservation_event_id=parent["payload"]["event_id"], admission_receipt_id=parent["payload"]["admission_receipt_id"], physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="parent", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    outcome = DispatchOutcome("provider_exhausted", "accepted", "p", "ph", "fam", "parent", parent["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", provider_evidence={"observation_id":"o","retryability_class":"availability","exhausted_attempt_count":1,"terminal_provider_evidence_id":"ev","precondition_identity":"pre","provider_epoch_identity":"epoch","provider_failure_key":key,"observed_at":"2026-01-01T00:00:00Z"})
    terminal = ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=parent["payload"]["event_id"], projection_key="parent")
    lease = ledger.create_probe_lease(provider_failure_key=key, expires_at=9999999999, parent_reservation_event_id=parent["payload"]["event_id"], phase="ph", route_identity="spec->backup")
    probe = ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key=key, passed=True, evidence_digest="e" * 64, parent_reservation_event_id=parent["payload"]["event_id"], phase="ph", route_identity="spec->backup")
    before = __import__("arnold_pipelines.megaplan.incident.schema", fromlist=["ProviderRecoverySource"]).ProviderRecoverySource("v1", "probe", "probe-receipt", {"state":"down"}, key)
    after = __import__("arnold_pipelines.megaplan.incident.schema", fromlist=["ProviderRecoverySource"]).ProviderRecoverySource("v2", "probe", "probe-receipt", {"state":"up"}, key)
    change = produce_provider_recovery_verified(plan_id="p", phase="ph", authoritative_subject="probe", before=before, after=after, evidence_event_id=probe["payload"]["event_id"], evidence=probe["payload"], actor="test")
    ledger.append_changed_precondition(change)
    kwargs = dict(plan_id="p", phase="ph", projection_key="parent", expected_projection_version=ledger.projection()["projection_version"], transition_kind="fallback", from_spec="spec", to_spec="backup", parent_logical_dispatch_id="parent", parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"], authorizing_event_id=change.event_id, configured_fallback_chain_identity="chain", precondition_identity="pre", child_dispatch_family_id="fam", child_logical_dispatch_id="child", child_physical_door_id="door", child_semantic_dispatch_fingerprint="a" * 64, child_route_liveness_identity="live")
    original = ledger._journal._emit_locked
    def append_then_crash(*args, **inner_kwargs):
        event = original(*args, **inner_kwargs)
        if inner_kwargs.get("payload", {}).get("event_type") == "provider_route_child_reserved":
            raise OSError("injected post-append receipt-boundary failure")
        return event
    monkeypatch.setattr(ledger._journal, "_emit_locked", append_then_crash)
    with pytest.raises(OSError):
        ledger.reserve_provider_route_child(**kwargs)
    reopened = IncidentLedger(tmp_path)
    children = [record for record in reopened.read_nbf_events() if record["payload"].get("event_type") == "provider_route_child_reserved"]
    assert len(children) == 1
    assert reopened.derive_receipt(children[0]) == IncidentLedger(tmp_path).derive_receipt(children[0])
    assert len([value for value in reopened.projection()["reservations"].values() if value.get("logical_dispatch_id") == "child"]) == 1


def _append_distinct_terminal(root, reservation_event_id, outcome, projection_key, result):
    try:
        record = IncidentLedger(root).append_terminal_outcome(outcome=outcome, reservation_event_id=reservation_event_id, projection_key=projection_key)
        result.put(("ok", record["payload"]["terminal_outcome_id"]))
    except Exception as exc:
        result.put((type(exc).__name__, str(exc)))


def test_two_process_terminal_linkage_is_atomic(tmp_path):
    ledger = IncidentLedger(tmp_path)
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", selected_spec="spec")
    ledger.append_controlled_adapter_state(reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="log", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    common = dict(launch_state="accepted", plan_id="p", phase="ph", dispatch_family_id="fam", logical_dispatch_id="log", admission_receipt_id=reservation["payload"]["admission_receipt_id"], semantic_dispatch_fingerprint="f" * 64, selected_spec="spec", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    success = DispatchOutcome(kind="success", success_payload={"ok": True}, terminal_outcome_event_id="terminal-success", **common)
    failure = DispatchOutcome(kind="ordinary_terminal_failure", terminal_failure={"error": "x"}, terminal_outcome_event_id="terminal-failure", **common)
    import multiprocessing
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_append_distinct_terminal, args=(tmp_path, reservation["payload"]["event_id"], outcome, "pk", queue)) for outcome in (success, failure)]
    for process in processes: process.start()
    for process in processes: process.join(10)
    results = [queue.get(timeout=2) for _ in processes]
    assert [result[0] for result in results].count("ok") == 1
    terminal = next(iter(IncidentLedger(tmp_path).projection()["terminals"].values()))
    winner = success if terminal["outcome_kind"] == "success" else failure
    assert IncidentLedger(tmp_path).append_terminal_outcome(outcome=winner, reservation_event_id=reservation["payload"]["event_id"], projection_key="pk")["payload"]["terminal_outcome_id"] == terminal["terminal_outcome_id"]


def test_terminal_rejects_reservation_context_mismatch(tmp_path):
    import pytest
    ledger = IncidentLedger(tmp_path)
    reservation, outcome = _terminal(ledger)
    forged = DispatchOutcome.from_dict({**outcome.to_dict(), "logical_dispatch_id": "other"})
    with pytest.raises(ValueError):
        ledger.append_terminal_outcome(outcome=forged, reservation_event_id=reservation["payload"]["event_id"], projection_key="pk")


def test_terminal_requires_persisted_accepted_launch_context(tmp_path):
    import pytest
    ledger = IncidentLedger(tmp_path)
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", selected_spec="spec")
    outcome = DispatchOutcome("success", "accepted", "p", "ph", "fam", "log", reservation["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", success_payload={"ok": True})
    with pytest.raises(ValueError):
        ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=reservation["payload"]["event_id"], projection_key="pk")


def test_terminal_without_accepted_marker_rejects_fully_populated_outcome(tmp_path):
    ledger = IncidentLedger(tmp_path)
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", selected_spec="spec")
    outcome = DispatchOutcome("success", "accepted", "p", "ph", "fam", "log", reservation["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", success_payload={"ok": True})
    import pytest
    with pytest.raises(ValueError):
        ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=reservation["payload"]["event_id"], projection_key="pk")


def test_accepted_marker_single_field_mismatch_rejects(tmp_path):
    import pytest
    fields = {"phase": "other", "selected_spec": "other-spec", "primary_spec": "other-primary", "logical_dispatch_id": "other-log", "worker_identity": {"host": "other", "pid": 2, "boot_id": "other"}, "started_at": "2026-01-01T00:00:02Z", "finished_at": "2026-01-01T00:00:03Z", "physical_door_id": "other-door"}
    for field, bad in fields.items():
        case = tmp_path / field
        ledger = IncidentLedger(case)
        reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", selected_spec="spec")
        marker = {"reservation_event_id": reservation["payload"]["event_id"], "admission_receipt_id": reservation["payload"]["admission_receipt_id"], "physical_door_id": "default-door", "launch_state_identity": "accepted", "phase": "ph", "selected_spec": "spec", "primary_spec": "spec", "logical_dispatch_id": "log", "worker_identity": WORKER, "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:01Z"}
        marker[field] = bad
        ledger.append_controlled_adapter_state(**{k: v for k, v in marker.items() if k not in {"physical_door_id", "launch_state_identity"}}, physical_door_id=marker["physical_door_id"], launch_state_identity=marker["launch_state_identity"])
        outcome = DispatchOutcome("success", "accepted", "p", "ph", "fam", "log", reservation["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", success_payload={"ok": True})
        with pytest.raises(ValueError):
            ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=reservation["payload"]["event_id"], projection_key="pk")


def test_blind_release_and_accepted_launch_release_reject(tmp_path):
    import pytest
    ledger = IncidentLedger(tmp_path)
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam")
    common = dict(reconciliation_id="r", plan_id="p", phase="ph", projection_key="pk", logical_dispatch_id="log", admission_receipt_id=reservation["payload"]["admission_receipt_id"], reservation_event_id=reservation["payload"]["event_id"], semantic_dispatch_fingerprint="f" * 64, resolution="released_no_launch", evidence_kind="controlled_adapter", evidence_event_ids=("missing",), launch_state_identity="not_started", observed_at="2026-01-01T00:00:00Z", recorded_at="2026-01-01T00:00:00Z", actor="test")
    with pytest.raises(ValueError):
        ledger.reconcile_reservation(ReservationReconciled(**common))
    ledger.append_controlled_adapter_state(reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", launch_state_identity="accepted", phase="ph", selected_spec="unspecified", primary_spec="unspecified", logical_dispatch_id="log", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    common["evidence_event_ids"] = ("entered",)
    with pytest.raises(ValueError):
        ledger.reconcile_reservation(ReservationReconciled(**common))


def test_conflicting_reconciliation_rejected_identical_replay_idempotent(tmp_path):
    import pytest
    ledger = IncidentLedger(tmp_path)
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam")
    marker = {"schema_version": 1, "event_type": "controlled_adapter_state", "event_id": "not-started", "reservation_event_id": reservation["payload"]["event_id"], "admission_receipt_id": reservation["payload"]["admission_receipt_id"], "physical_door_id": "default-door", "launch_state_identity": "not_started", "recorded_at": "2026-01-01T00:00:00Z", "actor": "test"}
    ledger._append_nbf(marker)
    reconciliation = ReservationReconciled("r", "p", "ph", "pk", "log", reservation["payload"]["admission_receipt_id"], reservation["payload"]["event_id"], "f" * 64, "released_no_launch", "controlled_adapter", ("not-started",), "not_started", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
    first = ledger.reconcile_reservation(reconciliation)
    assert ledger.reconcile_reservation(reconciliation) == first
    with pytest.raises(ValueError):
        ledger.reconcile_reservation(ReservationReconciled("r2", "p", "ph", "pk", "log", reservation["payload"]["admission_receipt_id"], reservation["payload"]["event_id"], "f" * 64, "released_no_launch", "controlled_adapter", ("not-started",), "not_started", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test"))


def test_lock_schema_and_projection_version_mismatch_fail_closed(tmp_path):
    import pytest
    ledger = IncidentLedger(tmp_path)
    with pytest.raises(ValueError):
        ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", expected_projection_version=1)
    ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam")
    with pytest.raises(ValueError):
        ledger.reserve(plan_id="p", phase="ph", projection_key="pk2", semantic_dispatch_fingerprint="e" * 64, logical_dispatch_id="log2", dispatch_family_id="fam", expected_projection_version=0)


def test_consumed_change_cannot_authorize_second_reservation(tmp_path):
    import pytest
    ledger = IncidentLedger(tmp_path)
    first = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam")
    marker = {"schema_version": 1, "event_type": "controlled_adapter_state", "event_id": "not-started", "reservation_event_id": first["payload"]["event_id"], "admission_receipt_id": first["payload"]["admission_receipt_id"], "physical_door_id": "default-door", "launch_state_identity": "not_started", "recorded_at": "2026-01-01T00:00:00Z", "actor": "test"}
    ledger._append_nbf(marker)
    release = ReservationReconciled("r", "p", "ph", "pk", "log", first["payload"]["admission_receipt_id"], first["payload"]["event_id"], "f" * 64, "released_no_launch", "controlled_adapter", ("not-started",), "not_started", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
    ledger.reconcile_reservation(release)
    from arnold_pipelines.megaplan.incident.schema import produce_source_revision_changed
    before = SourceRevisionSource("v1", "source", "source-receipt", 1)
    after = SourceRevisionSource("v2", "source", "source-receipt", 2)
    change = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=before, after=after, evidence_event_id=first["payload"]["event_id"], evidence=first["payload"], actor="test")
    ledger.append_changed_precondition(change)
    second = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", changed_precondition_event_id=change.event_id)
    marker2 = {"schema_version": 1, "event_type": "controlled_adapter_state", "event_id": "not-started-2", "reservation_event_id": second["payload"]["event_id"], "admission_receipt_id": second["payload"]["admission_receipt_id"], "physical_door_id": "default-door", "launch_state_identity": "not_started", "recorded_at": "2026-01-01T00:00:00Z", "actor": "test"}
    ledger._append_nbf(marker2)
    ledger.reconcile_reservation(ReservationReconciled("r2", "p", "ph", "pk", "log", second["payload"]["admission_receipt_id"], second["payload"]["event_id"], "f" * 64, "released_no_launch", "controlled_adapter", ("not-started-2",), "not_started", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test"))
    with pytest.raises(ValueError):
        ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam", changed_precondition_event_id=change.event_id)
