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
from arnold_pipelines.megaplan.orchestration.gate_checks import build_gate_artifact
from arnold_pipelines.megaplan.prompts.gate import _write_gate_template
from arnold_pipelines.megaplan.schema_projection import schema_property_names
from arnold_pipelines.megaplan.schemas import SCHEMAS
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
