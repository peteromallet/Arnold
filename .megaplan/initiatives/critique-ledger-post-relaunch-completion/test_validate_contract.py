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
    assert [item.kind for item in parsed.launch_preconditions] == [
        "finite_canary_receipt",
        "stable_exit_receipt",
        "git_tracked",
        "git_tracked",
    ]


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


def test_immutable_b39_lineage_cannot_promote_terminal_live_gate() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["current_canary_lineage"]["generations"][2]["gates"]["live"] = "ACCEPTED"
    with pytest.raises(contract.ContractError, match="immutable B39 history"):
        contract._validate_current_canary_lineage(custody, require_live=False)


def test_immutable_b39_lineage_preserves_closed_a40_nonproceed_history() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    lineage = custody["current_canary_lineage"]
    lineage["closed_decision"]["status"] = "PENDING"
    with pytest.raises(contract.ContractError, match="closed A40 decision drift"):
        contract._validate_current_canary_lineage(custody, require_live=False)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    attempt = custody["current_canary_lineage"]["generations"][2]["live_attempt_13"]
    attempt["gate"]["recommendation"] = "PROCEED"
    with pytest.raises(contract.ContractError, match="immutable B39 history"):
        contract._validate_current_canary_lineage(custody, require_live=False)


def test_attempt_14_immutable_outcome_cannot_be_rewritten() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["attempt_14_prelaunch"]["outcome"] = {"status": "PASSED", "receipt": "forged.json"}
    with pytest.raises(contract.ContractError, match="immutable outcome drift"):
        contract._validate_attempt_14_prelaunch(custody)


def test_attempt_15_infrastructure_outcome_and_exact_identity_cannot_be_rewritten() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["attempt_15_prelaunch"]["outcome"] = {
        "status": "PASSED",
        "receipt": "forged.json",
    }
    with pytest.raises(contract.ContractError, match="immutable infrastructure outcome drift"):
        contract._validate_attempt_15_prelaunch(custody)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["attempt_15_prelaunch"]["root_fixes"].pop()
    with pytest.raises(contract.ContractError, match="immutable infrastructure outcome drift"):
        contract._validate_attempt_15_prelaunch(custody)


def test_attempt_15_infrastructure_failure_cannot_gain_retry_authority() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    failure = custody["attempt_15_outcome_contract"]["infrastructure_failure"]
    failure["successor_authority"] = "RETRY"
    with pytest.raises(contract.ContractError, match="infrastructure failure contract drift"):
        contract._validate_attempt_14_outcome_and_runtime_contract(custody)


def test_attempt_16_infrastructure_recovery_receipt_cannot_be_reclassified() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    attempt = custody["attempt_16_terminal"]
    attempt["classification"]["infrastructure_failure"] = True
    with pytest.raises(contract.ContractError, match="infrastructure-recovery proof drift"):
        contract._validate_attempt_16_terminal(custody)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    receipt = custody["attempt_16_terminal"]["run_receipt"]
    receipt["gate_attempts"][1]["recommendation"] = "PROCEED"
    with pytest.raises(contract.ContractError, match="infrastructure-recovery proof drift"):
        contract._validate_attempt_16_terminal(custody)


def test_attempt_16_product_nonproceed_cannot_claim_durable_launch() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    contract_row = custody["attempt_16_outcome_contract"]
    contract_row["forbids"].remove("DURABLE_EPIC_LAUNCH_CLAIM")
    with pytest.raises(contract.ContractError, match="product non-PROCEED outcome contract drift"):
        contract._validate_attempt_14_outcome_and_runtime_contract(custody)


def test_v3_relaunch_requires_one_matched_runtime_tuple_after_launch() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    precursor = custody["v3_relaunch_precursor"]
    precursor["durable_relaunch_acceptance"]["requires"].remove(
        "EDITABLE_ROOT_EQUALS_IMPORT_ROOT"
    )
    with pytest.raises(
        contract.ContractError,
        match="v3 relaunch precursor or matched-runtime acceptance drift",
    ):
        contract._validate_v3_relaunch_precursor(custody)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    precursor = custody["v3_relaunch_precursor"]
    precursor["containment"]["durable_epic_launch"] = True
    with pytest.raises(
        contract.ContractError,
        match="v3 relaunch precursor or matched-runtime acceptance drift",
    ):
        contract._validate_v3_relaunch_precursor(custody)


def test_storage_root_cause_and_permanent_tasks_cannot_drift() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["storage_root_cause_follow_up"]["post_attempt_15_capacity"]["free_bytes"] += 1
    with pytest.raises(contract.ContractError, match="capacity or storage root-cause"):
        contract._validate_storage_root_cause_follow_up(custody)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    incident = custody["storage_root_cause_follow_up"]["notification_watchdog_incident"]
    incident["progress_auditor_sent_messages"] = True
    with pytest.raises(contract.ContractError, match="capacity or storage root-cause"):
        contract._validate_storage_root_cause_follow_up(custody)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["storage_root_cause_follow_up"]["safe_reclaim_receipt"]["remaining_count"] = 1
    with pytest.raises(contract.ContractError, match="capacity or storage root-cause"):
        contract._validate_storage_root_cause_follow_up(custody)

    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["storage_root_cause_follow_up"]["permanent_tasks"].pop()
    with pytest.raises(contract.ContractError, match="permanent task drift"):
        contract._validate_storage_root_cause_follow_up(custody)


def test_terminal_manual_review_alert_dedupe_contract_cannot_drift() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    tasks = custody["resident_availability_follow_up"]["tasks"]
    tasks[-1]["acceptance"] = "NON_DURABLE_REEMISSION_ALLOWED"
    with pytest.raises(contract.ContractError, match="resident availability follow-up task drift"):
        contract._validate_attempt_14_outcome_and_runtime_contract(custody)


def test_terminal_nonproceed_cannot_gain_f0_authority() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["attempt_14_outcome_contract"]["terminal_nonproceed"]["forbids"].remove("F0_AUTHORITY")
    with pytest.raises(contract.ContractError, match="PASS versus terminal non-PROCEED"):
        contract._validate_attempt_14_outcome_and_runtime_contract(custody)


def test_resident_outage_cannot_be_attributed_to_attempt_14() -> None:
    custody = contract._load_json(Path(__file__).with_name("custody-manifest.json"))
    custody["resident_availability_follow_up"]["observation"]["causal_attribution_to_canary"] = "CAUSED"
    with pytest.raises(contract.ContractError, match="resident availability incident fact drift"):
        contract._validate_attempt_14_outcome_and_runtime_contract(custody)


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
