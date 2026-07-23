from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import _enforce_openai_strict_mode
from arnold.pipeline import validate_payload_against_schema
from arnold_pipelines.megaplan.audits.robustness import CRITIQUE_CHECKS
from arnold_pipelines.megaplan.finalize_contract import FINALIZE_MODEL_OUTPUT_SCHEMA
from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.schemas.runtime import CRITIQUE_EVALUATOR_CHECK_IDS
from arnold_pipelines.megaplan.step_contracts import (
    STEP_CONTRACTS,
    contract_to_invocation,
)
from arnold_pipelines.megaplan.handlers.finalize import _validate_finalize_payload
from arnold_pipelines.megaplan.model_seam import capture_step_output
from arnold_pipelines.megaplan.workers import WorkerResult


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


def test_revise_schema_requires_every_north_star_closeout_field() -> None:
    """A schema-valid receipt must also satisfy the fail-closed consumer."""

    schema = SCHEMAS["revise.json"]
    assert "north_star_actions_addressed" in schema["required"]
    addressed = schema["properties"]["north_star_actions_addressed"]["items"]
    assert set(addressed["required"]) >= {
        "action_id",
        "resolution",
        "reason",
        "plan_refs",
        "action_type",
    }


def test_all_codex_output_schemas_have_strict_required_properties() -> None:
    for schema in SCHEMAS.values():
        strict = _enforce_openai_strict_mode(strict_schema(deepcopy(schema)))
        _assert_required_keys_have_properties(strict)
        _assert_array_schemas_have_items(strict)


def test_finalize_codex_schema_excludes_harness_owned_evidence() -> None:
    contract = STEP_CONTRACTS["finalize"]
    assert contract.schema_key == "finalize_model_output.json"
    assert contract.capture_schema_key == "finalize_model_output.json"

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


def test_finalize_critique_resolution_schema_cannot_drift_at_runtime_boundary() -> None:
    """The Codex capture schema must preserve the model contract's typed rows."""
    contract_schema = FINALIZE_MODEL_OUTPUT_SCHEMA["properties"][
        "critique_resolution_coverage"
    ]
    capture_schema = SCHEMAS["finalize_model_output.json"]["properties"][
        "critique_resolution_coverage"
    ]

    assert capture_schema == contract_schema
    _assert_array_schemas_have_items(capture_schema)


def test_model_native_finalize_graph_passes_capture_seam_and_handler(
    tmp_path: Path,
) -> None:
    """Do not require legacy executor-evidence fields from the finalizer model."""

    payload = {
        "task_contract_version": 1,
        "tasks": [
            {
                "id": "T1",
                "objective": "Implement the bounded correction.",
                "description": "Implement the bounded correction in source and tests.",
                "status": "pending",
                "kind": "code",
                "complexity": 4,
                "complexity_justification": "Two coupled source and regression files.",
                "estimated_minutes": 30,
                "depends_on": [],
                "dependency_reasons": {},
                "routing_group": "implementation",
                "write_set": {
                    "paths": ["arnold_pipelines/megaplan/example.py"],
                    "complete": True,
                },
                "narrow_tests": {
                    "selectors": ["tests/test_example.py"],
                    "max_seconds": 120,
                    "max_runs": 1,
                },
                "checkpoint": {
                    "required": False,
                    "max_interval_seconds": 300,
                    "records": [],
                },
            }
        ],
        "validation_jobs": [],
        "critique_resolution_coverage": [],
        "sense_checks": [],
        "watch_items": [],
        "user_actions": [],
        "meta_commentary": "Compiled from the gated plan.",
    }

    captured = capture_step_output(
        contract_to_invocation(STEP_CONTRACTS["finalize"]),
        payload,
    ).legacy_payload

    assert captured == payload
    assert "auto_attributed_files" not in captured["tasks"][0]
    assert "commands_run" not in captured["tasks"][0]
    assert "evidence_files" not in captured["tasks"][0]

    worker = WorkerResult(
        payload=dict(captured),
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
    )
    state = {
        "iteration": 1,
        "config": {"mode": "code"},
    }
    _validate_finalize_payload(tmp_path, state, worker)


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
