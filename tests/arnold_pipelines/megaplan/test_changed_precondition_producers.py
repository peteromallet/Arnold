import copy
import pytest
from arnold_pipelines.megaplan.incident.schema import ChangedPrecondition, ProviderFailureKey, SourceRevisionSource, ProviderRecoverySource, produce_source_revision_changed, produce_provider_recovery_verified, validate_nbf_event, _digest


def _source(kind, value, subject="source", key=None):
    source_type = ProviderRecoverySource if kind == "provider_recovery_verified" else SourceRevisionSource
    return source_type(source_version="v1", authoritative_subject=subject, source_identity=f"{subject}-receipt", content=value, provider_failure_key=key)


def test_producer_derives_unequal_ids_and_recovery_preserves_key():
    k=ProviderFailureKey.derive(phase="p",selected_spec="s",provider_failure_class="timeout",provider_epoch_identity="e").value
    evidence = {"event_id": "probe", "event_type": "provider_probe_result", "passed": True}
    c=produce_provider_recovery_verified(plan_id="p",phase="ph",authoritative_subject="probe",before=_source("provider_recovery_verified", {"ok":False}, "probe", k),after=_source("provider_recovery_verified", {"ok":True}, "probe", k),evidence_event_id="probe",evidence=evidence,actor="test")
    assert c.before_content_id != c.after_content_id
    with pytest.raises(ValueError): ChangedPrecondition.from_dict({**c.to_dict(), "after_content_id":"x"})


def test_free_form_reason_and_reuse_are_rejected():
        with pytest.raises(ValueError): ChangedPrecondition.produce(reason="notes", producer_kind="x", producer_version="1", plan_id="p", phase="ph", authoritative_subject="s", before=1, after=2, evidence_event_id="e", evidence={}, actor="t")


def test_reason_specific_producers_reject_caller_producer_identity():
    with pytest.raises(ValueError): ChangedPrecondition.produce(reason="source_revision_changed", producer_kind="forged", producer_version="1", plan_id="p", phase="ph", authoritative_subject="s", before=1, after=2, evidence_event_id="e", evidence={}, actor="t")


def test_forged_valid_hex_content_ids_reject():
    evidence = {"event_id": "e", "event_type": "source_receipt"}
    c = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=_source("source_revision_changed", 1), after=_source("source_revision_changed", 2), evidence_event_id="e", evidence=evidence, actor="t")
    with pytest.raises(ValueError): ChangedPrecondition.from_dict({**c.to_dict(), "after_content_id": "a" * 64})


def test_caller_supplied_provider_key_transition_rejects():
    with pytest.raises(ValueError): ChangedPrecondition.produce(reason="source_revision_changed", plan_id="p", phase="ph", authoritative_subject="s", before=1, after=2, evidence_event_id="e", evidence={}, actor="t", provider_failure_key_before="a" * 64, provider_failure_key_after="b" * 64)


def test_coherent_forged_provider_transition_with_recomputed_ids_rejects():
    old = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="old").value
    new = ProviderFailureKey.derive(phase="ph", selected_spec="spec", provider_failure_class="availability", provider_epoch_identity="new").value
    from pathlib import Path
    from tempfile import mkdtemp
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    ledger = IncidentLedger(Path(mkdtemp()))
    evidence = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam")
    change = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=_source("source_revision_changed", 1, key=old), after=_source("source_revision_changed", 2, key=old), evidence_event_id=evidence["payload"]["event_id"], evidence=evidence["payload"], actor="t")
    forged = copy.deepcopy(change.to_dict())
    forged["before_snapshot"]["content"] = 11
    forged["before_snapshot"]["provider_failure_key"] = new
    forged["after_snapshot"]["content"] = 12
    forged["after_snapshot"]["provider_failure_key"] = new
    forged["provider_failure_key_after"] = new
    forged["provider_failure_key_before"] = new
    forged["after_content_id"] = _digest(forged["after_snapshot"])
    forged["before_content_id"] = _digest(forged["before_snapshot"])
    forged["evidence_snapshot"] = {**forged["evidence_snapshot"], "tampered": True}
    forged["evidence_digest"] = _digest(forged["evidence_snapshot"])
    forged["event_id"] = _digest({"reason": forged["reason"], "before": forged["before_content_id"], "after": forged["after_content_id"], "evidence": forged["evidence_event_id"]})
    with pytest.raises(ValueError):
        ChangedPrecondition.from_dict(forged)
    with pytest.raises(ValueError):
        validate_nbf_event(forged)
    with pytest.raises(ValueError):
        ledger._append_nbf(forged)
    with ledger._locked() as (fd, records):
        with pytest.raises(ValueError):
            ledger._append_nbf_locked(fd, forged, records)
    assert not ledger.projection()["changed_preconditions"]
    with pytest.raises(ValueError):
        ledger.append_changed_precondition(forged)
    with pytest.raises(ValueError):
        ledger.reserve(plan_id="p", phase="ph", projection_key="other", semantic_dispatch_fingerprint="g" * 64, logical_dispatch_id="other", dispatch_family_id="fam", changed_precondition_event_id=forged["event_id"])
    assert not ledger.projection()["changed_preconditions"]
    forged_object = ChangedPrecondition(**change.to_dict())
    for name, value in forged.items():
        if name not in {"schema_version", "event_type"}:
            object.__setattr__(forged_object, name, value)
    with pytest.raises(ValueError):
        ledger.consume_changed_precondition(forged_object)


def test_authoritative_before_after_digests_match_source():
    before = _source("source_revision_changed", {"revision": "a"})
    after = _source("source_revision_changed", {"revision": "b"})
    c = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=before, after=after, evidence_event_id="e", evidence={"event_id": "e", "event_type": "source_receipt"}, actor="t")
    assert c.before_content_id == _digest(before.read())
    assert c.after_content_id == _digest(after.read())


def test_valid_reason_specific_source_reader_mints_and_consumes_once(tmp_path):
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    ledger = IncidentLedger(tmp_path)
    evidence = ledger.reserve(plan_id="p", phase="ph", projection_key="pk", semantic_dispatch_fingerprint="f" * 64, logical_dispatch_id="log", dispatch_family_id="fam")
    before = SourceRevisionSource("v1", "source", "source-receipt", {"revision": "a"})
    after = SourceRevisionSource("v2", "source", "source-receipt", {"revision": "b"})
    change = produce_source_revision_changed(plan_id="p", phase="ph", authoritative_subject="source", before=before, after=after, evidence_event_id=evidence["payload"]["event_id"], evidence=evidence["payload"], actor="test")
    ledger.append_changed_precondition(change)
    consumed = ledger.consume_changed_precondition(change)
    assert consumed["payload"]["changed_precondition_event_id"] == change.event_id
    with pytest.raises(ValueError): ledger.consume_changed_precondition(change)
