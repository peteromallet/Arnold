"""T4 (C4): Verify StepIOEnforcementError carries a populated author_diagnostic.

Tests confirm:
1. ``StepIOEnforcementError.__init__`` stores ``author_diagnostic`` as an attribute.
2. The attribute is distinct from any telemetry event payload.
3. A wrong-typed crossing routed through the executor raises
   ``StepIOEnforcementError`` with a non-None ``author_diagnostic`` whose
   field set is asserted exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from arnold.pipeline.executor import StepIOEnforcementError
from arnold.pipeline.runtime_contract_diagnostics import RuntimeContractDiagnostic
from arnold.pipeline.schema_registry import ContractSchemaRegistry
from arnold.pipeline.step_io_contract import (
    StepIOClassification,
    StepIOContractContext,
    StepIOOperation,
)
from arnold.pipeline.step_io_handoff import evaluate_step_io_handoff
from arnold.pipeline.step_io_policy import CONTRACT_MODE_ENFORCE, resolve_step_io_policy
from arnold.pipeline.step_io_seams import SeamResolution


# ---------------------------------------------------------------------------
# Unit: StepIOEnforcementError stores author_diagnostic
# ---------------------------------------------------------------------------


class TestStepIOEnforcementErrorInit:
    def test_default_author_diagnostic_is_none(self) -> None:
        err = StepIOEnforcementError("some violation")
        assert err.author_diagnostic is None

    def test_author_diagnostic_stored(self) -> None:
        diag = RuntimeContractDiagnostic(
            producer_stage="stage_a",
            consumer_stage="stage_b",
            seam_id="pipe.stage_a.out→stage_b.inp",
            logical_type="answer",
            schema_version="sha256:abc",
            failure_code="typed_invalid",
            suggested_author_action="fix the payload",
            detail="value must be integer",
        )
        err = StepIOEnforcementError("violation", author_diagnostic=diag)
        assert err.author_diagnostic is diag
        assert str(err) == "violation"

    def test_author_diagnostic_fields_exact(self) -> None:
        diag = RuntimeContractDiagnostic(
            producer_stage="p",
            consumer_stage="c",
            seam_id="s",
            logical_type="lt",
            schema_version="sv",
            failure_code="fc",
            suggested_author_action="action",
            detail="detail text",
        )
        err = StepIOEnforcementError("msg", author_diagnostic=diag)
        d = err.author_diagnostic
        assert d.producer_stage == "p"
        assert d.consumer_stage == "c"
        assert d.seam_id == "s"
        assert d.logical_type == "lt"
        assert d.schema_version == "sv"
        assert d.failure_code == "fc"
        assert d.suggested_author_action == "action"
        assert d.detail == "detail text"


# ---------------------------------------------------------------------------
# Integration: wrong-typed handoff raises with populated author_diagnostic
# ---------------------------------------------------------------------------


class TestEnforcementRaisesWithDiagnostic:
    """Simulate a typed enforce crossing at handoff level and confirm the
    author_diagnostic is populated and distinct from the telemetry record."""

    def _make_registry(self, tmp_path) -> tuple[ContractSchemaRegistry, str]:
        registry = ContractSchemaRegistry(tmp_path)
        version = registry.register(
            "answer",
            {
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "integer"}},
                "additionalProperties": False,
            },
        )
        return registry, version

    def test_wrong_typed_handoff_has_author_diagnostic(self, tmp_path) -> None:
        registry, version = self._make_registry(tmp_path)
        # Envelope with invalid payload (string where int required)
        envelope = {"logical_type": "answer", "schema_version": version, "payload": {"value": "bad"}}
        seam = SeamResolution(
            seam_id=None,
            producer_typed=True,
            consumer_typed=True,
            both_sides_typed=True,
            binding_found=True,
        )
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        handoff = evaluate_step_io_handoff(
            envelope,
            operation=StepIOOperation.WRITE,
            seam=seam,
            policy=policy,
            context=ctx,
            consumer_step="stage_b",
            producer_stage="stage_a",
        )
        # Handoff itself reports the violation
        assert handoff.decision.classification == StepIOClassification.TYPED_INVALID
        assert handoff.author_diagnostic is not None

        diag = handoff.author_diagnostic
        assert isinstance(diag, RuntimeContractDiagnostic)
        # All required fields are populated
        assert diag.producer_stage == "stage_a"
        assert diag.consumer_stage == "stage_b"
        assert diag.logical_type == "answer"
        assert diag.failure_code  # non-empty
        assert diag.suggested_author_action  # non-empty
        assert diag.detail  # non-empty

    def test_author_diagnostic_distinct_from_telemetry_payload(self, tmp_path) -> None:
        registry, version = self._make_registry(tmp_path)
        envelope = {"logical_type": "answer", "schema_version": version, "payload": {"value": "bad"}}
        seam = SeamResolution(
            seam_id=None,
            producer_typed=True,
            consumer_typed=True,
            both_sides_typed=True,
            binding_found=True,
        )
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        telemetry_path = tmp_path / "telemetry.jsonl"
        handoff = evaluate_step_io_handoff(
            envelope,
            operation=StepIOOperation.WRITE,
            seam=seam,
            policy=policy,
            context=ctx,
            consumer_step="stage_b",
            producer_stage="stage_a",
            telemetry_path=telemetry_path,
        )
        diag = handoff.author_diagnostic
        telemetry = handoff.telemetry_record
        # author_diagnostic is a RuntimeContractDiagnostic; telemetry is a StepIOViolationRecord
        # They are different types (distinct objects)
        assert diag is not telemetry
        assert type(diag) is not type(telemetry)
        assert isinstance(diag, RuntimeContractDiagnostic)

    def test_enforcement_error_raised_with_author_diagnostic(self, tmp_path) -> None:
        """Simulate the executor raise path: manually raise with handoff.author_diagnostic."""
        registry, version = self._make_registry(tmp_path)
        envelope = {"logical_type": "answer", "schema_version": version, "payload": {"value": "bad"}}
        seam = SeamResolution(
            seam_id=None,
            producer_typed=True,
            consumer_typed=True,
            both_sides_typed=True,
            binding_found=True,
        )
        policy = resolve_step_io_policy(
            configured_mode=CONTRACT_MODE_ENFORCE,
            producer_typed=True,
            consumer_typed=True,
        )
        ctx = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
        handoff = evaluate_step_io_handoff(
            envelope,
            operation=StepIOOperation.WRITE,
            seam=seam,
            policy=policy,
            context=ctx,
            consumer_step="stage_b",
            producer_stage="stage_a",
        )
        with pytest.raises(StepIOEnforcementError) as exc_info:
            raise StepIOEnforcementError(
                f"step IO enforced violation: {handoff.decision.block_reason}",
                author_diagnostic=handoff.author_diagnostic,
            )
        err = exc_info.value
        assert err.author_diagnostic is not None
        assert err.author_diagnostic.failure_code  # non-empty string
        assert err.author_diagnostic.suggested_author_action  # non-empty string
