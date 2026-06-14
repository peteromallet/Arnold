"""T3 (C4): Confirm the gradual-typing policy decision point and exercise
the three enforcement scenarios via real ``validate_artifact_io``.

Audit: ``step_io_policy.py:78`` (``is_step_io_enforcement_eligible``) and
``step_io_policy.py:88`` (``resolve_step_io_policy``) are the single
decision point that downgrades ``enforce``/``warn`` to ``shadow`` when not
both-sides-typed.  ``artifact_io.validate_artifact_io`` is the C1 chokepoint
composed from those primitives.  No restructuring of ``step_io_policy.py``
is performed — this file adds tests only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from arnold.pipeline.artifact_io import (
    ArtifactIOBlocked,
    ArtifactIOResult,
    validate_artifact_io,
    validate_large_artifact_by_manifest,
)
from arnold.pipeline.artifacts import LARGE_ARTIFACT_THRESHOLD_BYTES, write_versioned
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOContractDecision,
    StepIOOperation,
)
from arnold.pipeline.step_io_policy import (
    CONTRACT_MODE_ENFORCE,
    CONTRACT_MODE_SHADOW,
    resolve_step_io_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _Ctx:
    artifact_root: str


def _registry(tmp_path) -> ContractSchemaRegistry:
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


def _valid_envelope(registry: ContractSchemaRegistry) -> dict:
    version = registry.register(
        "answer",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return {"logical_type": "answer", "schema_version": version, "payload": {"value": 42}}


def _invalid_envelope(registry: ContractSchemaRegistry) -> dict:
    version = registry.register(
        "answer",
        {
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    return {"logical_type": "answer", "schema_version": version, "payload": {"value": "oops"}}


# ---------------------------------------------------------------------------
# Scenario A — fully-typed pipeline enforces and rejects wrong-typed payload
# ---------------------------------------------------------------------------


class TestFullyTypedEnforce:
    """Both-sides typed + enforce mode: a wrong-typed write raises ArtifactIOBlocked."""

    def test_valid_typed_write_passes(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _valid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        result = validate_artifact_io(
            envelope,
            operation=StepIOOperation.WRITE,
            policy=policy,
            contract_context=ctx,
        )
        assert not result.blocked
        assert result.classification == StepIOClassification.TYPED_VALID

    def test_invalid_typed_write_raises_blocked(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _invalid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        with pytest.raises(ArtifactIOBlocked):
            validate_artifact_io(
                envelope,
                operation=StepIOOperation.WRITE,
                policy=policy,
                contract_context=ctx,
            )


# ---------------------------------------------------------------------------
# Scenario B — one-untyped-consumer pipeline downgrades to shadow
# ---------------------------------------------------------------------------


class TestOneUntypedConsumerDowngradesToShadow:
    """producer_typed=True, consumer_typed=False → effective_mode=shadow.

    In shadow mode even a wrong-typed envelope must NOT raise or block.
    A telemetry record IS written when telemetry_path is supplied.
    """

    def test_policy_downgrades_to_shadow(self) -> None:
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=False,
        )
        assert policy.effective_mode == CONTRACT_MODE_SHADOW
        assert not policy.enforces

    def test_invalid_write_does_not_raise_under_shadow(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _invalid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=False,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        # must not raise
        result = validate_artifact_io(
            envelope,
            operation=StepIOOperation.WRITE,
            policy=policy,
            contract_context=ctx,
            telemetry_path=tmp_path / "telemetry.jsonl",
        )
        assert isinstance(result, ArtifactIOResult)
        assert not result.blocked

    def test_telemetry_emitted_for_violation_under_shadow(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _invalid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=False,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        telemetry_path = tmp_path / "telemetry.jsonl"
        result = validate_artifact_io(
            envelope,
            operation=StepIOOperation.WRITE,
            policy=policy,
            contract_context=ctx,
            telemetry_path=telemetry_path,
        )
        assert result.telemetry_record is not None


# ---------------------------------------------------------------------------
# Scenario C — entirely un-migrated legacy pipeline runs unchanged
# ---------------------------------------------------------------------------


class TestLegacyPipelinePassesThrough:
    """Non-envelope values (legacy / untyped) always return LEGACY_UNKNOWN unchanged."""

    def test_plain_dict_passes_through(self, tmp_path) -> None:
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=False,
            consumer_typed=False,
        )
        legacy_value = {"result": "some_string", "score": 1}
        result = validate_artifact_io(
            legacy_value,
            operation=StepIOOperation.WRITE,
            policy=policy,
        )
        assert result.classification == StepIOClassification.LEGACY_UNKNOWN
        assert result.value is legacy_value
        assert not result.blocked

    def test_string_value_passes_through(self, tmp_path) -> None:
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=False,
            consumer_typed=False,
        )
        result = validate_artifact_io(
            "raw legacy string",
            operation=StepIOOperation.READ,
            policy=policy,
        )
        assert result.classification == StepIOClassification.LEGACY_UNKNOWN
        assert result.value == "raw legacy string"
        assert not result.blocked


# ---------------------------------------------------------------------------
# T7 — enforce-mode READ carrier recovery and legacy carrier tolerance
# ---------------------------------------------------------------------------


class TestEnforceReadCarrierRecovery:
    """Prove callers can recover ``StepIOContractDecision`` from an
    enforce-mode READ ``ArtifactIOBlocked``, and that the carrier fields
    match the result's own decision reference."""

    def test_invalid_read_raises_blocked_with_carriers(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _invalid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        with pytest.raises(ArtifactIOBlocked) as exc_info:
            validate_artifact_io(
                envelope,
                operation=StepIOOperation.READ,
                policy=policy,
                contract_context=ctx,
            )
        exc = exc_info.value
        # carriers are populated by the enforced raise site
        assert exc.result is not None
        assert exc.decision is not None
        assert isinstance(exc.result, ArtifactIOResult)
        assert isinstance(exc.decision, StepIOContractDecision)
        # result.decision is the exact same object as exc.decision
        assert exc.result.decision is exc.decision

    def test_carrier_decision_is_classified_invalid(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _invalid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        with pytest.raises(ArtifactIOBlocked) as exc_info:
            validate_artifact_io(
                envelope,
                operation=StepIOOperation.READ,
                policy=policy,
                contract_context=ctx,
            )
        decision = exc_info.value.decision
        assert decision.classification == StepIOClassification.TYPED_INVALID
        assert decision.block_reason != ""
        assert len(decision.diagnostics) > 0

    def test_carrier_result_reflects_blocked_state(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _invalid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        with pytest.raises(ArtifactIOBlocked) as exc_info:
            validate_artifact_io(
                envelope,
                operation=StepIOOperation.READ,
                policy=policy,
                contract_context=ctx,
            )
        result = exc_info.value.result
        assert result.blocked is True
        assert result.block_reason != ""
        assert result.classification == StepIOClassification.TYPED_INVALID

    def test_valid_read_does_not_raise(self, tmp_path) -> None:
        registry = _registry(tmp_path)
        envelope = _valid_envelope(registry)
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
        result = validate_artifact_io(
            envelope,
            operation=StepIOOperation.READ,
            policy=policy,
            contract_context=ctx,
        )
        assert not result.blocked
        assert result.classification == StepIOClassification.TYPED_VALID


class TestLegacyRaiseCarrierTolerance:
    """Confirm that ``ArtifactIOBlocked`` raises from other sites
    (e.g. ``validate_large_artifact_by_manifest``) without carriers remain
    safe — ``result`` and ``decision`` are ``None`` and the message string
    is still accessible."""

    def test_missing_manifest_raise_has_no_carriers(self, tmp_path) -> None:
        blob = tmp_path / "v1.bin"
        blob.write_bytes(b"x" * 16)
        with pytest.raises(ArtifactIOBlocked) as exc_info:
            validate_large_artifact_by_manifest(
                blob, expected_schema_hash="sha256:h"
            )
        exc = exc_info.value
        assert exc.result is None
        assert exc.decision is None
        assert isinstance(exc.args[0], str)
        assert "missing sidecar" in exc.args[0].lower() or str(blob) in exc.args[0]

    def test_schema_hash_mismatch_raise_has_no_carriers(self, tmp_path) -> None:
        big = "y" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 16)
        dest = write_versioned(
            _Ctx(artifact_root=str(tmp_path)),
            "s", "l", big, "txt",
            content_type="text/plain", schema_hash="sha256:A",
        )
        with pytest.raises(ArtifactIOBlocked) as exc_info:
            validate_large_artifact_by_manifest(
                dest, expected_schema_hash="sha256:B"
            )
        exc = exc_info.value
        assert exc.result is None
        assert exc.decision is None
        assert "schema_hash mismatch" in exc.args[0].lower()

    def test_carrier_less_raise_still_behaves_as_value_error(self, tmp_path) -> None:
        blob = tmp_path / "v1.bin"
        blob.write_bytes(b"x" * 16)
        with pytest.raises(ValueError) as exc_info:
            validate_large_artifact_by_manifest(
                blob, expected_schema_hash="sha256:h"
            )
        # Must be catchable as ValueError (the super class)
        assert isinstance(exc_info.value, ArtifactIOBlocked)
        assert exc_info.value.result is None
        assert exc_info.value.decision is None
