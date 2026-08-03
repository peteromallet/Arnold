from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("validate_contract.py")
SPEC = importlib.util.spec_from_file_location("critique_ledger_follow_up_contract", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract)


def test_static_follow_up_contract_is_exact() -> None:
    contract.validate()


def test_deferred_obligation_drift_is_rejected() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["deferred_obligations"][0]["required_claim_id"] = "forged"
    with pytest.raises(contract.ContractError, match="invalid deferred obligation"):
        contract._validate_obligations(custody)


def test_pending_prelaunch_evidence_cannot_be_fabricated() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["prelaunch_release_gates"][0]["evidence"] = {
        "path": "forged.json",
        "sha256": "a" * 64,
        "status": "PENDING",
    }
    with pytest.raises(contract.ContractError, match="fabricated evidence"):
        contract._validate_prelaunch_gates(custody, require_live=False)


def test_live_validation_rejects_every_pending_gate() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    with pytest.raises(contract.ContractError, match="live gate is not accepted"):
        contract._validate_prelaunch_gates(custody, require_live=True)
