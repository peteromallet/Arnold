from __future__ import annotations

import json
from copy import deepcopy

import pytest

from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import capture_step_output
from arnold_pipelines.megaplan.provider_response import (
    ProviderResponseContractError,
    ResponseEnforcement,
    compile_response_contract,
    persist_response_enforcement_attestation,
    schema_sha256,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.workers._impl import _codex_response_schema_args


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
