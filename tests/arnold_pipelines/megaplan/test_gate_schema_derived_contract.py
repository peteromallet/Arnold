from __future__ import annotations

import json

import pytest

from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan._core import ensure_runtime_layout
from arnold_pipelines.megaplan.handlers.gate import (
    _build_gate_carry,
    _gate_response_fields,
    _normalize_gate_payload,
    _sync_legacy_last_gate_for_workflow,
)
from arnold_pipelines.megaplan.handlers.structured_output import promote_scratch
from arnold_pipelines.megaplan.model_seam import (
    ModelStructuralAuditError,
    capture_step_output,
)
from arnold_pipelines.megaplan.north_star_actions import NORTH_STAR_ACTION_SCHEMA
from arnold_pipelines.megaplan.orchestration.gate_checks import build_gate_artifact
from arnold_pipelines.megaplan.prompts.gate import (
    _north_star_action_contract_instruction,
    _write_gate_template,
)
from arnold_pipelines.megaplan.schema_projection import schema_property_names
from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers.hermes import clean_parsed_payload


def _invocation() -> StepInvocation:
    return StepInvocation(
        kind="model",
        metadata={
            "validation_step": "gate",
            "compatibility_validation_step": "gate",
        },
    )


def _payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "recommendation": "PROCEED",
        "rationale": "The plan is ready.",
        "signals_assessment": "No blocking signals remain.",
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "north_star_actions": [],
        "tiebreaker_flag_ids": [],
        "tiebreaker_fuzzy_group_id": "",
        "tiebreaker_question": "",
    }
    payload.update(updates)
    return payload


def _signals() -> dict[str, object]:
    return {
        "preflight_results": {"project_dir_exists": True},
        "criteria_check": {"count": 1},
        "unresolved_flags": [],
        "warnings": [],
        "robustness": "standard",
        "signals": {"addressed_flags": []},
    }


def test_exact_incident_missing_north_star_actions_fails_before_persistence() -> None:
    payload = _payload()
    payload.pop("north_star_actions")

    normalized = _normalize_gate_payload(dict(payload), {})
    assert "north_star_actions" not in normalized
    with pytest.raises(ModelStructuralAuditError, match="north_star_actions"):
        capture_step_output(_invocation(), normalized)


def test_hermes_does_not_synthesize_missing_required_gate_fields() -> None:
    payload = _payload()
    payload.pop("north_star_actions")

    clean_parsed_payload(payload, SCHEMAS["gate.json"], "gate")

    assert "north_star_actions" not in payload
    with pytest.raises(ModelStructuralAuditError, match="north_star_actions"):
        capture_step_output(_invocation(), payload)


def test_gate_rejects_unknown_nested_fields_instead_of_accepting_them() -> None:
    payload = _payload(
        accepted_tradeoffs=[
            {
                "flag_id": "flag-1",
                "concern": "A tradeoff.",
                "subsystem": "gate",
                "rationale": "Explicitly accepted.",
                "model_commentary": "not contract data",
            }
        ]
    )

    with pytest.raises(ModelStructuralAuditError, match="model_commentary"):
        capture_step_output(_invocation(), payload)


def test_gate_rejects_unknown_top_level_fields_instead_of_stripping_them() -> None:
    payload = _payload(model_commentary="not contract data")

    with pytest.raises(ModelStructuralAuditError, match="model_commentary"):
        capture_step_output(_invocation(), payload)


def test_gate_reader_enforces_worker_strict_action_inventory() -> None:
    action = {
        "id": "NSA7",
        "question_id": "Q7",
        "question": "What must change?",
        "concern": "The receipt is missing.",
        "category": "correctness",
        "action_type": "must_fix",
        "severity": "significant",
        "severity_source": "model",
        "evidence": "The canonical artifact has no receipt.",
        "plan_refs": ["Step 7"],
        "required_change": "Persist and bind the receipt.",
    }
    action.pop("question_id")

    with pytest.raises(ModelStructuralAuditError, match="question_id"):
        capture_step_output(_invocation(), _payload(north_star_actions=[action]))


def test_scratch_promotion_rejects_unknown_gate_field(tmp_path) -> None:
    payload = _payload(model_commentary="must remain a producer error")
    scratch = tmp_path / "gate_output.json"
    seed = json.dumps(_payload())
    scratch.write_text(json.dumps(payload), encoding="utf-8")
    worker = WorkerResult(payload=_payload(), raw_output="", duration_ms=1, cost_usd=0.0)

    with pytest.raises(ValueError, match="model_commentary"):
        promote_scratch(
            tmp_path,
            "gate_output.json",
            schema_property_names(
                SCHEMAS["gate.json"],
                contract="gate scratch promotion",
            ),
            worker,
            seed_json=seed,
        )


def test_gate_prompt_north_star_contract_matches_strict_worker_schema() -> None:
    strict_action_schema = strict_schema(NORTH_STAR_ACTION_SCHEMA)
    required = strict_action_schema["required"]

    instruction = _north_star_action_contract_instruction()

    for field in required:
        assert f'"{field}"' in instruction
    assert "Do not omit fields" in instruction
    assert '"question_id": "route-authority"' in instruction
    assert '"required_change": "Make the canonical route' in instruction
    assert '"severity_source": "schema"' in instruction


def test_exact_incident_incomplete_north_star_action_fails_strict_worker_audit() -> None:
    captured_action = {
        "id": "NSA-M10-1",
        "concern": "The plan leaves retry ownership ambiguous.",
        "category": "live_plan_topology_resume_risk",
        "action_type": "change_plan",
        "severity": "blocking",
        "evidence": "Phase 3 does not name the resume authority.",
        "plan_refs": ["Phase 3 - Step 2"],
    }
    payload = _payload(
        recommendation="ITERATE",
        north_star_actions=[captured_action],
        tiebreaker_question="",
        tiebreaker_flag_ids=[],
        tiebreaker_fuzzy_group_id="",
    )
    strict_gate_schema = strict_schema(SCHEMAS["gate.json"])

    with pytest.raises(ModelStructuralAuditError) as exc:
        capture_step_output(
            StepInvocation(
                kind="model",
                metadata={
                    "validation_step": "gate",
                    "compatibility_validation_step": "gate",
                    "capture_schema": strict_gate_schema,
                },
            ),
            payload,
        )
    diagnostic = str(exc.value)
    for missing_field in (
        "question",
        "question_id",
        "required_change",
        "severity_source",
    ):
        assert f"/north_star_actions/0/{missing_field}" in diagnostic


def test_fresh_gate_summary_clears_stale_artifact_recovery_marker() -> None:
    artifact = build_gate_artifact(_signals(), _payload(), override_forced=False)
    state: dict[str, object] = {
        "config": {"auto_approve": False},
        "meta": {
            "gate_artifact_recovery": {
                "reason": "adopted passing gate.json after worker failure"
            },
            "preserved": "value",
        },
    }

    _sync_legacy_last_gate_for_workflow(state, artifact)  # type: ignore[arg-type]

    assert state["meta"] == {"preserved": "value"}


def test_new_required_gate_field_survives_capture_and_every_persistence_projection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schema = SCHEMAS["gate.json"]
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)
    monkeypatch.setitem(
        schema,
        "required",
        [*schema["required"], "future_contract_field"],
    )
    payload = _payload(future_contract_field="preserve-me")

    captured = capture_step_output(_invocation(), payload).legacy_payload
    artifact = build_gate_artifact(_signals(), captured, override_forced=False)
    carry = _build_gate_carry(artifact, iteration=1)
    state: dict[str, object] = {"config": {"auto_approve": False}}
    _sync_legacy_last_gate_for_workflow(state, artifact)
    response = _gate_response_fields(state, artifact, 0)  # type: ignore[arg-type]

    assert captured["future_contract_field"] == "preserve-me"
    assert artifact["future_contract_field"] == "preserve-me"
    assert carry["future_contract_field"] == "preserve-me"
    assert state["last_gate"]["future_contract_field"] == "preserve-me"  # type: ignore[index]
    assert response["future_contract_field"] == "preserve-me"

    ensure_runtime_layout(tmp_path)
    materialized = json.loads(
        (tmp_path / ".megaplan" / "schemas" / "gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert "future_contract_field" in materialized["properties"]
    assert "future_contract_field" in materialized["required"]


def test_new_schema_field_survives_scratch_promotion_without_allowlist_edit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schema = SCHEMAS["gate.json"]
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)
    payload = _payload(future_contract_field="from-scratch")
    scratch = tmp_path / "gate_output.json"
    seed = json.dumps(_payload())
    scratch.write_text(json.dumps(payload), encoding="utf-8")
    worker = WorkerResult(payload=_payload(), raw_output="", duration_ms=1, cost_usd=0.0)

    status, promoted = promote_scratch(
        tmp_path,
        "gate_output.json",
        schema_property_names(schema, contract="gate scratch promotion"),
        worker,
        seed_json=seed,
    )

    assert status == "filled"
    assert promoted["future_contract_field"] == "from-scratch"


def test_new_schema_field_is_present_in_worker_scratch_template(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    schema = SCHEMAS["gate.json"]
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)

    output_path = _write_gate_template(tmp_path, {})  # type: ignore[arg-type]
    template = json.loads(output_path.read_text(encoding="utf-8"))

    assert set(template) == set(properties)
    assert template["future_contract_field"] == ""


def test_projection_reports_new_required_field_drift_actionably(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = SCHEMAS["gate.json"]
    properties = dict(schema["properties"])
    properties["future_contract_field"] = {"type": "string"}
    monkeypatch.setitem(schema, "properties", properties)
    monkeypatch.setitem(
        schema,
        "required",
        [*schema["required"], "future_contract_field"],
    )

    captured = capture_step_output(
        _invocation(),
        _payload(future_contract_field="present-at-worker-boundary"),
    ).legacy_payload
    captured.pop("future_contract_field")

    with pytest.raises(
        RuntimeError,
        match="gate artifact persistence.*future_contract_field",
    ):
        build_gate_artifact(_signals(), captured, override_forced=False)
