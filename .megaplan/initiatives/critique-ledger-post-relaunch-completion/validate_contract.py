#!/usr/bin/env python3
"""Deterministically validate the Critique Ledger follow-up handoff contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from arnold_pipelines.megaplan.chain.spec import load_spec, validate_launch_preconditions
from arnold_pipelines.megaplan.profiles import load_profiles, resolve_profile
from arnold_pipelines.megaplan.profiles.policy import (
    apply_deepseek_provider_rewrite,
    apply_depth_rewrite,
    apply_vendor_rewrite,
)


INITIATIVE = Path(__file__).resolve().parent
ROOT = INITIATIVE.parents[2]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
R5_REPAIR_CONTROL_EVIDENCE = (
    ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
    "evidence/r5-cl2-repair-control-incident-20260803.json"
)
PROVIDER_POLICY_BINDING_CONTRACT = "provider-policy-execution-binding-contract.json"
PROVIDER_SCHEMA_DIALECT_CONTRACT = "provider-schema-dialect-family-contract.json"
ARTIFACT_ARCHIVAL_PROJECTION_CONTRACT = (
    "artifact-archival-projection-cleanup-contract.json"
)
ESCALATION_SIDECAR_PATH_CONTRACT = (
    "escalation-sidecar-path-normalization-migration-contract.json"
)
FINALIZE_OUTPUT_HANDOFF_RETRY_CONTRACT = (
    "finalize-output-artifact-handoff-shared-retry-contract.json"
)
M11_ACCEPTANCE_GAP_EVIDENCE = (
    "evidence/m11-acceptance-dependency-gap-20260803.json"
)
M7_RUNTIME_REBIND_PROJECTION_EVIDENCE = (
    "evidence/r5-m7-runtime-rebind-projection-cursor-mismatch-20260803.json"
)
CROSS_CONTAINER_LIVENESS_EVIDENCE = (
    "evidence/r5-cross-container-liveness-observer-defect-20260803.json"
)

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

KNOWN_ATTEMPTS = [
    ("B8-build", "IMAGE_BUILD", "c0e5e745d796d01deb962129f834978127f3adc0", "0dc3d1e8c5d58ae5d09aa676148efadeb2f78ce8", None),
    ("B9-build", "IMAGE_BUILD", "cd120d8c585c078418583ba5142c966ac5554a12", "025d719eb1318a2ff1f52673b79ef0014be7a1b2", None),
    ("B10-build", "IMAGE_BUILD", "04178bf31748aa746a36e7e736c0ee38d441b666", "7c67c7c63dc8d065a2f63663cba73e4566ed4c0e", None),
    ("B10-smoke", "OFFLINE_STRUCTURAL_SMOKE", "04178bf31748aa746a36e7e736c0ee38d441b666", "7c67c7c63dc8d065a2f63663cba73e4566ed4c0e", "/var/lib/arnold-zero-recovery/critique-ledger-b10-offline-smoke.json"),
    ("B11-smoke", "OFFLINE_STRUCTURAL_SMOKE", "d610d1420a9851f2d3c0be27cf1cada5413b4f0f", "1e9153d8ceda3834dc1f7b658322c7afbe16e05b", "/var/lib/arnold-zero-recovery/critique-ledger-b11-offline-smoke.json"),
    ("B12-smoke", "OFFLINE_STRUCTURAL_SMOKE", "cc5cd5b3c435d1694a574eb23c8ec3ead52d70a2", "5494ba3a87b3f1522ac3639f5f00c1f08402f696", "/var/lib/arnold-zero-recovery/critique-ledger-b12-offline-smoke.json"),
    ("B13-smoke", "OFFLINE_STRUCTURAL_SMOKE", "63f8c0ae02e951361bab81949bec661f101a2f7e", "49afa570cb237185f91ef88782165d74a8c5f95c", "/var/lib/arnold-zero-recovery/critique-ledger-b13-offline-smoke.json"),
    ("B14-smoke", "OFFLINE_STRUCTURAL_SMOKE", "38a7608ff435d08ce7a16d0e632f08a5c29a1f2e", "17f5cbcf0cc281f7d5969848b64425b58ce16682", "/var/lib/arnold-zero-recovery/critique-ledger-b14-offline-smoke.json"),
    ("B15-smoke", "OFFLINE_STRUCTURAL_SMOKE", "4fbe51cdd7b04053bafccc5dba5d3fac0dd436aa", "f7869b70e2bdce0b06c37b6726b113280e85e78d", "/var/lib/arnold-zero-recovery/critique-ledger-b15-offline-smoke.json"),
    ("B16-smoke", "OFFLINE_STRUCTURAL_SMOKE", "05c874c875a9e81d2015c1bcce8746cbba540299", "6f332c32e17f3e9e1c99d3acdc168adb5c691d24", "/var/lib/arnold-zero-recovery/critique-ledger-b16-offline-smoke.json"),
    ("B17-smoke", "OFFLINE_STRUCTURAL_SMOKE", "dbb98ff2596063b4632b3e9d392b882a5808b7ec", "5115448b5da9ae95899f21f911d154ab9d1a97d0", "/var/lib/arnold-zero-recovery/critique-ledger-b17-offline-smoke.json"),
    ("B18-smoke", "OFFLINE_STRUCTURAL_SMOKE", "e1d26430b54d3121fa545a677eb6a5189fbb248e", "75bd6a645cfb49d267e4d985f88881beeda94b7b", "/var/lib/arnold-zero-recovery/critique-ledger-b18-offline-smoke.json"),
    ("B19-smoke", "OFFLINE_STRUCTURAL_SMOKE", "301abcae4187931eac4f97efdd4fac0120b068d9", "f743e9ecddccdaf95b0546960018630771f9468f", "/var/lib/arnold-zero-recovery/critique-ledger-b19-offline-smoke.json"),
    ("B20-smoke", "OFFLINE_STRUCTURAL_SMOKE", "be3ca786094013c3a0350b6860bbb042b63b1cc2", "602e5311d76d1163069834da9186e5380168c005", "/var/lib/arnold-zero-recovery/critique-ledger-b20-offline-smoke.json"),
    ("B21-smoke", "OFFLINE_STRUCTURAL_SMOKE", "29ee2bfd63b6f466c10e60baaaaffee45aa8bd81", "d78c2e2facea5ff0b14bb503c4cb0b7d9901caea", "/var/lib/arnold-zero-recovery/critique-ledger-b21-offline-smoke.json"),
    ("B22-smoke", "OFFLINE_STRUCTURAL_SMOKE", "4e2fca8a294eb18526aa88576c0818487730d26c", "a38dbd6a84e1205286f9e65c04996b23116071f2", "/var/lib/arnold-zero-recovery/critique-ledger-b22-offline-smoke.json"),
    ("B23-smoke", "OFFLINE_STRUCTURAL_SMOKE", "7c9256b210cefb998dec57929e41b5a799faf314", "55161ca5def9fb1688ca911d80afd94ba2df7eb4", "/var/lib/arnold-zero-recovery/critique-ledger-b23-offline-smoke.json"),
    ("B24-smoke", "OFFLINE_STRUCTURAL_SMOKE", "a172a7a7556984f76d86625f3d0953d089f45004", "461672f91b169fa961b9839ab51a6647bdd6f0f9", "/var/lib/arnold-zero-recovery/critique-ledger-b24-offline-smoke.json"),
    ("B25-smoke", "OFFLINE_STRUCTURAL_SMOKE", "117efa9e35307981b16379f9bc8204e5a5ec0695", "13995f708ab68240dfd08fa41430735cb66985b0", "/var/lib/arnold-zero-recovery/critique-ledger-b25-offline-smoke.json"),
]

B26_PASS = {
    "id": "B26-smoke",
    "commit": "9a8edcf11a488b5dfb47e5c4ef7defb17e3ba6d2",
    "tree": "1de51fd479e0bcffc8fb9f951cb27982ad9ee036",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b26-offline-smoke.json",
    "sha256": "cf0967638b2c84097ced4dfc113735bbd66db1a8925d00d7080bdf7242669487",
    "receipt_digest": "7a656459d4aace827e8b180eb025117b609262311641c15ce495ba87042cf64f",
    "production_image": "sha256:261642f73da83b4704b33b02b9b1c14f17c56d4cafb633c98cac4f938d6421ed",
    "derived_image": "sha256:74d24afc0af67ff6ae5de7d40ece647067873168793936f6d5d58e1a4a8742a7",
    "verifier_receipt_digest": "99c4420ac9440d539753e0a261781f6fc8588f974fa7e2ed07ee86cb2106e373",
}

B27_PASS = {
    "id": "B27-smoke",
    "commit": "0a3fbb56e48c5de98a455224c444a522ff31bf07",
    "tree": "beb5d68bfcbdd7b0867a139ec19885dbb260e57d",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b27-offline-smoke.json",
    "sha256": "77c39d4763641724aa3355210c3ccdcbb6deb8a8253b560d416a9f47d3f1e454",
    "receipt_digest": "173288c2fcd0aa793f894a3a995de1512447b4e9bbf6744fc241d2227d505b9b",
    "production_image": "sha256:c5687c73d88307ab9d7847585aaa371d27fab1e1286283b6456dbbf0d269470d",
    "derived_image": "sha256:71ef320bd30fe70211e9885c6972994a5f61c9625cc24bba9aecc2874082fb6e",
    "verifier_receipt_digest": "bae9f5e69d7d2eaf3106ac5652c77be2608fc7c643d708d5c24af74bf2b08184",
}

A27_REPAIR = {
    "id": "A27",
    "commit": "185e8d97732ff25e5e5d6a00b6877b7a46f08129",
    "tree": "a7c204b757fe0673516d1e9e22a1308b73b0d778",
}

A28_REPAIR = {
    "id": "A28",
    "commit": "4845a10a043f7d53ea235789d2603ad3869d212a",
    "tree": "5b2b48a45617f5ddae20075240f061239c884ffb",
}

B28_PASS = {
    "id": "B28-smoke",
    "commit": "d7194ec75dd27c9dc549af603effbdc4f11371ab",
    "tree": "0872e11712cb796cf0be2d65e7f4846bb54211d7",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b28-offline-smoke.json",
    "sha256": "2fa22ddcaeb92bb005cf24dfd8392b2e1e72206f7290c964b52a63549ef253d0",
    "receipt_digest": "3ec46ea9f0992d606da5f34c84d76a58c7c8650f51c79d9538d1682d78bf6d40",
    "production_image": "sha256:c1dcccbd0381bb8d578c14b9a0edfcbb24eddf9d70c537f1063a9e065feba878",
    "derived_image": "sha256:5677ed0b6a888be55ce4aaf1cedbfc57d3037f1e55b6ca1e8e19067029f99476",
    "verifier_receipt_digest": "fa98493c808093164446284204a7ba433f18a2934137a2d98c5ecac462381d40",
}

A29_REPAIR = {
    "id": "A29",
    "commit": "dcebf3749a1b25d2c4aac23223e5bc99280dd432",
    "tree": "b849184abf77d10491a40e252fa2587112ad72ab",
}

B29_PASS = {
    "id": "B29-smoke",
    "commit": "234dab1d37ff3dd9363f4e381cf0f4556d34d966",
    "tree": "ab078643d37e74a4a6ff173dfd9904cfa3c2b3e0",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b29-offline-smoke.json",
    "sha256": "2b32f71a5cf20bf3ef14774f47d3cd6aa0ed1bf2d836df6d1863478c6323e70b",
    "receipt_digest": "3877c42171d7d7a96935631d6202dd2ccdf4a4943515d57f3e77b60fa6c6092b",
    "production_image": "sha256:ddec86ad159adc1c464a7373292ab3ee7bd0cb08555418167f619096d81ef64e",
    "derived_image": "sha256:231c9ff9bfdcd1a1b54b305ca8c74ab7df63067b4501e4c33923cb6a4bc319fe",
    "verifier_receipt_digest": "f785eca5a73c1809ed7f8151e724082dc7da9e6f7b359137e2c2e99dfcca03f9",
}

A30_REPAIR = {
    "id": "A30",
    "commit": "c717f693dbff0c1775a3f4ee06d203a9996aa5ec",
    "tree": "e3dbec62223898005e57bdf03a3e2f97d023c66d",
}

B30_PASS = {
    "id": "B30-smoke",
    "commit": "0bc07ba280d8832e72b6859b20ddec38060954c6",
    "tree": "da191a1a9261d1b8e37bce648a7549a82c6901fb",
    "path": "/var/lib/arnold-zero-recovery/critique-ledger-b30-offline-smoke.json",
    "sha256": "068100927d60dc3b5b9c8fba4f7f814ca0548dbb4ceb8a4aebe791fd8dfd2d95",
    "receipt_digest": "9440f30306ef63895199aa70db7ba249c634780c3a241ac99ad096fa1767fed9",
    "production_image": "sha256:375ccaca36c9727cffd9ce8dab6615bbb163a5f0f62f17b06784c8044e266f6f",
    "derived_image": "sha256:f3d8df941bb2bb6d35e23aa3e61c10b3f16de4bd53f4edeeb28161dc40833ccb",
    "verifier_receipt_digest": "0a1378cb3cbe1040f76665ec0bae29591c23e768ce9dcb4bb14334190fe7e9d3",
}

SCHEMA_ACCESS_RECOVERY_HISTORY = [
    {
        "repair": {"id": "A31", "commit": "5ae02bb84b98d784cd230e69b633e89f77c95462", "tree": "3a42a1bb942d977dfa35705b23e26b2aaa1655aa"},
        "launch": {"id": "B31", "commit": "b0437d698a3806cfa2fed85a7e64cea99468aea5", "tree": "a13ae9c02dbe951f7d503c351b2467c7a9b1b4f1"},
        "change": "GRANT_MODEL_READ_ONLY_SCHEMA_ACCESS",
        "outcome": {"status": "OFFLINE_FAILED_NOT_ACCEPTED", "failure": "SOURCE_IDENTITY"},
    },
    {
        "repair": {"id": "A32", "commit": "9a09b25a3f6596e641b6a88329ccb280a8957bb4", "tree": "b664e32a82a4c6b93a21d718cdbf237e64cf7a0c"},
        "launch": {"id": "B32", "commit": "f1de9294ff19f842cdc82e3736335b5289cf2f4a", "tree": "df563da84ee6d3adb9f38dbd6d45c0d748510979"},
        "change": "IDENTIFY_EXACT_SOURCE_INTEGRITY_DRIFT",
        "outcome": {"status": "DIAGNOSTIC_ONLY_NOT_ACCEPTED"},
    },
    {
        "repair": {"id": "A33", "commit": "64afbf29cd381de63cdcfa07d5cb80dd44fc7acc", "tree": "2f043d195d1e1f0e9623ead35b4444b878af0e6d"},
        "launch": {"id": "B33", "commit": "109fa8c2f35f3094c7c005a264a14d48390a8b08", "tree": "7043994353fcb17af2ce32625a531f073c636cb4"},
        "change": "ATTEST_SCHEMA_DRIFT_TRANSITION",
        "outcome": {"status": "EXACT_DIAGNOSTIC_EVIDENCE_ESTABLISHED_NOT_ACCEPTED", "mode_transition": "0600_TO_0644", "content_hash": "UNCHANGED"},
    },
    {
        "repair": {"id": "A34", "commit": "eb057201716d4a161465669677d76fb636bddca0", "tree": "857f46813805c47542e7b56e70711ea2f5998ffb"},
        "launch": {"id": "B34", "commit": "c9b403d431f21174e0940433a17265a3978b9a78", "tree": "7532e1e4b21100339f6a8c6511c2b07b0c72e333"},
        "change": "REVOKE_TRANSIENT_SCHEMA_READ_GRANT",
        "outcome": {"status": "HAPPY_PATH_GRANT_REVOKE_PASSED_INDEPENDENT_NO_GO_NOT_ACCEPTED", "reason": "FAILURE_CLEANUP_INCOMPLETE"},
    },
    {
        "repair": {"id": "A35", "commit": "aa493800750e3547a78a4ef0bf00edc9ac4a9b50", "tree": "d0ff36acc353fd95eccdb6162fcdfdde54f9abc7"},
        "launch": {"id": "B35", "commit": "665851a8af14c895545a0b9f8d67251e0958f3c8", "tree": "2d5e49eab5e5f27ab522accb37b97039ae1e3988"},
        "change": "TOTAL_SCHEMA_GRANT_CLEANUP",
        "tests": {"passed": 177, "skipped": 1},
        "diagnostic_pass": {
            "path": None,
            "sha256": "f68b132bfe918ed8028597f25a38330edf3c3d9e23ad924eb55d424a1307e2b8",
            "digest_prefix": "0a5d477d",
            "digest_full": None,
            "status": "PASSED_REMOTE_PATH_AND_FULL_DIGEST_NOT_SUPPLIED",
        },
        "production_acceptance_smoke": {
            "path": None,
            "sha256": "901e677c85f7fd213f8e0129712f146024b36dc578225e3f86091e0f3fcae383",
            "digest_prefix": "8668387b",
            "digest_full": None,
            "production_image_prefix": "sha256:fec327f1",
            "production_image_full": None,
            "status": "PASSED_PENDING_INDEPENDENT_ACCEPTANCE_NOT_LIVE_GATE",
        },
        "fresh_predeploy": {"observation": "GO", "free_bytes": 1343115264, "gate_status": "PENDING_INDEPENDENT_EVIDENCE"},
        "independent_review": {"path": None, "sha256": None, "status": "PENDING"},
        "live_gate": "PENDING",
        "stable_exit_gate": "PENDING",
    },
    {
        "repair": {"id": "A36", "commit": "b9a7a2d2eacca529568b625e35525762a961eda5", "tree": "d9384fb3b9114e3d02dd4b5f66e191975819efa8"},
        "launch": {"id": "B36", "commit": "a3288a6364fb51776f816577a5857bdebab8aa74", "tree": "7ceb34a0a2cdd0973563d5f0c42eb4864ad85791"},
        "change": "RUNNING_STATUS_IS_NON_CANCELLING_IN_PROGRESS_AND_CLI_SUCCESS",
        "regression_tests": "ADDED_COUNT_NOT_SUPPLIED",
        "retry_isolation": {
            "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-10-20260803",
            "container": "megaplan-cloud-agent-finite-canary-10",
            "preserves_attempt": "B35-live-attempt-9",
        },
        "gates": {"offline": "PENDING", "independent": "PENDING", "live": "PENDING", "stable_exit": "PENDING"},
    },
]

FAILED_LIVE_TRANSACTION_ID = "404dd858567d48ffbe8cb7c27d85185a"

OPERATION_IDS = [
    "critique-ledger-zero-byte-bootstrap-20260803-034217z",
    "critique-ledger-capacity-reserve-remediation-20260803-0349z",
    "critique-ledger-capacity-reserve-fallback-20260803-0350z",
    "critique-ledger-failed-build-capacity-reset-20260803-0400z",
    "critique-ledger-failed-build-capacity-reset-corrected-20260803-0404z",
]

OPERATION_SUPERSESSION = {
    "critique-ledger-capacity-reserve-fallback-20260803-0350z": "critique-ledger-capacity-reserve-remediation-20260803-0349z",
    "critique-ledger-failed-build-capacity-reset-corrected-20260803-0404z": "critique-ledger-failed-build-capacity-reset-20260803-0400z",
}


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


def _repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ContractError(f"evidence path escapes repository: {value}") from exc
    return path


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
        else:
            evidence_path = _repo_path(evidence["path"])
            if not evidence_path.is_file() or _sha256(evidence_path) != evidence["sha256"]:
                raise ContractError(f"accepted gate evidence hash mismatch: {gate_id}")
        if require_live and gate.get("status") != "ACCEPTED":
            raise ContractError(f"live gate is not accepted: {gate_id}")
    if set(ids) != PRELAUNCH_GATES or len(ids) != len(set(ids)):
        raise ContractError("prelaunch gate set/uniqueness drift")


def _validate_attempt_history(custody: dict[str, Any], *, require_live: bool = False) -> None:
    attempts = custody.get("prelaunch_attempts")
    if not isinstance(attempts, list) or len(attempts) != len(KNOWN_ATTEMPTS) + 5:
        raise ContractError("prelaunch attempt history is incomplete")
    expected_fields = {"id", "kind", "candidate", "status", "failure", "remote_receipt"}
    ids: list[str] = []
    for index, attempt in enumerate(attempts):
        if index == len(KNOWN_ATTEMPTS):
            if not isinstance(attempt, dict):
                raise ContractError("B26 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review",
                }
                or attempt.get("id") != B26_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B26_PASS["commit"], "tree": B26_PASS["tree"]}
                or attempt.get("status") != "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B26_PASS["path"],
                    "sha256": B26_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_REQUIRED",
                }
                or attempt.get("receipt_digest") != B26_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B26_PASS["production_image"],
                    "derived": B26_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B26_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("independent_review") != {
                    "reviewer": "Sol",
                    "decision": "GO",
                    "artifact": {"path": None, "sha256": None, "status": "NO_LOCAL_ARTIFACT_PRESENT"},
                }
            ):
                raise ContractError("B26 passing smoke binding drift")
            continue
        if index == len(KNOWN_ATTEMPTS) + 1:
            if not isinstance(attempt, dict):
                raise ContractError("B27 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            review = attempt.get("independent_review")
            pending_review = review == {"path": None, "sha256": None, "status": "PENDING_SOL_ACCEPTANCE"}
            accepted_review = (
                isinstance(review, dict)
                and set(review) == {"path", "sha256", "status", "reviewer", "decision"}
                and review.get("reviewer") == "Sol"
                and review.get("decision") == "GO"
                and review.get("status") == "ACCEPTED"
                and isinstance(review.get("path"), str)
                and SHA256.fullmatch(str(review.get("sha256"))) is not None
            )
            if accepted_review:
                review_path = _repo_path(review["path"])
                accepted_review = review_path.is_file() and _sha256(review_path) == review["sha256"]
            expected_status = (
                "PASSED_EXIT_0_PENDING_INDEPENDENT_SOL_ACCEPTANCE_NOT_LIVE_GATE"
                if pending_review
                else "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
            )
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review", "repair_lineage",
                }
                or attempt.get("id") != B27_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B27_PASS["commit"], "tree": B27_PASS["tree"]}
                or attempt.get("status") != expected_status
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B27_PASS["path"],
                    "sha256": B27_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_AND_INDEPENDENT_REVIEW_REQUIRED",
                }
                or attempt.get("receipt_digest") != B27_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B27_PASS["production_image"],
                    "derived": B27_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B27_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("repair_lineage") != {
                    "repair": A27_REPAIR,
                    "launch": {"id": "B27", "commit": B27_PASS["commit"], "tree": B27_PASS["tree"]},
                    "tests": {"passed": 169, "skipped": 1},
                    "change": "NARROW_ABSENT_TMUX_SOCKET_CLASSIFIER_PLUS_FAIL_CLOSED_UNKNOWN_REGRESSION",
                }
                or not (pending_review or accepted_review)
            ):
                raise ContractError("B27 passing smoke binding drift")
            continue
        if index == len(KNOWN_ATTEMPTS) + 2:
            if not isinstance(attempt, dict):
                raise ContractError("B28 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            review = attempt.get("independent_review")
            pending_review = review == {"path": None, "sha256": None, "status": "PENDING_SOL_ACCEPTANCE"}
            accepted_review = (
                isinstance(review, dict)
                and set(review) == {"path", "sha256", "status", "reviewer", "decision"}
                and review.get("reviewer") == "Sol"
                and review.get("decision") == "GO"
                and review.get("status") == "ACCEPTED"
                and isinstance(review.get("path"), str)
                and SHA256.fullmatch(str(review.get("sha256"))) is not None
            )
            if accepted_review:
                review_path = _repo_path(review["path"])
                accepted_review = review_path.is_file() and _sha256(review_path) == review["sha256"]
            expected_status = (
                "PASSED_EXIT_0_PENDING_INDEPENDENT_SOL_ACCEPTANCE_NOT_LIVE_GATE"
                if pending_review
                else "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
            )
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review", "repair_lineage",
                    "retry_isolation",
                }
                or attempt.get("id") != B28_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B28_PASS["commit"], "tree": B28_PASS["tree"]}
                or attempt.get("status") != expected_status
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B28_PASS["path"],
                    "sha256": B28_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_AND_INDEPENDENT_REVIEW_REQUIRED",
                }
                or attempt.get("receipt_digest") != B28_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B28_PASS["production_image"],
                    "derived": B28_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B28_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("repair_lineage") != {
                    "repair": A28_REPAIR,
                    "launch": {"id": "B28", "commit": B28_PASS["commit"], "tree": B28_PASS["tree"]},
                    "tests": {"passed": 171, "skipped": 1},
                    "change": "ADMIT_ONLY_INERT_AF_UNIX_SOCKETS_THEN_COUNT_AND_SEAL_STILL_REJECT_OTHER_SPECIAL_LINKED_OBJECTS",
                }
                or attempt.get("retry_isolation") != {
                    "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-2-20260803",
                    "container": "megaplan-cloud-agent-finite-canary-2",
                    "preserves_attempt": "B27-live-attempt-1",
                }
                or not (pending_review or accepted_review)
            ):
                raise ContractError("B28 passing smoke binding drift")
            continue
        if index == len(KNOWN_ATTEMPTS) + 3:
            if not isinstance(attempt, dict):
                raise ContractError("B29 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            review = attempt.get("independent_review")
            pending_review = review == {"path": None, "sha256": None, "status": "PENDING_SOL_ACCEPTANCE"}
            accepted_review = (
                isinstance(review, dict)
                and set(review) == {"path", "sha256", "status", "reviewer", "decision"}
                and review.get("reviewer") == "Sol"
                and review.get("decision") == "GO"
                and review.get("status") == "ACCEPTED"
                and isinstance(review.get("path"), str)
                and SHA256.fullmatch(str(review.get("sha256"))) is not None
            )
            if accepted_review:
                review_path = _repo_path(review["path"])
                accepted_review = review_path.is_file() and _sha256(review_path) == review["sha256"]
            expected_status = (
                "PASSED_EXIT_0_PENDING_INDEPENDENT_SOL_ACCEPTANCE_NOT_LIVE_GATE"
                if pending_review
                else "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
            )
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review", "repair_lineage",
                    "retry_isolation",
                }
                or attempt.get("id") != B29_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B29_PASS["commit"], "tree": B29_PASS["tree"]}
                or attempt.get("status") != expected_status
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B29_PASS["path"],
                    "sha256": B29_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_AND_INDEPENDENT_REVIEW_REQUIRED",
                }
                or attempt.get("receipt_digest") != B29_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B29_PASS["production_image"],
                    "derived": B29_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B29_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("repair_lineage") != {
                    "repair": A29_REPAIR,
                    "launch": {"id": "B29", "commit": B29_PASS["commit"], "tree": B29_PASS["tree"]},
                    "tests": {"passed": 172, "skipped": 1},
                    "change": "ACCOUNT_SYMLINK_TARGET_BYTES_WITHOUT_RESOLVING_UNLINK_LINK_AFTER_UID_PROCESS_EMPTINESS_PRESERVE_EXTERNAL_TARGET",
                    "still_rejected": ["FIFO", "BLOCK_DEVICE", "CHARACTER_DEVICE", "HARDLINK"],
                }
                or attempt.get("retry_isolation") != {
                    "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-3-20260803",
                    "container": "megaplan-cloud-agent-finite-canary-3",
                    "preserves_attempts": ["B27-live-attempt-1", "B28-live-attempt-2"],
                }
                or not (pending_review or accepted_review)
            ):
                raise ContractError("B29 passing smoke binding drift")
            continue
        if index == len(KNOWN_ATTEMPTS) + 4:
            if not isinstance(attempt, dict):
                raise ContractError("B30 passing smoke has an invalid schema")
            ids.append(attempt.get("id"))
            review = attempt.get("independent_review")
            pending_review = review == {"path": None, "sha256": None, "status": "PENDING_SOL_ACCEPTANCE"}
            accepted_review = (
                isinstance(review, dict)
                and set(review) == {"path", "sha256", "status", "reviewer", "decision"}
                and review.get("reviewer") == "Sol"
                and review.get("decision") == "GO"
                and review.get("status") == "ACCEPTED"
                and isinstance(review.get("path"), str)
                and SHA256.fullmatch(str(review.get("sha256"))) is not None
            )
            if accepted_review:
                review_path = _repo_path(review["path"])
                accepted_review = review_path.is_file() and _sha256(review_path) == review["sha256"]
            expected_status = (
                "PASSED_EXIT_0_PENDING_INDEPENDENT_SOL_ACCEPTANCE_NOT_LIVE_GATE"
                if pending_review
                else "PASSED_EXIT_0_INDEPENDENT_SOL_GO_NOT_LIVE_GATE"
            )
            if (
                set(attempt) != {
                    "id", "kind", "candidate", "status", "result", "remote_receipt",
                    "receipt_digest", "image", "verifier_receipt_digest", "phases",
                    "privilege_receipt_count", "independent_review", "repair_lineage",
                    "retry_isolation",
                }
                or attempt.get("id") != B30_PASS["id"]
                or attempt.get("kind") != "OFFLINE_STRUCTURAL_SMOKE"
                or attempt.get("candidate") != {"commit": B30_PASS["commit"], "tree": B30_PASS["tree"]}
                or attempt.get("status") != expected_status
                or attempt.get("result") != {"exit_code": 0, "phase_status": "ALL_EXACT_PHASES_PASSED", "terminal_state": "finalized"}
                or attempt.get("remote_receipt") != {
                    "path": B30_PASS["path"],
                    "sha256": B30_PASS["sha256"],
                    "status": "REMOTE_SHA_DECLARED_COPY_AND_INDEPENDENT_REVIEW_REQUIRED",
                }
                or attempt.get("receipt_digest") != B30_PASS["receipt_digest"]
                or attempt.get("image") != {
                    "production": B30_PASS["production_image"],
                    "derived": B30_PASS["derived_image"],
                }
                or attempt.get("verifier_receipt_digest") != B30_PASS["verifier_receipt_digest"]
                or attempt.get("phases") != ["init", "plan", "critique", "gate", "finalize"]
                or attempt.get("privilege_receipt_count") != 4
                or attempt.get("repair_lineage") != {
                    "repair": A30_REPAIR,
                    "launch": {"id": "B30", "commit": B30_PASS["commit"], "tree": B30_PASS["tree"]},
                    "tests": {"passed": 172, "skipped": 1},
                    "change": "TAKE_TRUSTED_DIRECTORY_OWNERSHIP_AND_MODE_BEFORE_RECURSE_AFTER_UID_EMPTY_PROOF",
                    "capabilities": {"minimal": True, "dac_override": False},
                }
                or attempt.get("retry_isolation") != {
                    "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-4-20260803",
                    "container": "megaplan-cloud-agent-finite-canary-4",
                    "preserves_attempts": [
                        "B27-live-attempt-1", "B28-live-attempt-2", "B29-live-attempt-3",
                    ],
                }
                or not (pending_review or accepted_review)
            ):
                raise ContractError("B30 passing smoke binding drift")
            continue
        if not isinstance(attempt, dict) or set(attempt) != expected_fields:
            raise ContractError("prelaunch attempt has an inexact schema")
        attempt_id = attempt.get("id")
        ids.append(attempt_id)
        candidate = attempt.get("candidate")
        receipt = attempt.get("remote_receipt")
        if (
            not isinstance(attempt_id, str)
            or not isinstance(candidate, dict)
            or set(candidate) != {"commit", "tree"}
            or not all(re.fullmatch(r"[0-9a-f]{40}", str(candidate.get(key))) for key in ("commit", "tree"))
            or not isinstance(attempt.get("failure"), str)
            or not attempt.get("failure")
            or not isinstance(receipt, dict)
            or set(receipt) != {"path", "sha256", "status"}
        ):
            raise ContractError(f"invalid prelaunch attempt: {attempt_id!r}")
        if index < len(KNOWN_ATTEMPTS):
            expected_id, kind, commit, tree, remote_path = KNOWN_ATTEMPTS[index]
            expected_status = (
                "FAILED_ATTEMPT_THEN_LATER_REBUILD_SUCCEEDED_NOT_SMOKE_ACCEPTED"
                if expected_id == "B10-build"
                else "FAILED_NOT_ACCEPTED"
            )
            if (
                attempt_id != expected_id
                or attempt.get("kind") != kind
                or candidate != {"commit": commit, "tree": tree}
                or receipt.get("path") != remote_path
                or attempt.get("status") != expected_status
            ):
                raise ContractError(f"known attempt history drift: {expected_id}")
        if receipt.get("sha256") is None:
            if receipt.get("status") not in {"REMOTE_COPY_REQUIRED", "REMOTE_PATH_NOT_RECORDED_IN_LOCAL_AUTHORITY"}:
                raise ContractError(f"pending receipt has invalid disposition: {attempt_id}")
        elif not SHA256.fullmatch(str(receipt.get("sha256"))):
            raise ContractError(f"attempt receipt has invalid hash: {attempt_id}")
    if len(ids) != len(set(ids)):
        raise ContractError("prelaunch attempt IDs are not unique")


def _validate_live_deploy_attempts(custody: dict[str, Any]) -> None:
    attempts = custody.get("live_deploy_attempts")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise ContractError("live deploy attempt history is incomplete")
    attempt = attempts[0]
    expected = {
        "transaction_id": FAILED_LIVE_TRANSACTION_ID,
        "status": "FAILED_FAIL_CLOSED_NO_CANARY_CREATED",
        "durable_failure_receipt": {
            "path": f"/var/lib/arnold-zero-recovery/{FAILED_LIVE_TRANSACTION_ID}.host-zero-recovery-fence-apply-failure.json",
            "sha256": None,
            "status": "REMOTE_COPY_AND_RECONCILIATION_REQUIRED",
        },
        "marker_published": False,
        "stage": "verify_no_recovery_sessions",
        "error": "tmux_observation_unknown",
        "recovery_units": {"count": 8, "state": "ALL_INACTIVE_MASKED_PERSISTENT"},
        "canary_created": False,
        "observed_tmux": {
            "returncode": 1,
            "stderr": "error connecting to /tmp/tmux-0/default (No such file or directory)",
        },
        "root_cause": "NARROW_CLASSIFIER_TREATED_ABSENT_TMUX_SOCKET_AS_UNKNOWN",
        "repair": A27_REPAIR,
        "retry_status": "B27_LIVE_ATTEMPT_TERMINAL_RECONCILED",
    }
    if attempt != expected:
        raise ContractError("failed live deploy transaction binding drift")


def _validate_schema_access_recovery_history(custody: dict[str, Any], *, require_live: bool) -> None:
    history = custody.get("schema_access_recovery_history")
    if history != SCHEMA_ACCESS_RECOVERY_HISTORY:
        raise ContractError("A31-B36 schema-access recovery history drift")


def _validate_current_canary_lineage(custody: dict[str, Any], *, require_live: bool) -> None:
    lineage = custody.get("current_canary_lineage")
    if not isinstance(lineage, dict) or set(lineage) != {
        "schema", "status", "publication_gate", "generations",
        "closed_decision",
        "official_reclaim_v2", "live_attempt_12", "capacity_disposition",
        "temporary_b38_diagnostic_checkout_retirement",
        "unresolved_operation_reconciliation",
    }:
        raise ContractError("A37-B39 current canary lineage schema drift")
    generations = lineage.get("generations")
    expected_identities = [
        (
            {"id": "A37", "commit": "b8ffeb14ea408a2171ebcddc3bcda7b6188a36e5", "tree": "dbc56fc906f4bb1976510156f464e681302534db"},
            {"id": "B37", "commit": "c4ac9e76e6665ef47c4f11f5e2f5b37bebb524bd", "tree": "cd4ac3774fe9013751819d05bc12838b704755cd"},
        ),
        (
            {"id": "A38", "commit": "a965867e658193f4b3aba8fbdfa6517a653cb36b", "tree": "f5860f777ece19caedb25426e263c169e0be324c"},
            {"id": "B38", "commit": "84e4ff29eaac7c96b2a6334c5f938015742f11af", "tree": "e15c918e8fcb0bf4437cf534075a0c8258d725aa"},
        ),
        (
            {"id": "A39", "commit": "2159347ae291102dd5ec90d2aac736fc0d5a58e0", "tree": "0b6d9b7961d03665b48b505a2738d7a3612334bb"},
            {"id": "B39", "commit": "11305b7c2c1891614b85322f8e0f3c766d2586d6", "tree": "8adcb18fa955544a7a1da1777b6d9ffbb8d5b9a0"},
        ),
    ]
    if (
        lineage.get("schema") != "arnold.critique_ledger.current_canary_lineage.v2"
        or lineage.get("status")
        != "B39_ATTEMPT_13_IMMUTABLE_TERMINAL_SAFE_NONPROCEED_A40_CLOSED_B44_ATTEMPT_14_TERMINAL_FAILED_MISCLASSIFIED_A15_B15_ATTEMPT_15_TERMINAL_INFRASTRUCTURE_FAILURE_B16_ATTEMPT_16_INFRASTRUCTURE_RECOVERY_PASSED_PRODUCT_GATE_NOT_PROCEED"
        or lineage.get("publication_gate") != {
            "generation": "A36/B36",
            "status": "TERMINAL_NO_GO",
            "rule": "TERMINAL_PUBLICATION_REQUIRES_SEALED_STOP",
        }
        or not isinstance(generations, list)
        or len(generations) != 3
        or [
            (row.get("repair"), row.get("launch"))
            for row in generations
            if isinstance(row, dict)
        ]
        != expected_identities
    ):
        raise ContractError("A37-B39 current canary identity drift")
    b39 = generations[2]
    reclaim = lineage.get("official_reclaim_v2")
    attempt = lineage.get("live_attempt_12")
    retirement = lineage.get("temporary_b38_diagnostic_checkout_retirement")
    unresolved = lineage.get("unresolved_operation_reconciliation")
    if (
        b39.get("tests") != {"passed": 187, "skipped": 1}
        or b39.get("retry_isolation") != {
            "attempt": 13,
            "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-13-20260803",
            "container": "megaplan-cloud-agent-finite-canary-13",
        }
        or b39.get("diagnostic_receipt") != {
            "file_sha256": "c0949f6f2e40b0db1bbc6e3e251c1b701930ca2750a7cc9fcd87f4e64b4488d6",
            "receipt_digest": "84667d967794d93dc753076350d6d34face8d755aee5251d5340629812ef4ed1",
            "verifier_receipt_digest_prefix": "36c31861",
            "status": "EVIDENCE_PRESENT_GATE_PENDING",
        }
        or b39.get("production_receipt") != {
            "file_sha256": "087007324e255ebd42e82daf93781bf7032eb96bdee9643527984ce6240c6fc3",
            "receipt_digest": "1e956fb442e06d7e0520a4f21de04a6eec246e42209e23fcd88ad0da2f72046d",
            "verifier_receipt_digest_prefix": "a1bf4eb8",
            "image_id_prefix": "sha256:d38b921f",
            "status": "EVIDENCE_PRESENT_GATE_PENDING",
        }
        or b39.get("live_attempt_13") != {
            "status": "TERMINAL_SAFE_NONPROCEED_NOT_ACCEPTED",
            "run_receipt": {
                "file_sha256": "ece98b8f99d4613dce1ec17888328a7cbc033df610d25e4855aec1b214c04b9b",
                "receipt_digest": "72e4efaf37ea9b416cdada8e4447a30d2228d837b3029c9f163fee944bf85c11",
            },
            "returned_phases": ["plan", "critique", "gate"],
            "gate": {
                "recommendation": "ITERATE",
                "state": "critiqued",
                "blocking_change_count": 8,
            },
            "runner_diagnostic": {
                "classification": "unexpected_or_active_state",
                "cause": "STATE_CHECK_PRECEDES_GATE_RECOMMENDATION_CLASSIFICATION",
            },
            "finalize": {"run": False, "reason": "GATE_DID_NOT_RECOMMEND_PROCEED"},
            "container": {
                "id_prefix": "6cb81b", "stopped": True,
                "exit_code": 143, "oom_killed": False,
            },
            "workspace": {
                "sealed": True, "inode": 1317407,
                "owner": "root", "mode": "0700",
            },
            "notifications_sent": False,
            "reconciliation": "TERMINAL_RECONCILED",
        }
        or b39.get("gates") != {
            "offline": "OBSERVED_AT_TERMINATION_NOT_ACCEPTED",
            "independent": "OBSERVED_AT_TERMINATION_NOT_ACCEPTED",
            "live": "TERMINAL_NOT_ACCEPTED",
            "stable_exit": "NOT_PRODUCED_TERMINAL_NONPROCEED",
        }
        or lineage.get("closed_decision") != {
            "id": "A40",
            "status": "CLOSED_BOUNDED_TWO_ROUTE_RETRY_AUTHORIZED",
            "initial_implementation": {
                "commit": "a3fe53b67564bbacd7e7d07eea737d675d4d8233",
                "tree": "61205a4b2644548e0c7f3a3acb574fde0e90a611",
            },
            "validator_correction": {
                "commit": "cfab4da6877971f1517367387bd5584bb76a39e8",
                "tree": "607e6a13b62e2d0b58f80bc6aeb5b4b6d5521282",
            },
            "root_causes": [
                "STATIC_V2_ADMISSION", "LEGACY_STATUS_AND_PRIVILEGE_COMPATIBILITY",
                "ITERATION_DRIFT_ENFORCEMENT", "VERSIONED_GATE_CUSTODY",
            ],
            "authority": {
                "routes": [
                    ["init", "plan", "critique", "gate", "finalize"],
                    ["init", "plan", "critique", "gate", "revise", "critique", "gate", "finalize"],
                ],
                "max_revise_cycles": 1,
                "max_gate_attempts": 2,
                "finalize_requires": "PROCEED",
            },
            "f0_bridge": "PASS_BRANCH_ONLY_AFTER_EXACT_COMPLETION_AND_STABLE_EXIT_RECEIPTS",
        }
        or not isinstance(reclaim, dict)
        or reclaim.get("status") != "PASSED"
        or reclaim.get("free_bytes") != {
            "before": 807890944, "after": 1982816256, "delta": 1174925312,
        }
        or reclaim.get("recovery_units") != {"count": 8, "all_masked": True}
        or any(reclaim.get(key) != [] for key in ("systemd_jobs", "tmux_sessions", "processes"))
        or not isinstance(attempt, dict)
        or attempt.get("exact_primary_failure")
        != "finite-model UID retained a process after provider return"
        or attempt.get("downstream_failure") != "uid 65532 output ownership error"
        or attempt.get("root_cause") != "DOCKER_HOST_CONFIG_INIT_WAS_NULL"
        or attempt.get("container", {}).get("exit_code") != 137
        or attempt.get("container", {}).get("oom_killed") is not False
        or attempt.get("container", {}).get("restart_count") != 0
        or attempt.get("workspace") != {
            "attempt": 12, "sealed": True, "owner": "root",
            "mode": "0700", "same_inode": True,
        }
        or not isinstance(retirement, dict)
        or retirement.get("status") != "TERMINAL_RETIRED"
        or retirement.get("creation") != "O_EXCL"
        or retirement.get("commit") != expected_identities[1][1]["commit"]
        or retirement.get("tree") != expected_identities[1][1]["tree"]
        or retirement.get("checkout_size_bytes") != 128547498
        or retirement.get("free_bytes") != {
            "before": 1611960320, "after": 1756692480, "delta": 144732160,
        }
        or retirement.get("receipts_retained") is not True
        or retirement.get("evidence_retained") is not True
        or unresolved != {
            "status": "PENDING_REMOTE_RECEIPT_IMPORT_AND_INDEPENDENT_RECONCILIATION",
            "operation_count": 5,
            "rule": "DO_NOT_REWRITE_INTENTS_OR_REDISPATCH_AMBIGUOUS_OPERATIONS",
        }
    ):
        raise ContractError("immutable B39 history or closed A40 decision drift")
def _validate_attempt_14_prelaunch(custody: dict[str, Any]) -> None:
    attempt = custody.get("attempt_14_prelaunch")
    if not isinstance(attempt, dict):
        raise ContractError("attempt 14 prelaunch custody is missing")
    exact_outcome = {
        "status": "TERMINAL_FAILED_MISCLASSIFIED_NOT_ACCEPTED",
        "run_receipt": {
            "receipt_digest": "59f0d1712bbd6f379d921f9662989a7a524b62e8509182041e08ba368e0abe0d",
            "file_sha256": "23f260ba72c0785401d4749132491beeac1bd2cf7c61cc386c7b29e980ecb3c0",
        },
        "phases": ["init", "plan", "critique", "gate", "revise"],
        "gate": {
            "attempt": 1,
            "recommendation": "ITERATE",
            "state": "critiqued",
            "sha256": "415fb3ffac618a196d2822f288d69d9457abd6f121615c1153e34fb7404e6545",
        },
        "revise": {
            "returncode": 1,
            "state": "critiqued",
            "plan_iteration": 2,
            "recorded_dispatch_ordinal": 4,
            "worker_dispatched": False,
            "blocking_action": {
                "id": "NSA-7",
                "action_type": "add_human_halt",
                "severity": "blocking",
                "question_id": "runtime-source-identity",
            },
        },
        "runner": {
            "terminal_state": "failed",
            "failure": "RuntimeError:nonzero_returncode:1",
            "dispatch_integrity": "partial",
            "product_outcome": None,
            "classification": "MISCLASSIFIED_PRODUCT_TERMINAL_AS_INFRASTRUCTURE_FAILURE",
        },
        "finalize": {"run": False},
        "container": {
            "id": "3c1ff85aea2ad1600f5e5d301e410815ce86fef9067ccab24bf7128e14f3e3af",
            "stopped": True,
            "exit_code": 143,
            "oom_killed": False,
            "restart_count": 0,
        },
        "workspace": {
            "sealed": True,
            "inode": 1324286,
            "owner": "root",
            "group": "root",
            "mode": "0700",
        },
        "acceptance": "IMMUTABLE_HISTORY_NO_F0_AUTHORITY",
    }
    if (
        attempt.get("schema") != "arnold.critique_ledger.attempt_14_prelaunch.v1"
        or attempt.get("status") != "B44_EXACT_CANDIDATE_ATTEMPT_14_TERMINAL_FAILED_MISCLASSIFIED_NOT_ACCEPTED"
        or attempt.get("implementation") != {
            "commit": "a15e87adea1fa78e90008422f42bc79ae60dff13",
            "tree": "63a75d9333e3fa69c9a039846595d3dd4d3cc4b3",
        }
        or attempt.get("launch_manifest") != {
            "id": "B44",
            "commit": "006895e8d66812dec5e85d26b32635af21ca21c7",
            "tree": "8d70cc79bc8f5a79a60be282bcc22122109c7f83",
            "file_sha256": {
                "canary.yaml": "f61ed133dbe4299d01c4ab4753fdac3e20a26f509d16a916aac968d46a68e821",
                "cloud.yaml": "daa5224ba663c4f63e9234afcea32d58155370ffade073a08de1059231cf7b23",
                "proof-map.json": "62ea3c987f9aa688df5ed488f92b5ca94424a986c0d094008fc067fc0fb0ba1c",
                "traceability.json": "e190876881ae83f05ff8c052eda8c612f5a167e9b957059a70fb44425809c3cf",
            },
        }
        or attempt.get("production_image_id") != "sha256:209a64de1f321b5ec49e8d6e6748187f790099a6fe8a68696352a5488bc7ffa6"
        or attempt.get("execution_identity") != {
            "attempt": 14,
            "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-14-20260803",
            "container": "megaplan-cloud-agent-finite-canary-14",
        }
        or attempt.get("outcome") != exact_outcome
    ):
        raise ContractError("attempt 14 B44 identity or immutable outcome drift")
    policy = {
        "routes": [
            ["init", "plan", "critique", "gate", "finalize"],
            ["init", "plan", "critique", "gate", "revise", "critique", "gate", "finalize"],
        ],
        "max_revise_cycles": 1,
        "max_gate_attempts": 2,
        "finalize_requires": "PROCEED",
    }
    if attempt.get("policy") != policy:
        raise ContractError("attempt 14 bounded policy drift")
    rows = attempt.get("diagnostic_smokes")
    expected = [
        ("r1", "8c066722813cf5a9c3d9841ae5e117eeba1abe03967d62e8dfcf5ba0d4681b8b", "9b948d3c57bca531bcdbe39eec321a8a5322b7170c95f9cde3a978749e740ea5", "FAILED_EXIT_1"),
        ("r2", "9937b77ae1b2ee2d9457ecd838fe7306974b747dc366d173ca9aa07e35785437", "91a3409f6caa6a540685a57908a7045dffbd6a27283a0987ab8bce167d30df8d", "FAILED_EXIT_1"),
        ("r3", "ec92967021d8bbedb88eb9207dfabfa6fbd5ec1fd7024b0eff786575594bfcab", "aa38e64cec0751d2262f1b4895bdb07874061b0dc8729b495981a864a484ad78", "FAILED_EXIT_1"),
        ("r4", "30b0326db26be4e07a369f3f160eafede47d0154e29b4cfcfd7c24645e5b9ef2", "c1702e7d4b703dd25b526e1675eeefea14a820ac18795f56e994eac68184c546", "FAILED_EXIT_1"),
        ("r5", "dcf0bde1ba2964429d6d9b548c6dc9308774d4aca4ecf74afc9348514ace8a22", "0133f70e870b9120182c32f90630377efdb7c08d7e8991b654ca36250d83c843", "FAILED_EXIT_1"),
        ("r6", "33d50d935ff7fd5563dc955c8e225af5af11d3986a8e526a5209ba791900970c", "630882727cd432ff8dfa3638e3153a7e7c3db685ce91e5d10f816367f74c7f08", "PASSED_EXIT_0_REVISED_ROUTE_8_PHASES_7_PRIVILEGE_RECEIPTS"),
    ]
    if not isinstance(rows, list) or [
        (row.get("id"), row.get("file_sha256"), row.get("receipt_digest"), row.get("status"))
        for row in rows if isinstance(row, dict)
    ] != expected:
        raise ContractError("diagnostic r1-r6 custody drift")
    source_bindings = [
        ("r1", "ecec2410c20ccb400cf2063ae91c0b383f3c2395", "99e433be5481cfe9b7edd47546e5dadfbda763c0", "/var/lib/arnold-zero-recovery/critique-ledger-b40-diagnostic-offline-smoke.json"),
        ("r2", "ecec2410c20ccb400cf2063ae91c0b383f3c2395", "99e433be5481cfe9b7edd47546e5dadfbda763c0", "/var/lib/arnold-zero-recovery/critique-ledger-b40-diagnostic-offline-smoke-r2.json"),
        ("r3", "be0c3f14fce049ee30d0845d2b64354c1d3f8063", "d0ac3d27c6aa0a086fe9ddd280dd9ea17ab28c09", "/var/lib/arnold-zero-recovery/critique-ledger-b41-diagnostic-offline-smoke-r3.json"),
        ("r4", "edfc5a5a7bc5743c0d3a8115b320429a79c1f812", "77286b9b537edd2cc374e8a96c66d1dfbeb29909", "/var/lib/arnold-zero-recovery/critique-ledger-b42-diagnostic-offline-smoke-r4.json"),
        ("r5", "d2551caedaa4e784345c6c771bd2e148c417fc59", "882488f85fbf0fc5f8ff8a3b531e1ca460467ad2", "/var/lib/arnold-zero-recovery/critique-ledger-b43-diagnostic-offline-smoke-r5.json"),
        ("r6", "006895e8d66812dec5e85d26b32635af21ca21c7", "8d70cc79bc8f5a79a60be282bcc22122109c7f83", "/var/lib/arnold-zero-recovery/critique-ledger-b44-diagnostic-offline-smoke-r6.json"),
    ]
    if [(row["id"], row["source_commit"], row["source_tree"], row["path"]) for row in rows] != source_bindings:
        raise ContractError("diagnostic r1-r6 source binding drift")
    verifier_receipts = [
        ("r2", "50489c2d2146a72eb16e08a63d7629b0e4e2d27924eeb9aa436cae4e81b0c305", "9fe4e8b971402ac2819852ceb6df098905a521a0228c51bf8ea3a79447a19388"),
        ("r3", "631e6020a25c65caef189eef604e8af855954b8ed9105853756223d9becaa3ab", "df5658abf81342191c44b8435c7d061ee5d7ff57c4e17280dbbeda5dd6f1cb26"),
        ("r4", "77e1cc8454d3b51b36c6f39aead573ce5c1b56c939884066af8ca36e74c5453f", "57d946804ae69656d0f93e9cd96b3e19737f3f82b4852cebb3641a019d519187"),
        ("r5", "791b3942723346ffb2df146d6412f7e63b99fb729bf637525d022b0307d53dee", "4b4fb2545c5fee54c4b5d738f03483edc7446fc1442c5c75e97e3091b31973f5"),
    ]
    if [(row["id"], row["verifier_run_receipt_file_sha256"], row["verifier_run_receipt_digest"]) for row in rows[1:5]] != verifier_receipts:
        raise ContractError("diagnostic r2-r5 verifier receipt drift")
    if rows[5].get("verifier_run_receipt_file_sha256") != "d85831ced32d04f5c9dcc0f83b47836919188385e1ee154c534275eb7356461d":
        raise ContractError("diagnostic r6 verifier run receipt drift")
    smoke = attempt.get("production_smoke")
    if not isinstance(smoke, dict) or smoke != {
        "path": "/var/lib/arnold-zero-recovery/critique-ledger-b44-production-offline-smoke.json",
        "file_sha256": "68574193e948de6e88a1e31dabb000a922133db9f2013357e474ab4d396ab03b",
        "receipt_digest": "9480c5b95db9848668bfc9331611648619110360535e303ba4a341cf243a9b6e",
        "image_id": "sha256:209a64de1f321b5ec49e8d6e6748187f790099a6fe8a68696352a5488bc7ffa6",
        "derived_image_id": "sha256:7a9b4c1dc68a34a8890b9ebbf0b898e4bee08fdfa2e2aa16f570d5cd19bbb9bc",
        "verifier_receipt_digest": "c2ea7d29b7d9c0bdbc67039bb6e1ee0a13d1628d38d167fa72cecf09b22cd40b",
        "verifier_run_receipt_file_sha256": "2742dcc332b86d1b398ca3a7d9dc4b0c860b225a0f439946f9e606f78d1054ae",
        "status": "PASSED_EXIT_0_REVISED_ROUTE_8_PHASES_7_PRIVILEGE_RECEIPTS",
    }:
        raise ContractError("B44 production smoke custody drift")


def _validate_attempt_15_prelaunch(custody: dict[str, Any]) -> None:
    attempt = custody.get("attempt_15_prelaunch")
    if not isinstance(attempt, dict):
        raise ContractError("attempt 15 prelaunch custody is missing")
    if attempt != {
        "schema": "arnold.critique_ledger.attempt_15_prelaunch.v1",
        "status": "A15_B15_ATTEMPT_15_TERMINAL_INFRASTRUCTURE_FAILURE_NOT_ACCEPTED",
        "implementation": {
            "id": "A15",
            "commit": "8932873ba1c81d398cf42fb9879605d14d50cbb4",
            "tree": "7fdcf11dba38354645290314443c1de3c8b33bbb",
        },
        "launch_manifest": {
            "id": "B15",
            "commit": "4f021cb70f3202dd90d599f8d710b626ba27b16b",
            "tree": "3777df403e9ae06cba75cf6fb6ac3b804f808723",
            "file_sha256": {
                "canary.yaml": "f692b74aaabbce83746d009925bfa86a997b10c117f12370749fd1785291a316",
                "cloud.yaml": "13600d258f3718a160ff6d5373c32cc9d439242a41a7c5adb8a9c7944b527fed",
                "proof-map.json": "8d2ce59ef494bf6a027edfe1da751b16a3b541b64738aeb29e4ee8d44058bca2",
                "traceability.json": "c891718f4444a244fa3afe5d129659e9c6b4a50a7fcbc5f78380e0ed0753a61b",
            },
        },
        "production_image_id": "sha256:ea1e66940e7445649b083b8d7acc896080526011f9bfc4a9e21b475046e1814a",
        "execution_identity": {
            "attempt": 15,
            "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-15-20260803",
            "container": "megaplan-cloud-agent-finite-canary-15",
        },
        "root_fixes": [
            "CLEAN_COMMITTED_SOURCE_COMMIT_AND_TREE_SETTLED_FOR_FINALIZE_DIRECT_EXECUTE_BATCH_EXECUTE_AND_HANDOFF",
            "TYPED_REVISE_PHASE_RESULT_WITH_FRESH_INVOCATION_IDENTITY",
            "PRODUCT_REVISE_BLOCKED_CLASSIFICATION_FOR_HUMAN_HALT_AND_UNRESOLVED_BLOCKING",
            "EXACT_REVISE_DISPATCH_ORDINAL_4_VALIDATION_ONLY_WHEN_REVISE_WORKER_DISPATCHED",
        ],
        "terminal_observation": {
            "completed_at": "2026-08-03T11:00:12.627961Z",
            "container_id": "6f80cd29f7ba13c50bbc4b77bbaea6df7f7ceaf261b0972571984bfba840f6f2",
            "container_state": "exited",
            "container_exit_code": 143,
            "container_oom_killed": False,
            "container_restart_count": 0,
            "workspace_inode": 1680645,
            "workspace_owner": "root",
            "workspace_group": "root",
            "workspace_mode": "0700",
            "workspace_sealed": True,
        },
        "outcome": {
            "status": "TERMINAL_INFRASTRUCTURE_FAILURE_NOT_ACCEPTED",
            "run_receipt": {
                "receipt_digest": "59bc8d659ca8ec59baa9da9051fcd7320199e6ffea12a97d3b7018694b266331",
                "file_sha256": "10eb82a07ca0829b585c4316413b76851665ac9b90ef93e051f94626f91a182a",
            },
            "completed_at": "2026-08-03T11:00:12.627961Z",
            "phases": ["init", "plan", "critique"],
            "plan": {
                "model": "codex:gpt-5.6-sol:high",
                "dispatch_ordinal": 1,
                "returncode": 0,
                "state": "planned",
                "worker_result": "returned",
            },
            "critique": {
                "model": "codex:gpt-5.6-sol:high",
                "dispatch_ordinal": 2,
                "worker_dispatch": "RETURNED_NORMALLY_WITH_WORKER_OUTPUT",
                "code_mode_host": "REPEATED_SIGTRAP_AND_CLOSED_STDOUT",
                "effect": "COULD_NOT_INSPECT_OR_UPDATE_TEMPLATE",
                "returncode": 1,
                "state": "planned",
            },
            "not_run": ["gate", "revise", "finalize"],
            "runner": {
                "status": "failed",
                "terminal_state": "failed",
                "failure": "RuntimeError:nonzero_returncode:1",
                "failure_phase": "critique",
                "dispatch_integrity": "partial",
                "dispatch_ledger_sha256": "222abc464f60acf7b14689fcfef4ca8649a7746d80e3d09a600caf89988d7ded",
                "product_outcome": None,
            },
            "acceptance": "INFRASTRUCTURE_FAILURE_NO_F0_AUTHORITY",
            "retry": "ONLY_AFTER_CAPACITY_ROOT_CLEANUP_AND_NEW_EXPLICIT_AUTHORITY",
        },
    }:
        raise ContractError("attempt 15 A15/B15 identity or immutable infrastructure outcome drift")


def _validate_attempt_16_terminal(custody: dict[str, Any]) -> None:
    attempt = custody.get("attempt_16_terminal")
    if attempt != {
        "schema": "arnold.critique_ledger.attempt_16_terminal.v1",
        "status": "INFRASTRUCTURE_RECOVERY_PASSED_PRODUCT_GATE_NOT_PROCEED_NOT_DURABLE_EPIC_LAUNCH",
        "source": {
            "id": "B16",
            "commit": "fb5a394878bc900b189213a3de5dcc40169d8b7b",
            "tree": "a8f903a94e5029fa50c148df3289186dc4c39caf",
        },
        "outer_status": "available",
        "run_receipt": {
            "schema": "arnold.megaplan.finite_canary_run_receipt.v3",
            "status": "passed",
            "terminal_state": "product_gate_not_proceed",
            "product_outcome": {
                "kind": "product_gate_not_proceed",
                "recommendation": "ITERATE",
                "gate_attempt": 2,
            },
            "phases": ["init", "plan", "critique", "gate", "revise", "critique", "gate"],
            "phase_returncodes": [0, 0, 0, 0, 0, 0, 0],
            "dispatch_integrity": "complete",
            "failure": None,
            "gate_attempts": [
                {"attempt": 1, "recommendation": "ITERATE"},
                {
                    "attempt": 2,
                    "recommendation": "ITERATE",
                    "gate_sha256": "b8d6dcf366b04bde245890e1cb224c191f202101cb53dbb3fa59ca721c05d546",
                },
            ],
            "receipt_digest": "3a9925dbfcc0c901905db0265b48c062f051b16bdbb31b9f873c5e086eac08c0",
            "file_sha256": "1b4e1d013f444b3f3f2c3af1bb4938002e730f727a0be39834a2ca235fa592ba",
            "state_sha256": "4ef979066dfb3c822625de21ec52e95c7d25a42f185ea01970865d4b4116e525",
        },
        "terminal_observation": {
            "container_id": "0552d39f4589239cb0b8e10b68b12c8ebab3a0e2fde6284049e1e466f0896ba6",
            "container_state": "stopped",
            "container_exit_code": 143,
            "container_oom_killed": False,
            "container_restart_count": 0,
            "reconciled_stop": True,
            "workspace_sealed": True,
        },
        "classification": {
            "infrastructure_recovery_proof": "PASSED",
            "product_decision": "BOUNDED_SECOND_ITERATE_NOT_PROCEED",
            "infrastructure_failure": False,
            "durable_epic_launch": False,
            "relaunch_disposition": "REMAINING_PRODUCT_AND_SYSTEMIC_HARDENING_DEFERRED_TO_FOLLOW_UP_NONBLOCKING",
        },
        "follow_up_tasks": [
            {
                "id": "attempt-16-product-gate-iterate-hardening",
                "owner_milestone": "f2-admission-model-effect-release-closure",
                "status": "DEFERRED_POST_RELAUNCH_NONBLOCKING",
                "acceptance": "PRESERVE_BOTH_ITERATE_GATE_RESULTS_AND_RESOLVE_THEIR_PRODUCT_ACTIONS_BEFORE_ANY_FUTURE_PROCEED_CLAIM",
            },
            {
                "id": "attempt-16-broader-systemic-hardening",
                "owner_milestone": "f1-owner-storage-recovery-hardening",
                "status": "DEFERRED_POST_RELAUNCH_NONBLOCKING",
                "acceptance": "COMPLETE_THE_EXISTING_STORAGE_RESIDENT_NOTIFICATION_AND_RECOVERY_TASKS_WITHOUT_RECLASSIFYING_ATTEMPT_16_OR_BLOCKING_RELAUNCH",
            },
        ],
    }:
        raise ContractError("attempt 16 exact terminal infrastructure-recovery proof drift")


def _validate_v3_relaunch_precursor(custody: dict[str, Any]) -> None:
    precursor = custody.get("v3_relaunch_precursor")
    if precursor != {
        "schema": "arnold.critique_ledger.v3_relaunch_precursor.v1",
        "status": "CONTAINED_ACTIVE_RUNTIME_BINDING_BLOCKER_NOT_DURABLE_LAUNCH",
        "identity": {
            "session": "critique-ledger-accountability-v3-20260803",
            "workspace": "/workspace/critique-ledger-accountability-v3-20260803/Arnold",
            "spec": "/workspace/critique-ledger-accountability-v3-20260803/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml",
            "initiative_revision": "0bb0c0b74e6b1913d39b51f33559b2f5127f1886",
            "isolated_runtime_revision": "a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
        },
        "bootstrap_pin": {
            "status": "RESOLVED_BY_FULL_SHA_REPIN_AND_FRESH_RETRY",
            "rejected_value": "0bb0c0b74e",
            "rejected_reason": "intended_initiative_revision_unpinned",
            "rejected_before_init": True,
            "accepted_value": "0bb0c0b74e6b1913d39b51f33559b2f5127f1886",
            "retry_cloud_chain_exit_code": 0,
            "retry_session_alive": True,
            "retry_advanced_past_init": True,
            "retry_plan": "cl2-wbc-backed-ledger-20260803-1313",
            "retry_plan_state": "initialized",
        },
        "runtime_binding_observation": {
            "editable_root": "/workspace/runtime-candidates/arnold-a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
            "editable_revision": "a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
            "import_root": "/workspace/runtime-candidates/arnold-c7bcb06af536acfe759c1b31a785afc19afe92d4",
            "source_revision": "c7bcb06af536acfe759c1b31a785afc19afe92d4",
            "classification": "HARD_NO_GO_SPLIT_RUNTIME_TUPLE",
            "cause": "CLOUD_HOT_ENV_ORDERING_OVERRODE_THE_VERIFIED_PINNED_RUNTIME_IMPORT_SOURCE_AFTER_EDITABLE_BINDING",
            "trusted_execution": False,
        },
        "containment": {
            "action": "REDEPLOY_SAME_ISOLATED_COLLECTOR_TO_STOP_UNTRUSTED_RUN",
            "result": "SUCCEEDED",
            "durable_epic_launch": False,
            "resume_or_reuse_authority": "NONE",
        },
        "durable_relaunch_acceptance": {
            "requires": [
                "FULL_40_HEX_INITIATIVE_REVISION_PIN",
                "CLOUD_CHAIN_EXIT_ZERO",
                "SESSION_ALIVE",
                "ADVANCED_PAST_INIT",
                "EDITABLE_ROOT_EQUALS_IMPORT_ROOT",
                "EDITABLE_REVISION_EQUALS_SOURCE_REVISION",
                "IMPORT_ROOT_EQUALS_CONFIGURED_PINNED_RUNTIME_ROOT",
                "SOURCE_REVISION_EQUALS_CONFIGURED_PINNED_RUNTIME_REVISION",
                "POST_LAUNCH_STABILITY_OBSERVATION_PASSES",
            ],
            "forbids": [
                "SUCCESS_FROM_EXIT_CODE_ALONE",
                "SUCCESS_FROM_ALIVE_OR_ADVANCED_ALONE",
                "SPLIT_EDITABLE_AND_IMPORT_RUNTIME_TUPLE",
                "REUSE_OF_THE_INITIALIZED_UNTRUSTED_PLAN",
            ],
            "current_result": "NOT_ACCEPTED_RELAUNCH_BLOCKED_PENDING_FRESH_MATCHED_RUNTIME_RETRY",
        },
        "evidence": [
            {
                "operator_local_path": "/private/tmp/critique-v3-launch2.out",
                "sha256": "417e90bb0e0acc1e7379631e546ae35a22c2575f2aacec59d4407ee539895670",
                "proves": "SHORT_PIN_REJECTED_BEFORE_INIT",
            },
            {
                "operator_local_path": "/private/tmp/critique-v3-launch3.out",
                "sha256": "16fe3246fd9adcc502be38b8291216db0b1d1530eacfa5dc019cd5971340adc9",
                "proves": "FULL_SHA_RETRY_EXIT_ZERO_ALIVE_AND_ADVANCED",
            },
            {
                "operator_local_path": "/private/tmp/critique-v3-status-after.json",
                "sha256": "96959af534d7ed4aaab8e07edffd10531a262ef8550fa1282d1568bcf323d1b9",
                "proves": "INITIALIZED_PLAN_AND_SPLIT_RUNTIME_TUPLE",
            },
            {
                "operator_local_path": "/private/tmp/critique-v3-redeploy-stop.json",
                "sha256": "146c86dfd7039a67cc28e666348d5274722d5dc9e711755587a2cf9721c95613",
                "proves": "CONTAINMENT_REDEPLOY_SUCCEEDED",
            },
        ],
        "ownership": {
            "phase": "T6.2_PRE_F0_DURABLE_RELAUNCH_PRECURSOR",
            "f1_f2_deferred_obligations_changed": False,
            "rule": "FIX_AND_PROVE_A_FRESH_MATCHED_RUNTIME_RETRY_BEFORE_F0_ADMISSION",
        },
    }:
        raise ContractError("v3 relaunch precursor or matched-runtime acceptance drift")


def _validate_attempt_14_outcome_and_runtime_contract(custody: dict[str, Any]) -> None:
    tasks = custody.get("prelaunch_contract_tasks")
    if tasks != [{
        "id": "custody-v3-to-v4-semantic-migration",
        "status": "REQUIRED_BEFORE_FOLLOW_UP_LAUNCH",
        "source_schema": "arnold.critique_ledger.unfinished_work_custody.v3",
        "target_schema": "arnold.critique_ledger.unfinished_work_custody.v4",
        "scope": ["completion_receipt_producer", "finite_canary_receipt_validator", "stable_exit_receipt_validator", "fresh_clone_reconstruction"],
        "acceptance": "ALL_PRODUCERS_AND_VALIDATORS_BIND_V4_AND_REJECT_V3_WITH_REGRESSION_TESTS",
        "completion_evidence": None,
    }]:
        raise ContractError("custody v3-to-v4 migration task drift")
    outcome = custody.get("attempt_14_outcome_contract")
    if (
        not isinstance(outcome, dict)
        or outcome.get("status") != "TERMINAL_FAILED_MISCLASSIFIED_NOT_ACCEPTED"
        or outcome.get("actual_branch") != "terminal_nonproceed"
    ):
        raise ContractError("attempt 14 immutable outcome contract drift")
    passed = outcome.get("pass")
    terminal = outcome.get("terminal_nonproceed")
    if (
        not isinstance(passed, dict)
        or passed.get("f0_disposition") != "ELIGIBLE_AFTER_INDEPENDENT_CONTENT_ADDRESSED_VERIFICATION"
        or passed.get("requires") != ["FINALIZED", "EXACT_B44_SOURCE_TREE_IMAGE", "SUCCESSOR_STOPPED", "RUNTIME_ABSENCE", "STABLE_EXIT_RECEIPT", "PUSHED_CUSTODY", "FRESH_CLONE_RECONSTRUCTION"]
        or not isinstance(terminal, dict)
        or terminal.get("receipt") != "DISTINCT_TERMINAL_NONPROCEED_EXIT_AND_CUSTODY_RECEIPT"
        or terminal.get("later_attempt") != "ATTEMPT_15_HAS_NEW_EXPLICIT_A15_B15_AUTHORITY"
        or "F0_AUTHORITY" not in terminal.get("forbids", [])
    ):
        raise ContractError("attempt 14 PASS versus terminal non-PROCEED branch drift")
    successor = custody.get("attempt_15_outcome_contract")
    if successor != {
        "status": "TERMINAL_INFRASTRUCTURE_FAILURE_NOT_ACCEPTED",
        "actual_branch": "infrastructure_failure",
        "infrastructure_failure": {
            "requires": [
                "EXACT_EXECUTED_PREFIX", "EXACT_RECEIPT", "TERMINAL_STOP",
                "SEALED_WORKSPACE", "CAPACITY_ROOT_CAUSE_CUSTODY",
            ],
            "forbids": [
                "SUCCESS_COMPLETION_RECEIPT", "FINALIZED",
                "STABLE_EXIT_ACCEPTANCE", "ACCEPTED_SUCCESSOR",
                "RUNNABLE_REF", "F0_AUTHORITY", "RETRY_AUTHORITY",
            ],
            "retry": "ONLY_AFTER_CAPACITY_ROOT_CLEANUP_AND_NEW_EXPLICIT_AUTHORITY",
            "successor_authority": "NONE",
        },
    }:
        raise ContractError("attempt 15 infrastructure failure contract drift")
    recovery = custody.get("attempt_16_outcome_contract")
    if recovery != {
        "status": "INFRASTRUCTURE_RECOVERY_PASSED_PRODUCT_GATE_NOT_PROCEED",
        "actual_branch": "product_gate_not_proceed",
        "requires": [
            "EXACT_V3_RECEIPT", "SEVEN_ZERO_RETURN_PHASES",
            "TWO_ITERATE_GATE_ATTEMPTS", "COMPLETE_DISPATCH_INTEGRITY",
            "RECONCILED_TERMINAL_STOP", "SEALED_WORKSPACE",
        ],
        "forbids": [
            "INFRASTRUCTURE_FAILURE_CLASSIFICATION", "PRODUCT_PROCEED_CLAIM",
            "FINALIZED_CLAIM", "DURABLE_EPIC_LAUNCH_CLAIM",
        ],
        "relaunch": "NOT_BLOCKED_BY_DEFERRED_PRODUCT_OR_BROADER_SYSTEMIC_HARDENING",
        "future_execution": "REQUIRES_FRESH_EXPLICIT_AUTHORITY",
    }:
        raise ContractError("attempt 16 product non-PROCEED outcome contract drift")
    runtime = custody.get("validator_runtime_binding")
    if runtime != {
        "required_command": "PYTHONPATH=. python .megaplan/initiatives/critique-ledger-post-relaunch-completion/validate_contract.py",
        "repository_root": ".",
        "imported_module": "arnold_pipelines.megaplan.chain.spec",
        "expected_relative_path": "arnold_pipelines/megaplan/chain/spec.py",
        "foreign_worktree_import": "HARD_NO_GO",
    }:
        raise ContractError("validator runtime binding drift")
    imported = Path(load_spec.__code__.co_filename).resolve()
    expected_import = (ROOT / runtime["expected_relative_path"]).resolve()
    if Path.cwd().resolve() != ROOT or os.environ.get("PYTHONPATH") != "." or imported != expected_import:
        raise ContractError("validator must run from this repository with PYTHONPATH=.; foreign import root rejected")
    availability = custody.get("resident_availability_follow_up")
    if not isinstance(availability, dict) or availability.get("observation") != {
        "interaction": "/whats-cooking",
        "observed_local_time": "2026-08-03T11:42:00+02:00",
        "failure": "DISCORD_RESIDENT_OFFLINE",
        "production_container": "EXITED_ENOSPC",
        "restart_attempts": "FAILED_BEFORE_DISCORD_CONNECT",
        "resident_event_at_observation": False,
        "handler_ordering": "INTERACTION_DEFER_PRECEDES_STATUS_COLLECTION",
        "ack_ordering_ruled_out": True,
        "attempt_14_started_minutes_later": 27,
        "attempt_14_discord_token_present": False,
        "attempt_14_resident_present": False,
        "causal_attribution_to_canary": "NOT_ESTABLISHED_AND_MUST_NOT_BE_CLAIMED",
    }:
        raise ContractError("resident availability incident fact drift")
    tasks = availability.get("tasks")
    expected_tasks = [
        (
            "resident-liveness-supervision",
            "INJECTED_RESIDENT_EXIT_IS_DETECTED_AND_RECOVERED_THROUGH_ONE_BOUNDED_SAFE_RESTART_WITH_RECEIPTS",
        ),
        (
            "capacity-triggered-safe-recovery",
            "ENOSPC_BLOCKS_RESTART_LOOP_PERFORMS_BOUNDED_RECLAIM_AND_RESTARTS_ONLY_AFTER_ACCEPTED_CAPACITY_PROOF",
        ),
        (
            "interaction-availability-monitoring",
            "SYNTHETIC_DISCORD_INTERACTION_DETECTS_DEFER_OR_RESPONSE_UNAVAILABILITY_INDEPENDENTLY_OF_STATUS_COLLECTION",
        ),
        (
            "deduplicated-outage-alert",
            "DURABLE_INCIDENT_KEY_DEDUPE_EMITS_EXACTLY_ONE_TERMINAL_MANUAL_REVIEW_ALERT_PER_INCIDENT_ACROSS_WATCHDOG_RETRIES_WITH_A_SEPARATE_RECOVERY_TRANSITION",
        ),
    ]
    if (
        availability.get("schema") != "arnold.critique_ledger.resident_availability_follow_up.v1"
        or not isinstance(tasks, list)
        or [
            (row.get("id"), row.get("acceptance"))
            for row in tasks
            if isinstance(row, dict)
        ] != expected_tasks
        or any(row.get("owner_milestone") != "f1-owner-storage-recovery-hardening" for row in tasks)
    ):
        raise ContractError("resident availability follow-up task drift")


def _validate_storage_root_cause_follow_up(custody: dict[str, Any]) -> None:
    storage = custody.get("storage_root_cause_follow_up")
    if not isinstance(storage, dict):
        raise ContractError("storage root-cause follow-up missing")
    if (
        storage.get("schema") != "arnold.critique_ledger.storage_root_cause_follow_up.v1"
        or storage.get("status") != "MAJOR_ROOT_CAUSE_CONFIRMED_RETRY_BLOCKED"
        or storage.get("post_attempt_15_capacity") != {
            "free_bytes": 1484693504,
            "hard_floor_bytes": 1611661312,
            "shortfall_bytes": 126967808,
            "admission": "FAILED_BELOW_HARD_FLOOR",
        }
        or storage.get("read_only_inventory") != {
            "subject": "PRESERVED_PRODUCTION_PREDECESSOR_WRITABLE_SNAPSHOT_AND_CONTAINER",
            "total_size_approx_gb": "389.927",
            "tmp_size_approx_gb": "388.813",
            "tmp_pattern": "arnold-repair-loop.*",
            "typical_file_size_bytes": 395629,
            "progress_auditor_recursive_copy_count": 1156578,
            "progress_auditor_recursive_logical_bytes": 387889659906,
            "mutation_performed": False,
        }
        or storage.get("root_cause") != {
            "finding": "PROGRESS_AUDITOR_INSTALLED_SOURCE_SNAPSHOT_RECURSION",
            "mechanism": [
                "INSTALLED_SOURCE_TRAMPOLINE_PRECEDES_SNAPSHOT_GUARD",
                "SNAPSHOT_EXECS_SOURCE",
                "SOURCE_SEES_ACTIVE_PATH_MISMATCH_AND_CREATES_ANOTHER_SNAPSHOT",
                "LATER_CLEANUP_TRAP_IS_OVERWRITTEN",
            ],
            "consequences": [
                "HOST_ENOSPC", "DISCORD_RESIDENT_OUTAGE",
                "LIKELY_ATTEMPT_15_CODE_MODE_HOST_INSTABILITY",
            ],
            "certainty": {
                "auditor_recursion_to_disk_exhaustion_and_resident_crash": "CONFIRMED",
                "auditor_recursion_to_attempt_15_sigtrap_closed_stdout": "LIKELY_NOT_PROVEN_EXCLUSIVE",
            },
        }
        or storage.get("notification_watchdog_incident") != {
            "finding": "TERMINAL_MANUAL_REVIEW_INCIDENT_REEMITTED_WITHOUT_DURABLE_INCIDENT_KEY_DEDUPE",
            "owner": "NOTIFICATION_WATCHDOG_PATH",
            "repeated_discord_messages": True,
            "progress_auditor_sent_messages": False,
        }
        or storage.get("diagnostic_fixer") != {
            "launch": "FAILED",
            "failure": "PROVENANCE_VALIDATION_FAILED",
            "independent_of_notification_reemission": True,
        }
        or storage.get("safe_reclaim_receipt") != {
            "container_id": "277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab",
            "deleted_count": 1156578,
            "deleted_logical_bytes": 387889659906,
            "remaining_count": 0,
            "free_bytes_after": 390136713216,
            "predecessor_preserved": True,
            "workspace_preserved": True,
        }
        or storage.get("retry_gate") != {
            "status": "INFRASTRUCTURE_RECOVERY_PROVEN_REMAINING_HARDENING_NONBLOCKING",
            "satisfied": [
                "RECEIPTED_SAFE_RECLAIM_PRESERVING_ALL_WORKSPACES",
                "FREE_BYTES_AT_OR_ABOVE_RESERVED_HARD_FLOOR",
                "FRESH_EXPLICIT_ATTEMPT_16_AUTHORITY",
                "ATTEMPT_16_INFRASTRUCTURE_RECOVERY_PROOF_PASSED",
            ],
            "deferred_nonblocking_follow_up": [
                "PRODUCT_GATE_ITERATE_HARDENING",
                "BROADER_STORAGE_RESIDENT_NOTIFICATION_AND_RECOVERY_HARDENING",
            ],
        }
    ):
        raise ContractError("attempt 15 capacity or storage root-cause custody drift")
    tasks = storage.get("permanent_tasks")
    expected_tasks = [
        (
            "bounded-repair-temp-lifecycle",
            "INSTALLED_SOURCE_TRAMPOLINE_CHECKS_THE_SNAPSHOT_GUARD_BEFORE_EXEC_AND_EVERY_SNAPSHOT_HAS_FINALLY_CLEANUP_ON_SUCCESS_FAILURE_TIMEOUT_SIGNAL_AND_CANCELLATION_WITH_NO_OVERWRITTEN_TRAP",
        ),
        (
            "repair-loop-singleton-attempt-cap",
            "ONE_REPAIR_LOOP_OWNER_PER_SUBJECT_AND_A_DURABLE_ATTEMPT_CAP_PREVENT_UNBOUNDED_REDISPATCH_OR_TEMP_CREATION",
        ),
        (
            "disk-budget-reserved-headroom",
            "REPAIR_AND_RESIDENT_PATHS_ENFORCE_A_DISK_BUDGET_AND_PRESERVE_RESERVED_HEADROOM_ABOVE_THE_HARD_FLOOR",
        ),
        (
            "pre-model-tool-capacity-trip",
            "EVERY_MODEL_OR_TOOL_PHASE_TRIPS_FAIL_CLOSED_BEFORE_DISPATCH_WHEN_CAPACITY_IS_BELOW_THE_RESERVED_THRESHOLD",
        ),
        (
            "receipted-workspace-preserving-safe-reclaim",
            "SAFE_RECLAIM_IS_BOUNDED_RECEIPTED_AND_PROVES_ALL_HISTORICAL_AND_ACTIVE_WORKSPACES_ARE_PRESERVED_BYTE_FOR_BYTE",
        ),
        (
            "resident-only-recovery-surface",
            "RESIDENT_RECOVERY_USES_A_DEDICATED_BOUNDED_SURFACE_WITH_NO_GENERAL_REPAIR_LOOP_NOTIFICATION_OR_CANARY_RETRY_AUTHORITY",
        ),
    ]
    if (
        not isinstance(tasks, list)
        or [
            (task.get("id"), task.get("acceptance"))
            for task in tasks
            if isinstance(task, dict)
        ] != expected_tasks
        or any(
            task.get("owner_milestone") != "f1-owner-storage-recovery-hardening"
            for task in tasks
            if isinstance(task, dict)
        )
    ):
        raise ContractError("storage root-cause permanent task drift")


def _validate_live_canary_attempts(custody: dict[str, Any]) -> None:
    attempts = custody.get("live_canary_attempts")
    if not isinstance(attempts, list) or len(attempts) != 5:
        raise ContractError("live canary attempt history is incomplete")
    expected_b27 = {
        "id": "B27-live-attempt-1",
        "candidate": {"commit": B27_PASS["commit"], "tree": B27_PASS["tree"]},
        "status": "failed",
        "terminal_state": "failed",
        "run_receipt": {
            "path": None,
            "sha256": "710707648e66e37b2c57684faa135eb324f36b163796d45210763657ad6d4e17",
            "digest": "ac95bf39a39c946b73a56a08625d8d15e57f8673764365c0d4ad3354826085bd",
            "status": "PATH_NOT_PROVIDED_IMPORT_REQUIRED",
        },
        "dispatch_integrity": {
            "status": "partial",
            "start_dispatches": [
                {"phase": "plan", "count": 1, "provider": "Codex", "model": "gpt-5.6-sol", "reasoning": "high"}
            ],
            "terminal_dispatch_count": 0,
            "terminal_dispatch_absence_reason": "finite_model_boundary_failed",
        },
        "root_evidence": {
            "source": "plan_v1_raw",
            "observed_excerpt": (
                "finite model boundary failed: CliError:finite-model runtime contains a special or linked object | "
                "CliError:source object is not trusted-owner non-writable: "
                ".../.zero-recovery-plan-worker-output.json | "
                "CliError:plan artifact permissions are unsafe..."
            ),
            "actual_output": {"empty": True, "uid": 65532, "gid": 65532, "mode": "0600"},
            "primary_cause": "REAL_CODEX_CREATED_AF_UNIX_IPC_SOCKET_UNDER_ISOLATED_CODEX_HOME_OFFLINE_FAKE_DID_NOT_MODEL_IT",
            "boundary_effect": "RUNTIME_VALIDATOR_REJECTED_SOCKET_BEFORE_OUTPUT_RECLAIM",
            "cascading_errors": ["OUTPUT_OWNER_NONWRITABLE_REJECTION", "PLAN_ARTIFACT_PERMISSION_REJECTION"],
        },
        "container": {
            "id_prefix": "c6289bc3",
            "full_id": None,
            "stopped": True,
            "exit_code": 137,
            "oom_killed": False,
            "reconciled_stop": True,
        },
        "workspace": {
            "path": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-20260802",
            "owner": "root",
            "mode": "0700",
            "sealed": True,
            "preserved": True,
        },
        "background_effects": {"loop_started": False, "notifications_sent": False},
        "reconciliation": "TERMINAL_RECONCILED_REMOTE_RECEIPT_IMPORT_PENDING",
        "repair": A28_REPAIR,
    }
    expected_b28 = {
        "id": "B28-live-attempt-2",
        "candidate": {"commit": B28_PASS["commit"], "tree": B28_PASS["tree"]},
        "status": "failed",
        "terminal_state": "failed",
        "run_receipt": {
            "path": None,
            "sha256": "1f39fc0bc54958b127016b08a0778dece85f2900e30defbd40dfc39d6de00dad",
            "digest": "2f682fe966d45dfc71527284259cea98e34876d79ac49797603261f5aee102cf",
            "status": "PATH_NOT_PROVIDED_IMPORT_REQUIRED",
        },
        "dispatch_integrity": {"status": "partial", "phase": "plan", "start_dispatch_count": 1},
        "root_evidence": {
            "source": "plan_v1_raw",
            "exact_primary_raw": (
                "finite-model runtime contains a forbidden or linked object: "
                "/run/.../home/.codex/tmp/arg0/codex-arg0ZLod2y/codex-execve-wrapper "
                "mode=0o120000 nlink=1"
            ),
            "primary_cause": "REAL_CODEX_CREATED_TEMPORARY_ARG0_WRAPPER_SYMLINK_OFFLINE_FAKE_DID_NOT_MODEL_IT",
            "cascading_errors": ["OUTPUT_OWNER_NONWRITABLE_REJECTION", "PLAN_ARTIFACT_PERMISSION_REJECTION"],
        },
        "container": {
            "name": "megaplan-cloud-agent-finite-canary-2",
            "id_prefix": "84a022",
            "full_id": None,
            "stopped": True,
            "exit_code": 137,
            "oom_killed": False,
            "reconciled_stop": True,
        },
        "workspace": {
            "path": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-2-20260803",
            "owner": "root",
            "mode": "0700",
            "sealed": True,
            "preserved": True,
        },
        "reconciliation": "TERMINAL_RECONCILED_REMOTE_RECEIPT_IMPORT_PENDING",
        "repair": A29_REPAIR,
    }
    expected_b29 = {
        "id": "B29-live-attempt-3",
        "candidate": {"commit": B29_PASS["commit"], "tree": B29_PASS["tree"]},
        "status": "failed",
        "terminal_state": "failed",
        "run_receipt": {
            "path": None,
            "sha256": "81295354cb68fe743c952f64c332d4d34a883daed6cacc68062904ad7584cb11",
            "digest": "243d9ee2d979a296235983faa6058e94142e674b3c12045f1d44fd229e5df89c",
            "status": "PATH_NOT_PROVIDED_IMPORT_REQUIRED",
        },
        "phase_result": {"phase": "plan", "exit": "nonzero", "classification_progress": "SOCKET_AND_SYMLINK_ACCEPTED"},
        "root_evidence": {
            "source": "plan_v1_raw",
            "exact_primary_raw": (
                "finite model boundary failed: PermissionError:[Errno 13] Permission denied: "
                "'/run/.../home/.codex/tmp/arg0/codex-arg0O2caQy/codex-execve-wrapper'"
            ),
            "primary_cause": "RECLAIM_UNLINK_ATTEMPTED_WHILE_PARENT_REMAINED_MODEL_OWNED_0700",
            "trusted_root": {"dac_override": False, "absence_intentional": True},
        },
        "container": {
            "name": "megaplan-cloud-agent-finite-canary-3",
            "id_prefix": "940c",
            "full_id": None,
            "stopped": True,
            "oom_killed": False,
            "reconciled_stop": True,
        },
        "workspace": {
            "path": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-3-20260803",
            "sealed": True,
        },
        "reconciliation": "TERMINAL_RECONCILED_REMOTE_RECEIPT_IMPORT_PENDING",
        "repair": A30_REPAIR,
    }
    expected_b30 = {
        "id": "B30-live-attempt-4",
        "candidate": {"commit": B30_PASS["commit"], "tree": B30_PASS["tree"]},
        "status": "failed",
        "terminal_state": "failed",
        "run_receipt": {
            "path": None,
            "sha256": "c4aa925f98ffc5a41992f2347366e6d3175e089b6982708a0e6cac0a5b021080",
            "digest": "482910834d106e6ee4281cb930918d7f793d17b4a1140a63a9c1b796fcc662ee",
            "status": "PATH_NOT_PROVIDED_IMPORT_REQUIRED",
        },
        "root_evidence": {"failure": "SCHEMA_ROOT_0600_READ_DENIAL"},
        "container": {"name": "megaplan-cloud-agent-finite-canary-4", "stopped": True, "reconciled_stop": True},
        "workspace": {"path": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-4-20260803"},
        "reconciliation": "TERMINAL_RECONCILED_REMOTE_RECEIPT_IMPORT_PENDING",
        "repair": SCHEMA_ACCESS_RECOVERY_HISTORY[0]["repair"],
    }
    expected_b35 = {
        "id": "B35-live-attempt-9",
        "candidate": SCHEMA_ACCESS_RECOVERY_HISTORY[4]["launch"],
        "status": "terminated_by_overlapping_status_poll",
        "terminal_state": "failed",
        "run_receipt": {"path": None, "sha256": None, "digest": None, "status": "ABSENT"},
        "phase_evidence": {
            "init_receipt_sha256": "bec8be741aee9444926843a251cd53027de80a5c5a9eac010219d4f841c85623",
            "plan_started_sha256": "de51ef7812468e8da192e2fed7e404647eec783d7f33e607a9e14a1858a347c2",
            "dispatch_ledger_sha256": "f2d24e7bf3640145dcc15d70361ccb13469318acdec3b06e74b226b613f52bc7",
            "output": "EMPTY",
        },
        "container": {
            "name": "megaplan-cloud-agent-finite-canary-9",
            "id": "acf086d75ef2ffd678117e09236819d3387298112b522dbc0e98ed2e4e7e2381",
            "stopped": True,
            "exit_code": 137,
            "oom_killed": False,
            "restart_count": 0,
            "reconciled_stop": True,
        },
        "workspace": {
            "path": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-9-20260803",
            "sealed": True,
            "owner": "root",
            "mode": "0700",
            "transition_digest_prefix": "f513d54d",
            "transition_digest_full": None,
        },
        "timeline": {
            "status_began": "06:30:25.420",
            "docker_stop_sigterm": "06:30:26.882",
            "run_exited_137": "06:30:36.876",
        },
        "definitive_cause": "STATUS_POLL_OVERLAPPED_LIVE_RUN_AND_FINALLY_UNCONDITIONALLY_STOPPED_AND_RESEALED",
        "classification": "NOT_MODEL_OR_RUNTIME_FAILURE",
        "reconciliation": "TERMINAL_RECONCILED_NO_RUN_RECEIPT",
        "repair": SCHEMA_ACCESS_RECOVERY_HISTORY[5]["repair"],
    }
    if attempts[0] != expected_b27:
        raise ContractError("B27 live canary terminal binding drift")
    if attempts[1] != expected_b28:
        raise ContractError("B28 live canary terminal binding drift")
    if attempts[2] != expected_b29:
        raise ContractError("B29 live canary terminal binding drift")
    if attempts[3] != expected_b30:
        raise ContractError("B30 live canary terminal binding drift")
    if attempts[4] != expected_b35:
        raise ContractError("B35 live canary terminal binding drift")


def _validate_operation_reconciliation(*, require_live: bool) -> None:
    manifest_path = INITIATIVE / "evidence/operation-reconciliation-manifest.json"
    manifest = _load_json(manifest_path)
    if set(manifest) != {"schema", "status", "authority_rule", "independent_review", "operations"}:
        raise ContractError("operation reconciliation manifest has an inexact schema")
    if (
        manifest.get("schema") != "arnold.critique_ledger.operation_reconciliation_manifest.v1"
        or manifest.get("authority_rule") != "INTENTS_ARE_IMMUTABLE; EFFECTIVE_STATUS_IS_APPEND_ONLY; AMBIGUITY_IS_TERMINAL_NO_REDISPATCH"
    ):
        raise ContractError("operation reconciliation authority drift")
    review = manifest.get("independent_review")
    if not isinstance(review, dict) or set(review) != {"path", "sha256", "status"}:
        raise ContractError("operation reconciliation review schema drift")
    if review.get("status") == "PENDING":
        if review != {"path": None, "sha256": None, "status": "PENDING"}:
            raise ContractError("pending operation review fabricates evidence")
    elif (
        review.get("status") != "ACCEPTED"
        or not isinstance(review.get("path"), str)
        or not SHA256.fullmatch(str(review.get("sha256")))
    ):
        raise ContractError("operation reconciliation review is invalid")
    else:
        review_path = _repo_path(review["path"])
        if not review_path.is_file() or _sha256(review_path) != review["sha256"]:
            raise ContractError("operation reconciliation review hash mismatch")
    operations = manifest.get("operations")
    if not isinstance(operations, list) or len(operations) != len(OPERATION_IDS):
        raise ContractError("operation reconciliation has an inexact operation count")
    seen: list[str] = []
    edges: dict[str, str] = {}
    for row in operations:
        if not isinstance(row, dict) or set(row) != {
            "operation_id", "intent", "supersedes", "maximum_dispatches_by_effect",
            "terminal", "effective_status",
        }:
            raise ContractError("operation reconciliation row has an inexact schema")
        operation_id = row.get("operation_id")
        seen.append(operation_id)
        intent = row.get("intent")
        terminal = row.get("terminal")
        maxima = row.get("maximum_dispatches_by_effect")
        if (
            not isinstance(intent, dict)
            or set(intent) != {"path", "sha256", "authority_commit"}
            or not SHA256.fullmatch(str(intent.get("sha256")))
            or not re.fullmatch(r"[0-9a-f]{40}", str(intent.get("authority_commit")))
            or not isinstance(maxima, list)
            or not maxima
            or any(value != 1 for value in maxima)
            or not isinstance(terminal, dict)
            or set(terminal) != {"path", "sha256", "status", "dispatch_counts"}
        ):
            raise ContractError(f"invalid operation reconciliation row: {operation_id!r}")
        intent_path = _repo_path(str(intent.get("path")))
        intent_payload = _load_json(intent_path)
        effects = intent_payload.get("admitted_effects_in_order")
        if effects is None:
            effects = [intent_payload.get("admitted_effect")]
        expected_supersedes = intent_payload.get("supersedes_failed_operation")
        if (
            intent_payload.get("operation_id") != operation_id
            or intent_payload.get("status") != "AUTHORIZED_PENDING_SINGLE_DISPATCH"
            or _sha256(intent_path) != intent.get("sha256")
            or not isinstance(effects, list)
            or len(effects) != len(maxima)
            or any(not isinstance(effect, dict) or effect.get("maximum_dispatches") != 1 for effect in effects)
            or row.get("supersedes") != expected_supersedes
        ):
            raise ContractError(f"operation intent binding drift: {operation_id}")
        if expected_supersedes is not None:
            edges[operation_id] = expected_supersedes
        if row.get("effective_status") == "PENDING_RECONCILIATION":
            if terminal != {"path": None, "sha256": None, "status": "PENDING_RECONCILIATION", "dispatch_counts": None}:
                raise ContractError(f"pending operation fabricates terminal evidence: {operation_id}")
        else:
            counts = terminal.get("dispatch_counts")
            if (
                row.get("effective_status") not in {"COMPLETED", "FAILED_NO_EFFECT", "AMBIGUOUS_CONSUMED_NO_REDISPATCH"}
                or terminal.get("status") != row.get("effective_status")
                or not isinstance(counts, list)
                or len(counts) != len(maxima)
                or any(not isinstance(count, int) or count < 0 or count > limit for count, limit in zip(counts, maxima))
                or not isinstance(terminal.get("path"), str)
                or not SHA256.fullmatch(str(terminal.get("sha256")))
            ):
                raise ContractError(f"invalid terminal operation outcome: {operation_id}")
            terminal_path = _repo_path(terminal["path"])
            if not terminal_path.is_file() or _sha256(terminal_path) != terminal["sha256"]:
                raise ContractError(f"terminal operation receipt hash mismatch: {operation_id}")
    if seen != OPERATION_IDS or len(seen) != len(set(seen)) or edges != OPERATION_SUPERSESSION:
        raise ContractError("operation set/order/supersession drift")
    for start in edges:
        visited: set[str] = set()
        current = start
        while current in edges:
            if current in visited:
                raise ContractError("operation supersession cycle")
            visited.add(current)
            current = edges[current]
    if require_live:
        if manifest.get("status") != "ACCEPTED" or review.get("status") != "ACCEPTED":
            raise ContractError("operation reconciliation is not independently accepted")
        if any(row.get("effective_status") == "PENDING_RECONCILIATION" for row in operations):
            raise ContractError("operation reconciliation still has pending outcomes")
    elif manifest.get("status") not in {"PENDING_REMOTE_RECEIPT_IMPORT_AND_INDEPENDENT_RECONCILIATION", "ACCEPTED"}:
        raise ContractError("invalid operation reconciliation status")


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
    if (
        route.get("schema") != "arnold.critique_ledger.finite_canary_operational_route.v2"
        or route.get("launch_rule")
        != "Every binding is conjunctive and fail-closed; the base route alone has no launch authority. Exit zero, alive and advanced are insufficient unless the editable/import roots and revisions match the configured pinned runtime in a post-launch stability observation."
    ):
        raise ContractError("route schema or matched-runtime launch rule drift")
    bindings = route.get("additional_bindings")
    if not isinstance(bindings, dict):
        raise ContractError("route additional_bindings missing")
    custody_binding = bindings.get("custody_contract")
    if (
        not isinstance(custody_binding, dict)
        or custody_binding.get("required_sections") != [
            "prelaunch_release_gates", "trusted_host_control_state_contract",
            "capacity_cut.prelaunch", "isolation_receipt_contract",
            "model_evidence_contract", "operational_substrates", "deferred_obligations",
            "attempt_14_prelaunch", "prelaunch_contract_tasks",
            "attempt_14_outcome_contract", "attempt_15_prelaunch",
            "attempt_15_outcome_contract", "attempt_16_terminal",
            "attempt_16_outcome_contract", "v3_relaunch_precursor",
            "validator_runtime_binding",
            "resident_availability_follow_up", "storage_root_cause_follow_up",
        ]
    ):
        raise ContractError("route custody binding drift")
    if bindings.get("exact_attempt_14_candidate") != {
        "implementation_commit": "a15e87adea1fa78e90008422f42bc79ae60dff13",
        "implementation_tree": "63a75d9333e3fa69c9a039846595d3dd4d3cc4b3",
        "manifest_commit": "006895e8d66812dec5e85d26b32635af21ca21c7",
        "manifest_tree": "8d70cc79bc8f5a79a60be282bcc22122109c7f83",
        "production_image_id": "sha256:209a64de1f321b5ec49e8d6e6748187f790099a6fe8a68696352a5488bc7ffa6",
        "outcome": "TERMINAL_FAILED_MISCLASSIFIED_NOT_ACCEPTED",
        "run_receipt_digest": "59f0d1712bbd6f379d921f9662989a7a524b62e8509182041e08ba368e0abe0d",
        "run_receipt_file_sha256": "23f260ba72c0785401d4749132491beeac1bd2cf7c61cc386c7b29e980ecb3c0",
    }:
        raise ContractError("route B44 candidate drift")
    if bindings.get("exact_attempt_15_candidate") != {
        "implementation_commit": "8932873ba1c81d398cf42fb9879605d14d50cbb4",
        "implementation_tree": "7fdcf11dba38354645290314443c1de3c8b33bbb",
        "manifest_commit": "4f021cb70f3202dd90d599f8d710b626ba27b16b",
        "manifest_tree": "3777df403e9ae06cba75cf6fb6ac3b804f808723",
        "production_image_id": "sha256:ea1e66940e7445649b083b8d7acc896080526011f9bfc4a9e21b475046e1814a",
        "workspace": "/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-15-20260803",
        "container": "megaplan-cloud-agent-finite-canary-15",
        "outcome": "TERMINAL_INFRASTRUCTURE_FAILURE_NOT_ACCEPTED",
        "run_receipt_digest": "59bc8d659ca8ec59baa9da9051fcd7320199e6ffea12a97d3b7018694b266331",
        "run_receipt_file_sha256": "10eb82a07ca0829b585c4316413b76851665ac9b90ef93e051f94626f91a182a",
        "successor_authority": "NONE",
    }:
        raise ContractError("route A15/B15 candidate drift")
    if bindings.get("exact_attempt_16_candidate") != {
        "source_id": "B16",
        "source_commit": "fb5a394878bc900b189213a3de5dcc40169d8b7b",
        "source_tree": "a8f903a94e5029fa50c148df3289186dc4c39caf",
        "outer_status": "available",
        "receipt_schema": "arnold.megaplan.finite_canary_run_receipt.v3",
        "receipt_status": "passed",
        "terminal_state": "product_gate_not_proceed",
        "receipt_digest": "3a9925dbfcc0c901905db0265b48c062f051b16bdbb31b9f873c5e086eac08c0",
        "receipt_file_sha256": "1b4e1d013f444b3f3f2c3af1bb4938002e730f727a0be39834a2ca235fa592ba",
        "state_sha256": "4ef979066dfb3c822625de21ec52e95c7d25a42f185ea01970865d4b4116e525",
        "final_gate_sha256": "b8d6dcf366b04bde245890e1cb224c191f202101cb53dbb3fa59ca721c05d546",
        "outcome": "INFRASTRUCTURE_RECOVERY_PASSED_PRODUCT_GATE_NOT_PROCEED",
        "durable_epic_launch": False,
    }:
        raise ContractError("route B16 attempt-16 candidate drift")
    if bindings.get("custody_schema_migration") != {
        "task": "custody-v3-to-v4-semantic-migration",
        "status": "REQUIRED_BEFORE_FOLLOW_UP_LAUNCH",
        "source": "arnold.critique_ledger.unfinished_work_custody.v3",
        "target": "arnold.critique_ledger.unfinished_work_custody.v4",
    }:
        raise ContractError("route custody migration drift")
    if bindings.get("result_branch") != {
        "attempt_14": "TERMINAL_FAILED_MISCLASSIFIED_NOT_ACCEPTED",
        "attempt_15": "TERMINAL_INFRASTRUCTURE_FAILURE_NOT_ACCEPTED",
        "attempt_16": "INFRASTRUCTURE_RECOVERY_PASSED_PRODUCT_GATE_NOT_PROCEED",
        "durable_epic_launch": "NOT_PRODUCED",
        "relaunch": "NOT_BLOCKED_BY_DEFERRED_PRODUCT_OR_BROADER_SYSTEMIC_HARDENING",
        "future_execution": "REQUIRES_FRESH_EXPLICIT_AUTHORITY",
    }:
        raise ContractError("route terminal outcomes or successor authority drift")
    if bindings.get("durable_v3_relaunch_acceptance") != {
        "current_status": "BLOCKED_AFTER_CONTAINED_SPLIT_RUNTIME_RETRY",
        "bootstrap_pin_status": "FULL_SHA_REPIN_RESOLVED",
        "initiative_revision": "0bb0c0b74e6b1913d39b51f33559b2f5127f1886",
        "configured_runtime_root": "/workspace/runtime-candidates/arnold-a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
        "configured_runtime_revision": "a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
        "requires": [
            "FULL_40_HEX_INITIATIVE_REVISION_PIN",
            "CLOUD_CHAIN_EXIT_ZERO",
            "SESSION_ALIVE",
            "ADVANCED_PAST_INIT",
            "EDITABLE_ROOT_EQUALS_IMPORT_ROOT",
            "EDITABLE_REVISION_EQUALS_SOURCE_REVISION",
            "IMPORT_ROOT_EQUALS_CONFIGURED_PINNED_RUNTIME_ROOT",
            "SOURCE_REVISION_EQUALS_CONFIGURED_PINNED_RUNTIME_REVISION",
            "POST_LAUNCH_STABILITY_OBSERVATION_PASSES",
        ],
        "observed_rejected_runtime": {
            "editable_root": "/workspace/runtime-candidates/arnold-a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
            "editable_revision": "a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4",
            "import_root": "/workspace/runtime-candidates/arnold-c7bcb06af536acfe759c1b31a785afc19afe92d4",
            "source_revision": "c7bcb06af536acfe759c1b31a785afc19afe92d4",
        },
        "rejected_plan": "cl2-wbc-backed-ledger-20260803-1313",
        "rejected_plan_reuse": "FORBIDDEN",
        "next_attempt": "FRESH_RETRY_AFTER_HOT_ENV_ORDERING_FIX_AND_PRELAUNCH_TUPLE_PROOF",
    }:
        raise ContractError("route durable v3 relaunch runtime-binding acceptance drift")
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
    expected_preconditions = [
        (
            "chain_completed",
            ".megaplan/initiatives/critique-ledger/chain.yaml",
            True,
        ),
        ("git_tracked", ".megaplan/initiatives/critique-ledger", None),
        ("git_tracked", ".megaplan/initiatives/critique-ledger-post-relaunch-completion", None),
    ]
    preconditions = chain.get("launch_preconditions")
    if not isinstance(preconditions, list) or len(preconditions) != len(expected_preconditions):
        raise ContractError("chain launch precondition count drift")
    for row, (kind, target, require_manifest) in zip(preconditions, expected_preconditions):
        if not isinstance(row, dict) or row.get("kind") != kind:
            raise ContractError("chain launch precondition drift")
        if kind == "chain_completed":
            if row.get("chain") != target or row.get("require_manifest") is not require_manifest:
                raise ContractError("chain completion precondition drift")
        elif row.get("path") != target:
            raise ContractError("chain launch precondition path drift")
    milestones = chain.get("milestones")
    expected_labels = [
        "f0-finite-canary-handoff-admission",
        "f1-owner-storage-recovery-hardening",
        "f2-admission-model-effect-release-closure",
        "f2a-launch-profile-artifact-drift-containment",
        "f3-cl2-real-work-and-publication",
        "f4-cl3-cl5-epic-completion",
        "f5-product-release-and-deploy",
        "f6-production-acceptance",
        "f7-evidence-and-incident-closeout",
        "f8-seven-day-durability",
    ]
    if not isinstance(milestones, list) or [row.get("label") for row in milestones if isinstance(row, dict)] != expected_labels:
        raise ContractError("chain milestone order/set drift")
    if milestones[0].get("depends_on") not in (None, []) or milestones[1].get("depends_on") != [expected_labels[0]]:
        raise ContractError("F0/F1 dependency boundary drift")
    for index in range(2, len(milestones)):
        if milestones[index].get("depends_on") != [expected_labels[index - 1]]:
            raise ContractError("follow-up milestone dependency drift")
    if proof_map.get("f0-finite-canary-handoff-admission") != [
        "evidence/critique-ledger-recovery/T6.2/handoff-admission/completion-manifest.json"
    ]:
        raise ContractError("F0 proof map drift")
    f1_proofs = proof_map.get("f1-owner-storage-recovery-hardening", [])
    if "evidence/critique-ledger-recovery/T0.3/resident-availability/completion-manifest.json" not in f1_proofs:
        raise ContractError("resident availability proof map drift")
    if R5_REPAIR_CONTROL_EVIDENCE not in f1_proofs:
        raise ContractError("r5 repair-control incident proof map drift")
    if (
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + M11_ACCEPTANCE_GAP_EVIDENCE
        not in f1_proofs
    ):
        raise ContractError("M11 acceptance dependency-gap proof map drift")
    if (
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + ARTIFACT_ARCHIVAL_PROJECTION_CONTRACT
        not in f1_proofs
    ):
        raise ContractError("artifact archival/projection cleanup proof map drift")
    if (
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + ESCALATION_SIDECAR_PATH_CONTRACT
        not in f1_proofs
    ):
        raise ContractError("escalation sidecar path contract proof map drift")
    if (
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + M7_RUNTIME_REBIND_PROJECTION_EVIDENCE
        not in f1_proofs
    ):
        raise ContractError("M7 runtime-rebind projection evidence proof map drift")
    if (
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + CROSS_CONTAINER_LIVENESS_EVIDENCE
        not in f1_proofs
    ):
        raise ContractError("cross-container liveness evidence proof map drift")
    if (
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + FINALIZE_OUTPUT_HANDOFF_RETRY_CONTRACT
        not in f1_proofs
    ):
        raise ContractError("finalize output handoff/retry F1 proof map drift")
    if proof_map.get("f2a-launch-profile-artifact-drift-containment") != [
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        "provider-policy-execution-binding-contract.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        "provider-schema-dialect-family-contract.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/"
        + FINALIZE_OUTPUT_HANDOFF_RETRY_CONTRACT,
        "evidence/critique-ledger-recovery/F2A/"
        "provider-policy-execution-binding/completion-manifest.json",
        "evidence/critique-ledger-recovery/F2A/"
        "provider-schema-dialect-family/completion-manifest.json",
    ]:
        raise ContractError("F2A provider-policy/schema/binding proof map drift")
    if proof_map.get("finite-canary-stable-exit") != STABLE_EXIT_PROOFS:
        raise ContractError("stable-exit proof map drift")
    if proof_map.get("finite-canary-prelaunch-history") != [
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/custody-manifest.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/UNFINISHED_WORK.md",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/RUNBOOK.md",
    ]:
        raise ContractError("prelaunch history proof map drift")


def _validate_r5_repair_control_incident(incident: dict[str, Any]) -> None:
    if (
        incident.get("schema") != "arnold.critique_ledger.r5_repair_control_incident.v1"
        or incident.get("authority") != "read_only_cloud_and_source_audit"
        or incident.get("session") != "critique-ledger-accountability-v3-r5-20260803"
        or incident.get("plan") != "cl2-wbc-backed-ledger-20260803-1357"
    ):
        raise ContractError("r5 repair-control incident identity drift")
    phase = incident.get("phase_failure")
    messages = phase.get("observed_attempt_messages") if isinstance(phase, dict) else None
    if (
        not isinstance(phase, dict)
        or phase.get("recorded_kind") != "deterministic_phase_failure"
        or phase.get("retry_strategy") != "repair_phase_contract"
        or not SHA256.fullmatch(str(phase.get("failure_fingerprint") or ""))
        or not isinstance(messages, list)
        or len(messages) != 3
        or len(set(messages)) != 3
        or phase.get("classification")
        != "FALSE_DETERMINISTIC_LATCH_DISTINCT_CURRENT_ERRORS_WERE_MASKED_BY_PRIOR_FAILURE_PRECEDENCE"
        or phase.get("per_check_artifact_observation")
        != "ALL_NINE_CURRENT_PER_CHECK_AND_PRODUCER_V2_PAYLOADS_PASS_VALIDATE_CRITIQUE_CHECKS"
    ):
        raise ContractError("r5 phase-failure incident evidence drift")
    request = incident.get("repair_request")
    if (
        not isinstance(request, dict)
        or request.get("request_id")
        != "734816b31530e56a4835cc54c265e5712b247860a1de269b598ed93faf7b1d92"
        or request.get("claim_owner_pid") != 1310
        or request.get("claim_owner_pid_observation") != "DEAD"
        or request.get("managed_manifest_observation") != "ABSENT"
        or request.get("active_claim_managed_binding") != "ABSENT"
        or request.get("classification")
        != "PHANTOM_L1_DISPATCH_NO_MANAGED_REPAIR_PROCESS_OR_MANIFEST_WAS_ESTABLISHED"
    ):
        raise ContractError("r5 phantom repair-attempt evidence drift")
    goal = incident.get("repair_goal")
    immediate = incident.get("immediate_root_branch")
    follow_up = incident.get("follow_up_ownership")
    if (
        not isinstance(goal, dict)
        or goal.get("status") != "active"
        or goal.get("terminal") is not False
        or goal.get("owner_manifest_observation") != "ABSENT"
        or not isinstance(immediate, dict)
        or immediate.get("status") != "IN_PROGRESS_NOT_ACCEPTED_NOT_DEPLOYED"
        or immediate.get("completion_rule")
        != "NO_ITEM_IS_COMPLETE_UNTIL_COMMITTED_INTEGRATED_INSTALLED_AND_PROVEN_AGAINST_THE_EXACT_R5_FIXTURE"
        or not isinstance(follow_up, dict)
        or follow_up.get("milestone") != "f1-owner-storage-recovery-hardening"
    ):
        raise ContractError("r5 immediate/deferred repair custody drift")


def _validate_r5_cross_container_liveness_observer_defect(
    evidence: dict[str, Any],
) -> None:
    if (
        evidence.get("schema")
        != "arnold.critique_ledger.r5_cross_container_liveness_observer_defect.v1"
        or evidence.get("status")
        != "NON_BLOCKING_FOLLOW_UP_INPUT_NOT_RUNTIME_ACCEPTANCE"
        or evidence.get("authority") != "READ_ONLY_LIVE_OBSERVATION"
        or evidence.get("owner_milestone")
        != "f1-owner-storage-recovery-hardening"
        or evidence.get("session")
        != "critique-ledger-accountability-v3-r5-20260803"
        or evidence.get("plan") != "cl2-wbc-backed-ledger-20260803-1357"
    ):
        raise ContractError("cross-container liveness evidence identity drift")
    containers = evidence.get("containers")
    if (
        not isinstance(containers, dict)
        or containers.get("runner")
        != {
            "container_id": "782c6da82a8f988646747e8e57d51ca7f69d336d21920e3adebd9fb556e00117",
            "observed_state": "LIVE",
            "role": "ISOLATED_R5_CHAIN_RUNNER",
        }
        or containers.get("resident")
        != {
            "container_id": "a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a",
            "observed_state": "LIVE",
            "role": "DISCORD_RESIDENT_OBSERVER",
        }
        or containers.get("pid_namespaces") != "DISTINCT_FOREIGN_TO_EACH_OTHER"
        or evidence.get("defect_chain")
        != [
            "RESIDENT_OBSERVER_USED_LOCAL_TMUX_PS_AND_OS_KILL_FOR_FOREIGN_RUNNER_PID",
            "FOREIGN_PID_WAS_FALSELY_CLASSIFIED_DEAD_INSTEAD_OF_NOT_OBSERVABLE",
            "REDUCER_MISHANDLED_FRESH_HEARTBEAT_PLUS_FOREIGN_PROCESS_OBSERVATION",
            "PRESENTATION_EXCLUDED_THE_ACTIVE_ATTENTION_ROW",
            "WATCHDOG_REPORT_REMAINED_STALE_OR_MASKED_THE_LIVE_RUNNER",
        ]
    ):
        raise ContractError("exact runner/resident liveness defect observation drift")
    if evidence.get("canonical_observations") != {
        "runner_heartbeat": "FRESH",
        "resident_local_process_probe": "FOREIGN_PID_NAMESPACE_NOT_OBSERVABLE",
        "required_combined_classification": "REMOTE_LIVENESS_CONFIRMED_BY_BOUND_FRESH_LEASE_LOCAL_PROCESS_UNKNOWN",
        "canonical_run_state": "INTACT",
        "live_mutation_authority_from_this_record": False,
    }:
        raise ContractError("fresh-heartbeat/foreign-process classification drift")

    lease = evidence.get("shared_liveness_contract")
    if (
        not isinstance(lease, dict)
        or lease.get("owner")
        != "CANONICAL_CONTAINER_NEUTRAL_RUN_LIVENESS_LEASE_SERVICE"
        or lease.get("transport")
        != "SHARED_DURABLE_OWNER_AUTHENTICATED_COMPARE_AND_SWAP_RECORD"
        or lease.get("required_identity_fields")
        != [
            "session_id",
            "runner_container_id",
            "container_generation",
            "pid_namespace_id",
            "host_boot_id",
            "time_namespace_id",
            "run_id",
            "incarnation_id",
            "worker_pid",
            "process_start_identity",
            "lease_id",
            "fencing_token",
        ]
        or lease.get("required_freshness_fields")
        != [
            "heartbeat_sequence",
            "authority_accepted_monotonic_ns",
            "authority_expires_monotonic_ns",
            "last_progress_sequence",
            "last_progress_digest",
            "record_digest",
        ]
        or lease.get("freshness_rule")
        != "AUTHORITY_COMPUTES_MONOTONIC_FRESHNESS_IN_BOUND_BOOT_AND_TIME_NAMESPACE_OBSERVERS_DO_NOT_COMPARE_AMBIENT_LOCAL_CLOCKS"
        or lease.get("renewal_rule")
        != "MATCHING_RUN_CONTAINER_GENERATION_LEASE_AND_FENCE_COMPARE_AND_SWAP_ONLY"
        or lease.get("replacement_rule")
        != "NEW_CONTAINER_GENERATION_FENCES_PRIOR_LEASE_BEFORE_NEW_ACTIVE_PROJECTION"
        or lease.get("spoof_rule")
        != "UNAUTHENTICATED_MISMATCHED_REPLAYED_OR_NONMONOTONIC_HEARTBEAT_IS_REJECTED"
    ):
        raise ContractError("container-bound shared liveness lease drift")

    reducer = evidence.get("observer_reducer_contract")
    if reducer != {
        "local_process_probe_authority": "ONLY_FOR_MATCHING_CONTAINER_AND_PID_NAMESPACE_WITH_PROCESS_START_IDENTITY",
        "foreign_os_kill_result": "UNKNOWN_NOT_NEGATIVE_LIVENESS_AUTHORITY",
        "fresh_bound_heartbeat_plus_foreign_process": "REMOTE_LIVE_PROCESS_NOT_LOCALLY_OBSERVABLE",
        "fresh_heartbeat_plus_matched_dead_process": "TYPED_DEGRADED_LIVENESS_CONTRADICTION",
        "stale_heartbeat_plus_matched_live_process": "TYPED_DEGRADED_LIVENESS_CONTRADICTION",
        "contradiction_effect": "ZERO_AUTOMATIC_RECOVERY_UNTIL_CANONICAL_LEASE_RECONCILIATION",
        "presentation": "EXACTLY_ONE_ACTIVE_ATTENTION_ROW_WITH_CONTAINER_AND_EVIDENCE_STATUS",
        "watchdog": "CONSUME_SAME_CANONICAL_LIVENESS_VIEW_AND_REPORT_STALE_OR_DEGRADED_SOURCES_EXPLICITLY",
    }:
        raise ContractError("foreign-process liveness reducer/presentation drift")
    dedupe = evidence.get("recovery_dedupe_contract")
    if dedupe != {
        "key_fields": [
            "session_id",
            "run_id",
            "incarnation_id",
            "container_generation",
            "accepted_state_version",
            "liveness_failure_class",
        ],
        "maximum_recovery_occurrences_per_state_version": 1,
        "observer_count_does_not_multiply_recovery": True,
        "restart_or_response_loss_does_not_replenish_budget": True,
        "ambiguous_container_replacement": "FENCE_AND_RECONCILE_NO_SECOND_RECOVERY",
    }:
        raise ContractError("cross-container liveness recovery dedupe drift")
    if evidence.get("bounded_runner_lease_fix") != {
        "commit": "cfc65d7b7604c132664f8f725db0ce4eb12aa6a9",
        "summary": "fix(cloud): reject unbound marker PIDs",
        "regression": "OBSERVER_TOPOLOGY_COULD_TREAT_BARE_FOREIGN_OR_COLLIDING_PID_AS_LOCAL_LIVENESS",
        "fix": "PROCESS_LIVENESS_REQUIRES_MARKER_PID_NAMESPACE_TO_MATCH_OBSERVER_PID_NAMESPACE",
        "status": "BOUNDED_RUNNER_LEASE_OBSERVER_TOPOLOGY_REGRESSION_FIXED",
        "acceptance_boundary": "INPUT_FIX_REQUIRES_INTEGRATED_INSTALLED_CROSS_CONTAINER_F1_PROOF",
    }:
        raise ContractError("bounded runner-lease observer topology fix drift")

    adjacent = evidence.get("scoped_adjacent_input_evidence")
    if adjacent != {
        "old_wrapper": {
            "scope": "SCOPED_OLD_WRAPPER_RUNTIME_ONLY",
            "failure": "MISSING_ARNOLD_PIPELINES_MEGAPLAN_CLOUD_WRAPPERS_REPAIR_DELEGATION_MODULE",
            "classification": "HISTORICAL_WRAPPER_RUNTIME_DRIFT_NOT_CURRENT_CANONICAL_RUNNER_STATE",
        },
        "event_checkpoint": {
            "failure": "EventCheckpointError: non-monotonic event seq beyond checkpoint: 0 <= 9",
            "classification": "PREEXISTING_EVENT_CHECKPOINT_INCARNATION_DEFECT_INPUT_ONLY",
        },
        "rule": "DO_NOT_MASK_CROSS_CONTAINER_LIVENESS_WITH_EITHER_ADJACENT_FAILURE_AND_DO_NOT_RECLASSIFY_THEM_AS_CURRENT_RUNNER_DEATH",
    }:
        raise ContractError("scoped old-wrapper/checkpoint input evidence drift")
    if (
        evidence.get("required_mutation_tests")
        != [
            "RESIDENT_NAMESPACE_CANNOT_MARK_ISOLATED_RUNNER_PID_DEAD",
            "FOREIGN_OS_KILL_ESRCH_MAPS_TO_UNKNOWN_NOT_DEAD",
            "FRESH_BOUND_HEARTBEAT_PLUS_FOREIGN_PROCESS_PRODUCES_ONE_ACTIVE_ROW",
            "MATCHED_NAMESPACE_DEAD_PROCESS_PLUS_FRESH_HEARTBEAT_IS_TYPED_DEGRADED",
            "MATCHED_NAMESPACE_LIVE_PROCESS_PLUS_STALE_HEARTBEAT_IS_TYPED_DEGRADED",
            "RESIDENT_RESTART_PRESERVES_REMOTE_LIVENESS_VIEW",
            "RUNNER_RESTART_REQUIRES_NEW_INCARNATION_OR_VALID_LEASE_RENEWAL",
            "CONTAINER_REPLACEMENT_FENCES_OLD_GENERATION_BEFORE_NEW_ACTIVE_ROW",
            "STALE_HEARTBEAT_CANNOT_KEEP_REPLACED_CONTAINER_ACTIVE",
            "SPOOFED_OR_REPLAYED_HEARTBEAT_IS_REJECTED",
            "CONCURRENT_OBSERVERS_CREATE_ZERO_DUPLICATE_RECOVERY",
            "WATCHDOG_AND_PRESENTATION_CONSUME_IDENTICAL_CANONICAL_VIEW",
            "OLD_WRAPPER_MODULE_FAILURE_REMAINS_SCOPED_INPUT_EVIDENCE",
            "EVENT_CHECKPOINT_0_LE_9_REMAINS_SEPARATE_PREEXISTING_INPUT",
            "TWO_HUNDRED_POLLS_RETAIN_EXACTLY_ONE_ACTIVE_PROJECTION_AND_ONE_INCIDENT_MAXIMUM",
        ]
        or evidence.get("acceptance")
        != {
            "source_wheel_installed_cloud_parity": True,
            "resident_and_isolated_namespace_fixture_required": True,
            "real_container_replacement_fixture_required": True,
            "independent_review_required": True,
            "completion_evidence": "evidence/critique-ledger-recovery/T0.3/platform-capacity-and-storage-hardening/completion-manifest.json",
        }
    ):
        raise ContractError("cross-container liveness mutation-test acceptance drift")


def _validate_r5_m7_runtime_rebind_projection_cursor_mismatch(
    evidence: dict[str, Any],
) -> None:
    if (
        evidence.get("schema")
        != "arnold.critique_ledger.r5_m7_runtime_rebind_projection_cursor_mismatch.v1"
        or evidence.get("status")
        != "NON_BLOCKING_FOLLOW_UP_INPUT_NOT_RUNTIME_ACCEPTANCE"
        or evidence.get("authority") != "READ_ONLY_LIVE_OBSERVATION"
        or evidence.get("owner_milestone")
        != "f1-owner-storage-recovery-hardening"
        or evidence.get("session")
        != "critique-ledger-accountability-v3-r5-20260803"
        or evidence.get("plan") != "cl2-wbc-backed-ledger-20260803-1357"
    ):
        raise ContractError("M7 runtime-rebind projection evidence identity drift")
    rebind = evidence.get("runtime_rebind")
    observation = evidence.get("observation")
    if (
        rebind
        != {
            "minimum_runtime_commit": "18b279f5ef6d2a4db693586a59de8d87d7b45ab5",
            "event": "EXACT_18B_RUNTIME_REBIND_AND_RELAUNCH",
            "live_mutation_authority_from_this_record": False,
        }
        or not isinstance(observation, dict)
        or observation.get("projection") != "M7_CHAIN_STATE_PROJECTION"
        or observation.get("persisted_projection_cursor_record_count") != 645
        or observation.get("rebound_canonical_source_record_count") != 630
        or observation.get("observed_transition") != "645_TO_630"
        or observation.get("canonical_state") != "INTACT"
        or observation.get("classification")
        != "DERIVED_PROJECTION_CURSOR_MISMATCH_NON_BLOCKING_CANONICAL_STATE_INTACT"
        or observation.get("must_not_be_inferred")
        != [
            "CANONICAL_STATE_LOSS",
            "CHAIN_PRODUCT_FAILURE",
            "RELAUNCH_FAILURE",
            "AUTHORITY_TO_REPAIR_OR_RELAUNCH",
        ]
    ):
        raise ContractError("exact M7 645-to-630 observation drift")
    reconciliation = evidence.get("required_reconciliation_contract")
    if (
        not isinstance(reconciliation, dict)
        or reconciliation.get("cursor_identity_fields")
        != [
            "subject",
            "source_store_id",
            "source_epoch",
            "incarnation_id",
            "runtime_revision",
            "record_count",
            "last_record_digest",
            "projection_digest",
        ]
        or reconciliation.get("new_epoch_or_incarnation")
        != "ATOMICALLY_SUPERSEDE_OLD_CURSOR_AND_REBUILD_FROM_CANONICAL_SOURCE"
        or reconciliation.get("same_epoch_record_count_regression")
        != "TYPED_DEGRADED_SOURCE_DISAGREEMENT_NO_PROJECTION_ADVANCE_NO_MUTATION"
        or reconciliation.get("rebuild")
        != "ATOMIC_CONTENT_ADDRESSED_IDEMPOTENT_FROM_CANONICAL_STATE_AND_EVENTS"
        or reconciliation.get("crash_restart")
        != "RESUME_OR_RESTART_REBUILD_WITHOUT_MIXING_EPOCHS_OR_DUPLICATING_ROWS"
        or reconciliation.get("history")
        != "PRESERVE_OLD_CURSOR_AND_PROJECTION_AS_SUPERSEDED_INSPECTABLE_EVIDENCE"
        or reconciliation.get("authority_rule")
        != "PROJECTION_AND_CURSOR_ARE_NEVER_MUTATION_COMPLETION_REPAIR_RELAUNCH_OR_PUBLICATION_AUTHORITY"
        or reconciliation.get("operator_rule")
        != "NO_HAND_EDIT_DELETE_TRUNCATE_OR_COUNTER_BUMP_TO_FORCE_CONVERGENCE"
    ):
        raise ContractError("M7 epoch-aware projection reconciliation drift")
    if (
        evidence.get("required_mutation_tests")
        != [
            "EXACT_645_TO_630_RUNTIME_REBIND_FIXTURE_REBUILDS_UNDER_NEW_EPOCH",
            "SAME_EPOCH_645_TO_630_REGRESSION_RETURNS_TYPED_DEGRADED_WITHOUT_MUTATION",
            "CRASH_BEFORE_CURSOR_SUPERSESSION_RESTARTS_IDEMPOTENTLY",
            "CRASH_AFTER_SUPERSESSION_BEFORE_PROJECTION_PUBLISH_REBUILDS_ONCE",
            "RUNTIME_RESTART_DOES_NOT_REUSE_OLD_EPOCH_CURSOR",
            "OLD_AND_NEW_EPOCH_RECORDS_NEVER_MERGE_IN_ONE_PROJECTION",
            "HAND_EDITED_CURSOR_IS_REJECTED_AND_REBUILT_FROM_CANONICAL_SOURCE",
            "PROJECTION_CANNOT_AUTHORIZE_REPAIR_RELAUNCH_COMPLETION_OR_PUBLICATION",
            "CANONICAL_STATE_BYTES_AND_EVENT_HISTORY_REMAIN_UNCHANGED",
            "TWO_HUNDRED_UNCHANGED_POLLS_EMIT_ONE_DEGRADED_INCIDENT_MAXIMUM",
        ]
        or evidence.get("acceptance")
        != {
            "source_wheel_installed_cloud_parity": True,
            "exact_fixture_required": True,
            "independent_review_required": True,
            "completion_evidence": "evidence/critique-ledger-recovery/T0.3/platform-capacity-and-storage-hardening/completion-manifest.json",
        }
    ):
        raise ContractError("M7 projection mutation-test acceptance drift")


def _validate_escalation_sidecar_path_normalization_migration_contract(
    contract: dict[str, Any],
) -> None:
    if (
        contract.get("schema")
        != "arnold.cross_pipeline.escalation_sidecar_path_normalization_migration.v1"
        or contract.get("status")
        != "NORMATIVE_DESIGN_TARGET_WITH_READ_ONLY_INCIDENT_EVIDENCE"
        or contract.get("owner_milestone")
        != "f1-owner-storage-recovery-hardening"
        or contract.get("scope")
        != "ALL_ESCALATION_EVENT_AND_SIDECAR_WRITERS_AND_CONSUMERS"
        or contract.get("difficulty") != "4/5 HARD"
    ):
        raise ContractError("escalation sidecar path contract identity drift")

    incident = contract.get("incident_fixture")
    if incident != {
        "transition": "V2_ESCALATION_TERMINALIZATION",
        "feature_gate_outcome": "DISABLED_NO_OP",
        "writer_root_fault": "OVER_SPECIFIC_ESCALATIONS_DIRECTORY_REUSED_AS_REPAIR_DATA_ROOT",
        "causal_order": [
            "FEATURE_GATED_ESCALATION_ACTION_RETURNED_DISABLED_NO_OP",
            "TERMINALIZATION_SIDECAR_WRITER_APPENDED_ONE_RECORD_UNDER_DOUBLED_ESCALATIONS_SEGMENT",
            "CANONICAL_SUPERSEDED_EVENT_WAS_APPENDED_AT_SEQUENCE_635",
            "CANONICAL_CONSUMERS_IGNORED_THE_NONCANONICAL_NESTED_FILE",
        ],
        "noncanonical_record": {
            "path": "repair-data/escalations/escalations/escalations.jsonl",
            "record_count": 1,
            "canonical_consumer_visible": False,
            "classification": "IMMUTABLE_NONCANONICAL_AUDIT_EVIDENCE_NOT_LEDGER_AUTHORITY",
        },
        "canonical_superseding_event": {
            "path": "repair-data/escalations/escalations.jsonl",
            "event_sequence": 635,
            "event": "SUPERSEDED",
            "classification": "CANONICAL_TERMINALIZATION_AUTHORITY",
        },
        "live_mutation_authority": False,
    }:
        raise ContractError("exact escalation sidecar incident fixture drift")

    writer = contract.get("writer_contract")
    if (
        not isinstance(writer, dict)
        or writer.get("typed_root") != "REPAIR_DATA_ROOT"
        or writer.get("accepted_root_relative_path") != "repair-data"
        or writer.get("canonical_ledger_relative_path")
        != "escalations/escalations.jsonl"
        or writer.get("canonical_target")
        != "repair-data/escalations/escalations.jsonl"
        or writer.get("root_normalization_rule")
        != "CALLER_MUST_SUPPLY_TYPED_REPAIR_DATA_ROOT_OVER_SPECIFIC_LEDGER_DIRECTORY_IS_REJECTED_BEFORE_OPEN"
        or writer.get("path_construction_rule")
        != "ONE_CANONICAL_BUILDER_JOINS_TYPED_ROOT_AND_CANONICAL_LEDGER_RELATIVE_PATH_EXACTLY_ONCE"
        or writer.get("preflight_before_open")
        != [
            "RESOLVE_TYPED_ROOT_WITHOUT_FOLLOWING_UNTRUSTED_SYMLINKS",
            "REJECT_ROOT_ALREADY_ENDING_IN_ESCALATIONS_OR_ESCALATIONS_JSONL",
            "REJECT_ABSOLUTE_TRAVERSAL_SYMLINK_ESCAPE_AND_NON_REGULAR_TARGET",
            "ATTEST_EXACT_CANONICAL_RELATIVE_AND_RESOLVED_TARGET_PATHS",
            "ATTEST_EXPECTED_ESCALATIONS_SEGMENT_COUNT_AND_FILENAME",
            "FAIL_CLOSED_WITH_ZERO_WRITES_ON_ANY_MISMATCH",
        ]
        or writer.get("canonical_path_attestation_fields")
        != [
            "operation_id",
            "typed_root",
            "typed_root_identity",
            "canonical_relative_path",
            "resolved_target_path",
            "target_parent_identity",
            "path_policy_version",
            "attestation_digest",
        ]
        or writer.get("feature_gate_disabled_rule")
        != "DISABLED_NO_OP_MAY_TERMINALIZE_ONCE_IN_CANONICAL_LEDGER_BUT_MUST_NOT_CREATE_AN_ACTION_SIDECAR_OR_SECOND_TERMINAL_EVENT"
        or writer.get("consumer_rule")
        != "READ_ONLY_CANONICAL_ATTESTED_LEDGER_PATH_NESTED_OR_UNATTESTED_PATHS_ARE_NEVER_AUTO_DISCOVERED"
        or writer.get("append_rule")
        != "OPEN_AND_APPEND_ONLY_AFTER_CANONICAL_PATH_ATTESTATION_SUCCEEDS"
    ):
        raise ContractError("canonical escalation writer root/preflight drift")

    migration = contract.get("noncanonical_evidence_migration")
    if (
        not isinstance(migration, dict)
        or migration.get("authority")
        != "CURRENT_STORAGE_OWNER_WITH_EXACT_SOURCE_PATH_AND_HASH_MANIFEST"
        or migration.get("ordered_steps")
        != [
            "READ_NONCANONICAL_SOURCE_WITHOUT_TREATING_IT_AS_LEDGER_INPUT",
            "FREEZE_SOURCE_PATH_SIZE_SHA256_AND_BYTE_IDENTITY",
            "COPY_TO_CONTENT_ADDRESSED_QUARANTINE_OUTSIDE_ACTIVE_CONSUMER_DISCOVERY",
            "READ_BACK_AND_VERIFY_EXACT_BYTES_SIZE_AND_SHA256",
            "WRITE_AND_FSYNC_APPEND_ONLY_MIGRATION_MANIFEST",
            "ATTEST_CANONICAL_SEQUENCE_635_SUPERSESSION_REMAINS_AUTHORITATIVE",
            "RETAIN_ORIGINAL_UNTIL_SEPARATE_OWNER_AUTHORIZED_RETIREMENT",
        ]
        or migration.get("required_manifest_fields")
        != [
            "schema",
            "operation_id",
            "source_path",
            "source_size",
            "source_sha256",
            "quarantine_path",
            "quarantine_size",
            "quarantine_sha256",
            "canonical_ledger_path",
            "canonical_superseding_sequence",
            "copied_at",
            "verified_at",
        ]
        or migration.get("byte_preservation")
        != "SOURCE_AND_QUARANTINE_READBACK_SIZE_AND_SHA256_MUST_MATCH"
        or migration.get("canonical_event_rule")
        != "DO_NOT_REAPPEND_RENUMBER_OR_REWRITE_CANONICAL_SEQUENCE_635"
        or migration.get("original_default") != "RETAIN_NO_HAND_DELETE"
        or migration.get("destructive_retirement")
        != "SEPARATE_CURRENT_OWNER_GRANT_AFTER_VERIFIED_MANIFEST_OR_NO_DELETE"
        or migration.get("consumer_effect")
        != "ZERO_NEW_CANONICAL_EVENTS_ZERO_DUPLICATE_TERMINALIZATION_ZERO_NESTED_FILE_DISCOVERY"
    ):
        raise ContractError("noncanonical escalation evidence migration drift")

    if (
        contract.get("required_negative_and_mutation_tests")
        != [
            "TYPED_REPAIR_DATA_ROOT_WRITES_EXACT_CANONICAL_TARGET",
            "ROOT_REPAIR_DATA_ESCALATIONS_IS_REJECTED_BEFORE_OPEN_WITH_ZERO_WRITES",
            "ROOT_REPAIR_DATA_ESCALATIONS_ESCALATIONS_IS_REJECTED_BEFORE_OPEN_WITH_ZERO_WRITES",
            "DOUBLED_ESCALATIONS_TARGET_FAILS_CANONICAL_PATH_ATTESTATION",
            "ABSOLUTE_TRAVERSAL_AND_SYMLINK_ESCAPE_FAIL_WITH_ZERO_WRITES",
            "DISABLED_FEATURE_GATE_CREATES_NO_ACTION_SIDECAR_AND_ONE_CANONICAL_TERMINAL_EVENT_MAXIMUM",
            "NONCANONICAL_RECORD_IS_NEVER_AUTO_DISCOVERED_BY_LEDGER_CONSUMERS",
            "QUARANTINE_COPY_PRESERVES_EXACT_BYTES_SIZE_AND_SHA256",
            "HAND_DELETE_AND_UNMANIFESTED_MOVE_ARE_DENIED_WITH_ORIGINAL_PRESERVED",
            "MIGRATION_DOES_NOT_DUPLICATE_RENUMBER_OR_REWRITE_CANONICAL_SEQUENCE_635",
            "RESTART_AND_TWO_HUNDRED_POLLS_RETAIN_ONE_CANONICAL_TERMINALIZATION_AND_ZERO_NESTED_CONSUMPTION",
        ]
        or contract.get("acceptance")
        != {
            "source_wheel_installed_cloud_parity": True,
            "cross_pipeline_writer_consumer_inventory_required": True,
            "real_filesystem_path_fixture_required": True,
            "independent_review_required": True,
            "completion_evidence": "evidence/critique-ledger-recovery/T0.3/platform-capacity-and-storage-hardening/completion-manifest.json",
        }
    ):
        raise ContractError("escalation sidecar mutation-test acceptance drift")


def _validate_finalize_output_artifact_handoff_shared_retry_contract(
    contract: dict[str, Any],
) -> None:
    if (
        contract.get("schema")
        != "arnold.cross_pipeline.phase_output_artifact_handoff_shared_retry.v1"
        or contract.get("status")
        != "NORMATIVE_DESIGN_TARGET_WITH_READ_ONLY_INCIDENT_EVIDENCE"
        or contract.get("joint_owner_milestones")
        != [
            "f1-owner-storage-recovery-hardening",
            "f2a-launch-profile-artifact-drift-containment",
        ]
        or contract.get("scope")
        != "ALL_REGISTERED_PHASES_AGENTS_EXECUTORS_REPAIRERS_AND_OUTER_AUTO_DRIVERS"
        or contract.get("difficulty") != "5/5 VERY HARD"
    ):
        raise ContractError("finalize output handoff/retry contract identity drift")

    incident = contract.get("incident_fixture")
    artifact = incident.get("repair_artifact") if isinstance(incident, dict) else None
    receipt = incident.get("transport_receipt") if isinstance(incident, dict) else None
    failure = incident.get("observed_failure") if isinstance(incident, dict) else None
    retry = incident.get("retry_observation") if isinstance(incident, dict) else None
    if (
        not isinstance(incident, dict)
        or incident.get("session")
        != "critique-ledger-accountability-v3-r5-20260803"
        or incident.get("plan") != "cl2-wbc-backed-ledger-20260803-1357"
        or incident.get("phase") != "finalize"
        or artifact
        != {
            "producer": "SOL_REPAIR",
            "path": "finalize_output.json",
            "size_bytes": 72328,
            "observed_sha256_prefix": "af6149be",
            "full_sha256_status": "NOT_PRESENT_IN_AUDIT_INPUT_MUST_BE_CAPTURED_BEFORE_ACCEPTANCE",
            "json_and_model_output_schema_validation": "PASS",
            "task_count": 28,
            "coverage_count": 29,
            "feasibility": "ADMITTED",
        }
        or receipt
        != {
            "producer": "CODEX_CLI_DASH_O",
            "size_bytes": 339,
            "classification": "TRANSPORT_RECEIPT_NOT_PHASE_PAYLOAD",
        }
        or failure
        != {
            "validator": "LOCAL_STRICT_JSON",
            "rejected_input": "CODEX_CLI_DASH_O_TRANSPORT_RECEIPT",
            "reason": "REQUIRED_FINALIZE_FIELDS_MISSING",
            "valid_artifact_was_available": True,
        }
        or incident.get("schema_boundary_observation")
        != {
            "incorrect_worker_capture_schema": "finalize_capture.json_POST_HANDLER_ENRICHED_PRODUCT",
            "correct_worker_capture_schema": "FINALIZE_MODEL_OUTPUT_SCHEMA_PRE_MUTATION",
            "consequence": "EVEN_CORRECT_72328_BYTE_MODEL_OUTPUT_FAILS_IF_VALIDATED_AS_ENRICHED_PRODUCT_BEFORE_HANDLER_MUTATION",
        }
        or retry
        != {
            "inner_repair_count": 1,
            "outer_auto_launched_third_call": True,
            "classification": "NO_SHARED_CROSS_LAYER_OCCURRENCE_BUDGET",
        }
        or incident.get("root_causes")
        != [
            "PHASE_OUTPUT_AUTHORITY_WAS_IMPLICIT_ACROSS_FILE_ARTIFACT_AND_TRANSPORT_RECEIPT_CHANNELS",
            "VALIDATED_REPAIR_ARTIFACT_WAS_NOT_HANDED_OFF_AS_THE_AUTHORITATIVE_PHASE_PAYLOAD",
            "LOCAL_STRICT_VALIDATED_THE_SMALL_TRANSPORT_RECEIPT_INSTEAD_OF_THE_BOUND_ARTIFACT",
            "FINALIZE_WORKER_CAPTURE_SCHEMA_USED_POST_HANDLER_FINALIZE_CAPTURE_PRODUCT_SHAPE_INSTEAD_OF_PRE_MUTATION_MODEL_OUTPUT_SCHEMA",
            "INNER_REPAIR_AND_OUTER_AUTO_OWNED_INDEPENDENT_RETRY_BUDGETS",
        ]
        or incident.get("live_mutation_authority") is not False
    ):
        raise ContractError("exact finalize output/retry incident fixture drift")

    handoff = contract.get("artifact_handoff_contract")
    if (
        not isinstance(handoff, dict)
        or handoff.get("phase_declared_output_channel") != "FILE_ARTIFACT"
        or handoff.get("finalize_authoritative_artifact") != "finalize_output.json"
        or handoff.get("transport_receipt_role")
        != "DIAGNOSTIC_RECEIPT_ONLY_NEVER_STRUCTURED_PHASE_PAYLOAD"
        or handoff.get("required_pre_dispatch_binding")
        != [
            "occurrence_id",
            "state_version",
            "phase",
            "phase_invocation_id",
            "agent",
            "executor",
            "declared_output_channel",
            "expected_artifact_path",
            "canonical_schema_sha256",
            "artifact_generation_token",
        ]
        or handoff.get("producer_completion_attestation")
        != [
            "phase_invocation_id",
            "artifact_generation_token",
            "artifact_path",
            "artifact_size",
            "artifact_sha256",
            "schema_validation_result",
            "producer_exit_status",
            "transport_receipt_path_size_and_sha256",
        ]
        or handoff.get("ordered_handoff")
        != [
            "DECLARE_AND_BIND_ONE_OUTPUT_CHANNEL_BEFORE_DISPATCH",
            "WRITE_ARTIFACT_TO_INVOCATION_SCOPED_TEMPORARY_PATH",
            "FSYNC_CLOSE_AND_ATTEST_ARTIFACT_BYTES",
            "READ_BACK_EXACT_PATH_SIZE_SHA256_GENERATION_AND_SCHEMA",
            "CLASSIFY_EXECUTOR_OUTPUT_AS_TRANSPORT_RECEIPT",
            "ATOMICALLY_PROMOTE_VALIDATED_ARTIFACT_ONCE",
            "PERSIST_PROMOTION_RECEIPT_BEFORE_ADVANCING_PHASE",
        ]
        or handoff.get("selection_rule")
        != "VALID_BOUND_ARTIFACT_IS_AUTHORITATIVE_AND_TRANSPORT_RECEIPT_CAN_NEVER_REPLACE_OR_OVERRIDE_IT"
        or handoff.get("missing_invalid_or_stale_artifact")
        != "TYPED_OUTPUT_ARTIFACT_HANDOFF_FAILURE_NO_RECEIPT_FALLBACK"
        or handoff.get("post_attestation_change")
        != "HASH_OR_IDENTITY_MISMATCH_FAILS_CLOSED_NO_PROMOTION"
        or handoff.get("promotion_rule")
        != "COMPARE_AND_SWAP_ON_OCCURRENCE_STATE_VERSION_PHASE_INVOCATION_AND_ARTIFACT_DIGEST_EXACTLY_ONCE"
        or handoff.get("consumer_rule")
        != "LOCAL_STRICT_AND_DOWNSTREAM_PHASES_READ_ONLY_THE_PROMOTED_ATTESTED_ARTIFACT_BYTES"
    ):
        raise ContractError("explicit phase-output artifact handoff drift")

    if contract.get("finalize_schema_boundary_contract") != {
        "worker_capture_schema": "FINALIZE_MODEL_OUTPUT_SCHEMA",
        "worker_capture_stage": "PRE_HANDLER_PRE_MUTATION_MODEL_OWNED_BYTES",
        "forbidden_worker_capture_schema": "FINALIZE_CAPTURE_JSON_POST_HANDLER_ENRICHED_PRODUCT_SHAPE",
        "shared_pre_handler_consumers": [
            "FINALIZE_PROMPT_TEMPLATE",
            "FILE_ARTIFACT_WORKER_CAPTURE",
            "LOCAL_STRICT_MODEL_OUTPUT_VALIDATION",
            "HANDLER_INPUT_VALIDATION",
        ],
        "handler_owned_enrichment": [
            "VALIDATION_RESULTS",
            "EXECUTION_EVIDENCE",
            "BASELINE_TEST_METADATA",
            "CUSTODY_AND_PROMOTION_EVIDENCE",
        ],
        "persisted_product_rule": "HANDLER_VALIDATES_MODEL_OUTPUT_FIRST_THEN_ENRICHES_AND_PERSISTS_AGAINST_PRODUCT_SCHEMA",
        "required_schema_attestations": [
            "finalize_model_output_schema_sha256",
            "prompt_template_projection_sha256",
            "worker_capture_schema_sha256",
            "local_strict_schema_sha256",
            "handler_input_schema_sha256",
            "persisted_product_schema_sha256",
            "handler_enrichment_version_and_source_sha256",
        ],
        "template_reset_rule": "NEVER_TRUNCATE_RESEED_OVERWRITE_OR_UNLINK_A_RECEIPTED_CANDIDATE_FOR_THE_SAME_INVOCATION",
        "reset_after_receipt": "REUSE_EXACT_RECEIPTED_BYTES_OR_CREATE_NEW_SUPERSEDING_INVOCATION_PATH_AFTER_DURABLE_SUPERSESSION",
        "receipt_candidate_binding": "OCCURRENCE_STATE_VERSION_PHASE_INVOCATION_GENERATION_PATH_SIZE_SHA256_SCHEMA_AND_FSYNC_IDENTITY",
        "crash_or_ambiguity": "PRESERVE_CANDIDATE_AND_RECEIPT_FAIL_CLOSED_NO_TEMPLATE_RESET",
    }:
        raise ContractError("finalize pre/post-handler schema boundary drift")

    if contract.get("shared_retry_budget_contract") != {
        "owner": "DURABLE_CROSS_LAYER_OCCURRENCE_ATTEMPT_LEDGER",
        "key_fields": [
            "session_id",
            "plan_id",
            "run_id",
            "incarnation_id",
            "occurrence_id",
            "accepted_state_version",
            "phase",
            "failure_fingerprint",
        ],
        "maximum_phase_execution_calls_per_occurrence": 2,
        "allocation": {
            "initial_call": 1,
            "shared_repair_or_replay_call": 1,
            "outer_third_call": 0,
        },
        "claim_rule": "EVERY_INNER_OR_OUTER_EXECUTION_COMPARE_AND_SWAP_CLAIMS_THE_SAME_DURABLE_SLOT_BEFORE_DISPATCH",
        "valid_repair_artifact_rule": "PROMOTE_WITHOUT_ANOTHER_MODEL_CALL_WHEN_BOUND_ARTIFACT_ALREADY_VALIDATES",
        "independent_layer_budgets": "FORBIDDEN",
        "process_restart_response_loss_and_timeout": "DO_NOT_REPLENISH_OR_FORGET_CLAIMED_OR_AMBIGUOUS_SLOT",
        "concurrency": "ONE_WINNER_ALL_OTHER_INNER_OUTER_OR_OBSERVER_CLAIMS_RECEIVE_TYPED_BUDGET_EXHAUSTED",
        "new_budget_rule": "ONLY_NEW_DURABLE_OCCURRENCE_OR_ACCEPTED_STATE_VERSION_WITH_DISTINCT_FAILURE_FINGERPRINT",
        "terminal_effect": "ONE_VERSION_KEYED_FAILURE_OR_MANUAL_REVIEW_NOTIFICATION_MAXIMUM",
    }:
        raise ContractError("shared inner/outer occurrence retry budget drift")

    if contract.get("adjacent_observer_fix") != {
        "commit": "cfc65d7b7604c132664f8f725db0ce4eb12aa6a9",
        "summary": "fix(cloud): reject unbound marker PIDs",
        "regression": "OBSERVER_TOPOLOGY_COULD_TREAT_BARE_FOREIGN_OR_COLLIDING_PID_AS_LOCAL_LIVENESS",
        "fix": "PROCESS_LIVENESS_REQUIRES_MARKER_PID_NAMESPACE_TO_MATCH_OBSERVER_PID_NAMESPACE",
        "status": "BOUNDED_RUNNER_LEASE_OBSERVER_TOPOLOGY_REGRESSION_FIXED",
        "acceptance_boundary": "INPUT_FIX_REQUIRES_INTEGRATED_INSTALLED_CROSS_CONTAINER_F1_PROOF",
    }:
        raise ContractError("finalize contract adjacent observer-fix evidence drift")

    if (
        contract.get("required_negative_and_mutation_tests")
        != [
            "VALID_72328_BYTE_ARTIFACT_WINS_OVER_339_BYTE_TRANSPORT_RECEIPT",
            "TRANSPORT_RECEIPT_CAN_NEVER_SATISFY_FINALIZE_LOCAL_STRICT_SCHEMA",
            "FULL_ARTIFACT_SHA256_MUST_EXTEND_OBSERVED_AF6149BE_PREFIX_BEFORE_ACCEPTANCE",
            "TASK_28_COVERAGE_29_AND_FEASIBILITY_SURVIVE_EXACT_ARTIFACT_PROMOTION",
            "STALE_PRIOR_INVOCATION_ARTIFACT_IS_REJECTED",
            "WRONG_PATH_ARTIFACT_IS_REJECTED_WITHOUT_RECEIPT_FALLBACK",
            "POST_ATTESTATION_ARTIFACT_MUTATION_FAILS_CLOSED",
            "FINALIZE_WORKER_CAPTURE_USES_FINALIZE_MODEL_OUTPUT_SCHEMA_NOT_FINALIZE_CAPTURE_PRODUCT_SCHEMA",
            "VALID_MODEL_OUTPUT_WITHOUT_HANDLER_OWNED_FIELDS_PASSES_PRE_HANDLER_CAPTURE",
            "HANDLER_ENRICHES_ONLY_AFTER_MODEL_OUTPUT_VALIDATION_AND_PERSISTS_PRODUCT_SCHEMA",
            "TEMPLATE_RESET_NEVER_ERASES_TRUNCATES_OR_RESEEDS_RECEIPTED_CANDIDATE",
            "CRASH_BEFORE_OR_AFTER_RECEIPT_PRESERVES_CANDIDATE_AND_RECONCILES_WITHOUT_OVERWRITE",
            "INNER_REPAIR_VALID_ARTIFACT_PROMOTES_WITH_ZERO_OUTER_THIRD_CALLS",
            "INNER_AND_OUTER_CONCURRENT_RETRY_CLAIMS_HAVE_ONE_DURABLE_WINNER",
            "PROCESS_RESTART_RESPONSE_LOSS_AND_TIMEOUT_DO_NOT_REPLENISH_RETRY_BUDGET",
            "THIRD_CALL_IS_REJECTED_AFTER_INITIAL_PLUS_ONE_SHARED_REPAIR_OR_REPLAY",
            "DISTINCT_NEW_OCCURRENCE_DOES_NOT_INHERIT_PRIOR_EXHAUSTION",
            "SOURCE_WHEEL_INSTALLED_AND_CLOUD_CODEX_HERMES_AND_COMPATIBILITY_EXECUTORS_SHARE_HANDOFF_SEMANTICS",
            "UNBOUND_OR_FOREIGN_MARKER_PID_CANNOT_ESTABLISH_LOCAL_PROCESS_LIVENESS",
        ]
        or contract.get("acceptance")
        != {
            "full_artifact_sha256_required": True,
            "observed_hash_prefix_must_match": "af6149be",
            "source_wheel_installed_cloud_parity": True,
            "registry_closed_phase_agent_executor_matrix": True,
            "real_codex_dash_o_and_file_artifact_fixture_required": True,
            "pre_handler_and_post_handler_schema_hash_proof_required": True,
            "receipted_candidate_reset_safety_fixture_required": True,
            "restart_response_loss_and_concurrency_fixture_required": True,
            "independent_review_required": True,
            "completion_evidence": "evidence/critique-ledger-recovery/F2A/finalize-output-handoff-shared-retry/completion-manifest.json",
        }
    ):
        raise ContractError("finalize handoff/retry mutation-test acceptance drift")


def _validate_artifact_archival_projection_cleanup_contract(
    contract: dict[str, Any],
) -> None:
    if (
        contract.get("schema")
        != "arnold.cross_pipeline.receipt_aware_artifact_archival_projection_cleanup.v1"
        or contract.get("status") != "NORMATIVE_DESIGN_TARGET_NOT_RUNTIME_PROOF"
        or contract.get("owner_milestone")
        != "f1-owner-storage-recovery-hardening"
        or contract.get("scope")
        != "ALL_CUSTODY_BOUND_PRODUCER_ARTIFACTS_AND_ATTEMPT_PROJECTIONS"
        or contract.get("difficulty") != "5/5 VERY HARD"
    ):
        raise ContractError("artifact archival/projection contract identity drift")

    fixture = contract.get("incident_fixture")
    if (
        not isinstance(fixture, dict)
        or fixture.get("session")
        != "critique-ledger-accountability-v3-r5-20260803"
        or fixture.get("plan") != "cl2-wbc-backed-ledger-20260803-1357"
        or fixture.get("hazard")
        != "BROAD_CRITIQUE_CHECK_GLOB_CAN_RELOCATE_RAW_SOURCES_NAMED_BY_ACTIVE_CUSTODY_RECEIPTS"
        or fixture.get("receipt_versions")
        != ["critique_custody_v1.json", "critique_custody_v2.json"]
        or fixture.get("producer_patterns_are_discovery_only_not_mutation_authority")
        != [
            "critique_check_*_producer_vN.json",
            "critique_check_*_raw_vN.txt",
        ]
        or len(fixture.get("code_evidence") or []) != 2
    ):
        raise ContractError("artifact archival incident fixture drift")

    archive = contract.get("archive_contract")
    keep_set = archive.get("immutable_keep_set") if isinstance(archive, dict) else None
    preflight = archive.get("preflight") if isinstance(archive, dict) else None
    manifest = archive.get("archive_manifest") if isinstance(archive, dict) else None
    retirement = (
        archive.get("destructive_retirement") if isinstance(archive, dict) else None
    )
    expected_order = [
        "READ_AND_VALIDATE_ALL_ACTIVE_RECEIPTS",
        "FREEZE_IMMUTABLE_EXACT_PATH_AND_SHA256_KEEP_SET",
        "PREFLIGHT_EXACT_TARGETS_AND_DESTINATION",
        "COPY_TO_NON_DESTRUCTIVE_CONTENT_ADDRESSED_ARCHIVE",
        "READ_BACK_AND_VERIFY_EXACT_BYTES_AND_SHA256",
        "WRITE_AND_FSYNC_APPEND_ONLY_ARCHIVE_MANIFEST",
        "REVALIDATE_EVERY_ACTIVE_RECEIPT_AGAINST_ORIGINAL_OR_MANIFEST_BOUND_ARCHIVE_PATH",
        "PUBLISH_ARCHIVE_SUCCESS_RECEIPT",
        "SEPARATELY_AUTHORIZE_ANY_LATER_DESTRUCTIVE_RETIREMENT",
    ]
    if (
        not isinstance(archive, dict)
        or archive.get("authority") != "ACTIVE_VALIDATED_CUSTODY_RECEIPTS_ONLY"
        or archive.get("ordered_steps") != expected_order
        or not isinstance(keep_set, dict)
        or keep_set.get("derive_from")
        != [
            "validated_receipt_bytes",
            "receipt.plan_artifact_and_plan_sha256",
            "receipt.critique_artifact_and_critique_sha256",
            "receipt.raw_sources_artifact_and_sha256",
        ]
        or keep_set.get("freeze_before_preflight") is not True
        or keep_set.get("glob_results_may_expand_keep_set") is not False
        or keep_set.get("missing_ambiguous_or_mutating_source")
        != "FAIL_CLOSED_NO_ARCHIVE_NO_DELETE"
    ):
        raise ContractError("receipt-derived immutable archive order/keep-set drift")
    if (
        not isinstance(preflight, dict)
        or set(preflight.values()) != {True}
        or set(preflight)
        != {
            "exact_targets_only",
            "reject_globs_wildcards_and_unexpanded_patterns",
            "reject_symlink_path_escape_and_non_regular_files",
            "reject_source_identity_change_between_read_and_copy",
            "reject_destination_collision_unless_exact_same_bytes",
        }
    ):
        raise ContractError("exact-target archive preflight drift")
    required_manifest_fields = [
        "schema",
        "operation_id",
        "subject",
        "receipt_path",
        "receipt_sha256",
        "source_path",
        "source_sha256",
        "source_size",
        "archive_path",
        "archive_sha256",
        "archive_size",
        "copied_at",
        "verified_at",
    ]
    if (
        not isinstance(manifest, dict)
        or manifest.get("append_only") is not True
        or manifest.get("content_addressed") is not True
        or manifest.get("required_fields") != required_manifest_fields
        or manifest.get("exact_byte_hash_verification")
        != "SHA256_AND_SIZE_SOURCE_EQUALS_ARCHIVE_READBACK"
        or not isinstance(retirement, dict)
        or retirement
        != {
            "part_of_archive_transaction": False,
            "default": "RETAIN_ORIGINALS",
            "requires_separate_current_owner_grant": True,
            "requires_post_archive_custody_validation": True,
            "ambiguous_response": "NO_DELETE",
        }
    ):
        raise ContractError("archive manifest/readback/retirement contract drift")
    forbidden = set(archive.get("forbidden") or [])
    if (
        forbidden
        != {
            "MV_OR_DELETE_BY_BROAD_CRITIQUE_CHECK_GLOB",
            "MOVE_OR_DELETE_BEFORE_ARCHIVE_READBACK_VERIFICATION",
            "DERIVE_KEEP_SET_FROM_DIRECTORY_LISTING_WITHOUT_RECEIPTS",
            "REWRITE_RECEIPT_HASHES_TO_MATCH_MOVED_OR_MUTATED_BYTES",
            "CLAIM_SUCCESS_WHILE_ANY_ACTIVE_V1_OR_V2_RECEIPT_IS_UNREADABLE",
        }
        or archive.get("postcondition")
        != "EVERY_ACTIVE_V1_AND_V2_RECEIPT_VALIDATES_EXACT_BYTES_AT_ORIGINAL_OR_MANIFEST_BOUND_ARCHIVE_LOCATION"
    ):
        raise ContractError("broad-glob/v1-v2 custody protection drift")

    projection = contract.get("projection_cleanup_contract")
    polling = (
        projection.get("restart_and_poll_semantics")
        if isinstance(projection, dict)
        else None
    )
    expected_projection_rules = [
        "REBUILD_CURRENT_ATTENTION_FROM_AUTHORITATIVE_LIFECYCLE_AND_SUPERSESSION_RECORDS",
        "SHOW_EXACTLY_ONE_ACTIVE_R5_SUBJECT_OR_TYPED_DEGRADED_AMBIGUITY",
        "RETAIN_R2_R3_R4_AS_TERMINAL_HISTORICAL_EVIDENCE",
        "EXCLUDE_RETIRED_GENERATIONS_FROM_CURRENT_ATTENTION",
        "NEVER_DELETE_OR_REWRITE_RUN_RECEIPT_CUSTODY_OR_EVENT_HISTORY",
        "ATOMICALLY_PUBLISH_CONTENT_ADDRESSED_PROJECTION_WITH_SOURCE_CURSOR",
    ]
    if (
        not isinstance(projection, dict)
        or projection.get("authority")
        != "CANONICAL_LIFECYCLE_SUPERSESSION_AND_INCARNATION_RECORDS"
        or projection.get("active_generation")
        != "critique-ledger-accountability-v3-r5-20260803"
        or projection.get("retired_generation_suffixes") != ["r2", "r3", "r4"]
        or projection.get("rules") != expected_projection_rules
        or polling
        != {
            "idempotent_rebuild": True,
            "unchanged_poll_count": 200,
            "duplicate_current_rows": 0,
            "history_loss": 0,
            "ambiguous_authority_result": "TYPED_DEGRADED_NO_GUESS_NO_MUTATION",
        }
    ):
        raise ContractError("authoritative failed-attempt projection cleanup drift")

    tests = contract.get("required_negative_and_mutation_tests")
    if (
        not isinstance(tests, list)
        or len(tests) != 10
        or "BROAD_CRITIQUE_CHECK_STAR_MOVE_CANNOT_ORPHAN_V1_RECEIPT" not in tests
        or "BROAD_CRITIQUE_CHECK_STAR_MOVE_CANNOT_ORPHAN_V2_RECEIPT" not in tests
        or "R2_R3_R4_HISTORY_REMAINS_QUERYABLE_AFTER_PROJECTION_CLEANUP"
        not in tests
        or contract.get("acceptance")
        != {
            "source_wheel_installed_cloud_parity": True,
            "cross_pipeline_registry_closed": True,
            "independent_review_required": True,
            "completion_evidence": "evidence/critique-ledger-recovery/T0.3/platform-capacity-and-storage-hardening/completion-manifest.json",
        }
    ):
        raise ContractError("artifact archival/projection mutation-test acceptance drift")


def _validate_provider_schema_dialect_family_contract(
    dialect: dict[str, Any],
) -> None:
    if (
        dialect.get("schema")
        != "arnold.cross_pipeline.provider_schema_dialect_family.v1"
        or dialect.get("status") != "NORMATIVE_DESIGN_TARGET_NOT_RUNTIME_PROOF"
        or dialect.get("owner_milestone")
        != "f2a-launch-profile-artifact-drift-containment"
        or dialect.get("scope")
        != "ALL_REGISTERED_PRODUCTION_PIPELINES_MODEL_PHASES_PROVIDERS_PROFILES_AND_LAUNCHERS"
        or dialect.get("difficulty") != "5/5 VERY HARD"
        or dialect.get("dependencies")
        != [
            "f1-owner-storage-recovery-hardening",
            "f2-admission-model-effect-release-closure",
        ]
        or dialect.get("blocks") != ["f3-cl2-real-work-and-publication"]
    ):
        raise ContractError("provider-schema dialect identity/dependency drift")

    evidence = dialect.get("evidence_inputs")
    m9 = evidence.get("historical_m9") if isinstance(evidence, dict) else None
    r5 = evidence.get("current_r5") if isinstance(evidence, dict) else None
    commits = (
        r5.get("implementation_inputs_not_acceptance")
        if isinstance(r5, dict)
        else None
    )
    if (
        not isinstance(evidence, dict)
        or not isinstance(m9, dict)
        or m9
        != {
            "fixture": "M9_PROVIDER_SCHEMA_MUTATION_REPLAY",
            "unsupported_keyword_mutations": [
                "default",
                "const",
                "oneOf",
                "minimum",
            ],
            "required_disposition": "LOCAL_CANONICAL_VALIDATION_WITHOUT_SEMANTIC_REWRITE",
        }
        or not isinstance(r5, dict)
        or r5.get("session")
        != "critique-ledger-accountability-v3-r5-20260803"
        or r5.get("plan") != "cl2-wbc-backed-ledger-20260803-1357"
        or r5.get("phase") != "finalize"
        or r5.get("failure_identity")
        != "PROVIDER_CONTRACT_SCHEMA_ERROR_DETERMINISTIC_NONRETRYABLE"
        or commits
        != [
            {
                "commit": "f401431b7a91f11518c241da9aea5920d3d41538",
                "tree": "1f55839e952f6fbc255e2fcca72d5251ae68534a",
                "subject": "NEGOTIATE_PROVIDER_RESPONSE_ENFORCEMENT",
            },
            {
                "commit": "b168edbca01388fbad55383f43c290476ff0feda",
                "tree": "ccd93dff64f59aa0e3ac22dcd5a75e1e3a8bc768",
                "subject": "BOUND_PROVIDER_CONTRACT_FAILURE_RECOVERY",
            },
            {
                "commit": "18b279f5ef6d2a4db693586a59de8d87d7b45ab5",
                "tree": "a6a1eb49e8ace5632c610ab7ee3028c9da0a86b5",
                "subject": "HARDEN_PROVIDER_CONTRACT_RECOVERY_BOUNDARY_AND_ISOLATED_CANARY_CANDIDATE",
            },
        ]
        or evidence.get("rule")
        != "PRESERVE_AS_INPUT_EVIDENCE_UNTIL_INTEGRATED_INSTALLED_AND_ACCEPTED_BY_THIS_CONTRACT"
    ):
        raise ContractError("historical M9/current r5 provider-schema evidence drift")

    axes = dialect.get("orthogonal_runtime_axes")
    if (
        not isinstance(axes, dict)
        or axes.get("response_enforcement")
        != ["provider_strict", "local_strict_json"]
        or axes.get("tool_mode") != ["disabled", "enabled"]
        or axes.get("independence_rule")
        != "RESPONSE_ENFORCEMENT_SELECTION_MUST_NOT_READ_OR_DERIVE_FROM_TOOL_MODE"
        or axes.get("required_cross_product_tests") != 4
        or set(axes.get("forbidden") or [])
        != {
            "DISABLE_RESPONSE_ENFORCEMENT_BECAUSE_TOOLS_ARE_ENABLED",
            "DISABLE_TOOLS_BECAUSE_LOCAL_STRICT_JSON_IS_SELECTED",
            "CLAIM_PROVIDER_STRICT_WHEN_NO_WIRE_SCHEMA_WAS_SENT",
        }
    ):
        raise ContractError("response-enforcement/tool-mode independence drift")

    compilation = dialect.get("schema_compilation_contract")
    expected_attestation_fields = [
        "workflow_manifest_hash",
        "pipeline_identity",
        "run_id",
        "plan_id",
        "incarnation_id",
        "phase",
        "canonical_schema_sha256",
        "canonical_schema_version",
        "dialect_compiler_id",
        "dialect_compiler_version",
        "dialect_compiler_source_sha256",
        "response_enforcement",
        "tool_mode",
        "provider",
        "profile",
        "model",
        "runtime_revision",
        "runtime_image_digest",
        "wire_schema_sha256_or_explicit_null",
        "wire_schema_size_or_zero",
        "wire_request_sha256",
        "provider_response_sha256",
        "canonical_validation_result",
        "canary_receipt_sha256_or_explicit_null",
    ]
    if (
        not isinstance(compilation, dict)
        or compilation.get("canonical_semantics")
        != "IMMUTABLE_PROVIDER_NEUTRAL_SCHEMA_BYTES"
        or compilation.get("compile_time")
        != "AFTER_PROVIDER_PROFILE_MODEL_AND_RUNTIME_RESOLUTION_BEFORE_PROVIDER_CALL"
        or compilation.get("semantic_rewrite") != "FORBIDDEN"
        or compilation.get("unsupported_provider_dialect_result")
        != "LOCAL_STRICT_JSON_AGAINST_UNCHANGED_CANONICAL_SCHEMA"
        or compilation.get("dynamic_map_phases")
        != ["finalize", "feedback", "loop_plan"]
        or compilation.get("dynamic_map_rule")
        != "PRESERVE_ARBITRARY_DECLARED_KEYS_AND_NESTED_VALUES_UNDER_CANONICAL_LOCAL_VALIDATION"
        or compilation.get("attestation_fields") != expected_attestation_fields
        or compilation.get("hash_rules")
        != {
            "canonical": "SHA256_OF_CANONICAL_PROVIDER_NEUTRAL_SCHEMA_BYTES",
            "wire": "SHA256_OF_EXACT_PROVIDER_BOUND_SCHEMA_BYTES_OR_EXPLICIT_NULL_FOR_LOCAL_STRICT_JSON",
            "compiler": "VERSION_PLUS_SOURCE_SHA256",
            "runtime": "FULL_SOURCE_REVISION_PLUS_IMMUTABLE_IMAGE_DIGEST",
            "readback": "CHILD_RECOMPUTES_ALL_HASHES_BEFORE_FIRST_PROVIDER_CALL",
        }
    ):
        raise ContractError("canonical/wire schema compilation attestation drift")

    repair = dialect.get("failure_and_repair_contract")
    typed = repair.get("typed_failure") if isinstance(repair, dict) else None
    calls = repair.get("one_call_rule") if isinstance(repair, dict) else None
    fixer = repair.get("fixer") if isinstance(repair, dict) else None
    retry = repair.get("post_repair_retry") if isinstance(repair, dict) else None
    dedupe = repair.get("restart_dedupe") if isinstance(repair, dict) else None
    if (
        not isinstance(typed, dict)
        or typed.get("error_kind") != "provider_contract"
        or typed.get("error_layer") != "schema_error"
        or typed.get("deterministic") is not True
        or typed.get("nonretryable") is not True
        or typed.get("fingerprint_inputs")
        != [
            "canonical_schema_sha256",
            "dialect_compiler_source_sha256",
            "provider",
            "profile",
            "model",
            "runtime_revision",
            "phase",
            "normalized_schema_error",
        ]
        or calls
        != {
            "phase_invocations_before_repair": 1,
            "provider_transport_calls": "ZERO_FOR_PRE_DISPATCH_COMPILER_ERROR_OTHERWISE_ONE_MAXIMUM",
            "automatic_model_or_provider_fallback_calls": 0,
            "generic_external_retry_calls": 0,
        }
    ):
        raise ContractError("deterministic schema-error one-call rule drift")
    if (
        not isinstance(fixer, dict)
        or fixer.get("launches_per_occurrence") != 1
        or fixer.get("requires")
        != [
            "CURRENT_OCCURRENCE_AND_STATE_VERSION",
            "EXACT_FAILURE_FINGERPRINT",
            "DURABLE_DELEGATION_PROVENANCE",
            "VALIDATED_MANAGED_MANIFEST",
            "LIVE_CHILD_AND_ATOMIC_CLAIM_TRANSFER",
            "BOUNDED_MUTATION_SCOPE_AND_BUDGET",
        ]
        or fixer.get("missing_or_ambiguous_requirement")
        != "ZERO_FIXER_FAIL_CLOSED_TO_ONE_DEDUPED_MANUAL_REVIEW"
        or retry
        != {
            "maximum": 1,
            "requires_exact_repair_commit_at_target_head": True,
            "requires_same_occurrence_phase_and_failure_fingerprint": True,
            "second_failure": "TERMINAL_MANUAL_REVIEW_NO_FALLBACK_NO_SECOND_FIXER_NO_SECOND_RETRY",
        }
    ):
        raise ContractError("singleton fixer/exactly-one post-repair retry drift")
    if (
        not isinstance(dedupe, dict)
        or dedupe.get("key_fields")
        != [
            "occurrence_id",
            "accepted_state_version",
            "phase",
            "failure_fingerprint",
        ]
        or dedupe.get("process_restart_host_restart_and_response_loss")
        != "PRESERVE_ONE_PHASE_ATTEMPT_ONE_FIXER_CLAIM_ONE_POST_REPAIR_RETRY"
        or dedupe.get("unchanged_poll_count") != 200
        or dedupe.get("successful_repair_notifications") != 0
        or dedupe.get("terminal_failed_repair_notifications") != 1
        or dedupe.get("claim_recovery")
        != "OWNER_CHECKED_COMPARE_AND_SWAP_NEVER_TIMEOUT_ONLY_RECLAIM"
    ):
        raise ContractError("schema-repair occurrence/claim/notification dedupe drift")

    canary = dialect.get("real_codex_canary")
    final_binding = (
        canary.get("final_candidate_binding") if isinstance(canary, dict) else None
    )
    if (
        not isinstance(canary, dict)
        or canary.get("surface")
        != "FRESH_INSTALLED_CLOUD_RUNTIME_WITH_REAL_CODEX_PROVIDER_CALL"
        or canary.get("model_family") != "CODEX"
        or final_binding
        != {
            "minimum_ancestor_commit": "18b279f5ef6d2a4db693586a59de8d87d7b45ab5",
            "minimum_ancestor_tree": "a6a1eb49e8ace5632c610ab7ee3028c9da0a86b5",
            "rejected_earlier_candidate": "b168edbca01388fbad55383f43c290476ff0feda",
            "successor_rule": "FINAL_CANDIDATE_MUST_EQUAL_18B_OR_HAVE_18B_AS_GIT_ANCESTOR",
            "exact_equality_rule": "FINAL_CANDIDATE_COMMIT_EQUALS_DEPLOYED_RUNTIME_COMMIT_EQUALS_CANARY_TESTED_COMMIT_EQUALS_CANARY_RECEIPT_COMMIT",
            "temporal_rule": "CANARY_RECEIPT_MUST_BE_CREATED_AFTER_EXACT_FINAL_CANDIDATE_DEPLOYMENT",
            "required_runtime_binding": [
                "final_candidate_commit",
                "final_candidate_tree",
                "deployed_runtime_commit",
                "runtime_image_digest",
                "canary_tested_commit",
                "canary_receipt_commit",
                "deployment_receipt_sha256",
                "canary_receipt_sha256",
            ],
        }
        or canary.get("fixtures")
        != [
            "CLOSED_SCHEMA_PROVIDER_STRICT_WITH_TOOLS_DISABLED",
            "CLOSED_SCHEMA_PROVIDER_STRICT_WITH_TOOLS_ENABLED",
            "DYNAMIC_FINALIZE_LOCAL_STRICT_JSON_WITH_TOOLS_DISABLED",
            "DYNAMIC_FINALIZE_LOCAL_STRICT_JSON_WITH_TOOLS_ENABLED",
            "DYNAMIC_FEEDBACK_KEYS_PRESERVED",
            "DYNAMIC_LOOP_PLAN_NESTED_KEYS_PRESERVED",
            "UNSUPPORTED_KEYWORD_MUTATION_FALLS_BACK_WITHOUT_SEMANTIC_REWRITE",
        ]
        or set(canary.get("required_proof") or [])
        != {
            "EXACT_COMMITTED_CANONICAL_SCHEMA_HASH",
            "EXACT_WIRE_SCHEMA_HASH_OR_EXPLICIT_NULL",
            "COMPILER_VERSION_AND_SOURCE_HASH",
            "PROVIDER_PROFILE_MODEL_RUNTIME_AND_IMAGE_BINDING",
            "ONE_PROVIDER_CALL_MAXIMUM",
            "RAW_RESPONSE_HASH",
            "CANONICAL_VALIDATION_PASS",
            "ZERO_UNDECLARED_FALLBACK",
            "CONTENT_ADDRESSED_CANARY_RECEIPT",
        }
    ):
        raise ContractError("real installed-cloud Codex canary drift")

    findings = dialect.get("isolated_canary_findings")
    prompt_finding = (
        findings.get("long_inline_prompt_path_probe")
        if isinstance(findings, dict)
        else None
    )
    usage_finding = (
        findings.get("ephemeral_codex_usage_provenance")
        if isinstance(findings, dict)
        else None
    )
    if (
        not isinstance(prompt_finding, dict)
        or prompt_finding.get("affected_seam")
        != "arnold_pipelines.megaplan.workers._impl._normalize_stdin_text"
        or prompt_finding.get("failure")
        != "PATH_IS_FILE_CAN_RAISE_OSERROR_ENAMETOOLONG_FOR_LONG_SINGLE_LINE_INLINE_PROMPT"
        or prompt_finding.get("required_behavior")
        != "CATCH_OSERROR_INCLUDING_ENAMETOOLONG_AROUND_PATH_PROBE_AND_RETURN_ORIGINAL_INLINE_PROMPT_BYTE_FOR_BYTE"
        or prompt_finding.get("do_not_mask")
        != "AFTER_A_REAL_FILE_IS_ESTABLISHED_A_READ_FAILURE_IS_TYPED_PROMPT_INPUT_UNAVAILABLE_NOT_INLINE_TEXT"
        or prompt_finding.get("required_tests")
        != [
            "REAL_OS_LONG_SINGLE_LINE_PROMPT_DOES_NOT_RAISE",
            "MONKEYPATCHED_PATH_IS_FILE_OSERROR_ENAMETOOLONG_RETURNS_ORIGINAL",
            "LONG_UNICODE_SINGLE_LINE_PROMPT_IS_BYTE_PRESERVED",
            "NEWLINE_INLINE_PROMPT_BYPASSES_PATH_PROBE",
            "REAL_SHORT_PROMPT_FILE_STILL_LOADS_EXACT_BYTES",
            "ESTABLISHED_PROMPT_FILE_READ_OSERROR_IS_TYPED_NOT_SILENTLY_REINTERPRETED",
        ]
    ):
        raise ContractError("long inline prompt ENAMETOOLONG canary finding drift")
    if (
        not isinstance(usage_finding, dict)
        or usage_finding.get("affected_seam")
        != "CODEX_EPHEMERAL_ROLLOUT_SESSION_USAGE_AND_COST_CAPTURE"
        or usage_finding.get("locate_order")
        != [
            "PARSE_EXACT_THREAD_OR_SESSION_ID_FROM_STRUCTURED_CLI_EVENTS",
            "LOOK_UP_EXACT_SESSION_ROLLOUT_UNDER_BOUND_CODEX_HOME",
            "CORRELATE_EPHEMERAL_ROLLOUT_BY_INVOCATION_ID_AND_BOUNDED_START_END_WINDOW",
            "READ_AND_HASH_EXACT_ROLLOUT_USAGE_AND_OBSERVED_MODEL",
        ]
        or usage_finding.get("located_required_fields")
        != [
            "usage_status_located",
            "session_or_thread_id",
            "rollout_path",
            "rollout_sha256",
            "observed_model",
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "pricing_status_priced_or_unpriced",
            "cost_usd",
            "provenance_source",
        ]
        or usage_finding.get("unavailable_required_fields")
        != [
            "usage_status_unavailable",
            "typed_reason",
            "invocation_id",
            "searched_codex_home",
            "searched_time_window",
            "session_id_observation",
            "rollout_observation",
            "cost_pricing_unavailable",
            "numeric_compatibility_cost_usd_zero_non_authoritative",
        ]
        or set(usage_finding.get("forbidden") or [])
        != {
            "SILENT_ZERO_DOLLAR_COST_WITHOUT_USAGE_STATUS",
            "CLAIM_ZERO_TOKENS_WHEN_USAGE_IS_UNAVAILABLE",
            "CLAIM_REQUESTED_MODEL_AS_OBSERVED_MODEL_WITHOUT_ROLLOUT",
            "SEARCH_UNBOUNDED_OR_AMBIENT_CODEX_HOMES",
            "ATTACH_ANOTHER_CONCURRENT_INVOCATIONS_ROLLOUT",
            "PERSIST_EPHEMERAL_SESSION_AS_REUSABLE_SESSION",
        }
        or usage_finding.get("required_tests")
        != [
            "EPHEMERAL_STRUCTURED_SESSION_ID_LOCATES_EXACT_ROLLOUT",
            "MISSING_SESSION_ID_USES_BOUNDED_INVOCATION_WINDOW_CORRELATION",
            "MISSING_ROLLOUT_EMITS_TYPED_UNAVAILABLE_NOT_SILENT_ZERO",
            "UNREADABLE_OR_MALFORMED_ROLLOUT_EMITS_TYPED_UNAVAILABLE",
            "UNPRICED_MODEL_WITH_USAGE_IS_DISTINCT_FROM_USAGE_UNAVAILABLE",
            "CONCURRENT_ROLLOUT_CANNOT_CROSS_BIND",
            "CRASH_RESTART_PRESERVES_USAGE_PROVENANCE_OR_TYPED_UNAVAILABLE",
        ]
    ):
        raise ContractError("ephemeral Codex usage/provenance canary finding drift")

    acceptance = dialect.get("cross_pipeline_acceptance")
    if (
        not isinstance(acceptance, dict)
        or acceptance.get("coverage")
        != "REGISTRY_CLOSED_EVERY_PRODUCTION_PIPELINE_MODEL_PHASE_PROVIDER_PROFILE_RUNTIME_AND_LAUNCH_ENTRYPOINT"
        or acceptance.get("surfaces")
        != ["SOURCE", "WHEEL", "INSTALLED", "CLOUD"]
        or acceptance.get("registry_rule")
        != "A_NEW_PRODUCTION_PIPELINE_PHASE_PROVIDER_PROFILE_OR_LAUNCHER_WITHOUT_SCHEMA_DIALECT_FIXTURES_FAILS_CI"
        or acceptance.get("required_mutations")
        != [
            "TOOL_MODE_TOGGLE",
            "RESPONSE_ENFORCEMENT_TOGGLE",
            "CANONICAL_SCHEMA_BYTE_CHANGE",
            "WIRE_SCHEMA_BYTE_CHANGE",
            "COMPILER_SOURCE_OR_VERSION_CHANGE",
            "UNSUPPORTED_KEYWORD_INSERTION",
            "DYNAMIC_MAP_KEY_INSERTION",
            "PROVIDER_PROFILE_MODEL_DRIFT",
            "RUNTIME_REVISION_OR_IMAGE_DRIFT",
            "PROVIDER_SCHEMA_REJECTION",
            "FIXER_LAUNCH_RESPONSE_LOSS",
            "POST_REPAIR_RETRY_RESPONSE_LOSS",
            "PROCESS_RESTART",
            "HOST_RESTART",
            "NOTIFICATION_RESPONSE_LOSS",
        ]
        or acceptance.get("final_candidate_canary_gate")
        != "REJECT_ANY_COMPLETION_MANIFEST_WHOSE_CANARY_COMMIT_DIFFERS_FROM_THE_EXACT_FINAL_DEPLOYED_18B_OR_SUCCESSOR_COMMIT"
        or acceptance.get("completion_evidence")
        != "evidence/critique-ledger-recovery/F2A/provider-schema-dialect-family/completion-manifest.json"
        or acceptance.get("independent_review_required") is not True
    ):
        raise ContractError("provider-schema cross-pipeline registry closure drift")


def _validate_provider_policy_binding_contract(
    policy: dict[str, Any], chain: dict[str, Any]
) -> None:
    if (
        policy.get("schema")
        != "arnold.cross_pipeline.provider_policy_execution_binding.v1"
        or policy.get("status") != "NORMATIVE_DESIGN_TARGET_NOT_RUNTIME_PROOF"
        or policy.get("owner_milestone")
        != "f2a-launch-profile-artifact-drift-containment"
        or policy.get("scope")
        != "ALL_REGISTERED_PRODUCTION_PIPELINES_AND_CHAIN_LAUNCHERS"
        or policy.get("difficulty") != "5/5 VERY HARD"
        or policy.get("dependencies")
        != [
            "f1-owner-storage-recovery-hardening",
            "f2-admission-model-effect-release-closure",
        ]
        or policy.get("blocks") != ["f3-cl2-real-work-and-publication"]
    ):
        raise ContractError("F2A provider-policy/binding identity drift")

    reuse = policy.get("reuse_contract")
    if (
        not isinstance(reuse, dict)
        or reuse.get("forbidden_architecture")
        != "NEW_MEGAPLAN_ONLY_AUTHORITY_PROVENANCE_BINDING_OR_WATCHDOG_PROTOCOL"
        or reuse.get("broader_missing_seam")
        != "NO_NEUTRAL_TYPED_CONTRACT_CURRENTLY_JOINS_WORKFLOW_IDENTITY_RESOLVED_PROVIDER_POLICY_EXACT_REMOTE_READBACK_BYTES_CHILD_LOADED_BYTES_AND_REPAIR_CUSTODY"
        or reuse.get("broader_missing_test")
        != "NO_REGISTRY_CLOSED_CONFORMANCE_TEST_PROVES_EVERY_PRODUCTION_PIPELINE_AND_LAUNCHER_USES_THAT_JOINED_CONTRACT"
        or len(reuse.get("required_neutral_authorities") or []) != 5
        or len(reuse.get("extract_not_duplicate") or []) != 2
    ):
        raise ContractError("F2A neutral authority/provenance reuse drift")

    intent = policy.get("intended_epic_map")
    intended = intent.get("milestones") if isinstance(intent, dict) else None
    chain_milestones = chain.get("milestones")
    if not isinstance(intended, list) or not isinstance(chain_milestones, list):
        raise ContractError("F2A intended milestone map missing")
    exact_chain_map = [
        {
            "label": row.get("label"),
            "profile": row.get("profile"),
            "vendor": row.get("vendor"),
            "depth": row.get("depth"),
        }
        for row in chain_milestones
        if isinstance(row, dict)
    ]
    exact_intended_map = [
        {
            "label": row.get("label"),
            "profile": row.get("profile"),
            "vendor": row.get("vendor"),
            "depth": row.get("depth"),
        }
        for row in intended
        if isinstance(row, dict)
    ]
    if exact_intended_map != exact_chain_map:
        raise ContractError("F2A intended milestone profile/provider map drift")
    resolutions = intent.get("resolved_phase_maps")
    if (
        intent.get("unexpected_substitution") != "TYPED_POLICY_DRIFT_NO_SPAWN"
        or intent.get("all_codex_rule")
        != "ALLOWED_ONLY_WHEN_THE_EXACT_APPROVED_MILESTONE_MAP_NAMES_AN_ALL_CODEX_PROFILE_AND_RESOLVES_TO_IT"
        or not isinstance(resolutions, dict)
        or set(resolutions)
        != {
            "partnered-3-codex-high-direct",
            "partnered-3-codex-medium-direct",
            "partnered-4-codex-high-direct",
            "partnered-5-codex-high-direct",
        }
        or any(row.get("resolution") not in resolutions for row in intended)
        or any(row.get("profile") == "all-codex" for row in intended)
    ):
        raise ContractError("F2A resolved provider-policy map drift")
    profile_inputs = {
        row["resolution"]: (row["profile"], row["vendor"], row["depth"])
        for row in intended
    }
    try:
        available_profiles = load_profiles(project_dir=ROOT)
        actually_resolved = {}
        for resolution_id, (profile_name, vendor, depth) in profile_inputs.items():
            phase_map = resolve_profile(profile_name, available_profiles)
            phase_map = apply_vendor_rewrite(phase_map, vendor)
            phase_map = apply_depth_rewrite(phase_map, depth)
            actually_resolved[resolution_id] = apply_deepseek_provider_rewrite(
                phase_map, "direct"
            )
    except Exception as exc:
        raise ContractError(f"F2A profile resolver failed closed: {exc}") from exc
    if actually_resolved != resolutions:
        raise ContractError("F2A committed phase map differs from current resolver")

    preflight = policy.get("preflight_contract")
    launch = policy.get("launch_contract")
    watchdog = policy.get("watchdog_contract")
    notification = policy.get("notification_contract")
    tests = policy.get("all_pipeline_test_contract")
    if (
        not isinstance(preflight, dict)
        or preflight.get("order")
        != [
            "LOAD_INTENT",
            "RESOLVE_EVERY_MILESTONE",
            "COMPARE_EXACT_MAP",
            "CHECK_CREDENTIAL_CAPABILITIES",
            "SEAL_POLICY_DIGEST",
        ]
        or "SILENT_ALL_CODEX_SUBSTITUTION" not in preflight.get("forbidden", [])
    ):
        raise ContractError("F2A preflight order/refusal drift")
    if (
        not isinstance(launch, dict)
        or launch.get("order")
        != [
            "CANONICALIZE_BUNDLE",
            "UPLOAD_CONTENT_ADDRESSED_TEMP",
            "FSYNC_AND_ATOMIC_PUBLISH",
            "READ_BACK_EXACT_REMOTE_BYTES",
            "VERIFY_SIZE_AND_SHA256",
            "PERSIST_EXECUTION_BINDING",
            "SPAWN_FROM_BOUND_REMOTE_OBJECT",
            "CHILD_REVERIFY_BEFORE_PROVIDER_CALL",
        ]
        or launch.get("spawn_gate")
        != "NO_PROCESS_SPAWN_BEFORE_DURABLE_REMOTE_READBACK_BINDING"
        or launch.get("provider_gate")
        != "NO_PROVIDER_CALL_BEFORE_CHILD_ATTESTS_LOADED_BYTES_AND_RESOLVED_MAP"
    ):
        raise ContractError("F2A remote-byte launch binding drift")
    if (
        not isinstance(watchdog, dict)
        or watchdog.get("relaunch_limit") != 1
        or watchdog.get("relaunch_key_fields")
        != ["occurrence_id", "intended_map_digest", "remote_bundle_digest"]
        or watchdog.get("rollback")
        != "LAST_APPROVED_STILL_ADMISSIBLE_PROFILE_MAP_AND_REMOTE_BINDING_ONLY"
        or "TARGET_CGROUP_AND_PID_START_IDENTITY"
        not in watchdog.get("containment_order", [])
    ):
        raise ContractError("F2A bounded watchdog repair drift")
    if (
        not isinstance(notification, dict)
        or notification.get("notify_on_initial_detection") is not False
        or notification.get("successful_automatic_repair_notifications") != 0
        or notification.get("failed_bounded_repair_notifications") != 1
        or notification.get("notify_after")
        != "CONTAINMENT_OR_ROLLBACK_OR_SINGLE_RELAUNCH_FAILS_IS_UNSAFE_OR_EXHAUSTS"
    ):
        raise ContractError("F2A failure-only notification drift")
    if (
        not isinstance(tests, dict)
        or tests.get("coverage")
        != "REGISTRY_CLOSED_EVERY_PRODUCTION_PIPELINE_CHAIN_AND_LAUNCH_ENTRYPOINT"
        or tests.get("surfaces") != ["SOURCE", "WHEEL", "INSTALLED", "CLOUD"]
        or "ZERO_UNREGISTERED_PRODUCTION_LAUNCHERS"
        not in tests.get("required_assertions", [])
    ):
        raise ContractError("F2A all-pipeline conformance drift")


def _validate_m11_acceptance_dependency_gap(evidence: dict[str, Any]) -> None:
    historical = evidence.get("historical_promotion")
    if (
        evidence.get("schema")
        != "arnold.critique_ledger.m11_acceptance_dependency_gap.v1"
        or evidence.get("captured_on") != "2026-08-03"
        or evidence.get("authority")
        != "READ_ONLY_GIT_AND_COMMITTED_EVIDENCE_AUDIT"
        or not isinstance(historical, dict)
        or historical.get("commit")
        != "d10b0fef2b6dbc283639ca14adf6790153ebd2a6"
        or historical.get("tree")
        != "f1938d0de2127226ba23a0a48a6130ca0528ed52"
        or historical.get("parent")
        != "88f1f39c8f06832e155501ff13dd4e00a1522f94"
        or historical.get("current_authority")
        != "INVALIDATED_PENDING_DEPENDENCY_CLOSED_REVALIDATION"
        or historical.get("authority_scope")
        != "THIS_EPIC_REFUSES_CONSUMPTION_NOW_APPEND_ONLY_RUN_AUTHORITY_SUPERSESSION_IS_A_PENDING_P0_ACTION"
        or historical.get("history_rule")
        != "APPEND_SUPERSEDING_RUN_AUTHORITY_DECISION_NEVER_REWRITE_OR_DELETE_THE_HISTORICAL_COMMIT"
    ):
        raise ContractError("M11 historical promotion invalidation drift")

    blocking = evidence.get("unconsumed_blocking_evidence")
    ownership = blocking.get("ownership_decision_record") if isinstance(blocking, dict) else None
    fault_index = blocking.get("f01_f17_completion_index") if isinstance(blocking, dict) else None
    if (
        not isinstance(ownership, dict)
        or ownership.get("path") != "evidence/ownership-decision-record.json"
        or ownership.get("sha256_at_promoted_commit")
        != "aea9ba9c5e9f5f753d8d962af2c6d9e038968184b6e3b1c26b461610c13888fc"
        or ownership.get("blocker_count") != 4
        or ownership.get("global_blocker_ids")
        != [
            "OWNERSHIP-BLOCKER-001",
            "OWNERSHIP-BLOCKER-002",
            "OWNERSHIP-BLOCKER-003",
            "OWNERSHIP-BLOCKER-004",
        ]
        or ownership.get("m11_blocking_ids")
        != ["OWNERSHIP-BLOCKER-001", "OWNERSHIP-BLOCKER-003"]
        or not isinstance(fault_index, dict)
        or fault_index.get("path") != "evidence/f01-f17-completion-index.json"
        or fault_index.get("sha256_at_promoted_commit")
        != "20cbef1a1e1d4c4cca5667ebbf9c3d39a79ea1e1a5fefb783e1a44b29dda598c"
        or fault_index.get("provisional") is not True
        or fault_index.get("scenarios_completed_count") != 17
        or fault_index.get("scenarios_action_off_count") != 17
        or fault_index.get("classification")
        != "PROVISIONAL_ACTION_OFF_IS_NOT_LIVE_COMPLETION_PROOF"
    ):
        raise ContractError("M11 committed blocker/provisional evidence drift")
    if (
        _sha256(ROOT / ownership["path"])
        != ownership["sha256_at_promoted_commit"]
        or _sha256(ROOT / fault_index["path"])
        != fault_index["sha256_at_promoted_commit"]
    ):
        raise ContractError("M11 bound evidence file hash drift")

    gap = evidence.get("acceptance_consumption_gap")
    required_omissions = [
        "evidence/ownership-decision-record.json",
        "evidence/f01-f17-completion-index.json",
    ]
    if (
        not isinstance(gap, dict)
        or gap.get("acceptance_generator_sha256_at_promoted_commit")
        != "666bc0adfe0a7962b035f225f86fe3cc509d05b64001eb0fde12c477524820d3"
        or gap.get("m11_acceptance_module_sha256_at_promoted_commit")
        != "a0a586c1f1258c55c702f45a5d60682ed18cbf3c9780a5ee73b691b36bd441d0"
        or gap.get("fixed_acceptance_evidence_names")
        != [
            "full_suite",
            "no_debt",
            "runtime",
            "audit",
            "genuine_block",
            "recovery",
            "route",
            "wbc",
        ]
        or gap.get("required_but_unconsumed_paths") != required_omissions
        or gap.get("root_defect")
        != "ACCEPTANCE_WAS_NOT_DEPENDENCY_CLOSED_GREEN_LOCAL_AGGREGATES_COULD_PROMOTE_WHILE_AUTHORITATIVE_PREDECESSOR_BLOCKERS_REMAINED"
    ):
        raise ContractError("M11 acceptance-consumption gap drift")
    if (
        _sha256(ROOT / gap["acceptance_generator_path"])
        != gap["acceptance_generator_sha256_at_promoted_commit"]
        or _sha256(ROOT / gap["m11_acceptance_module_path"])
        != gap["m11_acceptance_module_sha256_at_promoted_commit"]
    ):
        raise ContractError("M11 acceptance source hash drift")

    revalidation = evidence.get("dependency_closed_revalidation")
    automation = evidence.get("automatic_repair_hold")
    required_revalidation = [
        "OWNERSHIP_DECISION_BLOCKER_COUNT_ZERO_AND_EVERY_PREDECESSOR_DEPENDENCY_ACCEPTED",
        "F01_F17_EACH_HAS_NON_PROVISIONAL_ACTION_ON_CONTROLLED_LIVE_PROOF_OR_AN_EXPLICITLY_INAPPLICABLE_NEGATIVE_CONTROL",
        "NO_ACTION_OFF_SHADOW_OR_SYNTHETIC_STATUS_MAY_SUBSTITUTE_FOR_LIVE_PROOF",
        "EVERY_RECEIPT_BINDS_EXACT_CANDIDATE_HEAD_TREE_SOURCE_RUNTIME_AND_EVIDENCE_FILE_SHA256",
        "CONTROLLED_LIVE_CANARY_PROVES_ONE_ADMITTED_EFFECT_AND_NEGATIVE_CONTROLS_PROVE_ZERO_BYPASS_DUPLICATE_OR_UNOWNED_EFFECTS",
        "INDEPENDENT_VERIFIER_REREADS_CURRENT_RUN_AUTHORITY_CUSTODY_WBC_AND_BOUND_SOURCE_BYTES",
        "A_NEW_CONTENT_ADDRESSED_COMPLETION_MANIFEST_CONSUMES_BOTH_FORMERLY_OMITTED_FILES_AND_ALL_DEPENDENCIES",
    ]
    if (
        not isinstance(revalidation, dict)
        or revalidation.get("owner_milestone")
        != "f1-owner-storage-recovery-hardening"
        or revalidation.get("gate") != "P0_REQUIRED_BEFORE_F1_ACCEPTANCE"
        or revalidation.get("authority_reuse")
        != [
            "EXISTING_RUN_AUTHORITY_APPEND_ONLY_DECISION",
            "EXISTING_CUSTODY_AND_WBC_ATTEMPT_EFFECT_RECORDS",
            "EXISTING_M11_ACCEPTANCE_AND_PROOF_MAP_SURFACES",
        ]
        or revalidation.get("forbidden_silo")
        != "NO_NEW_M11_STATUS_STORE_PROJECTION_OR_PARALLEL_ACCEPTANCE_AUTHORITY"
        or revalidation.get("requirements") != required_revalidation
        or not isinstance(automation, dict)
        or automation.get("state")
        != "DISABLED_FAIL_CLOSED_UNTIL_REVALIDATION_GREEN"
        or automation.get("forbidden_reenablements")
        != [
            "LEGACY_REPAIR_LOOP",
            "MANAGED_CHILD_AUTOMATIC_REPAIR",
            "WATCHDOG_DIRECT_REPAIR_FALLBACK",
            "META_REPAIR_LOOP",
        ]
        or automation.get("release_gate")
        != "EXACT_DEPENDENCY_CLOSED_M11_REVALIDATION_COMPLETION_MANIFEST_AND_SUPERSEDING_RUN_AUTHORITY_DECISION"
        or automation.get("manual_or_projection_override") != "FORBIDDEN"
    ):
        raise ContractError("M11 dependency-closed revalidation/automation hold drift")


def _validate_supersession(*, require_live: bool) -> None:
    index = _load_json(INITIATIVE / "supersession-index.json")
    if index.get("schema") != "arnold.critique_ledger.supersession_index.v2":
        raise ContractError("supersession index schema drift")
    current_generation = index.get("current_operational_generation")
    handoff_path = INITIATIVE / "current-operational-handoff.json"
    if (
        not isinstance(current_generation, dict)
        or current_generation.get("path")
        != ".megaplan/initiatives/critique-ledger-post-relaunch-completion/current-operational-handoff.json"
        or current_generation.get("sha256") != _sha256(handoff_path)
        or current_generation.get("status") != "RUNNING_OBSERVATION_DEGRADED"
        or current_generation.get("launch_authority") != "SEPARATELY_AUTHORIZED_R5"
        or current_generation.get("follow_up_disposition")
        != "BLOCKED_ON_R5_CHAIN_COMPLETION_MANIFEST"
    ):
        raise ContractError("current operational generation supersession drift")
    operation_rows = index.get("operation_supersession")
    if not isinstance(operation_rows, list) or [
        (row.get("operation_id"), row.get("superseded_by")) for row in operation_rows if isinstance(row, dict)
    ] != [
        ("critique-ledger-capacity-reserve-remediation-20260803-0349z", "critique-ledger-capacity-reserve-fallback-20260803-0350z"),
        ("critique-ledger-failed-build-capacity-reset-20260803-0400z", "critique-ledger-failed-build-capacity-reset-corrected-20260803-0404z"),
    ]:
        raise ContractError("operation supersession index drift")
    attempts = index.get("prelaunch_attempt_supersession")
    known_ids = [row[0] for row in KNOWN_ATTEMPTS]
    if (
        not isinstance(attempts, dict)
        or attempts.get("ordered_rejected_attempts") != known_ids
        or attempts.get("passing_successor") != "B44-production-acceptance-smoke"
        or attempts.get("pending_successor") is not None
        or attempts.get("terminal_failed_misclassified") != "B44-live-attempt-14"
        or attempts.get("terminal_infrastructure_failure") != "B15-live-attempt-15"
        or attempts.get("terminal_infrastructure_recovery_product_nonproceed")
        != "B16-live-attempt-16"
        or attempts.get("infrastructure_recovery_proof") != "PASSED"
        or attempts.get("durable_epic_launch") != "NOT_PRODUCED"
        or attempts.get("relaunch_disposition")
        != "NOT_BLOCKED_BY_DEFERRED_PRODUCT_OR_BROADER_SYSTEMIC_HARDENING"
        or attempts.get("future_execution_authority")
        != "FRESH_EXPLICIT_AUTHORITY_REQUIRED"
        or attempts.get("terminal_safe_nonproceed") != "B39-live-attempt-13"
        or attempts.get("closed_decision") != "A40"
        or attempts.get("rule") != "SUPERSESSION_PRESERVES_FAILURE_EVIDENCE_AND_NEVER_IMPLIES_SUCCESS"
    ):
        raise ContractError("attempt supersession index drift")
    accepted = attempts.get("accepted_successor")
    if accepted == B26_PASS["id"]:
        if attempts.get("status") != "B39_TERMINAL_SAFE_NONPROCEED_A40_CLOSED_B44_ATTEMPT_14_TERMINAL_FAILED_MISCLASSIFIED_A15_B15_ATTEMPT_15_TERMINAL_INFRASTRUCTURE_FAILURE_B16_ATTEMPT_16_INFRASTRUCTURE_RECOVERY_PASSED_PRODUCT_GATE_NOT_PROCEED":
            raise ContractError("latest terminal failure disposition drift")
    elif accepted != "B44-production-acceptance-smoke" or attempts.get("status") != "ACCEPTED_STRICTLY_LATER_SMOKE":
        raise ContractError("invalid accepted smoke successor")


def _validate_runbook() -> None:
    runbook = (INITIATIVE / "RUNBOOK.md").read_text(encoding="utf-8")
    required = [
        "do not use ordinary `cloud deploy`, `cloud chain`,",
        "`cloud supervise`",
        "Never redispatch",
        "Hard NO-GO default",
        "F0 may write only its admission manifest",
        "generic command is not a fallback",
    ]
    if any(text not in runbook for text in required):
        raise ContractError("incident runbook lost a fail-closed route rule")


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
    if require_live:
        digest_paths = {
            "built_image_smoke": STABLE_EXIT_PROOFS[0],
            "prelaunch_receipts_manifest": STABLE_EXIT_PROOFS[1],
            "conformance": STABLE_EXIT_PROOFS[2],
            "completion": STABLE_EXIT_PROOFS[3],
            "terminal_stop": ".megaplan/initiatives/critique-ledger-safe-v3-canary/terminal-stop-receipt.json",
            "fresh_clone_reconstruction": STABLE_EXIT_PROOFS[5],
        }
        for name, relative in digest_paths.items():
            proof_path = _repo_path(relative)
            if not proof_path.is_file() or _sha256(proof_path) != digests[name]:
                raise ContractError(f"stable-exit proof digest mismatch: {name}")


def validate(*, require_live: bool = False) -> None:
    custody = _load_json(INITIATIVE / "custody-manifest.json")
    if custody.get("schema") != "arnold.critique_ledger.unfinished_work_custody.v4":
        raise ContractError("custody manifest schema must be v4")
    _validate_obligations(custody)
    # The safe-v3 canary lineage is immutable history after the r5 recut. Its
    # absent terminal receipt paths must not decide current launch readiness.
    _validate_attempt_history(custody, require_live=False)
    _validate_schema_access_recovery_history(custody, require_live=False)
    _validate_current_canary_lineage(custody, require_live=False)
    _validate_attempt_14_prelaunch(custody)
    _validate_attempt_15_prelaunch(custody)
    _validate_attempt_16_terminal(custody)
    _validate_v3_relaunch_precursor(custody)
    _validate_attempt_14_outcome_and_runtime_contract(custody)
    _validate_storage_root_cause_follow_up(custody)
    _validate_live_deploy_attempts(custody)
    _validate_live_canary_attempts(custody)
    _validate_prelaunch_gates(custody, require_live=False)
    _validate_host_control_state_contract(custody)
    reconciliation = custody.get("live_operation_reconciliation")
    if reconciliation != {
        "path": ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json",
        "sha256": "9cf695c56250738f3dd67cc269aa220449b6636c7c6ee990ce79f1a8dd29c23b",
        "status": "PENDING_REMOTE_RECEIPT_IMPORT_AND_INDEPENDENT_RECONCILIATION",
        "launch_disposition": "HARD_NO_GO",
        "immutable_intent_count": 5,
        "rule": "DO_NOT_REWRITE_INTENTS_OR_REDISPATCH_AMBIGUOUS_OPERATIONS",
    }:
        if not (
            isinstance(reconciliation, dict)
            and set(reconciliation) == {"path", "sha256", "status", "launch_disposition", "immutable_intent_count", "rule"}
            and reconciliation.get("path") == ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json"
            and reconciliation.get("status") == "ACCEPTED"
            and reconciliation.get("launch_disposition") == "ADMITTED_BY_F0"
            and reconciliation.get("immutable_intent_count") == 5
            and reconciliation.get("rule") == "DO_NOT_REWRITE_INTENTS_OR_REDISPATCH_AMBIGUOUS_OPERATIONS"
            and SHA256.fullmatch(str(reconciliation.get("sha256")))
            and _sha256(INITIATIVE / "evidence/operation-reconciliation-manifest.json")
            == reconciliation.get("sha256")
        ):
            raise ContractError("custody operation reconciliation pointer drift")
    if _sha256(INITIATIVE / "evidence/operation-reconciliation-manifest.json") != reconciliation.get("sha256"):
        raise ContractError("custody operation reconciliation hash mismatch")
    _validate_operation_reconciliation(require_live=False)
    route_path = INITIATIVE / "finite-canary-operational-route.json"
    _validate_route(_load_json(route_path))
    proof_map = _load_json(INITIATIVE / "proof-map.json")
    _validate_r5_repair_control_incident(
        _load_json(INITIATIVE / "evidence/r5-cl2-repair-control-incident-20260803.json")
    )
    _validate_m11_acceptance_dependency_gap(
        _load_json(INITIATIVE / M11_ACCEPTANCE_GAP_EVIDENCE)
    )
    _validate_r5_cross_container_liveness_observer_defect(
        _load_json(INITIATIVE / CROSS_CONTAINER_LIVENESS_EVIDENCE)
    )
    _validate_r5_m7_runtime_rebind_projection_cursor_mismatch(
        _load_json(INITIATIVE / M7_RUNTIME_REBIND_PROJECTION_EVIDENCE)
    )
    _validate_escalation_sidecar_path_normalization_migration_contract(
        _load_json(INITIATIVE / ESCALATION_SIDECAR_PATH_CONTRACT)
    )
    _validate_finalize_output_artifact_handoff_shared_retry_contract(
        _load_json(INITIATIVE / FINALIZE_OUTPUT_HANDOFF_RETRY_CONTRACT)
    )
    _validate_artifact_archival_projection_cleanup_contract(
        _load_json(INITIATIVE / ARTIFACT_ARCHIVAL_PROJECTION_CONTRACT)
    )
    chain_path = INITIATIVE / "chain.yaml"
    chain = yaml.safe_load(chain_path.read_text(encoding="utf-8"))
    if not isinstance(chain, dict):
        raise ContractError("chain.yaml must contain a mapping")
    _validate_provider_policy_binding_contract(
        _load_json(INITIATIVE / PROVIDER_POLICY_BINDING_CONTRACT), chain
    )
    _validate_provider_schema_dialect_family_contract(
        _load_json(INITIATIVE / PROVIDER_SCHEMA_DIALECT_CONTRACT)
    )
    try:
        parsed_chain = load_spec(chain_path)
    except Exception as exc:
        raise ContractError(f"installed chain parser rejected chain.yaml: {exc}") from exc
    _validate_chain_and_proof_map(chain, proof_map)
    _validate_supersession(require_live=False)
    _validate_runbook()
    _validate_readme(route_path)
    _validate_stable_exit_receipt(require_live=False)
    if require_live:
        try:
            validate_launch_preconditions(parsed_chain, ROOT, chain_path)
        except Exception as exc:
            raise ContractError(
                f"current r5 chain-completion launch precondition failed: {exc}"
            ) from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    validate(require_live=args.require_live)
    print("critique-ledger follow-up contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
