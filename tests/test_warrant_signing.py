from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from megaplan._core.canonical import (
    canonical_projection_bytes,
    canonical_projection_sha256,
    canonical_projection_sha256_uri,
    hmac_sha256_hex,
    sign_canonical_projection,
    verify_canonical_projection_signature,
)
from megaplan._core.config_resolver import ConfigResolver
from megaplan.schemas import WarrantSignature
from megaplan.store.warrant import (
    WarrantError,
    build_warrant,
    verify_warrant,
    warrant_signed_envelope,
)
from megaplan.store.warrant_sources import build_warrant_source_projection
from megaplan.store.warrant_sources import inventory_warrant_sources


def _projection() -> dict[str, object]:
    return {
        "projection_id": "projection_1",
        "completeness": {
            "signable": True,
            "required_fields": ["authority", "account"],
            "present": ["account", "authority"],
            "missing": [],
            "unsupported": [],
        },
        "authority": {"authority_id": "authority_1", "policy_envelope": {"limit": 10}},
        "account": {
            "account_id": "account_1",
            "verified_result_ref": {"receipt_id": "receipt_1"},
        },
    }


def _complete_source_projection():
    verified_result_ref = {"kind": "verified_result", "sha256": "sha256:" + "a" * 64}
    captured_at = "2026-06-01T00:00:00Z"
    return build_warrant_source_projection(
        authority_envelope={
            "authority_id": "authority_1",
            "policy_envelope": {"allow_models": ["codex:gpt-5.5"], "spend_ceiling_usd": 10},
            "grantor": "ops",
            "captured_at": captured_at,
        },
        verified_work_account={
            "account_id": "account_1",
            "verified_work_units": [{"task_id": "T12", "status": "done"}],
            "verified_result_ref": verified_result_ref,
        },
        rationale_anchor={
            "anchor_id": "rationale_1",
            "manifest_hash": "sha256:" + "b" * 64,
            "rationale_ref": {"path": "review.json", "field": "summary"},
            "captured_at": captured_at,
        },
        behavioral_or_manifest_hash="sha256:" + "b" * 64,
        verified_result_ref=verified_result_ref,
        unsupported=("provider_cost_ref", "ledger_refs"),
        source_refs={"review_ref": "review.json"},
        projection_id="projection_1",
    )


def _adapter_complete_projection(kind: str):
    manifest_hash = "sha256:" + "c" * 64
    result_ref = {
        "kind": "final_decision",
        "sha256": "sha256:" + "d" * 64,
        "decision_id": "decision-42",
    }
    captured_at = "2026-06-01T12:00:00Z"
    units = [{"task_id": "T13", "status": "done", "mode": kind}]
    if kind == "multi-step":
        units.append({"task_id": "T13-review", "status": "done", "mode": "review"})
    return build_warrant_source_projection(
        authority_envelope={
            "authority_id": "adapter-authority",
            "policy_envelope": {
                "allowed_adapter": kind,
                "scope": "terminal-sink",
            },
            "grantor": "ops",
            "autonomy_level": "supervised",
            "captured_at": captured_at,
        },
        verified_work_account={
            "account_id": f"{kind}-verified-work",
            "verified_work_units": units,
            "verified_result_ref": result_ref,
        },
        rationale_anchor={
            "anchor_id": "decision-time-rationale",
            "manifest_hash": manifest_hash,
            "rationale_ref": {
                "path": "review.json",
                "field": "decision_rationale",
                "decision_id": "decision-42",
            },
            "captured_at": captured_at,
        },
        behavioral_or_manifest_hash=manifest_hash,
        verified_result_ref=result_ref,
        unsupported=("provider_cost_ref", "ledger_refs"),
        source_refs={
            "adapter": kind,
            "review_ref": "review.json",
            "decision_ref": "phase_result.json",
        },
        projection_id=f"{kind}-adapter-complete",
    )


def test_canonical_projection_bytes_and_sha_uri_are_stable() -> None:
    left = _projection()
    right = {
        "account": {
            "verified_result_ref": {"receipt_id": "receipt_1"},
            "account_id": "account_1",
        },
        "authority": {"policy_envelope": {"limit": 10}, "authority_id": "authority_1"},
        "completeness": {
            "unsupported": [],
            "missing": [],
            "present": ["account", "authority"],
            "required_fields": ["authority", "account"],
            "signable": True,
        },
        "projection_id": "projection_1",
    }

    assert canonical_projection_bytes(left) == canonical_projection_bytes(right)
    assert canonical_projection_bytes(left).startswith(b'{"account":')
    assert canonical_projection_sha256_uri(left) == (
        f"sha256:{canonical_projection_sha256(left)}"
    )


def test_warrant_key_env_precedence_over_lower_layers() -> None:
    state = {
        "config": {
            "override": {"signing": {"warrant_key": "override-key"}},
            "profile_settings": {"signing": {"warrant_key": "profile-key"}},
            "robustness_settings": {"signing": {"warrant_key": "robustness-key"}},
        }
    }
    resolver = ConfigResolver(
        state=state,
        env={"MEGAPLAN_SIGNING_WARRANT_KEY": "env-key"},
    )

    assert resolver.effective("signing", "warrant_key") == "env-key"
    assert resolver.explicit_at("signing", "warrant_key") == "env"


def test_warrant_key_defaults_to_empty_string() -> None:
    resolver = ConfigResolver(env={})

    assert resolver.effective("signing", "warrant_key") == ""
    assert resolver.explicit_at("signing", "warrant_key") is None


def test_hmac_signing_rejects_empty_warrant_key() -> None:
    with pytest.raises(ValueError, match="warrant signing key must be non-empty"):
        hmac_sha256_hex("", b"payload")


def test_warrant_signature_verifies_and_round_trips_schema() -> None:
    projection = _projection()
    signature_payload = sign_canonical_projection(
        projection,
        warrant_key="secret-key",
        key_id="test-key",
        signed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    signature = WarrantSignature.model_validate(signature_payload)

    assert signature.algorithm == "hmac-sha256"
    assert signature.signed_payload_sha256 == canonical_projection_sha256_uri(projection)
    assert verify_canonical_projection_signature(
        projection,
        signature.model_dump(mode="json"),
        warrant_key="secret-key",
    )


def test_warrant_signature_verification_fails_on_tamper() -> None:
    projection = _projection()
    signature = sign_canonical_projection(projection, warrant_key="secret-key")
    tampered = {**projection, "projection_id": "projection_2"}

    assert not verify_canonical_projection_signature(
        tampered,
        signature,
        warrant_key="secret-key",
    )


def test_build_warrant_rejects_partial_projection_before_signing() -> None:
    projection = build_warrant_source_projection(
        authority_envelope={"authority_id": "authority_1", "policy_envelope": {}},
        projection_id="partial_projection",
    )

    with pytest.raises(WarrantError) as exc_info:
        build_warrant(projection, warrant_key="secret-key")
    assert exc_info.value.error_kind == "incomplete_warrant_source"
    assert "verified_work_account" in exc_info.value.details["missing"]
    assert "verified_work_account" in exc_info.value.details["missing_required"]
    assert exc_info.value.details["unsupported_required"] == []
    assert exc_info.value.details["present"] == ["authority_envelope"]
    assert any("verified_work_account" in step for step in exc_info.value.details["next_steps"])


def test_build_warrant_incomplete_projection_reports_unsupported_required_fields() -> None:
    projection = build_warrant_source_projection(
        authority_envelope={"authority_id": "authority_1", "policy_envelope": {}},
        unsupported=["verified_result_ref"],
        projection_id="unsupported_projection",
    )

    with pytest.raises(WarrantError) as exc_info:
        build_warrant(projection, warrant_key="secret-key")

    assert exc_info.value.error_kind == "incomplete_warrant_source"
    assert "verified_result_ref" in exc_info.value.details["unsupported_required"]
    assert "authority_envelope" in exc_info.value.details["present"]
    assert any("source adapter support" in step for step in exc_info.value.details["legal_moves"])


def test_build_warrant_resolves_configured_key_and_verifies_complete_projection() -> None:
    resolver = ConfigResolver(env={"MEGAPLAN_SIGNING_WARRANT_KEY": "configured-key"})
    projection = _complete_source_projection()

    result = build_warrant(
        projection,
        resolver=resolver,
        key_id="configured",
        issued_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        signed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert result.warrant.signature.key_id == "configured"
    assert result.signed_envelope_sha256 == result.warrant.signature.signed_payload_sha256
    assert verify_warrant(result.warrant, resolver=resolver)


def test_build_and_verify_warrant_reject_missing_configured_key() -> None:
    projection = _complete_source_projection()

    with pytest.raises(WarrantError) as exc_info:
        build_warrant(projection, resolver=ConfigResolver(env={}))
    assert exc_info.value.error_kind == "missing_warrant_key"

    built = build_warrant(projection, warrant_key="secret-key")
    with pytest.raises(WarrantError) as verify_exc:
        verify_warrant(built.warrant, resolver=ConfigResolver(env={}))
    assert verify_exc.value.error_kind == "missing_warrant_key"


def test_warrant_verification_fails_on_signed_byte_tamper() -> None:
    built = build_warrant(
        _complete_source_projection(),
        warrant_key="secret-key",
        issued_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        signed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    tampered = built.warrant.model_dump(mode="json")
    tampered["verified_result_ref"] = {"kind": "verified_result", "sha256": "sha256:" + "f" * 64}

    assert not verify_warrant(tampered, warrant_key="secret-key")


def test_warrant_canonical_stability_for_equivalent_source_projection_ordering() -> None:
    issued_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    left = build_warrant(
        _complete_source_projection(),
        warrant_key="secret-key",
        issued_at=issued_at,
        signed_at=issued_at,
        metadata={"b": 2, "a": 1},
    )
    verified_result_ref = {"sha256": "sha256:" + "a" * 64, "kind": "verified_result"}
    captured_at = "2026-06-01T00:00:00Z"
    right_projection = build_warrant_source_projection(
        verified_result_ref=verified_result_ref,
        behavioral_or_manifest_hash="sha256:" + "b" * 64,
        rationale_anchor={
            "rationale_ref": {"field": "summary", "path": "review.json"},
            "manifest_hash": "sha256:" + "b" * 64,
            "anchor_id": "rationale_1",
            "captured_at": captured_at,
        },
        verified_work_account={
            "verified_result_ref": verified_result_ref,
            "verified_work_units": [{"status": "done", "task_id": "T12"}],
            "account_id": "account_1",
        },
        authority_envelope={
            "grantor": "ops",
            "policy_envelope": {"spend_ceiling_usd": 10, "allow_models": ["codex:gpt-5.5"]},
            "authority_id": "authority_1",
            "captured_at": captured_at,
        },
        unsupported=("ledger_refs", "provider_cost_ref"),
        source_refs={"review_ref": "review.json"},
        projection_id="projection_1",
    )
    right = build_warrant(
        right_projection,
        warrant_key="secret-key",
        issued_at=issued_at,
        signed_at=issued_at,
        metadata={"a": 1, "b": 2},
    )

    assert canonical_projection_bytes(warrant_signed_envelope(left.warrant)) == canonical_projection_bytes(
        warrant_signed_envelope(right.warrant)
    )
    assert left.warrant.signature.signature == right.warrant.signature.signature


def test_adapter_complete_one_shot_and_multi_step_warrants_keep_shape_and_account_semantics() -> None:
    issued_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    one_shot = build_warrant(
        _adapter_complete_projection("one-shot"),
        warrant_key="secret-key",
        issued_at=issued_at,
        signed_at=issued_at,
    ).warrant
    multi_step = build_warrant(
        _adapter_complete_projection("multi-step"),
        warrant_key="secret-key",
        issued_at=issued_at,
        signed_at=issued_at,
    ).warrant
    one_payload = one_shot.model_dump(mode="json")
    multi_payload = multi_step.model_dump(mode="json")

    assert set(one_payload) == set(multi_payload)
    assert set(one_payload["authority"]) == set(multi_payload["authority"])
    assert set(one_payload["account"]) == set(multi_payload["account"])
    assert set(one_payload["rationale_anchor"]) == set(multi_payload["rationale_anchor"])
    assert one_payload["account"]["verified_result_ref"] == multi_payload["account"]["verified_result_ref"]
    assert one_payload["verified_result_ref"] == multi_payload["verified_result_ref"]
    assert one_payload["account"]["unit"] == multi_payload["account"]["unit"] == "verified_work"
    assert one_payload["rationale_anchor"]["anchor_id"] == "decision-time-rationale"
    assert one_payload["rationale_anchor"]["rationale_ref"] == multi_payload["rationale_anchor"]["rationale_ref"]
    assert one_payload["rationale_anchor"]["rationale_ref"]["field"] == "decision_rationale"
    assert verify_warrant(one_shot, warrant_key="secret-key")
    assert verify_warrant(multi_step, warrant_key="secret-key")


def test_real_source_partial_projection_rejects_before_signing_without_receipt_schema_expansion(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "step_receipt_execute_v1.json"
    receipt_payload: dict[str, Any] = {
        "phase": "execute",
        "status": "ok",
        "schema_version": 1,
    }
    receipt_path.write_text(json.dumps(receipt_payload, sort_keys=True), encoding="utf-8")
    before = receipt_path.read_text(encoding="utf-8")
    (tmp_path / "phase_result.json").write_text(
        json.dumps({"phase": "execute", "exit_kind": "success"}, sort_keys=True),
        encoding="utf-8",
    )
    (tmp_path / "review.json").write_text(
        json.dumps({"summary": "decision-time rationale", "task_verdicts": []}, sort_keys=True),
        encoding="utf-8",
    )

    projection = inventory_warrant_sources(tmp_path)

    assert receipt_path.read_text(encoding="utf-8") == before
    assert set(json.loads(receipt_path.read_text(encoding="utf-8"))) == set(receipt_payload)
    assert projection.completeness.signable is False
    assert "receipt_refs" in projection.completeness.present
    assert projection.rationale_anchor is None
    with pytest.raises(WarrantError) as exc_info:
        build_warrant(projection, warrant_key="secret-key")
    assert exc_info.value.error_kind == "incomplete_warrant_source"
    assert "rationale_anchor" in exc_info.value.details["missing"]
    assert "rationale_anchor" in exc_info.value.details["missing_required"]
    assert "receipt_refs" in exc_info.value.details["present"]
