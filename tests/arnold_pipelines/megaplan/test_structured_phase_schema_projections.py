from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from arnold.execution.step_invocation import StepInvocation
from arnold.pipeline.contract_validation import validate_payload_against_schema
from arnold_pipelines.megaplan.execute.batch import (
    _normalize_execute_capture_payload as normalize_batch_execute,
)
from arnold_pipelines.megaplan.handlers.finalize import (
    _FINALIZE_INPUT_SCHEMA,
    _finalize_scratch_known_keys,
)
from arnold_pipelines.megaplan.handlers.review import _review_scratch_known_keys
from arnold_pipelines.megaplan.model_seam import (
    ModelStructuralAuditError,
    _normalize_critique_capture_payload,
    _normalize_execute_capture_payload,
    _normalize_native_capture_payload,
    _normalize_prep_distill_capture_payload,
    capture_step_output,
)
from arnold_pipelines.megaplan.orchestration.critique_runtime import (
    _critique_evaluator_scratch_known_keys,
    _critique_scratch_known_keys,
)
from arnold_pipelines.megaplan.prompts.critique import _write_critique_template
from arnold_pipelines.megaplan.prompts.critique_evaluator import (
    _write_critique_evaluator_template,
)
from arnold_pipelines.megaplan.prompts.finalize import _write_finalize_template
from arnold_pipelines.megaplan.prompts.review import _review_template_payload
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.step_contracts import STEP_CONTRACTS


@pytest.mark.parametrize(
    "step",
    [
        "plan",
        "review",
        "execute",
        "critique",
        "gate",
        "critique_evaluator",
        "prep-distill",
        "finalize",
    ],
)
def test_schema_owned_top_level_addition_survives_every_capture_normalizer(
    monkeypatch: pytest.MonkeyPatch,
    step: str,
) -> None:
    schema = SCHEMAS[STEP_CONTRACTS[step].capture_schema_key]
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)
    invocation = StepInvocation(
        kind="model",
        metadata={"compatibility_validation_step": step},
    )

    normalized = _normalize_native_capture_payload(
        invocation,
        {"future_contract_field": "preserve-me"},
    )

    assert normalized["future_contract_field"] == "preserve-me"


def test_runtime_guard_rejects_schema_owned_field_loss_before_validator_blame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arnold_pipelines.megaplan.model_seam as seam

    payload = {
        "recommendation": "PROCEED",
        "rationale": "Ready.",
        "signals_assessment": "Clear.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": [],
    }

    def lossy_gate_normalizer(value: dict[str, object]) -> dict[str, object]:
        normalized = dict(value)
        normalized.pop("north_star_actions")
        return normalized

    monkeypatch.setattr(seam, "_normalize_gate_capture_payload", lossy_gate_normalizer)
    invocation = StepInvocation(
        kind="model",
        metadata={"compatibility_validation_step": "gate"},
    )

    with pytest.raises(
        ModelStructuralAuditError,
        match=r"schema_owned_field_dropped.*\/north_star_actions",
    ):
        capture_step_output(invocation, payload)


def test_critique_nested_schema_additions_survive_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_schema = SCHEMAS["critique.json"]["properties"]["checks"]["items"]
    properties = dict(check_schema["properties"])
    properties["future_check_field"] = {"type": "string"}
    monkeypatch.setitem(check_schema, "properties", properties)

    normalized = _normalize_critique_capture_payload(
        {
            "checks": [
                {
                    "id": "correctness",
                    "question": "Correct?",
                    "findings": [],
                    "future_check_field": "preserve-me",
                    "model_commentary": "drop-me",
                }
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
    )

    assert normalized["checks"][0]["future_check_field"] == "preserve-me"
    assert "model_commentary" not in normalized["checks"][0]


@pytest.mark.parametrize(
    "normalizer",
    [_normalize_execute_capture_payload, normalize_batch_execute],
)
def test_execute_nested_schema_addition_survives_both_normalizers(
    monkeypatch: pytest.MonkeyPatch,
    normalizer: Callable[[dict[str, object]], dict[str, object]],
) -> None:
    task_schema = SCHEMAS["execution_batch_relaxed.json"]["properties"][
        "task_updates"
    ]["items"]
    properties = dict(task_schema["properties"])
    properties["future_task_field"] = {"type": "string"}
    monkeypatch.setitem(task_schema, "properties", properties)

    normalized = normalizer(
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "future_task_field": "preserve-me",
                    "model_commentary": "drop-me",
                }
            ],
            "sense_check_acknowledgments": [],
        }
    )

    assert normalized["task_updates"][0]["future_task_field"] == "preserve-me"
    assert "model_commentary" not in normalized["task_updates"][0]


def test_prep_nested_schema_addition_survives_alias_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item_schema = SCHEMAS["prep.json"]["properties"]["key_evidence"]["items"]
    properties = dict(item_schema["properties"])
    properties["future_evidence_field"] = {"type": "string"}
    monkeypatch.setitem(item_schema, "properties", properties)

    normalized = _normalize_prep_distill_capture_payload(
        {
            "key_evidence": [
                {
                    "finding": "Aliased point",
                    "file": "evidence.md",
                    "future_evidence_field": "preserve-me",
                    "model_commentary": "drop-me",
                }
            ],
            "relevant_code": [],
            "test_expectations": [],
        }
    )

    evidence = normalized["key_evidence"][0]
    assert evidence["point"] == "Aliased point"
    assert evidence["source"] == "evidence.md"
    assert evidence["future_evidence_field"] == "preserve-me"
    assert "model_commentary" not in evidence


def test_all_file_fill_scratch_projections_follow_schema_additions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projections = {
        "critique.json": _critique_scratch_known_keys,
        "critique_evaluator.json": _critique_evaluator_scratch_known_keys,
        "review.json": _review_scratch_known_keys,
    }
    for schema_name, projection in projections.items():
        schema = SCHEMAS[schema_name]
        properties = dict(schema["properties"])
        properties["future_contract_field"] = {"type": "string"}
        monkeypatch.setitem(schema, "properties", properties)
        assert "future_contract_field" in projection()


def test_review_template_and_promotion_cover_north_star_and_future_schema_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schema = SCHEMAS["review.json"]
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)
    (tmp_path / "finalize.json").write_text(
        json.dumps({"tasks": [], "sense_checks": []}),
        encoding="utf-8",
    )

    template = _review_template_payload(tmp_path)

    assert "north_star_actions" in template
    assert "north_star_actions" in _review_scratch_known_keys()
    assert template["future_contract_field"] == ""
    assert "future_contract_field" in _review_scratch_known_keys()


def test_finalize_input_contract_requires_all_model_owned_persisted_fields() -> None:
    expected = {
        "tasks",
        "sense_checks",
        "watch_items",
        "user_actions",
        "meta_commentary",
    }

    assert set(_FINALIZE_INPUT_SCHEMA["required"]) == expected
    assert _finalize_scratch_known_keys() == frozenset(
        _FINALIZE_INPUT_SCHEMA["properties"]
    )
    result = validate_payload_against_schema(
        {"tasks": [], "sense_checks": [], "watch_items": []},
        _FINALIZE_INPUT_SCHEMA,
    )
    assert result.ok is False
    assert {diagnostic.payload_pointer for diagnostic in result.diagnostics} >= {
        "/user_actions",
        "/meta_commentary",
    }


@pytest.mark.parametrize(
    ("schema", "writer", "filename"),
    [
        (
            SCHEMAS["critique.json"],
            lambda path: _write_critique_template(path, {}, ()),
            "critique_output.json",
        ),
        (
            SCHEMAS["critique_evaluator.json"],
            lambda path: _write_critique_evaluator_template(path, {}),
            "critique_evaluator_output.json",
        ),
        (
            _FINALIZE_INPUT_SCHEMA,
            lambda path: _write_finalize_template(path, {}),
            "finalize_output.json",
        ),
    ],
)
def test_remaining_file_fill_templates_follow_schema_additions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    schema: dict[str, object],
    writer: Callable,
    filename: str,
) -> None:
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)

    writer(tmp_path)
    template = json.loads((tmp_path / filename).read_text(encoding="utf-8"))

    assert template["future_contract_field"] == ""
