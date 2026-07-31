"""Focused tests for deterministic auditor reason reduction."""

from __future__ import annotations

import copy

from arnold_pipelines.megaplan.observability.auditor_reasons import (
    AuditorReasonFamily,
    REASON_ORDER,
    auditor_reason_fixture,
    auditor_reason_fixtures,
    reduce_auditor_reasons,
)


EXPECTED_FAMILIES = (
    "consecutive_normalized_blocks",
    "signature_drift",
    "unclosed_custody",
    "index_mismatch",
    "detection_slo_breach",
    "executor_repair_overlap",
    "cross_session_joins",
    "projection_amplification",
    "full_seriality",
    "oversized_rework",
    "invalid_model",
    "missing_ledger_coverage",
)


def _fixture_ids(records: tuple[dict, ...]) -> tuple[str, ...]:
    return tuple(record["evidence_id"] for record in records)


def test_reason_enum_contains_exactly_the_twelve_auditor_families() -> None:
    assert tuple(family.value for family in AuditorReasonFamily) == EXPECTED_FAMILIES
    assert tuple(family.value for family in REASON_ORDER) == EXPECTED_FAMILIES


def test_each_canonical_fixture_fires_exactly_once() -> None:
    for family in AuditorReasonFamily:
        records = auditor_reason_fixture(family)
        reasons = reduce_auditor_reasons(records)
        assert [reason.family for reason in reasons] == [family]
        assert reasons[0].evidence_ids == _fixture_ids(records)


def test_combined_fixtures_fire_every_family_once() -> None:
    records = auditor_reason_fixtures()
    reasons = reduce_auditor_reasons(records)

    assert tuple(reason.family.value for reason in reasons) == EXPECTED_FAMILIES
    assert len(reasons) == 12
    assert len({reason.family for reason in reasons}) == 12
    for reason in reasons:
        assert reason.evidence_ids
        assert all(evidence_id.startswith("ev-") for evidence_id in reason.evidence_ids)


def test_reduction_is_deterministic_for_repeated_runs() -> None:
    records = auditor_reason_fixtures()
    first = [reason.to_dict() for reason in reduce_auditor_reasons(records)]
    second = [reason.to_dict() for reason in reduce_auditor_reasons(records)]
    assert first == second


def test_reduction_is_independent_of_mapping_key_order() -> None:
    records = auditor_reason_fixtures()
    reordered: list[dict] = []
    for record in records:
        reordered.append({key: record[key] for key in reversed(tuple(record.keys()))})

    assert [reason.to_dict() for reason in reduce_auditor_reasons(tuple(reordered))] == [
        reason.to_dict() for reason in reduce_auditor_reasons(records)
    ]


def test_reasons_never_invent_evidence_ids() -> None:
    records = list(auditor_reason_fixture(AuditorReasonFamily.INDEX_MISMATCH))
    records[0] = dict(records[0])
    del records[0]["evidence_id"]

    assert reduce_auditor_reasons(tuple(records)) == ()


def test_reason_ids_bind_family_details_and_evidence_ids() -> None:
    records = auditor_reason_fixture(AuditorReasonFamily.INVALID_MODEL)
    reason = reduce_auditor_reasons(records)[0]
    changed = copy.deepcopy(records[0])
    changed["evidence_id"] = "ev-invalid-model-different"
    changed_reason = reduce_auditor_reasons((changed,))[0]

    assert reason.reason_id.startswith("invalid_model:")
    assert reason.reason_id != changed_reason.reason_id
    assert reason.to_dict()["evidence_ids"] == ["ev-invalid-model"]


def test_non_triggering_records_do_not_emit_reasons() -> None:
    records = (
        {
            "evidence_id": "ev-ok-block",
            "sequence": 1,
            "kind": "normalized_block",
            "status": "ok",
            "normalized_signature": "same",
        },
        {
            "evidence_id": "ev-ok-index",
            "sequence": 2,
            "kind": "index_check",
            "expected_index": 3,
            "observed_index": 3,
        },
        {
            "evidence_id": "ev-ok-model",
            "sequence": 3,
            "kind": "model_check",
            "model": "gpt-5.5",
            "valid_models": ["gpt-5.5"],
        },
    )

    assert reduce_auditor_reasons(records) == ()
