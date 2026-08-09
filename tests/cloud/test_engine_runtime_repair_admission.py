"""Regression tests for typed editable-runtime repair admission."""

from __future__ import annotations

from arnold_pipelines.megaplan.cloud.engine_runtime_repair import (
    ENGINE_RUNTIME_EFFECT_CLASS,
    ENGINE_RUNTIME_REPAIR_SCHEMA,
    SOURCE_REPAIR_SCOPE,
    parse_engine_runtime_repair_admission,
    materialize_engine_runtime_repair_admission,
    validate_engine_runtime_repair_admission,
)


def _admission(occurrence: str = "sha256:occurrence") -> dict[str, object]:
    return {
        "schema_version": ENGINE_RUNTIME_REPAIR_SCHEMA,
        "admission_id": "admission:one",
        "effect_class": ENGINE_RUNTIME_EFFECT_CLASS,
        "repair_scope": SOURCE_REPAIR_SCOPE,
        "occurrence_fingerprint": occurrence,
        "candidate": {
            "revision": "0123456789abcdef0123456789abcdef01234567",
            "runtime_sha256": "a" * 64,
            "verification_digest": "b" * 64,
            "provenance_digest": "c" * 64,
            "effect_barrier_digest": "d" * 64,
        },
        "authority": {
            "decision": "approved",
            "model": "gpt-5.6-sol",
            "profile": "horizon-a",
        },
        "run_authority_receipt": "run-authority:one",
        "custody_receipt": "custody:one",
        "wbc_receipt": "wbc:one",
        "fence_token": "fence:one",
        "one_effect": True,
    }


def test_horizon_a_admission_is_bound_to_exact_occurrence():
    payload = _admission()
    ok, reason = validate_engine_runtime_repair_admission(
        payload, occurrence_fingerprint="sha256:occurrence"
    )
    assert ok is True
    assert "Horizon-A" in reason
    parsed = parse_engine_runtime_repair_admission(
        payload, occurrence_fingerprint="sha256:occurrence"
    )
    assert parsed is not None
    assert parsed.candidate_revision.startswith("01234567")
    assert parsed.to_dict()["one_effect"] is True


def test_missing_receipt_or_wrong_model_fails_closed():
    payload = _admission()
    payload.pop("wbc_receipt")
    assert validate_engine_runtime_repair_admission(payload)[0] is False

    payload = _admission()
    payload["authority"] = {
        "decision": "approved",
        "model": "deepseek-v4-pro",
        "profile": "horizon-a",
    }
    assert validate_engine_runtime_repair_admission(payload)[0] is False


def test_occurrence_mismatch_cannot_authorize_candidate():
    ok, _ = validate_engine_runtime_repair_admission(
        _admission("sha256:other"), occurrence_fingerprint="sha256:current"
    )
    assert ok is False


def test_operator_charge_materializes_only_when_complete():
    payload = _admission("sha256:occurrence")
    # The queue producer may call this with a Sol review nested under the
    # operator charge; the bridge copies it but never invents receipts.
    charge = dict(payload)
    charge["sol_review"] = charge.pop("authority")
    materialized = materialize_engine_runtime_repair_admission(
        occurrence_fingerprint="sha256:occurrence",
        operator_charge=charge,
    )
    assert materialized is not None
    assert materialized["authority"]["model"] == "gpt-5.6-sol"

    charge.pop("wbc_receipt")
    assert materialize_engine_runtime_repair_admission(
        occurrence_fingerprint="sha256:occurrence", operator_charge=charge
    ) is None
