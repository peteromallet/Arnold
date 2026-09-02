"""Executable matrix and round-trip tests for the internal C2 wire contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.workflow.completion.binding import bind
from arnold.workflow.completion.evaluation import CompletionVerdict
from arnold.workflow.completion.evidence import EvidenceScope, EvidenceWindow, ScalarCursor
from arnold.workflow.completion.spec import SubjectKind, make_completion_spec
from arnold.workflow.completion.wire import (
    ACCEPTANCE_REFERENCE_SCHEMA_VERSION,
    ChangedBindingError,
    DecodeDisposition,
    ShadowAcceptanceReference,
    UnknownFutureVersionError,
    decode_acceptance_reference,
    decode_binding,
    decode_record,
    decode_spec,
    decode_verdict,
    encode_acceptance_reference,
    encode_binding,
    encode_spec,
    encode_verdict,
)


FIXTURE = Path(__file__).parents[2] / "fixtures" / "native_c2" / "decoder_matrix.json"


def _records() -> dict[str, object]:
    spec = make_completion_spec(
        obligation_id="wire:spec",
        subject_kind=SubjectKind.STEP,
        canonical_name="wire.step",
    )
    scope = EvidenceScope(
        subject_id="subject:wire",
        occurrence_id="occurrence:wire",
        attempt_id="attempt:1",
        generation=0,
        source_lock="sha256:" + "1" * 64,
        runtime_lock="sha256:" + "2" * 64,
        dependency_lock="sha256:" + "3" * 64,
        store_id="store:wire",
        store_incarnation="incarnation:1",
        restore_id="restore:1",
        restore_generation=0,
        evidence_window=EvidenceWindow(ScalarCursor(1), ScalarCursor(2)),
        custody={"lease": "wire"},
        authority_fence={"fence": "wire"},
        epoch=1,
        wbc_version="wbc.v1",
        admitted_child_set_digest="sha256:" + "4" * 64,
    )
    binding = bind(spec, "subject:wire", evidence_scope=scope)
    verdict = CompletionVerdict(spec_hash=spec.spec_hash, binding_hash=binding.binding_hash)
    reference = ShadowAcceptanceReference(
        binding_hash=binding.binding_hash,
        verdict_hash=verdict.verdict_hash,
        acceptance_transaction_hash="sha256:" + "5" * 64,
    )
    return {"spec": spec, "binding": binding, "verdict": verdict, "shadow_acceptance_reference": reference}


def _encoded(kind: str, records: dict[str, object]) -> bytes:
    return {
        "spec": encode_spec(records["spec"]),
        "binding": encode_binding(records["binding"]),
        "verdict": encode_verdict(records["verdict"]),
        "shadow_acceptance_reference": encode_acceptance_reference(
            records["shadow_acceptance_reference"]
        ),
    }[kind]


def test_known_v1_and_v2_records_are_byte_stable_and_round_trip() -> None:
    records = _records()
    for kind, record in records.items():
        encoded = _encoded(kind, records)
        assert encoded == _encoded(kind, records)
        result = decode_record(encoded, expected_kind=kind)
        assert result.disposition is DecodeDisposition.DECODED
        assert result.record == record


def test_strict_family_decoders_dispatch_on_wire_kind_and_version() -> None:
    records = _records()
    assert decode_spec(encode_spec(records["spec"])) == records["spec"]
    assert decode_binding(encode_binding(records["binding"])) == records["binding"]
    assert decode_verdict(encode_verdict(records["verdict"])) == records["verdict"]
    assert decode_acceptance_reference(
        encode_acceptance_reference(records["shadow_acceptance_reference"])
    ) == records["shadow_acceptance_reference"]


def test_legacy_ambiguous_binding_is_unknown_without_coordinate_reinterpretation() -> None:
    records = _records()
    payload = json.loads(encode_binding(records["binding"]))["payload"]
    payload.pop("evidence_scope")
    payload["evidence_window"] = ["old-start", "old-end"]
    payload["semantic_path"] = "must-not-be-used"
    result = decode_record(
        {"record_kind": "binding", "payload": payload},
        expected_kind="binding",
    )
    assert result.disposition is DecodeDisposition.LEGACY_UNKNOWN
    assert result.record is None


def test_unknown_future_versions_are_quarantined_before_body_decode() -> None:
    records = _records()
    envelope = json.loads(encode_spec(records["spec"]))
    envelope["schema_version"] = "arnold.workflow.completion_spec.v99"
    envelope["payload"] = {"invalid": "body"}
    result = decode_record(envelope, expected_kind="spec")
    assert result.disposition is DecodeDisposition.UNKNOWN_FUTURE
    assert result.record is None
    with pytest.raises(UnknownFutureVersionError):
        decode_spec(envelope)


def test_matrix_covers_all_families_and_failure_outcomes() -> None:
    matrix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = _records()
    assert set(matrix["record_kinds"]) == set(records)
    assert {case["expected"] for case in matrix["cases"]} >= {
        "decoded",
        "legacy/unknown",
        "corrupt",
        "unknown-future",
        "changed-binding",
    }
    for case in matrix["cases"]:
        kind = case["record_kind"]
        if case.get("mutation") == "legacy_ambiguous":
            payload = json.loads(encode_binding(records["binding"]))["payload"]
            payload.pop("evidence_scope")
            payload["evidence_window"] = ["old-start", "old-end"]
            payload["semantic_path"] = "ambiguous"
            value = {"record_kind": kind, "payload": payload}
        elif case.get("mutation") == "corrupt_json":
            value = b"{not-json"
        elif case.get("mutation") == "future_version":
            value = json.loads(_encoded(kind, records))
            value["schema_version"] = value["schema_version"].rsplit(".v", 1)[0] + ".v99"
        elif case.get("mutation") == "changed_binding":
            value = _encoded(kind, records)
        else:
            value = _encoded(kind, records)
        result = decode_record(
            value,
            expected_kind=kind,
            expected_binding_hash=("sha256:" + "f" * 64)
            if case.get("mutation") == "changed_binding"
            else None,
        )
        assert result.disposition.value == case["expected"], case["id"]


def test_changed_binding_requires_explicit_resume_disposition() -> None:
    reference = _records()["shadow_acceptance_reference"]
    with pytest.raises(ChangedBindingError):
        decode_acceptance_reference(
            encode_acceptance_reference(reference),
            expected_binding_hash="sha256:" + "f" * 64,
        )


def test_reference_is_explicitly_non_authoritative() -> None:
    reference = _records()["shadow_acceptance_reference"]
    assert reference.authoritative is False
    assert "not authoritative" in reference.warning
    assert reference.schema_version == ACCEPTANCE_REFERENCE_SCHEMA_VERSION
