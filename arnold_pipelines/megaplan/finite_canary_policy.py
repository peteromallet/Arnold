"""Closed policy contract for the bounded zero-recovery finite canary."""

from __future__ import annotations

from typing import Any


DIRECT_SUCCESS_ROUTE = ["init", "plan", "critique", "gate", "finalize"]
ONE_REVISION_SUCCESS_ROUTE = [
    "init",
    "plan",
    "critique",
    "gate",
    "revise",
    "critique",
    "gate",
    "finalize",
]
ALLOWED_SUCCESS_ROUTES = [DIRECT_SUCCESS_ROUTE, ONE_REVISION_SUCCESS_ROUTE]


def finite_canary_policy_is_exact(value: Any) -> bool:
    """Accept only the one bounded product-gate policy declared by A40."""
    return bool(
        isinstance(value, dict)
        and set(value)
        == {
            "allowed_success_routes",
            "max_revise_cycles",
            "max_gate_attempts",
            "finalize_requires",
        }
        and value.get("allowed_success_routes") == ALLOWED_SUCCESS_ROUTES
        and type(value.get("max_revise_cycles")) is int
        and value.get("max_revise_cycles") == 1
        and type(value.get("max_gate_attempts")) is int
        and value.get("max_gate_attempts") == 2
        and value.get("finalize_requires") == "PROCEED"
    )


def finite_canary_policy_allows_route(value: Any, phases: Any) -> bool:
    """Accept a completed route only when the exact manifest policy names it."""
    return bool(
        finite_canary_policy_is_exact(value)
        and isinstance(phases, list)
        and phases in value["allowed_success_routes"]
    )
