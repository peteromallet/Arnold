from __future__ import annotations

from dataclasses import dataclass
from typing import Final


IR_CONTRACT_VERSION: Final[str] = "vibecomfy.ir_contract.v2.8.0"
IR_CONTRACT_SHAPE: Final[str] = "ir_contract.v1"

PUBLIC_INPUT_UNREGISTERED: Final[str] = "ir.public_input.unregistered"
PUBLIC_INPUT_STALE_TARGET: Final[str] = "ir.public_input.stale_target"
VALIDATION_REPORT_OK_FIELD: Final[str] = "ir.validation.report_ok_field"
VALIDATION_OK_COMPILES_API: Final[str] = "ir.validation.ok_implies_compile_api"
COMPILED_EDGE_ENDPOINT_RESOLVED: Final[str] = "ir.compile.edge_endpoint_resolved"
HELPER_EDGE_REWIRED_OR_REPORTED: Final[str] = "ir.compile.helper_edge_rewired_or_reported"

IR_CONTRACT_CODES: Final[tuple[str, ...]] = (
    PUBLIC_INPUT_UNREGISTERED,
    PUBLIC_INPUT_STALE_TARGET,
    VALIDATION_REPORT_OK_FIELD,
    VALIDATION_OK_COMPILES_API,
    COMPILED_EDGE_ENDPOINT_RESOLVED,
    HELPER_EDGE_REWIRED_OR_REPORTED,
)


@dataclass(frozen=True, slots=True)
class IRContractAnchor:
    """Stable public identifier for one IR guarantee."""

    code: str
    guarantee: str
    migration_hint: str


IR_CONTRACT_ANCHORS: Final[tuple[IRContractAnchor, ...]] = (
    IRContractAnchor(
        code=PUBLIC_INPUT_UNREGISTERED,
        guarantee="set_input(name, value) only mutates registered public inputs.",
        migration_hint=(
            "Declare public inputs with register_input(), bind_input(), "
            "or InputSpec before calling set_input()."
        ),
    ),
    IRContractAnchor(
        code=PUBLIC_INPUT_STALE_TARGET,
        guarantee="set_input(name, value) rejects public inputs whose node or field target is stale.",
        migration_hint="After replacing a node or field, re-register the public input before setting it.",
    ),
    IRContractAnchor(
        code=VALIDATION_REPORT_OK_FIELD,
        guarantee="ValidationReport exposes its pass/fail state through report.ok.",
        migration_hint="Use report.ok; do not depend on a legacy alias.",
    ),
    IRContractAnchor(
        code=VALIDATION_OK_COMPILES_API,
        guarantee='A workflow with validate().ok must compile with compile("api").',
        migration_hint='Fix compile("api") errors before treating validation as successful.',
    ),
    IRContractAnchor(
        code=COMPILED_EDGE_ENDPOINT_RESOLVED,
        guarantee="Every compiled edge endpoint resolves to a node present in the compiled prompt.",
        migration_hint="Repair dangling or helper-stripped edges before queueing the workflow.",
    ),
    IRContractAnchor(
        code=HELPER_EDGE_REWIRED_OR_REPORTED,
        guarantee="Helper/UI-stripped edges are rewired or reported; they are not silently dropped.",
        migration_hint="Run port check and resolve helper diagnostics before promoting a template.",
    ),
)


def ir_contract_codes() -> tuple[str, ...]:
    """Return the stable code set for the public IR contract."""

    return IR_CONTRACT_CODES


def is_ir_contract_code(code: str) -> bool:
    """Return True when *code* is one of the stable public IR contract codes."""

    return code in IR_CONTRACT_CODES


def require_ir_contract_code(code: str) -> str:
    """Validate and return *code*, raising ValueError for unknown IR contract codes."""

    if not is_ir_contract_code(code):
        raise ValueError(f"unknown IR contract code: {code}")
    return code


__all__ = [
    "COMPILED_EDGE_ENDPOINT_RESOLVED",
    "HELPER_EDGE_REWIRED_OR_REPORTED",
    "IR_CONTRACT_ANCHORS",
    "IR_CONTRACT_CODES",
    "IR_CONTRACT_SHAPE",
    "IR_CONTRACT_VERSION",
    "IRContractAnchor",
    "PUBLIC_INPUT_STALE_TARGET",
    "PUBLIC_INPUT_UNREGISTERED",
    "VALIDATION_OK_COMPILES_API",
    "VALIDATION_REPORT_OK_FIELD",
    "ir_contract_codes",
    "is_ir_contract_code",
    "require_ir_contract_code",
]
