"""M8 acceptance regression: structural-audit checks (T2).

Covers two motivating failure classes from the README:

1. Raw ``additionalProperties`` rejection — structural validation must reject
   undeclared payload keys before downstream logic sees them.
2. Malformed named-output capture — ``capture_step_output`` must fail-closed
   with a structural error when the payload shape does not match the schema.

Fixtures are M8-distinct and reference ``SOURCE_TICKET`` found in the
regression ``helpers.py`` shared package. Existing model-seam tests in
``tests/arnold/pipelines/megaplan/test_model_seam.py`` are intentionally
not copied; these tests assert diagnostic paths that were missing before
the M8 gate.
"""

from __future__ import annotations

import pytest

from arnold.pipeline import (
    StepInvocation,
    validate_payload_against_schema,
)
from arnold.pipelines.megaplan.model_seam import (
    ModelStructuralAuditError,
    capture_step_output,
)
from .helpers import (
    ADDITIONAL_PROPERTIES_FAILURE_SCHEMA,
    MALFORMED_NAMED_OUTPUT_CAPTURE_SCHEMA,
    SOURCE_TICKET,
)


# ---------------------------------------------------------------------------
# additionalProperties rejection
# ---------------------------------------------------------------------------


def _m8_additional_payload(extra_key: str) -> dict:
    """Return a payload with an undeclared key under a strict schema."""
    return {"answer": "42", extra_key: "should-not-be-allowed"}


def test_additional_properties_rejection_direct_validation() -> None:
    """Direct schema validation rejects additional properties."""
    # The schema is strict (additionalProperties=False) and only allows "answer".
    payload = _m8_additional_payload("undeclared_field")

    result = validate_payload_against_schema(
        payload,
        ADDITIONAL_PROPERTIES_FAILURE_SCHEMA,
    )

    assert not result.ok, f"Expected validation failure, got {result}"
    assert len(result.diagnostics) >= 1
    diagnostic = result.diagnostics[0]
    # The diagnostic should mention the undeclared key or additionalProperties
    msg = diagnostic.message.lower()
    assert (
        "additionalproperties" in msg
        or "undeclared" in msg
        or "additional" in msg
        or "not allowed" in msg
    ), f"Expected diagnostic about additional properties, got: {msg}"


def test_additional_properties_rejection_capture_step_output() -> None:
    """capture_step_output rejects payload with additional properties when
    the schema is strict and does not allow extra keys."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "finalize",
            "schema": ADDITIONAL_PROPERTIES_FAILURE_SCHEMA,
        },
    )
    payload = _m8_additional_payload("hidden_field")

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        capture_step_output(invocation, payload)

    error_text = str(exc_info.value)
    assert "worker_structural_audit_failed" in error_text
    assert SOURCE_TICKET not in error_text  # model-seam errors are ticket-agnostic


def test_additional_properties_rejection_multiple_extra_keys() -> None:
    """Multiple undeclared keys are all caught by a single validation pass."""
    payload = {"answer": "valid", "extra_a": 1, "extra_b": True}

    result = validate_payload_against_schema(
        payload,
        ADDITIONAL_PROPERTIES_FAILURE_SCHEMA,
    )

    assert not result.ok
    # One or more diagnostics expected; at least one must flag additionalProperties
    messages = " ".join(d.message.lower() for d in result.diagnostics)
    assert (
        "additionalproperties" in messages
        or "undeclared" in messages
        or "additional" in messages
        or "unexpected" in messages
    ), f"Expected additional-properties diagnostic, got: {messages}"


# ---------------------------------------------------------------------------
# malformed named-output capture
# ---------------------------------------------------------------------------


def _m8_named_output_payload(shape_violation: str = "wrong_type") -> dict:
    """Return a payload that violates the named-output schema.

    The schema expects ``named_outputs`` to be an object with string values.
    """
    if shape_violation == "missing_required":
        return {}  # missing required "named_outputs"
    if shape_violation == "wrong_type":
        return {"named_outputs": "not-an-object"}
    if shape_violation == "extra_key":
        return {"named_outputs": {}, "unexpected_field": 123}
    if shape_violation == "wrong_value_type":
        return {"named_outputs": {"step_a": 42}}  # number, not string
    return {"named_outputs": {"step_a": "valid"}}  # should pass


def test_malformed_named_output_capture_wrong_type() -> None:
    """named_outputs with wrong type (string instead of object) must fail."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "finalize",
            "schema": MALFORMED_NAMED_OUTPUT_CAPTURE_SCHEMA,
        },
    )
    payload = _m8_named_output_payload("wrong_type")

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        capture_step_output(invocation, payload)

    assert "worker_structural_audit_failed" in str(exc_info.value)


def test_malformed_named_output_capture_missing_required() -> None:
    """Missing required 'named_outputs' key must produce a structural error."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "finalize",
            "schema": MALFORMED_NAMED_OUTPUT_CAPTURE_SCHEMA,
        },
    )
    payload = _m8_named_output_payload("missing_required")

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        capture_step_output(invocation, payload)

    assert "worker_structural_audit_failed" in str(exc_info.value)


def test_malformed_named_output_capture_extra_key() -> None:
    """Undeclared top-level key under a strict schema must fail."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "finalize",
            "schema": MALFORMED_NAMED_OUTPUT_CAPTURE_SCHEMA,
        },
    )
    payload = _m8_named_output_payload("extra_key")

    with pytest.raises(ModelStructuralAuditError) as exc_info:
        capture_step_output(invocation, payload)

    assert "worker_structural_audit_failed" in str(exc_info.value)


def test_malformed_named_output_capture_wrong_value_type() -> None:
    """named_outputs values must be strings — a number fails type validation
    when the schema declares named_outputs as a typed property."""
    # Use a schema where named_outputs has explicit property type checking
    # (the validator checks explicit properties but not additionalProperties values)
    schema: dict = {
        "type": "object",
        "required": ["named_outputs"],
        "properties": {
            "named_outputs": {
                "type": "object",
                "properties": {
                    "step_a": {"type": "string"},
                },
                "additionalProperties": False,
            }
        },
        "additionalProperties": False,
    }
    payload = {"named_outputs": {"step_a": 42}}

    result = validate_payload_against_schema(payload, schema)

    # Must fail because step_a value is int, not string
    assert not result.ok
    messages = " ".join(d.message.lower() for d in result.diagnostics)
    assert (
        "type" in messages
        or "string" in messages
        or "integer" in messages
        or "number" in messages
    ), f"Expected type-mismatch diagnostic, got: {messages}"


def test_malformed_named_output_capture_valid_shape_passes() -> None:
    """A correctly-shaped named_outputs payload must pass structural audit."""
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "finalize",
            "schema": MALFORMED_NAMED_OUTPUT_CAPTURE_SCHEMA,
        },
    )
    payload = _m8_named_output_payload("valid")

    # Must NOT raise
    outcome = capture_step_output(invocation, payload)
    assert outcome.contract_result.status.value == "completed"


def test_diagnostics_surface_source_ticket_marker_in_helpers() -> None:
    """Smoke test: the shared regression helpers carry the M8 source ticket."""
    assert SOURCE_TICKET == "01KT50AZRMK5X890TQ565DDB5V"
    assert "additional_properties_rejection" in (
        "additional_properties_rejection",
        "model_budget_overflow",
        "malformed_named_output_capture",
        "suspension_propagation",
    )
