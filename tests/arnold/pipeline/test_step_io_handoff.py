from __future__ import annotations

from types import SimpleNamespace

from arnold.pipeline import (
    AcceptedVersionRange,
    CONTRACT_RESULT_SCHEMA_VERSION,
    ContractSchemaRegistry,
    ContractResult,
    ContractStatus,
    EvidenceArtifactRef,
    Freshness,
    Port,
    PortRef,
    Provenance,
    SeamId,
    SeamResolution,
    StepIOClassification,
    StepIOContractContext,
    StepIOEnvelope,
    StepIOOperation,
    evaluate_step_io_handoff,
    read_violation_records,
)


def _schema(const: int | None = None) -> dict:
    properties = {"answer": {"type": "integer"}}
    if const is not None:
        properties["answer"] = {"const": const}
    return {
        "type": "object",
        "required": ["answer"],
        "properties": properties,
        "additionalProperties": False,
    }


def _contract_result(payload: dict, *, schema_version: str = CONTRACT_RESULT_SCHEMA_VERSION) -> ContractResult:
    return ContractResult(
        payload=payload,
        status=ContractStatus.SUSPENDED,
        schema_version=schema_version,
        evidence_refs=(
            EvidenceArtifactRef(
                uri="file:///tmp/evidence.json",
                content_type="application/json",
                digest="sha256:" + "d" * 64,
                size_bytes=17,
                name="evidence.json",
            ),
        ),
        authority_level="verified",
        provenance=Provenance(
            sources=("policy:review",),
            generator="scanner@1.2",
            generated_at="2026-06-12T12:00:00Z",
            chain=("step-a", "step-b"),
        ),
        freshness=Freshness(
            observed_at="2026-06-12T12:00:00Z",
            ttl_seconds=300,
            expires_at="2026-06-12T12:05:00Z",
        ),
    )


def _typed_seam() -> SeamResolution:
    return SeamResolution(
        seam_id=SeamId("pipe", "review", "result", "execute", "result"),
        producer_typed=True,
        consumer_typed=True,
        both_sides_typed=True,
        binding_found=True,
    )


def _mixed_seam() -> SeamResolution:
    return SeamResolution(
        seam_id=SeamId("pipe", "review", "result", "execute", "result"),
        producer_typed=True,
        consumer_typed=False,
        both_sides_typed=False,
        binding_found=True,
    )


def _unresolved_seam() -> SeamResolution:
    return SeamResolution(
        seam_id=None,
        producer_typed=False,
        consumer_typed=False,
        both_sides_typed=False,
        binding_found=False,
        reason="binding lookup unavailable",
    )


def _typed_but_unresolved_seam() -> SeamResolution:
    return SeamResolution(
        seam_id=None,
        producer_typed=True,
        consumer_typed=True,
        both_sides_typed=True,
        binding_found=False,
        reason="binding lookup unavailable",
    )


def test_handoff_validates_resolved_typed_port_pair_and_uses_payload_schema_version(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema())
    envelope = {
        "logical_type": "review",
        "schema_version": payload_version,
        "payload": {"answer": 7},
    }
    result = evaluate_step_io_handoff(
        envelope,
        operation=StepIOOperation.READ,
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef(
            "result",
            "application/json",
            logical_type="review",
            accepted_version_range=AcceptedVersionRange("review", min_version=payload_version),
        ),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.TYPED_VALID
    assert result.decision.value == {"answer": 7}
    assert result.policy.effective_mode == "enforce"
    assert result.allow_read is True
    assert result.allow_write is True


def test_step_io_context_does_not_discover_schema_registry_from_megaplan_env(
    tmp_path, monkeypatch
) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema())
    monkeypatch.setenv("MEGAPLAN_CONTRACT_SCHEMA_ROOT", str(tmp_path))

    result = evaluate_step_io_handoff(
        {
            "logical_type": "review",
            "schema_version": payload_version,
            "payload": {"answer": 7},
        },
        operation=StepIOOperation.READ,
        context=StepIOContractContext(operation=StepIOOperation.READ),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef(
            "result",
            "application/json",
            logical_type="review",
            accepted_version_range=AcceptedVersionRange("review", min_version=payload_version),
        ),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.SCHEMA_UNAVAILABLE


def test_handoff_enforce_blocks_invalid_typed_read_on_resolved_typed_seam(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema(1))
    envelope = {
        "logical_type": "review",
        "schema_version": payload_version,
        "payload": {"answer": 2},
    }

    result = evaluate_step_io_handoff(
        envelope,
        operation="read",
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef("result", "application/json", logical_type="review"),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.TYPED_INVALID
    assert result.allow_read is False
    assert result.allow_write is False


def test_handoff_rejects_payload_schema_version_outside_consumer_accepted_range(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    accepted = registry.register("review", _schema(1))
    rejected = registry.register("review", _schema(2))
    envelope = {
        "logical_type": "review",
        "schema_version": rejected,
        "payload": {"answer": 2},
    }
    result = evaluate_step_io_handoff(
        envelope,
        operation="write",
        context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef(
            "result",
            "application/json",
            logical_type="review",
            accepted_version_range=AcceptedVersionRange("review", max_version=accepted),
        ),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.TYPED_INVALID
    assert result.decision.diagnostics[-1].code == "schema_version_not_accepted"
    assert result.allow_write is False


def test_handoff_mixed_typed_seam_passes_through_without_schema_validation(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    missing_version = "sha256:" + "a" * 64
    envelope = {
        "logical_type": "review",
        "schema_version": missing_version,
        "payload": {"answer": "not validated"},
    }
    result = evaluate_step_io_handoff(
        envelope,
        operation="read",
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        seam=_mixed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=None,
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.LEGACY_UNKNOWN
    assert result.policy.effective_mode == "shadow"
    assert result.allow_read is True
    assert result.allow_write is True


def test_handoff_shadow_mode_emits_telemetry_without_blocking_invalid_typed_handoff(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema(1))
    telemetry_path = tmp_path / "telemetry.jsonl"
    envelope = {
        "logical_type": "review",
        "schema_version": payload_version,
        "payload": {"answer": 2},
    }

    result = evaluate_step_io_handoff(
        envelope,
        operation="write",
        context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef("result", "application/json", logical_type="review"),
        configured_mode="shadow",
        telemetry_path=telemetry_path,
        artifact="artifact.json",
    )

    assert result.decision.classification == StepIOClassification.TYPED_INVALID
    assert result.policy.effective_mode == "shadow"
    assert result.allow_read is True
    # Shadow mode emits telemetry; contract-level write blocking still applies
    # because decision.blocks_write is checked before policy.enforces.
    assert result.allow_write is False
    records = read_violation_records(telemetry_path)
    assert records[0]["mode"] == "shadow"
    assert records[0]["seam"] == "pipe::review.result<=execute.result"
    assert records[0]["pipeline_id"] == "pipe"
    assert records[0]["producer_step"] == "execute"
    assert records[0]["producer_port"] == "result"
    assert records[0]["consumer_step"] == "review"
    assert records[0]["consumer_port"] == "result"
    assert records[0]["classification"] == "typed_invalid"
    assert result.author_diagnostic is not None
    assert result.author_diagnostic.failure_code == result.decision.diagnostics[0].code
    assert "Suggested author action:" in result.author_diagnostic.message


def test_handoff_unresolved_typed_envelope_is_binding_unavailable_without_fallback_validation(
    tmp_path,
) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    missing_version = "sha256:" + "b" * 64
    envelope = {
        "logical_type": "review",
        "schema_version": missing_version,
        "payload": {"answer": "not validated"},
    }
    telemetry_path = tmp_path / "telemetry.jsonl"

    result = evaluate_step_io_handoff(
        envelope,
        operation="read",
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        seam=_unresolved_seam(),
        configured_mode="enforce",
        telemetry_path=telemetry_path,
        artifact="artifact.json",
    )

    assert result.decision.classification == StepIOClassification.BINDING_UNAVAILABLE
    assert result.policy.effective_mode == "shadow"
    assert result.allow_read is True
    assert result.allow_write is True
    assert result.decision.diagnostics[0].code == "binding_unavailable"
    records = read_violation_records(telemetry_path)
    assert records[0]["classification"] == "binding_unavailable"
    assert records[0]["schema_version"] == missing_version


def test_handoff_typed_but_unresolved_binding_caps_enforce_to_shadow_and_emits_unknown_logical_type(
    tmp_path,
) -> None:
    telemetry_path = tmp_path / "telemetry.jsonl"
    envelope = {
        "logical_type": "mystery",
        "schema_version": "sha256:" + "c" * 64,
        "payload": {"answer": "opaque"},
    }

    result = evaluate_step_io_handoff(
        envelope,
        operation="write",
        seam=_typed_but_unresolved_seam(),
        configured_mode="enforce",
        telemetry_path=telemetry_path,
        artifact="artifact.json",
    )

    assert result.decision.classification == StepIOClassification.BINDING_UNAVAILABLE
    assert result.policy.effective_mode == "enforce"
    assert result.allow_read is False
    assert result.allow_write is False
    records = read_violation_records(telemetry_path)
    assert records[0]["logical_type"] == "mystery"
    assert records[0]["mode"] == "enforce"
    assert result.author_diagnostic is not None
    assert result.author_diagnostic.failure_code == "binding_unavailable"
    assert result.author_diagnostic.logical_type == "mystery"
    assert "Suggested author action:" in result.author_diagnostic.message


def test_handoff_rejects_reserved_stream_on_resolved_typed_port_pair(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema())
    envelope = {
        "logical_type": "review",
        "schema_version": payload_version,
        "payload": {"answer": 7},
    }
    result = evaluate_step_io_handoff(
        envelope,
        operation="write",
        context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", cardinality="stream", logical_type="review"),
        consumer_port_decl=PortRef("result", "application/json", logical_type="review"),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.TYPED_INVALID
    assert result.decision.diagnostics[0].code == "reserved_stream_cardinality"
    assert result.allow_read is False
    assert result.allow_write is False


def test_handoff_rejects_structural_contract_result_schema_version_for_payload_registry_lookup(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    envelope = {
        "logical_type": "review",
        "schema_version": CONTRACT_RESULT_SCHEMA_VERSION,
        "payload": {"answer": 7},
    }

    result = evaluate_step_io_handoff(
        envelope,
        operation="read",
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef("result", "application/json", logical_type="review"),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.SCHEMA_UNAVAILABLE
    assert result.decision.diagnostics[0].code == "schema_unavailable"
    assert result.allow_read is False
    assert result.allow_write is False


def test_handoff_rejects_literal_v1_schema_version(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    envelope = {
        "logical_type": "review",
        "schema_version": "v1",
        "payload": {"answer": 7},
    }

    result = evaluate_step_io_handoff(
        envelope,
        operation="write",
        context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef("result", "application/json", logical_type="review"),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.SCHEMA_UNAVAILABLE
    assert result.decision.diagnostics[0].code == "schema_unavailable"
    assert result.allow_read is False
    assert result.allow_write is False


def test_handoff_can_resolve_ports_from_pipeline_binding_map(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema())
    envelope = {
        "logical_type": "review",
        "schema_version": payload_version,
        "payload": {"answer": 7},
    }
    pipeline = SimpleNamespace(
        binding_map={("review", "result"): ("execute", "result")},
        stages={
            "execute": SimpleNamespace(produces=(Port("result", "application/json"),)),
            "review": SimpleNamespace(consumes=(PortRef("result", "application/json"),)),
        },
    )

    result = evaluate_step_io_handoff(
        envelope,
        operation="read",
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        pipeline=pipeline,
        pipeline_id="pipe",
        consumer_step="review",
        consumer_port="result",
        producer_port=Port("result", "application/json"),
        consumer_port_decl=PortRef("result", "application/json"),
        configured_mode="enforce",
    )

    assert result.seam.binding_found is True
    assert result.policy.effective_mode == "enforce"
    assert result.decision.classification == StepIOClassification.TYPED_VALID


def test_handoff_contract_result_with_existing_envelope_payload_passes_through_without_double_wrap(
    tmp_path,
) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    payload_version = registry.register("review", _schema())
    inner_envelope = StepIOEnvelope(
        logical_type="review",
        schema_version=payload_version,
        payload={"answer": 7},
    )
    contract = _contract_result(inner_envelope.to_json())

    result = evaluate_step_io_handoff(
        contract,
        operation="read",
        context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef("result", "application/json", logical_type="review"),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.TYPED_VALID
    assert result.decision.envelope == inner_envelope
    assert result.decision.value == {"answer": 7}
    assert result.contract_result == contract
    assert result.contract_result.status is ContractStatus.SUSPENDED
    assert result.contract_result.authority_level == "verified"
    assert result.contract_result.evidence_refs[0].name == "evidence.json"


def test_handoff_contract_result_raw_payload_projects_latest_schema_version_and_preserves_metadata(
    tmp_path,
) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    registry.register("review", _schema(const=6))
    latest_version = registry.register("review", _schema())
    contract = _contract_result({"answer": 7}, schema_version=CONTRACT_RESULT_SCHEMA_VERSION)

    result = evaluate_step_io_handoff(
        contract,
        operation="write",
        context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
        seam=_typed_seam(),
        producer_port=Port("result", "application/json", logical_type="review"),
        consumer_port_decl=PortRef(
            "result",
            "application/json",
            logical_type="review",
            accepted_version_range=AcceptedVersionRange("review", min_version=latest_version),
        ),
        configured_mode="enforce",
    )

    assert result.decision.classification == StepIOClassification.TYPED_VALID
    assert result.decision.envelope == StepIOEnvelope(
        logical_type="review",
        schema_version=latest_version,
        payload={"answer": 7},
    )
    assert result.decision.envelope.schema_version != contract.schema_version
    assert result.decision.value == {"answer": 7}
    assert result.contract_result == contract
    assert result.contract_result.provenance.generator == "scanner@1.2"
    assert result.contract_result.provenance.chain == ("step-a", "step-b")
    assert result.contract_result.freshness.ttl_seconds == 300
