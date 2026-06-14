from __future__ import annotations

import pytest

from arnold.pipeline import StepInvocation, StepInvocationAdapterRegistry
from arnold.pipeline.model_seam import (
    AuditStatus,
    BudgetStatus,
    ModelBudgetError,
    ModelStructuralAuditError,
    ModelTier,
    TerminalStatus,
    capture_step_output,
    classify_model_family,
    install_model_step_adapter,
    register_capture_schema_resolver,
    register_compatibility_projection,
    register_native_normalizer,
    render_step_message,
)


def test_render_step_message_budgets_and_exposes_worker_payload() -> None:
    invocation = StepInvocation.model(
        metadata={
            "tier": "non_enforced",
            "worker": "shannon",
            "model": "claude-sonnet",
            "prompt": "Write a short summary.",
            "schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
            },
        }
    )

    rendered = render_step_message(invocation)

    assert rendered.text == "Write a short summary."
    assert rendered.prompt == "Write a short summary."
    assert rendered.schema == {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
    }
    assert rendered.budget is not None
    assert rendered.budget.budget_result in {
        BudgetStatus.WITHIN_BUDGET,
        BudgetStatus.DEGRADED_FALLBACK,
    }
    assert rendered.telemetry.terminal_status is TerminalStatus.RENDERED


def test_render_step_message_enforced_unknown_family_fails_closed() -> None:
    invocation = StepInvocation.model(
        metadata={
            "tier": "enforced",
            "model": "unknown-model-family",
            "prompt": "hello",
        }
    )

    with pytest.raises(ModelBudgetError, match="unknown normalized model family"):
        render_step_message(invocation)


def test_install_model_step_adapter_replaces_reserved_placeholder() -> None:
    registry = StepInvocationAdapterRegistry()
    install_model_step_adapter(registry)

    result = registry.invoke(
        StepInvocation.model(
            metadata={
                "tier": "non_enforced",
                "model": "claude-sonnet",
                "prompt": "hello",
            }
        )
    )

    assert result.text == "hello"


def test_capture_step_output_preserves_payload_and_typed_contract() -> None:
    invocation = StepInvocation.model(
        metadata={
            "tier": "non_enforced",
            "model": "claude-sonnet",
            "capture_schema": {
                "type": "object",
                "required": ["output"],
                "properties": {"output": {"type": "string"}},
                "additionalProperties": False,
            },
        }
    )

    outcome = capture_step_output(invocation, {"output": "ok"})

    assert outcome.legacy_payload == {"output": "ok"}
    assert outcome.telemetry.audit_result is AuditStatus.PASSED
    assert outcome.contract_result.payload["legacy_payload"] == {"output": "ok"}


def test_capture_step_output_rejects_invalid_enforced_payload() -> None:
    invocation = StepInvocation.model(
        metadata={
            "tier": "enforced",
            "model": "claude-sonnet",
            "capture_schema": {
                "type": "object",
                "required": ["output"],
                "properties": {"output": {"type": "string"}},
                "additionalProperties": False,
            },
        }
    )

    with pytest.raises(ModelStructuralAuditError):
        capture_step_output(invocation, {"wrong": "shape"})


def test_capture_step_output_uses_registered_hooks() -> None:
    step = "neutral_test_hook"
    register_native_normalizer(
        step,
        lambda payload: (
            payload
            if "projected" in payload
            else {"normalized": str(payload["raw"]).upper()}
        ),
    )
    register_compatibility_projection(
        step,
        lambda _invocation, payload: {"projected": payload["normalized"]},
    )
    register_capture_schema_resolver(
        lambda invocation: (
            {
                "type": "object",
                "required": ["projected"],
                "properties": {"projected": {"type": "string"}},
                "additionalProperties": False,
            }
            if invocation.metadata.get("validation_step") == step
            else None
        )
    )
    invocation = StepInvocation.model(
        metadata={
            "tier": "non_enforced",
            "model": "claude-sonnet",
            "validation_step": step,
        }
    )

    outcome = capture_step_output(invocation, {"raw": "ok"})

    assert outcome.legacy_payload == {"projected": "OK"}
    assert outcome.telemetry.audit_result is AuditStatus.PASSED


def test_classify_model_family_rejects_provider_prefixed_model_names() -> None:
    with pytest.raises(ModelBudgetError, match="provider-prefixed"):
        classify_model_family("anthropic/claude-sonnet")
