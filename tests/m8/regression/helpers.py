"""Shared payload schemas and assertions for M8 acceptance regressions."""

from __future__ import annotations

from typing import Any, Mapping

from arnold.pipeline import CONTRACT_RESULT_SCHEMA_VERSION, ContractResult, ContractStatus, Suspension

SOURCE_TICKET = "01KT50AZRMK5X890TQ565DDB5V"

FAILURE_CLASSES: tuple[str, ...] = (
    "additional_properties_rejection",
    "model_budget_overflow",
    "malformed_named_output_capture",
    "suspension_propagation",
)

ADDITIONAL_PROPERTIES_FAILURE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
    "additionalProperties": False,
}

MALFORMED_NAMED_OUTPUT_CAPTURE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["named_outputs"],
    "properties": {
        "named_outputs": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        }
    },
    "additionalProperties": False,
}

BUDGET_OVERFLOW_PAYLOAD: dict[str, Any] = {
    "failure_class": "model_budget_overflow",
    "ticket": SOURCE_TICKET,
    "error_kind": "budget_exceeded",
}

SUSPENSION_PROPAGATION_PAYLOAD: dict[str, Any] = {
    "failure_class": "suspension_propagation",
    "ticket": SOURCE_TICKET,
    "status_lattice": "completed<suspended<failed",
}


def make_contract_result(
    *,
    status: ContractStatus = ContractStatus.COMPLETED,
    payload: Mapping[str, Any] | None = None,
    suspension: Suspension | None = None,
    authority_level: str = "verified",
) -> ContractResult:
    """Return a deterministic ContractResult for M8 regression tests."""

    return ContractResult(
        payload=dict(payload or {}),
        status=status,
        schema_version=CONTRACT_RESULT_SCHEMA_VERSION,
        suspension=suspension,
        authority_level=authority_level,
    )


def make_budget_overflow_contract(message: str) -> ContractResult:
    payload = dict(BUDGET_OVERFLOW_PAYLOAD)
    payload["message"] = message
    return make_contract_result(status=ContractStatus.FAILED, payload=payload)


def make_suspended_contract(
    *,
    awaitable: str = "human_review/m8",
    prompt: str = "Awaiting M8 acceptance review",
    payload: Mapping[str, Any] | None = None,
) -> ContractResult:
    suspension = Suspension(kind="human", awaitable=awaitable, prompt=prompt)
    merged_payload = dict(SUSPENSION_PROPAGATION_PAYLOAD)
    if payload:
        merged_payload.update(payload)
    return make_contract_result(
        status=ContractStatus.SUSPENDED,
        payload=merged_payload,
        suspension=suspension,
    )


def assert_contract_status(result: ContractResult, expected: ContractStatus) -> None:
    assert result.status is expected


def assert_payload_contains(result: ContractResult, expected: Mapping[str, Any]) -> None:
    for key, value in expected.items():
        assert result.payload.get(key) == value


def assert_suspension_propagated(result: ContractResult) -> None:
    assert_contract_status(result, ContractStatus.SUSPENDED)
    assert result.suspension is not None
    assert_payload_contains(result, SUSPENSION_PROPAGATION_PAYLOAD)
