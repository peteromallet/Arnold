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
    if "evidence/critique-ledger-recovery/T0.3/resident-availability/completion-manifest.json" not in proof_map.get(
        "f1-owner-storage-recovery-hardening", []
    ):
        raise ContractError("resident availability proof map drift")
    if proof_map.get("finite-canary-stable-exit") != STABLE_EXIT_PROOFS:
        raise ContractError("stable-exit proof map drift")
    if proof_map.get("finite-canary-prelaunch-history") != [
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/operation-reconciliation-manifest.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/custody-manifest.json",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/UNFINISHED_WORK.md",
        ".megaplan/initiatives/critique-ledger-post-relaunch-completion/RUNBOOK.md",
    ]:
        raise ContractError("prelaunch history proof map drift")


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
    chain_path = INITIATIVE / "chain.yaml"
    chain = yaml.safe_load(chain_path.read_text(encoding="utf-8"))
    if not isinstance(chain, dict):
        raise ContractError("chain.yaml must contain a mapping")
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
