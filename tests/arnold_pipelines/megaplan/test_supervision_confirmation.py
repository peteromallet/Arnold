from pathlib import Path
import pytest
from arnold_pipelines.megaplan.incident.disposition import observe_confirmation, consume_confirmation
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger


def _consume_process(root, confirmation_id, result):
    try:
        consume_confirmation(IncidentLedger(root), confirmation_id_value=confirmation_id, second_observed_at="2026-01-01T00:00:02+00:00", second_evidence={"alive": True}, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, expires_at=1767225630.0, confirmation_policy_identity="default-v1", schema_version=1, disposition_id="disp")
        result.put("consumed")
    except Exception as exc:
        result.put(type(exc).__name__)


def test_confirmation_ttl_and_single_consumption(tmp_path: Path):
    ledger=IncidentLedger(tmp_path)
    first=observe_confirmation(ledger,site_id="watchdog",subject_class="worker",plan_id="p",admission_receipt_id="r",victim_pid=1,victim_process_start_identity="start",relevant_progress_identity="seq0",supervisor_incarnation_identity="sup",cause_kind="wedge",scan_interval_s=2,observed_at="2026-01-01T00:00:00+00:00",evidence={"alive":True})
    cid=first["payload"]["confirmation_id"]
    used=consume_confirmation(ledger,confirmation_id_value=cid,second_observed_at="2026-01-01T00:00:02+00:00",second_evidence={"alive":True}, victim_pid=1, victim_process_start_identity="start", relevant_progress_identity="seq0", supervisor_incarnation_identity="sup", cause_kind="wedge", scan_interval_s=2, expires_at=1767225630.0, confirmation_policy_identity="default-v1", schema_version=1)
    assert used["payload"]["confirmation_id"] == cid
    with pytest.raises(ValueError): consume_confirmation(ledger,confirmation_id_value=cid,second_observed_at="2026-01-01T00:00:04+00:00",second_evidence={})


def test_second_scan_too_early_and_expired_rejected(tmp_path):
    ledger=IncidentLedger(tmp_path); first=observe_confirmation(ledger,site_id="w",subject_class="worker",plan_id=None,admission_receipt_id=None,victim_pid=4,victim_process_start_identity="s",relevant_progress_identity="q",supervisor_incarnation_identity="i",cause_kind="wedge",scan_interval_s=1,observed_at="2026-01-01T00:00:00+00:00",evidence={})
    cid=first["payload"]["confirmation_id"]
    with pytest.raises(ValueError): consume_confirmation(ledger,confirmation_id_value=cid,second_observed_at="2026-01-01T00:00:00.5+00:00",second_evidence={}, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, expires_at=1767225630.0, confirmation_policy_identity="default-v1", schema_version=1)
    with pytest.raises(ValueError): consume_confirmation(ledger,confirmation_id_value=cid,second_observed_at="2026-01-01T00:10:00+00:00",second_evidence={}, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, expires_at=1767225630.0, confirmation_policy_identity="default-v1", schema_version=1)


def test_confirmation_compares_pid_start_progress_incarnation_cause(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    first = observe_confirmation(ledger, site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, observed_at="2026-01-01T00:00:00+00:00", evidence={"alive": True})
    common = dict(confirmation_id_value=first["payload"]["confirmation_id"], second_observed_at="2026-01-01T00:00:01+00:00", second_evidence={"alive": True}, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, expires_at=1767225630.0, confirmation_policy_identity="default-v1", schema_version=1)
    for field, value in (("victim_pid", 5), ("victim_process_start_identity", "replacement"), ("relevant_progress_identity", "advanced"), ("supervisor_incarnation_identity", "replacement-supervisor"), ("cause_kind", "timeout")):
        with pytest.raises(ValueError):
            consume_confirmation(ledger, **{**common, field: value})
    for field in ("victim_pid", "victim_process_start_identity", "relevant_progress_identity", "supervisor_incarnation_identity", "cause_kind"):
        omitted = dict(common)
        omitted.pop(field)
        with pytest.raises(ValueError):
            consume_confirmation(ledger, **omitted)
    for field, value in (("scan_interval_s", 2), ("expires_at", 1767225631.0), ("confirmation_policy_identity", "other-policy"), ("schema_version", 2)):
        with pytest.raises(ValueError):
            consume_confirmation(ledger, **{**common, field: value})
    for field in ("scan_interval_s", "expires_at", "confirmation_policy_identity", "schema_version"):
        omitted = dict(common)
        omitted.pop(field)
        with pytest.raises(ValueError):
            consume_confirmation(ledger, **omitted)
    with pytest.raises(ValueError):
        consume_confirmation(ledger, **{**common, "second_evidence": {"alive": False}})
    omitted_evidence = dict(common)
    omitted_evidence.pop("second_evidence")
    with pytest.raises(TypeError):
        consume_confirmation(ledger, **omitted_evidence)
    with pytest.raises(ValueError):
        ledger.consume_confirmation(
            confirmation_id=first["payload"]["confirmation_id"],
            second_observed_at=common["second_observed_at"],
            second_evidence_digest=None,
            victim_pid=common["victim_pid"],
            victim_process_start_identity=common["victim_process_start_identity"],
            relevant_progress_identity=common["relevant_progress_identity"],
            supervisor_incarnation_identity=common["supervisor_incarnation_identity"],
            cause_kind=common["cause_kind"],
            scan_interval_s=common["scan_interval_s"],
            expires_at=common["expires_at"],
            confirmation_policy_identity=common["confirmation_policy_identity"],
            schema_version=common["schema_version"],
        )


def test_expire_confirmation_after_consume_rejects(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    first = observe_confirmation(ledger, site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, observed_at="2026-01-01T00:00:00+00:00", evidence={"alive": True})
    cid = first["payload"]["confirmation_id"]
    consume_confirmation(ledger, confirmation_id_value=cid, second_observed_at="2026-01-01T00:00:01+00:00", second_evidence={"alive": True}, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, expires_at=1767225630.0, confirmation_policy_identity="default-v1", schema_version=1)
    with pytest.raises(ValueError):
        ledger.expire_confirmation(cid, observed_at="2026-01-01T00:01:00+00:00")
    assert ledger.projection()["confirmations"][cid]["consumed"] is True


def test_confirmation_replacement_and_expiry_are_durable(tmp_path: Path):
    ledger = IncidentLedger(tmp_path)
    observe_confirmation(ledger, site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, observed_at="2026-01-01T00:00:00+00:00", evidence={"alive": True})
    observe_confirmation(ledger, site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="new", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, observed_at="2026-01-01T00:00:01+00:00", evidence={"alive": True})
    assert any(r["payload"]["event_type"] == "supervision_confirmation_replaced" for r in ledger.read_nbf_events())
    replacement_id = ledger.read_nbf_events()[-1]["payload"]["confirmation_id"]
    ledger.expire_confirmation(replacement_id, observed_at="2026-01-01T00:01:00+00:00")
    assert any(r["payload"]["event_type"] == "supervision_confirmation_expired" for r in ledger.read_nbf_events())


def test_confirmation_survives_ledger_reopen_with_original_expiry(tmp_path: Path):
    first = observe_confirmation(IncidentLedger(tmp_path), site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=2, observed_at="2026-01-01T00:00:00+00:00", evidence={"alive": True})
    reopened = IncidentLedger(tmp_path).projection()["confirmations"][first["payload"]["confirmation_id"]]
    assert reopened["expires_at"] == first["payload"]["expires_at"]
    same = observe_confirmation(IncidentLedger(tmp_path), site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=2, observed_at="2026-01-01T00:00:01+00:00", evidence={"alive": True})
    assert same["payload"]["first_observed_at"] == first["payload"]["first_observed_at"]


def test_two_process_confirmation_single_consumer(tmp_path: Path):
    first = observe_confirmation(IncidentLedger(tmp_path), site_id="w", subject_class="worker", plan_id=None, admission_receipt_id=None, victim_pid=4, victim_process_start_identity="s", relevant_progress_identity="q", supervisor_incarnation_identity="i", cause_kind="wedge", scan_interval_s=1, observed_at="2026-01-01T00:00:00+00:00", evidence={"alive": True})
    import multiprocessing
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    processes = [ctx.Process(target=_consume_process, args=(tmp_path, first["payload"]["confirmation_id"], queue)) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
    results = [queue.get(timeout=2) for _ in processes]
    assert results.count("consumed") == 1
    assert len([record for record in IncidentLedger(tmp_path).read_nbf_events() if record["payload"]["event_type"] == "supervision_confirmation_consumed"]) == 1
