from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.maintenance_dispatch import (
    EffectReceipt,
    ReceiptAdoptionState,
    ReceiptIdentity,
    ReceiptStatus,
    ReportReceipt,
    UnknownReceipt,
    parse_maintenance_receipt,
    reconcile_typed_maintenance_receipt,
)


@pytest.fixture
def identity() -> ReceiptIdentity:
    return ReceiptIdentity(
        occurrence_id="occ-1",
        request_id="req-1",
        request_digest="req-digest-1",
        immutable_evidence_id="evidence-1",
        immutable_evidence_digest="evidence-digest-1",
        effect_id="effect-1",
        effect_digest="effect-digest-1",
        effect_class="retrigger",
    )


def test_report_and_effect_receipts_are_discriminated(identity: ReceiptIdentity) -> None:
    report_identity = identity.model_copy(
        update={"effect_id": None, "effect_digest": None, "effect_class": None}
    )
    report = ReportReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=report_identity,
        report_id="report-1",
    )
    effect = EffectReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=identity,
        effect_id="effect-1",
        effect_digest="effect-digest-1",
        effect_class="retrigger",
        receipt_id="receipt-1",
    )
    assert report.kind != effect.kind
    assert isinstance(parse_maintenance_receipt(report.model_dump()), ReportReceipt)
    assert isinstance(parse_maintenance_receipt(effect.model_dump()), EffectReceipt)
    with pytest.raises(ValueError):
        ReportReceipt(
            status=ReceiptStatus.SUCCEEDED,
            identity=identity,
            report_id="report-2",
        )


def test_report_only_reconciles_without_effect_coordinates(
    identity: ReceiptIdentity,
) -> None:
    report_identity = identity.model_copy(
        update={"effect_id": None, "effect_digest": None, "effect_class": None}
    )
    report = ReportReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=report_identity,
        report_id="report-1",
    )
    result = reconcile_typed_maintenance_receipt(report, expected=report_identity)
    assert result.state is ReceiptAdoptionState.REPORT_ONLY


def test_effect_adoption_requires_all_immutable_coordinates(identity: ReceiptIdentity) -> None:
    receipt = EffectReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=identity,
        effect_id="effect-1",
        effect_digest="effect-digest-1",
        effect_class="retrigger",
        receipt_id="receipt-1",
    )
    for field in (
        "occurrence_id",
        "request_id",
        "request_digest",
        "effect_id",
        "effect_digest",
        "effect_class",
        "immutable_evidence_id",
        "immutable_evidence_digest",
    ):
        changed = identity.model_copy(update={field: f"changed-{field}"})
        result = reconcile_typed_maintenance_receipt(receipt, expected=changed)
        assert result.state is ReceiptAdoptionState.REJECTED
        assert result.reasons


def test_partial_unknown_and_cross_kind_receipts_fail_closed(
    identity: ReceiptIdentity,
) -> None:
    unknown = parse_maintenance_receipt({"kind": "effect", "status": "mystery"})
    assert isinstance(unknown, UnknownReceipt)
    result = reconcile_typed_maintenance_receipt(unknown, expected=identity)
    assert result.state is ReceiptAdoptionState.INDETERMINATE

    report_identity = identity.model_copy(
        update={"effect_id": None, "effect_digest": None, "effect_class": None}
    )
    report = ReportReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=report_identity,
        report_id="report-1",
    )
    effect_expected = identity
    report_result = reconcile_typed_maintenance_receipt(
        report, expected=effect_expected
    )
    assert report_result.state is ReceiptAdoptionState.REJECTED
    assert "cross_kind_receipt" in report_result.reasons

def test_effect_receipt_adopts_prior_canonical_terminal_without_append(
    identity: ReceiptIdentity,
) -> None:
    receipt = EffectReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=identity,
        effect_id="effect-1",
        effect_digest="effect-digest-1",
        effect_class="retrigger",
        receipt_id="effect-event-1",
    )

    class Ledger:
        def __init__(self) -> None:
            self.lookups: list[str] = []
            self.appends = 0

        def lookup_maintenance_event(self, key: str) -> dict[str, object]:
            self.lookups.append(key)
            return {"event_id": key, "outcome": "succeeded"}

        def append(self, _event: object) -> None:
            self.appends += 1

    ledger = Ledger()
    from arnold_pipelines.megaplan.cloud.maintenance_dispatch import (
        reconcile_effect_receipt,
    )

    result = reconcile_effect_receipt(receipt, expected=identity, ledger=ledger)
    assert result.state is ReceiptAdoptionState.ADOPTED
    assert ledger.lookups == ["effect-event-1"]
    assert ledger.appends == 0

def test_rearm_consumes_only_failed_session_status_and_identity(
    identity: ReceiptIdentity,
) -> None:
    from arnold_pipelines.megaplan.cloud.maintenance_dispatch import (
        failed_session_receipt_allows_rearm,
    )

    report_identity = identity.model_copy(
        update={"effect_id": None, "effect_digest": None, "effect_class": None}
    )
    failed = ReportReceipt(
        status=ReceiptStatus.FAILED,
        identity=report_identity,
        report_id="session-1",
        returncode=1,
    )
    completed = failed.model_copy(update={"status": ReceiptStatus.SUCCEEDED})
    assert failed_session_receipt_allows_rearm(failed, expected=report_identity)
    assert not failed_session_receipt_allows_rearm(
        completed, expected=report_identity
    )

def test_terminal_adoption_is_side_effect_free(identity: ReceiptIdentity) -> None:
    receipt = EffectReceipt(
        status=ReceiptStatus.SUCCEEDED,
        identity=identity,
        effect_id="effect-1",
        effect_digest="effect-digest-1",
        effect_class="retrigger",
        receipt_id="receipt-1",
    )
    prior = {"seq": 7, "status": "succeeded"}
    result = reconcile_typed_maintenance_receipt(
        receipt, expected=identity, prior_terminal=prior
    )
    assert result.state is ReceiptAdoptionState.ADOPTED
    assert result.prior_terminal == prior


def test_request_file_is_not_completion_evidence(identity: ReceiptIdentity, tmp_path: Path) -> None:
    request = tmp_path / "request.json"
    request.write_text("{}", encoding="utf-8")
    assert request.exists()
    result = reconcile_typed_maintenance_receipt(None, expected=identity)
    assert result.state is ReceiptAdoptionState.INDETERMINATE
