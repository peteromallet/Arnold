from __future__ import annotations

import importlib
import sys


def test_ir_contract_codes_and_helpers_are_stable() -> None:
    from vibecomfy.contracts.ir import (
        HELPER_EDGE_REWIRED_OR_REPORTED,
        IR_CONTRACT_ANCHORS,
        IR_CONTRACT_CODES,
        IR_CONTRACT_SHAPE,
        IR_CONTRACT_VERSION,
        PUBLIC_INPUT_UNREGISTERED,
        VALIDATION_OK_COMPILES_API,
        VALIDATION_REPORT_OK_FIELD,
        ir_contract_codes,
        is_ir_contract_code,
        require_ir_contract_code,
    )

    assert IR_CONTRACT_VERSION == "vibecomfy.ir_contract.v2.8.0"
    assert IR_CONTRACT_SHAPE == "ir_contract.v1"
    assert IR_CONTRACT_CODES == (
        "ir.public_input.unregistered",
        "ir.public_input.stale_target",
        "ir.validation.report_ok_field",
        "ir.validation.ok_implies_compile_api",
        "ir.compile.edge_endpoint_resolved",
        "ir.compile.helper_edge_rewired_or_reported",
    )
    assert ir_contract_codes() == IR_CONTRACT_CODES
    assert is_ir_contract_code(PUBLIC_INPUT_UNREGISTERED)
    assert require_ir_contract_code(VALIDATION_OK_COMPILES_API) == VALIDATION_OK_COMPILES_API
    assert HELPER_EDGE_REWIRED_OR_REPORTED in {anchor.code for anchor in IR_CONTRACT_ANCHORS}
    assert any(
        anchor.code == VALIDATION_REPORT_OK_FIELD and "report.ok" in anchor.migration_hint
        for anchor in IR_CONTRACT_ANCHORS
    )
    assert not is_ir_contract_code("ir.validation.legacy_alias")


def test_unknown_ir_contract_code_raises_value_error() -> None:
    from vibecomfy.contracts.ir import require_ir_contract_code

    try:
        require_ir_contract_code("ir.validation.legacy_alias")
    except ValueError as exc:
        assert "unknown IR contract code" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("expected ValueError")


def test_contracts_package_lazily_exposes_ir_contract_symbols() -> None:
    for module_name in (
        "vibecomfy.contracts",
        "vibecomfy.contracts.ir",
        "vibecomfy.contracts.model",
    ):
        sys.modules.pop(module_name, None)

    contracts = importlib.import_module("vibecomfy.contracts")
    assert "vibecomfy.contracts.ir" not in sys.modules
    assert "vibecomfy.contracts.model" not in sys.modules

    assert contracts.IR_CONTRACT_VERSION == "vibecomfy.ir_contract.v2.8.0"
    assert "vibecomfy.contracts.ir" in sys.modules
    assert "vibecomfy.contracts.model" not in sys.modules
    assert "VALIDATION_REPORT_OK_FIELD" in contracts.__all__
    assert not hasattr(contracts, "ValidationReportLegacyAlias")
