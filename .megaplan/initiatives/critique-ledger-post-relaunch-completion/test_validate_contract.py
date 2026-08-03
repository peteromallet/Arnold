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


def test_chain_parses_through_installed_schema() -> None:
    parsed = contract.load_spec(Path(__file__).with_name("chain.yaml"))
    assert parsed.milestones[0].label == "f0-finite-canary-handoff-admission"
    assert parsed.milestones[1].depends_on == ["f0-finite-canary-handoff-admission"]
    assert {item.kind for item in parsed.launch_preconditions} == {"exists", "git_tracked"}


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


def test_global_marker_cannot_be_made_transaction_bound() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    marker = custody["trusted_host_control_state_contract"]["global_containment_marker"]
    marker["exact_fields"] = [
        "schema", "profile", "scope", "active", "transaction_id",
    ]
    marker["transaction_independent"] = False
    with pytest.raises(contract.ContractError, match="global containment marker"):
        contract._validate_host_control_state_contract(custody)


def test_failure_evidence_cannot_claim_pre_intent_host_durability() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["trusted_host_control_state_contract"]["failure_evidence"]["pre_intent"] = (
        "DURABLE_HOST_RECEIPT"
    )
    with pytest.raises(contract.ContractError, match="failure evidence authority split"):
        contract._validate_host_control_state_contract(custody)


def test_invented_global_marker_schema_is_rejected() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    marker = custody["trusted_host_control_state_contract"]["global_containment_marker"]
    marker["schema"] = "arnold.cloud.zero_recovery_global_containment_marker.v2"
    with pytest.raises(contract.ContractError, match="global containment marker"):
        contract._validate_host_control_state_contract(custody)


def test_known_failed_attempt_cannot_be_relabelled_accepted() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["prelaunch_attempts"][4]["status"] = "ACCEPTED"
    with pytest.raises(contract.ContractError, match="known attempt history drift"):
        contract._validate_attempt_history(custody)


def test_b26_pass_cannot_drift_into_unreviewed_acceptance() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    b26 = custody["prelaunch_attempts"][-1]
    b26["status"] = "PASSED_EXIT_0_INDEPENDENTLY_ACCEPTED_NOT_LIVE_CANARY"
    with pytest.raises(contract.ContractError, match="B26 passing smoke binding drift"):
        contract._validate_attempt_history(custody)


def test_pending_operation_cannot_fabricate_terminal_receipt() -> None:
    manifest_path = Path(__file__).with_name("evidence") / "operation-reconciliation-manifest.json"
    manifest = contract._load_json(manifest_path)
    row = manifest["operations"][0]
    row["terminal"] = {
        "path": "forged.json",
        "sha256": "a" * 64,
        "status": "PENDING_RECONCILIATION",
        "dispatch_counts": None,
    }
    original_loader = contract._load_json

    def load_with_mutation(path: Path):
        if path == manifest_path:
            return manifest
        return original_loader(path)

    contract._load_json = load_with_mutation
    try:
        with pytest.raises(contract.ContractError, match="fabricates terminal evidence"):
            contract._validate_operation_reconciliation(require_live=False)
    finally:
        contract._load_json = original_loader
