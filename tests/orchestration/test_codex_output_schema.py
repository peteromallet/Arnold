from __future__ import annotations

from copy import deepcopy
from typing import Any

from arnold_pipelines.megaplan._core.io import _enforce_openai_strict_mode
from arnold.pipeline import validate_payload_against_schema
from arnold_pipelines.megaplan.audits.robustness import CRITIQUE_CHECKS
from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.schemas.runtime import CRITIQUE_EVALUATOR_CHECK_IDS
from arnold_pipelines.megaplan.step_contracts import STEP_CONTRACTS


def _assert_required_keys_have_properties(schema: Any) -> None:
    if isinstance(schema, dict):
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            required = schema.get("required", [])
            assert isinstance(required, list)
            missing = set(required) - set(schema["properties"])
            assert not missing
        for value in schema.values():
            _assert_required_keys_have_properties(value)
    elif isinstance(schema, list):
        for value in schema:
            _assert_required_keys_have_properties(value)


def _assert_array_schemas_have_items(schema: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(schema, dict):
        schema_type = schema.get("type")
        if schema_type == "array" or (
            isinstance(schema_type, list) and "array" in schema_type
        ):
            assert "items" in schema, f"array schema missing items at {'/'.join(path)}"
        for key, value in schema.items():
            _assert_array_schemas_have_items(value, path + (str(key),))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            _assert_array_schemas_have_items(value, path + (str(index),))


def test_plan_and_revise_codex_output_schemas_keep_test_blast_radius_declared() -> None:
    for schema_name in ("plan.json", "revise.json"):
        schema = _enforce_openai_strict_mode(strict_schema(deepcopy(SCHEMAS[schema_name])))

        assert "test_blast_radius" in schema["properties"]
        blast_radius = schema["properties"]["test_blast_radius"]
        assert blast_radius["type"] == "object"
        assert set(blast_radius["properties"]) >= {
            "strategy",
            "confidence",
            "selectors",
            "changed_surfaces",
            "always_run",
            "full_suite_fallback",
            "rationale",
            "import_graph",
        }
        _assert_required_keys_have_properties(schema)


def test_all_codex_output_schemas_have_strict_required_properties() -> None:
    for schema in SCHEMAS.values():
        strict = _enforce_openai_strict_mode(strict_schema(deepcopy(schema)))
        _assert_required_keys_have_properties(strict)
        _assert_array_schemas_have_items(strict)


def test_finalize_codex_schema_excludes_harness_owned_evidence() -> None:
    contract = STEP_CONTRACTS["finalize"]
    assert contract.schema_key == "finalize_capture.json"
    assert contract.capture_schema_key == "finalize_capture.json"

    schema = _enforce_openai_strict_mode(
        strict_schema(deepcopy(SCHEMAS[contract.schema_key]))
    )
    properties = schema["properties"]
    assert set(schema["required"]) == set(properties)
    assert {
        "critique_custody",
        "validation",
        "baseline_test_failures",
        "baseline_test_command",
        "baseline_test_note",
        "suite_runs_ndjson_path",
    }.isdisjoint(properties)
    assert "critique_resolution_coverage" in properties


def test_critique_evaluator_schema_rejects_invented_catalog_lens_ids() -> None:
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "north_star_alignment",
                "complexity": 4,
                "complexity_justification": "Invented lens should be encoded as other.",
                "area": "North Star compliance",
            }
        ],
        "skipped": [],
        "evaluator_model": "gpt-5-codex",
        "flag_verifications": [],
    }

    result = validate_payload_against_schema(payload, schema)

    assert not result.ok


def test_critique_evaluator_schema_lens_ids_match_registry() -> None:
    assert CRITIQUE_EVALUATOR_CHECK_IDS == [check["id"] for check in CRITIQUE_CHECKS]
