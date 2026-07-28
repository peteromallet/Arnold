"""Tests for Step 6 schema-parity primitives (T7)."""

import hashlib
import json

import pytest

from arnold_pipelines.megaplan.handlers.schema_parity import (
    SCHEMA_PHASES,
    SchemaParityError,
    SchemaParityReport,
    canonical_schema_hash,
    canonicalize_schema,
    compare_schema_fields,
    compute_full_parity_report,
    schema_hash,
    verify_schema_hash,
    assert_schema_field_parity,
)


# ── canonicalization & hashing ────────────────────────────────────────────

def test_schema_hash_is_deterministic_sha256_hex():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    digest = schema_hash(schema)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    # canonical form is sorted, compact JSON
    expected = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert digest == expected


def test_canonical_schema_hash_is_alias_of_schema_hash():
    schema = {"b": 1, "a": 2}
    assert canonical_schema_hash(schema) == schema_hash(schema)


def test_key_ordering_does_not_change_hash():
    assert schema_hash({"a": 1, "b": 2}) == schema_hash({"b": 2, "a": 1})


def test_nan_is_rejected():
    with pytest.raises(SchemaParityError):
        schema_hash({"v": float("nan")})


def test_none_schema_refused_as_reconstruction():
    with pytest.raises(SchemaParityError):
        schema_hash(None)


def test_non_serializable_schema_refused():
    with pytest.raises(SchemaParityError):
        schema_hash({"v": object()})


# ── field comparison ──────────────────────────────────────────────────────

def test_compare_identical_fields_no_reasons():
    assert compare_schema_fields({"a": 1, "b": 2}, {"a": 1, "b": 2}) == []


def test_compare_missing_field():
    reasons = compare_schema_fields({"a": 1, "b": 2}, {"a": 1})
    assert any(r.startswith("missing:") for r in reasons)


def test_compare_unknown_field():
    reasons = compare_schema_fields({"a": 1}, {"a": 1, "z": 9})
    assert any(r.startswith("unknown:") for r in reasons)


def test_compare_drift_field():
    reasons = compare_schema_fields({"a": 1}, {"a": 2})
    assert any(r.startswith("drift:") for r in reasons)


def test_assert_field_parity_raises_on_missing():
    with pytest.raises(SchemaParityError) as ei:
        assert_schema_field_parity({"a": 1, "b": 2}, {"a": 1}, phase="prompt")
    assert ei.value.phase == "prompt"
    assert "missing" in ei.value.reason


def test_assert_field_parity_raises_on_unknown():
    with pytest.raises(SchemaParityError):
        assert_schema_field_parity({"a": 1}, {"a": 1, "extra": 0}, phase="capture")


def test_assert_field_parity_raises_on_drift():
    with pytest.raises(SchemaParityError):
        assert_schema_field_parity({"a": 1}, {"a": 2}, phase="handler")


def test_assert_field_parity_passes_exact_match():
    assert_schema_field_parity({"a": 1, "b": "x"}, {"a": 1, "b": "x"}, phase="receipt")


def test_assert_field_parity_rejects_defaulting():
    # Producer relies on a default by omitting "b".
    with pytest.raises(SchemaParityError):
        assert_schema_field_parity({"a": 1, "b": "default"}, {"a": 1}, phase="materialization")


def test_assert_field_parity_rejects_stripping():
    # Producer strips "optional" before emitting.
    with pytest.raises(SchemaParityError):
        assert_schema_field_parity({"required": 1, "optional": 2}, {"required": 1}, phase="parser")


def test_assert_field_parity_rejects_inference():
    # Declared type differs from inferred value.
    with pytest.raises(SchemaParityError):
        assert_schema_field_parity({"count": "int"}, {"count": "string"}, phase="scratch")


def test_non_mapping_declared_rejected():
    with pytest.raises(SchemaParityError):
        compare_schema_fields("not-a-map", {})


def test_non_mapping_observed_rejected():
    with pytest.raises(SchemaParityError):
        compare_schema_fields({}, 42)


# ── hash verification ─────────────────────────────────────────────────────

def test_verify_hash_accepts_exact_match():
    schema = {"type": "object"}
    h = schema_hash(schema)
    assert verify_schema_hash(h, schema, phase="prompt") == h


def test_verify_hash_rejects_drift():
    h = schema_hash({"type": "object"})
    with pytest.raises(SchemaParityError) as ei:
        verify_schema_hash(h, {"type": "array"}, phase="capture")
    assert "drift" in ei.value.reason


def test_verify_hash_rejects_missing_declared_hash():
    with pytest.raises(SchemaParityError) as ei:
        verify_schema_hash("", {"a": 1}, phase="handler")
    assert "reconstruction" in ei.value.reason.lower() or "missing" in ei.value.reason.lower()


def test_verify_hash_rejects_none_declared_hash():
    with pytest.raises(SchemaParityError):
        verify_schema_hash(None, {"a": 1}, phase="receipt")


def test_verify_hash_case_insensitive_declared():
    schema = {"x": 1}
    h = schema_hash(schema).upper()
    assert verify_schema_hash(h, schema, phase="replay") == h.lower()


# ── multi-phase report ────────────────────────────────────────────────────

def test_eight_phases_present():
    assert SCHEMA_PHASES == (
        "prompt", "materialization", "scratch", "parser",
        "capture", "handler", "receipt", "replay",
    )


def test_report_satisfied_when_all_declared_match():
    report = SchemaParityReport()
    for phase in SCHEMA_PHASES:
        schema = {"phase": phase}
        report.declare(phase, schema)
        report.observe_and_check(phase, schema)
    assert report.is_satisfied()


def test_report_unsatisfied_when_observation_missing():
    report = SchemaParityReport()
    report.declare("prompt", {"a": 1})
    assert not report.is_satisfied()


def test_report_records_drift_error():
    report = SchemaParityReport()
    report.declare("prompt", {"a": 1})
    with pytest.raises(SchemaParityError):
        report.observe_and_check("prompt", {"a": 2})
    assert not report.is_satisfied()


def test_report_unknown_phase_rejected():
    report = SchemaParityReport()
    with pytest.raises(SchemaParityError):
        report.declare("bogus", {"a": 1})


def test_report_observe_without_declare_refused():
    report = SchemaParityReport()
    with pytest.raises(SchemaParityError) as ei:
        report.observe_and_check("prompt", {"a": 1})
    assert "undeclared" in ei.value.reason or "reconstruction" in ei.value.reason.lower()


def test_compute_full_report_all_match():
    declared = {p: {"phase": p} for p in SCHEMA_PHASES}
    observed = {p: {"phase": p} for p in SCHEMA_PHASES}
    report = compute_full_parity_report(declared, observed)
    assert report.is_satisfied()
    assert not report.errors


def test_compute_full_report_missing_observation():
    declared = {"prompt": {"a": 1}}
    observed = {}
    report = compute_full_parity_report(declared, observed)
    assert not report.is_satisfied()
    assert "prompt" in report.errors


def test_compute_full_report_drift():
    declared = {"capture": {"a": 1}}
    observed = {"capture": {"a": 2}}
    report = compute_full_parity_report(declared, observed)
    assert not report.is_satisfied()
    assert "capture" in report.errors


def test_compute_full_report_unknown_phase():
    declared = {"bogus": {"a": 1}}
    observed = {}
    report = compute_full_parity_report(declared, observed)
    assert not report.is_satisfied()
    assert "bogus" in report.errors


def test_report_partial_declaration_satisfied():
    report = SchemaParityReport()
    report.declare("prompt", {"a": 1})
    report.observe_and_check("prompt", {"a": 1})
    # Only prompt declared; other phases are None and skipped.
    assert report.is_satisfied()
