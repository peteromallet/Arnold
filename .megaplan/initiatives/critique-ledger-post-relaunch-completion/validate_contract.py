#!/usr/bin/env python3
"""Deterministically validate the Critique Ledger follow-up handoff contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


INITIATIVE = Path(__file__).resolve().parent
ROOT = INITIATIVE.parents[2]
SHA256 = re.compile(r"^[0-9a-f]{64}$")

OBLIGATIONS = {
    "F1.platform_capacity_storage_hardening": "f1-owner-storage-recovery-hardening",
    "F1.physically_minimal_image": "f1-owner-storage-recovery-hardening",
    "F1.cross_pipeline_model_isolation": "f1-owner-storage-recovery-hardening",
    "F1.t1_5_monotonic_consumed_grant": "f1-owner-storage-recovery-hardening",
    "F1.production_recovery_owner": "f1-owner-storage-recovery-hardening",
    "F1.exact_occurrence_handoff": "f1-owner-storage-recovery-hardening",
    "F1.notification_occurrence_version_custody": "f1-owner-storage-recovery-hardening",
    "F1.t1_5_topology_retirement": "f1-owner-storage-recovery-hardening",
    "F1.t1_7_transactional_storage": "f1-owner-storage-recovery-hardening",
    "F1.t1_10_notification_policy": "f1-owner-storage-recovery-hardening",
    "F2.t1_1_universal_admission": "f2-admission-model-effect-release-closure",
    "F2.t1_2_attempt_model_handling": "f2-admission-model-effect-release-closure",
    "F2.provider_attested_model_identity": "f2-admission-model-effect-release-closure",
    "F2.t1_3_transport_integration": "f2-admission-model-effect-release-closure",
    "F2.t1_4_t1_6_release_closure": "f2-admission-model-effect-release-closure",
}

PRELAUNCH_GATES = {
    "accepted_finite_canary_candidate",
    "trusted_host_control_state",
    "bounded_fence_reclaim",
    "durable_failure_reconciliation",
    "built_image_four_phase_smoke",
    "live_capacity_and_predeploy",
    "finite_canary_and_stable_exit",
    "remote_custody_and_fresh_clone",
}

STABLE_EXIT_PROOFS = [
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/built-image-smoke-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/prelaunch-receipts-manifest.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/conformance-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/completion-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/stable-exit-receipt.json",
    ".megaplan/initiatives/critique-ledger-safe-v3-canary/fresh-clone-reconstruction-receipt.json",
]


class ContractError(RuntimeError):
    pass


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_obligations(custody: dict[str, Any]) -> None:
    rows = custody.get("deferred_obligations")
    if not isinstance(rows, list) or len(rows) != 15:
        raise ContractError("deferred_obligations must contain exactly 15 rows")
    expected_fields = {
        "id", "phase", "status", "operational_disposition", "owner_milestone",
        "acceptance_gate", "evidence_ref", "required_claim_id",
    }
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise ContractError("deferred obligation has an inexact schema")
        obligation_id = row.get("id")
        ids.append(obligation_id)
        owner = OBLIGATIONS.get(obligation_id)
        if (
            owner is None
            or row.get("phase") != obligation_id.split(".", 1)[0]
            or row.get("status") != "DEFERRED_POST_CANARY"
            or row.get("operational_disposition") != "NOT_CONSUMED_OPERATIONAL_CANARY"
            or row.get("owner_milestone") != owner
            or row.get("acceptance_gate") != "INDEPENDENT_COMPLETION_MANIFEST_REQUIRED"
            or row.get("evidence_ref") != f"proof-map.json#/{owner}"
            or row.get("required_claim_id") != obligation_id
        ):
            raise ContractError(f"invalid deferred obligation: {obligation_id!r}")
    if ids != list(OBLIGATIONS) or len(ids) != len(set(ids)):
        raise ContractError("deferred obligation order/set/uniqueness drift")


def _validate_prelaunch_gates(custody: dict[str, Any], *, require_live: bool) -> None:
    gates = custody.get("prelaunch_release_gates")
    if not isinstance(gates, list) or len(gates) != len(PRELAUNCH_GATES):
        raise ContractError("prelaunch_release_gates has an inexact count")
    expected_fields = {
        "id", "blocking_phase", "owner", "status", "acceptance_gate", "evidence",
    }
    ids: list[str] = []
    for gate in gates:
        if not isinstance(gate, dict) or set(gate) != expected_fields:
            raise ContractError("prelaunch gate has an inexact schema")
        gate_id = gate.get("id")
        ids.append(gate_id)
        evidence = gate.get("evidence")
        if (
            gate_id not in PRELAUNCH_GATES
            or gate.get("blocking_phase") != "T6.2_PRELAUNCH"
            or gate.get("status") not in {"PENDING", "ACCEPTED"}
            or gate.get("acceptance_gate") != "INDEPENDENT_EXACT_EVIDENCE_REQUIRED"
            or not isinstance(gate.get("owner"), str)
            or not gate.get("owner")
            or not isinstance(evidence, dict)
            or set(evidence) != {"path", "sha256", "status"}
        ):
            raise ContractError(f"invalid prelaunch gate: {gate_id!r}")
        if gate.get("status") == "PENDING":
            if evidence != {"path": None, "sha256": None, "status": "PENDING"}:
                raise ContractError(f"pending gate fabricated evidence: {gate_id}")
        elif (
            evidence.get("status") != "ACCEPTED"
            or not isinstance(evidence.get("path"), str)
            or not SHA256.fullmatch(str(evidence.get("sha256")))
        ):
            raise ContractError(f"accepted gate lacks exact evidence: {gate_id}")
        if require_live and gate.get("status") != "ACCEPTED":
            raise ContractError(f"live gate is not accepted: {gate_id}")
    if set(ids) != PRELAUNCH_GATES or len(ids) != len(set(ids)):
        raise ContractError("prelaunch gate set/uniqueness drift")


def _validate_host_control_state_contract(custody: dict[str, Any]) -> None:
    contract = custody.get("trusted_host_control_state_contract")
    if not isinstance(contract, dict) or set(contract) != {
        "global_containment_marker", "per_attempt_records", "failure_evidence",
    }:
        raise ContractError("trusted host control-state contract has an inexact schema")
    marker = contract.get("global_containment_marker")
    records = contract.get("per_attempt_records")
    failures = contract.get("failure_evidence")
    if marker != {
        "schema": "arnold.cloud.zero_recovery_marker.v2",
        "exact_fields": ["schema", "profile", "scope", "active"],
        "transaction_independent": True,
        "publish_after": [
            "durable_unit_containment_proof",
            "durable_systemd_job_containment_proof",
            "durable_session_containment_proof",
            "durable_process_containment_proof",
        ],
        "canonical_reuse": "ALLOWED_ONLY_AFTER_FRESH_DURABLE_CONTAINMENT_REPROOF",
        "mismatch": "HARD_NO_GO",
    }:
        raise ContractError("global containment marker contract drift")
    if records != {
        "records": ["intent", "apply", "verify", "failure"],
        "exact_binding_fields": ["transaction_id", "transaction_digest", "action"],
        "fresh_retry": "NEW_SUPPORTED_TRANSACTION_AND_FRESH_EVIDENCE",
    }:
        raise ContractError("per-attempt transaction record contract drift")
    if failures != {
        "pre_intent": "NO_MUTATION_FAIL_CLOSED_SUPPORTED_CALLER_CAPTURED_TYPED_ERROR",
        "post_intent_partial_post_prune": "DURABLE_O_EXCL_HOST_FAILURE_RECEIPT",
    }:
        raise ContractError("failure evidence authority split drift")


def _validate_route(route: dict[str, Any]) -> None:
    bindings = route.get("additional_bindings")
    if not isinstance(bindings, dict):
        raise ContractError("route additional_bindings missing")
    for name in ("trusted_host_control_state", "bounded_fence_reclaim", "stable_exit"):
        value = bindings.get(name)
        if not isinstance(value, dict) or value.get("status") != "PRELAUNCH_REQUIRED":
            raise ContractError(f"route binding {name} is not PRELAUNCH_REQUIRED")
    host = bindings["trusted_host_control_state"]
    identity = host.get("directory_identity")
    if (
        host.get("location") != "fixed_host_path_outside_all_historical_and_canary_workspaces"
        or identity != {"type": "directory", "uid": 0, "gid": 0, "mode": "0700", "symlink_free": True}
        or host.get("writes") != "dirfd_relative_no_follow_atomic_file_and_directory_fsync"
        or host.get("global_marker_exact_fields") != ["schema", "profile", "scope", "active"]
        or host.get("global_marker_publication") != "only_after_durable_unit_job_session_process_containment_proof"
        or host.get("global_marker_reuse") != "same_canonical_marker_after_fresh_durable_containment_reproof"
        or host.get("per_attempt_record_exact_fields") != ["transaction_id", "transaction_digest", "action"]
        or host.get("fresh_retry") != "new_supported_transaction_and_fresh_evidence"
        or host.get("global_marker_mismatch") != "HARD_NO_GO"
    ):
        raise ContractError("trusted host control-state contract drift")
    fence = bindings["bounded_fence_reclaim"]
    if (
        fence.get("all_eight_units_before_prune") != "absent_or_inactive_and_masked"
        or fence.get("systemd_jobs") != "emitter_parser_exact_empty_recovery_set"
        or fence.get("persistent_masks") != "crash_safe_before_prune"
        or fence.get("pre_intent_failure") != "no_mutation_fail_closed_supported_caller_captured_typed_error"
        or fence.get("post_intent_failure") != "durable_O_EXCL_host_failure_receipt"
        or fence.get("built_image_four_phase_smoke") != "REQUIRED_BEFORE_DEPLOY"
    ):
        raise ContractError("bounded fence/reclaim contract drift")


def _validate_chain_and_proof_map(chain: dict[str, Any], proof_map: dict[str, Any]) -> None:
    stable_path = ".megaplan/initiatives/critique-ledger-safe-v3-canary/stable-exit-receipt.json"
    matches = [
        item for item in chain.get("launch_preconditions", [])
        if isinstance(item, dict) and item.get("path") == stable_path
    ]
    if len(matches) != 1 or matches[0].get("kind") != "artifact" or matches[0].get("check") != {"kind": "exists"}:
        raise ContractError("chain lacks the fail-closed stable-exit artifact precondition")
    if proof_map.get("finite-canary-stable-exit") != STABLE_EXIT_PROOFS:
        raise ContractError("stable-exit proof map drift")


def _validate_readme(route_path: Path) -> None:
    readme = (INITIATIVE / "README.md").read_text(encoding="utf-8")
    digest = _sha256(route_path)
    if f"SHA-256 `{digest}`" not in readme:
        raise ContractError("README route digest is stale")
    supersession = _load_json(INITIATIVE / "supersession-index.json")
    current = supersession.get("current_operational_route")
    if not isinstance(current, dict) or current.get("sha256") != digest:
        raise ContractError("supersession index route digest is stale")


def _validate_stable_exit_receipt(*, require_live: bool) -> None:
    path = ROOT / ".megaplan/initiatives/critique-ledger-safe-v3-canary/stable-exit-receipt.json"
    if not path.exists():
        if require_live:
            raise ContractError("stable-exit receipt is missing")
        return
    payload = _load_json(path)
    required = {
        "schema", "status", "accepted_candidate", "receipt_digests",
        "predecessor", "successor", "runtime_absence", "host_control_state",
        "custody", "deferred_obligations", "observed_at",
    }
    candidate = payload.get("accepted_candidate")
    digests = payload.get("receipt_digests")
    predecessor = payload.get("predecessor")
    successor = payload.get("successor")
    absence = payload.get("runtime_absence")
    host = payload.get("host_control_state")
    custody = payload.get("custody")
    if (
        set(payload) != required
        or payload.get("schema") != "arnold.critique_ledger.stable_exit_receipt.v1"
        or payload.get("status") != "passed"
        or not isinstance(candidate, dict)
        or set(candidate) != {
            "implementation_commit", "implementation_tree", "manifest_commit",
            "manifest_tree", "image_id", "image_digest", "independent_review_sha256",
        }
        or any(not isinstance(candidate.get(key), str) or not candidate.get(key) for key in candidate)
        or not isinstance(digests, dict)
        or set(digests) != {
            "built_image_smoke", "prelaunch_receipts_manifest", "conformance",
            "completion", "terminal_stop", "fresh_clone_reconstruction",
        }
        or any(not SHA256.fullmatch(str(value)) for value in digests.values())
        or predecessor != {"state": "stopped", "preserved": True, "persistently_fenced": True}
        or successor != {"terminal": "finalized", "state": "stopped"}
        or not isinstance(absence, dict)
        or absence != {
            "systemd_jobs": [], "tmux_sessions": [], "processes": [],
            "notifier": False, "fixer": False, "resident": False,
            "watchdog": False, "timer": False,
        }
        or not isinstance(host, dict)
        or host.get("uid") != 0
        or host.get("gid") != 0
        or host.get("mode") != "0700"
        or host.get("symlink_free") is not True
        or set(host) != {
            "path", "uid", "gid", "mode", "symlink_free", "global_marker_v2",
            "global_marker_transaction_independent", "containment_reproved_for_exit",
            "per_attempt_receipts_transaction_bound",
        }
        or host.get("global_marker_v2") is not True
        or host.get("global_marker_transaction_independent") is not True
        or host.get("containment_reproved_for_exit") is not True
        or host.get("per_attempt_receipts_transaction_bound") is not True
        or not isinstance(custody, dict)
        or set(custody) != {
            "follow_up_commit", "follow_up_tree", "remote_ref", "custody_anchor",
            "prelaunch_tag", "postcanary_tag", "runnable_integration_ref",
            "fresh_clone_receipt_sha256",
        }
        or any(not isinstance(custody.get(key), str) or not custody.get(key) for key in custody)
        or not SHA256.fullmatch(str(custody.get("fresh_clone_receipt_sha256")))
        or payload.get("deferred_obligations") != list(OBLIGATIONS)
        or not isinstance(payload.get("observed_at"), str)
        or not payload.get("observed_at")
    ):
        raise ContractError("stable-exit receipt failed strict verification")


def validate(*, require_live: bool = False) -> None:
    custody = _load_json(INITIATIVE / "custody-manifest.json")
    if custody.get("schema") != "arnold.critique_ledger.unfinished_work_custody.v3":
        raise ContractError("custody manifest schema must be v3")
    _validate_obligations(custody)
    _validate_prelaunch_gates(custody, require_live=require_live)
    _validate_host_control_state_contract(custody)
    route_path = INITIATIVE / "finite-canary-operational-route.json"
    _validate_route(_load_json(route_path))
    proof_map = _load_json(INITIATIVE / "proof-map.json")
    chain = yaml.safe_load((INITIATIVE / "chain.yaml").read_text(encoding="utf-8"))
    if not isinstance(chain, dict):
        raise ContractError("chain.yaml must contain a mapping")
    _validate_chain_and_proof_map(chain, proof_map)
    _validate_readme(route_path)
    _validate_stable_exit_receipt(require_live=require_live)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    validate(require_live=args.require_live)
    print("critique-ledger follow-up contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
