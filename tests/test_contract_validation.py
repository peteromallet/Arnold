from __future__ import annotations

from copy import deepcopy

from arnold.pipeline.contract_validation import validate_contract_result, validate_payload_against_schema
from arnold.pipeline.types import ContractResult, Provenance


def test_matching_payload_passes_and_inputs_are_not_mutated() -> None:
    payload = {"name": "Ada", "score": 3, "tags": ["ok"]}
    schema = {
        "type": "object",
        "required": ["name", "score", "tags"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "score": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }
    payload_before = deepcopy(payload)
    schema_before = deepcopy(schema)

    result = validate_payload_against_schema(payload, schema)

    assert result.ok
    assert payload == payload_before
    assert schema == schema_before


def test_rejects_extra_keys_wrong_types_and_missing_required_fields() -> None:
    schema = {
        "type": "object",
        "required": ["name", "score", "enabled"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "score": {"type": "number"},
            "enabled": {"type": "boolean"},
        },
    }

    result = validate_payload_against_schema({"name": 7, "surprise": True}, schema)

    diagnostics = {(d.code, d.payload_pointer) for d in result.diagnostics}
    assert ("missing_required", "/enabled") in diagnostics
    assert ("missing_required", "/score") in diagnostics
    assert ("additional_property", "/surprise") in diagnostics
    assert ("type_mismatch", "/name") in diagnostics


def test_recurses_nested_objects_and_arrays_with_escaped_pointer_paths() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "a/b": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "c~d": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"value": {"type": "integer"}},
                        },
                    }
                },
            }
        },
    }

    result = validate_payload_against_schema({"a/b": {"c~d": [{"value": "bad"}]}}, schema)

    assert not result.ok
    assert result.diagnostics[0].payload_pointer == "/a~1b/c~0d/0/value"


def test_enum_const_one_of_any_of_and_type_union() -> None:
    schema = {
        "type": "object",
        "required": ["mode", "kind", "choice", "flex", "nullable"],
        "additionalProperties": False,
        "properties": {
            "mode": {"enum": ["fast", "safe"]},
            "kind": {"const": "audit"},
            "choice": {"oneOf": [{"type": "integer"}, {"const": "auto"}]},
            "flex": {"anyOf": [{"type": "boolean"}, {"enum": ["yes", "no"]}]},
            "nullable": {"type": ["null", "string"]},
        },
    }

    assert validate_payload_against_schema(
        {"mode": "fast", "kind": "audit", "choice": 3, "flex": "yes", "nullable": None},
        schema,
    ).ok

    result = validate_payload_against_schema(
        {"mode": "slow", "kind": "other", "choice": "x", "flex": 1, "nullable": 4},
        schema,
    )
    assert {d.code for d in result.diagnostics} == {
        "enum_mismatch",
        "const_mismatch",
        "one_of_mismatch",
        "any_of_mismatch",
        "type_mismatch",
    }


def test_strict_null_handling_does_not_treat_missing_as_null() -> None:
    schema = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "null"}},
        "additionalProperties": False,
    }

    assert validate_payload_against_schema({"value": None}, schema).ok
    missing = validate_payload_against_schema({}, schema)
    wrong_type = validate_payload_against_schema({"value": ""}, schema)
    assert [(d.code, d.payload_pointer) for d in missing.diagnostics] == [
        ("missing_required", "/value")
    ]
    assert [(d.code, d.payload_pointer) for d in wrong_type.diagnostics] == [
        ("type_mismatch", "/value")
    ]


def test_validate_contract_result_only_checks_payload_with_arbitrary_metadata() -> None:
    contract = ContractResult(
        payload={"answer": 42},
        authority_level="whatever-the-producer-said",
        provenance=Provenance(
            sources=("free-form-source",),
            generator="unknown-generator",
            chain=("not", "schema", "validated"),
        ),
    )
    schema = {
        "type": "object",
        "required": ["answer"],
        "additionalProperties": False,
        "properties": {"answer": {"type": "integer"}},
    }

    assert validate_contract_result(contract, schema).ok
