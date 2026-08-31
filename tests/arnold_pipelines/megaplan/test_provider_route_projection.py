from arnold_pipelines.megaplan.incident.schema import ProviderFailureKey, semantic_dispatch_fingerprint
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
from arnold_pipelines.megaplan.incident.schema import ChangedPrecondition, WorkerDisposition, SourceRevisionSource, ProviderRecoverySource, _digest
import pytest

WORKER = {"host": "test-host", "pid": 1234, "boot_id": "boot-1"}


def _accepted(ledger, **kwargs):
    for state in ("not_started", "entered", "accepted"):
        ledger.append_controlled_adapter_state(
            **kwargs, launch_state_identity=state
        )


def test_provider_key_and_fingerprint_exclude_volatile_identity():
    a = ProviderFailureKey.derive(phase="p", selected_spec=" spec ", provider_failure_class="timeout", provider_epoch_identity="epoch")
    b = ProviderFailureKey.derive(phase="p", selected_spec="spec", provider_failure_class="timeout", provider_epoch_identity="epoch")
    assert a.value == b.value
    f1 = semantic_dispatch_fingerprint(phase="p", selected_spec="spec", model_family="f", source_revision="r", route_liveness_digest="one", logical_dispatch_id="a")
    f2 = semantic_dispatch_fingerprint(phase="p", selected_spec="spec", model_family="f", source_revision="r", route_liveness_digest="two", logical_dispatch_id="b")
    assert f1 == f2


def test_unofficial_route_child_with_receipt_surface_absent():
    assert not hasattr(IncidentLedger, "reserve_provider_route_child_with_receipt")
    assert hasattr(IncidentLedger, "reserve_provider_route_child")
    assert hasattr(IncidentLedger, "derive_receipt")


def _provider_outcome(key, n="log", *, selected_spec="spec", logical_dispatch_id=None):
    return DispatchOutcome("provider_exhausted", "accepted", "p", "ph", "fam", logical_dispatch_id or n, "r"+n, "f"*64, selected_spec, WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", provider_evidence={"observation_id":"o"+n,"retryability_class":"availability","exhausted_attempt_count":1,"terminal_provider_evidence_id":"ev"+n,"precondition_identity":"pre","provider_epoch_identity":"epoch","provider_failure_key":key,"observed_at":"2026-01-01T00:00:00Z"})


def test_keyed_streak_replay_matching_different_and_success(tmp_path):
    ledger=IncidentLedger(tmp_path); key=ProviderFailureKey.derive(phase="ph",selected_spec="spec",provider_failure_class="availability",provider_epoch_identity="epoch").value
    for i, out in enumerate((_provider_outcome(key,"a"), _provider_outcome(key,"b"))):
        r=ledger.reserve(plan_id="p",phase="ph",projection_key="pk"+str(i),semantic_dispatch_fingerprint="f"*64,logical_dispatch_id="l"+str(i),dispatch_family_id="fam",selected_spec="spec")
        out = DispatchOutcome.from_dict({**out.to_dict(), "logical_dispatch_id": "l" + str(i), "admission_receipt_id": r["payload"]["admission_receipt_id"]})
        _accepted(ledger, reservation_event_id=r["payload"]["event_id"], admission_receipt_id=r["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="l" + str(i), worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
        ledger.append_terminal_outcome(outcome=out,reservation_event_id=r["payload"]["event_id"],projection_key="pk"+str(i))
    assert ledger.projection()["observation_streak"] == 2
    fresh=IncidentLedger(tmp_path); assert fresh.projection()["observation_streak"] == 2


def test_provider_streak_is_keyed_not_global(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="a", provider_failure_class="availability", provider_epoch_identity="e").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="b", provider_failure_class="availability", provider_epoch_identity="e").value
    for i, (spec, key) in enumerate((("a", key_a), ("b", key_b))):
        out = _provider_outcome(key, str(i), selected_spec=spec, logical_dispatch_id="l" + str(i))
        r = ledger.reserve(plan_id="p", phase="ph", projection_key="pk" + str(i), semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="l" + str(i), dispatch_family_id="fam", selected_spec=spec)
        out = DispatchOutcome.from_dict({**out.to_dict(), "admission_receipt_id": r["payload"]["admission_receipt_id"]})
        _accepted(ledger, reservation_event_id=r["payload"]["event_id"], admission_receipt_id=r["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec=spec, primary_spec=spec, logical_dispatch_id="l" + str(i), worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
        ledger.append_terminal_outcome(outcome=out, reservation_event_id=r["payload"]["event_id"], projection_key="pk" + str(i))
    projection = ledger.projection()
    assert {stream["provider_failure_key"] for stream in projection["provider_streaks"].values()} == {key_a, key_b}
    assert all(stream["observation_streak"] == 1 for stream in projection["provider_streaks"].values())


def test_fresh_replay_receipt_is_byte_identical(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    parent, terminal = _append_provider(ledger, key=key, logical="parent", projection="parent", suffix="parent")
    change, _ = _provider_recovery_change(ledger, before_key=key, after_key=key, parent_event_id=parent["payload"]["event_id"])
    child = ledger.reserve_provider_route_child(plan_id="p", phase="ph", projection_key="parent", expected_projection_version=ledger.projection()["projection_version"], transition_kind="fallback", from_spec="spec", to_spec="backup", parent_logical_dispatch_id="parent", parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"], authorizing_event_id=change.event_id, configured_fallback_chain_identity="chain", precondition_identity="pre", child_dispatch_family_id="fam", child_logical_dispatch_id="child", child_physical_door_id="door", child_semantic_dispatch_fingerprint="a" * 64, child_route_liveness_identity="live")
    first = ledger.derive_receipt(child)
    reopened = IncidentLedger(tmp_path)
    replayed = next(record for record in reopened.read_nbf_events() if record["payload"].get("event_type") == "provider_route_child_reserved")
    assert reopened.derive_receipt(replayed) == first


def _append_provider(ledger, *, key, spec="spec", logical="log", projection="pk", suffix="x"):
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key=projection,
                                 semantic_dispatch_fingerprint="f" * 64,
                                 logical_dispatch_id=logical, dispatch_family_id="fam",
                                 selected_spec=spec)
    _accepted(ledger, reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec=spec, primary_spec=spec, logical_dispatch_id=logical, worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    outcome = _provider_outcome(key, suffix, selected_spec=spec,
                                logical_dispatch_id=logical)
    outcome = DispatchOutcome.from_dict({**outcome.to_dict(),
                                         "admission_receipt_id": reservation["payload"]["admission_receipt_id"]})
    terminal = ledger.append_terminal_outcome(outcome=outcome,
                                              reservation_event_id=reservation["payload"]["event_id"],
                                              projection_key=projection)
    return reservation, terminal


def test_nonmatching_key_rekeys_at_one(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="a").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="b").value
    _append_provider(ledger, key=key_a, logical="a", projection="a", suffix="a")
    _append_provider(ledger, key=key_b, logical="b", projection="b", suffix="b")
    streams = ledger.projection()["provider_streaks"]
    assert streams[next(k for k, v in streams.items() if v["provider_failure_key"] == key_a)]["observation_streak"] == 1
    assert streams[next(k for k, v in streams.items() if v["provider_failure_key"] == key_b)]["observation_streak"] == 1


def test_success_resets_only_applicable_key(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="a").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="b").value
    _append_provider(ledger, key=key_a, logical="a1", projection="a1", suffix="a1")
    _append_provider(ledger, key=key_a, logical="a2", projection="a2", suffix="a2")
    _append_provider(ledger, key=key_b, logical="b1", projection="b1", suffix="b1")
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="b2", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="b2", dispatch_family_id="fam", selected_spec="spec")
    _accepted(ledger, reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="b2", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    success = DispatchOutcome("success", "accepted", "p", "ph", "fam", "b2", reservation["payload"]["admission_receipt_id"], "f" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", success_payload={"ok": True}, provider_failure_key=key_b)
    ledger.append_terminal_outcome(outcome=success, reservation_event_id=reservation["payload"]["event_id"], projection_key="b2")
    streams = ledger.projection()["provider_streaks"]
    assert next(v for v in streams.values() if v["provider_failure_key"] == key_a)["observation_streak"] == 2
    assert next(v for v in streams.values() if v["provider_failure_key"] == key_b)["observation_streak"] == 0


def _streaks(ledger):
    return {item["provider_failure_key"]: (item["observation_streak"], item["broken"]) for item in ledger.projection()["provider_streaks"].values()}


def test_success_for_non_latest_key_does_not_reset_latest(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="a").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="b").value
    _append_provider(ledger, key=key_a, logical="a1", projection="a1", suffix="a1")
    _append_provider(ledger, key=key_a, logical="a2", projection="a2", suffix="a2")
    _append_provider(ledger, key=key_b, logical="b1", projection="b1", suffix="b1")
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="a3", semantic_dispatch_fingerprint="a" * 64, logical_dispatch_id="a3", dispatch_family_id="fam", selected_spec="spec")
    _accepted(ledger, reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="a3", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    success = DispatchOutcome("success", "accepted", "p", "ph", "fam", "a3", reservation["payload"]["admission_receipt_id"], "a" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", success_payload={"ok": True}, provider_failure_key=key_a)
    ledger.append_terminal_outcome(outcome=success, reservation_event_id=reservation["payload"]["event_id"], projection_key="a3")
    assert _streaks(ledger)[key_a] == (0, False)
    assert _streaks(ledger)[key_b] == (1, False)


def test_ordinary_failure_breaks_only_applicable_stream(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="a").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="b").value
    _append_provider(ledger, key=key_a, logical="a1", projection="a1", suffix="a1")
    _append_provider(ledger, key=key_a, logical="a2", projection="a2", suffix="a2")
    _append_provider(ledger, key=key_b, logical="b1", projection="b1", suffix="b1")
    _append_provider(ledger, key=key_b, logical="b2", projection="b2", suffix="b2")
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="a-failure", semantic_dispatch_fingerprint="c" * 64, logical_dispatch_id="a-failure", dispatch_family_id="fam", selected_spec="spec")
    _accepted(ledger, reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="a-failure", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    failure = DispatchOutcome("ordinary_terminal_failure", "accepted", "p", "ph", "fam", "a-failure", reservation["payload"]["admission_receipt_id"], "c" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", terminal_failure={"error": "ordinary"}, provider_failure_key=key_a)
    ledger.append_terminal_outcome(outcome=failure, reservation_event_id=reservation["payload"]["event_id"], projection_key="a-failure")
    assert _streaks(ledger)[key_a] == (0, True)
    assert _streaks(ledger)[key_b] == (2, False)
    assert "provider_degraded" not in ledger.projection()


def test_applicable_key_survives_restart_and_replay(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="a").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="b").value
    _append_provider(ledger, key=key_a, logical="a1", projection="a1", suffix="a1")
    _append_provider(ledger, key=key_a, logical="a2", projection="a2", suffix="a2")
    _append_provider(ledger, key=key_b, logical="b1", projection="b1", suffix="b1")
    assert _streaks(IncidentLedger(tmp_path)) == _streaks(ledger)


def test_cross_key_isolation_after_success_and_disposition(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key_a = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="a").value
    key_b = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="b").value
    _append_provider(ledger, key=key_a, logical="a1", projection="a1", suffix="a1")
    _append_provider(ledger, key=key_b, logical="b1", projection="b1", suffix="b1")
    _append_provider(ledger, key=key_b, logical="b2", projection="b2", suffix="b2")
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="a-disposition", semantic_dispatch_fingerprint="d" * 64, logical_dispatch_id="a-disposition", dispatch_family_id="fam", selected_spec="spec")
    _accepted(ledger, reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="a-disposition", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    disposition = WorkerDisposition("a-disp", "in_band", "p", "ph", "fam", "a-disposition", reservation["payload"]["admission_receipt_id"], "d" * 64, "spec", "watchdog", "killer", "wedge", "SIGTERM", 1.0, WORKER, "2026-01-01T00:00:00Z", {"x": 1})
    ledger.append_disposition(disposition)
    outcome = DispatchOutcome("worker_disposition", "accepted", "p", "ph", "fam", "a-disposition", reservation["payload"]["admission_receipt_id"], "d" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", disposition_id="a-disp", provider_failure_key=key_a)
    ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=reservation["payload"]["event_id"], projection_key="a-disposition")
    assert _streaks(ledger)[key_a] == (0, True)
    assert _streaks(ledger)[key_b] == (2, False)


def _provider_recovery_change(ledger, *, before_key, after_key, parent_event_id=None):
    observation = ledger.append_provider_observation(observation_id="obs", provider_failure_key=before_key, selected_spec="spec", phase="ph", provider_failure_class="availability", provider_epoch_identity="epoch")
    lease = ledger.create_probe_lease(provider_failure_key=before_key, expires_at=9999999999, parent_reservation_event_id=parent_event_id, phase="ph", route_identity="spec->backup")
    probe = ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key=before_key, passed=True, evidence_digest="e" * 64, parent_reservation_event_id=parent_event_id, phase="ph", route_identity="spec->backup")
    before = ProviderRecoverySource("v1", "probe", "probe-receipt", {"state": "down"}, before_key)
    after = ProviderRecoverySource("v2", "probe", "probe-receipt", {"state": "up"}, after_key)
    change = __import__("arnold_pipelines.megaplan.incident.schema", fromlist=["produce_provider_recovery_verified"]).produce_provider_recovery_verified(plan_id="p", phase="ph", authoritative_subject="probe", before=before, after=after, evidence_event_id=probe["payload"]["event_id"], evidence=probe["payload"], actor="test")
    ledger.append_changed_precondition(change)
    return change, observation


def test_recovery_authorization_single_use_across_different_children(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    parent, terminal = _append_provider(ledger, key=key, logical="parent", projection="parent", suffix="parent")
    change, _ = _provider_recovery_change(ledger, before_key=key, after_key=key, parent_event_id=parent["payload"]["event_id"])
    child = ledger.reserve_provider_route_child(plan_id="p", phase="ph", projection_key="parent", expected_projection_version=ledger.projection()["projection_version"], transition_kind="fallback", from_spec="spec", to_spec="backup", parent_logical_dispatch_id="parent", parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"], authorizing_event_id=change.event_id, configured_fallback_chain_identity="chain", precondition_identity="pre", child_dispatch_family_id="fam", child_logical_dispatch_id="child", child_physical_door_id="door", child_semantic_dispatch_fingerprint="a" * 64, child_route_liveness_identity="live")
    assert child["payload"]["event_type"] == "provider_route_child_reserved"
    assert ledger.projection()["observation_streak"] == 1
    try:
        ledger.reserve_provider_route_child(plan_id="p", phase="ph", projection_key="parent", expected_projection_version=ledger.projection()["projection_version"], transition_kind="fallback", from_spec="spec", to_spec="backup2", parent_logical_dispatch_id="parent", parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"], authorizing_event_id=change.event_id, configured_fallback_chain_identity="chain", precondition_identity="pre", child_dispatch_family_id="fam", child_logical_dispatch_id="child2", child_physical_door_id="door", child_semantic_dispatch_fingerprint="b" * 64, child_route_liveness_identity="live")
    except ValueError:
        pass
    else:
        raise AssertionError("provider recovery authorizer was reusable")


def test_recovery_requires_passed_canonical_probe(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    parent, terminal = _append_provider(ledger, key=key, logical="parent", projection="parent", suffix="parent")
    lease = ledger.create_probe_lease(provider_failure_key=key, expires_at=9999999999, parent_reservation_event_id=parent["payload"]["event_id"], phase="ph", route_identity="spec->backup")
    failed = ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key=key, passed=False, evidence_digest="f" * 64, parent_reservation_event_id=parent["payload"]["event_id"], phase="ph", route_identity="spec->backup")
    before = ProviderRecoverySource("v1", "probe", "probe-receipt", {"state": "down"}, key)
    after = ProviderRecoverySource("v2", "probe", "probe-receipt", {"state": "up"}, key)
    change = __import__("arnold_pipelines.megaplan.incident.schema", fromlist=["produce_provider_recovery_verified"]).produce_provider_recovery_verified(plan_id="p", phase="ph", authoritative_subject="probe", before=before, after=after, evidence_event_id=failed["payload"]["event_id"], evidence=failed["payload"], actor="test")
    with pytest.raises(ValueError): ledger.append_changed_precondition(change)


def test_failed_absent_mismatched_replayed_consumed_recovery_rejects(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    with pytest.raises(ValueError): ledger.append_probe_result(probe_lease_id="missing", provider_failure_key=key, passed=True, evidence_digest="e" * 64)
    lease = ledger.create_probe_lease(provider_failure_key=key, expires_at=9999999999, phase="ph", route_identity="spec->backup")
    with pytest.raises(ValueError): ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key="a" * 64, passed=True, evidence_digest="e" * 64, phase="ph", route_identity="spec->backup")
    result = ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key=key, passed=True, evidence_digest="e" * 64, phase="ph", route_identity="spec->backup")
    with pytest.raises(ValueError): ledger.append_probe_result(probe_lease_id=lease["payload"]["probe_lease_id"], provider_failure_key=key, passed=True, evidence_digest="e" * 64, phase="ph", route_identity="spec->backup")
    assert result["payload"]["passed"] is True


def test_probe_result_requires_unexpired_matching_lease(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    expired = ledger.create_probe_lease(provider_failure_key=key, expires_at=1, phase="ph", route_identity="spec->backup")
    with pytest.raises(ValueError): ledger.append_probe_result(probe_lease_id=expired["payload"]["probe_lease_id"], provider_failure_key=key, passed=True, evidence_digest="e" * 64, phase="ph", route_identity="spec->backup")


def test_fresh_replay_composite_receipt_is_byte_identical(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    parent, terminal = _append_provider(ledger, key=key, logical="parent", projection="parent", suffix="parent")
    change, _ = _provider_recovery_change(ledger, before_key=key, after_key=key, parent_event_id=parent["payload"]["event_id"])
    child = ledger.reserve_provider_route_child(plan_id="p", phase="ph", projection_key="parent", expected_projection_version=ledger.projection()["projection_version"], transition_kind="fallback", from_spec="spec", to_spec="backup", parent_logical_dispatch_id="parent", parent_terminal_event_id=terminal["payload"]["terminal_outcome_id"], authorizing_event_id=change.event_id, configured_fallback_chain_identity="chain", precondition_identity="pre", child_dispatch_family_id="fam", child_logical_dispatch_id="child", child_physical_door_id="door", child_semantic_dispatch_fingerprint="a" * 64, child_route_liveness_identity="live")
    first = ledger.derive_receipt(child)
    reopened = IncidentLedger(tmp_path)
    replayed = next(record for record in reopened.read_nbf_events() if record["payload"].get("event_type") == "provider_route_child_reserved")
    assert reopened.derive_receipt(replayed) == first


def test_key_changing_precondition_rekeys_key_unchanged_does_not(tmp_path):
    ledger = IncidentLedger(tmp_path)
    old = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="old").value
    new = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="new").value
    _append_provider(ledger, key=old, logical="parent", projection="parent", suffix="parent")
    evidence = ledger.read_nbf_events()[0]["payload"]
    from arnold_pipelines.megaplan.incident.schema import produce_source_revision_changed
    changing = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=SourceRevisionSource("v1", "source", "source-receipt", 1, old), after=SourceRevisionSource("v2", "source", "source-receipt", 2, new), evidence_event_id=evidence["event_id"], evidence=evidence, actor="test")
    ledger.append_changed_precondition(changing)
    assert next(v for v in ledger.projection()["provider_streaks"].values() if v["provider_failure_key"] == new)["observation_streak"] == 0
    same = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=SourceRevisionSource("v3", "source", "source-receipt", 3, old), after=SourceRevisionSource("v4", "source", "source-receipt", 4, old), evidence_event_id=evidence["event_id"], evidence=evidence, actor="test")
    ledger.append_changed_precondition(same)
    assert len([v for v in ledger.projection()["provider_streaks"].values() if v["provider_failure_key"] == old]) == 1


def test_disposition_breaks_consecutiveness_without_degradation(tmp_path):
    ledger = IncidentLedger(tmp_path)
    key = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="epoch").value
    _append_provider(ledger, key=key, logical="p1", projection="p1", suffix="p1")
    reservation = ledger.reserve(plan_id="p", phase="ph", projection_key="d", semantic_dispatch_fingerprint="d" * 64, logical_dispatch_id="d", dispatch_family_id="fam", selected_spec="spec")
    _accepted(ledger, reservation_event_id=reservation["payload"]["event_id"], admission_receipt_id=reservation["payload"]["admission_receipt_id"], physical_door_id="default-door", phase="ph", selected_spec="spec", primary_spec="spec", logical_dispatch_id="d", worker_identity=WORKER, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z")
    disposition = WorkerDisposition("disp", "in_band", "p", "ph", "fam", "d", reservation["payload"]["admission_receipt_id"], "d" * 64, "spec", "watchdog", "k", "wedge", "SIGTERM", 1.0, WORKER, "2026-01-01T00:00:00Z", {"x": 1})
    ledger.append_disposition(disposition)
    outcome = DispatchOutcome("worker_disposition", "accepted", "p", "ph", "fam", "d", reservation["payload"]["admission_receipt_id"], "d" * 64, "spec", WORKER, "2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", disposition_id="disp", provider_failure_key=key)
    ledger.append_terminal_outcome(outcome=outcome, reservation_event_id=reservation["payload"]["event_id"], projection_key="d")
    _append_provider(ledger, key=key, logical="p2", projection="p2", suffix="p2")
    assert ledger.projection()["observation_streak"] == 1
