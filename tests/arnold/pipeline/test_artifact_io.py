from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipeline.artifact_io import (
    ArtifactIOBlocked,
    ArtifactIOResult,
    validate_artifact_io,
    validate_large_artifact_by_manifest,
)
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOOperation,
)
from arnold.pipeline.step_io_policy import CONTRACT_MODE_ENFORCE, resolve_step_io_policy


def _registry(tmp_path: Path) -> ContractSchemaRegistry:
    registry = ContractSchemaRegistry(tmp_path)
    registry.register(
        "answer",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return registry


def _envelope(registry: ContractSchemaRegistry, value) -> dict:
    return {
        "logical_type": "answer",
        "schema_version": registry.latest("answer"),
        "payload": {"value": value},
    }


def test_valid_typed_write_passes(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    policy = resolve_step_io_policy(
        configured_mode=CONTRACT_MODE_ENFORCE,
        producer_typed=True,
        consumer_typed=True,
    )

    result = validate_artifact_io(
        _envelope(registry, 42),
        operation=StepIOOperation.WRITE,
        policy=policy,
        contract_context=StepIOContractContext(
            operation=StepIOOperation.WRITE,
            registry=registry,
        ),
    )

    assert result.classification == StepIOClassification.TYPED_VALID
    assert result.value == {"value": 42}
    assert not result.blocked


def test_invalid_typed_write_blocks_under_enforce(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    policy = resolve_step_io_policy(
        configured_mode=CONTRACT_MODE_ENFORCE,
        producer_typed=True,
        consumer_typed=True,
    )

    with pytest.raises(ArtifactIOBlocked) as exc_info:
        validate_artifact_io(
            _envelope(registry, "oops"),
            operation=StepIOOperation.WRITE,
            policy=policy,
            contract_context=StepIOContractContext(
                operation=StepIOOperation.WRITE,
                registry=registry,
            ),
        )

    exc = exc_info.value
    assert exc.result is not None
    assert exc.decision is exc.result.decision
    assert exc.result.blocked is True


def test_invalid_typed_write_does_not_block_when_policy_downgrades(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    policy = resolve_step_io_policy(
        configured_mode=CONTRACT_MODE_ENFORCE,
        producer_typed=True,
        consumer_typed=False,
    )
    telemetry_path = tmp_path / "telemetry.jsonl"

    result = validate_artifact_io(
        _envelope(registry, "oops"),
        operation=StepIOOperation.WRITE,
        policy=policy,
        contract_context=StepIOContractContext(
            operation=StepIOOperation.WRITE,
            registry=registry,
        ),
        telemetry_path=telemetry_path,
    )

    assert isinstance(result, ArtifactIOResult)
    assert result.policy.effective_mode == "shadow"
    assert not result.blocked
    assert result.telemetry_record is not None
    assert telemetry_path.exists()


def test_legacy_values_pass_through_unchanged(tmp_path: Path) -> None:
    policy = resolve_step_io_policy(
        configured_mode=CONTRACT_MODE_ENFORCE,
        producer_typed=False,
        consumer_typed=False,
    )
    legacy = {"result": "raw"}

    result = validate_artifact_io(
        legacy,
        operation=StepIOOperation.READ,
        policy=policy,
    )

    assert result.classification == StepIOClassification.LEGACY_UNKNOWN
    assert result.value is legacy
    assert not result.blocked


def test_large_artifact_manifest_validation_blocks_missing_manifest(tmp_path: Path) -> None:
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"x" * 16)

    with pytest.raises(ArtifactIOBlocked):
        validate_large_artifact_by_manifest(blob, expected_schema_hash="sha256:h")
