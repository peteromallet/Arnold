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


def test_b26_sol_go_cannot_drift() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    b26 = custody["prelaunch_attempts"][-5]
    b26["independent_review"]["decision"] = "NO_GO"
    with pytest.raises(contract.ContractError, match="B26 passing smoke binding drift"):
        contract._validate_attempt_history(custody)


def test_b27_pass_cannot_drift_into_unreviewed_acceptance() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    b27 = custody["prelaunch_attempts"][-4]
    b27["status"] = "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
    with pytest.raises(contract.ContractError, match="B27 passing smoke binding drift"):
        contract._validate_attempt_history(custody)


def test_b28_pass_cannot_drift_into_unreviewed_acceptance() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    b28 = custody["prelaunch_attempts"][-3]
    b28["status"] = "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
    with pytest.raises(contract.ContractError, match="B28 passing smoke binding drift"):
        contract._validate_attempt_history(custody)


def test_b29_pass_cannot_drift_into_unreviewed_acceptance() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    b29 = custody["prelaunch_attempts"][-2]
    b29["status"] = "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
    with pytest.raises(contract.ContractError, match="B29 passing smoke binding drift"):
        contract._validate_attempt_history(custody)


def test_b30_pass_cannot_drift_into_unreviewed_acceptance() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    b30 = custody["prelaunch_attempts"][-1]
    b30["status"] = "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
    with pytest.raises(contract.ContractError, match="B30 passing smoke binding drift"):
        contract._validate_attempt_history(custody)


def test_b34_independent_no_go_cannot_be_erased() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["schema_access_recovery_history"][3]["outcome"]["status"] = "ACCEPTED"
    with pytest.raises(contract.ContractError, match="A31-B36 schema-access recovery history drift"):
        contract._validate_schema_access_recovery_history(custody, require_live=False)


def test_b35_prefix_evidence_cannot_be_promoted_to_full_digest() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["schema_access_recovery_history"][4]["production_acceptance_smoke"]["digest_full"] = "8" * 64
    with pytest.raises(contract.ContractError, match="A31-B36 schema-access recovery history drift"):
        contract._validate_schema_access_recovery_history(custody, require_live=False)


def test_b36_pending_offline_gate_cannot_be_promoted_without_evidence() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["schema_access_recovery_history"][5]["gates"]["offline"] = "ACCEPTED"
    with pytest.raises(contract.ContractError, match="A31-B36 schema-access recovery history drift"):
        contract._validate_schema_access_recovery_history(custody, require_live=False)


def test_failed_live_attempt_cannot_claim_marker_publication() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["live_deploy_attempts"][0]["marker_published"] = True
    with pytest.raises(contract.ContractError, match="failed live deploy transaction binding drift"):
        contract._validate_live_deploy_attempts(custody)


def test_b27_failed_live_attempt_cannot_claim_terminal_dispatch() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["live_canary_attempts"][0]["dispatch_integrity"]["terminal_dispatch_count"] = 1
    with pytest.raises(contract.ContractError, match="B27 live canary terminal binding drift"):
        contract._validate_live_canary_attempts(custody)


def test_b28_failed_live_attempt_cannot_claim_oom() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["live_canary_attempts"][1]["container"]["oom_killed"] = True
    with pytest.raises(contract.ContractError, match="B28 live canary terminal binding drift"):
        contract._validate_live_canary_attempts(custody)


def test_b29_failed_live_attempt_cannot_claim_dac_override() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["live_canary_attempts"][2]["root_evidence"]["trusted_root"]["dac_override"] = True
    with pytest.raises(contract.ContractError, match="B29 live canary terminal binding drift"):
        contract._validate_live_canary_attempts(custody)


def test_b30_failed_live_attempt_cannot_claim_running_container() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["live_canary_attempts"][3]["container"]["stopped"] = False
    with pytest.raises(contract.ContractError, match="B30 live canary terminal binding drift"):
        contract._validate_live_canary_attempts(custody)


def test_b35_status_poll_failure_cannot_be_relabelled_model_failure() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["live_canary_attempts"][4]["classification"] = "MODEL_FAILURE"
    with pytest.raises(contract.ContractError, match="B35 live canary terminal binding drift"):
        contract._validate_live_canary_attempts(custody)


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
