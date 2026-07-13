"""Canonical recovery decision vocabulary shared by producers and consumers.

Unknown evidence is deliberately not a human gate.  It may stop mutation, but
only an allowlisted, structured gate can assert that a person must decide.
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold_pipelines.megaplan.run_state.model import TypedHumanGate


HUMAN_GATE_FIELDS = (
    "gate_type",
    "human_gate",
    "gate",
    "category",
    "gate_kind",
    "kind",
)

HUMAN_GATE_TOKENS: dict[str, TypedHumanGate] = {
    "explicit_approval": TypedHumanGate.EXPLICIT_APPROVAL,
    "approval": TypedHumanGate.EXPLICIT_APPROVAL,
    "approval_needed": TypedHumanGate.EXPLICIT_APPROVAL,
    "credential": TypedHumanGate.CREDENTIAL_ACCOUNT,
    "credentials": TypedHumanGate.CREDENTIAL_ACCOUNT,
    "credential_account": TypedHumanGate.CREDENTIAL_ACCOUNT,
    "account": TypedHumanGate.CREDENTIAL_ACCOUNT,
    "missing_credential": TypedHumanGate.CREDENTIAL_ACCOUNT,
    "destructive_action": TypedHumanGate.DESTRUCTIVE_ACTION,
    "destructive-action": TypedHumanGate.DESTRUCTIVE_ACTION,
    "product_decision": TypedHumanGate.PRODUCT_DECISION,
    "product-decision": TypedHumanGate.PRODUCT_DECISION,
    "verification": TypedHumanGate.VERIFICATION,
    "human_verification": TypedHumanGate.VERIFICATION,
    "policy": TypedHumanGate.POLICY,
    "legal_policy": TypedHumanGate.POLICY,
    "user_action": TypedHumanGate.USER_ACTION,
    "user-action": TypedHumanGate.USER_ACTION,
}

MACHINE_REPAIRABLE_FAILURE_KINDS = frozenset(
    {
        "blocked_recovery_not_resolved",
        "deterministic_quality_blocked",
        "execution_blocked",
        "no_next_step_state_mapping_failure",
        "quality_gate_blocked",
        "route_metadata_mismatch",
        "workflow_cursor_mismatch",
    }
)


def typed_human_gate(payload: Mapping[str, Any] | None) -> TypedHumanGate | None:
    """Return an allowlisted typed human gate from structured evidence only."""

    if not isinstance(payload, Mapping):
        return None
    for field in HUMAN_GATE_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str):
            continue
        gate = HUMAN_GATE_TOKENS.get(value.strip().lower())
        if gate is not None:
            return gate
    return None


def is_machine_repairable_failure_kind(kind: object) -> bool:
    return isinstance(kind, str) and kind.strip().lower() in MACHINE_REPAIRABLE_FAILURE_KINDS


__all__ = [
    "HUMAN_GATE_FIELDS",
    "HUMAN_GATE_TOKENS",
    "MACHINE_REPAIRABLE_FAILURE_KINDS",
    "is_machine_repairable_failure_kind",
    "typed_human_gate",
]
