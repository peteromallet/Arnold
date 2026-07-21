"""M9 proof tests for deterministic auditor reason evidence bindings."""

from __future__ import annotations

import copy

from arnold_pipelines.megaplan.observability.auditor_reasons import (
    AuditorReasonFamily,
    auditor_reason_fixture,
    auditor_reason_fixtures,
    reduce_auditor_reasons,
)


EXPECTED_FIXTURE_IDS = {
    family: tuple(record["evidence_id"] for record in auditor_reason_fixture(family))
    for family in AuditorReasonFamily
}


def test_each_deterministic_reason_fires_once_with_exact_fixture_evidence_ids() -> None:
    for family in AuditorReasonFamily:
        reasons = reduce_auditor_reasons(auditor_reason_fixture(family))

        assert [reason.family for reason in reasons] == [family]
        assert reasons[0].evidence_ids == EXPECTED_FIXTURE_IDS[family]
        assert reasons[0].to_dict()["evidence_ids"] == list(EXPECTED_FIXTURE_IDS[family])


def test_combined_fixture_emits_one_reason_per_family_in_stable_order() -> None:
    reasons = reduce_auditor_reasons(auditor_reason_fixtures())

    assert tuple(reason.family for reason in reasons) == tuple(AuditorReasonFamily)
    assert len(reasons) == len(AuditorReasonFamily)
    assert len({reason.family for reason in reasons}) == len(AuditorReasonFamily)
    assert [reason.evidence_ids for reason in reasons] == [
        EXPECTED_FIXTURE_IDS[family] for family in AuditorReasonFamily
    ]


def test_missing_evidence_id_suppresses_only_that_reason_family() -> None:
    records = []
    dropped_family = AuditorReasonFamily.SIGNATURE_DRIFT
    for record in auditor_reason_fixtures():
        copied = copy.deepcopy(record)
        if copied.get("auditor_reason_family") == dropped_family.value:
            copied.pop("evidence_id", None)
        records.append(copied)

    reasons = reduce_auditor_reasons(tuple(records))

    assert dropped_family not in {reason.family for reason in reasons}
    assert len(reasons) == len(AuditorReasonFamily) - 1
    for reason in reasons:
        assert reason.evidence_ids == EXPECTED_FIXTURE_IDS[reason.family]


def test_reason_ids_are_stable_and_bind_exact_evidence_ids() -> None:
    records = auditor_reason_fixture(AuditorReasonFamily.INVALID_MODEL)
    reason = reduce_auditor_reasons(records)[0]
    repeated = reduce_auditor_reasons(copy.deepcopy(records))[0]
    changed_record = copy.deepcopy(records[0])
    changed_record["evidence_id"] = "ev-invalid-model-drifted"
    changed = reduce_auditor_reasons((changed_record,))[0]

    assert reason.reason_id == repeated.reason_id
    assert reason.reason_id != changed.reason_id
    assert reason.evidence_ids == ("ev-invalid-model",)
    assert changed.evidence_ids == ("ev-invalid-model-drifted",)
