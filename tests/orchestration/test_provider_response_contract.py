from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy

import pytest

from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import (
    LOCAL_STRICT_ARTIFACT_RECEIPT_SCHEMA,
    capture_step_output,
)
from arnold.pipeline.model_seam import ModelStructuralAuditError
from arnold_pipelines.megaplan.provider_response import (
    ProviderResponseContractError,
    ResponseEnforcement,
    compile_response_contract,
    persist_response_enforcement_attestation,
    schema_sha256,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.workers._impl import (
    _codex_repair_input,
    _codex_provider_contract_error,
    _codex_response_schema_args,
    _is_codex_provider_schema_rejection,
    _local_response_contract_error,
    _prepare_local_strict_artifact_handoff,
)


def test_codex_repair_diagnoses_canonical_output_not_jsonl_transport() -> None:
    transport = '{"type":"thread.started"}\n{"type":"turn.completed"}\n'
    canonical = '{"tasks":[],"user_actions":[]}'

    selected, parse_error = _codex_repair_input(transport, canonical)

    assert selected == canonical
    assert parse_error is None
from arnold_pipelines.megaplan.auto import _is_retryable_external_error
from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError
from arnold_pipelines.megaplan.orchestration.phase_result_classify import (
    classify_external_error_payload,
)


@pytest.mark.parametrize(
    ("schema_name", "reason_fragment"),
    [
        ("finalize_capture.json", "dynamic_or_open_object"),
        ("feedback.json", "dynamic_or_open_object"),
        ("loop_plan.json", "dynamic_or_open_object"),
    ],
)
def test_dynamic_contracts_select_local_strict_json(
    schema_name: str, reason_fragment: str
) -> None:
    schema = strict_schema(deepcopy(SCHEMAS[schema_name]))

    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase=schema_name.removesuffix(".json"),
    )

    assert compiled.transport_schema is None
    assert (
        compiled.attestation.response_enforcement
        == ResponseEnforcement.LOCAL_STRICT_JSON.value
    )
    assert reason_fragment in compiled.attestation.enforcement_reason
    assert compiled.attestation.canonical_schema_hash == schema_sha256(schema)
    assert compiled.attestation.transport_schema_hash is None


def test_closed_schema_uses_provider_strict_and_output_schema_argument(tmp_path) -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="closed",
    )
    schema_path = tmp_path / "transport.json"
    schema_path.write_text(json.dumps(compiled.transport_schema), encoding="utf-8")

    assert (
        compiled.attestation.response_enforcement
        == ResponseEnforcement.PROVIDER_STRICT.value
    )
    assert compiled.transport_schema == schema
    assert compiled.attestation.transport_schema_hash == schema_sha256(schema)
    assert _codex_response_schema_args(schema_path) == [
        "--output-schema",
        str(schema_path),
        "-",
    ]


def test_local_strict_command_omits_output_schema() -> None:
    assert _codex_response_schema_args(None) == ["-"]


def test_optional_semantic_fields_are_not_promoted_for_provider_acceptance() -> None:
    schema = {
        "type": "object",
        "properties": {
            "required_value": {"type": "string"},
            "optional_value": {"type": "string"},
        },
        "required": ["required_value"],
        "additionalProperties": False,
    }

    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="semantic"
    )

    assert compiled.transport_schema is None
    assert compiled.attestation.response_enforcement == "local_strict_json"
    assert "optional_object_properties" in compiled.attestation.enforcement_reason
    assert compiled.attestation.canonical_schema_hash == schema_sha256(schema)


@pytest.mark.parametrize(
    ("schema", "reason"),
    [
        ({"type": "string"}, "root_schema_must_be_object"),
        (
            {
                "type": ["object", "null"],
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "unsupported_type_union",
        ),
        (
            {
                "type": "object",
                "properties": {"answers": {"type": "array"}},
                "required": ["answers"],
                "additionalProperties": False,
            },
            "array_without_item_schema",
        ),
        (
            {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer", "answer"],
                "additionalProperties": False,
            },
            "optional_object_properties",
        ),
    ],
)
def test_ambiguous_provider_dialect_contracts_fail_closed_to_local_validation(
    schema, reason: str
) -> None:
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="conservative"
    )

    assert compiled.transport_schema is None
    assert compiled.attestation.response_enforcement == "local_strict_json"
    assert reason in compiled.attestation.enforcement_reason


def test_resume_transport_forces_local_strict_even_for_closed_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="execute",
        provider_schema_available=False,
    )
    assert compiled.transport_schema is None
    assert compiled.attestation.enforcement_reason == (
        "transport_does_not_support_provider_schema"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"default": "invented"},
        {"const": "invented"},
        {"oneOf": [{"type": "string"}, {"type": "integer"}]},
        {"minimum": 1},
    ],
)
def test_historical_schema_mutations_fail_closed_to_local_validation(mutation) -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string", **mutation}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="m9_mutation_replay",
    )

    assert compiled.transport_schema is None
    assert compiled.attestation.response_enforcement == "local_strict_json"
    assert compiled.attestation.enforcement_reason.startswith("unsupported_keyword:")


def test_local_strict_feedback_round_trip_preserves_dynamic_stage_keys() -> None:
    payload = {
        "overall": {"rating": 8, "comment": "good"},
        "stages": {
            "M9-provider-boundary": {"rating": 3, "comment": "reproduced"},
            "future-stage-id": {"rating": 7, "comment": "preserved"},
        },
    }
    schema = strict_schema(deepcopy(SCHEMAS["feedback.json"]))
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.6-sol",
            "validation_step": "feedback",
            "compatibility_validation_step": "feedback",
            "schema": schema,
            "capture_schema": SCHEMAS["feedback.json"],
        },
    )

    captured = capture_step_output(invocation, json.dumps(payload))

    assert captured.legacy_payload == payload


def test_local_strict_loop_plan_round_trip_preserves_open_spec_updates() -> None:
    payload = {
        "spec_updates": {
            "new_runtime_axis": {"enabled": True, "threshold": 4},
            "nested": {"provider": {"model": "future-model"}},
        },
        "next_action": "continue",
        "reasoning": "retain learned fields",
    }
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.6-sol",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": strict_schema(deepcopy(SCHEMAS["loop_plan.json"])),
            "capture_schema": SCHEMAS["loop_plan.json"],
        },
    )

    captured = capture_step_output(invocation, json.dumps(payload))

    assert captured.legacy_payload == payload


def test_attestation_is_durable_and_complete(tmp_path) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="loop_plan",
    )

    path = persist_response_enforcement_attestation(tmp_path, compiled.attestation)
    record = json.loads(path.read_text(encoding="utf-8"))

    assert set(record) == {
        "canonical_schema_hash",
        "response_enforcement",
        "enforcement_reason",
        "provider",
        "model",
        "phase",
        "transport_schema_hash",
        "compiler_version",
    }
    assert record["phase"] == "loop_plan"


def test_invalid_compiler_input_has_typed_stable_external_error() -> None:
    with pytest.raises(ProviderResponseContractError) as first:
        compile_response_contract(
            {}, provider="codex", model="gpt-5.6-sol", phase="finalize"
        )
    with pytest.raises(ProviderResponseContractError) as second:
        compile_response_contract(
            {}, provider="codex", model="gpt-5.6-sol", phase="finalize"
        )

    error = first.value.external_error()
    assert error == {
        "error_kind": "provider_contract",
        "error_layer": "schema_error",
        "deterministic": True,
        "nonretryable": True,
        "failure_fingerprint": second.value.failure_fingerprint,
    }


@pytest.mark.parametrize(
    "rendered",
    [
        'prefix {"spec_updates": {}, "next_action": "continue", "reasoning": "ok"}',
        '```json\n{"spec_updates": {}, "next_action": "continue", "reasoning": "ok"}\n```',
    ],
)
def test_local_strict_capture_rejects_candidate_recovery(
    tmp_path, rendered: str
) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    output = tmp_path / "response.txt"
    output.write_text(rendered, encoding="utf-8")
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.6-sol",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": compiled.attestation.to_json(),
            "capture_recovery": {
                "step": "loop_plan",
                "plan_dir": str(tmp_path),
                "output_path": str(output),
                "prefer_output_file": True,
            },
        },
    )

    with pytest.raises(json.JSONDecodeError):
        capture_step_output(invocation, rendered)


@pytest.mark.parametrize(
    "rendered, match",
    [
        (
            '{"spec_updates":{"x":1,"x":2},"next_action":"continue","reasoning":"ok"}',
            "duplicate JSON object key",
        ),
        (
            '{"spec_updates":{"x":NaN},"next_action":"continue","reasoning":"ok"}',
            "non-finite JSON number",
        ),
    ],
)
def test_local_strict_capture_rejects_ambiguous_json(
    tmp_path, rendered: str, match: str
) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    output = tmp_path / "response.txt"
    output.write_text(rendered, encoding="utf-8")
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": compiled.attestation.to_json(),
            "capture_recovery": {
                "step": "loop_plan",
                "plan_dir": str(tmp_path),
                "output_path": str(output),
            },
        },
    )

    with pytest.raises(ModelStructuralAuditError, match=match):
        capture_step_output(invocation, rendered)


def test_local_strict_capture_rejects_schema_attestation_substitution(tmp_path) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    attestation = compiled.attestation.to_json()
    attestation["canonical_schema_hash"] = "0" * 64
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": attestation,
        },
    )

    with pytest.raises(ModelStructuralAuditError, match="does not bind"):
        capture_step_output(
            invocation,
            '{"spec_updates":{},"next_action":"continue","reasoning":"ok"}',
        )


def _artifact_handoff_invocation(tmp_path, candidate, *, max_bytes=1024 * 1024):
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    return StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": compiled.attestation.to_json(),
            "capture_recovery": {
                "artifact_handoff": {
                    "schema": LOCAL_STRICT_ARTIFACT_RECEIPT_SCHEMA,
                    "root": str(candidate.parent),
                    "candidate_path": str(candidate),
                    "max_bytes": max_bytes,
                }
            },
        },
    )


def _artifact_receipt(candidate, data: bytes) -> str:
    return json.dumps(
        {
            "schema": LOCAL_STRICT_ARTIFACT_RECEIPT_SCHEMA,
            "path": str(candidate),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    )


def test_local_strict_artifact_handoff_round_trip_is_exact_and_schema_audited(tmp_path) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    payload = {
        "spec_updates": {"large": "x" * 50_000},
        "next_action": "continue",
        "reasoning": "durable handoff",
    }
    data = json.dumps(payload, separators=(",", ":")).encode()
    temporary = root / "write.tmp"
    temporary.write_bytes(data)
    os.replace(temporary, candidate)

    captured = capture_step_output(
        _artifact_handoff_invocation(tmp_path, candidate),
        _artifact_receipt(candidate, data),
    )

    assert captured.legacy_payload == payload
    assert "codex_capture:artifact_handoff" in captured.contract_result.provenance.sources


@pytest.mark.parametrize("mutation", ["path", "digest", "size", "extra"])
def test_local_strict_artifact_handoff_rejects_unbound_receipts(tmp_path, mutation) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    data = b'{"spec_updates":{},"next_action":"continue","reasoning":"ok"}'
    candidate.write_bytes(data)
    receipt = json.loads(_artifact_receipt(candidate, data))
    if mutation == "path":
        other = root / "stale.candidate.json"
        other.write_bytes(data)
        receipt["path"] = str(other)
    elif mutation == "digest":
        receipt["sha256"] = "0" * 64
    elif mutation == "size":
        receipt["bytes"] += 1
    else:
        receipt["nonce"] = "not-in-contract"

    with pytest.raises(ModelStructuralAuditError):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, candidate),
            json.dumps(receipt),
        )


def test_local_strict_artifact_handoff_rejects_symlink_and_path_escape(tmp_path) -> None:
    outside = tmp_path / "outside.json"
    data = b'{"spec_updates":{},"next_action":"continue","reasoning":"ok"}'
    outside.write_bytes(data)
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    candidate.symlink_to(outside)

    with pytest.raises(ModelStructuralAuditError, match="non-symlink regular file"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, candidate),
            _artifact_receipt(candidate, data),
        )

    escaped = tmp_path / "escape.candidate.json"
    escaped.write_bytes(data)
    invocation = _artifact_handoff_invocation(tmp_path, escaped)
    invocation.metadata["capture_recovery"]["artifact_handoff"]["root"] = str(root)
    with pytest.raises(ModelStructuralAuditError, match="escapes"):
        capture_step_output(invocation, _artifact_receipt(escaped, data))


def test_local_strict_artifact_handoff_rejects_oversize_and_invalid_payload(tmp_path) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    oversized = root / "large.candidate.json"
    oversized_data = b'{' + b' ' * 64 + b'}'
    oversized.write_bytes(oversized_data)
    with pytest.raises(ModelStructuralAuditError, match="size limit"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, oversized, max_bytes=16),
            _artifact_receipt(oversized, oversized_data),
        )

    invalid = root / "invalid.candidate.json"
    invalid_data = b'{"spec_updates":{},"next_action":"continue"}'
    invalid.write_bytes(invalid_data)
    with pytest.raises(ModelStructuralAuditError):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, invalid),
            _artifact_receipt(invalid, invalid_data),
        )


def test_local_strict_handoff_paths_are_unique_and_replay_bound(tmp_path) -> None:
    first = _prepare_local_strict_artifact_handoff(tmp_path, step="finalize")
    second = _prepare_local_strict_artifact_handoff(tmp_path, step="finalize")
    assert first["candidate_path"] != second["candidate_path"]
    assert "local-strict-artifacts" in first["candidate_path"]
    assert not first["candidate_path"].endswith("finalize_output.json")

    first_path = first["candidate_path"]
    data = b'{"spec_updates":{},"next_action":"continue","reasoning":"ok"}'
    first_candidate = __import__("pathlib").Path(first_path)
    first_candidate.write_bytes(data)
    second_candidate = __import__("pathlib").Path(second["candidate_path"])
    with pytest.raises(ModelStructuralAuditError, match="does not match"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, second_candidate),
            _artifact_receipt(first_candidate, data),
        )


def test_local_response_contract_exhaustion_is_nonretryable_and_bounded() -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    error = _local_response_contract_error(
        step="loop_plan", schema=schema, reason="bad receipt", raw="{}"
    )
    budget = error.extra["local_response_contract"]
    external = error.extra["_external_error"]
    assert budget == {
        "attempts": 2,
        "repairs": 1,
        "max_attempts": 2,
        "exhausted": True,
        "occurrence_id": budget["occurrence_id"],
        "failure_fingerprint": budget["failure_fingerprint"],
    }
    assert external["nonretryable"] is True
    assert external["failure_fingerprint"] == budget["failure_fingerprint"]
    classified = classify_external_error_payload(error)
    assert classified is not None
    assert not _is_retryable_external_error(
        "finalize", ExternalError.from_dict(classified)
    )


def test_unexpected_backend_schema_rejection_is_typed_and_stable() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="finalize"
    )
    raw_a = "HTTP 400 invalid_json_schema request_id=req-a"
    raw_b = "HTTP 400 invalid_json_schema request_id=req-b"

    assert _is_codex_provider_schema_rejection(raw_a)
    first = _codex_provider_contract_error(compiled, raw_a)
    second = _codex_provider_contract_error(compiled, raw_b)
    first_external = first.extra["_external_error"]
    second_external = second.extra["_external_error"]

    assert first.code == "provider_contract"
    assert first_external["error_kind"] == "provider_contract"
    assert first_external["deterministic"] is True
    assert first_external["nonretryable"] is True
    assert (
        first_external["failure_fingerprint"]
        == second_external["failure_fingerprint"]
    )


def test_generic_http_400_is_not_forged_into_schema_rejection() -> None:
    assert not _is_codex_provider_schema_rejection(
        "HTTP 400 invalid_request_error: malformed command argument"
    )
