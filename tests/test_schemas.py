"""Direct tests for megaplan.schemas."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from arnold.pipelines.megaplan._core.io import _enforce_openai_strict_mode
from arnold.pipelines.megaplan.schemas import GateArtifact, GatePayload, GateSignals, SCHEMAS, TiebreakerDecision, strict_schema


def _review_disk_schema() -> dict[str, object]:
    return json.loads((Path(__file__).resolve().parents[1] / ".megaplan" / "schemas" / "review.json").read_text(encoding="utf-8"))


def _minimal_review_payload() -> dict[str, object]:
    return {
        "review_verdict": "approved",
        "checks": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
        "criteria": [],
        "issues": [],
        "rework_items": [],
        "summary": "Approved.",
        "task_verdicts": [],
        "sense_check_verdicts": [],
    }


def _deterministic_check() -> dict[str, object]:
    return {
        "command": "python -m pytest tests/test_example.py -q",
        "baseline_status": "passed",
        "post_status": "failed",
        "evidence_file": None,
    }


def test_schema_registry_matches_5_step_workflow() -> None:
    required = {"plan.json", "prep.json", "revise.json", "gate.json", "critique.json", "finalize.json", "execution.json", "review.json"}
    assert required.issubset(set(SCHEMAS))


def test_planning_schema_contracts_export_from_schema_package() -> None:
    gate_payload: GatePayload = {
        "recommendation": "PROCEED",
        "rationale": "Ready.",
        "signals_assessment": "clear",
        "warnings": [],
        "settled_decisions": [],
    }
    gate_artifact: GateArtifact = {
        "passed": True,
        "criteria_check": {},
        "preflight_results": {},
        "unresolved_flags": [],
        "recommendation": "PROCEED",
        "rationale": "Ready.",
        "signals_assessment": "clear",
        "warnings": [],
        "settled_decisions": [],
        "signals": {},
    }
    gate_signals: GateSignals = {"signals": {}, "warnings": []}
    tiebreaker_decision: TiebreakerDecision = {"action": "pick"}

    assert gate_payload["recommendation"] == "PROCEED"
    assert gate_artifact["passed"] is True
    assert gate_signals["warnings"] == []
    assert tiebreaker_decision["action"] == "pick"


# ---------------------------------------------------------------------------
# strict_schema tests
# ---------------------------------------------------------------------------


def test_strict_schema_adds_additional_properties_false() -> None:
    result = strict_schema({"type": "object", "properties": {"a": {"type": "string"}}})
    assert result["additionalProperties"] is False


def test_strict_schema_preserves_existing_additional_properties() -> None:
    result = strict_schema({"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": True})
    assert result["additionalProperties"] is True


def test_strict_schema_sets_required_from_properties() -> None:
    result = strict_schema({"type": "object", "properties": {"x": {"type": "string"}, "y": {"type": "number"}}})
    assert set(result["required"]) == {"x", "y"}


def test_strict_schema_normalizes_partial_required_arrays_recursively() -> None:
    schema = {
        "type": "object",
        "required": ["stale_root"],
        "properties": {
            "inner": {
                "type": "object",
                "required": ["stale_inner"],
                "properties": {"child": {"type": "string"}},
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["stale_item"],
                    "properties": {"name": {"type": "string"}},
                },
            },
        },
    }

    result = strict_schema(schema)

    assert result["required"] == ["inner", "items"]
    assert result["properties"]["inner"]["required"] == ["child"]
    assert result["properties"]["items"]["items"]["required"] == ["name"]


def test_strict_schema_nested_objects_get_additional_properties() -> None:
    schema = {
        "type": "object",
        "properties": {
            "inner": {"type": "object", "properties": {"a": {"type": "string"}}},
        },
    }
    result = strict_schema(schema)
    assert result["properties"]["inner"]["additionalProperties"] is False
    assert result["properties"]["inner"]["required"] == ["a"]


def test_strict_schema_array_items_are_strict() -> None:
    schema = {
        "type": "object",
        "properties": {
            "list": {
                "type": "array",
                "items": {"type": "object", "properties": {"name": {"type": "string"}}},
            }
        },
    }
    result = strict_schema(schema)
    assert result["properties"]["list"]["items"]["additionalProperties"] is False


def test_strict_schema_deeply_nested() -> None:
    schema = {
        "type": "object",
        "properties": {
            "l1": {
                "type": "object",
                "properties": {
                    "l2": {
                        "type": "object",
                        "properties": {"l3": {"type": "string"}},
                    }
                },
            }
        },
    }
    result = strict_schema(schema)
    assert result["properties"]["l1"]["properties"]["l2"]["additionalProperties"] is False


def test_strict_schema_non_object_untouched() -> None:
    assert strict_schema({"type": "string"}) == {"type": "string"}
    assert strict_schema(42) == 42
    assert strict_schema("hello") == "hello"
    assert strict_schema([1, 2]) == [1, 2]


# ---------------------------------------------------------------------------
# Schema completeness tests
# ---------------------------------------------------------------------------


def test_schema_registry_has_all_expected_steps() -> None:
    required_schemas = {"plan.json", "prep.json", "revise.json", "gate.json", "critique.json", "finalize.json", "execution.json", "review.json"}
    assert required_schemas.issubset(set(SCHEMAS.keys()))


def test_schema_registry_entries_include_required_field() -> None:
    for name, schema in SCHEMAS.items():
        assert "required" in schema, f"Schema '{name}' missing 'required' field"
        assert isinstance(schema["required"], list)


def test_schema_registry_entries_are_objects() -> None:
    for name, schema in SCHEMAS.items():
        assert schema.get("type") == "object", f"Schema '{name}' is not type 'object'"
        assert "properties" in schema, f"Schema '{name}' missing 'properties'"


def test_critique_schema_flags_have_expected_structure() -> None:
    critique = SCHEMAS["critique.json"]
    flags_schema = critique["properties"]["flags"]
    assert flags_schema["type"] == "array"
    item_schema = flags_schema["items"]
    assert "id" in item_schema["properties"]
    assert "concern" in item_schema["properties"]
    assert "category" in item_schema["properties"]
    assert "severity_hint" in item_schema["properties"]
    assert "evidence" in item_schema["properties"]


def test_critique_evaluator_schema_accepts_legacy_catalog_and_other_shapes() -> None:
    schema = SCHEMAS["critique_evaluator.json"]
    validator = Draft7Validator(schema)

    legacy_payload = {
        "selections": [
            {
                "check_id": "correctness",
                "critic_model": "claude-opus-4-7",
                "why": "Stored artifact from the pre-complexity contract.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    catalog_payload = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "This lens needs deeper scrutiny.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    other_payload = {
        "selections": [
            {
                "check_id": "other",
                "area": "rollout safety",
                "why": "Probe a risk the catalog does not name.",
                "complexity": 3,
                "complexity_justification": "Moderate bespoke reasoning is enough.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }

    assert list(validator.iter_errors(legacy_payload)) == []
    assert list(validator.iter_errors(catalog_payload)) == []
    assert list(validator.iter_errors(other_payload)) == []


def test_critique_evaluator_schema_rejects_hybrid_selection_shapes() -> None:
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "correctness",
                "critic_model": "claude-opus-4-7",
                "complexity": 4,
                "complexity_justification": "Hybrid legacy/new payloads must fail.",
                "why": "This mixes two contracts.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors


# ── T5: stored-artifact schema tests (separate from live validation) ────


def test_stored_artifact_schema_accepts_legacy_with_optional_area() -> None:
    """Stored-artifact compatibility: old `{check_id, critic_model, why, area}` passes."""
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "correctness",
                "critic_model": "claude-opus-4-7",
                "why": "Stored pre-complexity selection.",
                "area": "core logic",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    assert list(Draft7Validator(schema).iter_errors(payload)) == []


def test_stored_artifact_schema_accepts_legacy_without_optional_area() -> None:
    """Stored-artifact compatibility: old `{check_id, critic_model, why}` (no area) passes."""
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "prerequisite_ordering",
                "critic_model": "claude-opus-4-7",
                "why": "Stored pre-complexity selection without area.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    assert list(Draft7Validator(schema).iter_errors(payload)) == []


def test_stored_artifact_schema_accepts_catalog_with_optional_area() -> None:
    """Stored-artifact compatibility: catalog `{check_id, complexity, complexity_justification, area}` passes."""
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Needs deeper scrutiny.",
                "area": "core validation logic",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    assert list(Draft7Validator(schema).iter_errors(payload)) == []


def test_stored_artifact_schema_rejects_catalog_with_bool_complexity() -> None:
    """Schema-level: bool complexity in catalog selections is rejected."""
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": True,
                "complexity_justification": "Bool complexity is invalid.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors


def test_stored_artifact_schema_rejects_catalog_with_missing_complexity_justification() -> None:
    """Schema-level: catalog selection without `complexity_justification` fails."""
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors


def test_stored_artifact_schema_rejects_other_without_area() -> None:
    """Schema-level: `other` selection without `area` fails."""
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "other",
                "why": "Custom concern.",
                "complexity": 3,
                "complexity_justification": "Moderate bespoke reasoning.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors


def test_stored_artifact_schema_preserves_optional_flag_verifications() -> None:
    """Stored-artifact schema keeps `flag_verifications` optional and valid when present.

    The field is NOT in `required` but must validate when supplied.
    """
    schema = SCHEMAS["critique_evaluator.json"]
    payload = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Top priority lens.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
        "flag_verifications": [
            {
                "flag_id": "FLAG-001",
                "lens": "correctness",
                "outcome": "verified",
                "rationale": "Diff addresses the flagged concern.",
            }
        ],
    }
    assert list(Draft7Validator(schema).iter_errors(payload)) == []


def test_stored_artifact_schema_flag_verifications_not_required() -> None:
    """Stored-artifact schema: `flag_verifications` is absent from top-level `required`."""
    schema = SCHEMAS["critique_evaluator.json"]
    assert "flag_verifications" not in schema["required"]


def test_stored_artifact_schema_has_single_source_no_duplicate_definitions() -> None:
    """Prove `critique_evaluator.json` has one builder — no duplicate definition drift.

    The schema in SCHEMAS is built from `_build_critique_evaluator_schema()`,
    imported once at the callsite. This test verifies the shape comes from that
    single builder by asserting the ``oneOf`` branches match expected structures
    exactly — legacy, catalog, and `other` — and that they carry the
    ``x-preserve-explicit-required`` marker used by the builder.
    """
    from arnold.pipelines.megaplan.schemas.runtime import _build_critique_evaluator_schema

    schema = SCHEMAS["critique_evaluator.json"]

    # Rebuild to compare — if the stored schema drifted from the builder,
    # this would diverge.
    rebuilt = _build_critique_evaluator_schema()
    assert schema == rebuilt, (
        "critique_evaluator.json schema has drifted from "
        "_build_critique_evaluator_schema(). There must be only one source of truth."
    )

    # Also verify the oneOf branches have the expected x-preserve-explicit-required marker.
    branches = schema["properties"]["selections"]["items"]["oneOf"]
    assert len(branches) == 3, "Expected exactly 3 branch schemas: legacy, catalog, other"
    for branch in branches:
        assert branch.get("x-preserve-explicit-required") is True, (
            "All selection branches must carry x-preserve-explicit-required from the builder"
        )


def test_stored_artifact_compatibility_separate_from_live_validate_evaluator_verdict() -> None:
    """Stored-artifact schema accepts legacy `critic_model` shapes that live validation rejects.

    This is the key separation: the runtime schema in SCHEMAS is for
    *stored-artifact* compatibility (old `.megaplan/` artifacts must still load
    without errors), while `validate_evaluator_verdict` in
    `megaplan/audits/critique_evaluator.py` is for *live* evaluator output and
    explicitly rejects per-lens ``critic_model`` selections.
    """
    from arnold.pipelines.megaplan.audits.critique_evaluator import validate_evaluator_verdict

    schema = SCHEMAS["critique_evaluator.json"]
    legacy_payload = {
        "selections": [
            {
                "check_id": "correctness",
                "critic_model": "claude-opus-4-7",
                "why": "Stored pre-complexity artifact.",
            }
        ],
        "skipped": [],
        "evaluator_model": "claude-opus-4-7",
    }

    # 1) Stored-artifact schema MUST accept the legacy shape.
    assert list(Draft7Validator(schema).iter_errors(legacy_payload)) == [], (
        "Stored-artifact schema must accept legacy `critic_model` selections."
    )

    # 2) Live validation MUST reject the same legacy shape.
    try:
        validate_evaluator_verdict(legacy_payload, evaluator_model="claude-opus-4-7")
        assert False, "Live validate_evaluator_verdict should have rejected legacy critic_model"
    except ValueError as exc:
        assert "must not include `critic_model`" in str(exc), (
            f"Unexpected rejection message: {exc}"
        )


def test_finalize_schema_tracks_structured_execution_fields() -> None:
    finalize = SCHEMAS["finalize.json"]
    assert "tasks" in finalize["properties"]
    assert "sense_checks" in finalize["properties"]
    assert "validation" in finalize["properties"]
    assert "baseline_test_failures" in finalize["properties"]
    assert "baseline_test_command" in finalize["properties"]
    assert "baseline_test_note" in finalize["properties"]
    assert "validation" in finalize["required"]
    assert "baseline_test_failures" not in finalize["required"]
    assert "baseline_test_command" not in finalize["required"]
    assert "baseline_test_note" not in finalize["required"]
    assert "final_plan" not in finalize["properties"]
    assert "task_count" not in finalize["properties"]
    task_schema = finalize["properties"]["tasks"]["items"]
    assert set(task_schema["properties"]) == {
        "id",
        "description",
        "depends_on",
        "status",
        "kind",
        "complexity",
        "complexity_justification",
        "executor_notes",
        "files_changed",
        "commands_run",
        "auto_attributed_files",
        "evidence_files",
        "reviewer_verdict",
        "stance",
        "stop_signal",
    }
    assert set(task_schema["required"]) == {
        "id",
        "description",
        "depends_on",
        "status",
        "complexity",
        "complexity_justification",
        "executor_notes",
        "files_changed",
        "commands_run",
        "evidence_files",
        "reviewer_verdict",
    }
    assert task_schema["properties"]["status"]["enum"] == ["pending", "done", "skipped", "blocked"]
    assert set(task_schema["properties"]["stance"]["properties"]) == {
        "challenge_engaged",
        "angle_taken",
        "what_changed",
    }
    assert set(task_schema["properties"]["stop_signal"]["properties"]) == {"requested", "defense"}
    assert "executor_note" in finalize["properties"]["sense_checks"]["items"]["properties"]
    # Validation sub-schema
    validation_schema = finalize["properties"]["validation"]
    assert "plan_steps_covered" in validation_schema["properties"]
    assert "orphan_tasks" in validation_schema["properties"]
    assert "completeness_notes" in validation_schema["properties"]
    assert "coverage_complete" in validation_schema["properties"]
    step_item = validation_schema["properties"]["plan_steps_covered"]["items"]
    assert "plan_step_summary" in step_item["properties"]
    assert "finalize_item_ids" in step_item["properties"]
    assert step_item["properties"]["finalize_item_ids"]["type"] == "array"


def test_execution_schema_requires_task_updates() -> None:
    execution = SCHEMAS["execution.json"]
    assert "task_updates" in execution["properties"]
    assert "task_updates" in execution["required"]
    assert "sense_check_acknowledgments" in execution["properties"]
    assert "sense_check_acknowledgments" in execution["required"]
    item_schema = execution["properties"]["task_updates"]["items"]
    assert item_schema["properties"]["status"]["enum"] == ["done", "skipped", "completed", "blocked"]
    assert "files_changed" in item_schema["properties"]
    assert "commands_run" in item_schema["properties"]
    assert "auto_attributed_files" in item_schema["properties"]
    assert item_schema["properties"]["auto_attributed_files"]["type"] == [
        "boolean",
        "null",
    ]
    assert "auto_attributed_files" not in item_schema["required"]


def test_execution_doc_schema_strips_auto_attributed_files() -> None:
    execution_doc = SCHEMAS["execution_doc.json"]
    item_schema = execution_doc["properties"]["task_updates"]["items"]
    assert "auto_attributed_files" not in item_schema["properties"]
    assert "stance" in item_schema["properties"]
    assert "stop_signal" in item_schema["properties"]


def test_review_schema_requires_task_and_sense_check_verdicts() -> None:
    review = SCHEMAS["review.json"]
    assert "review_verdict" in review["properties"]
    assert "checks" in review["properties"]
    assert "task_verdicts" in review["properties"]
    assert "sense_check_verdicts" in review["properties"]
    assert "rework_items" in review["properties"]
    assert "review_verdict" in review["required"]
    assert "checks" not in review["required"]
    assert "pre_check_flags" not in review["required"]
    assert "verified_flag_ids" not in review["required"]
    assert "disputed_flag_ids" not in review["required"]
    assert "task_verdicts" in review["required"]
    assert "sense_check_verdicts" in review["required"]
    assert "rework_items" in review["required"]
    assert "evidence_files" in review["properties"]["task_verdicts"]["items"]["properties"]
    # Rework items sub-schema
    rework_item = review["properties"]["rework_items"]["items"]
    assert "task_id" in rework_item["properties"]
    assert "issue" in rework_item["properties"]
    assert "expected" in rework_item["properties"]
    assert "actual" in rework_item["properties"]
    assert "evidence_file" in rework_item["properties"]
    assert "flag_id" in rework_item["properties"]
    assert "source" in rework_item["properties"]
    assert set(rework_item["required"]) == {
        "task_id",
        "issue",
        "expected",
        "actual",
        "evidence_file",
        "flag_id",
        "source",
        "deterministic_check",
    }
    assert rework_item["properties"]["flag_id"]["type"] == ["string", "null"]
    assert rework_item["properties"]["source"]["type"] == ["string", "null"]
    assert rework_item["properties"]["deterministic_check"]["type"] == ["object", "null"]


def test_review_schema_accepts_new_review_shape_without_checks() -> None:
    payload = _minimal_review_payload()
    payload.pop("checks")
    payload.pop("pre_check_flags")
    payload.pop("verified_flag_ids")
    payload.pop("disputed_flag_ids")

    assert list(Draft7Validator(SCHEMAS["review.json"]).iter_errors(payload)) == []


def test_review_schema_accepts_parallel_mode_extensions_in_both_copies() -> None:
    payload = {
        "review_verdict": "needs_rework",
        "checks": [
                {
                    "id": "coverage",
                    "question": "Does the diff cover the issue?",
                    "guidance": "Inspect the changed module for missing review follow-up.",
                    "concerned_task_ids": ["T1"],
                    "findings": [
                    {
                        "detail": "Coverage review found one concrete issue example that the diff still does not handle.",
                        "flagged": True,
                        "status": "blocking",
                        "evidence_file": "pkg/module.py",
                    }
                ],
                "prior_findings": [],
            }
        ],
        "pre_check_flags": [
            {
                "id": "PRECHECK-SOURCE_TOUCH",
                "check": "source_touch",
                "detail": "The diff touches a package source file.",
                "severity": "minor",
                "evidence_file": "pkg/module.py",
            }
        ],
        "verified_flag_ids": ["REVIEW-COVERAGE-001"],
        "disputed_flag_ids": ["REVIEW-PARITY-001"],
        "criteria": [{"name": "criterion", "priority": "must", "pass": "fail", "evidence": "Missing coverage."}],
        "issues": ["Coverage review found a blocking issue."],
        "rework_items": [
            {
                "task_id": "REVIEW",
                "issue": "Coverage gap remains.",
                "expected": "All issue examples are covered.",
                "actual": "One issue example remains uncovered.",
                "evidence_file": "pkg/module.py",
                "flag_id": None,
                "source": "review_coverage",
                "deterministic_check": _deterministic_check(),
            }
        ],
        "summary": "Heavy review found a blocking issue.",
        "task_verdicts": [
            {
                "task_id": "T1",
                "reviewer_verdict": "Needs follow-up.",
                "evidence_files": ["pkg/module.py"],
            }
        ],
        "sense_check_verdicts": [{"sense_check_id": "SC1", "verdict": "Needs follow-up."}],
    }
    disk_schema = _review_disk_schema()

    assert list(Draft7Validator(SCHEMAS["review.json"]).iter_errors(payload)) == []
    assert list(Draft7Validator(disk_schema).iter_errors(payload)) == []


def test_review_schema_accepts_optional_rework_item_flag_id() -> None:
    payload = _minimal_review_payload()
    payload["review_verdict"] = "needs_rework"
    payload["issues"] = ["Critique flag remains unresolved."]
    payload["rework_items"] = [
        {
            "task_id": "REVIEW",
            "issue": "Critique flag remains unresolved.",
            "expected": "The final diff addresses the flagged concern directly.",
            "actual": "The diff leaves the flagged behavior unchanged.",
            "evidence_file": "megaplan/prompts/review.py",
            "flag_id": "FLAG-001",
            "source": "review_flag_reverify",
            "deterministic_check": None,
        }
    ]
    disk_schema = _review_disk_schema()

    assert list(Draft7Validator(SCHEMAS["review.json"]).iter_errors(payload)) == []
    assert list(Draft7Validator(disk_schema).iter_errors(payload)) == []


def test_review_schema_still_accepts_rework_items_without_flag_id() -> None:
    payload = _minimal_review_payload()
    payload["review_verdict"] = "needs_rework"
    payload["issues"] = ["Executor still needs to finish the review follow-up."]
    payload["rework_items"] = [
        {
            "task_id": "REVIEW",
            "issue": "Executor still needs to finish the review follow-up.",
            "expected": "All required review follow-up work is complete.",
            "actual": "One required review follow-up item is still missing.",
            "evidence_file": "megaplan/handlers.py",
            "flag_id": None,
            "source": None,
            "deterministic_check": None,
        }
    ]
    disk_schema = _review_disk_schema()

    assert list(Draft7Validator(SCHEMAS["review.json"]).iter_errors(payload)) == []
    assert list(Draft7Validator(disk_schema).iter_errors(payload)) == []


# ---------------------------------------------------------------------------
# Original tests
# ---------------------------------------------------------------------------


def test_gate_schema_is_strict_and_requires_core_fields() -> None:
    schema = strict_schema(SCHEMAS["gate.json"])
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "recommendation",
        "rationale",
        "signals_assessment",
        "warnings",
        "settled_decisions",
        "flag_resolutions",
        "accepted_tradeoffs",
        "tiebreaker_question",
        "tiebreaker_flag_ids",
        "tiebreaker_fuzzy_group_id",
    ]
    assert schema["properties"]["recommendation"]["enum"] == [
        "PROCEED", "ITERATE", "ESCALATE", "TIEBREAKER",
    ]


def test_plan_schema_has_core_fields_only() -> None:
    schema = strict_schema(SCHEMAS["plan.json"])
    assert set(schema["required"]) == {"plan", "questions", "success_criteria", "assumptions"}
    assert "self_flags" not in schema["properties"]
    assert "gate_recommendation" not in schema["properties"]


def test_prep_schema_exists_and_has_expected_structure() -> None:
    schema = strict_schema(SCHEMAS["prep.json"])
    assert set(schema["required"]) == {
        "skip",
        "task_summary",
        "key_evidence",
        "relevant_code",
        "test_expectations",
        "constraints",
        "suggested_approach",
    }
    evidence_schema = schema["properties"]["key_evidence"]["items"]
    relevant_code_schema = schema["properties"]["relevant_code"]["items"]
    test_expectation_schema = schema["properties"]["test_expectations"]["items"]
    assert set(evidence_schema["required"]) == {"point", "source", "relevance"}
    assert evidence_schema["properties"]["relevance"]["enum"] == ["high", "medium", "low"]
    assert set(relevant_code_schema["required"]) == {"file_path", "why", "functions"}
    assert relevant_code_schema["properties"]["functions"]["items"]["type"] == "string"
    assert set(test_expectation_schema["required"]) == {"test_id", "what_it_checks", "status"}
    assert test_expectation_schema["properties"]["status"]["enum"] == ["fail_to_pass", "pass_to_pass"]
    assert "findings" not in schema["properties"]
    assert "areas" not in schema["properties"]
    assert "missed_units" not in schema["properties"]


def test_research_prep_sidecar_schemas_add_internal_detail_without_changing_prep() -> None:
    triage_schema = strict_schema(SCHEMAS["prep_triage.json"])
    assert set(triage_schema["required"]) == {"triage_framing", "areas"}
    area_schema = triage_schema["properties"]["areas"]["items"]
    assert set(area_schema["required"]) == {"id", "area", "brief", "suggested_files"}

    research_schema = strict_schema(SCHEMAS["research.json"])
    finding_schema = research_schema["properties"]["findings"]["items"]
    assert set(finding_schema["required"]) == {
        "area",
        "brief",
        "status",
        "findings",
        "files",
        "code_refs",
        "confidence",
        "error",
    }
    assert finding_schema["properties"]["status"]["enum"] == [
        "complete",
        "partial",
        "timed_out",
        "error",
        "not_needed",
    ]

    metrics_schema = strict_schema(SCHEMAS["prep_metrics.json"])
    assert "missed_units" in metrics_schema["properties"]
    assert "total_tokens" in metrics_schema["required"]
    assert "elapsed_time_ms" in metrics_schema["required"]
    assert "files" in metrics_schema["required"]
    assert "code_refs" in metrics_schema["required"]
    assert "gap_notes" in metrics_schema["required"]
    assert "contradiction_notes" in metrics_schema["required"]
    assert "overlap_groups" in metrics_schema["required"]
    assert "cross_reference" in metrics_schema["required"]
    assert "stage_metrics" in metrics_schema["required"]
    assert "per_unit" in metrics_schema["required"]
    cross_reference_schema = metrics_schema["properties"]["cross_reference"]
    assert set(cross_reference_schema["required"]) == {
        "performed",
        "checked_files",
        "existing_files",
        "missing_files",
        "shared_files",
    }
    overlap_schema = metrics_schema["properties"]["overlap_groups"]["items"]
    assert set(overlap_schema["required"]) == {"kind", "value", "areas"}
    stage_metrics_schema = metrics_schema["properties"]["stage_metrics"]
    assert set(stage_metrics_schema["required"]) == {"triage", "fanout", "distill"}
    per_unit_schema = metrics_schema["properties"]["per_unit"]["items"]
    assert set(per_unit_schema["required"]) == {"area", "status", "elapsed_time_ms", "files", "code_refs"}


def test_gate_schema_includes_settled_decisions_structure() -> None:
    schema = strict_schema(SCHEMAS["gate.json"])
    item_schema = schema["properties"]["settled_decisions"]["items"]
    assert set(item_schema["required"]) == {"id", "decision", "rationale"}
    assert "rationale" in item_schema["properties"]


def test_gate_schema_flag_resolutions_stay_codex_compatible() -> None:
    schema = strict_schema(SCHEMAS["gate.json"])
    item_schema = schema["properties"]["flag_resolutions"]["items"]

    assert set(item_schema["required"]) == {"flag_id", "action", "evidence", "rationale"}
    assert "oneOf" not in item_schema
    assert set(item_schema["properties"]["action"]["enum"]) == {
        "dispute",
        "accept_tradeoff",
        "verify_fixed",
    }
    assert "evidence" in item_schema["properties"]
    assert "rationale" in item_schema["properties"]


def test_schema_registry_covers_the_six_strict_mode_required_fixes() -> None:
    revise = SCHEMAS["revise.json"]
    gate = SCHEMAS["gate.json"]
    review = SCHEMAS["review.json"]
    review_check = review["properties"]["checks"]["items"]
    review_finding = review_check["properties"]["findings"]["items"]
    pre_check_flag = review["properties"]["pre_check_flags"]["items"]

    assert set(revise["required"]) == {
        "plan",
        "changes_summary",
        "flags_addressed",
        "assumptions",
        "success_criteria",
        "questions",
    }
    assert set(gate["required"]) == {
        "recommendation",
        "rationale",
        "signals_assessment",
        "warnings",
        "settled_decisions",
        "flag_resolutions",
        "accepted_tradeoffs",
    }
    assert set(review["required"]) == {
        "review_verdict",
        "criteria",
        "issues",
        "rework_items",
        "summary",
        "task_verdicts",
        "sense_check_verdicts",
    }
    assert {"checks", "pre_check_flags", "verified_flag_ids", "disputed_flag_ids"}.issubset(
        review["properties"]
    )
    assert set(review_check["required"]) == {
        "id",
        "question",
        "guidance",
        "findings",
        "prior_findings",
        "concerned_task_ids",
    }
    assert set(review_finding["required"]) == {"detail", "flagged", "status", "evidence_file"}
    assert set(pre_check_flag["required"]) == {"id", "check", "detail", "severity", "evidence_file"}


def test_strict_schema_new_tracking_objects_are_strict() -> None:
    schema = strict_schema(SCHEMAS["finalize.json"])
    task_schema = schema["properties"]["tasks"]["items"]
    sense_check_schema = schema["properties"]["sense_checks"]["items"]
    execution_schema = strict_schema(SCHEMAS["execution.json"])
    task_update_schema = execution_schema["properties"]["task_updates"]["items"]
    assert task_schema["additionalProperties"] is False
    assert "stance" in task_schema["properties"]
    assert "stop_signal" in task_schema["properties"]
    assert set(task_schema["required"]) == {
        "id",
        "description",
        "depends_on",
        "status",
        "complexity",
        "complexity_justification",
        "executor_notes",
        "files_changed",
        "commands_run",
        "evidence_files",
        "reviewer_verdict",
    }
    assert set(task_update_schema["required"]) == {
        "task_id",
        "status",
        "executor_notes",
        "files_changed",
        "commands_run",
    }
    assert sense_check_schema["additionalProperties"] is False
    assert set(sense_check_schema["required"]) == {"id", "task_id", "question", "executor_note", "verdict"}


def test_strict_critique_evaluator_schema_preserves_optional_flag_verifications_and_branch_local_shapes() -> None:
    schema = strict_schema(SCHEMAS["critique_evaluator.json"])
    assert set(schema["required"]) == {"selections", "skipped", "evaluator_model"}

    branches = schema["properties"]["selections"]["items"]["oneOf"]
    legacy_branch, catalog_branch, other_branch = branches

    assert legacy_branch["additionalProperties"] is False
    assert set(legacy_branch["required"]) == {"check_id", "critic_model", "why"}

    assert catalog_branch["additionalProperties"] is False
    assert set(catalog_branch["required"]) == {
        "check_id",
        "complexity",
        "complexity_justification",
    }

    assert other_branch["additionalProperties"] is False
    assert set(other_branch["required"]) == {
        "check_id",
        "area",
        "why",
        "complexity",
        "complexity_justification",
    }


def test_openai_runtime_critique_evaluator_schema_uses_supported_branching_keywords() -> None:
    schema = _enforce_openai_strict_mode(strict_schema(SCHEMAS["critique_evaluator.json"]))
    selection_items = schema["properties"]["selections"]["items"]

    assert "oneOf" not in selection_items
    assert "anyOf" in selection_items

    other_branch = selection_items["anyOf"][2]
    assert "const" not in other_branch["properties"]["check_id"]
    assert other_branch["properties"]["check_id"]["enum"] == ["other"]
    assert set(schema["required"]) == {
        "selections",
        "skipped",
        "evaluator_model",
        "flag_verifications",
    }


def test_plan_schema_requires_field_round_trip() -> None:
    from jsonschema import Draft7Validator

    schema = SCHEMAS["plan.json"]
    payload_with_requires = {
        "plan": "Test plan",
        "questions": [],
        "success_criteria": [
            {"criterion": "All tests pass", "priority": "must", "requires": ["run_tests"]},
            {"criterion": "Code is clean", "priority": "should", "requires": ["run_linter", "read_files"]},
            {"criterion": "Looks good", "priority": "info"},
        ],
        "assumptions": [],
    }
    assert list(Draft7Validator(schema).iter_errors(payload_with_requires)) == []

    payload_without_requires = {
        "plan": "Test plan",
        "questions": [],
        "success_criteria": [
            {"criterion": "All tests pass", "priority": "must"},
        ],
        "assumptions": [],
    }
    assert list(Draft7Validator(schema).iter_errors(payload_without_requires)) == []


def test_review_schema_accepts_deferred_human_verdict() -> None:
    from jsonschema import Draft7Validator

    payload = _minimal_review_payload()
    payload["criteria"] = [
        {"name": "UI check", "priority": "must", "pass": "deferred_human", "evidence": "Needs human."},
    ]
    assert list(Draft7Validator(SCHEMAS["review.json"]).iter_errors(payload)) == []


def test_critique_schema_accepts_verifiability_category() -> None:
    critique = SCHEMAS["critique.json"]
    category_enum = critique["properties"]["flags"]["items"]["properties"]["category"]["enum"]
    assert "verifiability" in category_enum


def test_gate_schema_accepts_tiebreaker_recommendation() -> None:
    schema = SCHEMAS["gate.json"]
    assert "TIEBREAKER" in schema["properties"]["recommendation"]["enum"]
    props = schema["properties"]
    assert "tiebreaker_question" in props
    assert "tiebreaker_flag_ids" in props
    assert "tiebreaker_fuzzy_group_id" in props


def test_tiebreaker_schemas_registered() -> None:
    assert "tiebreaker_researcher.json" in SCHEMAS
    assert "tiebreaker_challenger.json" in SCHEMAS
    researcher = SCHEMAS["tiebreaker_researcher.json"]
    challenger = SCHEMAS["tiebreaker_challenger.json"]
    assert researcher["type"] == "object"
    assert challenger["type"] == "object"
    assert "evidence" in researcher["properties"]
    assert "options" in researcher["properties"]
    assert "preliminary_pick" in researcher["properties"]
    assert "counter_recommendation" in challenger["properties"]
    assert "missing_options" in challenger["properties"]


# ---------------------------------------------------------------------------
# Complexity field validation tests
# ---------------------------------------------------------------------------

def _make_finalize_payload_with_task(**overrides: object) -> dict:
    """Return a minimal valid finalize.json payload with one task, overridable."""
    return {
        "tasks": [
            {
                "id": "T1",
                "description": "Test task",
                "depends_on": [],
                "status": "pending",
                "complexity": 3,
                "complexity_justification": "Test task; multi-file logic → tier 3.",
                "kind": "code",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
                **overrides,
            }
        ],
        "watch_items": [],
        "sense_checks": [],
        "user_actions": [],
        "meta_commentary": "",
        "validation": {
            "plan_steps_covered": [],
            "orphan_tasks": [],
            "completeness_notes": "",
            "coverage_complete": True,
        },
    }


def test_complexity_valid_values_1_through_5_accepted() -> None:
    schema = SCHEMAS["finalize.json"]
    for val in (1, 2, 3, 4, 5):
        payload = _make_finalize_payload_with_task(complexity=val)
        errors = list(Draft7Validator(schema).iter_errors(payload))
        assert errors == [], f"Complexity {val} should be accepted, got: {errors}"


def test_complexity_below_range_rejected() -> None:
    schema = SCHEMAS["finalize.json"]
    payload = _make_finalize_payload_with_task(complexity=0)
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


def test_complexity_above_range_rejected() -> None:
    schema = SCHEMAS["finalize.json"]
    payload = _make_finalize_payload_with_task(complexity=6)
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


def test_complexity_wrong_type_rejected() -> None:
    schema = SCHEMAS["finalize.json"]
    payload = _make_finalize_payload_with_task(complexity="high")
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


def test_complexity_missing_rejected() -> None:
    schema = SCHEMAS["finalize.json"]
    task_overrides = {
        k: v for k, v in _make_finalize_payload_with_task()["tasks"][0].items()
        if k != "complexity"
    }
    payload = _make_finalize_payload_with_task(**task_overrides)
    # Remove complexity key entirely
    del payload["tasks"][0]["complexity"]
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# T12(d): open_questions schema validation (prep.json)
# ---------------------------------------------------------------------------

def _minimal_prep_payload(**overrides: object) -> dict:
    payload: dict[str, object] = {
        "skip": False,
        "task_summary": "Test prep.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Proceed.",
    }
    payload.update(overrides)
    return payload


def test_prep_schema_validates_populated_open_questions() -> None:
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload(
        open_questions=[
            {
                "severity": "blocking",
                "question": "Which auth library?",
            },
            {
                "severity": "assume_and_proceed",
                "question": "Which cache backend?",
                "assumption": "Redis is fine.",
            },
        ],
    )
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_prep_schema_validates_absent_open_questions() -> None:
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload()
    assert "open_questions" not in payload
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_prep_schema_validates_empty_open_questions() -> None:
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload(open_questions=[])
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors == [], f"Expected no errors, got: {errors}"


def test_prep_schema_rejects_open_question_missing_severity() -> None:
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload(
        open_questions=[{"question": "Missing severity."}],
    )
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


def test_prep_schema_rejects_open_question_missing_question() -> None:
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload(
        open_questions=[{"severity": "blocking"}],
    )
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


def test_prep_schema_rejects_open_question_invalid_severity() -> None:
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload(
        open_questions=[{"severity": "critical", "question": "Bad severity."}],
    )
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert len(errors) > 0


def test_prep_schema_validates_open_questions_without_assumption() -> None:
    """assumption is optional — only severity and question are required."""
    schema = SCHEMAS["prep.json"]
    payload = _minimal_prep_payload(
        open_questions=[{"severity": "blocking", "question": "No assumption field."}],
    )
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert errors == [], f"Expected no errors, got: {errors}"
