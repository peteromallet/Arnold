from __future__ import annotations

from argparse import Namespace
import json
from types import SimpleNamespace
from pathlib import Path
import re
from typing import Any, Mapping

import pytest

from arnold.pipeline import ContractResult, ContractStatus
from arnold.pipeline.contract_validation import ValidationDiagnostic
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.types import CONTRACT_RESULT_SCHEMA_VERSION, Port, PortRef
from arnold.pipelines.megaplan._core.state import write_plan_state
from arnold.pipelines.megaplan._pipeline.executor import _EnforcementBinding, _evaluate_cursor_handoff
from arnold.pipelines.megaplan._pipeline.types import (
    Pipeline,
    PipelineVerdict,
    Stage,
    StepContext,
    StepResult,
)
from arnold.pipelines.megaplan.pipeline_contracts import (
    CONTENT_TYPE_JSON,
    PlanningPayloadBuildError,
    PRODUCTION_PLANNING_LOGICAL_TYPES,
    artifact_refs_from_outputs,
    consume_payload_result,
    consume_port,
    produce_payload_result,
    produce_port,
    produce_stage_payload_result,
    register_production_planning_contracts,
    with_stage_payload_result,
)
from arnold.pipelines.megaplan.runtime.inprocess_step import InProcessHandlerStep


SHA256_VERSION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _by_reference_payload(logical_type: str) -> dict:
    return {
        "logical_type": logical_type,
        "artifact_refs": [
            {
                "uri": "artifact://plan/prep.json",
                "content_type": "application/json",
                "digest": "sha256:abc123",
                "size_bytes": 123,
                "name": "prep.json",
            }
        ],
        "summary": "retained by reference",
        "metadata": {"phase": logical_type.rsplit(".", 1)[-1]},
    }


def test_registers_all_nine_production_planning_payload_contracts(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)

    contracts = register_production_planning_contracts(registry)

    assert tuple(contracts) == PRODUCTION_PLANNING_LOGICAL_TYPES
    assert len(contracts) == 9
    for logical_type, contract in contracts.items():
        assert contract.logical_type == logical_type
        assert SHA256_VERSION_RE.fullmatch(contract.schema_version)
        assert contract.schema_version == registry.latest(logical_type)
        assert registry.history(logical_type) == (contract.schema_version,)
        assert contract.accepted_range.logical_type == logical_type
        assert contract.accepted_range.min_version == contract.schema_version
        assert contract.accepted_range.max_version == contract.schema_version
        assert registry.accepts_version(
            logical_type,
            contract.schema_version,
            contract.accepted_range,
        )


def test_production_payload_schemas_are_by_reference_and_validate_examples(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contracts = register_production_planning_contracts(registry)

    for logical_type, contract in contracts.items():
        schema = registry.get_schema(contract.schema_version)
        payload = _by_reference_payload(logical_type)
        result = produce_payload_result(contract, payload)
        consumed, diagnostics = consume_payload_result(registry, contract, result)

        assert schema["required"] == ["logical_type", "artifact_refs"]
        assert schema["properties"]["logical_type"] == {"const": logical_type}
        assert schema["properties"]["artifact_refs"]["type"] == "array"
        assert schema["properties"]["artifact_refs"]["items"]["required"] == [
            "uri",
            "content_type",
        ]
        assert diagnostics == ()
        assert consumed == payload


def test_payload_helpers_keep_logical_schema_version_inside_payload(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[0]
    ]

    result = produce_payload_result(contract, _by_reference_payload(contract.logical_type))

    assert result.schema_version == CONTRACT_RESULT_SCHEMA_VERSION
    assert result.payload["logical_type"] == contract.logical_type
    assert result.payload["schema_version"] == contract.schema_version
    assert result.payload["schema_version"] != result.schema_version


def test_port_helpers_declare_logical_type_and_accepted_hash_range(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[1]
    ]

    producer = produce_port("plan", contract)
    consumer = consume_port("plan", contract)

    assert producer.name == "plan"
    assert producer.content_type == CONTENT_TYPE_JSON
    assert producer.logical_type == contract.logical_type
    assert producer.accepted_version_range == contract.accepted_range
    assert consumer.port_name == "plan"
    assert consumer.content_type == CONTENT_TYPE_JSON
    assert consumer.logical_type == contract.logical_type
    assert consumer.accepted_version_range == contract.accepted_range


def test_megaplan_cursor_handoff_resolves_lowered_typed_ports_without_bypass(
    tmp_path, monkeypatch
) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[0]
    ]
    payload = _by_reference_payload(contract.logical_type)
    contract_result = produce_payload_result(contract, payload)
    producer_port = contract.producer_port("prep_payload")
    consumer_port = contract.consumer_port("prep_payload")
    pipeline = Pipeline(
        stages={
            "prep": Stage(
                name="prep",
                step=object(),
                writes=(producer_port,),
            ),
            "plan": Stage(
                name="plan",
                step=object(),
                reads=(consumer_port,),
            ),
        },
        entry="prep",
        binding_map={("plan", "prep_payload"): ("prep", "prep_payload")},
    )
    result = StepResult(next="plan", contract_result=contract_result)
    captured: dict[str, object] = {}

    from arnold.pipeline import step_io_handoff as handoff_module

    original = handoff_module.evaluate_step_io_handoff

    def _capture(value, **kwargs):
        captured["value"] = value
        captured["producer_port"] = kwargs.get("producer_port")
        captured["consumer_port_decl"] = kwargs.get("consumer_port_decl")
        handoff = original(value, **kwargs)
        captured["handoff"] = handoff
        return handoff

    monkeypatch.setattr(handoff_module, "evaluate_step_io_handoff", _capture)

    _evaluate_cursor_handoff(
        pipeline=pipeline,
        binding=_EnforcementBinding(binding_map=pipeline.binding_map),
        producer_stage=pipeline.stages["prep"],
        consumer_stage=pipeline.stages["plan"],
        result=result,
        ctx=SimpleNamespace(plan_dir=tmp_path, state={}),
        artifact_root=tmp_path,
    )

    assert captured["value"] is contract_result
    assert captured["producer_port"] == producer_port
    assert captured["consumer_port_decl"] == consumer_port
    assert captured["handoff"].decision.classification.value == "typed_valid"


def test_consume_helper_rejects_unaccepted_registered_hash(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[2]
    ]
    newer_version = registry.register(
        contract.logical_type,
        {
            "type": "object",
            "required": ["logical_type", "artifact_refs", "extra"],
            "properties": {
                "logical_type": {"const": contract.logical_type},
                "artifact_refs": {"type": "array"},
                "extra": {"type": "string"},
            },
            "additionalProperties": False,
        },
    )
    result = produce_payload_result(contract, _by_reference_payload(contract.logical_type))
    result = type(result)(
        payload={**result.payload, "schema_version": newer_version},
        schema_version=result.schema_version,
    )

    consumed, diagnostics = consume_payload_result(registry, contract, result)

    assert consumed is None
    assert [diagnostic.code for diagnostic in diagnostics] == [
        "schema_version_not_accepted"
    ]


def test_stage_payload_builder_uses_declared_producer_port_hash_and_metadata(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[3]
    ]
    artifact = tmp_path / "gate.json"
    artifact.write_text('{"recommendation":"PROCEED"}', encoding="utf-8")
    outputs = {"gate": artifact}
    state_patch = {"current_state": "gated", "last_gate": {"recommendation": "PROCEED"}}
    verdict = PipelineVerdict(
        score=0.9,
        flags=("clear",),
        notes="ready",
        payload={"reason": "tests"},
        recommendation="proceed",
    )

    result = produce_stage_payload_result(
        producer_port=contract.producer_port("gate_payload"),
        outputs=outputs,
        state_patch=state_patch,
        contract=contract,
        verdict=verdict,
        outcome={"next": "finalize"},
        diagnostics=(
            ValidationDiagnostic(code="advisory", message="kept for telemetry"),
        ),
        summary="gate completed",
    )
    consumed, diagnostics = consume_payload_result(registry, contract, result)

    assert diagnostics == ()
    assert result.schema_version == CONTRACT_RESULT_SCHEMA_VERSION
    assert result.payload["schema_version"] == contract.schema_version
    assert consumed is not None
    assert consumed["logical_type"] == contract.logical_type
    assert consumed["summary"] == "gate completed"
    assert consumed["artifact_refs"] == list(artifact_refs_from_outputs(outputs))
    assert consumed["artifact_refs"][0]["digest"].startswith("sha256:")
    assert consumed["artifact_refs"][0]["size_bytes"] == artifact.stat().st_size
    metadata = consumed["metadata"]
    assert metadata["producer_port"]["name"] == "gate_payload"
    assert metadata["producer_port"]["logical_type"] == contract.logical_type
    assert metadata["producer_port"]["accepted_version_range"] == {
        "logical_type": contract.logical_type,
        "min_version": contract.schema_version,
        "max_version": contract.schema_version,
    }
    assert metadata["output_keys"] == ["gate"]
    assert metadata["state_patch_keys"] == ["current_state", "last_gate"]
    assert metadata["verdict"]["recommendation"] == "proceed"
    assert metadata["outcome"] == {"next": "finalize"}
    assert metadata["diagnostics"][0]["code"] == "advisory"


def test_with_stage_payload_result_preserves_legacy_outputs_and_state_patch_exactly(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[0]
    ]
    artifact = tmp_path / "prep.json"
    artifact.write_text("{}", encoding="utf-8")
    outputs: dict[str, Path] = {"prep": artifact}
    state_patch = {"current_state": "prepped", "nested": {"keep": ["exact"]}}
    legacy = StepResult(outputs=outputs, state_patch=state_patch, next="plan")

    typed = with_stage_payload_result(
        legacy,
        producer_port=contract.producer_port("prep_payload"),
        contract=contract,
    )

    assert typed is not legacy
    assert typed.outputs is outputs
    assert typed.outputs == legacy.outputs
    assert typed.state_patch is state_patch
    assert typed.state_patch == legacy.state_patch
    assert typed.next == legacy.next
    assert legacy.contract_result is None
    assert typed.contract_result is not None
    consumed, diagnostics = consume_payload_result(registry, contract, typed.contract_result)
    assert diagnostics == ()
    assert consumed["metadata"]["state_patch_keys"] == ["current_state", "nested"]


def test_stage_payload_builder_rejects_producer_port_schema_hash_drift(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[
        PRODUCTION_PLANNING_LOGICAL_TYPES[1]
    ]
    drifted = type(contract.accepted_range)(
        logical_type=contract.logical_type,
        min_version=contract.schema_version,
        max_version=PRODUCTION_PLANNING_LOGICAL_TYPES[0],
    )
    producer_port = type(contract.producer_port("plan_payload"))(
        "plan_payload",
        CONTENT_TYPE_JSON,
        logical_type=contract.logical_type,
        accepted_version_range=drifted,
    )

    try:
        produce_stage_payload_result(
            producer_port=producer_port,
            outputs={},
            state_patch={},
            contract=contract,
        )
    except PlanningPayloadBuildError as exc:
        assert "max_version does not match payload schema hash" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("expected PlanningPayloadBuildError")


def test_cursor_handoff_passes_contract_carrier_and_preserves_metadata(tmp_path, monkeypatch) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    contract = register_production_planning_contracts(registry)[PRODUCTION_PLANNING_LOGICAL_TYPES[0]]
    producer_port = contract.producer_port("prep_payload")
    consumer_port = contract.consumer_port("prep_payload")
    payload = _by_reference_payload(contract.logical_type)
    contract_result = ContractResult(
        status=ContractStatus.COMPLETED,
        authority_level="typed",
        schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
        payload={
            "logical_type": contract.logical_type,
            "schema_version": contract.schema_version,
            "payload": payload,
        },
    )
    pipeline = Pipeline(
        stages={
            "prep": Stage(
                name="prep",
                step=object(),
                produces=(producer_port,),
            ),
            "plan": Stage(
                name="plan",
                step=object(),
                consumes=(consumer_port,),
            ),
        },
        entry="prep",
        binding_map={("plan", "prep_payload"): ("prep", "prep_payload")},
    )
    result = StepResult(next="plan", contract_result=contract_result)
    captured: dict[str, object] = {}

    from arnold.pipeline import step_io_handoff as handoff_module

    original = handoff_module.evaluate_step_io_handoff

    def _capture(value, **kwargs):
        captured["value"] = value
        handoff = original(value, **kwargs)
        captured["handoff"] = handoff
        return handoff

    monkeypatch.setattr(handoff_module, "evaluate_step_io_handoff", _capture)

    _evaluate_cursor_handoff(
        pipeline=pipeline,
        binding=_EnforcementBinding(binding_map=pipeline.binding_map),
        producer_stage=pipeline.stages["prep"],
        consumer_stage=pipeline.stages["plan"],
        result=result,
        ctx=SimpleNamespace(plan_dir=tmp_path, state={}),
        artifact_root=tmp_path,
    )

    assert captured["value"] is contract_result
    handoff = captured["handoff"]
    assert handoff.contract_result is contract_result
    assert handoff.decision.classification.value == "typed_valid"
    assert handoff.decision.envelope is not None
    assert handoff.decision.envelope.payload == payload
    assert handoff.contract_result.authority_level == "typed"
    assert handoff.contract_result.schema_version == CONTRACT_RESULT_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("stage_name", "artifact_name", "logical_type", "next_state", "response"),
    (
        ("prep", "prep.json", PRODUCTION_PLANNING_LOGICAL_TYPES[0], "prepped", {}),
        (
            "critique",
            "critique_output.json",
            PRODUCTION_PLANNING_LOGICAL_TYPES[2],
            "critiqued",
            {},
        ),
        (
            "gate",
            "gate.json",
            PRODUCTION_PLANNING_LOGICAL_TYPES[3],
            "gated",
            {"recommendation": "PROCEED"},
        ),
        ("execute", "execution.json", PRODUCTION_PLANNING_LOGICAL_TYPES[6], "executed", {}),
        ("review", "review.json", PRODUCTION_PLANNING_LOGICAL_TYPES[7], "reviewed", {}),
    ),
)
def test_migrated_stage_outputs_are_carrier_only_at_cursor_seam(
    tmp_path,
    monkeypatch,
    stage_name: str,
    artifact_name: str,
    logical_type: str,
    next_state: str,
    response: Mapping[str, Any],
) -> None:
    plan_name = f"{stage_name}-plan"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan_name, "current_state": "ready"}),
        encoding="utf-8",
    )

    def _handler(root: Path, args: Namespace) -> Mapping[str, Any]:
        run_plan_dir = root / ".megaplan" / "plans" / args.plan
        (run_plan_dir / artifact_name).write_text(
            json.dumps({"stage": stage_name, "ok": True}),
            encoding="utf-8",
        )
        write_plan_state(
            run_plan_dir,
            mode="executor-key-merge",
            state={"current_state": next_state},
            executor_owned_keys=["current_state"],
        )
        return response

    registry = ContractSchemaRegistry(tmp_path)
    contracts = register_production_planning_contracts(registry)
    contract = contracts[logical_type]
    producer_port = contract.producer_port(f"{stage_name}_payload")
    consumer_port = contract.consumer_port(f"{stage_name}_payload")
    step = InProcessHandlerStep(
        name=stage_name,
        kind="produce",
        handler=_handler,
        produces=(producer_port,),
    )
    result = step.run(
        StepContext(
            plan_dir=plan_dir,
            state={"name": plan_name},
            profile={"root": tmp_path, "project_dir": tmp_path},
            mode="test",
            inputs={},
        )
    )

    assert artifact_name not in result.outputs
    assert result.contract_result is not None
    payload, diagnostics = consume_payload_result(
        registry,
        contract,
        result.contract_result,
    )
    assert diagnostics == ()
    assert payload is not None
    assert payload["logical_type"] == logical_type
    assert payload["metadata"]["output_keys"] == [artifact_name]
    assert [ref["name"] for ref in payload["artifact_refs"]] == [artifact_name]
    assert payload["artifact_refs"][0]["digest"].startswith("sha256:")

    pipeline = Pipeline(
        stages={
            stage_name: Stage(
                name=stage_name,
                step=object(),
                produces=(producer_port,),
            ),
            "downstream": Stage(
                name="downstream",
                step=object(),
                consumes=(consumer_port,),
            ),
        },
        entry=stage_name,
        binding_map={("downstream", f"{stage_name}_payload"): (stage_name, f"{stage_name}_payload")},
    )
    captured: dict[str, object] = {}

    from arnold.pipeline import step_io_handoff as handoff_module

    original = handoff_module.evaluate_step_io_handoff

    def _capture(value, **kwargs):
        captured["value"] = value
        handoff = original(value, **kwargs)
        captured["handoff"] = handoff
        return handoff

    monkeypatch.setattr(handoff_module, "evaluate_step_io_handoff", _capture)

    _evaluate_cursor_handoff(
        pipeline=pipeline,
        binding=_EnforcementBinding(binding_map=pipeline.binding_map),
        producer_stage=pipeline.stages[stage_name],
        consumer_stage=pipeline.stages["downstream"],
        result=result,
        ctx=SimpleNamespace(plan_dir=plan_dir, state={}),
        artifact_root=tmp_path,
    )

    assert captured["value"] is result.contract_result
    handoff = captured["handoff"]
    assert handoff.contract_result is result.contract_result
    assert handoff.decision.classification.value == "typed_valid"
